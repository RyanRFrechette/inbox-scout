"""
Focused tests for env_loader: key presence detection without value exposure.

Proves:
- openrouter_key_present() detects key without revealing value
- Missing/empty key fails safe (returns False)
- env_status() never exposes the key value
- load_env() returns False safely when .env absent
- Importing env_loader does not touch any Gmail modules

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_env_loader -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestKeyPresence(unittest.TestCase):
    def test_key_present_returns_true(self):
        from inbox_scout.env_loader import openrouter_key_present
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test-abc123"}):
            self.assertTrue(openrouter_key_present())

    def test_key_absent_returns_false(self):
        from inbox_scout.env_loader import openrouter_key_present
        clean = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
        with patch.dict(os.environ, clean, clear=True):
            self.assertFalse(openrouter_key_present())

    def test_key_empty_string_returns_false(self):
        from inbox_scout.env_loader import openrouter_key_present
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            self.assertFalse(openrouter_key_present())

    def test_key_whitespace_only_returns_false(self):
        from inbox_scout.env_loader import openrouter_key_present
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "   "}):
            self.assertFalse(openrouter_key_present())


class TestEnvStatus(unittest.TestCase):
    def test_status_does_not_reveal_value(self):
        from inbox_scout.env_loader import env_status
        secret = "sk-or-super-secret-key-9999"
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": secret}):
            status = env_status()
            self.assertNotIn(secret, status)
            self.assertIn("set", status)

    def test_status_not_set_message(self):
        from inbox_scout.env_loader import env_status
        clean = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
        with patch.dict(os.environ, clean, clear=True):
            self.assertIn("not set", env_status())


class TestLoadEnv(unittest.TestCase):
    def test_returns_false_when_no_dotenv_file(self):
        from inbox_scout import env_loader
        with patch.object(env_loader, "DOT_ENV_PATH", MagicMock(exists=lambda: False)):
            self.assertFalse(env_loader.load_env())

    def test_returns_true_when_file_exists_and_dotenv_available(self):
        from inbox_scout import env_loader
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        with patch.object(env_loader, "DOT_ENV_PATH", mock_path), \
             patch("inbox_scout.env_loader.load_dotenv", create=True):
            # patch the dotenv import inside load_env
            import types
            fake_dotenv = types.ModuleType("dotenv")
            fake_dotenv.load_dotenv = MagicMock(return_value=True)
            with patch.dict(sys.modules, {"dotenv": fake_dotenv}):
                result = env_loader.load_env()
            self.assertTrue(result)


class TestNoGmailTouched(unittest.TestCase):
    def test_import_does_not_load_gmail_modules(self):
        gmail_before = {k for k in sys.modules if "gmail" in k.lower()}
        # Force reimport
        for key in list(sys.modules.keys()):
            if "env_loader" in key:
                del sys.modules[key]
        import inbox_scout.env_loader  # noqa: F401
        gmail_after = {k for k in sys.modules if "gmail" in k.lower()}
        self.assertEqual(gmail_before, gmail_after)


if __name__ == "__main__":
    unittest.main()
