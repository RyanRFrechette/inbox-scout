"""
Test: marketing false-positive demotion for Job/career and Client/business.

Proves: product newsletters and deal emails mislabeled as Job/career or
Client/business are demoted to Promotion (manual_review=False, risk=15)
at classification time, so plan and runner see them as safe candidates.
Real job, client, receipt, and security emails are never demoted.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_marketing_false_positive_demotion -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _email(subject="", from_="ads@example.com", snippet=""):
    return {"subject": subject, "from": from_, "snippet": snippet}


def _result(category="Job/career", risk=70, manual_review=True):
    return {
        "category": category,
        "confidence_score": 80,
        "risk_score": risk,
        "reason": "original reason",
        "suggested_action": "Review manually.",
        "manual_review": manual_review,
    }


class TestDemoteMarketingFalsePositive(unittest.TestCase):

    def test_product_newsletter_job_career_is_demoted(self):
        # "Ship your first major feature with Claude Code" from no-reply sender
        from inbox_scout.ai_classifier import _demote_marketing_false_positive
        email = _email(
            subject="Ship your first major feature with Claude Code",
            from_="Claude Team <no-reply@email.claude.com>",
            snippet="Do hours or even days of work in minutes. Ship features with confidence.",
        )
        result = _demote_marketing_false_positive(email, _result(category="Job/career"))
        self.assertEqual(result["category"], "Promotion")
        self.assertFalse(result["manual_review"])
        self.assertEqual(result["risk_score"], 15)

    def test_daily_deals_client_business_is_demoted(self):
        # "Daily Deals: More ways to save" from newsletter sender
        from inbox_scout.ai_classifier import _demote_marketing_false_positive
        email = _email(
            subject="Daily Deals: More ways to save on every find.",
            from_="BenefitHub <daily-deals@newsletter.emailbenefithub.com>",
            snippet="The best deals online plus more ways to save. SHOP BRANDS YOU LOVE.",
        )
        result = _demote_marketing_false_positive(email, _result(category="Client/business", risk=90))
        self.assertEqual(result["category"], "Promotion")
        self.assertFalse(result["manual_review"])
        self.assertEqual(result["risk_score"], 15)

    def test_real_job_interview_email_not_demoted(self):
        # Subject/snippet contain "interview" → danger signal → not demoted
        from inbox_scout.ai_classifier import _demote_marketing_false_positive
        email = _email(
            subject="Your interview is scheduled for Thursday",
            from_="recruiter@company.com",
            snippet="We're excited to have you interview with our team.",
        )
        result = _demote_marketing_false_positive(email, _result(category="Job/career"))
        self.assertEqual(result["category"], "Job/career")
        self.assertTrue(result["manual_review"])

    def test_real_job_application_email_not_demoted(self):
        from inbox_scout.ai_classifier import _demote_marketing_false_positive
        email = _email(
            subject="Update on your application at Acme Corp",
            from_="no-reply@ats.workday.com",
            snippet="Your application has been received and is under review.",
        )
        result = _demote_marketing_false_positive(email, _result(category="Job/career"))
        # "application" is a danger term — not demoted even though "no-reply" is marketing
        self.assertEqual(result["category"], "Job/career")
        self.assertTrue(result["manual_review"])

    def test_real_client_email_without_marketing_signal_not_demoted(self):
        from inbox_scout.ai_classifier import _demote_marketing_false_positive
        email = _email(
            subject="Project update: Q2 deliverables",
            from_="jane@clientcompany.com",
            snippet="Hi Ryan, following up on the Q2 deliverables we discussed.",
        )
        result = _demote_marketing_false_positive(email, _result(category="Client/business"))
        # No marketing signal → not demoted
        self.assertEqual(result["category"], "Client/business")
        self.assertTrue(result["manual_review"])

    def test_receipt_email_not_demoted(self):
        from inbox_scout.ai_classifier import _demote_marketing_false_positive
        email = _email(
            subject="Your receipt from Anthropic, PBC",
            from_="no-reply@anthropic.com",
            snippet="Thank you for your payment. Receipt #2668.",
        )
        result = _demote_marketing_false_positive(email, _result(category="Client/business"))
        # "receipt" and "payment" are danger terms
        self.assertEqual(result["category"], "Client/business")

    def test_security_email_not_demoted(self):
        from inbox_scout.ai_classifier import _demote_marketing_false_positive
        email = _email(
            subject="New device login detected",
            from_="no-reply@accounts.google.com",
            snippet="A new device signed in to your account. If this was you, no action needed.",
        )
        result = _demote_marketing_false_positive(email, _result(category="Job/career"))
        # "login" is a danger term — not demoted
        self.assertEqual(result["category"], "Job/career")

    def test_non_demotable_category_untouched(self):
        # Finance/Security/etc are never eligible for demotion
        from inbox_scout.ai_classifier import _demote_marketing_false_positive
        email = _email(
            subject="No-reply newsletter deals sale promo",
            from_="no-reply@newsletter.example.com",
            snippet="sale discount coupon",
        )
        result = _demote_marketing_false_positive(email, _result(category="Finance"))
        self.assertEqual(result["category"], "Finance")

    def test_demoted_promotion_is_safe_trash_candidate(self):
        # After demotion, is_safe_trash_candidate should accept the item
        from inbox_scout.trash_candidate_plan import is_safe_trash_candidate
        item = {
            "queue_id": "11",
            "message_id": "msg11",
            "category": "Promotion",
            "subject": "Ship your first major feature with Claude Code",
            "from": "Claude Team <no-reply@email.claude.com>",
            "snippet": "Ship features with confidence.",
            "risk_score": 15,
            "manual_review": False,
            "local_decision": "pending_review",
            "gmail_action_type": "",
            "gmail_action_taken": False,
        }
        ok, reason = is_safe_trash_candidate(item)
        self.assertTrue(ok, f"expected safe after demotion; reason: {reason}")


if __name__ == "__main__":
    unittest.main()
