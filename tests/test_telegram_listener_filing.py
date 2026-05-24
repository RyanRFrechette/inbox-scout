"""
Tests: filing apply commands intercepted before Telegram Apply Gate.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_telegram_listener_filing -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

_NATURAL = "NATURAL"
_APPLY_GATE = "Telegram Apply Gate"


def _handle(text: str) -> str:
    from inbox_scout import telegram_listener
    with patch.object(telegram_listener, "evaluate_apply_gate", return_value=_APPLY_GATE) as mock_gate, \
         patch.object(telegram_listener, "evaluate_confirm_gate", return_value="CONFIRM_GATE"), \
         patch.object(telegram_listener, "evaluate_approval_command", return_value="APPROVAL"), \
         patch.object(telegram_listener, "handle_natural_message", return_value="NATURAL"):
        result = telegram_listener.handle_command(text)
    return result


class TestFilingApplyPreGuard(unittest.TestCase):
    def test_apply_filing_routes_to_natural(self):
        self.assertEqual(_NATURAL, _handle("apply filing"))

    def test_confirm_filing_routes_to_natural(self):
        self.assertEqual(_NATURAL, _handle("confirm filing"))

    def test_run_filing_routes_to_natural(self):
        self.assertEqual(_NATURAL, _handle("run filing"))

    def test_apply_filing_not_apply_gate(self):
        self.assertNotIn(_APPLY_GATE, _handle("apply filing"))

    def test_confirm_filing_not_confirm_gate(self):
        self.assertNotEqual("CONFIRM_GATE", _handle("confirm filing"))

    def test_apply_archive_still_hits_apply_gate(self):
        self.assertEqual(_APPLY_GATE, _handle("apply archive 2"))

    def test_apply_trash_still_hits_apply_gate(self):
        self.assertEqual(_APPLY_GATE, _handle("apply trash 2"))

    def test_apply_markread_still_hits_apply_gate(self):
        self.assertEqual(_APPLY_GATE, _handle("apply markread 2"))

    def test_confirm_trash_plan_still_hits_confirm_gate(self):
        self.assertEqual("CONFIRM_GATE", _handle("confirm trash plan"))


if __name__ == "__main__":
    unittest.main()
