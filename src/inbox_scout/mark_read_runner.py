from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
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
LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_PATH = LOG_DIR / "mark_read_actions.jsonl"

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
    "personal",
    "manual review",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def save_queue(original: Any) -> None:
    QUEUE_PATH.write_text(json.dumps(original, indent=2, ensure_ascii=False), encoding="utf-8")


def log_action(entry: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


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

    for nested_key in ("email", "message", "gmail", "raw"):
        nested = item.get(nested_key)
        if isinstance(nested, dict):
            for key in ("gmail_message_id", "message_id", "gmail_id", "email_message_id", "email_id"):
                if nested.get(key):
                    return str(nested.get(key))

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

    if category in PROTECTED_CATEGORIES:
        return True
    # Catch compound AI categories like "Bills/receipts", "Job/career", "Client/business"
    return any(part.strip() in PROTECTED_CATEGORIES for part in category.split("/"))


def already_marked_read(item: dict[str, Any]) -> bool:
    return is_true(item.get("gmail_marked_read")) or norm(item.get("gmail_read_action_type")) == "marked read"


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


def evaluate_mark_read_candidate(item: dict[str, Any]) -> tuple[bool, str]:
    """Eligibility for mark-as-read: safe reviewed items; archive/trash not required."""
    if already_marked_read(item):
        return False, "Already marked read"
    if is_protected(item):
        return False, "Protected/manual-review"
    if get_risk(item) > 40:
        return False, "Risk too high"
    if not get_message_id(item):
        return False, "Missing Gmail message ID"
    return True, "Eligible to mark as read"


def build_mark_read_plan_message() -> str:
    if not QUEUE_PATH.exists():
        return "No queue yet. Sort your inbox first."
    try:
        _, items = load_queue()
    except Exception as e:
        return f"Could not load queue: {e}\n\nGmail not touched."

    eligible = []
    skipped = 0
    for item in items:
        ok, _ = evaluate_mark_read_candidate(item)
        if ok:
            eligible.append(item)
        else:
            skipped += 1

    if not eligible:
        return (
            f"No safe reviewed emails to mark as read.\n\n"
            f"Skipped: {skipped} (protected, manual review, or high risk).\n\n"
            "Gmail not touched."
        )

    lines = [f"Mark-read plan: {len(eligible)} eligible email(s).", ""]
    lines.append("Eligible (safe reviewed, not protected, risk <= 40):")
    for item in eligible:
        lines.append(
            f"- ID {get_queue_id(item)}: {get_subject(item)[:55]}"
            f" | risk {get_risk(item)} | {get_category(item)}"
        )
    lines += [
        "",
        f"Skipped (protected/manual/high-risk): {skipped}",
        "",
        "No Gmail changes yet.",
        "",
        "Say 'confirm mark read' to mark these as read in Gmail.",
    ]
    return "\n".join(lines)


def build_mark_read_runner_message(apply: bool = False) -> str:
    if not QUEUE_PATH.exists():
        return "No queue yet. Sort your inbox first."
    try:
        original, items = load_queue()
    except Exception as e:
        return f"Could not load queue: {e}\n\nGmail not touched."

    eligible = [item for item in items if evaluate_mark_read_candidate(item)[0]]

    if not eligible:
        return "No safe reviewed emails to mark as read. Gmail not touched."

    if not apply:
        return (
            f"Dry run: {len(eligible)} email(s) would be marked read.\n\n"
            "No Gmail changes made.\n\n"
            "Say 'confirm mark read' to apply."
        )

    service = get_modify_service()
    marked = 0
    errors = 0

    for item in eligible:
        msg_id = get_message_id(item)
        try:
            service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
            item["gmail_marked_read"] = True
            item["gmail_marked_read_at"] = now_iso()
            item["gmail_read_action_type"] = "marked_read"
            item["gmail_read_action_taken"] = True
            marked += 1
            log_action({
                "timestamp": now_iso(),
                "action": "MARKED READ",
                "queue_id": get_queue_id(item),
                "message_id": msg_id,
                "subject": get_subject(item),
                "category": get_category(item),
                "risk": get_risk(item),
                "reason": "Confirmed mark-read command",
                "gmail_changed": True,
            })
        except Exception as e:
            errors += 1
            log_action({
                "timestamp": now_iso(),
                "action": "ERROR",
                "queue_id": get_queue_id(item),
                "message_id": msg_id,
                "subject": get_subject(item),
                "category": get_category(item),
                "risk": get_risk(item),
                "reason": f"Mark read failed: {e}",
                "gmail_changed": False,
            })

    save_queue(original)

    lines = [f"Marked {marked} email(s) as read in Gmail."]
    if errors:
        lines.append(f"Errors: {errors}")
    lines += [
        "",
        "Protected and manual review emails were not touched.",
        "Gmail not touched for anything outside the eligible set.",
    ]
    return "\n".join(lines)


def get_modify_service():
    from inbox_scout.gmail_auth import get_gmail_service

    try:
        return get_gmail_service(mode="modify")
    except TypeError:
        return get_gmail_service("modify")


def print_results(rows: list[dict[str, Any]], apply: bool) -> None:
    console = Console() if Console else None
    mode = "APPLY MODE" if apply else "DRY RUN"

    if console and Table:
        console.print("\n[bold]Inbox Scout Phase 10B: Mark-as-read Runner[/bold]")
        console.print(f"Mode: [bold]{mode}[/bold]\n")

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
                row["queue_id"],
                row["action"],
                str(row["risk"]),
                row["category"],
                row["sender"][:32],
                row["subject"][:42],
                row["reason"][:42],
            )

        console.print(table)

        would = sum(1 for r in rows if r["action"] == "WOULD MARK READ")
        marked = sum(1 for r in rows if r["action"] == "MARKED READ")
        skipped = sum(1 for r in rows if r["action"] == "SKIPPED")

        console.print()
        console.print(f"Would mark read: {would}")
        console.print(f"Marked read: {marked}")
        console.print(f"Skipped: {skipped}")
        return

    for row in rows:
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inbox Scout guarded mark-as-read runner")
    parser.add_argument("-Apply", "--apply", action="store_true", help="Actually remove UNREAD label from eligible emails")
    args = parser.parse_args()

    original, items = load_queue()
    rows = []

    service = get_modify_service() if args.apply else None

    for item in items:
        eligible, reason = evaluate_item(item)

        row = {
            "timestamp": now_iso(),
            "queue_id": get_queue_id(item),
            "message_id": get_message_id(item),
            "sender": get_sender(item),
            "subject": get_subject(item),
            "category": get_category(item),
            "risk": get_risk(item),
            "local_decision": get_decision(item),
            "reason": reason,
            "gmail_changed": False,
        }

        if not eligible:
            row["action"] = "SKIPPED"
            rows.append(row)
            continue

        if not args.apply:
            row["action"] = "WOULD MARK READ"
            rows.append(row)
            log_action(row)
            continue

        try:
            service.users().messages().modify(
                userId="me",
                id=row["message_id"],
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()

            item["gmail_marked_read"] = True
            item["gmail_marked_read_at"] = now_iso()
            item["gmail_read_action_type"] = "marked_read"
            item["gmail_read_action_taken"] = True

            row["action"] = "MARKED READ"
            row["gmail_changed"] = True
            rows.append(row)
            log_action(row)

        except Exception as e:
            row["action"] = "ERROR"
            row["reason"] = f"Mark read failed: {e}"
            rows.append(row)
            log_action(row)

    if args.apply:
        save_queue(original)

    print_results(rows, args.apply)

    if args.apply:
        print("\nApply complete. Eligible handled emails were marked read.")
    else:
        print("\nNo Gmail changes were made. Run with -Apply only after reviewing the dry-run.")


if __name__ == "__main__":
    main()
