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
            f"I cannot safely run that yet.\n\n"
            f"Reason: {reason}\n\n"
            "I did not scan Gmail. I did not touch Gmail."
        )

    result = run_scan_queue_runner()

    run_data = load_json(LATEST_SCAN_QUEUE_RUN)

    if result.returncode != 0 or run_data.get("status") != "complete":
        return (
            "I tried to run the safe read-only scan, but it did not complete cleanly.\n\n"
            "I stopped safely.\n"
            "I did not archive, trash, mark read, reply, or delete anything."
        )

    queue_output = str(run_data.get("queue_output_tail", ""))

    total = find_count("Total queued emails", queue_output)
    protected = find_count("Protected/manual review", queue_output)
    pending = find_count("Pending low-risk review", queue_output)

    is_sort_all = plan.get("sort_all") is True
    limit = plan.get("requested_limit") or 5

    continuation = (
        "\n\nThere may be more unread emails in your inbox. "
        "Say 'continue sorting' to process the next safe batch of 5."
        if is_sort_all
        else ""
    )

    return (
        f"Done. I safely scanned {limit} unread inbox emails and built a new review queue.\n\n"
        f"Result:\n"
        f"- Total queued emails: {total}\n"
        f"- Protected/manual review: {protected}\n"
        f"- Pending low-risk review: {pending}\n\n"
        "I only read Gmail and created a local queue.\n"
        "I did not archive anything.\n"
        "I did not move anything to Trash.\n"
        "I did not mark anything read.\n"
        "I did not reply or delete anything."
        f"{continuation}"
    )


def main() -> None:
    print(build_scan_approval_response())


if __name__ == "__main__":
    main()
