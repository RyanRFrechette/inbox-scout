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
    """sort all and variants must route to _run_both_inbox_zero (both accounts) by default."""

    def _assert_routes_to_inbox_zero(self, phrase: str) -> None:
        from inbox_scout import natural_intent

        called = []

        def fake_both(text: str) -> str:
            called.append(text)
            return "inbox_zero called"

        with patch("inbox_scout.natural_intent._run_both_inbox_zero", fake_both):
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

        def fake_inbox_zero(text, account="primary"):
            called["inbox_zero"] = True
            return "inbox_zero"

        def fake_autopilot(text, account="primary"):
            called["autopilot"] = True
            return "autopilot"

        with (
            patch("inbox_scout.natural_intent.run_inbox_zero_autopilot", fake_inbox_zero),
            patch("inbox_scout.natural_intent.run_autopilot_cleanup", fake_autopilot),
        ):
            natural_intent.handle_natural_message("clean my inbox")

        self.assertNotIn("inbox_zero", called, "clean my inbox must NOT route to inbox-zero")
        self.assertIn("autopilot", called, "clean my inbox must route to run_autopilot_cleanup")


class TestInboxZeroAccountRouting(unittest.TestCase):
    """Bare sort all defaults to both; explicit primary/secondary routes to one account."""

    def test_sort_all_routes_to_both_accounts(self):
        from inbox_scout import natural_intent
        called = []

        def fake_both(text):
            called.append("both")
            return "both called"

        with patch("inbox_scout.natural_intent._run_both_inbox_zero", fake_both):
            result = natural_intent.handle_natural_message("sort all")

        self.assertEqual(called, ["both"], "bare 'sort all' must route to both accounts")
        self.assertEqual(result, "both called")

    def test_sort_primary_routes_to_primary_only(self):
        from inbox_scout import natural_intent
        accounts = []

        def fake_single(text, account="primary"):
            accounts.append(account)
            return f"single called {account}"

        with patch("inbox_scout.natural_intent.run_inbox_zero_autopilot", fake_single):
            result = natural_intent.handle_natural_message("sort all primary email")

        self.assertEqual(accounts, ["primary"])
        self.assertIn("primary", result)

    def test_sort_secondary_routes_to_secondary_only(self):
        from inbox_scout import natural_intent
        accounts = []

        def fake_single(text, account="primary"):
            accounts.append(account)
            return f"single called {account}"

        with patch("inbox_scout.natural_intent.run_inbox_zero_autopilot", fake_single):
            result = natural_intent.handle_natural_message("sort all secondary email")

        self.assertEqual(accounts, ["secondary"])
        self.assertIn("secondary", result)


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

    def test_protected_item_archived_after_label(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [{
            "gmail_message_id": "MSG003",
            "category": "newsletter",
            "risk_score": 10,
            "local_decision": "protected_review",
        }]
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["archived"], 1, "Protected items must be archived after label success")
        self.assertEqual(result["protected"], 1)
        call_args = svc.users().messages().modify.call_args
        remove_labels = call_args.kwargs["body"]["removeLabelIds"]
        self.assertIn("INBOX", remove_labels, "Protected items must have INBOX removed after label success")

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

    def test_manual_review_item_archived_after_label(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items

        svc = self._make_service()
        items = [{
            "gmail_message_id": "MSG008",
            "category": "newsletter",
            "risk_score": 5,
            "manual_review": True,
        }]
        result = _process_non_trash_items(svc, items, {})

        self.assertEqual(result["archived"], 1, "manual_review items must be archived after label success")
        call_args = svc.users().messages().modify.call_args
        remove_labels = call_args.kwargs["body"]["removeLabelIds"]
        self.assertIn("INBOX", remove_labels, "manual_review items must have INBOX removed after label success")

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
            _get_total_inbox_count=MagicMock(return_value=n_batches * items_per_batch),
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

        def count_scan(account="primary"):
            scan_calls[0] += 1
            return MagicMock(returncode=0)

        original_patches["_run_scan"] = MagicMock(side_effect=count_scan)
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup", **original_patches):
            ac.run_inbox_zero_autopilot("sort all")
        self.assertGreaterEqual(scan_calls[0], 3)

    def test_stops_when_unread_zero_inbox_empty(self):
        from inbox_scout import autopilot_cleanup as ac
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup",
                _get_modify_service_for_autopilot=MagicMock(return_value=MagicMock()),
                _get_unread_inbox_count=MagicMock(return_value=0),
                _get_total_inbox_count=MagicMock(return_value=0),
                _beep_once=MagicMock()):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertIn("Inbox is empty", result)
        self.assertIn("Gmail not touched", result)

    def test_no_unread_but_read_emails_remain_singular(self):
        from inbox_scout import autopilot_cleanup as ac
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup",
                _get_modify_service_for_autopilot=MagicMock(return_value=MagicMock()),
                _get_unread_inbox_count=MagicMock(return_value=0),
                _get_total_inbox_count=MagicMock(return_value=1),
                _beep_once=MagicMock()):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertIn("No unread inbox emails to process", result)
        self.assertIn("1 read inbox email remains", result)
        self.assertIn("Gmail not touched", result)
        self.assertNotIn("error midway", result)
        self.assertNotIn("Couldn't process", result)

    def test_no_unread_but_read_emails_remain_plural(self):
        from inbox_scout import autopilot_cleanup as ac
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup",
                _get_modify_service_for_autopilot=MagicMock(return_value=MagicMock()),
                _get_unread_inbox_count=MagicMock(return_value=0),
                _get_total_inbox_count=MagicMock(return_value=5),
                _beep_once=MagicMock()):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertIn("No unread inbox emails to process", result)
        self.assertIn("5 read inbox emails remain", result)
        self.assertIn("Gmail not touched", result)

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
            patch.object(autopilot_cleanup, "_get_unread_inbox_count", return_value=5),
            patch.object(autopilot_cleanup, "_get_total_inbox_count", return_value=5),
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
            patch.object(autopilot_cleanup, "_get_unread_inbox_count", return_value=0),
            patch.object(autopilot_cleanup, "_get_total_inbox_count", return_value=0),
        ):
            result = autopilot_cleanup.run_inbox_zero_autopilot("sort all")

        self.assertIn("Inbox is empty", result)
        self.assertIn("Gmail not touched", result)


class TestLabelList(unittest.TestCase):
    """All required InboxScout labels must be present in INBOX_SCOUT_LABELS."""

    def setUp(self):
        from inbox_scout.label_manager import INBOX_SCOUT_LABELS
        self.labels = INBOX_SCOUT_LABELS

    def _assert_label(self, name: str) -> None:
        self.assertIn(name, self.labels, f"Missing label: {name}")

    def test_receipts(self): self._assert_label("InboxScout/Receipts")
    def test_shopping_history(self): self._assert_label("InboxScout/Shopping-History")
    def test_shipping_returns(self): self._assert_label("InboxScout/Shipping-Returns")
    def test_security(self): self._assert_label("InboxScout/Security")
    def test_finance(self): self._assert_label("InboxScout/Finance")
    def test_accounts(self): self._assert_label("InboxScout/Accounts")
    def test_jobs(self): self._assert_label("InboxScout/Jobs")
    def test_work_business(self): self._assert_label("InboxScout/Work-Business")
    def test_personal(self): self._assert_label("InboxScout/Personal")
    def test_medical(self): self._assert_label("InboxScout/Medical")
    def test_legal_tax(self): self._assert_label("InboxScout/Legal-Tax")
    def test_subscriptions(self): self._assert_label("InboxScout/Subscriptions")
    def test_newsletters(self): self._assert_label("InboxScout/Newsletters")
    def test_promotions(self): self._assert_label("InboxScout/Promotions")
    def test_social_notifications(self): self._assert_label("InboxScout/Social-Notifications")
    def test_school_learning(self): self._assert_label("InboxScout/School-Learning")
    def test_ai_dev_tools(self): self._assert_label("InboxScout/AI-Dev-Tools")
    def test_review(self): self._assert_label("InboxScout/Review")
    def test_trash_candidates(self): self._assert_label("InboxScout/Trash-Candidates")


class TestCategoryMappingExpanded(unittest.TestCase):
    """All new category mappings must route to the correct InboxScout label."""

    def setUp(self):
        from inbox_scout.autopilot_cleanup import _pick_inboxscout_label
        self.pick = _pick_inboxscout_label

    # Receipts — must NOT go to Finance
    def test_invoice_to_receipts(self):
        self.assertEqual(self.pick({"category": "invoice"}), "InboxScout/Receipts")

    def test_payment_to_receipts(self):
        self.assertEqual(self.pick({"category": "payment"}), "InboxScout/Receipts")

    def test_bill_to_receipts(self):
        self.assertEqual(self.pick({"category": "bill"}), "InboxScout/Receipts")

    def test_order_confirmation_to_receipts(self):
        self.assertEqual(self.pick({"category": "order confirmation"}), "InboxScout/Receipts")

    def test_purchase_confirmation_to_receipts(self):
        self.assertEqual(self.pick({"category": "purchase confirmation"}), "InboxScout/Receipts")

    # Shopping-History
    def test_order_to_shopping_history(self):
        self.assertEqual(self.pick({"category": "order"}), "InboxScout/Shopping-History")

    def test_delivered_to_shopping_history(self):
        self.assertEqual(self.pick({"category": "delivered"}), "InboxScout/Shopping-History")

    def test_order_delivered_to_shopping_history(self):
        self.assertEqual(self.pick({"category": "order delivered"}), "InboxScout/Shopping-History")

    # Shipping-Returns — must NOT go to Shopping-History
    def test_shipment_to_shipping_returns(self):
        self.assertEqual(self.pick({"category": "shipment"}), "InboxScout/Shipping-Returns")

    def test_shipping_to_shipping_returns(self):
        self.assertEqual(self.pick({"category": "shipping"}), "InboxScout/Shipping-Returns")

    def test_tracking_to_shipping_returns(self):
        self.assertEqual(self.pick({"category": "tracking"}), "InboxScout/Shipping-Returns")

    def test_refund_to_shipping_returns(self):
        self.assertEqual(self.pick({"category": "refund"}), "InboxScout/Shipping-Returns")

    def test_return_to_shipping_returns(self):
        self.assertEqual(self.pick({"category": "return"}), "InboxScout/Shipping-Returns")

    # Finance — still correct for banks/tax/insurance
    def test_finance_to_finance(self):
        self.assertEqual(self.pick({"category": "finance"}), "InboxScout/Finance")

    def test_bank_to_finance(self):
        self.assertEqual(self.pick({"category": "bank"}), "InboxScout/Finance")

    def test_tax_to_finance(self):
        self.assertEqual(self.pick({"category": "tax"}), "InboxScout/Finance")

    def test_insurance_to_finance(self):
        self.assertEqual(self.pick({"category": "insurance"}), "InboxScout/Finance")

    # AI-Dev-Tools — must NOT go to Review
    def test_github_to_ai_dev_tools(self):
        self.assertEqual(self.pick({"category": "github"}), "InboxScout/AI-Dev-Tools")

    def test_anthropic_to_ai_dev_tools(self):
        self.assertEqual(self.pick({"category": "anthropic"}), "InboxScout/AI-Dev-Tools")

    def test_openai_to_ai_dev_tools(self):
        self.assertEqual(self.pick({"category": "openai"}), "InboxScout/AI-Dev-Tools")

    # Social-Notifications — must NOT go to Review
    def test_reddit_to_social(self):
        self.assertEqual(self.pick({"category": "reddit"}), "InboxScout/Social-Notifications")

    def test_discord_to_social(self):
        self.assertEqual(self.pick({"category": "discord"}), "InboxScout/Social-Notifications")

    def test_social_to_social(self):
        self.assertEqual(self.pick({"category": "social"}), "InboxScout/Social-Notifications")

    # Newsletters — must NOT go to Review
    def test_newsletter_to_newsletters(self):
        self.assertEqual(self.pick({"category": "newsletter"}), "InboxScout/Newsletters")

    def test_digest_to_newsletters(self):
        self.assertEqual(self.pick({"category": "digest"}), "InboxScout/Newsletters")

    # Promotions — must NOT go to Review
    def test_promotion_to_promotions(self):
        self.assertEqual(self.pick({"category": "promotion"}), "InboxScout/Promotions")

    def test_marketing_to_promotions(self):
        self.assertEqual(self.pick({"category": "marketing"}), "InboxScout/Promotions")

    # Subscriptions
    def test_subscription_to_subscriptions(self):
        self.assertEqual(self.pick({"category": "subscription"}), "InboxScout/Subscriptions")

    def test_renewal_to_subscriptions(self):
        self.assertEqual(self.pick({"category": "renewal"}), "InboxScout/Subscriptions")

    # Medical
    def test_medical_to_medical(self):
        self.assertEqual(self.pick({"category": "medical"}), "InboxScout/Medical")

    def test_doctor_to_medical(self):
        self.assertEqual(self.pick({"category": "doctor"}), "InboxScout/Medical")

    # Legal-Tax
    def test_legal_to_legal_tax(self):
        self.assertEqual(self.pick({"category": "legal"}), "InboxScout/Legal-Tax")

    def test_irs_to_legal_tax(self):
        self.assertEqual(self.pick({"category": "irs"}), "InboxScout/Legal-Tax")

    # Accounts
    def test_account_update_to_accounts(self):
        self.assertEqual(self.pick({"category": "account update"}), "InboxScout/Accounts")

    # Uncertain → Review
    def test_uncertain_to_review(self):
        self.assertEqual(self.pick({"category": "totally_unknown_xyz"}), "InboxScout/Review")


class TestAlwaysRemoveInboxOnLabel(unittest.TestCase):
    """Non-protected items must always have INBOX removed after successful label."""

    def _make_service(self):
        svc = MagicMock()
        svc.users().labels().list(userId="me").execute.return_value = {"labels": []}
        svc.users().labels().create.return_value.execute.return_value = {"id": "Label_x"}
        svc.users().messages().modify.return_value.execute.return_value = {}
        return svc

    def test_any_non_protected_item_removes_inbox(self):
        from inbox_scout.autopilot_cleanup import _process_non_trash_items
        svc = self._make_service()
        items = [{"gmail_message_id": "MSG_NP", "category": "finance", "risk_score": 80}]
        result = _process_non_trash_items(svc, items, {})
        self.assertEqual(result["archived"], 1)
        call_args = svc.users().messages().modify.call_args
        self.assertIn("INBOX", call_args.kwargs["body"]["removeLabelIds"])

    def test_read_email_still_gets_label_and_inbox_removed(self):
        """Already-read inbox items must be labeled and have INBOX removed."""
        from inbox_scout.autopilot_cleanup import _process_non_trash_items
        svc = self._make_service()
        items = [{"gmail_message_id": "MSG_READ", "category": "newsletter", "risk_score": 5}]
        result = _process_non_trash_items(svc, items, {})
        self.assertEqual(result["labeled"], 1)
        call_args = svc.users().messages().modify.call_args
        remove_labels = call_args.kwargs["body"]["removeLabelIds"]
        self.assertIn("INBOX", remove_labels)

    def test_protected_item_has_inbox_removed(self):
        """Protected items must have INBOX removed after label success (archiving is recoverable)."""
        from inbox_scout.autopilot_cleanup import _process_non_trash_items
        svc = self._make_service()
        items = [{
            "gmail_message_id": "MSG_PROT",
            "category": "newsletter",
            "risk_score": 5,
            "local_decision": "protected_review",
        }]
        result = _process_non_trash_items(svc, items, {})
        self.assertEqual(result["archived"], 1)
        call_args = svc.users().messages().modify.call_args
        remove_labels = call_args.kwargs["body"]["removeLabelIds"]
        self.assertIn("INBOX", remove_labels, "Protected items must have INBOX removed after label success")

    def test_label_fail_does_not_remove_inbox(self):
        """If label lookup fails, INBOX must not be removed."""
        from inbox_scout.autopilot_cleanup import _process_non_trash_items
        svc = MagicMock()
        svc.users().labels().list.return_value.execute.side_effect = Exception("API error")
        items = [{"gmail_message_id": "MSG_FAIL", "category": "newsletter", "risk_score": 5}]
        result = _process_non_trash_items(svc, items, {})
        self.assertEqual(result["errors"], 1)
        svc.users().messages().modify.assert_not_called()

    def test_modify_call_fail_does_not_count_as_archived(self):
        """If the Gmail modify call fails, item must not be counted as archived."""
        from inbox_scout.autopilot_cleanup import _process_non_trash_items
        svc = MagicMock()
        svc.users().labels().list(userId="me").execute.return_value = {"labels": []}
        svc.users().labels().create.return_value.execute.return_value = {"id": "Label_x"}
        svc.users().messages().modify.return_value.execute.side_effect = Exception("modify failed")
        items = [{"gmail_message_id": "MSG_MODIFAIL", "category": "newsletter", "risk_score": 5}]
        result = _process_non_trash_items(svc, items, {})
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["archived"], 0, "Failed modify must not increment archived count")
        self.assertEqual(result["labeled"], 0)


class TestSortAllScansTotalInbox(unittest.TestCase):
    """sort all must count and scan the full inbox, not just unread."""

    def _base_patches(self, n_batches=1, items_per_batch=5):
        call_count = [0]

        def fake_items():
            call_count[0] += 1
            if call_count[0] <= n_batches:
                return [{"gmail_message_id": f"I{call_count[0]}_{i}", "category": "newsletter", "risk_score": 5}
                        for i in range(items_per_batch)]
            return []

        mock_plan = MagicMock()
        mock_plan.workflow_mode = "commands_planned"
        mock_plan.requested_limit = 25
        mock_plan.target = "unread_inbox"

        mock_cleanup = MagicMock()
        mock_cleanup.trash_candidate_count = 0

        return dict(
            _get_modify_service_for_autopilot=MagicMock(return_value=MagicMock()),
            _get_unread_inbox_count=MagicMock(return_value=3),
            _get_total_inbox_count=MagicMock(return_value=n_batches * items_per_batch),
            build_scan_queue_plan=MagicMock(return_value=mock_plan),
            save_plan=MagicMock(),
            _run_scan=MagicMock(return_value=MagicMock(returncode=0)),
            _load_json=MagicMock(return_value={"status": "complete"}),
            _load_items_from_queue=MagicMock(side_effect=fake_items),
            build_inbox_cleanup_plan=MagicMock(return_value=mock_cleanup),
            _process_non_trash_items=MagicMock(return_value={
                "labeled": items_per_batch, "archived": items_per_batch,
                "marked_read": items_per_batch, "protected": 0, "errors": 0,
            }),
            _beep_once=MagicMock(),
        )

    def test_report_includes_starting_inbox_total(self):
        from inbox_scout import autopilot_cleanup as ac
        patches = self._base_patches(n_batches=1, items_per_batch=10)
        patches["_get_total_inbox_count"] = MagicMock(return_value=10)
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup", **patches):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertIn("Starting Inbox total: 10", result)

    def test_report_includes_starting_unread(self):
        from inbox_scout import autopilot_cleanup as ac
        patches = self._base_patches(n_batches=1)
        patches["_get_unread_inbox_count"] = MagicMock(return_value=7)
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup", **patches):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertIn("Starting unread: 7", result)

    def test_plan_target_set_to_inbox(self):
        """run_inbox_zero_autopilot must set plan.target='inbox' before saving."""
        from inbox_scout import autopilot_cleanup as ac

        saved_targets = []

        def capture_save(plan):
            saved_targets.append(getattr(plan, "target", None))

        patches = self._base_patches(n_batches=1)
        patches["save_plan"] = capture_save
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup", **patches):
            ac.run_inbox_zero_autopilot("sort all")

        self.assertTrue(all(t == "inbox" for t in saved_targets),
                        f"plan.target must be 'inbox' but got: {saved_targets}")

    def test_stops_when_inbox_empty_not_just_unread_zero(self):
        """Loop must stop when scan returns 0 items (inbox truly empty)."""
        from inbox_scout import autopilot_cleanup as ac
        patches = self._base_patches(n_batches=0)
        with unittest.mock.patch.multiple("inbox_scout.autopilot_cleanup", **patches):
            result = ac.run_inbox_zero_autopilot("sort all")
        self.assertIn("Scanned: 0", result)
        self.assertIn("Nothing permanently deleted", result)


class TestRunnerAllowsInboxTarget(unittest.TestCase):
    """sort_scan_queue_runner must allow target='inbox' and skip --unread-only."""

    def _build_report_args(self, plan_dict: dict) -> list:
        """Replicate the runner's report_args construction logic."""
        import sys
        limit = plan_dict["requested_limit"]
        page_size = min(5, limit)
        args = [
            sys.executable, "-m", "inbox_scout.report_mode",
            "--limit", str(limit), "--page-size", str(page_size),
            "--export", "both",
        ]
        is_full_inbox_scan = plan_dict.get("sort_all") or plan_dict.get("target") == "inbox"
        if not is_full_inbox_scan:
            args.append("--unread-only")
        return args

    def test_inbox_target_passes_validation(self):
        from inbox_scout.sort_scan_queue_runner import validate_plan
        plan = {
            "workflow_mode": "commands_planned",
            "target": "inbox",
            "requested_limit": 5,
        }
        safe, notes = validate_plan(plan)
        self.assertTrue(safe, f"'inbox' target must be valid. Notes: {notes}")

    def test_unread_inbox_target_still_passes(self):
        from inbox_scout.sort_scan_queue_runner import validate_plan
        plan = {
            "workflow_mode": "commands_planned",
            "target": "unread_inbox",
            "requested_limit": 5,
        }
        safe, notes = validate_plan(plan)
        self.assertTrue(safe, f"'unread_inbox' target must still be valid. Notes: {notes}")

    def test_unknown_target_blocked(self):
        from inbox_scout.sort_scan_queue_runner import validate_plan
        plan = {
            "workflow_mode": "commands_planned",
            "target": "all_mail",
            "requested_limit": 5,
        }
        safe, _ = validate_plan(plan)
        self.assertFalse(safe, "Unknown targets must be blocked")

    def test_inbox_target_no_unread_only_in_args(self):
        """target='inbox' must NOT produce --unread-only in report args."""
        plan = {"requested_limit": 25, "target": "inbox", "sort_all": False}
        args = self._build_report_args(plan)
        self.assertNotIn("--unread-only", args, "target=inbox must skip --unread-only")

    def test_sort_all_true_no_unread_only_in_args(self):
        """sort_all=True must NOT produce --unread-only even if target=unread_inbox."""
        plan = {"requested_limit": 25, "target": "unread_inbox", "sort_all": True}
        args = self._build_report_args(plan)
        self.assertNotIn("--unread-only", args, "sort_all=True must skip --unread-only")

    def test_standard_sort_keeps_unread_only(self):
        """Standard limited sort (sort_all=False, target=unread_inbox) must keep --unread-only."""
        plan = {"requested_limit": 5, "target": "unread_inbox", "sort_all": False}
        args = self._build_report_args(plan)
        self.assertIn("--unread-only", args, "Standard sort must include --unread-only")

    def test_autopilot_plan_has_inbox_target_and_sort_all(self):
        """Autopilot must set both sort_all=True and target='inbox' before saving."""
        from inbox_scout import autopilot_cleanup as ac

        saved_plans = []

        def capture_save(plan):
            saved_plans.append({
                "target": getattr(plan, "target", None),
                "sort_all": getattr(plan, "sort_all", None),
                "requested_limit": getattr(plan, "requested_limit", None),
            })

        mock_plan = MagicMock()
        mock_plan.workflow_mode = "commands_planned"
        mock_plan.requested_limit = 25
        mock_plan.target = "unread_inbox"
        mock_plan.sort_all = False

        with (
            unittest.mock.patch.object(ac, "build_scan_queue_plan", return_value=mock_plan),
            unittest.mock.patch.object(ac, "save_plan", side_effect=capture_save),
            unittest.mock.patch.object(ac, "_run_scan", return_value=MagicMock(returncode=0)),
            unittest.mock.patch.object(ac, "_load_json", return_value={"status": "complete"}),
            unittest.mock.patch.object(ac, "_load_items_from_queue", return_value=[]),
            unittest.mock.patch.object(ac, "_get_modify_service_for_autopilot", return_value=MagicMock()),
            unittest.mock.patch.object(ac, "_get_unread_inbox_count", return_value=5),
            unittest.mock.patch.object(ac, "_get_total_inbox_count", return_value=5),
            unittest.mock.patch.object(ac, "_beep_once"),
        ):
            ac.run_inbox_zero_autopilot("sort all")

        self.assertTrue(len(saved_plans) >= 1, "save_plan must be called at least once")
        for sp in saved_plans:
            self.assertEqual(sp["target"], "inbox", f"All saved plans must have target='inbox', got {sp}")
            self.assertTrue(sp["sort_all"], f"All saved plans must have sort_all=True, got {sp}")
            self.assertEqual(sp["requested_limit"], 25, f"requested_limit must be 25, got {sp}")


if __name__ == "__main__":
    unittest.main()
