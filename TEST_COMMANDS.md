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

# Sort planning (read-only)
.venv\Scripts\python.exe -m inbox_scout.natural_intent "sort 5 emails"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "sort 25 emails"
.venv\Scripts\python.exe -m inbox_scout.natural_intent "sort all"

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

## Safety rules

- All commands prefixed with `#` are apply-mode commands that change Gmail. Do not run them unless you intend to.
- Never run apply-mode commands without reviewing the dry-run output first.
- Permanent delete is disabled and reserved for Phase 14. Never enable it without explicit nuclear confirmation.
- Telegram watcher must be stopped before running a second watcher instance.
