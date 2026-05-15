"""
Focused safety tests for mark-read candidate selection.

Proves:
- Safe reviewed emails are eligible
- manual_review/protected emails are excluded
- Financial, billing, receipt, compound-category emails are excluded
- No mark-read happens without explicit apply=True

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m pytest tests/test_mark_read_safety.py -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_scout.mark_read_runner import (
    build_mark_read_plan_message,
    build_mark_read_runner_message,
    evaluate_mark_read_candidate,
    is_explicitly_reviewed,
)


def _item(**overrides):
    base = {
        "queue_id": "q1",
        "subject": "April newsletter",
        "category": "Newsletter",
        "risk_score": 20,
        "manual_review": False,
        "protected": False,
        "local_decision": "keep",
        "gmail_message_id": "msg001",
        "gmail_marked_read": False,
    }
    return {**base, **overrides}


def _with_queue(items, fn, *args, **kwargs):
    import inbox_scout.mark_read_runner as mrr
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(items, f)
        tmp = f.name
    orig = mrr.QUEUE_PATH
    mrr.QUEUE_PATH = Path(tmp)
    try:
        return fn(*args, **kwargs)
    finally:
        mrr.QUEUE_PATH = orig
        os.unlink(tmp)


class TestEligibility(unittest.TestCase):
    def test_keep_decision_eligible(self):
        ok, reason = evaluate_mark_read_candidate(_item(local_decision="keep"))
        self.assertTrue(ok, reason)

    def test_ignore_decision_eligible(self):
        ok, reason = evaluate_mark_read_candidate(_item(local_decision="ignore"))
        self.assertTrue(ok, reason)

    def test_possible_archive_later_eligible(self):
        ok, reason = evaluate_mark_read_candidate(_item(local_decision="possible_archive_later"))
        self.assertTrue(ok, reason)

    def test_already_trashed_eligible(self):
        ok, reason = evaluate_mark_read_candidate(_item(local_decision="pending_review", gmail_action_type="trashed"))
        self.assertTrue(ok, reason)

    def test_already_archived_eligible(self):
        ok, reason = evaluate_mark_read_candidate(_item(local_decision="pending_review", gmail_action_type="archived"))
        self.assertTrue(ok, reason)

    def test_pending_review_excluded(self):
        ok, reason = evaluate_mark_read_candidate(_item(local_decision="pending_review"))
        self.assertFalse(ok)
        self.assertIn("pending review", reason)

    def test_review_later_excluded(self):
        ok, reason = evaluate_mark_read_candidate(_item(local_decision="review_later"))
        self.assertFalse(ok)
        self.assertIn("review later", reason)

    def test_manual_review_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(manual_review=True))
        self.assertFalse(ok)

    def test_protected_flag_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(protected=True))
        self.assertFalse(ok)

    def test_high_risk_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(risk_score=41))
        self.assertFalse(ok)

    def test_risk_boundary_40_eligible(self):
        ok, _ = evaluate_mark_read_candidate(_item(risk_score=40))
        self.assertTrue(ok)

    def test_already_marked_read_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(gmail_marked_read=True))
        self.assertFalse(ok)

    def test_missing_message_id_excluded(self):
        item = _item()
        del item["gmail_message_id"]
        ok, _ = evaluate_mark_read_candidate(item)
        self.assertFalse(ok)


class TestProtectedCategories(unittest.TestCase):
    def test_finance_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(category="Finance"))
        self.assertFalse(ok)

    def test_bills_receipts_compound_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(category="Bills/receipts"))
        self.assertFalse(ok)

    def test_job_career_compound_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(category="Job/career"))
        self.assertFalse(ok)

    def test_client_business_compound_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(category="Client/business"))
        self.assertFalse(ok)

    def test_security_alert_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(category="Security alert"))
        self.assertFalse(ok)

    def test_legal_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(category="Legal"))
        self.assertFalse(ok)

    def test_medical_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(category="Medical"))
        self.assertFalse(ok)

    def test_personal_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(category="Personal"))
        self.assertFalse(ok)

    def test_warranty_support_compound_excluded(self):
        ok, _ = evaluate_mark_read_candidate(_item(category="Warranty/support"))
        self.assertFalse(ok)


class TestNoMarkReadWithoutApproval(unittest.TestCase):
    def test_plan_shows_preview_no_gmail_changes(self):
        result = _with_queue([_item()], build_mark_read_plan_message)
        self.assertIn("mark-read plan", result.lower())
        self.assertIn("no gmail changes", result.lower())

    def test_plan_counts_eligible_correctly(self):
        items = [
            _item(queue_id="q1", local_decision="keep"),
            _item(queue_id="q2", manual_review=True),
            _item(queue_id="q3", local_decision="pending_review"),
        ]
        result = _with_queue(items, build_mark_read_plan_message)
        self.assertIn("1 eligible", result.lower())
        self.assertIn("skipped", result.lower())

    def test_dry_run_does_not_call_gmail(self):
        with patch("inbox_scout.mark_read_runner.get_modify_service") as mock_svc:
            result = _with_queue([_item()], build_mark_read_runner_message, apply=False)
        mock_svc.assert_not_called()
        self.assertIn("dry run", result.lower())

    def test_no_eligible_items_no_gmail_call(self):
        protected_item = _item(manual_review=True)
        with patch("inbox_scout.mark_read_runner.get_modify_service") as mock_svc:
            result = _with_queue([protected_item], build_mark_read_runner_message, apply=True)
        mock_svc.assert_not_called()
        self.assertIn("gmail not touched", result.lower())

    def test_all_protected_items_no_gmail_call(self):
        items = [
            _item(category="Finance"),
            _item(category="Bills/receipts"),
            _item(manual_review=True),
        ]
        with patch("inbox_scout.mark_read_runner.get_modify_service") as mock_svc:
            result = _with_queue(items, build_mark_read_runner_message, apply=True)
        mock_svc.assert_not_called()
        self.assertIn("gmail not touched", result.lower())


if __name__ == "__main__":
    unittest.main()
