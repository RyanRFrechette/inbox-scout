"""Tests: account metadata stamped on queue items (Phase 4D-A)."""
from __future__ import annotations
import unittest


def _results(n=2):
    return [
        {"message_id": f"msg{i}", "subject": f"s{i}", "from": "", "date": "",
         "snippet": "", "ai_classification": {"category": "newsletter", "risk_score": 10,
         "confidence_score": 0.9, "manual_review": False, "suggested_action": "", "reason": ""}}
        for i in range(n)
    ]


class TestBuildQueueItemsAccountStamp(unittest.TestCase):

    def test_primary_account_stamped(self):
        from inbox_scout.review_queue import build_queue_items
        items = build_queue_items(_results(), account="primary")
        for item in items:
            self.assertEqual(item["account"], "primary")

    def test_secondary_account_stamped(self):
        from inbox_scout.review_queue import build_queue_items
        items = build_queue_items(_results(), account="secondary")
        for item in items:
            self.assertEqual(item["account"], "secondary")

    def test_no_account_arg_omits_field(self):
        from inbox_scout.review_queue import build_queue_items
        items = build_queue_items(_results())
        for item in items:
            self.assertNotIn("account", item)

    def test_invalid_account_omits_field(self):
        from inbox_scout.review_queue import build_queue_items
        items = build_queue_items(_results(), account="bogus")
        for item in items:
            self.assertNotIn("account", item)

    def test_none_account_omits_field(self):
        from inbox_scout.review_queue import build_queue_items
        items = build_queue_items(_results(), account=None)
        for item in items:
            self.assertNotIn("account", item)


class TestSortScanQueueRunnerPassesAccount(unittest.TestCase):

    def test_account_passed_to_queue_args(self):
        import subprocess, sys
        from unittest.mock import patch, MagicMock
        import argparse

        captured = {}

        def fake_run(cmd, **kwargs):
            if "review_queue" in " ".join(cmd):
                captured["queue_cmd"] = cmd
            r = MagicMock()
            r.returncode = 0
            r.stdout = ""
            r.stderr = ""
            return r

        valid_plan = {
            "workflow_mode": "commands_planned",
            "target": "unread_inbox",
            "requested_limit": 5,
        }
        with patch("inbox_scout.sort_scan_queue_runner.run_command", side_effect=fake_run), \
             patch("inbox_scout.sort_scan_queue_runner.load_latest_plan", return_value=valid_plan), \
             patch("inbox_scout.sort_scan_queue_runner.save_result"), \
             patch("inbox_scout.sort_scan_queue_runner.build_result", return_value=MagicMock()), \
             patch("inbox_scout.sort_scan_queue_runner.asdict", return_value={}), \
             patch("builtins.print"), \
             patch("sys.argv", ["prog", "--run", "--account", "secondary"]):
            from inbox_scout import sort_scan_queue_runner
            sort_scan_queue_runner.main()

        self.assertIn("--account", captured.get("queue_cmd", []))
        idx = captured["queue_cmd"].index("--account")
        self.assertEqual(captured["queue_cmd"][idx + 1], "secondary")


class TestApplyFilingWordingFix(unittest.TestCase):

    def _run(self, items, account="primary"):
        from unittest.mock import patch
        from inbox_scout.inbox_filing_runner import apply_filing
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=items), \
             patch("inbox_scout.inbox_filing_runner._log_filing_action"):
            return apply_filing(account)

    def test_missing_account_wording(self):
        items = [{"queue_id": "q1", "message_id": "m1", "category": "newsletter",
                  "risk_score": 10, "protected": False, "manual_review": False}]
        result = self._run(items)
        self.assertIn("Skipped missing/unknown account: 1", result)
        self.assertIn("Skipped account mismatch: 0", result)

    def test_account_mismatch_wording(self):
        items = [{"queue_id": "q2", "message_id": "m2", "category": "newsletter",
                  "risk_score": 10, "protected": False, "manual_review": False,
                  "account": "secondary"}]
        result = self._run(items, account="primary")
        self.assertIn("Skipped account mismatch: 1", result)
        self.assertIn("Skipped missing/unknown account: 0", result)


if __name__ == "__main__":
    unittest.main()
