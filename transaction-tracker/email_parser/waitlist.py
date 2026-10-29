"""THE EVENT WAITLIST (Kerry 2026-10-29: "Kelly BARNA, Myself and Michael
Mesa need to go on a waitlist for Saturday. We can't have anymore than 32, so
Kelly needs to come off the active roster.").

An ordered list per event, keyed by customer_id, in app setting
`event_waitlist:<event_id>` (each entry: customer_id, name, note, added_at,
by). Putting someone on the list takes an RSVP-only player OFF the roster:
their RSVP email gets the Players tab's own `not_playing` override
(`rsvp_email_overrides`), which `_event_rsvp_only_players` already honours,
so a second "I'm in" tap cannot put them back. A PAID registration is never
touched here: no credit, no refund, nothing moves; it is reported so the
manager decides. Taking someone off the list clears the override only if the
waitlist set it. Nothing is emailed. Bridge `scoring-waitlist`.
"""
from __future__ import annotations

import json

KEY = "event_waitlist:{}"


def _event(conn, event_id):
    r = conn.execute("SELECT id, item_name FROM events WHERE id = ?", (int(event_id),)).fetchone()
    return dict(r) if r else None


def get(event_id: int, db_path=None) -> list:
    from . import database as db
    raw = db.get_app_setting(KEY.format(int(event_id)), db_path=db_path)
    try:
        return json.loads(raw) if raw else []
    except ValueError:
        return []


def _save(event_id, rows, db_path=None):
    from . import database as db
    db.set_app_setting(KEY.format(int(event_id)), json.dumps(rows), db_path=db_path)


def _rsvp_emails(conn, event_name, cid) -> list:
    rows = conn.execute(
        "SELECT DISTINCT lower(trim(player_email)) FROM rsvps WHERE customer_id = ? "
        "AND lower(COALESCE(matched_event, event_identifier, '')) = lower(?) "
        "AND COALESCE(player_email, '') <> ''", (int(cid), event_name)).fetchall()
    return [r[0] for r in rows]


def _paid_rows(conn, event_id, event_name, cid) -> list:
    from .database import PAIRING_INACTIVE_STATUSES
    ph = ",".join("?" * len(PAIRING_INACTIVE_STATUSES))
    return [int(r[0]) for r in conn.execute(
        f"SELECT id FROM items WHERE customer_id = ? AND (event_id = ? OR lower(item_name) = lower(?)) "
        f"AND COALESCE(transaction_status, 'active') NOT IN ({ph})",
        (int(cid), int(event_id), event_name, *PAIRING_INACTIVE_STATUSES)).fetchall()]


def add(event_id: int, customer_id: int, note: str = "", by: str = "", apply: bool = False,
        db_path=None) -> dict:
    """Put a person at the END of the waitlist; an RSVP-only player leaves the
    roster. Dry run unless apply."""
    from . import database as db
    from .timezone_utils import now_central
    with db._connect(db_path) as conn:
        ev = _event(conn, event_id)
        if not ev:
            return {"error": f"no event {event_id}"}
        c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                         (int(customer_id),)).fetchone()
        if not c:
            return {"error": f"no customer {customer_id}"}
        name = f"{c['first_name'] or ''} {c['last_name'] or ''}".strip()
        emails = _rsvp_emails(conn, ev["item_name"], customer_id)
        paid = _paid_rows(conn, event_id, ev["item_name"], customer_id)
    rows = get(event_id, db_path)
    if any(int(r["customer_id"]) == int(customer_id) for r in rows):
        return {"already": True, "position": [int(r["customer_id"]) for r in rows].index(int(customer_id)) + 1,
                "waitlist": rows}
    entry = {"customer_id": int(customer_id), "name": name, "note": note, "by": by,
             "added_at": now_central().strftime("%Y-%m-%d %H:%M"), "overrides": emails}
    out = {"dry_run": not apply, "event_id": int(event_id), "event": ev["item_name"],
           "add": entry, "position": len(rows) + 1,
           "roster": (f"RSVP not playing for {', '.join(emails)}: off the roster" if emails
                      else "no RSVP on this event: not on the roster"),
           "paid_registration": paid,
           "note_paid": ("a paid registration is left as it is; credit or WD is the manager's call"
                         if paid else None)}
    if not apply:
        return out
    for e in emails:
        db.set_rsvp_email_override(e, ev["item_name"], "not_playing", db_path=db_path)
    rows.append(entry)
    _save(event_id, rows, db_path)
    try:
        db.log_agent_action("waitlist", "waitlist_add",
                            f"event {event_id}: {name} ({customer_id}) #{len(rows)}; {note}",
                            db_path=db_path)
    except Exception:
        pass
    out["waitlist"] = rows
    return out


def remove(event_id: int, customer_id: int, apply: bool = False, db_path=None) -> dict:
    """Take a person off the list; clears only the overrides the list set
    (they are back on the roster if their RSVP still says PLAYING)."""
    from . import database as db
    rows = get(event_id, db_path)
    hit = [r for r in rows if int(r["customer_id"]) == int(customer_id)]
    if not hit:
        return {"error": "not on the waitlist", "waitlist": rows}
    if not apply:
        return {"dry_run": True, "remove": hit[0]}
    with db._connect(db_path) as conn:
        ev = _event(conn, event_id)
    for e in hit[0].get("overrides") or []:
        db.set_rsvp_email_override(e, ev["item_name"], "none", db_path=db_path)
    rows = [r for r in rows if int(r["customer_id"]) != int(customer_id)]
    _save(event_id, rows, db_path)
    return {"removed": hit[0], "waitlist": rows}
