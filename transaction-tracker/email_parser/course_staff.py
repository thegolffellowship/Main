"""COURSE STAFF: the people TGF works with at each course (migration 0014).

Kerry 2026-10-13: "Please do add these into our database and assign
appropriate roles. Also when we run events thru the quarry, those contacts
should come up in the event setup when Quarry is selected. Those would be
there for record and for the system to know who to send docs too."
Rule 3b: "Deploy now" (#1737). Shape #1699, db-claude PASS with changes #1701.

- Every contact is a person with a customer_id (principle 6). The email is
  read from customer_emails, never stored here.
- `for_course` is the ONE reader. `print_recipients` decides the Course Files
  email: To the primary active 'tgf_contact', CC the other active
  'tgf_contact' rows. No primary with an email means refused, never guessed.
- `save_staff` is the ONE writer (admin UI, or a bridge citing Kerry's
  OK post). Dry run unless apply. Rows are deactivated, never deleted.
- `non_member_ids` is the ONE "not a member audience" predicate (#1701-b):
  a person whose only roles are course_contact / sponsor / vendor, who has
  never bought or registered, is kept out of Brevo, rosters, member sends
  and the pairings roster. It folds in `vendor_customer_ids`.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

ROLES = ("tgf_contact", "general_manager", "head_golf_professional",
         "assistant_general_manager", "golf_shop", "food_beverage", "billing")
ROLE_LABELS = {
    "tgf_contact": "TGF contact",
    "general_manager": "General manager",
    "head_golf_professional": "Head golf professional",
    "assistant_general_manager": "Assistant general manager",
    "golf_shop": "Golf shop",
    "food_beverage": "Food & beverage",
    "billing": "Billing",
}
# Roles that make someone a member audience; a person holding one of these
# is never excluded, whatever else they are.
_AUDIENCE_ROLES = ("golfer", "manager", "admin", "owner")
_NON_AUDIENCE_ROLES = ("course_contact", "sponsor", "vendor")
_EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


def _table_exists(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'course_staff'").fetchone())


def _primary_email(conn, customer_id: int) -> str | None:
    r = conn.execute(
        """SELECT email FROM customer_emails
            WHERE customer_id = ? AND COALESCE(undeliverable, 0) = 0
              AND email IS NOT NULL AND email <> ''
            ORDER BY is_primary DESC, email_id LIMIT 1""", (customer_id,)).fetchone()
    return (r[0] or "").strip() or None if r else None


def for_course(conn, course_id: int, include_inactive: bool = False) -> list[dict]:
    """Everyone on file at one course, primary first within each role."""
    if not _table_exists(conn):
        return []
    rows = conn.execute(
        f"""SELECT s.course_staff_id, s.course_id, s.customer_id, s.role, s.is_primary,
                   s.notes, s.active, c.first_name, c.last_name, c.phone
              FROM course_staff s JOIN customers c ON c.customer_id = s.customer_id
             WHERE s.course_id = ? {"" if include_inactive else "AND s.active = 1"}
             ORDER BY s.active DESC, s.role, s.is_primary DESC, c.last_name, c.first_name""",
        (int(course_id),)).fetchall()
    out = []
    for r in rows:
        out.append({
            "course_staff_id": r["course_staff_id"], "course_id": r["course_id"],
            "customer_id": r["customer_id"],
            "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "role": r["role"], "role_label": ROLE_LABELS.get(r["role"], r["role"]),
            "is_primary": bool(r["is_primary"]), "active": bool(r["active"]),
            "notes": r["notes"], "phone": r["phone"],
            "email": _primary_email(conn, r["customer_id"]),
        })
    return out


def print_recipients(conn, course_id: int) -> dict:
    """Who gets the Course Files email (slice 1, #1699): To the primary
    active TGF contact, CC every other active TGF contact. Refused when there
    is no primary with an email."""
    staff = [s for s in for_course(conn, course_id) if s["role"] == "tgf_contact"]
    primary = next((s for s in staff if s["is_primary"]), None)
    if not primary:
        return {"ok": False, "why": "no primary TGF contact on file for this course",
                "staff": staff}
    if not primary["email"]:
        return {"ok": False, "why": f"the primary TGF contact ({primary['name']}) has no email on file",
                "staff": staff}
    cc = [s["email"] for s in staff if not s["is_primary"] and s["email"]]
    return {"ok": True, "to": primary["email"], "to_name": primary["name"],
            "cc": cc, "staff": staff}


def non_member_ids(conn) -> set:
    """The ONE "not a member audience" predicate (#1701-b), as a set.

    Vendors (`vendor_customer_ids`) plus anyone who holds a course_contact /
    sponsor role, holds no golfer/manager/admin/owner role, and has never
    bought or registered for anything (no items row). A course contact who
    also plays with TGF stays a member."""
    from email_parser import database as db
    out = set(db.vendor_customer_ids(conn))
    try:
        rows = conn.execute(
            f"""SELECT r.customer_id FROM customer_roles r
                 WHERE lower(r.role_type) IN ({",".join("?" * len(_NON_AUDIENCE_ROLES))})
                   AND NOT EXISTS (SELECT 1 FROM customer_roles a
                                    WHERE a.customer_id = r.customer_id
                                      AND lower(a.role_type) IN ({",".join("?" * len(_AUDIENCE_ROLES))}))
                   AND NOT EXISTS (SELECT 1 FROM items i WHERE i.customer_id = r.customer_id)""",
            (*_NON_AUDIENCE_ROLES, *_AUDIENCE_ROLES)).fetchall()
        out |= {int(r[0]) for r in rows if r[0] is not None}
    except Exception:
        logger.exception("non_member_ids: role read failed; vendors only")
    return out


def member_audience(conn, customer_id) -> bool:
    try:
        return int(customer_id) not in non_member_ids(conn)
    except (TypeError, ValueError):
        return True


def _resolve_person(conn, name: str, email: str) -> dict:
    """Email first (the dedupe db-claude asked for), then an exact unique
    first+last match, else a new person."""
    if email:
        r = conn.execute(
            "SELECT DISTINCT customer_id FROM customer_emails WHERE lower(email) = lower(?)",
            (email,)).fetchall()
        if len(r) == 1:
            return {"customer_id": int(r[0][0]), "matched": "email"}
        if len(r) > 1:
            return {"error": f"{email} is on {len(r)} customers; merge them first"}
    parts = (name or "").split()
    if len(parts) < 2:
        return {"error": "give a first and last name"}
    first, last = parts[0], " ".join(parts[1:])
    r = conn.execute(
        "SELECT customer_id FROM customers WHERE lower(first_name) = lower(?) AND lower(last_name) = lower(?)",
        (first, last)).fetchall()
    if len(r) == 1:
        return {"customer_id": int(r[0][0]), "matched": "name"}
    if len(r) > 1:
        return {"error": f"{len(r)} customers are named {first} {last}; enter their email to pick one"}
    return {"customer_id": None, "matched": "new", "first": first, "last": last}


def save_staff(course_id, *, name: str = "", email: str = "", phone: str = "",
               role: str = "tgf_contact", is_primary: bool = False, notes: str = "",
               customer_id=None, active: bool = True, apply: bool = False,
               set_by: str = "admin", kerry_ok_post=None, db_path=None) -> dict:
    """Add or update one person's role at one course. Making someone primary
    demotes the previous primary for that role. `active=False` deactivates the
    row (kept for history). From a bridge, `kerry_ok_post` must carry Kerry's
    word; the admin UI is Kerry's own session."""
    from email_parser import database as db
    role = (role or "").strip()
    if role not in ROLES:
        return {"refused": f"role must be one of {', '.join(ROLES)}"}
    email = (email or "").strip()
    if email and not _EMAIL_RE.match(email):
        return {"refused": f"not an email address: {email}"}
    with db._connect(db_path) as conn:
        if not _table_exists(conn):
            return {"refused": "course_staff is not in this database yet (migration 0014)"}
        if kerry_ok_post is not None:
            from email_parser.customer_query import _kerry_ok
            ok, why = _kerry_ok(conn, kerry_ok_post)
            if not ok:
                return {"refused": f"rule 3b: {why}"}
        course = conn.execute("SELECT course_id, name FROM courses WHERE course_id = ?",
                              (int(course_id),)).fetchone()
        if not course:
            return {"refused": f"course {course_id} not found"}
        if customer_id:
            c = conn.execute("SELECT customer_id, first_name, last_name FROM customers WHERE customer_id = ?",
                             (int(customer_id),)).fetchone()
            if not c:
                return {"refused": f"customer {customer_id} not found"}
            who = {"customer_id": int(c[0]), "matched": "id"}
            name = name or f"{c['first_name'] or ''} {c['last_name'] or ''}".strip()
        else:
            who = _resolve_person(conn, name, email)
            if who.get("error"):
                return {"refused": who["error"]}
        cid = who["customer_id"]
        existing = None
        if cid:
            existing = conn.execute(
                "SELECT course_staff_id, is_primary, active FROM course_staff "
                "WHERE course_id = ? AND customer_id = ? AND role = ?",
                (int(course_id), cid, role)).fetchone()
        prev_primary = conn.execute(
            """SELECT s.course_staff_id, s.customer_id, c.first_name, c.last_name
                 FROM course_staff s JOIN customers c ON c.customer_id = s.customer_id
                WHERE s.course_id = ? AND s.role = ? AND s.is_primary = 1 AND s.active = 1""",
            (int(course_id), role)).fetchone()
        demote = (bool(is_primary) and active and prev_primary is not None
                  and prev_primary["customer_id"] != cid)
        plan = {"course_id": int(course_id), "course": course["name"], "name": name,
                "email": email or None, "role": role, "is_primary": bool(is_primary) and active,
                "active": bool(active), "person": who["matched"], "customer_id": cid,
                "action": ("update" if existing else "add"),
                "demotes": (f"{prev_primary['first_name']} {prev_primary['last_name']}".strip()
                            if demote else None)}
        if not apply:
            return {"dry_run": True, **plan}
        if cid is None:
            cid = conn.execute(
                """INSERT INTO customers (first_name, last_name, phone, acquisition_source, account_status)
                   VALUES (?, ?, ?, 'course_contact', 'active') RETURNING customer_id""",
                (who["first"], who["last"], (phone or "").strip() or None)).fetchone()[0]
            plan["customer_id"] = cid
        if email:
            have = conn.execute("SELECT 1 FROM customer_emails WHERE customer_id = ? AND lower(email) = lower(?)",
                                (cid, email)).fetchone()
            if not have:
                n = conn.execute("SELECT COUNT(*) FROM customer_emails WHERE customer_id = ?", (cid,)).fetchone()[0]
                conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary, is_golf_genius, label) "
                             "VALUES (?, ?, ?, 0, 'course_staff')", (cid, email, 1 if n == 0 else 0))
        if not conn.execute("SELECT 1 FROM customer_roles WHERE customer_id = ? AND role_type = 'course_contact'",
                            (cid,)).fetchone():
            conn.execute("INSERT INTO customer_roles (customer_id, role_type) VALUES (?, 'course_contact')", (cid,))
        if demote:
            conn.execute("UPDATE course_staff SET is_primary = 0, updated_at = CURRENT_TIMESTAMP "
                         "WHERE course_staff_id = ?", (prev_primary["course_staff_id"],))
        prim = 1 if (is_primary and active) else 0
        if existing:
            conn.execute(
                """UPDATE course_staff SET is_primary = ?, active = ?, notes = COALESCE(?, notes),
                          updated_at = CURRENT_TIMESTAMP WHERE course_staff_id = ?""",
                (prim, 1 if active else 0, (notes or None), existing["course_staff_id"]))
            sid = existing["course_staff_id"]
        else:
            sid = conn.execute(
                """INSERT INTO course_staff (course_id, customer_id, role, is_primary, notes, active, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING course_staff_id""",
                (int(course_id), cid, role, prim, (notes or None), 1 if active else 0, set_by)).fetchone()[0]
        conn.commit()
    try:
        import json as _json
        db.log_agent_action(set_by, "course_staff_save",
                            _json.dumps({**plan, "course_staff_id": sid}, default=str),
                            outcome="applied", db_path=db_path)
    except Exception:
        logger.exception("course_staff: action log failed")
    return {"applied": True, "course_staff_id": sid, **plan}


# Kerry via Front Desk (#1699): The Quarry's people. Loaded by the seed
# bridge after 0014 applies, dry run first, never inside the SQL.
QUARRY_SEED = (
    ("Chris Lopez", "chris@quarrygolf.com", "tgf_contact", True),
    ("Alec Cech", "alec@quarrygolf.com", "tgf_contact", False),
    ("Dustin Burell", "dustin@quarrygolf.com", "general_manager", True),
    ("Miguel Amaya", "miguel@quarrygolf.com", "assistant_general_manager", True),
    ("Miguel Amaya", "miguel@quarrygolf.com", "head_golf_professional", True),
)


def seed_quarry(course_id: int, apply: bool = False, kerry_ok_post=None, db_path=None) -> dict:
    out = []
    for name, email, role, prim in QUARRY_SEED:
        out.append(save_staff(course_id, name=name, email=email, role=role, is_primary=prim,
                              apply=apply, set_by="seed:#1699", kerry_ok_post=kerry_ok_post,
                              db_path=db_path))
    return {"apply": apply, "rows": out,
            "count": sum(1 for r in out if r.get("applied") or r.get("dry_run"))}
