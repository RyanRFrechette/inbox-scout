from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

from inbox_scout.sort_planner import build_sort_plan


@dataclass
class SortWorkflowPlan:
    status: str
    original_message: str
    requested_limit: int | None
    sort_all: bool
    target: str
    workflow_mode: str
    steps: list[str]
    gmail_scan_enabled: bool
    gmail_changes_enabled: bool
    permanent_delete_enabled: bool
    safety_note: str


def build_sort_workflow_plan(message: str) -> SortWorkflowPlan:
    plan = build_sort_plan(message)

    if plan.status != "planned":
        return SortWorkflowPlan(
            status=plan.status,
            original_message=message,
            requested_limit=plan.limit,
            sort_all=plan.sort_all,
            target=plan.target,
            workflow_mode="blocked",
            steps=[plan.next_action],
            gmail_scan_enabled=False,
            gmail_changes_enabled=False,
            permanent_delete_enabled=False,
            safety_note=plan.safety_note,
        )

    safe_limit = plan.limit

    if plan.sort_all:
        workflow_mode = "sort_all_dry_run_only"
        steps = [
            "Block full inbox cleanup for now.",
            "Require future extra confirmation before any large scan.",
            "Recommend a 5-email test batch instead.",
        ]
        gmail_scan_enabled = False
    else:
        workflow_mode = "small_batch_dry_run_plan"
        steps = [
            f"Prepare a future unread inbox scan for up to {safe_limit} emails.",
            "Generate a local report only.",
            "Generate a local review queue only.",
            "Do not archive, trash, mark read, reply, or delete.",
        ]
        gmail_scan_enabled = False

    return SortWorkflowPlan(
        status="workflow_planned",
        original_message=message,
        requested_limit=safe_limit,
        sort_all=plan.sort_all,
        target=plan.target,
        workflow_mode=workflow_mode,
        steps=steps,
        gmail_scan_enabled=gmail_scan_enabled,
        gmail_changes_enabled=False,
        permanent_delete_enabled=False,
        safety_note="Workflow plan only. No Gmail scan or Gmail changes made.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inbox Scout sort workflow dry-run planner")
    parser.add_argument("message", nargs="+", help='Example: "sort 5 emails"')
    args = parser.parse_args()

    workflow = build_sort_workflow_plan(" ".join(args.message))
    print(json.dumps(asdict(workflow), indent=2))


if __name__ == "__main__":
    main()
