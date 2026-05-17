"""LLM-backed natural intent parser for Atlas.

Runs only after all deterministic routes in natural_intent.py have failed.
The LLM returns a structured intent dict — it never performs Gmail actions.
"""
from __future__ import annotations

import json
import os

import requests

ALLOWED_INTENTS = {
    "inbox_count",
    "inbox_zero_autopilot",
    "queue_summary",
    "next_review_item",
    "model_status",
    "help",
    "unknown",
}

CONFIDENCE_THRESHOLD = 0.75

_OLLAMA_URL = "http://localhost:11434/api/generate"
_OLLAMA_MODEL = "qwen3:8b"

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OPENROUTER_MODEL = "google/gemini-2.5-flash-lite"


def _build_prompt(text: str) -> str:
    safe = text.replace('"', "'")
    return (
        "You are Atlas, a Telegram bot controlling Inbox Scout (Gmail cleanup assistant).\n"
        f'User message: "{safe}"\n\n'
        "Classify into exactly one intent:\n"
        "- inbox_count: user wants to know how many/how full/how bad their inbox is\n"
        "- inbox_zero_autopilot: user wants to process, clean, sort, organize, file, handle, or deal with inbox emails\n"
        "- queue_summary: user wants to see the current review queue or scanned email batch\n"
        "- next_review_item: user wants to see the next email needing review\n"
        "- model_status: user wants to know which AI model is active\n"
        "- help: user wants help or a list of commands\n"
        "- unknown: cannot confidently classify\n\n"
        "Return ONLY valid JSON:\n"
        '{"intent":"...","confidence":0.0,'
        '"scope":"inbox|unread_inbox|queue|unknown",'
        '"limit":"all|number|default|unknown",'
        '"provider_preference":"auto|local|openrouter|unknown",'
        '"requires_write":false,"clarifying_question":""}\n\n'
        "Safety rules (never violate):\n"
        "- inbox_zero_autopilot is the ONLY intent that may set requires_write true.\n"
        "- If the user asks to delete, empty trash, block senders, reply, or send: return intent 'unknown'.\n"
        "- If confidence < 0.75, provide a short clarifying_question.\n"
        "- No text outside the JSON object.\n"
    )


def _unknown(reason: str = "") -> dict:
    result: dict = {
        "intent": "unknown",
        "confidence": 0.0,
        "scope": "unknown",
        "limit": "unknown",
        "provider_preference": "unknown",
        "requires_write": False,
        "clarifying_question": "",
    }
    if reason:
        result["_debug"] = reason
    return result


def _parse_response(raw: str) -> dict:
    """Extract, validate, and sanitize a JSON intent from raw LLM output."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return _unknown("no JSON in response")

    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return _unknown("invalid JSON")

    intent = str(parsed.get("intent", "unknown")).strip().lower()
    if intent not in ALLOWED_INTENTS:
        return _unknown(f"disallowed intent '{intent}'")

    try:
        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    # requires_write is only valid for inbox_zero_autopilot
    requires_write = bool(parsed.get("requires_write", False))
    if requires_write and intent != "inbox_zero_autopilot":
        requires_write = False

    return {
        "intent": intent,
        "confidence": confidence,
        "scope": str(parsed.get("scope", "unknown")),
        "limit": str(parsed.get("limit", "default")),
        "provider_preference": str(parsed.get("provider_preference", "auto")),
        "requires_write": requires_write,
        "clarifying_question": str(parsed.get("clarifying_question", "")),
    }


def _call_ollama(text: str) -> dict:
    try:
        payload = {
            "model": _OLLAMA_MODEL,
            "prompt": _build_prompt(text),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        r = requests.post(_OLLAMA_URL, json=payload, timeout=30)
        r.raise_for_status()
        raw = r.json().get("response", "")
        return _parse_response(raw)
    except Exception:
        return _unknown("ollama_unavailable")


def _call_openrouter(text: str) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return _unknown("OPENROUTER_API_KEY not set")
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": _OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": _build_prompt(text)}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        r = requests.post(_OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        return _parse_response(raw)
    except Exception:
        return _unknown("openrouter_unavailable")


def parse_intent(text: str) -> dict:
    """Call LLM to parse a natural language intent. Falls back to unknown if both providers fail."""
    result = _call_ollama(text)
    if result.get("_debug") == "ollama_unavailable":
        result = _call_openrouter(text)
    return result
