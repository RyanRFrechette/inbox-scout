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
LATEST_ARCHIVE_EXECUTION_GATE = PLANS_DIR / "latest_archive_execution_gate.json"
LATEST_ARCHIVE_EXECUTION_RUN = PLANS_DIR / "latest_archive_execution_run.json"
ARCHIVE_EXECUTION_LOG = LOGS_DIR / "archive_execution_runs.jsonl"


@dataclass
class ArchiveExecutionRunResult:
    run_id: str
    created_at: str
    status: str
    mode: str
    requested_ids: list[str]
    archived_ids: list[str]
    blocked_reasons: list[str]
    gmail_changes_enabled: bool
    archive_execution_enabled: bool
    permanent_delete_enabled: bool
    safety_notes: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("archiverun_%Y%m%d_%H%M%S")


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


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def load_queue_items() -> list[dict[str, Any]]:
    data = load_json(LATEST_QUEUE)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("queue_items", [])

    return []


def queue_item_by_id(queue_id: str) -> dict[str, Any] | None:
    for item in load_queue_items():
        qid = clean(item.get("queue_id") or item.get("id"))
        if qid == queue_id:
            return item
    return None


def archive_execution_enabled_in_config() -> bool:
    config = load_json(CONFIG_PATH)
    return is_true(config.get("telegram_archive_execution_enabled"))


def validate_gate() -> tuple[list[str], list[str]]:
    gate = load_json(LATEST_ARCHIVE_EXECUTION_GATE)
    blocked: list[str] = []

    if not gate:
        return [], ["No archive execution gate exists yet. Run confirm archive first."]

    if gate.get("status") != "dry_run_ready_execution_disabled":
        blocked.append(f"Archive gate status is not ready: {gate.get('status')}.")

    if gate.get("gmail_changes_enabled") is True:
        blocked.append("Gate unexpectedly has Gmail changes enabled.")

    if gate.get("archive_execution_enabled") is True:
        blocked.append("Gate unexpectedly has archive execution enabled.")

    if gate.get("permanent_delete_enabled") is True:
        blocked.append("Gate unexpectedly has permanent delete enabled.")

    ids = [str(x) for x in gate.get("would_archive_ids", [])]

    if not ids:
        blocked.append("Gate has no archive IDs.")

    for qid in ids:
        item = queue_item_by_id(qid)
        if not item:
            blocked.append(f"Queue item {qid} no longer exists in latest queue.")
            continue

        if clean(item.get("gmail_action_type")):
            blocked.append(f"Queue item {qid} already has Gmail action type locally.")

        if is_true(item.get("gmail_action_taken")):
            blocked.append(f"Queue item {qid} already has Gmail action taken locally.")

        if is_true(item.get("manual_review")):
            blocked.append(f"Queue item {qid} requires manual review.")

        if clean(item.get("local_decision")).lower() == "protected_review":
            blocked.append(f"Queue item {qid} is protected_review.")

    return ids, blocked


def build_result(
    *,
    status: str,
    mode: str,
    requested_ids: list[str],
    archived_ids: list[str],
    blocked_reasons: list[str],
    archive_execution_enabled: bool,
) -> ArchiveExecutionRunResult:
    return ArchiveExecutionRunResult(
        run_id=make_run_id(),
        created_at=now_iso(),
        status=status,
        mode=mode,
        requested_ids=requested_ids,
        archived_ids=archived_ids,
        blocked_reasons=blocked_reasons,
        gmail_changes_enabled=False,
        archive_execution_enabled=archive_execution_enabled,
        permanent_delete_enabled=False,
        safety_notes=[
            "Archive execution runner guard.",
            "No permanent delete is allowed.",
            "Trash execution is not allowed here.",
            "Mark-read execution is not allowed here.",
        ],
    )


def save_result(result: ArchiveExecutionRunResult) -> None:
    data = asdict(result)
    save_json(LATEST_ARCHIVE_EXECUTION_RUN, data)
    append_jsonl(ARCHIVE_EXECUTION_LOG, data)


def build_message(result: ArchiveExecutionRunResult) -> str:
    if result.status == "dry_run_ready":
        lines = [
            "Archive runner dry-run passed.",
            "",
            "If execution is enabled later, I would archive:",
        ]

        for qid in result.requested_ids:
            item = queue_item_by_id(qid) or {}
            subject = clean(item.get("subject"))
            category = clean(item.get("category"))
            risk = clean(item.get("risk_score") or item.get("risk"))
            lines.append(f"- ID {qid}: {subject} | risk {risk} | {category}")

        lines.extend([
            "",
            "I did not archive anything.",
            "I did not touch Gmail.",
        ])

        return "\n".join(lines)

    if result.status == "blocked_config_disabled":
        return (
            "Archive execution is blocked by config.\n\n"
            "The archive safety gate passed, but real archive execution is still disabled.\n\n"
            "I did not archive anything.\n"
            "I did not touch Gmail."
        )

    lines = [
        "Archive execution runner blocked for safety.",
        "",
    ]

    for reason in result.blocked_reasons:
        lines.append(f"- {reason}")

    lines.extend([
        "",
        "I did not archive anything.",
        "I did not touch Gmail.",
    ])

    return "\n".join(lines)


def run_archive_execution_guard(apply: bool = False) -> ArchiveExecutionRunResult:
    ids, blocked = validate_gate()
    config_enabled = archive_execution_enabled_in_config()

    if blocked:
        result = build_result(
            status="blocked_safety",
            mode="apply" if apply else "dry_run",
            requested_ids=ids,
            archived_ids=[],
            blocked_reasons=blocked,
            archive_execution_enabled=config_enabled,
        )
        save_result(result)
        return result

    if not apply:
        result = build_result(
            status="dry_run_ready",
            mode="dry_run",
            requested_ids=ids,
            archived_ids=[],
            blocked_reasons=[],
            archive_execution_enabled=config_enabled,
        )
        save_result(result)
        return result

    if not config_enabled:
        result = build_result(
            status="blocked_config_disabled",
            mode="apply",
            requested_ids=ids,
            archived_ids=[],
            blocked_reasons=["telegram_archive_execution_enabled is not true in config."],
            archive_execution_enabled=False,
        )
        save_result(result)
        return result

    result = build_result(
        status="blocked_not_implemented_yet",
        mode="apply",
        requested_ids=ids,
        archived_ids=[],
        blocked_reasons=["Real Gmail archive execution is intentionally not implemented in this step."],
        archive_execution_enabled=True,
    )
    save_result(result)
    return result


def build_archive_runner_message(apply: bool = False) -> str:
    result = run_archive_execution_guard(apply=apply)
    return build_message(result) + "\n\nGmail changes: 0"


def main() -> None:
    parser = argparse.ArgumentParser(description="Inbox Scout archive execution runner guard")
    parser.add_argument("--apply", action="store_true", help="Attempt real archive execution if config allows it.")
    args = parser.parse_args()

    print(build_archive_runner_message(apply=args.apply))


if __name__ == "__main__":
    main()
