"""Tests for cloud_startup.py — token decode from env vars.

All tests use temp dirs. No real token files are read or written.
No live Gmail. No live Telegram.
"""
import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestDecodeTokenEnvVars(unittest.TestCase):

    def _run(self, env: dict, existing_files: list[str] | None = None) -> tuple[list[str], dict]:
        """Helper: run decode_token_env_vars with a temp dir and controlled env."""
        from inbox_scout.cloud_startup import decode_token_env_vars

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            token_paths = {
                "GMAIL_TOKEN_JSON": tmp_path / "token.json",
                "GMAIL_TOKEN_MODIFY_JSON": tmp_path / "token_modify.json",
            }

            for fname in (existing_files or []):
                (tmp_path / fname).write_text("{}")

            with patch.dict(os.environ, env, clear=False):
                # Remove keys not in env
                for key in list(token_paths.keys()):
                    if key not in env:
                        os.environ.pop(key, None)
                messages = decode_token_env_vars(token_paths=token_paths)

            # Capture what files exist and their content
            written = {}
            for name, path in token_paths.items():
                if path.exists():
                    written[name] = path.read_bytes()

        return messages, written

    def test_writes_token_when_env_set_and_file_missing(self):
        payload = b'{"token": "fake_readonly"}'
        encoded = base64.b64encode(payload).decode()
        msgs, written = self._run({"GMAIL_TOKEN_JSON": encoded})
        self.assertIn("GMAIL_TOKEN_JSON", written)
        self.assertEqual(written["GMAIL_TOKEN_JSON"], payload)

    def test_writes_modify_token_when_env_set_and_file_missing(self):
        payload = b'{"token": "fake_modify"}'
        encoded = base64.b64encode(payload).decode()
        msgs, written = self._run({"GMAIL_TOKEN_MODIFY_JSON": encoded})
        self.assertIn("GMAIL_TOKEN_MODIFY_JSON", written)
        self.assertEqual(written["GMAIL_TOKEN_MODIFY_JSON"], payload)

    def test_does_not_overwrite_existing_file(self):
        payload = b'{"token": "new_value"}'
        encoded = base64.b64encode(payload).decode()
        msgs, written = self._run(
            {"GMAIL_TOKEN_JSON": encoded},
            existing_files=["token.json"],
        )
        # File should contain the original "{}" not the new payload
        self.assertNotEqual(written.get("GMAIL_TOKEN_JSON"), payload)
        self.assertTrue(any("already exists" in m for m in msgs))

    def test_skips_when_env_var_not_set(self):
        msgs, written = self._run({})
        self.assertNotIn("GMAIL_TOKEN_JSON", written)
        self.assertNotIn("GMAIL_TOKEN_MODIFY_JSON", written)
        self.assertTrue(any("not set" in m for m in msgs))

    def test_reports_error_on_invalid_base64(self):
        msgs, written = self._run({"GMAIL_TOKEN_JSON": "not-valid-base64!!!"})
        self.assertNotIn("GMAIL_TOKEN_JSON", written)
        self.assertTrue(any("base64 decode failed" in m for m in msgs))

    def test_both_tokens_written_independently(self):
        ro_payload = b'{"token": "readonly"}'
        mod_payload = b'{"token": "modify"}'
        msgs, written = self._run({
            "GMAIL_TOKEN_JSON": base64.b64encode(ro_payload).decode(),
            "GMAIL_TOKEN_MODIFY_JSON": base64.b64encode(mod_payload).decode(),
        })
        self.assertEqual(written["GMAIL_TOKEN_JSON"], ro_payload)
        self.assertEqual(written["GMAIL_TOKEN_MODIFY_JSON"], mod_payload)

    def test_messages_never_contain_token_value(self):
        payload = b'{"secret_field": "supersecretvalue12345"}'
        encoded = base64.b64encode(payload).decode()
        msgs, _ = self._run({"GMAIL_TOKEN_JSON": encoded})
        combined = " ".join(msgs)
        self.assertNotIn("supersecretvalue12345", combined)
        self.assertNotIn(encoded, combined)

    def test_status_message_mentions_filename_not_content(self):
        payload = b'{"x": 1}'
        encoded = base64.b64encode(payload).decode()
        msgs, _ = self._run({"GMAIL_TOKEN_JSON": encoded})
        written_msgs = [m for m in msgs if "decoded and written" in m]
        self.assertEqual(len(written_msgs), 1)
        self.assertIn("token.json", written_msgs[0])


class TestKillStaleWatchersLinuxSafe(unittest.TestCase):
    """kill_stale_watchers must not attempt PowerShell on non-Windows."""

    def test_no_subprocess_on_linux(self):
        import inbox_scout.telegram_watch as tw

        called = []

        def fake_run(*args, **kwargs):
            called.append(args)
            return type("R", (), {"stdout": "", "returncode": 0})()

        with patch("inbox_scout.telegram_watch.subprocess.run", fake_run), \
             patch("inbox_scout.telegram_watch.sys.platform", "linux"):
            tw.kill_stale_watchers()

        self.assertEqual(called, [], "subprocess.run must NOT be called on Linux")

    def test_subprocess_called_on_windows(self):
        import inbox_scout.telegram_watch as tw

        called = []

        def fake_run(*args, **kwargs):
            called.append(True)
            return type("R", (), {"stdout": "", "returncode": 0})()

        with patch("inbox_scout.telegram_watch.subprocess.run", fake_run), \
             patch("inbox_scout.telegram_watch.sys.platform", "win32"):
            tw.kill_stale_watchers()

        self.assertGreater(len(called), 0, "subprocess.run SHOULD be called on Windows")


class TestRefuseGlobalPython(unittest.TestCase):
    """refuse_global_python must allow any Python on non-Windows or when no .venv exists."""

    def test_allows_on_linux(self):
        import inbox_scout.telegram_watch as tw
        with patch("inbox_scout.telegram_watch.sys.platform", "linux"):
            result = tw.refuse_global_python()
        self.assertFalse(result)

    def test_allows_on_mac(self):
        import inbox_scout.telegram_watch as tw
        with patch("inbox_scout.telegram_watch.sys.platform", "darwin"):
            result = tw.refuse_global_python()
        self.assertFalse(result)

    def test_allows_on_windows_when_no_venv(self):
        import inbox_scout.telegram_watch as tw
        with patch("inbox_scout.telegram_watch.sys.platform", "win32"), \
             patch("inbox_scout.telegram_watch.PROJECT_ROOT", Path("/nonexistent/cloud/path")):
            result = tw.refuse_global_python()
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
