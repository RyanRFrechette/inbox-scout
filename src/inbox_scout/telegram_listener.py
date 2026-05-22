from __future__ import annotations

import argparse
import json
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from inbox_scout.telegram_notifier import load_config, load_token, send_message
from inbox_scout.telegram_status import build_status_message
from inbox_scout.telegram_approval import evaluate_approval_command
from inbox_scout.telegram_apply_gate import evaluate_apply_gate
from inbox_scout.telegram_confirm_gate import evaluate_confirm_gate
from inbox_scout.natural_intent import handle_natural_message


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = PROJECT_ROOT / "config" / "telegram_listener_state.json"
LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"
LOG_PATH = PROJECT_ROOT / "data" / "logs" / "telegram_watch.log"

_RESORT_RUN_PHRASES = [
    "resort my sorted emails",
    "resort my emails",
    "resort sorted emails",
    "resort everything",
    "audit my archives",
    "check if anything is in the wrong folder",
    "are my emails sorted correctly",
    "audit sorted folders",
    "check my sorted folders",
]

_RESORT_PREVIEW_PHRASES = [
    "resort preview",
    "show resort preview",
    "preview resort",
]


def _log_error(msg: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {msg}\n")


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"offset": 0}
    return json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_updates(offset: int | None = None) -> list[dict[str, Any]]:
    token = load_token()
    url = f"https://api.telegram.org/bot{token}/getUpdates"

    params = {"timeout": 5}
    if offset:
        params["offset"] = offset

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    return data.get("result", [])


def load_queue_items() -> list[dict[str, Any]]:
    if not LATEST_QUEUE.exists():
        return []

    data = json.loads(LATEST_QUEUE.read_text(encoding="utf-8-sig"))

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("queue_items", [])

    return []


def build_help() -> str:
    return (
        "Atlas (Inbox Scout) commands:\n\n"
        "READ-ONLY\n"
        "help / ping / status / audit / progress report\n"
        "queue / show emails\n"
        "next / what needs my attention\n"
        "inbox count / how many emails\n"
        "show folders / folder counts\n\n"
        "SORT (scan + classify — Gmail unchanged)\n"
        "sort 5 emails / sort N emails\n"
        "sort all / sort my whole inbox\n"
        "continue sorting / sort more / next batch\n"
        "sort plan / review plan\n\n"
        "CLEANUP (scan → trash plan → confirm)\n"
        "clean my inbox / clean N emails\n"
        "get me closer to inbox zero / get me to inbox zero\n"
        "cleanup status / cancel cleanup\n"
        "move trash  ← moves approved candidates to Gmail Trash\n\n"
        "RESORT (re-check already sorted emails)\n"
        "resort preview / preview resort  ← mismatches only, no changes\n"
        "resort my sorted emails / audit my archives  ← scan + plan\n"
        "resort all mail / resort everything  ← exhaustive scan\n"
        "apply resort fixes  ← applies Gmail label corrections\n\n"
        "TRASH / ARCHIVE (gate: plan → confirm → execute)\n"
        "trash candidates / what can go to trash\n"
        "confirm trash plan / apply trash\n"
        "archive candidates / archive plan / confirm archive\n\n"
        "MARK READ (gate)\n"
        "mark reviewed as read / confirm mark read\n\n"
        "BLOCK SENDERS (gate)\n"
        "block senders in trash / BLOCK N TRASH SENDERS\n\n"
        "MODEL / AI PROVIDER\n"
        "/model status / /model local / /model openrouter / /model auto\n\n"
        "CONFIRM / CANCEL\n"
        "yes / approve / go ahead  ←  confirm pending plan\n"
        "cancel / stop / never mind  ←  cancel\n\n"
        "Safety: protected and manual-review emails are always skipped.\n"
        "No permanent delete. No Gmail changes without your approval."
    )


def build_queue_summary() -> str:
    items = load_queue_items()

    if not items:
        return "No latest queue found."

    lines = ["Latest Inbox Scout queue:\n"]

    for item in items:
        qid = clean(item.get("queue_id") or item.get("id") or "?")
        decision = clean(item.get("local_decision"))
        risk = clean(item.get("risk_score") or item.get("risk"))
        category = clean(item.get("category"))
        action = clean(item.get("gmail_action_type"))
        read = clean(item.get("gmail_marked_read"))
        subject = clean(item.get("subject"))[:55]

        line = f"ID {qid}: {decision} | risk {risk} | {category}"
        if action:
            line += f" | {action}"
        if read:
            line += f" | read={read}"
        line += f"\n- {subject}"

        lines.append(line)

    lines.append("\nNo Gmail changes were made.")
    return "\n\n".join(lines)


def build_next_item() -> str:
    items = load_queue_items()

    for item in items:
        decision = clean(item.get("local_decision")).lower()
        action_taken = item.get("gmail_action_taken") is True
        marked_read = item.get("gmail_marked_read") is True

        if decision == "pending_review" and not action_taken and not marked_read:
            qid = clean(item.get("queue_id") or item.get("id") or "?")
            return (
                "Next pending review item:\n\n"
                f"ID: {qid}\n"
                f"Decision: {clean(item.get('local_decision'))}\n"
                f"Category: {clean(item.get('category'))}\n"
                f"Risk: {clean(item.get('risk_score') or item.get('risk'))}\n"
                f"From: {clean(item.get('from'))}\n"
                f"Subject: {clean(item.get('subject'))}\n\n"
                "Read-only mode. No Gmail changes were made."
            )

    return "No pending local review items found. No Gmail changes were made."


def handle_command(text: str) -> str:
    command = text.strip().lower()

    if command in {"help", "/help", "commands"}:
        return build_help()

    if command in {"ping", "/ping"}:
        return "pong ✅\nInbox Scout listener is running in read-only mode.\nNo Gmail changes were made."

    if command in {"status", "/status", "audit", "/audit"}:
        return build_status_message()

    if command in {"queue", "/queue"}:
        return build_queue_summary()

    if command in {"next", "/next"}:
        return build_next_item()

    if command.startswith("approve ") or command.startswith("/approve "):
        return evaluate_approval_command(text)

    if command.startswith("apply ") or command.startswith("/apply "):
        return evaluate_apply_gate(text)

    if command.startswith("confirm ") or command.startswith("/confirm ") or command in {"cancel", "/cancel"}:
        return evaluate_confirm_gate(text)

    if command.startswith(("/model ", "model ")):
        from inbox_scout.model_router import model_status_message, set_provider
        parts = command.split(None, 1)
        sub = parts[1].strip().lower() if len(parts) > 1 else ""
        if sub == "status":
            return model_status_message()
        if sub in ("local", "openrouter", "auto"):
            set_provider(sub)
            return f"Model provider set to: {sub}."
        return "Usage: /model status | /model local | /model openrouter | /model auto"

    return handle_natural_message(text)


def run_once() -> None:
    config = load_config()
    allowed_chat_id = str(config["telegram_chat_id"])

    state = load_state()
    offset = int(state.get("offset") or 0)

    updates = get_updates(offset=offset if offset > 0 else None)

    if not updates:
        print("No new Telegram updates.")
        return

    newest_update_id = offset

    for update in updates:
        update_id = int(update.get("update_id", 0))
        newest_update_id = max(newest_update_id, update_id + 1)

        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))

        text = clean(message.get("text"))

        if chat_id != allowed_chat_id:
            print(f"Skipped unauthorized chat: {chat_id}")
            continue

        if not text:
            print("Skipped non-text message.")
            continue

        print(f"Command received: {text}")
        _msg_lower = text.lower()
        is_resort_run = any(phrase in _msg_lower for phrase in _RESORT_RUN_PHRASES)
        is_resort_preview = any(phrase in _msg_lower for phrase in _RESORT_PREVIEW_PHRASES)
        if is_resort_run or is_resort_preview:
            if is_resort_run:
                ack = "Got it — scanning your sorted folders and applying safe label corrections. Labels only, no trash or delete."
            else:
                ack = "Got it — scanning your sorted folders (preview only). This is read-only and will not change Gmail."
            try:
                send_message(ack)
            except Exception:
                pass

            def _resort_thread(cmd_text=text):
                try:
                    reply = handle_command(cmd_text)
                except Exception as exc:
                    _log_error(
                        f"resort thread error for {cmd_text!r}:\n{traceback.format_exc()}"
                    )
                    reply = (
                        f"Resort stopped. {type(exc).__name__}: {exc}\n\n"
                        "Gmail not touched."
                    )
                try:
                    send_message(reply)
                except Exception as se:
                    _log_error(f"resort send failed: {type(se).__name__}: {se}")

            threading.Thread(target=_resort_thread, daemon=True).start()
        else:
            try:
                reply = handle_command(text)
            except Exception as exc:
                _log_error(
                    f"handle_command exception for {text!r}:\n{traceback.format_exc()}"
                )
                reply = (
                    f"Scan stopped. Error: {type(exc).__name__}: {exc}\n\n"
                    "Gmail not touched."
                )
            try:
                send_message(reply)
            except Exception as send_exc:
                _log_error(
                    f"send_message failed: {type(send_exc).__name__}: {send_exc}\n"
                    f"Reply was: {reply[:300]}"
                )
            print("Reply sent.")

    state["offset"] = newest_update_id
    save_state(state)
    print(f"Saved listener offset: {newest_update_id}")


def init_offset() -> None:
    updates = get_updates()
    newest = 0

    for update in updates:
        update_id = int(update.get("update_id", 0))
        newest = max(newest, update_id + 1)

    save_state({"offset": newest})
    print(f"Initialized Telegram listener offset to: {newest}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inbox Scout read-only Telegram command listener")
    parser.add_argument("--once", action="store_true", help="Check Telegram once, reply to new commands, then exit")
    parser.add_argument("--init-offset", action="store_true", help="Ignore old messages and start after latest Telegram update")
    args = parser.parse_args()

    if args.init_offset:
        init_offset()
        return

    if args.once:
        run_once()
        return

    print("Use --once for read-only one-shot mode or --init-offset to ignore old messages.")


if __name__ == "__main__":
    main()
