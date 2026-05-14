from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inbox_scout.telegram_approval import (
    evaluate_archive,
    evaluate_trash,
    evaluate_markread,
    find_item,
    get_queue_id,
    get_risk,
    clean,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "telegram_config.json"
LOG_DIR = PROJECT_ROOT / "data" / "logs"
GATE_LOG = LOG_DIR / "telegram_apply_gate_dryrun.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}

    return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))


def save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_apply_disabled() -> None:
    config = load_config()

    changed = False

    if "telegram_apply_enabled" not in config:
        config["telegram_apply_enabled"] = False
        changed = True

    if "permanent_delete_enabled" not in config:
        config["permanent_delete_enabled"] = False
        changed = True

    if "telegram_apply_requires_dryrun_pass" not in config:
        config["telegram_apply_requires_dryrun_pass"] = True
        changed = True

    if changed:
        save_config(config)


def parse_apply_command(command: str) -> tuple[str | None, str | None]:
    text = command.strip().lower()
    text = text.replace("/apply", "apply")

    match = re.match(r"^apply\s+(archive|trash|markread|mark-read|mark\s+read)\s+(\d+)$", text)

    if not match:
        return None, None

    action = match.group(1).replace("-", "").replace(" ", "")
    queue_id = match.group(2)

    if action == "markread":
        action = "markread"

    return action, queue_id


def log_gate_attempt(row: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with GATE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def evaluate_apply_gate(command: str) -> str:
    ensure_apply_disabled()
    config = load_config()

    action, queue_id = parse_apply_command(command)

    if not action or not queue_id:
        return (
            "Telegram Apply Gate\n\n"
            "Command not recognized.\n\n"
            "Use one of these formats:\n"
            "- apply archive 2\n"
            "- apply trash 2\n"
            "- apply markread 2\n\n"
            "Apply mode is currently DISABLED.\n"
            "No Gmail changes were made."
        )

    item = find_item(queue_id)

    if not item:
        return (
            f"Telegram Apply Gate\n\n"
            f"Queue item ID {queue_id} not found.\n\n"
            "Apply mode is currently DISABLED.\n"
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

    apply_enabled = bool(config.get("telegram_apply_enabled", False))

    if not allowed:
        status = "BLOCKED"
        final_reason = reason
    elif not apply_enabled:
        status = "READY BUT APPLY DISABLED"
        final_reason = "Dry-run passed, but Telegram Gmail apply mode is disabled in config."
    else:
        status = "WOULD APPLY IN FUTURE"
        final_reason = "Apply mode is enabled, but this skeleton still does not execute Gmail changes yet."

    row = {
        "timestamp": now_iso(),
        "command": command,
        "action": action,
        "queue_id": queue_id,
        "status": status,
        "reason": final_reason,
        "gmail_changed": False,
        "telegram_apply_enabled": apply_enabled,
        "subject": clean(item.get("subject")),
    }
    log_gate_attempt(row)

    return (
        "Telegram Apply Gate Dry-Run\n\n"
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

    parser = argparse.ArgumentParser(description="Inbox Scout Telegram apply gate dry-run skeleton")
    parser.add_argument("command", nargs="+", help="Example: apply archive 2")
    args = parser.parse_args()

    print(evaluate_apply_gate(" ".join(args.command)))


if __name__ == "__main__":
    main()
