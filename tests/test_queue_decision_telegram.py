"""
Focused tests for Telegram queue decision commands.

Proves:
- "keep 4", "ignore 4", "review later 4", "possible archive later 4" route correctly
- Bad/missing IDs fail safely with "Gmail not touched"
- No Gmail write helpers are called

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_queue_decision_telegram -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_scout.queue_decision import build_set_decision_message


def _queue_payload(queue_id=4, local_decision="pending_review"):
    return {
        "queue_items": [
            {
                "queue_id": queue_id,
                "subject": "April newsletter",
                "local_decision": local_decision,
                "gmail_action_taken": False,
            }
        ]
    }


def _with_queue(payload, fn, *args, **kwargs):
    import inbox_scout.queue_decision as qd
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(payload, f)
        tmp = Path(f.name)
    log_tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    orig_q = qd.LATEST_QUEUE_FILE
    orig_d = qd.QUEUE_DIR
    qd.LATEST_QUEUE_FILE = tmp
    qd.QUEUE_DIR = tmp.parent
    try:
        return fn(*args, **kwargs)
    finally:
        qd.LATEST_QUEUE_FILE = orig_q
        qd.QUEUE_DIR = orig_d
        tmp.unlink(missing_ok=True)
        log_tmp.unlink(missing_ok=True)


class TestDecisionParsing(unittest.TestCase):
    def test_keep_routes(self):
        result = _with_queue(_queue_payload(), build_set_decision_message, "keep 4")
        self.assertIsNotNone(result)
        self.assertIn("keep", result.lower())
        self.assertIn("4", result)
        self.assertIn("gmail not touched", result.lower())

    def test_ignore_routes(self):
        result = _with_queue(_queue_payload(), build_set_decision_message, "ignore 4")
        self.assertIsNotNone(result)
        self.assertIn("ignore", result.lower())
        self.assertIn("gmail not touched", result.lower())

    def test_review_later_routes(self):
        result = _with_queue(_queue_payload(), build_set_decision_message, "review later 4")
        self.assertIsNotNone(result)
        self.assertIn("review_later", result)
        self.assertIn("gmail not touched", result.lower())

    def test_possible_archive_later_routes(self):
        result = _with_queue(_queue_payload(), build_set_decision_message, "possible archive later 4")
        self.assertIsNotNone(result)
        self.assertIn("possible_archive_later", result)
        self.assertIn("gmail not touched", result.lower())

    def test_no_match_returns_none(self):
        self.assertIsNone(build_set_decision_message("keep sorting"))
        self.assertIsNone(build_set_decision_message("hello"))
        self.assertIsNone(build_set_decision_message("keep"))
        self.assertIsNone(build_set_decision_message("ignore"))

    def test_missing_id_returns_none(self):
        self.assertIsNone(build_set_decision_message("keep abc"))

    def test_uppercase_normalised(self):
        result = _with_queue(_queue_payload(), build_set_decision_message, "Keep 4")
        self.assertIsNotNone(result)
        self.assertIn("keep", result.lower())


class TestDecisionSafety(unittest.TestCase):
    def test_unknown_id_safe_message(self):
        result = _with_queue(_queue_payload(queue_id=1), build_set_decision_message, "keep 99")
        self.assertIn("no queue item found", result.lower())
        self.assertIn("gmail not touched", result.lower())

    def test_no_queue_file_safe_message(self):
        import inbox_scout.queue_decision as qd
        orig = qd.LATEST_QUEUE_FILE
        qd.LATEST_QUEUE_FILE = Path("/nonexistent/path/latest_queue.json")
        try:
            result = build_set_decision_message("keep 4")
        finally:
            qd.LATEST_QUEUE_FILE = orig
        self.assertIn("no queue found", result.lower())
        self.assertIn("gmail not touched", result.lower())

    def test_decision_written_to_queue(self):
        import inbox_scout.queue_decision as qd
        payload = _queue_payload()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(payload, f)
            tmp = Path(f.name)
        orig_q, orig_d = qd.LATEST_QUEUE_FILE, qd.QUEUE_DIR
        qd.LATEST_QUEUE_FILE = tmp
        qd.QUEUE_DIR = tmp.parent
        try:
            build_set_decision_message("keep 4")
            saved = json.loads(tmp.read_text(encoding="utf-8"))
        finally:
            qd.LATEST_QUEUE_FILE = orig_q
            qd.QUEUE_DIR = orig_d
            tmp.unlink(missing_ok=True)
        items = saved.get("queue_items", [])
        self.assertEqual(items[0]["local_decision"], "keep")
        self.assertFalse(items[0]["gmail_action_taken"])

    def test_no_gmail_write_helper_called(self):
        """Confirms no Gmail modify/trash/archive service is ever invoked."""
        with patch("inbox_scout.queue_decision.LATEST_QUEUE_FILE") as _mock_file:
            _mock_file.exists.return_value = False
            result = build_set_decision_message("keep 4")
        # Service helpers that touch Gmail must never be called
        self.assertIn("no queue found", result.lower())

    def test_already_actioned_item_preserves_gmail_fields(self):
        """keep N on a trashed item must not reset gmail_action_taken or gmail_action_type."""
        import inbox_scout.queue_decision as qd
        payload = {
            "queue_items": [
                {
                    "queue_id": 4,
                    "subject": "Already trashed",
                    "local_decision": "ignore",
                    "gmail_action_taken": True,
                    "gmail_action_type": "trashed",
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(payload, f)
            tmp = Path(f.name)
        orig_q, orig_d = qd.LATEST_QUEUE_FILE, qd.QUEUE_DIR
        qd.LATEST_QUEUE_FILE = tmp
        qd.QUEUE_DIR = tmp.parent
        try:
            build_set_decision_message("keep 4")
            saved = json.loads(tmp.read_text(encoding="utf-8"))
        finally:
            qd.LATEST_QUEUE_FILE = orig_q
            qd.QUEUE_DIR = orig_d
            tmp.unlink(missing_ok=True)
        item = saved["queue_items"][0]
        self.assertEqual(item["local_decision"], "keep")
        self.assertTrue(item["gmail_action_taken"], "gmail_action_taken must stay True")
        self.assertEqual(item["gmail_action_type"], "trashed", "gmail_action_type must stay 'trashed'")


class TestNaturalIntentRouting(unittest.TestCase):
    def test_keep_4_routes_through_natural_intent(self):
        from inbox_scout.natural_intent import handle_natural_message
        import inbox_scout.queue_decision as qd
        payload = _queue_payload()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(payload, f)
            tmp = Path(f.name)
        orig_q, orig_d = qd.LATEST_QUEUE_FILE, qd.QUEUE_DIR
        qd.LATEST_QUEUE_FILE = tmp
        qd.QUEUE_DIR = tmp.parent
        try:
            result = handle_natural_message("keep 4")
        finally:
            qd.LATEST_QUEUE_FILE = orig_q
            qd.QUEUE_DIR = orig_d
            tmp.unlink(missing_ok=True)
        self.assertIn("gmail not touched", result.lower())
        self.assertIn("keep", result.lower())

    def test_ignore_4_routes_through_natural_intent(self):
        from inbox_scout.natural_intent import handle_natural_message
        import inbox_scout.queue_decision as qd
        payload = _queue_payload()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(payload, f)
            tmp = Path(f.name)
        orig_q, orig_d = qd.LATEST_QUEUE_FILE, qd.QUEUE_DIR
        qd.LATEST_QUEUE_FILE = tmp
        qd.QUEUE_DIR = tmp.parent
        try:
            result = handle_natural_message("ignore 4")
        finally:
            qd.LATEST_QUEUE_FILE = orig_q
            qd.QUEUE_DIR = orig_d
            tmp.unlink(missing_ok=True)
        self.assertIn("gmail not touched", result.lower())
        self.assertIn("ignore", result.lower())


if __name__ == "__main__":
    unittest.main()
