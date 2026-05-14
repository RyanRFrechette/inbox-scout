from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "telegram_config.json"
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LOGS_DIR = PROJECT_ROOT / "data" / "logs"

LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"
LATEST_TRASH_EXECUTION_GATE = PLANS_DIR / "latest_trash_execution_gate.json"
LATEST_TRASH_EXECUTION_RUN = PLANS_DIR / "latest_trash_execution_run.json"
TRASH_EXECUTION_LOG = LOGS_DIR / "trash_execution_runs.jsonl"

TRASH_SAFE_CATEGORIES = {"newsletter", "promotion"}
MAX_TRASH_RISK = 30
MAX_TRASH_BATCH_SIZE = 25

PROTECTED_CATEGORIES = {
    "medical",
    "health",
    "finance",
    "financial",
    "banking",
    "legal",
    "tax",
    "security",
    "bill",
    "bills",
    "receipt",
    "receipts",
    "insurance",
    "client",
    "business",
    "work",
    "job",
    "account",
}

PROTECTED_TEXT_TERMS = {
    "doctor",
    "hospital",
    "clinic",
    "medical",
    "patient",
    "appointment",
    "invoice",
    "bill",
    "receipt",
    "payment",
    "bank",
    "credit",
    "debit",
    "loan",
    "mortgage",
    "insurance",
    "irs",
    "tax",
    "legal",
    "attorney",
    "lawyer",
    "security alert",
    "password",
    "verification",
    "2fa",
    "two-factor",
    "login",
    "account access",
}


@dataclass
class TrashExecutionRunResult:
    run_id: str
    created_at: str
    status: str
    mode: str
    requested_ids: list[str]
    trashed_ids: list[str]
    blocked_reasons: list[str]
    gmail_changes_enabled: bool
    trash_execution_enabled: bool
    permanent_delete_enabled: bool
    safety_notes: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("trashrun_%Y%m%d_%H%M%S")


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def append_jsonl(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def norm(value: Any) -> str:
    return clean(value).lower()


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def parse_int(value: Any, default: int = 999) -> int:
    try:
        return int(value)
    except Exception:
        return default


def load_queue_document() -> tuple[Any, list[dict[str, Any]]]:
    data = load_json(LATEST_QUEUE)

    if isinstance(data, list):
        return data, data

    if isinstance(data, dict):
        items = data.get("queue_items", [])
        if isinstance(items, list):
            return data, items

    return data, []


def save_queue_document(original: Any, items: list[dict[str, Any]]) -> None:
    if isinstance(original, list):
        save_json(LATEST_QUEUE, items)
        return

    if isinstance(original, dict):
        original["queue_items"] = items
        save_json(LATEST_QUEUE, original)
        return

    save_json(LATEST_QUEUE, {"queue_items": items})


def get_queue_id(item: dict[str, Any]) -> str:
    return clean(item.get("queue_id") or item.get("id"))


def get_message_id(item: dict[str, Any]) -> str:
    return clean(
        item.get("message_id")
        or item.get("gmail_message_id")
        or item.get("gmail_id")
    )


def get_subject(item: dict[str, Any]) -> str:
    return clean(item.get("subject") or "(no subject)")


def get_sender(item: dict[str, Any]) -> str:
    return clean(
        item.get("from")
        or item.get("sender")
        or item.get("from_email")
        or item.get("sender_email")
        or "unknown"
    )


def get_category(item: dict[str, Any]) -> str:
    return clean(item.get("category") or item.get("final_category") or item.get("label") or "unknown")


def get_risk(item: dict[str, Any]) -> int:
    return parse_int(item.get("risk_score", item.get("risk", 999)), 999)


def queue_item_by_id(items: list[dict[str, Any]], queue_id: str) -> dict[str, Any] | None:
    for item in items:
        if get_queue_id(item) == queue_id:
            return item
    return None


def trash_execution_enabled_in_config() -> bool:
    config = load_json(CONFIG_PATH)
    return is_true(config.get("telegram_trash_execution_enabled"))


def has_protected_text(item: dict[str, Any]) -> bool:
    combined = " ".join(
        [
            norm(get_category(item)),
            norm(get_sender(item)),
            norm(get_subject(item)),
            norm(item.get("snippet")),
            norm(item.get("reason")),
        ]
    )
    return any(term in combined for term in PROTECTED_TEXT_TERMS)


def validate_gate(items: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    gate = load_json(LATEST_TRASH_EXECUTION_GATE)
    blocked: list[str] = []

    if not gate:
        return [], ["No Trash execution gate exists yet. Run confirm trash first."]

    if gate.get("status") != "dry_run_ready_execution_disabled":
        blocked.append(f"Trash gate status is not ready: {gate.get('status')}.")

    if gate.get("gmail_changes_enabled") is True:
        blocked.append("Gate unexpectedly has Gmail changes enabled.")

    if gate.get("trash_execution_enabled") is True:
        blocked.append("Gate unexpectedly has Trash execution enabled.")

    if gate.get("permanent_delete_enabled") is True:
        blocked.append("Gate unexpectedly has permanent delete enabled.")

    ids = [str(x) for x in gate.get("would_trash_ids", [])]

    if not ids:
        blocked.append("Gate has no Trash IDs.")

    if len(ids) > MAX_TRASH_BATCH_SIZE:
        blocked.append(
            f"Trash batch is too large for Phase 13T: {len(ids)} IDs. "
            f"Max allowed: {MAX_TRASH_BATCH_SIZE}."
        )

    for qid in ids:
        item = queue_item_by_id(items, qid)

        if not item:
            blocked.append(f"Queue item {qid} no longer exists in latest queue.")
            continue

        category = norm(get_category(item))
        risk = get_risk(item)
        message_id = get_message_id(item)

        if not message_id:
            blocked.append(f"Queue item {qid} is missing Gmail message_id.")

        if clean(item.get("gmail_action_type")):
            blocked.append(f"Queue item {qid} already has Gmail action type locally.")

        if is_true(item.get("gmail_action_taken")):
            blocked.append(f"Queue item {qid} already has Gmail action taken locally.")

        if is_true(item.get("gmail_trashed")):
            blocked.append(f"Queue item {qid} is already marked trashed locally.")

        if is_true(item.get("gmail_archived")):
            blocked.append(f"Queue item {qid} is already marked archived locally.")

        if is_true(item.get("manual_review")) or is_true(item.get("manual_review_required")):
            blocked.append(f"Queue item {qid} requires manual review.")

        if clean(item.get("local_decision")).lower() == "protected_review":
            blocked.append(f"Queue item {qid} is protected_review.")

        if category in PROTECTED_CATEGORIES:
            blocked.append(f"Queue item {qid} has protected category: {get_category(item)}.")

        if category not in TRASH_SAFE_CATEGORIES:
            blocked.append(f"Queue item {qid} category is not Trash-safe: {get_category(item)}.")

        if risk > MAX_TRASH_RISK:
            blocked.append(f"Queue item {qid} risk is too high for Trash: {risk}.")

        if has_protected_text(item):
            blocked.append(f"Queue item {qid} has protected text in sender/subject/snippet.")

    return ids, blocked


def get_modify_service():
    try:
        from inbox_scout.gmail_auth import get_gmail_service

        try:
            return get_gmail_service(mode="modify")
        except TypeError:
            return get_gmail_service("modify")
    except Exception as e:
        raise RuntimeError(
            "Could not load Gmail modify service from inbox_scout.gmail_auth. "
            "Check that Gmail modify auth still works."
        ) from e


def build_result(
    *,
    status: str,
    mode: str,
    requested_ids: list[str],
    trashed_ids: list[str],
    blocked_reasons: list[str],
    trash_execution_enabled: bool,
    gmail_changes_enabled: bool = False,
) -> TrashExecutionRunResult:
    return TrashExecutionRunResult(
        run_id=make_run_id(),
        created_at=now_iso(),
        status=status,
        mode=mode,
        requested_ids=requested_ids,
        trashed_ids=trashed_ids,
        blocked_reasons=blocked_reasons,
        gmail_changes_enabled=gmail_changes_enabled,
        trash_execution_enabled=trash_execution_enabled,
        permanent_delete_enabled=False,
        safety_notes=[
            "Phase 13T guarded Trash execution.",
            "Only IDs from latest_trash_execution_gate.would_trash_ids are eligible.",
            "No permanent delete is allowed.",
            "Archive execution is not allowed here.",
            "Mark-read execution is not allowed here.",
            "Trash means Gmail Trash review folder, not permanent delete.",
        ],
    )


def log_execution_event(event: str, run_id: str, item: dict[str, Any], gmail_changed: bool, reason: str = "") -> None:
    append_jsonl(
        TRASH_EXECUTION_LOG,
        {
            "event": event,
            "run_id": run_id,
            "timestamp": now_iso(),
            "queue_id": get_queue_id(item),
            "message_id": get_message_id(item),
            "sender": get_sender(item),
            "subject": get_subject(item),
            "category": get_category(item),
            "risk": get_risk(item),
            "gmail_changed": gmail_changed,
            "reason": reason,
            "permanent_delete": False,
            "archive": False,
            "mark_read": False,
        },
    )


def save_result(result: TrashExecutionRunResult) -> None:
    data = asdict(result)
    save_json(LATEST_TRASH_EXECUTION_RUN, data)
    append_jsonl(TRASH_EXECUTION_LOG, data)


def execute_trash(ids: list[str], original_queue: Any, items: list[dict[str, Any]], run_id: str) -> tuple[list[str], list[str]]:
    service = get_modify_service()

    trashed_ids: list[str] = []
    errors: list[str] = []

    for qid in ids:
        item = queue_item_by_id(items, qid)

        if not item:
            errors.append(f"Queue item {qid} disappeared before execution.")
            continue

        message_id = get_message_id(item)

        if not message_id:
            errors.append(f"Queue item {qid} is missing Gmail message_id.")
            continue

        log_execution_event(
            event="before_gmail_trash",
            run_id=run_id,
            item=item,
            gmail_changed=False,
            reason="About to move this Gmail message to Trash review folder.",
        )

        try:
            service.users().messages().trash(userId="me", id=message_id).execute()

            trash_time = now_iso()

            item["gmail_trashed"] = True
            item["gmail_action_taken"] = True
            item["gmail_action_type"] = "trashed"
            item["gmail_trashed_at"] = trash_time
            item["gmail_trash_review_folder"] = True

            trashed_ids.append(qid)

            log_execution_event(
                event="after_gmail_trash",
                run_id=run_id,
                item=item,
                gmail_changed=True,
                reason="Moved to Gmail Trash for manual review. Not permanently deleted.",
            )

        except Exception as e:
            error = f"Queue item {qid} Trash failed: {e}"
            errors.append(error)
            log_execution_event(
                event="gmail_trash_error",
                run_id=run_id,
                item=item,
                gmail_changed=False,
                reason=error,
            )

    if trashed_ids:
        save_queue_document(original_queue, items)

    return trashed_ids, errors


def build_message(result: TrashExecutionRunResult) -> str:
    _, items = load_queue_document()

    if result.status == "dry_run_ready":
        lines = [
            "Trash runner dry-run passed.",
            "",
            "If execution is enabled later, I would move these to Gmail Trash for review:",
        ]

        for qid in result.requested_ids:
            item = queue_item_by_id(items, qid) or {}
            subject = get_subject(item)
            category = get_category(item)
            risk = get_risk(item)
            lines.append(f"- ID {qid}: {subject} | risk {risk} | {category}")

        lines.extend([
            "",
            "I did not move anything to Trash.",
            "I did not permanently delete anything.",
            "I did not touch Gmail.",
        ])

        return "\n".join(lines)

    if result.status == "blocked_config_disabled":
        return (
            "Trash execution is blocked by config.\n\n"
            "The Trash safety gate passed, but real Trash execution is still disabled.\n\n"
            "I did not move anything to Trash.\n"
            "I did not permanently delete anything.\n"
            "I did not touch Gmail."
        )

    if result.status in {"applied", "partial_error"}:
        lines = [
            "Trash execution complete.",
            "",
            "Moved to Gmail Trash for your manual review:",
        ]

        for qid in result.trashed_ids:
            item = queue_item_by_id(items, qid) or {}
            lines.append(f"- ID {qid}: {get_subject(item)}")

        if result.blocked_reasons:
            lines.extend(["", "Warnings/errors:"])
            for reason in result.blocked_reasons:
                lines.append(f"- {reason}")

        lines.extend([
            "",
            "Permanent delete: 0",
            "Archived: 0",
            "Marked read: 0",
        ])

        return "\n".join(lines)

    lines = [
        "Trash execution runner blocked for safety.",
        "",
    ]

    for reason in result.blocked_reasons:
        lines.append(f"- {reason}")

    lines.extend([
        "",
        "I did not move anything to Trash.",
        "I did not permanently delete anything.",
        "I did not touch Gmail.",
    ])

    return "\n".join(lines)


def run_trash_execution_guard(apply: bool = False) -> TrashExecutionRunResult:
    original_queue, items = load_queue_document()
    ids, blocked = validate_gate(items)
    config_enabled = trash_execution_enabled_in_config()

    if blocked:
        result = build_result(
            status="blocked_safety",
            mode="apply" if apply else "dry_run",
            requested_ids=ids,
            trashed_ids=[],
            blocked_reasons=blocked,
            trash_execution_enabled=config_enabled,
        )
        save_result(result)
        return result

    if not apply:
        result = build_result(
            status="dry_run_ready",
            mode="dry_run",
            requested_ids=ids,
            trashed_ids=[],
            blocked_reasons=[],
            trash_execution_enabled=config_enabled,
        )
        save_result(result)
        return result

    if not config_enabled:
        result = build_result(
            status="blocked_config_disabled",
            mode="apply",
            requested_ids=ids,
            trashed_ids=[],
            blocked_reasons=["telegram_trash_execution_enabled is not true in config."],
            trash_execution_enabled=False,
        )
        save_result(result)
        return result

    run_id = make_run_id()

    append_jsonl(
        TRASH_EXECUTION_LOG,
        {
            "event": "trash_execution_apply_start",
            "run_id": run_id,
            "timestamp": now_iso(),
            "requested_ids": ids,
            "gmail_changes_enabled": True,
            "trash_execution_enabled": True,
            "permanent_delete_enabled": False,
        },
    )

    trashed_ids, errors = execute_trash(ids, original_queue, items, run_id)

    status = "applied" if trashed_ids and not errors else "partial_error"

    result = TrashExecutionRunResult(
        run_id=run_id,
        created_at=now_iso(),
        status=status,
        mode="apply",
        requested_ids=ids,
        trashed_ids=trashed_ids,
        blocked_reasons=errors,
        gmail_changes_enabled=bool(trashed_ids),
        trash_execution_enabled=True,
        permanent_delete_enabled=False,
        safety_notes=[
            "Phase 13T guarded Trash execution completed.",
            "Messages were moved only to Gmail Trash for manual review.",
            "No permanent delete was performed.",
            "No archive action was performed.",
            "No mark-read action was performed.",
        ],
    )

    save_result(result)
    return result


def build_trash_runner_message(apply: bool = False) -> str:
    result = run_trash_execution_guard(apply=apply)
    return build_message(result) + f"\n\nGmail changes: {len(result.trashed_ids)}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Inbox Scout Trash execution runner guard")
    parser.add_argument("--apply", action="store_true", help="Attempt real Trash execution if config allows it.")
    args = parser.parse_args()

    print(build_trash_runner_message(apply=args.apply))


if __name__ == "__main__":
    main()
