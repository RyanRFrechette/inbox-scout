"""
Test: queue_audit reason codes are correct for key email types.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_queue_audit -v
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
        "category": "Newsletter",
        "subject": "",
        "from": "ads@example.com",
        "snippet": "",
        "risk_score": 10,
        "manual_review": False,
        "local_decision": "pending_review",
        "gmail_action_type": "",
        "gmail_action_taken": False,
    }
    base.update(kw)
    return base


class TestAuditItemReasonCodes(unittest.TestCase):

    def _audit(self, **kw):
        from inbox_scout.queue_audit import audit_item
        return audit_item(_item(**kw))

    def test_already_handled(self):
        bucket, code, _ = self._audit(gmail_action_taken=True)
        self.assertEqual(bucket, "handled")
        self.assertEqual(code, "already_handled")

    def test_manual_review_security(self):
        bucket, code, _ = self._audit(category="Security alert", manual_review=True, risk_score=80)
        self.assertEqual(bucket, "protected")
        self.assertEqual(code, "protected_security_login")

    def test_manual_review_job_career(self):
        bucket, code, _ = self._audit(category="Job/career", manual_review=True, risk_score=70)
        self.assertEqual(bucket, "protected")
        self.assertEqual(code, "protected_job_career")

    def test_protected_category_finance(self):
        bucket, code, _ = self._audit(category="Finance", manual_review=False, risk_score=60)
        self.assertEqual(bucket, "protected")
        self.assertEqual(code, "protected_finance")

    def test_protected_category_client_business(self):
        bucket, code, _ = self._audit(category="Client/business", manual_review=False, risk_score=50)
        self.assertEqual(bucket, "protected")
        self.assertEqual(code, "protected_client_business")

    def test_protected_high_risk(self):
        bucket, code, _ = self._audit(category="Personal", manual_review=False, risk_score=72)
        self.assertEqual(bucket, "protected")
        self.assertEqual(code, "protected_high_risk")

    def test_unclear_high_risk_mid_range(self):
        # risk 50: above MAX_TRASH_RISK(30), below 70 — unclear
        bucket, code, _ = self._audit(category="Newsletter", manual_review=False, risk_score=50)
        self.assertEqual(bucket, "unclear")
        self.assertEqual(code, "unclear_high_risk")

    def test_unclear_ineligible_category(self):
        bucket, code, _ = self._audit(category="Important", manual_review=False, risk_score=10)
        self.assertEqual(bucket, "unclear")
        self.assertEqual(code, "unclear_ineligible_category")

    def test_trash_candidate_newsletter(self):
        bucket, code, _ = self._audit(category="Newsletter", risk_score=10)
        self.assertEqual(bucket, "trash_candidate")
        self.assertEqual(code, "trash_candidate_newsletter_promotion")

    def test_trash_candidate_promotion(self):
        bucket, code, _ = self._audit(category="Promotion", risk_score=15)
        self.assertEqual(bucket, "trash_candidate")
        self.assertEqual(code, "trash_candidate_newsletter_promotion")

    def test_trash_candidate_marketing_rescue(self):
        bucket, code, _ = self._audit(
            category="Personal",
            subject="Still looking? Your cart is waiting — 20% off",
            risk_score=10,
        )
        self.assertEqual(bucket, "trash_candidate")
        self.assertEqual(code, "trash_candidate_marketing_rescue")

    def test_unclear_no_marketing_signal(self):
        bucket, code, _ = self._audit(
            category="Personal",
            subject="Hey buddy, how's it going",
            risk_score=10,
        )
        self.assertEqual(bucket, "unclear")
        self.assertEqual(code, "unclear_no_strong_marketing_signal")

    def test_blocked_by_security_danger_signal(self):
        bucket, code, human = self._audit(
            category="Newsletter",
            subject="Verification code: 12345 to login",
            risk_score=10,
        )
        self.assertEqual(bucket, "unclear")
        self.assertEqual(code, "marketing_rescue_blocked_by_danger_signal")
        self.assertIn("Security danger", human)

    def test_blocked_by_shipping_danger_signal(self):
        bucket, code, human = self._audit(
            category="Archive candidate",
            subject="Shipped: Your Lenovo Legion order",
            risk_score=10,
        )
        self.assertEqual(bucket, "unclear")
        self.assertEqual(code, "marketing_rescue_blocked_by_danger_signal")
        self.assertIn("Shipping danger", human)

    def test_blocked_by_receipt_danger_signal(self):
        bucket, code, human = self._audit(
            category="Personal",
            subject="Your receipt from Anthropic, PBC",
            risk_score=10,
        )
        self.assertEqual(bucket, "unclear")
        self.assertEqual(code, "marketing_rescue_blocked_by_danger_signal")
        self.assertIn("Receipt danger", human)

    def test_build_audit_rows_returns_correct_shape(self):
        from inbox_scout.queue_audit import build_audit_rows
        items = [
            _item(queue_id="1", category="Newsletter", risk_score=10),
            _item(queue_id="2", category="Finance", risk_score=60, manual_review=False),
        ]
        rows = build_audit_rows(items)
        self.assertEqual(len(rows), 2)
        self.assertIn("bucket", rows[0])
        self.assertIn("reason_code", rows[0])
        self.assertIn("human_reason", rows[0])
        self.assertEqual(rows[0]["bucket"], "trash_candidate")
        self.assertEqual(rows[1]["bucket"], "protected")


if __name__ == "__main__":
    unittest.main()
