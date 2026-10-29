"""RE-STAGE A SAVED SHEET BY PACE (Kerry 2026-10-28, Event Ops #2483-3:
"hole assignments are moot until Rafe confirms, and groups should be ordered
by pace ratings anyway"; Kerry 10/29 "Start on them now").

After a manager hand-edits the groups, the sheet can be re-staged so the
fastest groups still start first, without changing who plays with whom:
each GROUP keeps its players, carts and blinds; only which start (slot)
it holds changes. The ordering is the generator's own (PAIRING_STAGING_*):
  * shotgun: short groups lead the train, then foursomes fastest first in
    play order (database._stage_shotgun_smalls_lead);
  * tee times: short groups take the earliest times, then fastest first;
    pace ties go to the lower total handicap.
Group pace = the average member pace_rating (1 slowest .. 3 fastest, unrated
reads as 2). A STANDINGS sheet on tee times is left alone (Kerry 10/28:
"We only want to honor leaders off last if it's tee times").
Dry run by default. Applied from the PAIRINGS tab's "Re-stage by pace" button
(POST /api/events/<id>/pairings/restage-pace) or bridge scoring-restage-pace.
After the lock, a re-stage moves people's starts, so the after-lock job sends
the UPDATED GROUP emails as it does for any saved change.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def plan(event_id: int, db_path=None) -> dict:
    from . import database as db
    with db._connect(db_path) as conn:
        db._ensure_pairing_tables(conn)
        ev = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
        if not ev:
            return {"error": f"no event {event_id}"}
        ev = dict(ev)
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM event_pairings WHERE event_id = ? ORDER BY holes, group_num, cart_pos",
            (int(event_id),))]
        roster = db._event_roster_rows(conn, int(event_id))
        cid_by_name = {db._pair_key_name(r.get("customer")): r.get("customer_id") for r in roster}
        # The seat's own customer_id first; the roster name match covers
        # rows saved before the column existed.
        cid_of = {r["player_name"]: (r.get("customer_id")
                                     or cid_by_name.get(db._pair_key_name(r["player_name"])))
                  for r in rows}
        paces = {}
        cids = sorted({int(c) for c in cid_of.values() if c})
        if cids:
            for r in conn.execute(f"SELECT customer_id, pace_rating FROM customers WHERE customer_id IN "
                                  f"({','.join('?' * len(cids))})", cids):
                paces[int(r[0])] = r[1]
    if not rows:
        return {"error": "no saved pairings for this event"}
    rules = db.get_pairing_staging_rules(db_path=db_path)
    default_r = rules.get("default_rating", 2)
    out = {"event_id": int(event_id), "legs": {}}
    for holes in sorted({r["holes"] for r in rows}):
        leg = [r for r in rows if r["holes"] == holes]
        groups: dict = {}
        labels: dict = {}
        for r in leg:
            groups.setdefault(r["group_num"], []).append(r)
            labels[r["group_num"]] = r["slot_label"]
        order = sorted(groups)
        combo = (ev.get("format") or "").strip() == "9/18 Combo"
        st = ev.get("start_type_18" if (combo and holes == "18") else "start_type") or ""
        shotgun = st == "Shotgun"
        if (ev.get("pairing_mode") or "") == "standings" and not shotgun:
            out["legs"][holes] = {"skipped": "standings on tee times: leaders go off last (Kerry 10/28)"}
            continue
        names = {g: [p["player_name"] for p in groups[g]] for g in order}

        def pace_fn(ns):
            vals = [(paces.get(int(cid_of[n]) if cid_of.get(n) else None) or default_r) for n in ns]
            return sum(vals) / len(vals) if vals else float(default_r)

        def hcp_fn(ns):
            by = {p["player_name"]: p.get("handicap_index") for g in order for p in groups[g]}
            return sum((by.get(n) if by.get(n) is not None else 20.0) for n in ns)

        glist = [names[g] for g in order]
        slots = [labels[g] for g in order]
        if shotgun:
            staged = db._stage_shotgun_smalls_lead(glist, slots, pace_fn, hcp_fn,
                                                    ring=9 if holes == "9" else 18)
        else:
            staged = sorted(glist, key=lambda g: (len(g) >= 4, -pace_fn(g), len(g), hcp_fn(g)))
        # staged[i] is the group (by its name list) that should hold slot i.
        key_of = {tuple(names[g]): g for g in order}
        moves = []
        for i, ns in enumerate(staged):
            src = key_of[tuple(ns)]
            dst = order[i]
            moves.append({"from_group": src, "to_group": dst, "from": labels[src], "to": labels[dst],
                          "players": ns, "pace": round(pace_fn(ns), 2)})
        out["legs"][holes] = {"shotgun": shotgun, "moves": moves,
                              "changes": sum(1 for m in moves if m["from_group"] != m["to_group"])}
    return out


def apply(event_id: int, db_path=None, by: str = "") -> dict:
    """Write the plan: groups take their new slots; blinds move with them."""
    from . import database as db
    p = plan(event_id, db_path)
    if p.get("error"):
        return p
    with db._connect(db_path) as conn:
        for holes, leg in p["legs"].items():
            if leg.get("skipped") or not leg.get("changes"):
                continue
            # Park every row of the leg first (UNIQUE event/holes/group/cart).
            conn.execute("UPDATE event_pairings SET group_num = group_num + 10000 "
                         "WHERE event_id = ? AND holes = ?", (int(event_id), holes))
            try:
                conn.execute("UPDATE blind_draws SET slot_key = 'tmp:' || id, group_num = group_num + 10000 "
                             "WHERE event_id = ? AND holes = ? AND group_num IS NOT NULL",
                             (int(event_id), holes))
            except Exception:
                pass
            for m in leg["moves"]:
                conn.execute("UPDATE event_pairings SET group_num = ?, slot_label = ? "
                             "WHERE event_id = ? AND holes = ? AND group_num = ?",
                             (m["to_group"], m["to"], int(event_id), holes, m["from_group"] + 10000))
                try:
                    conn.execute("UPDATE blind_draws SET group_num = ?, slot_label = ?, "
                                 "slot_key = ? || ':' || ? || ':' || cart_pos "
                                 "WHERE event_id = ? AND holes = ? AND group_num = ?",
                                 (m["to_group"], m["to"], holes, m["to_group"], int(event_id), holes,
                                  m["from_group"] + 10000))
                except Exception:
                    pass
            try:  # a blind not in a moved group keeps its own seat
                conn.execute("UPDATE blind_draws SET slot_key = holes || ':' || group_num || ':' || cart_pos "
                             "WHERE event_id = ? AND holes = ? AND slot_key LIKE 'tmp:%' AND group_num IS NOT NULL",
                             (int(event_id), holes))
            except Exception:
                pass
        conn.commit()
    try:
        db.log_agent_action("pace-restage", "pairings_restaged",
                            f"event {event_id}: {sum(l.get('changes', 0) for l in p['legs'].values())} "
                            f"group(s) moved by pace; by {by or 'unknown'}", db_path=db_path)
    except Exception:
        pass
    try:
        from .live_scoring_default import follow_sheet
        follow_sheet(int(event_id), db_path=db_path)
    except Exception:
        logger.exception("pace restage: follow_sheet failed")
    p["applied"] = True
    return p
