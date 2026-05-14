import json

from rich.console import Console
from rich.table import Table

from inbox_scout.review_queue import LATEST_QUEUE_FILE

console = Console()

SAFE_TRASH_CATEGORIES = {
    "Promotion",
    "Newsletter"
}

PROTECTED_DECISIONS = {
    "protected_review",
    "keep",
    "review_later"
}


def is_trash_candidate(item):
    decision = item.get("local_decision")
    category = item.get("category")
    risk = int(item.get("risk_score") or 999)
    manual = bool(item.get("manual_review"))

    if manual:
        return False, "Manual review protected"

    if decision in PROTECTED_DECISIONS:
        return False, f"Protected decision: {decision}"

    if decision != "ignore":
        return False, "Not marked ignore"

    if category not in SAFE_TRASH_CATEGORIES:
        return False, f"Category not trash-safe: {category}"

    if risk > 30:
        return False, "Risk too high for trash"

    if item.get("gmail_archived"):
        return False, "Already archived"

    if item.get("gmail_trashed"):
        return False, "Already marked trashed locally"

    return True, "Eligible for future trash"


def main():
    console.print("\n[bold cyan]Inbox Scout Trash Planner[/bold cyan]\n")
    console.print("[yellow]Dry-run only. No emails will be trashed, deleted, or permanently deleted.[/yellow]\n")

    if not LATEST_QUEUE_FILE.exists():
        console.print("[red]latest_queue.json not found. Run inboxqueue first.[/red]")
        return

    payload = json.loads(LATEST_QUEUE_FILE.read_text(encoding="utf-8"))
    items = payload.get("queue_items", [])

    table = Table(title="Trash Eligibility Plan")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Decision", style="green")
    table.add_column("Category", style="magenta")
    table.add_column("Risk", style="yellow")
    table.add_column("Plan", style="red")
    table.add_column("Reason", style="blue")
    table.add_column("Subject", style="white")

    eligible = 0
    skipped = 0
    protected = 0

    for item in items:
        queue_id = item.get("queue_id")
        decision = item.get("local_decision")
        category = item.get("category")
        risk = int(item.get("risk_score") or 999)
        subject = str(item.get("subject", "(No subject)"))

        ok, reason = is_trash_candidate(item)

        if ok:
            plan = "WOULD TRASH"
            eligible += 1
        else:
            plan = "SKIP"
            skipped += 1
            if bool(item.get("manual_review")) or decision in PROTECTED_DECISIONS:
                protected += 1

        table.add_row(
            str(queue_id),
            str(decision),
            str(category),
            str(risk),
            plan,
            reason,
            subject[:70],
        )

    console.print(table)
    console.print(f"\n[bold green]Future trash candidates:[/bold green] {eligible}")
    console.print(f"[bold yellow]Protected/skipped locked items:[/bold yellow] {protected}")
    console.print(f"[bold yellow]Total skipped:[/bold yellow] {skipped}")
    console.print("\n[yellow]No Gmail changes were made.[/yellow]\n")


if __name__ == "__main__":
    main()
