"""WHO UNSUBSCRIBED (Kerry 2026-10-23: "let's add any daily unsubscribed to my
Daily TGF Briefings/Digest").

Two sources, read-only toward both:
- Tracker event invitations: every confirmed "Stop invitations" is logged as
  agent_action_log `event_invite_unsubscribe` (invitations.record_answer), so
  a window is read straight from the log.
- Brevo (the TGF Insider): Brevo keeps its own unsubscribes
  (`emailBlacklisted` on the contact). Brevo has no "unsubscribed since"
  query, so `refresh` compares today's blacklisted set with the one stored
  yesterday (app setting BREVO_SNAPSHOT_KEY) and appends each change to
  LOG_KEY with the time it was SEEN. The first run only stores the baseline.

`recent(hours)` is what the daily digest and the Front Desk brief read
(bridge `scoring-unsubscribes`). Nothing here writes to Brevo or changes
anyone's preferences.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

BREVO_SNAPSHOT_KEY = "brevo_blacklist_snapshot"
LOG_KEY = "unsubscribe_log"
LOG_KEEP_DAYS = 90


def _now() -> datetime:
    return datetime.utcnow()


def _stamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _get(key, db_path=None):
    from email_parser import database as db
    return db.get_app_setting(key, db_path=db_path)


def _set(key, value, db_path=None):
    from email_parser import database as db
    db.set_app_setting(key, value, db_path=db_path)


def brevo_blacklisted(key: str, fetch=None) -> set:
    """Every Brevo contact email with emailBlacklisted = true (lowercase)."""
    if fetch is not None:
        return {e.strip().lower() for e in fetch() if e}
    import requests
    from email_parser.brevo import BREVO_API, _headers, _PAUSE
    out, offset = set(), 0
    while True:
        r = requests.get(f"{BREVO_API}/contacts", params={"limit": 1000, "offset": offset},
                         headers=_headers(key), timeout=60)
        r.raise_for_status()
        contacts = r.json().get("contacts") or []
        for c in contacts:
            if c.get("emailBlacklisted") and c.get("email"):
                out.add(c["email"].strip().lower())
        if len(contacts) < 1000:
            return out
        offset += 1000
        time.sleep(_PAUSE)


def _who(conn, email: str) -> tuple:
    r = conn.execute(
        "SELECT c.customer_id, c.first_name, c.last_name FROM customer_emails e "
        "JOIN customers c ON c.customer_id = e.customer_id "
        "WHERE lower(e.email) = lower(?) LIMIT 1", (email,)).fetchone()
    if not r:
        return None, None
    return int(r[0]), " ".join(x for x in (r[1], r[2]) if x).strip() or None


def _log(db_path=None) -> list:
    try:
        return json.loads(_get(LOG_KEY, db_path) or "[]")
    except (TypeError, ValueError):
        return []


def refresh(db_path=None, now: datetime | None = None, fetch=None) -> dict:
    """Compare Brevo's unsubscribed set with the stored one and log changes."""
    from email_parser import database as db
    from email_parser.brevo import _api_key
    now = now or _now()
    key = _api_key()
    if not key and fetch is None:
        return {"brevo": "not configured"}
    try:
        cur = brevo_blacklisted(key, fetch=fetch)
    except Exception as e:  # noqa: BLE001 — the digest must still go out
        logger.warning("unsubscribes: Brevo read failed: %s", e)
        return {"brevo": f"read failed: {type(e).__name__}"}
    prev_raw = _get(BREVO_SNAPSHOT_KEY, db_path)
    _set(BREVO_SNAPSHOT_KEY, json.dumps(sorted(cur)), db_path)
    if prev_raw is None:
        return {"brevo": "baseline", "count": len(cur)}
    prev = set(json.loads(prev_raw or "[]"))
    added, removed = sorted(cur - prev), sorted(prev - cur)
    if added or removed:
        log = _log(db_path)
        conn = db.get_connection(db_path)
        try:
            for email, kind in [(e, "unsubscribed") for e in added] + [(e, "resubscribed") for e in removed]:
                cid, name = _who(conn, email)
                log.append({"at": _stamp(now), "source": "brevo", "kind": kind,
                            "email": email, "customer_id": cid, "name": name})
        finally:
            conn.close()
        cutoff = _stamp(now - timedelta(days=LOG_KEEP_DAYS))
        _set(LOG_KEY, json.dumps([x for x in log if x.get("at", "") >= cutoff]), db_path)
    return {"brevo": "ok", "count": len(cur), "new": len(added), "back": len(removed)}


def recent(hours: int = 24, db_path=None, now: datetime | None = None) -> list:
    """Unsubscribes (and Brevo resubscribes) in the last `hours`, newest first."""
    from email_parser import database as db
    now = now or _now()
    since = _stamp(now - timedelta(hours=hours))
    out = []
    conn = db.get_connection(db_path)
    try:
        for at, desc in conn.execute(
                "SELECT created_at, description FROM agent_action_log "
                "WHERE action_type = 'event_invite_unsubscribe' AND created_at >= ? "
                "ORDER BY created_at DESC", (since,)).fetchall():
            cid = None
            try:
                cid = int(str(desc).split()[-1])
            except (ValueError, IndexError):
                pass
            name = None
            if cid:
                r = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                                 (cid,)).fetchone()
                if r:
                    name = " ".join(x for x in (r[0], r[1]) if x).strip() or None
            out.append({"at": at, "source": "invitations", "kind": "unsubscribed",
                        "customer_id": cid, "name": name, "email": None})
    finally:
        conn.close()
    out += [x for x in _log(db_path) if x.get("at", "") >= since]
    return sorted(out, key=lambda x: x.get("at", ""), reverse=True)


SOURCE_LABEL = {"invitations": "Event invitations", "brevo": "TGF Insider (Brevo)"}
