"""Read-only Gmail label/folder explorer for Atlas.

Lists InboxScout label counts and drills into a specific label+time range.
Never modifies Gmail. Always uses readonly token.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

INBOX_SCOUT_PREFIX = "InboxScout/"
DRILLDOWN_LIMIT = 15
_DAY_CAP = 90

# Short alias (lowercase) → full Gmail label name
LABEL_ALIASES: dict[str, str] = {
    "protected review":       "InboxScout/Protected Review",
    "possible archive later": "InboxScout/Possible Archive Later",
    "keep":                   "InboxScout/Keep",
    "review later":           "InboxScout/Review Later",
    "ignore":                 "InboxScout/Ignore",
    "trash candidates":       "InboxScout/Trash-Candidates",
    "trash-candidates":       "InboxScout/Trash-Candidates",
    "shopping history":       "InboxScout/Shopping-History",
    "shopping-history":       "InboxScout/Shopping-History",
    "receipts":               "InboxScout/Receipts",
    "shipping returns":       "InboxScout/Shipping-Returns",
    "shipping-returns":       "InboxScout/Shipping-Returns",
    "security":               "InboxScout/Security",
    "finance":                "InboxScout/Finance",
    "accounts":               "InboxScout/Accounts",
    "jobs":                   "InboxScout/Jobs",
    "work business":          "InboxScout/Work-Business",
    "work-business":          "InboxScout/Work-Business",
    "personal":               "InboxScout/Personal",
    "medical":                "InboxScout/Medical",
    "legal tax":              "InboxScout/Legal-Tax",
    "legal-tax":              "InboxScout/Legal-Tax",
    "subscriptions":          "InboxScout/Subscriptions",
    "newsletters":            "InboxScout/Newsletters",
    "promotions":             "InboxScout/Promotions",
    "social notifications":   "InboxScout/Social-Notifications",
    "social-notifications":   "InboxScout/Social-Notifications",
    "school learning":        "InboxScout/School-Learning",
    "school-learning":        "InboxScout/School-Learning",
    "ai dev tools":           "InboxScout/AI-Dev-Tools",
    "ai-dev-tools":           "InboxScout/AI-Dev-Tools",
    "review":                 "InboxScout/Review",
}

# Sorted longest-first so multi-word aliases match before single-word ones
_SORTED_ALIASES = sorted(LABEL_ALIASES, key=len, reverse=True)

_TIME_RE = re.compile(r"last\s+(\d+)\s+days?")
_SHOW_IN_RE = re.compile(r"\b(show|list)\b.{0,30}\bin\b", re.IGNORECASE)

_SHOPPING_TERMS = frozenset({
    "amazon", "order", "shipment", "shipped", "delivery", "receipt",
    "invoice", "tracking", "package", "purchase", "confirmation",
    "ups", "fedex", "usps", "dhl", "walmart", "target", "ebay",
    "shop", "store",
})

_FINANCE_LIKE = frozenset({"finance"})


def _has_shopping_signal(lines: list[str]) -> bool:
    """True when at least half the visible emails look like shopping/shipping/receipts."""
    if not lines:
        return False
    hits = sum(1 for line in lines if any(term in line.lower() for term in _SHOPPING_TERMS))
    return hits >= max(2, len(lines) // 2)


def _build_intro(short: str, estimate: int, shown: int, lines: list[str]) -> str:
    """One-sentence natural summary inserted before the email list."""
    crowded = estimate > shown
    shopping = _has_shopping_signal(lines)
    is_finance_like = short.lower() in _FINANCE_LIKE

    parts: list[str] = []
    if crowded:
        parts.append(f"{short} is pretty crowded.")
    else:
        suffix = "email" if estimate == 1 else "emails"
        parts.append(f"{short} has {estimate} {suffix}.")

    if shopping and is_finance_like:
        parts.append(
            "A lot of this looks like shopping receipts and shipment/order emails, "
            "not true banking."
        )

    parts.append(f"I'm showing the newest {shown}." if crowded else "I'm showing all of them.")
    return " ".join(parts)


def _get_service(account: str = "primary"):
    from inbox_scout.gmail_auth import get_gmail_service
    return get_gmail_service(mode="readonly", account=account)


def resolve_label(text: str) -> Optional[str]:
    """Return the full InboxScout label name found in text, or None."""
    t = text.lower()
    for alias in _SORTED_ALIASES:
        if alias in t:
            return LABEL_ALIASES[alias]
    return None


def parse_days(text: str) -> int:
    """Return day count from 'last N days', 'this week', 'this month'. 0 = not found. No cap applied."""
    t = text.lower()
    m = _TIME_RE.search(t)
    if m:
        return max(1, int(m.group(1)))
    if "this week" in t or "last week" in t:
        return 7
    if "this month" in t or "last month" in t:
        return 30
    return 0


def parse_drilldown(text: str) -> tuple[Optional[str], int, bool]:
    """
    Parse a drilldown phrase.
    Returns (full_label_name, days, summarize).
    label is None if no recognizable label found.
    days is 0 if no time range found (caller should default).
    """
    label = resolve_label(text)
    days = parse_days(text)
    summarize = bool(re.search(r"\bsummar", text.lower()))
    return label, days, summarize


def is_drilldown_phrase(text: str) -> bool:
    """True if text is a folder drilldown request: time+label, or show/list … in <label>."""
    t = text.lower()
    has_time = bool(_TIME_RE.search(t) or
                    any(w in t for w in ("this week", "last week", "this month", "last month")))
    has_label = resolve_label(text) is not None
    has_show_in = bool(_SHOW_IN_RE.search(text))
    return has_label and (has_time or has_show_in)


def build_folder_counts_message(account: str = "primary") -> str:
    try:
        service = _get_service(account)
    except Exception as e:
        return f"Couldn't connect to Gmail to check folders.\n\n{e}\n\nNothing was changed."

    try:
        results = service.users().labels().list(userId="me").execute()
        all_labels = results.get("labels", [])
    except Exception as e:
        return f"Couldn't list labels.\n\n{e}\n\nNothing was changed."

    inbox_scout = [
        (lbl["name"], lbl["id"])
        for lbl in all_labels
        if lbl["name"].startswith(INBOX_SCOUT_PREFIX)
    ]

    if not inbox_scout:
        return "No InboxScout folders yet — run a sort first to start building them."

    lines: list[str] = []
    for name, label_id in sorted(inbox_scout):
        short = name[len(INBOX_SCOUT_PREFIX):]
        try:
            detail = service.users().labels().get(userId="me", id=label_id).execute()
            total = detail.get("messagesTotal", 0)
            if total > 0:
                suffix = "email" if total == 1 else "emails"
                lines.append(f"• {short}: {total} {suffix}")
        except Exception:
            pass

    if not lines:
        return "All InboxScout folders are empty right now."

    header = f"Your InboxScout folders ({len(lines)} with mail):\n\n"
    footer = "\n\nRead-only. Nothing was changed."
    return header + "\n".join(lines) + footer


def build_drilldown_message(label_name: str, days: int, summarize: bool = False, account: str = "primary") -> str:
    short = label_name[len(INBOX_SCOUT_PREFIX):]
    requested_days = days
    if days > 0:
        days = min(days, _DAY_CAP)
    cap_note = (
        f"\n\n(You asked for {requested_days} days, so I capped this at {_DAY_CAP} days for safety.)"
        if requested_days > _DAY_CAP else ""
    )
    human_range = f" from the last {days} day{'s' if days != 1 else ''}" if days else ""

    date_filter = ""
    if days:
        cutoff = datetime.now() - timedelta(days=days)
        date_filter = f" after:{cutoff.strftime('%Y/%m/%d')}"

    query = f'label:"{label_name}"{date_filter}'

    try:
        service = _get_service(account)
        resp = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=DRILLDOWN_LIMIT,
        ).execute()
    except Exception as e:
        return f"Couldn't query {short}.\n\n{e}\n\nNothing was changed."

    messages = resp.get("messages", [])
    estimate = resp.get("resultSizeEstimate", 0)

    if not messages:
        range_note = f" in the last {days} day{'s' if days != 1 else ''}" if days else ""
        return f"I didn't find anything in {short}{range_note}.{cap_note}\n\nRead-only. Nothing was changed."

    lines: list[str] = []
    for msg in messages:
        try:
            detail = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            hdrs = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            sender = hdrs.get("From", "Unknown")[:50]
            subject = hdrs.get("Subject", "(no subject)")[:60]
            date = hdrs.get("Date", "")[:16]
            lines.append(f"• {date}\n  {sender}\n  {subject}")
        except Exception:
            lines.append("• (could not load this email)")

    shown = len(lines)
    intro = _build_intro(short, estimate, shown, lines)
    if summarize:
        header = f"{short}{human_range} — {estimate} total, showing {shown}:\n\n"
    else:
        header = f"Emails in {short}{human_range} ({estimate} total, showing {shown}):\n\n"

    footer = "\n\nRead-only. Nothing was changed."
    return intro + "\n\n" + header + "\n\n".join(lines) + cap_note + footer
