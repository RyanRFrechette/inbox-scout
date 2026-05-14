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
LOG_PATH = LOG_DIR / "trash_actions.jsonl"

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
    "password",
    "password/security",
    "job",
    "job/interview",
    "client",
    "client/business",
    "business",
    "invoice",
    "invoice/payment",
    "payment",
    "family",
    "warranty",
    "warranty/support",
    "support",
    "refund",
    "refunds",
    "return",
    "returns",
    "collections",
    "collections/balances",
    "balance",
    "account",
    "account access",
    "account_access",
    "bills",
    "bill",
    "receipt",
    "receipts",
    "insurance",
}


PROTECTED_TEXT_TERMS = {
    "collection",
    "collections",
    "balance collection",
    "debt",
    "resurgent",
    "ecollect",
    "medical",
    "patientgateway",
    "appointment reminder",
    "security alert",
    "verification code",
    "single-use code",
    "account-security",
    "password",
    "refund",
    "return request",
    "ordered:",
    "delivered:",
    "invoice",
    "payment",
    "insurance",
    "auto-confirm@amazon.com",
    "return@amazon.com",
    "order-update@amazon.com",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def norm(value: Any) -> str:
    return clean(value).lower().replace("_", " ").replace("-", " ").strip()


def get_console():
    if Console:
        return Console()
    return None


def load_queue() -> tuple[Any, list[dict[str, Any]]]:
    if not QUEUE_PATH.exists():
        raise FileNotFoundError(f"Queue not found: {QUEUE_PATH}")

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
        value = item.get(key)
        if value is not None:
            return str(value)
    return "unknown"


def get_message_id(item: dict[str, Any]) -> str | None:
    possible_keys = (
        "gmail_message_id",
        "message_id",
        "gmail_id",
        "email_message_id",
        "email_id",
    )

    for key in possible_keys:
        value = item.get(key)
        if value:
            return str(value)

    nested_keys = ("email", "message", "gmail", "raw")
    for nk in nested_keys:
        nested = item.get(nk)
        if isinstance(nested, dict):
            for key in possible_keys:
                value = nested.get(key)
                if value:
                    return str(value)

    return None


def get_sender(item: dict[str, Any]) -> str:
    return clean(
        item.get("from")
        or item.get("sender")
        or item.get("from_email")
        or item.get("sender_email")
        or "unknown"
    )


def get_subject(item: dict[str, Any]) -> str:
    return clean(item.get("subject") or "(no subject)")


def get_category(item: dict[str, Any]) -> str:
    return clean(item.get("category") or item.get("final_category") or item.get("label") or "unknown")


def get_decision(item: dict[str, Any]) -> str:
    return clean(item.get("local_decision") or item.get("decision") or "unknown")


def get_risk(item: dict[str, Any]) -> int:
    value = item.get("risk_score", item.get("risk", 999))
    try:
        return int(value)
    except Exception:
        return 999


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def already_trashed(item: dict[str, Any]) -> bool:
    return is_true(item.get("gmail_trashed")) or norm(item.get("gmail_action_type")) == "trashed"


def already_archived(item: dict[str, Any]) -> bool:
    return is_true(item.get("gmail_archived")) or norm(item.get("gmail_action_type")) == "archived"


def is_protected(item: dict[str, Any]) -> bool:
    category = norm(get_category(item))
    decision = clean(get_decision(item)).lower()

    if decision == "protected_review":
        return True

    if is_true(item.get("manual_review")) or is_true(item.get("manual_review_required")):
        return True

    if is_true(item.get("protected")) or is_true(item.get("protected_review")):
        return True

    return category in PROTECTED_CATEGORIES


def has_protected_text(item: dict[str, Any]) -> bool:
    combined = " ".join(
        [
            norm(get_category(item)),
            norm(get_sender(item)),
            norm(get_subject(item)),
            norm(item.get("snippet")),
            norm(item.get("reason")),
        ]
    )

    return any(term in combined for term in PROTECTED_TEXT_TERMS)


def evaluate_item(item: dict[str, Any]) -> tuple[bool, str]:
    decision = clean(get_decision(item)).lower()
    category = norm(get_category(item))
    risk = get_risk(item)
    message_id = get_message_id(item)

    if already_trashed(item):
        return False, "Already marked trashed locally"

    if already_archived(item):
        return False, "Already archived locally"

    if is_protected(item):
        return False, "Protected/manual-review item"

    if has_protected_text(item):
        return False, "Protected keyword in sender/subject/category"

    if decision != "ignore":
        return False, "Local decision is not ignore"

    if category not in SAFE_TRASH_CATEGORIES:
        return False, f"Category not trash-safe: {get_category(item)}"

    if risk > 40:
        return False, f"Risk too high: {risk}"

    if not message_id:
        return False, "Missing Gmail message ID"

    return True, "Eligible for Gmail Trash"


def get_modify_service():
    try:
        from inbox_scout.gmail_auth import get_gmail_service

        try:
            return get_gmail_service(mode="modify")
        except TypeError:
            return get_gmail_service("modify")
    except Exception as e:
        raise RuntimeError(
            "Could not load Gmail modify service from inbox_scout.gmail_auth. "
            "Check that Phase 7 gmail_auth.py still supports modify mode."
        ) from e


def print_results(rows: list[dict[str, Any]], apply: bool) -> None:
    console = get_console()
    title = "Inbox Scout Phase 9B: Trash Runner"
    mode = "APPLY MODE" if apply else "DRY RUN"

    if console and Table:
        console.print(f"\n[bold]{title}[/bold]")
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
                row["reason"][:44],
            )

        console.print(table)

        would_trash = sum(1 for r in rows if r["action"] == "WOULD TRASH")
        trashed = sum(1 for r in rows if r["action"] == "TRASHED")
        skipped = sum(1 for r in rows if r["action"] == "SKIPPED")

        console.print()
        console.print(f"Would trash: {would_trash}")
        console.print(f"Trashed: {trashed}")
        console.print(f"Skipped: {skipped}")
        console.print("Permanent delete: 0")
        return

    print(f"\n{title}")
    print(f"Mode: {mode}\n")
    for row in rows:
        print(
            f"[{row['action']}] ID {row['queue_id']} | "
            f"risk={row['risk']} | category={row['category']} | "
            f"from={row['sender']} | subject={row['subject']} | reason={row['reason']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inbox Scout guarded trash runner")
    parser.add_argument("-Apply", "--apply", action="store_true", help="Actually move eligible emails to Gmail Trash")
    args = parser.parse_args()

    original, items = load_queue()
    rows = []

    service = None
    if args.apply:
        service = get_modify_service()

    for item in items:
        eligible, reason = evaluate_item(item)
        queue_id = get_queue_id(item)
        message_id = get_message_id(item)
        sender = get_sender(item)
        subject = get_subject(item)
        category = get_category(item)
        decision = get_decision(item)
        risk = get_risk(item)

        row = {
            "timestamp": now_iso(),
            "queue_id": queue_id,
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "category": category,
            "risk": risk,
            "local_decision": decision,
            "reason": reason,
            "gmail_changed": False,
        }

        if not eligible:
            row["action"] = "SKIPPED"
            rows.append(row)
            continue

        if not args.apply:
            row["action"] = "WOULD TRASH"
            rows.append(row)
            log_action(row)
            continue

        try:
            service.users().messages().trash(userId="me", id=message_id).execute()

            item["gmail_trashed"] = True
            item["gmail_action_taken"] = True
            item["gmail_action_type"] = "trashed"
            item["gmail_trashed_at"] = now_iso()

            row["action"] = "TRASHED"
            row["gmail_changed"] = True
            rows.append(row)
            log_action(row)

        except Exception as e:
            row["action"] = "ERROR"
            row["reason"] = f"Trash failed: {e}"
            rows.append(row)
            log_action(row)

    if args.apply:
        save_queue(original)

    print_results(rows, args.apply)

    if not args.apply:
        print("\nNo Gmail changes were made. Run with -Apply only after reviewing the dry-run.")
    else:
        print("\nApply complete. Eligible emails were moved to Gmail Trash only, not permanently deleted.")


if __name__ == "__main__":
    main()

