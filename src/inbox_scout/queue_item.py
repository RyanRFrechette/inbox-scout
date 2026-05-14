import argparse
import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from inbox_scout.review_queue import LATEST_QUEUE_FILE

console = Console()


def clean(text):
    if text is None:
        return ""
    return str(text).replace("\r", " ").replace("\n", " ").strip()


def main():
    parser = argparse.ArgumentParser(description="View one Inbox Scout queue item")
    parser.add_argument("--id", type=int, required=True)
    args = parser.parse_args()

    if not LATEST_QUEUE_FILE.exists():
        console.print("[red]No latest_queue.json found. Run inboxqueue first.[/red]")
        return

    payload = json.loads(LATEST_QUEUE_FILE.read_text(encoding="utf-8"))
    items = payload.get("queue_items", [])

    item = next((x for x in items if x.get("queue_id") == args.id), None)

    if not item:
        console.print(f"[red]No queue item found with ID {args.id}.[/red]")
        return

    table = Table(title=f"Inbox Scout Queue Item #{args.id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Decision", clean(item.get("local_decision")))
    table.add_row("Category", clean(item.get("category")))
    table.add_row("Risk", clean(item.get("risk_score")))
    table.add_row("Confidence", clean(item.get("confidence_score")))
    table.add_row("Manual review", clean(item.get("manual_review")))
    table.add_row("From", clean(item.get("from")))
    table.add_row("Date", clean(item.get("date")))
    table.add_row("Subject", clean(item.get("subject")))
    table.add_row("Suggested action", clean(item.get("suggested_action")))
    table.add_row("Reason", clean(item.get("reason")))
    table.add_row("Gmail label applied", clean(item.get("gmail_label_applied")))
    table.add_row("Gmail action type", clean(item.get("gmail_action_type")))
    table.add_row("Gmail action taken", clean(item.get("gmail_action_taken")))
    table.add_row("Gmail marked read", clean(item.get("gmail_marked_read")))
    table.add_row("Gmail read action type", clean(item.get("gmail_read_action_type")))
    table.add_row("Gmail read action taken", clean(item.get("gmail_read_action_taken")))
    table.add_row("Gmail marked read at", clean(item.get("gmail_marked_read_at")))

    console.print(table)
    console.print(Panel(clean(item.get("snippet")), title="Snippet", expand=False))
    console.print("[yellow]No archive, delete, or reply action was performed.[/yellow]")


if __name__ == "__main__":
    main()
