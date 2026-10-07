"""THE N/H FLAG (Kerry, "Good on both", CoS #1078 item 1 / #1079).

A manager marks a player who has no handicap as N/H for one event, from the
missing-handicap banner or the roster. Setting it clears the banner for that
player and tells Side Games' engine the player is N/H: their scores are
entered like anyone's, they play at zero, and a blind stands in for their
money (#1073). Table `event_nh_flags` (migrations/0003).

  event_nh_players(conn, event_id) -> set[int]   THE reader. Side Games'
      engine and the warning read only this, never the table.
  set_nh(event_id, customer_id, nh, set_by, note)  the one writer; logs
      before/after to agent_action_log. Refuses a customer who is not on
      the event's roster, and refuses to flag a player who HAS a handicap
      (N/H is for the missing case only).

Portable SQL (#682): ON CONFLICT ... DO UPDATE, no INSERT OR REPLACE.
"""
from __future__ import annotations


def event_nh_players(conn, event_id: int) -> set:
    try:
        return {int(r[0]) for r in conn.execute(
            "SELECT customer_id FROM event_nh_flags WHERE event_id = ? AND nh = 1",
            (int(event_id),))}
    except Exception:
        return set()


def set_nh(event_id: int, customer_id: int, nh: bool, set_by: str,
           note: str = "", db_path=None) -> dict:
    from email_parser import database as db
    from email_parser.handicap_warnings import missing_handicaps
    event_id, customer_id = int(event_id), int(customer_id)
    with db._connect(db_path) as conn:
        on_roster = any(int(r.get("customer_id") or 0) == customer_id
                        for r in db._event_roster_rows(conn, event_id))
        if not on_roster:
            return {"refused": f"customer {customer_id} is not on event {event_id}'s roster"}
        before = customer_id in event_nh_players(conn, event_id)
    if nh:
        m = missing_handicaps(event_id, db_path=db_path)
        missing_ids = {p.get("customer_id") for p in m.get("players", [])} | \
                      {p.get("customer_id") for p in m.get("nh_players", [])}
        if customer_id not in missing_ids:
            return {"refused": "this player has a handicap; N/H is only for a player with none"}
    with db._connect(db_path) as conn:
        conn.execute(
            """INSERT INTO event_nh_flags (event_id, customer_id, nh, set_by, note)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (event_id, customer_id) DO UPDATE SET
                   nh = excluded.nh, set_by = excluded.set_by,
                   set_at = datetime('now'), note = excluded.note""",
            (event_id, customer_id, 1 if nh else 0, set_by or "manager", note or None))
        conn.commit()
    try:
        db.log_agent_action(set_by or "manager", "set_nh_flag",
                            f"event {event_id} customer {customer_id} N/H {before} -> {bool(nh)}"
                            + (f"; {note}" if note else "") + "; authority CoS #1078",
                            db_path=db_path)
    except Exception:
        pass
    return {"event_id": event_id, "customer_id": customer_id, "before": before,
            "nh": bool(nh), "set_by": set_by}
