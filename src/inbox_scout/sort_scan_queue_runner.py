from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_SCAN_QUEUE_PLAN = PLANS_DIR / "latest_scan_queue_plan.json"
LATEST_SCAN_QUEUE_RUN = PLANS_DIR / "latest_scan_queue_run.json"
LATEST_GMAIL_SCAN_CURSOR = PLANS_DIR / "latest_gmail_scan_cursor.json"

MAX_SAFE_RUN_LIMIT = 25


@dataclass
class ScanQueueRunResult:
    run_id: str
    created_at: str
    source_plan_id: str | None
    status: str
    requested_limit: int | None
    ran_report: bool
    ran_queue: bool
    gmail_scan_ran: bool
    gmail_changes_enabled: bool
    permanent_delete_enabled: bool
    report_return_code: int | None
    queue_return_code: int | None
    safety_notes: list[str]
    report_output_tail: str
    queue_output_tail: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("scanrun_%Y%m%d_%H%M%S")


def load_latest_plan() -> dict[str, Any]:
    if not LATEST_SCAN_QUEUE_PLAN.exists():
        return {}

    return json.loads(LATEST_SCAN_QUEUE_PLAN.read_text(encoding="utf-8-sig"))


def load_cursor() -> dict[str, Any]:
    if not LATEST_GMAIL_SCAN_CURSOR.exists():
        return {}

    return json.loads(LATEST_GMAIL_SCAN_CURSOR.read_text(encoding="utf-8-sig"))


def tail_text(text: str, max_chars: int = 4000) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def validate_plan(plan: dict[str, Any]) -> tuple[bool, list[str]]:
    notes: list[str] = []

    if not plan:
        notes.append("No latest scan/queue plan found.")
        return False, notes

    if plan.get("workflow_mode") != "commands_planned":
        notes.append(f"Blocked: workflow_mode is {plan.get('workflow_mode')}.")
        return False, notes

    if plan.get("target") not in ("unread_inbox", "inbox"):
        notes.append(f"Blocked: unsupported target {plan.get('target')}.")
        return False, notes

    limit = plan.get("requested_limit")

    if not isinstance(limit, int):
        notes.append("Blocked: requested_limit is not a safe integer.")
        return False, notes

    if limit < 1:
        notes.append("Blocked: requested_limit must be at least 1.")
        return False, notes

    if limit > MAX_SAFE_RUN_LIMIT:
        notes.append(f"Blocked: requested_limit {limit} is above current safe run limit {MAX_SAFE_RUN_LIMIT}.")
        return False, notes

    notes.append("Plan is safe for a read-only scan + local queue run.")
    notes.append("This runner will not archive, trash, mark read, reply, or delete.")
    return True, notes


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    return subprocess.run(
        args,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        timeout=900,
        encoding="utf-8",
        errors="replace",
    )


def save_result(result: ScanQueueRunResult) -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_SCAN_QUEUE_RUN.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")


def build_result(
    *,
    plan: dict[str, Any],
    status: str,
    ran_report: bool,
    ran_queue: bool,
    gmail_scan_ran: bool,
    report_return_code: int | None,
    queue_return_code: int | None,
    safety_notes: list[str],
    report_output: str = "",
    queue_output: str = "",
) -> ScanQueueRunResult:
    return ScanQueueRunResult(
        run_id=make_run_id(),
        created_at=now_iso(),
        source_plan_id=plan.get("plan_id"),
        status=status,
        requested_limit=plan.get("requested_limit"),
        ran_report=ran_report,
        ran_queue=ran_queue,
        gmail_scan_ran=gmail_scan_ran,
        gmail_changes_enabled=False,
        permanent_delete_enabled=False,
        report_return_code=report_return_code,
        queue_return_code=queue_return_code,
        safety_notes=safety_notes,
        report_output_tail=tail_text(report_output),
        queue_output_tail=tail_text(queue_output),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inbox Scout safe scan + queue runner")
    parser.add_argument("--run", action="store_true", help="Run read-only Gmail scan and local queue creation.")
    parser.add_argument("--account", type=str, default="primary", help="Gmail account to scan (primary or secondary).")
    args = parser.parse_args()

    plan = load_latest_plan()
    safe, notes = validate_plan(plan)

    if not safe:
        result = build_result(
            plan=plan,
            status="blocked",
            ran_report=False,
            ran_queue=False,
            gmail_scan_ran=False,
            report_return_code=None,
            queue_return_code=None,
            safety_notes=notes,
        )
        save_result(result)
        print(json.dumps(asdict(result), indent=2))
        print("Gmail changes: 0")
        return

    limit = plan["requested_limit"]
    page_size = min(5, limit)
    is_continuation = plan.get("is_continuation", False)

    report_args = [
        sys.executable,
        "-m",
        "inbox_scout.report_mode",
        "--limit",
        str(limit),
        "--page-size",
        str(page_size),
        "--export",
        "both",
    ]

    # Scan all INBOX (read + unread) when sort_all=True or target="inbox".
    # Standard limited sorts still use --unread-only.
    is_full_inbox_scan = plan.get("sort_all") or plan.get("target") == "inbox"
    if not is_full_inbox_scan:
        report_args.append("--unread-only")

    if args.account != "primary":
        report_args.extend(["--account", args.account])

    if is_continuation:
        cursor = load_cursor()
        saved_token = cursor.get("next_page_token")
        if saved_token:
            report_args.extend(["--page-token", saved_token])
            notes.append("Continuation: using saved Gmail cursor to advance to next batch.")
        else:
            notes.append("Continuation requested but no cursor token found. Starting from first page.")

    queue_args = [
        sys.executable,
        "-m",
        "inbox_scout.review_queue",
        "--from-latest-report",
    ]

    if not args.run:
        preview_notes = notes + [
            "Preview only. The scan was not run.",
            "Run again with --run only when ready.",
        ]
        result = build_result(
            plan=plan,
            status="preview_only",
            ran_report=False,
            ran_queue=False,
            gmail_scan_ran=False,
            report_return_code=None,
            queue_return_code=None,
            safety_notes=preview_notes,
            report_output=" ".join(report_args),
            queue_output=" ".join(queue_args),
        )
        save_result(result)
        print(json.dumps(asdict(result), indent=2))
        print("Gmail changes: 0")
        return

    report = run_command(report_args)

    if report.returncode != 0:
        result = build_result(
            plan=plan,
            status="report_failed",
            ran_report=True,
            ran_queue=False,
            gmail_scan_ran=True,
            report_return_code=report.returncode,
            queue_return_code=None,
            safety_notes=notes + ["Report mode failed. Queue was not created."],
            report_output=report.stdout + "\n" + report.stderr,
        )
        save_result(result)
        print(json.dumps(asdict(result), indent=2))
        print("Gmail changes: 0")
        return

    queue = run_command(queue_args)

    status = "complete" if queue.returncode == 0 else "queue_failed"

    result = build_result(
        plan=plan,
        status=status,
        ran_report=True,
        ran_queue=queue.returncode == 0,
        gmail_scan_ran=True,
        report_return_code=report.returncode,
        queue_return_code=queue.returncode,
        safety_notes=notes + ["Read-only scan/queue run complete. Gmail modifications were not enabled."],
        report_output=report.stdout + "\n" + report.stderr,
        queue_output=queue.stdout + "\n" + queue.stderr,
    )
    save_result(result)

    print(json.dumps(asdict(result), indent=2))
    print("Gmail changes: 0")


if __name__ == "__main__":
    main()
