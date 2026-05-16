"""Read-only audit of the latest scan queue.

Shows exactly why Atlas placed each email into protected / unclear /
trash_candidate.  No data files are modified.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m inbox_scout.queue_audit
"""
from __future__ import annotations

import re
from typing import Any

from inbox_scout.trash_candidate_plan import (
    MARKETING_RESCUE_CATEGORIES,
    MAX_TRASH_RISK,
    PROTECTED_CATEGORIES,
    PROTECTED_DANGER_TERMS,
    TRASH_SAFE_CATEGORIES,
    already_handled,
    clean,
    has_obvious_marketing_signal,
    has_protected_danger_signal,
    is_true,
    load_items,
    risk_int,
    _signal_text,
)
from inbox_scout.trash_execution_runner import find_protected_text_terms

_SECURITY_DANGER = frozenset({
    "login", "password", "security alert", "security",
    "recovery email updated", "verification code", "account access",
})
_RECEIPT_DANGER = frozenset({"receipt", "payment", "invoice", "bill", "statement"})
_SHIPPING_DANGER = frozenset({"shipped", "delivered", "tracking", "order confirmation"})
_JOB_DANGER = frozenset({
    "job application", "job offer", "offer letter", "offer extended",
    "recruiter", "hiring", "candidate", "application status", "application", "interview",
})

_CATEGORY_REASON_CODES: dict[str, str] = {
    "finance": "protected_finance",
    "bills/receipts": "protected_bills_receipts",
    "medical": "protected_medical",
    "legal": "protected_legal",
    "tax": "protected_tax",
    "security": "protected_security_login",
    "security alert": "protected_security_login",
    "client/business": "protected_client_business",
    "insurance": "protected_insurance",
    "manual review": "protected_manual_review_category",
    "job/career": "protected_job_career",
}


def _matched_danger_terms(item: dict[str, Any]) -> list[str]:
    text = _signal_text(item)
    return [t for t in PROTECTED_DANGER_TERMS if re.search(r"\b" + re.escape(t) + r"\b", text)]


def audit_item(item: dict[str, Any]) -> tuple[str, str, str]:
    """Return (bucket, reason_code, human_reason) for one queue item.

    Mirrors is_safe_trash_candidate logic exactly — no behaviour change.
    """
    category = clean(item.get("category")).lower()
    risk = risk_int(item)
    decision = clean(item.get("local_decision")).lower()

    if already_handled(item):
        return "handled", "already_handled", "Gmail action already taken."

    if is_true(item.get("manual_review")):
        code = _CATEGORY_REASON_CODES.get(category, "protected_manual_review")
        return "protected", code, f"manual_review=True ({category})."

    if decision == "protected_review":
        return "protected", "protected_local_decision", "local_decision=protected_review."

    if category in PROTECTED_CATEGORIES:
        code = _CATEGORY_REASON_CODES.get(category, "protected_category")
        return "protected", code, f"Category '{category}' always protected."

    if risk >= 70:
        return "protected", "protected_high_risk", f"Risk {risk} >= 70."

    if risk > MAX_TRASH_RISK:
        return "unclear", "unclear_high_risk", f"Risk {risk} > threshold {MAX_TRASH_RISK}."

    if decision not in {"pending_review", "possible_archive_later", "possible_trash_later"}:
        return "unclear", "unclear_local_decision", f"local_decision '{decision}' not eligible."

    if has_protected_danger_signal(item):
        matched = _matched_danger_terms(item)
        signals = ", ".join(sorted(matched)[:3])
        if any(t in _SECURITY_DANGER for t in matched):
            label = f"Security danger: {signals}."
        elif any(t in _RECEIPT_DANGER for t in matched):
            label = f"Receipt danger: {signals}."
        elif any(t in _SHIPPING_DANGER for t in matched):
            label = f"Shipping danger: {signals}."
        elif any(t in _JOB_DANGER for t in matched):
            label = f"Job danger: {signals}."
        else:
            label = f"Danger signal: {signals}."
        return "unclear", "blocked_by_protected_danger_signal", label

    if category in TRASH_SAFE_CATEGORIES:
        matched = find_protected_text_terms(item)
        if matched:
            terms = ", ".join(matched[:3])
            return "runner_block", "final_runner_blocked_by_protected_text", f"Runner protected text: {terms}."
        return "trash_candidate", "trash_candidate_newsletter_promotion", "Newsletter/Promotion — low risk."

    if category in MARKETING_RESCUE_CATEGORIES:
        if has_obvious_marketing_signal(item):
            matched = find_protected_text_terms(item)
            if matched:
                terms = ", ".join(matched[:3])
                return "runner_block", "final_runner_blocked_by_protected_text", f"Runner protected text: {terms}."
            return "trash_candidate", "trash_candidate_marketing_rescue", "Marketing signal in Personal/Archive candidate."
        return "unclear", "unclear_no_strong_marketing_signal", "Personal/Archive candidate — no marketing signal."

    return "unclear", "unclear_ineligible_category", f"Category '{category}' not eligible."


def build_audit_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        bucket, code, human = audit_item(item)
        rows.append({
            "id": clean(item.get("queue_id") or item.get("id") or "?"),
            "subject": (clean(item.get("subject")) or "(no subject)")[:55],
            "category": clean(item.get("category")),
            "risk": risk_int(item),
            "manual_review": is_true(item.get("manual_review")),
            "local_decision": clean(item.get("local_decision")),
            "bucket": bucket,
            "reason_code": code,
            "human_reason": human,
        })
    return rows


def print_audit_table() -> None:
    from rich.console import Console
    from rich.table import Table

    items = load_items()
    rows = build_audit_rows(items)

    console = Console()
    table = Table(title=f"Queue Audit — {len(rows)} items", show_lines=False)
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Subject", style="white", max_width=38, overflow="fold")
    table.add_column("Category", style="yellow", max_width=16)
    table.add_column("Risk", style="red", width=4)
    table.add_column("MR", width=3)
    table.add_column("Decision", max_width=20)
    table.add_column("Bucket", width=16)
    table.add_column("Reason Code", style="blue", max_width=42)
    table.add_column("Human Reason", style="dim white", max_width=44)

    _bucket_style = {
        "protected": "red",
        "trash_candidate": "green",
        "unclear": "yellow",
        "runner_block": "magenta",
        "handled": "dim",
    }
    for row in rows:
        style = _bucket_style.get(row["bucket"], "white")
        table.add_row(
            row["id"],
            row["subject"],
            row["category"],
            str(row["risk"]),
            "Y" if row["manual_review"] else "N",
            row["local_decision"],
            f"[{style}]{row['bucket']}[/{style}]",
            row["reason_code"],
            row["human_reason"],
        )

    console.print(table)


def print_audit_plain() -> None:
    items = load_items()
    rows = build_audit_rows(items)
    header = f"{'ID':<4}  {'Bucket':<16}  {'Code':<38}  {'Risk':<4}  {'MR':<2}  {'Category':<18}  Subject"
    print(header)
    print("-" * len(header))
    for row in rows:
        subject = row["subject"][:50]
        print(
            f"{row['id']:<4}  {row['bucket']:<16}  {row['reason_code']:<38}"
            f"  {row['risk']:<4}  {'Y' if row['manual_review'] else 'N':<2}"
            f"  {row['category']:<18}  {subject}"
        )


def main() -> None:
    import sys
    if "--plain" in sys.argv:
        print_audit_plain()
    else:
        print_audit_table()


if __name__ == "__main__":
    main()
