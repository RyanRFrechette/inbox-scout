# Inbox Scout - Project State

Last updated: 2026-05-14 (continuation cursor fix — pre-Phase 13Y)

## Current location
C:\Users\ryanr\inbox-scout

## Current safety mode
READ-ONLY ONLY

Inbox Scout currently does NOT:
- Archive emails
- Delete emails
- Apply Gmail labels
- Send replies
- Modify Gmail in any way

## Completed phases

### Phase 0 - Project setup
Status: COMPLETE

Completed:
- Created project folder
- Created Python virtual environment
- Installed dependencies
- Set up project structure

### Phase 1 - Gmail read-only connection
Status: COMPLETE

Completed:
- Gmail OAuth connected
- token.json exists
- Gmail read-only access works

### Phase 2 - Inbox fetcher
Status: COMPLETE

Completed:
- Can fetch recent Gmail inbox messages
- Can read sender, subject, date, snippet/body basics

### Phase 3 - Rule-based classifier
Status: COMPLETE

Completed:
- Emails can be categorized with local rules
- Protected categories are preserved
- Risk/manual-review logic exists

### Phase 4 - AI classifier
Status: COMPLETE

Completed:
- Ollama/qwen3:8b classifier works
- AI classification can assist rule-based results
- Classification history exists

### Phase 5 - Report mode
Status: IN PROGRESS, MOSTLY WORKING

Completed:
- Markdown reports generate
- JSON reports generate
- Grouped report summaries work
- Report shows read-only safety status
- Report shows manual-review count
- Report shows low-risk archive-later count
- Test report successfully scanned 5 emails

Latest known report result:
- Total emails scanned: 5
- Manual review required: 3
- Low-risk / possible archive later: 2

Still needed:
- Confirm permanent PowerShell command: inboxreport
- Polish report formatting
- Add this PROJECT_STATE.md update habit after each completed step

## Current next step
Confirm the `inboxreport` command works from a fresh PowerShell window.

## Future phases

### Phase 6 - Local safe review queue
Status: NOT STARTED

Goal:
Create a local review queue where emails can be marked as keep, archive later, ignore, or protected without changing Gmail.

### Phase 7 - Gmail label mode
Status: NOT STARTED

Goal:
Upgrade Gmail permissions from read-only to modify scope so Inbox Scout can apply labels safely.

### Phase 8 - Approve-to-archive
Status: NOT STARTED

Goal:
Allow approved low-risk emails to be archived only after manual confirmation.

### Phase 9 - Atlas/Telegram control
Status: NOT STARTED

Goal:
Control Inbox Scout through Atlas or Telegram commands.

### Phase 10 - Approve-to-trash
Status: NOT STARTED

Goal:
Allow manually approved trash actions for obvious junk only.

### Phase 11 - Guarded auto-trash
Status: NOT STARTED

Goal:
Optional final phase. Auto-trash only extremely obvious junk with strict protected-category rules.

## Permanent protected/manual-review categories

Never auto-archive or auto-delete without review:
- Financial
- Legal
- Medical
- Tax
- Password/security
- Job/interview
- Client/business
- Invoice/payment
- Family
- Warranty/support
- Refunds/returns
- Collections/balances
- Account access

## Completed step - 2026-05-07
Confirmed permanent PowerShell command:

inboxreport

Result:
- Opens the newest Inbox Scout Markdown report in Notepad
- Latest report shortcut is working
- No Gmail changes are made
- Project remains read-only


## Completed step - 2026-05-07
Confirmed permanent PowerShell command:

inboxreport

Result:
- Opens the newest Inbox Scout Markdown report in Notepad
- Latest report shortcut is working
- No Gmail changes are made
- Project remains read-only


## Completed step - 2026-05-07
Polished Phase 5 Markdown report formatting.

Result:
- Updated make_markdown_report() in src\inbox_scout\report_mode.py
- Added table of contents
- Added clean run settings table
- Added safety status table
- Added summary table
- Added action bucket table
- Added cleaner category sections
- Added email detail tables
- Generated a test report with --limit 5
- No Gmail changes were made


## Phase 5 final status - 2026-05-07
Status: COMPLETE

Completed:
- Report mode works
- Markdown reports generate
- JSON reports generate
- Latest report shortcut works with `inboxreport`
- Report formatting has been polished
- Reports include safety status, summary, action buckets, category sections, and email detail tables
- Tested with --limit 5
- Project remains read-only
- No Gmail changes were made

Next phase:
Phase 6 - Local safe review queue

Goal:
Create a local review queue where Inbox Scout can save email decisions locally first:
- keep
- ignore
- review later
- possible archive later
- protected/manual review

Important:
Phase 6 still does NOT change Gmail. It only creates a local review system.


## Completed step - Phase 6
Created first local safe review queue module.

Result:
- Created src\inbox_scout\review_queue.py
- Reads newest inbox_report_*.json
- Creates local review queue JSON
- Saves queue files inside data\review_queue
- Creates latest_queue.json
- Adds local-only decisions
- Does not modify Gmail
- No archive/delete/label/reply actions exist in this phase


## Completed step - Phase 6
Created local queue viewer.

Result:
- Created src\inbox_scout\queue_viewer.py
- Reads data\review_queue\latest_queue.json
- Displays queued emails in a Rich terminal table
- Shows queue ID, local decision, risk, category, sender, and subject
- Still local-only
- No Gmail changes were made


## Completed step - Phase 6
Created permanent PowerShell shortcut: inboxqueue

Result:
- inboxqueue opens the latest local review queue in terminal
- Uses queue_viewer.py
- Still local-only
- No Gmail changes were made


## Completed step - Phase 6
Created local queue decision updater.

Result:
- Created src\inbox_scout\queue_decision.py
- Can update local_decision by queue ID
- Supports keep, ignore, review_later, possible_archive_later, protected_review
- Writes local decision notes
- Writes local decision_log.jsonl
- Test updated queue item 3 locally
- Still local-only
- No Gmail changes were made


## Completed step - Phase 6
Created permanent PowerShell shortcut: inboxdecide

Result:
- inboxdecide can update local queue decisions by ID
- Supports keep, ignore, review_later, possible_archive_later, protected_review
- Tested shortcut on queue item 3
- Still local-only
- No Gmail changes were made


## Completed step - Phase 6
Created individual queue item viewer.

Result:
- Created src\inbox_scout\queue_item.py
- Created permanent PowerShell shortcut: inboxitem
- inboxitem -Id NUMBER shows detailed local queue item info
- Shows decision, category, risk, confidence, sender, subject, reason, suggested action, and snippet
- Still local-only
- No Gmail changes were made


## Completed step - Phase 6
Fixed queue item viewer boolean display.

Result:
- Updated clean() in src\inbox_scout\queue_item.py
- False values now display as False instead of blank
- inboxitem still works
- Still local-only
- No Gmail changes were made


## Completed step - Phase 6
Created next pending queue item command.

Result:
- Created src\inbox_scout\queue_next.py
- Created permanent PowerShell shortcut: inboxnext
- inboxnext shows the next pending_review or review_later item
- Shows decision examples for inboxdecide
- Still local-only
- No Gmail changes were made


## Phase 6 final status
Status: COMPLETE

Completed:
- Created local safe review queue
- Created latest_queue.json
- Created inboxqueue shortcut
- Created inboxitem shortcut
- Created inboxdecide shortcut
- Created inboxnext shortcut
- Local decision updates work
- Full local triage loop passed
- No pending local review items remain
- Protected/manual review items stayed protected
- Still local-only
- No Gmail changes were made

Next phase:
Phase 7 - Gmail label/permission preflight

Goal:
Safely inspect current Gmail OAuth permissions before adding any Gmail modify abilities.


## Completed step - Phase 7
Created Gmail scope preflight checker.

Result:
- Created src\inbox_scout\scope_check.py
- Checks token.json
- Shows whether gmail.readonly exists
- Shows whether gmail.modify exists
- Does not modify Gmail
- No archive/delete/label/reply actions were performed


## Completed step - Phase 7
Updated Gmail auth to support separate readonly and modify modes.

Result:
- Backed up gmail_auth.py
- Added READONLY_SCOPES
- Added MODIFY_SCOPES
- Added separate token files:
  - token.json for readonly
  - token_modify.json for modify
- Default mode remains readonly
- Tested readonly Gmail profile connection
- No Gmail changes were made


## Completed step - Phase 7
Updated Gmail scope checker and created inboxscope shortcut.

Result:
- Updated src\inbox_scout\scope_check.py
- Checks token.json for readonly scope
- Checks token_modify.json for modify scope
- Created permanent PowerShell shortcut: inboxscope
- No Gmail changes were made


## Completed step - Phase 7
Created Gmail modify token.

Result:
- Created src\inbox_scout\modify_token_setup.py
- Browser opened for Gmail modify permission
- token_modify.json should now exist
- inboxscope checks readonly and modify tokens
- No Gmail changes were made


## Completed step - Phase 7
Created Gmail label manager in dry-run mode.

Result:
- Created src\inbox_scout\label_manager.py
- Uses Gmail modify token only to inspect labels
- Planned Inbox Scout labels:
  - InboxScout/Protected Review
  - InboxScout/Possible Archive Later
  - InboxScout/Keep
  - InboxScout/Review Later
  - InboxScout/Ignore
- Ran dry-run mode only
- No labels were created
- No emails were labeled, archived, deleted, or replied to


## Completed step - Phase 7
Created Inbox Scout Gmail labels.

Result:
- Created missing Gmail labels:
  - InboxScout/Protected Review
  - InboxScout/Possible Archive Later
  - InboxScout/Keep
  - InboxScout/Review Later
  - InboxScout/Ignore
- No emails were labeled
- No emails were archived
- No emails were deleted
- No replies were sent


## Completed step - Phase 7
Verified Inbox Scout Gmail labels exist after creation.

Result:
- Ran label manager dry-run after label creation
- Confirmed InboxScout labels exist
- No emails were labeled
- No emails were archived
- No emails were deleted
- No replies were sent


## Completed step - Phase 7
Created Gmail label applier dry-run.

Result:
- Created src\inbox_scout\label_applier.py
- Maps local queue decisions to InboxScout Gmail labels
- Ran dry-run only
- Previewed which labels would be applied
- No labels were applied
- No emails were archived
- No emails were deleted
- No replies were sent


## Completed step - Phase 7
Applied Inbox Scout Gmail labels to queued emails.

Result:
- Applied labels based on latest local queue decisions
- protected_review emails received InboxScout/Protected Review
- possible_archive_later emails received InboxScout/Possible Archive Later
- No emails were archived
- No emails were deleted
- No replies were sent


## Completed step - Phase 7
Updated inboxitem to show Gmail label status.

Result:
- Updated src\inbox_scout\queue_item.py
- inboxitem now displays Gmail label applied
- inboxitem now displays Gmail action type
- Updated local latest_queue.json to mark label_applied_only where labels were already applied
- No emails were archived
- No emails were deleted
- No replies were sent


## Phase 7 final status
Status: COMPLETE

Completed:
- Gmail modify token exists
- InboxScout Gmail labels exist
- Labels were applied to queued emails
- inboxitem now shows Gmail label status
- No emails were archived
- No emails were deleted
- No replies were sent

Next phase:
Phase 8 - Archive dry-run and approval workflow

Goal:
Preview archive candidates before any Gmail archive action is allowed.


## Completed step - Phase 8
Created archive dry-run planner.

Result:
- Created src\inbox_scout\archive_planner.py
- Checks latest local queue
- Marks only low-risk possible_archive_later items as WOULD ARCHIVE
- Protected/manual review items are skipped
- Dry-run only
- No emails were archived
- No emails were deleted
- No replies were sent


## Completed step - Phase 8
Created permanent PowerShell shortcut: inboxarchiveplan

Result:
- inboxarchiveplan runs the archive dry-run planner
- Shows which emails would be archived
- Protected/manual-review emails stay skipped
- No emails were archived
- No emails were deleted
- No replies were sent


## Completed step - Phase 8
Created guarded archive runner in dry-run mode.

Result:
- Created src\inbox_scout\archive_runner.py
- Dry-run previews archive actions
- Only possible_archive_later items with risk <= 40 can be archived
- Manual/protected items are skipped
- No emails were archived
- No emails were deleted
- No replies were sent


## Completed step - Phase 8
Created permanent PowerShell shortcut: inboxarchive

Result:
- inboxarchive runs guarded archive runner in dry-run mode by default
- inboxarchive -Apply is required to actually archive eligible emails
- Tested dry-run mode
- No emails were archived
- No emails were deleted
- No replies were sent


## Completed step - Phase 8
Applied guarded archive action.

Result:
- Ran inboxarchive -Apply
- Archived exactly 2 eligible emails:
  - Queue item 3
  - Queue item 4
- Skipped 3 protected/manual-review emails
- No emails were deleted
- No replies were sent
- Protected emails were not touched


## Phase 8 final status
Status: COMPLETE

Completed:
- Guarded archive apply mode worked
- Archived exactly 2 eligible emails
- Protected/manual-review emails stayed untouched
- Re-running inboxarchive skips already archived items
- No emails were deleted
- No replies were sent

Next:
Run a fresh bigger inbox scan and create the next local review queue.


## Completed step - Trash/delete planning
Created trash planner dry-run.

Result:
- Created src\inbox_scout\trash_planner.py
- Dry-run only
- Only future items marked ignore can become trash candidates
- Only Promotion/Newsletter categories can be trash candidates
- Manual/protected/keep/review_later items are skipped
- No emails were trashed
- No emails were permanently deleted
- No replies were sent


## Completed step - Trash/delete planning
Created permanent PowerShell shortcut: inboxtrashplan

Result:
- inboxtrashplan runs the trash planner dry-run
- Shows future trash candidates
- Requires items to be marked ignore before trash eligibility
- Protected/manual-review items stay skipped
- No emails were trashed
- No emails were permanently deleted
- No replies were sent


## Phase 9 final status - 2026-05-08
Status: COMPLETE

Completed:
- Created guarded trash runner: src\inbox_scout\trash_runner.py
- Created permanent PowerShell shortcut: inboxtrash
- inboxtrash runs dry-run mode by default
- inboxtrash -Apply is required to move eligible emails to Gmail Trash
- Fixed inboxtrash to use the project .venv Python
- Added extra protected keyword safety checks
- Debt/collection-like emails are blocked even if categorized as Promotion
- Tested dry-run with 25-email queue
- Marked queue item 17 as ignore for controlled trash test
- Dry-run showed only item 17 as WOULD TRASH
- Apply mode moved exactly item 17 to Gmail Trash
- No permanent deletes happened
- Re-running inboxtrash showed item 17 skipped as already marked trashed locally
- Protected/manual-review emails stayed untouched
- Gmail action type for item 17 is now trashed
- Gmail action taken for item 17 is now True

Final Phase 9 safety result:
- Would trash: 0 after verification
- Trashed: 0 after verification
- Skipped: 25 after verification
- Permanent delete: 0

Next phase:
Phase 10 - Mark-as-read system

Goal:
Build a dry-run-first system that can mark safe handled emails as read after they have already been archived or trashed.

Important:
Do not mark protected/manual-review emails read automatically.
Do not run full all-unread cleanup yet.
Do not permanently delete anything yet.

## Phase 10 final status - 2026-05-08
Status: COMPLETE

Completed:
- Created mark-as-read planner: src\inbox_scout\mark_read_planner.py
- Created permanent PowerShell shortcut: inboxmarkreadplan
- Created guarded mark-as-read runner: src\inbox_scout\mark_read_runner.py
- Created permanent PowerShell shortcut: inboxmarkread
- inboxmarkread runs dry-run mode by default
- inboxmarkread -Apply is required to actually mark eligible emails as read
- Mark-as-read only allows emails already safely handled by archive or trash
- Protected/manual-review emails are skipped
- Low-risk unhandled emails are skipped until archived or trashed first
- Apply mode marked exactly queue item 17 as read
- Re-running inboxmarkread showed item 17 skipped as already marked read locally
- inboxitem now displays mark-read fields:
  - Gmail marked read
  - Gmail read action type
  - Gmail read action taken
  - Gmail marked read at
- No protected emails were marked read
- No emails were permanently deleted
- No replies were sent

Final Phase 10 safety result:
- Would mark read: 0 after verification
- Marked read: 0 after verification
- Skipped: 25 after verification
- Gmail changes: 0 after verification

Next phase:
Phase 11 - Pagination and batch engine

Goal:
Allow Inbox Scout to scan multiple pages of unread Inbox emails safely without running full cleanup yet.

Important:
Do not run full all-unread Inbox cleanup yet.
Do not permanently delete anything yet.
Do not bypass Telegram control.

## Phase 11A status - 2026-05-08
Status: COMPLETE

Completed:
- Created pagination probe: src\inbox_scout\pagination_probe.py
- Created permanent PowerShell shortcut: inboxpageprobe
- inboxpageprobe uses the project .venv Python
- Pagination probe supports:
  - Page size control
  - Max message safety limit
  - Unread-only mode
  - Optional days filter
- Test command succeeded:
  inboxpageprobe -PageSize 10 -MaxMessages 25 -UnreadOnly
- Result:
  - Page 1 fetched 10 unread Inbox message IDs
  - Page 2 fetched 10 unread Inbox message IDs
  - Page 3 fetched 5 unread Inbox message IDs
  - Total fetched IDs: 25
  - Pages fetched: 3
  - More available after stop: True
- Gmail remained read-only
- No emails were archived, trashed, labeled, deleted, replied to, or marked read

Next step:
Phase 11B - Build paginated report fetcher

Goal:
Upgrade report fetching so Inbox Scout can scan multiple Gmail pages safely while still respecting a max-message limit.

Important:
Do not run full all-unread cleanup yet.
Do not apply Gmail actions from pagination.
Do not bypass Telegram control.

## Phase 11B status - 2026-05-08
Status: COMPLETE

Completed:
- Upgraded report_mode.py to support paginated Gmail fetching with --page-size
- Added visible AI classification progress logging
- Added AI timeout/error fallback so Ollama failures do not kill the report
- Fixed duplicate --page-size bug
- Confirmed 5-email verification works:
  python -m inbox_scout.report_mode --limit 5 --page-size 5 --unread-only --export both
- Result:
  - Fetched 5 unread Inbox emails
  - Fetched across 1 Gmail page
  - Classified all 5 emails
  - Generated JSON and Markdown reports
  - Manual review required: 3
  - Low-risk / possible archive later: 2
- Gmail changes: 0
- No emails were archived, trashed, labeled, deleted, replied to, or marked read

Testing rule going forward:
- Use --limit 5 --page-size 5 --unread-only by default
- Do not run large/full unread Inbox scans until the full system is complete

Next step:
Phase 11C - Generate a fresh 5-email local queue from the newest report and verify the queue still works with paginated reports.

## Phase 11C status - 2026-05-08
Status: COMPLETE

Completed:
- Generated a fresh local review queue from the newest 5-email paginated report
- Command used:
  python -m inbox_scout.review_queue --from-latest-report
- Queue file created:
  data\review_queue\inbox_queue_20260508_185644.json
- inboxqueue confirmed latest queue works
- Total queued emails: 5
- Protected/manual review: 3
- Pending low-risk review: 2
- Gmail changes: 0

Current queue:
- ID 1 protected_review - Bills/receipts - Amazon delivered receipt
- ID 2 pending_review - Promotion - Amazon promo
- ID 3 protected_review - Promotion - Vans promo, risk 90
- ID 4 pending_review - Newsletter - USPS Informed Delivery
- ID 5 protected_review - Finance - TD Bank payment alert

Testing rule remains:
- Continue using 5-email batches only until the full Inbox Scout system is complete.

Next step:
Phase 11D - Verify local decision flow still works on the fresh 5-email queue, then test label/archive/trash/mark-read gates only on approved safe items.

## Phase 11D status - 2026-05-08
Status: IN PROGRESS - SAFE STOPPING POINT

Completed this session:
- Fresh 5-email queue was created from paginated report mode.
- Queue had:
  - 5 total emails
  - 3 protected/manual-review emails
  - 2 pending low-risk emails
- Inspected queue item 2:
  - Amazon promo
  - Subject: Deals curated for you
  - Risk: 30
  - Manual review: False
- Inspected queue item 4:
  - USPS Informed Delivery daily digest
  - Subject: Your Daily Digest for Fri, 5/8 is ready to view
  - Risk: 30
  - Manual review: False
- Marked item 2 locally as possible_archive_later.
- Marked item 4 locally as possible_archive_later.
- Ran inboxarchive dry-run.
- Dry-run showed exactly:
  - WOULD ARCHIVE: ID 2 and ID 4
  - SKIP: ID 1, ID 3, ID 5
- Ran inboxarchive -Apply.
- Apply mode archived exactly 2 eligible emails:
  - ID 2 - Amazon promo - Deals curated for you
  - ID 4 - USPS Informed Delivery - Your Daily Digest for Fri, 5/8 is ready to view
- inboxitem -Id 2 verified:
  - Gmail action type: archived
  - Gmail action taken: True
- inboxitem -Id 4 verified:
  - Gmail action type: archived
  - Gmail action taken: True

Safety result:
- Archived emails: 2
- Protected emails skipped: 3
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0
- Full unread cleanup: NOT RUN
- Batch size rule: still locked to 5 emails at a time

Current safe stopping point:
Phase 11D archive apply is complete.
Do not continue tonight unless intentionally resuming the project.

Next step when resuming:
Run inboxmarkread dry-run to check whether archived IDs 2 and 4 are eligible to be marked read.

Next command:
inboxmarkread

Expected:
- WOULD MARK READ: ID 2 and ID 4
- SKIPPED: protected items

Only after reviewing dry-run:
inboxmarkread -Apply

Important:
Do not run full all-unread Inbox cleanup yet.
Do not permanently delete anything yet.
Do not bypass Telegram control.
Keep testing to 5 emails at a time until full project completion.

## Phase 11D final status - 2026-05-08
Status: COMPLETE

Completed:
- Fresh 5-email queue was tested end-to-end.
- Queue had:
  - 5 total emails
  - 3 protected/manual-review emails
  - 2 pending low-risk emails
- Inspected low-risk items:
  - ID 2 - Amazon promo - Deals curated for you
  - ID 4 - USPS Informed Delivery daily digest
- Marked ID 2 and ID 4 locally as possible_archive_later.
- Ran inboxarchive dry-run.
- Dry-run showed:
  - WOULD ARCHIVE: ID 2 and ID 4
  - SKIP: ID 1, ID 3, ID 5
- Ran inboxarchive -Apply.
- Archived exactly 2 eligible emails:
  - ID 2
  - ID 4
- Verified with inboxitem:
  - ID 2 Gmail action type: archived
  - ID 2 Gmail action taken: True
  - ID 4 Gmail action type: archived
  - ID 4 Gmail action taken: True
- Ran inboxmarkread dry-run.
- Dry-run showed:
  - WOULD MARK READ: ID 2 and ID 4
  - SKIP: ID 1, ID 3, ID 5
- Ran inboxmarkread -Apply.
- Marked exactly 2 eligible archived emails as read:
  - ID 2
  - ID 4
- Verified with inboxitem:
  - ID 2 Gmail marked read: True
  - ID 2 Gmail read action type: marked_read
  - ID 2 Gmail read action taken: True
  - ID 4 Gmail marked read: True
  - ID 4 Gmail read action type: marked_read
  - ID 4 Gmail read action taken: True
- Final inboxmarkread dry-run showed:
  - Would mark read: 0
  - Marked read: 0
  - Skipped: 5

Safety result:
- Archived emails: 2
- Marked read: 2
- Protected emails skipped: 3
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0
- Full unread cleanup: NOT RUN
- Batch size rule: still locked to 5 emails at a time

Phase 11D is complete.

Next recommended phase:
Phase 12 - Action log and safety audit

Goal:
Create an audit command that summarizes what Inbox Scout has done:
- archived emails
- trashed emails
- marked-read emails
- skipped protected emails
- errors
- timestamps
- Gmail changes made

Important:
Continue using 5-email batches only until full project completion.
Do not run full all-unread Inbox cleanup yet.
Do not permanently delete anything yet.
Do not bypass Telegram control.

## Phase 12A status - 2026-05-08
Status: COMPLETE

Completed:
- Created safety audit module:
  src\inbox_scout\audit.py
- Created permanent PowerShell shortcut:
  inboxaudit
- inboxaudit uses the project .venv Python
- inboxaudit reads:
  - latest_queue.json
  - trash_actions.jsonl
  - mark_read_actions.jsonl
  - decision_log.jsonl
- inboxaudit shows:
  - latest queue item count
  - protected/manual-review count
  - archived count
  - trashed count
  - marked-read count
  - trash log entries
  - mark-read log entries
  - local decision log entries
  - permanent deletes found
  - replies sent found
  - Gmail changes made by audit
- Test result:
  - Latest queue items: 5
  - Protected/manual-review: 3
  - Archived in latest queue: 2
  - Marked read in latest queue: 2
  - Trashed in latest queue: 0
  - Permanent deletes found: 0
  - Replies sent found: 0
  - Gmail changes made by audit: 0
- inboxaudit correctly shows:
  - ID 2 archived and marked read
  - ID 4 archived and marked read
  - ID 1, 3, and 5 protected/untouched

Next step:
Phase 12B - Improve audit logging by adding archive_actions.jsonl support so archive actions are logged like trash and mark-read actions.

Important:
Continue using 5-email batches only until full project completion.
Do not run full all-unread Inbox cleanup yet.
Do not permanently delete anything yet.
Do not bypass Telegram control.

## Phase 12B status - 2026-05-08
Status: COMPLETE

Completed:
- Updated archive_runner.py to support archive action logging.
- Added archive log file:
  data\logs\archive_actions.jsonl
- Future archive dry-runs will log WOULD ARCHIVE.
- Future archive apply actions will log ARCHIVED.
- Backfilled existing archived queue items from latest_queue.json:
  - ID 2 - Amazon promo - Deals curated for you
  - ID 4 - USPS Informed Delivery daily digest
- Backfill was local-only.
- Backfill did not touch Gmail.
- Updated inboxaudit to read archive_actions.jsonl.
- inboxaudit now shows:
  - Archive log entries
  - Archive Log Counts
  - Trash Log Counts
  - Mark-Read Log Counts
  - Latest Queue Gmail Action Status
- Test result:
  - Archive log entries: 2
  - ARCHIVED_BACKFILLED_FROM_QUEUE: 2
  - Latest queue items: 5
  - Protected/manual-review: 3
  - Archived in latest queue: 2
  - Marked read in latest queue: 2
  - Permanent deletes found: 0
  - Replies sent found: 0
  - Gmail changes made by audit: 0

Safety result:
- No Gmail changes were made by the backfill.
- No emails were deleted.
- No emails were permanently deleted.
- No replies were sent.
- Full unread cleanup was NOT run.

Next recommended step:
Phase 12C - Decide whether to improve skipped/protected audit detail or move to Phase 13 Telegram control.

Important:
Continue using 5-email batches only until full project completion.
Do not run full all-unread Inbox cleanup yet.
Do not permanently delete anything yet.
Do not bypass Telegram control.

## Phase 12C status - 2026-05-08
Status: COMPLETE

Completed:
- Enhanced inboxaudit with better safety detail.
- Added latest queue decision counts.
- Added latest queue category counts.
- Added Protected / Untouched Items table.
- Added Handled Items table.
- inboxaudit now clearly shows:
  - what was archived
  - what was marked read
  - what stayed protected
  - category breakdown
  - decision breakdown
  - audit made 0 Gmail changes

Test result:
- Latest queue items: 5
- Protected/manual-review: 3
- Archived: 2
- Marked read: 2
- Protected/untouched:
  - ID 1 - Amazon receipt
  - ID 3 - Vans high-risk promotion
  - ID 5 - TD Bank finance alert
- Handled:
  - ID 2 - archived + marked read
  - ID 4 - archived + marked read
- Permanent deletes found: 0
- Replies sent found: 0
- Gmail changes made by audit: 0

Phase 12 audit system is now strong enough to support Telegram control.

Next recommended phase:
Phase 13 - Telegram control layer

Goal:
Control Inbox Scout from Telegram with safe commands like:
- status
- audit
- latest queue
- next item
- approve archive
- approve trash
- mark read
- stop/cancel

Important:
Continue using 5-email batches only until full project completion.
Do not run full all-unread Inbox cleanup yet.
Do not permanently delete anything yet.
Telegram must use approval gates before Gmail changes.

## Phase 12C status - 2026-05-08
Status: COMPLETE

Completed:
- Enhanced inboxaudit with better safety detail.
- Added latest queue decision counts.
- Added latest queue category counts.
- Added Protected / Untouched Items table.
- Added Handled Items table.
- inboxaudit now clearly shows:
  - what was archived
  - what was marked read
  - what stayed protected
  - category breakdown
  - decision breakdown
  - audit made 0 Gmail changes

Test result:
- Latest queue items: 5
- Protected/manual-review: 3
- Archived: 2
- Marked read: 2
- Protected/untouched:
  - ID 1 - Amazon receipt
  - ID 3 - Vans high-risk promotion
  - ID 5 - TD Bank finance alert
- Handled:
  - ID 2 - archived + marked read
  - ID 4 - archived + marked read
- Permanent deletes found: 0
- Replies sent found: 0
- Gmail changes made by audit: 0

Phase 12 audit system is now strong enough to support Telegram control.

Next recommended phase:
Phase 13 - Telegram control layer

Goal:
Control Inbox Scout from Telegram with safe commands like:
- status
- audit
- latest queue
- next item
- approve archive
- approve trash
- mark read
- stop/cancel

Important:
Continue using 5-email batches only until full project completion.
Do not run full all-unread Inbox cleanup yet.
Do not permanently delete anything yet.
Telegram must use approval gates before Gmail changes.

## Phase 13A/B status - 2026-05-08
Status: COMPLETE

Completed:
- Telegram bot token preflight passed.
- Telegram getMe returned OK for Atlas bot.
- Telegram chat ID found:
  8754933622
- Created local Telegram config:
  config\telegram_config.json
- Config includes:
  - telegram_chat_id
  - bot_name: Atlas
  - bot_username: ryan_atlas_ai_bot
  - project: Inbox Scout
  - gmail_actions_require_approval: true
  - batch_limit: 5
- Tested direct PowerShell Telegram sendMessage.
- Direct Telegram message arrived successfully.
- Created Python Telegram notifier module:
  src\inbox_scout\telegram_notifier.py
- Fixed UTF-8 BOM config issue by reading telegram_config.json with utf-8-sig.
- Python notifier test succeeded:
  Telegram send OK: True
- Atlas sent the Inbox Scout notifier test message successfully.

Safety result:
- Gmail changes: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Next step:
Phase 13C - Build Telegram status/audit sender so Inbox Scout can send status summaries to Telegram.

Important:
Telegram control must stay read-only first.
Approval gates must be added before any Telegram-triggered Gmail changes.
Continue using 5-email batches only until full project completion.

## Phase 13C status - 2026-05-08
Status: COMPLETE

Completed:
- Created Telegram status/audit sender:
  src\inbox_scout\telegram_status.py
- Telegram status reads local files only:
  - latest_queue.json
  - archive_actions.jsonl
  - trash_actions.jsonl
  - mark_read_actions.jsonl
  - decision_log.jsonl
- Telegram status sends:
  - current batch rule
  - latest queue count
  - protected/manual-review count
  - archived count
  - trashed count
  - marked-read count
  - decision counts
  - handled items
  - protected/untouched items
  - safety summary
- Test command succeeded:
  python -m inbox_scout.telegram_status
- Result:
  Telegram status send OK: True
- Telegram message was received successfully.

Safety result:
- Gmail changes: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Next step:
Phase 13D - Create permanent shortcut for Telegram status, then build a read-only Telegram command listener.

Important:
Telegram listener must start read-only.
No Telegram-triggered Gmail actions until approval gates are built.
Continue using 5-email batches only until full project completion.

## Phase 13D status - 2026-05-08
Status: COMPLETE

Completed:
- Created permanent PowerShell shortcut:
  inboxtelegramstatus
- inboxtelegramstatus runs:
  python -m inbox_scout.telegram_status
- Shortcut uses the project .venv Python.
- Test succeeded:
  Telegram status send OK: True
- Telegram status message was received in Atlas.
- Message includes:
  - batch rule
  - latest queue count
  - protected/manual-review count
  - archived count
  - trashed count
  - marked-read count
  - decision counts
  - handled items
  - protected/untouched items
  - safety summary

Safety result:
- Gmail changes: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Next step:
Phase 13E - Build read-only Telegram command listener.

Goal:
Allow Telegram messages like:
- status
- audit
- queue
- next
- help

Important:
Read-only listener first.
No Telegram-triggered Gmail actions yet.
Approval gates come later.
Continue using 5-email batches only until full project completion.

## Phase 13E status - 2026-05-08
Status: COMPLETE

Completed:
- Created read-only Telegram command listener:
  src\inbox_scout\telegram_listener.py
- Listener supports:
  - help
  - ping
  - status
  - audit
  - queue
  - next
- Ran listener offset initialization to ignore old messages.
- Tested Telegram commands successfully:
  - help replied with command list
  - ping replied with pong
  - status sent status/audit summary
  - queue sent latest 5-email queue
  - next returned no pending local review items
- Created permanent PowerShell shortcut:
  inboxtelegramlisten
- inboxtelegramlisten runs one read-only listener check:
  python -m inbox_scout.telegram_listener --once
- Shortcut test result:
  No new Telegram updates.

Safety result:
- Telegram listener is read-only
- Gmail changes: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0
- No Telegram-triggered Gmail actions exist yet

Phase 13E is complete.

Next phase:
Phase 13F - Telegram approval gate planning

Goal:
Design safe approval commands before allowing Telegram to trigger Gmail actions.

Possible future commands:
- approve archive ID
- approve trash ID
- approve markread ID
- cancel
- audit
- queue
- next

Important:
Do not let Telegram change Gmail until approval gates are built and tested in dry-run mode first.
Continue using 5-email batches only until full project completion.
Do not permanently delete anything yet.

## Phase 13E status - 2026-05-08
Status: COMPLETE

Completed:
- Created read-only Telegram command listener:
  src\inbox_scout\telegram_listener.py
- Listener supports:
  - help
  - ping
  - status
  - audit
  - queue
  - next
- Ran listener offset initialization to ignore old messages.
- Tested Telegram commands successfully:
  - help replied with command list
  - ping replied with pong
  - status sent status/audit summary
  - queue sent latest 5-email queue
  - next returned no pending local review items
- Created permanent PowerShell shortcut:
  inboxtelegramlisten
- inboxtelegramlisten runs one read-only listener check:
  python -m inbox_scout.telegram_listener --once
- Shortcut test result:
  No new Telegram updates.

Safety result:
- Telegram listener is read-only
- Gmail changes: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0
- No Telegram-triggered Gmail actions exist yet

Phase 13E is complete.

Next phase:
Phase 13F - Telegram approval gate planning

Goal:
Design safe approval commands before allowing Telegram to trigger Gmail actions.

Possible future commands:
- approve archive ID
- approve trash ID
- approve markread ID
- cancel
- audit
- queue
- next

Important:
Do not let Telegram change Gmail until approval gates are built and tested in dry-run mode first.
Continue using 5-email batches only until full project completion.
Do not permanently delete anything yet.

## Phase 13F status - 2026-05-08
Status: COMPLETE

Completed:
- Created Telegram approval dry-run planner:
  src\inbox_scout\telegram_approval.py
- Connected approval dry-run commands to Telegram listener.
- Telegram now understands:
  - approve archive ID
  - approve trash ID
  - approve markread ID
- Approval commands are dry-run only.
- No Telegram approval command can modify Gmail yet.
- Tested through Atlas:
  - approve trash 3 = BLOCKED because item is protected/manual-review
  - approve archive 2 = BLOCKED because Gmail action already taken locally
  - approve markread 4 = BLOCKED because item is already marked read locally
- Atlas replied correctly in Telegram for all tests.

Safety result:
- Gmail changes: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0
- Telegram approval system is still dry-run only

Next phase:
Phase 13G - Plan Telegram approval apply gates

Goal:
Allow Telegram to approve Gmail actions only after:
- dry-run approval passes
- item is low-risk
- item is not protected
- item has not already been handled
- command is explicit
- audit/logging is written

Important:
Keep apply gates dry-run-first.
Do not enable permanent delete yet.
Continue using 5-email batches only until full project completion.

## Phase 13G status - 2026-05-08
Status: COMPLETE

Completed:
- Created Telegram apply gate dry-run module:
  src\inbox_scout\telegram_apply_gate.py
- Connected apply commands to Telegram listener.
- Telegram now understands:
  - apply archive ID
  - apply trash ID
  - apply markread ID
- Apply gate is dry-run only.
- Real Gmail actions remain disabled by config:
  telegram_apply_enabled: false
- Permanent delete remains disabled:
  permanent_delete_enabled: false
- Tested through Atlas:
  - apply trash 3 = BLOCKED because item is protected/manual-review
  - apply archive 2 = BLOCKED because Gmail action already taken locally
  - apply markread 4 = BLOCKED because item is already marked read locally
- Atlas replied correctly in Telegram for all tests.

Safety result:
- Gmail changes: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0
- Telegram apply system is still dry-run only

Phase 13G is complete.

Next recommended phase:
Phase 13H - Safe Telegram apply execution planning

Goal:
Decide whether to enable real Telegram-triggered Gmail actions later for only:
- archive
- markread
- maybe trash

Important:
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep 5-email batch testing until the whole project is complete.

## Phase 13H status - 2026-05-08
Status: COMPLETE

Completed:
- Created Telegram two-step confirmation dry-run module:
  src\inbox_scout\telegram_confirm_gate.py
- Connected confirm/cancel commands to Telegram listener.
- Telegram now understands:
  - confirm archive ID
  - confirm trash ID
  - confirm markread ID
  - cancel
- Confirmation gate is dry-run only.
- Real Gmail actions remain disabled:
  telegram_apply_enabled: false
  telegram_confirm_enabled: false
- Permanent delete remains disabled:
  permanent_delete_enabled: false
- Two-step confirmation requirement is enabled:
  telegram_two_step_required: true
- Tested through Atlas:
  - confirm trash 3 = BLOCKED because item is protected/manual-review
  - confirm archive 2 = BLOCKED because Gmail action already taken locally
  - confirm markread 4 = BLOCKED because item is already marked read locally
  - cancel = safe cancellation message
- Atlas replied correctly in Telegram for all tests.

Safety result:
- Gmail changes: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0
- Telegram confirm system is still dry-run only

Phase 13H is complete.

Next recommended phase:
Phase 13I - Decide whether to enable safe Telegram execution for archive/markread only, or stop here and generate a fresh 5-email batch first.

Important:
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep 5-email batch testing until the whole project is complete.

## Fresh 5-email batch after Phase 13H - 2026-05-08
Status: VERIFIED

Completed:
- Generated a fresh 5-email unread Inbox report.
- Created a new local queue from the latest report.
- Queue file:
  data\review_queue\inbox_queue_20260508_201836.json
- Result:
  - Total queued emails: 5
  - Protected/manual review: 5
  - Pending low-risk review: 0
- inboxqueue confirmed all 5 items are protected_review.
- Telegram queue command confirmed Atlas reads the newest queue correctly.

Latest queue:
- ID 1 protected_review - Bills/receipts - Amazon delivered receipt
- ID 2 protected_review - Promotion - Vans promo, risk 90
- ID 3 protected_review - Finance - TD Bank payment alert
- ID 4 protected_review - Manual review - Amazon shipment tracking
- ID 5 protected_review - Manual review - Amazon shipment tracking

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Trashed emails: 0
- Marked read: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Decision:
Do not run archive, trash, or mark-read on this batch because there are no low-risk pending items.

Next options:
- Generate another 5-email batch later if a safe pending item is needed for future apply testing.
- Or move toward natural-language Telegram command interpretation while keeping all Gmail actions locked behind approval gates.

## Phase 13I-A status - 2026-05-08
Status: COMPLETE

Completed:
- Created natural language intent router:
  src\inbox_scout\natural_intent.py
- Connected natural language fallback to Telegram listener.
- Atlas now understands natural messages like:
  - sort my email please
  - clean up my inbox
  - show my queue
  - what needs review
  - inbox status
- Tested through Telegram:
  sort my email please
- Atlas understood the request as cleanup/sort intent.
- Atlas summarized the current 5-email batch:
  - Total emails: 5
  - Protected: 5
  - Pending review: 0
  - Possible archive later: 0
- Atlas explained the future safe flow:
  scan → show plan → ask approval → confirm → apply

Safety result:
- Gmail changes: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0
- Natural language cannot directly change Gmail yet.

Phase 13I-A is complete.

Next step:
Phase 13I-B - Make natural language responses more assistant-like and less technical while keeping all safety gates underneath.

## Phase 13I-B status - 2026-05-08
Status: COMPLETE - PAUSED HERE

Completed:
- Repaired natural_intent.py after a string syntax issue.
- Updated natural language responses to sound more assistant-like and less technical.
- Local test succeeded:
  python -m inbox_scout.natural_intent sort my email please
- Test response confirmed:
  - Atlas understood the request as sorting/cleaning email.
  - Atlas checked the current batch.
  - Current batch has 5 emails.
  - All 5 look protected or worth reviewing.
  - Atlas refused to archive, trash, or mark anything read.
  - Atlas confirmed: I did not touch Gmail.

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Trashed emails: 0
- Marked read: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Current pause point:
Phase 13I-B natural language polish works locally.
No more steps tonight.

Future resume point:
Test the polished natural response through Telegram, then continue improving natural-language control while keeping approval and confirmation gates underneath.

Important:
Do not enable Telegram-triggered Gmail execution yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep 5-email batch testing until the whole project is complete.

## Phase 13I-B Telegram verification - 2026-05-09
Status: COMPLETE

Completed:
- Tested polished natural-language response through Telegram.
- Telegram message used:
  sort my email please
- Atlas correctly understood the request as an inbox cleanup/sort request.
- Atlas responded naturally instead of using technical command language.
- Atlas checked the current batch.
- Atlas reported:
  - 5 emails in current batch
  - all 5 look protected or worth reviewing
  - nothing looks safe enough to auto-handle
- Atlas refused to archive, trash, or mark anything read.
- Atlas confirmed:
  I did not touch Gmail.

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Trashed emails: 0
- Marked read: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Phase 13I-B is fully verified.

Next future phase:
Phase 13I-C - Continue improving natural Telegram control so Atlas can understand more casual phrases while keeping approval and confirmation gates underneath.

Important:
Do not enable Telegram-triggered Gmail execution yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep 5-email batch testing until the whole project is complete.

## Phase 13I-C status - 2026-05-09
Status: STARTED - SAFE STOPPING POINT

Completed:
- Created natural sort command parser:
  src\inbox_scout\sort_command_parser.py
- Local parser test succeeded using:
  python -m inbox_scout.sort_command_parser "sort 25 emails"
- Parser correctly returned:
  - intent: sort
  - limit: 25
  - sort_all: false
  - target: unread_inbox
  - dry_run: true
  - trash_review_mode: true
  - allow_trash_plan: false
  - allow_permanent_delete: false
  - confidence: 90
  - reason: Parsed a safe inbox sorting request.

What this means:
- Inbox Scout can now begin understanding natural commands like:
  - sort 25 emails
  - sort 100 emails
  - sort all
  - clean up my inbox
  - move junk to trash
- This parser only translates the user request into a safe structured command.
- It does not scan Gmail by itself.
- It does not archive anything.
- It does not trash anything.
- It does not mark anything read.
- It does not permanently delete anything.

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Trashed emails: 0
- Marked read: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Important permanent-delete note:
- The future natural command feature for phrases like:
  - delete everything in trash
  - empty my trash
  - clear the trash folder
  - permanently delete the emails in trash
- is reserved for Phase 14 only.
- It must remain disabled for now.
- Natural language may eventually trigger a permanent-delete PLAN only.
- Permanent delete must require exact nuclear confirmation with the Trash email count.
- Do not build or enable this until the end-stage permanent-delete phase.

Current pause point:
Phase 13I-C parser exists and passed the first safe test.

Future resume point:
Continue Phase 13I-C by testing more natural parser phrases before building the sort planner.

Good future parser tests:
- sort 5 emails
- sort 25 emails
- sort 100 emails
- sort all
- clean up my unread inbox
- move junk to trash so I can review it
- sort my inbox but do not delete anything

Next future build after parser testing:
Phase 13J - Build sort planner dry-run.

Planned first Phase 13J module:
src\inbox_scout\sort_planner.py

Important:
Do not enable Telegram-triggered Gmail execution yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep 5-email or dry-run testing until the whole project is complete.

## Phase 13I-C parser verification - 2026-05-10
Status: COMPLETE

Completed:
- Tested natural sort command parser with normal sorting language.
- Tested safe trash-review language.
- Tested permanent-delete language.
- Confirmed parser stays dry-run and planner-only.

Verified parser phrases:
- sort 5 emails
- sort 25 emails
- sort 100 emails
- sort all
- clean up my unread inbox
- move junk to trash so I can review it
- sort my inbox but do not delete anything
- empty my trash

Key results:
- Normal sort requests parse as:
  - intent: sort
  - target: unread_inbox
  - dry_run: true
  - trash_review_mode: true
  - allow_trash_plan: false
  - allow_permanent_delete: false
- Safe trash-review language now parses correctly as a sort/planning request.
- Permanent-delete language is blocked as:
  - intent: permanent_delete_plan_only
  - target: trash
  - allow_permanent_delete: false
  - reason: Phase 14 only and disabled

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Trashed emails: 0
- Marked read: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Phase 13I-C is complete.

Next phase:
Phase 13J - Build sort planner dry-run.

Planned module:
src\inbox_scout\sort_planner.py

Important:
Do not enable Telegram-triggered Gmail execution yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep 5-email or dry-run testing until the whole project is complete.


## Phase 13J sort planner dry-run verification - 2026-05-10
Status: COMPLETE

Completed:
- Created sort planner dry-run module:
  src\inbox_scout\sort_planner.py
- Connected sort planner to natural command parser.
- Tested normal sorting language.
- Tested safe trash-review language.
- Tested unclear/unknown language.
- Tested permanent-delete language.
- Tested sort-all language.

Verified planner phrases:
- sort 25 emails
- empty my trash
- move junk to trash so I can review it
- banana sandwich
- sort all

Key results:
- Normal sort request returned:
  - status: planned
  - parsed_intent: sort
  - limit: 25
  - target: unread_inbox
  - dry_run: true
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false

- Permanent-delete request returned:
  - status: blocked_phase_14_only
  - parsed_intent: permanent_delete_plan_only
  - target: trash
  - dry_run: true
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false
  - safety_note: Permanent delete remains disabled.

- Safe trash-review request returned:
  - status: planned
  - parsed_intent: sort
  - limit: 25
  - target: unread_inbox
  - dry_run: true
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false

- Unknown language returned:
  - status: blocked
  - parsed_intent: unknown
  - target: unknown
  - dry_run: true
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false

- Sort-all request returned:
  - status: planned
  - parsed_intent: sort
  - limit: null
  - sort_all: true
  - target: unread_inbox
  - dry_run: true
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false

Safety result:
- Gmail scans from planner: 0
- Gmail changes: 0
- Archived emails: 0
- Trashed emails: 0
- Marked read: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Phase 13J is complete.

Next phase:
Phase 13K - Connect natural sort planner to a future dry-run scan/queue workflow.

Goal of next phase:
- Convert natural commands like "sort 5 emails" or "sort 25 emails" into a safe planned workflow.
- Keep Gmail execution disabled.
- Keep permanent delete disabled.
- Prefer 5-email test batches until the full project is complete.
- Do not run full all-unread cleanup yet.

Important:
Do not enable Telegram-triggered Gmail execution yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep 5-email or dry-run testing until the whole project is complete.


## Phase 13K sort workflow dry-run verification - 2026-05-10
Status: COMPLETE

Completed:
- Created sort workflow dry-run module:
  src\inbox_scout\sort_workflow.py
- Connected workflow planner to sort planner.
- Tested small batch sorting language.
- Tested sort-all language.
- Tested permanent-delete language.
- Tested safe trash-review language.

Verified workflow phrases:
- sort 5 emails
- sort all
- empty my trash
- move junk to trash so I can review it

Key results:
- Small batch request returned:
  - status: workflow_planned
  - requested_limit: 5
  - target: unread_inbox
  - workflow_mode: small_batch_dry_run_plan
  - gmail_scan_enabled: false
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false

- Sort-all request returned:
  - status: workflow_planned
  - sort_all: true
  - workflow_mode: sort_all_dry_run_only
  - gmail_scan_enabled: false
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false
  - recommended 5-email test batch instead

- Permanent-delete request returned:
  - status: blocked_phase_14_only
  - target: trash
  - workflow_mode: blocked
  - gmail_scan_enabled: false
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false

- Safe trash-review request returned:
  - status: workflow_planned
  - requested_limit: 25
  - target: unread_inbox
  - workflow_mode: small_batch_dry_run_plan
  - gmail_scan_enabled: false
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false

Safety result:
- Gmail scans from workflow: 0
- Gmail changes: 0
- Archived emails: 0
- Trashed emails: 0
- Marked read: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Phase 13K is complete.

Next phase:
Phase 13L - Connect natural workflow planning to a future dry-run scan/queue command.

Goal of next phase:
- Keep natural language input.
- Keep default testing at 5 emails.
- Prepare command flow for future:
  natural request -> workflow plan -> report generation -> local queue creation.
- Do not enable actual Gmail changes yet.

Important:
Do not enable Telegram-triggered Gmail execution yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep 5-email or dry-run testing until the whole project is complete.


## Phase 13L scan/queue command planner verification - 2026-05-10
Status: COMPLETE

Completed:
- Created scan/queue command planner:
  src\inbox_scout\sort_scan_queue_plan.py
- Connected natural workflow planning to future report/queue command suggestions.
- Kept execution disabled.
- Verified default safe testing stays at 5 emails unless the user explicitly requests a number.
- Verified sort-all remains blocked.
- Verified permanent-delete language remains blocked.
- Verified safe trash-review language maps to a 5-email dry-run command plan.

Verified command-planner phrases:
- sort 5 emails
- sort all
- empty my trash
- move junk to trash so I can review it

Key results:
- "sort 5 emails" returned:
  - status: commands_planned
  - requested_limit: 5
  - workflow_mode: small_batch_dry_run_plan
  - report_command: .\.venv\Scripts\python.exe -m inbox_scout.report_mode --limit 5 --unread-only --export both
  - queue_command: .\.venv\Scripts\python.exe -m inbox_scout.review_queue --from-latest-report
  - commands_are_suggestions_only: true
  - gmail_scan_enabled_now: false
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false

- "sort all" returned:
  - status: blocked_large_scan
  - workflow_mode: sort_all_dry_run_only
  - report_command: null
  - queue_command: null
  - gmail_scan_enabled_now: false
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false

- "empty my trash" returned:
  - status: blocked_phase_14_only
  - workflow_mode: blocked
  - report_command: null
  - queue_command: null
  - gmail_scan_enabled_now: false
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false

- "move junk to trash so I can review it" returned:
  - status: commands_planned
  - requested_limit: 5
  - workflow_mode: small_batch_dry_run_plan
  - report_command: .\.venv\Scripts\python.exe -m inbox_scout.report_mode --limit 5 --unread-only --export both
  - queue_command: .\.venv\Scripts\python.exe -m inbox_scout.review_queue --from-latest-report
  - commands_are_suggestions_only: true
  - gmail_scan_enabled_now: false
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false

Safety result:
- Gmail scans executed by planner: 0
- Gmail changes: 0
- Archived emails: 0
- Trashed emails: 0
- Marked read: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Phase 13L is complete.

Next future phase:
Connect this planner into the natural Telegram control layer or build an approved manual wrapper that can optionally run the suggested report/queue commands later, still with Gmail actions disabled.

Important:
Do not enable Telegram-triggered Gmail execution yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep 5-email or dry-run testing until the whole project is complete.


## Natural intent scan/queue planner integration progress - 2026-05-10
Status: SAFE STOPPING POINT

Completed:
- Patched natural_intent.py to route natural sorting requests through:
  src\inbox_scout\sort_scan_queue_plan.py
- Verified "sort 5 emails" now returns a safe dry-run command plan.
- Verified "sort all" is blocked from full inbox scanning.
- Verified "empty my trash" routes into permanent-delete safety logic and stays blocked.
- Fixed routing bug where "move junk to trash so I can review it" was being intercepted by the generic review route.
- Verified safe trash-review language now returns a dry-run scan/queue command plan with a 5-email default limit.

Verified local natural-language tests:
- sort 5 emails
- sort all
- empty my trash
- move junk to trash so I can review it

Latest successful test:
- Command:
  .\.venv\Scripts\python.exe -m inbox_scout.natural_intent "move junk to trash so I can review it"
- Result:
  - Requested limit: 5
  - Workflow mode: small_batch_dry_run_plan
  - Suggested report command:
    .\.venv\Scripts\python.exe -m inbox_scout.report_mode --limit 5 --unread-only --export both
  - Suggested queue command:
    .\.venv\Scripts\python.exe -m inbox_scout.review_queue --from-latest-report

Safety result:
- Commands run automatically: 0
- Gmail scans executed: 0
- Gmail changes: 0
- Archived emails: 0
- Trashed emails: 0
- Marked read: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Current pause point:
Natural language can now safely convert sort/trash-review requests into suggested local report/queue commands without executing them.

Next future step:
Test the same natural phrase through Telegram listener:
- Send Atlas: move junk to trash so I can review it
- Run:
  .\.venv\Scripts\python.exe -m inbox_scout.telegram_listener --once
- Confirm Atlas replies with the safe dry-run command plan.

Important:
Do not enable Telegram-triggered Gmail execution yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep 5-email or dry-run testing until the whole project is complete.


## Phase 13J-A status - 2026-05-11
Status: COMPLETE

Completed:
- Created sort planner dry-run module:
  src\inbox_scout\sort_planner.py
- Created latest sort plan storage:
  data\plans\latest_sort_plan.json
- Tested:
  python -m inbox_scout.sort_planner "sort 25 emails"
- Result:
  - intent: sort
  - limit: 25
  - workflow_mode: small_batch_dry_run_plan
  - gmail_scan_enabled_now: false
  - gmail_changes_enabled: false
  - permanent_delete_enabled: false
  - latest_sort_plan.json saved
- Tested safety command:
  python -m inbox_scout.sort_planner "sort all"
- Result:
  - workflow_mode: sort_all_dry_run_only
  - Gmail scan disabled for now
  - Gmail changes disabled
- Tested nuclear command:
  python -m inbox_scout.sort_planner "empty my trash"
- Result:
  - intent: permanent_delete_plan_only
  - workflow_mode: blocked_phase_14_only
  - permanent delete disabled
- Tuned parser so safe trash-review language works:
  move junk to trash so I can review it
- Result:
  - allow_trash_plan: true
  - dry_run: true
  - allow_permanent_delete: false
  - Gmail changes: 0

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Trashed emails: 0
- Marked read: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

Next:
Phase 13J-B - Build scan/queue command planner.
This should prepare exact safe report/queue commands, but not execute them yet.

## Phase 13J-B natural Telegram UX verification - 2026-05-11
Status: COMPLETE

Completed:
- Updated natural_intent.py so Telegram no longer shows PowerShell commands to the user.
- Natural Telegram response now feels assistant-like instead of developer/terminal-like.
- Tested through Atlas with:
  sort 5 emails
- Atlas replied automatically through the always-on watcher.
- Atlas response said:
  - it can prepare a safe Inbox Scout scan
  - it would scan 5 unread inbox emails
  - it would build a review queue
  - it will only read Gmail
  - it will not archive anything
  - it will not move anything to Trash
  - it will not mark anything read
  - it will not reply or delete anything
  - it did not scan Gmail
  - it did not touch Gmail

Safety result:
- Gmail scan run: 0
- Gmail changes: 0
- Archived emails: 0
- Trashed emails: 0
- Marked read: 0
- Deleted emails: 0
- Permanent deletes: 0
- Replies sent: 0

UX result:
- Telegram no longer exposes PowerShell commands.
- Atlas now feels more natural for sort planning.

Next future phase:
Build the next safe layer where Atlas can run the read-only scan + local queue creation after natural approval, while Gmail modifications remain disabled.

Important:
Do not enable archive/trash/mark-read execution from Telegram yet.
Do not enable permanent delete yet.
Do not run full all-unread cleanup yet.
Keep testing in small safe batches.

## Phase 13K-B natural Telegram read-only scan approval - 2026-05-11
Status: COMPLETE

Completed:
- Natural Telegram approval flow works end-to-end.
- Tested through Atlas:
  sort 5 emails
- Atlas responded naturally and asked:
  Want me to run the safe read-only scan now?
  Reply yes to continue, or cancel to stop.
- Ryan replied:
  yes
- Atlas automatically ran the safe read-only scan and created a local review queue.
- Atlas returned:
  - Total queued emails: 5
  - Protected/manual review: 4
  - Pending low-risk review: 1

Safety result:
- Gmail read-only scan: yes
- Local queue created: yes
- Gmail changes: 0
- Archived emails: 0
- Moved to Trash: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

UX result:
- No PowerShell command was needed from the user.
- Atlas worked naturally through Telegram.
- Atlas asked for approval before running the read-only scan.
- Atlas clearly stated what it did and did not do.

Current capability:
Ryan can say:
  sort 5 emails
Then say:
  yes
Atlas will safely scan 5 unread inbox emails and build a local review queue.

Next future phase:
Build natural review-plan summary for the newly created queue, then later add approval/confirmation for safe archive or Trash actions.

Important:
Do not enable archive/trash/mark-read execution from Telegram yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep small safe batch testing until the workflow is complete.

## Phase 13L-A natural review-plan summary - 2026-05-11
Status: COMPLETE

Completed:
- Created review-plan module:
  src\inbox_scout\review_plan.py
- Connected natural review-plan requests to:
  src\inbox_scout\natural_intent.py
- Tested locally:
  python -m inbox_scout.review_plan
  python -m inbox_scout.natural_intent "show me the plan"
- Tested through Telegram:
  show me the plan
- Atlas correctly replied with the safe review plan for the latest batch.

Latest plan result:
- Total emails: 5
- Protected / leave untouched: 4
- Possible archive later: 1
- Possible Trash later: 0
- Needs review: 0
- Already handled: 0

Possible archive later:
- ID 3: Make the most of Alexa+ | risk 30 | Newsletter

Protected / untouched:
- ID 1: Daily Deals: More ways to save on every find. | risk 90 | Client/business
- ID 2: Appointment Reminder | risk 95 | Medical
- ID 4: Appointment Reminder | risk 95 | Medical
- ID 5: Delivered Amazon receipt | risk 70 | Bills/receipts

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Moved to Trash: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

Current capability:
Ryan can now say through Telegram:
  sort 5 emails
Then:
  yes
Then:
  show me the plan

Atlas will scan safely, create a local queue, and explain the review plan naturally.

Next future phase:
Build natural approval planning for the possible archive item, still dry-run/confirmation first.

Important:
Do not enable archive/trash/mark-read execution from Telegram yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep small safe batch testing until the workflow is complete.

## Phase 13M-A natural archive-plan routing - 2026-05-11
Status: COMPLETE

Completed:
- Created archive approval plan module:
  src\inbox_scout\archive_approval_plan.py
- Created archive plan storage:
  data\plans\latest_archive_plan.json
- Connected natural archive-plan phrases to:
  src\inbox_scout\natural_intent.py
- Tested locally:
  python -m inbox_scout.natural_intent "what can be archived"
- Tested through Telegram:
  what can be archived
- Atlas correctly found 1 safe archive candidate.

Safe archive candidate:
- ID 3
- Subject: Make the most of Alexa+
- Category: Newsletter
- Risk: 30
- Sender: Amazon Alexa
- Reason: Low-risk newsletter/promotion. Safe archive candidate after approval.

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Moved to Trash: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

Current capability:
Ryan can now say through Telegram:
  sort 5 emails
Then:
  yes
Then:
  show me the plan
Then:
  what can be archived

Atlas will safely scan, build a local queue, show the review plan, and identify safe archive candidates without changing Gmail.

Next future phase:
Build archive confirmation planning so Atlas can ask for approval before any archive action is allowed.

Important:
Do not enable archive execution from Telegram yet.
Do not enable Trash execution from Telegram yet.
Do not enable mark-read execution from Telegram yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.
Keep small safe batch testing until the workflow is complete.

## Phase 13M-B archive confirmation planning - 2026-05-11
Status: COMPLETE

Completed:
- Created archive confirmation planning module:
  src\inbox_scout\archive_confirmation_plan.py
- Created archive confirmation plan storage:
  data\plans\latest_archive_confirmation_plan.json
- Connected natural phrases to archive confirmation planning:
  - prepare archive
  - approve archive
  - archive this
  - archive candidate
  - archive candidates
  - confirm archive plan
- Tested locally:
  python -m inbox_scout.natural_intent "prepare archive"
- Tested through Telegram:
  prepare archive
- Atlas correctly showed the safe archive candidate but refused to run it.

Safe archive candidate:
- ID 3
- Subject: Make the most of Alexa+
- Category: Newsletter
- Risk: 30

Confirmation plan:
- Status: awaiting_future_confirmation
- Required future confirmation: confirm archive
- Gmail changes enabled: false
- Archive execution enabled: false
- Permanent delete enabled: false

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Moved to Trash: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

Current capability:
Ryan can now say through Telegram:
  sort 5 emails
Then:
  yes
Then:
  show me the plan
Then:
  what can be archived
Then:
  prepare archive

Atlas will safely prepare the archive confirmation plan but will not change Gmail.

Next future phase:
Build the archive execution gate dry-run, then later enable real archive only after confirmation.

Important:
Do not enable archive execution until the execution gate is built and tested.
Do not enable Trash execution from Telegram yet.
Do not enable mark-read execution from Telegram yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.

## Phase 13N-A archive execution gate dry-run - 2026-05-11
Status: COMPLETE

Completed:
- Created archive execution gate dry-run module:
  src\inbox_scout\archive_execution_gate.py
- Created archive execution gate storage:
  data\plans\latest_archive_execution_gate.json
- Connected natural/local command:
  confirm archive
- Patched Telegram confirm gate so plain natural:
  confirm archive
  routes to the new archive execution dry-run gate.
- Tested locally:
  python -m inbox_scout.archive_execution_gate
  python -m inbox_scout.natural_intent "confirm archive"
- Tested through Telegram:
  confirm archive
- Atlas correctly passed the archive safety gate and said it would archive ID 3 if execution were enabled.

Dry-run result:
- Status: dry_run_ready_execution_disabled
- Would archive IDs:
  - ID 3
- Subject: Make the most of Alexa+
- Category: Newsletter
- Risk: 30
- Blocked reasons: none
- Gmail changes enabled: false
- Archive execution enabled: false
- Permanent delete enabled: false

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Moved to Trash: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

Current capability:
Ryan can now say through Telegram:
  sort 5 emails
Then:
  yes
Then:
  show me the plan
Then:
  what can be archived
Then:
  prepare archive
Then:
  confirm archive

Atlas will validate the archive safety gate and show what it would archive, but Gmail execution remains disabled.

Next future phase:
Build the real archive execution runner, still guarded by config and confirmation.

Important:
Do not enable Trash execution from Telegram yet.
Do not enable mark-read execution from Telegram yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.

## Phase 13N-B archive execution runner guard - 2026-05-11
Status: COMPLETE

Completed:
- Created archive execution runner guard:
  src\inbox_scout\archive_execution_runner.py
- Created archive execution run storage:
  data\plans\latest_archive_execution_run.json
- Created archive execution log:
  data\logs\archive_execution_runs.jsonl
- Tested dry-run mode:
  python -m inbox_scout.archive_execution_runner
- Dry-run result:
  - Would archive ID 3
  - Subject: Make the most of Alexa+
  - Risk: 30
  - Category: Newsletter
  - Gmail changes: 0
- Tested apply mode:
  python -m inbox_scout.archive_execution_runner --apply
- Apply result:
  - Correctly blocked by config
  - Reason: telegram_archive_execution_enabled is not true in config
  - archived_ids: []
  - Gmail changes: 0

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Moved to Trash: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

Current capability:
Archive runner can now prove it would archive the safe candidate, but real execution is still blocked unless config explicitly enables it.

Next future phase:
Connect archive execution runner to Telegram natural language as dry-run/apply-blocked, then later decide whether to enable real archive execution only.

Important:
Do not enable Trash execution from Telegram yet.
Do not enable mark-read execution from Telegram yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.

## Phase 13N-C archive runner Telegram routing - 2026-05-11
Status: COMPLETE

Completed:
- Patched archive_execution_runner.py to expose callable functions:
  - run_archive_execution_guard()
  - build_archive_runner_message()
- Connected natural phrases in natural_intent.py:
  - run archive dry run
  - archive runner
  - test archive runner
  - try archive apply
  - test archive apply
- Tested locally:
  python -m inbox_scout.natural_intent "run archive dry run"
  python -m inbox_scout.natural_intent "try archive apply"
- Tested through Telegram:
  run archive dry run
  try archive apply

Telegram dry-run result:
- Archive runner dry-run passed.
- Would archive:
  - ID 3
  - Subject: Make the most of Alexa+
  - Risk: 30
  - Category: Newsletter
- Gmail changes: 0

Telegram apply result:
- Archive execution blocked by config.
- Real archive execution is still disabled.
- Gmail changes: 0

Safety result:
- Gmail changes: 0
- Archived emails: 0
- Moved to Trash: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

Current capability:
Ryan can now say through Telegram:
  run archive dry run
or:
  try archive apply

Atlas will prove the archive action is safe, but real Gmail archive execution remains blocked by config.

Next future phase:
Decide whether to enable real archive execution for archive-only actions, or continue building Trash/mark-read planning first.

Important:
Do not enable Trash execution from Telegram yet.
Do not enable mark-read execution from Telegram yet.
Do not enable permanent delete yet.
Do not run full all-unread Inbox cleanup yet.

## Inbox Scout Master Finish Prompt - 2026-05-11
Status: ACTIVE BUILD PLAN

This prompt replaces the old archive-first direction and locks the project back onto the real MVP goal:

sort X emails -> show plan -> approve -> move safe junk to Gmail Trash for review -> log -> summarize

Master prompt:

Yes. Copy the full master prompt you just sent, then run this PowerShell block. It will append it cleanly to both files.  ```powershell cd $HOME\inbox-scout  $promptText = Get-Clipboard  $update = @"

## Inbox Scout Master Finish Plan - 2026-05-11
Status: ACTIVE BUILD PLAN

This replaces the archive-first direction and locks Inbox Scout back onto the real MVP goal:

sort X emails -> show plan -> approve -> move safe junk to Gmail Trash for review -> log -> summarize

Current direction:
- Stop expanding archive unless it directly helps the final Trash workflow.
- Prioritize Trash-as-review-folder.
- Safe clutter goes to Gmail Trash.
- Ryan reviews Trash manually in Gmail.
- Permanent delete stays disabled until Phase 14 nuclear confirmation mode.

Current working flow:
- sort 5 emails
- yes
- show me the plan
- what can be archived
- prepare archive
- confirm archive
- run archive dry run
- try archive apply

Current confirmed safety:
- Gmail changes: 0
- Archive execution blocked by config
- Trash execution not enabled
- Mark-read execution not enabled
- Permanent delete disabled
- Full inbox cleanup disabled

Next build phases:

PHASE 13O: Trash candidate planner
- Read latest_queue.json.
- Identify only safe low-risk clutter as Trash candidates.
- Good candidates: newsletters, promotions, obvious deals, marketing clutter.
- Conservative risk threshold: <= 30.
- Never include protected categories:
  bills/receipts, finance, medical, legal, tax, security, client/business, insurance, manual review.
- Never include protected_review.
- Never include manual_review.
- Never include already handled items.
- Save:
  data/plans/latest_trash_plan.json
- Gmail changes: 0.

PHASE 13P: Natural Trash plan in Telegram
Natural phrases:
- what can go to trash
- what can be trashed
- move junk to trash so I can review it
- trash the safe junk
- show trash plan
- what is safe to trash

Expected:
Atlas shows safe Trash candidates and confirms this is not permanent delete.
Gmail changes: 0.

PHASE 13Q: Trash confirmation plan
- Build latest_trash_confirmation_plan.json.
- Candidate IDs must match latest Trash plan.
- Gmail changes false.
- Trash execution false.
- Permanent delete false.
- Plan expires after a safe time window.

PHASE 13R: Trash execution gate dry-run
- confirm trash or run trash dry run validates candidates.
- Still does not touch Gmail.
- Output says what would move to Trash.
- Gmail changes: 0.

PHASE 13S: Trash execution runner guard
- Default dry-run only.
- Apply blocked unless telegram_trash_execution_enabled is true.
- Gmail changes: 0.

PHASE 13T: Real Trash execution, small batch only
First real MVP milestone:
- Move only safe Trash candidates to Gmail Trash.
- Do not permanently delete.
- Do not archive.
- Do not mark read unless later approved.
- Log before and after.
- Update latest_queue.json:
  gmail_action_type: trashed
  gmail_action_taken: true
  gmail_action_taken_at timestamp
- Save:
  data/logs/trash_execution_runs.jsonl
- Telegram summary must show:
  moved to Trash
  protected left untouched
  errors
  permanent delete: 0

PHASE 13U: Mark-read after Trash, optional
Default:
- Do not mark read yet.
Only build if explicitly approved later.

PHASE 13V: Scale to sort 25 emails
- Same safe flow as 5.
- Scan -> queue -> plan -> approve -> move safe junk to Trash.
- No full inbox cleanup yet.

PHASE 13W: Scale to sort 100 emails
- Add progress messages.
- Add timeout handling.
- Add batch summary.
- Failures block safely.

PHASE 13X: Sort all as batch loop
- Not one reckless job.
- Process in safe batches.
- Add pause/resume.
- Save batch state.
- Never permanent delete.

PHASE 13Y: Natural UX polish
Atlas should understand:
- clean up my inbox
- sort my email
- sort 25
- clean 100 emails
- move the junk to trash
- what did you move?
- what is protected?
- what needs review?
- why did you protect this?
- where did it go?

No PowerShell command leakage in Telegram.

PHASE 13Z: Final local MVP
Ryan can use Inbox Scout locally from Telegram without touching PowerShell for normal use:
- always-on watcher
- sort 5, 25, 100
- safe Trash review workflow
- logs
- audit summary
- protected categories
- natural language control
- no permanent delete
- no full sort all unless batch loop is ready

PHASE 14: Permanent Delete Mode
Nuclear final-stage feature only.

Natural language may trigger a permanent-delete PLAN only:
- delete everything in trash
- empty my trash
- clear the trash folder
- permanently delete trash
- wipe the trash

Rules:
- Count Gmail Trash first.
- Distinguish Inbox Scout moved-to-trash, pre-existing Trash, and unknown Trash.
- Show irreversible warning.
- Require exact phrase:
  PERMANENTLY DELETE [COUNT] TRASH EMAILS
- yes is not enough.
- confirm is not enough.
- Block if count changes.
- Block if plan expires.
- Block if Gmail API errors occur.
- Log before deleting.
- Send final audit summary.

Immediate next step:
Start Phase 13O: build trash_candidate planner from latest_queue.json.

Do not enable real Trash execution yet.
Do not enable permanent delete.
Do not run sort all.


## Phase 13O trash candidate planner - 2026-05-11
Status: COMPLETE - PAUSED HERE

Completed:
- Created Trash candidate planner:
  src\inbox_scout\trash_candidate_plan.py
- Created Trash plan storage:
  data\plans\latest_trash_plan.json
- Tested locally:
  python -m inbox_scout.trash_candidate_plan
- Planner reads latest_queue.json and identifies only safe low-risk clutter candidates for Gmail Trash review.

Latest Trash plan result:
- Safe Trash candidates: 1
- Protected / untouched: 4
- Skipped: 4

Safe Trash-review candidate:
- ID 3
- Subject: Make the most of Alexa+
- Sender: Amazon Alexa
- Category: Newsletter
- Risk: 30
- Reason: Low-risk clutter. Safe Trash-review candidate after approval.

Safety result:
- Gmail changes: 0
- Moved to Trash: 0
- Archived emails: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

Plan flags:
- gmail_changes_enabled: false
- trash_execution_enabled: false
- permanent_delete_enabled: false

Current pause point:
Phase 13O is complete.
Trash candidate planning now works locally.
No Gmail changes were made.

Next future phase:
Phase 13P - Connect natural Telegram phrases to the Trash planner:
- what can go to trash
- what can be trashed
- move junk to trash so I can review it
- trash the safe junk
- show trash plan
- what is safe to trash

Important:
Do not enable real Trash execution yet.
Do not enable permanent delete.
Do not run sort all.
Keep moving toward Trash-as-review-folder MVP.

## Phase 13P natural Trash plan routing - 2026-05-12
Status: COMPLETE

Completed:
- Connected Trash-planning natural phrases to:
  src\inbox_scout\natural_intent.py
- Natural phrases now routed to:
  build_trash_plan_message()
- Tested locally:
  python -m inbox_scout.natural_intent "what can go to trash"
- Tested through Telegram:
  what can go to trash
- Atlas correctly showed the safe Trash-review plan.

Natural phrases supported:
- what can go to trash
- what can be trashed
- move junk to trash so I can review it
- move junk to trash
- trash the safe junk
- show trash plan
- what is safe to trash
- safe trash
- trash candidates

Latest Telegram result:
- Safe Trash candidates: 1
- Protected / untouched: 4

Safe Trash-review candidate:
- ID 3
- Subject: Make the most of Alexa+
- Category: Newsletter
- Risk: 30

Safety result:
- Gmail changes: 0
- Moved to Trash: 0
- Archived emails: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

Current capability:
Ryan can now say through Telegram:
  what can go to trash

Atlas will show safe Trash-review candidates and explain that Trash means Gmail Trash for manual review, not permanent delete.

Next future phase:
Phase 13Q - Build Trash confirmation plan:
- prepare trash
- approve trash
- move them to trash
- confirm trash plan

Important:
Do not enable real Trash execution yet.
Do not enable permanent delete.
Do not run sort all.
Keep moving toward Trash-as-review-folder MVP.

## Phase 13Q Trash confirmation plan - 2026-05-12
Status: COMPLETE

Completed:
- Created Trash confirmation planning module:
  src\inbox_scout\trash_confirmation_plan.py
- Created Trash confirmation plan storage:
  data\plans\latest_trash_confirmation_plan.json
- Connected natural phrases to Trash confirmation planning:
  - prepare trash
  - approve trash
  - move them to trash
  - confirm trash plan
  - prepare trash move
  - approve trash move
- Tested locally:
  python -m inbox_scout.natural_intent "prepare trash"
- Tested through Telegram:
  prepare trash
- Atlas correctly showed the safe Trash candidate but refused to run it.

Safe Trash candidate:
- ID 3
- Subject: Make the most of Alexa+
- Category: Newsletter
- Risk: 30

Confirmation plan:
- Status: awaiting_future_confirmation
- Required future confirmation: confirm trash
- Gmail changes enabled: false
- Trash execution enabled: false
- Permanent delete enabled: false

Safety result:
- Gmail changes: 0
- Moved to Trash: 0
- Archived emails: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

Current capability:
Ryan can now say through Telegram:
  what can go to trash
Then:
  prepare trash

Atlas will safely prepare the Trash confirmation plan but will not change Gmail.

Next future phase:
Phase 13R - Build Trash execution gate dry-run:
- confirm trash
- run trash dry run

Important:
Do not enable real Trash execution yet.
Do not enable permanent delete.
Do not run sort all.
Keep moving toward Trash-as-review-folder MVP.

## Phase 13R Trash execution gate dry-run - 2026-05-12
Status: COMPLETE

Completed:
- Created Trash execution gate dry-run module:
  src\inbox_scout\trash_execution_gate.py
- Created Trash execution gate storage:
  data\plans\latest_trash_execution_gate.json
- Connected natural/local command:
  confirm trash
- Connected additional dry-run phrases:
  run trash dry run
  trash dry run
  test trash gate
- Patched Telegram confirm gate so plain natural:
  confirm trash
  routes to the new Trash execution dry-run gate.
- Tested locally:
  python -m inbox_scout.trash_execution_gate
  python -m inbox_scout.natural_intent "confirm trash"
  python -m inbox_scout.telegram_confirm_gate "confirm trash"
- Tested through Telegram:
  confirm trash
- Atlas correctly passed the Trash safety gate and said it would move ID 3 to Gmail Trash if execution were enabled.

Dry-run result:
- Status: dry_run_ready_execution_disabled
- Would move to Trash:
  - ID 3
- Subject: Make the most of Alexa+
- Category: Newsletter
- Risk: 30
- Blocked reasons: none
- Gmail changes enabled: false
- Trash execution enabled: false
- Permanent delete enabled: false

Safety result:
- Gmail changes: 0
- Moved to Trash: 0
- Archived emails: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

Current capability:
Ryan can now say through Telegram:
  what can go to trash
Then:
  prepare trash
Then:
  confirm trash

Atlas will validate the Trash safety gate and show what it would move to Gmail Trash for review, but Gmail execution remains disabled.

Future feature notes:
- Add auto-sort when PC launches later, after Trash workflow is complete and safe.
- Add auto-block useless senders later as a heavily gated feature with sender review, protected-sender checks, allowlist checks, logging, and explicit confirmation.

Next future phase:
Phase 13S - Build Trash execution runner guard:
- Default dry-run only
- Apply mode blocked unless config flag telegram_trash_execution_enabled is true
- Gmail changes remain 0

Important:
Do not enable real Trash execution yet.
Do not enable permanent delete.
Do not run sort all.
Keep moving toward Trash-as-review-folder MVP.

## Phase 13S Trash execution runner guard - 2026-05-13
Status: COMPLETE

Completed:
- Created Trash execution runner guard:
  src\inbox_scout\trash_execution_runner.py
- Created Trash execution run storage:
  data\plans\latest_trash_execution_run.json
- Created Trash execution log:
  data\logs\trash_execution_runs.jsonl
- Connected natural phrases in natural_intent.py:
  - run trash runner
  - test trash runner
  - run trash apply dry run
  - try trash apply
  - test trash apply
  - apply trash
- Tested locally:
  python -m inbox_scout.trash_execution_runner
  python -m inbox_scout.trash_execution_runner --apply
  python -m inbox_scout.natural_intent "run trash runner"
  python -m inbox_scout.natural_intent "try trash apply"
- Tested through Telegram:
  run trash runner
  try trash apply

Telegram dry-run result:
- Trash runner dry-run passed.
- Would move to Gmail Trash:
  - ID 3
  - Subject: Make the most of Alexa+
  - Category: Newsletter
  - Risk: 30
- Gmail changes: 0

Telegram apply result:
- Trash execution blocked by config.
- Reason: telegram_trash_execution_enabled is not true in config.
- trashed_ids: []
- Gmail changes: 0

Safety result:
- Gmail changes: 0
- Moved to Trash: 0
- Archived emails: 0
- Marked read: 0
- Replies sent: 0
- Deleted emails: 0
- Permanent deletes: 0

Current capability:
Ryan can now say through Telegram:
  what can go to trash
  prepare trash
  confirm trash
  run trash runner
  try trash apply

Atlas can prove the Trash action is safe, but real Gmail Trash execution remains blocked by config.

Next future phase:
Phase 13T - Real Trash execution, small batch only:
- Enable only after final review.
- Move only safe Trash candidates to Gmail Trash.
- Never permanently delete.
- Log before and after.
- Update latest_queue.json after successful Trash move.

Important:
Do not enable permanent delete.
Do not run sort all.
Do not mark read automatically.
Trash means Gmail Trash review folder, not permanent delete.

---

## Phase 13T COMPLETE - Real Trash execution, small batch only

Completed: 2026-05-12 21:13:25

Result:
- Real Gmail Trash execution was tested successfully on one safe candidate only.
- Queue ID moved: 3
- Subject: Make the most of Alexa+
- Sender: Amazon Alexa <account-update@amazon.com>
- Category: Newsletter
- Risk: 30
- Gmail action: moved to Gmail Trash for manual review
- Permanent delete: 0
- Archive: 0
- Mark read: 0

Evidence:
- data/logs/trash_execution_runs.jsonl contains:
  - trash_execution_apply_start
  - before_gmail_trash
  - after_gmail_trash
  - status applied
  - trashed_ids ["3"]
- data/review_queue/latest_queue.json shows:
  - gmail_trashed = true
  - gmail_action_taken = true
  - gmail_action_type = trashed
  - gmail_trash_review_folder = true
- config/telegram_config.json was automatically turned back off:
  - telegram_trash_execution_enabled = false

Important safety note:
- A later blocked_safety result is expected because ID 3 was already marked trashed locally.
- That proves the duplicate-action guard works.
- Trash still means Gmail Trash review folder, not permanent delete.

Next phase:
Phase 13U - Telegram status polish:
- Make "what did you move?" clearly summarize the last successful Trash move.
- Make "what still needs review?" ignore already-trashed items.
- Do not expose PowerShell details in Telegram.
- Do not enable broad automatic cleanup yet.


---

## Phase 13U COMPLETE - Telegram status polish

Completed: 2026-05-12 21:21:54

Result:
- Atlas now correctly answers:
  - what did you move
  - what still needs review
  - status
- "what did you move" summarizes the last successful Gmail Trash move:
  - ID 3
  - Subject: Make the most of Alexa+
  - Action: moved to Gmail Trash for manual review
- "what still needs review" now ignores already-trashed items.
- Status now shows:
  - Latest queue items: 5
  - Still needs review: 4
  - Trashed: 1
  - Permanent deletes: 0
  - Gmail changes made by status command: 0

Telegram live test passed:
- Atlas returned the new clean messages after restarting the Telegram watcher.
- The issue was two Telegram watcher processes running at the same time.
- Restarting only the venv watcher fixed it.

Safety:
- No permanent delete.
- No archive.
- No mark read.
- No hidden Gmail changes from status commands.

Next phase:
Phase 13V - Telegram watcher hardening
- Ensure only one watcher runs.
- Ensure startup uses the venv Python only.
- Prevent stale global Python watcher from running again.
- Then continue toward the real MVP loop:
  sort X emails -> show plan -> approve -> move safe junk to Gmail Trash -> summarize.


---

## Phase 13U COMPLETE - Telegram status polish

Completed: 2026-05-12 21:22:21

Result:
- Atlas now correctly answers:
  - what did you move
  - what still needs review
  - status
- "what did you move" summarizes the last successful Gmail Trash move:
  - ID 3
  - Subject: Make the most of Alexa+
  - Action: moved to Gmail Trash for manual review
- "what still needs review" now ignores already-trashed items.
- Status now shows:
  - Latest queue items: 5
  - Still needs review: 4
  - Trashed: 1
  - Permanent deletes: 0
  - Gmail changes made by status command: 0

Telegram live test passed:
- Atlas returned the new clean messages after restarting the Telegram watcher.
- The issue was two Telegram watcher processes running at the same time.
- Restarting only the venv watcher fixed it.

Safety:
- No permanent delete.
- No archive.
- No mark read.
- No hidden Gmail changes from status commands.

Next phase:
Phase 13V - Telegram watcher hardening
- Ensure only one watcher runs.
- Ensure startup uses the venv Python only.
- Prevent stale global Python watcher from running again.
- Then continue toward the real MVP loop:
  sort X emails -> show plan -> approve -> move safe junk to Gmail Trash -> summarize.


---

## Phase 13V PAUSED - Telegram watcher hardening

Paused: 2026-05-12 21:39:49

Current status:
- Atlas live Telegram test PASSED.
- Ryan sent: status
- Atlas replied successfully.
- This proves:
  - Telegram watcher was running.
  - Atlas received the Telegram message.
  - Atlas processed the status command.
  - Atlas sent a reply back.

Confirmed working:
- Phase 13T is complete.
  - Real Gmail Trash move worked.
  - ID 3, Make the most of Alexa+, was moved to Gmail Trash for manual review.
  - Permanent delete: 0
  - Archive: 0
  - Mark read: 0
- Phase 13U is complete.
  - what did you move works.
  - what still needs review works.
  - status works.
- Atlas status output shows:
  - Still needs review: 4
  - Trashed: 1
  - Permanent deletes: 0
  - Gmail changes made by status command: 0

Phase 13V progress:
- Startup shortcut was inspected.
- Startup shortcut points to:
  - C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
  - Script: C:\Users\ryanr\inbox-scout\scripts\Start-InboxScoutTelegramWatcher.ps1
  - Working directory: C:\Users\ryanr\inbox-scout
- Hardened launcher script was written.
- Launcher refuses global Python fallback.
- telegram_watch.py was rewritten with self-protection logic.
- telegram_watch.py now checks that it is running from:
  - C:\Users\ryanr\inbox-scout\.venv\Scripts\python.exe
- Visible watcher test worked after correcting PYTHONPATH.
- Atlas replied to status after the watcher was running.

What held us up:
- There were duplicate watcher processes.
- One process appeared as:
  - C:\Users\ryanr\AppData\Local\Programs\Python\Python312\python.exe -m inbox_scout.telegram_watch
- Later inspection showed this Python312 process was a child of the venv watcher, not clearly a separate startup shortcut.
- Need one final clean verification tomorrow before marking Phase 13V complete.

Important clarification:
- Live Telegram reply test PASSED.
- Startup hardening is not fully marked complete yet because we still need one clean restart/startup verification.
- Do not update Phase 13V to COMPLETE until that final verification is done.

Next exact pickup step:
1. Reboot or manually kill all watcher processes.
2. Launch using the actual Windows Startup shortcut.
3. Confirm Atlas replies to:
   status
4. Run a process check and confirm:
   - One PowerShell launcher is running.
   - One project .venv watcher is running.
   - If Python312 appears, confirm whether it is only a child of the venv watcher.
5. If Atlas replies and there is no separate rogue startup process, mark Phase 13V COMPLETE.

Useful commands for tomorrow:

cd $HOME\inbox-scout

Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "inbox_scout.telegram_watch" -or
        $_.CommandLine -match "Start-InboxScoutTelegramWatcher"
    } |
    Select-Object ProcessId, ParentProcessId, Name, CommandLine |
    Format-List

Then test Telegram:
status

Next phase after 13V:
Phase 13W - continue MVP loop polish:
- sort X emails
- show safe plan
- prepare trash
- confirm trash
- move safe junk to Gmail Trash for review
- summarize what moved
- keep everything approval-gated


---

## Phase 13V COMPLETE - Telegram watcher hardening

Completed: 2026-05-14

Final verification:
- Started hardened watcher from a fresh PowerShell window using the launcher script.
- Watcher started cleanly using project .venv Python only.
- Atlas responded to ping through Telegram.
- Watcher stopped cleanly with Ctrl+C.
- Watcher restarted cleanly — no stale lock error, no already-running error.
- Single-instance lock (port 47631) released and reacquired correctly.

Confirmed working:
- Start-InboxScoutTelegramWatcher.ps1 refuses global Python fallback.
- telegram_watch.py self-protection logic works correctly.
- Single-instance lock acquires on start and releases cleanly on stop.
- No duplicate watcher processes on restart.
- No replay of already-processed Telegram messages.

Files touched: none (verification only)
No source code changes.
No config changes.
No token, credential, or .env changes.
No data, queue, or log edits.
No Gmail actions were run.

Safety:
- Gmail changes: 0
- Archived emails: 0
- Moved to Trash: 0
- Marked read: 0
- Permanent deletes: 0
- Replies sent: 0

Next recommended phase:
Phase 13X - Sort-all as a safe batch loop (now complete, see below).


---

## Phase 13W COMPLETE - natural_intent.py cleanup

Completed: 2026-05-13
Commit: a29f572

Change:
- Removed duplicate unreachable handler blocks from src/inbox_scout/natural_intent.py.
- The archive runner, archive gate, archive confirmation, trash runner, trash gate, trash confirmation, trash plan, archive plan, and review plan handler blocks were each present 4 times inside handle_natural_message().
- Because Python if/return chains short-circuit at the first match, all copies after the first were completely unreachable dead code.
- Removed 3 duplicate sets (194 lines deleted).
- Behavior is unchanged.

Tests passed:
- py_compile OK
- natural_intent import OK (PYTHONPATH=src)

Files touched:
- src/inbox_scout/natural_intent.py (only)

Files NOT touched:
- No Gmail runner files
- No config files
- No Telegram config
- No .env, tokens, credentials, data folders, queue files

Gmail changes: 0
Permanent deletes: 0
Replies sent: 0

Next recommended step:
- Create or update CLAUDE.md project memory file.
- Then consider archive/ folder structure cleanup for .bak and snapshot files.
- Then continue toward MVP loop: sort X emails -> plan -> approve -> Trash -> summarize.
- Phase 14 permanent delete stays disabled until explicitly enabled with nuclear confirmation.


---

## Pre-13X Backup Archive Cleanup COMPLETE

Completed: 2026-05-14
Commit: 150acbf — chore: archive phase backup snapshots before Phase 13X

Change:
- Moved 12 backup/snapshot files from src/inbox_scout/ to archive/phase_backups/.
- Git recorded all 12 as renames (0 insertions, 0 content deletions).
- No source code behavior changed.
- No docs were edited in this commit.

Files moved:
- gmail_auth.py.bak_20260507_210318
- queue_item.py.bak_20260507_205957
- queue_item.py.bak_20260507_211027
- report_mode.py.bak_20260507_205301
- report_mode.py.bak_ai_timeout_safe_20260508_184206
- report_mode.py.bak_phase11b_20260508_173925
- report_mode.py.bak_phase11b_20260508_182837
- natural_intent.before_phase13u_20260512_211434.py
- telegram_status.before_phase13u_20260512_211434.py
- telegram_watch.before_phase13v_final.py
- telegram_watch.before_phase13v_selfprotect.py
- trash_execution_runner.phase13s_backup.py

Verification passed:
- py_compile OK: natural_intent.py, telegram_watch.py, trash_execution_runner.py, report_mode.py
- natural_intent import OK (PYTHONPATH=src)
- Repo clean after commit

Files NOT touched:
- No config, token, credential, or .env files
- No data, queue, log, or Gmail files
- No source code edited

Gmail changes: 0
Permanent deletes: 0
Replies sent: 0

Next recommended phase:
Phase 13X complete. See section below.


---

## Phase 13X COMPLETE — Safe sort-all batch loop

Completed: 2026-05-14
Commit: f0dd6e8 — feat: add Phase 13X safe sort-all batch loop

Change:
- "sort all" now runs as a safe controlled batch loop, not an unlimited Gmail scan.
- Each batch scans exactly 5 unread inbox emails (MAX_SAFE_RUN_LIMIT = 5 enforced).
- After each batch Atlas says: "There may be more unread emails. Say 'continue sorting' to process the next safe batch of 5."
- Two-step approval preserved for every batch: plan → yes → scan.

Continuation phrases added to natural_intent.py:
- continue sorting
- sort more
- next batch
- keep sorting

All four route to sort_plan_message("sort all"), creating a fresh 5-email batch plan and asking for approval. Block placed before the "next" review handler to avoid the "next batch" routing conflict.

Technical changes:
- sort_scan_queue_plan.py: sort_all branch changed from blocked_large_scan to commands_planned with effective_limit=5.
- sort_scan_queue_approval.py: Removed sort_all hard-block. Replaced != 5 check with range check (< 1 or > 5). Success response shows dynamic limit and appends continuation prompt when sort_all=True.
- sort_scan_queue_runner.py: Removed sort_all hard-block from validate_plan.
- natural_intent.py: Removed dead blocked_large_scan branch. Added sort_all batch messaging. Added continuation phrase dispatch.

Tests passed:
- py_compile OK: all 4 files
- Import OK: all 4 modules
- "sort all" → batch plan message ✓
- "continue sorting", "sort more", "next batch", "keep sorting" → batch plan message ✓
- "next" alone → still routes to next review item ✓
- "empty my trash", "permanently delete" → still blocked ✓
- "status", "what can go to trash", "what can be archived" → unchanged ✓

Files changed:
- src/inbox_scout/sort_scan_queue_plan.py
- src/inbox_scout/sort_scan_queue_approval.py
- src/inbox_scout/sort_scan_queue_runner.py
- src/inbox_scout/natural_intent.py

Files NOT touched:
- No config, token, credential, or .env files
- No data, queue, log, or Gmail files
- No Telegram config

Gmail changes: 0
Permanent deletes: 0
Replies sent: 0

Next recommended phase:
Continuation cursor fix is COMPLETE (commit 29580b2). Ready for Phase 13Y.


---

## Phase 13X UTF-8 subprocess fixes

Completed: 2026-05-14
Commits: 9948430, fd30a37

Two bugs found and fixed during live Telegram testing. Both in sort_scan_queue_runner.py only.

### Bug 1 (commit 9948430)
Symptom: "yes" after "sort all" → "I tried to run the safe read-only scan, but it did not complete cleanly."
Cause: report_mode.py crashed with UnicodeEncodeError when printing an email subject containing the 🎯 emoji (U+1F3AF). Rich's LegacyWindowsTerm was trying to encode it with cp1252, which does not support emoji.
Fix: Added env["PYTHONUTF8"] = "1" to run_command() in sort_scan_queue_runner.py. This forces report_mode.py subprocess to use UTF-8 for all I/O.

### Bug 2 (commit fd30a37)
Symptom: Same error after restart. Run file not updated (still showed 10:40 AM first-failure state despite "yes" being sent at 10:46 AM).
Diagnosis: The PYTHONUTF8=1 fix made report_mode.py write UTF-8 bytes successfully, but sort_scan_queue_runner.py was reading them with subprocess.run(text=True) and no encoding — defaulting to cp1252. UTF-8 byte 0x8D (from U+200D ZERO WIDTH JOINER, present in combined emoji sequences) is undefined in cp1252. This caused a UnicodeDecodeError inside subprocess.run() in run_command(), which crashed the runner before save_result() was ever called.
Fix: Added env["PYTHONIOENCODING"] = "utf-8" and changed subprocess.run(..., text=True) to subprocess.run(..., encoding="utf-8", errors="replace") in run_command().

File changed: src/inbox_scout/sort_scan_queue_runner.py (both fixes, run_command() only)
Gmail changes: 0
Permanent deletes: 0


---

## Phase 13X live Telegram test — PASSED

Tested: 2026-05-14

Test flow:
1. Sent "sort all" → Atlas showed safe batch message (batch of 5, safety checks, asked for approval) ✓
2. Sent "yes" → Atlas scanned 5 unread inbox emails and built local review queue ✓
3. Result shown in Telegram:
   - Total queued emails: 5
   - Protected/manual review: 4
   - Pending low-risk review: 1
4. Atlas confirmed: only read Gmail, did not archive/trash/mark-read/reply/delete ✓
5. Continuation prompt shown: "Say 'continue sorting' to process the next safe batch of 5." ✓

Confirmed from latest_scan_queue_run.json (scanrun_20260514_145851):
- status: "complete"
- gmail_scan_ran: true
- gmail_changes_enabled: false
- permanent_delete_enabled: false
- report_return_code: 0
- queue_return_code: 0

Gmail changes: 0
Permanent deletes: 0


---

## Phase 13X continuation audit

Audited: 2026-05-14

Finding: "continue sorting" WILL repeat the same 5 emails, not advance to the next 5.

Root cause:
- report_mode.py --limit 5 --page-size 5 --unread-only always calls Gmail API messages.list with no pageToken
- Gmail API always returns the first N matching messages (most recent first) when no pageToken is provided
- Since the 5 scanned emails are not archived, marked read, or moved, they remain the first 5 unread inbox results
- Every subsequent "continue sorting" → "yes" would re-fetch and re-queue the same 5 emails

Status: FIXED — see section below.

---

## Continuation cursor fix

Completed: 2026-05-14
Commit: 29580b2 — fix: add Gmail cursor support for sort continuation batches

### What changed

1. **report_mode.py** — Added `--page-token` argument and `initial_page_token` parameter to `fetch_report_emails()`. After each batch, saves the Gmail `nextPageToken` to `data/plans/latest_gmail_scan_cursor.json` via new `save_scan_cursor()`. Returns `(emails, next_page_token)` tuple.

2. **sort_scan_queue_runner.py** — Added `LATEST_GMAIL_SCAN_CURSOR` constant and `load_cursor()` function. For continuation plans (`is_continuation=True`), reads the saved cursor and extends `report_args` with `--page-token TOKEN`. If no cursor token, starts from first page with a log note.

3. **sort_scan_queue_plan.py** — Added `is_continuation: bool` field to `ScanQueuePlan` dataclass. `build_scan_queue_plan()` now accepts `continuation: bool = False` parameter.

4. **sort_scan_queue_approval.py** — Added early return for exhausted cursor: if cursor file exists and `next_page_token` is null/empty, returns "inbox looks fully sorted" without running a new scan. After successful run, reads cursor to show dynamic continuation vs. done message.

5. **natural_intent.py** — Continuation phrase dispatch now calls `sort_plan_message("sort all", continuation=True)`. Updated `sort_plan_message()` signature and messaging to distinguish fresh vs. continuation plans.

### Behavior after fix

- "sort all" = fresh start, cursor ignored even if one exists
- "continue sorting" / "sort more" / "next batch" / "keep sorting" = use saved cursor token to fetch the next Gmail page
- If no cursor token saved yet, falls back to first page with log note
- After a batch where Gmail has no more pages (null nextPageToken), Atlas says "Your inbox looks fully sorted for now" and stops
- Subsequent "continue sorting" attempts with an exhausted cursor return the "fully sorted" message without scanning

### Cursor file location

data/plans/latest_gmail_scan_cursor.json
Format:
{
  "created_at": "ISO timestamp",
  "next_page_token": "TOKEN or null",
  "unread_only": true,
  "batch_limit": 5,
  "source": "report_mode"
}

### Files changed

- src/inbox_scout/report_mode.py
- src/inbox_scout/sort_scan_queue_runner.py
- src/inbox_scout/sort_scan_queue_plan.py
- src/inbox_scout/sort_scan_queue_approval.py
- src/inbox_scout/natural_intent.py

Gmail changes: 0
Permanent deletes: 0
No config/token/credential/data files touched.

Tests: py_compile OK (all 5 files), import OK, local logic checks passed ("sort all" shows fresh plan, "continue sorting" shows continuation plan with "from where the last batch left off").

Next recommended phase: Phase 13Y — Natural UX polish.
