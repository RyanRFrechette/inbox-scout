from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inbox_scout.archive_execution_gate import build_archive_execution_gate_message
from inbox_scout.inbox_cleanup_runner import attempt_mark_read_after_action
from inbox_scout.telegram_approval import (
    clean,
    evaluate_archive,
    evaluate_markread,
    evaluate_trash,
    find_item,
    get_message_id,
    get_queue_id,
    get_risk,
)
from inbox_scout.trash_execution_gate import build_trash_execution_gate_message
from inbox_scout.trash_execution_runner import get_modify_service


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "telegram_config.json"
LOG_DIR = PROJECT_ROOT / "data" / "logs"
CONFIRM_LOG = LOG_DIR / "telegram_confirm_gate_dryrun.jsonl"
LATEST_QUEUE_PATH = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}

    return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))


def save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_confirm_disabled() -> None:
    config = load_config()
    changed = False

    defaults = {
        "telegram_apply_enabled": False,
        "telegram_confirm_enabled": False,
        "telegram_two_step_required": True,
        "permanent_delete_enabled": False,
        "telegram_apply_requires_dryrun_pass": True,
    }

    for key, value in defaults.items():
        if key not in config:
            config[key] = value
            changed = True

    if changed:
        save_config(config)


def parse_confirm_command(command: str) -> tuple[str | None, str | None]:
    text = command.strip().lower()
    text = text.replace("/confirm", "confirm")

    match = re.match(r"^confirm\s+(archive|trash|markread|mark-read|mark\s+read)\s+(\d+)$", text)

    if not match:
        return None, None

    action = match.group(1).replace("-", "").replace(" ", "")
    queue_id = match.group(2)

    return action, queue_id


def log_confirm_attempt(row: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIRM_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _reset_execution_flags() -> None:
    config = load_config()
    config["telegram_confirm_enabled"] = False
    config["telegram_apply_enabled"] = False
    save_config(config)


def _load_full_queue() -> tuple[Any, list]:
    data = json.loads(LATEST_QUEUE_PATH.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        return data, data
    return data, data.get("queue_items", [])


def _save_full_queue(original: Any) -> None:
    LATEST_QUEUE_PATH.write_text(
        json.dumps(original, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _execute_confirmed_action(action: str, queue_id: str, item: dict) -> str:
    message_id = get_message_id(item)
    if not message_id:
        log_confirm_attempt({
            "timestamp": now_iso(), "command": f"confirm {action} {queue_id}",
            "action": action, "queue_id": queue_id, "message_id": None,
            "status": "BLOCKED_NO_MESSAGE_ID", "gmail_changed": False,
            "mark_read_success": False, "error": "Missing Gmail message ID",
        })
        return f"Blocked: missing Gmail message ID for ID {queue_id}.\n\nGmail not touched."

    try:
        service = get_modify_service()
    except Exception as e:
        log_confirm_attempt({
            "timestamp": now_iso(), "command": f"confirm {action} {queue_id}",
            "action": action, "queue_id": queue_id, "message_id": message_id,
            "status": "SERVICE_ERROR", "gmail_changed": False,
            "mark_read_success": False, "error": str(e),
        })
        return f"Could not connect to Gmail: {e}\n\nGmail not touched."

    original, items = _load_full_queue()
    live_item = next((i for i in items if get_queue_id(i) == queue_id), None)
    if not live_item:
        log_confirm_attempt({
            "timestamp": now_iso(), "command": f"confirm {action} {queue_id}",
            "action": action, "queue_id": queue_id, "message_id": message_id,
            "status": "ITEM_MISSING_AT_EXECUTION", "gmail_changed": False,
            "mark_read_success": False, "error": "Item not found in queue at execution time",
        })
        return f"Queue item {queue_id} not found at execution time. Gmail not touched."

    action_taken = False
    error_msg = None
    action_time = now_iso()

    try:
        if action == "archive":
            service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}
            ).execute()
            live_item["gmail_archived"] = True
            live_item["gmail_action_taken"] = True
            live_item["gmail_action_type"] = "archived"
            live_item["gmail_archived_at"] = action_time
        elif action == "trash":
            service.users().messages().trash(userId="me", id=message_id).execute()
            live_item["gmail_trashed"] = True
            live_item["gmail_action_taken"] = True
            live_item["gmail_action_type"] = "trashed"
            live_item["gmail_trashed_at"] = action_time
        action_taken = True
    except Exception as e:
        error_msg = str(e)

    mark_read_ok = False
    if action_taken:
        mark_read_ok = attempt_mark_read_after_action(service, message_id, live_item)
        _save_full_queue(original)

    log_confirm_attempt({
        "timestamp": now_iso(),
        "command": f"confirm {action} {queue_id}",
        "action": action,
        "queue_id": queue_id,
        "message_id": message_id,
        "status": "EXECUTED" if action_taken else "EXECUTION_FAILED",
        "gmail_changed": action_taken,
        "mark_read_success": mark_read_ok,
        "error": error_msg,
    })

    if not action_taken:
        return (
            f"Gmail {action} failed for ID {queue_id}.\n\n"
            f"Error: {error_msg}\n\n"
            "Gmail not touched."
        )

    subject = clean(live_item.get("subject", "(no subject)"))[:55]
    return (
        f"Done. {action.capitalize()} executed for ID {queue_id}.\n\n"
        f"Subject: {subject}\n"
        f"Mark-read: {'yes' if mark_read_ok else 'no'}\n\n"
        "Flags reset. Gmail updated."
    )


def evaluate_confirm_gate(command: str) -> str:
    clean_command = command.strip().lower()

    if clean_command in {"confirm trash", "run trash dry run", "trash dry run", "test trash gate"}:
        return build_trash_execution_gate_message(clean_command)

    if clean_command in {"confirm archive", "run archive", "execute archive"}:
        return build_archive_execution_gate_message(clean_command)

    ensure_confirm_disabled()
    config = load_config()

    text = command.strip().lower()

    if text in {"cancel", "/cancel"}:
        row = {
            "timestamp": now_iso(),
            "command": command,
            "status": "CANCELLED_DRYRUN",
            "gmail_changed": False,
        }
        log_confirm_attempt(row)

        return "Cancelled. Gmail not touched."

    action, queue_id = parse_confirm_command(command)

    if not action or not queue_id:
        return (
            "Telegram Confirm Gate\n\n"
            "Command not recognized.\n\n"
            "Use one of these formats:\n"
            "- confirm archive 2\n"
            "- confirm trash 2\n"
            "- confirm markread 2\n"
            "- cancel\n\n"
            "Confirmation execution is currently DISABLED.\n"
            "No Gmail changes were made."
        )

    item = find_item(queue_id)

    if not item:
        return (
            f"Telegram Confirm Gate\n\n"
            f"Queue item ID {queue_id} not found.\n\n"
            "No Gmail changes were made."
        )

    if action == "archive":
        allowed, reason = evaluate_archive(item)
    elif action == "trash":
        allowed, reason = evaluate_trash(item)
    elif action == "markread":
        allowed, reason = evaluate_markread(item)
    else:
        allowed, reason = False, "Blocked: unknown action."

    confirm_enabled = bool(config.get("telegram_confirm_enabled", False))
    apply_enabled = bool(config.get("telegram_apply_enabled", False))

    if not allowed:
        status = "BLOCKED"
        final_reason = reason
    elif not confirm_enabled:
        status = "READY BUT CONFIRM DISABLED"
        final_reason = "Dry-run passed, but Telegram confirmation execution is disabled in config."
    elif not apply_enabled:
        status = "READY BUT APPLY DISABLED"
        final_reason = "Confirm is enabled, but Telegram Gmail apply mode is disabled in config."
    else:
        try:
            return _execute_confirmed_action(action, queue_id, item)
        finally:
            _reset_execution_flags()

    row = {
        "timestamp": now_iso(),
        "command": command,
        "action": action,
        "queue_id": queue_id,
        "status": status,
        "reason": final_reason,
        "gmail_changed": False,
        "telegram_confirm_enabled": confirm_enabled,
        "telegram_apply_enabled": apply_enabled,
        "subject": clean(item.get("subject")),
    }
    log_confirm_attempt(row)

    return (
        "Telegram Confirm Gate Dry-Run\n\n"
        f"Command: {command}\n"
        f"Status: {status}\n"
        f"Reason: {final_reason}\n\n"
        "Item:\n"
        f"- ID: {get_queue_id(item)}\n"
        f"- Decision: {clean(item.get('local_decision'))}\n"
        f"- Category: {clean(item.get('category'))}\n"
        f"- Risk: {get_risk(item)}\n"
        f"- Gmail action: {clean(item.get('gmail_action_type')) or 'none'}\n"
        f"- Marked read: {clean(item.get('gmail_marked_read')) or 'False'}\n"
        f"- Subject: {clean(item.get('subject'))[:80]}\n\n"
        "No Gmail changes were made."
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Inbox Scout Telegram confirm gate dry-run")
    parser.add_argument("command", nargs="+", help="Example: confirm archive 2")
    args = parser.parse_args()

    print(evaluate_confirm_gate(" ".join(args.command)))


if __name__ == "__main__":
    main()
