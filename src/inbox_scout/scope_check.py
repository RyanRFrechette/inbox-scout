import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()

TOKENS = [
    {
        "name": "Readonly token",
        "path": Path("token.json"),
        "expected_scope": "https://www.googleapis.com/auth/gmail.readonly"
    },
    {
        "name": "Modify token",
        "path": Path("token_modify.json"),
        "expected_scope": "https://www.googleapis.com/auth/gmail.modify"
    }
]


def load_scopes(path):
    if not path.exists():
        return None

    token_data = json.loads(path.read_text(encoding="utf-8"))
    return token_data.get("scopes", [])


def main():
    console.print("\n[bold cyan]Inbox Scout Gmail Scope Check[/bold cyan]\n")

    table = Table(title="Gmail OAuth Token Status")
    table.add_column("Token", style="cyan")
    table.add_column("Exists", style="green")
    table.add_column("Expected Scope Present", style="yellow")
    table.add_column("Can Modify Gmail", style="red")

    for token in TOKENS:
        scopes = load_scopes(token["path"])
        exists = scopes is not None
        expected_present = bool(scopes and token["expected_scope"] in scopes)
        can_modify = bool(scopes and "https://www.googleapis.com/auth/gmail.modify" in scopes)

        table.add_row(
            token["name"],
            str(exists),
            str(expected_present),
            str(can_modify)
        )

    console.print(table)

    console.print("\n[bold yellow]Scope details:[/bold yellow]")

    for token in TOKENS:
        scopes = load_scopes(token["path"])
        console.print(f"\n[bold]{token['name']}:[/bold] {token['path']}")

        if scopes is None:
            console.print("- Missing")
            continue

        for scope in scopes:
            console.print(f"- {scope}")

    console.print("\n[yellow]No Gmail changes were made.[/yellow]")


if __name__ == "__main__":
    main()
