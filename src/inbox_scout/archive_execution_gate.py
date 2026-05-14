from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"
LATEST_ARCHIVE_PLAN = PLANS_DIR / "latest_archive_plan.json"
LATEST_ARCHIVE_CONFIRMATION_PLAN = PLANS_DIR / "latest_archive_confirmation_plan.json"
LATEST_ARCHIVE_EXECUTION_GATE = PLANS_DIR / "latest_archive_execution_gate.json"


@dataclass
class ArchiveExecutionGateResult:
    gate_id: str
    created_at: str
    status: str
    requested_command: str
    would_archive_ids: list[str]
    blocked_reasons: list[str]
    gmail_changes_enabled: bool
    archive_execution_enabled: bool
    permanent_delete_enabled: bool
    safety_notes: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_gate_id() -> str:
    return datetime.now(timezone.utc).strftime("archivegate_%Y%m%d_%H%M%S")


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_gate(result: ArchiveExecutionGateResult) -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_ARCHIVE_EXECUTION_GATE.write_text(
        json.dumps(asdict(result), indent=2),
        encoding="utf-8",
    )


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def risk_int(item: dict[str, Any]) -> int:
    raw = item.get("risk_score", item.get("risk", 999))
    try:
        return int(raw)
    except Exception:
        return 999


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


def validate_candidate(queue_id: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    item = queue_item_by_id(queue_id)

    if not item:
        return False, [f"Queue item {queue_id} was not found in the latest queue."]

    decision = clean(item.get("local_decision")).lower()
    category = clean(item.get("category")).lower()
    risk = risk_int(item)

    if is_true(item.get("manual_review")):
        reasons.append("Item requires manual review.")

    if decision == "protected_review":
        reasons.append("Item is protected_review.")

    if category not in {"newsletter", "promotion"}:
        reasons.append(f"Item category is not archive-safe: {category}.")

    if risk > 40:
        reasons.append(f"Item risk is too high for archive: {risk}.")

    if clean(item.get("gmail_action_type")):
        reasons.append("Item already has a Gmail action type locally.")

    if is_true(item.get("gmail_action_taken")):
        reasons.append("Item already has Gmail action taken locally.")

    if reasons:
        return False, reasons

    return True, ["Candidate passed archive gate validation."]


def evaluate_archive_execution_gate(command: str = "confirm archive") -> ArchiveExecutionGateResult:
    archive_plan = load_json(LATEST_ARCHIVE_PLAN)
    confirmation_plan = load_json(LATEST_ARCHIVE_CONFIRMATION_PLAN)

    blocked: list[str] = []
    would_archive_ids: list[str] = []

    if not archive_plan:
        blocked.append("No archive plan exists.")

    if not confirmation_plan:
        blocked.append("No archive confirmation plan exists.")

    if confirmation_plan and confirmation_plan.get("status") != "awaiting_future_confirmation":
        blocked.append(f"Confirmation plan status is not awaiting_future_confirmation: {confirmation_plan.get('status')}.")

    if archive_plan and archive_plan.get("gmail_changes_enabled") is True:
        blocked.append("Archive plan unexpectedly has Gmail changes enabled.")

    if confirmation_plan and confirmation_plan.get("gmail_changes_enabled") is True:
        blocked.append("Confirmation plan unexpectedly has Gmail changes enabled.")

    if confirmation_plan and confirmation_plan.get("archive_execution_enabled") is True:
        blocked.append("Confirmation plan unexpectedly has archive execution enabled.")

    candidate_ids = confirmation_plan.get("candidate_ids", []) if isinstance(confirmation_plan, dict) else []

    if not candidate_ids:
        blocked.append("No candidate IDs are available.")

    for queue_id in candidate_ids:
        queue_id = str(queue_id)
        ok, reasons = validate_candidate(queue_id)

        if ok:
            would_archive_ids.append(queue_id)
        else:
            blocked.extend([f"ID {queue_id}: {reason}" for reason in reasons])

    if blocked:
        status = "blocked"
    elif would_archive_ids:
        status = "dry_run_ready_execution_disabled"
    else:
        status = "blocked"

    return ArchiveExecutionGateResult(
        gate_id=make_gate_id(),
        created_at=now_iso(),
        status=status,
        requested_command=command,
        would_archive_ids=would_archive_ids,
        blocked_reasons=blocked,
        gmail_changes_enabled=False,
        archive_execution_enabled=False,
        permanent_delete_enabled=False,
        safety_notes=[
            "Archive execution gate dry-run only.",
            "No Gmail changes were made.",
            "No emails were archived.",
            "No emails were moved to Trash.",
            "No emails were marked read.",
            "Permanent delete is disabled.",
            "Real archive execution remains disabled until a later phase.",
        ],
    )


def build_archive_execution_gate_message(command: str = "confirm archive") -> str:
    result = evaluate_archive_execution_gate(command)
    save_gate(result)

    if result.status == "blocked":
        lines = [
            "I blocked the archive action for safety.",
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

    lines = [
        "Archive safety gate passed.",
        "",
        "If archive execution were enabled, I would archive:",
    ]

    for qid in result.would_archive_ids:
        item = queue_item_by_id(qid) or {}
        subject = clean(item.get("subject"))
        category = clean(item.get("category"))
        risk = risk_int(item)
        lines.append(f"- ID {qid}: {subject} | risk {risk} | {category}")

    lines.extend([
        "",
        "But archive execution is still disabled right now.",
        "",
        "I did not archive anything.",
        "I did not move anything to Trash.",
        "I did not mark anything read.",
        "I did not delete anything.",
    ])

    return "\n".join(lines)


def main() -> None:
    print(build_archive_execution_gate_message("confirm archive"))


if __name__ == "__main__":
    main()
