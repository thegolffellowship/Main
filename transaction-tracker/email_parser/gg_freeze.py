"""FREEZE THE 2026 CHAMPIONSHIP RECORD (Kerry 2026-10-13: "All needs to be
hardened/locked on our side to not rely on Golf Genius for anything related
to 2026 without losing ANY results").

The Fellowship Cup and Players Cup boards add the TGF Championship's points
read LIVE off Golf Genius, and each row expands to a championship card read
live too. A GG-side change (a board emptied, a round repointed) or GG going
away would change or blank them. And the race is close: the copy saved on
8/13-8/16 (`gg_champ_final_board_*`) differs from today's live board by a
point for Jeff Young in the Players Cup (60 saved vs 59 shown), which would
flip the champion if it were served instead. So nothing is re-derived: this
captures EXACTLY the payload members see now, while GG is still reachable,
into `gg_data_snapshots` (the database, so it is replicated and backed up):

  frozen_champ_points:<race>  the full fetch_champ_points payload
  frozen_champ_cards:<race>   {"cards": {"<cid>|<board>|": card payload}}

`fetch_champ_points` / `fetch_champ_player_card` serve these once GG points
intake is off. Nothing here writes anything else. Re-running replaces the
capture (refuses a stale or empty board).
"""

from __future__ import annotations

import time


def freeze_points(race_key: str, apply: bool = False, db_path=None) -> dict:
    from . import database as db
    live = db.fetch_champ_points(race_key, max_age=0, db_path=db_path, live=True)
    players = live.get("players") or []
    summary = {"race": race_key, "configured": live.get("configured"),
               "stale": live.get("stale"), "error": live.get("error"),
               "players": len(players), "boards": live.get("boards"),
               "field": live.get("field"), "scoring": live.get("scoring"),
               "top": [(p.get("name"), p.get("points")) for p in players[:6]]}
    if not live.get("configured") or not players or live.get("stale") or live.get("error"):
        summary["refused"] = "the live board is not complete and fresh, nothing frozen"
        return summary
    if apply:
        db.save_gg_snapshot(f"frozen_champ_points:{race_key}", live, db_path)
        summary["frozen"] = True
    return summary


def freeze_cards(race_key: str, start: int = 0, budget: float = 20.0,
                 db_path=None) -> dict:
    """Capture every player's card on the frozen board, per round label and
    the default view, a chunk at a time (call again with start=next)."""
    from . import database as db
    pts = db.load_gg_snapshot(f"frozen_champ_points:{race_key}", db_path)
    if not pts:
        return {"error": f"freeze the {race_key} board first"}
    cids = []
    for p in pts.get("players") or []:
        cid = p.get("customer_id")
        if cid is not None and int(cid) not in cids:
            cids.append(int(cid))
    boards = [None] + [b for b in (pts.get("boards") or []) if b]
    keys = [(c, b) for c in cids for b in boards]
    snap = db.load_gg_snapshot(f"frozen_champ_cards:{race_key}", db_path) or {}
    snap.pop("fetched_at", None)
    cards = snap.get("cards") or {}
    errors, i, t0 = [], start, time.monotonic()
    while i < len(keys):
        if i > start and time.monotonic() - t0 > budget:
            break
        cid, b = keys[i]
        try:
            card = db.fetch_champ_player_card(race_key, cid, max_age=0, db_path=db_path,
                                              board_label=b, live=True)
        except Exception as exc:
            card = {"error": repr(exc)}
        if card.get("holes") and not card.get("stale"):
            cards[f"{cid}|{b or ''}|"] = card
        else:
            errors.append({"customer_id": cid, "board": b,
                           "why": card.get("error") or ("stale" if card.get("stale") else "no holes")})
        i += 1
    db.save_gg_snapshot(f"frozen_champ_cards:{race_key}", {"cards": cards}, db_path)
    return {"race": race_key, "total": len(keys), "done": i, "cards": len(cards),
            "next": i if i < len(keys) else None, "errors": errors}
