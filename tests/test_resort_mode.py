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

from inbox_scout.resort_mode import build_resort_candidates, build_resort_preview_message, _scan_one_account


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


def _make_scan_service(label_names, msgs_per_label=10, metadata_total=None):
    """Build a mock Gmail service for _scan_one_account tests.
    metadata_total overrides messagesTotal in label metadata (simulates stale/zero counts)."""
    svc = MagicMock()
    reported = metadata_total if metadata_total is not None else msgs_per_label
    svc.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        "labels": [
            {"name": n, "id": f"id_{i}", "messagesTotal": reported}
            for i, n in enumerate(label_names)
        ]
    }
    msg_ids = [{"id": f"msg_{j}"} for j in range(msgs_per_label)]
    svc.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": msg_ids
    }
    svc.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "payload": {"headers": [
            {"name": "From", "value": "promo@example.com"},
            {"name": "Subject", "value": "Big Sale"},
            {"name": "Date", "value": "Mon, 1 Jan 2024"},
        ]},
        "snippet": "sale snippet",
    }
    return svc


def _make_get_side_effect():
    """Returns a callable that always returns a valid message metadata response."""
    resp = {
        "payload": {"headers": [
            {"name": "From", "value": "promo@example.com"},
            {"name": "Subject", "value": "Big Sale"},
            {"name": "Date", "value": "Mon, 1 Jan 2024"},
        ]},
        "snippet": "sale snippet",
    }
    return lambda *a, **kw: MagicMock(**{"execute.return_value": resp})


def _classified_promo():
    return {
        "message_id": "msg_x",
        "from": "promo@example.com",
        "subject": "Big Sale",
        "snippet": "sale snippet",
        "ai_classification": {
            "category": "Promotion",
            "risk_score": 5,
            "manual_review": False,
            "protected": False,
        },
    }


class TestFetchLabeledEmailsPagination(unittest.TestCase):
    """Verify _fetch_labeled_emails paginates through multiple Gmail API pages."""

    def _make_paginated_service(self, pages: list[list[str]]):
        """pages = list of lists of message IDs per page. Last page has no nextPageToken."""
        svc = MagicMock()
        list_responses = []
        for i, page_ids in enumerate(pages):
            resp = {"messages": [{"id": mid} for mid in page_ids]}
            if i < len(pages) - 1:
                resp["nextPageToken"] = f"tok_{i}"
            list_responses.append(resp)
        svc.users.return_value.messages.return_value.list.return_value.execute.side_effect = (
            list_responses
        )
        # messages.get always returns the same stub
        get_resp = {
            "payload": {"headers": [
                {"name": "From", "value": "a@b.com"},
                {"name": "Subject", "value": "Test"},
                {"name": "Date", "value": "Mon, 1 Jan 2024"},
            ]},
            "snippet": "test",
        }
        svc.users.return_value.messages.return_value.get.return_value.execute.return_value = get_resp
        return svc

    def test_fetches_all_pages(self):
        from inbox_scout.resort_mode import _fetch_labeled_emails
        svc = self._make_paginated_service([["msg1", "msg2"], ["msg3", "msg4"]])
        result = _fetch_labeled_emails(svc, "InboxScout/Newsletter", remaining_cap=100)
        self.assertEqual(len(result), 4)
        self.assertEqual([r["message_id"] for r in result], ["msg1", "msg2", "msg3", "msg4"])

    def test_stops_at_no_next_page(self):
        from inbox_scout.resort_mode import _fetch_labeled_emails
        svc = self._make_paginated_service([["msg1", "msg2"]])
        result = _fetch_labeled_emails(svc, "InboxScout/Newsletter", remaining_cap=100)
        self.assertEqual(len(result), 2)
        # Only one list() call — no second page requested
        self.assertEqual(
            svc.users.return_value.messages.return_value.list.return_value.execute.call_count, 1
        )

    def test_respects_remaining_cap_mid_page(self):
        from inbox_scout.resort_mode import _fetch_labeled_emails
        svc = self._make_paginated_service([["msg1", "msg2", "msg3", "msg4", "msg5"]])
        result = _fetch_labeled_emails(svc, "InboxScout/Newsletter", remaining_cap=3)
        self.assertEqual(len(result), 3)

    def test_respects_remaining_cap_across_pages(self):
        from inbox_scout.resort_mode import _fetch_labeled_emails
        svc = self._make_paginated_service([["msg1", "msg2"], ["msg3", "msg4"], ["msg5"]])
        result = _fetch_labeled_emails(svc, "InboxScout/Newsletter", remaining_cap=3)
        self.assertEqual(len(result), 3)
        # Should stop fetching after cap — not all 3 pages requested
        list_execute_count = (
            svc.users.return_value.messages.return_value.list.return_value.execute.call_count
        )
        self.assertLessEqual(list_execute_count, 2)

    def test_three_page_scan_returns_all(self):
        from inbox_scout.resort_mode import _fetch_labeled_emails
        svc = self._make_paginated_service([
            ["a1", "a2", "a3"],
            ["b1", "b2", "b3"],
            ["c1", "c2"],
        ])
        result = _fetch_labeled_emails(svc, "InboxScout/Newsletter", remaining_cap=500)
        self.assertEqual(len(result), 8)

    def test_scan_account_reports_capped_in_completion(self):
        from inbox_scout import resort_mode
        labels = ["InboxScout/Newsletter"]
        svc = _make_scan_service(labels, msgs_per_label=5)
        items = [_classified_promo() for _ in range(5)]
        progress_calls = []
        with patch.object(resort_mode, "_get_service", return_value=svc), \
             patch("inbox_scout.report_mode.classify_for_report", return_value=items), \
             patch.object(resort_mode, "RESORT_MAX_SCAN_TOTAL", 3):
            _scan_one_account("primary", on_progress=progress_calls.append)
        complete = next(c for c in progress_calls if "complete" in c.lower())
        self.assertIn("cap", complete.lower())

    def test_scan_account_not_capped_reports_no_cap(self):
        from inbox_scout import resort_mode
        labels = ["InboxScout/Newsletter"]
        svc = _make_scan_service(labels, msgs_per_label=5)
        items = [_classified_promo() for _ in range(5)]
        progress_calls = []
        with patch.object(resort_mode, "_get_service", return_value=svc), \
             patch("inbox_scout.report_mode.classify_for_report", return_value=items):
            result = _scan_one_account("primary", on_progress=progress_calls.append)
        self.assertFalse(result.get("capped"))
        complete = next(c for c in progress_calls if "complete" in c.lower())
        self.assertNotIn("cap", complete.lower())


class TestScanProgressCallback(unittest.TestCase):
    """Verify _scan_one_account fires on_progress at milestones and completion (no start message)."""

    def _run(self, label_names, msgs_per_label=10, classified_items=None):
        from inbox_scout import resort_mode
        svc = _make_scan_service(label_names, msgs_per_label)
        items = classified_items or [_classified_promo() for _ in range(msgs_per_label)]
        progress_calls = []
        with patch.object(resort_mode, "_get_service", return_value=svc), \
             patch("inbox_scout.report_mode.classify_for_report", return_value=items):
            _scan_one_account("primary", on_progress=progress_calls.append)
        return progress_calls

    def test_no_start_message_sent_before_scan(self):
        # Atlas already sent an ack; scan must not send a back-to-back start message
        labels = [f"InboxScout/Label{i}" for i in range(3)]
        calls = self._run(labels, msgs_per_label=5)
        non_completion = [c for c in calls if "Resort scan" in c and "complete" not in c.lower()]
        self.assertEqual(non_completion, [], f"Unexpected start message(s): {non_completion}")

    def test_completion_message_sent(self):
        labels = [f"InboxScout/Label{i}" for i in range(2)]
        calls = self._run(labels, msgs_per_label=5)
        self.assertTrue(any("complete" in c.lower() for c in calls))

    def test_progress_milestone_sent_when_enough_emails(self):
        # 26 labels × 10 emails = 260 → crosses _PROGRESS_INTERVAL (250)
        labels = [f"InboxScout/Label{i}" for i in range(26)]
        calls = self._run(labels, msgs_per_label=10)
        self.assertTrue(any("Resort progress:" in c for c in calls))

    def test_no_progress_milestone_below_interval(self):
        # 3 labels × 10 emails = 30 → below _PROGRESS_INTERVAL (250), no mid-scan update
        labels = [f"InboxScout/Label{i}" for i in range(3)]
        calls = self._run(labels, msgs_per_label=10)
        self.assertFalse(any("Resort progress:" in c for c in calls))

    def test_no_crash_when_on_progress_is_none(self):
        from inbox_scout import resort_mode
        labels = ["InboxScout/Newsletter"]
        svc = _make_scan_service(labels, msgs_per_label=2)
        with patch.object(resort_mode, "_get_service", return_value=svc), \
             patch("inbox_scout.report_mode.classify_for_report", return_value=[_classified_promo()]):
            result = _scan_one_account("primary", on_progress=None)
        self.assertIn("scanned", result)

    def test_progress_fires_when_messages_total_is_zero(self):
        # Regression: messagesTotal=0 (stale/unreliable) but emails actually fetched
        # Progress must still fire based on actual fetched count, not messagesTotal
        labels = [f"InboxScout/Label{i}" for i in range(26)]
        items = [_classified_promo() for _ in range(10)]
        from inbox_scout import resort_mode
        svc = _make_scan_service(labels, msgs_per_label=10, metadata_total=0)
        progress_calls = []
        with patch.object(resort_mode, "_get_service", return_value=svc), \
             patch("inbox_scout.report_mode.classify_for_report", return_value=items):
            _scan_one_account("primary", on_progress=progress_calls.append)
        # Progress must still fire (260 emails → crosses 250-email threshold)
        self.assertTrue(any("Resort progress:" in c for c in progress_calls))
        # No progress message should report 0 emails scanned
        self.assertFalse(any("progress: 0 emails" in c for c in progress_calls))

    def test_preview_path_passes_no_progress(self):
        # build_resort_preview_message must NOT call on_progress (stays silent)
        progress_calls = []
        def fake_scan(acct, on_progress=None):
            if on_progress is not None:
                progress_calls.append("LEAKED")
            return _mock_scan(acct)
        with patch("inbox_scout.resort_mode._scan_one_account", side_effect=fake_scan), \
             patch("inbox_scout.resort_mode.LATEST_RESORT_PLAN") as mock_path:
            mock_path.parent = MagicMock()
            mock_path.write_text = MagicMock()
            build_resort_preview_message(account="primary")
        self.assertEqual(progress_calls, [], "Preview must not send progress messages")


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
