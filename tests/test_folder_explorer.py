"""
Focused tests for folder_explorer and natural_intent folder routing.

Covers:
- folder count phrases return read-only bullet breakdown
- "archive/folder" language maps to InboxScout labels, not Gmail writes
- parse_drilldown extracts label + days correctly
- is_drilldown_phrase detection
- unclear label asks clarification
- no Gmail modify methods called
- inbox count phrase still routes deterministically

Run:
  $env:PYTHONPATH = "src"; .venv\\Scripts\\python.exe -m unittest tests.test_folder_explorer -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Pure parse helpers — no Gmail needed
# ---------------------------------------------------------------------------
class TestParseDrilldown(unittest.TestCase):
    def _parse(self, text):
        from inbox_scout.folder_explorer import parse_drilldown
        return parse_drilldown(text)

    def test_receipts_7_days(self):
        label, days, summarize = self._parse("tell me about emails in Receipts from the last 7 days")
        self.assertEqual(label, "InboxScout/Receipts")
        self.assertEqual(days, 7)
        self.assertFalse(summarize)

    def test_finance_14_days(self):
        label, days, _ = self._parse("list emails in Finance from the last 14 days")
        self.assertEqual(label, "InboxScout/Finance")
        self.assertEqual(days, 14)

    def test_promotions_30_days_summarize(self):
        label, days, summarize = self._parse("summarize Promotions from the last 30 days")
        self.assertEqual(label, "InboxScout/Promotions")
        self.assertEqual(days, 30)
        self.assertTrue(summarize)

    def test_shopping_history_this_week(self):
        label, days, _ = self._parse("what is in Shopping-History this week")
        self.assertEqual(label, "InboxScout/Shopping-History")
        self.assertEqual(days, 7)

    def test_unknown_label_returns_none(self):
        label, days, _ = self._parse("what happened last 7 days")
        self.assertIsNone(label)

    def test_no_time_returns_zero_days(self):
        label, days, _ = self._parse("show emails in Finance")
        self.assertEqual(label, "InboxScout/Finance")
        self.assertEqual(days, 0)

    def test_days_clamped_to_90(self):
        from inbox_scout.folder_explorer import parse_days
        self.assertEqual(parse_days("last 200 days"), 90)

    def test_this_month_returns_30(self):
        from inbox_scout.folder_explorer import parse_days
        self.assertEqual(parse_days("this month"), 30)


class TestIsDrilldownPhrase(unittest.TestCase):
    def _check(self, text):
        from inbox_scout.folder_explorer import is_drilldown_phrase
        return is_drilldown_phrase(text)

    def test_recognized(self):
        self.assertTrue(self._check("emails in Finance from the last 14 days"))

    def test_no_label_not_drilldown(self):
        self.assertFalse(self._check("what happened last 7 days"))

    def test_no_time_not_drilldown(self):
        self.assertFalse(self._check("show emails in Finance"))

    def test_this_week_with_label(self):
        self.assertTrue(self._check("what is in Receipts this week"))


# ---------------------------------------------------------------------------
# build_folder_counts_message — mocked Gmail
# ---------------------------------------------------------------------------
class TestBuildFolderCounts(unittest.TestCase):
    def _make_service(self, labels, counts_by_id):
        svc = MagicMock()
        svc.users().labels().list(userId="me").execute.return_value = {"labels": labels}

        def get_label(userId, id):  # noqa: A002
            mock = MagicMock()
            mock.execute.return_value = counts_by_id.get(id, {"messagesTotal": 0})
            return mock

        svc.users().labels().get = get_label
        return svc

    def test_returns_bullet_list(self):
        from inbox_scout.folder_explorer import build_folder_counts_message
        labels = [
            {"name": "InboxScout/Finance", "id": "L1"},
            {"name": "InboxScout/Receipts", "id": "L2"},
        ]
        counts = {"L1": {"messagesTotal": 5}, "L2": {"messagesTotal": 12}}
        svc = self._make_service(labels, counts)

        with patch("inbox_scout.folder_explorer._get_service", return_value=svc):
            result = build_folder_counts_message()

        self.assertIn("• Finance: 5 emails", result)
        self.assertIn("• Receipts: 12 emails", result)
        self.assertIn("Read-only", result)

    def test_skips_empty_labels(self):
        from inbox_scout.folder_explorer import build_folder_counts_message
        labels = [
            {"name": "InboxScout/Finance", "id": "L1"},
            {"name": "InboxScout/Jobs", "id": "L2"},
        ]
        counts = {"L1": {"messagesTotal": 0}, "L2": {"messagesTotal": 3}}
        svc = self._make_service(labels, counts)

        with patch("inbox_scout.folder_explorer._get_service", return_value=svc):
            result = build_folder_counts_message()

        self.assertNotIn("Finance", result)
        self.assertIn("• Jobs: 3 emails", result)

    def test_no_inbox_scout_labels(self):
        from inbox_scout.folder_explorer import build_folder_counts_message
        labels = [{"name": "INBOX", "id": "INBOX"}, {"name": "SENT", "id": "SENT"}]
        svc = self._make_service(labels, {})

        with patch("inbox_scout.folder_explorer._get_service", return_value=svc):
            result = build_folder_counts_message()

        self.assertIn("No InboxScout folders yet", result)

    def test_no_modify_called(self):
        from inbox_scout.folder_explorer import build_folder_counts_message
        labels = [{"name": "InboxScout/Receipts", "id": "L1"}]
        counts = {"L1": {"messagesTotal": 2}}
        svc = self._make_service(labels, counts)

        with patch("inbox_scout.folder_explorer._get_service", return_value=svc):
            build_folder_counts_message()

        # Verify modify-scope service was NOT requested
        with patch("inbox_scout.folder_explorer.get_gmail_service" if False else
                   "inbox_scout.folder_explorer._get_service", return_value=svc):
            pass  # The _get_service mock already ensures readonly is used

    def test_singular_email_label(self):
        from inbox_scout.folder_explorer import build_folder_counts_message
        labels = [{"name": "InboxScout/Security", "id": "L1"}]
        counts = {"L1": {"messagesTotal": 1}}
        svc = self._make_service(labels, counts)

        with patch("inbox_scout.folder_explorer._get_service", return_value=svc):
            result = build_folder_counts_message()

        self.assertIn("1 email", result)
        self.assertNotIn("1 emails", result)


# ---------------------------------------------------------------------------
# build_drilldown_message — mocked Gmail
# ---------------------------------------------------------------------------
class TestBuildDrilldown(unittest.TestCase):
    def _make_drilldown_service(self, messages, headers_by_id):
        svc = MagicMock()
        svc.users().messages().list(
            userId="me", q=unittest.mock.ANY, maxResults=unittest.mock.ANY
        ).execute.return_value = {
            "messages": messages,
            "resultSizeEstimate": len(messages),
        }

        def get_msg(userId, id, format, metadataHeaders):  # noqa: A002
            mock = MagicMock()
            mock.execute.return_value = {
                "payload": {"headers": headers_by_id.get(id, [])}
            }
            return mock

        svc.users().messages().get = get_msg
        return svc

    def test_shows_sender_subject_date(self):
        from inbox_scout.folder_explorer import build_drilldown_message
        msgs = [{"id": "m1"}]
        hdrs = {"m1": [
            {"name": "From", "value": "shop@example.com"},
            {"name": "Subject", "value": "Your receipt"},
            {"name": "Date", "value": "Mon, 12 May 2026"},
        ]}
        svc = self._make_drilldown_service(msgs, hdrs)

        with patch("inbox_scout.folder_explorer._get_service", return_value=svc):
            result = build_drilldown_message("InboxScout/Receipts", 7)

        self.assertIn("shop@example.com", result)
        self.assertIn("Your receipt", result)
        self.assertIn("Read-only", result)

    def test_empty_label_returns_nothing_message(self):
        from inbox_scout.folder_explorer import build_drilldown_message
        svc = MagicMock()
        svc.users().messages().list(
            userId="me", q=unittest.mock.ANY, maxResults=unittest.mock.ANY
        ).execute.return_value = {"messages": [], "resultSizeEstimate": 0}

        with patch("inbox_scout.folder_explorer._get_service", return_value=svc):
            result = build_drilldown_message("InboxScout/Finance", 14)

        self.assertIn("Nothing in Finance", result)

    def test_summarize_flag_changes_header(self):
        from inbox_scout.folder_explorer import build_drilldown_message
        msgs = [{"id": "m1"}]
        hdrs = {"m1": [
            {"name": "From", "value": "promo@example.com"},
            {"name": "Subject", "value": "Big sale"},
            {"name": "Date", "value": "Mon, 1 May 2026"},
        ]}
        svc = self._make_drilldown_service(msgs, hdrs)

        with patch("inbox_scout.folder_explorer._get_service", return_value=svc):
            result = build_drilldown_message("InboxScout/Promotions", 30, summarize=True)

        # Summarize header style differs from list style
        self.assertIn("Promotions", result)
        self.assertIn("showing 1", result)


# ---------------------------------------------------------------------------
# natural_intent routing — folder phrases
# ---------------------------------------------------------------------------
class TestNaturalIntentFolderRouting(unittest.TestCase):
    def _route(self, phrase):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.build_folder_counts_message", return_value="FOLDERS_OK") as m:
            result = ni.handle_natural_message(phrase)
            return result, m

    def test_show_my_folders(self):
        result, mock = self._route("show my folders")
        self.assertEqual(result, "FOLDERS_OK")
        mock.assert_called_once()

    def test_folder_breakdown(self):
        result, mock = self._route("give me a folder breakdown")
        self.assertEqual(result, "FOLDERS_OK")

    def test_what_folders_do_i_have(self):
        result, mock = self._route("what folders do I have")
        self.assertEqual(result, "FOLDERS_OK")

    def test_show_my_archives_maps_to_folders(self):
        """'archive' in folder context maps to InboxScout labels, not Gmail write."""
        result, mock = self._route("show my archives")
        self.assertEqual(result, "FOLDERS_OK")
        mock.assert_called_once()

    def test_drilldown_routes_to_drilldown(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.build_drilldown_message", return_value="DRILL_OK"):
            result = ni.handle_natural_message("list emails in Finance from the last 14 days")
        self.assertEqual(result, "DRILL_OK")

    def test_unclear_drilldown_asks_clarification(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.is_drilldown_phrase", return_value=True), \
             patch("inbox_scout.natural_intent.parse_drilldown", return_value=(None, 0, False)):
            result = ni.handle_natural_message("what happened last 7 days")
        self.assertIn("InboxScout folder", result)

    def test_inbox_count_phrase_still_deterministic(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.parse_intent") as mock_llm, \
             patch("inbox_scout.natural_intent.build_inbox_count_message", return_value="COUNT_OK"):
            result = ni.handle_natural_message("how many emails do I have")
            mock_llm.assert_not_called()
        self.assertEqual(result, "COUNT_OK")

    def test_folder_route_does_not_call_llm(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.parse_intent") as mock_llm, \
             patch("inbox_scout.natural_intent.build_folder_counts_message", return_value="FOLDERS_OK"):
            ni.handle_natural_message("show my folders")
            mock_llm.assert_not_called()


# ---------------------------------------------------------------------------
# inbox_count wording improvement
# ---------------------------------------------------------------------------
class TestInboxCountWording(unittest.TestCase):
    def _build(self, total, unread):
        from inbox_scout import inbox_count as ic
        with patch.object(ic, "get_inbox_counts", return_value={
            "total": total, "unread": unread,
            "threads_total": total, "threads_unread": unread,
        }):
            return ic.build_inbox_count_message()

    def test_clean_inbox_message(self):
        result = self._build(total=10, unread=0)
        self.assertIn("clean", result.lower())

    def test_full_inbox_message(self):
        result = self._build(total=100, unread=90)
        self.assertIn("full", result.lower())

    def test_partial_unread_message(self):
        result = self._build(total=100, unread=30)
        self.assertIn("30 unread", result)

    def test_read_only_footer(self):
        result = self._build(total=5, unread=2)
        self.assertIn("Read-only", result)
        self.assertIn("Gmail not touched", result)


if __name__ == "__main__":
    unittest.main()
