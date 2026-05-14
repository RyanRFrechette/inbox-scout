from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass


DEFAULT_SORT_LIMIT = 25
MAX_NORMAL_LIMIT = 100


@dataclass
class SortCommand:
    intent: str
    limit: int | None
    sort_all: bool
    target: str
    dry_run: bool
    trash_review_mode: bool
    allow_trash_plan: bool
    allow_permanent_delete: bool
    original_message: str
    confidence: int
    reason: str


def has_any(msg: str, phrases: list[str]) -> bool:
    return any(phrase in msg for phrase in phrases)


def parse_sort_command(message: str) -> SortCommand:
    msg = message.lower().strip()

    permanent_delete_phrases = [
        "empty my trash",
        "delete everything in trash",
        "delete everything in the trash",
        "clear the trash",
        "clear my trash",
        "clear the trash folder",
        "wipe the trash",
        "delete all trashed emails",
        "permanently delete",
    ]

    if has_any(msg, permanent_delete_phrases):
        return SortCommand(
            intent="permanent_delete_plan_only",
            limit=None,
            sort_all=False,
            target="trash",
            dry_run=True,
            trash_review_mode=False,
            allow_trash_plan=False,
            allow_permanent_delete=False,
            original_message=message,
            confidence=80,
            reason="Permanent delete language detected. This is Phase 14 only and remains disabled.",
        )

    sort_words = [
        "sort",
        "clean",
        "clean up",
        "cleanup",
        "organize",
        "inbox zero",
        "clear my inbox",
        "process",
    ]

    inbox_words = [
        "email",
        "emails",
        "inbox",
        "unread",
        "gmail",
    ]

    trash_review_phrases = [
        "move junk to trash",
        "junk to trash",
        "trash so i can review",
        "trash for review",
        "move the junk",
        "move junk",
        "not worth keeping",
    ]

    has_sort_intent = has_any(msg, sort_words)
    has_inbox_context = has_any(msg, inbox_words)
    has_trash_review_intent = has_any(msg, trash_review_phrases)

    if not has_sort_intent and not has_inbox_context and not has_trash_review_intent:
        return SortCommand(
            intent="unknown",
            limit=None,
            sort_all=False,
            target="unknown",
            dry_run=True,
            trash_review_mode=True,
            allow_trash_plan=False,
            allow_permanent_delete=False,
            original_message=message,
            confidence=20,
            reason="Could not confidently identify this as an inbox sorting command.",
        )

    sort_all = bool(re.search(r"\b(all|everything|entire inbox|whole inbox)\b", msg))

    number_match = re.search(r"\b(\d{1,5})\b", msg)

    if sort_all:
        limit = None
    elif number_match:
        limit = int(number_match.group(1))
    else:
        limit = DEFAULT_SORT_LIMIT

    if limit is not None and limit < 1:
        limit = DEFAULT_SORT_LIMIT

    allow_trash_plan = has_trash_review_intent

    if limit is not None and limit > MAX_NORMAL_LIMIT:
        reason = (
            f"Requested {limit} emails. This is above the normal safety limit, "
            "so it should stay dry-run and require extra confirmation."
        )
    elif sort_all:
        reason = "User requested sort all. This must stay dry-run first and require extra confirmation."
    elif allow_trash_plan:
        reason = "Parsed as a safe trash-review planning request. No Gmail actions are enabled."
    else:
        reason = "Parsed a safe inbox sorting request."

    return SortCommand(
        intent="sort",
        limit=limit,
        sort_all=sort_all,
        target="unread_inbox",
        dry_run=True,
        trash_review_mode=True,
        allow_trash_plan=allow_trash_plan,
        allow_permanent_delete=False,
        original_message=message,
        confidence=90 if has_sort_intent else 80,
        reason=reason,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inbox Scout natural sort command parser")
    parser.add_argument("message", nargs="+", help='Example: "sort 25 emails"')
    args = parser.parse_args()

    command = parse_sort_command(" ".join(args.message))
    print(json.dumps(asdict(command), indent=2))


if __name__ == "__main__":
    main()
