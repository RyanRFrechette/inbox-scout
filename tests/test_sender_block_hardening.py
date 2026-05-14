"""
Focused tests for trash_sender_block_runner and trash_sender_block_plan hardening.
Run: $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_sender_block_hardening -v
"""
from __future__ import annotations

import json
import sys
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_scout.trash_sender_block_plan import is_system_sender, filter_senders
from inbox_scout.trash_sender_block_runner import (
    scope_is_available,
    get_existing_blocked_senders,
)


def _make_service(list_return=None, list_raise=None):
    """Build a fake Gmail service object for settings().filters().list()."""
    svc = MagicMock()
    list_call = svc.users.return_value.settings.return_value.filters.return_value.list.return_value
    if list_raise:
        list_call.execute.side_effect = list_raise
    else:
        list_call.execute.return_value = list_return or {}
    return svc


# ---------------------------------------------------------------------------
# scope_is_available
# ---------------------------------------------------------------------------
class TestScopeIsAvailable(unittest.TestCase):
    def test_returns_true_on_successful_probe(self):
        svc = _make_service(list_return={"filter": []})
        self.assertTrue(scope_is_available(svc))

    def test_returns_false_on_403_scope_error(self):
        svc = _make_service(list_raise=Exception("Request had insufficient authentication scopes. [403]"))
        self.assertFalse(scope_is_available(svc))

    def test_returns_false_on_network_error(self):
        svc = _make_service(list_raise=ConnectionError("network timeout"))
        self.assertFalse(scope_is_available(svc))

    def test_returns_false_on_500_server_error(self):
        svc = _make_service(list_raise=Exception("500 internal server error"))
        self.assertFalse(scope_is_available(svc))

    def test_returns_false_on_generic_exception(self):
        svc = _make_service(list_raise=RuntimeError("unexpected failure"))
        self.assertFalse(scope_is_available(svc))


# ---------------------------------------------------------------------------
# get_existing_blocked_senders
# ---------------------------------------------------------------------------
class TestGetExistingBlockedSenders(unittest.TestCase):
    def _filter_entry(self, from_addr, adds, removes):
        return {
            "criteria": {"from": from_addr},
            "action": {"addLabelIds": adds, "removeLabelIds": removes},
        }

    def test_returns_sender_from_trash_and_remove_inbox_filter(self):
        svc = _make_service(list_return={"filter": [
            self._filter_entry("spam@example.com", ["TRASH"], ["INBOX", "UNREAD"]),
        ]})
        result = get_existing_blocked_senders(svc)
        self.assertIn("spam@example.com", result)

    def test_ignores_filter_without_trash_label(self):
        svc = _make_service(list_return={"filter": [
            self._filter_entry("news@example.com", ["LABEL_123"], ["INBOX"]),
        ]})
        result = get_existing_blocked_senders(svc)
        self.assertNotIn("news@example.com", result)

    def test_ignores_filter_without_inbox_removal(self):
        svc = _make_service(list_return={"filter": [
            self._filter_entry("promo@example.com", ["TRASH"], []),
        ]})
        result = get_existing_blocked_senders(svc)
        self.assertNotIn("promo@example.com", result)

    def test_returns_empty_set_on_api_exception(self):
        svc = _make_service(list_raise=Exception("API error"))
        result = get_existing_blocked_senders(svc)
        self.assertEqual(result, set())

    def test_multiple_blocked_senders(self):
        svc = _make_service(list_return={"filter": [
            self._filter_entry("a@example.com", ["TRASH"], ["INBOX"]),
            self._filter_entry("b@example.com", ["TRASH"], ["INBOX", "UNREAD"]),
        ]})
        result = get_existing_blocked_senders(svc)
        self.assertEqual(result, {"a@example.com", "b@example.com"})

    def test_handles_name_plus_email_format(self):
        svc = _make_service(list_return={"filter": [
            self._filter_entry("Sender Name <sender@example.com>", ["TRASH"], ["INBOX"]),
        ]})
        result = get_existing_blocked_senders(svc)
        self.assertIn("sender@example.com", result)


# ---------------------------------------------------------------------------
# System sender regex tightening
# ---------------------------------------------------------------------------
class TestSystemSenderPatterns(unittest.TestCase):
    def test_real_google_support_is_protected(self):
        self.assertTrue(is_system_sender("support@google.com"))

    def test_real_google_accounts_is_protected(self):
        self.assertTrue(is_system_sender("accounts@google.com"))

    def test_google_subdomain_is_protected(self):
        self.assertTrue(is_system_sender("support@mail.google.com"))

    def test_evil_google_domain_is_not_protected(self):
        self.assertFalse(is_system_sender("support@evil-google.com"))

    def test_evil_google_domain_accounts_is_not_protected(self):
        self.assertFalse(is_system_sender("accounts@notgoogle.com"))

    def test_noreply_is_always_protected(self):
        self.assertTrue(is_system_sender("noreply@anydomain.com"))

    def test_security_is_always_protected(self):
        self.assertTrue(is_system_sender("security@somebank.com"))


# ---------------------------------------------------------------------------
# filter_senders: system senders excluded, deduplication
# ---------------------------------------------------------------------------
class TestFilterSenders(unittest.TestCase):
    def test_excludes_system_senders(self):
        raw = ["noreply@example.com", "newsletter@spam.com"]
        result = filter_senders(raw)
        self.assertNotIn("noreply@example.com", result)
        self.assertIn("newsletter@spam.com", result)

    def test_deduplicates(self):
        raw = ["dup@example.com", "dup@example.com", "dup@example.com"]
        result = filter_senders(raw)
        self.assertEqual(result, ["dup@example.com"])

    def test_excludes_invalid_emails(self):
        raw = ["notanemail", "also bad", "good@example.com"]
        result = filter_senders(raw)
        self.assertEqual(result, ["good@example.com"])


# ---------------------------------------------------------------------------
# load_and_validate_plan: wrong confirmation blocked, plan gates
# ---------------------------------------------------------------------------
class TestLoadAndValidatePlan(unittest.TestCase):
    def _write_plan(self, path, overrides=None):
        plan = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sender_count": 2,
            "senders": ["a@x.com", "b@x.com"],
            "confirmation_phrase": "BLOCK 2 TRASH SENDERS",
            "gmail_changes_enabled": False,
            "permanent_delete_enabled": False,
        }
        if overrides:
            plan.update(overrides)
        path.write_text(json.dumps(plan), encoding="utf-8")

    def test_wrong_confirmation_is_blocked(self):
        from inbox_scout.trash_sender_block_runner import load_and_validate_plan
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            self._write_plan(plan_path)
            with patch("inbox_scout.trash_sender_block_runner.LATEST_SENDER_BLOCK_PLAN", plan_path):
                senders, errors = load_and_validate_plan("BLOCK 99 TRASH SENDERS")
        self.assertEqual(senders, [])
        self.assertTrue(any("Wrong confirmation" in e for e in errors))

    def test_correct_confirmation_passes(self):
        from inbox_scout.trash_sender_block_runner import load_and_validate_plan
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            self._write_plan(plan_path)
            with patch("inbox_scout.trash_sender_block_runner.LATEST_SENDER_BLOCK_PLAN", plan_path):
                senders, errors = load_and_validate_plan("BLOCK 2 TRASH SENDERS")
        self.assertEqual(errors, [])
        self.assertEqual(senders, ["a@x.com", "b@x.com"])

    def test_permanent_delete_enabled_blocks(self):
        from inbox_scout.trash_sender_block_runner import load_and_validate_plan
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            self._write_plan(plan_path, {"permanent_delete_enabled": True})
            with patch("inbox_scout.trash_sender_block_runner.LATEST_SENDER_BLOCK_PLAN", plan_path):
                senders, errors = load_and_validate_plan("BLOCK 2 TRASH SENDERS")
        self.assertEqual(senders, [])
        self.assertTrue(any("permanent delete" in e.lower() for e in errors))

    def test_no_plan_file_returns_error(self):
        from inbox_scout.trash_sender_block_runner import load_and_validate_plan
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "nonexistent.json"
            with patch("inbox_scout.trash_sender_block_runner.LATEST_SENDER_BLOCK_PLAN", plan_path):
                senders, errors = load_and_validate_plan("BLOCK 2 TRASH SENDERS")
        self.assertEqual(senders, [])
        self.assertTrue(len(errors) > 0)


# ---------------------------------------------------------------------------
# Duplicate sender skipping in build_sender_block_runner_message
# ---------------------------------------------------------------------------
class TestDuplicateFilterSkipping(unittest.TestCase):
    def _make_plan_file(self, tmp_dir, senders):
        count = len(senders)
        plan = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sender_count": count,
            "senders": senders,
            "confirmation_phrase": f"BLOCK {count} TRASH SENDERS",
            "gmail_changes_enabled": False,
            "permanent_delete_enabled": False,
        }
        p = Path(tmp_dir) / "plan.json"
        p.write_text(json.dumps(plan), encoding="utf-8")
        return p

    def _make_service_with_filters(self, existing_senders):
        filters = []
        for addr in existing_senders:
            filters.append({
                "criteria": {"from": addr},
                "action": {"addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX"]},
            })
        svc = MagicMock()
        list_call = svc.users.return_value.settings.return_value.filters.return_value.list.return_value
        list_call.execute.return_value = {"filter": filters}
        create_call = svc.users.return_value.settings.return_value.filters.return_value.create.return_value
        create_call.execute.return_value = {"id": "new_filter_id"}
        return svc

    def test_duplicate_sender_is_skipped(self):
        from inbox_scout.trash_sender_block_runner import build_sender_block_runner_message
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = self._make_plan_file(tmp, ["already@blocked.com"])
            log_path = Path(tmp) / "log.jsonl"
            svc = self._make_service_with_filters(["already@blocked.com"])
            with (
                patch("inbox_scout.trash_sender_block_runner.LATEST_SENDER_BLOCK_PLAN", plan_path),
                patch("inbox_scout.trash_sender_block_runner.SENDER_BLOCK_LOG", log_path),
                patch("inbox_scout.trash_sender_block_runner.get_settings_service", return_value=svc),
            ):
                result = build_sender_block_runner_message("BLOCK 1 TRASH SENDERS")
        self.assertIn("skipped", result.lower())
        self.assertIn("already@blocked.com", result)
        # Confirm no filter was created
        svc.users.return_value.settings.return_value.filters.return_value.create.assert_not_called()

    def test_new_sender_creates_filter(self):
        from inbox_scout.trash_sender_block_runner import build_sender_block_runner_message
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = self._make_plan_file(tmp, ["new@sender.com"])
            log_path = Path(tmp) / "log.jsonl"
            svc = self._make_service_with_filters([])  # no existing filters
            with (
                patch("inbox_scout.trash_sender_block_runner.LATEST_SENDER_BLOCK_PLAN", plan_path),
                patch("inbox_scout.trash_sender_block_runner.SENDER_BLOCK_LOG", log_path),
                patch("inbox_scout.trash_sender_block_runner.get_settings_service", return_value=svc),
            ):
                result = build_sender_block_runner_message("BLOCK 1 TRASH SENDERS")
        self.assertIn("Blocked 1", result)
        self.assertIn("new@sender.com", result)

    def test_scope_unavailable_blocks_execution(self):
        from inbox_scout.trash_sender_block_runner import build_sender_block_runner_message
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = self._make_plan_file(tmp, ["x@example.com"])
            svc = _make_service(list_raise=Exception("insufficient authentication scopes [403]"))
            with (
                patch("inbox_scout.trash_sender_block_runner.LATEST_SENDER_BLOCK_PLAN", plan_path),
                patch("inbox_scout.trash_sender_block_runner.get_settings_service", return_value=svc),
            ):
                result = build_sender_block_runner_message("BLOCK 1 TRASH SENDERS")
        self.assertIn("Gmail not touched", result)
        self.assertIn("scope", result.lower())


if __name__ == "__main__":
    unittest.main()
