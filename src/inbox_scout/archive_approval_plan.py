from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_ARCHIVE_PLAN = PLANS_DIR / "latest_archive_plan.json"


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
class ArchiveCandidate:
    queue_id: str
    category: str
    risk: int
    sender: str
    subject: str
    reason: str


@dataclass
class ArchivePlan:
    plan_id: str
    created_at: str
    status: str
    candidate_count: int
    candidates: list[ArchiveCandidate]
    gmail_changes_enabled: bool
    permanent_delete_enabled: bool
    safety_notes: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_plan_id() -> str:
    return datetime.now(timezone.utc).strftime("archiveplan_%Y%m%d_%H%M%S")


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


def is_safe_archive_candidate(item: dict[str, Any]) -> tuple[bool, str]:
    decision = clean(item.get("local_decision")).lower()
    category = clean(item.get("category")).lower()
    risk = risk_int(item)

    manual_review = is_true(item.get("manual_review"))
    already_handled = bool(clean(item.get("gmail_action_type"))) or is_true(item.get("gmail_marked_read"))

    if already_handled:
        return False, "Already handled locally."

    if manual_review:
        return False, "Manual review item."

    if decision == "protected_review":
        return False, "Protected review item."

    if category in PROTECTED_CATEGORIES:
        return False, "Protected category."

    if risk > 40:
        return False, "Risk score too high for archive planning."

    if category not in {"newsletter", "promotion"}:
        return False, "Only newsletter/promotion items are eligible for this archive plan."

    if decision not in {"pending_review", "possible_archive_later"}:
        return False, "Local decision is not eligible for archive planning."

    return True, "Low-risk newsletter/promotion. Safe archive candidate after approval."


def build_archive_plan() -> ArchivePlan:
    items = load_items()
    candidates: list[ArchiveCandidate] = []

    for item in items:
        ok, reason = is_safe_archive_candidate(item)

        if not ok:
            continue

        candidates.append(
            ArchiveCandidate(
                queue_id=clean(item.get("queue_id") or item.get("id") or "?"),
                category=clean(item.get("category")),
                risk=risk_int(item),
                sender=clean(item.get("from") or item.get("sender")),
                subject=clean(item.get("subject")),
                reason=reason,
            )
        )

    status = "candidates_found" if candidates else "no_candidates"

    return ArchivePlan(
        plan_id=make_plan_id(),
        created_at=now_iso(),
        status=status,
        candidate_count=len(candidates),
        candidates=candidates,
        gmail_changes_enabled=False,
        permanent_delete_enabled=False,
        safety_notes=[
            "Archive plan only.",
            "No Gmail changes were made.",
            "No emails were archived.",
            "No emails were moved to Trash.",
            "No emails were marked read.",
            "Permanent delete is disabled.",
        ],
    )


def save_plan(plan: ArchivePlan) -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_ARCHIVE_PLAN.write_text(json.dumps(asdict(plan), indent=2), encoding="utf-8")


def build_archive_plan_message() -> str:
    plan = build_archive_plan()
    save_plan(plan)

    if plan.candidate_count == 0:
        return (
            "I do not see anything safe to archive in the latest batch.\n\n"
            "I did not archive anything. I did not touch Gmail."
        )

    lines = [
        "I found a safe archive plan for the latest batch.",
        "",
        f"Possible archive candidates: {plan.candidate_count}",
        "",
    ]

    for item in plan.candidates[:5]:
        lines.append(f"- ID {item.queue_id}: {item.subject} | risk {item.risk} | {item.category}")

    lines.extend([
        "",
        "This is only a plan.",
        "I did not archive anything.",
        "I did not move anything to Trash.",
        "I did not mark anything read.",
        "",
        "Next, we will add a confirmation step before any Gmail action is allowed.",
    ])

    return "\n".join(lines)


def main() -> None:
    print(build_archive_plan_message())


if __name__ == "__main__":
    main()
