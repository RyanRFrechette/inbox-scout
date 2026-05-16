import json
from datetime import datetime

from rich.console import Console
from rich.table import Table

from inbox_scout.rule_classifier import classify_email, load_json, load_lines
from inbox_scout.inbox_fetcher import fetch_inbox_emails
from inbox_scout.paths import HISTORY_DIR, PROTECTED_SENDERS_FILE, PROTECTED_TERMS_FILE, RULES_FILE
from inbox_scout.model_router import classify_with_provider
from inbox_scout.trash_candidate_plan import (
    has_obvious_marketing_signal,
    has_protected_danger_signal,
    _DEMOTABLE_PROTECTED_CATEGORIES,
)

console = Console()

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

# Only these rule-identified categories hard-override AI. All others let AI decide.
_ALWAYS_PROTECTED_RULE_CATEGORIES = frozenset({
    "finance",
    "bills/receipts",
    "legal",
    "medical",
    "security alert",
    "job/career",
    "client/business",
    "warranty/support",
    "personal",
    "important",
    "needs reply",
})


def _demote_marketing_false_positive(email: dict, result: dict) -> dict:
    """Demote Job/career or Client/business to Promotion when strong marketing signal
    exists and no protected danger signal exists. Corrects AI/rule over-classification
    of product newsletters and deal emails."""
    original_category = (result.get("category") or "").lower().strip()
    if original_category not in _DEMOTABLE_PROTECTED_CATEGORIES:
        return result
    signal_item = {
        "from": email.get("from", ""),
        "subject": email.get("subject", ""),
        "snippet": email.get("snippet", ""),
    }
    if has_protected_danger_signal(signal_item):
        return result
    if not has_obvious_marketing_signal(signal_item):
        return result
    result = dict(result)
    result["category"] = "Promotion"
    result["manual_review"] = False
    result["risk_score"] = 15
    result["reason"] = (
        f"Marketing signal detected — demoted from {original_category}. "
        + str(result.get("reason", ""))
    )
    result["suggested_action"] = "Low-risk marketing email. Safe to archive or trash."
    return result


def classify_with_ai(email, rule_result, batch_size: int = 1):
    validated = classify_with_provider(email, rule_result, batch_size=batch_size)

    if rule_result.get("manual_review"):
        rule_category = (rule_result.get("category") or "").lower().strip()
        if rule_category in _ALWAYS_PROTECTED_RULE_CATEGORIES:
            validated["category"] = rule_result.get("category", "Manual review")
            validated["manual_review"] = True
            validated["risk_score"] = max(validated.get("risk_score", 0), rule_result.get("risk_score", 90))
            validated["suggested_action"] = "Review manually before taking action."
            validated["reason"] = "Protected rule category preserved. " + str(validated.get("reason", ""))

    validated = _demote_marketing_false_positive(email, validated)
    return validated


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



