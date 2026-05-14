from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inbox_scout.trash_candidate_plan import is_safe_trash_candidate, load_items


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_INBOX_CLEANUP_PLAN = PLANS_DIR / "latest_inbox_cleanup_plan.json"


@dataclass
class InboxCleanupPlan:
    plan_id: str
    created_at: str
    total_scanned: int
    trash_candidate_count: int
    protected_count: int
    needs_review_count: int
    trash_candidates: list[dict[str, Any]]
    gmail_changes_enabled: bool
    permanent_delete_enabled: bool


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_plan_id() -> str:
    return datetime.now(timezone.utc).strftime("cleanup_%Y%m%d_%H%M%S")


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


def is_protected(item: dict[str, Any]) -> bool:
    decision = clean(item.get("local_decision")).lower()
    return decision == "protected_review" or is_true(item.get("manual_review"))


def is_already_handled(item: dict[str, Any]) -> bool:
    return bool(clean(item.get("gmail_action_type"))) or is_true(item.get("gmail_action_taken"))


def build_inbox_cleanup_plan() -> InboxCleanupPlan:
    items = load_items()

    candidates: list[dict[str, Any]] = []
    protected_count = 0
    needs_review_count = 0

    for item in items:
        if is_already_handled(item):
            continue

        if is_protected(item):
            protected_count += 1
            continue

        ok, _ = is_safe_trash_candidate(item)
        if ok:
            candidates.append({
                "queue_id": clean(item.get("queue_id") or item.get("id") or "?"),
                "subject": clean(item.get("subject") or "(no subject)"),
                "category": clean(item.get("category") or "unknown"),
                "risk": risk_int(item),
            })
        else:
            needs_review_count += 1

    plan = InboxCleanupPlan(
        plan_id=make_plan_id(),
        created_at=now_iso(),
        total_scanned=len(items),
        trash_candidate_count=len(candidates),
        protected_count=protected_count,
        needs_review_count=needs_review_count,
        trash_candidates=candidates,
        gmail_changes_enabled=False,
        permanent_delete_enabled=False,
    )

    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_INBOX_CLEANUP_PLAN.write_text(
        json.dumps(asdict(plan), indent=2),
        encoding="utf-8",
    )

    return plan


def build_inbox_cleanup_plan_message() -> str:
    plan = build_inbox_cleanup_plan()

    if plan.total_scanned == 0:
        return (
            "No queue to build a cleanup plan from.\n\n"
            "Say sort to scan your inbox first."
        )

    header = (
        f"Cleanup plan ready.\n\n"
        f"Scanned: {plan.total_scanned} | Protected: {plan.protected_count} | "
        f"Needs review: {plan.needs_review_count} | Trash candidates: {plan.trash_candidate_count}"
    )

    if plan.trash_candidate_count == 0:
        return header + "\n\nNo safe trash candidates found. Gmail not touched."

    lines = [header, "", "Safe to move to Trash:"]
    for c in plan.trash_candidates:
        lines.append(f"- ID {c['queue_id']}: {c['subject']} | risk {c['risk']} | {c['category']}")

    lines.extend([
        "",
        "Nothing has been moved yet.",
        "",
        "Say move trash to move only these to Gmail Trash.",
        "Nothing will be permanently deleted.",
    ])

    return "\n".join(lines)


def main() -> None:
    print(build_inbox_cleanup_plan_message())


if __name__ == "__main__":
    main()
