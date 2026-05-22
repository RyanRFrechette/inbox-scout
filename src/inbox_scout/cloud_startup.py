"""Cloud startup helpers: decode Gmail OAuth tokens from environment variables.

On cloud deployments (DigitalOcean/VPS/any Linux host), Gmail token files are not on disk.
This module decodes base64-encoded token JSON from env vars and writes them to
the expected paths — only if the target file does not already exist.

Env vars consumed:
    GMAIL_TOKEN_JSON         base64-encoded contents of token.json (readonly scope)
    GMAIL_TOKEN_MODIFY_JSON  base64-encoded contents of token_modify.json (modify scope)

Safe by design:
    - Never overwrites existing token files (local dev is always preserved)
    - Never logs or prints token content
    - Returns a plain-text status string (presence only, never values)
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_token_paths() -> dict[str, Path]:
    root = _project_root()
    return {
        "GMAIL_TOKEN_JSON": root / "token.json",
        "GMAIL_TOKEN_MODIFY_JSON": root / "token_modify.json",
    }


def decode_token_env_vars(token_paths: dict[str, Path] | None = None) -> list[str]:
    """Decode Gmail token env vars to disk if not already present.

    Args:
        token_paths: Override target paths (for testing). Keys must be env var names.

    Returns:
        List of status messages (safe to print/log — never contains token values).
    """
    if token_paths is None:
        token_paths = _default_token_paths()

    messages: list[str] = []

    for env_var, target_path in token_paths.items():
        raw = os.environ.get(env_var, "").strip()
        if not raw:
            messages.append(f"{env_var}: not set — skipping")
            continue

        if target_path.exists():
            messages.append(f"{env_var}: target file already exists — skipping (local dev)")
            continue

        try:
            decoded = base64.b64decode(raw)
        except Exception as exc:
            messages.append(f"{env_var}: base64 decode failed — {type(exc).__name__}: {exc}")
            continue

        try:
            json.loads(decoded)
        except (json.JSONDecodeError, ValueError) as exc:
            messages.append(f"{env_var}: decoded content is not valid JSON — {exc}")
            continue

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(decoded)
            messages.append(f"{env_var}: decoded and written to {target_path.name}")
        except Exception as exc:
            messages.append(f"{env_var}: write failed — {type(exc).__name__}: {exc}")

    return messages


def cloud_startup(print_fn=print) -> None:
    """Run all cloud startup steps. Safe to call on Windows dev too (no-ops if files exist)."""
    results = decode_token_env_vars()
    for msg in results:
        print_fn(f"[cloud-startup] {msg}")
