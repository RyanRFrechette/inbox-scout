"""
Test: runner protected-text blocks are surfaced with the matched term.

Proves:
- find_protected_text_terms returns the matched term(s)
- validate_candidate skip reason includes matched term
- audit_item returns runner_block bucket with matched term in human_reason

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

    def test_irs_in_first_is_detected(self):
        from inbox_scout.trash_execution_runner import find_protected_text_terms
        item = _queue_item(subject="Ship your first major feature")
        matched = find_protected_text_terms(item)
        self.assertIn("irs", matched)

    def test_ask_questions_first_is_detected(self):
        from inbox_scout.trash_execution_runner import find_protected_text_terms
        item = _queue_item(subject="Make AI Ask Questions First")
        matched = find_protected_text_terms(item)
        self.assertIn("irs", matched)

    def test_clean_item_returns_empty(self):
        from inbox_scout.trash_execution_runner import find_protected_text_terms
        item = _queue_item(subject="Daily Deals: More ways to save", snippet="Shop now.")
        matched = find_protected_text_terms(item)
        self.assertEqual(matched, [])

    def test_real_protected_term_detected(self):
        from inbox_scout.trash_execution_runner import find_protected_text_terms
        item = _queue_item(subject="Your receipt from Anthropic", snippet="Payment confirmed.")
        matched = find_protected_text_terms(item)
        self.assertIn("receipt", matched)
        self.assertIn("payment", matched)


class TestValidateCandidateSurfacedReason(unittest.TestCase):

    def test_skip_reason_includes_matched_term(self):
        from inbox_scout.inbox_cleanup_runner import validate_candidate
        candidate = {"queue_id": "12"}
        item = _queue_item(queue_id="12", subject="Ship your first major feature with Claude Code")
        ok, reason = validate_candidate(candidate, [item])
        self.assertFalse(ok)
        self.assertIn("irs", reason)

    def test_clean_newsletter_passes_validate(self):
        from inbox_scout.inbox_cleanup_runner import validate_candidate
        candidate = {"queue_id": "99"}
        item = _queue_item(
            queue_id="99",
            subject="Daily Deals: More ways to save",
            from_="deals@newsletter.example.com",
            snippet="Shop brands you love. Unsubscribe anytime.",
        )
        item["from"] = item.pop("from_", item.get("from", ""))
        ok, reason = validate_candidate(candidate, [item])
        self.assertTrue(ok, f"expected pass; reason: {reason}")


class TestAuditItemRunnerBlock(unittest.TestCase):

    def test_newsletter_with_first_in_subject_is_runner_block(self):
        from inbox_scout.queue_audit import audit_item
        item = _queue_item(subject="Ship your first major feature with Claude Code")
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

    def test_personal_marketing_rescue_with_protected_text_is_runner_block(self):
        from inbox_scout.queue_audit import audit_item
        item = _queue_item(
            category="Personal",
            subject="Special offer — save on your first order",
            snippet="Unsubscribe anytime.",
        )
        bucket, code, human = audit_item(item)
        self.assertEqual(bucket, "runner_block")
        self.assertEqual(code, "final_runner_blocked_by_protected_text")
        self.assertIn("irs", human)


if __name__ == "__main__":
    unittest.main()
