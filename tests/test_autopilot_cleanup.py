"""
Orchestration tests: run_autopilot_cleanup chains scan → plan → trash runner in order.

Proves:
- Correct call order: build_plan → save_plan → run_scan → build_cleanup_plan → runner
- Scan failure blocks runner (Gmail not touched)
- Zero candidates blocks runner (Gmail not touched)
- Runner used is the existing build_inbox_cleanup_runner_message safety gate
- Limit is capped at 25

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_autopilot_cleanup -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _run(
    text: str = "clean 25 emails",
    *,
    scan_rc: int = 0,
    scan_status: str = "complete",
    scanned: int = 10,
    protected: int = 3,
    needs_review: int = 2,
    candidates: int = 5,
) -> tuple[str, list[str]]:
    from inbox_scout.autopilot_cleanup import run_autopilot_cleanup

    call_order: list[str] = []

    mock_plan = MagicMock()
    mock_plan.workflow_mode = "commands_planned"
    mock_plan.requested_limit = 25

    mock_cleanup = MagicMock()
    mock_cleanup.total_scanned = scanned
    mock_cleanup.protected_count = protected
    mock_cleanup.needs_review_count = needs_review
    mock_cleanup.trash_candidate_count = candidates

    mock_proc = MagicMock()
    mock_proc.returncode = scan_rc

    def fake_build_plan(msg: str):
        call_order.append("build_plan")
        return mock_plan

    def fake_save_plan(p):
        call_order.append("save_plan")

    def fake_run_scan():
        call_order.append("run_scan")
        return mock_proc

    def fake_build_cleanup_plan():
        call_order.append("build_cleanup_plan")
        return mock_cleanup

    def fake_runner():
        call_order.append("runner")
        return "Moved 5 emails to Gmail Trash for review."

    with (
        patch("inbox_scout.autopilot_cleanup.build_scan_queue_plan", fake_build_plan),
        patch("inbox_scout.autopilot_cleanup.save_plan", fake_save_plan),
        patch("inbox_scout.autopilot_cleanup._run_scan", fake_run_scan),
        patch("inbox_scout.autopilot_cleanup._load_json", return_value={"status": scan_status}),
        patch("inbox_scout.autopilot_cleanup.build_inbox_cleanup_plan", fake_build_cleanup_plan),
        patch("inbox_scout.autopilot_cleanup.build_inbox_cleanup_runner_message", fake_runner),
    ):
        result = run_autopilot_cleanup(text)

    return result, call_order


class TestAutopilotOrchestration(unittest.TestCase):
    def test_call_order_full_flow(self):
        _, order = _run()
        self.assertEqual(
            order,
            ["build_plan", "save_plan", "run_scan", "build_cleanup_plan", "runner"],
        )

    def test_runner_output_in_result(self):
        result, _ = _run()
        self.assertIn("Moved 5 emails", result)

    def test_header_includes_counts(self):
        result, _ = _run(scanned=10, protected=3, needs_review=2, candidates=5)
        self.assertIn("10", result)
        self.assertIn("3 protected", result)
        self.assertIn("2 unclear", result)
        self.assertIn("5 trash candidates", result)

    def test_zero_candidates_blocks_runner(self):
        result, order = _run(candidates=0)
        self.assertNotIn("runner", order)
        self.assertIn("Gmail not touched", result)
        self.assertIn("Protected and unclear emails were left alone", result)

    def test_scan_failure_blocks_runner(self):
        result, order = _run(scan_rc=1, scan_status="report_failed")
        self.assertNotIn("runner", order)
        self.assertNotIn("build_cleanup_plan", order)
        self.assertIn("Gmail not touched", result)

    def test_scan_status_incomplete_blocks_runner(self):
        result, order = _run(scan_rc=0, scan_status="report_failed")
        self.assertNotIn("runner", order)
        self.assertIn("Gmail not touched", result)

    def test_zero_scanned_blocks_runner(self):
        result, order = _run(scanned=0, candidates=0)
        self.assertNotIn("runner", order)
        self.assertIn("Gmail not touched", result)

    def test_uses_build_inbox_cleanup_runner_message(self):
        # Verifies the runner used is the existing safety gate, not a bypass
        _, order = _run()
        self.assertIn("runner", order)

    def test_cap_notice_shown_when_over_limit(self):
        result, _ = _run(text="clean 50 emails")
        self.assertIn("capped at 25", result)
        self.assertIn("50", result)

    def test_no_cap_notice_at_or_under_limit(self):
        result, _ = _run(text="clean 25 emails")
        self.assertNotIn("capped", result)

    def test_limit_parse_with_number(self):
        from inbox_scout.autopilot_cleanup import _parse_limit
        self.assertEqual(_parse_limit("clean 25 emails"), 25)
        self.assertEqual(_parse_limit("sort 10 emails"), 10)

    def test_limit_capped_at_25(self):
        from inbox_scout.autopilot_cleanup import _parse_limit
        self.assertEqual(_parse_limit("sort 50 emails"), 25)
        self.assertEqual(_parse_limit("sort 100 emails"), 25)

    def test_limit_default_when_no_number(self):
        from inbox_scout.autopilot_cleanup import _parse_limit
        self.assertEqual(_parse_limit("handle a batch"), 25)
        self.assertEqual(_parse_limit("get me closer to inbox zero"), 25)
        self.assertEqual(_parse_limit("clean up my inbox"), 25)


if __name__ == "__main__":
    unittest.main()
