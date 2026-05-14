from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"

LATEST_TRASH_PLAN = PLANS_DIR / "latest_trash_plan.json"
LATEST_TRASH_CONFIRMATION_PLAN = PLANS_DIR / "latest_trash_confirmation_plan.json"


@dataclass
class TrashConfirmationPlan:
    confirmation_id: str
    created_at: str
    source_trash_plan_id: str | None
    status: str
    candidate_count: int
    candidate_ids: list[str]
    gmail_changes_enabled: bool
    trash_execution_enabled: bool
    permanent_delete_enabled: bool
    required_future_confirmation: str
    safety_notes: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_confirmation_id() -> str:
    return datetime.now(timezone.utc).strftime("trashconfirm_%Y%m%d_%H%M%S")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_confirmation_plan(plan: TrashConfirmationPlan) -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_TRASH_CONFIRMATION_PLAN.write_text(
        json.dumps(asdict(plan), indent=2),
        encoding="utf-8",
    )


def build_trash_confirmation_plan() -> TrashConfirmationPlan:
    trash_plan = load_json(LATEST_TRASH_PLAN)
    candidates = trash_plan.get("candidates", [])

    candidate_ids = [
        str(item.get("queue_id"))
        for item in candidates
        if item.get("queue_id") is not None
    ]

    if not trash_plan:
        status = "blocked_no_trash_plan"
        required_future_confirmation = "Run Trash planning first."
        notes = [
            "No Trash plan exists yet.",
            "No Gmail changes were made.",
        ]

    elif trash_plan.get("gmail_changes_enabled") is True:
        status = "blocked_unexpected_gmail_enabled"
        required_future_confirmation = "Blocked for safety."
        notes = [
            "Trash plan unexpectedly had Gmail changes enabled.",
            "Blocked for safety.",
            "No Gmail changes were made.",
        ]

    elif trash_plan.get("permanent_delete_enabled") is True:
        status = "blocked_permanent_delete_enabled"
        required_future_confirmation = "Blocked for safety."
        notes = [
            "Trash plan unexpectedly had permanent delete enabled.",
            "Blocked for safety.",
            "No Gmail changes were made.",
        ]

    elif not candidate_ids:
        status = "blocked_no_candidates"
        required_future_confirmation = "No Trash confirmation available."
        notes = [
            "No safe Trash candidates were found.",
            "No Gmail changes were made.",
        ]

    else:
        status = "awaiting_future_confirmation"
        required_future_confirmation = "confirm trash"
        notes = [
            "Trash confirmation plan only.",
            "No Gmail changes were made.",
            "No emails were moved to Trash.",
            "No emails were permanently deleted.",
            "Permanent delete is disabled.",
            "Trash execution remains disabled until a later phase.",
            "Trash means Gmail Trash review folder, not permanent delete.",
        ]

    return TrashConfirmationPlan(
        confirmation_id=make_confirmation_id(),
        created_at=now_iso(),
        source_trash_plan_id=trash_plan.get("plan_id"),
        status=status,
        candidate_count=len(candidate_ids),
        candidate_ids=candidate_ids,
        gmail_changes_enabled=False,
        trash_execution_enabled=False,
        permanent_delete_enabled=False,
        required_future_confirmation=required_future_confirmation,
        safety_notes=notes,
    )


def build_trash_confirmation_message() -> str:
    trash_plan = load_json(LATEST_TRASH_PLAN)
    plan = build_trash_confirmation_plan()
    save_confirmation_plan(plan)

    if plan.status == "blocked_no_trash_plan":
        return (
            "I do not have a Trash plan ready yet.\n\n"
            "Ask me: what can go to trash\n\n"
            "I did not touch Gmail."
        )

    if plan.status == "blocked_no_candidates":
        return (
            "I do not see anything safe to move to Trash right now.\n\n"
            "I did not touch Gmail."
        )

    if plan.status != "awaiting_future_confirmation":
        return (
            "I blocked Trash confirmation for safety.\n\n"
            "I did not touch Gmail."
        )

    candidates = trash_plan.get("candidates", [])

    lines = [
        "I can prepare this Trash move, but I am not allowed to run it yet.",
        "",
        f"Safe Trash candidates: {plan.candidate_count}",
        "",
        "These would move to Gmail Trash for your manual review, not permanent delete.",
        "",
    ]

    for item in candidates[:10]:
        lines.append(
            f"- ID {item.get('queue_id')}: {item.get('subject')} | risk {item.get('risk')} | {item.get('category')}"
        )

    lines.extend([
        "",
        "This is still confirmation planning only.",
        "I did not move anything to Trash.",
        "I did not permanently delete anything.",
        "I did not touch Gmail.",
        "",
        "Next phase will build the Trash safety gate dry-run before any Gmail action is allowed.",
    ])

    return "\n".join(lines)


def main() -> None:
    print(build_trash_confirmation_message())


if __name__ == "__main__":
    main()
