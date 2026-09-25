"""The Golf Genius raw archive in its own file (Kerry 2026-09-23, #627).

Proves: a fresh database puts the archive straight into the file; a
legacy database keeps serving the main-file table until the cutover;
migrate is resumable and copies in short transactions; verify catches a
changed row; cutover refuses without |go, refuses when verify fails, and
drops the main table only after the count check; readers (the gg_history
join) and both writers work before and after; a restored volume with the
archive file missing still opens; the health report and digest show the
file; the archive backup snapshots the right file.
"""
import os, sys, sqlite3, tempfile, zlib, json, logging

root = tempfile.mkdtemp(prefix="tgf-ggarc-")
tmp = os.path.join(root, "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ["PERF_SAMPLES"] = "0"
os.environ.setdefault("SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

from email_parser import database as db
from email_parser import gg_archive as ga
from email_parser import gg_history as gh
from email_parser import health, perf

fails = []
def check(l, c, d=""):
    print(("  PASS  " if c else "  FAIL  ") + l + ("" if c else f"  {d}"))
    if not c: fails.append(l)

def blob(s): return zlib.compress(s.encode())

print("== a fresh database: the archive goes straight to its own file ==")
db.init_db(tmp)
arc_path = ga.archive_path(tmp)
check("archive_path sits beside the main file with the _gg_archive suffix",
      str(arc_path) == os.path.join(root, "t_gg_archive.db"), str(arc_path))
with db._connect(tmp) as conn:
    names = [r[1] for r in conn.execute("PRAGMA database_list")]
    check("get_connection ATTACHes the archive file as 'arc'", "arc" in names, names)
    check("init_db no longer creates gg_raw_archive in the main file",
          conn.execute("SELECT 1 FROM main.sqlite_master WHERE name='gg_raw_archive'").fetchone() is None)
    t = ga.archive_table(conn)
    check("archive_table() names the file's table on a fresh database", t == "arc.gg_raw_archive", t)
    rid = gh._archive_raw(conn, "https://x/1", "<html>one</html>")
    conn.commit()
    check("the gg_history writer inserts into the file and returns a rowid", rid == 1, rid)
check("...and the bytes landed in the archive file, not the main one",
      sqlite3.connect(str(arc_path)).execute("SELECT COUNT(*) FROM gg_raw_archive").fetchone()[0] == 1)
st = ga.status(tmp)
check("status() says mode=file with 1 row", st["mode"] == "file" and st["rows"] == 1, st)
check("plan() on a fresh database has nothing to move", "done" in ga.plan(tmp)["next"], ga.plan(tmp)["next"])
check("migrate() is a no-op when there is no legacy table", ga.migrate(tmp)["done"] is True)
check("cutover refuses without |go", "error" in ga.cutover(tmp, go=False))
check("vacuum refuses without |go", "error" in ga.vacuum_main(tmp, go=False))
with db._connect(tmp) as conn:
    check("the WAL pragma ran on the archive file", conn.execute("PRAGMA arc.journal_mode").fetchone()[0] == "wal")

print("\n== a legacy database: the table still in the main file ==")
leg = os.path.join(root, "legacy.db")
db.init_db(leg)
raw = sqlite3.connect(leg)
raw.execute("CREATE TABLE gg_raw_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL, "
            "fetched_at TEXT DEFAULT (datetime('now')), body_gz BLOB)")
for i in range(1, 101):
    raw.execute("INSERT INTO gg_raw_archive (id, url, fetched_at, body_gz) VALUES (?,?,?,?)",
                (i, f"https://gg/{i}", f"2026-09-{(i % 28) + 1:02d} 10:00:00", blob("page %d " % i * 50)))
raw.commit(); raw.close()
with db._connect(leg) as conn:
    check("archive_table() keeps naming the main-file table before the cutover",
          ga.archive_table(conn) == "main.gg_raw_archive")
    rid = gh._archive_raw(conn, "https://gg/101", "<html>101</html>"); conn.commit()
    check("...and a new write during that time goes to the main table", rid == 101, rid)
st = ga.status(leg)
check("status() says mode=main, 101 rows in main, 0 in the file",
      st["mode"] == "main" and st["main_rows"] == 101 and (st["rows"] or 0) == 0, st)
p = ga.plan(leg)
check("plan() says migrate next and counts the remaining rows",
      p["next"].startswith("migrate") and p["remaining"] == 101 and p["table_bytes"] > 0, p)

m1 = ga.migrate(leg, budget_s=60, batch=30)
check("migrate copies every row in batches and reports done", m1["done"] and m1["copied"] == 101 and m1["batches"] >= 4, m1)
# a row written while the migration was in flight (id above the copied max)
with db._connect(leg) as conn:
    gh._archive_raw(conn, "https://gg/102", "<html>102</html>"); conn.commit()
m2 = ga.migrate(leg, budget_s=60, batch=30)
check("a second migrate only moves the new row (resumable, idempotent)", m2["copied"] == 1 and m2["done"], m2)
v = ga.verify(leg)
check("verify passes: same count, no missing or changed rows", v["ok"] and v["in_main"] == v["in_archive"] == 102, v)

# tamper with one archived row → verify must fail and cutover must refuse
a = sqlite3.connect(str(ga.archive_path(leg)))
a.execute("UPDATE gg_raw_archive SET body_gz = ? WHERE id = 50", (blob("tampered"),)); a.commit(); a.close()
v2 = ga.verify(leg)
check("verify catches a row whose body differs in the file", not v2["ok"] and v2["mismatched_or_missing"] == 1, v2)
c0 = ga.cutover(leg, go=True)
check("cutover REFUSES while verify fails — nothing dropped", "error" in c0, c0)
with db._connect(leg) as conn:
    check("...the main table is still there", ga.archive_table(conn) == "main.gg_raw_archive")
# repair the tampered row by re-copying it
a = sqlite3.connect(str(ga.archive_path(leg)))
a.execute("DELETE FROM gg_raw_archive WHERE id = 50"); a.commit(); a.close()
m3 = ga.migrate(leg, budget_s=60)
check("migrate after a delete in the file does NOT refill by id gap (copies only above max id)", m3["copied"] == 0, m3)
a = sqlite3.connect(str(ga.archive_path(leg)))
a.execute("INSERT INTO gg_raw_archive (id, url, fetched_at, body_gz) SELECT 50, 'https://gg/50', '2026-09-23 10:00:00', ?", (blob("page 50 " * 50),))
a.commit(); a.close()
check("verify passes again once the row is put back", ga.verify(leg)["ok"], ga.verify(leg))

c1 = ga.cutover(leg, go=True)
check("cutover|go drops the main table after the in-transaction count check",
      c1.get("ok") and c1["dropped_main_table"] and c1["rows"] == 102, c1)
with db._connect(leg) as conn:
    check("after the cutover archive_table() names the file", ga.archive_table(conn) == "arc.gg_raw_archive")
    check("...and the main file no longer has the table",
          conn.execute("SELECT 1 FROM main.sqlite_master WHERE name='gg_raw_archive'").fetchone() is None)
    rid = gh._archive_raw(conn, "https://gg/103", "<html>103</html>"); conn.commit()
    check("a write after the cutover lands in the file with the next id", rid == 103, rid)
    db._ensure_scoring_tables(conn)
    check("_ensure_scoring_tables does not resurrect the table in the main file",
          conn.execute("SELECT 1 FROM main.sqlite_master WHERE name='gg_raw_archive'").fetchone() is None)
st = ga.status(leg)
check("status() after cutover: mode=file, 103 rows, cutover_at recorded",
      st["mode"] == "file" and st["rows"] == 103 and st["cutover_at"], st)
lay = perf.db_layout(leg)
check("the dropped table left free pages behind in the main file", (lay.get("freelist_pages") or 0) > 0, lay)
vac = ga.vacuum_main(leg, go=True)
check("vacuum|go reclaims them and records the time", vac["ok"] and vac["bytes_after"] < vac["bytes_before"] and vac["vacuum_at"], vac)
check("...free pages are gone", perf.db_layout(leg)["freelist_pages"] == 0)

print("\n== the reader: gg_history's archive join works before and after ==")
with db._connect(leg) as conn:
    gh.ensure_gg_history_tables(conn)
    conn.execute("INSERT INTO gg_history_portals (subdomain, chapter, season, kind, brand) VALUES ('tgf-sa','SA','2024','portal','TGF')")
    pid = conn.execute("SELECT id FROM gg_history_portals").fetchone()[0]
    conn.execute("INSERT INTO gg_history_pages (portal_id, gg_page_id, page_kind, raw_archive_id, fetch_status) VALUES (?,?,?,?,?)",
                 (pid, "p1", "season_standings", 103, "done"))
    conn.commit()
    rows = conn.execute(f"""SELECT a.body_gz FROM gg_history_pages g
                            JOIN {ga.archive_table(conn)} a ON a.id=g.raw_archive_id
                            WHERE g.fetch_status='done'""").fetchall()
    check("the cross-file join finds the archived page by raw_archive_id",
          len(rows) == 1 and zlib.decompress(rows[0][0]).decode() == "<html>103</html>", rows)

print("\n== a restored volume: main file back, archive file missing ==")
os.remove(str(ga.archive_path(leg)))
for ext in ("-wal", "-shm"):
    try: os.remove(str(ga.archive_path(leg)) + ext)
    except OSError: pass
ga._WAL_DONE.clear()
with db._connect(leg) as conn:
    t = ga.archive_table(conn)
    check("the connection still opens and the archive is recreated empty on first touch",
          t == "arc.gg_raw_archive" and conn.execute("SELECT COUNT(*) FROM arc.gg_raw_archive").fetchone()[0] == 0, t)
    rows = conn.execute(f"SELECT a.body_gz FROM gg_history_pages g JOIN {t} a ON a.id=g.raw_archive_id").fetchall()
    check("the reader returns no rows instead of crashing", rows == [])
check("status() reports the empty file", ga.status(leg)["mode"] == "file" and ga.status(leg)["rows"] == 0)

print("\n== in-memory databases skip the file ==")
mem = sqlite3.connect(":memory:")
check("attach() declines an in-memory main", ga.attach(mem) is False)
check("archive_table() falls back to a main-file table there", ga.archive_table(mem) == "main.gg_raw_archive")

print("\n== the health report and digest show the file ==")
rep = health.build_health_report(days=1, db_path=leg, record_size=False)
check("report['db']['archive'] carries mode/bytes/rows", rep["db"]["archive"]["mode"] == "file" and "bytes" in rep["db"]["archive"], rep["db"].get("archive"))
md = health.render_markdown(rep)
check("the digest prints a GG ARCHIVE FILE line", "**GG ARCHIVE FILE**" in md, md[-600:])
rep2 = health.build_health_report(days=1, db_path=tmp, record_size=False)
check("no db_big_table finding once the archive is out of the main file",
      not any(f["key"].startswith("db_big_table") for f in health.find(rep2)))

print("\n== the archive's own backup ==")
os.environ.pop("AZURE_TENANT_ID", None)
res = ga.run_archive_backup(leg, force=True, dry_run=True)
check("without Graph creds the backup reports the error and never raises", res.get("ok") is False and "Graph" in res.get("error", ""), res)
from email_parser import backups
snap = backups.snapshot_database(os.path.join(root, "arc-snap.db"), db_path=ga.archive_path(tmp))
check("snapshot_database works on the archive file itself (VACUUM INTO, integrity ok)",
      snap.get("integrity") == "ok" and sqlite3.connect(os.path.join(root, "arc-snap.db")).execute("SELECT COUNT(*) FROM gg_raw_archive").fetchone()[0] == 1, snap)
leg2 = os.path.join(root, "legacy2.db")
db.init_db(leg2)
r2 = sqlite3.connect(leg2)
r2.execute("CREATE TABLE gg_raw_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL, fetched_at TEXT, body_gz BLOB)")
r2.commit(); r2.close()
res2 = ga.run_archive_backup(leg2)
check("a legacy database's backup is skipped with a reason (the nightly backup still covers it)",
      res2.get("ok") and "main file" in res2.get("skipped", ""), res2)

print("\n== the scheduler carries the weekly archive backup job ==")
os.environ.setdefault("EMAIL_ADDRESS", "x@y.z"); os.environ.setdefault("EMAIL_PASSWORD", "p")
os.environ["DB_BACKUP_DISABLED"] = "0"
import app as appmod
try:
    appmod.start_scheduler()
except Exception:
    pass
job = appmod.scheduler.get_job("gg_archive_backup") if getattr(appmod, "scheduler", None) else None
check("gg_archive_backup is scheduled (Sunday 08:45 UTC)", job is not None and "sun" in str(job.trigger), str(job.trigger if job else None))
try:
    appmod.scheduler.shutdown(wait=False)
except Exception:
    pass

print("\n== the bridge ==")
import mcp_server
os.environ["DATABASE_PATH"] = tmp
out = json.loads(mcp_server._scoring_dispatch("https://tgf-sa.golfgenius.com/", "scoring-gg-archive"))
check("scoring-gg-archive (plan) answers read-only with the mode", out.get("mode") in ("file", "main", "none"), out)
out = json.loads(mcp_server._scoring_dispatch("https://tgf-sa.golfgenius.com/", "scoring-gg-archive:cutover"))
check("scoring-gg-archive:cutover without |go is refused", "error" in out, out)
out = json.loads(mcp_server._scoring_dispatch("https://tgf-sa.golfgenius.com/", "scoring-gg-archive:bogus"))
check("an unknown step prints the usage", "usage" in out.get("error", ""), out)

print()
print("ALL PASS" if not fails else f"FAILED: {fails}")
sys.exit(1 if fails else 0)
