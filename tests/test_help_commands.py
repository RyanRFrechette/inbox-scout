"""Focused tests: /help output covers simplified default and advanced power commands."""
from __future__ import annotations
import unittest

from inbox_scout.telegram_listener import build_help, build_help_advanced
from inbox_scout.natural_intent import help_message, help_message_advanced


class HelpDefaultBase:
    """Mixin for default /help — should show main workflow, not power commands."""

    def _h(self):
        return self.fn()

    def test_main_commands(self):
        h = self._h()
        self.assertIn("cleanup", h)
        self.assertIn("file inbox", h)
        self.assertIn("apply filing", h)

    def test_navigation_commands(self):
        h = self._h()
        self.assertIn("status", h)
        self.assertIn("cancel", h)
        self.assertIn("/help advanced", h)

    def test_basic_commands(self):
        h = self._h()
        self.assertIn("ping", h)
        self.assertIn("queue", h)
        self.assertIn("next", h)

    def test_safety_disclaimer(self):
        h = self._h()
        self.assertIn("permanent delete", h)
        self.assertIn("approval", h)

    def test_no_autopilot_confirm(self):
        h = self._h()
        self.assertNotIn("CONFIRM INBOX AUTOPILOT", h)


class HelpAdvancedBase:
    """Mixin for /help advanced — should show power commands."""

    def _h(self):
        return self.fn()

    def test_sort_commands(self):
        h = self._h()
        self.assertIn("sort all", h)
        self.assertIn("continue sorting", h)

    def test_apply_commands(self):
        h = self._h()
        self.assertIn("apply archive", h)
        self.assertIn("apply trash", h)
        self.assertIn("apply markread", h)

    def test_block_senders(self):
        h = self._h()
        self.assertIn("block senders in trash", h)

    def test_model_commands(self):
        h = self._h()
        self.assertIn("/model status", h)
        self.assertIn("/model local", h)
        self.assertIn("/model openrouter", h)
        self.assertIn("/model auto", h)

    def test_safety_disclaimer(self):
        h = self._h()
        self.assertIn("permanent delete", h)


class TestBuildHelp(HelpDefaultBase, unittest.TestCase):
    def setUp(self):
        self.fn = build_help


class TestHelpMessage(HelpDefaultBase, unittest.TestCase):
    def setUp(self):
        self.fn = help_message


class TestBuildHelpAdvanced(HelpAdvancedBase, unittest.TestCase):
    def setUp(self):
        self.fn = build_help_advanced


class TestHelpMessageAdvanced(HelpAdvancedBase, unittest.TestCase):
    def setUp(self):
        self.fn = help_message_advanced


if __name__ == "__main__":
    unittest.main()
