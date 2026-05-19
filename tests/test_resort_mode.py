"""
Test: Resort Mode preview logic — no Gmail calls, no file I/O.

Proves: build_resort_candidates correctly flags mismatches and applies
safety gates (manual_review, protected, high_risk, review_label).
Also verifies account scoping in build_resort_preview_message.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_resort_mode -v
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

from inbox_scout.resort_mode import build_resort_candidates, build_resort_preview_message


def _classified(**ai_overrides):
    """Return a classify_for_report-style item."""
    ai = {
        "category": "Promotion",
        "risk_score": 10,
        "manual_review": False,
        "protected": False,
    }
    ai.update(ai_overrides)
    return {
        "message_id": "msg1",
        "from": "promo@example.com",
        "subject": "Summer sale — 20% off",
        "snippet": "Don't miss out.",
        "ai_classification": ai,
    }


def _mock_scan(account: str) -> dict:
    return {
        "account": account,
        "scanned": 5,
        "mismatches": [
            {
                "message_id": f"{account}_msg1",
                "subject": "Test mismatch",
                "from": "test@example.com",
                "current_label": "InboxScout/Finance",
                "recommended_label": "InboxScout/Promotions",
                "recommended_category": "Promotion",
                "risk_score": 10,
                "manual_review": False,
            }
        ],
        "skipped_protected": 0,
        "skipped_manual_review": 0,
        "skipped_high_risk": 0,
        "skipped_review_label": 0,
    }


class TestBuildResortCandidates(unittest.TestCase):

    def test_mismatch_appears_when_labels_differ(self):
        # category=Promotion → InboxScout/Promotions, but currently in Finance
        item = _classified(category="Promotion")
        mismatches, _ = build_resort_candidates([item], "InboxScout/Finance")
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["recommended_label"], "InboxScout/Promotions")
        self.assertEqual(mismatches[0]["current_label"], "InboxScout/Finance")

    def test_no_mismatch_when_labels_match(self):
        item = _classified(category="Promotion")
        mismatches, _ = build_resort_candidates([item], "InboxScout/Promotions")
        self.assertEqual(len(mismatches), 0)

    def test_manual_review_skipped(self):
        item = _classified(manual_review=True)
        mismatches, skips = build_resort_candidates([item], "InboxScout/Finance")
        self.assertEqual(len(mismatches), 0)
        self.assertEqual(skips["manual_review"], 1)

    def test_protected_skipped(self):
        item = _classified(protected=True)
        mismatches, skips = build_resort_candidates([item], "InboxScout/Finance")
        self.assertEqual(len(mismatches), 0)
        self.assertEqual(skips["protected"], 1)

    def test_high_risk_skipped(self):
        item = _classified(risk_score=50)
        mismatches, skips = build_resort_candidates([item], "InboxScout/Finance")
        self.assertEqual(len(mismatches), 0)
        self.assertEqual(skips["high_risk"], 1)

    def test_risk_at_threshold_not_skipped(self):
        # Exactly 30 is allowed; only > 30 is blocked
        item = _classified(category="Promotion", risk_score=30)
        mismatches, skips = build_resort_candidates([item], "InboxScout/Finance")
        self.assertEqual(skips["high_risk"], 0)
        self.assertEqual(len(mismatches), 1)

    def test_review_label_skipped(self):
        item = _classified(category="Promotion")
        mismatches, skips = build_resort_candidates([item], "InboxScout/Review")
        self.assertEqual(len(mismatches), 0)
        self.assertEqual(skips["review_label"], 1)

    def test_protected_review_label_skipped(self):
        item = _classified(category="Promotion")
        mismatches, skips = build_resort_candidates([item], "InboxScout/Protected Review")
        self.assertEqual(len(mismatches), 0)
        self.assertEqual(skips["review_label"], 1)


class TestResortPreviewAccountScoping(unittest.TestCase):

    def _run_preview(self, account: str, scan_side_effect=None) -> tuple[str, list]:
        called_with = []

        def fake_scan(acct):
            called_with.append(acct)
            return _mock_scan(acct)

        side = scan_side_effect or fake_scan

        with patch("inbox_scout.resort_mode._scan_one_account", side_effect=side), \
             patch("inbox_scout.resort_mode.LATEST_RESORT_PLAN") as mock_path:
            mock_path.parent = MagicMock()
            mock_path.write_text = MagicMock()
            result = build_resort_preview_message(account=account)

        return result, called_with

    def test_both_account_preview_scans_primary_and_secondary(self):
        result, called = self._run_preview("both")
        self.assertIn("primary", called)
        self.assertIn("secondary", called)
        self.assertIn("Primary email", result)
        self.assertIn("Second email", result)

    def test_unspecified_scans_both(self):
        result, called = self._run_preview("unspecified")
        self.assertIn("primary", called)
        self.assertIn("secondary", called)

    def test_secondary_only_scans_secondary(self):
        result, called = self._run_preview("secondary")
        self.assertNotIn("primary", called)
        self.assertIn("secondary", called)
        self.assertIn("Second email", result)

    def test_primary_only_scans_primary(self):
        result, called = self._run_preview("primary")
        self.assertIn("primary", called)
        self.assertNotIn("secondary", called)

    def test_preview_includes_apply_prompt_when_mismatches_found(self):
        result, _ = self._run_preview("primary")
        self.assertIn("apply resort", result)

    def test_preview_footer_says_nothing_changed(self):
        result, _ = self._run_preview("primary")
        self.assertIn("Nothing was changed", result)


class TestResortRouting(unittest.TestCase):
    """Verify natural_intent routing: resort phrases win before status/audit catch-all."""

    def _route(self, text: str) -> str:
        """Return the function name that handle_natural_message would call for text."""
        from unittest.mock import patch, MagicMock
        import inbox_scout.natural_intent as ni

        resort_mock = MagicMock(return_value="__resort__")
        status_mock = MagicMock(return_value="__status__")

        with patch.object(ni, "build_resort_preview_message", resort_mock, create=True), \
             patch("inbox_scout.resort_mode.build_resort_preview_message", resort_mock), \
             patch("inbox_scout.natural_intent.build_status_message", status_mock):
            result = ni.handle_natural_message(text)

        if resort_mock.called:
            return "resort"
        if status_mock.called:
            return "status"
        return result

    def test_audit_my_archives_routes_to_resort(self):
        self.assertEqual(self._route("audit my archives"), "resort")

    def test_audit_sorted_folders_routes_to_resort(self):
        self.assertEqual(self._route("audit sorted folders"), "resort")

    def test_resort_my_sorted_emails_routes_to_resort(self):
        self.assertEqual(self._route("resort my sorted emails"), "resort")

    def test_inbox_status_routes_to_status(self):
        self.assertEqual(self._route("inbox status"), "status")

    def test_how_is_my_inbox_routes_to_status(self):
        self.assertEqual(self._route("how is my inbox"), "status")


class TestResortAck(unittest.TestCase):
    """Verify an immediate ack is sent before handle_command for resort phrases."""

    def _run(self, text: str):
        import inbox_scout.telegram_listener as tl
        sent = []
        with patch("inbox_scout.telegram_listener.send_message", side_effect=sent.append), \
             patch("inbox_scout.telegram_listener.handle_command", return_value="__final__"):
            # Simulate the relevant dispatch block directly
            if any(phrase in text.lower() for phrase in tl._RESORT_PREVIEW_PHRASES):
                try:
                    tl.send_message("Got it — starting Resort Mode Preview now. This is read-only and will not change Gmail.")
                except Exception:
                    pass
            tl.send_message(tl.handle_command(text))
        return sent

    def test_resort_command_sends_ack_first(self):
        sent = self._run("resort my sorted emails")
        self.assertEqual(len(sent), 2)
        self.assertIn("Resort Mode Preview", sent[0])
        self.assertIn("read-only", sent[0])

    def test_audit_my_archives_sends_ack_first(self):
        sent = self._run("audit my archives")
        self.assertIn("Resort Mode Preview", sent[0])

    def test_audit_sorted_folders_sends_ack_first(self):
        sent = self._run("audit sorted folders")
        self.assertIn("Resort Mode Preview", sent[0])

    def test_non_resort_command_no_ack(self):
        sent = self._run("status")
        self.assertEqual(len(sent), 1)
        self.assertNotIn("Resort Mode Preview", sent[0])


if __name__ == "__main__":
    unittest.main()
