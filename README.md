# AI Gmail Cleanup Assistant — Inbox Scout with Telegram Control

## Recruiter TL;DR

Inbox Scout is a Python automation project that connects Gmail, Telegram, and AI classification into a safety-first email cleanup assistant. It demonstrates API integration, OAuth workflows, local/cloud model routing, audit logging, and guarded automation that moves only low-risk junk to Gmail Trash while protecting sensitive email. Relevant to technical support, cloud support, automation, and junior systems roles.

**Inbox Scout** is a local-first AI Gmail cleanup assistant controlled through Telegram. The Telegram bot, **Atlas**, helps scan unread inbox messages, classify risk, move obvious low-risk junk to Gmail Trash, mark safely handled messages as read, and leave sensitive email untouched for manual review.

This project was built as a real-world automation system, not a toy demo. It combines Gmail API access, AI-assisted classification, natural-language command routing, guarded Gmail actions, audit logging, and safety-first automation design.

> Portfolio focus: practical Python automation, API integration, AI-assisted workflow design, safety guardrails, local-first tooling, and operational thinking.

---

## Problem

Email cleanup is repetitive, risky, and easy to get wrong. A normal inbox contains newsletters, promotions, shipping notices, receipts, bank alerts, login/security messages, medical messages, job emails, and personal messages all mixed together.

The goal of Inbox Scout is to reduce inbox noise without creating a dangerous automation that can accidentally delete or hide important email.

Inbox Scout is designed around one core rule:

**Automate the obvious. Protect the risky. Log everything.**

---

## What Inbox Scout does

Inbox Scout can:

- Read unread Gmail inbox messages through the Gmail API.
- Classify emails using local rules plus optional AI assistance.
- Route AI calls between local Ollama and OpenRouter.
- Accept natural-language Telegram commands through Atlas.
- Build local review queues for safe triage.
- Identify obvious low-risk newsletter/promotion-style emails.
- Move only safe trash candidates to Gmail Trash, not permanent delete.
- Mark successfully handled emails as read after the Gmail action succeeds.
- Preserve sensitive emails for manual review.
- Show audit output explaining what happened and why.

Inbox Scout does **not** permanently delete email.

---

## Current project status

**Status:** Active portfolio MVP with real Gmail integration and live safety testing.

Implemented areas:

- Gmail read-only and modify OAuth flows
- Rule-based email classification
- AI-assisted classification
- OpenRouter model switching
- Telegram bot control through Atlas
- Natural-language cleanup commands
- Inbox Zero batch autopilot: scan, classify, auto-trash safe junk, mark read
- Safe Gmail Trash runner
- Mark-as-read after successful safe action
- Queue audit tooling
- Protected-category safety system
- InboxScout Gmail labels
- Classification audit explanations
- Resort Everything: full corpus scan with label-only correction mode
- Cloud deployment config (render.yaml reference, DigitalOcean-compatible)

Current active direction:

- Cloud deployment: decode Gmail OAuth token from env var at startup (GMAIL_TOKEN_JSON).
- Linux-native process cleanup in telegram_watch.py (currently uses PowerShell, fails silently on Linux).
- Phase 14 permanent delete mode (disabled; reserved for future explicit confirmation flow).

---

## Architecture

```text
Telegram user command
        |
        v
Atlas Telegram bot
        |
        v
Natural-language intent router
        |
        v
Gmail unread scan -> classifier -> local review queue
        |                         |
        |                         v
        |                  rule + AI risk decision
        |
        v
Safety gate / cleanup plan
        |
        v
Allowed action only if low-risk and non-protected
        |
        +--> move to Gmail Trash
        +--> mark read after successful action
        +--> label/category audit
        +--> leave protected emails untouched
```

---

## Tech stack

| Area | Tools |
|---|---|
| Language | Python |
| Email API | Gmail API / Google OAuth |
| Chat control | Telegram Bot API |
| Local AI | Ollama / qwen3:8b |
| Cloud AI option | OpenRouter |
| Data storage | Local JSON queues and JSONL audit logs |
| CLI tooling | PowerShell shortcuts + Python module entrypoints |
| Safety model | Rule gates, protected categories, risk thresholds, dry-run planners, final runners |
| Deployment target | Local Windows environment first; cloud worker planned |

---

## Key features

### 1. Telegram-controlled inbox assistant

Inbox Scout is controlled through a Telegram bot named Atlas. The goal is to let the user send commands like:

```text
clean 25 emails
clean up a batch
get me closer to inbox zero
sort all
status
progress report
show queue
/model status
/model openrouter
/model auto
```

Atlas translates natural language into safe workflow actions.

---

### 2. Local-first Gmail safety model

The project separates planning from execution.

A scan can classify emails and build a local queue without changing Gmail. Actions are handled by guarded runners that re-check safety before touching Gmail.

Safety layers include:

- Protected category checks
- Protected keyword checks
- Risk score thresholds
- Manual-review preservation
- Gmail action state tracking
- Final runner validation
- Audit logging
- No permanent delete path enabled

---

### 3. Rule + AI classification

Inbox Scout uses deterministic rules first, then AI when useful.

The classification system can identify common categories such as:

- Promotion
- Newsletter
- Shopping history
- Receipts
- Security
- Finance
- Accounts
- Jobs
- Manual review
- Protected review

AI output is not blindly trusted. If local rules mark something protected, the system preserves that safety decision even if the AI suggests a lower-risk category.

---

### 4. OpenRouter model switching

Inbox Scout supports model routing between local and cloud AI providers.

Supported modes include:

```text
/model status
/model local
/model openrouter
/model auto
```

Auto mode is designed to keep costs low:

- Obvious rule-based junk can skip AI.
- Small scans can use local models.
- Larger cleanup batches can use OpenRouter when configured.
- Protected emails stay protected regardless of provider output.

---

### 5. Reversible cleanup actions

Inbox Scout moves safe junk to **Gmail Trash**, not permanent delete.

That distinction matters. Gmail Trash is reversible. Permanent deletion is intentionally disabled because inbox automation should fail safely.

The cleanup runner only handles low-risk candidates such as obvious promotions or newsletters. Sensitive categories are skipped.

---

### 6. Mark-read only after successful handling

Inbox Scout can mark an email as read only after the email was successfully handled by a safe Gmail action.

That prevents important unread emails from being hidden just because the classifier saw them.

---

### 7. Audit-first development

Inbox Scout includes audit tools so the system can explain what happened.

The queue audit helper can show:

- Email ID
- Subject
- Category
- Risk score
- Manual-review status
- Local decision
- Candidate bucket
- Human-readable reason
- Whether the final runner would block the item

This makes the system easier to debug and safer to improve.

---

## Safety rules

Inbox Scout is intentionally conservative.

Protected or manual-review email categories include:

- Finance and banking
- Payments
- Receipts and invoices
- Shipping and order confirmations
- Security and login alerts
- Legal and tax
- Medical and health
- Job and career
- Personal messages
- Client or business communication
- Warranty, support, refunds, and account access

Automation rules:

- No permanent delete.
- No Gmail writes without a safe runner.
- No protected/manual-review email is auto-trashed.
- No protected/manual-review email is auto-marked-read.
- No sender blocking unless explicitly approved in a separate safety flow.
- Secrets, tokens, OAuth files, queues, logs, and runtime data are excluded from source control.

---

## Example workflow

```text
User sends Telegram command:
clean 25 emails

Atlas scans unread inbox messages.
Inbox Scout classifies each message.
Protected emails are locked for manual review.
Obvious low-risk promotions/newsletters become trash candidates.
The final safety runner checks each candidate again.
Only safe candidates move to Gmail Trash.
Successfully moved emails are marked read.
Atlas summarizes what happened.
```

Example outcome:

```text
Scanned: 25
Protected: 17
Unclear: 0
Trash candidates: 8
Moved to Trash: only candidates that passed final safety checks
Permanent deletes: 0
```

---

## What I built

This project includes multiple production-style components:

- Gmail OAuth setup with separate read-only and modify tokens
- Gmail inbox fetcher
- Paginated Gmail scan support
- Rule-based classifier
- AI classifier integration
- OpenRouter provider router
- Local review queue system
- Queue viewer and decision updater
- Gmail label manager
- Archive planner and guarded runner
- Trash planner and guarded runner
- Trash execution safety gate
- Mark-read planner and guarded runner
- Telegram notifier
- Telegram listener
- Natural-language intent router
- Cleanup autopilot path
- Model switching commands
- Queue audit module
- Protected text detection
- Filing category labels
- Project documentation and phase logs

---

## Skills demonstrated

This project demonstrates practical ability in:

- Python application design
- API integration
- OAuth-based authentication workflows
- Gmail API automation
- Telegram bot automation
- AI-assisted classification
- Prompt/routing strategy for local and cloud models
- Safety-critical automation design
- Test-driven feature hardening
- JSON/JSONL local state management
- CLI workflow design
- Windows/PowerShell developer tooling
- Git-based phased development
- Operational debugging and audit logging

---

## Running locally

> This project requires private Gmail and Telegram credentials. Secrets are not included in this repository.

Install dependencies:

```powershell
pip install -r requirements.txt
```

Set module path:

```powershell
$env:PYTHONPATH = "src"
```

Run the Telegram watcher:

```powershell
python -m inbox_scout.telegram_watch
```

Run a read-only report scan:

```powershell
python -m inbox_scout.report_mode --limit 25 --page-size 5 --unread-only --export both
```

Run queue audit:

```powershell
python -m inbox_scout.queue_audit --plain
```

---

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token for Atlas |
| `TELEGRAM_CHAT_ID` | Yes | Authorized Telegram chat ID (numeric) |
| `GMAIL_TOKEN_JSON` | Cloud only | base64-encoded `token.json` (readonly Gmail scope) |
| `GMAIL_TOKEN_MODIFY_JSON` | Cloud only | base64-encoded `token_modify.json` (modify Gmail scope) |
| `OPENROUTER_API_KEY` | No | Cloud AI classifier; falls back to rule-based if not set |
| `PYTHONPATH` | Yes | Must include `src` |

Local dev uses `token.json` / `token_modify.json` on disk. Cloud uses base64 env vars decoded at startup.

Credential files and local `.env` are intentionally ignored by git.

---

## Cloud deployment (DigitalOcean / VPS / Linux)

### 1. Encode Gmail tokens

On Windows (PowerShell):

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("token.json")) | clip
[Convert]::ToBase64String([IO.File]::ReadAllBytes("token_modify.json")) | clip
```

On Linux/macOS:

```bash
base64 -w 0 token.json
base64 -w 0 token_modify.json
```

### 2. Set environment secrets

In your cloud dashboard (DigitalOcean App Platform / VPS env), set these as secrets (never commit values):

```
TELEGRAM_BOT_TOKEN=<your Atlas bot token>
TELEGRAM_CHAT_ID=<your numeric chat ID>
GMAIL_TOKEN_JSON=<base64 output from step 1>
GMAIL_TOKEN_MODIFY_JSON=<base64 output from step 1>
OPENROUTER_API_KEY=<optional>
PYTHONPATH=src
ENABLE_TELEGRAM_WATCHER=true
```

Note: `ENABLE_TELEGRAM_WATCHER=true` is required on Linux/cloud — the watcher exits immediately without it to prevent conflicts with a local Windows watcher. Keep it unset if running Atlas locally.

### 3. Start command

```
python -m inbox_scout.telegram_watch
```

The worker auto-decodes token env vars to disk on startup (only if the files are missing).
`render.yaml` is included as a deploy config reference; adapt env var names for DigitalOcean App Platform or your VPS setup.

### 4. Verify deployment

After the worker starts, send in Telegram:

```
status
progress report
```

Atlas should respond with queue state. No Gmail reads happen from status alone.

### Safety guarantees

- Protected email categories are never auto-trashed (finance, receipts, billing, legal, medical, job/career, account/security, personal, client/business, warranty/support)
- No permanent delete path exists
- Gmail Trash only — reversible
- No sender blocking
- No replies

---

## Roadmap

Next milestones:

- Add safe category filing for shopping history and other low-risk archival categories.
- Add a lightweight dashboard or web status view for portfolio/demo visibility.
- Keep permanent delete disabled unless a future explicit nuclear confirmation flow is designed and reviewed.

Completed milestones:

- Inbox Zero batch autopilot (`clean 25 emails`, `clean up a batch`, `sort all`)
- OpenRouter AI classifier integration with local fallback
- Resort Everything: full corpus label correction mode
- Cloud deployment config (cloud_startup.py, Linux-safe watcher, DigitalOcean-compatible)

---

## Why this matters

Inbox Scout shows how AI automation can be useful without being reckless.

The project is intentionally built like a real operations tool:

- It has safety gates.
- It has audit logs.
- It separates planning from execution.
- It treats sensitive data carefully.
- It uses AI where helpful, but not as the only source of truth.
- It solves a real repetitive workflow with measurable value.

For a hiring manager, this project demonstrates the ability to build practical automation systems that connect APIs, AI, user interfaces, and safety controls into a working product.
