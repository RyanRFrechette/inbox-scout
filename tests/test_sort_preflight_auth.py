"""Tests: sort-all preflight blocks on auth failure and does not save pending autopilot."""
from __future__ import annotations
import unittest
from unittest.mock import patch, call

from inbox_scout import natural_intent


class TestSortPreflightAuthGuard(unittest.TestCase):

    def _run_preview(self, text, p_counts, s_counts):
        with patch("inbox_scout.natural_intent._fetch_inbox_counts", side_effect=[p_counts, s_counts]), \
             patch("inbox_scout.natural_intent._save_pending_autopilot") as mock_save, \
             patch("inbox_scout.natural_intent._parse_account", return_value="both"):
            result = natural_intent._inbox_zero_preview_prompt(text)
        return result, mock_save

    def test_primary_auth_fail_blocks_and_no_pending(self):
        result, mock_save = self._run_preview("sort all", (-1, -1), (3, 10))
        self.assertIn("Primary Gmail authorization failed", result)
        self.assertIn("No Gmail changes made", result)
        mock_save.assert_not_called()

    def test_secondary_auth_fail_blocks_and_no_pending(self):
        result, mock_save = self._run_preview("sort all", (5, 20), (-1, -1))
        self.assertIn("Secondary Gmail authorization failed", result)
        self.assertIn("No Gmail changes made", result)
        mock_save.assert_not_called()

    def test_healthy_both_accounts_saves_pending_and_shows_prompt(self):
        result, mock_save = self._run_preview("sort all", (5, 20), (3, 10))
        self.assertIn("Ready to sort both inboxes", result)
        self.assertIn("Reply yes to start", result)
        mock_save.assert_called_once()

    def test_primary_only_auth_fail_blocks(self):
        with patch("inbox_scout.natural_intent._fetch_inbox_counts", return_value=(-1, -1)), \
             patch("inbox_scout.natural_intent._save_pending_autopilot") as mock_save, \
             patch("inbox_scout.natural_intent._parse_account", return_value="primary"):
            result = natural_intent._inbox_zero_preview_prompt("sort primary inbox")
        self.assertIn("Primary Gmail authorization failed", result)
        self.assertIn("No Gmail changes made", result)
        mock_save.assert_not_called()

    def test_primary_only_healthy_saves_pending(self):
        with patch("inbox_scout.natural_intent._fetch_inbox_counts", return_value=(7, 30)), \
             patch("inbox_scout.natural_intent._save_pending_autopilot") as mock_save, \
             patch("inbox_scout.natural_intent._parse_account", return_value="primary"):
            result = natural_intent._inbox_zero_preview_prompt("sort primary inbox")
        self.assertIn("Ready to sort primary inbox", result)
        self.assertIn("Reply yes to start", result)
        mock_save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
