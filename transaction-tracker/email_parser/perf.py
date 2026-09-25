"""The Tracker measures itself (Tracker Health & Performance lane, 2026-09-22).

Kerry, after the 41-second PAIRINGS open: *"We need to add in those types
of elements across the Tracker so that we can track and improve
performance. Probably need an agent specifically designed for this that
will log things and report back to you and the COO for you to pick up.
Should be a standard once a day routine."*

ONE stopwatch for every heavy path — a request, a scheduler job, an MCP
bridge — instead of a private `_lap()` per route. Every sample lands in
`perf_samples` (the whole distribution, not only the slow ones: p50 and
p95 need the fast opens too), and a slow one ALSO writes the
`agent_action_log` row the v2.484.3 pattern already taught Kerry to read
(`<name>_slow`, the breakdown in the description).

Why the samples never touch the request thread's connection: the thing
being measured is, on the evidence so far, a cost every section pays
(a connection open, a lock wait, another thread holding the GIL). A
synchronous INSERT per request would add one more write-lock touch to
exactly that path. Samples queue in memory and a daemon thread writes
them in one transaction every few seconds; `flush()` exists for tests
and for the digest, which wants everything on disk before it reads.

What a sample carries beside its sections — because "where did the time
go" has two very different answers, "in this code" and "waiting on
something else": `load1` (the box's one-minute load average) and
`concurrent` (every other stopwatch that was running when this one
started — the scheduler job, the other request). Two 11-second opens
ten seconds apart with the time spread evenly over four unrelated
sections is not a slow function; it is contention, and the sample
should be able to say with what.
"""
from __future__ import annotations

import functools
import json
import logging
import os
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ── thresholds: rules as data ───────────────────────────────────────────
# A path over its threshold is logged as SLOW (agent_action_log +
# status). The dial `perf_slow_ms` (app_settings, JSON {name: ms})
# overrides any entry without a deploy; unknown names take the kind's
# default. The pairings number is the v2.484.3 one.
SLOW_MS_DEFAULT = {"route": 2000, "job": 120_000, "bridge": 10_000}
SLOW_MS = {
    "pairings_get": 4000,
    "items_list": 1500,
    "events_list": 1500,
    "hcp_index_map": 1500,
    "rsvps_bulk": 1500,
    "flights_board": 2500,
    "print_pack_pdf": 15_000,        # headless Chromium renders
    "coo_context": 6000,
    "customers_list": 1500,
    "dashboard_api": 2500,
    "auto_pairings_grab": 400_000,   # budgeted at 280 s per portal
    "spotlight_player": 2500,
    "spotlight_warm": 30_000,        # the job that pays the cold cost instead of a page
    "scoring-gg-archive": 120_000,   # migrate ~14 s / cutover ~19 s / backup upload ~86 s on 2026-09-25
    "db_backup": 300_000,            # VACUUM INTO + gzip + OneDrive upload of a 430 MB file (~145 s)
    # Bridges that SEND — one Graph call per recipient — are long by nature
    "scoring-hcp-cards": 60_000,     # a card email per player who played (9/23: 18.7 s for 23)
    "scoring-print-pack-pdf": 60_000,
    "scoring-recap-draft-email": 30_000,
    "auto_gg_results_sync": 600_000,
}
RETENTION_DAYS = 30
FLUSH_INTERVAL_S = 3.0
# Keep a sample's breakdown readable — a job with hundreds of laps is a
# trace, not a breakdown. The largest N laps are kept, the rest summed.
MAX_BREAKDOWN_KEYS = 24

_QUEUE: deque = deque()
_ENSURED_PATHS: set = set()   # files whose perf_samples table this process has created
_LOCK = threading.Lock()
_INFLIGHT: dict = {}          # id(stopwatch) -> stopwatch
_FLUSHER: threading.Thread | None = None
_SLOW_DIAL: dict = {"at": 0.0, "value": {}}
# Set by tests / the digest to a specific file; None means DB_PATH.
_DB_PATH_OVERRIDE = None
DISABLED = os.getenv("PERF_SAMPLES", "1").strip().lower() in ("0", "off", "false")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _db_path(db_path=None):
    if db_path is not None:
        return db_path
    if _DB_PATH_OVERRIDE is not None:
        return _DB_PATH_OVERRIDE
    from .database import DB_PATH
    return DB_PATH


def ensure_table(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS perf_samples (
               id         INTEGER PRIMARY KEY AUTOINCREMENT,
               at         TEXT NOT NULL,
               kind       TEXT NOT NULL,
               name       TEXT NOT NULL,
               event_id   INTEGER,
               total_ms   INTEGER NOT NULL,
               breakdown  TEXT,
               status     TEXT NOT NULL DEFAULT 'ok',
               role       TEXT,
               detail     TEXT
           )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_perf_samples_at ON perf_samples(at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_perf_samples_name_at "
                 "ON perf_samples(name, at)")


def slow_threshold(kind: str, name: str, db_path=None) -> int:
    """The SLOW line for a path: the dial wins, then the table, then the
    kind's default. The dial is re-read at most once a minute."""
    now = time.time()
    if now - _SLOW_DIAL["at"] > 60:
        val = {}
        try:
            from .database import get_app_setting
            raw = get_app_setting("perf_slow_ms", db_path=_db_path(db_path))
            if raw:
                val = {str(k): int(v) for k, v in json.loads(raw).items()}
        except Exception:
            val = {}
        _SLOW_DIAL["value"], _SLOW_DIAL["at"] = val, now
    v = _SLOW_DIAL["value"].get(name)
    if v is not None:
        return int(v)
    return int(SLOW_MS.get(name, SLOW_MS_DEFAULT.get(kind, 2000)))


def _load1() -> float | None:
    try:
        return round(os.getloadavg()[0], 2)
    except (AttributeError, OSError):
        return None


def _current_role() -> str | None:
    """The session role behind a request sample; None outside a request."""
    try:
        from flask import has_request_context, session
        if has_request_context():
            return session.get("role") or "anon"
    except Exception:
        pass
    return None


class Stopwatch:
    """Per-section laps for one measured thing.

        sw = Stopwatch("route", "pairings_get", event_id=3309)
        ...; sw.lap("saved_sheet"); ...; sw.lap("roster")
        sw.finish()          # queues the sample; logs it if slow

    `snapshot()` is the `timings_ms` a JSON answer carries — the laps so
    far plus their sum — so a route can put the numbers in its payload
    before the decorator closes the sample with the true total.
    """

    def __init__(self, kind: str, name: str, slow_ms: int | None = None,
                 event_id: int | None = None, role: str | None = None,
                 db_path=None):
        self.kind, self.name = kind, name
        self.event_id = event_id
        self.role = role if role is not None else (
            _current_role() or {"job": "scheduler", "bridge": "mcp"}.get(kind))
        self.db_path = db_path
        self.slow_ms = slow_ms
        self.started_at = _utcnow_iso()
        self._t_start = time.perf_counter()
        self._t_lap = self._t_start
        self.laps: dict = {}
        self.detail: dict = {}
        self.status: str | None = None
        self._done = False
        self.load1 = _load1()
        with _LOCK:
            self.concurrent = sorted({f"{s.kind}:{s.name}" for s in _INFLIGHT.values()})
            _INFLIGHT[id(self)] = self

    # ── laps ──
    def lap(self, label: str) -> int:
        """Close the section that began at the previous lap (or the
        start) under `label`; returns its ms. A repeated label adds up."""
        now = time.perf_counter()
        ms = int(round((now - self._t_lap) * 1000))
        self._t_lap = now
        self.laps[label] = self.laps.get(label, 0) + ms
        return ms

    def mark(self) -> None:
        """Start a section here without closing one (skip the gap)."""
        self._t_lap = time.perf_counter()

    def elapsed_ms(self) -> int:
        return int(round((time.perf_counter() - self._t_start) * 1000))

    def note(self, **kv) -> None:
        self.detail.update(kv)

    def snapshot(self) -> dict:
        out = dict(self.laps)
        out["total"] = sum(self.laps.values())
        return out

    # ── close ──
    def discard(self) -> None:
        self._done = True
        with _LOCK:
            _INFLIGHT.pop(id(self), None)

    def finish(self, status: str | None = None, error: str | None = None) -> dict:
        if self._done:
            return self.snapshot()
        self._done = True
        with _LOCK:
            _INFLIGHT.pop(id(self), None)
        total = self.elapsed_ms()
        # Whatever ran after the last lap is a section too.
        tail = total - sum(self.laps.values())
        if tail > 0 and self.laps:
            self.laps["_rest"] = tail
        threshold = self.slow_ms if self.slow_ms is not None else slow_threshold(
            self.kind, self.name, self.db_path)
        self.status = status or ("error" if error else ("slow" if total > threshold else "ok"))
        detail = dict(self.detail)
        if error:
            detail["error"] = str(error)[:500]
        if self.load1 is not None:
            detail["load1"] = self.load1
        if self.concurrent:
            detail["concurrent"] = self.concurrent
        sample = {
            "at": self.started_at, "kind": self.kind, "name": self.name,
            "event_id": self.event_id, "total_ms": total,
            "breakdown": _compact_breakdown(self.laps), "status": self.status,
            "role": self.role, "detail": detail or None,
        }
        _enqueue(sample, self.db_path)
        if self.status == "slow" or (self.status == "error" and self.kind != "route"):
            _log_slow(sample)
        out = self.snapshot()
        out["total"] = total
        return out

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.finish(error=repr(exc) if exc else None)
        return False


def _compact_breakdown(laps: dict) -> dict:
    if len(laps) <= MAX_BREAKDOWN_KEYS:
        return dict(laps)
    items = sorted(laps.items(), key=lambda kv: -kv[1])
    keep = dict(items[:MAX_BREAKDOWN_KEYS])
    keep["_other"] = sum(v for _, v in items[MAX_BREAKDOWN_KEYS:])
    return keep


def _log_slow(sample: dict) -> None:
    """The agent_action_log row Kerry already reads (v2.484.3 shape)."""
    try:
        from .database import log_agent_action
        bd = sample.get("breakdown") or {}
        worst = ", ".join(f"{k} {v} ms" for k, v in sorted(
            bd.items(), key=lambda kv: -kv[1])[:4])
        ev = f"event {sample['event_id']}: " if sample.get("event_id") else ""
        detail = sample.get("detail") or {}
        extra = ""
        if detail.get("concurrent"):
            extra += f" — while {', '.join(detail['concurrent'])} ran"
        if detail.get("error"):
            extra += f" — {detail['error'][:160]}"
        log_agent_action(
            "app", f"{sample['name']}_{sample['status']}",
            f"{ev}{sample['total_ms']} ms — {worst}{extra}",
            db_path=_db_path(sample.get("_db_path")))
    except Exception:
        logger.debug("perf: slow-log write failed (non-fatal)", exc_info=True)


# ── the queue and its flusher ───────────────────────────────────────────
def _enqueue(sample: dict, db_path=None) -> None:
    if DISABLED:
        return
    sample["_db_path"] = db_path
    with _LOCK:
        _QUEUE.append(sample)
    _start_flusher()


def _start_flusher() -> None:
    global _FLUSHER
    if _FLUSHER is not None and _FLUSHER.is_alive():
        return
    with _LOCK:
        if _FLUSHER is not None and _FLUSHER.is_alive():
            return
        t = threading.Thread(target=_flush_loop, name="perf-flush", daemon=True)
        _FLUSHER = t
        t.start()


def _flush_loop() -> None:
    while True:
        time.sleep(FLUSH_INTERVAL_S)
        try:
            flush()
        except Exception:
            logger.debug("perf: flush failed (retried next tick)", exc_info=True)


def flush(db_path=None) -> int:
    """Write every queued sample. Returns how many were written. Samples
    queued against another database are left for their own flush."""
    with _LOCK:
        pending = list(_QUEUE)
        _QUEUE.clear()
    if not pending:
        return 0
    target = str(_db_path(db_path))
    mine = [s for s in pending if str(_db_path(s.get("_db_path"))) == target]
    others = [s for s in pending if s not in mine]
    if others:
        with _LOCK:
            _QUEUE.extendleft(reversed(others))
    if not mine:
        return 0
    try:
        conn = sqlite3.connect(target, timeout=10)
        try:
            if target not in _ENSURED_PATHS:
                ensure_table(conn)
                _ENSURED_PATHS.add(target)
            conn.executemany(
                """INSERT INTO perf_samples
                   (at, kind, name, event_id, total_ms, breakdown, status, role, detail)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(s["at"], s["kind"], s["name"], s.get("event_id"), s["total_ms"],
                  json.dumps(s.get("breakdown") or {}), s["status"], s.get("role"),
                  json.dumps(s["detail"]) if s.get("detail") else None)
                 for s in mine])
            conn.commit()
        finally:
            conn.close()
        return len(mine)
    except sqlite3.Error:
        # Put them back; the next tick tries again. Never lose a sample
        # to a busy lock, and never raise into the thread that measured.
        with _LOCK:
            _QUEUE.extendleft(reversed(mine))
        raise


def record(kind: str, name: str, total_ms: int, breakdown: dict | None = None,
           status: str = "ok", event_id: int | None = None, role: str | None = None,
           detail: dict | None = None, db_path=None) -> None:
    """A sample measured elsewhere (a client-reported paint, a one-off)."""
    _enqueue({"at": _utcnow_iso(), "kind": kind, "name": name, "event_id": event_id,
              "total_ms": int(total_ms), "breakdown": breakdown or {},
              "status": status, "role": role, "detail": detail}, db_path)


# ── decorators ──────────────────────────────────────────────────────────
_LOCAL = threading.local()


def current() -> Stopwatch | None:
    """The route stopwatch for this thread, if a timed route is running —
    so a view (or something it calls) can `perf.current().lap("x")`."""
    return getattr(_LOCAL, "sw", None)


def timed_route(name: str, slow_ms: int | None = None, event_arg: str = "event_id"):
    """Wrap a Flask view. The sample closes when the view returns (or
    raises — status 'error', and the exception continues up to Flask's
    handler as before). `perf.current()` is the stopwatch inside."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            sw = Stopwatch("route", name, slow_ms=slow_ms, event_id=kw.get(event_arg))
            prev = getattr(_LOCAL, "sw", None)
            _LOCAL.sw = sw
            try:
                resp = fn(*a, **kw)
            except Exception as exc:
                sw.finish(error=repr(exc))
                raise
            finally:
                _LOCAL.sw = prev
            code = None
            try:
                code = resp[1] if isinstance(resp, tuple) else getattr(resp, "status_code", None)
            except Exception:
                code = None
            if code is not None:
                sw.note(http=int(code))
            sw.finish(status="error" if (code or 200) >= 500 else None)
            return resp
        return wrapper
    return deco


def timed_job(fn, name: str | None = None):
    """Wrap a scheduler callable so every run is a sample. Exceptions
    propagate exactly as before (APScheduler logs them); the sample says
    'error' and carries the message. Idempotent — wrapping a wrapped job
    returns it unchanged."""
    if getattr(fn, "_perf_job", False):
        return fn
    jname = name or getattr(fn, "__name__", "job")

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        sw = Stopwatch("job", jname)
        try:
            out = fn(*a, **kw)
        except Exception as exc:
            sw.finish(error=repr(exc))
            raise
        sw.finish()
        return out
    wrapper._perf_job = True
    return wrapper


def timed_call(kind: str, name: str, fn, *a, event_id=None, **kw):
    """Run `fn(*a, **kw)` under a stopwatch (a bridge, a context build)."""
    sw = Stopwatch(kind, name, event_id=event_id)
    try:
        out = fn(*a, **kw)
    except Exception as exc:
        sw.finish(error=repr(exc))
        raise
    sw.finish()
    return out


# ── reading the samples ─────────────────────────────────────────────────
def _pct(sorted_vals: list, p: float) -> int:
    """Nearest-rank percentile: with five opens, the p95 IS the slowest
    one. Interpolating would report 808 ms for (300, 400, 500, 6000,
    9000) and hide the two slow opens a digest exists to show."""
    if not sorted_vals:
        return 0
    import math
    k = max(1, math.ceil(p * len(sorted_vals))) - 1
    return int(sorted_vals[min(k, len(sorted_vals) - 1)])


def _since(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def samples(days: float = 1, name: str | None = None, kind: str | None = None,
            limit: int = 500, db_path=None) -> list[dict]:
    clauses, params = ["at >= ?"], [_since(days)]
    if name:
        clauses.append("name = ?"); params.append(name)
    if kind:
        clauses.append("kind = ?"); params.append(kind)
    conn = sqlite3.connect(str(_db_path(db_path)), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        ensure_table(conn)
        rows = conn.execute(
            f"SELECT * FROM perf_samples WHERE {' AND '.join(clauses)} "
            f"ORDER BY at DESC, id DESC LIMIT ?", params + [limit]).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("breakdown", "detail"):
            try:
                d[k] = json.loads(d[k]) if d.get(k) else ({} if k == "breakdown" else None)
            except (TypeError, ValueError):
                pass
        out.append(d)
    return out


def summary(days: float = 1, db_path=None) -> dict:
    """p50 / p95 / max / count / slow / errors per measured name, split by
    kind, over the window. Reads the table directly (one query)."""
    conn = sqlite3.connect(str(_db_path(db_path)), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        ensure_table(conn)
        rows = conn.execute(
            "SELECT kind, name, total_ms, status FROM perf_samples WHERE at >= ? "
            "ORDER BY name", (_since(days),)).fetchall()
    finally:
        conn.close()
    by: dict = {}
    for r in rows:
        k = (r["kind"], r["name"])
        e = by.setdefault(k, {"kind": r["kind"], "name": r["name"], "vals": [],
                              "slow": 0, "errors": 0})
        e["vals"].append(r["total_ms"])
        if r["status"] == "slow":
            e["slow"] += 1
        elif r["status"] == "error":
            e["errors"] += 1
    out = {"route": [], "job": [], "bridge": [], "other": []}
    for e in by.values():
        v = sorted(e["vals"])
        row = {"name": e["name"], "count": len(v), "p50": _pct(v, .5),
               "p95": _pct(v, .95), "max": v[-1], "avg": int(round(sum(v) / len(v))),
               "slow": e["slow"], "errors": e["errors"],
               "slow_ms": slow_threshold(e["kind"], e["name"], db_path)}
        out.get(e["kind"], out["other"]).append(row)
    for k in out:
        out[k].sort(key=lambda r: -r["p95"])
    return out


def prune(days: int = RETENTION_DAYS, db_path=None) -> int:
    conn = sqlite3.connect(str(_db_path(db_path)), timeout=10)
    try:
        ensure_table(conn)
        cur = conn.execute("DELETE FROM perf_samples WHERE at < ?", (_since(days),))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def db_size(db_path=None) -> dict:
    """The database file and its WAL, in bytes — the growth number."""
    p = str(_db_path(db_path))
    out = {"path": p, "bytes": 0, "wal_bytes": 0}
    try:
        out["bytes"] = os.path.getsize(p)
    except OSError:
        pass
    try:
        out["wal_bytes"] = os.path.getsize(p + "-wal")
    except OSError:
        pass
    return out


def disk_usage(db_path=None) -> dict:
    """The VOLUME the database sits on — total / used / free bytes and the
    used percentage. 2026-09-22, 8:46 PM: the 500 MB Railway volume hit
    99% (431 MB file + WAL), SQLite could not grow the WAL/shm, and every
    data read raised until Kerry resized it from his phone. Railway had
    mailed a 95% warning three days earlier; it sat in the action items
    at confidence 45. This number is on the health report, /api/health
    and the 5:00 AM digest so the app itself says it first."""
    p = str(_db_path(db_path))
    out = {"total_bytes": None, "used_bytes": None, "free_bytes": None, "pct_used": None}
    try:
        import shutil
        u = shutil.disk_usage(os.path.dirname(os.path.abspath(p)) or ".")
        out.update({"total_bytes": u.total, "used_bytes": u.used, "free_bytes": u.free,
                    "pct_used": round(100.0 * u.used / u.total, 1) if u.total else None})
    except (OSError, ValueError):
        pass
    return out


def db_layout(db_path=None, top: int = 12) -> dict:
    """WHERE the bytes are: page size / count, FREE pages (space deleted
    rows left behind — a VACUUM candidate when large), and the biggest
    tables + indexes by bytes via the dbstat virtual table (present in
    every CPython build; reported as unavailable otherwise). The live file
    read 431 MB for ~2,300 orders on 2026-09-22 — this is how the digest
    says which table that is."""
    out = {"page_size": None, "page_count": None, "freelist_pages": None,
           "free_bytes": None, "tables": [], "dbstat": True}
    conn = sqlite3.connect(str(_db_path(db_path)), timeout=10)
    try:
        ps = conn.execute("PRAGMA page_size").fetchone()[0]
        pc = conn.execute("PRAGMA page_count").fetchone()[0]
        fl = conn.execute("PRAGMA freelist_count").fetchone()[0]
        out.update(page_size=ps, page_count=pc, freelist_pages=fl, free_bytes=ps * fl)
        try:
            rows = conn.execute(
                "SELECT name, SUM(pgsize) AS bytes, COUNT(*) AS pages FROM dbstat "
                "GROUP BY name ORDER BY bytes DESC LIMIT ?", (top,)).fetchall()
            kinds = {r[0]: r[1] for r in conn.execute(
                "SELECT name, type FROM sqlite_master WHERE type IN ('table','index')")}
            out["tables"] = [{"name": r[0], "bytes": int(r[1] or 0), "pages": r[2],
                              "type": kinds.get(r[0], "?")} for r in rows]
        except sqlite3.Error:
            out["dbstat"] = False
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return out


def probe_db_ms(db_path=None) -> dict:
    """How long a bare connection open + a one-row read takes right now —
    the number that tells "the code is slow" from "every touch of the
    file is slow" (a busy lock, a cold page cache on a network volume)."""
    t0 = time.perf_counter()
    conn = sqlite3.connect(str(_db_path(db_path)), timeout=10)
    t1 = time.perf_counter()
    try:
        conn.execute("PRAGMA journal_mode").fetchone()
        t2 = time.perf_counter()
        conn.execute("SELECT id FROM items ORDER BY id DESC LIMIT 1").fetchone()
        t3 = time.perf_counter()
    except sqlite3.Error:
        t2 = t3 = time.perf_counter()
    finally:
        conn.close()
    return {"connect_ms": int(round((t1 - t0) * 1000)),
            "pragma_ms": int(round((t2 - t1) * 1000)),
            "read_ms": int(round((t3 - t2) * 1000))}
