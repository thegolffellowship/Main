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

## The fix (proposed — small, and it should not wait)

1. **Nightly job**, alongside the existing scheduler entries.
2. **`VACUUM INTO` / `Connection.backup()`**, never a file copy, so the
   snapshot is consistent even mid-write.
3. **Ship it OFF Railway.** Cheapest correct target is Supabase Storage
   — the TGF Event Images project is already ACTIVE and reachable, so
   there is no new vendor and no new bill. S3 or OneDrive also work.
4. **Retention:** 7 daily, 4 weekly, 12 monthly. Small files; storage is
   not the constraint.
5. **Report it.** A line in the COO digest saying the backup ran and how
   big it was. A silent backup that has been failing for a month is the
   classic version of this failure.
6. **Restore drill.** Pull last night's file, load it locally, confirm
   row counts and the latest transaction. **Until that is done once,
   this item is not closed.**

Rough size: an hour of work, no new dependency, no new cost.

---

## Related, same conversation

**Vercel is on the Hobby plan** (team `thegolffellowship`). Hobby
prohibits commercial use. Nothing enforces it today, but when the TGF
Platform serves real members on it, that is a terms violation whose
failure mode is the project being pulled rather than an invoice. Pro is
$20/month. Fix before launch, not after.
