import argparse
import json

from rich.console import Console
from rich.table import Table

from inbox_scout.gmail_auth import get_gmail_service
from inbox_scout.review_queue import LATEST_QUEUE_FILE

console = Console()

DECISION_TO_LABEL = {
    "protected_review": "InboxScout/Protected Review",
    "possible_archive_later": "InboxScout/Possible Archive Later",
    "keep": "InboxScout/Keep",
    "review_later": "InboxScout/Review Later",
    "ignore": "InboxScout/Ignore",
}


def get_label_map(service):
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])
    return {label["name"]: label["id"] for label in labels}


def main():
    parser = argparse.ArgumentParser(description="Inbox Scout Label Applier")
    parser.add_argument("--apply", action="store_true", help="Actually apply Gmail labels")
    args = parser.parse_args()

    console.print("\n[bold cyan]Inbox Scout Label Applier[/bold cyan]\n")

    if args.apply:
        console.print("[yellow]APPLY MODE: Gmail labels will be applied to matching emails.[/yellow]\n")
    else:
        console.print("[yellow]Dry-run mode. No Gmail labels will be applied.[/yellow]\n")

    if not LATEST_QUEUE_FILE.exists():
        console.print("[red]latest_queue.json not found. Run inboxqueue first.[/red]")
        return

    payload = json.loads(LATEST_QUEUE_FILE.read_text(encoding="utf-8"))
    items = payload.get("queue_items", [])

    service = get_gmail_service(mode="modify")
    label_map = get_label_map(service)

    table = Table(title="Inbox Scout Label Plan")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Decision", style="green")
    table.add_column("Label", style="yellow")
    table.add_column("Action", style="magenta")
    table.add_column("Subject", style="white")

    applied_count = 0
    skipped_count = 0

    for item in items:
        queue_id = item.get("queue_id")
        decision = item.get("local_decision")
        subject = str(item.get("subject", "(No subject)"))
        message_id = item.get("message_id")

        label_name = DECISION_TO_LABEL.get(decision)

        if not label_name:
            action = "Skipped - no label mapping"
            skipped_count += 1
            table.add_row(str(queue_id), str(decision), "None", action, subject[:70])
            continue

        label_id = label_map.get(label_name)

        if not label_id:
            action = "Skipped - label missing"
            skipped_count += 1
            table.add_row(str(queue_id), str(decision), label_name, action, subject[:70])
            continue

        if not message_id:
            action = "Skipped - missing message_id"
            skipped_count += 1
            table.add_row(str(queue_id), str(decision), label_name, action, subject[:70])
            continue

        if args.apply:
            body = {"addLabelIds": [label_id], "removeLabelIds": []}
            service.users().messages().modify(
                userId="me",
                id=message_id,
                body=body
            ).execute()
            item["gmail_label_applied"] = label_name
            item["gmail_label_applied_id"] = label_id
            action = "Applied"
            applied_count += 1
        else:
            action = "Would apply"
            applied_count += 1

        table.add_row(str(queue_id), str(decision), label_name, action, subject[:70])

    console.print(table)

    if args.apply:
        LATEST_QUEUE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"\n[bold green]Applied labels to {applied_count} emails.[/bold green]")
        console.print(f"[yellow]Skipped: {skipped_count}[/yellow]")
        console.print("[yellow]No emails were archived, deleted, or replied to.[/yellow]\n")
    else:
        console.print(f"\n[yellow]Dry run complete. Would label {applied_count} emails. Skipped: {skipped_count}.[/yellow]")
        console.print("[yellow]No Gmail changes were made.[/yellow]\n")


if __name__ == "__main__":
    main()
