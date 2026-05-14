from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from inbox_scout.gmail_auth import get_gmail_service
from inbox_scout.review_queue import LATEST_QUEUE_FILE

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "data" / "logs"
ARCHIVE_LOG_PATH = LOG_DIR / "archive_actions.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def log_action(entry: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with ARCHIVE_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_entry(item: dict[str, Any], action: str, reason: str, gmail_changed: bool) -> dict[str, Any]:
    return {
        "timestamp": now_iso(),
        "queue_id": clean(item.get("queue_id")),
        "message_id": clean(item.get("message_id")),
        "sender": clean(item.get("from") or item.get("sender")),
        "subject": clean(item.get("subject")),
        "category": clean(item.get("category")),
        "risk": item.get("risk_score") or item.get("risk"),
        "local_decision": clean(item.get("local_decision")),
        "reason": reason,
        "gmail_changed": gmail_changed,
        "action": action,
    }


def is_archive_eligible(item: dict[str, Any]):
    decision = item.get("local_decision")
    risk = int(item.get("risk_score") or 999)
    manual = bool(item.get("manual_review"))

    if manual:
        return False, "Manual review protected"

    if decision != "possible_archive_later":
        return False, "Decision is not possible_archive_later"

    if risk > 40:
        return False, "Risk too high"

    if item.get("gmail_archived") or clean(item.get("gmail_action_type")).lower() == "archived":
        return False, "Already marked archived locally"

    return True, "Eligible"


def main():
    parser = argparse.ArgumentParser(description="Inbox Scout Guarded Archive Runner")
    parser.add_argument("--apply", action="store_true", help="Actually archive eligible Gmail messages")
    args = parser.parse_args()

    console.print("\n[bold cyan]Inbox Scout Phase 8: Guarded Archive Runner[/bold cyan]\n")

    if args.apply:
        console.print("[bold yellow]APPLY MODE: eligible emails will be archived from Inbox.[/bold yellow]\n")
    else:
        console.print("[yellow]Dry-run mode. No emails will be archived.[/yellow]\n")

    if not LATEST_QUEUE_FILE.exists():
        console.print("[red]latest_queue.json not found. Run inboxqueue first.[/red]")
        return

    payload = json.loads(LATEST_QUEUE_FILE.read_text(encoding="utf-8"))
    items = payload.get("queue_items", [])

    service = get_gmail_service(mode="modify") if args.apply else None

    table = Table(title="Guarded Archive Plan")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Decision", style="green")
    table.add_column("Risk", style="yellow")
    table.add_column("Plan", style="magenta")
    table.add_column("Reason", style="blue")
    table.add_column("Subject", style="white")

    archived_count = 0
    would_archive_count = 0
    skipped_count = 0

    for item in items:
        queue_id = item.get("queue_id")
        decision = item.get("local_decision")
        risk = int(item.get("risk_score") or 999)
        subject = str(item.get("subject", "(No subject)"))
        message_id = item.get("message_id")

        eligible, reason = is_archive_eligible(item)

        if not eligible:
            plan = "SKIP"
            skipped_count += 1
        elif not message_id:
            plan = "SKIP"
            reason = "Missing message_id"
            skipped_count += 1
        elif args.apply:
            body = {"removeLabelIds": ["INBOX"], "addLabelIds": []}
            service.users().messages().modify(
                userId="me",
                id=message_id,
                body=body
            ).execute()

            archive_time = now_iso()

            item["gmail_archived"] = True
            item["gmail_archived_at"] = archive_time
            item["gmail_action_type"] = "archived"
            item["gmail_action_taken"] = True

            plan = "ARCHIVED"
            archived_count += 1
            log_action(log_entry(item, "ARCHIVED", reason, True))
        else:
            plan = "WOULD ARCHIVE"
            would_archive_count += 1
            log_action(log_entry(item, "WOULD ARCHIVE", reason, False))

        table.add_row(
            str(queue_id),
            str(decision),
            str(risk),
            plan,
            reason,
            subject[:70]
        )

    console.print(table)

    if args.apply:
        payload["last_updated_at"] = now_iso()
        LATEST_QUEUE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        console.print(f"\n[bold green]Archived emails:[/bold green] {archived_count}")
        console.print(f"[yellow]Skipped:[/yellow] {skipped_count}")
        console.print("[yellow]No emails were deleted. No replies were sent.[/yellow]\n")
    else:
        console.print(f"\n[bold green]Would archive:[/bold green] {would_archive_count}")
        console.print(f"[yellow]Skipped:[/yellow] {skipped_count}")
        console.print("[yellow]Dry run complete. No Gmail changes were made.[/yellow]\n")


if __name__ == "__main__":
    main()
