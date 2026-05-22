"""
Focused tests for Junk Sender Scout — Phase 1 read-only report.

Covers:
1. All Mail scan uses read-only Gmail service
2. Protected senders (finance/medical domain) are excluded
3. Newsletter/promo senders become candidates
4. No Gmail modify/filter/trash/delete APIs are called
5. Natural language route works

Run:
  $env:PYTHONPATH = "src"; .venv\\Scripts\\python.exe -m unittest tests.test_junk_sender_scout -v
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_service(messages: list[dict], headers_map: dict[str, dict]) -> MagicMock:
    """
    Build a minimal mock Gmail service.
    messages: list of {"id": "..."} stubs returned by messages.list
    headers_map: dict of msg_id -> {"From": ..., "Subject": ...}
    """
    service = MagicMock()

    # messages().list().execute()
    list_exec = service.users.return_value.messages.return_value.list.return_value.execute
    list_exec.return_value = {"messages": messages}

    # messages().get().execute() — keyed by id
    def get_execute_side_effect(**kwargs):
        msg_id = kwargs.get("id", "")
        hdrs = headers_map.get(msg_id, {})
        payload_headers = [{"name": k, "value": v} for k, v in hdrs.items()]
        return {"payload": {"headers": payload_headers}}

    get_mock = service.users.return_value.messages.return_value.get.return_value
    get_mock.execute.side_effect = lambda: get_execute_side_effect(
        id=service.users.return_value.messages.return_value.get.call_args[1].get("id", "")
    )

    return service


def _make_service_v2(messages_list, headers_by_id):
    """Cleaner mock — each .get(id=...) call returns the right headers."""
    service = MagicMock()

    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": messages_list
    }

    def _get(**kwargs):
        mid = kwargs.get("id", "")
        hdrs = headers_by_id.get(mid, {})
        payload_hdrs = [{"name": k, "value": v} for k, v in hdrs.items()]
        result_mock = MagicMock()
        result_mock.execute.return_value = {"payload": {"headers": payload_hdrs}}
        return result_mock

    service.users.return_value.messages.return_value.get.side_effect = _get
    return service


class TestReadOnlyService(unittest.TestCase):
    """Verify All Mail scan always uses read-only Gmail service."""

    def test_uses_readonly_mode(self):
        from inbox_scout.junk_sender_scout import scan_junk_senders
        service = _make_service_v2([], {})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service) as mock_auth:
            scan_junk_senders(account="primary")
        mock_auth.assert_called_once_with(mode="readonly", account="primary")

    def test_secondary_account_passed_through(self):
        from inbox_scout.junk_sender_scout import scan_junk_senders
        service = _make_service_v2([], {})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service) as mock_auth:
            scan_junk_senders(account="secondary")
        mock_auth.assert_called_once_with(mode="readonly", account="secondary")

    def test_query_covers_all_mail_categories(self):
        from inbox_scout.junk_sender_scout import scan_junk_senders
        service = _make_service_v2([], {})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            scan_junk_senders()
        list_call = service.users.return_value.messages.return_value.list.call_args
        q = list_call[1].get("q", list_call[0][0] if list_call[0] else "")
        self.assertIn("promotions", q)
        self.assertIn("updates", q)


class TestProtectedSendersExcluded(unittest.TestCase):
    """Finance/medical/security senders must never appear in candidates."""

    def _scan_with_sender(self, sender_email: str, subject: str) -> list[dict]:
        from inbox_scout.junk_sender_scout import scan_junk_senders
        messages = [{"id": "m1"}]
        headers = {"m1": {"From": sender_email, "Subject": subject}}
        service = _make_service_v2(messages, headers)
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            return scan_junk_senders()

    def test_bank_domain_excluded(self):
        candidates = self._scan_with_sender("alerts@bankofamerica.com", "Your statement is ready")
        addrs = [c["sender"] for c in candidates]
        self.assertNotIn("alerts@bankofamerica.com", addrs)

    def test_paypal_domain_excluded(self):
        candidates = self._scan_with_sender("noreply@paypal.com", "Your receipt")
        addrs = [c["sender"] for c in candidates]
        self.assertNotIn("noreply@paypal.com", addrs)

    def test_medical_subject_excluded(self):
        # Subject contains a protected text term ("appointment")
        candidates = self._scan_with_sender("updates@clinic.example.com", "Your appointment reminder")
        addrs = [c["sender"] for c in candidates]
        self.assertNotIn("updates@clinic.example.com", addrs)

    def test_password_subject_excluded(self):
        candidates = self._scan_with_sender("promo@shop.com", "Reset your password today")
        addrs = [c["sender"] for c in candidates]
        self.assertNotIn("promo@shop.com", addrs)

    def test_system_sender_excluded(self):
        candidates = self._scan_with_sender("security@google.com", "Weekly digest")
        addrs = [c["sender"] for c in candidates]
        self.assertNotIn("security@google.com", addrs)


class TestNewsletterCandidates(unittest.TestCase):
    """Newsletter/promo senders should appear as candidates."""

    def _scan_with_senders(self, sender_subjects: dict[str, list[str]]) -> list[dict]:
        from inbox_scout.junk_sender_scout import scan_junk_senders
        messages = []
        headers = {}
        mid = 0
        for addr, subjects in sender_subjects.items():
            for subj in subjects:
                mid += 1
                msg_id = f"m{mid}"
                messages.append({"id": msg_id})
                headers[msg_id] = {"From": addr, "Subject": subj}
        service = _make_service_v2(messages, headers)
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            return scan_junk_senders()

    def test_promo_sender_is_candidate(self):
        candidates = self._scan_with_senders({
            "deals@store.com": ["50% off today!", "Weekend sale", "Exclusive offer"]
        })
        addrs = [c["sender"] for c in candidates]
        self.assertIn("deals@store.com", addrs)

    def test_candidate_has_required_fields(self):
        candidates = self._scan_with_senders({
            "news@example.com": ["Monthly newsletter", "Unsubscribe here"]
        })
        self.assertTrue(len(candidates) > 0)
        c = candidates[0]
        self.assertIn("sender", c)
        self.assertIn("count", c)
        self.assertIn("samples", c)
        self.assertIn("reason", c)
        self.assertIn("risk_score", c)
        self.assertIn("safe_to_review", c)

    def test_candidate_count_matches_messages(self):
        candidates = self._scan_with_senders({
            "promo@brand.com": ["Deal 1", "Deal 2", "Deal 3", "Deal 4"]
        })
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["count"], 4)

    def test_high_signal_sender_marked_safe_to_review(self):
        subjects = ["50% off today", "Unsubscribe from our weekly newsletter",
                    "Sale ends soon", "Discount available", "Limited time offer",
                    "Shop now for deals", "Monthly promo digest"]
        candidates = self._scan_with_senders({"promo@megastore.com": subjects})
        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0]["safe_to_review"])

    def test_sorted_by_count_descending(self):
        candidates = self._scan_with_senders({
            "a@one.com": ["Sale"] * 2,
            "b@two.com": ["Newsletter"] * 5,
            "c@three.com": ["Promo"] * 3,
        })
        counts = [c["count"] for c in candidates]
        self.assertEqual(counts, sorted(counts, reverse=True))


class TestNoGmailWrites(unittest.TestCase):
    """No Gmail write, filter, trash, delete, or modify APIs must be called."""

    def test_messages_modify_not_called(self):
        from inbox_scout.junk_sender_scout import scan_junk_senders
        service = _make_service_v2([{"id": "m1"}], {
            "m1": {"From": "news@example.com", "Subject": "Weekly digest"}
        })
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            scan_junk_senders()
        # messages().modify should never be called
        service.users.return_value.messages.return_value.modify.assert_not_called()

    def test_settings_filters_not_called(self):
        from inbox_scout.junk_sender_scout import scan_junk_senders
        service = _make_service_v2([{"id": "m1"}], {
            "m1": {"From": "promo@example.com", "Subject": "Sale"}
        })
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            scan_junk_senders()
        # Gmail Settings API for filter creation must not be accessed
        service.users.return_value.settings.assert_not_called()

    def test_messages_trash_not_called(self):
        from inbox_scout.junk_sender_scout import scan_junk_senders
        service = _make_service_v2([{"id": "m1"}], {
            "m1": {"From": "promo@example.com", "Subject": "Deal of the day"}
        })
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            scan_junk_senders()
        service.users.return_value.messages.return_value.trash.assert_not_called()

    def test_output_says_no_gmail_changes(self):
        from inbox_scout.junk_sender_scout import junk_sender_scout_message
        service = _make_service_v2([], {})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            result = junk_sender_scout_message()
        self.assertIn("No Gmail changes made", result)

    def test_output_says_no_gmail_changes_with_candidates(self):
        from inbox_scout.junk_sender_scout import junk_sender_scout_message
        service = _make_service_v2([{"id": "m1"}], {
            "m1": {"From": "news@example.com", "Subject": "Monthly newsletter"}
        })
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            result = junk_sender_scout_message()
        self.assertIn("No Gmail changes made", result)


class TestNaturalLanguageRoute(unittest.TestCase):
    """Natural language phrases must route to junk_sender_scout_message."""

    def _route(self, phrase: str):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.junk_sender_scout.get_gmail_service") as mock_auth:
            mock_auth.return_value = _make_service_v2([], {})
            with patch("inbox_scout.natural_intent.junk_sender_scout_message",
                       return_value="JUNK_REPORT") as mock_scout:
                result = ni.handle_natural_message(phrase)
        return result, mock_scout

    def test_find_junk_senders_routes(self):
        result, mock_scout = self._route("find junk senders")
        mock_scout.assert_called_once()
        self.assertEqual(result, "JUNK_REPORT")

    def test_find_newsletter_senders_routes(self):
        result, mock_scout = self._route("find newsletter senders")
        mock_scout.assert_called_once()

    def test_scan_archived_junk_senders_routes(self):
        result, mock_scout = self._route("scan archived junk senders")
        mock_scout.assert_called_once()

    def test_find_senders_to_block_routes(self):
        result, mock_scout = self._route("find senders to block")
        mock_scout.assert_called_once()

    def test_junk_sender_scan_routes(self):
        result, mock_scout = self._route("junk sender scan")
        mock_scout.assert_called_once()

    def test_secondary_account_passed(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.junk_sender_scout_message",
                   return_value="JUNK_REPORT") as mock_scout:
            ni.handle_natural_message("find junk senders secondary")
        mock_scout.assert_called_once_with(account="secondary")

    def test_primary_account_is_default(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.junk_sender_scout_message",
                   return_value="JUNK_REPORT") as mock_scout:
            ni.handle_natural_message("find junk senders")
        mock_scout.assert_called_once_with(account="primary")


if __name__ == "__main__":
    unittest.main()
