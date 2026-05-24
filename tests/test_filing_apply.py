"""Tests: inbox filing apply mode — safety guards, account routing, Gmail mock calls, PII-free log."""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call


def _make_item(queue_id, msg_id, category, risk=10, protected=False, manual_review=False, account=None):
    item = {
        "queue_id": queue_id,
        "message_id": msg_id,
        "category": category,
        "risk_score": risk,
        "protected": protected,
        "manual_review": manual_review,
        "local_decision": "",
    }
    if account:
        item["account"] = account
    return item


def _mock_service():
    svc = MagicMock()
    # Do not pre-call modify() here — that would taint the call-count assertions.
    return svc


class TestApplyFilingSafeItems(unittest.TestCase):

    def _run(self, items, account="primary"):
        svc = _mock_service()
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=items), \
             patch("inbox_scout.inbox_filing_runner.get_gmail_service", return_value=svc), \
             patch("inbox_scout.inbox_filing_runner._log_filing_action"), \
             patch("inbox_scout.inbox_filing_runner._get_or_create_label", return_value="LABEL_ID"):
            from inbox_scout.inbox_filing_runner import apply_filing
            return apply_filing(account), svc

    def test_safe_filing_item_archives_and_marks_read(self):
        items = [_make_item("q1", "msg1", "newsletter", account="primary")]
        result, svc = self._run(items)
        call_args = svc.users().messages().modify.call_args
        body = call_args[1]["body"]
        self.assertIn("INBOX", body["removeLabelIds"])
        self.assertIn("UNREAD", body["removeLabelIds"])
        self.assertIn("Labeled: 1", result)
        self.assertIn("Archived: 1", result)
        self.assertIn("Marked read: 1", result)

    def test_label_only_item_does_not_archive_or_mark_read(self):
        from inbox_scout.inbox_filing_runner import apply_filing
        # shopping_history_soft: category=bills/receipts with low risk
        item = _make_item("q2", "msg2", "bills/receipts", risk=5, account="primary")
        # force it into label_only bucket by patching is_shopping_history_soft
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=[item]), \
             patch("inbox_scout.inbox_filing_runner.get_gmail_service", return_value=_mock_service()), \
             patch("inbox_scout.inbox_filing_runner._log_filing_action"), \
             patch("inbox_scout.inbox_filing_runner._get_or_create_label", return_value="LBL"), \
             patch("inbox_scout.inbox_filing_runner._bucket", return_value="label_only"):
            result = apply_filing("primary")
        self.assertIn("Label only", result)
        self.assertIn("Archived: 0", result)
        self.assertIn("Marked read: 0", result)

    def test_protected_item_skipped_no_gmail_call(self):
        items = [_make_item("q3", "msg3", "newsletter", protected=True, account="primary")]
        result, svc = self._run(items)
        svc.users().messages().modify.assert_not_called()
        self.assertIn("No Gmail changes made", result)

    def test_manual_review_item_skipped(self):
        items = [_make_item("q4", "msg4", "newsletter", manual_review=True, account="primary")]
        result, svc = self._run(items)
        svc.users().messages().modify.assert_not_called()

    def test_high_risk_item_skipped(self):
        items = [_make_item("q5", "msg5", "newsletter", risk=99, account="primary")]
        result, svc = self._run(items)
        svc.users().messages().modify.assert_not_called()


class TestApplyFilingAccountGuard(unittest.TestCase):

    def _run(self, items, account):
        from inbox_scout.inbox_filing_runner import apply_filing
        svc = _mock_service()
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=items), \
             patch("inbox_scout.inbox_filing_runner.get_gmail_service", return_value=svc), \
             patch("inbox_scout.inbox_filing_runner._log_filing_action"), \
             patch("inbox_scout.inbox_filing_runner._get_or_create_label", return_value="LABEL_ID"):
            return apply_filing(account), svc

    def test_secondary_account_uses_secondary_service(self):
        items = [_make_item("q6", "msg6", "newsletter", account="secondary")]
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=items), \
             patch("inbox_scout.inbox_filing_runner.get_gmail_service") as mock_svc_fn, \
             patch("inbox_scout.inbox_filing_runner._log_filing_action"), \
             patch("inbox_scout.inbox_filing_runner._get_or_create_label", return_value="LBL"):
            mock_svc_fn.return_value = _mock_service()
            from inbox_scout.inbox_filing_runner import apply_filing
            apply_filing("secondary")
        mock_svc_fn.assert_called_once_with(mode="modify", account="secondary")

    def test_item_with_mismatched_account_is_skipped(self):
        items = [_make_item("q7", "msg7", "newsletter", account="secondary")]
        result, svc = self._run(items, "primary")
        svc.users().messages().modify.assert_not_called()
        self.assertIn("No Gmail changes made", result)

    def test_item_with_no_account_field_is_skipped(self):
        items = [_make_item("q8", "msg8", "newsletter")]  # no account field — must be skipped
        result, svc = self._run(items, "primary")
        svc.users().messages().modify.assert_not_called()
        self.assertIn("No Gmail changes made", result)

    def test_all_items_missing_account_does_not_call_gmail_service(self):
        from inbox_scout.inbox_filing_runner import apply_filing
        items = [_make_item("q8b", "msg8b", "newsletter")]  # no account field
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=items), \
             patch("inbox_scout.inbox_filing_runner.get_gmail_service") as mock_svc, \
             patch("inbox_scout.inbox_filing_runner._log_filing_action"):
            result = apply_filing("primary")
        mock_svc.assert_not_called()
        self.assertIn("No Gmail changes made", result)

    def test_explicit_primary_account_item_applies(self):
        items = [_make_item("q8c", "msg8c", "newsletter", account="primary")]
        result, svc = self._run(items, "primary")
        self.assertIn("Labeled: 1", result)

    def test_explicit_secondary_account_item_applies(self):
        from inbox_scout.inbox_filing_runner import apply_filing
        items = [_make_item("q8d", "msg8d", "newsletter", account="secondary")]
        svc = _mock_service()
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=items), \
             patch("inbox_scout.inbox_filing_runner.get_gmail_service", return_value=svc), \
             patch("inbox_scout.inbox_filing_runner._log_filing_action"), \
             patch("inbox_scout.inbox_filing_runner._get_or_create_label", return_value="LABEL_ID"):
            result = apply_filing("secondary")
        self.assertIn("Labeled: 1", result)

    def test_unknown_account_string_refused(self):
        from inbox_scout.inbox_filing_runner import apply_filing
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=[]):
            result = apply_filing("bogus")
        self.assertIn("Unknown account", result)
        self.assertIn("No Gmail changes made", result)


class TestApplyFilingEdgeCases(unittest.TestCase):

    def test_empty_queue_returns_no_work_message(self):
        from inbox_scout.inbox_filing_runner import apply_filing
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=[]):
            result = apply_filing("primary")
        self.assertIn("No queue found", result)
        self.assertIn("No Gmail changes made", result)

    def test_auth_failure_returns_safe_message(self):
        from inbox_scout.inbox_filing_runner import apply_filing
        items = [_make_item("q9", "msg9", "newsletter", account="primary")]
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=items), \
             patch("inbox_scout.inbox_filing_runner.get_gmail_service", side_effect=Exception("invalid_grant")), \
             patch("inbox_scout.inbox_filing_runner._log_filing_action"):
            result = apply_filing("primary")
        self.assertIn("authorization failed", result)
        self.assertIn("No Gmail changes made", result)

    def test_missing_message_id_counted_as_failed(self):
        from inbox_scout.inbox_filing_runner import apply_filing
        item = _make_item("q10", None, "newsletter", account="primary")
        item.pop("message_id", None)
        svc = _mock_service()
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=[item]), \
             patch("inbox_scout.inbox_filing_runner.get_gmail_service", return_value=svc), \
             patch("inbox_scout.inbox_filing_runner._log_filing_action"), \
             patch("inbox_scout.inbox_filing_runner._get_or_create_label", return_value="LBL"):
            result = apply_filing("primary")
        svc.users().messages().modify.assert_not_called()
        self.assertIn("Failed: 1", result)


class TestApplyFilingLogPiiSafety(unittest.TestCase):

    def test_log_entries_contain_no_pii_fields(self):
        from inbox_scout.inbox_filing_runner import apply_filing
        logged = []
        items = [_make_item("q11", "msg11", "newsletter")]
        svc = _mock_service()
        with patch("inbox_scout.inbox_filing_runner._load_queue", return_value=items), \
             patch("inbox_scout.inbox_filing_runner.get_gmail_service", return_value=svc), \
             patch("inbox_scout.inbox_filing_runner._log_filing_action", side_effect=logged.append), \
             patch("inbox_scout.inbox_filing_runner._get_or_create_label", return_value="LBL"):
            apply_filing("primary")
        self.assertGreater(len(logged), 0)
        pii_fields = {"subject", "from", "sender", "snippet", "message_id", "gmail_message_id", "email"}
        for entry in logged:
            for field in pii_fields:
                self.assertNotIn(field, entry, f"PII field '{field}' found in log entry")


class TestNaturalIntentApplyFilingRouting(unittest.TestCase):

    def _route(self, phrase):
        from inbox_scout import natural_intent
        with patch("inbox_scout.inbox_filing_runner.apply_filing", return_value="applied") as mock_apply, \
             patch("inbox_scout.natural_intent.apply_filing", return_value="applied") as mock_ni:
            result = natural_intent.handle_natural_message(phrase)
        return result

    def test_apply_filing_primary_routes_to_apply(self):
        from inbox_scout import natural_intent
        with patch("inbox_scout.natural_intent.apply_filing", return_value="applied") as mock_apply:
            result = natural_intent.handle_natural_message("apply filing primary")
        mock_apply.assert_called_once_with("primary")

    def test_apply_filing_secondary_routes_to_apply(self):
        from inbox_scout import natural_intent
        with patch("inbox_scout.natural_intent.apply_filing", return_value="applied") as mock_apply:
            result = natural_intent.handle_natural_message("apply filing secondary")
        mock_apply.assert_called_once_with("secondary")

    def test_apply_filing_no_account_asks_to_specify(self):
        from inbox_scout import natural_intent
        with patch("inbox_scout.natural_intent.apply_filing", return_value="applied") as mock_apply:
            result = natural_intent.handle_natural_message("apply filing")
        mock_apply.assert_not_called()
        self.assertIn("No Gmail changes made", result)

    def test_confirm_filing_routes_to_apply(self):
        from inbox_scout import natural_intent
        with patch("inbox_scout.natural_intent.apply_filing", return_value="applied") as mock_apply:
            result = natural_intent.handle_natural_message("confirm filing primary")
        mock_apply.assert_called_once_with("primary")

    def test_run_filing_routes_to_apply(self):
        from inbox_scout import natural_intent
        with patch("inbox_scout.natural_intent.apply_filing", return_value="applied") as mock_apply:
            result = natural_intent.handle_natural_message("run filing secondary")
        mock_apply.assert_called_once_with("secondary")


class TestTelegramFilingGateRouting(unittest.TestCase):
    """Filing phrases must reach handle_natural_message, not evaluate_apply_gate."""

    def _handle(self, text):
        from inbox_scout.telegram_listener import handle_command
        return handle_command(text)

    def test_apply_filing_primary_does_not_hit_apply_gate(self):
        with patch("inbox_scout.telegram_listener.handle_natural_message", return_value="filing_called") as mock_ni, \
             patch("inbox_scout.telegram_listener.evaluate_apply_gate") as mock_gate:
            result = self._handle("apply filing primary")
        mock_ni.assert_called_once()
        mock_gate.assert_not_called()

    def test_apply_filing_secondary_does_not_hit_apply_gate(self):
        with patch("inbox_scout.telegram_listener.handle_natural_message", return_value="filing_called") as mock_ni, \
             patch("inbox_scout.telegram_listener.evaluate_apply_gate") as mock_gate:
            result = self._handle("apply filing secondary")
        mock_ni.assert_called_once()
        mock_gate.assert_not_called()

    def test_apply_archive_2_still_hits_apply_gate(self):
        with patch("inbox_scout.telegram_listener.evaluate_apply_gate", return_value="gate_called") as mock_gate, \
             patch("inbox_scout.telegram_listener.handle_natural_message") as mock_ni:
            result = self._handle("apply archive 2")
        mock_gate.assert_called_once()
        mock_ni.assert_not_called()


if __name__ == "__main__":
    unittest.main()
