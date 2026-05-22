"""
Focused tests for autonomous cleanup routing in telegram_listener.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_telegram_autonomous_cleanup -v
"""
from __future__ import annotations

import os
import sys
import threading
import unittest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestIsAutonomousCleanupCommand(unittest.TestCase):
    def _check(self, msg):
        from inbox_scout.telegram_listener import _is_autonomous_cleanup_command
        return _is_autonomous_cleanup_command(msg)

    def test_cleanup_bare(self):
        self.assertTrue(self._check("cleanup"))

    def test_cleanup_with_whitespace(self):
        self.assertTrue(self._check("  cleanup  "))

    def test_clean_up(self):
        self.assertTrue(self._check("clean up"))

    def test_clean_all(self):
        self.assertTrue(self._check("clean all"))

    def test_clean_my_inbox(self):
        self.assertTrue(self._check("clean my inbox"))

    def test_get_me_closer_to_inbox_zero(self):
        self.assertTrue(self._check("get me closer to inbox zero"))

    def test_cleanup_status_excluded(self):
        self.assertFalse(self._check("cleanup status"))

    def test_cleanup_progress_excluded(self):
        self.assertFalse(self._check("cleanup progress"))

    def test_cleanup_help_excluded(self):
        self.assertFalse(self._check("cleanup help"))

    def test_cancel_excluded(self):
        self.assertFalse(self._check("cancel"))

    def test_yes_excluded(self):
        self.assertFalse(self._check("yes"))

    def test_sort_all_excluded(self):
        self.assertFalse(self._check("sort all"))

    def test_status_excluded(self):
        self.assertFalse(self._check("status"))


class TestCleanupEtaMsg(unittest.TestCase):
    def test_eta_includes_unread_count_and_minutes(self):
        import inbox_scout.telegram_listener as tl
        mock_svc = MagicMock()
        with patch.object(tl, "_get_modify_service_for_autopilot", return_value=mock_svc), \
             patch.object(tl, "_get_unread_inbox_count", return_value=50), \
             patch.object(tl, "AUTOPILOT_MAX_LIMIT", 25):
            msg = tl._cleanup_eta_msg()
        self.assertIn("50", msg)
        self.assertIn("minute", msg)

    def test_eta_math_uses_ceil_batches(self):
        import inbox_scout.telegram_listener as tl
        mock_svc = MagicMock()
        with patch.object(tl, "_get_modify_service_for_autopilot", return_value=mock_svc), \
             patch.object(tl, "_get_unread_inbox_count", return_value=26), \
             patch.object(tl, "AUTOPILOT_MAX_LIMIT", 25):
            msg = tl._cleanup_eta_msg()
        # 26 unread / 25 per batch = 2 batches = 2 minutes
        self.assertIn("2 minute", msg)

    def test_eta_minimum_one_minute(self):
        import inbox_scout.telegram_listener as tl
        mock_svc = MagicMock()
        with patch.object(tl, "_get_modify_service_for_autopilot", return_value=mock_svc), \
             patch.object(tl, "_get_unread_inbox_count", return_value=5), \
             patch.object(tl, "AUTOPILOT_MAX_LIMIT", 25):
            msg = tl._cleanup_eta_msg()
        self.assertIn("1 minute", msg)

    def test_eta_fallback_when_count_unavailable(self):
        import inbox_scout.telegram_listener as tl
        with patch.object(tl, "_get_modify_service_for_autopilot", side_effect=Exception("auth fail")):
            msg = tl._cleanup_eta_msg()
        self.assertIn("few minutes", msg)
        self.assertNotIn("There are", msg)


class TestCleanupThread(unittest.TestCase):
    def test_sends_autopilot_result(self):
        import inbox_scout.telegram_listener as tl
        sent = []
        with patch.object(tl, "run_inbox_zero_autopilot", return_value="Cleanup done. Scanned 10."), \
             patch.object(tl, "send_message", side_effect=sent.append):
            tl._cleanup_thread("cleanup")
        self.assertEqual(len(sent), 1)
        self.assertIn("Cleanup done", sent[0])

    def test_exception_sends_safe_failure_message(self):
        import inbox_scout.telegram_listener as tl
        sent = []
        with patch.object(tl, "run_inbox_zero_autopilot", side_effect=RuntimeError("api down")), \
             patch.object(tl, "send_message", side_effect=sent.append), \
             patch.object(tl, "_log_error"):
            tl._cleanup_thread("cleanup")
        self.assertEqual(len(sent), 1)
        self.assertIn("Gmail not touched", sent[0])
        self.assertIn("No further action", sent[0])

    def test_exception_message_does_not_include_trash_or_archive(self):
        import inbox_scout.telegram_listener as tl
        sent = []
        with patch.object(tl, "run_inbox_zero_autopilot", side_effect=RuntimeError("fail")), \
             patch.object(tl, "send_message", side_effect=sent.append), \
             patch.object(tl, "_log_error"):
            tl._cleanup_thread("cleanup")
        self.assertNotIn("trash", sent[0].lower())
        self.assertNotIn("archive", sent[0].lower())


class TestRunOnceAutonomousCleanupRouting(unittest.TestCase):
    def _make_update(self, text: str, chat_id: str = "12345") -> dict:
        return {
            "update_id": 1001,
            "message": {
                "chat": {"id": chat_id},
                "text": text,
            },
        }

    def _run_with_message(self, text: str):
        import inbox_scout.telegram_listener as tl
        sent = []
        started_threads = []

        class FakeThread:
            def __init__(self, target=None, args=(), daemon=False):
                self._target = target
                self._args = args
                started_threads.append(self)

            def start(self):
                pass

        with patch.object(tl, "load_config", return_value={"telegram_chat_id": "12345"}), \
             patch.object(tl, "load_state", return_value={"offset": 0}), \
             patch.object(tl, "save_state"), \
             patch.object(tl, "get_updates", return_value=[self._make_update(text)]), \
             patch.object(tl, "send_message", side_effect=sent.append), \
             patch.object(tl, "_cleanup_eta_msg", return_value="There are 30 unread emails. Estimated completion time: about 2 minutes."), \
             patch("inbox_scout.telegram_listener.threading.Thread", FakeThread):
            tl.run_once()

        return sent, started_threads

    def test_cleanup_sends_eta_immediately(self):
        sent, threads = self._run_with_message("cleanup")
        self.assertGreater(len(sent), 0)
        self.assertIn("30 unread", sent[0])
        self.assertIn("2 minutes", sent[0])

    def test_cleanup_starts_background_thread(self):
        sent, threads = self._run_with_message("cleanup")
        self.assertEqual(len(threads), 1)
        self.assertEqual(threads[0]._target.__name__, "_cleanup_thread")

    def test_cleanup_thread_receives_original_text(self):
        sent, threads = self._run_with_message("cleanup")
        self.assertEqual(threads[0]._args, ("cleanup",))

    def test_cleanup_status_does_not_start_cleanup_thread(self):
        import inbox_scout.telegram_listener as tl
        started_threads = []

        class FakeThread:
            def __init__(self, target=None, args=(), daemon=False):
                started_threads.append(target)
            def start(self):
                pass

        with patch.object(tl, "load_config", return_value={"telegram_chat_id": "12345"}), \
             patch.object(tl, "load_state", return_value={"offset": 0}), \
             patch.object(tl, "save_state"), \
             patch.object(tl, "get_updates", return_value=[self._make_update("cleanup status")]), \
             patch.object(tl, "send_message"), \
             patch.object(tl, "handle_command", return_value="status ok"), \
             patch("inbox_scout.telegram_listener.threading.Thread", FakeThread):
            tl.run_once()

        cleanup_thread_started = any(
            getattr(t, "__name__", "") == "_cleanup_thread" for t in started_threads
        )
        self.assertFalse(cleanup_thread_started)

    def test_clean_up_phrase_starts_cleanup(self):
        sent, threads = self._run_with_message("clean up")
        self.assertEqual(len(threads), 1)
        self.assertEqual(threads[0]._target.__name__, "_cleanup_thread")


if __name__ == "__main__":
    unittest.main()
