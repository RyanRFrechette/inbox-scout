from __future__ import annotations

import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from inbox_scout.telegram_listener import run_once


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_PATH = LOG_DIR / "telegram_watch.log"
LOCK_PORT = 47631


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {message}\n")


def kill_stale_watchers() -> None:
    """Kill any telegram_watch processes not running from the project venv Python."""
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
            if exe == venv_python:
                log(f"Duplicate venv watcher detected: PID={pid} — port lock will handle it.")
            else:
                log(
                    f"Killing stale/non-venv watcher: PID={pid} "
                    f"exe={proc.get('ExecutablePath')}"
                )
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
    expected = (PROJECT_ROOT / ".venv" / "Scripts" / "python.exe").resolve()
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
