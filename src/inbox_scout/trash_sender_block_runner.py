from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inbox_scout.trash_sender_block_plan import LATEST_SENDER_BLOCK_PLAN, PLAN_MAX_AGE_MINUTES


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = PROJECT_ROOT / "data" / "logs"
SENDER_BLOCK_LOG = LOGS_DIR / "sender_block_runs.jsonl"

# Gmail Settings API requires gmail.settings.basic scope — NOT included in gmail.modify.
# Until the user re-authorizes with this scope, filter creation is blocked here.
REQUIRED_SCOPE = "https://www.googleapis.com/auth/gmail.settings.basic"

FILTER_LABEL_IDS_ADD = ["TRASH"]
FILTER_LABEL_IDS_REMOVE = ["INBOX", "UNREAD"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def append_jsonl(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")


def get_settings_service():
    try:
        from inbox_scout.gmail_auth import get_gmail_service
        try:
            return get_gmail_service(mode="modify")
        except TypeError:
            return get_gmail_service("modify")
    except Exception as e:
        raise RuntimeError("Could not load Gmail service.") from e


def scope_is_available(service) -> bool:
    """Test if gmail.settings.basic is usable by probing the filters.list endpoint."""
    try:
        service.users().settings().filters().list(userId="me").execute()
        return True
    except Exception as exc:
        msg = str(exc).lower()
        return "insufficient" not in msg and "403" not in msg and "scope" not in msg


def load_and_validate_plan(confirmation: str) -> tuple[list[str], list[str]]:
    plan = load_json(LATEST_SENDER_BLOCK_PLAN)
    errors: list[str] = []

    if not plan:
        return [], ["No sender block plan found. Say 'block senders in trash' first."]

    try:
        created_at = datetime.fromisoformat(str(plan.get("created_at", "")))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - created_at).total_seconds() / 60
        if age > PLAN_MAX_AGE_MINUTES:
            return [], [
                f"Sender block plan expired ({age:.0f} min old). "
                "Say 'block senders in trash' to rebuild it."
            ]
    except Exception:
        return [], ["Sender block plan has an invalid timestamp."]

    if plan.get("gmail_changes_enabled") is True:
        errors.append("Plan unexpectedly has Gmail changes enabled. Blocked.")

    if plan.get("permanent_delete_enabled") is True:
        errors.append("Plan has permanent delete enabled. Blocked.")

    senders = plan.get("senders", [])
    if not senders:
        return [], ["No senders in plan. Rebuild the plan first."]

    expected_phrase = plan.get("confirmation_phrase", "")
    if confirmation.strip().upper() != expected_phrase.strip().upper():
        return [], [
            f"Wrong confirmation phrase. Expected exactly:\n  {expected_phrase}\n\nGmail not touched."
        ]

    if len(senders) != plan.get("sender_count", -1):
        return [], [
            "Sender count changed since the plan was built. "
            "Say 'block senders in trash' to rebuild the plan."
        ]

    if errors:
        return [], errors

    return senders, []


def is_scope_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "insufficient" in msg or ("403" in msg and "scope" in msg)


def create_filter_for_sender(service, sender: str) -> tuple[bool, str]:
    body = {
        "criteria": {"from": sender},
        "action": {
            "addLabelIds": FILTER_LABEL_IDS_ADD,
            "removeLabelIds": FILTER_LABEL_IDS_REMOVE,
        },
    }
    try:
        service.users().settings().filters().create(userId="me", body=body).execute()
        return True, ""
    except Exception as exc:
        if is_scope_error(exc):
            return False, f"SCOPE_ERROR: {REQUIRED_SCOPE} not provisioned"
        return False, str(exc)


def build_sender_block_runner_message(confirmation: str) -> str:
    senders, errors = load_and_validate_plan(confirmation)

    if errors:
        return errors[0] + "\n\nGmail not touched."

    # Check scope before touching Gmail
    try:
        service = get_settings_service()
    except Exception as exc:
        return f"Could not connect to Gmail: {exc}\n\nGmail not touched."

    if not scope_is_available(service):
        return (
            "Gmail filter creation requires an additional OAuth scope:\n"
            f"  {REQUIRED_SCOPE}\n\n"
            "This scope is not yet provisioned.\n\n"
            "To enable it: re-run Gmail OAuth authorization with the settings scope added.\n\n"
            "Gmail not touched. No senders were blocked."
        )

    run_id = datetime.now(timezone.utc).strftime("blockrun_%Y%m%d_%H%M%S")
    blocked: list[str] = []
    failed: list[str] = []

    for sender in senders:
        ok, err = create_filter_for_sender(service, sender)
        if ok:
            blocked.append(sender)
            append_jsonl(SENDER_BLOCK_LOG, {
                "run_id": run_id,
                "timestamp": now_iso(),
                "event": "filter_created",
                "sender": sender,
                "gmail_changed": True,
                "permanent_delete": False,
            })
        else:
            failed.append(f"{sender}: {err}")
            append_jsonl(SENDER_BLOCK_LOG, {
                "run_id": run_id,
                "timestamp": now_iso(),
                "event": "filter_failed",
                "sender": sender,
                "gmail_changed": False,
                "error": err,
            })

    # Check if all failures are scope errors — surface a clean message
    scope_failures = [f for f in failed if "SCOPE_ERROR" in f]
    if scope_failures and not blocked:
        return (
            "Gmail filter creation requires an additional OAuth scope:\n"
            f"  {REQUIRED_SCOPE}\n\n"
            "This scope is not yet provisioned in your Gmail token.\n\n"
            "To enable it: re-run Gmail OAuth authorization with the settings scope added.\n\n"
            "Gmail not touched. No senders were blocked."
        )

    lines = []
    if blocked:
        lines.append(
            f"Blocked {len(blocked)} sender(s). "
            "Future emails from these senders should go to Trash."
        )
        lines.append("Nothing was permanently deleted.")
        lines.append("")
        lines.append("Blocked:")
        for s in blocked:
            lines.append(f"  - {s}")

    if failed:
        other_failures = [f for f in failed if "SCOPE_ERROR" not in f]
        if other_failures:
            lines.append("")
            lines.append(f"Failed ({len(other_failures)}):")
            for f_msg in other_failures:
                lines.append(f"  - {f_msg}")

    if not blocked and not failed:
        lines.append("No senders processed. Gmail not touched.")

    return "\n".join(lines)
