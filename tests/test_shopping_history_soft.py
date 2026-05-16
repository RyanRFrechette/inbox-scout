"""
Test: shopping_history_soft bucket detection and audit visibility.

Proves:
- Shipped/delivered retail emails with no danger signal become shopping_history_soft
- Receipt/refund/dropoff/security emails are NOT shopping_history_soft
- Ordered emails are NOT shopping_history_soft (excluded by subject prefix rule)
- audit_item returns the soft bucket and correct reason code
- Age gate deferred — no fake date logic

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_shopping_history_soft -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _item(**kw):
    base = {
        "queue_id": "1",
        "message_id": "msg1",
        "category": "Bills/receipts",
        "subject": "Shipped: Your order from Amazon",
        "from": "shipment-tracking@amazon.com",
        "snippet": "Your package is on its way. Track your shipment.",
        "risk_score": 30,
        "manual_review": True,
        "local_decision": "protected_review",
        "gmail_action_type": "",
        "gmail_action_taken": False,
    }
    base.update(kw)
    return base


class TestIsShoppingHistorySoft(unittest.TestCase):

    def _soft(self, **kw):
        from inbox_scout.trash_candidate_plan import is_shopping_history_soft
        return is_shopping_history_soft(_item(**kw))

    # --- Eligible: Shipped ---

    def test_shipped_retail_no_danger_is_soft(self):
        self.assertTrue(self._soft(subject="Shipped: Your order from Amazon"))

    def test_shipped_lowercase_prefix_is_soft(self):
        self.assertTrue(self._soft(subject="shipped: Nirovien Womens Hoodies"))

    # --- Eligible: Delivered ---

    def test_delivered_retail_no_danger_is_soft(self):
        self.assertTrue(self._soft(subject="Delivered: Beast Claws Meat Shredder"))

    def test_delivered_mixed_case_prefix_is_soft(self):
        self.assertTrue(self._soft(subject="Delivered: TACNEX Elastic Belt/Strap"))

    # --- Not eligible: wrong subject prefix ---

    def test_ordered_is_not_soft(self):
        self.assertFalse(self._soft(subject='Ordered: "Anime Baseball Cap Canvas..."'))

    def test_plain_purchase_subject_is_not_soft(self):
        self.assertFalse(self._soft(subject="Your Amazon order has been placed"))

    # --- Not eligible: wrong category ---

    def test_security_alert_category_is_not_soft(self):
        self.assertFalse(self._soft(
            category="Security alert",
            subject="Shipped: New device login detected",
        ))

    def test_newsletter_category_is_not_soft(self):
        self.assertFalse(self._soft(
            category="Newsletter",
            subject="Shipped: your weekly digest",
        ))

    # --- Not eligible: danger signal present ---

    def test_shipped_with_refund_in_snippet_is_not_soft(self):
        self.assertFalse(self._soft(
            subject="Shipped: Your return",
            snippet="Your refund has been initiated.",
        ))

    def test_delivered_with_payment_in_snippet_is_not_soft(self):
        self.assertFalse(self._soft(
            subject="Delivered: Your Lenovo Legion",
            snippet="Payment of $1,299.99 was charged.",
        ))

    def test_shipped_with_dropoff_in_subject_is_not_soft(self):
        self.assertFalse(self._soft(subject="Shipped: dropoff confirmed for your return"))

    def test_shipped_with_return_in_subject_is_not_soft(self):
        self.assertFalse(self._soft(subject="Shipped: return label for your order"))

    def test_receipt_subject_is_not_soft(self):
        self.assertFalse(self._soft(
            subject="Your receipt from Anthropic, PBC",
            snippet="Thank you for your payment.",
        ))

    def test_security_login_snippet_is_not_soft(self):
        self.assertFalse(self._soft(
            subject="Shipped: Lenovo Legion",
            snippet="Login to your account to track your order securely.",
        ))


class TestAuditItemShoppingHistorySoft(unittest.TestCase):

    def _audit(self, **kw):
        from inbox_scout.queue_audit import audit_item
        return audit_item(_item(**kw))

    def test_eligible_shipped_item_shows_soft_bucket(self):
        bucket, code, human = self._audit(subject="Shipped: Your order from Amazon")
        self.assertEqual(bucket, "shopping_history_soft")
        self.assertEqual(code, "soft_shopping_history")
        self.assertIn("Not auto-handled", human)

    def test_eligible_delivered_item_shows_soft_bucket(self):
        bucket, code, _ = self._audit(subject="Delivered: Beast Claws Meat Shredder")
        self.assertEqual(bucket, "shopping_history_soft")
        self.assertEqual(code, "soft_shopping_history")

    def test_receipt_email_shows_protected_not_soft(self):
        bucket, code, _ = self._audit(
            subject="Your receipt from Anthropic, PBC",
            snippet="Thank you for your payment.",
        )
        self.assertNotEqual(bucket, "shopping_history_soft")
        self.assertEqual(bucket, "protected")

    def test_shipped_with_refund_shows_protected_not_soft(self):
        bucket, _, _ = self._audit(
            subject="Shipped: Your return",
            snippet="Refund of $49.99 has been issued.",
        )
        self.assertNotEqual(bucket, "shopping_history_soft")

    def test_ordered_item_shows_protected_not_soft(self):
        bucket, _, _ = self._audit(subject='Ordered: "Anime Baseball Cap Canvas..."')
        self.assertNotEqual(bucket, "shopping_history_soft")
        self.assertEqual(bucket, "protected")


if __name__ == "__main__":
    unittest.main()
