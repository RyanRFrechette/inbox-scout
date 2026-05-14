import json
from datetime import datetime

from rich.console import Console
from rich.table import Table

from inbox_scout.inbox_fetcher import fetch_inbox_emails
from inbox_scout.paths import CONFIG_DIR, HISTORY_DIR, PROTECTED_SENDERS_FILE, PROTECTED_TERMS_FILE, RULES_FILE

console = Console()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_lines(path):
    if not path.exists():
        return []

    lines = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        clean = line.strip()
        if clean and not clean.startswith("#"):
            lines.append(clean.lower())

    return lines


def text_contains_any(text, terms):
    text_lower = text.lower()
    return [term for term in terms if term in text_lower]


def sender_is_protected(sender, protected_senders):
    sender_lower = sender.lower()

    for protected in protected_senders:
        if protected.startswith("@") and protected in sender_lower:
            return True
        if protected in sender_lower:
            return True

    return False


def classify_email(email, rules, protected_terms, protected_senders):
    sender = email.get("from", "")
    subject = email.get("subject", "")
    snippet = email.get("snippet", "")

    combined_text = f"{sender} {subject} {snippet}".lower()

    matched_protected_terms = text_contains_any(combined_text, protected_terms)
    protected_sender = sender_is_protected(sender, protected_senders)

    matched_categories = []

    for category, keywords in rules.get("categories", {}).items():
        matched_keywords = text_contains_any(combined_text, [k.lower() for k in keywords])

        if matched_keywords:
            matched_categories.append({
                "category": category,
                "matched_keywords": matched_keywords
            })

    if protected_sender:
        return {
            "category": "Manual review",
            "confidence_score": 95,
            "risk_score": 95,
            "reason": "Sender is protected.",
            "suggested_action": "Review manually.",
            "manual_review": True,
            "matched_categories": matched_categories,
            "matched_protected_terms": matched_protected_terms
        }

    if matched_protected_terms:
        category = matched_categories[0]["category"] if matched_categories else "Manual review"

        return {
            "category": category,
            "confidence_score": 85,
            "risk_score": 90,
            "reason": "Protected term found.",
            "suggested_action": "Review manually before taking action.",
            "manual_review": True,
            "matched_categories": matched_categories,
            "matched_protected_terms": matched_protected_terms
        }

    if matched_categories:
        category = matched_categories[0]["category"]

        protected_categories = rules.get("protected_categories", [])
        is_protected_category = category in protected_categories

        return {
            "category": category,
            "confidence_score": 75,
            "risk_score": 70 if is_protected_category else 30,
            "reason": "Matched rule-based category keywords.",
            "suggested_action": "Review manually." if is_protected_category else "Possible archive later.",
            "manual_review": is_protected_category,
            "matched_categories": matched_categories,
            "matched_protected_terms": matched_protected_terms
        }

    return {
        "category": rules.get("default_category", "Manual review"),
        "confidence_score": 50,
        "risk_score": 60,
        "reason": "No rule matched.",
        "suggested_action": "Review manually.",
        "manual_review": True,
        "matched_categories": [],
        "matched_protected_terms": []
    }


def classify_inbox(limit=25):
    rules = load_json(RULES_FILE)
    protected_terms = load_lines(PROTECTED_TERMS_FILE)
    protected_senders = load_lines(PROTECTED_SENDERS_FILE)

    emails = fetch_inbox_emails(limit=limit)

    classified = []

    for email in emails:
        classification = classify_email(email, rules, protected_terms, protected_senders)
        classified.append({
            **email,
            "classification": classification
        })

    return classified


def save_history(classified):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    history_path = HISTORY_DIR / f"classification_history_{timestamp}.json"

    history_path.write_text(
        json.dumps(classified, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return history_path


def print_classification_summary(classified):
    table = Table(title="Inbox Scout Rule-Based Classification")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Category", style="green")
    table.add_column("Risk", style="yellow", width=6)
    table.add_column("Manual?", style="red", width=8)
    table.add_column("Subject", style="white", overflow="fold")

    for index, item in enumerate(classified, start=1):
        c = item["classification"]

        table.add_row(
            str(index),
            c["category"],
            str(c["risk_score"]),
            "YES" if c["manual_review"] else "NO",
            item.get("subject", "")[:90]
        )

    console.print(table)



def print_grouped_summary(classified):
    counts = {}
    manual_count = 0
    archive_candidate_count = 0

    for item in classified:
        classification = item["classification"]
        category = classification["category"]

        counts[category] = counts.get(category, 0) + 1

        if classification["manual_review"]:
            manual_count += 1

        if classification["suggested_action"].lower().startswith("possible archive"):
            archive_candidate_count += 1

    table = Table(title="Grouped Summary")
    table.add_column("Category", style="green")
    table.add_column("Count", style="cyan")

    for category in sorted(counts):
        table.add_row(category, str(counts[category]))

    console.print(table)

    console.print(f"[bold yellow]Manual review required:[/bold yellow] {manual_count}")
    console.print(f"[bold cyan]Possible archive candidates later:[/bold cyan] {archive_candidate_count}")

def main():
    console.print("\n[bold cyan]Inbox Scout Phase 3: Rule-Based Classifier[/bold cyan]\n")
    console.print("[yellow]Read-only mode. No Gmail changes will be made.[/yellow]\n")

    classified = classify_inbox(limit=25)

    print_classification_summary(classified)
    print_grouped_summary(classified)

    history_path = save_history(classified)

    console.print(f"\n[bold green]Classified {len(classified)} emails safely.[/bold green]")
    console.print(f"History saved: {history_path}")
    console.print("\n[yellow]No Gmail changes were made.[/yellow]\n")


if __name__ == "__main__":
    main()

