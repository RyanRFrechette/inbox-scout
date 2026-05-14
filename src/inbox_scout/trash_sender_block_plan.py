from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inbox_scout.trash_execution_runner import (
    PROTECTED_CATEGORIES,
    TRASH_EXECUTION_LOG,
    get_category,
    get_sender,
    has_protected_text,
    load_queue_document,
    is_true,
    norm,
    clean,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
LATEST_SENDER_BLOCK_PLAN = PLANS_DIR / "latest_sender_block_plan.json"

PLAN_MAX_AGE_MINUTES = 60

# Security/account senders that should never be blocked
SYSTEM_SENDER_PATTERNS = [
    r"no.?reply@",
    r"noreply@",
    r"security@",
    r"account@",
    r"alerts@",
    r"notifications@",
    r"support@.*google",
    r"accounts@.*google",
]
_SYSTEM_RE = [re.compile(p, re.IGNORECASE) for p in SYSTEM_SENDER_PATTERNS]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def extract_email(raw: str) -> str:
    """Extract bare email address from 'Name <addr>' or plain addr."""
    raw = raw.strip()
    m = re.search(r"<([^>]+)>", raw)
    if m:
        return m.group(1).strip().lower()
    if "@" in raw:
        return raw.lower()
    return ""


def is_valid_email(addr: str) -> bool:
    return bool(addr) and "@" in addr and "." in addr.split("@")[-1]


def is_system_sender(addr: str) -> bool:
    return any(r.search(addr) for r in _SYSTEM_RE)


def collect_trashed_senders() -> list[str]:
    """Read senders from trash execution logs (gmail_changed=true entries)."""
    if not TRASH_EXECUTION_LOG.exists():
        return []

    senders: list[str] = []
    with TRASH_EXECUTION_LOG.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("gmail_changed") is True:
                raw = clean(entry.get("sender", ""))
                if raw:
                    senders.append(raw)
    return senders


def collect_queue_trashed_senders() -> list[str]:
    """Fallback: read senders from queue items marked trashed or trash_candidate."""
    _, items = load_queue_document()
    senders: list[str] = []
    for item in items:
        decision = norm(item.get("local_decision", ""))
        trashed = is_true(item.get("gmail_trashed")) or is_true(item.get("gmail_action_taken"))
        action = norm(item.get("gmail_action_type", ""))
        if trashed or action == "trash" or decision in {"trash_candidate", "trash"}:
            raw = get_sender(item)
            if raw and raw != "unknown":
                senders.append(raw)
    return senders


def filter_senders(raw_senders: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in raw_senders:
        addr = extract_email(raw)
        if not is_valid_email(addr):
            continue
        if is_system_sender(addr):
            continue
        if addr in seen:
            continue
        seen.add(addr)
        result.append(addr)
    return sorted(result)


def build_sender_block_plan() -> tuple[list[str], str]:
    """Build plan from trash logs, falling back to queue. Returns (senders, source_label)."""
    raw = collect_trashed_senders()
    source = "latest trash run log"
    if not raw:
        raw = collect_queue_trashed_senders()
        source = "local review queue (trashed items)"
    return filter_senders(raw), source


def build_sender_block_plan_message() -> str:
    senders, source = build_sender_block_plan()

    if not senders:
        return (
            "No trash sender data found.\n\n"
            "Run a cleanup pass first so I have a record of which senders were moved to Trash.\n\n"
            "Gmail not touched."
        )

    count = len(senders)
    confirmation_phrase = f"BLOCK {count} TRASH SENDERS"

    plan = {
        "created_at": now_iso(),
        "source": source,
        "sender_count": count,
        "senders": senders,
        "confirmation_phrase": confirmation_phrase,
        "gmail_changes_enabled": False,
        "permanent_delete_enabled": False,
        "scope_required": "https://www.googleapis.com/auth/gmail.settings.basic",
    }
    save_json(LATEST_SENDER_BLOCK_PLAN, plan)

    lines = [
        f"I found {count} sender(s) from your trashed emails ({source}).",
        "",
        "Blocking these senders will create Gmail filters so future emails from them skip your Inbox and go to Trash.",
        "Nothing is permanently deleted. Existing emails are not affected.",
        "",
        "Senders to block:",
    ]
    for addr in senders:
        lines.append(f"  - {addr}")

    lines += [
        "",
        "To confirm, reply exactly:",
        f"  {confirmation_phrase}",
        "",
        "Or say cancel to stop. Gmail not touched yet.",
    ]
    return "\n".join(lines)
