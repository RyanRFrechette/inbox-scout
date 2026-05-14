import argparse

from rich.console import Console
from rich.table import Table

from inbox_scout.gmail_auth import get_gmail_service

console = Console()

INBOX_SCOUT_LABELS = [
    "InboxScout/Protected Review",
    "InboxScout/Possible Archive Later",
    "InboxScout/Keep",
    "InboxScout/Review Later",
    "InboxScout/Ignore",
]


def get_existing_labels(service):
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])
    return {label["name"]: label for label in labels}


def create_label(service, name):
    body = {
        "name": name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }

    return service.users().labels().create(userId="me", body=body).execute()


def main():
    parser = argparse.ArgumentParser(description="Inbox Scout Gmail Label Manager")
    parser.add_argument("--create", action="store_true", help="Actually create missing labels")
    args = parser.parse_args()

    console.print("\n[bold cyan]Inbox Scout Gmail Label Manager[/bold cyan]\n")

    if not args.create:
        console.print("[yellow]Dry-run mode. No Gmail labels will be created.[/yellow]\n")
    else:
        console.print("[yellow]Create mode. Missing Inbox Scout labels will be created.[/yellow]\n")

    service = get_gmail_service(mode="modify")
    existing = get_existing_labels(service)

    table = Table(title="Inbox Scout Label Plan")
    table.add_column("Label", style="cyan")
    table.add_column("Exists", style="green")
    table.add_column("Action", style="yellow")

    for label_name in INBOX_SCOUT_LABELS:
        exists = label_name in existing

        if exists:
            action = "Already exists"
        elif args.create:
            create_label(service, label_name)
            action = "Created"
        else:
            action = "Would create"

        table.add_row(label_name, str(exists), action)

    console.print(table)

    if args.create:
        console.print("\n[bold green]Label setup complete.[/bold green]")
        console.print("[yellow]Only labels may have been created. No emails were labeled, archived, deleted, or replied to.[/yellow]\n")
    else:
        console.print("\n[yellow]Dry run complete. No Gmail changes were made.[/yellow]\n")


if __name__ == "__main__":
    main()
