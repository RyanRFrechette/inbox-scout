from pathlib import Path
from datetime import datetime, timezone
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"

PROGRESS_FILE = PLANS_DIR / "latest_cleanup_progress.json"
CLEANUP_PLAN_FILE = PLANS_DIR / "latest_inbox_cleanup_plan.json"
SCAN_PLAN_FILE = PLANS_DIR / "latest_scan_queue_plan.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_cleanup_status_message() -> str:
    progress = load_json(PROGRESS_FILE)
    plan = load_json(CLEANUP_PLAN_FILE)

    if not progress and not plan:
        return "No cleanup progress found. Gmail not touched."

    lines = ["Cleanup status", ""]

    if progress:
        lines.append(f"Status: {progress.get('status', 'unknown')}")
        lines.append(f"Scanned: {progress.get('scanned', 0)}")
        lines.append(f"Batches: {progress.get('batch_count', 0)}")
        lines.append(f"Batch size: {progress.get('batch_size', 5)}")
        lines.append(f"Cap: {progress.get('cap_emails', 0)}")
        lines.append(f"Progress vs cap: {progress.get('progress_vs_cap_percent', 0)}%")

    if plan:
        lines.append("")
        lines.append(f"Trash candidates: {plan.get('trash_candidate_count', 0)}")
        lines.append(f"Protected: {plan.get('protected_count', 0)}")
        lines.append(f"Needs review: {plan.get('pending_review_count', 0)}")

    lines.append("")
    lines.append("Read-only. Gmail not touched.")
    return "\n".join(lines)


def _rename_if_exists(path: Path, stamp: str) -> bool:
    if not path.exists():
        return False
    new_name = path.with_name(f"{path.stem}.cancelled_{stamp}{path.suffix}")
    path.rename(new_name)
    return True


def build_cancel_cleanup_message() -> str:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    cancelled = []
    if _rename_if_exists(CLEANUP_PLAN_FILE, stamp):
        cancelled.append("cleanup plan")
    if _rename_if_exists(SCAN_PLAN_FILE, stamp):
        cancelled.append("scan plan")
    if _rename_if_exists(PROGRESS_FILE, stamp):
        cancelled.append("cleanup progress")

    if not cancelled:
        return "No active cleanup plan found. Gmail not touched."

    return "Cleanup cancelled. Invalidated: " + ", ".join(cancelled) + ".\n\nGmail not touched."
