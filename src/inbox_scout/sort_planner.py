from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inbox_scout.sort_command_parser import parse_sort_command


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_PLAN = PLANS_DIR / "latest_sort_plan.json"


@dataclass
class SortPlan:
    plan_id: str
    created_at: str
    original_message: str
    intent: str
    limit: int | None
    sort_all: bool
    target: str
    dry_run: bool
    workflow_mode: str
    gmail_scan_enabled_now: bool
    gmail_changes_enabled: bool
    permanent_delete_enabled: bool
    trash_review_mode: bool
    allow_trash_plan: bool
    recommended_next_step: str
    safety_notes: list[str]
    suggested_commands: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_plan_id() -> str:
    return datetime.now(timezone.utc).strftime("sortplan_%Y%m%d_%H%M%S")


def build_sort_plan(message: str) -> SortPlan:
    parsed = parse_sort_command(message)

    safety_notes = [
        "Dry-run/planning only.",
        "No Gmail changes will be made.",
        "Permanent delete is disabled.",
        "Telegram-triggered Gmail execution is still disabled.",
    ]

    suggested_commands: list[str] = []

    if parsed.intent == "permanent_delete_plan_only":
        workflow_mode = "blocked_phase_14_only"
        recommended_next_step = "Permanent-delete language detected. This belongs to Phase 14 and remains disabled."
        safety_notes.append("Do not build or run permanent delete yet.")

    elif parsed.intent != "sort":
        workflow_mode = "unknown"
        recommended_next_step = "Ask user for a clearer inbox sorting command."

    elif parsed.sort_all:
        workflow_mode = "sort_all_dry_run_only"
        recommended_next_step = "Sort-all must remain dry-run only until the full safety system is complete."
        suggested_commands.append("future: python -m inbox_scout.report_mode --unread-only --export both")
        safety_notes.append("Do not run full all-unread cleanup yet.")

    else:
        workflow_mode = "small_batch_dry_run_plan"
        recommended_next_step = "Next phase can connect this to a safe report/queue dry-run."
        suggested_commands.append(
            f"future: python -m inbox_scout.report_mode --limit {parsed.limit} --page-size 5 --unread-only --export both"
        )
        suggested_commands.append("future: python -m inbox_scout.review_queue --from-latest-report")

    return SortPlan(
        plan_id=make_plan_id(),
        created_at=now_iso(),
        original_message=message,
        intent=parsed.intent,
        limit=parsed.limit,
        sort_all=parsed.sort_all,
        target=parsed.target,
        dry_run=True,
        workflow_mode=workflow_mode,
        gmail_scan_enabled_now=False,
        gmail_changes_enabled=False,
        permanent_delete_enabled=False,
        trash_review_mode=parsed.trash_review_mode,
        allow_trash_plan=parsed.allow_trash_plan,
        recommended_next_step=recommended_next_step,
        safety_notes=safety_notes,
        suggested_commands=suggested_commands,
    )


def save_plan(plan: SortPlan) -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_PLAN.write_text(json.dumps(asdict(plan), indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inbox Scout sort planner dry-run")
    parser.add_argument("message", nargs="+", help='Example: "sort 25 emails"')
    args = parser.parse_args()

    plan = build_sort_plan(" ".join(args.message))
    save_plan(plan)

    print(json.dumps(asdict(plan), indent=2))
    print()
    print(f"Saved latest plan: {LATEST_PLAN}")
    print("Gmail changes: 0")


if __name__ == "__main__":
    main()
