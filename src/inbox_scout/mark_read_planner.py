from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from rich.console import Console
    from rich.table import Table
except Exception:
    Console = None
    Table = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUEUE_PATH = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"

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


def clean(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def norm(value: Any) -> str:
    return clean(value).lower().replace("_", " ").replace("-", " ").strip()


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def load_queue() -> tuple[Any, list[dict[str, Any]]]:
    data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))

    if isinstance(data, list):
        return data, data

    if isinstance(data, dict):
        for key in ("queue_items", "items", "queue", "emails", "messages"):
            if isinstance(data.get(key), list):
                return data, data[key]

    raise ValueError("latest_queue.json format not recognized.")


def get_queue_id(item: dict[str, Any]) -> str:
    for key in ("queue_id", "local_id", "item_id", "id"):
        if item.get(key) is not None:
            return str(item.get(key))
    return "unknown"


def get_sender(item: dict[str, Any]) -> str:
    return clean(item.get("from") or item.get("sender") or item.get("from_email") or "unknown")


def get_subject(item: dict[str, Any]) -> str:
    return clean(item.get("subject") or "(no subject)")


def get_category(item: dict[str, Any]) -> str:
    return clean(item.get("category") or item.get("final_category") or "unknown")


def get_risk(item: dict[str, Any]) -> int:
    try:
        return int(item.get("risk_score", item.get("risk", 999)))
    except Exception:
        return 999


def get_decision(item: dict[str, Any]) -> str:
    return clean(item.get("local_decision") or item.get("decision") or "unknown")


def get_message_id(item: dict[str, Any]) -> str | None:
    for key in ("gmail_message_id", "message_id", "gmail_id", "email_message_id", "email_id"):
        if item.get(key):
            return str(item.get(key))
    return None


def is_protected(item: dict[str, Any]) -> bool:
    category = norm(get_category(item))
    decision = norm(get_decision(item))

    if decision == "protected review":
        return True

    if is_true(item.get("manual_review")) or is_true(item.get("manual_review_required")):
        return True

    if is_true(item.get("protected")) or is_true(item.get("protected_review")):
        return True

    return category in PROTECTED_CATEGORIES


def already_marked_read(item: dict[str, Any]) -> bool:
    return is_true(item.get("gmail_marked_read")) or norm(item.get("gmail_action_type")) == "marked_read"


def was_safely_handled(item: dict[str, Any]) -> bool:
    action_type = norm(item.get("gmail_action_type"))
    return action_type in {"archived", "trashed"}


def evaluate_item(item: dict[str, Any]) -> tuple[bool, str]:
    if already_marked_read(item):
        return False, "Already marked read locally"

    if is_protected(item):
        return False, "Protected/manual-review item"

    if not was_safely_handled(item):
        return False, "Not archived or trashed yet"

    if get_risk(item) > 40:
        return False, "Risk too high"

    if not get_message_id(item):
        return False, "Missing Gmail message ID"

    return True, "Eligible to mark as read"


def main() -> None:
    _, items = load_queue()

    rows = []
    for item in items:
        eligible, reason = evaluate_item(item)
        rows.append({
            "id": get_queue_id(item),
            "action": "WOULD MARK READ" if eligible else "SKIPPED",
            "risk": get_risk(item),
            "category": get_category(item),
            "from": get_sender(item),
            "subject": get_subject(item),
            "reason": reason,
        })

    console = Console() if Console else None

    if console and Table:
        console.print("\n[bold]Inbox Scout Phase 10A: Mark-as-read Planner[/bold]")
        console.print("Mode: [bold]DRY RUN[/bold]\n")

        table = Table(show_header=True, header_style="bold")
        table.add_column("ID")
        table.add_column("Action")
        table.add_column("Risk")
        table.add_column("Category")
        table.add_column("From")
        table.add_column("Subject")
        table.add_column("Reason")

        for row in rows:
            table.add_row(
                row["id"],
                row["action"],
                str(row["risk"]),
                row["category"],
                row["from"][:32],
                row["subject"][:42],
                row["reason"][:42],
            )

        console.print(table)

        would = sum(1 for r in rows if r["action"] == "WOULD MARK READ")
        skipped = sum(1 for r in rows if r["action"] == "SKIPPED")

        console.print()
        console.print(f"Would mark read: {would}")
        console.print(f"Skipped: {skipped}")
        console.print("Gmail changes: 0")
    else:
        for row in rows:
            print(row)

    print("\nNo Gmail changes were made.")


if __name__ == "__main__":
    main()
