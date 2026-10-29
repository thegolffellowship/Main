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


# ── THE OPEN PIXEL (Kerry 10/29: "If the open-tracking pixel is no big deal
# then let's do it for all emails so we know who's opening and not opening
# stuff. If someone never ever interacts with our emails then that might be
# someone that we remove from the list or something.") ──────────────────────
# Every email the Tracker sends goes through fetcher.send_mail_graph, which
# calls pixel_for() and adds a 1x1 image when it is safe to:
#   * exactly one To address, not a staff address, a known customer;
#   * NO CC and NO BCC: Kerry's copy of the same HTML would fire the player's
#     pixel and count as the player opening it;
#   * dial email_open_pixel (on unless "off").
# The send is logged (`email_sent`, with a short key of the subject) so the
# engagement read can say "sent 12, opened 3, clicked 1".
# An open is classified, never trusted blindly: Apple Mail Privacy Protection
# loads every image on delivery (IP 17.x), so its opens are "unknown"; an empty
# user agent is a scanner; Gmail's GoogleImageProxy fetches when the person
# opens, so it counts. Nobody is removed from anything here; that is Kerry's
# call, read off `engagement()`.
PIXEL_DIAL = "email_open_pixel"
STAFF_DOMAIN = "@thegolffellowship.com"
GIF = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,"
       b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")


def _subject_key(subject: str) -> str:
    return hashlib.sha256((subject or "").encode()).hexdigest()[:8]


def pixel_for(to_address: str, cc=None, bcc=None, subject: str = "", db_path=None) -> str:
    """The <img> to add to one outgoing email, or "" (and logs the send)."""
    try:
        from email_parser import database as db
        if (db.get_app_setting(PIXEL_DIAL, db_path=db_path) or "on").strip().lower() in ("off", "0", "false", "no"):
            return ""
        addrs = [a.strip().lower() for a in (to_address or "").split(",") if a.strip()]
        if len(addrs) != 1 or (cc or "").strip() or (bcc or "").strip() or addrs[0].endswith(STAFF_DOMAIN):
            return ""
        conn = db.get_connection(db_path)
        try:
            r = conn.execute("SELECT customer_id FROM customer_emails WHERE lower(email) = ? "
                             "AND customer_id IS NOT NULL LIMIT 1", (addrs[0],)).fetchone()
        finally:
            conn.close()
        if not r:
            return ""
        cid, key = int(r[0]), _subject_key(subject)
        db.log_agent_action(AGENT, "email_sent",
                            f"customer {cid} event - | scanner=| key={key} | subject={(subject or '')[:100]}",
                            db_path=db_path)
        body = base64.urlsafe_b64encode(json.dumps({"c": cid, "k": "open", "s": key},
                                                   separators=(",", ":")).encode()).rstrip(b"=").decode()
        sig = hmac.new(_secret(), b"clk." + body.encode(), hashlib.sha256).hexdigest()[:16]
        from email_parser.score_entry import _base_url
        return (f'<img src="{_base_url()}/o/{body}.{sig}.gif" width="1" height="1" alt="" '
                f'style="display:block;width:1px;height:1px;border:0;" />')
    except Exception:
        logger.exception("open pixel: skipped")
        return ""


def classify_open(client: dict) -> str:
    """'' = the person opened it; else why it does not count."""
    ua = (client.get("ua") or "").lower()
    ip = (client.get("ip") or "").split(",")[0].strip()
    if "googleimageproxy" in ua:
        return ""
    if ip.startswith("17."):
        return "apple privacy preload"
    if not ua:
        return "no user agent"
    return ""


def record_open(tag: str, client: dict, db_path=None) -> None:
    p = read_tag(tag)
    if not p or p.get("k") != "open":
        return
    try:
        from email_parser import database as db
        why = classify_open(client or {})
        db.log_agent_action(
            AGENT, "email_open",
            f"customer {int(p['c'])} event - | scanner={why}| key={p.get('s')} | "
            f"ua={(client.get('ua') or '')[:160]} | ip={(client.get('ip') or '')[:60]}", db_path=db_path)
    except Exception:
        logger.exception("open pixel: record failed")


def engagement(days: int = 120, min_sent: int = 3, db_path=None) -> dict:
    """Per customer over the last `days`: emails sent, opened (by them),
    unknown (Apple preload), clicks (any link-click open + invitation taps).
    `never` = sent at least `min_sent` and no open or click at all."""
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT agent_name, action_type, description FROM agent_action_log "
            "WHERE agent_name IN (?, 'rsvp-link') AND created_at >= datetime('now', ?)",
            (AGENT, f"-{int(days)} days")).fetchall()
        names = {int(r[0]): f"{r[1] or ''} {r[2] or ''}".strip() for r in conn.execute(
            "SELECT customer_id, first_name, last_name FROM customers")}
    finally:
        conn.close()
    per: dict = {}
    cre = re.compile(r"customer (\d+)")
    for agent, action, desc in rows:
        m = cre.search(desc or "")
        if not m:
            continue
        c = per.setdefault(int(m.group(1)), {"sent": 0, "opened": 0, "unknown": 0, "clicks": 0})
        scanner = (re.search(r"scanner=([^|]*)\|", desc or "") or [None, ""])[1].strip()
        if action == "email_sent":
            c["sent"] += 1
        elif action == "email_open":
            if scanner == "apple privacy preload":
                c["unknown"] += 1
            elif not scanner:
                c["opened"] += 1
        elif (agent == AGENT and action.endswith("_open") and not scanner) or action == "event_invite_tap":
            c["clicks"] += 1
    never = sorted(([cid, names.get(cid, ""), v["sent"]] for cid, v in per.items()
                    if v["sent"] >= min_sent and not v["opened"] and not v["clicks"] and not v["unknown"]),
                   key=lambda x: -x[2])
    return {"days": days, "people": len(per), "never_engaged": never,
            "apple_unknown": sum(1 for v in per.values() if v["unknown"] and not v["opened"] and not v["clicks"]),
            "by_customer": per}
