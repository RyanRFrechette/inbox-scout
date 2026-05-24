import argparse
import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from inbox_scout.paths import REPORTS_DIR

console = Console()

QUEUE_DIR = REPORTS_DIR.parent / "review_queue"
LATEST_QUEUE_FILE = QUEUE_DIR / "latest_queue.json"


def find_latest_report_json():
    reports = sorted(
        REPORTS_DIR.glob("inbox_report_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not reports:
        raise FileNotFoundError("No inbox_report_*.json files found. Run report mode first.")

    return reports[0]


_KNOWN_ACCOUNTS = {"primary", "secondary"}


def build_queue_items(results, account=None):
    queue_items = []
    stamped_account = account if account in _KNOWN_ACCOUNTS else None

    for index, item in enumerate(results, start=1):
        ai = item.get("ai_classification", {})
        manual_review = bool(ai.get("manual_review"))

        entry = {
            "queue_id": index,
            "message_id": item.get("message_id"),
            "subject": item.get("subject", "(No subject)"),
            "from": item.get("from", ""),
            "date": item.get("date", ""),
            "category": ai.get("category", "Unknown"),
            "confidence_score": ai.get("confidence_score"),
            "risk_score": ai.get("risk_score"),
            "manual_review": manual_review,
            "suggested_action": ai.get("suggested_action", "Review manually."),
            "reason": ai.get("reason", ""),
            "snippet": item.get("snippet", ""),
            "local_decision": "protected_review" if manual_review else "pending_review",
            "gmail_action_taken": False,
        }
        if stamped_account is not None:
            entry["account"] = stamped_account

        queue_items.append(entry)

    return queue_items


def save_queue(queue_items, source_report):
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    queue_path = QUEUE_DIR / f"inbox_queue_{timestamp}.json"

    payload = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_report": str(source_report),
        "safety_mode": "LOCAL_ONLY_NO_GMAIL_CHANGES",
        "allowed_local_decisions": [
            "keep",
            "ignore",
            "review_later",
            "possible_archive_later",
            "protected_review"
        ],
        "queue_items": queue_items
    }

    queue_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LATEST_QUEUE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return queue_path


def print_queue_summary(queue_items, queue_path):
    protected = sum(1 for item in queue_items if item["manual_review"])
    pending = len(queue_items) - protected

    table = Table(title="Inbox Scout Local Review Queue")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green")

    table.add_row("Total queued emails", str(len(queue_items)))
    table.add_row("Protected/manual review", str(protected))
    table.add_row("Pending low-risk review", str(pending))

    console.print(table)
    console.print(f"\n[bold green]Local review queue created:[/bold green] {queue_path}")
    console.print("[yellow]No Gmail changes were made.[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="Inbox Scout Local Review Queue")
    parser.add_argument("--from-latest-report", action="store_true")
    parser.add_argument("--account", type=str, default=None)
    args = parser.parse_args()

    source_report = find_latest_report_json()
    results = json.loads(source_report.read_text(encoding="utf-8"))

    queue_items = build_queue_items(results, account=args.account)
    queue_path = save_queue(queue_items, source_report)

    print_queue_summary(queue_items, queue_path)


if __name__ == "__main__":
    main()
