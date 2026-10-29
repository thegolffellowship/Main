"""AN EVENT'S COURSE CONTACTS FREEZE WHEN IT COMPLETES (Kerry 2026-10-28,
Event Ops #2476-3; guiding principle 4, past events are frozen).

Kerry: "Update standard contacts associated with course, not just event. Of
course after an event is completed all of that hardens to that event's
contact info, so even if the course contact info changes like if Skyler went
to another company, her contact would still show if we dug into the archives
for that event."

- `course_staff` stays the STANDARD, per course, going forward.
- Once an event is complete (its date is before today, Central), its course
  contacts are copied onto the event: app setting
  `event_course_contacts:<event_id>` = {taken_at, source, course_id, course,
  contacts: [{customer_id, name, role, role_label, is_primary, email, phone,
  company}]}. Never rewritten once taken (`snapshot(..., force=True)` only
  by hand).
- `contacts_for_event` is the event-facing reader: the snapshot for a
  completed event (taken on first read if the backfill has not reached it),
  the live `course_staff.for_course` otherwise. `print_pack.course_recipients_for_event`
  (Course Files, tee-times course email, course update, no-show notice,
  course shortfall) reads through it.
- Backfill: job `event_contacts_backfill` daily and once at boot, for every
  completed event with a course and no snapshot. Bridge
  `scoring-event-contacts[:<event_id>][|apply]` (dry run default).
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

KEY = "event_course_contacts:{}"


def _setting(key, db_path=None):
    from email_parser import database as db
    try:
        return db.get_app_setting(key, db_path=db_path)
    except Exception:
        return None


def is_completed(ev: dict, today: str | None = None) -> bool:
    """An event is complete once its date is before today (Central)."""
    from email_parser.timezone_utils import today_central_str
    d = str((ev or {}).get("event_date") or "")[:10]
    return bool(d) and d < (today or today_central_str())


def stored(event_id: int, db_path=None) -> dict | None:
    raw = _setting(KEY.format(int(event_id)), db_path)
    if not raw:
        return None
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else None
    except ValueError:
        return None


def _course_id(conn, ev: dict):
    if ev.get("course_id"):
        return int(ev["course_id"])
    r = conn.execute("SELECT course_id FROM events WHERE id = ?", (int(ev["id"]),)).fetchone()
    return int(r[0]) if r and r[0] else None


def build(conn, ev: dict) -> dict | None:
    """The snapshot body for one event from today's course_staff. None when
    the event has no course linked."""
    from email_parser import course_staff as cs
    cid = _course_id(conn, ev)
    if not cid:
        return None
    crow = conn.execute("SELECT name FROM courses WHERE course_id = ?", (cid,)).fetchone()
    course = (crow[0] if crow else None) or ev.get("course")
    staff = cs.for_course(conn, cid)
    out = []
    for s in staff:
        comp = None
        try:
            r = conn.execute("SELECT company_name FROM customers WHERE customer_id = ?",
                             (int(s["customer_id"]),)).fetchone()
            comp = (r[0] if r else None) or None
        except Exception:
            comp = None
        out.append({"customer_id": s["customer_id"], "name": s["name"], "role": s["role"],
                    "role_label": s["role_label"], "is_primary": bool(s["is_primary"]),
                    "email": s["email"], "phone": s["phone"], "company": comp or course})
    return {"course_id": cid, "course": course, "contacts": out}


def snapshot(event_id: int, apply: bool = False, force: bool = False, source: str = "complete",
             db_path=None) -> dict:
    """Freeze one event's course contacts. Dry run unless apply. A snapshot
    already taken is kept unless force."""
    from email_parser import database as db
    from datetime import datetime
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
        if not r:
            return {"error": f"no event {event_id}"}
        ev = dict(r)
        have = stored(event_id, db_path)
        if have and not force:
            return {"event_id": int(event_id), "status": "already frozen", "snapshot": have}
        body = build(conn, ev)
    if body is None:
        return {"event_id": int(event_id), "status": "no course linked"}
    if not body["contacts"] and not force:
        # Nothing to freeze: an empty list would hide contacts added later
        # for a course that had none on file. The event keeps reading live.
        return {"event_id": int(event_id), "status": "no contacts on file"}
    body.update(taken_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                source=source, event_date=str(ev.get("event_date") or "")[:10])
    if not apply:
        return {"event_id": int(event_id), "status": "would freeze", "dry_run": True, "snapshot": body}
    db.set_app_setting(KEY.format(int(event_id)), json.dumps(body, sort_keys=True), db_path=db_path)
    try:
        db.log_agent_action("event-contacts", "event_contacts_snapshot",
                            f"event {event_id}: {len(body['contacts'])} course contact(s) frozen ({source})",
                            db_path=db_path)
    except Exception:
        pass
    return {"event_id": int(event_id), "status": "frozen", "snapshot": body}


def contacts_for_event(ev: dict, db_path=None, today: str | None = None) -> dict:
    """{course_id, contacts, frozen} for an event. A completed event reads its
    snapshot (frozen on first read when the backfill has not reached it); an
    upcoming one reads course_staff live."""
    from email_parser import database as db
    from email_parser import course_staff as cs
    eid = ev.get("id")
    if eid is not None and is_completed(ev, today):
        snap = stored(int(eid), db_path)
        if snap is None:
            try:
                snap = (snapshot(int(eid), apply=True, source="first_read", db_path=db_path)
                        .get("snapshot"))
            except Exception:
                logger.exception("event contacts: snapshot failed for %s", eid)
                snap = None
        if snap:
            return {"course_id": snap.get("course_id"), "contacts": snap.get("contacts") or [],
                    "frozen": True, "taken_at": snap.get("taken_at")}
    with db._connect(db_path) as conn:
        cid = _course_id(conn, ev) if eid is not None or ev.get("course_id") else None
        staff = cs.for_course(conn, cid) if cid else []
    return {"course_id": cid, "contacts": staff, "frozen": False}


def recipients(contacts: list[dict]) -> dict:
    """The Course Files rule (course_staff.print_recipients) over a list of
    contacts: To the primary TGF contact, CC the other TGF contacts."""
    staff = [s for s in contacts if s.get("role") == "tgf_contact"]
    primary = next((s for s in staff if s.get("is_primary")), None)
    if not primary:
        return {"ok": False, "why": "no primary TGF contact on file for this course", "staff": staff}
    if not primary.get("email"):
        return {"ok": False, "why": f"the primary TGF contact ({primary.get('name')}) has no email on file",
                "staff": staff}
    cc = [s["email"] for s in staff if not s.get("is_primary") and s.get("email")]
    return {"ok": True, "to": primary["email"], "to_name": primary.get("name"), "cc": cc, "staff": staff}


def backfill(apply: bool = False, today: str | None = None, limit: int = 0, db_path=None) -> dict:
    """Every completed event with a course and no snapshot. Dry run unless apply."""
    from email_parser import database as db
    from email_parser.timezone_utils import today_central_str
    today = today or today_central_str()
    with db._connect(db_path) as conn:
        ids = [int(x[0]) for x in conn.execute(
            "SELECT id FROM events WHERE course_id IS NOT NULL AND event_date IS NOT NULL "
            "AND substr(event_date, 1, 10) < ? ORDER BY event_date DESC, id DESC", (today,)).fetchall()]
        have = {k for (k,) in conn.execute(
            "SELECT key FROM app_settings WHERE substr(key, 1, 22) = 'event_course_contacts:'").fetchall()}
    todo = [i for i in ids if KEY.format(i) not in have]
    if limit:
        todo = todo[:limit]
    done = []
    for eid in todo:
        r = snapshot(eid, apply=apply, source="backfill", db_path=db_path)
        done.append({"event_id": eid, "status": r.get("status"),
                     "contacts": len((r.get("snapshot") or {}).get("contacts") or [])})
    return {"dry_run": not apply, "completed_events": len(ids), "missing": len(todo), "events": done}
