"""Resort Mode Apply: correct InboxScout label placements.

Reads latest_resort_plan.json, applies recommended label corrections.
Adds new label first, then removes old label (safe order).
Never trashes, archives, deletes, marks read, or blocks senders.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from inbox_scout.paths import LATEST_RESORT_PLAN, DATA_DIR
from inbox_scout.trash_execution_runner import append_jsonl

RESORT_APPLY_LOG = DATA_DIR / "logs" / "resort_apply_runs.jsonl"
PLAN_MAX_AGE_MINUTES = 120
INBOX_SCOUT_PREFIX = "InboxScout/"
MAX_SAFE_RISK = 30

_SENSITIVE_SENDER_KEYWORDS: tuple[str, ...] = (
    "paypal", "venmo", "cashapp", "cash app", "stripe", "zelle",
    "coinbase", "robinhood",
    "chase", "wellsfargo", "citibank", "bankofamerica", "capital one",
    "discover", "americanexpress", "amex", "mastercard",
    "@irs.gov", "revenue service",
    "billing@", "payments@", "security@", "legal@", "compliance@",
)

_SENSITIVE_SUBJECT_KEYWORDS: tuple[str, ...] = (
    "password reset", "security alert", "verify your account",
    "unauthorized access", "suspicious activity", "account suspended",
    "legal notice", "two-factor",
)


def _is_sensitive(m: dict) -> bool:
    sender = (m.get("from") or "").lower()
    subject = (m.get("subject") or "").lower()
    for term in _SENSITIVE_SENDER_KEYWORDS:
        if term in sender:
            return True
    for term in _SENSITIVE_SUBJECT_KEYWORDS:
        if term in subject:
            return True
    return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("resort_apply_%Y%m%d_%H%M%S")


def _get_modify_service(account: str):
    from inbox_scout.gmail_auth import get_gmail_service
    return get_gmail_service(mode="modify", account=account)


def _fetch_label_ids(service) -> dict[str, str]:
    """Return {label_name: label_id} for all labels in the account. Raises on failure."""
    resp = service.users().labels().list(userId="me").execute()
    return {lbl["name"]: lbl["id"] for lbl in resp.get("labels", [])}


def _validate_plan() -> tuple[dict | None, str]:
    if not LATEST_RESORT_PLAN.exists():
        return None, "No resort preview found. Say 'resort my sorted emails' first."
    try:
        plan = json.loads(LATEST_RESORT_PLAN.read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"Could not read resort plan: {e}"
    try:
        created_at = datetime.fromisoformat(str(plan.get("created_at", "")))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - created_at).total_seconds() / 60
        if age > PLAN_MAX_AGE_MINUTES:
            return None, f"Resort plan expired ({age:.0f} min old). Run 'resort preview' again."
    except Exception:
        return None, "Resort plan has an invalid timestamp. Run 'resort preview' again."
    return plan, ""


def _validate_mismatch(m: dict) -> tuple[bool, str]:
    if not (m.get("message_id") or "").strip():
        return False, "missing message_id"
    if m.get("protected"):
        return False, "protected — skipped"
    if m.get("manual_review"):
        return False, "manual_review — skipped"
    current = (m.get("current_label") or "").strip()
    recommended = (m.get("recommended_label") or "").strip()
    if not current.startswith(INBOX_SCOUT_PREFIX):
        return False, f"current_label '{current}' is not InboxScout"
    if not recommended.startswith(INBOX_SCOUT_PREFIX):
        return False, f"recommended_label '{recommended}' is not InboxScout"
    if current == recommended:
        return False, "current and recommended labels are the same"
    risk = int(m.get("risk_score") or 0)
    if risk > MAX_SAFE_RISK:
        return False, f"risk {risk} > {MAX_SAFE_RISK}"
    if _is_sensitive(m):
        return False, "sensitive sender/subject — manual review required"
    return True, ""


def build_resort_run_message(account: str = "both") -> str:
    """Scan InboxScout folders then immediately apply safe label corrections."""
    from inbox_scout.resort_mode import _scan_one_account

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

    scan_errors = [p["error"] for p in plans if p.get("error")]
    has_mismatches = any(p.get("mismatches") for p in plans)
    if scan_errors and not has_mismatches:
        return "Scan failed: " + "; ".join(scan_errors) + "\n\nGmail not touched."

    return build_resort_apply_message()


def build_resort_apply_message() -> str:
    plan, err = _validate_plan()
    if err:
        return err + "\n\nGmail not touched."

    all_items: list[dict] = []
    for acct_plan in plan.get("plans", []):
        acct = acct_plan.get("account", "primary")
        for m in acct_plan.get("mismatches", []):
            all_items.append({**m, "_account": acct})

    if not all_items:
        return "No corrections in resort plan. Gmail not touched."

    valid: list[dict] = []
    skipped: list[tuple[str, str]] = []
    for m in all_items:
        ok, reason = _validate_mismatch(m)
        label = (m.get("subject") or "(no subject)")[:50]
        if ok:
            valid.append(m)
        else:
            skipped.append((label, reason))

    if not valid:
        lines = ["No corrections passed safety validation.\n"]
        lines.extend(f"- {s}: {r}" for s, r in skipped)
        lines.append("\nGmail not touched.")
        return "\n".join(lines)

    run_id = _run_id()
    append_jsonl(RESORT_APPLY_LOG, {
        "event": "resort_apply_start",
        "run_id": run_id,
        "timestamp": _now_iso(),
        "requested": len(valid),
        "skipped": len(skipped),
        "gmail_changes_enabled": True,
        "permanent_delete_enabled": False,
        "trash_enabled": False,
    })

    applied: list[str] = []
    errors: list[str] = []

    by_account: dict[str, list[dict]] = defaultdict(list)
    for m in valid:
        by_account[m["_account"]].append(m)

    for account, items in by_account.items():
        try:
            service = _get_modify_service(account)
        except Exception as e:
            for m in items:
                subj = (m.get("subject") or "(no subject)")[:50]
                errors.append(f"'{subj}': Gmail connect failed — {e}")
                append_jsonl(RESORT_APPLY_LOG, {
                    "event": "resort_apply_error",
                    "run_id": run_id,
                    "timestamp": _now_iso(),
                    "account": account,
                    "message_id": m.get("message_id"),
                    "error": str(e),
                    "gmail_changed": False,
                })
            continue

        try:
            label_ids = _fetch_label_ids(service)
        except Exception as e:
            for m in items:
                subj = (m.get("subject") or "(no subject)")[:50]
                errors.append(f"'{subj}': could not fetch Gmail labels — {e}")
                append_jsonl(RESORT_APPLY_LOG, {
                    "event": "resort_apply_error",
                    "run_id": run_id,
                    "timestamp": _now_iso(),
                    "account": account,
                    "message_id": m.get("message_id"),
                    "error": f"label fetch failed: {e}",
                    "gmail_changed": False,
                })
            continue

        for m in items:
            message_id = m["message_id"]
            current_label = m["current_label"]
            recommended_label = m["recommended_label"]
            subj = (m.get("subject") or "(no subject)")[:50]

            recommended_id = label_ids.get(recommended_label)
            current_id = label_ids.get(current_label)

            if not recommended_id:
                reason = f"label '{recommended_label}' not found in Gmail"
                errors.append(f"'{subj}': {reason}")
                append_jsonl(RESORT_APPLY_LOG, {
                    "event": "resort_apply_skip",
                    "run_id": run_id,
                    "timestamp": _now_iso(),
                    "account": account,
                    "message_id": message_id,
                    "reason": reason,
                    "gmail_changed": False,
                })
                continue

            # Step 1: apply new (correct) label first
            try:
                service.users().messages().modify(
                    userId="me",
                    id=message_id,
                    body={"addLabelIds": [recommended_id]},
                ).execute()
            except Exception as e:
                errors.append(f"'{subj}': failed to add '{recommended_label}' — {e}")
                append_jsonl(RESORT_APPLY_LOG, {
                    "event": "resort_apply_error",
                    "run_id": run_id,
                    "timestamp": _now_iso(),
                    "account": account,
                    "message_id": message_id,
                    "step": "add_label",
                    "label": recommended_label,
                    "error": str(e),
                    "gmail_changed": False,
                })
                continue

            # Step 2: remove old wrong label (only if we have its ID)
            removed_old = False
            if current_id:
                try:
                    service.users().messages().modify(
                        userId="me",
                        id=message_id,
                        body={"removeLabelIds": [current_id]},
                    ).execute()
                    removed_old = True
                except Exception as e:
                    errors.append(
                        f"'{subj}': new label added, old '{current_label}' remove failed — {e}"
                    )
                    append_jsonl(RESORT_APPLY_LOG, {
                        "event": "resort_apply_partial",
                        "run_id": run_id,
                        "timestamp": _now_iso(),
                        "account": account,
                        "message_id": message_id,
                        "added_label": recommended_label,
                        "failed_to_remove": current_label,
                        "error": str(e),
                        "gmail_changed": True,
                    })

            cur_short = current_label[len(INBOX_SCOUT_PREFIX):]
            rec_short = recommended_label[len(INBOX_SCOUT_PREFIX):]
            summary = f"'{subj}': {cur_short} → {rec_short}"
            if not removed_old and current_id:
                summary += " (old label may still be attached)"
            applied.append(summary)

            append_jsonl(RESORT_APPLY_LOG, {
                "event": "resort_apply_moved",
                "run_id": run_id,
                "timestamp": _now_iso(),
                "account": account,
                "message_id": message_id,
                "subject": m.get("subject"),
                "from": m.get("from"),
                "current_label": current_label,
                "recommended_label": recommended_label,
                "old_label_removed": removed_old,
                "gmail_changed": True,
                "permanent_delete": False,
                "trashed": False,
                "archived": False,
            })

    if not applied and errors:
        lines = ["Resort apply failed — no corrections made.\n"]
        lines.extend(f"- {e}" for e in errors)
        lines.append("\nGmail not touched.")
        return "\n".join(lines)

    lines = [f"Done. Applied {len(applied)} resort correction(s).", ""]
    lines.extend(f"- {a}" for a in applied)
    if errors:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {e}" for e in errors)
    if skipped:
        lines.extend(["", "Skipped (safety check):"])
        lines.extend(f"- {s}: {r}" for s, r in skipped)
    lines.extend(["", "Labels corrected. No emails trashed, deleted, or archived."])
    return "\n".join(lines)
