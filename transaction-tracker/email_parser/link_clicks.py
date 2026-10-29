"""THE CLICK LOG (Kerry 2026-10-28 via Event Ops #2480-2 / #2481: "Yes, clicks
first"; 10/29: "Let's do the click log next", after "Has Eric clicked on the
email about his handicap yet?" had no answer).

Every visit to a link we sent a person is logged with who (customer_id), the
event, when, the browser (user agent, language) and the IP:
  handicap   /handicap/<token>        (the handicap ask)
  payout     /payout/<token>          (the payout ask)
  teesheet   /member/teesheet/<id>?w= (the event-day email's tee-sheet button)
  results    /member/results/<id>?w=  (the results email's full-results button)
  invite     /rsvp/<token>            (already logged by invitations.log_tap)
The two public pages carry a short signed `w` tag (`tag_url`) naming the
person; the page itself stays public and works without it.

A likely mail scanner (no user agent, a known scanner agent, no language, the
same rule the invitation guard uses: invitations.tap_fingerprint) is logged
and FLAGGED, never counted as the person opening it.

Storage: agent_action_log, agent `link-click`, action `<kind>_open` (the same
log the invitation taps already use). No new table. `opened(kind, cid)` is
the one reader: the missing-handicap banner and the payout-ask chips show it.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re

logger = logging.getLogger(__name__)

AGENT = "link-click"
KINDS = ("handicap", "payout", "teesheet", "results")
_DESC = re.compile(r"customer (\d+) event (\d+|-) \| scanner=([^|]*)\|")


def _secret() -> bytes:
    from email_parser.memberships import _secret as s
    return s()


def make_tag(customer_id: int, event_id: int, kind: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps(
        {"c": int(customer_id), "v": int(event_id), "k": kind}, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    sig = hmac.new(_secret(), b"clk." + body.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{body}.{sig}"


def read_tag(tag: str) -> dict | None:
    tag = (tag or "").strip()
    if "." not in tag:
        return None
    body, sig = tag.rsplit(".", 1)
    want = hmac.new(_secret(), b"clk." + body.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, want):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None


def tag_url(url: str, customer_id, event_id, kind: str) -> str:
    """The url with this person's `w` tag (before any #fragment)."""
    if not url or not customer_id:
        return url
    base, _, frag = url.partition("#")
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}w={make_tag(int(customer_id), int(event_id), kind)}" + (f"#{frag}" if frag else "")


def client_of(request) -> dict:
    return {"ua": request.headers.get("User-Agent", ""),
            "lang": request.headers.get("Accept-Language", ""),
            "ip": (request.headers.get("X-Forwarded-For", "") or request.remote_addr or "")}


def record(kind: str, customer_id, event_id, client: dict | None, db_path=None) -> None:
    """Log one visit. Never raises."""
    if not customer_id:
        return
    try:
        from email_parser import database as db
        from email_parser.invitations import tap_fingerprint
        c = client or {}
        why = tap_fingerprint(c, db_path) or ""
        db.log_agent_action(
            AGENT, f"{kind}_open",
            f"customer {int(customer_id)} event {int(event_id) if event_id else '-'} | "
            f"scanner={why}| ua={(c.get('ua') or '')[:160]} | lang={(c.get('lang') or '')[:40]} | "
            f"ip={(c.get('ip') or '')[:60]}", db_path=db_path)
    except Exception:
        logger.exception("click log: record failed")


def record_tag(request, kind: str, event_id: int, db_path=None) -> None:
    """A public page's visit, when it carries a valid `w` tag for this event."""
    p = read_tag(request.args.get("w") or "")
    if p and p.get("k") == kind and int(p.get("v", 0)) == int(event_id):
        record(kind, p.get("c"), event_id, client_of(request), db_path)


def opened(kind: str, customer_id: int, event_id: int | None = None, db_path=None) -> dict | None:
    """{first, last, count, scanner_only} of this person's visits, or None.
    Scanner-flagged visits are counted apart and never make `first`."""
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT description, created_at FROM agent_action_log WHERE agent_name = ? "
            "AND action_type = ? AND description LIKE ? ORDER BY id",
            (AGENT, f"{kind}_open", f"customer {int(customer_id)} event %")).fetchall()
    finally:
        conn.close()
    people, scanners = [], 0
    for r in rows:
        m = _DESC.match(r[0] or "")
        if not m:
            continue
        if event_id and m.group(2) != str(int(event_id)):
            continue
        if m.group(3).strip():
            scanners += 1
        else:
            people.append(r[1])
    if not people and not scanners:
        return None
    return {"first": people[0] if people else None, "last": people[-1] if people else None,
            "count": len(people), "scanner_only": not people, "scanner_hits": scanners}


def opened_line(kind: str, customer_id: int, event_id: int | None = None, db_path=None) -> str:
    """'opened Thu 8:12 AM' / 'opened 3 times, last …' / 'link checked by a mail
    scanner only' / ''. Times are created_at (UTC) shown in Central."""
    o = opened(kind, customer_id, event_id, db_path)
    if not o:
        return "not opened yet"
    if o["scanner_only"]:
        return "link checked by a mail scanner only, not opened by them"
    when = _central(o["last"])
    return f"opened {when}" if o["count"] == 1 else f"opened {o['count']} times, last {when}"


def _central(utc_text: str) -> str:
    from datetime import datetime
    import pytz
    try:
        d = datetime.strptime(str(utc_text)[:19], "%Y-%m-%d %H:%M:%S")
        d = pytz.utc.localize(d).astimezone(pytz.timezone("America/Chicago"))
        return d.strftime("%a %-I:%M %p")
    except Exception:
        return str(utc_text)
