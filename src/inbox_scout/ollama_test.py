import json
import requests
from rich.console import Console

console = Console()

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:8b"


def extract_json(text):
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response.")

    return json.loads(text[start:end + 1])


def test_ollama_json():
    payload = {
        "model": MODEL,
        "prompt": """
Return ONLY valid JSON.

Classify this email:

From: Google <no-reply@accounts.google.com>
Subject: Security alert
Snippet: New sign-in detected on your Google Account.

Required JSON keys:
category, confidence_score, risk_score, reason, suggested_action, manual_review
""",
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0
        }
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()

    raw_text = response.json().get("response", "")
    parsed = extract_json(raw_text)

    console.print("[bold green]Ollama JSON test passed.[/bold green]")
    console.print_json(json.dumps(parsed))


if __name__ == "__main__":
    test_ollama_json()
