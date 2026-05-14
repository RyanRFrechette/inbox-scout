import argparse
import json
from datetime import datetime

from rich.console import Console
from rich.table import Table

from inbox_scout.review_queue import LATEST_QUEUE_FILE, QUEUE_DIR

console = Console()

ALLOWED_DECISIONS = [
    "keep",
    "ignore",
    "review_later",
    "possible_archive_later",
    "protected_review"
]


def save_decision_log(queue_id, old_decision, new_decision, note):
    log_path = QUEUE_DIR / "decision_log.jsonl"
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "queue_id": queue_id,
        "old_decision": old_decision,
        "new_decision": new_decision,
        "note": note or "",
        "gmail_action_taken": False
    }

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Update local Inbox Scout queue decision")
    parser.add_argument("--id", type=int, required=True, help="Queue ID to update")
    parser.add_argument("--decision", choices=ALLOWED_DECISIONS, required=True)
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    if not LATEST_QUEUE_FILE.exists():
        console.print("[red]No latest_queue.json found. Run inboxqueue first.[/red]")
        return

    payload = json.loads(LATEST_QUEUE_FILE.read_text(encoding="utf-8"))
    items = payload.get("queue_items", [])

    target = None
    for item in items:
        if item.get("queue_id") == args.id:
            target = item
            break

    if not target:
        console.print(f"[red]No queue item found with ID {args.id}.[/red]")
        return

    old_decision = target.get("local_decision")
    target["local_decision"] = args.decision
    target["decision_note"] = args.note
    target["decision_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target["gmail_action_taken"] = False

    payload["last_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LATEST_QUEUE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    save_decision_log(args.id, old_decision, args.decision, args.note)

    table = Table(title="Local Decision Updated")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Queue ID", str(args.id))
    table.add_row("Old decision", str(old_decision))
    table.add_row("New decision", str(args.decision))
    table.add_row("Subject", str(target.get("subject", "")))
    table.add_row("Gmail action taken", "False")

    console.print(table)
    console.print("[yellow]No Gmail changes were made.[/yellow]")


if __name__ == "__main__":
    main()
