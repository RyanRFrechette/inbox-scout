import argparse

from rich.console import Console

from inbox_scout.gmail_auth import get_gmail_service

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Verify a Gmail account slot is authorized correctly")
    parser.add_argument("--account", default="primary", help="Account slot to verify (default: primary)")
    parser.add_argument("--mode", choices=["readonly", "modify", "settings"], default="modify",
                        help="Auth mode to use (default: modify)")
    args = parser.parse_args()

    console.print(f"\n[bold cyan]Gmail Account Check[/bold cyan]")
    console.print(f"Account slot : [yellow]{args.account}[/yellow]")
    console.print(f"Auth mode    : [yellow]{args.mode}[/yellow]\n")

    service = get_gmail_service(mode=args.mode, account=args.account)
    profile = service.users().getProfile(userId="me").execute()

    email = profile.get("emailAddress", "(unknown)")
    console.print(f"[bold green]Authorized as:[/bold green] {email}")
    console.print("\n[yellow]No Gmail labels or messages were changed.[/yellow]\n")


if __name__ == "__main__":
    main()
