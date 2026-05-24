"""Inbox Filing Mode v1A — preview and explicit apply mode."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inbox_scout.trash_candidate_plan import is_shopping_history_soft
from inbox_scout.paths import FILING_LOG
from inbox_scout.gmail_auth import get_gmail_service

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"

_SAFE_FILING_CATEGORIES = frozenset({
    "newsletter", "newsletters",
    "promotion", "promotions",
    "social_notification", "social_notifications", "social notification",
})

_UNTOUCHED_CATEGORIES = frozenset({
    "finance", "financial",
    "security",
    "medical",
    "legal", "legal-tax", "legal/tax", "legal tax",
    "job", "jobs", "career",
    "account", "accounts", "account/login", "login",
    "bills/receipts", "receipt", "receipts", "order confirmation", "order confirmations",
    "refund", "refunds",
    "warranty", "support",
    "client", "business", "client/business", "work-business", "work business",
})


def _clean(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _load_queue() -> list[dict[str, Any]]:
    if not LATEST_QUEUE.exists():
        return []
    data = json.loads(LATEST_QUEUE.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("queue_items", [])
    return []


def _is_protected(item: dict[str, Any]) -> bool:
    if item.get("manual_review"):
        return True
    if item.get("protected"):
        return True
    decision = _clean(item.get("local_decision")).lower()
    if decision in ("protected_review",):
        return True
    return False


def _risk(item: dict[str, Any]) -> int:
    v = item.get("risk_score")
    if v is None:
        return 999
    try:
        return int(v)
    except (ValueError, TypeError):
        return 999


def _category(item: dict[str, Any]) -> str:
    return _clean(item.get("category")).lower()


def _bucket(item: dict[str, Any]) -> str:
    """Return bucket name: 'safe_filing', 'label_only', or 'untouched'."""
    if _is_protected(item):
        return "untouched"
    if _risk(item) > 40:
        return "untouched"
    # shopping_history_soft must be checked before _UNTOUCHED_CATEGORIES
    # because bills/receipts is in both sets
    if is_shopping_history_soft(item):
        return "label_only"
    cat = _category(item)
    if cat in _UNTOUCHED_CATEGORIES:
        return "untouched"
    if cat in _SAFE_FILING_CATEGORIES:
        return "safe_filing"
    return "untouched"


def build_filing_preview() -> str:
    items = _load_queue()
    if not items:
        return (
            "Inbox Filing Mode preview\n\n"
            "No latest queue found.\n\n"
            "Run 'sort all' or 'clean my inbox' first to build a queue,\n"
            "then try 'file inbox' again."
        )

    safe_filing: list[dict] = []
    label_only: list[dict] = []
    untouched: list[dict] = []

    for item in items:
        b = _bucket(item)
        if b == "safe_filing":
            safe_filing.append(item)
        elif b == "label_only":
            label_only.append(item)
        else:
            untouched.append(item)

    lines = [
        "Inbox Filing Mode preview",
        "No Gmail changes yet.",
        "",
        f"Safe to label + archive + mark read: {len(safe_filing)}",
        f"  (newsletter / promotion / social_notification, risk ≤ 40, not protected)",
        f"Label only (shopping history soft): {len(label_only)}",
        f"Untouched (protected / high-risk / sensitive category): {len(untouched)}",
        f"Total queue items: {len(items)}",
        "",
        "Say 'apply filing primary' or 'apply filing secondary' to apply.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers shared by apply_filing
# ---------------------------------------------------------------------------

_CATEGORY_TO_LABEL: dict[str, str] = {
    "newsletter": "InboxScout/Newsletter",
    "newsletters": "InboxScout/Newsletter",
    "promotion": "InboxScout/Promotions",
    "promotions": "InboxScout/Promotions",
    "social_notification": "InboxScout/Social",
    "social_notifications": "InboxScout/Social",
    "social notification": "InboxScout/Social",
}
_SHOPPING_LABEL = "InboxScout/Shopping"
_KNOWN_ACCOUNTS = {"primary", "secondary"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_queue_id(item: dict[str, Any]) -> str:
    for key in ("queue_id", "local_id", "item_id", "id"):
        if item.get(key) is not None:
            return str(item[key])
    return "unknown"


def _get_message_id(item: dict[str, Any]) -> str | None:
    for key in ("gmail_message_id", "message_id", "gmail_id", "email_id"):
        if item.get(key):
            return str(item[key])
    return None


def _get_item_account(item: dict[str, Any]) -> str | None:
    """Return 'primary', 'secondary', or None if the item has no account tag."""
    for key in ("account", "source_account", "gmail_account"):
        val = str(item.get(key) or "").strip().lower()
        if val in ("primary", "ryanrjfrechette@gmail.com"):
            return "primary"
        if val in ("secondary", "ryanrfrechette@gmail.com"):
            return "secondary"
    return None


def _log_filing_action(entry: dict[str, Any]) -> None:
    FILING_LOG.parent.mkdir(parents=True, exist_ok=True)
    with FILING_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _get_or_create_label(service: Any, label_name: str) -> str | None:
    try:
        result = service.users().labels().list(userId="me").execute()
        for lbl in result.get("labels", []):
            if lbl["name"] == label_name:
                return lbl["id"]
        created = service.users().labels().create(
            userId="me", body={"name": label_name}
        ).execute()
        return created["id"]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Filing apply
# ---------------------------------------------------------------------------

def apply_filing(account: str) -> str:
    """Apply filing labels/archive/mark-read to safe queue items for the given account.

    Uses Gmail modify service for the specified account.
    Items missing a message_id are skipped (failed).
    Items with an explicit account field that mismatches are skipped.
    Protected/manual-review/high-risk items are never touched.
    PII-free JSONL entries are written to FILING_LOG per action.
    """
    if account not in _KNOWN_ACCOUNTS:
        return f"Unknown account '{account}'. Use 'primary' or 'secondary'.\n\nNo Gmail changes made."

    items = _load_queue()
    if not items:
        return (
            "No queue found. Run 'file inbox' or 'cleanup' first.\n\nNo Gmail changes made."
        )

    safe_filing: list[dict] = []
    label_only_items: list[dict] = []
    skipped_protected = 0
    skipped_account_unknown = 0

    for item in items:
        item_account = _get_item_account(item)
        if item_account is None:
            skipped_account_unknown += 1
            _log_filing_action({
                "event": "filing_skipped", "timestamp": _now_iso(),
                "queue_id": _get_queue_id(item), "account": account,
                "bucket": "unknown", "action": "skip",
                "gmail_changed": False, "skipped_reason": "missing_or_unknown_account",
            })
            continue
        if item_account != account:
            skipped_account_unknown += 1
            _log_filing_action({
                "event": "filing_skipped", "timestamp": _now_iso(),
                "queue_id": _get_queue_id(item), "account": account,
                "bucket": "account_mismatch", "action": "skip",
                "gmail_changed": False, "skipped_reason": "account_mismatch",
            })
            continue
        b = _bucket(item)
        if b == "untouched":
            skipped_protected += 1
        elif b == "safe_filing":
            safe_filing.append(item)
        elif b == "label_only":
            label_only_items.append(item)

    if not safe_filing and not label_only_items:
        return (
            f"No actionable items for {account} account.\n"
            f"Protected/untouched skipped: {skipped_protected}\n"
            f"Account mismatch skipped: {skipped_account_unknown}\n\n"
            "No Gmail changes made."
        )

    try:
        service = get_gmail_service(mode="modify", account=account)
    except Exception as e:
        return (
            f"{account.capitalize()} Gmail authorization failed: {e}\n\nNo Gmail changes made."
        )

    label_cache: dict[str, str | None] = {}

    def _label_id(name: str) -> str | None:
        if name not in label_cache:
            label_cache[name] = _get_or_create_label(service, name)
        return label_cache[name]

    labeled = archived = marked_read = label_only_count = failed = 0

    for item in safe_filing:
        queue_id = _get_queue_id(item)
        msg_id = _get_message_id(item)
        if not msg_id:
            failed += 1
            _log_filing_action({
                "event": "filing_failed", "timestamp": _now_iso(),
                "queue_id": queue_id, "account": account, "bucket": "safe_filing",
                "action": "skip", "gmail_changed": False,
                "skipped_reason": "missing_message_id",
            })
            continue
        label_name = _CATEGORY_TO_LABEL.get(_category(item), "InboxScout/Misc")
        lid = _label_id(label_name)
        if lid is None:
            failed += 1
            _log_filing_action({
                "event": "filing_failed", "timestamp": _now_iso(),
                "queue_id": queue_id, "account": account, "bucket": "safe_filing",
                "action": "skip", "gmail_changed": False,
                "skipped_reason": "label_create_failed",
            })
            continue
        try:
            service.users().messages().modify(
                userId="me", id=msg_id,
                body={"addLabelIds": [lid], "removeLabelIds": ["INBOX", "UNREAD"]},
            ).execute()
            labeled += 1
            archived += 1
            marked_read += 1
            _log_filing_action({
                "event": "filing_applied", "timestamp": _now_iso(),
                "queue_id": queue_id, "account": account, "bucket": "safe_filing",
                "action": "label+archive+mark_read", "gmail_changed": True,
                "skipped_reason": None,
            })
        except Exception as exc:
            failed += 1
            _log_filing_action({
                "event": "filing_failed", "timestamp": _now_iso(),
                "queue_id": queue_id, "account": account, "bucket": "safe_filing",
                "action": "skip", "gmail_changed": False,
                "skipped_reason": f"gmail_error:{type(exc).__name__}",
            })

    for item in label_only_items:
        queue_id = _get_queue_id(item)
        msg_id = _get_message_id(item)
        if not msg_id:
            failed += 1
            _log_filing_action({
                "event": "filing_failed", "timestamp": _now_iso(),
                "queue_id": queue_id, "account": account, "bucket": "label_only",
                "action": "skip", "gmail_changed": False,
                "skipped_reason": "missing_message_id",
            })
            continue
        lid = _label_id(_SHOPPING_LABEL)
        if lid is None:
            failed += 1
            _log_filing_action({
                "event": "filing_failed", "timestamp": _now_iso(),
                "queue_id": queue_id, "account": account, "bucket": "label_only",
                "action": "skip", "gmail_changed": False,
                "skipped_reason": "label_create_failed",
            })
            continue
        try:
            service.users().messages().modify(
                userId="me", id=msg_id,
                body={"addLabelIds": [lid]},
            ).execute()
            label_only_count += 1
            labeled += 1
            _log_filing_action({
                "event": "filing_applied", "timestamp": _now_iso(),
                "queue_id": queue_id, "account": account, "bucket": "label_only",
                "action": "label_only", "gmail_changed": True,
                "skipped_reason": None,
            })
        except Exception as exc:
            failed += 1
            _log_filing_action({
                "event": "filing_failed", "timestamp": _now_iso(),
                "queue_id": queue_id, "account": account, "bucket": "label_only",
                "action": "skip", "gmail_changed": False,
                "skipped_reason": f"gmail_error:{type(exc).__name__}",
            })

    lines = [
        f"Inbox filing complete ({account} account).",
        f"Labeled: {labeled}",
        f"Archived: {archived}",
        f"Marked read: {marked_read}",
        f"Label only (not archived): {label_only_count}",
        f"Skipped protected: {skipped_protected}",
        f"Skipped account mismatch: {skipped_account_unknown}",
        f"Failed: {failed}",
    ]
    if labeled == 0 and failed == 0:
        lines.append("\nNo Gmail changes made.")
    return "\n".join(lines)
