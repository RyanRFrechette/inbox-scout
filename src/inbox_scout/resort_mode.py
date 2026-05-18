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
CAP_PER_LABEL = 10  # Max messages to fetch per label per account
_RISK_THRESHOLD = 30

# Labels that are manual-review buckets — never flag as mismatches
_SKIP_CURRENT_LABELS = frozenset({
    "InboxScout/Review",
    "InboxScout/Protected Review",
})


def _get_service(account: str):
    from inbox_scout.gmail_auth import get_gmail_service
    return get_gmail_service(mode="readonly", account=account)


def _fetch_labeled_emails(service, label_name: str) -> list[dict]:
    """Fetch up to CAP_PER_LABEL message metadata for a given InboxScout label."""
    try:
        resp = service.users().messages().list(
            userId="me",
            q=f'label:"{label_name}"',
            maxResults=CAP_PER_LABEL,
        ).execute()
    except Exception:
        return []

    messages = resp.get("messages", [])
    result = []
    for msg in messages:
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
        except Exception:
            pass
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


def _scan_one_account(account: str) -> dict:
    """Scan all InboxScout labels for one account. Returns plan dict. No Gmail writes."""
    from inbox_scout.report_mode import classify_for_report

    try:
        service = _get_service(account)
        results = service.users().labels().list(userId="me").execute()
        all_labels = results.get("labels", [])
    except Exception as e:
        return {"account": account, "error": str(e), "mismatches": [], "scanned": 0}

    inbox_scout_labels = [
        lbl["name"]
        for lbl in all_labels
        if lbl["name"].startswith(INBOX_SCOUT_PREFIX)
    ]

    all_mismatches: list[dict] = []
    total_scanned = 0
    total_skips = {"protected": 0, "manual_review": 0, "high_risk": 0, "review_label": 0}

    for label_name in inbox_scout_labels:
        emails = _fetch_labeled_emails(service, label_name)
        if not emails:
            continue
        classified = classify_for_report(emails)
        total_scanned += len(classified)
        mismatches, skips = build_resort_candidates(classified, label_name)
        all_mismatches.extend(mismatches)
        for k in total_skips:
            total_skips[k] += skips.get(k, 0)

    return {
        "account": account,
        "scanned": total_scanned,
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
        plans = [_scan_one_account("primary"), _scan_one_account("secondary")]
    elif account == "primary":
        plans = [_scan_one_account("primary")]
    else:
        plans = [_scan_one_account("secondary")]

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
