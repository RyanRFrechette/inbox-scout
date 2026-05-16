from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from inbox_scout.sort_scan_queue_plan import build_scan_queue_plan, save_plan
from inbox_scout.inbox_cleanup_plan import build_inbox_cleanup_plan
from inbox_scout.inbox_cleanup_runner import build_inbox_cleanup_runner_message


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_SCAN_QUEUE_RUN = PLANS_DIR / "latest_scan_queue_run.json"

AUTOPILOT_MAX_LIMIT = 25
AUTOPILOT_DEFAULT_LIMIT = 25


def _parse_limit(text: str) -> int:
    m = re.search(r"\b(\d+)\b", text.lower())
    if m:
        return min(max(int(m.group(1)), 1), AUTOPILOT_MAX_LIMIT)
    return AUTOPILOT_DEFAULT_LIMIT


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _run_scan() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "inbox_scout.sort_scan_queue_runner", "--run"],
        cwd=str(PROJECT_ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=900,
    )


def run_autopilot_cleanup(text: str) -> str:
    limit = _parse_limit(text)

    # Build a plain scan plan using the capped limit.
    # We use "sort N emails" as the canonical plan text so the plan builder
    # takes the non-cleanup_mode branch, which respects the limit correctly.
    plan = build_scan_queue_plan(f"sort {limit} emails")
    if plan.workflow_mode != "commands_planned":
        return "Could not build a safe scan plan. Gmail not touched."
    plan.requested_limit = min(plan.requested_limit or limit, AUTOPILOT_MAX_LIMIT)
    save_plan(plan)

    # Step 1: read-only Gmail scan + local queue build
    try:
        result = _run_scan()
    except subprocess.TimeoutExpired:
        return "Scan timed out after 15 minutes. Gmail not touched."

    run_data = _load_json(LATEST_SCAN_QUEUE_RUN)
    if result.returncode != 0 or run_data.get("status") != "complete":
        return "Scan did not complete cleanly. Gmail not touched."

    # Step 2: build local cleanup plan from queue
    cleanup_plan = build_inbox_cleanup_plan()

    scanned = cleanup_plan.total_scanned
    protected = cleanup_plan.protected_count
    needs_review = cleanup_plan.needs_review_count
    candidates = cleanup_plan.trash_candidate_count

    if scanned == 0:
        return "No emails scanned. Gmail not touched."

    header = (
        f"Scanned {scanned} — {protected} protected, "
        f"{needs_review} unclear, {candidates} safe to trash."
    )

    if candidates == 0:
        return (
            f"{header}\n\n"
            "No obvious junk found. Nothing moved.\n"
            "Protected and unclear emails were left alone.\n"
            "Gmail not touched."
        )

    # Step 3: move safe trash candidates + mark-read after each successful trash
    runner_msg = build_inbox_cleanup_runner_message()
    return f"{header}\n\n{runner_msg}"
