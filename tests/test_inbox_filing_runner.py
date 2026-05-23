"""
Tests for Inbox Filing Mode v1A preview.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_inbox_filing_runner -v
"""
from __future__ import annotations

import json
import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_scout.inbox_filing_runner import build_filing_preview, _bucket, _load_queue

_SAFE_CATS = ["newsletter", "newsletters", "promotion", "promotions",
               "social_notification", "social_notifications"]

_UNTOUCHED_CATS = ["finance", "security", "medical", "legal", "job", "jobs",
                    "account", "accounts", "bills/receipts", "receipts",
                    "refund", "warranty", "client/business"]


def _item(category="newsletter", risk=10, manual=False, protected=False, decision="keep"):
    return {
        "category": category,
        "risk_score": risk,
        "manual_review": manual,
        "protected": protected,
        "local_decision": decision,
        "subject": "Weekly digest",
    }


class TestBucket(unittest.TestCase):
    def test_newsletter_safe_filing(self):
        self.assertEqual(_bucket(_item("newsletter", 10)), "safe_filing")

    def test_promotion_safe_filing(self):
        self.assertEqual(_bucket(_item("promotion", 30)), "safe_filing")

    def test_social_notification_safe_filing(self):
        self.assertEqual(_bucket(_item("social_notification", 0)), "safe_filing")

    def test_high_risk_untouched(self):
        self.assertEqual(_bucket(_item("newsletter", 41)), "untouched")

    def test_manual_review_untouched(self):
        self.assertEqual(_bucket(_item("newsletter", 5, manual=True)), "untouched")

    def test_protected_flag_untouched(self):
        self.assertEqual(_bucket(_item("newsletter", 5, protected=True)), "untouched")

    def test_protected_decision_untouched(self):
        self.assertEqual(_bucket(_item("newsletter", 5, decision="protected_review")), "untouched")

    def test_finance_untouched(self):
        self.assertEqual(_bucket(_item("finance", 10)), "untouched")

    def test_security_untouched(self):
        self.assertEqual(_bucket(_item("security", 10)), "untouched")

    def test_medical_untouched(self):
        self.assertEqual(_bucket(_item("medical", 10)), "untouched")

    def test_legal_untouched(self):
        self.assertEqual(_bucket(_item("legal", 10)), "untouched")

    def test_jobs_untouched(self):
        self.assertEqual(_bucket(_item("jobs", 10)), "untouched")

    def test_accounts_untouched(self):
        self.assertEqual(_bucket(_item("accounts", 10)), "untouched")

    def test_receipts_untouched(self):
        self.assertEqual(_bucket(_item("bills/receipts", 10)), "untouched")

    def test_refunds_untouched(self):
        self.assertEqual(_bucket(_item("refund", 10)), "untouched")

    def test_warranty_untouched(self):
        self.assertEqual(_bucket(_item("warranty", 10)), "untouched")

    def test_shopping_history_soft_label_only(self):
        soft_item = {
            "category": "bills/receipts",
            "risk_score": 10,
            "manual_review": False,
            "protected": False,
            "local_decision": "keep",
            "subject": "Shipped: your order",
            "snippet": "your package is on the way",
        }
        self.assertEqual(_bucket(soft_item), "label_only")


class TestPreviewOutput(unittest.TestCase):
    def _preview_with_items(self, items):
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=items):
            return build_filing_preview()

    def test_no_queue_safe_message(self):
        result = self._preview_with_items([])
        self.assertIn("sort all", result.lower())
        self.assertNotIn("Gmail changes", result)

    def test_output_contains_header(self):
        result = self._preview_with_items([_item("newsletter", 10)])
        self.assertIn("Inbox Filing Mode preview", result)

    def test_output_no_gmail_changes_yet(self):
        result = self._preview_with_items([_item("newsletter", 10)])
        self.assertIn("No Gmail changes yet.", result)

    def test_apply_mode_not_implemented(self):
        result = self._preview_with_items([_item("newsletter", 10)])
        self.assertIn("Apply mode is not implemented yet.", result)

    def test_no_subject_in_output(self):
        item = _item("newsletter", 10)
        item["subject"] = "SECRET SUBJECT LINE"
        result = self._preview_with_items([item])
        self.assertNotIn("SECRET SUBJECT LINE", result)

    def test_no_sender_in_output(self):
        item = _item("newsletter", 10)
        item["from"] = "secret@sender.com"
        result = self._preview_with_items([item])
        self.assertNotIn("secret@sender.com", result)

    def test_no_snippet_in_output(self):
        item = _item("newsletter", 10)
        item["snippet"] = "private snippet text"
        result = self._preview_with_items([item])
        self.assertNotIn("private snippet text", result)

    def test_no_message_id_in_output(self):
        item = _item("newsletter", 10)
        item["message_id"] = "19e4a5d97e92530f"
        result = self._preview_with_items([item])
        self.assertNotIn("19e4a5d97e92530f", result)

    def test_counts_correct(self):
        items = [
            _item("newsletter", 10),
            _item("promotion", 20),
            _item("finance", 10),
            _item("newsletter", 5, manual=True),
        ]
        result = self._preview_with_items(items)
        self.assertIn("Safe to label + archive + mark read: 2", result)
        self.assertIn("Untouched", result)

    def test_label_only_count(self):
        soft = {
            "category": "bills/receipts", "risk_score": 10, "manual_review": False,
            "protected": False, "local_decision": "keep",
            "subject": "Shipped: your order", "snippet": "package on the way",
        }
        result = self._preview_with_items([soft])
        self.assertIn("Label only (shopping history soft): 1", result)


class TestNaturalIntentRouting(unittest.TestCase):
    def _route(self, phrase):
        from inbox_scout import natural_intent
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=[]):
            return natural_intent.handle_natural_message(phrase)

    def test_file_inbox_routes_to_preview(self):
        result = self._route("file inbox")
        self.assertIn("Inbox Filing Mode", result)

    def test_file_safe_emails_routes_to_preview(self):
        result = self._route("file safe emails")
        self.assertIn("Inbox Filing Mode", result)

    def test_preview_filing_routes_to_preview(self):
        result = self._route("preview filing")
        self.assertIn("Inbox Filing Mode", result)

    def test_no_autopilot_confirm_in_filing(self):
        result = self._route("file inbox")
        self.assertNotIn("CONFIRM INBOX AUTOPILOT", result)

    def test_no_trash_language_in_filing(self):
        result = self._route("file inbox")
        self.assertNotIn("trash", result.lower())


class TestFilingApplyGuard(unittest.TestCase):
    _STUB = "Inbox Filing Apply Mode is not implemented yet."
    _AUTOPILOT = "CONFIRM INBOX AUTOPILOT"

    def _route(self, phrase):
        from inbox_scout import natural_intent
        with patch("inbox_scout.natural_intent._llm_fallback", return_value="LLM_CALLED") as mock_llm:
            result = natural_intent.handle_natural_message(phrase)
            self._mock_llm = mock_llm
        return result

    def test_apply_filing_returns_stub(self):
        self.assertIn(self._STUB, self._route("apply filing"))

    def test_confirm_filing_returns_stub(self):
        self.assertIn(self._STUB, self._route("confirm filing"))

    def test_run_filing_returns_stub(self):
        self.assertIn(self._STUB, self._route("run filing"))

    def test_apply_filing_not_autopilot(self):
        self.assertNotIn(self._AUTOPILOT, self._route("apply filing"))

    def test_confirm_filing_not_autopilot(self):
        self.assertNotIn(self._AUTOPILOT, self._route("confirm filing"))

    def test_apply_filing_not_llm_fallback(self):
        from inbox_scout import natural_intent
        with patch("inbox_scout.natural_intent._llm_fallback", return_value="LLM_CALLED") as mock_llm:
            natural_intent.handle_natural_message("apply filing")
        mock_llm.assert_not_called()

    def test_file_inbox_preview_still_works(self):
        from inbox_scout import natural_intent
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=[]):
            result = natural_intent.handle_natural_message("file inbox")
        self.assertIn("Inbox Filing Mode preview", result)

    def test_sort_all_unaffected(self):
        from inbox_scout import natural_intent
        with patch.object(natural_intent, "_inbox_zero_preview_prompt", return_value="INBOX_ZERO"):
            result = natural_intent.handle_natural_message("sort all")
        self.assertNotIn(self._STUB, result)


if __name__ == "__main__":
    unittest.main()
