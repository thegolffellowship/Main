"""Off-site database backups (Kerry 2026-09-03, HIGH PRIORITY).

Every transaction, customer, event, membership and payout TGF has ever
recorded lives in ONE SQLite file on ONE Railway volume. Before this
module the only backup was a manual ``/admin/backup`` endpoint that
copied that file **onto the same volume** — a second copy in the same
box, which is not a backup — using ``shutil.copy2`` on a database the
scheduler is actively writing to.

This fixes all three problems:

1. **Consistent snapshot.** ``VACUUM INTO`` asks SQLite itself for a
   clean copy, so a snapshot taken mid-write is still valid. A plain
   file copy of a live database can produce a file that looks fine and
   fails on restore — the worst kind of backup.
2. **Off Railway.** The snapshot is gzipped and uploaded to OneDrive
   through Microsoft Graph, reusing the AZURE_* credentials the Tracker
   already holds for mail. No new vendor, no new secret, no new bill —
   the Azure app registration only needs the ``Files.ReadWrite.All``
   application permission added.
3. **It says something when it breaks.** Every run is recorded, and a
   failure emails Kerry (throttled). A backup that has silently failed
   for a month is the classic version of this disaster.

Retention is grandfather-father-son: 7 daily, 4 weekly, 12 monthly.

**A backup nobody has restored is a belief, not a capability** — so
``verify_latest_backup()`` pulls the newest file back down, opens it,
runs SQLite's own integrity check and compares row counts against the
live database. Run it after the first backup, then periodically.
"""

from __future__ import annotations

import gzip
import logging
import os
import shutil
import sqlite3
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
BACKUP_PREFIX = "tracker_"
BACKUP_SUFFIX = ".db.gz"
DEFAULT_FOLDER = "TGF-Tracker-Backups"
# Graph takes a simple PUT up to 4 MB; bigger needs a chunked session.
SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024
CHUNK_SIZE = 5 * 1024 * 1024          # must be a multiple of 320 KiB
KEEP_DAILY, KEEP_WEEKLY, KEEP_MONTHLY = 7, 4, 12
ALERT_THROTTLE_HOURS = 12
_ALERT_KEY = "backup_failed"
# Tables whose row counts are compared live-vs-restored in the drill.
VERIFY_TABLES = ("items", "customers", "events", "acct_transactions",
                 "customer_memberships", "leads")


def _folder(db_path=None) -> str:
    from . import database as db
    try:
        v = (db.get_app_setting("backup_onedrive_folder", db_path=db_path)
             if db_path else db.get_app_setting("backup_onedrive_folder"))
    except Exception:
        v = None
    return (v or DEFAULT_FOLDER).strip("/")


def _graph_creds() -> dict | None:
    creds = {
        "tenant_id": os.getenv("AZURE_TENANT_ID"),
        "client_id": os.getenv("AZURE_CLIENT_ID"),
        "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
        "user": os.getenv("BACKUP_ONEDRIVE_USER") or os.getenv("EMAIL_ADDRESS"),
    }
    return creds if all(creds.values()) else None


def _token(creds: dict) -> str | None:
    from .fetcher import _get_graph_token
    return _get_graph_token(creds["tenant_id"], creds["client_id"],
                            creds["client_secret"])


# ── schema ───────────────────────────────────────────────────────────

def ensure_backup_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backup_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT DEFAULT (datetime('now')),
            finished_at TEXT,
            status      TEXT NOT NULL DEFAULT 'running',
            remote_name TEXT,
            bytes_raw   INTEGER,
            bytes_gz    INTEGER,
            pruned      INTEGER DEFAULT 0,
            error       TEXT
        )""")


# ── 1. consistent snapshot ───────────────────────────────────────────

def snapshot_database(dest: str | Path, db_path: str | Path | None = None
                      ) -> dict:
    """A CONSISTENT copy of the live database, safe to take while the
    scheduler is writing. ``VACUUM INTO`` is SQLite's own supported
    mechanism; it refuses to write over an existing file, so the
    destination must not exist. Falls back to the backup API on older
    SQLite builds."""
    from . import database as db
    src = Path(db_path or db.DB_PATH)
    dest = Path(dest)
    if not src.exists():
        return {"error": f"source database not found: {src}"}
    if dest.exists():
        dest.unlink()
    conn = sqlite3.connect(str(src))
    try:
        try:
            conn.execute("VACUUM INTO ?", (str(dest),))
            method = "VACUUM INTO"
        except sqlite3.OperationalError:
            # SQLite < 3.27 — the online backup API is equally consistent.
            out = sqlite3.connect(str(dest))
            try:
                conn.backup(out)
            finally:
                out.close()
            method = "backup API"
    finally:
        conn.close()
    # Prove the snapshot opens and passes SQLite's own integrity check
    # BEFORE we ship it anywhere. A corrupt snapshot is worse than none.
    check = sqlite3.connect(str(dest))
    try:
        ok = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if ok != "ok":
        return {"error": f"snapshot failed integrity check: {ok}"}
    return {"path": str(dest), "bytes": dest.stat().st_size,
            "method": method, "integrity": ok}


def gzip_file(src: str | Path, dest: str | Path) -> int:
    with open(src, "rb") as f_in, gzip.open(dest, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)
    return Path(dest).stat().st_size


# ── 2. off-site: OneDrive via Graph ──────────────────────────────────

def _upload(token: str, user: str, folder: str, name: str,
            path: Path) -> dict:
    size = path.stat().st_size
    base = f"{GRAPH_BASE}/users/{user}/drive/root:/{folder}/{name}"
    if size <= SIMPLE_UPLOAD_LIMIT:
        with open(path, "rb") as fh:
            r = requests.put(
                f"{base}:/content",
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/octet-stream"},
                data=fh, timeout=300)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"upload failed {r.status_code}: {r.text[:300]}")
        return r.json()
    # Chunked upload session for anything larger.
    r = requests.post(f"{base}:/createUploadSession",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
                      timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"createUploadSession failed {r.status_code}: "
                           f"{r.text[:300]}")
    url = r.json()["uploadUrl"]
    with open(path, "rb") as fh:
        start = 0
        while start < size:
            chunk = fh.read(CHUNK_SIZE)
            end = start + len(chunk) - 1
            cr = requests.put(url, headers={
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{end}/{size}"},
                data=chunk, timeout=300)
            if cr.status_code not in (200, 201, 202):
                raise RuntimeError(f"chunk {start}-{end} failed "
                                   f"{cr.status_code}: {cr.text[:200]}")
            start = end + 1
        return cr.json() if cr.content else {"name": name}


def list_remote_backups(token: str, user: str, folder: str) -> list[dict]:
    r = requests.get(
        f"{GRAPH_BASE}/users/{user}/drive/root:/{folder}:/children"
        "?$select=name,size,lastModifiedDateTime&$top=200",
        headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return [f for f in r.json().get("value", [])
            if f.get("name", "").startswith(BACKUP_PREFIX)]


def _delete_remote(token: str, user: str, folder: str, name: str) -> bool:
    r = requests.delete(f"{GRAPH_BASE}/users/{user}/drive/root:/{folder}/{name}",
                        headers={"Authorization": f"Bearer {token}"}, timeout=60)
    return r.status_code in (200, 204)


# ── 3. retention (pure, so it is testable without a network) ─────────

def parse_backup_date(name: str) -> date | None:
    """tracker_YYYYMMDD_HHMMSS.db.gz -> date"""
    if not name.startswith(BACKUP_PREFIX):
        return None
    stamp = name[len(BACKUP_PREFIX):][:8]
    try:
        return datetime.strptime(stamp, "%Y%m%d").date()
    except ValueError:
        return None


def select_backups_to_delete(names: list[str], today: date | None = None,
                             daily: int = KEEP_DAILY, weekly: int = KEEP_WEEKLY,
                             monthly: int = KEEP_MONTHLY) -> list[str]:
    """Grandfather-father-son. Keeps the newest backup of each of the last
    `daily` days, of each of the last `weekly` ISO weeks, and of each of
    the last `monthly` months. Returns what may be deleted. Anything
    unparseable is KEPT — never delete a file we do not understand."""
    today = today or date.today()
    dated = []
    for n in names:
        d = parse_backup_date(n)
        if d is not None:
            dated.append((d, n))
    dated.sort(key=lambda x: (x[0], x[1]), reverse=True)   # newest first
    keep: set = set()
    seen_day: dict = {}
    seen_week: dict = {}
    seen_month: dict = {}
    for d, n in dated:
        if d not in seen_day:
            seen_day[d] = n
            if len(seen_day) <= daily:
                keep.add(n)
        wk = d.isocalendar()[:2]
        if wk not in seen_week:
            seen_week[wk] = n
            if len(seen_week) <= weekly:
                keep.add(n)
        mo = (d.year, d.month)
        if mo not in seen_month:
            seen_month[mo] = n
            if len(seen_month) <= monthly:
                keep.add(n)
    return [n for d, n in dated if n not in keep]


# ── 4. the run ───────────────────────────────────────────────────────

def run_backup(db_path: str | Path | None = None, prune: bool = True,
               dry_run: bool = False) -> dict:
    """Snapshot → gzip → OneDrive → prune. Records the run either way.
    Never raises: a backup failure must not take the scheduler down."""
    from . import database as db
    started = datetime.utcnow()
    res: dict = {"ok": False}
    run_id = None
    try:
        with db._connect(db_path) as conn:
            ensure_backup_table(conn)
            conn.execute("INSERT INTO backup_runs (status) VALUES ('running')")
            run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
    except Exception:
        logger.warning("could not record backup run start", exc_info=True)

    tmpdir = tempfile.mkdtemp(prefix="tgf-backup-")
    try:
        name = f"{BACKUP_PREFIX}{started.strftime('%Y%m%d_%H%M%S')}{BACKUP_SUFFIX}"
        raw = Path(tmpdir) / "snapshot.db"
        snap = snapshot_database(raw, db_path=db_path)
        if snap.get("error"):
            raise RuntimeError(snap["error"])
        gz = Path(tmpdir) / name
        gz_bytes = gzip_file(raw, gz)
        res.update({"name": name, "bytes_raw": snap["bytes"],
                    "bytes_gz": gz_bytes, "method": snap["method"],
                    "integrity": snap["integrity"]})

        creds = _graph_creds()
        if not creds:
            raise RuntimeError(
                "Graph credentials missing (AZURE_TENANT_ID / AZURE_CLIENT_ID "
                "/ AZURE_CLIENT_SECRET / EMAIL_ADDRESS)")
        if dry_run:
            res.update({"ok": True, "dry_run": True, "uploaded": False})
            return res
        token = _token(creds)
        if not token:
            raise RuntimeError("could not acquire a Graph token")
        folder = _folder(db_path)
        _upload(token, creds["user"], folder, name, gz)
        res["uploaded"] = True
        res["folder"] = folder

        if prune:
            remote = [f["name"] for f in
                      list_remote_backups(token, creds["user"], folder)]
            doomed = select_backups_to_delete(remote, today=started.date())
            deleted = [n for n in doomed
                       if _delete_remote(token, creds["user"], folder, n)]
            res["pruned"] = len(deleted)
            res["remote_total"] = len(remote) - len(deleted)
        res["ok"] = True
        return res
    except Exception as e:
        logger.exception("Database backup FAILED")
        res["error"] = str(e)
        _alert_failure(str(e), db_path=db_path)
        return res
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if run_id:
            try:
                with db._connect(db_path) as conn:
                    conn.execute(
                        "UPDATE backup_runs SET finished_at = datetime('now'), "
                        "status = ?, remote_name = ?, bytes_raw = ?, "
                        "bytes_gz = ?, pruned = ?, error = ? WHERE id = ?",
                        ("ok" if res.get("ok") else "failed", res.get("name"),
                         res.get("bytes_raw"), res.get("bytes_gz"),
                         res.get("pruned", 0), res.get("error"), run_id))
                    conn.commit()
            except Exception:
                logger.warning("could not record backup run finish", exc_info=True)


def _alert_failure(detail: str, db_path=None) -> None:
    """Email Kerry when a backup fails — throttled. A silently failing
    backup is the whole disaster, so this must not be quiet."""
    try:
        from . import database as db
        from .fetcher import send_mail_graph
        key = f"alert_sent_{_ALERT_KEY}"
        now = datetime.utcnow()
        try:
            last = db.get_app_setting(key, db_path=db_path) if db_path \
                else db.get_app_setting(key)
            if last and (now - datetime.fromisoformat(last[:19])) \
                    < timedelta(hours=ALERT_THROTTLE_HOURS):
                logger.info("backup failure alert suppressed (throttled)")
                return
        except Exception:
            pass
        creds = _graph_creds()
        to = os.getenv("COO_EMAIL_TO") or os.getenv("EMAIL_ADDRESS")
        if not creds or not to:
            logger.warning("backup failed and alert creds missing: %s", detail)
            return
        ok = send_mail_graph(
            tenant_id=creds["tenant_id"], client_id=creds["client_id"],
            client_secret=creds["client_secret"], from_address=creds["user"],
            to_address=to,
            subject="TGF ALERT: nightly database backup FAILED",
            html_body=(
                "<p>Hi Kerry,</p><p><strong>The nightly Tracker database "
                "backup did not complete.</strong> The Tracker itself is "
                "running normally — but until this is fixed, the only copy "
                "of the database is the live one on Railway.</p>"
                f"<p style='font-size:0.85rem;color:#6b7280;'>Detail: "
                f"{detail[:500]}</p>"
                "<p style='font-size:0.8rem;color:#9ca3af;'>At most one of "
                f"these every {ALERT_THROTTLE_HOURS} hours. &mdash; TGF System</p>"))
        if ok:
            db.set_app_setting(key, now.isoformat(timespec="seconds"))
    except Exception:
        logger.warning("backup failure alert itself failed", exc_info=True)


# ── 5. the restore drill ─────────────────────────────────────────────

def verify_latest_backup(db_path: str | Path | None = None) -> dict:
    """Pull the NEWEST remote backup back down, decompress it, run
    SQLite's integrity check, and compare row counts against the live
    database. This is the drill: until it passes once, we do not know we
    have backups — we only believe it."""
    from . import database as db
    creds = _graph_creds()
    if not creds:
        return {"error": "Graph credentials missing"}
    token = _token(creds)
    if not token:
        return {"error": "could not acquire a Graph token"}
    folder = _folder(db_path)
    files = list_remote_backups(token, creds["user"], folder)
    if not files:
        return {"error": f"no backups found in OneDrive /{folder}"}
    newest = sorted(files, key=lambda f: f["name"])[-1]
    tmpdir = tempfile.mkdtemp(prefix="tgf-verify-")
    try:
        r = requests.get(
            f"{GRAPH_BASE}/users/{creds['user']}/drive/root:/{folder}/"
            f"{newest['name']}:/content",
            headers={"Authorization": f"Bearer {token}"}, timeout=300)
        r.raise_for_status()
        gz = Path(tmpdir) / newest["name"]
        gz.write_bytes(r.content)
        restored = Path(tmpdir) / "restored.db"
        with gzip.open(gz, "rb") as f_in, open(restored, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        conn = sqlite3.connect(str(restored))
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            restored_counts = {}
            for t in VERIFY_TABLES:
                try:
                    restored_counts[t] = conn.execute(
                        f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                except sqlite3.Error:
                    restored_counts[t] = None
        finally:
            conn.close()

        live_counts = {}
        with db._connect(db_path) as live:
            for t in VERIFY_TABLES:
                try:
                    live_counts[t] = live.execute(
                        f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                except sqlite3.Error:
                    live_counts[t] = None

        # The live DB only ever grows, so restored <= live is expected;
        # restored > live means the snapshot is not what we think it is.
        drift = {t: {"restored": restored_counts.get(t), "live": live_counts.get(t)}
                 for t in VERIFY_TABLES
                 if restored_counts.get(t) is not None
                 and live_counts.get(t) is not None
                 and restored_counts[t] > live_counts[t]}
        return {"ok": integrity == "ok" and not drift,
                "backup": newest["name"],
                "backup_bytes": newest.get("size"),
                "taken_at": newest.get("lastModifiedDateTime"),
                "integrity": integrity,
                "restored_counts": restored_counts,
                "live_counts": live_counts,
                "unexpected_drift": drift or None,
                "remote_backup_count": len(files)}
    except Exception as e:
        logger.exception("backup verification failed")
        return {"error": str(e)}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def backup_status(db_path: str | Path | None = None) -> dict:
    """Last few runs + whether the whole thing is even configured."""
    from . import database as db
    out = {"graph_configured": bool(_graph_creds()),
           "folder": _folder(db_path), "runs": []}
    try:
        with db._connect(db_path) as conn:
            ensure_backup_table(conn)
            out["runs"] = [dict(r) for r in conn.execute(
                "SELECT * FROM backup_runs ORDER BY id DESC LIMIT 10")]
    except Exception as e:
        out["error"] = str(e)
    last_ok = next((r for r in out["runs"] if r.get("status") == "ok"), None)
    out["last_success"] = last_ok.get("finished_at") if last_ok else None
    out["healthy"] = bool(last_ok) and (out["runs"][0].get("status") == "ok"
                                        if out["runs"] else False)
    return out


# ── DOC MIRROR TO ONEDRIVE (Kerry 2026-09-03) ────────────────────────
# The Claude M365 connector is READ-ONLY by design — its Entra app
# requests Files.Read / Files.Read.All and no write scope at all, so a
# session cannot save anything to OneDrive no matter who consents.
#
# The Tracker can, because its own app registration was granted
# Files.ReadWrite.All for the nightly backup. So the repo stays the
# source of truth and the Tracker pushes a MIRROR into OneDrive: every
# doc Claude writes lands in Kerry's folders without anyone remembering
# to drag a file. Kerry: "Nothing can fall thru the cracks."
#
# Routing follows his existing filing system rather than inventing one:
#   Update_Fragment_*.md  → 06_STRATEGY/Update_Fragments
#   everything else       → 7_Web & App Development/TGF Transaction Tracker/Tracker Docs
DOCS_FOLDER_DEFAULT = "7_Web & App Development/TGF Transaction Tracker/Tracker Docs"
FRAGMENTS_FOLDER_DEFAULT = "06_STRATEGY/Update_Fragments"


def _doc_targets(db_path=None) -> dict:
    from . import database as db
    def _dial(key, default):
        try:
            v = (db.get_app_setting(key, db_path=db_path) if db_path
                 else db.get_app_setting(key))
        except Exception:
            v = None
        return (v or default).strip("/")
    return {"docs": _dial("onedrive_docs_folder", DOCS_FOLDER_DEFAULT),
            "fragments": _dial("onedrive_fragments_folder",
                               FRAGMENTS_FOLDER_DEFAULT)}


def _folder_for(name: str, targets: dict) -> str:
    return targets["fragments"] if name.startswith("Update_Fragment") \
        else targets["docs"]


def mirror_docs_to_onedrive(db_path: str | Path | None = None,
                            dry_run: bool = False,
                            only: str = "") -> dict:
    """Push the Tracker's living docs (CLAUDE.md + docs/claude/*.md) into
    OneDrive. Idempotent — every run replaces, so it is safe to schedule
    and safe to re-run. `only` uploads a single filename."""
    root = Path(__file__).resolve().parent.parent
    docs: list[Path] = []
    claude_md = root / "CLAUDE.md"
    if claude_md.is_file():
        docs.append(claude_md)
    docs_dir = root / "docs" / "claude"
    if docs_dir.is_dir():
        docs.extend(sorted(docs_dir.glob("*.md")))
    if only:
        docs = [d for d in docs if d.name == only]
        if not docs:
            return {"error": f"no doc named {only!r}"}

    targets = _doc_targets(db_path)
    res: dict = {"targets": targets, "found": len(docs), "uploaded": 0,
                 "skipped_too_big": [], "errors": [], "files": []}
    if dry_run:
        res["files"] = [{"name": d.name, "folder": _folder_for(d.name, targets),
                         "bytes": d.stat().st_size} for d in docs]
        res["dry_run"] = True
        return res

    creds = _graph_creds()
    if not creds:
        res["errors"].append("Graph credentials missing")
        return res
    token = _token(creds)
    if not token:
        res["errors"].append("could not acquire a Graph token")
        return res

    for d in docs:
        size = d.stat().st_size
        if size > SIMPLE_UPLOAD_LIMIT:
            # Docs are markdown; anything over 4 MB is not a doc.
            res["skipped_too_big"].append(d.name)
            continue
        folder = _folder_for(d.name, targets)
        try:
            _upload(token, creds["user"], folder, d.name, d)
            res["uploaded"] += 1
            res["files"].append({"name": d.name, "folder": folder,
                                 "bytes": size})
        except Exception as e:
            logger.warning("doc mirror failed for %s: %s", d.name, e)
            res["errors"].append(f"{d.name}: {e}")
    res["ok"] = not res["errors"]
    return res
