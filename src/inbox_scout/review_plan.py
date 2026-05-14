from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"


PROTECTED_CATEGORIES = {
    "bills/receipts",
    "finance",
    "medical",
    "legal",
    "tax",
    "security",
    "client/business",
    "insurance",
    "manual review",
}


@dataclass
class QueueItemSummary:
    queue_id: str
    decision: str
    category: str
    risk: int
    sender: str
    subject: str
    suggested_bucket: str
    reason: str


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def risk_int(item: dict[str, Any]) -> int:
    raw = item.get("risk_score", item.get("risk", 999))
    try:
        return int(raw)
    except Exception:
        return 999


def load_items() -> list[dict[str, Any]]:
    if not LATEST_QUEUE.exists():
        return []

    data = json.loads(LATEST_QUEUE.read_text(encoding="utf-8-sig"))

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("queue_items", [])

    return []


def summarize_item(item: dict[str, Any]) -> QueueItemSummary:
    qid = clean(item.get("queue_id") or item.get("id") or "?")
    decision = clean(item.get("local_decision")).lower()
    category = clean(item.get("category"))
    category_key = category.lower()
    risk = risk_int(item)
    sender = clean(item.get("from") or item.get("sender"))
    subject = clean(item.get("subject"))

    manual_review = is_true(item.get("manual_review"))
    already_handled = bool(clean(item.get("gmail_action_type"))) or is_true(item.get("gmail_marked_read"))

    if already_handled:
        bucket = "already_handled"
        reason = "Already handled locally."

    elif manual_review or decision == "protected_review" or category_key in PROTECTED_CATEGORIES or risk >= 70:
        bucket = "protected"
        reason = "Protected because it looks important, sensitive, high-risk, or manual-review."

    elif decision in {"pending_review", "possible_archive_later"} and risk <= 40 and category_key in {"newsletter", "promotion"}:
        bucket = "possible_archive"
        reason = "Low-risk newsletter/promotion. Good candidate to archive later after approval."

    elif decision in {"pending_review", "possible_archive_later"} and risk <= 20 and category_key in {"newsletter", "promotion"}:
        bucket = "possible_trash"
        reason = "Very low-risk clutter. Could be a future Trash candidate after stronger approval."

    else:
        bucket = "needs_review"
        reason = "Not safe enough to act on automatically."

    return QueueItemSummary(
        queue_id=qid,
        decision=decision,
        category=category,
        risk=risk,
        sender=sender,
        subject=subject,
        suggested_bucket=bucket,
        reason=reason,
    )


def build_review_plan_message() -> str:
    items = load_items()

    if not items:
        return (
            "I do not see a current review queue yet.\n\n"
            "Ask me to sort 5 emails first.\n\n"
            "I did not touch Gmail."
        )

    summaries = [summarize_item(item) for item in items]

    protected = [s for s in summaries if s.suggested_bucket == "protected"]
    possible_archive = [s for s in summaries if s.suggested_bucket == "possible_archive"]
    possible_trash = [s for s in summaries if s.suggested_bucket == "possible_trash"]
    needs_review = [s for s in summaries if s.suggested_bucket == "needs_review"]
    already_handled = [s for s in summaries if s.suggested_bucket == "already_handled"]

    lines = [
        "Here is the safe review plan for the latest batch:",
        "",
        f"- Total emails: {len(summaries)}",
        f"- Protected / leave untouched: {len(protected)}",
        f"- Possible archive later: {len(possible_archive)}",
        f"- Possible Trash later: {len(possible_trash)}",
        f"- Needs review: {len(needs_review)}",
        f"- Already handled: {len(already_handled)}",
        "",
    ]

    if possible_archive:
        lines.append("Possible archive later:")
        for item in possible_archive[:5]:
            lines.append(f"- ID {item.queue_id}: {item.subject} | risk {item.risk} | {item.category}")
        lines.append("")

    if possible_trash:
        lines.append("Possible Trash later:")
        for item in possible_trash[:5]:
            lines.append(f"- ID {item.queue_id}: {item.subject} | risk {item.risk} | {item.category}")
        lines.append("")

    if protected:
        lines.append("Protected / untouched:")
        for item in protected[:5]:
            lines.append(f"- ID {item.queue_id}: {item.subject} | risk {item.risk} | {item.category}")
        lines.append("")

    lines.append("I am only showing the plan.")
    lines.append("I did not archive, move to Trash, mark read, reply, or delete anything.")

    return "\n".join(lines)


def main() -> None:
    print(build_review_plan_message())


if __name__ == "__main__":
    main()
