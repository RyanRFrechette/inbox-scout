"""
Focused tests for model_router provider switching and auto-select logic.
Run: $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_model_router -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_scout.model_router import (
    AUTO_MASS_THRESHOLD,
    REQUIRED_KEYS,
    VALID_PROVIDERS,
    get_active_provider,
    get_provider,
    is_obvious_trash,
    set_provider,
    _normalize_score,
    _validate,
    _extract_json,
    classify_with_provider,
    model_status_message,
)


def _settings_file_patch(tmp_dir: str):
    return patch(
        "inbox_scout.model_router.MODEL_SETTINGS_FILE",
        Path(tmp_dir) / "model_settings.json",
    )


class TestGetProvider(unittest.TestCase):
    def test_default_is_local_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                self.assertEqual(get_provider(), "local")

    def test_reads_provider_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "model_settings.json"
            p.write_text(json.dumps({"provider": "openrouter"}), encoding="utf-8")
            with _settings_file_patch(tmp):
                self.assertEqual(get_provider(), "openrouter")

    def test_returns_local_for_invalid_value_in_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "model_settings.json"
            p.write_text(json.dumps({"provider": "bogus"}), encoding="utf-8")
            with _settings_file_patch(tmp):
                self.assertEqual(get_provider(), "local")

    def test_returns_local_for_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "model_settings.json"
            p.write_text("not json", encoding="utf-8")
            with _settings_file_patch(tmp):
                self.assertEqual(get_provider(), "local")


class TestSetProvider(unittest.TestCase):
    def test_set_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("local")
                self.assertEqual(get_provider(), "local")

    def test_set_openrouter(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("openrouter")
                self.assertEqual(get_provider(), "openrouter")

    def test_set_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("auto")
                self.assertEqual(get_provider(), "auto")

    def test_invalid_provider_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                with self.assertRaises(ValueError):
                    set_provider("bogus")


class TestGetActiveProvider(unittest.TestCase):
    def test_local_stays_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("local")
                self.assertEqual(get_active_provider(batch_size=100), "local")

    def test_openrouter_stays_openrouter(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("openrouter")
                self.assertEqual(get_active_provider(batch_size=1), "openrouter")

    def test_auto_small_batch_returns_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("auto")
                self.assertEqual(get_active_provider(batch_size=AUTO_MASS_THRESHOLD), "local")

    def test_auto_large_batch_returns_openrouter(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("auto")
                self.assertEqual(get_active_provider(batch_size=AUTO_MASS_THRESHOLD + 1), "openrouter")


class TestIsObviousTrash(unittest.TestCase):
    def test_low_risk_newsletter_is_obvious(self):
        rule = {"category": "Newsletter", "risk_score": 20, "manual_review": False}
        self.assertTrue(is_obvious_trash(rule))

    def test_low_risk_promotion_is_obvious(self):
        rule = {"category": "Promotion", "risk_score": 30, "manual_review": False}
        self.assertTrue(is_obvious_trash(rule))

    def test_high_risk_newsletter_is_not_obvious(self):
        rule = {"category": "Newsletter", "risk_score": 50, "manual_review": False}
        self.assertFalse(is_obvious_trash(rule))

    def test_manual_review_is_never_obvious(self):
        rule = {"category": "Newsletter", "risk_score": 5, "manual_review": True}
        self.assertFalse(is_obvious_trash(rule))

    def test_non_newsletter_category_is_not_obvious(self):
        rule = {"category": "Finance", "risk_score": 10, "manual_review": False}
        self.assertFalse(is_obvious_trash(rule))

    def test_risk_exactly_30_is_obvious(self):
        rule = {"category": "Newsletter", "risk_score": 30, "manual_review": False}
        self.assertTrue(is_obvious_trash(rule))

    def test_risk_31_is_not_obvious(self):
        rule = {"category": "Newsletter", "risk_score": 31, "manual_review": False}
        self.assertFalse(is_obvious_trash(rule))


class TestNormalizeScore(unittest.TestCase):
    def test_integer_in_range(self):
        self.assertEqual(_normalize_score(75), 75)

    def test_float_fraction_scaled(self):
        self.assertEqual(_normalize_score(0.5), 50)

    def test_clamps_above_100(self):
        self.assertEqual(_normalize_score(150), 100)

    def test_clamps_below_0(self):
        self.assertEqual(_normalize_score(-10), 0)

    def test_invalid_returns_default(self):
        self.assertEqual(_normalize_score("bad", default=42), 42)


class TestValidate(unittest.TestCase):
    def _valid_result(self, **overrides):
        base = {
            "category": "Newsletter",
            "confidence_score": 80,
            "risk_score": 20,
            "reason": "Looks like a newsletter.",
            "suggested_action": "Archive.",
            "manual_review": False,
        }
        base.update(overrides)
        return base

    def test_valid_passes(self):
        result = _validate(self._valid_result())
        self.assertEqual(result["category"], "Newsletter")

    def test_unknown_category_remapped_to_manual_review(self):
        result = _validate(self._valid_result(category="Spam"))
        self.assertEqual(result["category"], "Manual review")
        self.assertTrue(result["manual_review"])

    def test_missing_key_raises(self):
        bad = self._valid_result()
        del bad["reason"]
        with self.assertRaises(ValueError):
            _validate(bad)

    def test_fraction_score_normalized(self):
        result = _validate(self._valid_result(confidence_score=0.8))
        self.assertEqual(result["confidence_score"], 80)


class TestExtractJson(unittest.TestCase):
    def test_extracts_embedded_json(self):
        text = 'Here is the response: {"key": "value"} done.'
        self.assertEqual(_extract_json(text), {"key": "value"})

    def test_raises_on_no_json(self):
        with self.assertRaises(ValueError):
            _extract_json("no json here")


class TestClassifyWithProvider(unittest.TestCase):
    def _email(self):
        return {"from": "news@example.com", "subject": "Weekly Digest", "snippet": "Top stories"}

    def _obvious_rule(self):
        return {
            "category": "Newsletter",
            "risk_score": 20,
            "manual_review": False,
            "confidence_score": 80,
            "reason": "Rule match.",
            "suggested_action": "Archive.",
        }

    def test_auto_obvious_trash_skips_ai(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("auto")
                result = classify_with_provider(self._email(), self._obvious_rule(), batch_size=5)
        self.assertTrue(result.get("ai_skipped"))

    def test_auto_obvious_trash_returns_all_required_keys(self):
        # rule_result missing confidence_score and suggested_action — common for rule-only results
        minimal_rule = {"category": "Newsletter", "risk_score": 20, "manual_review": False}
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("auto")
                result = classify_with_provider(self._email(), minimal_rule, batch_size=5)
        self.assertTrue(result.get("ai_skipped"))
        for key in REQUIRED_KEYS:
            self.assertIn(key, result, f"auto-skip result missing key: {key}")
        _ = result["confidence_score"]
        _ = result["suggested_action"]

    def test_local_calls_ollama(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("local")
                with patch("inbox_scout.model_router.classify_with_ollama") as mock_ollama:
                    mock_ollama.return_value = self._obvious_rule()
                    classify_with_provider(self._email(), self._obvious_rule())
                    mock_ollama.assert_called_once()

    def test_openrouter_calls_openrouter(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("openrouter")
                with patch("inbox_scout.model_router.classify_with_openrouter") as mock_or:
                    mock_or.return_value = self._obvious_rule()
                    classify_with_provider(self._email(), self._obvious_rule())
                    mock_or.assert_called_once()

    def test_openrouter_missing_api_key_returns_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("openrouter")
                with patch.dict(os.environ, {}, clear=True):
                    os.environ.pop("OPENROUTER_API_KEY", None)
                    result = classify_with_provider(self._email(), self._obvious_rule())
        self.assertEqual(result["category"], "Manual review")
        self.assertTrue(result["manual_review"])

    def test_auto_large_batch_calls_openrouter(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("auto")
                non_obvious = {**self._obvious_rule(), "risk_score": 60}
                with patch("inbox_scout.model_router.classify_with_openrouter") as mock_or:
                    mock_or.return_value = self._obvious_rule()
                    classify_with_provider(self._email(), non_obvious, batch_size=AUTO_MASS_THRESHOLD + 1)
                    mock_or.assert_called_once()

    def test_auto_small_batch_calls_ollama(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("auto")
                non_obvious = {**self._obvious_rule(), "risk_score": 60}
                with patch("inbox_scout.model_router.classify_with_ollama") as mock_ol:
                    mock_ol.return_value = self._obvious_rule()
                    classify_with_provider(self._email(), non_obvious, batch_size=5)
                    mock_ol.assert_called_once()


class TestModelStatusMessage(unittest.TestCase):
    def test_contains_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _settings_file_patch(tmp):
                set_provider("local")
                msg = model_status_message()
        self.assertIn("local", msg)
        self.assertIn("OPENROUTER_API_KEY", msg)


if __name__ == "__main__":
    unittest.main()
