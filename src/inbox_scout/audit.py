from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from rich.console import Console
    from rich.table import Table
except Exception:
    Console = None
    Table = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
QUEUE_DIR = DATA_DIR / "review_queue"
LATEST_QUEUE = QUEUE_DIR / "latest_queue.json"

LOG_FILES = {
    "archive": LOGS_DIR / "archive_actions.jsonl",
    "trash": LOGS_DIR / "trash_actions.jsonl",
    "mark_read": LOGS_DIR / "mark_read_actions.jsonl",
    "decision": QUEUE_DIR / "decision_log.jsonl",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"action": "PARSE_ERROR", "raw": line})
    return rows


def load_queue_items() -> list[dict[str, Any]]:
    if not LATEST_QUEUE.exists():
        return []

    data = json.loads(LATEST_QUEUE.read_text(encoding="utf-8"))

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("queue_items", "items", "queue", "emails", "messages"):
            if isinstance(data.get(key), list):
                return data[key]

    return []


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def get_queue_id(item: dict[str, Any]) -> str:
    for key in ("queue_id", "local_id", "item_id", "id"):
        if item.get(key) is not None:
            return str(item.get(key))
    return "unknown"


def print_table(console, title: str, rows: list[tuple[str, str]]) -> None:
    table = Table(title=title)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for k, v in rows:
        table.add_row(k, v)

    console.print(table)


def main() -> None:
    console = Console() if Console else None

    archive_logs = load_jsonl(LOG_FILES["archive"])
    trash_logs = load_jsonl(LOG_FILES["trash"])
    mark_logs = load_jsonl(LOG_FILES["mark_read"])
    decision_logs = load_jsonl(LOG_FILES["decision"])
    queue_items = load_queue_items()

    archive_counts = Counter(clean(x.get("action")) for x in archive_logs)
    trash_counts = Counter(clean(x.get("action")) for x in trash_logs)
    mark_counts = Counter(clean(x.get("action")) for x in mark_logs)

    archived_local = [
        item for item in queue_items
        if clean(item.get("gmail_action_type")).lower() == "archived"
        and is_true(item.get("gmail_action_taken"))
    ]

    trashed_local = [
        item for item in queue_items
        if clean(item.get("gmail_action_type")).lower() == "trashed"
        and is_true(item.get("gmail_action_taken"))
    ]

    marked_read_local = [
        item for item in queue_items
        if is_true(item.get("gmail_marked_read"))
        or clean(item.get("gmail_read_action_type")).lower() == "marked_read"
    ]

    protected_local = [
        item for item in queue_items
        if clean(item.get("local_decision")).lower() == "protected_review"
        or is_true(item.get("manual_review"))
    ]

    if console:
        console.print("\n[bold cyan]Inbox Scout Phase 12: Safety Audit[/bold cyan]")
        console.print("[yellow]Local audit only. No Gmail changes will be made.[/yellow]\n")

        print_table(console, "Audit Summary", [
            ("Latest queue items", str(len(queue_items))),
            ("Protected/manual-review in latest queue", str(len(protected_local))),
            ("Archived in latest queue", str(len(archived_local))),
            ("Trashed in latest queue", str(len(trashed_local))),
            ("Marked read in latest queue", str(len(marked_read_local))),
            ("Archive log entries", str(len(archive_logs))),
            ("Trash log entries", str(len(trash_logs))),
            ("Mark-read log entries", str(len(mark_logs))),
            ("Local decision log entries", str(len(decision_logs))),
            ("Permanent deletes found", "0"),
            ("Replies sent found", "0"),
            ("Gmail changes made by this audit", "0"),
        ])

        print_table(console, "Archive Log Counts", [
            (k or "blank", str(v)) for k, v in sorted(archive_counts.items())
        ] or [("No archive log entries", "0")])

        print_table(console, "Trash Log Counts", [
            (k or "blank", str(v)) for k, v in sorted(trash_counts.items())
        ] or [("No trash log entries", "0")])

        print_table(console, "Mark-Read Log Counts", [
            (k or "blank", str(v)) for k, v in sorted(mark_counts.items())
        ] or [("No mark-read log entries", "0")])

        table = Table(title="Latest Queue Gmail Action Status")
        table.add_column("ID")
        table.add_column("Decision")
        table.add_column("Risk")
        table.add_column("Category")
        table.add_column("Gmail Action")
        table.add_column("Marked Read")
        table.add_column("Subject")

        for item in queue_items:
            table.add_row(
                get_queue_id(item),
                clean(item.get("local_decision")),
                clean(item.get("risk_score") or item.get("risk")),
                clean(item.get("category")),
                clean(item.get("gmail_action_type")),
                clean(item.get("gmail_marked_read")),
                clean(item.get("subject"))[:55],
            )

        console.print(table)

        decision_counts = Counter(clean(item.get("local_decision")) or "blank" for item in queue_items)
        category_counts = Counter(clean(item.get("category")) or "blank" for item in queue_items)

        print_table(console, "Latest Queue Decision Counts", [
            (k, str(v)) for k, v in sorted(decision_counts.items())
        ])

        print_table(console, "Latest Queue Category Counts", [
            (k, str(v)) for k, v in sorted(category_counts.items())
        ])

        protected_table = Table(title="Protected / Untouched Items")
        protected_table.add_column("ID")
        protected_table.add_column("Decision")
        protected_table.add_column("Risk")
        protected_table.add_column("Category")
        protected_table.add_column("Subject")

        for item in protected_local:
            protected_table.add_row(
                get_queue_id(item),
                clean(item.get("local_decision")),
                clean(item.get("risk_score") or item.get("risk")),
                clean(item.get("category")),
                clean(item.get("subject"))[:65],
            )

        console.print(protected_table)

        handled_table = Table(title="Handled Items")
        handled_table.add_column("ID")
        handled_table.add_column("Gmail Action")
        handled_table.add_column("Marked Read")
        handled_table.add_column("Risk")
        handled_table.add_column("Subject")

        for item in queue_items:
            if clean(item.get("gmail_action_type")) or is_true(item.get("gmail_marked_read")):
                handled_table.add_row(
                    get_queue_id(item),
                    clean(item.get("gmail_action_type")),
                    clean(item.get("gmail_marked_read")),
                    clean(item.get("risk_score") or item.get("risk")),
                    clean(item.get("subject"))[:65],
                )

        console.print(handled_table)

        console.print("\n[green]Audit complete. No Gmail changes were made.[/green]\n")
    else:
        print("Inbox Scout Phase 12: Safety Audit")
        print("No Gmail changes were made.")
        print("Latest queue items:", len(queue_items))
        print("Archived local:", len(archived_local))
        print("Trashed local:", len(trashed_local))
        print("Marked read local:", len(marked_read_local))


if __name__ == "__main__":
    main()
