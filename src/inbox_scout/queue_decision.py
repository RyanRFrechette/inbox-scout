import argparse
import json
import re
from datetime import datetime

from rich.console import Console
from rich.table import Table

from inbox_scout.review_queue import LATEST_QUEUE_FILE, QUEUE_DIR

console = Console()

ALLOWED_DECISIONS = [
    "keep",
    "ignore",
    "review_later",
    "possible_archive_later",
    "protected_review"
]

# Maps natural-language phrases (lowercased) to local_decision values
DECISION_ALIASES: dict[str, str] = {
    "keep": "keep",
    "ignore": "ignore",
    "review later": "review_later",
    "possible archive later": "possible_archive_later",
}


def build_set_decision_message(text: str) -> str | None:
    """Parse 'keep 4', 'ignore 4', etc. and update local queue. Returns None if no match."""
    msg = text.lower().strip()

    matched_decision = None
    matched_id = None

    for alias in sorted(DECISION_ALIASES, key=len, reverse=True):  # longest-first to avoid prefix collision
        m = re.match(rf"^{re.escape(alias)}\s+(\d+)$", msg)
        if m:
            matched_decision = DECISION_ALIASES[alias]
            matched_id = int(m.group(1))
            break

    if matched_decision is None:
        return None

    if not LATEST_QUEUE_FILE.exists():
        return "No queue found. Say sort 5 emails first.\n\nGmail not touched."

    try:
        payload = json.loads(LATEST_QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Could not read queue: {e}\n\nGmail not touched."

    if isinstance(payload, list):
        items = payload
        is_list = True
    else:
        items = payload.get("queue_items", [])
        is_list = False

    target = None
    for item in items:
        if str(item.get("queue_id")) == str(matched_id):
            target = item
            break

    if not target:
        return f"No queue item found with ID {matched_id}.\n\nGmail not touched."

    old_decision = target.get("local_decision", "unknown")
    target["local_decision"] = matched_decision
    target["decision_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Preserve gmail_action_taken/gmail_action_type if a Gmail action already ran
    if not (target.get("gmail_action_taken") or target.get("gmail_action_type")):
        target["gmail_action_taken"] = False

    if not is_list:
        payload["last_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        LATEST_QUEUE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        save_decision_log(matched_id, old_decision, matched_decision, "via Telegram")
    except Exception as e:
        return f"Could not save queue: {e}\n\nGmail not touched."

    subject = str(target.get("subject", "(no subject)"))[:55]
    return (
        f"ID {matched_id} updated.\n\n"
        f"Decision: {matched_decision}\n"
        f"Subject: {subject}\n\n"
        "Gmail not touched."
    )


def save_decision_log(queue_id, old_decision, new_decision, note):
    log_path = QUEUE_DIR / "decision_log.jsonl"
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "queue_id": queue_id,
        "old_decision": old_decision,
        "new_decision": new_decision,
        "note": note or "",
        "gmail_action_taken": False
    }

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Update local Inbox Scout queue decision")
    parser.add_argument("--id", type=int, required=True, help="Queue ID to update")
    parser.add_argument("--decision", choices=ALLOWED_DECISIONS, required=True)
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    if not LATEST_QUEUE_FILE.exists():
        console.print("[red]No latest_queue.json found. Run inboxqueue first.[/red]")
        return

    payload = json.loads(LATEST_QUEUE_FILE.read_text(encoding="utf-8"))
    items = payload.get("queue_items", [])

    target = None
    for item in items:
        if item.get("queue_id") == args.id:
            target = item
            break

    if not target:
        console.print(f"[red]No queue item found with ID {args.id}.[/red]")
        return

    old_decision = target.get("local_decision")
    target["local_decision"] = args.decision
    target["decision_note"] = args.note
    target["decision_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target["gmail_action_taken"] = False

    payload["last_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LATEST_QUEUE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    save_decision_log(args.id, old_decision, args.decision, args.note)

    table = Table(title="Local Decision Updated")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Queue ID", str(args.id))
    table.add_row("Old decision", str(old_decision))
    table.add_row("New decision", str(args.decision))
    table.add_row("Subject", str(target.get("subject", "")))
    table.add_row("Gmail action taken", "False")

    console.print(table)
    console.print("[yellow]No Gmail changes were made.[/yellow]")


if __name__ == "__main__":
    main()
