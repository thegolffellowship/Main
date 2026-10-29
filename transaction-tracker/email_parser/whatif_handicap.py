"""WHAT IF HE HAD PLAYED OFF HIS OWN HANDICAP (Kerry 2026-10-29).

After "Paul Cleary": Adam Baker played s9.27, s9.28 and s9.29 off 5 (the
guest's 9.0 index) when his own index at the time gave 4. Kerry: "show me
the corrected versions based on what his handicaps should have been for each
of those events...not his current handicap."

`whatif(event_id, overrides)` re-runs the event's engine IN MEMORY with the
given players' playing handicaps replaced ({customer_id: ph}) and their pops
re-laid on their own tee's stroke index by the ruled allocator
(`handicap_calc.ruled_dots`, the call the G-0 publish stores pops with).
The flights stay as the event froze them. It returns the money per game
before and after, the points and MVP, and each changed row. Writes nothing.
"""
from __future__ import annotations

import copy


def _money(pay: dict) -> dict:
    """{customer_id: total} for one game's payout rows."""
    out: dict = {}
    for r in (pay or {}).get("rows") or []:
        cid = r.get("customer_id")
        amt = float(r.get("amount") or 0)
        if cid is not None and amt:
            out[cid] = round(out.get(cid, 0.0) + amt, 2)
    return out


def _names(state: dict) -> dict:
    return {p["customer_id"]: p["name"] for p in state["players"] if p.get("customer_id")}


def _mvp(lb: dict) -> list:
    g = (lb.get("games") or {}).get("mvp") or {}
    w = g.get("winners") or g.get("winner") or []
    if isinstance(w, dict):
        w = [w]
    return [{"customer_id": x.get("customer_id"), "name": x.get("name"),
             "points": x.get("points")} for x in w]


def whatif(event_id: int, overrides: dict, db_path=None) -> dict:
    from . import database as db
    from . import live_scoring as _ls
    from .handicap_calc import ruled_dots
    with db._connect(db_path) as conn:
        ev = conn.execute("SELECT item_name, event_date FROM events WHERE id = ?",
                          (int(event_id),)).fetchone()
    if not ev:
        return {"error": f"no event {event_id}"}
    st0 = db.event_engine_state(ev["item_name"], db_path=db_path)
    if st0.get("error"):
        return {"error": st0["error"]}
    st1 = copy.deepcopy(st0)
    base_si = {h["hole"]: h["stroke_index"] for h in st1["holes"]}
    changed = []
    for p in st1["players"]:
        cid = p.get("customer_id")
        if cid is None or int(cid) not in overrides:
            continue
        new_ph = overrides[int(cid)]
        si = {h: (p.get("stroke_index_by_hole") or {}).get(h, s) for h, s in base_si.items()}
        old = {"ph": p["playing_handicap"], "pops": dict(p.get("strokes_received") or {})}
        p["playing_handicap"] = float(new_ph)
        p["strokes_received"] = {int(h): v for h, v in ruled_dots(new_ph, si).items()}
        changed.append({"customer_id": cid, "name": p["name"], "ph_was": old["ph"],
                        "ph_now": new_ph, "pops_was": old["pops"],
                        "pops_now": p["strokes_received"]})
    if not changed:
        return {"error": "none of those customers has a card on this event"}

    fb = db.event_flights_board(int(event_id), db_path=db_path)
    pay0 = db.engine_game_payouts(ev["item_name"], db_path=db_path, state=st0, board=fb)
    pay1 = db.engine_game_payouts(ev["item_name"], db_path=db_path, state=st1, board=fb)
    formulas = db.get_scoring_formulas(db_path)
    lb0 = _ls.compute_leaderboard(st0, formulas)
    lb1 = _ls.compute_leaderboard(st1, formulas)
    names = _names(st0)

    games = {}
    total0: dict = {}
    total1: dict = {}
    for g in sorted(set((pay0.get("games") or {})) | set((pay1.get("games") or {}))):
        m0 = _money((pay0.get("games") or {}).get(g))
        m1 = _money((pay1.get("games") or {}).get(g))
        for cid, a in m0.items():
            total0[cid] = round(total0.get(cid, 0) + a, 2)
        for cid, a in m1.items():
            total1[cid] = round(total1.get(cid, 0) + a, 2)
        diff = [{"customer_id": c, "name": names.get(c), "was": m0.get(c, 0.0),
                 "now": m1.get(c, 0.0)}
                for c in sorted(set(m0) | set(m1)) if m0.get(c, 0.0) != m1.get(c, 0.0)]
        games[g] = {"status": ((pay1.get("games") or {}).get(g) or {}).get("status"),
                    "changes": diff}
    # Team Net is not on the flight board: its standings come from the engine.
    for gk in ("team_net",):
        def _tn(lb):
            res = (lb["games"].get(gk) or {})
            return [{"team": t.get("team"), "place": t.get("place"), "vs_par": t.get("vs_par"),
                     "members": t.get("members")} for t in (res.get("teams") or [])][:5]
        games[gk + "_top"] = {"was": _tn(lb0), "now": _tn(lb1)}

    def _pts(lb):
        return {r["customer_id"]: r["points"] for r in lb["overall"] if r.get("customer_id")}
    p0, p1 = _pts(lb0), _pts(lb1)

    def _top(lb, n=5):
        return [{"name": r["name"], "points": r["points"], "net": r["net"], "rank": r.get("rank")}
                for r in lb["overall"][:n]]
    flights = {}
    for entry in (fb or {}).get("games") or []:
        for f in (entry.get("selection") or {}).get("flights") or []:
            for m in f.get("members") or []:
                if m.get("customer_id") in overrides:
                    flights.setdefault(entry["game"], {
                        "flight": f.get("flight_no"),
                        "member": {k: m.get(k) for k in ("index", "playing_handicap", "hcp", "handicap") if k in m},
                        "flight_range": {k: f.get(k) for k in ("low", "high", "range", "label") if k in f}})
    return {
        "event": ev["item_name"], "event_date": ev["event_date"], "writes": "none",
        "board_state": (fb or {}).get("state"),
        "changed_players": changed,
        "points": [{"customer_id": c["customer_id"], "name": c["name"],
                    "was": p0.get(c["customer_id"]), "now": p1.get(c["customer_id"])}
                   for c in changed],
        "points_top_was": _top(lb0), "points_top_now": _top(lb1),
        "mvp_was": _mvp(lb0), "mvp_now": _mvp(lb1),
        "games": games,
        "money_changes": [{"customer_id": c, "name": names.get(c),
                           "was": total0.get(c, 0.0), "now": total1.get(c, 0.0)}
                          for c in sorted(set(total0) | set(total1))
                          if total0.get(c, 0.0) != total1.get(c, 0.0)],
        "pot_was": round(sum(total0.values()), 2), "pot_now": round(sum(total1.values()), 2),
        "flights_held_as_frozen": flights,
    }
