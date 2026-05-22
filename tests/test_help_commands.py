"""Focused tests: /help output covers all real command groups and safety disclaimer."""
from __future__ import annotations
import unittest

from inbox_scout.telegram_listener import build_help
from inbox_scout.natural_intent import help_message


class HelpContentBase:
    """Mixin — subclasses set self.fn before setUp runs."""

    def _h(self):
        return self.fn()

    def test_read_only_commands(self):
        h = self._h()
        self.assertIn("ping", h)
        self.assertIn("status", h)
        self.assertIn("queue", h)
        self.assertIn("next", h)

    def test_sort_commands(self):
        h = self._h()
        self.assertIn("sort", h)
        self.assertIn("sort all", h)
        self.assertIn("continue sorting", h)

    def test_cleanup_commands(self):
        h = self._h()
        self.assertIn("clean", h)
        self.assertIn("inbox zero", h)
        self.assertIn("move trash", h)

    def test_resort_commands(self):
        h = self._h()
        self.assertIn("resort preview", h)
        self.assertIn("resort my sorted emails", h)
        self.assertIn("resort all mail", h)
        self.assertIn("apply resort fixes", h)

    def test_trash_archive_commands(self):
        h = self._h()
        self.assertIn("trash candidates", h)
        self.assertIn("archive", h)

    def test_mark_read_commands(self):
        h = self._h()
        self.assertIn("mark reviewed as read", h)
        self.assertIn("confirm mark read", h)

    def test_block_senders_commands(self):
        h = self._h()
        self.assertIn("block senders in trash", h)

    def test_model_commands(self):
        h = self._h()
        self.assertIn("/model status", h)
        self.assertIn("/model local", h)
        self.assertIn("/model openrouter", h)
        self.assertIn("/model auto", h)

    def test_confirm_cancel(self):
        h = self._h()
        self.assertIn("yes", h)
        self.assertIn("cancel", h)

    def test_safety_disclaimer(self):
        h = self._h()
        self.assertIn("protected", h)
        self.assertIn("permanent delete", h)
        self.assertIn("approval", h)


class TestBuildHelp(HelpContentBase, unittest.TestCase):
    def setUp(self):
        self.fn = build_help


class TestHelpMessage(HelpContentBase, unittest.TestCase):
    def setUp(self):
        self.fn = help_message


if __name__ == "__main__":
    unittest.main()
