"""
Test: "tracking" danger term false-positive fix.

Proves:
- "tracking your progress" (newsletter context) does NOT trigger protected danger signal
- "package tracking", "order tracking", "tracking number", "shipment tracking" still trigger
- roadmap.sh-style newsletter is no longer blocked by the tracking term

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_tracking_false_positive -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _item(**kw):
    base = {
        "queue_id": "24",
        "message_id": "msg24",
        "category": "Newsletter",
        "subject": "Level up your skills with roadmap.sh",
        "from": "Kamran Ahmed <roadmap@email.roadmap.sh>",
        "snippet": "tracking your progress is one of the most effective ways to stay committed.",
        "risk_score": 10,
        "manual_review": False,
        "local_decision": "pending_review",
        "gmail_action_type": "",
        "gmail_action_taken": False,
    }
    base.update(kw)
    return base


class TestTrackingFalsePositive(unittest.TestCase):

    def _danger(self, **kw):
        from inbox_scout.trash_candidate_plan import has_protected_danger_signal
        return has_protected_danger_signal(_item(**kw))

    def test_tracking_your_progress_not_blocked(self):
        # Bare "tracking" is gone — learning context is safe
        self.assertFalse(self._danger(
            snippet="tracking your progress is one of the most effective ways to learn."
        ))

    def test_roadmap_newsletter_not_blocked(self):
        # Exact ID 24 pattern — should no longer be a false positive
        self.assertFalse(self._danger(
            snippet="tracking your progress and sharing achievements with your road card."
        ))

    def test_package_tracking_still_blocked(self):
        self.assertTrue(self._danger(snippet="Your package tracking update is available."))

    def test_order_tracking_still_blocked(self):
        self.assertTrue(self._danger(snippet="Use order tracking to find your shipment."))

    def test_tracking_number_still_blocked(self):
        self.assertTrue(self._danger(snippet="Your tracking number is 1Z999AA10123456784."))

    def test_shipment_tracking_still_blocked(self):
        self.assertTrue(self._danger(snippet="Click here for shipment tracking details."))

    def test_is_safe_trash_candidate_accepts_newsletter_after_fix(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        ok, reason = is_safe_trash_candidate(_item(
            snippet="tracking your progress is one of the most effective ways to learn."
        ))
        self.assertTrue(ok, f"expected safe after fix; reason: {reason}")

    def test_is_safe_trash_candidate_still_blocks_package_tracking(self):
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        ok, _ = is_safe_trash_candidate(_item(
            category="Archive candidate",
            subject="Your package tracking update",
        ))
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
