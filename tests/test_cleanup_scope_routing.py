"""Tests: unspecified cleanup scope routes to both accounts; explicit scope routes correctly."""
from __future__ import annotations
import unittest
from unittest.mock import patch

from inbox_scout import natural_intent


class TestCleanupScopeRouting(unittest.TestCase):

    def _route(self, phrase: str, both_return="both done", single_return="single done"):
        with patch("inbox_scout.natural_intent._run_both_autopilot_cleanup", return_value=both_return) as mock_both, \
             patch("inbox_scout.natural_intent._run_autonomous_cleanup", return_value=single_return) as mock_single:
            result = natural_intent.handle_natural_message(phrase)
        return result, mock_both, mock_single

    def test_bare_cleanup_routes_to_both(self):
        result, mock_both, mock_single = self._route("cleanup")
        mock_both.assert_called_once()
        mock_single.assert_not_called()

    def test_clean_up_routes_to_both(self):
        result, mock_both, mock_single = self._route("clean up")
        mock_both.assert_called_once()
        mock_single.assert_not_called()

    def test_clean_my_inbox_routes_to_both(self):
        result, mock_both, mock_single = self._route("clean my inbox")
        mock_both.assert_called_once()
        mock_single.assert_not_called()

    def test_explicit_primary_routes_to_single(self):
        # "clean up" matches _AUTOPILOT_PHRASES; "primary inbox" sets account scope
        result, mock_both, mock_single = self._route("clean up my primary inbox")
        mock_single.assert_called_once()
        call_kwargs = mock_single.call_args
        self.assertEqual(call_kwargs[1].get("account") or call_kwargs[0][1], "primary")
        mock_both.assert_not_called()

    def test_explicit_secondary_routes_to_single(self):
        result, mock_both, mock_single = self._route("clean up my secondary inbox")
        mock_single.assert_called_once()
        call_kwargs = mock_single.call_args
        self.assertEqual(call_kwargs[1].get("account") or call_kwargs[0][1], "secondary")
        mock_both.assert_not_called()


if __name__ == "__main__":
    unittest.main()
