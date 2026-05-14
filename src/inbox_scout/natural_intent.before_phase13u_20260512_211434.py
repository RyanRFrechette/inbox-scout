from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inbox_scout.telegram_status import build_status_message
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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"


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


def sort_plan_message(text: str) -> str:
    plan = build_scan_queue_plan(text)
    save_plan(plan)

    if plan.workflow_mode == "blocked_large_scan":
        return (
            "I understand you want me to sort everything.\n\n"
            "I am blocking that for now because full-inbox sorting needs extra safety checks first.\n\n"
            "Start with a small test like: sort 5 emails.\n\n"
            "I did not scan Gmail. I did not touch Gmail."
        )

    if plan.workflow_mode == "blocked_phase_14_only":
        return (
            "That sounds like a permanent delete request.\n\n"
            "Permanent delete is a Phase 14 nuclear feature and is disabled right now.\n\n"
            "I did not scan Gmail. I did not delete anything."
        )

    if plan.workflow_mode != "commands_planned":
        return (
            "I am not sure how to safely turn that into an inbox sorting plan yet.\n\n"
            "Try saying: sort 5 emails.\n\n"
            "I did not touch Gmail."
        )

    return (
        "I can prepare a safe Inbox Scout scan.\n\n"
        f"I would scan {plan.requested_limit} unread inbox emails and build a review queue.\n\n"
        "Safety check:\n"
        "- I will only read Gmail.\n"
        "- I will not archive anything.\n"
        "- I will not move anything to Trash.\n"
        "- I will not mark anything read.\n"
        "- I will not reply or delete anything.\n\n"
        "For now, I only prepared the plan.\n"
        "I did not scan Gmail. I did not touch Gmail.\n\n"
        "Want me to run the safe read-only scan now?\n"
        "Reply yes to continue, or cancel to stop."
    )


def queue_summary() -> str:
    items = load_queue_items()

    if not items:
        return "I do not see a current Inbox Scout queue yet. I did not touch Gmail."

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
        "Here is the current batch:",
        "",
        f"Total emails: {len(items)}",
        f"Protected: {len(protected)}",
        f"Already handled: {len(handled)}",
        f"Needs review: {len(pending)}",
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
    lines.append("I did not touch Gmail.")
    return "\n".join(lines)


def next_review_item() -> str:
    items = load_queue_items()

    for item in items:
        decision = clean(item.get("local_decision")).lower()
        if decision == "pending_review":
            return (
                "This is the next email that needs review:\n\n"
                f"ID: {clean(item.get('queue_id'))}\n"
                f"Category: {clean(item.get('category'))}\n"
                f"Risk: {clean(item.get('risk_score') or item.get('risk'))}\n"
                f"From: {clean(item.get('from'))}\n"
                f"Subject: {clean(item.get('subject'))}\n\n"
                "I did not touch Gmail."
            )

    return "Nothing needs review in the current batch. I did not touch Gmail."


def help_message() -> str:
    return (
        "You can talk to Inbox Scout naturally.\n\n"
        "Try saying things like:\n"
        "- sort 5 emails\n"
        "- sort 25 emails\n"
        "- sort all\n"
        "- clean up my inbox\n"
        "- move junk to trash so I can review it\n"
        "- show me the queue\n"
        "- what needs my attention?\n"
        "- how many emails are in my inbox?\n\n"
        "Right now I can understand you naturally, but I still will not change Gmail without approval."
    )


def handle_natural_message(text: str) -> str:
    msg = text.lower().strip()

    if msg in {"yes", "y", "approve", "go ahead", "run it", "do it", "start scan", "run the scan", "proceed"}:
        return build_scan_approval_response(text)

    if msg in {"cancel", "stop", "never mind", "nevermind"}:
        return "Cancelled. I did not scan Gmail. I did not touch Gmail."

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
    ]):
        return build_inbox_count_message()

    if any(word in msg for word in ["help", "commands", "what can you do"]):
        return help_message()

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

    if any(phrase in msg for phrase in ["queue", "show emails", "show my emails", "latest batch"]):
        return queue_summary()

    if any(phrase in msg for phrase in ["next", "next review", "needs review", "what needs my attention"]):
        return next_review_item()

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

    return (
        "I understand this is about Inbox Scout, but I am not sure what you want me to do yet.\n\n"
        + help_message()
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Inbox Scout natural language intent router")
    parser.add_argument("message", nargs="+")
    args = parser.parse_args()

    print(handle_natural_message(" ".join(args.message)))


if __name__ == "__main__":
    main()
