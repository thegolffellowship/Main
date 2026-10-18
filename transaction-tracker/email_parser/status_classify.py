"""Give a status to every customer who has none (Kerry 2026-10-18: "Yes
please classify"). About a fifth of every invitation went to people whose
customers.current_player_status was NULL, so the counts by type could not
say who they were.

The rules are the ones the system already uses, applied to the NULL rows the
existing passes skip (`memberships.sync_player_status_with_terms` only
touches rows that already carry a status; `_migrate_autocorrect_player_status`
only upgrades membership buyers):

1. A membership term on file: current -> active_member, lapsed ->
   expired_member.
2. Otherwise by what they have played (active registrations, not credited /
   refunded / transferred / WD), using the event's date:
   - none -> left as is (a contact or lead, not a player), reported;
   - last played more than 12 months ago -> inactive;
   - one event -> first_timer;
   - two or more -> active_guest.
Vendors and course contacts (`course_staff.non_member_ids`) are never
classified. Only NULL rows are ever written. Dry run by default.
"""
from __future__ import annotations

from datetime import date, timedelta

_SKIP = ("credited", "refunded", "transferred", "wd")


def classify(apply: bool = False, db_path=None) -> dict:
    from email_parser import database as db
    from email_parser.course_staff import non_member_ids
    from email_parser.memberships import _write_status_history, ensure_membership_tables

    conn = db.get_connection(db_path)
    try:
        ensure_membership_tables(conn)
        skip_ids = non_member_ids(conn)
        today = date.today().isoformat()
        cutoff = (date.today() - timedelta(days=365)).isoformat()
        rows = conn.execute(
            "SELECT customer_id, first_name, last_name FROM customers "
            "WHERE current_player_status IS NULL").fetchall()
        terms = {r["customer_id"]: r["expires_at"] for r in conn.execute(
            """SELECT m.customer_id, m.expires_at FROM customer_memberships m
                 JOIN (SELECT customer_id, MAX(started_at) AS latest
                         FROM customer_memberships GROUP BY customer_id) lp
                   ON lp.customer_id = m.customer_id AND lp.latest = m.started_at""").fetchall()}
        ph = ",".join("?" * len(_SKIP))
        played = {}
        for r in conn.execute(
                f"""SELECT i.customer_id, COUNT(DISTINCT i.event_id) AS n,
                           MAX(e.event_date) AS last_date
                      FROM items i JOIN events e ON e.id = i.event_id
                     WHERE i.customer_id IS NOT NULL AND i.parent_item_id IS NULL
                       AND COALESCE(i.transaction_status, 'active') NOT IN ({ph})
                       AND e.event_date IS NOT NULL AND e.event_date <= ?
                     GROUP BY i.customer_id""", (*_SKIP, today)).fetchall():
            played[r["customer_id"]] = (r["n"], r["last_date"])

        plan = {"active_member": [], "expired_member": [], "inactive": [],
                "first_timer": [], "active_guest": []}
        left, skipped = [], []
        for r in rows:
            cid = r["customer_id"]
            name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
            if cid in skip_ids:
                skipped.append({"customer_id": cid, "name": name}); continue
            if cid in terms:
                to = "active_member" if (terms[cid] or "") >= today else "expired_member"
            elif cid in played:
                n, last = played[cid]
                to = "inactive" if (last or "") < cutoff else ("first_timer" if n == 1 else "active_guest")
            else:
                left.append({"customer_id": cid, "name": name}); continue
            plan[to].append({"customer_id": cid, "name": name})

        out = {"null_status": len(rows), "counts": {k: len(v) for k, v in plan.items()},
               "left_no_play": len(left), "skipped_non_member": len(skipped),
               "examples": {k: v[:5] for k, v in plan.items()},
               "left_examples": left[:10], "applied": False}
        if not apply:
            return out
        for to, people in plan.items():
            ids = [p["customer_id"] for p in people]
            for cid in ids:
                conn.execute(
                    "UPDATE customers SET current_player_status = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE customer_id = ? AND current_player_status IS NULL", (to, cid))
            if to == "active_member" and ids:
                _write_status_history(conn, ids, "member", "classified from membership term")
            elif to == "expired_member" and ids:
                _write_status_history(conn, ids, "former", "classified from lapsed term")
        conn.commit()
        out["applied"] = True
        return out
    finally:
        conn.close()
