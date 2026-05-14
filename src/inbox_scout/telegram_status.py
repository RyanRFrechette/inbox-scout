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
TRASH_EXECUTION_LOG = LOGS_DIR / "trash_execution_runs.jsonl"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def norm(value: Any) -> str:
    return clean(value).lower()


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


def item_subject(item: dict[str, Any]) -> str:
    return clean(item.get("subject") or "(no subject)")


def item_category(item: dict[str, Any]) -> str:
    return clean(item.get("category") or item.get("final_category") or item.get("label") or "unknown")


def item_risk(item: dict[str, Any]) -> str:
    return clean(item.get("risk_score") or item.get("risk") or "?")


def item_sender(item: dict[str, Any]) -> str:
    return clean(
        item.get("from")
        or item.get("sender")
        or item.get("from_email")
        or item.get("sender_email")
        or "unknown"
    )


def is_gmail_handled(item: dict[str, Any]) -> bool:
    action = norm(item.get("gmail_action_type"))
    return (
        is_true(item.get("gmail_action_taken"))
        or is_true(item.get("gmail_trashed"))
        or is_true(item.get("gmail_archived"))
        or is_true(item.get("gmail_marked_read"))
        or action in {"trashed", "archived"}
    )


def is_review_needed(item: dict[str, Any]) -> bool:
    if is_gmail_handled(item):
        return False

    decision = norm(item.get("local_decision"))

    if decision in {"pending_review", "protected_review"}:
        return True

    if is_true(item.get("manual_review")) or is_true(item.get("manual_review_required")):
        return True

    category = norm(item_category(item))
    if category in {
        "medical",
        "health",
        "finance",
        "financial",
        "banking",
        "legal",
        "tax",
        "security",
        "bill",
        "bills",
        "receipt",
        "receipts",
        "insurance",
        "client",
        "business",
        "client/business",
        "work",
        "job",
        "account",
    }:
        return True

    return False


def build_moved_message() -> str:
    rows = load_jsonl(TRASH_EXECUTION_LOG)
    items = load_queue_items()

    successful_runs = [
        row for row in rows
        if row.get("status") == "applied"
        and row.get("trashed_ids")
    ]

    if not successful_runs:
        return "Nothing moved yet. Gmail not touched."

    latest = successful_runs[-1]
    moved_ids = [str(x) for x in latest.get("trashed_ids", [])]

    lines = [
        "Last Gmail move I made:",
        "",
        f"Action: moved to Gmail Trash for manual review",
        f"Run: {clean(latest.get('run_id'))}",
        f"Moved count: {len(moved_ids)}",
        "",
    ]

    for qid in moved_ids:
        item = next((x for x in items if item_id(x) == qid), {})
        lines.append(
            f"- ID {qid}: {item_subject(item)} | "
            f"risk {item_risk(item)} | {item_category(item)}"
        )

    lines.extend([
        "",
        "Moved to Trash only. No archive, delete, or mark-read.",
    ])

    return "\n".join(lines)


def build_still_needs_review_message() -> str:
    items = load_queue_items()
    remaining = [item for item in items if is_review_needed(item)]
    already_handled = [item for item in items if is_gmail_handled(item)]

    lines = [
        "Still needs review:",
        "",
        f"Remaining review items: {len(remaining)}",
        f"Already handled: {len(already_handled)}",
        "",
    ]

    if not remaining:
        lines.append("Nothing needs review in the current batch.")
    else:
        for item in remaining:
            lines.append(
                f"- ID {item_id(item)}: {item_subject(item)} | "
                f"risk {item_risk(item)} | {item_category(item)}"
            )

    lines.extend([
        "",
        "Already-trashed items not shown. Gmail not touched.",
    ])

    return "\n".join(lines)


def build_status_message() -> str:
    items = load_queue_items()

    archive_logs = load_jsonl(LOGS_DIR / "archive_actions.jsonl")
    trash_logs = load_jsonl(TRASH_EXECUTION_LOG)
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

    review_remaining = [item for item in items if is_review_needed(item)]

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
        "Inbox Scout Status\n\n"
        f"Queue: {len(items)} | Needs review: {len(review_remaining)} | Protected: {len(protected)}\n"
        f"Archived: {len(archived)} | Trashed: {len(trashed)} | Marked read: {len(marked_read)}\n\n"
        "Decisions:\n"
        + "\n".join(f"- {k}: {v}" for k, v in sorted(decision_counts.items()))
        + "\n\nHandled:\n"
        + ("\n".join(handled_lines) if handled_lines else "- None")
        + "\n\nProtected:\n"
        + ("\n".join(protected_lines) if protected_lines else "- None")
        + "\n\nRead-only. No Gmail changes."
    )

    return message


def main() -> None:
    message = build_status_message()
    result = send_message(message)
    print("Telegram status send OK:", result.get("ok"))


if __name__ == "__main__":
    main()
