from __future__ import annotations

from typing import Any

from inbox_scout.report_mode import classify_for_report, fetch_report_emails, save_scan_cursor
from inbox_scout.review_queue import build_queue_items, save_queue
from inbox_scout.inbox_cleanup_plan import build_inbox_cleanup_plan_message


MAX_CLEANUP_BATCHES = 1000  # safety cap: 1000 * 5 = 5000 emails max
BATCH_SIZE = 5


def run_full_cleanup_scan() -> str:
    all_results: list[dict[str, Any]] = []
    seen_message_ids: set[str] = set()
    page_token: str | None = None
    batch_count = 0
    stopped_by_cap = False
    scan_error: str | None = None

    while True:
        if batch_count >= MAX_CLEANUP_BATCHES:
            stopped_by_cap = True
            break

        try:
            emails, next_page_token = fetch_report_emails(
                limit=BATCH_SIZE,
                unread_only=True,
                page_size=BATCH_SIZE,
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
        page_token = next_page_token

        if not page_token:
            break

    if batch_count == 0:
        error_detail = f" Error: {scan_error}" if scan_error else ""
        return f"Scan failed. No batches completed.{error_detail}\n\nGmail not touched."

    # Save cursor: None if fully scanned, or the cutoff token if stopped by cap
    save_scan_cursor(page_token if stopped_by_cap else None, True, BATCH_SIZE)

    if not all_results:
        return "Scan complete. No unread emails found in inbox.\n\nGmail not touched."

    # Build one merged queue from all accumulated results
    queue_items = build_queue_items(all_results)
    save_queue(queue_items, "cleanup_full_scan")

    # Build cleanup plan from the merged queue
    cleanup_msg = build_inbox_cleanup_plan_message()

    cap_note = ""
    if stopped_by_cap:
        cap_note = (
            f"\n\nNote: Stopped at {MAX_CLEANUP_BATCHES}-batch safety cap "
            f"({MAX_CLEANUP_BATCHES * BATCH_SIZE} emails max). "
            "Some unread emails may not have been included."
        )

    error_note = ""
    if scan_error and batch_count > 0:
        error_note = (
            f"\n\nNote: Scan stopped early after {batch_count} batch(es). "
            f"Error: {scan_error}"
        )

    header = (
        f"Scanned {len(all_results)} unread emails across {batch_count} batch(es).\n"
        "Read-only. No Gmail changes."
        + cap_note
        + error_note
    )

    return header + "\n\n" + cleanup_msg
