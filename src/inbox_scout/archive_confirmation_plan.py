from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_ARCHIVE_PLAN = PLANS_DIR / "latest_archive_plan.json"
LATEST_ARCHIVE_CONFIRMATION_PLAN = PLANS_DIR / "latest_archive_confirmation_plan.json"


@dataclass
class ArchiveConfirmationPlan:
    confirmation_id: str
    created_at: str
    source_archive_plan_id: str | None
    status: str
    candidate_count: int
    candidate_ids: list[str]
    gmail_changes_enabled: bool
    archive_execution_enabled: bool
    permanent_delete_enabled: bool
    required_future_confirmation: str
    safety_notes: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_confirmation_id() -> str:
    return datetime.now(timezone.utc).strftime("archiveconfirm_%Y%m%d_%H%M%S")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_confirmation_plan(plan: ArchiveConfirmationPlan) -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_ARCHIVE_CONFIRMATION_PLAN.write_text(
        json.dumps(asdict(plan), indent=2),
        encoding="utf-8",
    )


def build_archive_confirmation_plan() -> ArchiveConfirmationPlan:
    archive_plan = load_json(LATEST_ARCHIVE_PLAN)
    candidates = archive_plan.get("candidates", [])

    candidate_ids = [
        str(item.get("queue_id"))
        for item in candidates
        if item.get("queue_id") is not None
    ]

    if not archive_plan:
        status = "blocked_no_archive_plan"
        required_future_confirmation = "Run archive planning first."
        notes = [
            "No archive plan exists yet.",
            "No Gmail changes were made.",
        ]

    elif archive_plan.get("gmail_changes_enabled") is True:
        status = "blocked_unexpected_gmail_enabled"
        required_future_confirmation = "Blocked for safety."
        notes = [
            "Archive plan unexpectedly had Gmail changes enabled.",
            "Blocked for safety.",
            "No Gmail changes were made.",
        ]

    elif not candidate_ids:
        status = "blocked_no_candidates"
        required_future_confirmation = "No archive confirmation available."
        notes = [
            "No safe archive candidates were found.",
            "No Gmail changes were made.",
        ]

    else:
        status = "awaiting_future_confirmation"
        required_future_confirmation = "confirm archive"
        notes = [
            "Archive confirmation plan only.",
            "No Gmail changes were made.",
            "No emails were archived.",
            "No emails were moved to Trash.",
            "No emails were marked read.",
            "Permanent delete is disabled.",
            "Archive execution remains disabled until a later phase.",
        ]

    return ArchiveConfirmationPlan(
        confirmation_id=make_confirmation_id(),
        created_at=now_iso(),
        source_archive_plan_id=archive_plan.get("plan_id"),
        status=status,
        candidate_count=len(candidate_ids),
        candidate_ids=candidate_ids,
        gmail_changes_enabled=False,
        archive_execution_enabled=False,
        permanent_delete_enabled=False,
        required_future_confirmation=required_future_confirmation,
        safety_notes=notes,
    )


def build_archive_confirmation_message() -> str:
    archive_plan = load_json(LATEST_ARCHIVE_PLAN)
    plan = build_archive_confirmation_plan()
    save_confirmation_plan(plan)

    if plan.status == "blocked_no_archive_plan":
        return (
            "I do not have an archive plan ready yet.\n\n"
            "Ask me: what can be archived\n\n"
            "I did not touch Gmail."
        )

    if plan.status == "blocked_no_candidates":
        return (
            "I do not see anything safe to archive right now.\n\n"
            "I did not touch Gmail."
        )

    if plan.status != "awaiting_future_confirmation":
        return (
            "I blocked archive confirmation for safety.\n\n"
            "I did not touch Gmail."
        )

    candidates = archive_plan.get("candidates", [])

    lines = [
        "I can prepare this archive action, but I am not allowed to run it yet.",
        "",
        f"Safe archive candidates: {plan.candidate_count}",
        "",
    ]

    for item in candidates[:5]:
        lines.append(
            f"- ID {item.get('queue_id')}: {item.get('subject')} | risk {item.get('risk')} | {item.get('category')}"
        )

    lines.extend([
        "",
        "This is still confirmation planning only.",
        "I did not archive anything.",
        "I did not move anything to Trash.",
        "I did not mark anything read.",
        "",
        "In a later phase, this will require a final confirmation before Gmail changes are allowed.",
    ])

    return "\n".join(lines)


def main() -> None:
    print(build_archive_confirmation_message())


if __name__ == "__main__":
    main()
