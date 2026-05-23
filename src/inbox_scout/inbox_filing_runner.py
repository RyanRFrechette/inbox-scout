"""Inbox Filing Mode v1A — preview only. No Gmail writes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inbox_scout.trash_candidate_plan import is_shopping_history_soft

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
        "Apply mode is not implemented yet.",
    ]
    return "\n".join(lines)
