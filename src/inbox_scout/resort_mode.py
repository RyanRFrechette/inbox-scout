"""Read-only Resort Mode: scan InboxScout-labeled emails and flag mismatches.

Never modifies Gmail. Always uses readonly token.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from inbox_scout.autopilot_cleanup import _pick_inboxscout_label, CATEGORY_TO_LABEL  # noqa: F401
from inbox_scout.paths import LATEST_RESORT_PLAN

INBOX_SCOUT_PREFIX = "InboxScout/"
RESORT_SCAN_PAGE_SIZE = 100   # Messages per Gmail API page (max 500)
RESORT_MAX_SCAN_TOTAL = 2000  # Hard cap: total emails scanned per account per run
_RISK_THRESHOLD = 30
_PROGRESS_INTERVAL = 250      # Send progress every N actual emails processed
_PROGRESS_LABEL_INTERVAL = 25 # Also send progress every N labels (fallback when emails are sparse)

# Labels that are manual-review buckets — never flag as mismatches
_SKIP_CURRENT_LABELS = frozenset({
    "InboxScout/Review",
    "InboxScout/Protected Review",
})


def _get_service(account: str):
    from inbox_scout.gmail_auth import get_gmail_service
    return get_gmail_service(mode="readonly", account=account)


def _fetch_labeled_emails(service, label_name: str, remaining_cap: int) -> list[dict]:
    """Fetch message metadata for a label, paginating until cap or no more pages."""
    result: list[dict] = []
    page_token = None
    while remaining_cap > 0:
        try:
            kwargs: dict = {
                "userId": "me",
                "q": f'label:"{label_name}"',
                "maxResults": min(RESORT_SCAN_PAGE_SIZE, remaining_cap),
            }
            if page_token:
                kwargs["pageToken"] = page_token
            resp = service.users().messages().list(**kwargs).execute()
        except Exception:
            break

        messages = resp.get("messages", [])
        if not messages:
            break

        for msg in messages:
            if remaining_cap <= 0:
                break
            try:
                detail = service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()
                hdrs = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
                result.append({
                    "message_id": msg["id"],
                    "from": hdrs.get("From", ""),
                    "subject": hdrs.get("Subject", "(no subject)"),
                    "date": hdrs.get("Date", ""),
                    "snippet": detail.get("snippet", ""),
                })
                remaining_cap -= 1
            except Exception:
                pass

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return result


def build_resort_candidates(classified_emails: list[dict], current_label: str) -> tuple[list[dict], dict]:
    """
    Given classified emails (output of classify_for_report) and their current label,
    return (mismatches, skip_counts). Pure logic — no Gmail calls.
    """
    mismatches: list[dict] = []
    skips = {"protected": 0, "manual_review": 0, "high_risk": 0, "review_label": 0}

    if current_label in _SKIP_CURRENT_LABELS:
        skips["review_label"] += len(classified_emails)
        return mismatches, skips

    for item in classified_emails:
        ai = item.get("ai_classification", {})
        risk = int(ai.get("risk_score") or 0)
        manual = bool(ai.get("manual_review"))
        protected = bool(ai.get("protected") or item.get("protected"))

        if protected:
            skips["protected"] += 1
            continue
        if manual:
            skips["manual_review"] += 1
            continue
        if risk > _RISK_THRESHOLD:
            skips["high_risk"] += 1
            continue

        # Build lookup dict that _pick_inboxscout_label expects (category + sender context)
        lookup = {
            "category": ai.get("category", ""),
            "from": item.get("from", ""),
            "subject": item.get("subject", ""),
            "snippet": item.get("snippet", ""),
        }
        recommended = _pick_inboxscout_label(lookup)
        if recommended == current_label:
            continue

        mismatches.append({
            "message_id": item.get("message_id", ""),
            "subject": item.get("subject", ""),
            "from": item.get("from", ""),
            "current_label": current_label,
            "recommended_label": recommended,
            "recommended_category": ai.get("category", ""),
            "risk_score": risk,
            "manual_review": manual,
        })

    return mismatches, skips


def _scan_one_account(account: str, on_progress=None, on_log=None) -> dict:
    """Scan all InboxScout labels for one account. Returns plan dict. No Gmail writes."""
    from inbox_scout.report_mode import classify_for_report

    def _notify(msg: str) -> None:
        if on_progress is None:
            return
        try:
            on_progress(msg)
        except Exception:
            pass

    def _log(msg: str) -> None:
        if on_log is None:
            return
        try:
            on_log(msg)
        except Exception:
            pass

    try:
        service = _get_service(account)
        results = service.users().labels().list(userId="me").execute()
        all_labels = results.get("labels", [])
    except Exception as e:
        return {
            "account": account, "error": str(e), "mismatches": [], "scanned": 0,
            "total_in_library": 0, "total_to_scan": 0,
        }

    inbox_scout_labels = [
        lbl["name"]
        for lbl in all_labels
        if lbl["name"].startswith(INBOX_SCOUT_PREFIX)
    ]

    label_msg_counts = {lbl["name"]: lbl.get("messagesTotal", 0) for lbl in all_labels}
    total_in_library = sum(label_msg_counts.get(n, 0) for n in inbox_scout_labels)
    n_labels = len(inbox_scout_labels)

    if n_labels > 0:
        _log(f"[resort] {account}: scanning {n_labels} InboxScout label{'s' if n_labels != 1 else ''}")

    all_mismatches: list[dict] = []
    total_scanned = 0
    total_skips = {"protected": 0, "manual_review": 0, "high_risk": 0, "review_label": 0}
    _last_email_bucket = 0
    _last_label_bucket = 0
    remaining_cap = RESORT_MAX_SCAN_TOTAL

    for label_idx, label_name in enumerate(inbox_scout_labels, start=1):
        if remaining_cap <= 0:
            break
        emails = _fetch_labeled_emails(service, label_name, remaining_cap=remaining_cap)
        if not emails:
            continue
        remaining_cap -= len(emails)
        classified = classify_for_report(emails)
        total_scanned += len(classified)
        mismatches, skips = build_resort_candidates(classified, label_name)
        all_mismatches.extend(mismatches)
        for k in total_skips:
            total_skips[k] += skips.get(k, 0)

        label_short = label_name[len(INBOX_SCOUT_PREFIX):]
        found_so_far = len(all_mismatches)
        _log(
            f"[resort] {account} [{label_idx}/{n_labels}] {label_short} — "
            f"{total_scanned} emails, {found_so_far} correction{'s' if found_so_far != 1 else ''}"
        )

        # Trigger on actual email milestone OR label milestone (never depends on messagesTotal)
        email_bucket = total_scanned // _PROGRESS_INTERVAL
        label_bucket = label_idx // _PROGRESS_LABEL_INTERVAL
        if email_bucket > _last_email_bucket or label_bucket > _last_label_bucket:
            _last_email_bucket = email_bucket
            _last_label_bucket = label_bucket
            _notify(f"Resort progress: {total_scanned} emails — {label_idx}/{n_labels} labels")

    capped = remaining_cap <= 0

    if n_labels > 0:
        found = len(all_mismatches)
        cap_note = f" (cap: {RESORT_MAX_SCAN_TOTAL})" if capped else ""
        _notify(
            f"Resort scan complete — {account}: {total_scanned} scanned{cap_note}, "
            f"{found} correction{'s' if found != 1 else ''} found"
        )
        _log(
            f"[resort] {account}: done — {total_scanned} scanned"
            + (f" (capped at {RESORT_MAX_SCAN_TOTAL})" if capped else "")
            + f", {found} correction{'s' if found != 1 else ''} found"
        )

    return {
        "account": account,
        "scanned": total_scanned,
        "total_in_library": total_in_library,
        "capped": capped,
        "mismatches": all_mismatches,
        "skipped_protected": total_skips["protected"],
        "skipped_manual_review": total_skips["manual_review"],
        "skipped_high_risk": total_skips["high_risk"],
        "skipped_review_label": total_skips["review_label"],
    }


def _format_account_preview(plan: dict) -> str:
    acct = plan.get("account", "?")
    label = "Primary email" if acct == "primary" else "Second email"
    err = plan.get("error")
    if err:
        return f"{label}: couldn't connect ({err})"

    scanned = plan.get("scanned", 0)
    mismatches = plan.get("mismatches", [])
    skipped_total = (
        plan.get("skipped_protected", 0)
        + plan.get("skipped_manual_review", 0)
        + plan.get("skipped_high_risk", 0)
        + plan.get("skipped_review_label", 0)
    )

    if scanned == 0:
        return f"{label}: no InboxScout emails found."

    lines = [f"{label} — scanned {scanned} emails"]

    if not mismatches:
        lines.append("Everything looks correctly sorted.")
    else:
        suffix = "email looks" if len(mismatches) == 1 else "emails look"
        lines.append(f"{len(mismatches)} {suffix} like they may be in the wrong folder:")
        for m in mismatches[:10]:
            short_subj = (m.get("subject") or "(no subject)")[:55]
            cur = m["current_label"][len(INBOX_SCOUT_PREFIX):]
            rec = m["recommended_label"][len(INBOX_SCOUT_PREFIX):]
            lines.append(f'  • [{cur}] "{short_subj}" → {rec}')
        if len(mismatches) > 10:
            lines.append(f"  ...and {len(mismatches) - 10} more")

    if skipped_total:
        lines.append(
            f"{skipped_total} skipped (protected, manual-review, or high-risk — never auto-moved)."
        )

    return "\n".join(lines)


def build_resort_preview_message(account: str = "both") -> str:
    """
    Read-only resort preview. Scans InboxScout-labeled emails, reclassifies,
    and reports mismatches. Never modifies Gmail.
    """
    if account in ("both", "unspecified"):
        plans = [_scan_one_account("primary", on_log=print), _scan_one_account("secondary", on_log=print)]
    elif account == "primary":
        plans = [_scan_one_account("primary", on_log=print)]
    else:
        plans = [_scan_one_account("secondary", on_log=print)]

    combined = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "account_scope": account,
        "confirmed": False,
        "plans": plans,
    }
    LATEST_RESORT_PLAN.parent.mkdir(parents=True, exist_ok=True)
    LATEST_RESORT_PLAN.write_text(json.dumps(combined, indent=2), encoding="utf-8")

    parts = [_format_account_preview(p) for p in plans]
    body = "\n\n".join(parts)

    total_mismatches = sum(len(p.get("mismatches", [])) for p in plans)
    footer = "\n\nRead-only. Nothing was changed."
    if total_mismatches:
        footer += '\n\nSay "apply resort" to move them when you\'re ready.'

    return body + footer
