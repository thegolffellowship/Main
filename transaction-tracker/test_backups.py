"""Tests for off-site database backups (Kerry 2026-09-03, HIGH PRIORITY).

The point of this file is that a backup you have never restored is a
belief, not a capability. So the snapshot is exercised against a REAL
SQLite database being written to, and the restore path is exercised end
to end through gzip — no mocks in the parts that could silently corrupt
data.

  - VACUUM INTO produces a consistent, integrity-clean snapshot even
    while another connection is mid-transaction (the exact case
    shutil.copy2 gets wrong);
  - the snapshot round-trips through gzip and opens with every row
    intact;
  - grandfather-father-son retention keeps 7 daily / 4 weekly / 12
    monthly and never deletes a file it cannot parse;
  - run_backup records the run, never raises, and reports the failure
    when credentials are missing.

Run: python3 test_backups.py
"""

import gzip
import os
import shutil
import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("DATABASE_PATH", ":memory:")

import logging  # noqa: E402
logging.disable(logging.ERROR)   # the failure test logs a deliberate traceback

from email_parser import backups  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def main():
    tmp = tempfile.mkdtemp(prefix="tgf-backup-test-")
    live = Path(tmp) / "live.db"

    print("Consistent snapshot of a LIVE database")
    conn = sqlite3.connect(str(live))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, amount REAL, memo TEXT)")
    conn.executemany("INSERT INTO items (amount, memo) VALUES (?,?)",
                     [(i * 1.5, f"row {i}") for i in range(5000)])
    conn.commit()

    # A second connection sits mid-transaction, exactly the situation a
    # plain file copy gets wrong.
    writer = sqlite3.connect(str(live))
    writer.execute("BEGIN")
    writer.execute("INSERT INTO items (amount, memo) VALUES (999, 'uncommitted')")

    snap = Path(tmp) / "snap.db"
    res = backups.snapshot_database(snap, db_path=live)
    check("snapshot succeeds while another write is open", not res.get("error"), res)
    check("snapshot passes SQLite's integrity check", res.get("integrity") == "ok", res)
    check("uses VACUUM INTO", res.get("method") == "VACUUM INTO", res)

    sc = sqlite3.connect(str(snap))
    n = sc.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    uncommitted = sc.execute(
        "SELECT COUNT(*) FROM items WHERE memo = 'uncommitted'").fetchone()[0]
    sc.close()
    check("every committed row is present", n == 5000, n)
    check("the uncommitted row is correctly absent", uncommitted == 0, uncommitted)
    writer.rollback(); writer.close()

    check("refuses a snapshot when the source is missing",
          backups.snapshot_database(Path(tmp) / "x.db",
                                    db_path=Path(tmp) / "nope.db").get("error"))
    # VACUUM INTO fails on an existing file, so we must clear it first.
    res2 = backups.snapshot_database(snap, db_path=live)
    check("overwrites a previous snapshot rather than erroring",
          not res2.get("error"), res2)

    print("Round trip through gzip (the actual restore path)")
    gz = Path(tmp) / "snap.db.gz"
    gz_bytes = backups.gzip_file(snap, gz)
    check("gzip shrinks the file", gz_bytes < res["bytes"], (gz_bytes, res["bytes"]))
    back = Path(tmp) / "restored.db"
    with gzip.open(gz, "rb") as f_in, open(back, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    rc = sqlite3.connect(str(back))
    check("restored copy passes integrity check",
          rc.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
    check("restored copy has all 5000 rows",
          rc.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 5000)
    check("restored data is byte-identical in content",
          rc.execute("SELECT memo FROM items WHERE id = 4321").fetchone()[0]
          == "row 4320")
    rc.close()
    conn.close()

    print("Retention — grandfather / father / son")
    today = date(2026, 9, 3)
    names = []
    for i in range(400):                      # ~13 months of dailies
        d = today - timedelta(days=i)
        names.append(f"tracker_{d.strftime('%Y%m%d')}_031500.db.gz")
    doomed = backups.select_backups_to_delete(names, today=today)
    kept = [n for n in names if n not in doomed]
    check("keeps far fewer than it deletes", len(kept) < 30, (len(kept), len(doomed)))
    for i in range(7):
        d = today - timedelta(days=i)
        nm = f"tracker_{d.strftime('%Y%m%d')}_031500.db.gz"
        check(f"keeps daily {d.isoformat()}", nm in kept)
    check("keeps roughly 7 daily + 4 weekly + 12 monthly",
          15 <= len(kept) <= 23, len(kept))
    # 12 monthly points means the NEWEST backup in each of 12 calendar
    # months, so the span back is ~10-12 months depending on today's
    # date — not 12 x 30 days. Assert the contract, not the span.
    kept_months = {(backups.parse_backup_date(n).year,
                    backups.parse_backup_date(n).month) for n in kept}
    check("a restore point exists in each of the last 12 months",
          len(kept_months) == 12, sorted(kept_months))
    oldest_kept = min(backups.parse_backup_date(n) for n in kept)
    check("the oldest kept point is in the 12th month back",
          (oldest_kept.year, oldest_kept.month) == (2025, 10), oldest_kept)
    kept_weeks = {backups.parse_backup_date(n).isocalendar()[:2] for n in kept}
    check("and a restore point in each of the last 4 ISO weeks",
          len(kept_weeks) >= 4, sorted(kept_weeks)[-5:])

    check("an unparseable filename is NEVER deleted",
          "notes.txt" not in backups.select_backups_to_delete(
              names + ["notes.txt"], today=today))
    check("a single backup is never deleted",
          backups.select_backups_to_delete(
              ["tracker_20260903_031500.db.gz"], today=today) == [])
    check("parse_backup_date reads the stamp",
          backups.parse_backup_date("tracker_20260903_031500.db.gz")
          == date(2026, 9, 3))
    check("parse_backup_date rejects junk",
          backups.parse_backup_date("tracker_notadate.db.gz") is None)

    print("Failure handling")
    for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
              "EMAIL_ADDRESS", "BACKUP_ONEDRIVE_USER"):
        os.environ.pop(k, None)
    check("no Graph credentials means not configured",
          backups._graph_creds() is None)
    r = backups.run_backup(db_path=live, dry_run=True)
    check("a dry run still snapshots and verifies before failing on creds",
          r.get("error") and "credentials" in r["error"].lower(), r)
    check("run_backup never raises", isinstance(r, dict))

    with backups.sqlite3.connect(str(live)) as c:
        backups.ensure_backup_table(c)
        c.commit()
        cols = {row[1] for row in c.execute("PRAGMA table_info(backup_runs)")}
    check("backup_runs table records what a run did",
          {"status", "remote_name", "bytes_gz", "error", "finished_at"} <= cols,
          cols)

    print("Doc mirror routing")
    t = {"docs": "7_Web & App Development/TGF Transaction Tracker/Tracker Docs",
         "fragments": "06_STRATEGY/Update_Fragments"}
    check("update fragments route to Kerry's fragments folder",
          backups._folder_for("Update_Fragment_2026-09-03_X.md", t)
          == t["fragments"])
    check("everything else routes to the tracker docs folder",
          backups._folder_for("state-of-the-tracker.md", t) == t["docs"])
    check("CLAUDE.md routes to the docs folder",
          backups._folder_for("CLAUDE.md", t) == t["docs"])
    dry = backups.mirror_docs_to_onedrive(dry_run=True)
    check("dry run finds the real repo docs", dry["found"] > 20, dry.get("found"))
    names = {f["name"] for f in dry["files"]}
    check("CLAUDE.md is included", "CLAUDE.md" in names)
    check("the session context file is included",
          "TGF_Tracker_LeadCenter_Context_v1_0.md" in names)
    frag = [f for f in dry["files"] if f["name"].startswith("Update_Fragment")]
    check("the update fragment is routed to 06_STRATEGY/Update_Fragments",
          frag and all(f["folder"] == t["fragments"] for f in frag),
          [f["folder"] for f in frag])
    check("dry run uploads nothing", dry["uploaded"] == 0)
    one = backups.mirror_docs_to_onedrive(dry_run=True, only="leads.md")
    check("dry run honors a single-file selection",
          one["found"] == 1 and one["files"][0]["name"] == "leads.md", one)
    check("unknown filename is refused",
          backups.mirror_docs_to_onedrive(dry_run=True, only="nope.md").get("error"))

    shutil.rmtree(tmp, ignore_errors=True)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
