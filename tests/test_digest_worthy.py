"""
Test: digest-worthiness filtering for routine shopping confirmations.

Proves: routine order/receipt emails are suppressed from digest while
problem-signal emails, unknown manual-review items, and important categories
remain visible.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_digest_worthy -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _item(**kw):
    base = {
        "queue_id": "1",
        "category": "Bills/receipts",
        "from": "auto-confirm@amazon.com",
        "subject": 'Ordered: "Amazon Basics 5000-BTU Air Conditioner"',
        "snippet": "Order #123-456-789 has been placed.",
        "manual_review": True,
        "local_decision": "pending_review",
    }
    base.update(kw)
    return base


class TestDigestWorthy(unittest.TestCase):

    def test_amazon_order_confirmation_not_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = _item()
        self.assertFalse(_is_digest_worthy(item))

    def test_bills_receipts_no_problem_not_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = _item(**{"from": "noreply@shop.com", "subject": "Your purchase confirmation"})
        self.assertFalse(_is_digest_worthy(item))

    def test_archive_candidate_order_not_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = _item(category="Archive candidate", subject="Your order has been delivered")
        self.assertFalse(_is_digest_worthy(item))

    def test_amazon_order_with_payment_issue_is_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = _item(subject="Your order: payment issue — please update payment")
        self.assertTrue(_is_digest_worthy(item))

    def test_amazon_refund_is_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = _item(subject="Refund processed for your recent order")
        self.assertTrue(_is_digest_worthy(item))

    def test_amazon_failed_payment_is_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = _item(subject="Your Amazon order — payment failed")
        self.assertTrue(_is_digest_worthy(item))

    def test_amazon_dispute_is_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = _item(snippet="A dispute has been opened on order #123")
        self.assertTrue(_is_digest_worthy(item))

    def test_unknown_manual_review_is_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = {
            "category": "Manual review",
            "from": "someone@example.com",
            "subject": "We need to talk",
            "snippet": "",
            "manual_review": True,
            "local_decision": "pending_review",
        }
        self.assertTrue(_is_digest_worthy(item))

    def test_job_career_manual_review_is_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = {
            "category": "Job/career",
            "from": "hr@company.com",
            "subject": "Your application has been reviewed",
            "snippet": "We'd like to schedule an interview.",
            "manual_review": True,
            "local_decision": "pending_review",
        }
        self.assertTrue(_is_digest_worthy(item))

    def test_security_alert_is_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = {
            "category": "Security alert",
            "from": "security@google.com",
            "subject": "New sign-in to your account",
            "snippet": "A new device signed in from an unknown location.",
            "manual_review": True,
            "local_decision": "pending_review",
        }
        self.assertTrue(_is_digest_worthy(item))

    def test_amazon_fraud_alert_is_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = _item(subject="Fraud alert on your Amazon account")
        self.assertTrue(_is_digest_worthy(item))

    def test_amazon_suspicious_activity_is_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = _item(snippet="We detected suspicious activity on your account.")
        self.assertTrue(_is_digest_worthy(item))

    def test_protected_review_non_shopping_is_digest_worthy(self):
        from inbox_scout.autopilot_cleanup import _is_digest_worthy
        item = {
            "category": "Finance",
            "from": "statements@bank.com",
            "subject": "Your monthly statement is ready",
            "snippet": "",
            "manual_review": False,
            "local_decision": "protected_review",
        }
        self.assertTrue(_is_digest_worthy(item))


if __name__ == "__main__":
    unittest.main()
