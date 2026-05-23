"""
Routing tests: natural cleanup phrases must route to run_autopilot_cleanup,
not the yes-gate sort_plan_message path.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_natural_intent_autopilot -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestAutopilotRouting(unittest.TestCase):
    def _assert_routes_to_autopilot(self, phrase: str) -> None:
        from inbox_scout import natural_intent

        called = []

        def fake_autopilot(text: str, account="primary") -> str:
            called.append(text)
            return "autopilot called"

        with patch("inbox_scout.natural_intent.run_autopilot_cleanup", fake_autopilot):
            result = natural_intent.handle_natural_message(phrase)

        self.assertEqual(result, "autopilot called", f"Expected autopilot for: {phrase!r}")
        self.assertEqual(len(called), 1, f"run_autopilot_cleanup should be called once for: {phrase!r}")

    def test_clean_25_emails(self):
        self._assert_routes_to_autopilot("clean 25 emails")

    def test_sort_50_emails(self):
        self._assert_routes_to_autopilot("sort 50 emails")

    def test_get_me_closer_to_inbox_zero(self):
        self._assert_routes_to_autopilot("get me closer to inbox zero")

    def test_handle_a_batch(self):
        self._assert_routes_to_autopilot("handle a batch")

    def test_clean_up_my_inbox(self):
        self._assert_routes_to_autopilot("clean up my inbox")

    def test_clean_the_next_25(self):
        self._assert_routes_to_autopilot("clean the next 25")

    def test_clean_my_inbox(self):
        self._assert_routes_to_autopilot("clean my inbox")

    def test_sort_5_emails(self):
        self._assert_routes_to_autopilot("sort 5 emails")

    def test_clean_up_a_batch(self):
        self._assert_routes_to_autopilot("clean up a batch")

    def test_clean_a_batch(self):
        self._assert_routes_to_autopilot("clean a batch")

    def test_cleanup_bare(self):
        self._assert_routes_to_autopilot("cleanup")

    def test_clean_up_bare(self):
        self._assert_routes_to_autopilot("clean up")

    def test_clean_all_routes_to_autopilot(self):
        self._assert_routes_to_autopilot("clean all")

    def test_cleanup_does_not_return_yes_cancel_prompt(self):
        from inbox_scout import natural_intent
        with patch("inbox_scout.natural_intent.run_autopilot_cleanup", return_value="Scanned 5 — 5 protected."):
            result = natural_intent.handle_natural_message("cleanup")
        self.assertNotIn("say yes", result.lower())
        self.assertNotIn("say cancel", result.lower())

    def test_cleanup_status_not_routed_to_autopilot(self):
        from inbox_scout import natural_intent
        called = []
        with patch("inbox_scout.natural_intent.run_autopilot_cleanup", side_effect=lambda *a, **kw: called.append(1) or ""), \
             patch("inbox_scout.natural_intent.build_cleanup_status_message", return_value="status ok"):
            result = natural_intent.handle_natural_message("cleanup status")
        self.assertEqual(result, "status ok")
        self.assertEqual(len(called), 0, "run_autopilot_cleanup must not fire for 'cleanup status'")

    def test_autonomous_cleanup_includes_eta_when_unread_known(self):
        from inbox_scout import natural_intent
        with patch("inbox_scout.natural_intent._fetch_inbox_counts", return_value=(20, 50)), \
             patch("inbox_scout.natural_intent.run_autopilot_cleanup", return_value="Done."):
            result = natural_intent._run_autonomous_cleanup("cleanup")
        self.assertIn("20 unread", result)
        self.assertIn("minute", result)

    def test_autonomous_cleanup_skips_eta_when_count_unavailable(self):
        from inbox_scout import natural_intent
        with patch("inbox_scout.natural_intent._fetch_inbox_counts", return_value=(-1, -1)), \
             patch("inbox_scout.natural_intent.run_autopilot_cleanup", return_value="Done."):
            result = natural_intent._run_autonomous_cleanup("cleanup")
        self.assertEqual(result, "Done.")

    def test_is_autopilot_cleanup_helper(self):
        from inbox_scout.natural_intent import _is_autopilot_cleanup

        self.assertTrue(_is_autopilot_cleanup("clean 25 emails"))
        self.assertTrue(_is_autopilot_cleanup("sort 50 emails"))
        self.assertTrue(_is_autopilot_cleanup("get me closer to inbox zero"))
        self.assertTrue(_is_autopilot_cleanup("handle a batch"))
        self.assertTrue(_is_autopilot_cleanup("clean up my inbox"))
        self.assertTrue(_is_autopilot_cleanup("clean the next 25"))
        self.assertTrue(_is_autopilot_cleanup("clean up a batch"))
        self.assertTrue(_is_autopilot_cleanup("clean a batch"))
        self.assertTrue(_is_autopilot_cleanup("cleanup"))
        self.assertTrue(_is_autopilot_cleanup("clean up"))
        self.assertTrue(_is_autopilot_cleanup("clean all"))

        # These should NOT trigger autopilot
        self.assertFalse(_is_autopilot_cleanup("yes"))
        self.assertFalse(_is_autopilot_cleanup("cancel"))
        self.assertFalse(_is_autopilot_cleanup("move trash"))
        self.assertFalse(_is_autopilot_cleanup("sort all"))
        self.assertFalse(_is_autopilot_cleanup("queue"))
        self.assertFalse(_is_autopilot_cleanup("status"))


class TestFilingModeGuard(unittest.TestCase):
    _FILING_STUB = "Inbox Filing Mode preview is not implemented yet."
    _AUTOPILOT_CONFIRM = "CONFIRM INBOX AUTOPILOT"

    def _route(self, phrase: str) -> str:
        from inbox_scout import natural_intent
        with patch.object(natural_intent, "_llm_fallback", return_value="LLM_FALLBACK"):
            return natural_intent.handle_natural_message(phrase)

    def test_file_inbox_not_autopilot(self):
        result = self._route("file inbox")
        self.assertNotIn(self._AUTOPILOT_CONFIRM, result)

    def test_file_safe_emails_not_autopilot(self):
        result = self._route("file safe emails")
        self.assertNotIn(self._AUTOPILOT_CONFIRM, result)

    def test_preview_filing_not_autopilot(self):
        result = self._route("preview filing")
        self.assertNotIn(self._AUTOPILOT_CONFIRM, result)

    def test_file_inbox_returns_stub(self):
        self.assertIn(self._FILING_STUB, self._route("file inbox"))

    def test_file_safe_emails_returns_stub(self):
        self.assertIn(self._FILING_STUB, self._route("file safe emails"))

    def test_preview_filing_returns_stub(self):
        self.assertIn(self._FILING_STUB, self._route("preview filing"))

    def test_sort_all_not_affected(self):
        from inbox_scout import natural_intent
        with patch.object(natural_intent, "_inbox_zero_preview_prompt", return_value="INBOX_ZERO"):
            result = natural_intent.handle_natural_message("sort all")
        self.assertNotIn(self._FILING_STUB, result)

    def test_confirm_autopilot_not_filing_stub(self):
        from inbox_scout import natural_intent
        with patch.object(natural_intent, "_llm_fallback", return_value="LLM_FALLBACK"):
            result = natural_intent.handle_natural_message("confirm inbox autopilot")
        self.assertNotIn(self._FILING_STUB, result)


if __name__ == "__main__":
    unittest.main()
