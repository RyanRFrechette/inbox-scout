from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"

SAFE_TRASH_CATEGORIES = {
    "promotion",
    "promotions",
    "newsletter",
    "newsletters",
}

PROTECTED_CATEGORIES = {
    "financial",
    "finance",
    "legal",
    "medical",
    "tax",
    "security",
    "security alert",
    "password",
    "job",
    "job/interview",
    "client",
    "client/business",
    "business",
    "invoice",
    "payment",
    "family",
    "warranty",
    "refund",
    "return",
    "returns",
    "collections",
    "collections/balances",
    "account",
    "account access",
    "bills",
    "bill",
    "receipt",
    "receipts",
    "insurance",
    "manual review",
}


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def norm(value: Any) -> str:
    return clean(value).lower().replace("_", " ").replace("-", " ").strip()


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def load_queue_items() -> list[dict[str, Any]]:
    if not LATEST_QUEUE.exists():
        return []

    data = json.loads(LATEST_QUEUE.read_text(encoding="utf-8-sig"))

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("queue_items", [])

    return []


def get_queue_id(item: dict[str, Any]) -> str:
    return clean(item.get("queue_id") or item.get("id") or "?")


def get_risk(item: dict[str, Any]) -> int:
    try:
        return int(item.get("risk_score") or item.get("risk") or 999)
    except Exception:
        return 999


def get_message_id(item: dict[str, Any]) -> str:
    return clean(item.get("message_id") or item.get("gmail_message_id") or item.get("gmail_id"))


def find_item(queue_id: str) -> dict[str, Any] | None:
    for item in load_queue_items():
        if get_queue_id(item) == str(queue_id):
            return item
    return None


def is_protected(item: dict[str, Any]) -> bool:
    decision = norm(item.get("local_decision"))
    category = norm(item.get("category"))

    if decision == "protected review":
        return True

    if is_true(item.get("manual_review")) or is_true(item.get("manual_review_required")):
        return True

    if is_true(item.get("protected")) or is_true(item.get("protected_review")):
        return True

    return category in PROTECTED_CATEGORIES


def already_gmail_actioned(item: dict[str, Any]) -> bool:
    return is_true(item.get("gmail_action_taken")) or bool(clean(item.get("gmail_action_type")))


def already_marked_read(item: dict[str, Any]) -> bool:
    return is_true(item.get("gmail_marked_read")) or norm(item.get("gmail_read_action_type")) == "marked read"


def safely_handled(item: dict[str, Any]) -> bool:
    return norm(item.get("gmail_action_type")) in {"archived", "trashed"}


def evaluate_archive(item: dict[str, Any]) -> tuple[bool, str]:
    if is_protected(item):
        return False, "Blocked: protected/manual-review item."

    if norm(item.get("local_decision")) != "possible archive later":
        return False, "Blocked: local decision is not possible_archive_later."

    if get_risk(item) > 40:
        return False, f"Blocked: risk too high ({get_risk(item)})."

    if already_gmail_actioned(item):
        return False, "Blocked: Gmail action already taken locally."

    if not get_message_id(item):
        return False, "Blocked: missing Gmail message ID."

    return True, "Allowed in dry-run: item is eligible for archive approval."


def evaluate_trash(item: dict[str, Any]) -> tuple[bool, str]:
    if is_protected(item):
        return False, "Blocked: protected/manual-review item."

    if norm(item.get("local_decision")) != "ignore":
        return False, "Blocked: local decision is not ignore."

    if norm(item.get("category")) not in SAFE_TRASH_CATEGORIES:
        return False, f"Blocked: category is not trash-safe ({clean(item.get('category'))})."

    if get_risk(item) > 40:
        return False, f"Blocked: risk too high ({get_risk(item)})."

    if already_gmail_actioned(item):
        return False, "Blocked: Gmail action already taken locally."

    if not get_message_id(item):
        return False, "Blocked: missing Gmail message ID."

    return True, "Allowed in dry-run: item is eligible for trash approval."


def evaluate_markread(item: dict[str, Any]) -> tuple[bool, str]:
    if is_protected(item):
        return False, "Blocked: protected/manual-review item."

    if not safely_handled(item):
        return False, "Blocked: item has not been archived or trashed yet."

    if already_marked_read(item):
        return False, "Blocked: item is already marked read locally."

    if get_risk(item) > 40:
        return False, f"Blocked: risk too high ({get_risk(item)})."

    if not get_message_id(item):
        return False, "Blocked: missing Gmail message ID."

    return True, "Allowed in dry-run: item is eligible for mark-read approval."


def parse_command(command: str) -> tuple[str | None, str | None]:
    text = command.strip().lower()
    text = text.replace("/approve", "approve")

    match = re.match(r"^approve\s+(archive|trash|markread|mark-read|mark\s+read)\s+(\d+)$", text)

    if not match:
        return None, None

    action = match.group(1).replace("-", "").replace(" ", "")
    queue_id = match.group(2)

    if action == "markread":
        action = "markread"

    return action, queue_id


def evaluate_approval_command(command: str) -> str:
    action, queue_id = parse_command(command)

    if not action or not queue_id:
        return (
            "Approval command not recognized.\n\n"
            "Use one of these formats:\n"
            "- approve archive 2\n"
            "- approve trash 2\n"
            "- approve markread 2\n\n"
            "Dry-run only. No Gmail changes were made."
        )

    item = find_item(queue_id)

    if not item:
        return f"Queue item ID {queue_id} not found.\n\nDry-run only. No Gmail changes were made."

    if action == "archive":
        allowed, reason = evaluate_archive(item)
    elif action == "trash":
        allowed, reason = evaluate_trash(item)
    elif action == "markread":
        allowed, reason = evaluate_markread(item)
    else:
        allowed, reason = False, "Blocked: unknown action."

    status = "WOULD ALLOW" if allowed else "BLOCKED"

    return (
        f"Telegram Approval Dry-Run\n\n"
        f"Command: {command}\n"
        f"Status: {status}\n"
        f"Reason: {reason}\n\n"
        f"Item:\n"
        f"- ID: {get_queue_id(item)}\n"
        f"- Decision: {clean(item.get('local_decision'))}\n"
        f"- Category: {clean(item.get('category'))}\n"
        f"- Risk: {get_risk(item)}\n"
        f"- Gmail action: {clean(item.get('gmail_action_type')) or 'none'}\n"
        f"- Marked read: {clean(item.get('gmail_marked_read')) or 'False'}\n"
        f"- Subject: {clean(item.get('subject'))[:80]}\n\n"
        f"No Gmail changes were made."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inbox Scout Telegram approval dry-run planner")
    parser.add_argument("command", nargs="+", help="Example: approve archive 2")
    args = parser.parse_args()

    print(evaluate_approval_command(" ".join(args.command)))


if __name__ == "__main__":
    main()
