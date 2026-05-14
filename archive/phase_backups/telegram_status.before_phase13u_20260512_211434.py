from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from inbox_scout.telegram_notifier import send_message


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"
LOGS_DIR = PROJECT_ROOT / "data" / "logs"
DECISION_LOG = PROJECT_ROOT / "data" / "review_queue" / "decision_log.jsonl"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


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
            pass
    return rows


def load_queue_items() -> list[dict[str, Any]]:
    if not LATEST_QUEUE.exists():
        return []

    data = json.loads(LATEST_QUEUE.read_text(encoding="utf-8"))

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("queue_items", [])

    return []


def item_id(item: dict[str, Any]) -> str:
    return clean(item.get("queue_id") or item.get("id") or "?")


def build_status_message() -> str:
    items = load_queue_items()

    archive_logs = load_jsonl(LOGS_DIR / "archive_actions.jsonl")
    trash_logs = load_jsonl(LOGS_DIR / "trash_actions.jsonl")
    mark_logs = load_jsonl(LOGS_DIR / "mark_read_actions.jsonl")
    decision_logs = load_jsonl(DECISION_LOG)

    protected = [
        item for item in items
        if clean(item.get("local_decision")).lower() == "protected_review"
        or is_true(item.get("manual_review"))
    ]

    archived = [
        item for item in items
        if clean(item.get("gmail_action_type")).lower() == "archived"
        and is_true(item.get("gmail_action_taken"))
    ]

    trashed = [
        item for item in items
        if clean(item.get("gmail_action_type")).lower() == "trashed"
        and is_true(item.get("gmail_action_taken"))
    ]

    marked_read = [
        item for item in items
        if is_true(item.get("gmail_marked_read"))
        or clean(item.get("gmail_read_action_type")).lower() == "marked_read"
    ]

    decision_counts = Counter(clean(item.get("local_decision")) or "blank" for item in items)

    handled_lines = []
    for item in items:
        action = clean(item.get("gmail_action_type"))
        read = is_true(item.get("gmail_marked_read"))
        if action or read:
            handled_lines.append(
                f"- ID {item_id(item)}: {action or 'no_action'}"
                f"{' + marked_read' if read else ''} | {clean(item.get('subject'))[:45]}"
            )

    protected_lines = []
    for item in protected:
        protected_lines.append(
            f"- ID {item_id(item)}: risk {clean(item.get('risk_score') or item.get('risk'))} | "
            f"{clean(item.get('subject'))[:45]}"
        )

    message = (
        "Inbox Scout Status / Audit\n\n"
        "Current batch rule: 5 emails at a time\n"
        "Mode: safe/local audit\n\n"
        f"Latest queue items: {len(items)}\n"
        f"Protected/manual-review: {len(protected)}\n"
        f"Archived: {len(archived)}\n"
        f"Trashed: {len(trashed)}\n"
        f"Marked read: {len(marked_read)}\n\n"
        f"Archive log entries: {len(archive_logs)}\n"
        f"Trash log entries: {len(trash_logs)}\n"
        f"Mark-read log entries: {len(mark_logs)}\n"
        f"Decision log entries: {len(decision_logs)}\n\n"
        "Decision counts:\n"
        + "\n".join(f"- {k}: {v}" for k, v in sorted(decision_counts.items()))
        + "\n\nHandled items:\n"
        + ("\n".join(handled_lines) if handled_lines else "- None")
        + "\n\nProtected / untouched:\n"
        + ("\n".join(protected_lines) if protected_lines else "- None")
        + "\n\nSafety:\n"
        "- Permanent deletes: 0\n"
        "- Replies sent: 0\n"
        "- Gmail changes made by this Telegram status command: 0"
    )

    return message


def main() -> None:
    message = build_status_message()
    result = send_message(message)
    print("Telegram status send OK:", result.get("ok"))


if __name__ == "__main__":
    main()
