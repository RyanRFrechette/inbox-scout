"""
Tests: Resort Mode Apply runner — safety gates and Gmail write order.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_resort_apply_runner -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_plan(mismatches=None, age_minutes=0, account="primary"):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=age_minutes)).isoformat()
    return {
        "created_at": ts,
        "account_scope": account,
        "confirmed": False,
        "plans": [{
            "account": account,
            "scanned": 2,
            "mismatches": mismatches or [],
            "skipped_protected": 0,
            "skipped_manual_review": 0,
            "skipped_high_risk": 0,
            "skipped_review_label": 0,
        }],
    }


def _mismatch(**overrides):
    base = {
        "message_id": "msg001",
        "subject": "Big Sale Today",
        "from": "promo@example.com",
        "current_label": "InboxScout/Finance",
        "recommended_label": "InboxScout/Promotions",
        "recommended_category": "Promotion",
        "risk_score": 10,
        "manual_review": False,
    }
    base.update(overrides)
    return base


def _mock_service(label_map: dict | None = None):
    svc = MagicMock()
    label_map = label_map or {
        "InboxScout/Finance": "Label_111",
        "InboxScout/Promotions": "Label_222",
    }
    svc.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        "labels": [{"name": n, "id": i} for n, i in label_map.items()]
    }
    svc.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}
    return svc


class TestValidateMismatch(unittest.TestCase):
    def setUp(self):
        from inbox_scout import resort_apply_runner
        self.v = resort_apply_runner._validate_mismatch

    def test_valid_passes(self):
        ok, reason = self.v(_mismatch())
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_manual_review_skipped(self):
        ok, reason = self.v(_mismatch(manual_review=True))
        self.assertFalse(ok)
        self.assertIn("manual_review", reason)

    def test_high_risk_skipped(self):
        ok, reason = self.v(_mismatch(risk_score=50))
        self.assertFalse(ok)
        self.assertIn("risk", reason)

    def test_risk_at_threshold_passes(self):
        ok, _ = self.v(_mismatch(risk_score=30))
        self.assertTrue(ok)

    def test_missing_message_id_skipped(self):
        ok, reason = self.v(_mismatch(message_id=""))
        self.assertFalse(ok)
        self.assertIn("message_id", reason)

    def test_non_inboxscout_current_label_skipped(self):
        ok, reason = self.v(_mismatch(current_label="INBOX"))
        self.assertFalse(ok)
        self.assertIn("InboxScout", reason)

    def test_non_inboxscout_recommended_label_skipped(self):
        ok, reason = self.v(_mismatch(recommended_label="Trash"))
        self.assertFalse(ok)
        self.assertIn("InboxScout", reason)

    def test_same_labels_skipped(self):
        ok, _ = self.v(_mismatch(
            current_label="InboxScout/Finance",
            recommended_label="InboxScout/Finance",
        ))
        self.assertFalse(ok)


class TestConfirmationGate(unittest.TestCase):
    def test_no_plan_file_blocks_apply(self):
        from inbox_scout import resort_apply_runner
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "no_plan.json"
            with patch.object(resort_apply_runner, "LATEST_RESORT_PLAN", fake_path):
                result = resort_apply_runner.build_resort_apply_message()
        self.assertIn("Gmail not touched", result)
        self.assertIn("resort", result.lower())

    def test_expired_plan_blocks_apply(self):
        from inbox_scout import resort_apply_runner
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "latest_resort_plan.json"
            plan_path.write_text(json.dumps(_make_plan(age_minutes=200)), encoding="utf-8")
            with patch.object(resort_apply_runner, "LATEST_RESORT_PLAN", plan_path):
                result = resort_apply_runner.build_resort_apply_message()
        self.assertIn("expired", result.lower())
        self.assertIn("Gmail not touched", result)

    def test_empty_mismatches_blocks_apply(self):
        from inbox_scout import resort_apply_runner
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "latest_resort_plan.json"
            plan_path.write_text(json.dumps(_make_plan(mismatches=[])), encoding="utf-8")
            with patch.object(resort_apply_runner, "LATEST_RESORT_PLAN", plan_path):
                result = resort_apply_runner.build_resort_apply_message()
        self.assertIn("Gmail not touched", result)


class TestLabelOrderAndSafety(unittest.TestCase):
    def _run(self, mismatches, label_map=None):
        from inbox_scout import resort_apply_runner
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "latest_resort_plan.json"
            plan_path.write_text(json.dumps(_make_plan(mismatches=mismatches)), encoding="utf-8")
            log_path = Path(tmpdir) / "resort_apply.jsonl"
            svc = _mock_service(label_map)
            with patch.object(resort_apply_runner, "LATEST_RESORT_PLAN", plan_path), \
                 patch.object(resort_apply_runner, "RESORT_APPLY_LOG", log_path), \
                 patch.object(resort_apply_runner, "_get_modify_service", return_value=svc):
                result = resort_apply_runner.build_resort_apply_message()
        return result, svc

    def test_new_label_applied_before_old_removed(self):
        result, svc = self._run([_mismatch()])
        modify_mock = svc.users.return_value.messages.return_value.modify
        self.assertEqual(modify_mock.call_count, 2)
        first_body = modify_mock.call_args_list[0][1]["body"]
        second_body = modify_mock.call_args_list[1][1]["body"]
        self.assertIn("addLabelIds", first_body)
        self.assertIn("removeLabelIds", second_body)

    def test_no_trash_calls(self):
        result, svc = self._run([_mismatch()])
        svc.users.return_value.messages.return_value.trash.assert_not_called()

    def test_no_delete_calls(self):
        result, svc = self._run([_mismatch()])
        svc.users.return_value.messages.return_value.delete.assert_not_called()

    def test_non_inboxscout_current_label_not_removed(self):
        result, svc = self._run([_mismatch(current_label="IMPORTANT")])
        modify_mock = svc.users.return_value.messages.return_value.modify
        modify_mock.assert_not_called()
        self.assertIn("Gmail not touched", result)

    def test_manual_review_skipped(self):
        result, svc = self._run([_mismatch(manual_review=True)])
        modify_mock = svc.users.return_value.messages.return_value.modify
        modify_mock.assert_not_called()
        self.assertIn("Gmail not touched", result)

    def test_successful_apply_reports_correction(self):
        result, _ = self._run([_mismatch()])
        self.assertIn("Applied 1", result)
        self.assertIn("Finance", result)
        self.assertIn("Promotions", result)

    def test_recommended_label_missing_in_gmail_blocks_that_item(self):
        result, svc = self._run(
            [_mismatch()],
            label_map={"InboxScout/Finance": "Label_111"},  # recommended missing
        )
        modify_mock = svc.users.return_value.messages.return_value.modify
        modify_mock.assert_not_called()
        self.assertIn("Gmail not touched", result)


class TestNaturalIntentRouting(unittest.TestCase):
    def _route(self, phrase):
        from inbox_scout.natural_intent import handle_natural_message
        return handle_natural_message(phrase)

    def test_confirm_resort_apply_routes_to_runner(self):
        from inbox_scout import resort_apply_runner
        with patch.object(resort_apply_runner, "build_resort_apply_message",
                          return_value="__apply_called__") as mock_fn:
            result = self._route("CONFIRM RESORT APPLY")
        mock_fn.assert_called_once()
        self.assertEqual(result, "__apply_called__")

    def test_apply_resort_fixes_routes_to_runner(self):
        from inbox_scout import resort_apply_runner
        with patch.object(resort_apply_runner, "build_resort_apply_message",
                          return_value="__apply_called__") as mock_fn:
            result = self._route("apply resort fixes")
        mock_fn.assert_called_once()

    def test_apply_resort_corrections_routes_to_runner(self):
        from inbox_scout import resort_apply_runner
        with patch.object(resort_apply_runner, "build_resort_apply_message",
                          return_value="__apply_called__") as mock_fn:
            result = self._route("apply resort corrections")
        mock_fn.assert_called_once()

    def test_resort_preview_does_not_route_to_apply(self):
        from inbox_scout import resort_apply_runner
        from inbox_scout import resort_mode
        with patch.object(resort_apply_runner, "build_resort_apply_message",
                          return_value="WRONG") as apply_mock, \
             patch.object(resort_mode, "build_resort_preview_message",
                          return_value="preview_result"):
            result = self._route("resort preview")
        apply_mock.assert_not_called()
        self.assertEqual(result, "preview_result")


if __name__ == "__main__":
    unittest.main()
