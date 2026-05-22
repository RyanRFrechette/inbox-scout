"""
Junk Sender Scout — read-only Gmail scan for newsletter/promo sender candidates.

Phase 1: Report only. No Gmail writes, no filter creation, no labels.
Scans All Mail (promotions + updates categories) to surface senders
worth reviewing for future blocking.
"""
from __future__ import annotations

import re
from collections import defaultdict

from inbox_scout.gmail_auth import get_gmail_service
from inbox_scout.trash_execution_runner import PROTECTED_TEXT_TERMS
from inbox_scout.trash_sender_block_plan import extract_email, is_system_sender, is_valid_email

MAX_MESSAGES = 100
SAMPLE_SIZE = 3

_JUNK_SUBJECT_PATTERNS = [
    r"\bunsubscribe\b",
    r"\b\d+\s*%\s*off\b",
    r"\bsale\b",
    r"\bdeal\b",
    r"\bcoupon\b",
    r"\bdiscount\b",
    r"\blimited\s+time\b",
    r"\bshop\s+now\b",
    r"\bpromo(?:tion)?\b",
    r"\bnewsletter\b",
    r"\bdigest\b",
    r"\bweekly\b",
    r"\bmonthly\b",
]
_JUNK_RE = [re.compile(p, re.IGNORECASE) for p in _JUNK_SUBJECT_PATTERNS]

# Sender domain substrings that should never be flagged for blocking
_PROTECTED_SENDER_KEYWORDS = {
    "bank", "credit", "capital", "fidelity", "schwab", "vanguard",
    "paypal", "stripe", "tax", "irs", ".gov", "hospital", "clinic",
    "health", "medical", "insurance", "legal", "attorney", "law",
    "pharmacy", "doctor", "dentist", "visa", "mastercard",
    "amex", "wellsfargo", "chase", "citibank", "usbank",
}


def _get_headers(service, msg_id: str) -> dict[str, str]:
    """Fetch only From and Subject headers for a message."""
    result = service.users().messages().get(
        userId="me",
        id=msg_id,
        format="metadata",
        metadataHeaders=["From", "Subject"],
    ).execute()
    out: dict[str, str] = {}
    for h in result.get("payload", {}).get("headers", []):
        out[h["name"]] = h["value"]
    return out


def _is_protected(addr: str, subjects: list[str]) -> bool:
    """Return True if this sender should never be flagged."""
    domain = addr.split("@")[-1].lower() if "@" in addr else addr.lower()
    for kw in _PROTECTED_SENDER_KEYWORDS:
        if kw in domain:
            return True
    combined = " ".join(subjects).lower()
    for term in PROTECTED_TEXT_TERMS:
        if term in combined:
            return True
    return False


def _count_junk_signals(subjects: list[str]) -> tuple[int, list[str]]:
    combined = " ".join(subjects).lower()
    matched = [p.pattern for p in _JUNK_RE if p.search(combined)]
    return len(matched), matched


def _risk_score(count: int, signal_count: int) -> int:
    """Lower score = more confident it is safe to review for blocking."""
    base = 40
    base -= min(signal_count * 5, 20)
    base -= min((count - 1) // 3, 5) * 2
    return max(5, base)


def scan_junk_senders(account: str = "primary", max_results: int = MAX_MESSAGES) -> list[dict]:
    """
    Read-only Gmail scan. Returns list of candidate dicts.
    No Gmail writes are performed.
    """
    service = get_gmail_service(mode="readonly", account=account)

    response = service.users().messages().list(
        userId="me",
        q="category:promotions OR category:updates",
        maxResults=max_results,
    ).execute()
    messages = response.get("messages", [])

    sender_subjects: dict[str, list[str]] = defaultdict(list)
    for stub in messages:
        try:
            hdrs = _get_headers(service, stub["id"])
        except Exception:
            continue
        raw_from = hdrs.get("From", "")
        subject = hdrs.get("Subject", "(no subject)")
        addr = extract_email(raw_from)
        if not addr or not is_valid_email(addr):
            continue
        sender_subjects[addr].append(subject)

    candidates: list[dict] = []
    for addr, subjects in sender_subjects.items():
        if is_system_sender(addr):
            continue
        if _is_protected(addr, subjects):
            continue
        sig_count, signals = _count_junk_signals(subjects)
        risk = _risk_score(len(subjects), sig_count)
        candidates.append({
            "sender": addr,
            "count": len(subjects),
            "samples": subjects[:SAMPLE_SIZE],
            "reason": (
                f"newsletter/promo signals ({sig_count}): "
                + (", ".join(signals[:3]) if signals else "volume/category")
            ),
            "risk_score": risk,
            "safe_to_review": risk <= 30,
        })

    candidates.sort(key=lambda x: (-x["count"], x["risk_score"]))
    return candidates


def junk_sender_scout_message(account: str = "primary") -> str:
    """Entry point for natural_intent routing. Always read-only."""
    try:
        candidates = scan_junk_senders(account=account)
    except Exception as exc:
        return f"Junk Sender Scout failed: {exc}\n\nNo Gmail changes made."

    if not candidates:
        return (
            "Junk Sender Scout: no newsletter or promo sender candidates found "
            f"({account} account).\n\n"
            "This scans Gmail's promotions and updates categories across all mail. "
            "If your inbox is already well-sorted, this is expected.\n\n"
            "No Gmail changes made."
        )

    reviewable = [c for c in candidates if c["safe_to_review"]]
    lines = [
        f"Junk Sender Scout — {account} account",
        f"Found {len(candidates)} newsletter/promo candidate(s) "
        f"({len(reviewable)} marked safe to review for blocking).",
        "",
    ]

    for i, c in enumerate(candidates[:20], 1):
        marker = "[safe to review]" if c["safe_to_review"] else "[needs review]"
        lines.append(f"{i}. {c['sender']} — {c['count']} email(s) {marker}")
        for s in c["samples"]:
            lines.append(f"   \"{s}\"")
        lines.append(f"   Risk {c['risk_score']} — {c['reason']}")
        lines.append("")

    if len(candidates) > 20:
        lines.append(f"... and {len(candidates) - 20} more.")
        lines.append("")

    lines.append("No Gmail changes made.")
    return "\n".join(lines)
