from __future__ import annotations

import contextlib
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from inbox_scout.cloud_startup import cloud_startup
from inbox_scout.env_loader import load_env, env_status, validate_telegram_env
from inbox_scout.telegram_listener import run_once


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_PATH = LOG_DIR / "telegram_watch.log"
LOCK_PORT = 47631

# Matches Telegram bot tokens (digits:alphanumeric, 35+ chars after colon)
_TOKEN_RE = re.compile(r"\d{6,12}:[A-Za-z0-9_\-]{35,}")


def _redact(text: str) -> str:
    """Replace any Telegram bot token in text with [BOT_TOKEN]."""
    return _TOKEN_RE.sub("[BOT_TOKEN]", text)


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {_redact(message)}\n")


_PYTHON_EXE_NAMES = {"python.exe", "pythonw.exe"}
_SHELL_EXE_NAMES = {"powershell.exe", "pwsh.exe", "cmd.exe", "explorer.exe", "wt.exe", "windowsterminal.exe"}


def kill_stale_watchers() -> None:
    """Kill stale Python telegram_watch processes on Windows. No-op on Linux/macOS."""
    if sys.platform != "win32":
        log("kill_stale_watchers: non-Windows platform — skipping (port lock handles dedup)")
        return

    our_pid = os.getpid()
    venv_python = str((PROJECT_ROOT / ".venv" / "Scripts" / "python.exe").resolve()).lower()
    killed_any = False

    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.CommandLine -like '*telegram_watch*' } | "
                    "Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        raw = result.stdout.strip()
        if not raw:
            return

        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]

        for proc in data:
            pid = proc.get("ProcessId")
            exe = str(proc.get("ExecutablePath") or "").lower()
            if pid is None or pid == our_pid:
                continue

            exe_name = Path(exe).name if exe else ""
            if exe_name not in _PYTHON_EXE_NAMES:
                log(
                    f"Skipping non-Python process with telegram_watch in cmdline: "
                    f"PID={pid} exe={exe_name or '(unknown)'}"
                )
                continue

            if exe == venv_python:
                log(f"Duplicate venv watcher detected: PID={pid} — port lock will handle it.")
            else:
                log(f"Killing stale/non-venv Python watcher: PID={pid} exe={exe_name}")
                subprocess.run(
                    [
                        "powershell", "-NoProfile", "-NonInteractive", "-Command",
                        f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue",
                    ],
                    timeout=5,
                )
                killed_any = True

    except Exception as exc:
        log(f"Warning: stale watcher scan failed: {type(exc).__name__}: {exc}")

    if killed_any:
        time.sleep(1)


def refuse_global_python() -> bool:
    """Reject non-venv Python on Windows dev. No-op on cloud (no .venv present)."""
    if sys.platform != "win32":
        return False

    venv_dir = PROJECT_ROOT / ".venv"
    if not venv_dir.exists():
        # No .venv — cloud or CI environment; allow any Python
        return False

    expected = (venv_dir / "Scripts" / "python.exe").resolve()
    actual = Path(sys.executable).resolve()

    if actual == expected:
        return False

    message = (
        "REFUSING TO START: telegram_watch must run from project .venv Python only. "
        f"Actual Python: {actual}"
    )
    print(message)
    log(message)
    return True


def acquire_single_instance_lock() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", LOCK_PORT))
    s.listen(1)
    return s


def main() -> None:
    cloud_startup(print_fn=log)
    load_env()
    log(f"Env loaded. {env_status()}")

    # On Linux/cloud, require explicit opt-in to avoid competing with a local watcher.
    # On Windows, always allowed. On Render, set ENABLE_TELEGRAM_WATCHER=true in the dashboard.
    if sys.platform != "win32" and os.environ.get("ENABLE_TELEGRAM_WATCHER", "").lower() != "true":
        msg = "Cloud Telegram watcher disabled. Set ENABLE_TELEGRAM_WATCHER=true to enable Atlas on this host."
        print(msg)
        log(msg)
        return

    issues = validate_telegram_env()
    if issues:
        for issue in issues:
            log(f"Startup config error: {issue}")
            print(f"ERROR: {issue}")
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env then restart.")
        return

    kill_stale_watchers()

    if refuse_global_python():
        return

    try:
        lock_socket = acquire_single_instance_lock()
    except OSError:
        print("Inbox Scout Telegram watcher is already running.")
        log("Watcher refused to start because another instance already owns the lock.")
        return

    print("Inbox Scout Telegram watcher is running.")
    print("Atlas will now listen automatically while this process is active.")
    print("No Gmail actions are enabled from this watcher.")
    log("Watcher started from project .venv Python. Gmail actions remain disabled.")

    while True:
        try:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                run_once()

            output = buffer.getvalue().strip()

            if output and "No new Telegram updates." not in output:
                print(output)
                log(output)

            time.sleep(2)

        except KeyboardInterrupt:
            log("Watcher stopped by keyboard interrupt.")
            print("Inbox Scout Telegram watcher stopped.")
            break

        except Exception as e:
            log(f"ERROR: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            time.sleep(10)

    lock_socket.close()


if __name__ == "__main__":
    main()
