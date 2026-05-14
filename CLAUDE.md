# Inbox Scout - CLAUDE.md

Last updated: 2026-05-14 (Phase 13X)

---

## 1. What Inbox Scout does

Inbox Scout is a personal Gmail inbox manager that:
- Fetches unread Gmail inbox messages via the Gmail API
- Classifies emails using local rules and an AI classifier (Ollama/qwen3:8b)
- Builds a local review queue with decisions (keep, archive, trash, ignore, protected)
- Applies Gmail actions (archive, trash, mark-as-read) after explicit two-step confirmation
- Sends status and accepts control commands via Telegram (bot: Atlas)

The Telegram bot ("Atlas") allows Ryan to run inbox operations from his phone without a laptop.

---

## 2. Current phase / status

**Current branch:** master
**Last commit:** `f0dd6e8` — feat: add Phase 13X safe sort-all batch loop (2026-05-14)

**Phase 13X** is the most recently completed phase (2026-05-14):
- "sort all" now runs as a safe controlled batch loop — 5 emails per batch, never unlimited
- Continuation phrases added: "continue sorting", "sort more", "next batch", "keep sorting"
- After each batch Atlas says: "There may be more. Say 'continue sorting' to process the next safe batch of 5."
- Two-step approval preserved on every batch (plan → yes → scan)
- Removed three separate `sort_all` hard-blocks from plan, approval, and runner layers
- No Gmail write actions. No config changes. No token/credential/data files touched.
- Commit: `f0dd6e8`

**Pre-13X Backup Archive Cleanup** was completed prior (2026-05-14):
- Moved 12 backup/snapshot files from `src/inbox_scout/` to `archive/phase_backups/`

**Phase 13W** was completed prior (2026-05-13):
- Cleaned up `natural_intent.py` — removed 194 lines of dead/duplicate code

**Current safety mode:** READ-ONLY ONLY (see PROJECT_STATE.md for flag details)

**Next planned steps (in order):**
1. Phase 13Y — Natural UX polish
2. Phase 13Z — Final local MVP
3. Phase 14 — Permanent delete mode (nuclear, disabled until explicitly enabled)

---

## 3. Safety rules

- **Never take any Gmail action (archive, trash, mark-as-read, label, reply, delete) without explicit apply-mode confirmation from Ryan.**
- All runners default to dry-run. Apply mode requires `-Apply` flag or explicit two-step Telegram confirmation.
- Do not enable permanent delete. It is reserved for Phase 14 and must never be activated without a nuclear confirmation flag.
- Do not run two Telegram watcher instances simultaneously. Stop the existing watcher first.
- Do not bypass the two-step confirmation gate in any Telegram apply flow.
- Do not run any Gmail modify actions in response to a Telegram message unless the full confirmation chain has completed.
- Config flags that gate live Gmail actions must default to `False`. Never flip them to `True` without explicit user instruction.
- After any live Gmail apply action, the config flag must automatically reset to `False`.

---

## 4. Files never to touch without explicit approval

**Credentials and tokens — never read, write, move, or delete:**
- `credentials.json`
- `token.json`
- `modify_token.json`
- Any `*.json` file in the project root that looks like an OAuth token

**Data and queue files — never modify without explicit instruction:**
- `data/queue/*.json` — local review queue
- `data/reports/*.json` and `data/reports/*.md` — generated inbox reports
- `data/logs/*.jsonl` — action logs (archive_actions.jsonl, etc.)

**Backup files — never delete or overwrite:**
- Any file ending in `.before_*`, `.phase*_backup`, or containing a timestamp in the name (e.g., `telegram_status.before_phase13u_20260512_211434.py`)

**Environment and config:**
- `.env` (if it exists)
- Any file containing API keys, bot tokens, or credentials

---

## 5. Gmail action rules

- **Never** call any Gmail API method that modifies state (archive, trash, label, mark-as-read, send, delete) without explicit approval from Ryan.
- Dry-run mode must be verified before any apply mode is run.
- Apply mode must print a clear summary of exactly what will change before executing.
- After apply, log every action to `data/logs/` in JSONL format.
- Protected categories (anything matching protected keyword rules) are NEVER eligible for Gmail actions regardless of config.
- Manual-review flagged emails are NEVER eligible for automatic Gmail actions.
- Permanent delete (bypass Trash) is disabled at the code level. Do not re-enable it.

---

## 6. Telegram action rules

- The Telegram bot (Atlas) controls Inbox Scout via natural language commands.
- All destructive commands (archive, trash, mark-as-read) require a two-step confirmation flow: plan → confirm.
- Read-only commands (status, audit, queue, next, help, ping, scan/report) are safe to run any time.
- Never route a Telegram command directly to a Gmail apply action without the confirmation gate.
- Never expose raw PowerShell commands, file paths, or technical errors in Telegram replies — responses must be natural, assistant-like.
- The watcher (`telegram_watch.py`) must be stopped before starting a second instance. There is self-protection logic for this.
- If the watcher crashes or restarts, it should not replay already-processed messages.

---

## 7. Git workflow rules

- Work in small, single-purpose commits. One logical change per commit.
- Commit message format: `type: short description` (e.g., `refactor: remove duplicate handlers`, `docs: record Phase 13W completion`).
- Always run `git log --oneline -3` and `git status` before starting any phase.
- If the repo is not clean (unexpected staged or modified files), stop and tell Ryan before proceeding.
- Never commit: `credentials.json`, `token.json`, `modify_token.json`, `data/queue/`, `data/logs/`, `data/reports/`, `.env`.
- Do not amend published commits. Create a new commit for fixes.
- Do not force-push.
- Do not commit until Ryan explicitly approves.

---

## 8. Testing rules

- After any code change, run at minimum:
  1. Syntax check: `.venv\Scripts\python.exe -m py_compile <changed_file>`
  2. Import check: `.venv\Scripts\python.exe -c "from inbox_scout import <module>; print('OK')"`
- For natural_intent.py changes, test key phrases using the commands in `TEST_COMMANDS.md`.
- Dry-run mode must be verified before any apply-mode test.
- Never run apply-mode tests without Ryan's explicit go-ahead.
- Gmail connection tests (fetching emails) are read-only and safe but should be noted.
- Do not run `inboxreport` or `inboxqueue` against live Gmail without noting it will consume API quota.

See `TEST_COMMANDS.md` for the full list of safe test commands.

---

## 9. Current next steps

1. **Phase 13Y** — Natural UX polish.
2. Continue through 13Z (final local MVP), then discuss Phase 14 (permanent delete, nuclear mode) separately.

**Do not jump ahead to Phase 14 without Ryan explicitly initiating it.**

---

## 10. Ryan's preferences for how to work

- **Small, safe phases only.** One logical unit of work per session. Stop and show output before moving to the next phase.
- **Always show diffs before committing.** Run `git diff -- <file>` after edits. Ryan reviews before any commit.
- **Never chain phases.** Complete one phase, stop, wait for explicit go-ahead before starting the next.
- **No surprises.** If something unexpected is found (unknown files, unexpected state, a file that shouldn't exist), stop and report it rather than fixing it silently.
- **Dry-run first, always.** For any action that touches Gmail or data files, dry-run output must be reviewed first.
- **Ask before anything irreversible.** Deleting files, modifying data, moving files, enabling apply mode — always confirm first.
- **Keep commits tight.** One file changed per commit is ideal. If multiple files must change, explain why in the commit message.
- **Do not create documentation files unless asked.** Work from conversation context. Exception: CLAUDE.md and explicitly requested docs.

---

## Source layout (key files)

```
src/inbox_scout/
  natural_intent.py          # Telegram natural language router — core dispatch
  telegram_watch.py          # Telegram watcher/listener (long-running)
  telegram_listener.py       # Read-only Telegram command handler
  telegram_approval.py       # Approval command handler
  telegram_apply_gate.py     # Apply gate (dry-run → confirm flow)
  telegram_confirm_gate.py   # Two-step confirmation gate
  archive_execution_runner.py
  trash_execution_runner.py
  mark_read_runner.py
  archive_planner.py
  trash_planner.py / trash_candidate_plan.py
  report_mode.py             # Paginated inbox report generator
  review_queue.py / queue_*.py  # Local queue management
  audit.py                   # Safety audit log reader
  gmail_auth.py              # OAuth helpers
  rule_classifier.py         # Local rule-based classifier
  ai_classifier.py           # Ollama/qwen3:8b AI classifier
  paths.py                   # Centralized path constants

data/
  queue/          # Local review queue (never commit)
  logs/           # JSONL action logs (never commit)
  reports/        # Generated inbox reports (never commit)
```

---

## Reference files

- `PROJECT_STATE.md` — Full project history and detailed phase status
- `PHASE_LOG.md` — Condensed phase log
- `TEST_COMMANDS.md` — Safe test commands for all modules
