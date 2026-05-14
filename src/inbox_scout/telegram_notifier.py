from __future__ import annotations

import json
import os
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "telegram_config.json"
TOKEN_PATH = Path.home() / ".atlas-telegram-token"


def load_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token.strip()
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(f"Telegram token file not found: {TOKEN_PATH}")
    return TOKEN_PATH.read_text(encoding="utf-8").strip()


def load_config() -> dict:
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if chat_id:
        return {"telegram_chat_id": chat_id}
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Telegram config file not found: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))


def send_message(text: str) -> dict:
    token = load_token()
    config = load_config()
    chat_id = config["telegram_chat_id"]

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def main() -> None:
    config = load_config()

    message = (
        "Inbox Scout notifier test\n\n"
        f"Project: {config.get('project')}\n"
        f"Bot: {config.get('bot_name')}\n"
        f"Batch limit: {config.get('batch_limit')}\n"
        f"Approval required: {config.get('gmail_actions_require_approval')}\n\n"
        "No Gmail changes were made."
    )

    result = send_message(message)
    print("Telegram send OK:", result.get("ok"))


if __name__ == "__main__":
    main()
