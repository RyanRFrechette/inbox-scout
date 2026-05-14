from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_SCAN_QUEUE_PLAN = PLANS_DIR / "latest_scan_queue_plan.json"
LATEST_SCAN_QUEUE_RUN = PLANS_DIR / "latest_scan_queue_run.json"
LATEST_GMAIL_SCAN_CURSOR = PLANS_DIR / "latest_gmail_scan_cursor.json"

PLAN_MAX_AGE_MINUTES = 30


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def plan_age_minutes(plan: dict[str, Any]) -> float | None:
    created_at = parse_dt(str(plan.get("created_at", "")))
    if not created_at:
        return None

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    return (datetime.now(timezone.utc) - created_at).total_seconds() / 60


def validate_latest_plan(plan: dict[str, Any]) -> tuple[bool, str]:
    if not plan:
        return False, "I do not see a saved scan plan yet. Say something like: sort 5 emails."

    age = plan_age_minutes(plan)
    if age is None:
        return False, "The saved scan plan has an invalid timestamp. Please ask me to sort 5 emails again."

    if age > PLAN_MAX_AGE_MINUTES:
        return False, "That scan plan expired. Please ask me to sort 5 emails again."

    if plan.get("workflow_mode") != "commands_planned":
        return False, "The saved plan is not safe to run. Please start with: sort 5 emails."

    if plan.get("target") != "unread_inbox":
        return False, "The saved plan target is not supported yet."

    limit = plan.get("requested_limit")
    if not isinstance(limit, int) or limit < 1 or limit > 5:
        return False, "The scan plan has an unsafe batch size. Please say 'sort 5 emails' to start."

    return True, "Plan is safe for read-only scan."


def run_scan_queue_runner() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    return subprocess.run(
        [sys.executable, "-m", "inbox_scout.sort_scan_queue_runner", "--run"],
        cwd=str(PROJECT_ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=300,
    )


def find_count(label: str, text: str) -> str:
    for line in text.splitlines():
        if label.lower() in line.lower():
            nums = re.findall(r"\d+", line)
            if nums:
                return nums[-1]
    return "unknown"


def build_scan_approval_response(_: str = "") -> str:
    plan = load_json(LATEST_SCAN_QUEUE_PLAN)
    ok, reason = validate_latest_plan(plan)

    if not ok:
        return (
            f"Cannot run scan: {reason}\n\n"
            "Gmail not touched."
        )

    # If this is a continuation and the last batch already exhausted Gmail pages, stop early.
    if plan.get("is_continuation"):
        cursor = load_json(LATEST_GMAIL_SCAN_CURSOR)
        if cursor and "next_page_token" in cursor and not cursor["next_page_token"]:
            return (
                "Inbox looks fully sorted.\n\n"
                "No more unread pages after the last batch.\n\n"
                "Say sort all to start fresh. Gmail not touched."
            )

    result = run_scan_queue_runner()

    run_data = load_json(LATEST_SCAN_QUEUE_RUN)

    if result.returncode != 0 or run_data.get("status") != "complete":
        return (
            "Scan did not complete cleanly. I stopped safely.\n\n"
            "No Gmail changes were made."
        )

    queue_output = str(run_data.get("queue_output_tail", ""))

    total = find_count("Total queued emails", queue_output)
    protected = find_count("Protected/manual review", queue_output)
    pending = find_count("Pending low-risk review", queue_output)

    is_cleanup = plan.get("cleanup_mode") is True
    is_sort_all = plan.get("sort_all") is True
    limit = plan.get("requested_limit") or 5

    base = (
        f"Done. Scanned {limit} unread emails.\n\n"
        f"Total: {total} | Protected: {protected} | Pending: {pending}\n\n"
        "Read-only. No Gmail changes."
    )

    if is_cleanup:
        from inbox_scout.inbox_cleanup_plan import build_inbox_cleanup_plan_message
        cleanup_msg = build_inbox_cleanup_plan_message()
        return base + "\n\n" + cleanup_msg

    if is_sort_all:
        cursor = load_json(LATEST_GMAIL_SCAN_CURSOR)
        if cursor.get("next_page_token"):
            continuation = (
                "\n\nSay continue sorting for the next 5.\n"
                "Say queue to see this batch. Say next to review an item."
            )
        else:
            continuation = (
                "\n\nNo more pages. Inbox looks fully sorted.\n"
                "Say queue to see this batch."
            )
    else:
        continuation = "\n\nSay queue to see this batch. Say next to review an item."

    return base + continuation


def main() -> None:
    print(build_scan_approval_response())


if __name__ == "__main__":
    main()
