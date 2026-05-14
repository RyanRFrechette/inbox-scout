from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from inbox_scout.sort_command_parser import parse_sort_command


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_SCAN_QUEUE_PLAN = PLANS_DIR / "latest_scan_queue_plan.json"


@dataclass
class ScanQueuePlan:
    plan_id: str
    created_at: str
    original_message: str
    parsed_intent: str
    requested_limit: int | None
    sort_all: bool
    is_continuation: bool
    cleanup_mode: bool
    target: str
    workflow_mode: str
    report_command: str | None
    queue_command: str | None
    commands_are_suggestions_only: bool
    gmail_scan_enabled_now: bool
    gmail_changes_enabled: bool
    permanent_delete_enabled: bool
    safety_notes: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_plan_id() -> str:
    return datetime.now(timezone.utc).strftime("scanqueue_%Y%m%d_%H%M%S")


def build_scan_queue_plan(message: str, continuation: bool = False, cleanup_mode: bool = False) -> ScanQueuePlan:
    parsed = parse_sort_command(message)

    safety_notes = [
        "This module only prepares commands.",
        "It does not run Gmail scan automatically.",
        "It does not modify Gmail.",
        "Permanent delete is disabled.",
    ]

    report_command = None
    queue_command = None
    effective_limit = parsed.limit

    if parsed.intent == "permanent_delete_plan_only":
        workflow_mode = "blocked_phase_14_only"
        safety_notes.append("Permanent delete language detected. Phase 14 only. Blocked for now.")

    elif parsed.intent != "sort":
        workflow_mode = "unknown"
        safety_notes.append("Could not build a scan plan from this message.")

    elif parsed.sort_all or cleanup_mode:
        workflow_mode = "commands_planned"
        if cleanup_mode and parsed.limit is not None and "test" in message.lower():
            effective_limit = parsed.limit
        else:
            effective_limit = 5
        page_size = min(5, effective_limit)
        report_command = (
            f'.\\.venv\\Scripts\\python.exe -m inbox_scout.report_mode '
            f'--limit {effective_limit} --page-size {page_size} --unread-only --export both'
        )
        queue_command = (
            '.\\.venv\\Scripts\\python.exe -m inbox_scout.review_queue --from-latest-report'
        )
        if cleanup_mode:
            safety_notes.append("Cleanup mode: builds trash plan after scan. No Gmail changes during scan.")
        else:
            safety_notes.append("Sort-all runs in safe batches of 5. Say 'continue sorting' after each batch.")
        safety_notes.append("Review queue command is local-only and makes no Gmail changes.")

    else:
        workflow_mode = "commands_planned"
        effective_limit = parsed.limit or 5
        page_size = min(5, effective_limit)

        report_command = (
            f'.\\.venv\\Scripts\\python.exe -m inbox_scout.report_mode '
            f'--limit {effective_limit} --page-size {page_size} --unread-only --export both'
        )
        queue_command = (
            '.\\.venv\\Scripts\\python.exe -m inbox_scout.review_queue --from-latest-report'
        )

        safety_notes.append(f"Prepared read-only scan command for {effective_limit} unread Inbox emails.")
        safety_notes.append("Review queue command is local-only and makes no Gmail changes.")

    return ScanQueuePlan(
        plan_id=make_plan_id(),
        created_at=now_iso(),
        original_message=message,
        parsed_intent=parsed.intent,
        requested_limit=effective_limit,
        sort_all=parsed.sort_all or cleanup_mode,
        is_continuation=continuation,
        cleanup_mode=cleanup_mode,
        target=parsed.target,
        workflow_mode=workflow_mode,
        report_command=report_command,
        queue_command=queue_command,
        commands_are_suggestions_only=True,
        gmail_scan_enabled_now=False,
        gmail_changes_enabled=False,
        permanent_delete_enabled=False,
        safety_notes=safety_notes,
    )


def save_plan(plan: ScanQueuePlan) -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_SCAN_QUEUE_PLAN.write_text(json.dumps(asdict(plan), indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inbox Scout scan/queue command planner")
    parser.add_argument("message", nargs="+")
    args = parser.parse_args()

    plan = build_scan_queue_plan(" ".join(args.message))
    save_plan(plan)

    print(json.dumps(asdict(plan), indent=2))
    print()
    print(f"Saved latest scan/queue plan: {LATEST_SCAN_QUEUE_PLAN}")
    print("Gmail changes: 0")


if __name__ == "__main__":
    main()
