from rich.console import Console
from rich.table import Table

from inbox_scout.paths import verify_project_structure

console = Console()


def run_phase_0_check() -> None:
    console.print("\n[bold cyan]Inbox Scout Phase 0 Health Check[/bold cyan]\n")

    results = verify_project_structure()

    table = Table(title="Project Structure Check")
    table.add_column("Path", style="white")
    table.add_column("Status", style="green")

    all_good = True

    for path, exists in results.items():
        status = "OK" if exists else "MISSING"
        if not exists:
            all_good = False
        table.add_row(path, status)

    console.print(table)

    if all_good:
        console.print("\n[bold green]Phase 0 success: Inbox Scout project structure is ready.[/bold green]")
        console.print("[yellow]Next phase: Gmail read-only connection test.[/yellow]\n")
    else:
        console.print("\n[bold red]Phase 0 failed: Some files or folders are missing.[/bold red]\n")


if __name__ == "__main__":
    run_phase_0_check()
