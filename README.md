# Inbox Scout

Inbox Scout is a local-first Gmail inbox cleanup assistant controlled via Telegram (bot: Atlas).

## Current Status — Phase 13Z-C (Live MVP complete, 2026-05-14)

**Phase 13Z-C live test passed.** Full cleanup flow verified end-to-end through Telegram:

- "clean my inbox" → 25-email read-only scan across 5 batches (cap enforced)
- cleanup status → `stopped_by_cap`, scanned 25, batches 5, cap 25, progress 100%
- cleanup plan → 17 protected, 0 needs review, 8 trash candidates
- "move trash" → moved exactly those 8 candidates to Gmail Trash
- nothing permanently deleted

**Key commits:**
- `6e02ca1` fix: prevent duplicate telegram watchers
- `c0cdf47` feat: harden cleanup test progress and watcher errors
- `fc19dd5` docs: add token-efficient Claude workflow

**Next:** portfolio/cloud deployment planning (Phase 14 — permanent delete — disabled until explicitly enabled).

## Safety Rules

- Read-only by default. No archiving, no permanent delete.
- Gmail Trash via "move trash" only — requires prior cleanup plan (gated, two-step).
- Protected/manual-review emails never touched by any automated action.
- Permanent delete disabled at the code level (Phase 14, nuclear flag required).
- Duplicate Telegram watcher prevention: self-protection lock enforced.

## What it does

1. Fetches unread Gmail inbox messages via Gmail API
2. Classifies emails with local rules + AI (Ollama/qwen3:8b)
3. Builds a local review queue with decisions (keep, archive, trash, ignore, protected)
4. Applies Gmail Trash actions only after explicit two-step Telegram confirmation
5. Sends status and accepts commands via Telegram (Atlas)

## Telegram commands (Atlas)

| Command | Effect |
|---|---|
| `clean my inbox` / `cleanup my inbox` | Read-only 25-email scan, builds cleanup plan |
| `yes` | Confirms and runs the pending scan/action |
| `move trash` | Moves safe trash candidates to Gmail Trash (requires plan) |
| `cleanup status` | Shows current cleanup progress |
| `cancel cleanup` | Cancels in-progress cleanup |
| `sort all` | 5-email batch sort (read-only) |
| `continue sorting` | Advance to next batch using saved cursor |
| `queue` / `next` / `status` | Read-only info commands |
| `ping` | Health check |

## Cloud Deployment — Render Background Worker

GitHub repo: https://github.com/RyanRFrechette/inbox-scout

### Build & start commands

| | Command |
|---|---|
| Build | `pip install -r requirements.txt` |
| Start | `python -m inbox_scout.telegram_watch` |
| PYTHONPATH | `src` |

### Required secrets (set in Render dashboard — never commit)

| Env var | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Atlas bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID (numeric) |
| `GMAIL_TOKEN_JSON` | base64-encoded `token.json` (Gmail OAuth refresh token) |

The code reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from env vars first, falling back to local files for development.

### Persistent disk

Render's ephemeral filesystem loses `data/logs/` and `data/plans/` on every redeploy.
Attach a **1 GB persistent disk** mounted at `/opt/render/project/src/data` (configured in `render.yaml`).

### Known limitations for cloud

| Limitation | Impact | Fix required |
|---|---|---|
| Gmail OAuth tokens can't be refreshed interactively | Must pre-provision `token.json` via a startup wrapper that decodes `GMAIL_TOKEN_JSON` | Startup entrypoint script |
| Ollama (AI classifier) not available on Render | Classification falls back to rule-based only — no Gmail safety impact | Optional: swap to a cloud LLM |
| `telegram_watch.py` stale-watcher cleanup uses PowerShell | Fails silently on Linux; watcher still starts | Port to `psutil` or `pkill` |

### Deploy checklist (portfolio demo)

- [ ] Push latest `master` to GitHub
- [ ] Create Render Background Worker from repo
- [ ] Set `PYTHONPATH=src` env var
- [ ] Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets
- [ ] Encode `token.json` → base64 → set as `GMAIL_TOKEN_JSON`
- [ ] Add startup wrapper to decode `GMAIL_TOKEN_JSON` to `data/token.json`
- [ ] Attach 1 GB persistent disk at `/opt/render/project/src/data`
- [ ] Deploy and send `ping` from Telegram — expect `pong`
- [ ] Send `status` — expect inbox summary
