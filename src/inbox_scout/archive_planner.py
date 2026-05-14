import json

from rich.console import Console
from rich.table import Table

from inbox_scout.review_queue import LATEST_QUEUE_FILE

console = Console()


def main():
    console.print("\n[bold cyan]Inbox Scout Phase 8: Archive Dry-Run Planner[/bold cyan]\n")
    console.print("[yellow]Dry-run only. No emails will be archived.[/yellow]\n")

    if not LATEST_QUEUE_FILE.exists():
        console.print("[red]latest_queue.json not found. Run inboxqueue first.[/red]")
        return

    payload = json.loads(LATEST_QUEUE_FILE.read_text(encoding="utf-8"))
    items = payload.get("queue_items", [])

    table = Table(title="Archive Eligibility Plan")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Decision", style="green")
    table.add_column("Risk", style="yellow")
    table.add_column("Manual", style="red")
    table.add_column("Archive Plan", style="magenta")
    table.add_column("Subject", style="white")

    eligible = 0
    protected = 0
    skipped = 0

    for item in items:
        queue_id = item.get("queue_id")
        decision = item.get("local_decision")
        risk = int(item.get("risk_score") or 999)
        manual = bool(item.get("manual_review"))
        subject = str(item.get("subject", "(No subject)"))

        if manual or decision == "protected_review":
            plan = "SKIP - protected"
            protected += 1
        elif decision == "possible_archive_later" and risk <= 40:
            plan = "WOULD ARCHIVE"
            eligible += 1
        else:
            plan = "SKIP - not eligible"
            skipped += 1

        table.add_row(
            str(queue_id),
            str(decision),
            str(risk),
            str(manual),
            plan,
            subject[:70]
        )

    console.print(table)
    console.print(f"\n[bold green]Eligible archive candidates:[/bold green] {eligible}")
    console.print(f"[bold yellow]Protected skipped:[/bold yellow] {protected}")
    console.print(f"[bold yellow]Other skipped:[/bold yellow] {skipped}")
    console.print("\n[yellow]No Gmail changes were made.[/yellow]\n")


if __name__ == "__main__":
    main()
