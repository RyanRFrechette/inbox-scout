from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inbox_scout.trash_execution_runner import (
    PROTECTED_CATEGORIES,
    TRASH_EXECUTION_LOG,
    TRASH_SAFE_CATEGORIES,
    MAX_TRASH_RISK,
    append_jsonl,
    find_protected_text_terms,
    get_category,
    get_message_id,
    get_modify_service,
    get_queue_id,
    get_risk,
    get_subject,
    is_true,
    load_queue_document,
    norm,
    save_queue_document,
)
from inbox_scout.trash_candidate_plan import (
    MARKETING_RESCUE_CATEGORIES,
    has_obvious_marketing_signal,
    has_protected_danger_signal,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_INBOX_CLEANUP_PLAN = PLANS_DIR / "latest_inbox_cleanup_plan.json"

CLEANUP_PLAN_MAX_AGE_MINUTES = 120


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("cleanup_run_%Y%m%d_%H%M%S")


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def queue_item_by_id(items: list[dict[str, Any]], queue_id: str) -> dict[str, Any] | None:
    for item in items:
        if get_queue_id(item) == queue_id:
            return item
    return None


def load_and_validate_cleanup_plan() -> tuple[list[dict], list[str]]:
    plan = load_json(LATEST_INBOX_CLEANUP_PLAN)

    if not plan:
        return [], ["No cleanup plan found. Say clean my inbox first."]

    try:
        created_at = datetime.fromisoformat(str(plan.get("created_at", "")))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_minutes = (datetime.now(timezone.utc) - created_at).total_seconds() / 60
        if age_minutes > CLEANUP_PLAN_MAX_AGE_MINUTES:
            return [], [
                f"Cleanup plan expired ({age_minutes:.0f} min old). "
                "Say clean my inbox to rebuild it."
            ]
    except Exception:
        return [], ["Cleanup plan has an invalid timestamp."]

    if plan.get("gmail_changes_enabled") is True:
        return [], ["Cleanup plan unexpectedly has Gmail changes enabled. Blocked."]

    if plan.get("permanent_delete_enabled") is True:
        return [], ["Cleanup plan has permanent delete enabled. Blocked."]

    candidates = plan.get("trash_candidates", [])
    if not candidates:
        return [], ["No trash candidates in cleanup plan. Gmail not touched."]

    return candidates, []


def validate_candidate(candidate: dict, items: list[dict[str, Any]]) -> tuple[bool, str]:
    queue_id = str(candidate.get("queue_id", ""))
    item = queue_item_by_id(items, queue_id)

    if not item:
        return False, f"Queue item {queue_id} not found in latest queue."

    if not get_message_id(item):
        return False, f"Queue item {queue_id} is missing Gmail message_id."

    if is_true(item.get("manual_review")) or is_true(item.get("manual_review_required")):
        return False, f"Queue item {queue_id} requires manual review."

    if clean(item.get("local_decision")).lower() == "protected_review":
        return False, f"Queue item {queue_id} is protected_review."

    category = norm(get_category(item))
    if category in PROTECTED_CATEGORIES:
        return False, f"Queue item {queue_id} has protected category: {get_category(item)}."

    if category in TRASH_SAFE_CATEGORIES:
        pass
    elif category in MARKETING_RESCUE_CATEGORIES:
        if has_protected_danger_signal(item):
            return False, f"Queue item {queue_id} has protected danger signal."
        if not has_obvious_marketing_signal(item):
            return False, f"Queue item {queue_id} has no obvious marketing signal."
    else:
        return False, f"Queue item {queue_id} category is not Trash-safe: {get_category(item)}."

    if get_risk(item) > MAX_TRASH_RISK:
        return False, f"Queue item {queue_id} risk is too high: {get_risk(item)}."

    if clean(item.get("gmail_action_type")):
        return False, f"Queue item {queue_id} already has a Gmail action."

    if is_true(item.get("gmail_action_taken")):
        return False, f"Queue item {queue_id} already has Gmail action taken."

    if is_true(item.get("gmail_trashed")):
        return False, f"Queue item {queue_id} is already trashed."

    matched = find_protected_text_terms(item)
    if matched:
        terms = ", ".join(matched[:3])
        return False, f"Queue item {queue_id} has protected text in sender/subject/snippet: {terms}."

    return True, ""


def attempt_mark_read_after_action(service: Any, message_id: str, item: dict[str, Any]) -> bool:
    """Mark email as read after a successful approved Gmail action. Non-critical: swallows errors."""
    try:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
        item["gmail_marked_read"] = True
        item["gmail_marked_read_at"] = now_iso()
        item["gmail_read_action_type"] = "marked_read_after_trash"
        item["gmail_read_action_taken"] = True
        return True
    except Exception:
        return False


def build_inbox_cleanup_runner_message() -> str:
    candidates, plan_errors = load_and_validate_cleanup_plan()

    if plan_errors:
        return plan_errors[0] + "\n\nGmail not touched."

    original_queue, items = load_queue_document()

    valid_pairs: list[tuple[dict, dict]] = []
    skipped: list[tuple[str, str]] = []  # (queue_id, reason)

    for candidate in candidates:
        queue_id = str(candidate.get("queue_id", ""))
        item = queue_item_by_id(items, queue_id)
        ok, reason = validate_candidate(candidate, items)
        if ok and item:
            valid_pairs.append((candidate, item))
        else:
            skipped.append((queue_id, reason))

    if not valid_pairs:
        lines = ["No candidates passed safety validation.\n"]
        lines.extend(f"- {r}" for _, r in skipped)
        lines.append("\nGmail not touched.")
        return "\n".join(lines)

    run_id = make_run_id()

    for skip_id, skip_reason in skipped:
        append_jsonl(TRASH_EXECUTION_LOG, {
            "event": "cleanup_trash_skipped",
            "run_id": run_id,
            "timestamp": now_iso(),
            "queue_id": skip_id,
            "reason": skip_reason,
            "gmail_changed": False,
        })

    append_jsonl(TRASH_EXECUTION_LOG, {
        "event": "cleanup_trash_apply_start",
        "run_id": run_id,
        "timestamp": now_iso(),
        "requested_count": len(valid_pairs),
        "gmail_changes_enabled": True,
        "trash_execution_enabled": True,
        "permanent_delete_enabled": False,
    })

    try:
        service = get_modify_service()
    except RuntimeError as e:
        return f"Could not connect to Gmail modify service.\n\n{e}\n\nGmail not touched."

    trashed: list[str] = []
    errors: list[str] = []

    for candidate, item in valid_pairs:
        queue_id = get_queue_id(item)
        message_id = get_message_id(item)

        try:
            service.users().messages().trash(userId="me", id=message_id).execute()

            trash_time = now_iso()
            item["gmail_trashed"] = True
            item["gmail_action_taken"] = True
            item["gmail_action_type"] = "trashed"
            item["gmail_trashed_at"] = trash_time
            item["gmail_trash_review_folder"] = True

            trashed.append(queue_id)
            mark_read_ok = attempt_mark_read_after_action(service, message_id, item)
            append_jsonl(TRASH_EXECUTION_LOG, {
                "event": "cleanup_mark_read",
                "run_id": run_id,
                "timestamp": now_iso(),
                "queue_id": queue_id,
                "message_id": message_id,
                "gmail_changed": mark_read_ok,
                "success": mark_read_ok,
            })

            append_jsonl(TRASH_EXECUTION_LOG, {
                "event": "cleanup_trash_moved",
                "run_id": run_id,
                "timestamp": trash_time,
                "queue_id": queue_id,
                "message_id": message_id,
                "subject": get_subject(item),
                "category": get_category(item),
                "risk": get_risk(item),
                "gmail_changed": True,
                "permanent_delete": False,
            })

        except Exception as e:
            error = f"ID {queue_id}: Trash failed — {e}"
            errors.append(error)
            append_jsonl(TRASH_EXECUTION_LOG, {
                "event": "cleanup_trash_error",
                "run_id": run_id,
                "timestamp": now_iso(),
                "queue_id": queue_id,
                "error": str(e),
                "gmail_changed": False,
            })

    if trashed:
        save_queue_document(original_queue, items)

    if not trashed and errors:
        lines = ["Cleanup move failed.\n"]
        lines.extend(f"- {e}" for e in errors)
        lines.append("\nGmail not touched.")
        return "\n".join(lines)

    lines = [f"Done. Moved {len(trashed)} email(s) to Gmail Trash for review.", ""]
    for queue_id in trashed:
        queued_item = queue_item_by_id(items, queue_id) or {}
        lines.append(f"- ID {queue_id}: {get_subject(queued_item)}")

    if errors:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {e}" for e in errors)

    if skipped:
        lines.extend(["", "Skipped (failed safety check):"])
        lines.extend(f"- ID {sid}: {sreason}" for sid, sreason in skipped)

    lines.extend([
        "",
        "In Gmail Trash — not permanently deleted.",
        "You can review and restore from Trash.",
        f"\nGmail changes: {len(trashed)}",
    ])

    return "\n".join(lines)


def main() -> None:
    print(build_inbox_cleanup_runner_message())


if __name__ == "__main__":
    main()
