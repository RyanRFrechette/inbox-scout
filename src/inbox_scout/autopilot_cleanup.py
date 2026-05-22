from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from inbox_scout.sort_scan_queue_plan import build_scan_queue_plan, save_plan
from inbox_scout.inbox_cleanup_plan import build_inbox_cleanup_plan
from inbox_scout.inbox_cleanup_runner import build_inbox_cleanup_runner_message


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_SCAN_QUEUE_RUN = PLANS_DIR / "latest_scan_queue_run.json"

AUTOPILOT_MAX_LIMIT = 25
AUTOPILOT_DEFAULT_LIMIT = 25

# Full inbox-zero autopilot constants
AUTOPILOT_EMERGENCY_CAP = 5000  # Runaway protection only — not a product limit
QUEUE_PATH = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"

_DIGEST_IMPORTANT_CATEGORIES: frozenset = frozenset({
    "InboxScout/Jobs",
    "InboxScout/Finance",
    "InboxScout/Security",
    "InboxScout/Medical",
    "InboxScout/Legal-Tax",
    "InboxScout/Personal",
})

_DIGEST_NOISE_CATEGORIES: frozenset = frozenset({
    "InboxScout/Newsletters",
    "InboxScout/Promotions",
    "InboxScout/Shopping-History",
})

# Rule-classified categories that represent routine transactional mail.
# No action required unless a problem signal is present.
_DIGEST_ROUTINE_CATEGORIES: frozenset[str] = frozenset({
    "bills/receipts",
})

# Sender substrings that identify known order/shipping automation.
_DIGEST_SHOPPING_SENDER_TOKENS: frozenset[str] = frozenset({
    "amazon",
    "auto-confirm@",
    "ship-confirm@",
})

# Problem signals that override routine suppression and keep the item in digest.
_DIGEST_PROBLEM_SIGNALS: frozenset[str] = frozenset({
    "refund",
    "failed",
    "declined",
    "payment issue",
    "cancelled",
    "cancellation",
    "delayed",
    "problem",
    "dispute",
    "chargeback",
    "returned",
    "return required",
    "action required",
    "suspicious",
    "fraud",
})


def _is_routine_shopping(item: dict) -> bool:
    """True when item is a routine order/receipt/shipping confirmation with no problem signal."""
    cat = (item.get("category") or "").strip().lower()
    sender = (item.get("from") or item.get("sender") or "").lower()
    subject = (item.get("subject") or "").lower()
    snippet = (item.get("snippet") or "").lower()
    combined = f"{sender} {subject} {snippet}"

    if any(sig in combined for sig in _DIGEST_PROBLEM_SIGNALS):
        return False

    if cat in _DIGEST_ROUTINE_CATEGORIES:
        return True

    if any(tok in sender for tok in _DIGEST_SHOPPING_SENDER_TOKENS):
        return True

    return False


def _is_digest_worthy(item: dict) -> bool:
    if _is_routine_shopping(item):
        return False
    if item.get("manual_review") or item.get("local_decision") == "protected_review":
        return True
    cat = (item.get("category") or "").strip()
    return cat in _DIGEST_IMPORTANT_CATEGORIES


CATEGORY_TO_LABEL: dict[str, str] = {
    # Receipts — order/payment confirmations, invoices, bills paid
    "receipt": "InboxScout/Receipts",
    "receipts": "InboxScout/Receipts",
    "invoice": "InboxScout/Receipts",
    "invoices": "InboxScout/Receipts",
    "order confirmation": "InboxScout/Receipts",
    "purchase confirmation": "InboxScout/Receipts",
    "payment confirmation": "InboxScout/Receipts",
    "payment receipt": "InboxScout/Receipts",
    "transaction confirmation": "InboxScout/Receipts",
    "donation receipt": "InboxScout/Receipts",
    "billing receipt": "InboxScout/Receipts",
    "bill paid": "InboxScout/Receipts",
    "payment": "InboxScout/Receipts",
    "bill": "InboxScout/Receipts",
    "bills": "InboxScout/Receipts",
    # Shopping-History — delivered orders, past purchases
    "shopping": "InboxScout/Shopping-History",
    "shopping history": "InboxScout/Shopping-History",
    "order": "InboxScout/Shopping-History",
    "order delivered": "InboxScout/Shopping-History",
    "order history": "InboxScout/Shopping-History",
    "delivered": "InboxScout/Shopping-History",
    "package delivered": "InboxScout/Shopping-History",
    "delivery confirmation": "InboxScout/Shopping-History",
    "past purchase": "InboxScout/Shopping-History",
    # Shipping-Returns — active tracking, returns, refunds
    "shipment": "InboxScout/Shipping-Returns",
    "shipping": "InboxScout/Shipping-Returns",
    "tracking": "InboxScout/Shipping-Returns",
    "return": "InboxScout/Shipping-Returns",
    "returns": "InboxScout/Shipping-Returns",
    "refund": "InboxScout/Shipping-Returns",
    "refund pending": "InboxScout/Shipping-Returns",
    "delivery exception": "InboxScout/Shipping-Returns",
    "shipment delayed": "InboxScout/Shipping-Returns",
    "return label": "InboxScout/Shipping-Returns",
    "label created": "InboxScout/Shipping-Returns",
    "dropoff": "InboxScout/Shipping-Returns",
    # Security — login alerts, 2FA, resets
    "security": "InboxScout/Security",
    "security alert": "InboxScout/Security",
    "password": "InboxScout/Security",
    "password reset": "InboxScout/Security",
    "login alert": "InboxScout/Security",
    "sign in alert": "InboxScout/Security",
    "verification": "InboxScout/Security",
    "two factor": "InboxScout/Security",
    "2fa": "InboxScout/Security",
    "mfa": "InboxScout/Security",
    "suspicious sign in": "InboxScout/Security",
    "account recovery": "InboxScout/Security",
    # Finance — banks, credit cards, statements, loans, investment
    "finance": "InboxScout/Finance",
    "financial": "InboxScout/Finance",
    "tax": "InboxScout/Finance",
    "taxes": "InboxScout/Finance",
    "insurance": "InboxScout/Finance",
    "bank": "InboxScout/Finance",
    "banking": "InboxScout/Finance",
    "credit card": "InboxScout/Finance",
    "statement": "InboxScout/Finance",
    "loan": "InboxScout/Finance",
    "investment": "InboxScout/Finance",
    "paypal": "InboxScout/Finance",
    "venmo": "InboxScout/Finance",
    "cash app": "InboxScout/Finance",
    # Accounts — profile/terms/privacy updates, non-security account notices
    "account": "InboxScout/Accounts",
    "accounts": "InboxScout/Accounts",
    "account access": "InboxScout/Accounts",
    "account update": "InboxScout/Accounts",
    "profile update": "InboxScout/Accounts",
    "terms update": "InboxScout/Accounts",
    "privacy update": "InboxScout/Accounts",
    "username": "InboxScout/Accounts",
    # Jobs — applications, recruiters, career
    "job": "InboxScout/Jobs",
    "jobs": "InboxScout/Jobs",
    "career": "InboxScout/Jobs",
    "interview": "InboxScout/Jobs",
    "recruiter": "InboxScout/Jobs",
    "hiring": "InboxScout/Jobs",
    "job alert": "InboxScout/Jobs",
    "linkedin job": "InboxScout/Jobs",
    "application": "InboxScout/Jobs",
    # Work-Business — client/business communications
    "work": "InboxScout/Work-Business",
    "business": "InboxScout/Work-Business",
    "work business": "InboxScout/Work-Business",
    "client": "InboxScout/Work-Business",
    "professional": "InboxScout/Work-Business",
    "partnership": "InboxScout/Work-Business",
    "vendor": "InboxScout/Work-Business",
    # Personal — friends, family, real human messages
    "personal": "InboxScout/Personal",
    "friend": "InboxScout/Personal",
    "family": "InboxScout/Personal",
    "human": "InboxScout/Personal",
    # Medical — doctors, prescriptions, appointments
    "medical": "InboxScout/Medical",
    "health": "InboxScout/Medical",
    "doctor": "InboxScout/Medical",
    "hospital": "InboxScout/Medical",
    "prescription": "InboxScout/Medical",
    "appointment": "InboxScout/Medical",
    "medical billing": "InboxScout/Medical",
    # Legal-Tax — IRS, legal notices, government forms
    "legal": "InboxScout/Legal-Tax",
    "legal tax": "InboxScout/Legal-Tax",
    "irs": "InboxScout/Legal-Tax",
    "government": "InboxScout/Legal-Tax",
    "court": "InboxScout/Legal-Tax",
    "tax document": "InboxScout/Legal-Tax",
    "legal notice": "InboxScout/Legal-Tax",
    # Subscriptions — renewals, billing notices, trial ending
    "subscription": "InboxScout/Subscriptions",
    "subscriptions": "InboxScout/Subscriptions",
    "renewal": "InboxScout/Subscriptions",
    "renewals": "InboxScout/Subscriptions",
    "trial ending": "InboxScout/Subscriptions",
    "billing notice": "InboxScout/Subscriptions",
    # Newsletters — digests, creator updates, Substack
    "newsletter": "InboxScout/Newsletters",
    "newsletters": "InboxScout/Newsletters",
    "digest": "InboxScout/Newsletters",
    "substack": "InboxScout/Newsletters",
    # Promotions — coupons, sales, marketing, abandoned cart
    "promotion": "InboxScout/Promotions",
    "promotions": "InboxScout/Promotions",
    "promo": "InboxScout/Promotions",
    "coupon": "InboxScout/Promotions",
    "sale": "InboxScout/Promotions",
    "marketing": "InboxScout/Promotions",
    "advertising": "InboxScout/Promotions",
    "abandoned cart": "InboxScout/Promotions",
    "brand offer": "InboxScout/Promotions",
    # Social-Notifications — Reddit, Discord, YouTube, social platforms
    "social": "InboxScout/Social-Notifications",
    "social notifications": "InboxScout/Social-Notifications",
    "reddit": "InboxScout/Social-Notifications",
    "discord": "InboxScout/Social-Notifications",
    "facebook": "InboxScout/Social-Notifications",
    "instagram": "InboxScout/Social-Notifications",
    "tiktok": "InboxScout/Social-Notifications",
    "youtube": "InboxScout/Social-Notifications",
    "twitter": "InboxScout/Social-Notifications",
    "forum": "InboxScout/Social-Notifications",
    "community": "InboxScout/Social-Notifications",
    "notification": "InboxScout/Social-Notifications",
    "notifications": "InboxScout/Social-Notifications",
    # School-Learning — courses, certificates, training
    "school": "InboxScout/School-Learning",
    "learning": "InboxScout/School-Learning",
    "course": "InboxScout/School-Learning",
    "certificate": "InboxScout/School-Learning",
    "training": "InboxScout/School-Learning",
    "bootcamp": "InboxScout/School-Learning",
    "education": "InboxScout/School-Learning",
    "study": "InboxScout/School-Learning",
    "lab": "InboxScout/School-Learning",
    # AI-Dev-Tools — Claude, OpenAI, GitHub, dev platforms
    "ai dev tools": "InboxScout/AI-Dev-Tools",
    "developer": "InboxScout/AI-Dev-Tools",
    "dev tools": "InboxScout/AI-Dev-Tools",
    "github": "InboxScout/AI-Dev-Tools",
    "claude": "InboxScout/AI-Dev-Tools",
    "anthropic": "InboxScout/AI-Dev-Tools",
    "anthropic receipt": "InboxScout/AI-Dev-Tools",
    "anthropic invoice": "InboxScout/AI-Dev-Tools",
    "openai": "InboxScout/AI-Dev-Tools",
    "chatgpt": "InboxScout/AI-Dev-Tools",
    "replit": "InboxScout/AI-Dev-Tools",
    "cursor": "InboxScout/AI-Dev-Tools",
    "ollama": "InboxScout/AI-Dev-Tools",
    "vercel": "InboxScout/AI-Dev-Tools",
    "render": "InboxScout/AI-Dev-Tools",
    "lovable": "InboxScout/AI-Dev-Tools",
    "openrouter": "InboxScout/AI-Dev-Tools",
    "coding": "InboxScout/AI-Dev-Tools",
    # Amazon / retail ordering — AI may return these exact category strings
    "amazon order": "InboxScout/Shopping-History",
    "amazon shipped": "InboxScout/Shipping-Returns",
    "amazon delivered": "InboxScout/Shopping-History",
    "amazon tracking": "InboxScout/Shipping-Returns",
    "order notification": "InboxScout/Shopping-History",
    "order update": "InboxScout/Shopping-History",
    "order status": "InboxScout/Shopping-History",
    "order placed": "InboxScout/Receipts",
    "order shipped": "InboxScout/Shipping-Returns",
    "shipping update": "InboxScout/Shipping-Returns",
    "shipping confirmation": "InboxScout/Shipping-Returns",
    "delivery notification": "InboxScout/Shopping-History",
    "delivery update": "InboxScout/Shopping-History",
    "package tracking": "InboxScout/Shipping-Returns",
    "tracking update": "InboxScout/Shipping-Returns",
    # USPS / carrier receipts
    "usps": "InboxScout/Shipping-Returns",
    "click-n-ship": "InboxScout/Receipts",
    "click n ship": "InboxScout/Receipts",
    "shipping label": "InboxScout/Shipping-Returns",
    # Finance — more specific AI-returned strings for true Finance
    "paypal statement": "InboxScout/Finance",
    "paypal monthly": "InboxScout/Finance",
    "merrill": "InboxScout/Finance",
    "merrill lynch": "InboxScout/Finance",
    "brokerage statement": "InboxScout/Finance",
    "investment statement": "InboxScout/Finance",
    "account statement": "InboxScout/Finance",
}


def _parse_limit(text: str) -> int:
    m = re.search(r"\b(\d+)\b", text.lower())
    if m:
        return min(max(int(m.group(1)), 1), AUTOPILOT_MAX_LIMIT)
    return AUTOPILOT_DEFAULT_LIMIT


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _run_scan(account: str = "primary") -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    argv = [sys.executable, "-m", "inbox_scout.sort_scan_queue_runner", "--run"]
    if account != "primary":
        argv += ["--account", account]
    return subprocess.run(
        argv,
        cwd=str(PROJECT_ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=900,
    )


def run_autopilot_cleanup(text: str, account: str = "primary") -> str:
    m = re.search(r"\b(\d+)\b", text.lower())
    raw_limit = int(m.group(1)) if m else AUTOPILOT_DEFAULT_LIMIT
    limit = min(max(raw_limit, 1), AUTOPILOT_MAX_LIMIT)
    capped = raw_limit > AUTOPILOT_MAX_LIMIT

    # Build a plain scan plan using the capped limit.
    # We use "sort N emails" as the canonical plan text so the plan builder
    # takes the non-cleanup_mode branch, which respects the limit correctly.
    plan = build_scan_queue_plan(f"sort {limit} emails")
    if plan.workflow_mode != "commands_planned":
        return "Could not build a safe scan plan. Gmail not touched."
    plan.requested_limit = min(plan.requested_limit or limit, AUTOPILOT_MAX_LIMIT)
    save_plan(plan)

    # Step 1: read-only Gmail scan + local queue build
    try:
        result = _run_scan(account)
    except subprocess.TimeoutExpired:
        return "Scan timed out after 15 minutes. Gmail not touched."

    run_data = _load_json(LATEST_SCAN_QUEUE_RUN)
    if result.returncode != 0 or run_data.get("status") != "complete":
        return "Scan did not complete cleanly. Gmail not touched."

    # Step 2: build local cleanup plan from queue
    cleanup_plan = build_inbox_cleanup_plan()

    scanned = cleanup_plan.total_scanned
    protected = cleanup_plan.protected_count
    needs_review = cleanup_plan.needs_review_count
    candidates = cleanup_plan.trash_candidate_count

    if scanned == 0:
        return "No emails scanned. Gmail not touched."

    cap_note = f"(Scan capped at {AUTOPILOT_MAX_LIMIT} — you requested {raw_limit}.)\n" if capped else ""
    header = (
        f"{cap_note}Scanned {scanned} — {protected} protected, "
        f"{needs_review} unclear, {candidates} trash candidates."
    )

    if candidates == 0:
        return (
            f"{header}\n\n"
            "No obvious junk found. Nothing moved.\n"
            "Protected and unclear emails were left alone.\n"
            "Gmail not touched."
        )

    # Step 3: move safe trash candidates + mark-read after each successful trash
    runner_msg = build_inbox_cleanup_runner_message()
    return f"{header}\n\n{runner_msg}"


# ---------------------------------------------------------------------------
# Inbox-zero autopilot helpers
# ---------------------------------------------------------------------------

def _norm_cat(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace("_", " ").replace("-", " ")


def _get_msg_id_for_item(item: dict) -> str | None:
    for key in ("gmail_message_id", "message_id", "gmail_id", "email_id"):
        if item.get(key):
            return str(item[key])
    return None


def _item_is_protected_for_autopilot(item: dict) -> bool:
    decision = _norm_cat(item.get("local_decision"))
    if "protected" in decision:
        return True
    if item.get("manual_review") or item.get("manual_review_required"):
        return True
    return False


def _item_risk(item: dict) -> int:
    try:
        return int(item.get("risk_score") or item.get("risk") or 999)
    except Exception:
        return 999


def _item_already_handled(item: dict) -> bool:
    if item.get("gmail_trashed"):
        return True
    return _norm_cat(item.get("gmail_action_type")) in {"trashed", "archived"}


def _parse_trashed_count(runner_msg: str) -> int:
    m = re.search(r"Moved (\d+) email", runner_msg)
    return int(m.group(1)) if m else 0


def _beep_once() -> None:
    """Emit one terminal bell so the watcher window chimes at run completion."""
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass


# Signals that confirm true Finance — block any Finance → other-folder demotion.
_FINANCE_KEEP_SIGNALS: frozenset[str] = frozenset({
    "statement", "bank statement", "credit card", "investment", "irs", "tax form",
    "w-2", "1099", "401k", "payroll", "merrill", "fidelity", "schwab", "vanguard",
    "brokerage", "mortgage", "insurance premium",
})


def _override_finance_label(item: dict) -> str | None:
    """Return a better label when Finance is over-assigned due to broad keywords.

    Returns None to keep Finance when a true Finance signal is found in
    subject/snippet, or when the sender is not a known retail/AI sender.
    """
    sender = (item.get("from") or "").lower()
    subject = (item.get("subject") or item.get("snippet") or "").lower()

    # Never demote when a true Finance signal is present
    if any(sig in subject for sig in _FINANCE_KEEP_SIGNALS):
        return None

    # Amazon → route by subject signals
    if "amazon" in sender:
        if any(s in subject for s in ("shipped", "shipment", "tracking", "on its way", "out for delivery")):
            return "InboxScout/Shipping-Returns"
        return "InboxScout/Receipts"

    # Anthropic → AI-Dev-Tools (receipts, welcome, plan emails)
    if "anthropic" in sender:
        return "InboxScout/AI-Dev-Tools"

    # USPS → Click-N-Ship payment → Receipts; other USPS → Shipping-Returns
    if "usps" in sender:
        if "click-n-ship" in subject or "click n ship" in subject or "payment" in subject:
            return "InboxScout/Receipts"
        return "InboxScout/Shipping-Returns"

    return None


def _pick_inboxscout_label(item: dict) -> str:
    cat = _norm_cat(item.get("category") or item.get("final_category") or "")

    # Finance override: use sender/subject to route to a more precise folder
    # when the Finance category was triggered by overly broad rule keywords.
    if cat == "finance":
        override = _override_finance_label(item)
        if override:
            return override

    if cat in CATEGORY_TO_LABEL:
        return CATEGORY_TO_LABEL[cat]
    for part in cat.split("/"):
        part = part.strip()
        if part in CATEGORY_TO_LABEL:
            return CATEGORY_TO_LABEL[part]
    return "InboxScout/Review"


def _get_or_create_label(service: Any, label_name: str, cache: dict) -> str | None:
    if label_name in cache:
        return cache[label_name]
    try:
        results = service.users().labels().list(userId="me").execute()
        existing = {lbl["name"]: lbl["id"] for lbl in results.get("labels", [])}
        if label_name in existing:
            cache[label_name] = existing[label_name]
            return existing[label_name]
        created = service.users().labels().create(
            userId="me",
            body={
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        ).execute()
        lid = created["id"]
        cache[label_name] = lid
        return lid
    except Exception:
        return None


def _load_items_from_queue() -> list[dict]:
    if not QUEUE_PATH.exists():
        return []
    try:
        data = json.loads(QUEUE_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("queue_items", "items", "queue"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _process_non_trash_items(service: Any, items: list[dict], label_cache: dict) -> dict:
    labeled = archived = marked_read = protected_count = errors = 0

    for item in items:
        if _item_already_handled(item):
            continue

        msg_id = _get_msg_id_for_item(item)
        if not msg_id:
            errors += 1
            continue

        cat = _norm_cat(item.get("category") or item.get("final_category") or "")
        protected = _item_is_protected_for_autopilot(item)
        risk = _item_risk(item)

        label_name = _pick_inboxscout_label(item)
        label_id = _get_or_create_label(service, label_name, label_cache)

        if label_id is None:
            errors += 1
            continue

        add_labels: list[str] = [label_id]
        # Always remove INBOX and UNREAD after successful label application.
        # Protected/manual-review items are labeled InboxScout/Review and archived
        # (recoverable). Only trashing is blocked for them — not archiving.
        remove_labels: list[str] = ["INBOX", "UNREAD"]

        if protected:
            protected_count += 1
            continue  # never label, archive, or mark-read protected/manual-review items

        try:
            service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"addLabelIds": add_labels, "removeLabelIds": remove_labels},
            ).execute()
            labeled += 1
            archived += 1
            marked_read += 1
        except Exception:
            errors += 1

    return {
        "labeled": labeled,
        "archived": archived,
        "marked_read": marked_read,
        "protected": protected_count,
        "errors": errors,
    }


def _get_unread_inbox_count(service: Any) -> int:
    try:
        result = service.users().labels().get(userId="me", id="INBOX").execute()
        return int(result.get("messagesUnread", 0))
    except Exception:
        return 0


def _get_total_inbox_count(service: Any) -> int:
    try:
        result = service.users().labels().get(userId="me", id="INBOX").execute()
        return int(result.get("messagesTotal", 0))
    except Exception:
        return 0


def _get_modify_service_for_autopilot(account: str = "primary") -> Any:
    from inbox_scout.gmail_auth import get_gmail_service
    try:
        return get_gmail_service(mode="modify", account=account)
    except TypeError:
        return get_gmail_service("modify")


def run_inbox_zero_autopilot(text: str, account: str = "primary", _collect: list | None = None) -> str:
    """Process all unread INBOX emails: trash safe + label + mark-read until inbox is empty."""
    total_scanned = total_trashed = total_labeled = total_archived = 0
    total_marked_read = total_protected = total_errors = 0
    stopped_early = False

    try:
        service = _get_modify_service_for_autopilot(account)
    except Exception as e:
        _beep_once()
        return f"Could not connect to Gmail.\n\n{e}\n\nGmail not touched."

    initial_unread = _get_unread_inbox_count(service)
    initial_total = _get_total_inbox_count(service)

    if initial_unread == 0:
        _beep_once()
        if initial_total == 0:
            return "Inbox is empty. Gmail not touched."
        read_word, verb = ("email", "remains") if initial_total == 1 else ("emails", "remain")
        return (
            f"No unread inbox emails to process. "
            f"{initial_total} read inbox {read_word} {verb}.\n\nGmail not touched."
        )

    label_cache: dict = {}
    no_progress_stop = False
    cursor_path = PLANS_DIR / "latest_gmail_scan_cursor.json"

    # Always start from page 1; delete any saved cursor.
    if cursor_path.exists():
        cursor_path.unlink()

    # Loop until inbox is empty (scan returns 0) or emergency runaway cap is hit.
    while total_scanned < AUTOPILOT_EMERGENCY_CAP:
        # Never use continuation — always scan page 1 so that emails removed
        # from INBOX by prior actions don't cause stale page-token skips.
        plan = build_scan_queue_plan(f"sort {AUTOPILOT_MAX_LIMIT} emails")
        if plan.workflow_mode != "commands_planned":
            stopped_early = True
            break
        plan.requested_limit = AUTOPILOT_MAX_LIMIT
        plan.sort_all = True   # belt-and-suspenders: signal to runner to skip --unread-only
        plan.target = "inbox"  # primary signal: scan all INBOX, not just unread
        save_plan(plan)

        try:
            scan_result = _run_scan(account)
        except subprocess.TimeoutExpired:
            total_errors += 1
            stopped_early = True
            break

        run_data = _load_json(LATEST_SCAN_QUEUE_RUN)
        if scan_result.returncode != 0 or run_data.get("status") != "complete":
            total_errors += 1
            stopped_early = True
            break

        items = _load_items_from_queue()
        if not items:
            break  # Inbox fully processed.

        if _collect is not None:
            _collect.extend(item for item in items if _is_digest_worthy(item))

        total_scanned += len(items)

        # Trash safe candidates; count only actual successes.
        trashed_before = total_trashed
        cleanup_plan = build_inbox_cleanup_plan()
        if cleanup_plan.trash_candidate_count > 0:
            runner_msg = build_inbox_cleanup_runner_message()
            actual_trashed = _parse_trashed_count(runner_msg)
            items = _load_items_from_queue()
            total_trashed += actual_trashed
            total_marked_read += actual_trashed

        # Label + mark-read non-trash items.
        result_data = _process_non_trash_items(service, items, label_cache)
        total_labeled += result_data["labeled"]
        total_archived += result_data["archived"]
        total_marked_read += result_data["marked_read"]
        total_protected += result_data["protected"]
        total_errors += result_data["errors"]

        # No-progress guard: if this batch found items but nothing was trashed,
        # labeled, archived, or marked-read, all remaining items are protected/
        # manual-review. Stop now to avoid looping forever on the same emails.
        trashed_this_iter = total_trashed - trashed_before
        if trashed_this_iter + result_data["labeled"] == 0 and items:
            no_progress_stop = True
            stopped_early = True
            break

    emergency_cap_hit = total_scanned >= AUTOPILOT_EMERGENCY_CAP
    complete = not stopped_early and not emergency_cap_hit

    lines = [
        "Inbox Zero complete." if complete else "Inbox Zero stopped.",
        "",
        f"Starting Inbox total: {initial_total}",
        f"Starting unread: {initial_unread}",
        f"Scanned: {total_scanned}",
        f"Moved to Trash: {total_trashed}",
        f"Labeled: {total_labeled}",
        f"Archived: {total_archived}",
        f"Marked read: {total_marked_read}",
        f"Flagged for your review: {total_protected}",
    ]
    if total_errors:
        lines.append(f"Couldn't process: {total_errors}")
    if no_progress_stop:
        lines.append("All remaining emails need your review — auto-sort skipped them.")
    elif stopped_early and not emergency_cap_hit:
        lines.append("Hit an error midway — run sort all again to continue.")
    if emergency_cap_hit:
        lines.extend(["", f"Hit the safety limit ({AUTOPILOT_EMERGENCY_CAP} emails) — run sort all again to continue."])
    lines.extend(["", "Nothing permanently deleted — all recoverable from Gmail."])
    _beep_once()
    return "\n".join(lines)
