"""
Inbox-zero autopilot routing and behavior tests.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_inbox_zero_autopilot -v
"""
from __future__ import annotations

import os
import sys
import unittest
import unittest.mock
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
    def test_emergency_cap_greater_than_250(self):
        from inbox_scout.autopilot_cleanup import AUTOPILOT_EMERGENCY_CAP
        self.assertGreater(AUTOPILOT_EMERGENCY_CAP, 250)

    def test_emergency_cap_at_least_1000(self):
        from inbox_scout.autopilot_cleanup import AUTOPILOT_EMERGENCY_CAP
        self.assertGreaterEqual(AUTOPILOT_EMERGENCY_CAP, 1000)

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


class TestRunInboxZeroAutopilotFullInbox(unittest.TestCase):
    """sort all must process the full inbox without artificial 250-email cap."""

    def _base_patches(self, ac, n_batches: int, items_per_batch: int = 25):
        """Return a dict of patch kwargs that simulate n_batches then empty."""
        call_count = [0]

        def fake_items():
            call_count[0] += 1
            if call_count[0] <= n_batches:
                return [{"gmail_message_id": f"M{call_count[0]}_{i}", "category": "newsletter", "risk_score": 5}
                        for i in range(items_per_batch)]
            return []

        mock_plan = MagicMock()
        mock_plan.workflow_mode = "commands_planned"
        mock_plan.requested_limit = 25

        mock_cleanup = MagicMock()
        mock_cleanup.trash_candidate_count = 0

        return dict(
            _get_modify_service_for_autopilot=MagicMock(return_value=MagicMock()),
            _get_unread_inbox_count=MagicMock(return_value=n_batches * items_per_batch),
            build_scan_queue_plan=MagicMock(return_value=mock_plan),
            save_plan=MagicMock(),
            _run_scan=MagicMock(return_value=MagicMock(returncode=0)),
            _load_json=MagicMock(return_value={"status": "complete"}),
            _load_items_from_queue=MagicMock(side_effect=fake_items),
            build_inbox_cleanup_plan=MagicMock(return_value=mock_cleanup),
            _process_non_trash_items=MagicMock(return_value={
                "labeled": items_per_batch, "archived": 0,
                "marked_read": items_per_batch, "protected": 0, "errors": 0,
            }),
            _beep_once=MagicMock(),
        )

    def test_sort_all_shows_starting_unread_count(self):
        from inbox_scout import autopilot_cleanup as ac
        patches = self._base_patches(ac, n_batches=1, items_per_batch=25)
        patches["_get_unread_inbox_count"] = MagicMock(return_value=42)
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup", **patches):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertIn("Starting unread: 42", result)

    def test_sort_all_can_exceed_250(self):
        from inbox_scout import autopilot_cleanup as ac
        patches = self._base_patches(ac, n_batches=11, items_per_batch=25)  # 275 total
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup", **patches):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertIn("Scanned: 275", result)

    def test_no_safety_cap_250_in_normal_completion(self):
        from inbox_scout import autopilot_cleanup as ac
        patches = self._base_patches(ac, n_batches=2)
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup", **patches):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertNotIn("Safety cap", result)
        self.assertNotIn("Run again to continue", result)

    def test_loops_multiple_batches_without_confirmation(self):
        from inbox_scout import autopilot_cleanup as ac
        scan_calls = [0]

        original_patches = self._base_patches(ac, n_batches=3)

        def count_scan():
            scan_calls[0] += 1
            return MagicMock(returncode=0)

        original_patches["_run_scan"] = MagicMock(side_effect=count_scan)
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup", **original_patches):
            ac.run_inbox_zero_autopilot("sort all")
        self.assertGreaterEqual(scan_calls[0], 3)

    def test_stops_when_unread_zero(self):
        from inbox_scout import autopilot_cleanup as ac
        mock_plan = MagicMock()
        mock_plan.workflow_mode = "commands_planned"
        mock_plan.requested_limit = 25
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup",
                _get_modify_service_for_autopilot=MagicMock(return_value=MagicMock()),
                _get_unread_inbox_count=MagicMock(return_value=0),
                build_scan_queue_plan=MagicMock(return_value=mock_plan),
                save_plan=MagicMock(),
                _run_scan=MagicMock(return_value=MagicMock(returncode=0)),
                _load_json=MagicMock(return_value={"status": "complete"}),
                _load_items_from_queue=MagicMock(return_value=[]),
                _beep_once=MagicMock()):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertIn("Scanned: 0", result)
        self.assertIn("Nothing permanently deleted", result)

    def test_emergency_cap_not_hit_for_2000_inbox(self):
        from inbox_scout import autopilot_cleanup as ac
        patches = self._base_patches(ac, n_batches=80, items_per_batch=25)  # 2000 total
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup", **patches):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertIn("Scanned: 2000", result)
        self.assertNotIn("Emergency runaway cap", result)
        self.assertNotIn("Run again", result)

    def test_complete_message_on_normal_finish(self):
        from inbox_scout import autopilot_cleanup as ac
        patches = self._base_patches(ac, n_batches=2)
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup", **patches):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertIn("Inbox Zero complete.", result)


class TestParseTrashedCount(unittest.TestCase):
    def setUp(self):
        from inbox_scout.autopilot_cleanup import _parse_trashed_count
        self.parse = _parse_trashed_count

    def test_parse_5_moved(self):
        self.assertEqual(self.parse("Done. Moved 5 email(s) to Gmail Trash for review."), 5)

    def test_parse_1_moved(self):
        self.assertEqual(self.parse("Done. Moved 1 email(s) to Gmail Trash for review."), 1)

    def test_parse_zero_on_no_match(self):
        self.assertEqual(self.parse("No candidates passed safety validation.\n\nGmail not touched."), 0)

    def test_parse_zero_on_error_msg(self):
        self.assertEqual(self.parse("Cleanup move failed.\n\nGmail not touched."), 0)


class TestLabelFailNoMarkRead(unittest.TestCase):
    def test_label_fail_skips_mark_read(self):
        """If label lookup/create fails, email must not be marked read."""
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = MagicMock()
        svc.users().labels().list.return_value.execute.side_effect = Exception("label API error")
        items = [{"gmail_message_id": "MSG099", "category": "finance", "risk_score": 10}]
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["marked_read"], 0)
        svc.users().messages().modify.assert_not_called()


class TestUncertainEmailGetsReviewLabel(unittest.TestCase):
    def _make_service(self):
        svc = MagicMock()
        svc.users().labels().list(userId="me").execute.return_value = {"labels": []}
        svc.users().labels().create.return_value.execute.return_value = {"id": "Label_review"}
        svc.users().messages().modify.return_value.execute.return_value = {}
        return svc

    def test_uncertain_labeled_review_and_marked_read(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [{"gmail_message_id": "MSG010", "category": "unknown_xyz", "risk_score": 50}]
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["labeled"], 1)
        self.assertEqual(result["marked_read"], 1)
        create_call = svc.users().labels().create.call_args
        self.assertIn("InboxScout/Review", str(create_call))


class TestAutopilotLoopAlwaysPageOne(unittest.TestCase):
    def test_loop_never_passes_continuation(self):
        """Loop must always call build_scan_queue_plan without continuation=True."""
        from unittest.mock import patch, MagicMock
        from inbox_scout import autopilot_cleanup

        continuation_values = []

        def capture_plan(msg, continuation=False, cleanup_mode=False):
            continuation_values.append(continuation)
            p = MagicMock()
            p.workflow_mode = "commands_planned"
            p.requested_limit = 5
            return p

        with (
            patch.object(autopilot_cleanup, "build_scan_queue_plan", side_effect=capture_plan),
            patch.object(autopilot_cleanup, "save_plan"),
            patch.object(autopilot_cleanup, "_run_scan", return_value=MagicMock(returncode=0)),
            patch.object(autopilot_cleanup, "_load_json", return_value={"status": "complete"}),
            patch.object(autopilot_cleanup, "_load_items_from_queue", return_value=[]),
            patch.object(autopilot_cleanup, "_get_modify_service_for_autopilot", return_value=MagicMock()),
        ):
            autopilot_cleanup.run_inbox_zero_autopilot("sort all")

        self.assertGreater(len(continuation_values), 0)
        self.assertTrue(all(not c for c in continuation_values),
                        "Loop must never use continuation=True")

    def test_loop_stops_when_scan_returns_empty(self):
        """Loop stops when scan returns 0 items (inbox empty), not via cursor check."""
        from unittest.mock import patch, MagicMock
        from inbox_scout import autopilot_cleanup

        mock_plan = MagicMock()
        mock_plan.workflow_mode = "commands_planned"
        mock_plan.requested_limit = 5

        with (
            patch.object(autopilot_cleanup, "build_scan_queue_plan", return_value=mock_plan),
            patch.object(autopilot_cleanup, "save_plan"),
            patch.object(autopilot_cleanup, "_run_scan", return_value=MagicMock(returncode=0)),
            patch.object(autopilot_cleanup, "_load_json", return_value={"status": "complete"}),
            patch.object(autopilot_cleanup, "_load_items_from_queue", return_value=[]),
            patch.object(autopilot_cleanup, "_get_modify_service_for_autopilot", return_value=MagicMock()),
        ):
            result = autopilot_cleanup.run_inbox_zero_autopilot("sort all")

        self.assertIn("Scanned: 0", result)
        self.assertIn("Nothing permanently deleted", result)


if __name__ == "__main__":
    unittest.main()
