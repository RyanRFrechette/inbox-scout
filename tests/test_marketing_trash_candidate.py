"""
Test: marketing-signal trash candidate detection.

Proves: Personal/Archive-candidate emails with strong marketing signals and no
danger signals become safe trash candidates. Receipt/order/shipping/security
emails never qualify regardless of marketing words present.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_marketing_trash_candidate -v
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
        "category": "Personal",
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


class TestMarketingTrashCandidate(unittest.TestCase):

    def test_personal_cart_promo_is_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Personal", subject="Still looking? Your cart is waiting — 20% off")
        ok, reason = is_safe_trash_candidate(item)
        self.assertTrue(ok, f"expected safe; reason: {reason}")

    def test_archive_candidate_free_shipping_sale_is_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Archive candidate", subject="Free shipping sale this weekend!")
        ok, reason = is_safe_trash_candidate(item)
        self.assertTrue(ok, f"expected safe; reason: {reason}")

    def test_archive_candidate_shipped_is_not_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Archive candidate", subject="Shipped: Your Lenovo Legion order")
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_archive_candidate_delivered_is_not_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Archive candidate", subject="Delivered: TACNEX Elastic Belt")
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_archive_candidate_tracking_is_not_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Archive candidate", subject="Your package tracking update")
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_security_recovery_email_is_not_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Personal", subject="Verification code: 12345 to login")
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_receipt_email_is_not_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Personal", subject="Your receipt from Anthropic, PBC")
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_order_confirmation_is_not_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Archive candidate", subject="Order confirmation: TACNEX Belt")
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_newsletter_tips_remains_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Newsletter", subject="Tips to get the most out of Claude Code")
        ok, reason = is_safe_trash_candidate(item)
        self.assertTrue(ok, f"expected safe; reason: {reason}")

    def test_newsletter_daily_digest_remains_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Newsletter", subject="Your daily digest — Friday")
        ok, _ = is_safe_trash_candidate(item)
        self.assertTrue(ok)

    def test_newsletter_with_danger_signal_blocked(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Newsletter", subject="Your payment is overdue")
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_personal_no_marketing_signal_not_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Personal", subject="Hey buddy, how's it going")
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_junk_low_risk_is_safe(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Junk", subject="Win a free iPhone now!!!")
        ok, reason = is_safe_trash_candidate(item)
        self.assertTrue(ok, f"expected safe; reason: {reason}")

    def test_junk_with_danger_signal_blocked(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Junk", subject="Your password reset link")
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_junk_manual_review_blocked(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Junk", subject="Spam-ish email", manual_review=True)
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_junk_high_risk_blocked(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Junk", subject="Click here now", risk_score=50)
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_archive_candidate_not_trash_safe_without_marketing(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = _item(category="Archive candidate", subject="Just an email to archive", risk_score=20)
        ok, _ = is_safe_trash_candidate(item)
        self.assertFalse(ok)

    def test_runner_validate_accepts_marketing_rescue(self):
        # Confirms the runner's validate_candidate also honors the rescue path.
        from inbox_scout.inbox_cleanup_runner import validate_candidate
        item = _item(
            queue_id="42",
            message_id="msg42",
            category="Archive candidate",
            subject="Free shipping sale this weekend!",
        )
        ok, reason = validate_candidate({"queue_id": "42"}, [item])
        self.assertTrue(ok, f"runner expected accept; reason: {reason}")

    def test_runner_validate_blocks_shipping_confirmation(self):
        # Confirms the runner blocks shipping confirmations even with Archive candidate label.
        from inbox_scout.inbox_cleanup_runner import validate_candidate
        item = _item(
            queue_id="43",
            message_id="msg43",
            category="Archive candidate",
            subject="Shipped: Your Lenovo Legion order",
        )
        ok, reason = validate_candidate({"queue_id": "43"}, [item])
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
