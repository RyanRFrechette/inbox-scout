"""AI provider routing: local (Ollama) or OpenRouter."""
from __future__ import annotations

import json
import os

import requests

from inbox_scout.paths import CONFIG_DIR

MODEL_SETTINGS_FILE = CONFIG_DIR / "model_settings.json"
VALID_PROVIDERS = {"local", "openrouter", "auto"}

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:8b"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "google/gemini-2.5-flash-lite"

AUTO_MASS_THRESHOLD = 10  # batch_size > this → openrouter in auto mode

ALLOWED_CATEGORIES = [
    "Important",
    "Needs reply",
    "Job/career",
    "Client/business",
    "Bills/receipts",
    "Warranty/support",
    "Finance",
    "Legal",
    "Security alert",
    "Personal",
    "Medical",
    "Newsletter",
    "Promotion",
    "Junk",
    "Archive candidate",
    "Manual review",
]

REQUIRED_KEYS = [
    "category",
    "confidence_score",
    "risk_score",
    "reason",
    "suggested_action",
    "manual_review",
]


def get_provider() -> str:
    """Return current configured provider (default: 'local')."""
    if MODEL_SETTINGS_FILE.exists():
        try:
            data = json.loads(MODEL_SETTINGS_FILE.read_text(encoding="utf-8"))
            p = data.get("provider", "local")
            if p in VALID_PROVIDERS:
                return p
        except Exception:
            pass
    return "local"


def set_provider(provider: str) -> None:
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Valid: {sorted(VALID_PROVIDERS)}")
    MODEL_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODEL_SETTINGS_FILE.write_text(
        json.dumps({"provider": provider}, indent=2),
        encoding="utf-8",
    )


def get_active_provider(batch_size: int = 1) -> str:
    """Resolve 'auto' to a concrete provider based on batch size."""
    p = get_provider()
    if p != "auto":
        return p
    return "openrouter" if batch_size > AUTO_MASS_THRESHOLD else "local"


def is_obvious_trash(rule_result: dict) -> bool:
    """True if low-risk newsletter/promo — AI can be skipped in auto mode."""
    if rule_result.get("manual_review"):
        return False
    category = (rule_result.get("category") or "").lower()
    risk = rule_result.get("risk_score", 100)
    return category in {"newsletter", "promotion"} and risk <= 30


def _build_prompt(email: dict, rule_result: dict) -> str:
    return (
        "You are Inbox Scout, a local-first Gmail cleanup assistant.\n\n"
        "Return ONLY valid JSON. Do not include markdown. Do not explain outside JSON.\n\n"
        f"Allowed categories:\n{ALLOWED_CATEGORIES}\n\n"
        "Required JSON keys:\n"
        "category, confidence_score, risk_score, reason, suggested_action, manual_review\n\n"
        "Scoring:\n"
        "confidence_score must be 0-100.\n"
        "risk_score must be 0-100.\n"
        "manual_review must be true or false.\n\n"
        "Safety rules:\n"
        "- Anything financial, legal, medical, tax, password, security, job, interview, "
        "client, invoice, family, warranty, refund, return, collection, or account access "
        "related must be manual_review true.\n"
        "- Never suggest delete.\n"
        "- Never suggest auto-send.\n"
        "- Never suggest automatic Gmail changes.\n"
        "- If unsure, use Manual review.\n\n"
        f"Rule-based baseline:\n{json.dumps(rule_result, ensure_ascii=False)}\n\n"
        f"Email:\n"
        f"From: {email.get('from', '')}\n"
        f"Subject: {email.get('subject', '')}\n"
        f"Snippet: {email.get('snippet', '')}\n"
    )


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response.")
    return json.loads(text[start:end + 1])


def _normalize_score(value, default: int = 50) -> int:
    try:
        number = float(value)
        if 0 <= number <= 1:
            number *= 100
        return max(0, min(100, int(round(number))))
    except Exception:
        return default


def _validate(result: dict) -> dict:
    for key in REQUIRED_KEYS:
        if key not in result:
            raise ValueError(f"Missing required key: {key}")
    category = result.get("category")
    if category not in ALLOWED_CATEGORIES:
        result["category"] = "Manual review"
        result["reason"] = (
            f"AI returned unsupported category '{category}'. "
            + str(result.get("reason", ""))
        )
        result["manual_review"] = True
        result["risk_score"] = 90
    result["confidence_score"] = _normalize_score(result.get("confidence_score"), default=50)
    result["risk_score"] = _normalize_score(result.get("risk_score"), default=60)
    result["manual_review"] = bool(result.get("manual_review"))
    return result


def _fallback(error: Exception) -> dict:
    return {
        "category": "Manual review",
        "confidence_score": 0,
        "risk_score": 100,
        "reason": f"AI classification failed: {error}",
        "suggested_action": "Review manually.",
        "manual_review": True,
    }


def classify_with_ollama(email: dict, rule_result: dict) -> dict:
    prompt = _build_prompt(email, rule_result)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=180)
        response.raise_for_status()
        raw = response.json().get("response", "")
        return _validate(_extract_json(raw))
    except Exception as e:
        return _fallback(e)


def classify_with_openrouter(email: dict, rule_result: dict) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return _fallback(RuntimeError("OPENROUTER_API_KEY not set"))
    prompt = _build_prompt(email, rule_result)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        return _validate(_extract_json(raw))
    except Exception as e:
        return _fallback(e)


def classify_with_provider(email: dict, rule_result: dict, batch_size: int = 1) -> dict:
    """Classify an email using the configured provider."""
    provider = get_provider()

    # Auto mode: skip AI entirely for obvious low-risk newsletter/promo.
    # Build a complete dict with all REQUIRED_KEYS so downstream display code never KeyErrors.
    if provider == "auto" and is_obvious_trash(rule_result):
        return {
            "category": rule_result.get("category", "Newsletter"),
            "confidence_score": _normalize_score(rule_result.get("confidence_score", 80)),
            "risk_score": _normalize_score(rule_result.get("risk_score", 20)),
            "reason": "Obvious rule trash — no AI needed.",
            "suggested_action": rule_result.get("suggested_action", "Safe to archive."),
            "manual_review": False,
            "ai_skipped": True,
        }

    active = get_active_provider(batch_size=batch_size)
    if active == "openrouter":
        return classify_with_openrouter(email, rule_result)
    return classify_with_ollama(email, rule_result)


def model_status_message() -> str:
    provider = get_provider()
    active = get_active_provider()
    openrouter_key_set = bool(os.environ.get("OPENROUTER_API_KEY", ""))
    lines = [
        f"Model provider: {provider}",
        f"Active provider: {active}",
        f"Local model: {OLLAMA_MODEL}",
        f"OpenRouter model: {OPENROUTER_MODEL}",
        f"OPENROUTER_API_KEY set: {'yes' if openrouter_key_set else 'no'}",
        f"Auto mass threshold: >{AUTO_MASS_THRESHOLD} emails -> openrouter",
    ]
    return "\n".join(lines)
