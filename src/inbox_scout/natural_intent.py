from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from inbox_scout.telegram_status import build_status_message, build_moved_message, build_still_needs_review_message
from inbox_scout.inbox_count import build_inbox_count_message
from inbox_scout.sort_scan_queue_plan import build_scan_queue_plan, save_plan
from inbox_scout.sort_scan_queue_approval import build_scan_approval_response
from inbox_scout.review_plan import build_review_plan_message
from inbox_scout.archive_approval_plan import build_archive_plan_message
from inbox_scout.archive_confirmation_plan import build_archive_confirmation_message
from inbox_scout.archive_execution_gate import build_archive_execution_gate_message
from inbox_scout.archive_execution_runner import build_archive_runner_message
from inbox_scout.trash_candidate_plan import build_trash_plan_message
from inbox_scout.trash_confirmation_plan import build_trash_confirmation_message
from inbox_scout.trash_execution_gate import build_trash_execution_gate_message
from inbox_scout.trash_execution_runner import build_trash_runner_message
from inbox_scout.inbox_cleanup_runner import build_inbox_cleanup_runner_message
from inbox_scout.cleanup_control import build_cleanup_status_message, build_cancel_cleanup_message
from inbox_scout.trash_sender_block_plan import build_sender_block_plan_message
from inbox_scout.trash_sender_block_runner import build_sender_block_runner_message
from inbox_scout.model_router import get_provider, set_provider, model_status_message, get_active_provider, OLLAMA_MODEL, OPENROUTER_MODEL
from inbox_scout.mark_read_runner import build_mark_read_plan_message, build_mark_read_runner_message
from inbox_scout.queue_decision import build_set_decision_message
from inbox_scout.autopilot_cleanup import run_autopilot_cleanup, run_inbox_zero_autopilot, _is_digest_worthy
from inbox_scout.natural_intent_llm import parse_intent, CONFIDENCE_THRESHOLD
from inbox_scout.folder_explorer import (
    build_folder_counts_message,
    build_drilldown_message,
    parse_drilldown,
    is_drilldown_phrase,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"
_LLM_PENDING_PATH = PROJECT_ROOT / "config" / "llm_pending_action.json"


def _save_pending_autopilot(original_text: str) -> None:
    _LLM_PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LLM_PENDING_PATH.write_text(
        json.dumps({"pending": "inbox_zero_autopilot", "original_text": original_text}),
        encoding="utf-8",
    )


def _get_pending_action() -> dict:
    if not _LLM_PENDING_PATH.exists():
        return {}
    try:
        return json.loads(_LLM_PENDING_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _clear_pending_action() -> None:
    if _LLM_PENDING_PATH.exists():
        _LLM_PENDING_PATH.unlink()


_CONFIRM_ALIASES: frozenset = frozenset({
    "confirm", "yes", "y", "yep", "yeah", "do it", "go ahead",
    "start", "run it", "proceed", "approve", "okay", "ok", "sure",
})

_CANCEL_ALIASES: frozenset = frozenset({
    "cancel", "stop", "nevermind", "never mind", "no", "nope",
    "don't", "dont", "abort", "back out", "forget it", "not now",
    "cancel that", "stop that",
})


def _is_pending_autopilot_confirmation(msg: str) -> bool:
    return (
        _get_pending_action().get("pending") == "inbox_zero_autopilot"
        and msg in _CONFIRM_ALIASES
    )


def _is_pending_autopilot_cancellation(msg: str) -> bool:
    return (
        bool(_get_pending_action().get("pending"))
        and msg in _CANCEL_ALIASES
    )


def _execute_pending_autopilot(pending: dict, fallback_text: str) -> str:
    _orig = pending.get("original_text", fallback_text)
    _scope = _account_scope_for_action(_orig)
    if _scope == "both":
        return _run_both_inbox_zero(_orig)
    return run_inbox_zero_autopilot(_orig, account=_scope)


_PRIMARY_RE = re.compile(
    r"\b(first|main|primary)\s+(email|account|gmail|inbox)\b", re.IGNORECASE
)
_SECONDARY_RE = re.compile(
    r"\b(second(ary)?|other)\s+(email|account|gmail|inbox)\b", re.IGNORECASE
)
_BOTH_RE = re.compile(
    r"\b(both|all)\s+(emails?|accounts?|gmails?|inboxes?)\b", re.IGNORECASE
)


def _parse_account(msg: str) -> str:
    """Return explicit account scope, or 'unspecified' if no account phrase present."""
    if _BOTH_RE.search(msg):
        return "both"
    if _PRIMARY_RE.search(msg):
        return "primary"
    if _SECONDARY_RE.search(msg):
        return "secondary"
    return "unspecified"


def _account_scope_for_action(text: str) -> str:
    """For write-capable action commands: treat unspecified as both."""
    scope = _parse_account(text)
    return "both" if scope == "unspecified" else scope


def _account_label(scope: str) -> str:
    if scope == "both":
        return "both emails (ryanrjfrechette@gmail.com + ryanrfrechette@gmail.com)"
    if scope == "secondary":
        return "second email (ryanrfrechette@gmail.com)"
    return "primary email (ryanrjfrechette@gmail.com)"


def _autopilot_confirm_prompt(text: str) -> str:
    """Save pending action and return confirmation prompt showing target account scope."""
    _save_pending_autopilot(text)
    _acct = _account_scope_for_action(text)
    return (
        "I can start safely working through your inbox — "
        "this can move, label, and trash safe emails.\n\n"
        f"Target: {_account_label(_acct)}\n\n"
        "Reply CONFIRM INBOX AUTOPILOT to start, or 'cancel autopilot' to cancel."
    )


_DIGEST_BUCKET_MAP: dict = {
    "InboxScout/Jobs": "Jobs / Interviews",
    "InboxScout/Finance": "Money / Bills / Security",
    "InboxScout/Security": "Money / Bills / Security",
    "InboxScout/Medical": "Medical / Legal",
    "InboxScout/Legal-Tax": "Medical / Legal",
    "InboxScout/Personal": "Personal / Urgent",
}
_DIGEST_BUCKET_ORDER = [
    "Jobs / Interviews",
    "Money / Bills / Security",
    "Medical / Legal",
    "Personal / Urgent",
    "Needs Review",
]


def _build_important_digest(primary_items: list, secondary_items: list) -> str:
    primary_items = [i for i in primary_items if _is_digest_worthy(i)]
    secondary_items = [i for i in secondary_items if _is_digest_worthy(i)]
    if not primary_items and not secondary_items:
        return "No important emails flagged from this run."
    sections = []
    for label, items in [("Primary email", primary_items), ("Second email", secondary_items)]:
        if not items:
            continue
        buckets: dict = {b: [] for b in _DIGEST_BUCKET_ORDER}
        for item in items:
            cat = (item.get("category") or "").strip()
            bucket = _DIGEST_BUCKET_MAP.get(cat, "Needs Review")
            subject = item.get("subject") or "(No subject)"
            sender = item.get("from") or ""
            buckets[bucket].append(f"- {subject} — {sender}")
        account_lines = [f"{label}:"]
        for bucket in _DIGEST_BUCKET_ORDER:
            if buckets[bucket]:
                account_lines.append(f"  {bucket}:")
                account_lines.extend(f"    {line}" for line in buckets[bucket])
        if len(account_lines) > 1:
            sections.append("\n".join(account_lines))
    if not sections:
        return "No important emails flagged from this run."
    return "--- What needs your attention ---\n" + "\n\n".join(sections)


def _run_both_inbox_zero(text: str) -> str:
    primary_items: list = []
    primary_result = run_inbox_zero_autopilot(text, account="primary", _collect=primary_items)
    secondary_items: list = []
    secondary_result = run_inbox_zero_autopilot(text, account="secondary", _collect=secondary_items)
    digest = _build_important_digest(primary_items, secondary_items)
    return (
        "--- Primary email ---\n"
        f"{primary_result}\n\n"
        "--- Second email ---\n"
        f"{secondary_result}\n\n"
        f"{digest}"
    )


def _run_both_autopilot_cleanup(text: str) -> str:
    primary_result = run_autopilot_cleanup(text, account="primary")
    secondary_result = run_autopilot_cleanup(text, account="secondary")
    return (
        "--- Primary email ---\n"
        f"{primary_result}\n\n"
        "--- Second email ---\n"
        f"{secondary_result}"
    )


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def load_queue_items() -> list[dict[str, Any]]:
    if not LATEST_QUEUE.exists():
        return []

    data = json.loads(LATEST_QUEUE.read_text(encoding="utf-8-sig"))

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("queue_items", [])

    return []


def sort_plan_message(text: str, continuation: bool = False, cleanup: bool = False) -> str:
    plan = build_scan_queue_plan(text, continuation=continuation, cleanup_mode=cleanup)
    save_plan(plan)

    if plan.workflow_mode == "blocked_phase_14_only":
        return (
            "Permanent delete is disabled.\n\n"
            "That is a Phase 14 nuclear feature. I did not scan or delete anything."
        )

    if plan.workflow_mode != "commands_planned":
        return (
            "Not sure how to turn that into a safe sort plan.\n\n"
            "Try: sort 5 emails\n\n"
            "Gmail not touched."
        )

    _limit = plan.requested_limit or 5
    _prov = get_active_provider(batch_size=_limit)
    _model = OPENROUTER_MODEL if _prov == "openrouter" else OLLAMA_MODEL
    _prov_line = f"Using {_prov}: {_model}"

    if plan.sort_all:
        if plan.is_continuation:
            return (
                "Picking up where we left off — scanning the next 5 unread emails.\n\n"
                f"{_prov_line}\n"
                "Nothing in Gmail changes until you confirm.\n\n"
                "Say yes to scan this batch, or cancel."
            )
        if plan.cleanup_mode and "test" in text.lower():
            return (
                f"I'll scan up to {plan.requested_limit} unread emails and build a cleanup plan.\n"
                "Nothing moves until you review the candidates and say move trash.\n\n"
                f"{_prov_line}\n"
                "Nothing in Gmail changes yet.\n\n"
                "Say yes to start, or cancel."
            )
        if plan.cleanup_mode:
            return (
                "I'll scan your whole unread inbox and put together a cleanup plan.\n"
                "Depending on how many emails you have, this might take a few passes.\n"
                "Nothing moves until you say move trash.\n\n"
                f"{_prov_line}\n"
                "Nothing in Gmail changes yet.\n\n"
                "Say yes to start, or cancel."
            )
        return (
            "I'll scan the first 5 unread emails and build a review queue.\n"
            "Say continue sorting after each batch to keep going.\n\n"
            f"{_prov_line}\n"
            "Nothing in Gmail changes yet.\n\n"
            "Say yes to scan, or cancel."
        )

    return (
        f"I'll scan {plan.requested_limit} unread emails and build a review queue.\n\n"
        f"{_prov_line}\n"
        "Nothing in Gmail changes yet.\n\n"
        "Say yes to scan, or cancel."
    )


def queue_summary() -> str:
    items = load_queue_items()

    if not items:
        return "No queue yet. Run sort to scan your inbox first."

    protected = [
        item for item in items
        if clean(item.get("local_decision")).lower() == "protected_review"
        or is_true(item.get("manual_review"))
    ]

    handled = [
        item for item in items
        if clean(item.get("gmail_action_type")) or is_true(item.get("gmail_marked_read"))
    ]

    pending = [
        item for item in items
        if clean(item.get("local_decision")).lower() == "pending_review"
    ]

    lines = [
        f"Current batch — {len(items)} emails:",
        "",
        f"Flagged for review: {len(protected)}",
        f"Already handled: {len(handled)}",
        f"Still pending: {len(pending)}",
        "",
    ]

    for item in items:
        qid = clean(item.get("queue_id") or item.get("id") or "?")
        decision = clean(item.get("local_decision"))
        risk = clean(item.get("risk_score") or item.get("risk"))
        subject = clean(item.get("subject"))[:55]
        lines.append(f"ID {qid}: {decision} | risk {risk}")
        lines.append(f"- {subject}")

    lines.append("")
    lines.append("No Gmail changes were made.")
    return "\n".join(lines)


def next_review_item() -> str:
    items = load_queue_items()

    for item in items:
        decision = clean(item.get("local_decision")).lower()
        if decision == "pending_review":
            return (
                "Here's the next one:\n\n"
                f"ID: {clean(item.get('queue_id'))}\n"
                f"Category: {clean(item.get('category'))}\n"
                f"Risk: {clean(item.get('risk_score') or item.get('risk'))}\n"
                f"From: {clean(item.get('from'))}\n"
                f"Subject: {clean(item.get('subject'))}\n\n"
                "Nothing in Gmail has changed."
            )

    return "Nothing left to review in this batch."


def help_message() -> str:
    return (
        "Just talk to me naturally. Some things you can say:\n\n"
        "- sort 5 emails\n"
        "- sort all\n"
        "- clean up my inbox\n"
        "- show me the queue\n"
        "- what needs my attention?\n"
        "- how many emails are in my inbox?\n\n"
        "I won't touch Gmail without your approval."
    )


def _handle_model_command(msg: str) -> str | None:
    """Return a response if the message is a /model command, else None."""
    stripped = msg.lstrip("/").strip()
    if not stripped.startswith("model"):
        return None
    parts = stripped.split()
    if len(parts) < 2:
        return model_status_message()
    subcmd = parts[1]
    if subcmd == "status":
        return model_status_message()
    if subcmd == "local":
        set_provider("local")
        return "Switched to local mode (Ollama/qwen3:8b). No cloud API calls."
    if subcmd == "openrouter":
        set_provider("openrouter")
        return "Switched to OpenRouter (google/gemini-2.5-flash-lite). Requires OPENROUTER_API_KEY."
    if subcmd == "auto":
        set_provider("auto")
        return (
            "Switched to auto mode.\n\n"
            "Rules:\n"
            "- Obvious newsletter/promo (risk <=30): no AI\n"
            "- Small scans (<=10 emails): local\n"
            "- Mass cleanup (>10 emails): OpenRouter\n"
            "- Protected/sensitive: manual review always"
        )
    return f"Unknown model command: {subcmd}\n\nTry: /model status | /model local | /model openrouter | /model auto"


_AUTOPILOT_PHRASES = [
    "get me closer to inbox zero",
    "handle a batch",
    "clean the next",
    "clean up my inbox",
    "clean my inbox",
    "cleanup my inbox",
    "clean inbox",
]


def _is_autopilot_cleanup(msg: str) -> bool:
    if any(phrase in msg for phrase in _AUTOPILOT_PHRASES):
        return True
    return bool(re.search(r"\b(sort|clean)\s+\d+\b", msg))


_INBOX_ZERO_PHRASES = [
    "sort all",
    "clean all",
    "get me to inbox zero",
    "file my inbox",
    "sort my whole inbox",
    "clean my whole inbox",
]


def _is_inbox_zero(msg: str) -> bool:
    return any(phrase in msg for phrase in _INBOX_ZERO_PHRASES)


def _llm_fallback(text: str) -> str:
    """LLM intent parser — runs only when all deterministic routes fail."""
    parsed = parse_intent(text)
    intent = parsed.get("intent", "unknown")
    confidence = parsed.get("confidence", 0.0)
    clarifying = parsed.get("clarifying_question", "").strip()

    if confidence < CONFIDENCE_THRESHOLD or intent == "unknown":
        if clarifying:
            return clarifying
        return "Not sure what you mean.\n\n" + help_message()

    if intent == "inbox_count":
        return build_inbox_count_message()
    if intent == "inbox_zero_autopilot":
        return _autopilot_confirm_prompt(text)
    if intent == "queue_summary":
        return queue_summary()
    if intent == "next_review_item":
        return next_review_item()
    if intent == "model_status":
        return model_status_message()
    if intent == "help":
        return help_message()

    return "Not sure what you mean.\n\n" + help_message()


def handle_natural_message(text: str) -> str:
    msg = text.lower().strip()

    # Natural confirmation aliases — only fires when pending autopilot exists
    if _is_pending_autopilot_confirmation(msg):
        pending = _get_pending_action()
        _clear_pending_action()
        return _execute_pending_autopilot(pending, text)

    # Exact confirm phrase — also gives feedback when nothing is pending
    if msg == "confirm inbox autopilot":
        pending = _get_pending_action()
        if pending.get("pending") == "inbox_zero_autopilot":
            _clear_pending_action()
            return _execute_pending_autopilot(pending, text)
        return "No inbox autopilot is pending. Say something like 'handle my inbox' to start."

    # Natural cancellation aliases — only fires when pending exists
    if _is_pending_autopilot_cancellation(msg):
        _clear_pending_action()
        return "Cancelled. Gmail not touched."

    if any(p in msg for p in ("cancel autopilot", "cancel inbox autopilot")):
        if _get_pending_action().get("pending"):
            _clear_pending_action()
            return "Cancelled. Gmail not touched."
        return "Nothing pending to cancel."

    model_response = _handle_model_command(msg)
    if model_response is not None:
        return model_response

    decision_response = build_set_decision_message(msg)
    if decision_response is not None:
        return decision_response

    # Cleanup control commands must run before generic "status" matching.
    if any(phrase in msg for phrase in [
        "cleanup status",
        "cleanup progress",
        "cleaning status",
    ]):
        return build_cleanup_status_message()

    if any(phrase in msg for phrase in [
        "cancel cleanup",
        "stop cleanup",
        "pause cleanup",
    ]):
        return build_cancel_cleanup_message()


    if msg in {"yes", "y", "approve", "go ahead", "run it", "do it", "start scan", "run the scan", "proceed"}:
        return build_scan_approval_response(text)

    if msg in {"cancel", "stop", "never mind", "nevermind"}:
        return "Cancelled. Gmail not touched."

    if any(phrase in msg for phrase in [
        "empty my trash",
        "delete everything in trash",
        "delete everything in the trash",
        "clear the trash",
        "clear my trash",
        "clear the trash folder",
        "wipe the trash",
        "delete all trashed emails",
        "permanently delete",
    ]):
        return sort_plan_message(text)

    if any(phrase in msg for phrase in [
        "how many emails",
        "how many unread",
        "email count",
        "inbox count",
        "how full is my inbox",
        "how many emails are in my inbox",
        "how bad is my inbox",
        "inbox situation",
        "give me the inbox situation",
        "what's my inbox looking like",
        "whats my inbox looking like",
        "am i close to inbox zero",
    ]):
        return build_inbox_count_message()

    if any(word in msg for word in ["help", "commands", "what can you do"]):
        return help_message()


    if msg in {
        "what did you move",
        "what did you move?",
        "what did you trash",
        "what did you trash?",
        "what got moved",
        "what got moved?",
        "what happened",
        "last move",
        "last trash move",
        "show last move",
    }:
        return build_moved_message()

    if msg in {
        "what still needs review",
        "what still needs review?",
        "what needs review",
        "what needs review?",
        "what needs my attention",
        "what still needs my attention",
        "show remaining review",
        "show remaining reviews",
        "remaining review",
        "remaining reviews",
    }:
        return build_still_needs_review_message()

    if any(phrase in msg for phrase in [
        "resort my sorted emails",
        "resort my emails",
        "resort sorted emails",
        "resort everything",
        "audit my archives",
        "check if anything is in the wrong folder",
        "are my emails sorted correctly",
        "resort preview",
        "show resort preview",
        "audit sorted folders",
        "check my sorted folders",
    ]):
        from inbox_scout.resort_mode import build_resort_preview_message
        _scope = _parse_account(msg)
        if _scope == "unspecified":
            _scope = "both"
        return build_resort_preview_message(account=_scope)

    if any(phrase in msg for phrase in [
        "confirm resort apply",
        "apply resort fixes",
        "apply resort corrections",
        "apply resort",
    ]):
        from inbox_scout.resort_apply_runner import build_resort_apply_message
        return build_resort_apply_message()

    if any(phrase in msg for phrase in ["status", "audit", "how is my inbox", "inbox status"]):
        return build_status_message()

    if msg in {"run archive dry run", "archive runner", "test archive runner"}:
        return build_archive_runner_message(apply=False)

    if msg in {"try archive apply", "test archive apply"}:
        return build_archive_runner_message(apply=True)

    if msg in {"confirm archive", "run archive", "execute archive"}:
        return build_archive_execution_gate_message(text)

    if any(phrase in msg for phrase in [
        "prepare archive",
        "approve archive",
        "archive this",
        "archive candidate",
        "archive candidates",
        "confirm archive plan",
    ]):
        return build_archive_confirmation_message()

    if msg in {"run trash runner", "test trash runner", "run trash apply dry run"}:
        return build_trash_runner_message(apply=False)

    if msg in {"try trash apply", "test trash apply", "apply trash"}:
        return build_trash_runner_message(apply=True)

    if msg in {"confirm trash", "run trash dry run", "trash dry run", "test trash gate"}:
        return build_trash_execution_gate_message(text)

    if any(phrase in msg for phrase in [
        "prepare trash",
        "approve trash",
        "move them to trash",
        "confirm trash plan",
        "prepare trash move",
        "approve trash move",
    ]):
        return build_trash_confirmation_message()

    if any(phrase in msg for phrase in [
        "what can go to trash",
        "what can be trashed",
        "move junk to trash so i can review it",
        "move junk to trash",
        "trash the safe junk",
        "show trash plan",
        "what is safe to trash",
        "safe trash",
        "trash candidates",
    ]):
        return build_trash_plan_message()

    if any(phrase in msg for phrase in [
        "what can be archived",
        "what can you archive",
        "show archive plan",
        "archive plan",
        "safe archive",
        "archive candidates",
    ]):
        return build_archive_plan_message()

    if any(phrase in msg for phrase in [
        "show me the plan",
        "review plan",
        "what would you do",
        "what would you do with these emails",
        "what is the plan",
        "safe plan",
        "sort plan",
    ]):
        return build_review_plan_message()

    # --- Read-only folder/label explorer (must run before generic "show emails" queue check) ---
    if any(phrase in msg for phrase in [
        "show my folders",
        "show my archives",
        "show folders",
        "list folders",
        "what folders do i have",
        "what is in each folder",
        "show inboxscout folder counts",
        "give me a folder breakdown",
        "folder breakdown",
        "folder counts",
        "my folders",
        "label counts",
        "show labels",
        "inboxscout folders",
    ]):
        return build_folder_counts_message(account=_parse_account(msg))

    if is_drilldown_phrase(msg):
        label, days, summarize = parse_drilldown(msg)
        if label is None:
            return (
                "Which InboxScout folder? Try: Receipts, Finance, Promotions, "
                "Newsletters, Security, Jobs, Personal, Medical, Legal-Tax, Shopping-History."
            )
        return build_drilldown_message(label, days or 7, summarize=summarize, account=_parse_account(msg))

    if any(phrase in msg for phrase in ["queue", "show emails", "show my emails", "latest batch"]):
        return queue_summary()

    if any(phrase in msg for phrase in [
        "continue sorting",
        "sort more",
        "next batch",
        "keep sorting",
    ]):
        return sort_plan_message("sort all", continuation=True)

    if any(phrase in msg for phrase in [
        "cleanup test 25",
        "clean my inbox test 25",
        "test cleanup 25",
    ]):
        return sort_plan_message(text, cleanup=True)

    if _is_inbox_zero(msg):
        _scope = _account_scope_for_action(text)
        if _scope == "both":
            return _autopilot_confirm_prompt(text)
        return run_inbox_zero_autopilot(text, account=_scope)

    if _is_autopilot_cleanup(msg):
        _scope = _account_scope_for_action(text)
        if _scope == "both":
            return _autopilot_confirm_prompt(text)
        return run_autopilot_cleanup(text, account=_scope)

    if any(phrase in msg for phrase in ["next", "next review", "needs review", "what needs my attention"]):
        return next_review_item()

    if any(phrase in msg for phrase in [
        "cleanup status",
        "cleanup progress",
        "cleaning status",
    ]):
        return build_cleanup_status_message()

    if any(phrase in msg for phrase in [
        "cancel cleanup",
        "stop cleanup",
        "pause cleanup",
    ]):
        return build_cancel_cleanup_message()

    if any(phrase in msg for phrase in [
        "clean my inbox",
        "cleanup my inbox",
        "clean inbox",
        "sort all and move trash",
        "sort and move trash",
    ]):
        return sort_plan_message(text, cleanup=True)

    if any(phrase in msg for phrase in [
        "move trash",
        "move the trash",
        "send trash to trash",
    ]):
        return build_inbox_cleanup_runner_message()

    # Sender-block confirmation: exact phrase "BLOCK N TRASH SENDERS" (case-insensitive)
    if re.match(r"^block\s+\d+\s+trash\s+senders$", msg):
        return build_sender_block_runner_message(text.strip())

    if any(phrase in msg for phrase in [
        "block senders in trash",
        "block all senders in trash",
        "block all the senders in the trash",
        "block trash senders",
        "block the trash senders",
    ]):
        return build_sender_block_plan_message()

    if any(phrase in msg for phrase in [
        "mark reviewed as read",
        "mark safe sorted as read",
        "mark read plan",
        "what can be marked read",
    ]):
        return build_mark_read_plan_message()

    if any(phrase in msg for phrase in [
        "confirm mark read",
        "apply mark read",
    ]):
        return build_mark_read_runner_message(apply=True)

    if any(phrase in msg for phrase in [
        "sort",
        "clean",
        "cleanup",
        "clean up",
        "organize",
        "inbox zero",
        "move junk",
        "not worth keeping",
        "junk to trash",
    ]):
        return sort_plan_message(text)

    return _llm_fallback(text)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Inbox Scout natural language intent router")
    parser.add_argument("message", nargs="+")
    args = parser.parse_args()

    print(handle_natural_message(" ".join(args.message)))


if __name__ == "__main__":
    main()

