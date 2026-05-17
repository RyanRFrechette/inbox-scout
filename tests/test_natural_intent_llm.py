"""
Focused tests for LLM-backed natural intent fallback.

Covers:
- _parse_response: allowed intents, disallowed intents, requires_write safety
- parse_intent routing: inbox_zero_autopilot, inbox_count, low confidence, unknown
- handle_natural_message: LLM not called for existing deterministic phrases
- LLM cannot trigger delete/block/reply

Run:
  $env:PYTHONPATH = "src"; .venv\\Scripts\\python.exe -m unittest tests.test_natural_intent_llm -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_llm_response(intent, confidence=0.9, requires_write=False, clarifying=""):
    return json.dumps({
        "intent": intent,
        "confidence": confidence,
        "scope": "inbox",
        "limit": "all",
        "provider_preference": "auto",
        "requires_write": requires_write,
        "clarifying_question": clarifying,
    })


class TestParseResponse(unittest.TestCase):
    def _parse(self, raw):
        from inbox_scout.natural_intent_llm import _parse_response
        return _parse_response(raw)

    def test_valid_inbox_zero_autopilot(self):
        raw = _make_llm_response("inbox_zero_autopilot", confidence=0.92)
        result = self._parse(raw)
        self.assertEqual(result["intent"], "inbox_zero_autopilot")
        self.assertAlmostEqual(result["confidence"], 0.92)

    def test_valid_inbox_count(self):
        raw = _make_llm_response("inbox_count", confidence=0.88)
        result = self._parse(raw)
        self.assertEqual(result["intent"], "inbox_count")

    def test_disallowed_intent_returns_unknown(self):
        raw = _make_llm_response("delete_all", confidence=0.99)
        result = self._parse(raw)
        self.assertEqual(result["intent"], "unknown")

    def test_block_senders_intent_returns_unknown(self):
        raw = _make_llm_response("block_senders", confidence=0.95)
        result = self._parse(raw)
        self.assertEqual(result["intent"], "unknown")

    def test_requires_write_forced_false_for_non_autopilot(self):
        raw = _make_llm_response("inbox_count", confidence=0.9, requires_write=True)
        result = self._parse(raw)
        self.assertFalse(result["requires_write"])

    def test_requires_write_allowed_for_autopilot(self):
        raw = _make_llm_response("inbox_zero_autopilot", confidence=0.9, requires_write=True)
        result = self._parse(raw)
        self.assertTrue(result["requires_write"])

    def test_low_confidence_preserves_clarifying_question(self):
        raw = _make_llm_response("inbox_zero_autopilot", confidence=0.5,
                                  clarifying="Did you want me to scan all emails or just unread?")
        result = self._parse(raw)
        self.assertIn("scan all emails", result["clarifying_question"])

    def test_no_json_returns_unknown(self):
        result = self._parse("sorry I cannot help")
        self.assertEqual(result["intent"], "unknown")

    def test_invalid_json_returns_unknown(self):
        result = self._parse("{not valid json}")
        self.assertEqual(result["intent"], "unknown")

    def test_confidence_clamped_to_0_1(self):
        raw = json.dumps({"intent": "help", "confidence": 5.0, "scope": "unknown",
                          "limit": "default", "provider_preference": "auto",
                          "requires_write": False, "clarifying_question": ""})
        result = self._parse(raw)
        self.assertLessEqual(result["confidence"], 1.0)


class TestLLMFallbackRouting(unittest.TestCase):
    """Test _llm_fallback dispatch via mocked parse_intent."""

    def _call_fallback(self, parsed_result, original="handle my inbox"):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.parse_intent", return_value=parsed_result), \
             patch("inbox_scout.natural_intent.run_inbox_zero_autopilot", return_value="AUTOPILOT_OK"), \
             patch("inbox_scout.natural_intent.build_inbox_count_message", return_value="COUNT_OK"), \
             patch("inbox_scout.natural_intent.queue_summary", return_value="QUEUE_OK"), \
             patch("inbox_scout.natural_intent.next_review_item", return_value="NEXT_OK"), \
             patch("inbox_scout.natural_intent.model_status_message", return_value="MODEL_OK"), \
             patch("inbox_scout.natural_intent._save_pending_autopilot"):
            return ni._llm_fallback(original)

    def test_inbox_zero_autopilot_routes_to_autopilot(self):
        parsed = {
            "intent": "inbox_zero_autopilot", "confidence": 0.92,
            "requires_write": True, "clarifying_question": "",
        }
        result = self._call_fallback(parsed)
        self.assertIn("CONFIRM INBOX AUTOPILOT", result)

    def test_inbox_count_routes_correctly(self):
        parsed = {
            "intent": "inbox_count", "confidence": 0.88,
            "requires_write": False, "clarifying_question": "",
        }
        result = self._call_fallback(parsed)
        self.assertEqual(result, "COUNT_OK")

    def test_queue_summary_routes_correctly(self):
        parsed = {
            "intent": "queue_summary", "confidence": 0.80,
            "requires_write": False, "clarifying_question": "",
        }
        result = self._call_fallback(parsed, "show my queue")
        self.assertEqual(result, "QUEUE_OK")

    def test_low_confidence_returns_clarifying_question(self):
        parsed = {
            "intent": "inbox_zero_autopilot", "confidence": 0.5,
            "requires_write": False,
            "clarifying_question": "Did you want to scan all emails or just unread ones?",
        }
        result = self._call_fallback(parsed)
        self.assertIn("scan all emails", result)

    def test_low_confidence_no_clarifying_returns_help(self):
        parsed = {
            "intent": "inbox_count", "confidence": 0.4,
            "requires_write": False, "clarifying_question": "",
        }
        result = self._call_fallback(parsed)
        self.assertIn("Not sure", result)

    def test_unknown_intent_returns_help(self):
        parsed = {
            "intent": "unknown", "confidence": 0.95,
            "requires_write": False, "clarifying_question": "",
        }
        result = self._call_fallback(parsed)
        self.assertIn("Not sure", result)


class TestDeterministicRoutePrecedence(unittest.TestCase):
    """Verify existing exact-match phrases do NOT reach the LLM fallback."""

    def test_how_bad_is_my_inbox_does_not_call_llm(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.parse_intent") as mock_llm, \
             patch("inbox_scout.natural_intent.build_inbox_count_message", return_value="COUNT_OK"):
            ni.handle_natural_message("how bad is my inbox right now")
            mock_llm.assert_not_called()

    def test_inbox_situation_does_not_call_llm(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.parse_intent") as mock_llm, \
             patch("inbox_scout.natural_intent.build_inbox_count_message", return_value="COUNT_OK"):
            ni.handle_natural_message("inbox situation")
            mock_llm.assert_not_called()


class TestLLMSafetyBoundary(unittest.TestCase):
    """Verify the LLM parser cannot trigger disallowed Gmail actions."""

    def test_delete_intent_blocked(self):
        from inbox_scout.natural_intent_llm import _parse_response
        raw = _make_llm_response("delete_all_emails", confidence=0.99)
        result = _parse_response(raw)
        self.assertEqual(result["intent"], "unknown")
        self.assertFalse(result["requires_write"])

    def test_send_email_intent_blocked(self):
        from inbox_scout.natural_intent_llm import _parse_response
        raw = _make_llm_response("send_email", confidence=0.99)
        result = _parse_response(raw)
        self.assertEqual(result["intent"], "unknown")

    def test_empty_trash_intent_blocked(self):
        from inbox_scout.natural_intent_llm import _parse_response
        raw = _make_llm_response("empty_trash", confidence=0.99)
        result = _parse_response(raw)
        self.assertEqual(result["intent"], "unknown")


if __name__ == "__main__":
    unittest.main()
