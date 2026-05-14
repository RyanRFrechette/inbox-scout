from rich.console import Console

from inbox_scout.gmail_auth import get_gmail_service

console = Console()


def main():
    console.print("\n[bold cyan]Inbox Scout Modify Token Setup[/bold cyan]\n")
    console.print("[yellow]This will request Gmail modify permission only.[/yellow]")
    console.print("[yellow]This will NOT archive, delete, label, reply, or change Gmail.[/yellow]\n")

    service = get_gmail_service(mode="modify")
    profile = service.users().getProfile(userId="me").execute()

    console.print("\n[bold green]Gmail modify token created successfully.[/bold green]")
    console.print(f"Email: {profile.get('emailAddress')}")
    console.print(f"Total messages: {profile.get('messagesTotal')}")
    console.print(f"Total threads: {profile.get('threadsTotal')}")
    console.print("\n[yellow]No Gmail changes were made.[/yellow]\n")


if __name__ == "__main__":
    main()
