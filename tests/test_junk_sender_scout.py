"""
Focused tests for Junk Sender Scout — Phase 1 read-only report.

scan_junk_senders() now returns:
  {messages_scanned, profiles_total, candidates, archive_only, excluded}

Each profile has: sender, display_name, count, samples,
                  recommendation_class, risk_score, reason, safe_to_review

Run:
  $env:PYTHONPATH = "src"; .venv\\Scripts\\python.exe -m unittest tests.test_junk_sender_scout -v
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_scout.junk_sender_scout import SAFE, ARCHIVE_ONLY, EXCLUDED


# ── mock helpers ──────────────────────────────────────────────────────────────

def _make_service(messages_list, headers_by_id):
    """Mock Gmail service: list returns stubs, get returns headers by id."""
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


def _scan(sender_subjects: dict[str, list[str]]) -> dict:
    """Build a mock service from {addr: [subjects]} and call scan_junk_senders."""
    from inbox_scout.junk_sender_scout import scan_junk_senders
    messages, headers = [], {}
    mid = 0
    for addr, subjects in sender_subjects.items():
        for subj in subjects:
            mid += 1
            msg_id = f"m{mid}"
            messages.append({"id": msg_id})
            headers[msg_id] = {"From": addr, "Subject": subj}
    service = _make_service(messages, headers)
    with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
        return scan_junk_senders()


def _candidate_addrs(result: dict) -> list[str]:
    return [c["sender"] for c in result["candidates"]]

def _excluded_addrs(result: dict) -> list[str]:
    return [c["sender"] for c in result["excluded"]]

def _archive_addrs(result: dict) -> list[str]:
    return [c["sender"] for c in result["archive_only"]]


# ── query and scan scope ──────────────────────────────────────────────────────

class TestScanScope(unittest.TestCase):

    def _get_query(self) -> str:
        from inbox_scout.junk_sender_scout import scan_junk_senders
        service = _make_service([], {})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            scan_junk_senders()
        return service.users.return_value.messages.return_value.list.call_args[1].get("q", "")

    def test_uses_readonly_service(self):
        from inbox_scout.junk_sender_scout import scan_junk_senders
        service = _make_service([], {})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service) as mock_auth:
            scan_junk_senders(account="primary")
        mock_auth.assert_called_once_with(mode="readonly", account="primary")

    def test_secondary_account_passed_through(self):
        from inbox_scout.junk_sender_scout import scan_junk_senders
        service = _make_service([], {})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service) as mock_auth:
            scan_junk_senders(account="secondary")
        mock_auth.assert_called_once_with(mode="readonly", account="secondary")

    def test_query_includes_promotions(self):
        self.assertIn("promotions", self._get_query())

    def test_query_includes_updates(self):
        self.assertIn("updates", self._get_query())

    def test_query_excludes_trash(self):
        self.assertIn("-in:trash", self._get_query())

    def test_query_excludes_spam(self):
        self.assertIn("-in:spam", self._get_query())

    def test_query_does_not_restrict_to_inbox(self):
        q = self._get_query()
        self.assertNotIn("in:inbox", q)

    def test_query_does_not_restrict_to_unread(self):
        q = self._get_query()
        self.assertNotIn("is:unread", q)

    def test_returns_dict_with_required_keys(self):
        result = _scan({})
        for key in ("messages_scanned", "profiles_total", "candidates", "archive_only", "excluded"):
            self.assertIn(key, result)


# ── regression: protected senders must NOT be candidates ─────────────────────

class TestProtectedExcluded(unittest.TestCase):
    """Sensitive/protected senders must never appear in candidates."""

    def _assert_not_candidate(self, addr: str, subjects: list[str]):
        result = _scan({addr: subjects})
        self.assertNotIn(addr, _candidate_addrs(result),
                         f"{addr} must not be a block candidate")

    def test_usps_informed_delivery_not_candidate(self):
        self._assert_not_candidate(
            "USPSInformeddelivery@email.informeddelivery.usps.com",
            ["Your Daily Digest for Thu, 5/22 is ready to view"] * 5,
        )

    def test_usps_is_archive_only(self):
        result = _scan({
            "USPSInformeddelivery@email.informeddelivery.usps.com":
                ["Your Daily Digest for Thu, 5/22 is ready to view"] * 3
        })
        # extract_email normalises to lowercase
        self.assertIn(
            "uspsinformeddelivery@email.informeddelivery.usps.com",
            _archive_addrs(result),
        )

    def test_chime_not_candidate(self):
        self._assert_not_candidate(
            "alerts@chime.com",
            ["Your Chime account balance"] * 4,
        )

    def test_chime_is_excluded(self):
        result = _scan({"alerts@chime.com": ["Your Chime account balance"] * 4})
        self.assertIn("alerts@chime.com", _excluded_addrs(result))

    def test_google_play_receipt_not_candidate(self):
        self._assert_not_candidate(
            "noreply@google.com",
            ["Your Google Play receipt"] * 3,
        )

    def test_digitalocean_not_candidate(self):
        self._assert_not_candidate(
            "support@digitalocean.com",
            ["Your DigitalOcean droplet is ready"] * 3,
        )

    def test_digitalocean_is_excluded(self):
        result = _scan({"support@digitalocean.com": ["DigitalOcean invoice"] * 3})
        self.assertIn("support@digitalocean.com", _excluded_addrs(result))

    def test_welo_job_not_candidate(self):
        self._assert_not_candidate(
            "recruiting@welo.com",
            ["Job opportunity at Welo - Software Engineer"] * 2,
        )

    def test_welocalize_not_candidate(self):
        self._assert_not_candidate(
            "careers@welocalize.com",
            ["Open position at Welocalize"] * 2,
        )

    def test_chatgpt_medical_reminder_not_candidate(self):
        self._assert_not_candidate(
            "noreply@openai.com",
            ["Your medical appointment reminder from ChatGPT"] * 2,
        )

    def test_openai_domain_excluded(self):
        result = _scan({"noreply@openai.com": ["ChatGPT weekly digest"] * 3})
        self.assertIn("noreply@openai.com", _excluded_addrs(result))

    def test_ssh_security_notification_not_candidate(self):
        self._assert_not_candidate(
            "alerts@hosting.com",
            ["SSH key added to your account"] * 2,
        )

    def test_order_shipped_not_candidate(self):
        self._assert_not_candidate(
            "ship@retailer.com",
            ["Your order has been shipped"] * 3,
        )

    def test_order_is_archive_only(self):
        result = _scan({"ship@retailer.com": ["Your order has been shipped"] * 3})
        self.assertIn("ship@retailer.com", _archive_addrs(result))

    def test_finance_payment_not_candidate(self):
        self._assert_not_candidate(
            "billing@service.com",
            ["Your payment was processed"] * 4,
        )

    def test_bank_domain_not_candidate(self):
        self._assert_not_candidate(
            "alerts@bankofamerica.com",
            ["Your statement is ready"] * 3,
        )

    def test_medical_appointment_not_candidate(self):
        self._assert_not_candidate(
            "reminders@healthsystem.com",
            ["Your appointment with Dr. Smith is tomorrow"] * 2,
        )

    def test_personal_gmail_not_candidate(self):
        self._assert_not_candidate(
            "john.doe@gmail.com",
            ["Hey, check this out"] * 3,
        )

    def test_github_not_candidate(self):
        self._assert_not_candidate(
            "noreply@github.com",
            ["New security vulnerability in your dependency"] * 2,
        )

    def test_linkedin_recruiting_not_candidate(self):
        self._assert_not_candidate(
            "jobs@linkedin.com",
            ["Job opportunity matching your profile"] * 3,
        )


# ── safe block candidates ─────────────────────────────────────────────────────

class TestSafeCandidates(unittest.TestCase):
    """High-confidence promo senders should be safe_to_review_for_blocking."""

    def _assert_is_candidate(self, addr: str, subjects: list[str]):
        result = _scan({addr: subjects})
        self.assertIn(addr, _candidate_addrs(result),
                      f"{addr} should be a block candidate")

    def test_repeated_promo_sender_is_candidate(self):
        self._assert_is_candidate(
            "deals@randomretailer.example",
            ["50% off today!", "Weekend sale ends soon", "Flash sale — today only",
             "Exclusive offer for you", "New deals this week"],
        )

    def test_newsletter_with_unsubscribe_is_candidate(self):
        self._assert_is_candidate(
            "newsletter@couponblog.example",
            ["Weekly deals newsletter — unsubscribe here",
             "Top coupons this month — manage preferences"],
        )

    def test_offers_sender_with_promo_subjects_is_candidate(self):
        self._assert_is_candidate(
            "offers@shoppingbrand.example",
            ["Sale ends tonight", "Discount available now", "Shop now — free shipping",
             "Limited time offer"],
        )

    def test_marketing_sender_three_messages_is_candidate(self):
        self._assert_is_candidate(
            "marketing@brand.example",
            ["New arrivals this week", "Trending items picked for you", "Recommendations for you"],
        )

    def test_candidate_has_all_required_fields(self):
        result = _scan({
            "promo@store.example": ["Big sale today", "50% off", "Shop now"] * 2
        })
        self.assertTrue(len(result["candidates"]) > 0)
        c = result["candidates"][0]
        for field in ("sender", "display_name", "count", "samples",
                      "recommendation_class", "risk_score", "reason", "safe_to_review"):
            self.assertIn(field, c)

    def test_candidate_recommendation_class_is_safe(self):
        result = _scan({
            "newsletter@deals.example": ["Unsubscribe | weekly deals newsletter"] * 5
        })
        self.assertTrue(len(result["candidates"]) > 0)
        self.assertEqual(result["candidates"][0]["recommendation_class"], SAFE)

    def test_candidate_safe_to_review_is_true(self):
        result = _scan({
            "promo@megastore.example": ["50% off", "Sale ends soon", "Discount today",
                                         "Shop now", "Flash sale"]
        })
        self.assertTrue(len(result["candidates"]) > 0)
        self.assertTrue(result["candidates"][0]["safe_to_review"])

    def test_one_off_promo_is_not_safe_to_review(self):
        result = _scan({"deals@store.example": ["Sale today"]})
        # 1 message with 1 promo hit: risk = 50 - 10 + 10 = 50 → not safe
        addrs = _candidate_addrs(result)
        self.assertNotIn("deals@store.example", addrs)

    def test_candidates_sorted_by_risk_ascending(self):
        result = _scan({
            "a@promo.example": ["50% off today"] * 2,
            "b@newsletter.example": ["Unsubscribe | weekly deals"] * 8,
        })
        risks = [c["risk_score"] for c in result["candidates"]]
        self.assertEqual(risks, sorted(risks))


# ── no Gmail writes ───────────────────────────────────────────────────────────

class TestNoGmailWrites(unittest.TestCase):

    def _get_service_after_scan(self, sender, subject):
        from inbox_scout.junk_sender_scout import scan_junk_senders
        service = _make_service([{"id": "m1"}], {"m1": {"From": sender, "Subject": subject}})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            scan_junk_senders()
        return service

    def test_messages_modify_not_called(self):
        svc = self._get_service_after_scan("news@example.com", "Weekly digest")
        svc.users.return_value.messages.return_value.modify.assert_not_called()

    def test_messages_trash_not_called(self):
        svc = self._get_service_after_scan("promo@example.com", "Big sale today")
        svc.users.return_value.messages.return_value.trash.assert_not_called()

    def test_settings_filters_not_called(self):
        svc = self._get_service_after_scan("promo@example.com", "Sale")
        svc.users.return_value.settings.assert_not_called()

    def test_messages_delete_not_called(self):
        svc = self._get_service_after_scan("promo@example.com", "Deal")
        svc.users.return_value.messages.return_value.delete.assert_not_called()

    def test_output_always_has_no_gmail_changes(self):
        from inbox_scout.junk_sender_scout import junk_sender_scout_message
        service = _make_service([], {})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            result = junk_sender_scout_message()
        self.assertIn("No Gmail changes made", result)

    def test_output_has_no_gmail_changes_with_candidates(self):
        from inbox_scout.junk_sender_scout import junk_sender_scout_message
        service = _make_service([{"id": "m1"}], {
            "m1": {"From": "deals@store.example", "Subject": "50% off today"}
        })
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            result = junk_sender_scout_message()
        self.assertIn("No Gmail changes made", result)


# ── output format ─────────────────────────────────────────────────────────────

class TestOutputFormat(unittest.TestCase):

    def test_output_includes_account_name(self):
        from inbox_scout.junk_sender_scout import junk_sender_scout_message
        service = _make_service([], {})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            result = junk_sender_scout_message(account="secondary")
        self.assertIn("secondary", result)

    def test_output_mentions_all_mail_scope(self):
        from inbox_scout.junk_sender_scout import junk_sender_scout_message
        service = _make_service([], {})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            result = junk_sender_scout_message()
        self.assertIn("All Mail", result)

    def test_output_includes_scanned_count(self):
        from inbox_scout.junk_sender_scout import junk_sender_scout_message
        service = _make_service([], {})
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            result = junk_sender_scout_message()
        self.assertIn("Scanned", result)

    def test_excluded_summary_present_when_excluded_exist(self):
        from inbox_scout.junk_sender_scout import junk_sender_scout_message
        service = _make_service([{"id": "m1"}], {
            "m1": {"From": "alerts@chime.com", "Subject": "Your Chime balance"}
        })
        with patch("inbox_scout.junk_sender_scout.get_gmail_service", return_value=service):
            result = junk_sender_scout_message()
        self.assertIn("excluded", result.lower())


# ── natural language routing ──────────────────────────────────────────────────

class TestNaturalLanguageRoute(unittest.TestCase):

    def _route(self, phrase: str):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.junk_sender_scout_message",
                   return_value="JUNK_REPORT") as mock_scout:
            result = ni.handle_natural_message(phrase)
        return result, mock_scout

    def test_find_junk_senders_routes(self):
        result, mock = self._route("find junk senders")
        mock.assert_called_once()
        self.assertEqual(result, "JUNK_REPORT")

    def test_find_newsletter_senders_routes(self):
        _, mock = self._route("find newsletter senders")
        mock.assert_called_once()

    def test_scan_archived_junk_senders_routes(self):
        _, mock = self._route("scan archived junk senders")
        mock.assert_called_once()

    def test_find_senders_to_block_routes(self):
        _, mock = self._route("find senders to block")
        mock.assert_called_once()

    def test_junk_sender_scan_routes(self):
        _, mock = self._route("junk sender scan")
        mock.assert_called_once()

    def test_primary_is_default(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.junk_sender_scout_message",
                   return_value="JUNK_REPORT") as mock:
            ni.handle_natural_message("find junk senders")
        mock.assert_called_once_with(account="primary")

    def test_secondary_passed(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.junk_sender_scout_message",
                   return_value="JUNK_REPORT") as mock:
            ni.handle_natural_message("find junk senders secondary")
        mock.assert_called_once_with(account="secondary")

    def test_both_accounts_calls_both(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.junk_sender_scout_message",
                   return_value="JUNK_REPORT") as mock:
            result = ni.handle_natural_message("find junk senders both accounts")
        self.assertEqual(mock.call_count, 2)
        calls = {c[1]["account"] for c in mock.call_args_list}
        self.assertEqual(calls, {"primary", "secondary"})
        self.assertIn("PRIMARY", result)
        self.assertIn("SECONDARY", result)

    def test_both_scan_archived_routes(self):
        from inbox_scout import natural_intent as ni
        with patch("inbox_scout.natural_intent.junk_sender_scout_message",
                   return_value="JUNK_REPORT") as mock:
            result = ni.handle_natural_message("scan archived junk senders both accounts")
        self.assertEqual(mock.call_count, 2)


# ── classify helper unit tests ────────────────────────────────────────────────

class TestClassifyUnit(unittest.TestCase):
    """Direct tests of _classify() without Gmail API calls."""

    def _cls(self, addr, subjects):
        from inbox_scout.junk_sender_scout import _classify
        rec, risk, reason = _classify(addr, "", subjects)
        return rec, risk, reason

    def test_usps_is_archive_only(self):
        rec, _, _ = self._cls(
            "noreply@informeddelivery.usps.com",
            ["Your Daily Digest"] * 5
        )
        self.assertEqual(rec, ARCHIVE_ONLY)

    def test_chime_is_excluded(self):
        rec, _, _ = self._cls("alerts@chime.com", ["Balance update"] * 3)
        self.assertEqual(rec, EXCLUDED)

    def test_digitalocean_is_excluded(self):
        rec, _, _ = self._cls("support@digitalocean.com", ["Droplet alert"] * 3)
        self.assertEqual(rec, EXCLUDED)

    def test_welo_is_excluded(self):
        rec, _, _ = self._cls("jobs@welo.com", ["Job opportunity"] * 2)
        self.assertEqual(rec, EXCLUDED)

    def test_openai_is_excluded(self):
        rec, _, _ = self._cls("noreply@openai.com", ["ChatGPT update"] * 3)
        self.assertEqual(rec, EXCLUDED)

    def test_ssh_subject_is_excluded(self):
        rec, _, _ = self._cls("alerts@host.com", ["SSH key added to your account"] * 2)
        self.assertEqual(rec, EXCLUDED)

    def test_appointment_subject_is_excluded(self):
        rec, _, _ = self._cls("reminders@portal.com", ["Your appointment tomorrow"] * 2)
        self.assertEqual(rec, EXCLUDED)

    def test_google_play_receipt_is_archive_only(self):
        rec, _, _ = self._cls("noreply@google.com", ["Your Google Play receipt"] * 2)
        self.assertEqual(rec, ARCHIVE_ONLY)

    def test_order_shipped_is_archive_only(self):
        rec, _, _ = self._cls("ship@store.com", ["Your order has been shipped"] * 3)
        self.assertEqual(rec, ARCHIVE_ONLY)

    def test_marketing_local_part_lowers_risk(self):
        from inbox_scout.junk_sender_scout import _compute_risk
        # marketing local part should reduce risk
        risk_with = _compute_risk("marketing", "brand.com", ["New arrivals"] * 3)
        risk_without = _compute_risk("info", "brand.com", ["New arrivals"] * 3)
        self.assertLess(risk_with, risk_without)

    def test_repeated_promo_sender_is_safe(self):
        rec, risk, _ = self._cls(
            "deals@store.example",
            ["50% off today", "Flash sale ends soon", "Shop now — free shipping",
             "Exclusive offer", "Weekend deals"]
        )
        self.assertEqual(rec, SAFE)
        self.assertLessEqual(risk, 30)

    def test_single_message_not_safe(self):
        rec, risk, _ = self._cls("deals@store.example", ["50% off today"])
        self.assertNotEqual(rec, SAFE)
        self.assertGreater(risk, 30)

    def test_bank_domain_is_excluded(self):
        rec, _, _ = self._cls("alerts@bankofamerica.com", ["Statement ready"] * 3)
        self.assertEqual(rec, EXCLUDED)

    def test_personal_gmail_is_excluded(self):
        rec, _, _ = self._cls("friend@gmail.com", ["Hey check this out"] * 3)
        self.assertEqual(rec, EXCLUDED)

    def test_github_is_excluded(self):
        rec, _, _ = self._cls("noreply@github.com", ["New release"] * 3)
        self.assertEqual(rec, EXCLUDED)

    def test_jobs_subject_is_excluded(self):
        rec, _, _ = self._cls("hr@company.com", ["Job opportunity at Company Inc"] * 2)
        self.assertEqual(rec, EXCLUDED)

    def test_newsletter_local_part_reduces_risk(self):
        from inbox_scout.junk_sender_scout import _compute_risk
        risk = _compute_risk("newsletter", "brand.com", ["Monthly digest"] * 5)
        self.assertLessEqual(risk, 30)


if __name__ == "__main__":
    unittest.main()
