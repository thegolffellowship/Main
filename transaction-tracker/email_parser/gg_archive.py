"""The Golf Genius raw archive in its own SQLite file.

Kerry 2026-09-23 (mailbox #627): "Yes, move the GG archive to its own
file." ``gg_raw_archive`` — every gzipped Golf Genius page the history
ingest and the scorecard import ever fetched — was 374 MB of the 444 MB
``transactions.db``: it is why the nightly backup took 145 s, why the
500 MB volume filled on 9/22, and what every VACUUM / integrity check /
restore drill pays for. The rows are an insurance copy (re-parse anything
if GG severs access), read by ONE audit query and written by two ingest
paths; nothing member-facing touches them.

How it works (#627's five requirements):

1. **Its own file, beside the main one** — ``transactions_gg_archive.db``
   (``archive_path``), ATTACHed as schema ``arc`` by ``get_connection``
   on every connection, so cross-file joins keep working unchanged.
2. **Backed up on its own schedule** — ``run_archive_backup`` snapshots
   the archive file (VACUUM INTO → gzip → OneDrive ``<folder>/archive``),
   Sunday nights and only when its row count changed. The nightly main
   backup no longer carries it. The archive is also rebuildable from Golf
   Genius for any page GG still serves.
3. **Readers never see the move** — ``archive_table(conn)`` returns the
   qualified name to use: ``main.gg_raw_archive`` while the legacy table
   still lives in the main file (before the cutover), ``arc.gg_raw_archive``
   after it. A fresh database and a restored volume (main file restored,
   archive file missing) both open: the file is created empty on first
   touch and the audit reader simply finds no rows.
4. **The health report shows both files** — ``status()`` feeds the
   DATABASE line of the CTO digest.
5. **Migrate in place, verify, drop, VACUUM — as separate, resumable
   steps**, each a bridge call (``scoring-gg-archive:<step>``): ``plan``
   (read-only numbers), ``migrate`` (copies in short transactions under a
   time budget; call it again until ``done``), ``verify`` (full row-by-row
   compare, read-only), ``cutover`` (final copy, count check, DROP of the
   main table — needs ``|go``), ``vacuum`` (reclaims the main file's free
   pages — needs ``|go``, off-hours, Kerry's call), ``backup``.
   Nothing here deletes a row that is not proven present in the new file.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA = "arc"
TABLE = "gg_raw_archive"
SUFFIX = "_gg_archive.db"
_DDL = ("CREATE TABLE IF NOT EXISTS {q}" + TABLE + " ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL, "
        "fetched_at TEXT DEFAULT (datetime('now')), body_gz BLOB)")
_WAL_DONE: set = set()
_ATTACH_FAILED: set = set()
BACKUP_PREFIX = "gg_archive_"
BACKUP_KEEP = 4
SETTING_ROWS = "gg_archive_backup_rows"
SETTING_LAST = "gg_archive_backup_at"
SETTING_CUTOVER = "gg_archive_cutover_at"
SETTING_VACUUM = "gg_archive_vacuum_at"


# ── paths and attachment ────────────────────────────────────────────────

def archive_path(db_path) -> Path:
    """``/data/transactions.db`` → ``/data/transactions_gg_archive.db``."""
    p = Path(str(db_path))
    return p.with_name(p.stem + SUFFIX)


def _main_file(conn: sqlite3.Connection) -> str:
    for _seq, name, file in conn.execute("PRAGMA database_list").fetchall():
        if name == "main":
            return file or ""
    return ""


def _is_attached(conn: sqlite3.Connection) -> bool:
    return any(r[1] == SCHEMA for r in conn.execute("PRAGMA database_list").fetchall())


def attach(conn: sqlite3.Connection, db_path=None) -> bool:
    """ATTACH the archive file as ``arc`` (creating it on first use).
    Called by ``get_connection`` before any statement runs — ATTACH is
    refused inside a transaction, so it must happen at connect time.
    In-memory databases have no file beside them and skip it. Never
    raises: a directory that cannot take a second file logs once and the
    readers fall back to the main file."""
    if conn.in_transaction or _is_attached(conn):
        return _is_attached(conn)
    f = str(db_path) if db_path else _main_file(conn)
    if not f or f == ":memory:":
        return False
    path = str(archive_path(f))
    if path in _ATTACH_FAILED:
        return False
    try:
        conn.execute(f"ATTACH DATABASE ? AS {SCHEMA}", (path,))
        try:
            key = (path, os.stat(path).st_ino)
        except OSError:
            key = (path, None)
        if key not in _WAL_DONE:
            conn.execute(f"PRAGMA {SCHEMA}.journal_mode=WAL")
            _WAL_DONE.add(key)
        return True
    except sqlite3.Error as e:
        _ATTACH_FAILED.add(path)
        logger.warning("gg archive: could not attach %s (%s) — using the main file", path, e)
        return False


def _legacy_in_main(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM main.sqlite_master WHERE type='table' AND name=?", (TABLE,)
    ).fetchone() is not None


def archive_table(conn: sqlite3.Connection) -> str:
    """The qualified table name every reader and writer of the raw archive
    uses. ``main.gg_raw_archive`` while the legacy table is still in the
    main file; ``arc.gg_raw_archive`` once it has been cut over (or on a
    fresh database). Creates the table where it belongs if missing."""
    if _legacy_in_main(conn):
        return f"main.{TABLE}"
    if not _is_attached(conn) and not attach(conn):
        conn.execute(_DDL.format(q="main."))
        return f"main.{TABLE}"
    conn.execute(_DDL.format(q=f"{SCHEMA}."))
    return f"{SCHEMA}.{TABLE}"


# ── status (health report) ──────────────────────────────────────────────

def status(db_path=None) -> dict:
    """Where the archive lives right now and how big it is — both files."""
    from .database import DB_PATH, get_connection, get_app_setting
    p = Path(str(db_path or DB_PATH))
    ap = archive_path(p)
    out = {"mode": "none", "path": str(ap), "bytes": 0, "rows": None,
           "main_rows": None, "main_table": False, "cutover_at": None,
           "vacuum_at": None, "last_backup_at": None}
    try:
        out["bytes"] = os.path.getsize(ap)
    except OSError:
        pass
    try:
        out["cutover_at"] = get_app_setting(SETTING_CUTOVER, db_path=p)
        out["vacuum_at"] = get_app_setting(SETTING_VACUUM, db_path=p)
        out["last_backup_at"] = get_app_setting(SETTING_LAST, db_path=p)
    except Exception:
        pass
    conn = get_connection(p)
    try:
        if _legacy_in_main(conn):
            out["main_table"] = True
            out["main_rows"] = conn.execute(f"SELECT COUNT(*) FROM main.{TABLE}").fetchone()[0]
            out["mode"] = "main"
        if _is_attached(conn):
            try:
                out["rows"] = conn.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{TABLE}").fetchone()[0]
                if not out["main_table"]:
                    out["mode"] = "file"
            except sqlite3.Error:
                out["rows"] = 0
                if not out["main_table"]:
                    out["mode"] = "file"
    finally:
        conn.close()
    return out


# ── the move, one resumable step at a time ──────────────────────────────

def plan(db_path=None) -> dict:
    """Read-only: what a migration would move and what it would free."""
    from .database import DB_PATH
    from . import perf
    p = Path(str(db_path or DB_PATH))
    st = status(p)
    lay = perf.db_layout(p, top=40)
    size = perf.db_size(p)
    tbl = next((t for t in lay.get("tables") or [] if t["name"] == TABLE), None)
    out = {**st, "main_bytes": size["bytes"],
           "table_bytes": tbl["bytes"] if tbl else 0,
           "free_bytes_now": lay.get("free_bytes") or 0,
           "disk": perf.disk_usage(p)}
    if st["mode"] == "main":
        out["next"] = ("migrate (copies rows into the archive file in short "
                       "transactions; repeat until done), then verify, then "
                       "cutover|go, then vacuum|go off-hours")
        out["copied_so_far"] = st["rows"] or 0
        out["remaining"] = max(0, (st["main_rows"] or 0) - (st["rows"] or 0))
    elif st["mode"] == "file":
        out["next"] = ("done — the archive lives in its own file"
                       + ("" if st["vacuum_at"] else "; the main file still holds the "
                          "dropped table's free pages until vacuum|go"))
    else:
        out["next"] = "nothing to move: no archive table anywhere"
    return out


def migrate(db_path=None, budget_s: float = 20.0, batch: int = 40) -> dict:
    """Copy rows from the main-file table into the archive file, oldest
    first, ``batch`` rows per transaction, until ``budget_s`` is spent or
    every row is over. Idempotent and resumable: rows are copied by id
    above the archive's current max, so a repeat call only moves what is
    new. Nothing is deleted here."""
    from .database import DB_PATH, get_connection
    p = Path(str(db_path or DB_PATH))
    t0 = time.perf_counter()
    conn = get_connection(p)
    try:
        if not _legacy_in_main(conn):
            return {"done": True, "copied": 0, "remaining": 0, "why": "no legacy table in the main file"}
        if not _is_attached(conn) and not attach(conn):
            return {"error": "archive file could not be attached"}
        conn.execute(_DDL.format(q=f"{SCHEMA}."))
        total = conn.execute(f"SELECT COUNT(*) FROM main.{TABLE}").fetchone()[0]
        copied = 0
        batches = 0
        while time.perf_counter() - t0 < budget_s:
            hi = conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {SCHEMA}.{TABLE}").fetchone()[0]
            cur = conn.execute(
                f"INSERT OR IGNORE INTO {SCHEMA}.{TABLE} (id, url, fetched_at, body_gz) "
                f"SELECT id, url, fetched_at, body_gz FROM main.{TABLE} "
                f"WHERE id > ? ORDER BY id LIMIT ?", (hi, batch))
            conn.commit()
            batches += 1
            if cur.rowcount <= 0:
                break
            copied += cur.rowcount
        in_arc = conn.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{TABLE}").fetchone()[0]
        hi_main = conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM main.{TABLE}").fetchone()[0]
        hi_arc = conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {SCHEMA}.{TABLE}").fetchone()[0]
        remaining = conn.execute(f"SELECT COUNT(*) FROM main.{TABLE} WHERE id > ?", (hi_arc,)).fetchone()[0]
        return {"done": remaining == 0 and hi_arc >= hi_main, "copied": copied,
                "batches": batches, "in_archive": in_arc, "in_main": total,
                "remaining": remaining, "ms": int((time.perf_counter() - t0) * 1000)}
    finally:
        conn.close()


def verify(db_path=None) -> dict:
    """Read-only, full compare: every main-file row must exist in the
    archive file with the same url, fetched_at and body length, and the
    counts must match. This is the proof the cutover's DROP relies on."""
    from .database import DB_PATH, get_connection
    p = Path(str(db_path or DB_PATH))
    t0 = time.perf_counter()
    conn = get_connection(p)
    try:
        if not _legacy_in_main(conn):
            return {"ok": True, "why": "no legacy table in the main file"}
        if not _is_attached(conn):
            return {"ok": False, "error": "archive file not attached"}
        n_main = conn.execute(f"SELECT COUNT(*) FROM main.{TABLE}").fetchone()[0]
        n_arc = conn.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{TABLE}").fetchone()[0]
        mismatched = conn.execute(
            f"SELECT COUNT(*) FROM main.{TABLE} m LEFT JOIN {SCHEMA}.{TABLE} a ON a.id = m.id "
            f"WHERE a.id IS NULL OR a.url IS NOT m.url OR a.fetched_at IS NOT m.fetched_at "
            f"OR length(a.body_gz) IS NOT length(m.body_gz)").fetchone()[0]
        return {"ok": n_main == n_arc and mismatched == 0, "in_main": n_main,
                "in_archive": n_arc, "mismatched_or_missing": mismatched,
                "ms": int((time.perf_counter() - t0) * 1000)}
    finally:
        conn.close()


def cutover(db_path=None, go: bool = False) -> dict:
    """Final straggler copy, count check, then DROP the main-file table —
    in one write transaction, so a row inserted mid-way is either copied
    or never dropped. Refuses without ``go`` and refuses if ``verify``
    does not pass first. Reclaiming the space is ``vacuum`` (separate)."""
    from .database import DB_PATH, get_connection, set_app_setting
    p = Path(str(db_path or DB_PATH))
    if not go:
        return {"error": "cutover needs |go — it drops the main-file table after the copy is verified"}
    v = verify(p)
    if not v.get("ok"):
        return {"error": "verify did not pass — run migrate again", "verify": v}
    conn = get_connection(p)
    try:
        if not _legacy_in_main(conn):
            return {"ok": True, "why": "already cut over"}
        conn.execute("BEGIN IMMEDIATE")
        hi = conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {SCHEMA}.{TABLE}").fetchone()[0]
        cur = conn.execute(
            f"INSERT OR IGNORE INTO {SCHEMA}.{TABLE} (id, url, fetched_at, body_gz) "
            f"SELECT id, url, fetched_at, body_gz FROM main.{TABLE} WHERE id > ? ORDER BY id", (hi,))
        stragglers = cur.rowcount
        n_main = conn.execute(f"SELECT COUNT(*) FROM main.{TABLE}").fetchone()[0]
        n_arc = conn.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{TABLE}").fetchone()[0]
        missing = conn.execute(
            f"SELECT COUNT(*) FROM main.{TABLE} m WHERE NOT EXISTS "
            f"(SELECT 1 FROM {SCHEMA}.{TABLE} a WHERE a.id = m.id)").fetchone()[0]
        if missing or n_arc < n_main:
            conn.rollback()
            return {"error": "count check failed inside the transaction — nothing dropped",
                    "in_main": n_main, "in_archive": n_arc, "missing": missing}
        conn.execute(f"DROP TABLE main.{TABLE}")
        conn.commit()
    finally:
        conn.close()
    at = datetime.utcnow().isoformat(timespec="seconds")
    try:
        set_app_setting(SETTING_CUTOVER, at, db_path=p)
    except Exception:
        logger.warning("could not record cutover time", exc_info=True)
    logger.info("gg archive cut over: %d rows now in %s (%d stragglers copied)", n_arc, archive_path(p), stragglers)
    return {"ok": True, "dropped_main_table": True, "rows": n_arc,
            "stragglers": max(0, stragglers), "cutover_at": at,
            "note": "the main file keeps the dropped pages as free space until vacuum|go"}


def vacuum_main(db_path=None, go: bool = False) -> dict:
    """VACUUM the main file to give the dropped table's pages back.
    Holds the write lock for the duration (seconds for a ~50 MB live
    set), so: off-hours, and only with ``go``."""
    from .database import DB_PATH, set_app_setting
    from . import perf
    p = Path(str(db_path or DB_PATH))
    if not go:
        return {"error": "vacuum needs |go — it holds the write lock while the file is rewritten"}
    before = perf.db_size(p)["bytes"]
    t0 = time.perf_counter()
    conn = sqlite3.connect(str(p), timeout=30)
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()
    after = perf.db_size(p)["bytes"]
    at = datetime.utcnow().isoformat(timespec="seconds")
    try:
        set_app_setting(SETTING_VACUUM, at, db_path=p)
    except Exception:
        pass
    return {"ok": True, "bytes_before": before, "bytes_after": after,
            "freed_mb": round((before - after) / 1048576, 1),
            "ms": int((time.perf_counter() - t0) * 1000), "vacuum_at": at}


# ── the archive's own backup ────────────────────────────────────────────

def run_archive_backup(db_path=None, force: bool = False, dry_run: bool = False) -> dict:
    """Snapshot the archive file → gzip → OneDrive ``<folder>/archive``,
    keeping the newest ``BACKUP_KEEP``. Skips (``skipped``) when the row
    count has not changed since the last upload unless ``force``. Never
    raises. Only runs once the archive lives in its own file."""
    import shutil
    import tempfile
    from .database import DB_PATH, get_app_setting, set_app_setting
    from . import backups
    p = Path(str(db_path or DB_PATH))
    ap = archive_path(p)
    res: dict = {"ok": False}
    st = status(p)
    if st["mode"] != "file":
        return {"ok": True, "skipped": f"archive still in the main file (mode {st['mode']}); the nightly backup covers it"}
    rows = st.get("rows") or 0
    try:
        last_rows = get_app_setting(SETTING_ROWS, db_path=p)
    except Exception:
        last_rows = None
    if not force and last_rows is not None and str(rows) == str(last_rows):
        return {"ok": True, "skipped": f"unchanged since last backup ({rows} rows)"}
    tmpdir = tempfile.mkdtemp(prefix="tgf-gg-archive-")
    try:
        started = datetime.utcnow()
        name = f"{BACKUP_PREFIX}{started.strftime('%Y%m%d_%H%M%S')}.db.gz"
        raw = Path(tmpdir) / "archive.db"
        snap = backups.snapshot_database(raw, db_path=ap)
        if snap.get("error"):
            raise RuntimeError(snap["error"])
        gz = Path(tmpdir) / name
        res.update({"name": name, "bytes_raw": snap["bytes"],
                    "bytes_gz": backups.gzip_file(raw, gz), "rows": rows})
        creds = backups._graph_creds()
        if not creds:
            raise RuntimeError("Graph credentials missing")
        if dry_run:
            res.update({"ok": True, "dry_run": True, "uploaded": False})
            return res
        token = backups._token(creds)
        if not token:
            raise RuntimeError("could not acquire a Graph token")
        folder = backups._folder(p) + "/archive"
        backups._ensure_folder(token, creds["user"], folder)
        backups._upload(token, creds["user"], folder, name, gz)
        res.update({"uploaded": True, "folder": folder})
        try:
            remote = sorted(f["name"] for f in backups.list_remote_backups(token, creds["user"], folder)
                            if f.get("name", "").startswith(BACKUP_PREFIX))
        except Exception:
            remote = []
        doomed = remote[:-BACKUP_KEEP] if len(remote) > BACKUP_KEEP else []
        res["pruned"] = sum(1 for n in doomed if backups._delete_remote(token, creds["user"], folder, n))
        set_app_setting(SETTING_ROWS, str(rows), db_path=p)
        set_app_setting(SETTING_LAST, started.isoformat(timespec="seconds"), db_path=p)
        res["ok"] = True
        return res
    except Exception as e:
        logger.exception("GG archive backup FAILED")
        res["error"] = str(e)
        return res
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
