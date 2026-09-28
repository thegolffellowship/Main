"""The DRESS REHEARSAL scratch copy + the restore drill (CA #800/#801,
Kerry 2026-09-27: "Why not have it test run tonight?"; restore drill #728).

Two halves, because only the production app holds the OneDrive credentials
and the rehearsal lanes run in their own Claude Code sandboxes:

ON PRODUCTION (bridge ``scoring-rehearsal:<step>``)
  ``restore()``  — the restore drill. Pulls the NEWEST nightly backup from
                   OneDrive, gunzips it, runs ``PRAGMA integrity_check``,
                   compares row counts with the live file, and times every
                   step. The live database is only READ (counts).
  ``scrub()``    — on the restored copy, never on the live file: every
                   contact / secret column is blanked (emails become
                   ``r<table>-<rowid>@rehearsal.invalid``, phones / addresses
                   / birthdays / message bodies / tokens become NULL or ''),
                   secret-looking app_settings rows are emptied, then the
                   copy is rewritten with ``VACUUM INTO`` so no free page
                   still holds a scrubbed value. Names, scores, events,
                   money and ids stay — the replay needs them.
  There is NO download path: the copy stays on the production volume.
                   (A token-gated download to the lanes' sandboxes was built
                   and refused on 2026-09-27 as data leaving Railway; how the
                   lanes reach the copy is Kerry's decision.)
  Files live in ``<volume>/rehearsal/`` beside the live database, never at
  ``DB_PATH``. Nothing here writes to the live database except the drill
  record in ``app_settings`` (``rehearsal_drill``).

IN A LANE'S SANDBOX (``guard()``)
  With ``TGF_REHEARSAL=1`` in the environment, importing ``email_parser``
  installs a socket guard: every outbound connection that is not loopback
  raises ``RehearsalOutboundBlocked``. That is ONE check for EVERY channel —
  Graph mail, Brevo, Stripe, Twilio/SMS, Golf Genius, Meta, HubSpot,
  Anthropic — present and future, instead of a flag per sender (the
  protect-the-class rule). ``app.py`` also refuses to start the scheduler
  in rehearsal mode. ``test_rehearsal.py`` proves both.
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import sys
import re
import shutil
import socket
import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DIRNAME = "rehearsal"
SCRUBBED = "tracker_rehearsal.db"
SCRUBBED_GZ = "tracker_rehearsal.db.gz"
SETTING_DRILL = "rehearsal_drill"

# Column-name patterns that carry contact details, secrets or raw message
# text. Matched against every column of every table in the COPY.
_EMAIL_COL = re.compile(r"e_?mail", re.I)
_BLANK_COL = re.compile(
    r"phone|mobile|sms|address|street|zip|postal|birth|dob\b|ssn|venmo_(user|handle)|payment_handle"
    r"|token|secret|password|passcode|pin_hash|api_key|ip_addr|user_agent"
    r"|body|html|raw_text|raw_email|message_text|card_last|last4", re.I)
_SECRET_SETTING = re.compile(r"token|secret|password|api_key|refresh|cookie|session", re.I)
# Columns the replay needs even though a pattern would catch them.
_KEEP = {("gg_raw_archive", "body_gz")}


class RehearsalOutboundBlocked(ConnectionError):
    """Raised for any non-loopback connection while TGF_REHEARSAL=1."""


# ── the sandbox side: every outbound channel off ────────────────────────

_ORIG_CREATE = socket.create_connection
_ORIG_CONNECT = socket.socket.connect
_ORIG_CONNECT_EX = socket.socket.connect_ex
_ORIG_GETADDRINFO = socket.getaddrinfo
_GUARDED = False
BLOCKED: list = []          # every refused destination, for the proof test


def active() -> bool:
    return os.getenv("TGF_REHEARSAL", "") == "1"


_PROXY_ENV = ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy")
_BLOCKED_LOCAL_PORTS: set = set()


def _loopback(host) -> bool:
    h = str(host or "").strip("[]").lower()
    return h in ("localhost", "::1", "") or h.startswith("127.") or h.startswith("/")


def _allowed(address) -> bool:
    """Loopback only — and never a local egress proxy, which would carry the
    connection out (a Claude Code sandbox routes HTTPS through 127.0.0.1)."""
    host = _host_of(address)
    if not _loopback(host):
        return False
    port = address[1] if isinstance(address, (tuple, list)) and len(address) > 1 else None
    return port not in _BLOCKED_LOCAL_PORTS


def _host_of(address):
    if isinstance(address, (tuple, list)) and address:
        return address[0]
    return address


def guard() -> bool:
    """Install the outbound guard (idempotent). Returns True when active."""
    global _GUARDED
    if not active() or _GUARDED:
        return _GUARDED

    def _refuse(host):
        BLOCKED.append(str(host))
        raise RehearsalOutboundBlocked(
            f"TGF_REHEARSAL=1: outbound connection to {host!r} refused — "
            "no email, SMS, Brevo, Stripe, Golf Genius or any other send "
            "leaves a rehearsal")

    # A local egress proxy would carry a "loopback" connection out: note its
    # port as blocked and drop the proxy settings so clients connect direct
    # (and hit the guard).
    from urllib.parse import urlparse
    for k in _PROXY_ENV:
        v = os.environ.pop(k, None)
        if v:
            try:
                u = urlparse(v if "://" in v else "http://" + v)
                if u.port:
                    _BLOCKED_LOCAL_PORTS.add(u.port)
            except ValueError:
                pass

    def create_connection(address, *a, **kw):
        if not _allowed(address):
            _refuse(address)
        return _ORIG_CREATE(address, *a, **kw)

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _allowed(address):
            _refuse(address)
        return _ORIG_CONNECT(self, address)

    def connect_ex(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _allowed(address):
            _refuse(address)
        return _ORIG_CONNECT_EX(self, address)

    def getaddrinfo(host, *a, **kw):
        if not _loopback(host):
            _refuse(host)
        return _ORIG_GETADDRINFO(host, *a, **kw)

    socket.create_connection = create_connection
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo
    _GUARDED = True
    logger.warning("TGF_REHEARSAL=1 — outbound network guard installed; "
                   "every non-loopback connection is refused")
    return True


# ── the production side: restore drill, scrub, link ─────────────────────

def rehearsal_dir(db_path=None) -> Path:
    from .database import DB_PATH
    return Path(str(db_path or DB_PATH)).parent / DIRNAME


def _counts(conn) -> dict:
    out = {}
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                             "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
        try:
            out[t] = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except sqlite3.Error:
            out[t] = None
    return out


def scrub(path) -> dict:
    """Blank contact details and secrets in a restored COPY (never the live
    file), then rewrite it so freed pages keep nothing. Returns what it did."""
    from .database import DB_PATH
    path = Path(str(path))
    if path.resolve() == Path(str(DB_PATH)).resolve():
        raise ValueError("scrub() refuses the live database path")
    conn = sqlite3.connect(str(path))
    done = {"columns": [], "settings_blanked": 0}
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for t in tables:
            cols = conn.execute(f'PRAGMA table_info("{t}")').fetchall()
            for _cid, name, ctype, notnull, _dflt, pk in cols:
                if pk or (t, name) in _KEEP:
                    continue
                if _EMAIL_COL.search(name) and not re.search(r"sent|count|opt|status|_at$|_on$|verified|bounce", name, re.I):
                    conn.execute(
                        f'UPDATE "{t}" SET "{name}" = \'r{t}-\' || rowid || \'@rehearsal.invalid\' '
                        f'WHERE "{name}" IS NOT NULL AND "{name}" != \'\'')
                    done["columns"].append(f"{t}.{name}")
                elif _BLANK_COL.search(name) and "INT" not in (ctype or "").upper() \
                        and not re.search(r"_at$|_on$|count|flag", name, re.I):
                    # NULL never collides with a UNIQUE index; a NOT NULL
                    # column gets a per-row placeholder for the same reason
                    # (recurring_payments.merchant_token, 2026-09-27).
                    val = f"'redacted-' || rowid" if notnull else "NULL"
                    conn.execute(f'UPDATE "{t}" SET "{name}" = {val} '
                                 f'WHERE "{name}" IS NOT NULL')
                    done["columns"].append(f"{t}.{name}")
        if "app_settings" in tables:
            rows = conn.execute("SELECT key FROM app_settings").fetchall()
            for (k,) in rows:
                if _SECRET_SETTING.search(k or ""):
                    conn.execute("UPDATE app_settings SET value = '' WHERE key = ?", (k,))
                    done["settings_blanked"] += 1
        conn.commit()
    finally:
        conn.close()
    # Rewrite so no free page still holds a scrubbed value.
    tmp = path.with_suffix(".vacuumed")
    if tmp.exists():
        tmp.unlink()
    c2 = sqlite3.connect(str(path))
    try:
        c2.execute("VACUUM INTO ?", (str(tmp),))
    finally:
        c2.close()
    os.replace(tmp, path)
    return done


def restore(db_path=None) -> dict:
    """THE RESTORE DRILL into the rehearsal folder: newest OneDrive backup →
    gunzip → integrity → counts vs live → scrub → gzip. Times each step."""
    import requests
    from . import backups
    from .database import DB_PATH, _connect, set_app_setting
    live = Path(str(db_path or DB_PATH))
    rdir = rehearsal_dir(live)
    rdir.mkdir(parents=True, exist_ok=True)
    t = {}
    t0 = time.perf_counter()
    creds = backups._graph_creds()
    if not creds:
        return {"ok": False, "error": "Graph credentials missing"}
    token = backups._token(creds)
    if not token:
        return {"ok": False, "error": "could not acquire a Graph token"}
    folder = backups._folder(live)
    files = backups.list_remote_backups(token, creds["user"], folder)
    if not files:
        return {"ok": False, "error": f"no backups in OneDrive /{folder}"}
    newest = sorted(files, key=lambda f: f["name"])[-1]
    tmpdir = Path(tempfile.mkdtemp(prefix="tgf-rehearsal-", dir=str(rdir)))
    try:
        r = requests.get(
            f"{backups.GRAPH_BASE}/users/{creds['user']}/drive/root:/{folder}/"
            f"{newest['name']}:/content",
            headers={"Authorization": f"Bearer {token}"}, timeout=600)
        r.raise_for_status()
        gz = tmpdir / newest["name"]
        gz.write_bytes(r.content)
        t["download_ms"] = int((time.perf_counter() - t0) * 1000)
        t1 = time.perf_counter()
        restored = tmpdir / "restored.db"
        with gzip.open(gz, "rb") as f_in, open(restored, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        t["gunzip_ms"] = int((time.perf_counter() - t1) * 1000)
        t2 = time.perf_counter()
        c = sqlite3.connect(str(restored))
        try:
            integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
            fk = c.execute("PRAGMA foreign_key_check").fetchall()
            restored_counts = _counts(c)
        finally:
            c.close()
        t["integrity_ms"] = int((time.perf_counter() - t2) * 1000)
        restore_ms = int((time.perf_counter() - t0) * 1000)
        with _connect(live) as lc:
            live_counts = {k: lc.execute(f'SELECT COUNT(*) FROM "{k}"').fetchone()[0]
                           for k in ("items", "customers", "events", "scoring_rounds",
                                     "scoring_holes", "handicap_rounds", "acct_transactions")
                           if k in restored_counts}
        drift = {k: {"restored": restored_counts.get(k), "live": v}
                 for k, v in live_counts.items()
                 if restored_counts.get(k) is not None and restored_counts[k] > v}
        drill = {"backup": newest["name"], "backup_bytes": newest.get("size"),
                 "taken_at": newest.get("lastModifiedDateTime"),
                 "time_to_restore_ms": restore_ms, "integrity": integrity,
                 "foreign_key_violations": len(fk), "tables": len(restored_counts),
                 "counts_vs_live": {k: {"restored": restored_counts.get(k), "live": v}
                                    for k, v in live_counts.items()},
                 "unexpected_drift": drift or None}
        t3 = time.perf_counter()
        try:
            sc = scrub(restored)
        except Exception as e:
            logger.exception("rehearsal scrub failed")
            return {"ok": False, "stage": "scrub", "error": str(e), "timings_ms": t, **drill}
        final = rdir / SCRUBBED
        os.replace(restored, final)
        t["scrub_ms"] = int((time.perf_counter() - t3) * 1000)
        t4 = time.perf_counter()
        gz_out = rdir / SCRUBBED_GZ
        with open(final, "rb") as f_in, gzip.open(gz_out, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
        c = sqlite3.connect(str(final))
        try:
            integrity_after = c.execute("PRAGMA integrity_check").fetchone()[0]
            leaked = c.execute(
                "SELECT COUNT(*) FROM customer_emails WHERE email LIKE '%@%' "
                "AND email NOT LIKE '%@rehearsal.invalid'").fetchone()[0] \
                if "customer_emails" in restored_counts else 0
        except sqlite3.Error:
            leaked = None
        finally:
            c.close()
        t["gzip_ms"] = int((time.perf_counter() - t4) * 1000)
        out = {
            "ok": integrity == "ok" and integrity_after == "ok" and not drift and not leaked,
            "backup": newest["name"], "backup_bytes": newest.get("size"),
            "taken_at": newest.get("lastModifiedDateTime"),
            "time_to_restore_ms": restore_ms, "timings_ms": t,
            "total_ms": int((time.perf_counter() - t0) * 1000),
            "integrity": integrity, "foreign_key_violations": len(fk),
            "integrity_after_scrub": integrity_after,
            "counts_vs_live": {k: {"restored": restored_counts.get(k), "live": v}
                               for k, v in live_counts.items()},
            "unexpected_drift": drift or None,
            "tables": len(restored_counts),
            "scrubbed_columns": len(sc["columns"]), "settings_blanked": sc["settings_blanked"],
            "customer_emails_left_unscrubbed": leaked,
            "scratch_path": str(final), "scratch_bytes": final.stat().st_size,
            "download_bytes": gz_out.stat().st_size,
            "restored_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
        try:
            set_app_setting(SETTING_DRILL, json.dumps({k: v for k, v in out.items()
                                                       if k != "counts_vs_live"}), db_path=live)
        except Exception:
            logger.warning("could not record the drill", exc_info=True)
        return out
    except Exception as e:
        logger.exception("rehearsal restore failed")
        return {"ok": False, "error": str(e)}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def status(db_path=None) -> dict:
    from .database import get_app_setting
    rdir = rehearsal_dir(db_path)
    try:
        drill = json.loads(get_app_setting(SETTING_DRILL, db_path=db_path) or "null")
    except Exception:
        drill = None
    gz = rdir / SCRUBBED_GZ
    return {"last_drill": drill, "scratch_ready": gz.exists(),
            "download_bytes": gz.stat().st_size if gz.exists() else None,
            "scratch_path": str(rdir / SCRUBBED)}


# ── the RAILWAY REHEARSAL RUNNER (CA #832: Kerry chose B) ────────────────
# The dress-rehearsal lanes cannot take the scratch copy off Railway, so
# the rehearsal runs HERE, against <volume>/rehearsal/tracker_rehearsal.db,
# in a SEPARATE PROCESS:
#   * the child's environment is an ALLOW-LIST (no Graph / Brevo / Stripe /
#     Twilio / Anthropic / HubSpot / Meta secrets, no RAILWAY_* vars), plus
#     TGF_REHEARSAL=1, so importing email_parser installs the outbound guard
#     before any code runs;
#   * a TOOL job runs one of the lane harnesses below with the scratch path
#     filled in by the runner and every argument checked against that tool's
#     allow-list — no free-form command line, no other file;
#   * a BRIDGE job runs one `scoring-*` bridge through mcp_server with
#     DATABASE_PATH pointing at the scratch copy (never the live file);
#   * one job at a time (the lanes share one copy), a hard time limit, and
#     the output kept in <volume>/rehearsal/jobs/ for `job|<id>`.
# Results come back through the bridge like any other bridge answer; the
# database file itself never leaves the volume.

import re as _re
import shlex as _shlex
import subprocess as _subprocess
import threading as _threading

JOBS = "jobs"
JOB_TIMEOUT_S = 30 * 60
_ENV_KEEP = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "PYTHONPATH", "VIRTUAL_ENV",
             "PYTHONHOME", "NIXPACKS_PATH", "LD_LIBRARY_PATH")
_NUM_LIST = r"^\d+(,\d+)*$"
RUNNER_TOOLS = {
    # Track A: replay GG cards through score entry (tools/se_replay.py)
    "se_replay": {"script": "tools/se_replay.py", "db_flag": "--db",
                  "flags": {"--events": _NUM_LIST, "--workers": r"^[1-9]\d?$"},
                  "switches": set(), "out_flag": "--out", "db_env": False},
    # Tracker Build: park GG rows + publish entered rows (#811 GO, #833)
    "takeover": {"script": "tools/scratch_entry_takeover.py", "db_flag": None,
                 "flags": {"--events": _NUM_LIST}, "switches": {"--undo"},
                 "out_flag": None, "db_env": False},
    # Track B: the synthetic Lone Star Cup weekend (tools/lsc_synthetic_weekend.py)
    "lsc_weekend": {"script": "tools/lsc_synthetic_weekend.py", "db_flag": None,
                    "flags": {}, "switches": {"--synthetic-index"},
                    "out_flag": "--out", "db_env": False},
}
# Bridges a rehearsal must not run: the runner itself, the archive mover,
# and anything that only exists to reach outside (it would be refused by
# the guard anyway; refusing here says so plainly).
_BRIDGE_REFUSE = _re.compile(
    r"^scoring-(rehearsal|gg-archive|import-orders|brevo|insider|recap-draft-email|"
    r"hcp-cards|print-pack-pdf|backup)", _re.I)


def runner_scratch_ok(path) -> bool:
    """True only inside a rehearsal-runner child, for a file inside the
    rehearsal folder. The lane tools call this so their 'never on Railway,
    never under /data' guards admit exactly this case and nothing else."""
    if os.getenv("TGF_REHEARSAL_RUNNER") != "1" or os.getenv("TGF_REHEARSAL") != "1":
        return False
    rd = os.getenv("TGF_REHEARSAL_DIR") or ""
    if not rd:
        return False
    p = os.path.realpath(str(path))
    root = os.path.realpath(rd)
    return p.startswith(root + os.sep) and os.path.basename(p) != "transactions.db"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _jobs_dir(db_path=None) -> Path:
    d = rehearsal_dir(db_path) / JOBS
    d.mkdir(parents=True, exist_ok=True)
    return d


def _child_env(rdir: Path, scratch: Path, bridge: bool) -> dict:
    env = {k: os.environ[k] for k in _ENV_KEEP if k in os.environ}
    env.update({"TGF_REHEARSAL": "1", "TGF_REHEARSAL_RUNNER": "1",
                "TGF_REHEARSAL_DIR": str(rdir), "PYTHONUNBUFFERED": "1",
                "SECRET_KEY": "rehearsal-runner", "PERF_SAMPLES": "0"})
    if bridge:
        env["DATABASE_PATH"] = str(scratch)
    return env


def _pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def _running(jd: Path):
    for m in sorted(jd.glob("*.json")):
        try:
            meta = json.loads(m.read_text())
        except Exception:
            continue
        if meta.get("status") == "running" and _pid_alive(meta.get("pid")):
            return meta
    return None


def build_tool_argv(tool: str, args: str, scratch: Path, out_path: Path) -> list:
    """The exact argv a tool job runs, or ValueError naming what was refused."""
    spec = RUNNER_TOOLS.get(tool)
    if not spec:
        raise ValueError(f"unknown tool {tool!r}; one of {sorted(RUNNER_TOOLS)}")
    toks = _shlex.split(args or "")
    argv = [sys.executable, str(_repo_root() / spec["script"])]
    argv += [spec["db_flag"], str(scratch)] if spec["db_flag"] else [str(scratch)]
    i, seen = 0, set()
    while i < len(toks):
        t = toks[i]
        if t in spec["switches"]:
            argv.append(t); i += 1; continue
        if t in spec["flags"]:
            if i + 1 >= len(toks) or not _re.match(spec["flags"][t], toks[i + 1]):
                raise ValueError(f"{t} needs a value matching {spec['flags'][t]}")
            argv += [t, toks[i + 1]]; seen.add(t); i += 2; continue
        raise ValueError(f"argument {t!r} is not allowed for {tool} "
                         f"(allowed: {sorted(spec['flags']) + sorted(spec['switches'])})")
    if tool in ("se_replay", "takeover") and "--events" not in seen:
        raise ValueError("--events <id,id> is required")
    if spec["out_flag"]:
        argv += [spec["out_flag"], str(out_path)]
    argv.append("--i-am-scratch")
    return argv


_BRIDGE_CHILD = r'''
import json, os, sys
sys.path.insert(0, os.getcwd())
import email_parser                      # installs the outbound guard first
from email_parser import rehearsal as rh
assert rh._GUARDED, "outbound guard not installed - refusing"
import mcp_server
ex = sys.argv[1]
url = sys.argv[2] if len(sys.argv) > 2 else "https://tgf-sa.golfgenius.com/"
out = mcp_server._scoring_dispatch(url, ex)
print("RESULT_BEGIN")
print(out if isinstance(out, str) else json.dumps(out, default=str))
print("RESULT_END")
'''


HOLD_LEAD_MIN = 60   # a live round's hold starts this long before its first tee


def _parse_tee(t: str):
    """'17:00' / '5:00 PM' / '8:30am' -> (hour, minute), or None."""
    m = _re.match(r"^\s*(\d{1,2}):(\d{2})\s*([ap])?\.?m?\.?\s*$", str(t or ""), _re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    if ap == "p" and h < 12:
        h += 12
    elif ap == "a" and h == 12:
        h = 0
    return (h, mi) if h < 24 and mi < 60 else None


def live_event_hold(db_path=None, now=None) -> str | None:
    """Why a rehearsal job may not start now, or None (Front Desk, #851).

    Rehearsal jobs run on the production host, so they stay out of a live
    score-entry event: from an hour before the first tee of a round dated
    today (Central) until that round is closed. With no readable tee time
    the hold covers the whole day. App setting ``rehearsal_hold`` = 1
    holds every job by hand. Reads the LIVE file; writes nothing."""
    from .timezone_utils import now_central
    now = now or now_central()
    today = now.strftime("%Y-%m-%d")
    from .database import get_app_setting
    try:
        if str(get_app_setting("rehearsal_hold", db_path=db_path) or "").strip() in ("1", "true", "on", "yes"):
            return "app setting rehearsal_hold is on"
    except Exception:
        pass
    try:
        from .score_entry import open_rounds_on
        rows = [(r["id"], r["item_name"], r["start_time"]) for r in open_rounds_on(today, db_path=db_path)]
    except Exception as e:     # can't tell whether a round is live: hold
        return f"could not read today's live rounds ({type(e).__name__})"
    for rid, name, start in rows:
        tee = _parse_tee(start)
        if tee is None:
            return f"live score-entry round {rid} ({name}) is open today, tee time unknown"
        first = now.replace(hour=tee[0], minute=tee[1], second=0, microsecond=0)
        if (first - now).total_seconds() <= HOLD_LEAD_MIN * 60:
            return (f"live score-entry round {rid} ({name}) tees off {start}; "
                    "rehearsal jobs wait until it is closed")
    return None


def start_job(kind: str, spec: str, args: str = "", db_path=None) -> dict:
    """Start one rehearsal job in a separate process. kind = 'tool' (spec =
    a RUNNER_TOOLS key, args = its flags) or 'bridge' (spec = the scoring-*
    extract). Returns the job id; read it back with job_status()."""
    rdir = rehearsal_dir(db_path)
    scratch = rdir / SCRUBBED
    if not scratch.is_file():
        return {"error": "no scratch copy — run scoring-rehearsal:restore first"}
    held = live_event_hold(db_path)
    if held:
        return {"error": f"held: {held}. Nothing started."}
    jd = _jobs_dir(db_path)
    busy = _running(jd)
    if busy:
        return {"error": f"job {busy['id']} is still running ({busy['kind']} {busy['spec']}); "
                         "one job at a time on the shared copy"}
    jid = datetime.utcnow().strftime("%Y%m%dT%H%M%S") + "-" + _re.sub(r"[^a-z0-9]+", "-", f"{kind}-{spec}".lower())[:40]
    log = jd / f"{jid}.log"
    out_path = jd / f"{jid}-report.json"
    try:
        if kind == "tool":
            argv = build_tool_argv(spec, args, scratch, out_path)
            env = _child_env(rdir, scratch, bridge=False)
        elif kind == "bridge":
            ex = (spec or "").strip()
            if not ex.startswith("scoring-"):
                return {"error": "a bridge job runs one scoring-* bridge"}
            if _BRIDGE_REFUSE.match(ex):
                return {"error": f"{ex.split(':')[0]} is not run in a rehearsal (it only reaches outside, or is the runner itself)"}
            argv = [sys.executable, "-c", _BRIDGE_CHILD, ex]
            env = _child_env(rdir, scratch, bridge=True)
        else:
            return {"error": "kind is tool or bridge"}
    except ValueError as e:
        return {"error": str(e)}
    # Lowest CPU priority: a job shares the host with live requests and
    # must lose every contest for the CPU (Front Desk #851).
    shown = argv
    _nice = shutil.which("nice")
    if _nice:
        argv = [_nice, "-n", "19"] + argv
    fh = open(log, "wb")
    proc = _subprocess.Popen(argv, cwd=str(_repo_root()), env=env, stdout=fh,
                             stderr=_subprocess.STDOUT, stdin=_subprocess.DEVNULL,
                             start_new_session=True)
    meta = {"id": jid, "kind": kind, "spec": spec, "args": args, "pid": proc.pid,
            "status": "running", "started_at": datetime.utcnow().isoformat(timespec="seconds"),
            "argv": [a if a != _BRIDGE_CHILD else "<bridge child>" for a in shown[1:]],
            "nice": 19 if _nice else None,
            "scratch": str(scratch)}
    mp = jd / f"{jid}.json"
    mp.write_text(json.dumps(meta))

    def _wait():
        t0 = time.monotonic()
        try:
            rc = proc.wait(timeout=JOB_TIMEOUT_S)
            status = "done" if rc == 0 else "failed"
        except _subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, 9)
            except OSError:
                proc.kill()
            rc, status = None, "timeout"
        fh.close()
        meta.update({"status": status, "exit_code": rc,
                     "ended_at": datetime.utcnow().isoformat(timespec="seconds"),
                     "secs": round(time.monotonic() - t0, 1)})
        mp.write_text(json.dumps(meta))
    _threading.Thread(target=_wait, daemon=True, name=f"rehearsal-{jid}").start()
    return {"id": jid, "status": "running", "kind": kind, "spec": spec,
            "read_with": f"scoring-rehearsal:job|{jid}"}


def job_status(jid: str, db_path=None, tail_chars: int = 12000) -> dict:
    jd = _jobs_dir(db_path)
    jid = _re.sub(r"[^A-Za-z0-9T\-]", "", jid or "")
    mp = jd / f"{jid}.json"
    if not jid or not mp.is_file():
        return {"error": f"no job {jid!r}"}
    meta = json.loads(mp.read_text())
    if meta.get("status") == "running" and not _pid_alive(meta.get("pid")):
        meta["status"] = "lost"      # the process ended without the waiter (e.g. a restart)
    log = jd / f"{jid}.log"
    text = log.read_text(errors="replace") if log.is_file() else ""
    if "RESULT_BEGIN" in text and "RESULT_END" in text:
        body = text.split("RESULT_BEGIN", 1)[1].split("RESULT_END", 1)[0].strip()
        try:
            meta["result"] = json.loads(body)
        except ValueError:
            meta["result"] = body[-tail_chars:]
    rp = jd / f"{jid}-report.json"
    if rp.is_file():
        try:
            meta["report"] = json.loads(rp.read_text())
        except ValueError:
            meta["report"] = rp.read_text()[-tail_chars:]
    meta["log_tail"] = text[-tail_chars:]
    return meta


def list_jobs(db_path=None, limit: int = 20) -> list:
    jd = _jobs_dir(db_path)
    out = []
    for m in sorted(jd.glob("*.json"), reverse=True):
        if m.name.endswith("-report.json"):
            continue
        try:
            meta = json.loads(m.read_text())
        except Exception:
            continue
        if meta.get("status") == "running" and not _pid_alive(meta.get("pid")):
            meta["status"] = "lost"
        out.append({k: meta.get(k) for k in ("id", "kind", "spec", "args", "status", "secs", "started_at")})
        if len(out) >= limit:
            break
    return out
