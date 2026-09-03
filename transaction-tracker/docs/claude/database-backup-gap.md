# Database backup — the open risk (Kerry: HIGH PRIORITY, 2026-09-03)

> Kerry, 2026-09-03: *"Definitely add the backup to the list of high
> priority. My developer friend asked me that question that I asked you
> about AWS. I'm guessing that was his concern too."*

Two people arrived at this independently. That is usually a sign it is
real.

---

## The situation, stated plainly

**Every transaction, customer, event, membership, payout and handicap
TGF has ever recorded lives in one SQLite file on one Railway volume.**

What is already handled:
- The volume is persistent. `app.py` logs a loud warning at startup if
  `DATABASE_PATH` is unset, and it is set — so the database survives
  redeploys.

What is **not** handled:
- **The only backup mechanism is manual.** `/admin/backup` (admin-only)
  copies the file and checkpoints the WAL. Nothing schedules it.
- **It writes the copy to the same volume** (`<db>.backup`). If that
  volume is lost or corrupted, both the database and its "backup" go
  together. This is not a backup; it is a second copy in the same box.
- **Nothing is off Railway.** No cloud storage, no other provider.
- **No restore has ever been tested.** An untested backup is a belief,
  not a capability.
- **`shutil.copy2` on a live SQLite file is not safe** under concurrent
  writes. The scheduler runs jobs on a timer, so a copy can land
  mid-write. `sqlite3.Connection.backup()` or `VACUUM INTO` is the
  correct mechanism — both produce a consistent snapshot of a database
  that is actively being written.

**Blast radius: the business.** Not a feature, not a report — the
financial records, the membership history, the money owed and paid.

---

## The fix — BUILT, v2.296.0 (2026-09-03)

`email_parser/backups.py`. Nightly at 08:15 UTC (03:15 Central).
Idle until the Azure app gains one permission; see "What Kerry
must do" below.

### As built

1. **Consistent snapshot** — `VACUUM INTO`, SQLite's own mechanism,
   which is valid even taken mid-write. The snapshot then has to pass
   `PRAGMA integrity_check` **before** it is shipped anywhere; a corrupt
   backup is worse than an obviously missing one. Falls back to the
   online backup API on older SQLite.
2. **Gzipped and shipped OFF Railway** to OneDrive through Microsoft
   Graph — reusing the `AZURE_*` credentials the Tracker already holds
   for mail. **No new vendor, no new secret, no new bill.** (Supabase
   Storage was the other candidate; OneDrive won because it needed zero
   new credentials.) Chunked upload session above 4 MB.
3. **Retention:** grandfather-father-son — 7 daily, 4 weekly, 12
   monthly. A file whose name cannot be parsed is **never** deleted.
4. **It speaks when it breaks.** Every run is recorded in `backup_runs`;
   a failure emails Kerry, throttled to one per 12 hours. `run_backup`
   never raises — a backup failure must not take the scheduler down.
5. **The restore drill is automated.** `verify_latest_backup()` pulls
   the newest file back from OneDrive, decompresses it, runs SQLite's
   integrity check, and compares row counts against live.

Bridge: `scoring-backup-run[:dry]`, `scoring-backup-verify`,
`scoring-backup-status`. Disable with `DB_BACKUP_DISABLED=1`. Folder via
the `backup_onedrive_folder` dial (default `TGF-Tracker-Backups`).
Test: `test_backups.py` — exercises the snapshot against a real database
with an open uncommitted write, round-trips through gzip, and checks all
5,000 rows survive.

### What Kerry must do (one permission, no new secret)

Azure Portal → App registrations → the app already used for TGF mail →
**API permissions** → Add → Microsoft Graph → **Application permissions**
→ `Files.ReadWrite.All` → Add → then **Grant admin consent**.

Nothing else. No new environment variable, because `AZURE_TENANT_ID`,
`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` and `EMAIL_ADDRESS` are already
set on Railway.

### CLOSED — the drill passed, 2026-09-03 19:49 UTC

Kerry granted `Files.ReadWrite.All` and consented. First real run:

| | |
|---|---|
| Snapshot | `VACUUM INTO`, integrity **ok** |
| Size | 198.1 MB raw → **134.8 MB** gzipped |
| Uploaded | OneDrive `/TGF-Tracker-Backups/tracker_20260903_194856.db.gz` |

`scoring-backup-verify` then pulled that file back out of OneDrive,
decompressed it, integrity-checked it, and compared row counts to live.
**Every table matched exactly:**

items 2,033 · customers 719 · events 85 · acct_transactions 8,756 ·
customer_memberships 259 · leads 86

That is the difference between believing we have backups and knowing it.
Nightly from here at 03:15 Central.

### Honest limits of this setup

- **One destination, and it is inside the same Microsoft tenant** as
  TGF's email. A compromise of that M365 account could reach both. This
  is enormously better than a copy on the same Railway volume, but it is
  not a second provider. A true 3-2-1 posture would add one — worth
  revisiting, not urgent.
- **Size to watch:** 135 MB per backup, up to 23 retained, so roughly
  3 GB of OneDrive at steady state. Fine against the 1 TB an M365
  Business seat carries, but it grows with the database.
- **198 MB is a large SQLite file** for this business. Worth
  understanding what dominates it (GG snapshots? stored email bodies?)
  before it becomes a performance issue rather than after.

---

## Related, same conversation

**Vercel is on the Hobby plan** (team `thegolffellowship`). Hobby
prohibits commercial use. Nothing enforces it today, but when the TGF
Platform serves real members on it, that is a terms violation whose
failure mode is the project being pulled rather than an invoice. Pro is
$20/month. Fix before launch, not after.
