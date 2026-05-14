import csv
import json
from datetime import datetime

from rich.console import Console
from rich.table import Table

from inbox_scout.gmail_auth import get_gmail_service
from inbox_scout.paths import RAW_DIR

console = Console()


def get_header(headers, name):
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def fetch_inbox_emails(limit=25):
    service = get_gmail_service()

    results = service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        maxResults=limit
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        message_id = msg["id"]

        message = service.users().messages().get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()

        headers = message.get("payload", {}).get("headers", [])

        email_data = {
            "message_id": message_id,
            "from": get_header(headers, "From"),
            "subject": get_header(headers, "Subject"),
            "date": get_header(headers, "Date"),
            "snippet": message.get("snippet", "")
        }

        emails.append(email_data)

    return emails


def save_results(emails):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = RAW_DIR / f"inbox_fetch_{timestamp}.json"
    csv_path = RAW_DIR / f"inbox_fetch_{timestamp}.csv"

    json_path.write_text(
        json.dumps(emails, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["message_id", "from", "subject", "date", "snippet"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(emails)

    return json_path, csv_path


def print_summary(emails):
    table = Table(title="Latest Inbox Emails")
    table.add_column("#", style="cyan", width=4)
    table.add_column("From", style="green", overflow="fold")
    table.add_column("Subject", style="white", overflow="fold")
    table.add_column("Date", style="yellow", overflow="fold")

    for index, email in enumerate(emails, start=1):
        table.add_row(
            str(index),
            email["from"][:60],
            email["subject"][:80],
            email["date"][:40]
        )

    console.print(table)


def main():
    console.print("\n[bold cyan]Inbox Scout Phase 2: Basic Inbox Fetcher[/bold cyan]\n")
    console.print("[yellow]Read-only mode. No emails will be changed, archived, deleted, or labeled.[/yellow]\n")

    emails = fetch_inbox_emails(limit=25)

    print_summary(emails)

    json_path, csv_path = save_results(emails)

    console.print(f"\n[bold green]Fetched {len(emails)} inbox emails safely.[/bold green]")
    console.print(f"JSON saved: {json_path}")
    console.print(f"CSV saved: {csv_path}")
    console.print("\n[yellow]No Gmail changes were made.[/yellow]\n")


if __name__ == "__main__":
    main()
