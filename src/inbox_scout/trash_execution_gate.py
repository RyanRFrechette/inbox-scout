from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"

LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"
LATEST_TRASH_PLAN = PLANS_DIR / "latest_trash_plan.json"
LATEST_TRASH_CONFIRMATION_PLAN = PLANS_DIR / "latest_trash_confirmation_plan.json"
LATEST_TRASH_EXECUTION_GATE = PLANS_DIR / "latest_trash_execution_gate.json"


TRASH_SAFE_CATEGORIES = {"newsletter", "promotion"}
PROTECTED_CATEGORIES = {
    "bills/receipts",
    "finance",
    "medical",
    "legal",
    "tax",
    "security",
    "client/business",
    "insurance",
    "manual review",
}
MAX_TRASH_RISK = 30


@dataclass
class TrashExecutionGateResult:
    gate_id: str
    created_at: str
    status: str
    requested_command: str
    would_trash_ids: list[str]
    blocked_reasons: list[str]
    gmail_changes_enabled: bool
    trash_execution_enabled: bool
    permanent_delete_enabled: bool
    safety_notes: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_gate_id() -> str:
    return datetime.now(timezone.utc).strftime("trashgate_%Y%m%d_%H%M%S")


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_gate(result: TrashExecutionGateResult) -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_TRASH_EXECUTION_GATE.write_text(
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

    if category in PROTECTED_CATEGORIES:
        reasons.append(f"Item category is protected: {category}.")

    if category not in TRASH_SAFE_CATEGORIES:
        reasons.append(f"Item category is not Trash-safe: {category}.")

    if risk > MAX_TRASH_RISK:
        reasons.append(f"Item risk is too high for Trash: {risk}.")

    if clean(item.get("gmail_action_type")):
        reasons.append("Item already has a Gmail action type locally.")

    if is_true(item.get("gmail_action_taken")):
        reasons.append("Item already has Gmail action taken locally.")

    if reasons:
        return False, reasons

    return True, ["Candidate passed Trash gate validation."]


def evaluate_trash_execution_gate(command: str = "confirm trash") -> TrashExecutionGateResult:
    trash_plan = load_json(LATEST_TRASH_PLAN)
    confirmation_plan = load_json(LATEST_TRASH_CONFIRMATION_PLAN)

    blocked: list[str] = []
    would_trash_ids: list[str] = []

    if not trash_plan:
        blocked.append("No Trash plan exists.")

    if not confirmation_plan:
        blocked.append("No Trash confirmation plan exists.")

    if confirmation_plan and confirmation_plan.get("status") != "awaiting_future_confirmation":
        blocked.append(f"Confirmation plan status is not awaiting_future_confirmation: {confirmation_plan.get('status')}.")

    for source_name, plan in [("Trash plan", trash_plan), ("Trash confirmation plan", confirmation_plan)]:
        if plan and plan.get("gmail_changes_enabled") is True:
            blocked.append(f"{source_name} unexpectedly has Gmail changes enabled.")
        if plan and plan.get("trash_execution_enabled") is True:
            blocked.append(f"{source_name} unexpectedly has Trash execution enabled.")
        if plan and plan.get("permanent_delete_enabled") is True:
            blocked.append(f"{source_name} unexpectedly has permanent delete enabled.")

    candidate_ids = confirmation_plan.get("candidate_ids", []) if isinstance(confirmation_plan, dict) else []

    if not candidate_ids:
        blocked.append("No candidate IDs are available.")

    for queue_id in candidate_ids:
        queue_id = str(queue_id)
        ok, reasons = validate_candidate(queue_id)

        if ok:
            would_trash_ids.append(queue_id)
        else:
            blocked.extend([f"ID {queue_id}: {reason}" for reason in reasons])

    if blocked:
        status = "blocked"
    elif would_trash_ids:
        status = "dry_run_ready_execution_disabled"
    else:
        status = "blocked"

    return TrashExecutionGateResult(
        gate_id=make_gate_id(),
        created_at=now_iso(),
        status=status,
        requested_command=command,
        would_trash_ids=would_trash_ids,
        blocked_reasons=blocked,
        gmail_changes_enabled=False,
        trash_execution_enabled=False,
        permanent_delete_enabled=False,
        safety_notes=[
            "Trash execution gate dry-run only.",
            "No Gmail changes were made.",
            "No emails were moved to Trash.",
            "No emails were permanently deleted.",
            "Permanent delete is disabled.",
            "Real Trash execution remains disabled until a later phase.",
            "Trash means Gmail Trash review folder, not permanent delete.",
        ],
    )


def build_trash_execution_gate_message(command: str = "confirm trash") -> str:
    result = evaluate_trash_execution_gate(command)
    save_gate(result)

    if result.status == "blocked":
        lines = ["I blocked the Trash action for safety.", ""]

        for reason in result.blocked_reasons:
            lines.append(f"- {reason}")

        lines.extend([
            "",
            "I did not move anything to Trash.",
            "I did not permanently delete anything.",
            "I did not touch Gmail.",
        ])

        return "\n".join(lines)

    lines = [
        "Trash safety gate passed.",
        "",
        "If Trash execution were enabled, I would move these to Gmail Trash for review:",
    ]

    for qid in result.would_trash_ids:
        item = queue_item_by_id(qid) or {}
        subject = clean(item.get("subject"))
        category = clean(item.get("category"))
        risk = risk_int(item)
        lines.append(f"- ID {qid}: {subject} | risk {risk} | {category}")

    lines.extend([
        "",
        "But Trash execution is still disabled right now.",
        "",
        "I did not move anything to Trash.",
        "I did not permanently delete anything.",
        "I did not touch Gmail.",
    ])

    return "\n".join(lines)


def main() -> None:
    print(build_trash_execution_gate_message("confirm trash"))


if __name__ == "__main__":
    main()
