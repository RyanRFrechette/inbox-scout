"""
Test: runner protected-text matching uses word boundaries.

Proves:
- "irs" does NOT match "first" (false positive fixed)
- "irs" still matches "IRS notice" and "irs.gov"
- Claude/product emails with "first" in subject are no longer runner-blocked
- Real IRS/tax emails are still blocked with the matched term in reason
- find_protected_text_terms and validate_candidate surface matched terms accurately

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_runner_protected_text_visibility -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _queue_item(**kw):
    base = {
        "queue_id": "12",
        "message_id": "msgABC",
        "category": "Promotion",
        "subject": "Ship your first major feature with Claude Code",
        "from": "Claude Team <no-reply@email.claude.com>",
        "snippet": "Do hours or even days of work in minutes.",
        "risk_score": 15,
        "manual_review": False,
        "local_decision": "pending_review",
        "gmail_action_type": "",
        "gmail_action_taken": False,
        "gmail_trashed": False,
        "reason": "",
    }
    base.update(kw)
    return base


class TestFindProtectedTextTerms(unittest.TestCase):

    def test_first_in_subject_does_not_match_irs(self):
        from inbox_scout.trash_execution_runner import find_protected_text_terms
        item = _queue_item(subject="Ship your first major feature with Claude Code")
        matched = find_protected_text_terms(item)
        self.assertNotIn("irs", matched)

    def test_first_in_title_does_not_match_irs(self):
        from inbox_scout.trash_execution_runner import find_protected_text_terms
        item = _queue_item(subject="Make AI Ask Questions First")
        matched = find_protected_text_terms(item)
        self.assertNotIn("irs", matched)

    def test_first_commit_snippet_does_not_match_irs(self):
        from inbox_scout.trash_execution_runner import find_protected_text_terms
        item = _queue_item(
            subject="Welcome to Claude Code",
            snippet="Ship your first commit in 5 minutes.",
        )
        matched = find_protected_text_terms(item)
        self.assertNotIn("irs", matched)

    def test_irs_notice_still_matches(self):
        from inbox_scout.trash_execution_runner import find_protected_text_terms
        item = _queue_item(subject="IRS notice: action required on your account")
        matched = find_protected_text_terms(item)
        self.assertIn("irs", matched)

    def test_irs_gov_still_matches(self):
        from inbox_scout.trash_execution_runner import find_protected_text_terms
        # "." is non-word so \birs\b matches "irs" in "irs.gov"
        item = _queue_item(subject="Visit irs.gov for your tax refund status")
        matched = find_protected_text_terms(item)
        self.assertIn("irs", matched)

    def test_clean_item_returns_empty(self):
        from inbox_scout.trash_execution_runner import find_protected_text_terms
        item = _queue_item(subject="Daily Deals: More ways to save", snippet="Shop now.")
        matched = find_protected_text_terms(item)
        self.assertEqual(matched, [])

    def test_real_protected_terms_detected(self):
        from inbox_scout.trash_execution_runner import find_protected_text_terms
        item = _queue_item(subject="Your receipt from Anthropic", snippet="Payment confirmed.")
        matched = find_protected_text_terms(item)
        self.assertIn("receipt", matched)
        self.assertIn("payment", matched)


class TestValidateCandidateSurfacedReason(unittest.TestCase):

    def test_claude_code_first_email_now_passes(self):
        # After fix: "first" no longer triggers IRS block
        from inbox_scout.inbox_cleanup_runner import validate_candidate
        candidate = {"queue_id": "12"}
        item = _queue_item(queue_id="12", subject="Ship your first major feature with Claude Code")
        ok, reason = validate_candidate(candidate, [item])
        self.assertTrue(ok, f"expected pass after irs fix; reason: {reason}")

    def test_real_irs_email_blocked_with_matched_term(self):
        from inbox_scout.inbox_cleanup_runner import validate_candidate
        candidate = {"queue_id": "55"}
        item = _queue_item(
            queue_id="55",
            subject="IRS notice: action required",
            snippet="Please review your tax filing.",
        )
        ok, reason = validate_candidate(candidate, [item])
        self.assertFalse(ok)
        self.assertIn("irs", reason)

    def test_clean_newsletter_passes_validate(self):
        from inbox_scout.inbox_cleanup_runner import validate_candidate
        candidate = {"queue_id": "99"}
        item = _queue_item(
            queue_id="99",
            category="Promotion",
            subject="Daily Deals: More ways to save",
            **{"from": "deals@newsletter.example.com"},
            snippet="Shop brands you love. Unsubscribe anytime.",
        )
        ok, reason = validate_candidate(candidate, [item])
        self.assertTrue(ok, f"expected pass; reason: {reason}")


class TestAuditItemRunnerBlock(unittest.TestCase):

    def test_newsletter_with_first_is_now_trash_candidate(self):
        from inbox_scout.queue_audit import audit_item
        item = _queue_item(subject="Ship your first major feature with Claude Code")
        bucket, code, _ = audit_item(item)
        self.assertEqual(bucket, "trash_candidate")
        self.assertEqual(code, "trash_candidate_newsletter_promotion")

    def test_questions_first_newsletter_is_now_trash_candidate(self):
        from inbox_scout.queue_audit import audit_item
        item = _queue_item(category="Newsletter", subject="Make AI Ask Questions First")
        bucket, code, _ = audit_item(item)
        self.assertEqual(bucket, "trash_candidate")
        self.assertEqual(code, "trash_candidate_newsletter_promotion")

    def test_irs_notice_newsletter_is_still_runner_block(self):
        from inbox_scout.queue_audit import audit_item
        item = _queue_item(subject="IRS notice: action required on your account")
        bucket, code, human = audit_item(item)
        self.assertEqual(bucket, "runner_block")
        self.assertEqual(code, "final_runner_blocked_by_protected_text")
        self.assertIn("irs", human)

    def test_newsletter_without_protected_text_is_trash_candidate(self):
        from inbox_scout.queue_audit import audit_item
        item = _queue_item(
            subject="Daily Deals: More ways to save",
            snippet="Shop brands you love. Unsubscribe anytime.",
        )
        bucket, code, _ = audit_item(item)
        self.assertEqual(bucket, "trash_candidate")
        self.assertEqual(code, "trash_candidate_newsletter_promotion")


if __name__ == "__main__":
    unittest.main()
