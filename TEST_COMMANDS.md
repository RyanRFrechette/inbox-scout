# Inbox Scout - Test Commands

Safe read-only and local-only commands for verifying the project.
None of these commands change Gmail unless explicitly noted.

---

## Syntax check

```powershell
# Syntax-check a single module
.venv\Scripts\python.exe -m py_compile src\inbox_scout\natural_intent.py

# Import-check a module
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -c "from inbox_scout import natural_intent; print('natural_intent import OK')"
```

---

## Natural intent router

```powershell
$env:PYTHONPATH = "src"

# Sort planning (read-only, local logic only)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "sort 5 emails"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "sort 25 emails"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "sort all"

# Continuation phrases — should show "from where the last batch left off" and "next safe batch"
# (local logic only, does not touch Gmail, uses saved cursor if present)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "continue sorting"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "sort more"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "next batch"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "keep sorting"

# Check saved Gmail cursor (read-only, safe to run any time)
Get-Content data\plans\latest_gmail_scan_cursor.json

# "next" alone should route to next review item, NOT to continuation
.venv\Scripts\python.exe -m inbox_scout.natural_intent "next"

# Safety blocks (should return blocked responses, not execute)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "empty my trash"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "permanently delete trash emails"

# Trash plan (dry-run only, does not touch Gmail)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "what can go to trash"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "trash candidates"

# Archive plan (dry-run only, does not touch Gmail)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "what can be archived"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "archive candidates"

# Review plan
.venv\Scripts\python.exe -m inbox_scout.natural_intent "show me the plan"

# Status
.venv\Scripts\python.exe -m inbox_scout.natural_intent "status"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "what did you move"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "what still needs review"

# Cleanup flow — Phase 13Z (scan phrases are read-only; "move trash" CHANGES GMAIL)
# Live MVP test passed 2026-05-14: 25 emails / 5 batches / 8 moved to Trash

# Step 1: show cleanup scan plan (read-only, local logic only)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "clean my inbox"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "sort all and move trash"

# Step 2: "yes" triggers a real Gmail scan (safe but uses API quota)
# Step 3: "move trash" CHANGES GMAIL — only run after reviewing cleanup plan output
# .venv\Scripts\python.exe -m inbox_scout.natural_intent "move trash"

# Check cleanup status (read-only)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "cleanup status"

# Cancel an in-progress cleanup (read-only, local only)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "cancel cleanup"

# Verify "move trash" without prior cleanup plan (should block safely)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "move trash"

# Verify routing safety: "sort all and move trash" must NOT route to runner (must route to scanner)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "sort all and move trash"
```

---

## Sort command parser

```powershell
$env:PYTHONPATH = "src"

.venv\Scripts\python.exe -m inbox_scout.sort_command_parser "sort 25 emails"
.venv\Scripts\python.exe -m inbox_scout.sort_command_parser "sort all"
.venv\Scripts\python.exe -m inbox_scout.sort_command_parser "empty my trash"
.venv\Scripts\python.exe -m inbox_scout.sort_command_parser "move junk to trash so I can review it"
```

---

## Local queue

```powershell
# View current queue (local only, no Gmail)
inboxqueue

# View next pending item
inboxnext

# View a specific item
inboxitem -Id 1
```

---

## Archive dry-run (no Gmail changes)

```powershell
# Dry-run only
inboxarchive

# Apply mode — CHANGES GMAIL — only run after reviewing dry-run
# inboxarchive -Apply
```

---

## Trash dry-run (no Gmail changes)

```powershell
# Dry-run only
inboxtrash

# Apply mode — CHANGES GMAIL — only run after reviewing dry-run
# inboxtrash -Apply
```

---

## Mark-as-read dry-run (no Gmail changes)

```powershell
# Dry-run only
inboxmarkread

# Apply mode — CHANGES GMAIL — only run after reviewing dry-run
# inboxmarkread -Apply
```

---

## Audit (read-only)

```powershell
inboxaudit
```

---

## Telegram status (read-only send to Atlas)

```powershell
inboxtelegramstatus

# One-shot listener check (reads from Telegram only, no Gmail)
inboxtelegramlisten
```

---

## Git

```powershell
# Verify checkpoint
git log --oneline -3
git status

# Show changes to a specific file
git diff -- src/inbox_scout/natural_intent.py

# Verify git identity is set locally
git config user.name
git config user.email
```

---

## Sender blocking — Phase 13Z-D

```powershell
$env:PYTHONPATH = "src"

# Step 1: build plan (read-only, no Gmail changes)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "block senders in trash"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "block all senders in trash"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "block all the senders in the trash"

# Step 2: wrong confirmation must block safely
.venv\Scripts\python.exe -m inbox_scout.natural_intent "BLOCK 99 TRASH SENDERS"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "yes block them"

# Step 3: exact confirmation — routes to runner (scope gate will block until gmail.settings.basic is provisioned)
# Replace N with the count shown in the plan output
# .venv\Scripts\python.exe -m inbox_scout.natural_intent "BLOCK N TRASH SENDERS"

# Permanent delete still blocked
.venv\Scripts\python.exe -m inbox_scout.natural_intent "permanently delete"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "empty my trash"
```

---

## Safety rules

- All commands prefixed with `#` are apply-mode commands that change Gmail. Do not run them unless you intend to.
- Never run apply-mode commands without reviewing the dry-run output first.
- Permanent delete is disabled and reserved for Phase 14. Never enable it without explicit nuclear confirmation.
- Telegram watcher must be stopped before running a second watcher instance.
