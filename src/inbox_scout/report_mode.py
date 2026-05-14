import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from inbox_scout.ai_classifier import classify_with_ai
from inbox_scout.gmail_auth import get_gmail_service
from inbox_scout.inbox_fetcher import get_header
from inbox_scout.rule_classifier import classify_email, load_json, load_lines
from inbox_scout.paths import REPORTS_DIR, PROTECTED_SENDERS_FILE, PROTECTED_TERMS_FILE, RULES_FILE

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_GMAIL_SCAN_CURSOR = PLANS_DIR / "latest_gmail_scan_cursor.json"


def build_gmail_query(unread_only=False, days=None):
    query_parts = []

    if unread_only:
        query_parts.append("is:unread")

    if days:
        query_parts.append(f"newer_than:{days}d")

    return " ".join(query_parts)


def fetch_report_emails(limit=25, unread_only=False, days=None, page_size=25, initial_page_token=None):
    service = get_gmail_service()
    query = build_gmail_query(unread_only=unread_only, days=days)

    max_messages = max(0, int(limit))
    page_size = max(1, min(int(page_size), 500))

    emails = []
    page_token = initial_page_token
    next_page_token = None
    page_count = 0

    while len(emails) < max_messages:
        remaining = max_messages - len(emails)
        this_page_size = min(page_size, remaining)

        request = {
            "userId": "me",
            "labelIds": ["INBOX"],
            "maxResults": this_page_size
        }

        if query:
            request["q"] = query

        if page_token:
            request["pageToken"] = page_token

        results = service.users().messages().list(**request).execute()
        messages = results.get("messages", [])

        page_count += 1
        console.print(f"[dim]Fetched Gmail page {page_count}: {len(messages)} message IDs[/dim]")

        for msg in messages:
            message_id = msg["id"]

            message = service.users().messages().get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()

            headers = message.get("payload", {}).get("headers", [])

            emails.append({
                "message_id": message_id,
                "from": get_header(headers, "From"),
                "subject": get_header(headers, "Subject"),
                "date": get_header(headers, "Date"),
                "snippet": message.get("snippet", "")
            })

            if len(emails) >= max_messages:
                break

        next_page_token = results.get("nextPageToken")
        page_token = next_page_token

        if not page_token:
            break

        if not messages:
            break

    console.print(f"[dim]Total report emails fetched: {len(emails)} across {page_count} page(s)[/dim]")
    return emails, next_page_token


def save_scan_cursor(next_page_token, unread_only, batch_limit):
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    cursor = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "next_page_token": next_page_token,
        "unread_only": unread_only,
        "batch_limit": batch_limit,
        "source": "report_mode",
    }
    LATEST_GMAIL_SCAN_CURSOR.write_text(json.dumps(cursor, indent=2), encoding="utf-8")


def classify_for_report(emails):
    rules = load_json(RULES_FILE)
    protected_terms = load_lines(PROTECTED_TERMS_FILE)
    protected_senders = load_lines(PROTECTED_SENDERS_FILE)

    results = []
    total = len(emails)

    for index, email in enumerate(emails, start=1):
        subject = str(email.get("subject") or "(no subject)")[:80]
        console.print(f"[dim]Classifying {index}/{total}: {subject}[/dim]")

        rule_result = classify_email(email, rules, protected_terms, protected_senders)

        try:
            ai_result = classify_with_ai(email, rule_result)
        except Exception as e:
            console.print(f"[yellow]AI classifier failed on {index}/{total}; using rule fallback. Error: {e}[/yellow]")

            ai_result = {
                "category": rule_result.get("category", "Manual review"),
                "confidence_score": rule_result.get("confidence_score", 50),
                "risk_score": rule_result.get("risk_score", 80),
                "manual_review": rule_result.get("manual_review", True),
                "suggested_action": rule_result.get("suggested_action", "Manual review."),
                "reason": "AI classifier timeout/error. Used rule-based fallback."
            }

        results.append({
            **email,
            "rule_classification": rule_result,
            "ai_classification": ai_result
        })

    console.print(f"[dim]Finished classifying {len(results)} email(s)[/dim]")
    return results


def filter_by_category(results, category):
    if not category:
        return results

    wanted = category.lower()

    return [
        item for item in results
        if item["ai_classification"]["category"].lower() == wanted
    ]


def group_results(results):
    grouped = {}

    for item in results:
        category = item["ai_classification"]["category"]
        grouped.setdefault(category, [])
        grouped[category].append(item)

    return grouped


def make_markdown_report(results, args):
    grouped = group_results(results)

    def clean(value):
        text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
        return text if text else "None"

    def cell(value):
        return clean(value).replace("|", "\\|")

    def trim(value, max_len=240):
        text = clean(value)
        if len(text) <= max_len:
            return text
        return text[:max_len].rstrip() + "..."

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    manual_count = sum(1 for item in results if item["ai_classification"].get("manual_review"))
    low_risk_count = len(results) - manual_count

    lines = []
    lines.append("# Inbox Scout Report")
    lines.append("")
    lines.append(f"**Generated:** {generated}")
    lines.append("")
    lines.append("> Safety locked: Inbox Scout is running in read-only mode. No Gmail changes were made.")
    lines.append("")
    lines.append("## Table of Contents")
    lines.append("")
    lines.append("- [Run Settings](#run-settings)")
    lines.append("- [Safety Status](#safety-status)")
    lines.append("- [Summary](#summary)")
    lines.append("- [Action Buckets](#action-buckets)")
    lines.append("- [Email Categories](#email-categories)")
    lines.append("")
    lines.append("## Run Settings")
    lines.append("")
    lines.append("| Setting | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Limit | {args.limit} |")
    lines.append(f"| Page size | {getattr(args, "page_size", "N/A")} |")
    lines.append(f"| Unread only | {args.unread_only} |")
    lines.append(f"| Days | {args.days if args.days else 'All'} |")
    lines.append(f"| Category filter | {args.category if args.category else 'None'} |")
    lines.append("")
    lines.append("## Safety Status")
    lines.append("")
    lines.append("| Capability | Status |")
    lines.append("|---|---|")
    lines.append("| Gmail mode | Read-only |")
    lines.append("| Archive emails | Disabled |")
    lines.append("| Delete emails | Disabled |")
    lines.append("| Apply labels | Disabled |")
    lines.append("| Send replies | Disabled |")
    lines.append("| Modify Gmail | Disabled |")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---:|")
    lines.append(f"| Total emails scanned | {len(results)} |")
    lines.append(f"| Manual review required | {manual_count} |")
    lines.append(f"| Low-risk / possible archive later | {low_risk_count} |")
    lines.append(f"| Categories found | {len(grouped)} |")
    lines.append("")
    lines.append("## Action Buckets")
    lines.append("")
    lines.append("| Bucket | Count | Meaning |")
    lines.append("|---|---:|---|")
    lines.append(f"| Manual review | {manual_count} | Protected, sensitive, unclear, or higher-risk emails. Do not auto-touch. |")
    lines.append(f"| Possible archive later | {low_risk_count} | Lower-risk emails that may be safe to archive after approval in a future phase. |")
    lines.append("")
    lines.append("## Email Categories")
    lines.append("")

    if not results:
        lines.append("No emails matched this report run.")
        lines.append("")
        return "\n".join(lines)

    for category in sorted(grouped):
        items = grouped[category]
        lines.append(f"### {category} ({len(items)})")
        lines.append("")

        for item in items:
            ai = item["ai_classification"]
            review_label = "MANUAL REVIEW" if ai.get("manual_review") else "LOW RISK"
            subject = clean(item.get("subject", "(No subject)"))

            lines.append(f"#### {review_label}: {subject}")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("|---|---|")
            lines.append(f"| From | {cell(item.get('from'))} |")
            lines.append(f"| Date | {cell(item.get('date'))} |")
            lines.append(f"| Confidence | {cell(ai.get('confidence_score'))} |")
            lines.append(f"| Risk | {cell(ai.get('risk_score'))} |")
            lines.append(f"| Manual review | {cell(ai.get('manual_review'))} |")
            lines.append(f"| Suggested action | {cell(ai.get('suggested_action'))} |")
            lines.append(f"| Reason | {cell(ai.get('reason'))} |")
            lines.append(f"| Snippet | {cell(trim(item.get('snippet')))} |")
            lines.append("")

    return "\n".join(lines)


def save_report(results, args):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"inbox_report_{timestamp}"

    json_path = REPORTS_DIR / f"{base_name}.json"
    md_path = REPORTS_DIR / f"{base_name}.md"

    if args.export in ["json", "both"]:
        json_path.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    if args.export in ["md", "both"]:
        md_report = make_markdown_report(results, args)
        md_path.write_text(md_report, encoding="utf-8")

    return json_path, md_path


def print_report_summary(results):
    grouped = group_results(results)

    table = Table(title="Inbox Scout Report Summary")
    table.add_column("Category", style="green")
    table.add_column("Count", style="cyan")

    for category in sorted(grouped):
        table.add_row(category, str(len(grouped[category])))

    console.print(table)

    manual_count = sum(1 for item in results if item["ai_classification"]["manual_review"])
    low_risk_count = len(results) - manual_count

    console.print(f"[bold yellow]Manual review required:[/bold yellow] {manual_count}")
    console.print(f"[bold cyan]Low-risk / possible archive later:[/bold cyan] {low_risk_count}")


def parse_args():
    parser = argparse.ArgumentParser(description="Inbox Scout Report Mode")

    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--unread-only", action="store_true")
    parser.add_argument("--days", type=int)
    parser.add_argument("--category", type=str)
    parser.add_argument("--export", choices=["md", "json", "both"], default="both")
    parser.add_argument("--page-token", type=str, default=None)

    return parser.parse_args()


def main():
    args = parse_args()

    console.print("\n[bold cyan]Inbox Scout Phase 5: Report Mode[/bold cyan]\n")
    console.print("[yellow]Read-only mode. No Gmail changes will be made.[/yellow]\n")

    emails, next_page_token = fetch_report_emails(
        limit=args.limit,
        unread_only=args.unread_only,
        days=args.days,
        page_size=args.page_size,
        initial_page_token=args.page_token,
    )

    results = classify_for_report(emails)
    results = filter_by_category(results, args.category)

    print_report_summary(results)

    json_path, md_path = save_report(results, args)

    save_scan_cursor(next_page_token, args.unread_only, args.limit)

    console.print(f"\n[bold green]Report created safely.[/bold green]")
    console.print(f"JSON report: \n{json_path}")
    console.print(f"Markdown report: \n{md_path}")

    if next_page_token:
        console.print("[dim]Gmail cursor saved. Say 'continue sorting' to scan the next batch.[/dim]")
    else:
        console.print("[dim]No further Gmail pages available. Inbox may be fully scanned.[/dim]")

    console.print("\n[yellow]No Gmail changes were made.[/yellow]\n")


if __name__ == "__main__":
    main()
