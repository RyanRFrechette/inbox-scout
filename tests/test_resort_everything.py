"""Tests for resort_everything.py — full Gmail corpus scan."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, call

from inbox_scout.resort_everything import (
    collect_all_message_ids,
    _build_label_maps,
    _fetch_metadata_batch,
    _get_current_inboxscout_label,
    _is_system_label_id,
    _run_account_everything,
    build_resort_everything_message,
    _format_everything_summary,
    INBOX_SCOUT_PREFIX,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_list_service(pages: list[list[str]], include_next_page_token: bool = True):
    """Build mock service whose messages.list returns multiple pages of IDs."""
    svc = MagicMock()
    page_resps = []
    for i, page_ids in enumerate(pages):
        resp = {"messages": [{"id": mid} for mid in page_ids]}
        if i < len(pages) - 1 and include_next_page_token:
            resp["nextPageToken"] = f"tok_{i}"
        page_resps.append(resp)

    svc.users.return_value.messages.return_value.list.return_value.execute.side_effect = page_resps
    svc.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        "labels": [
            {"name": "InboxScout/Newsletter", "id": "lbl_nl"},
            {"name": "InboxScout/Promotions", "id": "lbl_pr"},
        ]
    }
    return svc


def _make_get_side_effect(label_ids: list[str] = None):
    """Return a side-effect for messages.get that fills labelIds."""
    label_ids = label_ids or ["lbl_nl"]

    def _side(userId, id, format, metadataHeaders):  # noqa: A002
        mock = MagicMock()
        mock.execute.return_value = {
            "labelIds": label_ids,
            "payload": {"headers": [
                {"name": "From", "value": "test@example.com"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Mon, 1 Jan 2024"},
            ]},
            "snippet": "test snippet",
        }
        return mock

    return _side


def _classified_nl():
    return {
        "message_id": "msg_x",
        "from": "nl@example.com",
        "subject": "Newsletter",
        "snippet": "read our newsletter",
        "ai_classification": {
            "category": "Newsletter",
            "risk_score": 5,
            "manual_review": False,
            "protected": False,
        },
    }


# ---------------------------------------------------------------------------
# 1. Pagination collects multiple pages
# ---------------------------------------------------------------------------

class TestCollectAllMessageIds(unittest.TestCase):

    def test_pagination_collects_multiple_pages(self):
        svc = _make_list_service([["a", "b"], ["c", "d"], ["e"]])
        ids, capped = collect_all_message_ids(svc)
        self.assertEqual(sorted(ids), ["a", "b", "c", "d", "e"])
        self.assertFalse(capped)

    def test_single_page_no_next_token(self):
        svc = _make_list_service([["x", "y"]], include_next_page_token=False)
        ids, capped = collect_all_message_ids(svc)
        self.assertEqual(sorted(ids), ["x", "y"])
        self.assertFalse(capped)

    def test_duplicate_ids_deduped(self):
        # Same ID appearing on two pages should be counted once
        svc = _make_list_service([["a", "b", "a"], ["b", "c"]])
        ids, capped = collect_all_message_ids(svc)
        self.assertEqual(sorted(ids), ["a", "b", "c"])
        self.assertFalse(capped)

    def test_debug_cap_stops_early_and_reports_incomplete(self):
        svc = _make_list_service([["a", "b", "c"], ["d", "e"]])
        ids, capped = collect_all_message_ids(svc, debug_cap=2)
        self.assertEqual(len(ids), 2)
        self.assertTrue(capped)

    def test_empty_account_returns_empty(self):
        svc = MagicMock()
        svc.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }
        ids, capped = collect_all_message_ids(svc)
        self.assertEqual(ids, [])
        self.assertFalse(capped)


# ---------------------------------------------------------------------------
# 2. System label guard
# ---------------------------------------------------------------------------

class TestSystemLabelGuard(unittest.TestCase):

    def test_inbox_is_system(self):
        self.assertTrue(_is_system_label_id("INBOX"))

    def test_trash_is_system(self):
        self.assertTrue(_is_system_label_id("TRASH"))

    def test_category_prefix_is_system(self):
        self.assertTrue(_is_system_label_id("CATEGORY_PROMOTIONS"))

    def test_custom_label_not_system(self):
        self.assertFalse(_is_system_label_id("Label_abc123"))

    def test_inboxscout_label_id_not_system(self):
        self.assertFalse(_is_system_label_id("lbl_nl"))


# ---------------------------------------------------------------------------
# 3. _get_current_inboxscout_label
# ---------------------------------------------------------------------------

class TestGetCurrentInboxscoutLabel(unittest.TestCase):

    def test_returns_inboxscout_label(self):
        id_to_name = {"lbl_nl": "InboxScout/Newsletter", "INBOX": "INBOX"}
        result = _get_current_inboxscout_label(["INBOX", "lbl_nl"], id_to_name)
        self.assertEqual(result, "InboxScout/Newsletter")

    def test_returns_empty_when_no_inboxscout_label(self):
        id_to_name = {"INBOX": "INBOX", "UNREAD": "UNREAD"}
        result = _get_current_inboxscout_label(["INBOX", "UNREAD"], id_to_name)
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# 4. Full account run — completion reports scanned == target
# ---------------------------------------------------------------------------

class TestRunAccountEverything(unittest.TestCase):

    def _make_full_service(self, msg_ids: list[str], label_ids_on_msg: list[str] = None):
        """Mock service: lists msg_ids in one page, get returns label_ids_on_msg."""
        label_ids_on_msg = label_ids_on_msg or ["lbl_nl"]
        svc = MagicMock()
        svc.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": mid} for mid in msg_ids]
        }
        svc.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": [
                {"name": "InboxScout/Newsletter", "id": "lbl_nl"},
                {"name": "InboxScout/Promotions", "id": "lbl_pr"},
            ]
        }
        get_mock = MagicMock()
        get_mock.execute.return_value = {
            "labelIds": label_ids_on_msg,
            "payload": {"headers": [
                {"name": "From", "value": "nl@example.com"},
                {"name": "Subject", "value": "Newsletter"},
                {"name": "Date", "value": "Mon, 1 Jan 2024"},
            ]},
            "snippet": "newsletter text",
        }
        svc.users.return_value.messages.return_value.get.return_value = get_mock
        return svc

    def test_completion_scanned_equals_target(self):
        from inbox_scout import resort_everything
        msg_ids = [f"msg_{i}" for i in range(5)]
        svc = self._make_full_service(msg_ids, label_ids_on_msg=["lbl_nl"])
        classified_items = [_classified_nl() for _ in range(5)]
        with patch.object(resort_everything, "_get_readonly_service", return_value=svc), \
             patch("inbox_scout.report_mode.classify_for_report", return_value=classified_items):
            result = _run_account_everything("primary")
        self.assertEqual(result["target"], 5)
        self.assertEqual(result["scanned"], 5)
        self.assertTrue(result["complete"])
        self.assertFalse(result["capped"])

    def test_debug_cap_marks_incomplete(self):
        from inbox_scout import resort_everything
        msg_ids = [f"msg_{i}" for i in range(10)]
        svc = self._make_full_service(msg_ids)
        classified_items = [_classified_nl() for _ in range(10)]
        with patch.object(resort_everything, "_get_readonly_service", return_value=svc), \
             patch.object(resort_everything, "_debug_cap", return_value=3), \
             patch("inbox_scout.report_mode.classify_for_report", return_value=classified_items):
            result = _run_account_everything("primary")
        self.assertTrue(result["capped"])
        self.assertFalse(result["complete"])
        self.assertLessEqual(result["target"], 3)

    def test_messages_without_inboxscout_label_counted_not_moved(self):
        from inbox_scout import resort_everything
        msg_ids = ["msg_no_label"]
        svc = self._make_full_service(msg_ids, label_ids_on_msg=["INBOX"])
        classified_items = [_classified_nl()]
        with patch.object(resort_everything, "_get_readonly_service", return_value=svc), \
             patch("inbox_scout.report_mode.classify_for_report", return_value=classified_items):
            result = _run_account_everything("primary")
        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["applied"], 0)
        self.assertEqual(result["skipped_no_label"], 1)

    def test_system_labels_never_removed(self):
        """Even if an InboxScout label ID turns out to be a system label, it is not removed."""
        from inbox_scout import resort_everything
        # Patch _is_system_label_id to claim the current label's ID is a system label
        msg_ids = ["msg_sys"]
        svc = self._make_full_service(msg_ids, label_ids_on_msg=["lbl_nl"])

        classified_nl_wrong = {
            "message_id": "msg_sys",
            "from": "promo@example.com",
            "subject": "Big Sale",
            "snippet": "sale snippet",
            "ai_classification": {
                "category": "Promotion",  # mismatch: msg is in Newsletter but classified Promo
                "risk_score": 5,
                "manual_review": False,
                "protected": False,
            },
        }
        mod_svc = MagicMock()
        mod_svc.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}

        with patch.object(resort_everything, "_get_readonly_service", return_value=svc), \
             patch.object(resort_everything, "_get_modify_service", return_value=mod_svc), \
             patch("inbox_scout.report_mode.classify_for_report", return_value=[classified_nl_wrong]), \
             patch.object(resort_everything, "_is_system_label_id", return_value=True):
            result = _run_account_everything("primary")

        # Modify should never have been called to remove the "system" label
        remove_calls = [
            c for c in mod_svc.users.return_value.messages.return_value.modify.call_args_list
            if c.kwargs.get("body", {}).get("removeLabelIds")
        ]
        self.assertEqual(remove_calls, [], "System labels must never be removed")


# ---------------------------------------------------------------------------
# 5. Telegram quiet / console verbose
# ---------------------------------------------------------------------------

class TestTelegramQuietConsoleVerbose(unittest.TestCase):

    def test_on_progress_not_called_during_scan(self):
        """on_progress (Telegram) must not fire for per-batch console progress."""
        from inbox_scout import resort_everything
        svc = MagicMock()
        # Build a service with 300 messages across 6 pages of 50 so _LOG_BATCH_INTERVAL triggers
        all_ids = [f"msg_{i}" for i in range(300)]
        svc.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": mid} for mid in all_ids]
        }
        svc.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": [{"name": "InboxScout/Newsletter", "id": "lbl_nl"}]
        }
        get_mock = MagicMock()
        get_mock.execute.return_value = {
            "labelIds": ["lbl_nl"],
            "payload": {"headers": [
                {"name": "From", "value": "nl@example.com"},
                {"name": "Subject", "value": "Newsletter"},
                {"name": "Date", "value": "Mon, 1 Jan 2024"},
            ]},
            "snippet": "nl text",
        }
        svc.users.return_value.messages.return_value.get.return_value = get_mock

        progress_calls: list[str] = []
        log_calls: list[str] = []
        classified = [_classified_nl() for _ in range(50)]

        with patch.object(resort_everything, "_get_readonly_service", return_value=svc), \
             patch("inbox_scout.report_mode.classify_for_report", return_value=classified):
            _run_account_everything("primary",
                                    on_progress=progress_calls.append,
                                    on_log=log_calls.append)

        # Telegram must be silent (on_progress only fires at high milestones or errors)
        self.assertEqual(progress_calls, [], "Telegram must stay quiet during full-corpus scan")
        # Console must receive progress lines
        self.assertTrue(any("[resort-all]" in c for c in log_calls), "Console must log progress")

    def test_on_log_fires_at_progress_milestones(self):
        from inbox_scout import resort_everything
        svc = MagicMock()
        all_ids = [f"msg_{i}" for i in range(200)]
        svc.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": mid} for mid in all_ids]
        }
        svc.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": [{"name": "InboxScout/Newsletter", "id": "lbl_nl"}]
        }
        get_mock = MagicMock()
        get_mock.execute.return_value = {
            "labelIds": ["INBOX"],
            "payload": {"headers": [
                {"name": "From", "value": "x@example.com"},
                {"name": "Subject", "value": "Hello"},
                {"name": "Date", "value": "Mon, 1 Jan 2024"},
            ]},
            "snippet": "hello",
        }
        svc.users.return_value.messages.return_value.get.return_value = get_mock
        classified = [_classified_nl() for _ in range(50)]
        log_calls: list[str] = []

        with patch.object(resort_everything, "_get_readonly_service", return_value=svc), \
             patch("inbox_scout.report_mode.classify_for_report", return_value=classified):
            _run_account_everything("primary", on_log=log_calls.append)

        start = [c for c in log_calls if "collecting" in c or "unique messages" in c]
        done = [c for c in log_calls if "done" in c]
        self.assertTrue(start, "Console must log start")
        self.assertTrue(done, "Console must log completion")


# ---------------------------------------------------------------------------
# 6. Format summary — incomplete flagging
# ---------------------------------------------------------------------------

class TestFormatEverythingSummary(unittest.TestCase):

    def test_complete_shows_complete(self):
        r = [{"account": "primary", "scanned": 100, "target": 100, "applied": 3,
               "complete": True, "capped": False, "errors": 0,
               "skipped_protected": 0, "skipped_manual_review": 0,
               "skipped_high_risk": 0, "skipped_sensitive": 0, "skipped_no_label": 0,
               "apply_errors": []}]
        summary = _format_everything_summary(r)
        self.assertIn("Complete", summary)
        self.assertNotIn("INCOMPLETE", summary)

    def test_capped_shows_incomplete(self):
        r = [{"account": "primary", "scanned": 50, "target": 50, "applied": 0,
               "complete": False, "capped": True, "errors": 0,
               "skipped_protected": 0, "skipped_manual_review": 0,
               "skipped_high_risk": 0, "skipped_sensitive": 0, "skipped_no_label": 0,
               "apply_errors": []}]
        summary = _format_everything_summary(r)
        self.assertIn("INCOMPLETE", summary)
        self.assertIn("cap", summary.lower())

    def test_no_gmail_write_footer(self):
        r = [{"account": "primary", "scanned": 10, "target": 10, "applied": 0,
               "complete": True, "capped": False, "errors": 0,
               "skipped_protected": 0, "skipped_manual_review": 0,
               "skipped_high_risk": 0, "skipped_sensitive": 0, "skipped_no_label": 0,
               "apply_errors": []}]
        summary = _format_everything_summary(r)
        self.assertIn("Labels corrected only", summary)
        self.assertNotIn("move to trash", summary.lower())

    def test_combined_line_when_two_accounts(self):
        r = [
            {"account": "primary", "scanned": 100, "target": 100, "applied": 2,
             "complete": True, "capped": False, "errors": 0,
             "skipped_protected": 0, "skipped_manual_review": 0,
             "skipped_high_risk": 0, "skipped_sensitive": 0, "skipped_no_label": 0,
             "apply_errors": []},
            {"account": "secondary", "scanned": 50, "target": 50, "applied": 1,
             "complete": True, "capped": False, "errors": 0,
             "skipped_protected": 0, "skipped_manual_review": 0,
             "skipped_high_risk": 0, "skipped_sensitive": 0, "skipped_no_label": 0,
             "apply_errors": []},
        ]
        summary = _format_everything_summary(r)
        self.assertIn("150/150", summary)
        self.assertIn("Combined", summary)


if __name__ == "__main__":
    unittest.main()
