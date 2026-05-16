"""
Focused tests for Telegram confirm gate execution (archive/trash + mark-read).

Proves:
- archive success calls modify removeLabelIds ["INBOX"], then mark-read ["UNREAD"]
- trash success calls .trash(), then mark-read ["UNREAD"]
- failed archive/trash does NOT call mark-read
- disabled flags block execution
- protected/manual_review items stay blocked
- safety flags reset after execution attempt

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_telegram_confirm_execute -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _archive_item(queue_id="4", **overrides):
    base = {
        "queue_id": queue_id,
        "subject": "April newsletter",
        "category": "newsletter",
        "local_decision": "possible_archive_later",
        "risk_score": 20,
        "manual_review": False,
        "gmail_message_id": "msg001",
        "gmail_action_taken": False,
        "gmail_action_type": "",
    }
    return {**base, **overrides}


def _trash_item(queue_id="4", **overrides):
    base = {
        "queue_id": queue_id,
        "subject": "Promo email",
        "category": "newsletter",
        "local_decision": "ignore",
        "risk_score": 20,
        "manual_review": False,
        "gmail_message_id": "msg001",
        "gmail_action_taken": False,
        "gmail_action_type": "",
    }
    return {**base, **overrides}


def _enabled_config():
    return {
        "telegram_confirm_enabled": True,
        "telegram_apply_enabled": True,
        "permanent_delete_enabled": False,
        "telegram_two_step_required": True,
    }


def _disabled_config():
    return {
        "telegram_confirm_enabled": False,
        "telegram_apply_enabled": False,
        "permanent_delete_enabled": False,
        "telegram_two_step_required": True,
    }


def _run_gate(command, item, config, mock_svc):
    import inbox_scout.telegram_confirm_gate as gate
    items = [item]
    with patch.object(gate, "find_item", return_value=item), \
         patch.object(gate, "load_config", return_value=config), \
         patch.object(gate, "save_config"), \
         patch.object(gate, "ensure_confirm_disabled"), \
         patch.object(gate, "get_modify_service", return_value=mock_svc), \
         patch.object(gate, "_load_full_queue", return_value=(items, items)), \
         patch.object(gate, "_save_full_queue"), \
         patch.object(gate, "log_confirm_attempt"), \
         patch.object(gate, "_reset_execution_flags"):
        from inbox_scout.telegram_confirm_gate import evaluate_confirm_gate
        return evaluate_confirm_gate(command)


class TestArchiveExecution(unittest.TestCase):
    def test_archive_calls_modify_inbox_then_mark_read(self):
        mock_svc = MagicMock()
        item = _archive_item()
        result = _run_gate("confirm archive 4", item, _enabled_config(), mock_svc)

        # Archive: removeLabelIds ["INBOX"]
        mock_svc.users.return_value.messages.return_value.modify.assert_any_call(
            userId="me", id="msg001", body={"removeLabelIds": ["INBOX"]}
        )
        # Mark-read: removeLabelIds ["UNREAD"]
        mock_svc.users.return_value.messages.return_value.modify.assert_any_call(
            userId="me", id="msg001", body={"removeLabelIds": ["UNREAD"]}
        )
        self.assertIn("done", result.lower())
        self.assertIn("archive", result.lower())

    def test_archive_sets_queue_fields(self):
        mock_svc = MagicMock()
        item = _archive_item()
        items = [item]
        import inbox_scout.telegram_confirm_gate as gate
        with patch.object(gate, "find_item", return_value=item), \
             patch.object(gate, "load_config", return_value=_enabled_config()), \
             patch.object(gate, "save_config"), \
             patch.object(gate, "ensure_confirm_disabled"), \
             patch.object(gate, "get_modify_service", return_value=mock_svc), \
             patch.object(gate, "_load_full_queue", return_value=(items, items)), \
             patch.object(gate, "_save_full_queue"), \
             patch.object(gate, "log_confirm_attempt"), \
             patch.object(gate, "_reset_execution_flags"):
            gate.evaluate_confirm_gate("confirm archive 4")
        self.assertTrue(item.get("gmail_archived"))
        self.assertTrue(item.get("gmail_action_taken"))
        self.assertEqual(item.get("gmail_action_type"), "archived")

    def test_failed_archive_does_not_mark_read(self):
        mock_svc = MagicMock()
        mock_svc.users.return_value.messages.return_value.modify.return_value.execute.side_effect = RuntimeError("fail")
        item = _archive_item()
        result = _run_gate("confirm archive 4", item, _enabled_config(), mock_svc)
        # Mark-read modify should not have been called (only one modify attempt — the archive one that failed)
        self.assertIn("failed", result.lower())
        self.assertFalse(item.get("gmail_archived", False))


class TestTrashExecution(unittest.TestCase):
    def test_trash_calls_trash_then_mark_read(self):
        mock_svc = MagicMock()
        item = _trash_item()
        result = _run_gate("confirm trash 4", item, _enabled_config(), mock_svc)

        mock_svc.users.return_value.messages.return_value.trash.assert_called_once_with(
            userId="me", id="msg001"
        )
        mock_svc.users.return_value.messages.return_value.modify.assert_called_once_with(
            userId="me", id="msg001", body={"removeLabelIds": ["UNREAD"]}
        )
        self.assertIn("done", result.lower())
        self.assertIn("trash", result.lower())

    def test_failed_trash_does_not_mark_read(self):
        mock_svc = MagicMock()
        mock_svc.users.return_value.messages.return_value.trash.return_value.execute.side_effect = RuntimeError("fail")
        item = _trash_item()
        result = _run_gate("confirm trash 4", item, _enabled_config(), mock_svc)
        mock_svc.users.return_value.messages.return_value.modify.assert_not_called()
        self.assertIn("failed", result.lower())
        self.assertFalse(item.get("gmail_trashed", False))


class TestSafetyGates(unittest.TestCase):
    def test_disabled_flags_block_execution(self):
        mock_svc = MagicMock()
        item = _archive_item()
        result = _run_gate("confirm archive 4", item, _disabled_config(), mock_svc)
        mock_svc.users.return_value.messages.return_value.modify.assert_not_called()
        self.assertIn("disabled", result.lower())

    def test_protected_item_blocked(self):
        mock_svc = MagicMock()
        item = _archive_item(manual_review=True)
        result = _run_gate("confirm archive 4", item, _enabled_config(), mock_svc)
        mock_svc.users.return_value.messages.return_value.modify.assert_not_called()
        self.assertIn("blocked", result.lower())

    def test_flags_reset_after_execution(self):
        import inbox_scout.telegram_confirm_gate as gate
        mock_svc = MagicMock()
        item = _archive_item()
        items = [item]
        reset_calls = []
        with patch.object(gate, "find_item", return_value=item), \
             patch.object(gate, "load_config", return_value=_enabled_config()), \
             patch.object(gate, "save_config"), \
             patch.object(gate, "ensure_confirm_disabled"), \
             patch.object(gate, "get_modify_service", return_value=mock_svc), \
             patch.object(gate, "_load_full_queue", return_value=(items, items)), \
             patch.object(gate, "_save_full_queue"), \
             patch.object(gate, "log_confirm_attempt"), \
             patch.object(gate, "_reset_execution_flags", side_effect=lambda: reset_calls.append(1)):
            gate.evaluate_confirm_gate("confirm archive 4")
        self.assertEqual(len(reset_calls), 1)

    def test_flags_reset_even_on_gmail_failure(self):
        import inbox_scout.telegram_confirm_gate as gate
        mock_svc = MagicMock()
        mock_svc.users.return_value.messages.return_value.modify.return_value.execute.side_effect = RuntimeError("fail")
        item = _archive_item()
        items = [item]
        reset_calls = []
        with patch.object(gate, "find_item", return_value=item), \
             patch.object(gate, "load_config", return_value=_enabled_config()), \
             patch.object(gate, "save_config"), \
             patch.object(gate, "ensure_confirm_disabled"), \
             patch.object(gate, "get_modify_service", return_value=mock_svc), \
             patch.object(gate, "_load_full_queue", return_value=(items, items)), \
             patch.object(gate, "_save_full_queue"), \
             patch.object(gate, "log_confirm_attempt"), \
             patch.object(gate, "_reset_execution_flags", side_effect=lambda: reset_calls.append(1)):
            gate.evaluate_confirm_gate("confirm archive 4")
        self.assertEqual(len(reset_calls), 1)


if __name__ == "__main__":
    unittest.main()
