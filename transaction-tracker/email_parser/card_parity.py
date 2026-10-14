"""The engine and the scorecard must agree, player by player (Kerry 10/14).

s9.27 The Quarry (10/13): the stored cards were right and the payout engine
was wrong for Dan Stich (net 41 against the card's 38), because the engine
worked out his strokes a second time on the wrong tee's indexes. Nothing
noticed until the money was checked by hand. Kerry: "My members need full
confidence in this app."

`engine_card_parity(event)` compares, for every entered card on an event:

  1. the STORED strokes on each hole against the rule (the player's own
     tee, the nine he played, `handicap_calc.ruled_dots`), worked out here
     independently, so a card saved with the wrong strokes is caught; and
  2. the ENGINE's card (`event_engine_state` + `live_scoring.build_cards`,
     the one payouts and points read) against the stored card: strokes on
     every hole, gross and net.

Any difference HOLDS the money and the points:
  - `record_event_game_payouts` refuses (every writer: auto payouts, the
    bridge, the closeout);
  - `closeout_final_check` lists it as blocking;
  - `tracker_points` leaves the event out and refuses to apply;
and publishing raises one COO action item naming each player and hole.

Golf Genius-era cards carry GG's own dots and are not checked here.
Read-only. Bridge `scoring-card-parity:<event>`; guard `test_card_parity.py`.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

ENTRY_SOURCE = "entry"


def _resolve(conn, event) -> dict | None:
    if isinstance(event, int) or str(event).strip().isdigit():
        row = conn.execute("SELECT * FROM events WHERE id = ?", (int(event),)).fetchone()
    else:
        row = conn.execute("SELECT * FROM events WHERE lower(item_name) = lower(?)",
                           (str(event).strip(),)).fetchone()
    return dict(row) if row else None


def _played_set(holes: list) -> list:
    """The nine (or 18) a card belongs to, from the holes it carries."""
    if not holes:
        return []
    if max(holes) <= 9:
        return list(range(1, 10))
    if min(holes) >= 10:
        return list(range(10, 19))
    return list(range(1, 19))


def engine_card_parity(event, db_path=None, state: dict | None = None) -> dict:
    """{event, checked, ok, mismatches: [{customer_id, name, kind, detail}]}.
    `state` may be passed by a caller that already built the engine state."""
    from email_parser import database as db
    from email_parser import live_scoring as ls
    from email_parser.handicap_calc import ruled_dots

    with db._connect(db_path) as conn:
        db._ensure_scoring_tables(conn)
        ev = _resolve(conn, event)
        if not ev:
            return {"error": f"no event matches {event!r}"}
        cards = [dict(r) for r in conn.execute(
            "SELECT id, customer_id, player_name, tee_id, playing_handicap, "
            "lower(COALESCE(source,'gg')) AS src FROM scoring_rounds WHERE event_id = ?",
            (ev["id"],)).fetchall()]
        entry = [c for c in cards if c["src"] == ENTRY_SOURCE]
        out = {"event": {"id": ev["id"], "name": ev["item_name"]},
               "checked": 0, "mismatches": []}
        stored: dict = {}
        tee_si: dict = {}
        for c in list(entry):
            holes = {}
            for h in conn.execute(
                    "SELECT hole_number, strokes, strokes_received FROM scoring_holes "
                    "WHERE scoring_round_id = ?", (c["id"],)).fetchall():
                holes[int(h["hole_number"])] = (h["strokes"], int(h["strokes_received"] or 0))
            if not holes:
                # A card with no holes saved has nothing to score or compare.
                entry.remove(c)
                continue
            stored[c["id"]] = holes
            if c["tee_id"] and c["tee_id"] not in tee_si:
                tee_si[c["tee_id"]] = {int(x["hole_number"]): int(x["stroke_index"])
                                       for x in db._ls_tee_holes(conn, c["tee_id"])
                                       if x.get("stroke_index")}

    out["checked"] = len(entry)
    if not entry:
        out["ok"] = True
        out["note"] = ("no entered cards with holes on this event "
                       "(Golf Genius cards carry GG's own strokes)")
        return out
    miss = out["mismatches"]

    def _add(c, kind, detail):
        miss.append({"customer_id": c["customer_id"],
                     "name": c["player_name"] or f"customer {c['customer_id']}",
                     "scoring_round_id": c["id"], "kind": kind, "detail": detail})

    # 1. Stored strokes against the rule, worked out independently.
    for c in entry:
        holes = stored[c["id"]]
        if c["playing_handicap"] is None:
            continue
        nine = _played_set(sorted(holes))
        si_all = tee_si.get(c["tee_id"]) or {}
        si = {h: si_all[h] for h in nine if h in si_all}
        if len(si) != len(nine):
            _add(c, "no_stroke_index",
                 "the card's tee has no stroke index for every hole played; "
                 "its strokes cannot be checked")
            continue
        want = ruled_dots(c["playing_handicap"], si)
        bad = [f"hole {h}: card {holes[h][1]}, rule {int(want.get(h, 0) or 0)}"
               for h in sorted(holes) if holes[h][1] != int(want.get(h, 0) or 0)]
        if bad:
            _add(c, "stored_strokes_off_rule",
                 f"strokes saved on the card differ from the rule "
                 f"(handicap {c['playing_handicap']}, own tee): " + "; ".join(bad))

    # 2. The engine's card against the stored card.
    st = state if state is not None else db.event_engine_state(ev["item_name"], db_path=db_path)
    if st.get("error"):
        out["engine_error"] = st["error"]
        _add({"customer_id": None, "player_name": "(event)", "id": None}, "engine_error",
             f"the engine could not build this event: {st['error']}")
    else:
        formulas = (db.get_championship_formulas(db_path=db_path)
                    if (st.get("meta") or {}).get("championship")
                    else db.get_scoring_formulas(db_path))
        eng = {str(c.get("key")): c for c in ls.build_cards(st, formulas)}
        for c in entry:
            ec = eng.get(str(c["id"]))
            holes = stored[c["id"]]
            if ec is None:
                _add(c, "engine_missing", "the engine has no card for this player")
                continue
            e_holes = {int(h["hole"]): h for h in ec.get("holes") or []}
            bad = []
            for h, (g, sr) in sorted(holes.items()):
                eh = e_holes.get(h)
                if g is None:
                    continue
                if eh is None:
                    bad.append(f"hole {h}: not on the engine's card")
                    continue
                if (eh.get("strokes") != g) or int(eh.get("strokes_received") or 0) != sr:
                    bad.append(f"hole {h}: card {g}/{sr} pops, engine "
                               f"{eh.get('strokes')}/{int(eh.get('strokes_received') or 0)} pops")
            gross = sum(g for g, _ in holes.values() if g is not None)
            net = gross - sum(sr for g, sr in holes.values() if g is not None)
            if ec.get("gross") != gross:
                bad.append(f"gross: card {gross}, engine {ec.get('gross')}")
            if ec.get("net") != net:
                bad.append(f"net: card {net}, engine {ec.get('net')}")
            if bad:
                _add(c, "engine_differs_from_card", "; ".join(bad))
    out["ok"] = not miss
    return out


def blocking_reason(parity: dict) -> str | None:
    """One line for a refusal, or None when the event is clean."""
    if not parity or parity.get("ok") or parity.get("error"):
        return None
    names = sorted({m["name"] for m in parity["mismatches"]})
    return (f"engine and scorecards disagree for {len(names)} player(s): "
            f"{', '.join(names)} — payouts and points held until fixed "
            f"(scoring-card-parity:{parity['event']['id']})")


def alarm(parity: dict, db_path=None) -> None:
    """One COO action item per event while it is open (deduped by subject)."""
    if not parity or parity.get("ok") or parity.get("error"):
        return
    from email_parser import database as db
    ev = parity["event"]
    lines = [f"- {m['name']}: {m['detail']}" for m in parity["mismatches"]]
    try:
        db.save_action_item({
            "subject": f"SCORING HOLD: engine vs scorecard — {ev['name']}",
            "from_name": "Card parity check",
            "summary": ("Payouts and points are held for this event until the engine "
                        "and the saved scorecards agree on every player.\n" + "\n".join(lines)),
            "urgency": "high", "category": "scoring"}, db_path=db_path)
    except Exception:
        logger.exception("card parity alarm failed for %s", ev.get("name"))
