import json

from rich.console import Console

from inbox_scout.review_queue import LATEST_QUEUE_FILE
from inbox_scout.queue_item import clean
from rich.panel import Panel
from rich.table import Table

console = Console()

PENDING_DECISIONS = ["pending_review", "review_later"]


def main():
    if not LATEST_QUEUE_FILE.exists():
        console.print("[red]No latest_queue.json found. Run inboxqueue first.[/red]")
        return

    payload = json.loads(LATEST_QUEUE_FILE.read_text(encoding="utf-8"))
    items = payload.get("queue_items", [])

    item = next(
        (x for x in items if x.get("local_decision") in PENDING_DECISIONS),
        None
    )

    if not item:
        console.print("[bold green]No pending local review items found.[/bold green]")
        console.print("[yellow]No Gmail changes were made.[/yellow]")
        return

    queue_id = item.get("queue_id")

    table = Table(title=f"Next Pending Inbox Scout Item #{queue_id}")
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
    table.add_row("Gmail action taken", clean(item.get("gmail_action_taken")))

    console.print(table)
    console.print(Panel(clean(item.get("snippet")), title="Snippet", expand=False))

    console.print("\n[bold cyan]Decision examples:[/bold cyan]")
    console.print(f'inboxdecide -Id {queue_id} -Decision possible_archive_later -Note "Low-risk newsletter/promo"')
    console.print(f'inboxdecide -Id {queue_id} -Decision keep -Note "Worth keeping"')
    console.print(f'inboxdecide -Id {queue_id} -Decision review_later -Note "Need to check later"')
    console.print("\n[yellow]No Gmail changes were made.[/yellow]")


if __name__ == "__main__":
    main()
