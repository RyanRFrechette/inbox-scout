"""
Focused tests for scan provider display and timeout handling.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_scan_provider_timeout -v
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestProviderLabel(unittest.TestCase):
    def test_local_provider_label(self):
        from inbox_scout.sort_scan_queue_approval import _provider_label
        with patch("inbox_scout.sort_scan_queue_approval.get_active_provider", return_value="local"), \
             patch("inbox_scout.sort_scan_queue_approval.OLLAMA_MODEL", "qwen3:8b"):
            label = _provider_label(5)
        self.assertIn("local", label)
        self.assertIn("qwen3:8b", label)

    def test_openrouter_provider_label(self):
        from inbox_scout.sort_scan_queue_approval import _provider_label
        with patch("inbox_scout.sort_scan_queue_approval.get_active_provider", return_value="openrouter"), \
             patch("inbox_scout.sort_scan_queue_approval.OPENROUTER_MODEL", "google/gemini-2.5-flash-lite"):
            label = _provider_label(15)
        self.assertIn("openrouter", label)
        self.assertIn("google/gemini-2.5-flash-lite", label)

    def test_large_batch_auto_uses_openrouter(self):
        from inbox_scout.model_router import get_active_provider, AUTO_MASS_THRESHOLD
        with patch("inbox_scout.model_router.get_provider", return_value="auto"):
            provider = get_active_provider(batch_size=AUTO_MASS_THRESHOLD + 1)
        self.assertEqual(provider, "openrouter")

    def test_small_batch_auto_uses_local(self):
        from inbox_scout.model_router import get_active_provider, AUTO_MASS_THRESHOLD
        with patch("inbox_scout.model_router.get_provider", return_value="auto"):
            provider = get_active_provider(batch_size=AUTO_MASS_THRESHOLD)
        self.assertEqual(provider, "local")


class TestScanTimeout(unittest.TestCase):
    def _make_valid_plan(self):
        from datetime import datetime, timezone
        return {
            "workflow_mode": "commands_planned",
            "target": "unread_inbox",
            "requested_limit": 5,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_continuation": False,
            "cleanup_mode": False,
            "sort_all": False,
        }

    def test_timeout_returns_gmail_not_touched(self):
        import inbox_scout.sort_scan_queue_approval as sqa
        plan = self._make_valid_plan()
        with patch.object(sqa, "load_json", return_value=plan), \
             patch.object(sqa, "validate_latest_plan", return_value=(True, "ok")), \
             patch.object(sqa, "run_scan_queue_runner", side_effect=subprocess.TimeoutExpired("cmd", 900)):
            result = sqa.build_scan_approval_response()
        self.assertIn("gmail was not touched", result.lower())
        self.assertIn("timed out", result.lower())
        self.assertIn("sort 5 emails", result.lower())

    def test_timeout_message_includes_provider(self):
        import inbox_scout.sort_scan_queue_approval as sqa
        plan = self._make_valid_plan()
        with patch.object(sqa, "load_json", return_value=plan), \
             patch.object(sqa, "validate_latest_plan", return_value=(True, "ok")), \
             patch.object(sqa, "run_scan_queue_runner", side_effect=subprocess.TimeoutExpired("cmd", 900)), \
             patch.object(sqa, "_provider_label", return_value="Using local: qwen3:8b"):
            result = sqa.build_scan_approval_response()
        self.assertIn("Using local: qwen3:8b", result)

    def test_completion_message_includes_provider(self):
        import inbox_scout.sort_scan_queue_approval as sqa
        from unittest.mock import MagicMock
        plan = self._make_valid_plan()
        mock_result = MagicMock()
        mock_result.returncode = 0
        run_data = {"status": "complete", "queue_output_tail": "Total queued emails: 5\nProtected/manual review: 2\nPending low-risk review: 3"}
        with patch.object(sqa, "load_json", side_effect=[plan, run_data]), \
             patch.object(sqa, "validate_latest_plan", return_value=(True, "ok")), \
             patch.object(sqa, "run_scan_queue_runner", return_value=mock_result), \
             patch.object(sqa, "_provider_label", return_value="Using local: qwen3:8b"):
            result = sqa.build_scan_approval_response()
        self.assertIn("Using local: qwen3:8b", result)
        self.assertIn("read-only", result.lower())


class TestClassifyForReportResilience(unittest.TestCase):
    """Prove classify_for_report survives rule or AI classification exceptions per email."""

    def _fake_email(self):
        return {"message_id": "abc123", "from": "x@example.com", "subject": "Test", "date": "", "snippet": ""}

    def test_rule_classifier_exception_produces_manual_review(self):
        from inbox_scout import report_mode
        email = self._fake_email()
        with patch.object(report_mode, "load_json", return_value={}), \
             patch.object(report_mode, "load_lines", return_value=[]), \
             patch.object(report_mode, "get_active_provider", return_value="local"), \
             patch.object(report_mode, "OLLAMA_MODEL", "qwen3:8b"), \
             patch.object(report_mode, "classify_email", side_effect=RuntimeError("rule crash")):
            results = report_mode.classify_for_report([email])
        self.assertEqual(len(results), 1)
        ai = results[0]["ai_classification"]
        self.assertTrue(ai.get("manual_review"), "failed email must be manual_review=True")
        self.assertGreaterEqual(ai.get("risk_score", 0), 99, "failed email must have max risk")
        self.assertEqual(ai.get("reason"), "ai_provider_error")

    def test_ai_classifier_exception_uses_rule_fallback(self):
        from inbox_scout import report_mode
        email = self._fake_email()
        rule_result = {"category": "Newsletter", "risk_score": 40, "manual_review": False, "confidence_score": 70, "suggested_action": "Archive."}
        with patch.object(report_mode, "load_json", return_value={}), \
             patch.object(report_mode, "load_lines", return_value=[]), \
             patch.object(report_mode, "get_active_provider", return_value="local"), \
             patch.object(report_mode, "OLLAMA_MODEL", "qwen3:8b"), \
             patch.object(report_mode, "classify_email", return_value=rule_result), \
             patch.object(report_mode, "classify_with_ai", side_effect=ConnectionError("provider down")):
            results = report_mode.classify_for_report([email])
        self.assertEqual(len(results), 1)
        ai = results[0]["ai_classification"]
        self.assertEqual(ai.get("category"), "Newsletter")
        self.assertIn("fallback", ai.get("reason", "").lower())

    def test_provider_lookup_exception_falls_back_to_local(self):
        from inbox_scout import report_mode
        email = self._fake_email()
        rule_result = {"category": "Newsletter", "risk_score": 20, "manual_review": False, "confidence_score": 80, "suggested_action": "Archive."}
        ai_result = {**rule_result, "reason": "ok"}
        with patch.object(report_mode, "load_json", return_value={}), \
             patch.object(report_mode, "load_lines", return_value=[]), \
             patch.object(report_mode, "get_active_provider", side_effect=RuntimeError("env broken")), \
             patch.object(report_mode, "OLLAMA_MODEL", "qwen3:8b"), \
             patch.object(report_mode, "classify_email", return_value=rule_result), \
             patch.object(report_mode, "classify_with_ai", return_value=ai_result):
            results = report_mode.classify_for_report([email])
        self.assertEqual(len(results), 1)

    def test_failed_email_never_produces_trash_candidate(self):
        from inbox_scout import report_mode
        email = self._fake_email()
        with patch.object(report_mode, "load_json", return_value={}), \
             patch.object(report_mode, "load_lines", return_value=[]), \
             patch.object(report_mode, "get_active_provider", return_value="local"), \
             patch.object(report_mode, "OLLAMA_MODEL", "qwen3:8b"), \
             patch.object(report_mode, "classify_email", side_effect=RuntimeError("crash")):
            results = report_mode.classify_for_report([email])
        ai = results[0]["ai_classification"]
        action = ai.get("suggested_action", "").lower()
        self.assertNotIn("trash", action)
        self.assertNotIn("archive", action)
        self.assertNotIn("mark read", action)


if __name__ == "__main__":
    unittest.main()
