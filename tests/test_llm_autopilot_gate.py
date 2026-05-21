"""
Focused tests for LLM inbox autopilot confirmation gate.

Covers:
- LLM inbox_zero_autopilot returns confirmation prompt, does NOT call run_inbox_zero_autopilot
- CONFIRM INBOX AUTOPILOT runs pending autopilot and clears state
- cancel autopilot clears pending action
- read-only LLM intents (inbox_count) still run immediately
- deterministic sort all is unchanged
- no pending → confirm says nothing is pending
- no pending → cancel says nothing to cancel

Run:
  $env:PYTHONPATH = "src"; .venv\\Scripts\\python.exe -m unittest tests.test_llm_autopilot_gate -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _pending(action="inbox_zero_autopilot", original="handle my inbox"):
    return {"pending": action, "original_text": original}


class TestLLMAutopilotGate(unittest.TestCase):
    """Gate: LLM-routed autopilot must not run until confirmed."""

    def _call_fallback(self, parsed, original="handle my inbox"):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.parse_intent", return_value=parsed), \
             patch("inbox_scout.natural_intent.run_inbox_zero_autopilot") as mock_run, \
             patch("inbox_scout.natural_intent._save_pending_autopilot") as mock_save:
            result = ni._llm_fallback(original)
            return result, mock_run, mock_save

    def test_autopilot_intent_returns_prompt_not_run(self):
        parsed = {"intent": "inbox_zero_autopilot", "confidence": 0.92,
                  "requires_write": True, "clarifying_question": ""}
        result, mock_run, mock_save = self._call_fallback(parsed)

        mock_run.assert_not_called()
        mock_save.assert_called_once_with("handle my inbox")
        self.assertIn("CONFIRM INBOX AUTOPILOT", result)
        self.assertIn("cancel autopilot", result)

    def test_autopilot_prompt_mentions_write_actions(self):
        parsed = {"intent": "inbox_zero_autopilot", "confidence": 0.88,
                  "requires_write": True, "clarifying_question": ""}
        result, _, _ = self._call_fallback(parsed)
        # User must know what they're confirming
        self.assertTrue(
            any(w in result.lower() for w in ("move", "label", "trash")),
            "Confirmation prompt should mention what actions will happen"
        )

    def test_inbox_count_runs_immediately_no_gate(self):
        parsed = {"intent": "inbox_count", "confidence": 0.88,
                  "requires_write": False, "clarifying_question": ""}
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.parse_intent", return_value=parsed), \
             patch("inbox_scout.natural_intent.build_inbox_count_message", return_value="COUNT_OK") as mock_count, \
             patch("inbox_scout.natural_intent._save_pending_autopilot") as mock_save:
            result = ni._llm_fallback("how bad is my inbox")
            mock_count.assert_called_once()
            mock_save.assert_not_called()
        self.assertEqual(result, "COUNT_OK")

    def test_queue_summary_runs_immediately(self):
        parsed = {"intent": "queue_summary", "confidence": 0.85,
                  "requires_write": False, "clarifying_question": ""}
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.parse_intent", return_value=parsed), \
             patch("inbox_scout.natural_intent.queue_summary", return_value="QUEUE_OK"), \
             patch("inbox_scout.natural_intent._save_pending_autopilot") as mock_save:
            result = ni._llm_fallback("show me the queue")
            mock_save.assert_not_called()
        self.assertEqual(result, "QUEUE_OK")


class TestConfirmAndCancel(unittest.TestCase):
    """Confirm and cancel gate via handle_natural_message."""

    def test_confirm_runs_autopilot_and_clears_state(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent._get_pending_action",
                   return_value=_pending("inbox_zero_autopilot", "handle my inbox")), \
             patch("inbox_scout.natural_intent._clear_pending_action") as mock_clear, \
             patch("inbox_scout.natural_intent.run_inbox_zero_autopilot",
                   return_value="AUTOPILOT_RAN") as mock_run:
            result = ni.handle_natural_message("CONFIRM INBOX AUTOPILOT")

        mock_run.assert_called_once_with("handle my inbox", account="primary")
        mock_clear.assert_called_once()
        self.assertEqual(result, "AUTOPILOT_RAN")

    def test_confirm_case_insensitive(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent._get_pending_action",
                   return_value=_pending()), \
             patch("inbox_scout.natural_intent._clear_pending_action"), \
             patch("inbox_scout.natural_intent.run_inbox_zero_autopilot",
                   return_value="AUTOPILOT_RAN"):
            result = ni.handle_natural_message("confirm inbox autopilot")
        self.assertEqual(result, "AUTOPILOT_RAN")

    def test_confirm_with_no_pending_says_nothing_pending(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent._get_pending_action", return_value={}), \
             patch("inbox_scout.natural_intent.run_inbox_zero_autopilot") as mock_run:
            result = ni.handle_natural_message("confirm inbox autopilot")
        mock_run.assert_not_called()
        self.assertIn("pending", result.lower())

    def test_cancel_autopilot_clears_pending(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent._get_pending_action",
                   return_value=_pending()), \
             patch("inbox_scout.natural_intent._clear_pending_action") as mock_clear:
            result = ni.handle_natural_message("cancel autopilot")
        mock_clear.assert_called_once()
        self.assertIn("Cancelled", result)
        self.assertIn("Gmail not touched", result)

    def test_cancel_inbox_autopilot_phrase_also_works(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent._get_pending_action",
                   return_value=_pending()), \
             patch("inbox_scout.natural_intent._clear_pending_action") as mock_clear:
            result = ni.handle_natural_message("cancel inbox autopilot")
        mock_clear.assert_called_once()
        self.assertIn("Cancelled", result)

    def test_cancel_with_no_pending_says_nothing_to_cancel(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent._get_pending_action", return_value={}):
            result = ni.handle_natural_message("cancel autopilot")
        self.assertIn("Nothing pending", result)


class TestStateHelpers(unittest.TestCase):
    """Unit tests for pending state read/write/clear."""

    def test_save_and_get_round_trip(self):
        from inbox_scout import natural_intent as ni
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "pending.json"
            with patch.object(ni, "_LLM_PENDING_PATH", tmp_path):
                ni._save_pending_autopilot("handle my inbox")
                result = ni._get_pending_action()
        self.assertEqual(result["pending"], "inbox_zero_autopilot")
        self.assertEqual(result["original_text"], "handle my inbox")

    def test_clear_removes_file(self):
        from inbox_scout import natural_intent as ni
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "pending.json"
            with patch.object(ni, "_LLM_PENDING_PATH", tmp_path):
                ni._save_pending_autopilot("something")
                self.assertTrue(tmp_path.exists())
                ni._clear_pending_action()
                self.assertFalse(tmp_path.exists())

    def test_get_returns_empty_when_no_file(self):
        from inbox_scout import natural_intent as ni
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "pending.json"
            with patch.object(ni, "_LLM_PENDING_PATH", tmp_path):
                result = ni._get_pending_action()
        self.assertEqual(result, {})

    def test_get_returns_empty_on_corrupt_file(self):
        from inbox_scout import natural_intent as ni
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "pending.json"
            tmp_path.write_text("not json", encoding="utf-8")
            with patch.object(ni, "_LLM_PENDING_PATH", tmp_path):
                result = ni._get_pending_action()
        self.assertEqual(result, {})


class TestDeterministicRoutesUnchanged(unittest.TestCase):
    """Existing deterministic routing must be unaffected by this change."""

    def test_sort_all_does_not_hit_llm_or_gate(self):
        # "sort all" is in _INBOX_ZERO_PHRASES → routes to run_inbox_zero_autopilot directly,
        # bypassing both the LLM and the confirmation gate.
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.parse_intent") as mock_llm, \
             patch("inbox_scout.natural_intent.run_inbox_zero_autopilot", return_value="AUTOPILOT_OK") as mock_run:
            result = ni.handle_natural_message("sort all")
        mock_llm.assert_not_called()
        # Confirm gate not involved — run_inbox_zero_autopilot called directly (existing behavior)
        mock_run.assert_called_once()
        self.assertEqual(result, "AUTOPILOT_OK")

    def test_inbox_count_phrase_still_deterministic(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.parse_intent") as mock_llm, \
             patch("inbox_scout.natural_intent.build_inbox_count_message", return_value="COUNT_OK"):
            result = ni.handle_natural_message("how many emails do I have")
        mock_llm.assert_not_called()
        self.assertEqual(result, "COUNT_OK")


if __name__ == "__main__":
    unittest.main()
