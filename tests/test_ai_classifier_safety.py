"""
Focused safety test: classify_with_ai() must preserve manual_review rule results
even when the provider returns a non-manual, low-risk classification.

Run: $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_ai_classifier_safety -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_scout.ai_classifier import classify_with_ai


class TestClassifyWithAiSafety(unittest.TestCase):
    def _unsafe_provider_result(self):
        return {
            "category": "Newsletter",
            "confidence_score": 0.9,
            "risk_score": 10,
            "reason": "Looks like a newsletter.",
            "suggested_action": "Archive it.",
            "manual_review": False,
        }

    def test_manual_review_rule_overrides_provider(self):
        email = {"subject": "Suspicious email", "from": "unknown@example.com", "body": ""}
        rule_result = {
            "category": "Manual review",
            "manual_review": True,
            "risk_score": 90,
            "suggested_action": "Review manually before taking action.",
            "reason": "Matched manual review rule.",
        }

        with patch(
            "inbox_scout.ai_classifier.classify_with_provider",
            return_value=self._unsafe_provider_result(),
        ):
            result = classify_with_ai(email, rule_result)

        self.assertTrue(result["manual_review"], "manual_review must be True")
        self.assertGreaterEqual(result["risk_score"], 90, "risk_score must be >= rule risk_score")
        self.assertEqual(result["suggested_action"], "Review manually before taking action.")
        self.assertIn("Protected rule category preserved", result["reason"])
        self.assertEqual(result["category"], "Manual review")


if __name__ == "__main__":
    unittest.main()
