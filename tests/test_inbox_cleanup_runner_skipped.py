"""
Test: skipped cleanup candidates are logged and reported.

Proves: when some candidates pass validation and one fails (risk too high),
the failing candidate is logged as cleanup_trash_skipped with gmail_changed=False
and shown in the returned Telegram message. No Gmail write occurs for the skip.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_inbox_cleanup_runner_skipped -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

_VALID = {
    "queue_id": "3",
    "message_id": "msg003",
    "subject": "Weekly Newsletter",
    "category": "Newsletter",
    "risk_score": 10,
    "manual_review": False,
    "local_decision": "pending_review",
    "gmail_action_taken": False,
    "gmail_action_type": "",
    "gmail_trashed": False,
}

# risk_score 50 > MAX_TRASH_RISK(30) → fails validate_candidate
_SKIPPED = {
    "queue_id": "24",
    "message_id": "msg024",
    "subject": "Make AI Ask Questions First",
    "category": "Newsletter",
    "risk_score": 50,
    "manual_review": False,
    "local_decision": "pending_review",
    "gmail_action_taken": False,
    "gmail_action_type": "",
    "gmail_trashed": False,
}

_CANDIDATES = [
    {"queue_id": "3",  "subject": "Weekly Newsletter",        "category": "Newsletter", "risk": 10},
    {"queue_id": "24", "subject": "Make AI Ask Questions First", "category": "Newsletter", "risk": 10},
]


class TestCleanupRunnerSkipped(unittest.TestCase):

    @patch("inbox_scout.inbox_cleanup_runner.get_modify_service")
    @patch("inbox_scout.inbox_cleanup_runner.append_jsonl")
    @patch("inbox_scout.inbox_cleanup_runner.save_queue_document")
    @patch("inbox_scout.inbox_cleanup_runner.load_queue_document")
    @patch("inbox_scout.inbox_cleanup_runner.load_and_validate_cleanup_plan")
    def test_skipped_candidate_logged_and_reported(
        self,
        mock_plan,
        mock_load_queue,
        mock_save_queue,
        mock_append_jsonl,
        mock_get_service,
    ):
        mock_plan.return_value = (_CANDIDATES, [])
        mock_load_queue.return_value = ([], [_VALID, _SKIPPED])

        svc = MagicMock()
        svc.users.return_value.messages.return_value.trash.return_value.execute.return_value = {}
        svc.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}
        mock_get_service.return_value = svc

        from inbox_scout.inbox_cleanup_runner import build_inbox_cleanup_runner_message
        result = build_inbox_cleanup_runner_message()

        # Message must report exactly 1 moved and mention the skip
        self.assertIn("Moved 1 email(s)", result)
        self.assertIn("Skipped (failed safety check)", result)
        self.assertIn("24", result)

        # cleanup_trash_skipped must be in the log
        logged = [
            c.args[1]
            for c in mock_append_jsonl.call_args_list
            if len(c.args) >= 2 and isinstance(c.args[1], dict)
        ]
        skip_entries = [e for e in logged if e.get("event") == "cleanup_trash_skipped"]
        self.assertEqual(len(skip_entries), 1)
        self.assertEqual(skip_entries[0]["queue_id"], "24")
        self.assertFalse(skip_entries[0]["gmail_changed"])

        # No cleanup_trash_skipped logged for the valid item
        self.assertTrue(all(e.get("queue_id") != "3" for e in skip_entries))
