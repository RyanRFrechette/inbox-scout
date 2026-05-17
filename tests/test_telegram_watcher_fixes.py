"""
Focused tests for telegram watcher stability fixes.

Covers:
- kill_stale_watchers ignores PowerShell/shell processes with telegram_watch in cmdline
- kill_stale_watchers only kills Python exe processes
- _redact() removes bot tokens from URLs and log strings
- validate_telegram_env() catches missing/invalid token and chat ID without printing secrets

Run:
  $env:PYTHONPATH = "src"; .venv\\Scripts\\python.exe -m unittest tests.test_telegram_watcher_fixes -v
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _extract_killed_pids(cmd):
    """Extract PIDs from Stop-Process -Id <pid> commands."""
    joined = " ".join(str(c) for c in cmd)
    if "Stop-Process" not in joined:
        return []
    m = re.search(r"-Id\s+(\d+)", joined)
    return [int(m.group(1))] if m else []


# ---------------------------------------------------------------------------
# Token redaction
# ---------------------------------------------------------------------------
class TestRedact(unittest.TestCase):
    def _redact(self, text):
        from inbox_scout.telegram_watch import _redact
        return _redact(text)

    def test_redacts_token_in_url(self):
        url = "https://api.telegram.org/bot123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_abcdefgh12/sendMessage"
        result = self._redact(url)
        self.assertIn("[BOT_TOKEN]", result)
        self.assertNotIn("ABCdefGHIjklMNOpqrSTUvwxYZ_abcdefgh12", result)

    def test_redacts_token_in_plain_string(self):
        text = "Token is 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_abcdefgh12 here"
        result = self._redact(text)
        self.assertIn("[BOT_TOKEN]", result)
        self.assertNotIn("ABCdefGHIjklMNOpqrSTUvwxYZ_abcdefgh12", result)

    def test_leaves_non_token_strings_alone(self):
        text = "No token here, just some normal log output"
        self.assertEqual(self._redact(text), text)

    def test_short_token_like_string_not_redacted(self):
        # Too short after colon — not a real token
        text = "ref:shortval"
        self.assertEqual(self._redact(text), text)


# ---------------------------------------------------------------------------
# kill_stale_watchers — Python-exe-only filter
# ---------------------------------------------------------------------------
class TestKillStaleWatchers(unittest.TestCase):
    def _run_kill(self, procs_json, our_pid=9999):
        """Invoke kill_stale_watchers with mocked subprocess output and our_pid."""
        import json
        import inbox_scout.telegram_watch as tw

        scan_result = MagicMock()
        scan_result.stdout = json.dumps(procs_json)
        stop_result = MagicMock()
        stop_result.stdout = ""

        killed_pids = []
        call_count = [0]

        def fake_run(cmd, **kwargs):
            call_count[0] += 1
            killed_pids.extend(_extract_killed_pids(cmd))
            return scan_result if call_count[0] == 1 else stop_result

        with patch("inbox_scout.telegram_watch.os.getpid", return_value=our_pid), \
             patch("inbox_scout.telegram_watch.subprocess.run", side_effect=fake_run), \
             patch("inbox_scout.telegram_watch.log"):
            tw.kill_stale_watchers()

        return killed_pids

    def test_ignores_powershell_process(self):
        procs = [{"ProcessId": 1001, "ExecutablePath": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"}]
        killed = self._run_kill(procs)
        self.assertNotIn(1001, killed)

    def test_ignores_pwsh_process(self):
        procs = [{"ProcessId": 1002, "ExecutablePath": "C:\\Program Files\\PowerShell\\7\\pwsh.exe"}]
        killed = self._run_kill(procs)
        self.assertNotIn(1002, killed)

    def test_ignores_cmd_process(self):
        procs = [{"ProcessId": 1003, "ExecutablePath": "C:\\Windows\\System32\\cmd.exe"}]
        killed = self._run_kill(procs)
        self.assertNotIn(1003, killed)

    def test_ignores_current_pid(self):
        procs = [{"ProcessId": 9999, "ExecutablePath": "C:\\some\\python.exe"}]
        killed = self._run_kill(procs, our_pid=9999)
        self.assertNotIn(9999, killed)

    def test_kills_stale_python_watcher(self):
        # A python.exe that is NOT our venv python should be killed
        import inbox_scout.telegram_watch as tw
        import json
        procs = [{"ProcessId": 2000, "ExecutablePath": "C:\\other\\python.exe"}]

        scan_result = MagicMock()
        scan_result.stdout = json.dumps(procs)
        stop_result = MagicMock()
        stop_result.stdout = ""

        killed_pids = []
        call_count = [0]

        def fake_run(cmd, **kwargs):
            call_count[0] += 1
            killed_pids.extend(_extract_killed_pids(cmd))
            return scan_result if call_count[0] == 1 else stop_result

        with patch("inbox_scout.telegram_watch.os.getpid", return_value=9999), \
             patch("inbox_scout.telegram_watch.subprocess.run", side_effect=fake_run), \
             patch("inbox_scout.telegram_watch.log"):
            tw.kill_stale_watchers()

        self.assertIn(2000, killed_pids)

    def test_does_not_kill_venv_python_duplicate(self):
        # A duplicate venv python watcher — port lock handles it, not a kill
        import inbox_scout.telegram_watch as tw
        import json

        venv_path = str((tw.PROJECT_ROOT / ".venv" / "Scripts" / "python.exe").resolve())
        procs = [{"ProcessId": 3000, "ExecutablePath": venv_path}]

        scan_result = MagicMock()
        scan_result.stdout = json.dumps(procs)
        stop_result = MagicMock()
        stop_result.stdout = ""

        killed_pids = []
        call_count = [0]

        def fake_run(cmd, **kwargs):
            call_count[0] += 1
            killed_pids.extend(_extract_killed_pids(cmd))
            return scan_result if call_count[0] == 1 else stop_result

        with patch("inbox_scout.telegram_watch.os.getpid", return_value=9999), \
             patch("inbox_scout.telegram_watch.subprocess.run", side_effect=fake_run), \
             patch("inbox_scout.telegram_watch.log"):
            tw.kill_stale_watchers()

        self.assertNotIn(3000, killed_pids)


# ---------------------------------------------------------------------------
# validate_telegram_env
# ---------------------------------------------------------------------------
class TestValidateTelegramEnv(unittest.TestCase):
    def test_valid_config_returns_empty(self):
        from inbox_scout.env_loader import validate_telegram_env
        env = {"TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_abcdefgh12", "TELEGRAM_CHAT_ID": "987654321"}
        with patch.dict(os.environ, env):
            self.assertEqual(validate_telegram_env(), [])

    def test_missing_token_flagged(self):
        from inbox_scout.env_loader import validate_telegram_env
        clean = {k: v for k, v in os.environ.items() if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}
        with patch.dict(os.environ, {**clean, "TELEGRAM_CHAT_ID": "123"}, clear=True):
            issues = validate_telegram_env()
            self.assertTrue(any("TELEGRAM_BOT_TOKEN" in i for i in issues))

    def test_token_without_colon_flagged(self):
        from inbox_scout.env_loader import validate_telegram_env
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "nocolontoken", "TELEGRAM_CHAT_ID": "123"}):
            issues = validate_telegram_env()
            self.assertTrue(any("TELEGRAM_BOT_TOKEN" in i for i in issues))

    def test_blank_token_flagged(self):
        from inbox_scout.env_loader import validate_telegram_env
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "123"}):
            issues = validate_telegram_env()
            self.assertTrue(any("TELEGRAM_BOT_TOKEN" in i for i in issues))

    def test_missing_chat_id_flagged(self):
        from inbox_scout.env_loader import validate_telegram_env
        clean = {k: v for k, v in os.environ.items() if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}
        with patch.dict(os.environ, {**clean, "TELEGRAM_BOT_TOKEN": "123:abc"}, clear=True):
            issues = validate_telegram_env()
            self.assertTrue(any("TELEGRAM_CHAT_ID" in i for i in issues))

    def test_issues_do_not_reveal_token_value(self):
        from inbox_scout.env_loader import validate_telegram_env
        secret = "999999999:SuperSecretTokenValueNeverReveal_abcde"
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": secret, "TELEGRAM_CHAT_ID": ""}):
            issues = validate_telegram_env()
            for issue in issues:
                self.assertNotIn(secret, issue)


if __name__ == "__main__":
    unittest.main()
