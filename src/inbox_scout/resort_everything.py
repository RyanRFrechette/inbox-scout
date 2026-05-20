"""Resort Everything: full Gmail corpus scan with InboxScout label corrections.

Enumerates all messages (includeSpamTrash=True), deduplicates by ID,
reclassifies, and applies safe InboxScout label corrections.
Never trashes, archives, deletes, marks read, blocks senders, or removes system labels.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from inbox_scout.resort_apply_runner import (
    _is_sensitive,
    _validate_mismatch,
    _get_modify_service,
    INBOX_SCOUT_PREFIX,
    RESORT_APPLY_LOG,
)
from inbox_scout.trash_execution_runner import append_jsonl

_LIST_PAGE_SIZE = 500       # Max per messages.list call
_PROCESS_BATCH_SIZE = 50    # Messages per classify batch
_LOG_BATCH_INTERVAL = 200   # Console progress every N messages scanned

# Gmail system label IDs that must never be removed
_SYSTEM_LABEL_IDS = frozenset({
    "INBOX", "TRASH", "SPAM", "SENT", "UNREAD",
    "IMPORTANT", "STARRED", "DRAFT",
})


def _is_system_label_id(lid: str) -> bool:
    return lid in _SYSTEM_LABEL_IDS or lid.startswith("CATEGORY_")


def _debug_cap() -> Optional[int]:
    """Return debug cap from RESORT_EVERYTHING_DEBUG_CAP env var, or None (uncapped)."""
    raw = os.environ.get("RESORT_EVERYTHING_DEBUG_CAP", "").strip()
    if not raw:
        return None
    try:
        v = int(raw)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def _get_readonly_service(account: str):
    from inbox_scout.gmail_auth import get_gmail_service
    return get_gmail_service(mode="readonly", account=account)


def collect_all_message_ids(service, debug_cap: Optional[int] = None) -> tuple[list[str], bool]:
    """Page through all Gmail messages (includeSpamTrash=True). Deduplicate by ID.

    Returns (unique_ids, is_capped). is_capped=True only when debug_cap is hit.
    Normal behavior is uncapped — runs until pagination is exhausted.
    """
    seen: set[str] = set()
    page_token = None
    is_capped = False

    while True:
        kwargs: dict = {
            "userId": "me",
            "maxResults": _LIST_PAGE_SIZE,
            "includeSpamTrash": True,
        }
        if page_token:
            kwargs["pageToken"] = page_token
        try:
            resp = service.users().messages().list(**kwargs).execute()
        except Exception:
            break

        for msg in resp.get("messages", []):
            seen.add(msg["id"])
            if debug_cap is not None and len(seen) >= debug_cap:
                is_capped = True
                break

        if is_capped:
            break

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return list(seen), is_capped


def _build_label_maps(service) -> tuple[dict, dict]:
    """Return (name→id, id→name) for all labels in the account."""
    resp = service.users().labels().list(userId="me").execute()
    name_to_id: dict[str, str] = {}
    id_to_name: dict[str, str] = {}
    for lbl in resp.get("labels", []):
        name_to_id[lbl["name"]] = lbl["id"]
        id_to_name[lbl["id"]] = lbl["name"]
    return name_to_id, id_to_name


def _fetch_metadata_batch(service, message_ids: list[str]) -> list[dict]:
    """Fetch From/Subject/Date/snippet/labelIds for a batch of message IDs."""
    result: list[dict] = []
    for msg_id in message_ids:
        try:
            detail = service.users().messages().get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            hdrs = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            result.append({
                "message_id": msg_id,
                "from": hdrs.get("From", ""),
                "subject": hdrs.get("Subject", "(no subject)"),
                "date": hdrs.get("Date", ""),
                "snippet": detail.get("snippet", ""),
                "label_ids": detail.get("labelIds", []),
            })
        except Exception:
            pass
    return result


def _get_current_inboxscout_label(label_ids: list[str], id_to_name: dict) -> str:
    """Return the first InboxScout/* label name the message currently has, or ''."""
    for lid in label_ids:
        name = id_to_name.get(lid, "")
        if name.startswith(INBOX_SCOUT_PREFIX):
            return name
    return ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_account_everything(account: str, on_progress=None, on_log=None) -> dict:
    """Full corpus scan + label correction for one account. No Gmail writes except label swaps."""
    from inbox_scout.report_mode import classify_for_report
    from inbox_scout.autopilot_cleanup import _pick_inboxscout_label

    def _notify(msg: str) -> None:
        if on_progress is None:
            return
        try:
            on_progress(msg)
        except Exception:
            pass

    def _log(msg: str) -> None:
        if on_log is None:
            return
        try:
            on_log(msg)
        except Exception:
            pass

    cap = _debug_cap()

    # Phase 1: collect all message IDs
    try:
        ro_service = _get_readonly_service(account)
    except Exception as e:
        return _err_result(account, str(e))

    _log(f"[resort-all] {account}: collecting all message IDs...")
    try:
        ids, is_capped = collect_all_message_ids(ro_service, debug_cap=cap)
    except Exception as e:
        return _err_result(account, f"ID collection failed: {e}")

    target = len(ids)
    if is_capped:
        _log(f"[resort-all] {account}: DEBUG CAP HIT at {target:,} — run will be INCOMPLETE")
    else:
        _log(f"[resort-all] {account}: {target:,} unique messages to scan")

    if target == 0:
        return _empty_result(account)

    # Phase 2: build label maps
    try:
        name_to_id, id_to_name = _build_label_maps(ro_service)
    except Exception as e:
        return _err_result(account, f"Label fetch failed: {e}", target=target, capped=is_capped)

    # Phase 3: scan and classify in batches
    all_corrections: list[dict] = []
    total_scanned = 0
    skips = {"protected": 0, "manual_review": 0, "high_risk": 0, "sensitive": 0, "no_label": 0}
    error_count = 0
    _last_log_bucket = 0

    for batch_start in range(0, target, _PROCESS_BATCH_SIZE):
        batch_ids = ids[batch_start: batch_start + _PROCESS_BATCH_SIZE]
        emails = _fetch_metadata_batch(ro_service, batch_ids)

        if not emails:
            total_scanned += len(batch_ids)
            error_count += len(batch_ids)
            continue

        classified = classify_for_report(emails)
        total_scanned += len(classified)

        raw_by_id = {e["message_id"]: e for e in emails}

        for item in classified:
            msg_id = item.get("message_id", "")
            raw = raw_by_id.get(msg_id, {})
            current_label = _get_current_inboxscout_label(raw.get("label_ids", []), id_to_name)

            if not current_label:
                skips["no_label"] += 1
                continue

            ai = item.get("ai_classification", {})
            lookup = {
                "category": ai.get("category", ""),
                "from": item.get("from", ""),
                "subject": item.get("subject", ""),
                "snippet": item.get("snippet", ""),
            }
            recommended = _pick_inboxscout_label(lookup)
            if recommended == current_label:
                continue

            mismatch = {
                "message_id": msg_id,
                "subject": item.get("subject", ""),
                "from": item.get("from", ""),
                "current_label": current_label,
                "recommended_label": recommended,
                "recommended_category": ai.get("category", ""),
                "risk_score": int(ai.get("risk_score") or 0),
                "manual_review": bool(ai.get("manual_review")),
                "protected": bool(ai.get("protected") or item.get("protected")),
                "_account": account,
            }
            ok, reason = _validate_mismatch(mismatch)
            if not ok:
                if "protected" in reason:
                    skips["protected"] += 1
                elif "manual_review" in reason or "manual review" in reason:
                    skips["manual_review"] += 1
                elif "risk" in reason:
                    skips["high_risk"] += 1
                elif "sensitive" in reason:
                    skips["sensitive"] += 1
                continue
            all_corrections.append(mismatch)

        log_bucket = total_scanned // _LOG_BATCH_INTERVAL
        if log_bucket > _last_log_bucket:
            _last_log_bucket = log_bucket
            pct = int(100 * total_scanned / target) if target else 0
            remaining = target - total_scanned
            _log(
                f"[resort-all] {account}: {total_scanned:,}/{target:,} ({pct}%) "
                f"— {remaining:,} remaining, {len(all_corrections)} corrections"
            )

    # Phase 4: apply label corrections
    applied = 0
    apply_errors: list[str] = []

    if all_corrections:
        try:
            mod_service = _get_modify_service(account)
        except Exception as e:
            apply_errors.append(f"Gmail connect failed: {e}")
            mod_service = None

        if mod_service:
            for m in all_corrections:
                msg_id = m["message_id"]
                current_label = m["current_label"]
                recommended_label = m["recommended_label"]
                subj = (m.get("subject") or "(no subject)")[:50]

                recommended_id = name_to_id.get(recommended_label)
                current_id = name_to_id.get(current_label)

                if not recommended_id:
                    apply_errors.append(f"'{subj}': label '{recommended_label}' not in Gmail")
                    error_count += 1
                    continue

                # Safety guard: never remove a system label
                if current_id and _is_system_label_id(current_id):
                    apply_errors.append(f"'{subj}': refusing to remove system label '{current_label}'")
                    error_count += 1
                    continue

                try:
                    mod_service.users().messages().modify(
                        userId="me",
                        id=msg_id,
                        body={"addLabelIds": [recommended_id]},
                    ).execute()
                except Exception as e:
                    apply_errors.append(f"'{subj}': add label failed — {e}")
                    error_count += 1
                    continue

                if current_id and not _is_system_label_id(current_id):
                    try:
                        mod_service.users().messages().modify(
                            userId="me",
                            id=msg_id,
                            body={"removeLabelIds": [current_id]},
                        ).execute()
                    except Exception as e:
                        apply_errors.append(f"'{subj}': remove old label failed — {e}")

                applied += 1
                append_jsonl(RESORT_APPLY_LOG, {
                    "event": "resort_everything_moved",
                    "timestamp": _now_iso(),
                    "account": account,
                    "message_id": msg_id,
                    "subject": m.get("subject"),
                    "from": m.get("from"),
                    "current_label": current_label,
                    "recommended_label": recommended_label,
                    "gmail_changed": True,
                    "permanent_delete": False,
                    "trashed": False,
                    "archived": False,
                })

    complete = not is_capped and error_count == 0 and total_scanned >= target

    incomplete_note = ""
    if is_capped:
        incomplete_note = " INCOMPLETE (debug cap hit)"
    elif error_count > 0:
        incomplete_note = f" INCOMPLETE ({error_count} errors)"

    _log(
        f"[resort-all] {account}: done — {total_scanned:,}/{target:,} scanned, "
        f"{applied} applied{incomplete_note}"
    )

    return {
        "account": account,
        "target": target,
        "scanned": total_scanned,
        "applied": applied,
        "complete": complete,
        "capped": is_capped,
        "skipped_protected": skips["protected"],
        "skipped_manual_review": skips["manual_review"],
        "skipped_high_risk": skips["high_risk"],
        "skipped_sensitive": skips["sensitive"],
        "skipped_no_label": skips["no_label"],
        "errors": error_count,
        "apply_errors": apply_errors,
    }


def _err_result(account: str, error: str, target: int = 0, capped: bool = False) -> dict:
    return {
        "account": account, "error": error, "target": target, "scanned": 0,
        "applied": 0, "complete": False, "capped": capped,
        "skipped_protected": 0, "skipped_manual_review": 0,
        "skipped_high_risk": 0, "skipped_sensitive": 0, "skipped_no_label": 0,
        "errors": 0, "apply_errors": [],
    }


def _empty_result(account: str) -> dict:
    return {
        "account": account, "target": 0, "scanned": 0, "applied": 0,
        "complete": True, "capped": False,
        "skipped_protected": 0, "skipped_manual_review": 0,
        "skipped_high_risk": 0, "skipped_sensitive": 0, "skipped_no_label": 0,
        "errors": 0, "apply_errors": [],
    }


def build_resort_everything_message(account: str = "both") -> str:
    """Telegram entry point. Ack is sent by router; this returns the final summary."""
    try:
        from inbox_scout.telegram_notifier import send_message as _send_progress
    except Exception:
        _send_progress = None

    if account in ("both", "unspecified"):
        results = [
            _run_account_everything("primary", on_progress=_send_progress, on_log=print),
            _run_account_everything("secondary", on_progress=_send_progress, on_log=print),
        ]
    elif account == "primary":
        results = [_run_account_everything("primary", on_progress=_send_progress, on_log=print)]
    else:
        results = [_run_account_everything("secondary", on_progress=_send_progress, on_log=print)]

    return _format_everything_summary(results)


def _format_everything_summary(results: list[dict]) -> str:
    lines: list[str] = []

    for r in results:
        acct = r.get("account", "?")
        label = "Primary" if acct == "primary" else "Secondary"
        err = r.get("error")
        if err:
            lines.append(f"{label}: failed — {err}")
            continue

        scanned = r.get("scanned", 0)
        target = r.get("target", 0)
        applied = r.get("applied", 0)
        capped = r.get("capped", False)
        complete = r.get("complete", False)
        errors = r.get("errors", 0)

        if capped:
            status = "INCOMPLETE — debug cap hit"
        elif not complete:
            status = f"INCOMPLETE — {errors} error(s)" if errors else "INCOMPLETE"
        else:
            status = "Complete"

        lines.append(f"{label}: {scanned:,}/{target:,} scanned — {applied} corrections — {status}")

    errors_only = [r for r in results if r.get("error")]
    good = [r for r in results if not r.get("error")]

    if len(good) > 1:
        total_scanned = sum(r.get("scanned", 0) for r in good)
        total_target = sum(r.get("target", 0) for r in good)
        total_applied = sum(r.get("applied", 0) for r in good)
        all_complete = all(r.get("complete", False) for r in good)
        lines.append(
            f"\nCombined: {total_scanned:,}/{total_target:,} — {total_applied} corrections — "
            + ("Complete" if all_complete else "INCOMPLETE")
        )

    skipped = sum(
        r.get("skipped_protected", 0) + r.get("skipped_manual_review", 0)
        + r.get("skipped_high_risk", 0) + r.get("skipped_sensitive", 0)
        for r in good
    )
    if skipped:
        lines.append(f"{skipped:,} skipped (protected/manual-review/high-risk/sensitive).")

    lines.append("\nLabels corrected only. No emails trashed, deleted, or archived.")
    return "\n".join(lines)
