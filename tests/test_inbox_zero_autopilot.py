"""
Inbox-zero autopilot routing and behavior tests.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_inbox_zero_autopilot -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestInboxZeroRouting(unittest.TestCase):
    """sort all and variants must route to run_inbox_zero_autopilot, not sort_plan_message."""

    def _assert_routes_to_inbox_zero(self, phrase: str) -> None:
        from inbox_scout import natural_intent

        called = []

        def fake_inbox_zero(text: str) -> str:
            called.append(text)
            return "inbox_zero called"

        with patch("inbox_scout.natural_intent.run_inbox_zero_autopilot", fake_inbox_zero):
            result = natural_intent.handle_natural_message(phrase)

        self.assertEqual(result, "inbox_zero called", f"Expected inbox-zero autopilot for: {phrase!r}")
        self.assertEqual(len(called), 1)

    def test_sort_all(self):
        self._assert_routes_to_inbox_zero("sort all")

    def test_clean_all(self):
        self._assert_routes_to_inbox_zero("clean all")

    def test_get_me_to_inbox_zero(self):
        self._assert_routes_to_inbox_zero("get me to inbox zero")

    def test_file_my_inbox(self):
        self._assert_routes_to_inbox_zero("file my inbox")

    def test_sort_my_whole_inbox(self):
        self._assert_routes_to_inbox_zero("sort my whole inbox")

    def test_clean_my_whole_inbox(self):
        self._assert_routes_to_inbox_zero("clean my whole inbox")

    def test_sort_all_does_not_call_sort_plan_message(self):
        from inbox_scout import natural_intent

        sort_plan_calls = []

        with (
            patch("inbox_scout.natural_intent.run_inbox_zero_autopilot", return_value="inbox_zero"),
            patch(
                "inbox_scout.natural_intent.sort_plan_message",
                side_effect=lambda *a, **kw: sort_plan_calls.append(a) or "sort_plan",
            ),
        ):
            natural_intent.handle_natural_message("sort all")

        self.assertEqual(sort_plan_calls, [], "sort_plan_message must not be called for 'sort all'")

    def test_sort_all_response_has_no_yes_prompt(self):
        from inbox_scout import natural_intent

        with patch("inbox_scout.natural_intent.run_inbox_zero_autopilot", return_value="Inbox Zero complete."):
            result = natural_intent.handle_natural_message("sort all")

        self.assertNotIn("reply yes", result.lower())
        self.assertNotIn("scan the first 5", result.lower())
        self.assertNotIn("scan 5 unread", result.lower())

    def test_clean_my_inbox_still_routes_to_autopilot_cleanup(self):
        """clean my inbox (no 'whole') must stay on run_autopilot_cleanup, not inbox-zero."""
        from inbox_scout import natural_intent

        called = {}

        def fake_inbox_zero(text):
            called["inbox_zero"] = True
            return "inbox_zero"

        def fake_autopilot(text):
            called["autopilot"] = True
            return "autopilot"

        with (
            patch("inbox_scout.natural_intent.run_inbox_zero_autopilot", fake_inbox_zero),
            patch("inbox_scout.natural_intent.run_autopilot_cleanup", fake_autopilot),
        ):
            natural_intent.handle_natural_message("clean my inbox")

        self.assertNotIn("inbox_zero", called, "clean my inbox must NOT route to inbox-zero")
        self.assertIn("autopilot", called, "clean my inbox must route to run_autopilot_cleanup")


class TestInboxZeroCap(unittest.TestCase):
    def test_autopilot_sort_all_max_greater_than_5(self):
        from inbox_scout.autopilot_cleanup import AUTOPILOT_SORT_ALL_MAX
        self.assertGreater(AUTOPILOT_SORT_ALL_MAX, 5)

    def test_autopilot_sort_all_max_at_least_50(self):
        from inbox_scout.autopilot_cleanup import AUTOPILOT_SORT_ALL_MAX
        self.assertGreaterEqual(AUTOPILOT_SORT_ALL_MAX, 50)

    def test_inbox_zero_phrases_contains_sort_all(self):
        from inbox_scout.natural_intent import _INBOX_ZERO_PHRASES
        self.assertIn("sort all", _INBOX_ZERO_PHRASES)


class TestIsInboxZeroHelper(unittest.TestCase):
    def setUp(self):
        from inbox_scout.natural_intent import _is_inbox_zero
        self.check = _is_inbox_zero

    def test_sort_all_matches(self):
        self.assertTrue(self.check("sort all"))

    def test_clean_all_matches(self):
        self.assertTrue(self.check("clean all"))

    def test_get_me_to_inbox_zero_matches(self):
        self.assertTrue(self.check("get me to inbox zero"))

    def test_file_my_inbox_matches(self):
        self.assertTrue(self.check("file my inbox"))

    def test_sort_my_whole_inbox_matches(self):
        self.assertTrue(self.check("sort my whole inbox"))

    def test_clean_my_whole_inbox_matches(self):
        self.assertTrue(self.check("clean my whole inbox"))

    def test_sort_5_emails_does_not_match(self):
        self.assertFalse(self.check("sort 5 emails"))

    def test_clean_my_inbox_does_not_match(self):
        self.assertFalse(self.check("clean my inbox"))

    def test_yes_does_not_match(self):
        self.assertFalse(self.check("yes"))

    def test_cancel_does_not_match(self):
        self.assertFalse(self.check("cancel"))


class TestPickInboxScoutLabel(unittest.TestCase):
    def setUp(self):
        from inbox_scout.autopilot_cleanup import _pick_inboxscout_label
        self.pick = _pick_inboxscout_label

    def test_receipt(self):
        self.assertEqual(self.pick({"category": "receipt"}), "InboxScout/Receipts")

    def test_security(self):
        self.assertEqual(self.pick({"category": "security"}), "InboxScout/Security")

    def test_finance(self):
        self.assertEqual(self.pick({"category": "finance"}), "InboxScout/Finance")

    def test_job(self):
        self.assertEqual(self.pick({"category": "job"}), "InboxScout/Jobs")

    def test_account(self):
        self.assertEqual(self.pick({"category": "account"}), "InboxScout/Accounts")

    def test_unknown_defaults_to_review(self):
        self.assertEqual(self.pick({"category": "unknown_xyz"}), "InboxScout/Review")

    def test_empty_defaults_to_review(self):
        self.assertEqual(self.pick({}), "InboxScout/Review")

    def test_compound_job_interview(self):
        self.assertEqual(self.pick({"category": "job/interview"}), "InboxScout/Jobs")


class TestProcessNonTrashItems(unittest.TestCase):
    def _make_service(self, existing_labels=None):
        svc = MagicMock()
        svc.users().labels().list(userId="me").execute.return_value = {
            "labels": existing_labels or []
        }
        svc.users().labels().create.return_value.execute.return_value = {"id": "Label_new"}
        svc.users().messages().modify.return_value.execute.return_value = {}
        return svc

    def test_mark_read_called_for_non_trash_item(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [{"gmail_message_id": "MSG001", "category": "newsletter", "risk_score": 20}]
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["marked_read"], 1)
        call_args = svc.users().messages().modify.call_args
        self.assertIn("UNREAD", call_args.kwargs["body"]["removeLabelIds"])

    def test_trashed_items_skipped(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [{"gmail_message_id": "MSG001", "gmail_trashed": True, "category": "newsletter"}]
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["marked_read"], 0)
        self.assertEqual(result["labeled"], 0)
        svc.users().messages().modify.assert_not_called()

    def test_non_trash_item_gets_label(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service([{"name": "InboxScout/Review", "id": "Label_review"}])
        items = [{"gmail_message_id": "MSG001", "category": "transactional", "risk_score": 50}]
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["labeled"], 1)

    def test_safe_newsletter_archived(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [{"gmail_message_id": "MSG002", "category": "newsletter", "risk_score": 10}]
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["archived"], 1)
        call_args = svc.users().messages().modify.call_args
        self.assertIn("INBOX", call_args.kwargs["body"]["removeLabelIds"])

    def test_protected_item_not_archived(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [{
            "gmail_message_id": "MSG003",
            "category": "newsletter",
            "risk_score": 10,
            "local_decision": "protected_review",
        }]
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["archived"], 0)
        self.assertEqual(result["protected"], 1)
        call_args = svc.users().messages().modify.call_args
        remove_labels = call_args.kwargs["body"]["removeLabelIds"]
        self.assertNotIn("INBOX", remove_labels, "Protected items must not have INBOX removed")

    def test_protected_item_marked_read(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [{
            "gmail_message_id": "MSG004",
            "category": "finance",
            "risk_score": 10,
            "manual_review": True,
        }]
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["marked_read"], 1, "Protected items should still be marked read")

    def test_protected_item_not_permanently_deleted(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [{
            "gmail_message_id": "MSG005",
            "category": "finance",
            "risk_score": 10,
            "manual_review": True,
        }]
        _process_non_trash_items(svc, items, {})

        svc.users().messages().delete.assert_not_called()

    def test_no_permanently_deleted_for_any_item(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [
            {"gmail_message_id": "MSG006", "category": "newsletter", "risk_score": 5},
            {"gmail_message_id": "MSG007", "category": "finance", "risk_score": 5, "manual_review": True},
        ]
        _process_non_trash_items(svc, items, {})

        svc.users().messages().delete.assert_not_called()

    def test_manual_review_item_not_archived(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [{
            "gmail_message_id": "MSG008",
            "category": "newsletter",
            "risk_score": 5,
            "manual_review": True,
        }]
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["archived"], 0)
        call_args = svc.users().messages().modify.call_args
        remove_labels = call_args.kwargs["body"]["removeLabelIds"]
        self.assertNotIn("INBOX", remove_labels, "manual_review items must not be archived")

    def test_items_missing_message_id_counted_as_errors(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [{"category": "newsletter", "risk_score": 5}]  # no message ID
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["marked_read"], 0)
        svc.users().messages().modify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
