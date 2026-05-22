"""
Junk Sender Scout — read-only Gmail scan for newsletter/promo block candidates.
Phase 1: Report only. No Gmail writes.
"""
from __future__ import annotations

import re
from collections import defaultdict

from inbox_scout.gmail_auth import get_gmail_service
from inbox_scout.trash_sender_block_plan import extract_email, is_valid_email

SAFE = "safe_to_review_for_blocking"
ARCHIVE_ONLY = "archive_only_do_not_block"
EXCLUDED = "excluded_protected"

EMERGENCY_CAP = 5000   # hard stop; full paginated scan by default
_PAGE_SIZE = 500        # Gmail API max per page
SAMPLE_SIZE = 5
_QUERY = "(category:promotions OR category:updates) -in:trash -in:spam"

# ── positive signals ──────────────────────────────────────────────────────────
_PROMO_TERMS = frozenset({
    "sale", "deals", "deal", "discount", "coupon", "promo", "promotion",
    "save", "savings", "clearance", "limited time", "last chance",
    "ends tonight", "ends soon", "final hours", "exclusive offer",
    "special offer", "shop now", "new arrivals", "trending",
    "recommended for you", "picked for you", "because you viewed",
    "price drop", "rewards", "points", "sweepstakes", "giveaway",
    "free shipping", "flash sale", "unlock", "today only",
    "newsletter", "digest", "weekly update", "daily update", "monthly update",
    "roundup", "from the blog", "tips", "recommendations",
})

_BULK_CONTENT_TERMS = frozenset({
    "unsubscribe", "manage preferences", "email preferences",
    "view in browser", "view this email", "mailing list",
    "you are receiving this", "update your preferences",
})

_BULK_LOCAL_PARTS = frozenset({
    "newsletter", "marketing", "promo", "promos", "deals", "offers",
    "offer", "mailer", "campaign", "campaigns", "news", "notification",
})

_BULK_SUBDOMAINS = frozenset({
    "email", "mail", "news", "em", "send", "promo", "marketing",
    "newsletter", "deals", "offers", "notify", "e",
})

# ── hard exclusions → excluded_protected ─────────────────────────────────────
_SECURITY_TERMS = frozenset({
    "login", "log in", "sign in", "signin", "password", "passcode",
    "2fa", "mfa", "verification code", "security alert", "suspicious activity",
    "account locked", "account recovery", "reset your password",
    "compromised", "breach", "new device", "authentication",
    "verify your", "confirm your identity", "ssh key", "ssh access",
})

_MEDICAL_TERMS = frozenset({
    "doctor", "appointment", "mri", "endocrinology", "neurosurgery",
    "dermatology", "prescription", "patient portal", "lab results",
    "test results", "neurosurgeon", "endocrinologist",
    "mgh", "mass general", "st. joe", "st. joseph",
})

_JOBS_TERMS = frozenset({
    "recruiter", "recruiting", "job offer", "hiring manager",
    "your application", "open position", "job opportunity", "career opportunity",
    "interview invitation", "interview request",
})

_CLOUD_DEV_TERMS = frozenset({
    "ssh ", "droplet", "ssl certificate", "api key", "security vulnerability",
    "server outage", "incident report", "infrastructure alert",
    "deployment failed", "build failed",
})

_FINANCE_TERMS = frozenset({
    "payment", "autopay", "account balance", "credit card statement",
    "loan statement", "mortgage statement", "payroll", "paycheck",
    "direct deposit", "overdraft", "insurance claim", "policy number",
})

_FINANCE_DOMAIN_SUBSTRINGS = frozenset({
    "paypal", "venmo", "chime", "stripe", "plaid", "onepay",
    "cashapp", "cash-app", "wellsfargo", "citibank", "usbank", "amex",
    "fidelity", "schwab", "vanguard",
})

_JOBS_DOMAIN_SUBSTRINGS = frozenset({
    "linkedin", "indeed", "ziprecruiter", "glassdoor", "workday",
    "greenhouse", "lever", "welo", "welocalize", "jobvite",
})

_MEDICAL_DOMAIN_SUBSTRINGS = frozenset({
    "hospital", "clinic", "health", "medical", "pharmacy", "patient",
})

_LEGAL_DOMAIN_SUBSTRINGS = frozenset({
    "court", "legal", "attorney", "lawyer", "dmv",
})

_CLOUD_DEV_BASE_DOMAINS = frozenset({
    "digitalocean.com", "openai.com", "anthropic.com",
    "cloudflare.com", "github.com",
})

_PERSONAL_DOMAINS = frozenset({
    "gmail.com", "yahoo.com", "icloud.com", "hotmail.com",
    "outlook.com", "me.com", "aol.com",
})

# ── archive-only (useful, don't block) ───────────────────────────────────────
_ORDERS_TERMS = frozenset({
    "your order", "order confirmation", "order shipped", "order delivered",
    "shipping confirmation", "tracking number", "return request",
    "your receipt", "purchase confirmation", "google play",
    "has been shipped", "out for delivery",
})

_ARCHIVE_ONLY_DOMAIN_SUBSTRINGS = frozenset({
    "usps", "ups", "fedex", "dhl", "shopify", "informeddelivery",
})

_ARCHIVE_ONLY_BASE_DOMAINS = frozenset({
    "amazon.com", "etsy.com", "walmart.com", "ebay.com", "google.com",
})


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_display_name(raw_from: str) -> str:
    m = re.match(r'^"?([^"<]{2,60}?)"?\s*<', raw_from.strip())
    return m.group(1).strip().strip('"') if m else ""


def _get_headers(service, msg_id: str) -> dict[str, str]:
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


def _domain_matches_base(domain: str, base: str) -> bool:
    return domain == base or domain.endswith("." + base)


def _compute_risk(local: str, domain: str, subjects: list[str]) -> int:
    count = len(subjects)
    combined = " ".join(subjects).lower()
    base = 50
    if count >= 3:
        base -= 10
    if count >= 5:
        base -= 10
    if count >= 10:
        base -= 15
    if count == 1:
        base += 10
    promo_hits = sum(1 for s in subjects if any(t in s.lower() for t in _PROMO_TERMS))
    if promo_hits >= 2:
        base -= 10
    if local in _BULK_LOCAL_PARTS or any(p in local for p in _BULK_LOCAL_PARTS if len(p) >= 5):
        base -= 10
    subdomain = domain.split(".")[0] if domain.count(".") >= 2 else ""
    if subdomain in _BULK_SUBDOMAINS:
        base -= 10
    if any(t in combined for t in _BULK_CONTENT_TERMS):
        base -= 10
    return max(0, min(100, base))


def _classify(addr: str, display_name: str, subjects: list[str]) -> tuple[str, int, str]:
    """Return (recommendation_class, risk_score, reason). Pure logic, no I/O."""
    domain = addr.split("@")[-1].lower() if "@" in addr else addr.lower()
    local = addr.split("@")[0].lower() if "@" in addr else ""
    combined = " ".join(subjects).lower()

    if domain in _PERSONAL_DOMAINS:
        return EXCLUDED, 90, "personal email domain"

    for t in _SECURITY_TERMS:
        if t in combined:
            return EXCLUDED, 90, f"security: {t}"
    for t in _MEDICAL_TERMS:
        if t in combined:
            return EXCLUDED, 90, f"medical: {t}"
    for t in _JOBS_TERMS:
        if t in combined:
            return EXCLUDED, 85, f"jobs: {t}"
    for t in _CLOUD_DEV_TERMS:
        if t in combined:
            return EXCLUDED, 85, f"cloud/dev: {t}"
    for t in _FINANCE_TERMS:
        if t in combined:
            return EXCLUDED, 90, f"finance: {t}"

    for t in _ORDERS_TERMS:
        if t in combined:
            return ARCHIVE_ONLY, 70, f"order/receipt: {t}"

    if "bank" in domain:
        return EXCLUDED, 90, "banking domain"
    if any(k in domain for k in _FINANCE_DOMAIN_SUBSTRINGS):
        return EXCLUDED, 90, "finance domain"
    if any(_domain_matches_base(domain, b) for b in _CLOUD_DEV_BASE_DOMAINS):
        return EXCLUDED, 85, "cloud/dev domain"
    if any(k in domain for k in _JOBS_DOMAIN_SUBSTRINGS):
        return EXCLUDED, 85, "jobs/recruiting domain"
    if any(k in domain for k in _MEDICAL_DOMAIN_SUBSTRINGS):
        return EXCLUDED, 85, "medical domain"
    if any(k in domain for k in _LEGAL_DOMAIN_SUBSTRINGS) or ".gov" in domain:
        return EXCLUDED, 85, "legal/government domain"

    if any(k in domain for k in _ARCHIVE_ONLY_DOMAIN_SUBSTRINGS):
        return ARCHIVE_ONLY, 70, "shipping/USPS domain"
    if any(_domain_matches_base(domain, b) for b in _ARCHIVE_ONLY_BASE_DOMAINS):
        return ARCHIVE_ONLY, 70, "major service domain (archive-only)"

    risk = _compute_risk(local, domain, subjects)
    if risk <= 30:
        return SAFE, risk, "high-confidence newsletter/promo sender"
    return ARCHIVE_ONLY, risk, "insufficient evidence for safe blocking recommendation"


# ── public API ────────────────────────────────────────────────────────────────

def scan_junk_senders(account: str = "primary", emergency_cap: int = EMERGENCY_CAP) -> dict:
    """Full paginated read-only Gmail scan. No Gmail writes."""
    service = get_gmail_service(mode="readonly", account=account)

    msgs: list[dict] = []
    page_token: str | None = None
    cap_hit = False

    while True:
        kwargs: dict = {"userId": "me", "q": _QUERY, "maxResults": _PAGE_SIZE}
        if page_token:
            kwargs["pageToken"] = page_token
        response = service.users().messages().list(**kwargs).execute()
        page = response.get("messages", [])
        if not page:
            break
        msgs.extend(page)
        if len(msgs) >= emergency_cap:
            msgs = msgs[:emergency_cap]
            cap_hit = True
            break
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    sender_data: dict[str, dict] = {}
    for stub in msgs:
        try:
            hdrs = _get_headers(service, stub["id"])
        except Exception:
            continue
        raw_from = hdrs.get("From", "")
        subject = hdrs.get("Subject", "(no subject)")
        addr = extract_email(raw_from)
        if not addr or not is_valid_email(addr):
            continue
        if addr not in sender_data:
            sender_data[addr] = {
                "display_name": _extract_display_name(raw_from),
                "subjects": [],
            }
        sender_data[addr]["subjects"].append(subject)

    candidates: list[dict] = []
    archive_only: list[dict] = []
    excluded: list[dict] = []

    for addr, data in sender_data.items():
        subjects = data["subjects"]
        rec, risk, reason = _classify(addr, data["display_name"], subjects)
        profile = {
            "sender": addr,
            "display_name": data["display_name"],
            "count": len(subjects),
            "samples": subjects[:SAMPLE_SIZE],
            "recommendation_class": rec,
            "risk_score": risk,
            "reason": reason,
            "safe_to_review": rec == SAFE,
        }
        if rec == SAFE:
            candidates.append(profile)
        elif rec == ARCHIVE_ONLY:
            archive_only.append(profile)
        else:
            excluded.append(profile)

    candidates.sort(key=lambda x: (x["risk_score"], -x["count"]))
    archive_only.sort(key=lambda x: -x["count"])

    return {
        "messages_scanned": len(msgs),
        "profiles_total": len(sender_data),
        "candidates": candidates,
        "archive_only": archive_only,
        "excluded": excluded,
        "cap_hit": cap_hit,
    }


def _format_account_result(result: dict, account: str) -> str:
    """Format one account's scan result. No Gmail-changes footer — caller adds it."""
    candidates = result["candidates"]
    archive_only = result["archive_only"]
    excluded = result["excluded"]

    lines = [
        f"Scope: All Mail (promotions + updates), archived-capable",
        f"Scanned: {result['messages_scanned']} messages, "
        f"{result['profiles_total']} sender profile(s)",
    ]

    if result.get("cap_hit"):
        lines.append(
            f"** Emergency cap hit at {EMERGENCY_CAP} messages "
            "— results are partial, not a full scan. **"
        )

    lines.append("")

    if not candidates:
        lines += [
            "No block-review candidates found.",
            "All senders were protected, archive-only, or low-evidence.",
        ]
    else:
        lines.append(f"Block-review candidates ({len(candidates)}):")
        lines.append("")
        for i, c in enumerate(candidates[:10], 1):
            dn = f" ({c['display_name']})" if c["display_name"] else ""
            lines.append(
                f"{i}. {c['sender']}{dn} — {c['count']} email(s) [risk {c['risk_score']}]"
            )
            for s in c["samples"]:
                lines.append(f'   "{s}"')
            lines.append(f"   {c['reason']}")
            lines.append("")
        if len(candidates) > 10:
            lines.append(f"... and {len(candidates) - 10} more candidates.")
            lines.append("")

    if archive_only:
        lines.append(f"Archive-only examples ({len(archive_only)} total — useful, don't block):")
        for c in archive_only[:10]:
            dn = f" ({c['display_name']})" if c["display_name"] else ""
            lines.append(f"  - {c['sender']}{dn} ({c['count']} emails) — {c['reason']}")
        if len(archive_only) > 10:
            lines.append(f"  ... and {len(archive_only) - 10} more.")
        lines.append("")

    parts = []
    if excluded:
        parts.append(f"{len(excluded)} excluded (protected/sensitive)")
    if parts:
        lines.append("Filtered out: " + ", ".join(parts))

    return "\n".join(lines)


def junk_sender_scout_message(account: str = "primary") -> str:
    """Single-account entry point. Always read-only."""
    try:
        result = scan_junk_senders(account=account)
    except Exception as exc:
        return f"Junk Sender Scout failed: {exc}\n\nNo Gmail changes made."

    header = f"Junk Sender Scout — {account} account\n"
    return header + _format_account_result(result, account) + "\n\nNo Gmail changes made."


def junk_sender_scout_both_message() -> str:
    """Scan primary + secondary and combine output. Always read-only."""
    sections = ["Junk Sender Scout — both accounts", ""]

    for acct in ("primary", "secondary"):
        sections.append(f"{'=' * 4} {acct.upper()} {'=' * 4}")
        try:
            result = scan_junk_senders(account=acct)
            sections.append(_format_account_result(result, acct))
        except Exception as exc:
            sections.append(f"Error scanning {acct}: {exc}")
        sections.append("")

    sections.append("No Gmail changes made.")
    return "\n".join(sections)
