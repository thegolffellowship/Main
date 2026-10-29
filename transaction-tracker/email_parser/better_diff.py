"""THE BETTER-DIFFERENTIAL RULE (Kerry 2026-10-28, Event Ops #2479/#2480,
CoS #2505-1; Kerry 10/29 "Start on them now").

Kerry: "As a new rule for handicaps. If a new player with a temporary handicap
(doesn't have a TGF Handicap) shoots a differential better than their temporary
handicap, then that their temporary handicap immediately updates to that
differential until they establish their TGF Handicap." And: "This would be like
the Adam Wilson rule. Where he greatly beat his initial intro handicap he
submitted for s9.28 TPC Canyons, it immediately goes to that differential to
protect the field."

At every handicap posting (both derive paths, so the closeout chain and a
manual post alike), for each player of the posted event:
  * WHO: a customer with a temporary handicap (customers.starting_handicap_18,
    any source) and no established TGF Handicap yet: fewer than 27 holes
    posted (3 nines) counting this event (CoS reading of the Standard's §2).
  * WHAT: the event's differential on the 18-hole scale: a nine's
    differential x 2 (the Wilson step: 3.1 for 9 -> 6.2), an 18 posted as
    two nines = the two nines' differentials summed. The differential is the
    one the post itself computed (WHS net double bogey), never a raw one.
  * ONLY DOWN: if it is lower than the temporary handicap, the temporary
    handicap becomes it (set_by "rule:better_differential", the note names
    the event and the differential). A worse round changes nothing.
  * The event just played is never re-scored: payouts, flights and points
    stand. The real TGF index takes over once established (as it always did).
Dial `better_differential_rule` (on unless "off").
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SET_BY = "rule:better_differential"
ESTABLISHED_HOLES = 27


def enabled(db_path=None) -> bool:
    from . import database as db
    return (db.get_app_setting("better_differential_rule", db_path=db_path) or "on").strip().lower() \
        not in ("off", "0", "false", "no")


def _event_ids(conn, names) -> list:
    out = []
    for n in names or []:
        for r in conn.execute("SELECT id FROM events WHERE lower(item_name) = lower(?)", (n,)):
            out.append(int(r[0]))
    return out


def plan(event_ids, db_path=None) -> list:
    """What the rule would change for these events (pure read)."""
    from . import database as db
    out = []
    with db._connect(db_path) as conn:
        for eid in event_ids:
            ev = conn.execute("SELECT item_name FROM events WHERE id = ?", (int(eid),)).fetchone()
            rounds = conn.execute(
                "SELECT id, customer_id FROM scoring_rounds WHERE event_id = ? AND customer_id IS NOT NULL",
                (int(eid),)).fetchall()
            for sr in rounds:
                cid = int(sr["customer_id"])
                c = conn.execute("SELECT starting_handicap_18, first_name, last_name FROM customers "
                                 "WHERE customer_id = ?", (cid,)).fetchone()
                if not c or c["starting_handicap_18"] is None:
                    continue
                diffs = [float(r[0]) for r in conn.execute(
                    "SELECT differential FROM handicap_rounds WHERE scoring_round_id = ? "
                    "AND differential IS NOT NULL", (int(sr["id"]),))]
                if not diffs:
                    continue
                nines = conn.execute(
                    "SELECT COUNT(*) FROM handicap_rounds WHERE differential IS NOT NULL AND "
                    "(customer_id = ? OR player_name IN (SELECT player_name FROM handicap_player_links "
                    "WHERE customer_id = ?))", (cid, cid)).fetchone()[0]
                if nines * 9 >= ESTABLISHED_HOLES:
                    continue          # established: the real index rules
                d18 = round(diffs[0] * 2 if len(diffs) == 1 else sum(diffs), 1)
                cur = float(c["starting_handicap_18"])
                if d18 < cur:
                    out.append({"customer_id": cid,
                                "name": f"{c['first_name'] or ''} {c['last_name'] or ''}".strip(),
                                "event_id": int(eid), "event": ev["item_name"] if ev else "",
                                "was": cur, "now": d18, "nines": [round(x, 1) for x in diffs]})
    return out


def apply_for_events(event_ids, apply: bool = True, db_path=None) -> dict:
    if not enabled(db_path):
        return {"skipped": "better_differential_rule is off"}
    from . import database as db
    changes = plan(event_ids, db_path)
    if apply:
        for ch in changes:
            note = (f"{ch['event']}: differential {' + '.join(str(x) for x in ch['nines'])} "
                    f"(18-hole {ch['now']}) beat the temporary {ch['was']} (Kerry 10/28, the Wilson rule)")
            r = db.set_starting_handicap(ch["customer_id"], ch["now"], set_by=SET_BY, note=note,
                                         db_path=db_path)
            ch["applied"] = not r.get("error")
            try:
                db.log_agent_action("better-differential", "starting_handicap_lowered",
                                    f"customer {ch['customer_id']} ({ch['name']}): {ch['was']} -> {ch['now']}; {note}",
                                    db_path=db_path)
            except Exception:
                pass
    return {"dry_run": not apply, "changes": changes}


def after_post(event_names, db_path=None) -> dict | None:
    """Called by both derive paths after a real posting. Never raises."""
    try:
        from . import database as db
        with db._connect(db_path) as conn:
            ids = _event_ids(conn, event_names)
        return apply_for_events(ids, apply=True, db_path=db_path)
    except Exception:
        logger.exception("better differential: skipped")
        return None
