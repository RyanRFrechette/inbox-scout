"""
Focused tests for ai_classifier.classify_with_ai() overprotection fix.

Proves:
- promo/newsletter rule manual_review is NOT hard-preserved — AI result stands
- security alert rule manual_review IS hard-preserved
- receipt/invoice rule manual_review IS hard-preserved
- finance/payment rule manual_review IS hard-preserved
- empty rule category with manual_review — AI result stands

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_ai_classifier_overprotection -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_email():
    return {"subject": "Test email", "from": "sender@example.com", "snippet": "body"}


def _ai_result(category="Newsletter", risk_score=20, manual_review=False):
    return {
        "category": category,
        "confidence_score": 85,
        "risk_score": risk_score,
        "reason": "AI decided",
        "suggested_action": "Archive",
        "manual_review": manual_review,
    }


class TestPromoNotPreserved(unittest.TestCase):
    def test_promotion_ai_result_stands(self):
        from inbox_scout.ai_classifier import classify_with_ai
        rule = {"category": "Promotion", "manual_review": True, "risk_score": 80}
        ai = _ai_result(category="Promotion", risk_score=15, manual_review=False)
        with patch("inbox_scout.ai_classifier.classify_with_provider", return_value=ai):
            result = classify_with_ai(_make_email(), rule)
        self.assertFalse(result["manual_review"])
        self.assertEqual(result["risk_score"], 15)

    def test_newsletter_ai_result_stands(self):
        from inbox_scout.ai_classifier import classify_with_ai
        rule = {"category": "Newsletter", "manual_review": True, "risk_score": 80}
        ai = _ai_result(category="Newsletter", risk_score=18, manual_review=False)
        with patch("inbox_scout.ai_classifier.classify_with_provider", return_value=ai):
            result = classify_with_ai(_make_email(), rule)
        self.assertFalse(result["manual_review"])
        self.assertEqual(result["risk_score"], 18)

    def test_junk_ai_result_stands(self):
        from inbox_scout.ai_classifier import classify_with_ai
        rule = {"category": "Junk", "manual_review": True, "risk_score": 75}
        ai = _ai_result(category="Junk", risk_score=10, manual_review=False)
        with patch("inbox_scout.ai_classifier.classify_with_provider", return_value=ai):
            result = classify_with_ai(_make_email(), rule)
        self.assertFalse(result["manual_review"])
        self.assertEqual(result["risk_score"], 10)

    def test_archive_candidate_ai_result_stands(self):
        from inbox_scout.ai_classifier import classify_with_ai
        rule = {"category": "Archive candidate", "manual_review": True, "risk_score": 70}
        ai = _ai_result(category="Archive candidate", risk_score=12, manual_review=False)
        with patch("inbox_scout.ai_classifier.classify_with_provider", return_value=ai):
            result = classify_with_ai(_make_email(), rule)
        self.assertFalse(result["manual_review"])
        self.assertEqual(result["risk_score"], 12)

    def test_empty_rule_category_ai_result_stands(self):
        from inbox_scout.ai_classifier import classify_with_ai
        rule = {"category": "", "manual_review": True, "risk_score": 70}
        ai = _ai_result(category="Newsletter", risk_score=20, manual_review=False)
        with patch("inbox_scout.ai_classifier.classify_with_provider", return_value=ai):
            result = classify_with_ai(_make_email(), rule)
        self.assertFalse(result["manual_review"])
        self.assertEqual(result["risk_score"], 20)


class TestProtectedPreserved(unittest.TestCase):
    def test_security_alert_preserved(self):
        from inbox_scout.ai_classifier import classify_with_ai
        rule = {"category": "Security alert", "manual_review": True, "risk_score": 90}
        ai = _ai_result(category="Newsletter", risk_score=10, manual_review=False)
        with patch("inbox_scout.ai_classifier.classify_with_provider", return_value=ai):
            result = classify_with_ai(_make_email(), rule)
        self.assertTrue(result["manual_review"])
        self.assertGreaterEqual(result["risk_score"], 90)

    def test_bills_receipts_preserved(self):
        from inbox_scout.ai_classifier import classify_with_ai
        rule = {"category": "Bills/receipts", "manual_review": True, "risk_score": 85}
        ai = _ai_result(category="Promotion", risk_score=15, manual_review=False)
        with patch("inbox_scout.ai_classifier.classify_with_provider", return_value=ai):
            result = classify_with_ai(_make_email(), rule)
        self.assertTrue(result["manual_review"])
        self.assertGreaterEqual(result["risk_score"], 85)

    def test_finance_preserved(self):
        from inbox_scout.ai_classifier import classify_with_ai
        rule = {"category": "Finance", "manual_review": True, "risk_score": 88}
        ai = _ai_result(category="Junk", risk_score=5, manual_review=False)
        with patch("inbox_scout.ai_classifier.classify_with_provider", return_value=ai):
            result = classify_with_ai(_make_email(), rule)
        self.assertTrue(result["manual_review"])
        self.assertGreaterEqual(result["risk_score"], 88)

    def test_legal_preserved(self):
        from inbox_scout.ai_classifier import classify_with_ai
        rule = {"category": "Legal", "manual_review": True, "risk_score": 95}
        ai = _ai_result(category="Archive candidate", risk_score=8, manual_review=False)
        with patch("inbox_scout.ai_classifier.classify_with_provider", return_value=ai):
            result = classify_with_ai(_make_email(), rule)
        self.assertTrue(result["manual_review"])
        self.assertGreaterEqual(result["risk_score"], 95)

    def test_medical_preserved(self):
        from inbox_scout.ai_classifier import classify_with_ai
        rule = {"category": "Medical", "manual_review": True, "risk_score": 92}
        ai = _ai_result(category="Newsletter", risk_score=5, manual_review=False)
        with patch("inbox_scout.ai_classifier.classify_with_provider", return_value=ai):
            result = classify_with_ai(_make_email(), rule)
        self.assertTrue(result["manual_review"])
        self.assertGreaterEqual(result["risk_score"], 92)

    def test_no_rule_manual_review_ai_result_stands(self):
        """No manual_review flag from rule — AI result always stands."""
        from inbox_scout.ai_classifier import classify_with_ai
        rule = {"category": "Finance", "manual_review": False, "risk_score": 88}
        ai = _ai_result(category="Junk", risk_score=5, manual_review=False)
        with patch("inbox_scout.ai_classifier.classify_with_provider", return_value=ai):
            result = classify_with_ai(_make_email(), rule)
        self.assertFalse(result["manual_review"])
        self.assertEqual(result["risk_score"], 5)


if __name__ == "__main__":
    unittest.main()
