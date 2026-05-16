from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from inbox_scout.sort_scan_queue_plan import build_scan_queue_plan, save_plan
from inbox_scout.inbox_cleanup_plan import build_inbox_cleanup_plan
from inbox_scout.inbox_cleanup_runner import build_inbox_cleanup_runner_message


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_SCAN_QUEUE_RUN = PLANS_DIR / "latest_scan_queue_run.json"

AUTOPILOT_MAX_LIMIT = 25
AUTOPILOT_DEFAULT_LIMIT = 25

# Full inbox-zero autopilot constants
AUTOPILOT_SORT_ALL_MAX = 250
QUEUE_PATH = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"

CATEGORY_TO_LABEL: dict[str, str] = {
    "receipt": "InboxScout/Receipts",
    "receipts": "InboxScout/Receipts",
    "security": "InboxScout/Security",
    "security alert": "InboxScout/Security",
    "password": "InboxScout/Security",
    "password reset": "InboxScout/Security",
    "finance": "InboxScout/Finance",
    "financial": "InboxScout/Finance",
    "tax": "InboxScout/Finance",
    "invoice": "InboxScout/Finance",
    "payment": "InboxScout/Finance",
    "bill": "InboxScout/Finance",
    "bills": "InboxScout/Finance",
    "insurance": "InboxScout/Finance",
    "account": "InboxScout/Accounts",
    "accounts": "InboxScout/Accounts",
    "account access": "InboxScout/Accounts",
    "job": "InboxScout/Jobs",
    "jobs": "InboxScout/Jobs",
    "career": "InboxScout/Jobs",
    "shopping": "InboxScout/Shopping-History",
    "shopping history": "InboxScout/Shopping-History",
    "order": "InboxScout/Shopping-History",
    "shipment": "InboxScout/Shopping-History",
    "shipping": "InboxScout/Shopping-History",
}

SAFE_ARCHIVE_AFTER_LABEL: frozenset[str] = frozenset({
    "newsletter", "promotion", "promotions", "social", "ignore",
    "notifications", "notification", "marketing", "advertising",
})


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
    m = re.search(r"\b(\d+)\b", text.lower())
    raw_limit = int(m.group(1)) if m else AUTOPILOT_DEFAULT_LIMIT
    limit = min(max(raw_limit, 1), AUTOPILOT_MAX_LIMIT)
    capped = raw_limit > AUTOPILOT_MAX_LIMIT

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

    cap_note = f"(Scan capped at {AUTOPILOT_MAX_LIMIT} — you requested {raw_limit}.)\n" if capped else ""
    header = (
        f"{cap_note}Scanned {scanned} — {protected} protected, "
        f"{needs_review} unclear, {candidates} trash candidates."
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


# ---------------------------------------------------------------------------
# Inbox-zero autopilot helpers
# ---------------------------------------------------------------------------

def _norm_cat(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace("_", " ").replace("-", " ")


def _get_msg_id_for_item(item: dict) -> str | None:
    for key in ("gmail_message_id", "message_id", "gmail_id", "email_id"):
        if item.get(key):
            return str(item[key])
    return None


def _item_is_protected_for_autopilot(item: dict) -> bool:
    decision = _norm_cat(item.get("local_decision"))
    if "protected" in decision:
        return True
    if item.get("manual_review") or item.get("manual_review_required"):
        return True
    return False


def _item_risk(item: dict) -> int:
    try:
        return int(item.get("risk_score") or item.get("risk") or 999)
    except Exception:
        return 999


def _item_already_handled(item: dict) -> bool:
    if item.get("gmail_trashed"):
        return True
    return _norm_cat(item.get("gmail_action_type")) in {"trashed", "archived"}


def _pick_inboxscout_label(item: dict) -> str:
    cat = _norm_cat(item.get("category") or item.get("final_category") or "")
    if cat in CATEGORY_TO_LABEL:
        return CATEGORY_TO_LABEL[cat]
    for part in cat.split("/"):
        part = part.strip()
        if part in CATEGORY_TO_LABEL:
            return CATEGORY_TO_LABEL[part]
    return "InboxScout/Review"


def _get_or_create_label(service: Any, label_name: str, cache: dict) -> str | None:
    if label_name in cache:
        return cache[label_name]
    try:
        results = service.users().labels().list(userId="me").execute()
        existing = {lbl["name"]: lbl["id"] for lbl in results.get("labels", [])}
        if label_name in existing:
            cache[label_name] = existing[label_name]
            return existing[label_name]
        created = service.users().labels().create(
            userId="me",
            body={
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        ).execute()
        lid = created["id"]
        cache[label_name] = lid
        return lid
    except Exception:
        return None


def _load_items_from_queue() -> list[dict]:
    if not QUEUE_PATH.exists():
        return []
    try:
        data = json.loads(QUEUE_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("queue_items", "items", "queue"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _process_non_trash_items(service: Any, items: list[dict], label_cache: dict) -> dict:
    labeled = archived = marked_read = protected_count = errors = 0

    for item in items:
        if _item_already_handled(item):
            continue

        msg_id = _get_msg_id_for_item(item)
        if not msg_id:
            errors += 1
            continue

        cat = _norm_cat(item.get("category") or item.get("final_category") or "")
        protected = _item_is_protected_for_autopilot(item)
        risk = _item_risk(item)

        label_name = _pick_inboxscout_label(item)
        label_id = _get_or_create_label(service, label_name, label_cache)

        add_labels: list[str] = []
        remove_labels: list[str] = ["UNREAD"]

        if label_id:
            add_labels.append(label_id)

        should_archive = not protected and risk <= 30 and cat in SAFE_ARCHIVE_AFTER_LABEL
        if should_archive:
            remove_labels.append("INBOX")

        if protected:
            protected_count += 1

        try:
            body: dict = {}
            if add_labels:
                body["addLabelIds"] = add_labels
            if remove_labels:
                body["removeLabelIds"] = remove_labels
            if body:
                service.users().messages().modify(
                    userId="me",
                    id=msg_id,
                    body=body,
                ).execute()
            if add_labels:
                labeled += 1
            if should_archive:
                archived += 1
            marked_read += 1
        except Exception:
            errors += 1

    return {
        "labeled": labeled,
        "archived": archived,
        "marked_read": marked_read,
        "protected": protected_count,
        "errors": errors,
    }


def _get_modify_service_for_autopilot() -> Any:
    from inbox_scout.gmail_auth import get_gmail_service
    try:
        return get_gmail_service(mode="modify")
    except TypeError:
        return get_gmail_service("modify")


def run_inbox_zero_autopilot(text: str) -> str:
    """Batch scan → trash safe + label + mark-read loop, capped at AUTOPILOT_SORT_ALL_MAX."""
    cap = AUTOPILOT_SORT_ALL_MAX

    total_scanned = total_trashed = total_labeled = total_archived = 0
    total_marked_read = total_protected = total_errors = 0

    try:
        service = _get_modify_service_for_autopilot()
    except Exception as e:
        return f"Could not connect to Gmail.\n\n{e}\n\nGmail not touched."

    label_cache: dict = {}
    cursor_path = PLANS_DIR / "latest_gmail_scan_cursor.json"

    # Always start from page 1 for a fresh "sort all".
    if cursor_path.exists():
        cursor_path.unlink()

    is_first_batch = True

    while total_scanned < cap:
        remaining = cap - total_scanned
        batch_limit = min(AUTOPILOT_MAX_LIMIT, remaining)

        plan = build_scan_queue_plan(
            f"sort {batch_limit} emails",
            continuation=not is_first_batch,
        )
        if plan.workflow_mode != "commands_planned":
            break
        plan.requested_limit = min(plan.requested_limit or batch_limit, AUTOPILOT_MAX_LIMIT)
        save_plan(plan)

        try:
            scan_result = _run_scan()
        except subprocess.TimeoutExpired:
            total_errors += 1
            break

        run_data = _load_json(LATEST_SCAN_QUEUE_RUN)
        if scan_result.returncode != 0 or run_data.get("status") != "complete":
            total_errors += 1
            break

        items = _load_items_from_queue()
        if not items:
            break

        batch_count = len(items)
        total_scanned += batch_count
        is_first_batch = False

        # Trash safe candidates, then reload queue to see updated state.
        cleanup_plan = build_inbox_cleanup_plan()
        if cleanup_plan.trash_candidate_count > 0:
            build_inbox_cleanup_runner_message()
            items = _load_items_from_queue()
            total_trashed += cleanup_plan.trash_candidate_count
            total_marked_read += cleanup_plan.trash_candidate_count

        # Label + mark-read non-trash items.
        result_data = _process_non_trash_items(service, items, label_cache)
        total_labeled += result_data["labeled"]
        total_archived += result_data["archived"]
        total_marked_read += result_data["marked_read"]
        total_protected += result_data["protected"]
        total_errors += result_data["errors"]

        # Stop if Gmail has no next page (inbox fully processed).
        cursor = _load_json(cursor_path)
        if not cursor.get("next_page_token"):
            break

    cap_reached = total_scanned >= cap
    lines = [
        "Inbox Zero complete.",
        "",
        f"Scanned: {total_scanned}",
        f"Moved to Trash: {total_trashed}",
        f"Labeled (InboxScout): {total_labeled}",
        f"Archived: {total_archived}",
        f"Marked read: {total_marked_read}",
        f"Left in inbox (labeled, protected): {total_protected}",
    ]
    if total_errors:
        lines.append(f"Errors: {total_errors}")
    if cap_reached:
        lines.extend(["", f"Safety cap: {cap} emails. Run again to continue."])
    lines.extend(["", "Nothing permanently deleted. All recoverable from Trash or Gmail."])
    return "\n".join(lines)
