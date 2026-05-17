from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOT_ENV_PATH = PROJECT_ROOT / ".env"


def load_env() -> bool:
    """Load .env into os.environ if present. Returns True if loaded. Never reveals values."""
    if not DOT_ENV_PATH.exists():
        return False
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=DOT_ENV_PATH, override=False)
        return True
    except ImportError:
        return False


def openrouter_key_present() -> bool:
    """Return True if OPENROUTER_API_KEY is set and non-empty. Never reveals value."""
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def env_status() -> str:
    """Return a safe status string showing key presence only. Never reveals value."""
    if openrouter_key_present():
        return "OPENROUTER_API_KEY: set"
    return "OPENROUTER_API_KEY: not set"


def telegram_token_valid() -> bool:
    """Return True if TELEGRAM_BOT_TOKEN is set, non-empty, and contains ':'. Never reveals value."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    return bool(token) and ":" in token


def telegram_chat_id_valid() -> bool:
    """Return True if TELEGRAM_CHAT_ID is set and non-empty. Never reveals value."""
    return bool(os.environ.get("TELEGRAM_CHAT_ID", "").strip())


def validate_telegram_env() -> list[str]:
    """Return list of config issues. Empty list means config is valid. Never reveals values."""
    issues: list[str] = []
    if not telegram_token_valid():
        issues.append("TELEGRAM_BOT_TOKEN missing or invalid (must be non-empty and contain ':')")
    if not telegram_chat_id_valid():
        issues.append("TELEGRAM_CHAT_ID missing or blank")
    return issues
