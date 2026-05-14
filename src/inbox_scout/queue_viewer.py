import json

from rich.console import Console
from rich.table import Table

from inbox_scout.review_queue import LATEST_QUEUE_FILE

console = Console()


def shorten(text, max_len=70):
    text = str(text or "").replace("\n", " ").replace("\r", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."


def main():
    if not LATEST_QUEUE_FILE.exists():
        console.print("[red]No latest_queue.json found. Run review_queue first.[/red]")
        return

    payload = json.loads(LATEST_QUEUE_FILE.read_text(encoding="utf-8"))
    items = payload.get("queue_items", [])

    console.print("\n[bold cyan]Inbox Scout Local Review Queue Viewer[/bold cyan]")
    console.print(f"[yellow]Safety mode:[/yellow] {payload.get('safety_mode')}")
    console.print(f"[yellow]Created at:[/yellow] {payload.get('created_at')}")
    console.print("[yellow]No Gmail changes will be made.[/yellow]\n")

    table = Table(title="Latest Local Queue")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Decision", style="green")
    table.add_column("Risk", style="yellow", no_wrap=True)
    table.add_column("Category", style="magenta")
    table.add_column("From", style="blue")
    table.add_column("Subject", style="white")

    for item in items:
        table.add_row(
            str(item.get("queue_id")),
            str(item.get("local_decision")),
            str(item.get("risk_score")),
            shorten(item.get("category"), 24),
            shorten(item.get("from"), 36),
            shorten(item.get("subject"), 70),
        )

    console.print(table)


if __name__ == "__main__":
    main()
