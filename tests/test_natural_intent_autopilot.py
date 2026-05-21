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

        # These should NOT trigger autopilot
        self.assertFalse(_is_autopilot_cleanup("yes"))
        self.assertFalse(_is_autopilot_cleanup("cancel"))
        self.assertFalse(_is_autopilot_cleanup("move trash"))
        self.assertFalse(_is_autopilot_cleanup("sort all"))
        self.assertFalse(_is_autopilot_cleanup("queue"))
        self.assertFalse(_is_autopilot_cleanup("status"))


if __name__ == "__main__":
    unittest.main()
