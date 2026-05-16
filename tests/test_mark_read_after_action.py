"""
Tests for mark-read-after-action integration in inbox_cleanup_runner.

Proves:
- Successful approved trash action also marks email as read
- Failed Gmail trash does NOT mark email as read
- Protected/manual_review emails are excluded entirely
- Gmail modify (mark-read) is called AFTER trash succeeds, not before
- attempt_mark_read_after_action swallows errors gracefully

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m pytest tests/test_mark_read_after_action.py -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_scout.inbox_cleanup_runner import attempt_mark_read_after_action


def _safe_item(**overrides):
    """Queue item that passes all cleanup runner safety checks (newsletter, risk<=30)."""
    base = {
        "queue_id": "q1",
        "subject": "April newsletter",
        "category": "newsletter",
        "risk_score": 20,
        "manual_review": False,
        "manual_review_required": False,
        "protected": False,
        "local_decision": "pending_review",
        "gmail_message_id": "msg001",
        "gmail_action_type": "",
        "gmail_action_taken": False,
        "gmail_trashed": False,
        "gmail_marked_read": False,
        "from": "news@example.com",
        "snippet": "Check out this month's newsletter",
    }
    return {**base, **overrides}


def _candidate(queue_id: str = "q1") -> dict:
    return {"queue_id": queue_id, "category": "newsletter", "risk_score": 20}


def _run_cleanup(candidates, queue_items, mock_svc):
    import inbox_scout.inbox_cleanup_runner as runner
    from inbox_scout.inbox_cleanup_runner import build_inbox_cleanup_runner_message
    with patch.object(runner, "load_and_validate_cleanup_plan", return_value=(candidates, [])), \
         patch.object(runner, "load_queue_document", return_value=(queue_items, queue_items)), \
         patch.object(runner, "save_queue_document"), \
         patch.object(runner, "append_jsonl"), \
         patch.object(runner, "get_modify_service", return_value=mock_svc):
        return build_inbox_cleanup_runner_message()


class TestAttemptMarkReadAfterAction(unittest.TestCase):
    def test_success_sets_fields_and_returns_true(self):
        mock_svc = MagicMock()
        item: dict = {}
        result = attempt_mark_read_after_action(mock_svc, "msg001", item)
        self.assertTrue(result)
        mock_svc.users.return_value.messages.return_value.modify.assert_called_once_with(
            userId="me",
            id="msg001",
            body={"removeLabelIds": ["UNREAD"]},
        )
        mock_svc.users.return_value.messages.return_value.modify.return_value.execute.assert_called_once()
        self.assertTrue(item.get("gmail_marked_read"))
        self.assertEqual(item.get("gmail_read_action_type"), "marked_read_after_trash")
        self.assertTrue(item.get("gmail_read_action_taken"))
        self.assertIn("gmail_marked_read_at", item)

    def test_gmail_failure_does_not_set_fields_and_returns_false(self):
        mock_svc = MagicMock()
        mock_svc.users.return_value.messages.return_value.modify.return_value.execute.side_effect = RuntimeError("API error")
        item: dict = {}
        result = attempt_mark_read_after_action(mock_svc, "msg001", item)
        self.assertFalse(result)
        self.assertFalse(item.get("gmail_marked_read", False))
        self.assertNotIn("gmail_read_action_type", item)
        self.assertNotIn("gmail_read_action_taken", item)
        self.assertNotIn("gmail_marked_read_at", item)

    def test_modify_not_called_on_exception_during_modify_call(self):
        mock_svc = MagicMock()
        mock_svc.users.return_value.messages.return_value.modify.side_effect = RuntimeError("Connection error")
        item: dict = {}
        result = attempt_mark_read_after_action(mock_svc, "msg001", item)
        self.assertFalse(result)
        self.assertFalse(item.get("gmail_marked_read", False))


class TestCleanupRunnerMarkRead(unittest.TestCase):
    def test_successful_trash_also_marks_read(self):
        mock_svc = MagicMock()
        item = _safe_item()
        result = _run_cleanup([_candidate()], [item], mock_svc)
        mock_svc.users.return_value.messages.return_value.trash.assert_called_once_with(
            userId="me", id="msg001"
        )
        mock_svc.users.return_value.messages.return_value.modify.assert_called_once_with(
            userId="me", id="msg001", body={"removeLabelIds": ["UNREAD"]}
        )
        self.assertIn("moved", result.lower())
        self.assertTrue(item.get("gmail_marked_read"))

    def test_failed_trash_does_not_mark_read(self):
        mock_svc = MagicMock()
        mock_svc.users.return_value.messages.return_value.trash.return_value.execute.side_effect = RuntimeError("Trash failed")
        item = _safe_item()
        _run_cleanup([_candidate()], [item], mock_svc)
        mock_svc.users.return_value.messages.return_value.modify.assert_not_called()
        self.assertFalse(item.get("gmail_marked_read", False))

    def test_manual_review_item_not_touched(self):
        mock_svc = MagicMock()
        item = _safe_item(manual_review=True)
        _run_cleanup([_candidate()], [item], mock_svc)
        mock_svc.users.return_value.messages.return_value.trash.assert_not_called()
        mock_svc.users.return_value.messages.return_value.modify.assert_not_called()

    def test_protected_review_item_not_touched(self):
        mock_svc = MagicMock()
        item = _safe_item(local_decision="protected_review")
        _run_cleanup([_candidate()], [item], mock_svc)
        mock_svc.users.return_value.messages.return_value.trash.assert_not_called()
        mock_svc.users.return_value.messages.return_value.modify.assert_not_called()

    def test_mark_read_called_only_after_successful_trash(self):
        """Verify order: trash execute → mark-read modify execute."""
        mock_svc = MagicMock()
        call_order: list[str] = []
        mock_svc.users.return_value.messages.return_value.trash.return_value.execute.side_effect = \
            lambda: call_order.append("trash")
        mock_svc.users.return_value.messages.return_value.modify.return_value.execute.side_effect = \
            lambda: call_order.append("mark_read")
        item = _safe_item()
        _run_cleanup([_candidate()], [item], mock_svc)
        self.assertEqual(call_order, ["trash", "mark_read"])

    def test_mark_read_failure_is_non_critical(self):
        """Mark-read failure does not affect trash success reporting."""
        mock_svc = MagicMock()
        mock_svc.users.return_value.messages.return_value.modify.return_value.execute.side_effect = RuntimeError("Mark read failed")
        item = _safe_item()
        result = _run_cleanup([_candidate()], [item], mock_svc)
        self.assertIn("moved", result.lower())
        self.assertTrue(item.get("gmail_trashed"))
        self.assertFalse(item.get("gmail_marked_read", False))

    def test_pending_review_item_not_in_candidates_not_touched(self):
        """Items not in the candidate list are not touched regardless of state."""
        mock_svc = MagicMock()
        item_in_plan = _safe_item(queue_id="q1")
        item_not_in_plan = _safe_item(queue_id="q2", gmail_message_id="msg002")
        _run_cleanup([_candidate("q1")], [item_in_plan, item_not_in_plan], mock_svc)
        # Only one trash call for q1
        self.assertEqual(
            mock_svc.users.return_value.messages.return_value.trash.call_count, 1
        )
        call_kwargs = mock_svc.users.return_value.messages.return_value.trash.call_args[1]
        self.assertEqual(call_kwargs["id"], "msg001")
        self.assertFalse(item_not_in_plan.get("gmail_marked_read", False))


class TestMarkReadLogging(unittest.TestCase):
    def _run_with_log_capture(self, mock_svc, candidates, queue_items):
        import inbox_scout.inbox_cleanup_runner as runner
        from inbox_scout.inbox_cleanup_runner import build_inbox_cleanup_runner_message
        log_entries: list[dict] = []
        with patch.object(runner, "load_and_validate_cleanup_plan", return_value=(candidates, [])), \
             patch.object(runner, "load_queue_document", return_value=(queue_items, queue_items)), \
             patch.object(runner, "save_queue_document"), \
             patch.object(runner, "append_jsonl", side_effect=lambda _path, entry: log_entries.append(entry)), \
             patch.object(runner, "get_modify_service", return_value=mock_svc):
            build_inbox_cleanup_runner_message()
        return log_entries

    def test_mark_read_success_logged(self):
        mock_svc = MagicMock()
        entries = self._run_with_log_capture(mock_svc, [_candidate()], [_safe_item()])
        mark_read_entries = [e for e in entries if e.get("event") == "cleanup_mark_read"]
        self.assertEqual(len(mark_read_entries), 1)
        self.assertTrue(mark_read_entries[0]["success"])
        self.assertTrue(mark_read_entries[0]["gmail_changed"])
        self.assertEqual(mark_read_entries[0]["message_id"], "msg001")

    def test_mark_read_failure_logged(self):
        mock_svc = MagicMock()
        mock_svc.users.return_value.messages.return_value.modify.return_value.execute.side_effect = RuntimeError("fail")
        entries = self._run_with_log_capture(mock_svc, [_candidate()], [_safe_item()])
        mark_read_entries = [e for e in entries if e.get("event") == "cleanup_mark_read"]
        self.assertEqual(len(mark_read_entries), 1)
        self.assertFalse(mark_read_entries[0]["success"])
        self.assertFalse(mark_read_entries[0]["gmail_changed"])


if __name__ == "__main__":
    unittest.main()
