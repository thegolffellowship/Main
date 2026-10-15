"""ADVISOR ACCESS, design B (Kerry 2026-10-15, rule 3b: "Yep B." — CoS #1905;
CONCEPTS section #1904; migration 0024 `advisors`).

Outside advisors (the SA advisory board first) open CONCEPTS and the PII-free
member pages through a per-person signed magic link. The link IS the
credential, the same pattern as the roster / `/me` links in memberships.py:

  token = base64url({"a": advisor_id, "v": token_version, "i": issued_at,
                     "e": expires_at}) + "." + HMAC-SHA256(SECRET_KEY)[:32]

- identity comes from the token only, never a query parameter;
- revoking bumps that advisor's `token_version` and stamps `revoked_at`, so
  every link and every open session of that advisor stops at once, and no
  other advisor is touched;
- season-long expiry (`TOKEN_DAYS`).

The session an advisor link opens carries role `advisor` (rank between
member and view-only, app.py `_ROLE_RANK`), `advisor_id` and the token
version; `session_advisor()` re-checks the row on every request.
Pages opened are logged in agent_action_log as agent `advisor:<id>`, action
`advisor_concept_open` (one new table only, per #1905).

The Tracker never emails an advisor: Kerry copies the link from Admin →
Advisors and hands it over himself.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

TOKEN_DAYS = 240            # about a season: issued in October, good into June
OPEN_ACTION = "advisor_concept_open"
SEEN_EVERY_SECONDS = 300    # last_seen_at is written at most every 5 minutes


def _secret() -> bytes:
    from email_parser.memberships import _secret as s
    return s()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _stamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def make_token(advisor_id: int, token_version: int, now: datetime | None = None) -> str:
    now = now or _now()
    payload = {"a": int(advisor_id), "v": int(token_version), "i": int(now.timestamp()),
               "e": int((now + timedelta(days=TOKEN_DAYS)).timestamp())}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
    sig = hmac.new(_secret(), ("adv." + body).encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def decode_token(token: str) -> dict | None:
    """The signed payload, or None if the signature fails or it expired.
    Does NOT check revocation: `resolve_token` does."""
    token = (token or "").strip()
    if "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    want = hmac.new(_secret(), ("adv." + body).encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, want):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("e") or 0) < int(_now().timestamp()):
        return None
    return payload


def _row(conn, advisor_id: int):
    return conn.execute("SELECT * FROM advisors WHERE advisor_id = ?", (int(advisor_id),)).fetchone()


def resolve_token(token: str, db_path=None) -> dict:
    """{"ok": True, "advisor": {...}} or {"ok": False, "why": "invalid" | "inactive"}."""
    from email_parser import database as db
    p = decode_token(token)
    if not p:
        return {"ok": False, "why": "invalid"}
    with db._connect(db_path) as conn:
        r = _row(conn, p["a"])
    if not r or r["revoked_at"] or int(r["token_version"]) != int(p["v"]):
        return {"ok": False, "why": "inactive"}
    return {"ok": True, "advisor": {"advisor_id": r["advisor_id"], "name": r["name"],
                                    "token_version": r["token_version"]}}


def session_advisor(sess, db_path=None, touch: bool = True) -> dict | None:
    """The advisor behind an `advisor` session, or None when the row is gone,
    revoked or re-versioned (the caller then ends the session)."""
    from email_parser import database as db
    aid, tv = sess.get("advisor_id"), sess.get("advisor_tv")
    if not aid or tv is None:
        return None
    with db._connect(db_path) as conn:
        r = _row(conn, aid)
        if not r or r["revoked_at"] or int(r["token_version"]) != int(tv):
            return None
        if touch:
            last = r["last_seen_at"]
            now = _now()
            stale = True
            if last:
                try:
                    stale = (now - datetime.strptime(str(last)[:19], "%Y-%m-%d %H:%M:%S")
                             .replace(tzinfo=timezone.utc)).total_seconds() >= SEEN_EVERY_SECONDS
                except ValueError:
                    stale = True
            if stale:
                conn.execute("UPDATE advisors SET last_seen_at = ? WHERE advisor_id = ?",
                             (_stamp(now), r["advisor_id"]))
                conn.commit()
    return {"advisor_id": r["advisor_id"], "name": r["name"]}


def add(name: str, email: str = "", by: str = "", db_path=None) -> dict:
    from email_parser import database as db
    name = " ".join((name or "").split())
    email = (email or "").strip().lower() or None
    if not name:
        return {"error": "name is required"}
    if len(name) > 120 or (email and len(email) > 200):
        return {"error": "name or email is too long"}
    with db._connect(db_path) as conn:
        aid = conn.execute(
            "INSERT INTO advisors (name, email, created_by) VALUES (?, ?, ?) RETURNING advisor_id",
            (name, email, by or None)).fetchone()[0]
        conn.commit()
    _log("admin", "advisor_add", f"advisor {aid} {name}", db_path)
    return {"advisor_id": aid, "name": name}


def link(advisor_id: int, base_url: str = "", db_path=None) -> dict:
    """A fresh link for an ACTIVE advisor (older links of the same version
    keep working; revoke to end them all)."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = _row(conn, advisor_id)
    if not r:
        return {"error": "no such advisor"}
    if r["revoked_at"]:
        return {"error": "this advisor is revoked; reinstate first"}
    tok = make_token(r["advisor_id"], r["token_version"])
    return {"advisor_id": r["advisor_id"], "url": f"{base_url.rstrip('/')}/advisor/{tok}"}


def revoke(advisor_id: int, by: str = "", db_path=None) -> dict:
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = _row(conn, advisor_id)
        if not r:
            return {"error": "no such advisor"}
        conn.execute("UPDATE advisors SET token_version = token_version + 1, revoked_at = ? "
                     "WHERE advisor_id = ?", (_stamp(_now()), r["advisor_id"]))
        conn.commit()
    _log("admin", "advisor_revoke", f"advisor {r['advisor_id']} {r['name']} by {by or '-'}", db_path)
    return {"revoked": r["advisor_id"]}


def reinstate(advisor_id: int, by: str = "", db_path=None) -> dict:
    """Undo a revoke. The version stays bumped, so the old links stay dead:
    a NEW link must be copied and handed over."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = _row(conn, advisor_id)
        if not r:
            return {"error": "no such advisor"}
        conn.execute("UPDATE advisors SET revoked_at = NULL WHERE advisor_id = ?", (r["advisor_id"],))
        conn.commit()
    _log("admin", "advisor_reinstate", f"advisor {r['advisor_id']} {r['name']} by {by or '-'}", db_path)
    return {"reinstated": r["advisor_id"]}


def log_open(advisor_id: int, doc_id: str, db_path=None) -> None:
    _log(f"advisor:{int(advisor_id)}", OPEN_ACTION, str(doc_id)[:120], db_path)


def _log(agent: str, action: str, desc: str, db_path=None) -> None:
    from email_parser import database as db
    try:
        db.log_agent_action(agent, action, desc, db_path=db_path)
    except Exception:
        logger.debug("advisor action log failed", exc_info=True)


def list_all(db_path=None) -> list[dict]:
    """Every advisor with last seen and the pages opened (doc_id → count,
    last opened), for the Admin row."""
    from email_parser import database as db
    out = []
    with db._connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM advisors ORDER BY revoked_at IS NOT NULL, name").fetchall()
        for r in rows:
            opens: dict = {}
            for o in conn.execute(
                    "SELECT description, created_at FROM agent_action_log "
                    "WHERE agent_name = ? AND action_type = ? ORDER BY id",
                    (f"advisor:{r['advisor_id']}", OPEN_ACTION)).fetchall():
                d = opens.setdefault(o["description"], {"doc_id": o["description"], "count": 0, "last": None})
                d["count"] += 1
                d["last"] = o["created_at"]
            out.append({"advisor_id": r["advisor_id"], "name": r["name"], "email": r["email"],
                        "created_at": r["created_at"], "revoked_at": r["revoked_at"],
                        "last_seen_at": r["last_seen_at"],
                        "pages_opened": sorted(opens.values(), key=lambda d: d["last"] or "", reverse=True)})
    return out
