import json
from datetime import datetime

import requests
from rich.console import Console
from rich.table import Table

from inbox_scout.rule_classifier import classify_email, load_json, load_lines
from inbox_scout.inbox_fetcher import fetch_inbox_emails
from inbox_scout.paths import HISTORY_DIR, PROTECTED_SENDERS_FILE, PROTECTED_TERMS_FILE, RULES_FILE

console = Console()

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:8b"

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
    "Manual review"
]

REQUIRED_KEYS = [
    "category",
    "confidence_score",
    "risk_score",
    "reason",
    "suggested_action",
    "manual_review"
]


def extract_json(text):
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response.")

    return json.loads(text[start:end + 1])


def normalize_score(value, default=50):
    try:
        number = float(value)

        if 0 <= number <= 1:
            number = number * 100

        number = int(round(number))

        if number < 0:
            return 0

        if number > 100:
            return 100

        return number
    except Exception:
        return default


def validate_ai_result(result):
    for key in REQUIRED_KEYS:
        if key not in result:
            raise ValueError(f"Missing required key: {key}")

    category = result.get("category")

    if category not in ALLOWED_CATEGORIES:
        result["category"] = "Manual review"
        result["reason"] = f"AI returned unsupported category '{category}'. " + str(result.get("reason", ""))
        result["manual_review"] = True
        result["risk_score"] = 90

    result["confidence_score"] = normalize_score(result.get("confidence_score"), default=50)
    result["risk_score"] = normalize_score(result.get("risk_score"), default=60)
    result["manual_review"] = bool(result.get("manual_review"))

    return result


def classify_with_ai(email, rule_result):
    prompt = f"""
You are Inbox Scout, a local-first Gmail cleanup assistant.

Return ONLY valid JSON.
Do not include markdown.
Do not explain outside JSON.

Allowed categories:
{ALLOWED_CATEGORIES}

Required JSON keys:
category, confidence_score, risk_score, reason, suggested_action, manual_review

Scoring:
confidence_score must be 0-100.
risk_score must be 0-100.
manual_review must be true or false.

Safety rules:
- Anything financial, legal, medical, tax, password, security, job, interview, client, invoice, family, warranty, refund, return, collection, or account access related must be manual_review true.
- Never suggest delete.
- Never suggest auto-send.
- Never suggest automatic Gmail changes.
- If unsure, use Manual review.

Rule-based baseline:
{json.dumps(rule_result, ensure_ascii=False)}

Email:
From: {email.get("from", "")}
Subject: {email.get("subject", "")}
Snippet: {email.get("snippet", "")}
"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=180)
        response.raise_for_status()

        raw_text = response.json().get("response", "")
        parsed = extract_json(raw_text)
        validated = validate_ai_result(parsed)

        if rule_result.get("manual_review"):
            validated["category"] = rule_result.get("category", "Manual review")
            validated["manual_review"] = True
            validated["risk_score"] = max(validated["risk_score"], rule_result.get("risk_score", 90))
            validated["suggested_action"] = "Review manually before taking action."
            validated["reason"] = "Protected rule category preserved. " + str(validated.get("reason", ""))

        return validated

    except Exception as error:
        return {
            "category": "Manual review",
            "confidence_score": 0,
            "risk_score": 100,
            "reason": f"AI classification failed: {error}",
            "suggested_action": "Review manually.",
            "manual_review": True
        }


def run_ai_classifier(limit=25):
    rules = load_json(RULES_FILE)
    protected_terms = load_lines(PROTECTED_TERMS_FILE)
    protected_senders = load_lines(PROTECTED_SENDERS_FILE)

    emails = fetch_inbox_emails(limit=limit)

    results = []

    for email in emails:
        rule_result = classify_email(email, rules, protected_terms, protected_senders)
        ai_result = classify_with_ai(email, rule_result)

        results.append({
            **email,
            "rule_classification": rule_result,
            "ai_classification": ai_result
        })

    return results


def print_ai_summary(results):
    table = Table(title="Inbox Scout AI Classification")
    table.add_column("#", style="cyan", width=4)
    table.add_column("AI Category", style="green")
    table.add_column("Confidence", style="cyan", width=10)
    table.add_column("Risk", style="yellow", width=6)
    table.add_column("Manual?", style="red", width=8)
    table.add_column("Subject", style="white", overflow="fold")

    for index, item in enumerate(results, start=1):
        ai = item["ai_classification"]

        table.add_row(
            str(index),
            ai["category"],
            str(ai["confidence_score"]),
            str(ai["risk_score"]),
            "YES" if ai["manual_review"] else "NO",
            item.get("subject", "")[:90]
        )

    console.print(table)



def print_ai_grouped_summary(results):
    counts = {}
    manual_count = 0
    safe_count = 0

    for item in results:
        ai = item["ai_classification"]
        category = ai["category"]

        counts[category] = counts.get(category, 0) + 1

        if ai["manual_review"]:
            manual_count += 1
        else:
            safe_count += 1

    table = Table(title="AI Grouped Summary")
    table.add_column("Category", style="green")
    table.add_column("Count", style="cyan")

    for category in sorted(counts):
        table.add_row(category, str(counts[category]))

    console.print(table)
    console.print(f"[bold yellow]Manual review required:[/bold yellow] {manual_count}")
    console.print(f"[bold cyan]Low-risk / possible archive later:[/bold cyan] {safe_count}")

def save_ai_history(results):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    history_path = HISTORY_DIR / f"ai_classification_history_{timestamp}.json"

    history_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return history_path


def main():
    console.print("\n[bold cyan]Inbox Scout Phase 4: Ollama AI Classifier[/bold cyan]\n")
    console.print("[yellow]Read-only mode. No Gmail changes will be made.[/yellow]")
    console.print("[yellow]Testing 25 emails with local Ollama AI.[/yellow]\n")

    results = run_ai_classifier(limit=25)

    print_ai_summary(results)
    print_ai_grouped_summary(results)

    history_path = save_ai_history(results)

    console.print(f"\n[bold green]AI-classified {len(results)} emails safely.[/bold green]")
    console.print(f"History saved: {history_path}")
    console.print("\n[yellow]No Gmail changes were made.[/yellow]\n")


if __name__ == "__main__":
    main()



