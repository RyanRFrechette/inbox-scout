from __future__ import annotations

import traceback
from typing import Any
import json
from datetime import datetime, timezone
from pathlib import Path

from inbox_scout.report_mode import classify_for_report, fetch_report_emails, save_scan_cursor
from inbox_scout.review_queue import build_queue_items, save_queue
from inbox_scout.inbox_cleanup_plan import build_inbox_cleanup_plan_message


MAX_CLEANUP_BATCHES = 1000  # safety cap: 1000 * 5 = 5000 emails max
BATCH_SIZE = 5
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_SCAN_QUEUE_PLAN = PLANS_DIR / "latest_scan_queue_plan.json"
PROGRESS_FILE = PLANS_DIR / "latest_cleanup_progress.json"
LOG_FILE = PROJECT_ROOT / "data" / "logs" / "telegram_watch.log"


def _log_error(message: str) -> None:
    log_dir = LOG_FILE.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {message}\n")


def load_scan_cap() -> int:
    max_cap = MAX_CLEANUP_BATCHES * BATCH_SIZE
    if not LATEST_SCAN_QUEUE_PLAN.exists():
        return max_cap
    plan = json.loads(LATEST_SCAN_QUEUE_PLAN.read_text(encoding="utf-8-sig"))
    msg = str(plan.get("original_message", "")).lower()
    limit = plan.get("requested_limit")
    if "test" in msg and isinstance(limit, int) and limit > 0:
        return min(limit, max_cap)
    return max_cap


def save_progress(status: str, scanned: int, batch_count: int, cap_emails: int, batch_size: int = BATCH_SIZE) -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    percent = int( (scanned / cap_emails) * 100 ) if cap_emails else 0
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "scanned": scanned,
        "batch_count": batch_count,
        "batch_size": batch_size,
        "cap_emails": cap_emails,
        "progress_vs_cap_percent": min(percent, 100),
        "gmail_changes_enabled": False,
        "permanent_delete_enabled": False,
    }
    PROGRESS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_full_cleanup_scan() -> str:
    all_results: list[dict[str, Any]] = []
    seen_message_ids: set[str] = set()
    page_token: str | None = None
    batch_count = 0
    stopped_by_cap = False
    scan_error: str | None = None
    cap_emails = load_scan_cap()
    save_progress("running", 0, 0, cap_emails)

    try:
        while len(all_results) < cap_emails:
            if batch_count >= MAX_CLEANUP_BATCHES:
                stopped_by_cap = True
                break

            try:
                emails, next_page_token = fetch_report_emails(
                    limit=min(BATCH_SIZE, cap_emails - len(all_results)),
                    unread_only=True,
                    page_size=min(BATCH_SIZE, cap_emails - len(all_results)),
                    initial_page_token=page_token,
                )
            except Exception as e:
                scan_error = str(e)
                break

            if not emails:
                break

            try:
                classified = classify_for_report(emails)
            except Exception as e:
                scan_error = str(e)
                break

            for item in classified:
                mid = str(item.get("message_id", ""))
                if mid and mid not in seen_message_ids:
                    seen_message_ids.add(mid)
                    all_results.append(item)

            batch_count += 1
            save_progress("running", len(all_results), batch_count, cap_emails)
            page_token = next_page_token

            if not page_token:
                break

        if len(all_results) >= cap_emails and page_token:
            stopped_by_cap = True

        if batch_count == 0:
            error_detail = f" Error: {scan_error}" if scan_error else ""
            save_progress("failed", 0, 0, cap_emails)
            return f"Scan failed. No batches completed.{error_detail}\n\nGmail not touched."

        # Save cursor: None if fully scanned, or the cutoff token if stopped by cap
        save_scan_cursor(page_token if stopped_by_cap else None, True, BATCH_SIZE)

        if not all_results:
            save_progress("complete", 0, batch_count, cap_emails)
            return "Scan complete. No unread emails found in inbox.\n\nGmail not touched."

        # Build one merged queue from all accumulated results
        queue_items = build_queue_items(all_results)
        save_queue(queue_items, "cleanup_full_scan")

        # Build cleanup plan from the merged queue
        cleanup_msg = build_inbox_cleanup_plan_message()

        cap_note = ""
        if stopped_by_cap:
            cap_note = (
                f"\n\nNote: Stopped at {cap_emails}-email safety cap. "
                "Some unread emails may not have been included."
            )

        error_note = ""
        if scan_error and batch_count > 0:
            error_note = (
                f"\n\nNote: Scan stopped early after {batch_count} batch(es). "
                f"Error: {scan_error}"
            )

        final_status = "stopped_by_cap" if stopped_by_cap else ("stopped_after_error" if scan_error else "complete")
        save_progress(final_status, len(all_results), batch_count, cap_emails)

        header = (
            f"Scanned {len(all_results)} unread emails across {batch_count} batch(es).\n"
            "Read-only. No Gmail changes."
            + cap_note
            + error_note
        )

        return header + "\n\n" + cleanup_msg

    except Exception as exc:
        _log_error(
            f"run_full_cleanup_scan unhandled exception after {batch_count} batch(es), "
            f"{len(all_results)} scanned:\n{traceback.format_exc()}"
        )
        save_progress("failed", len(all_results), batch_count, cap_emails)
        return (
            f"Scan stopped after {batch_count} batch(es) ({len(all_results)} scanned).\n"
            f"Error: {type(exc).__name__}: {exc}\n\n"
            "Gmail not touched."
        )
