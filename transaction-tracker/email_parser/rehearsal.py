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
  ``mint_link()``— a random one-use-per-lane download token (48 h, stored
                   only as a SHA-256) and the URL that serves the scrubbed
                   gzip: ``GET /rehearsal/snapshot.db.gz?t=<token>``.
                   Anything else (no token, wrong, expired, file missing) → 404.
  Files live in ``<volume>/rehearsal/`` beside the live database, never at
  ``DB_PATH``. Nothing here writes to the live database except the drill
  record in ``app_settings`` (``rehearsal_drill`` / ``rehearsal_tokens``).

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
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import shutil
import socket
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DIRNAME = "rehearsal"
SCRUBBED = "tracker_rehearsal.db"
SCRUBBED_GZ = "tracker_rehearsal.db.gz"
TOKEN_TTL_H = 48
SETTING_DRILL = "rehearsal_drill"
SETTING_TOKENS = "rehearsal_tokens"

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
                    val = "''" if notnull else "NULL"
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
        t3 = time.perf_counter()
        sc = scrub(restored)
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


def _hash(tok: str) -> str:
    return hashlib.sha256(tok.encode()).hexdigest()


def _tokens(db_path=None) -> list:
    from .database import get_app_setting
    try:
        return json.loads(get_app_setting(SETTING_TOKENS, db_path=db_path) or "[]")
    except Exception:
        return []


def mint_link(lane: str = "", db_path=None, base_url: str = "") -> dict:
    """A 48-hour download token for the scrubbed copy. Stored hashed."""
    from .database import set_app_setting
    gz = rehearsal_dir(db_path) / SCRUBBED_GZ
    if not gz.exists():
        return {"error": "no scratch copy yet — run scoring-rehearsal:restore first"}
    tok = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    keep = [x for x in _tokens(db_path) if x.get("exp", "") > now.isoformat()]
    keep.append({"h": _hash(tok), "exp": (now + timedelta(hours=TOKEN_TTL_H)).isoformat(timespec="seconds"),
                 "lane": (lane or "")[:60]})
    set_app_setting(SETTING_TOKENS, json.dumps(keep[-50:]), db_path=db_path)
    base = (base_url or os.getenv("PUBLIC_BASE_URL") or "https://tgf-tracker.up.railway.app").rstrip("/")
    return {"url": f"{base}/rehearsal/snapshot.db.gz?t={tok}",
            "expires_utc": keep[-1]["exp"], "bytes": gz.stat().st_size}


def check_token(tok: str, db_path=None) -> bool:
    if not tok:
        return False
    h = _hash(tok)
    now = datetime.utcnow().isoformat()
    return any(hmac.compare_digest(h, x.get("h", "")) and x.get("exp", "") > now
               for x in _tokens(db_path))


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
            "live_tokens": sum(1 for x in _tokens(db_path)
                               if x.get("exp", "") > datetime.utcnow().isoformat())}
