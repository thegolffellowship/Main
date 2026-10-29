"""CORRECT A PLAYED CARD'S PLAYING HANDICAP (Kerry 2026-10-29).

Adam Baker played s9.27, s9.28 and s9.29 off 5, a guest's index (the
"Paul Cleary" link), where his own index then gave 4. Kerry: "Leave the paid
money alone, but correct the points."

`correct(event_id, customer_id, ph, apply)`:
  * the entered round's se_players handicap (score_entry, so a republish
    keeps it);
  * the published card: playing_handicap, net and the pops re-laid by the
    ruled allocator (entry_publish._derived_dots, the publish's own call);
  * a record in app setting `ph_corrections` with Kerry's ruling, including
    that the PAID money stands as recorded.
Payout rows are never touched. Points follow from the corrected card when
the races are rebuilt (tracker_points). Dry run by default.
"""
from __future__ import annotations

import json

SETTING = "ph_corrections"


def correct(event_id: int, customer_id: int, ph: float, apply: bool = False,
            note: str = "", db_path=None) -> dict:
    from . import database as db
    from . import score_entry as se
    from .entry_publish import _derived_dots
    from .timezone_utils import now_central
    with db._connect(db_path) as conn:
        r = conn.execute(
            "SELECT id, tee_id, playing_handicap, gross, net FROM scoring_rounds "
            "WHERE event_id = ? AND customer_id = ? AND source = 'entry'",
            (int(event_id), int(customer_id))).fetchone()
        if not r:
            return {"error": f"no published entered card for customer {customer_id} on event {event_id}"}
        holes = {h[0]: h[1] for h in conn.execute(
            "SELECT hole_number, strokes_received FROM scoring_holes WHERE scoring_round_id = ?",
            (r["id"],)).fetchall()}
        dots = _derived_dots(conn, {}, r["tee_id"], ph, sorted(holes))
        if ph and not dots:
            return {"error": "no stroke index for every hole on his tee; nothing changed"}
        out = {"event_id": event_id, "customer_id": customer_id, "scoring_round_id": r["id"],
               "ph_was": r["playing_handicap"], "ph_now": float(ph),
               "net_was": r["net"], "net_now": (r["gross"] - ph) if r["gross"] is not None else None,
               "pops_was": holes, "pops_now": {h: int(dots.get(h, 0) or 0) for h in holes},
               "entered_round": se.correct_player_handicap(event_id, customer_id, ph,
                                                           apply=False, db_path=db_path),
               "payouts": "untouched", "applied": bool(apply)}
        if not apply:
            return out
        conn.execute("UPDATE scoring_rounds SET playing_handicap = ?, net = ? WHERE id = ?",
                     (float(ph), out["net_now"], r["id"]))
        for h in holes:
            conn.execute("UPDATE scoring_holes SET strokes_received = ? "
                         "WHERE scoring_round_id = ? AND hole_number = ?",
                         (out["pops_now"][h], r["id"], h))
        conn.commit()
    se.correct_player_handicap(event_id, customer_id, ph, apply=True, db_path=db_path)
    raw = db.get_app_setting(SETTING, db_path=db_path) or "[]"
    try:
        rec = json.loads(raw)
    except ValueError:
        rec = []
    rec.append({"event_id": event_id, "customer_id": customer_id, "ph_was": out["ph_was"],
                "ph_now": float(ph), "at": now_central().strftime("%Y-%m-%d %H:%M"),
                "note": note})
    db.set_app_setting(SETTING, json.dumps(rec), db_path=db_path)
    db.log_agent_action("tracker-claude", "ph_correct",
                        f"event {event_id} customer {customer_id}: playing handicap "
                        f"{out['ph_was']} -> {ph}; payouts untouched. {note}", db_path=db_path)
    return out
