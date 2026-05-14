from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LATEST_QUEUE = PROJECT_ROOT / "data" / "review_queue" / "latest_queue.json"
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_TRASH_PLAN = PLANS_DIR / "latest_trash_plan.json"


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


TRASH_SAFE_CATEGORIES = {
    "newsletter",
    "promotion",
}


MAX_TRASH_RISK = 30


@dataclass
class TrashCandidate:
    queue_id: str
    category: str
    risk: int
    sender: str
    subject: str
    reason: str


@dataclass
class TrashPlan:
    plan_id: str
    created_at: str
    status: str
    candidate_count: int
    candidates: list[TrashCandidate]
    protected_count: int
    skipped_count: int
    gmail_changes_enabled: bool
    trash_execution_enabled: bool
    permanent_delete_enabled: bool
    safety_notes: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_plan_id() -> str:
    return datetime.now(timezone.utc).strftime("trashplan_%Y%m%d_%H%M%S")


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


def load_items() -> list[dict[str, Any]]:
    if not LATEST_QUEUE.exists():
        return []

    data = json.loads(LATEST_QUEUE.read_text(encoding="utf-8-sig"))

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("queue_items", [])

    return []


def is_protected_item(item: dict[str, Any]) -> bool:
    decision = clean(item.get("local_decision")).lower()
    category = clean(item.get("category")).lower()
    risk = risk_int(item)

    if is_true(item.get("manual_review")):
        return True

    if decision == "protected_review":
        return True

    if category in PROTECTED_CATEGORIES:
        return True

    if risk >= 70:
        return True

    return False


def already_handled(item: dict[str, Any]) -> bool:
    return bool(clean(item.get("gmail_action_type"))) or is_true(item.get("gmail_action_taken"))


def is_safe_trash_candidate(item: dict[str, Any]) -> tuple[bool, str]:
    decision = clean(item.get("local_decision")).lower()
    category = clean(item.get("category")).lower()
    risk = risk_int(item)

    if already_handled(item):
        return False, "Already handled locally."

    if is_protected_item(item):
        return False, "Protected/manual-review/high-risk item."

    if category not in TRASH_SAFE_CATEGORIES:
        return False, "Only newsletter/promotion clutter can be planned for Trash right now."

    if risk > MAX_TRASH_RISK:
        return False, f"Risk score {risk} is above safe Trash threshold {MAX_TRASH_RISK}."

    if decision not in {"pending_review", "possible_archive_later", "possible_trash_later"}:
        return False, "Local decision is not eligible for Trash planning."

    return True, "Low-risk clutter. Safe Trash-review candidate after approval."


def build_trash_plan() -> TrashPlan:
    items = load_items()

    candidates: list[TrashCandidate] = []
    protected_count = 0
    skipped_count = 0

    for item in items:
        if is_protected_item(item):
            protected_count += 1

        ok, reason = is_safe_trash_candidate(item)

        if not ok:
            skipped_count += 1
            continue

        candidates.append(
            TrashCandidate(
                queue_id=clean(item.get("queue_id") or item.get("id") or "?"),
                category=clean(item.get("category")),
                risk=risk_int(item),
                sender=clean(item.get("from") or item.get("sender")),
                subject=clean(item.get("subject")),
                reason=reason,
            )
        )

    status = "candidates_found" if candidates else "no_candidates"

    return TrashPlan(
        plan_id=make_plan_id(),
        created_at=now_iso(),
        status=status,
        candidate_count=len(candidates),
        candidates=candidates,
        protected_count=protected_count,
        skipped_count=skipped_count,
        gmail_changes_enabled=False,
        trash_execution_enabled=False,
        permanent_delete_enabled=False,
        safety_notes=[
            "Trash plan only.",
            "No Gmail changes were made.",
            "No emails were moved to Trash.",
            "No emails were permanently deleted.",
            "Protected/manual-review/high-risk emails are excluded.",
            "Trash means Gmail Trash review folder, not permanent delete.",
        ],
    )


def save_plan(plan: TrashPlan) -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_TRASH_PLAN.write_text(json.dumps(asdict(plan), indent=2), encoding="utf-8")


def build_trash_plan_message() -> str:
    plan = build_trash_plan()
    save_plan(plan)

    if plan.candidate_count == 0:
        return (
            "I do not see anything safe to move to Trash in the latest batch.\n\n"
            f"Protected / untouched: {plan.protected_count}\n"
            f"Skipped: {plan.skipped_count}\n\n"
            "I did not move anything to Trash.\n"
            "I did not permanently delete anything.\n"
            "I did not touch Gmail."
        )

    lines = [
        "I found safe Trash-review candidates in the latest batch.",
        "",
        f"Safe Trash candidates: {plan.candidate_count}",
        f"Protected / untouched: {plan.protected_count}",
        "",
        "These would go to Gmail Trash for your manual review, not permanent delete.",
        "",
    ]

    for item in plan.candidates[:10]:
        lines.append(f"- ID {item.queue_id}: {item.subject} | risk {item.risk} | {item.category}")

    lines.extend([
        "",
        "This is only a plan.",
        "I did not move anything to Trash.",
        "I did not permanently delete anything.",
        "I did not touch Gmail.",
    ])

    return "\n".join(lines)


def main() -> None:
    print(build_trash_plan_message())


if __name__ == "__main__":
    main()
