"""Publish entered scores into the scoring record (G-0 keystone).

Ruling (Kerry, CA mailbox #786 GO 1), verbatim: "When a group's card is
CLOSED AND SIGNED, copy the gross scores into scoring_rounds/scoring_holes
with source='entry' (customer_id, course, tee, slope, rating, 9 or 18). A
GG import may never double it; if both sources exist for one event, keep
both and diff them (that IS the G2a/G2b parity check on 9/29 and 10/6).
Kerry's D22/D23 (off GG after the cup) already authorizes entered scores as
the record. No new table."

WHY. Every downstream computation -- handicap posting
(derive_handicap_rounds_from_scoring, derive_18hole_rounds_as_two_nines),
the Games-tab winners and record_event_game_payouts, MVP, points, closeout,
the scorecard pages -- reads scoring_rounds / scoring_holes, which until now
only the Golf Genius import filled. Off GG those would all go empty.

HOW "KEEP BOTH" IS HONOURED. About a hundred readers of scoring_rounds do
not filter on `source`, so an entry row may NEVER sit beside a GG row for
the same event and player or every reader double counts. So:

  AUTHORITATIVE MODE -- the event has no GG scoring_rounds rows (any source
    other than 'entry') AND its date is on/after the cutover app setting
    `entry_record_from` (default 2026-10-10, the Lone Star Cup). Eligible
    players are written to scoring_rounds (source='entry',
    gg_aggregate_id='entry:<score-entry round id>') and scoring_holes.
    Re-publishing upserts in place; nothing is ever duplicated.

  SHADOW MODE -- the event has GG rows, or it is before the cutover. Nothing
    is written to scoring_rounds. The entered scores stay where score entry
    keeps them and the GG rows stay in scoring_rounds; `entry_parity`
    returns the per-player, per-hole diff between them (the 9/29 and 10/6
    parity check).

  And the other direction: import_gg_scorecards refuses to write rows into
    an event that already has source='entry' rows (database.py, the G-0
    gate), so a GG import can never double an entered record.

Entered scores are read ONLY through score_entry.get_entered_scores (the
score-entry tables belong to email_parser/score_entry.py alone; the guard
in test_score_entry.py fails otherwise).

ELIGIBILITY (one function, `publish_eligibility`): a player is published
only when (a) the round is closed OR his group's card has been submitted
(a card check exists), AND (b) he holds a live (non-voided) 'player'
signature -- his own or the scorekeeper's on his behalf, AND (c) his own
card is complete: every hole of the round carries a gross. Anyone else is
returned as `held` with the reason and never written.

Portable SQL (CA #682): explicit SELECT then UPDATE / INSERT, RETURNING on
inserts, lower() on both sides of case-insensitive comparisons, no new
table, no DDL.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from email_parser import database as db
from email_parser import score_entry as se

logger = logging.getLogger(__name__)

CUTOVER_SETTING = "entry_record_from"
CUTOVER_DEFAULT = "2026-10-10"
ENTRY_SOURCE = "entry"
AGG_PREFIX = "entry:"


def _now_utc() -> str:
    # Same shape as SQLite's datetime('now') so imported_at stays comparable
    # with the GG rows (the money hold settles from it).
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _agg_id(round_id: int) -> str:
    return f"{AGG_PREFIX}{int(round_id)}"


def cutover_date(db_path=None) -> str:
    try:
        v = (db.get_app_setting(CUTOVER_SETTING, db_path) or "").strip()
    except Exception:
        v = ""
    return v[:10] or CUTOVER_DEFAULT


# ---------------------------------------------------------------------------
# Eligibility: the ONE place the "closed and signed" rule lives.
# ---------------------------------------------------------------------------

def _round_holes(rnd: dict) -> list[int]:
    """The holes a complete card must carry. Mirrors score_entry._player_card:
    the round's own hole list; with no hole list, the round's hole count."""
    holes = [int(h["hole"]) for h in (rnd.get("course") or [])]
    return sorted(holes)


def publish_eligibility(rnd: dict, player: dict) -> tuple[bool, str | None]:
    """(eligible, reason_if_held) for one player of one round, from the
    get_entered_scores read. Change the rule here and only here."""
    cid = player.get("customer_id")
    if not cid:
        return False, "no customer_id"
    submitted = any(c.get("group_id") == player.get("group_id")
                    for c in (rnd.get("card_checks") or []))
    if rnd.get("status") != "closed" and not submitted:
        return False, "round still open and the group's card has not been submitted"
    signed = any(s.get("customer_id") == cid and s.get("kind") == "player"
                 for s in (rnd.get("signoffs") or []))
    if not signed:
        return False, "card not signed (no live player signature)"
    scores = player.get("scores") or {}
    holes = _round_holes(rnd)
    if holes:
        missing = [h for h in holes if scores.get(str(h)) is None]
        if missing:
            return False, f"card incomplete: no gross on hole(s) {missing}"
    elif len([v for v in scores.values() if v is not None]) != int(rnd.get("holes") or 0):
        return False, (f"card incomplete: {len(scores)} of {rnd.get('holes')} holes "
                       "(no hole list on the round)")
    return True, None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(conn, event_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return dict(r) if r else None


def _gg_rows(conn, event_id: int) -> list[dict]:
    """Every non-entry scoring_rounds row on the event (GG, NULL, or a GG
    history tag): any of them makes the event a shadow event."""
    return [dict(r) for r in conn.execute(
        "SELECT id, customer_id, player_name, round_date, holes_played, gross, source "
        "FROM scoring_rounds WHERE event_id = ? "
        "AND lower(COALESCE(source, 'gg')) <> lower(?) ORDER BY id",
        (event_id, ENTRY_SOURCE)).fetchall()]


def _mode(conn, ev: dict, db_path=None) -> tuple[str, str]:
    gg = _gg_rows(conn, ev["id"])
    cut = cutover_date(db_path)
    ev_date = str(ev.get("event_date") or "")[:10]
    if gg:
        return "shadow", f"the event has {len(gg)} Golf Genius scoring row(s); entered scores are diffed, not written"
    if not ev_date:
        return "shadow", "the event has no date, so the cutover cannot be checked"
    if ev_date < cut:
        return "shadow", f"event date {ev_date} is before the entry-record cutover {cut}"
    return "authoritative", f"no Golf Genius rows and event date {ev_date} >= cutover {cut}"


def _customer_names(conn, cids: list[int]) -> dict:
    if not cids:
        return {}
    cols = {r[1] for r in conn.execute("PRAGMA table_info(customers)").fetchall()}
    sel = "customer_id, first_name, last_name" + (", suffix" if "suffix" in cols else "")
    ph = ",".join("?" * len(cids))
    out = {}
    for r in conn.execute(f"SELECT {sel} FROM customers WHERE customer_id IN ({ph})",
                          tuple(cids)).fetchall():
        parts = [(r["first_name"] or "").strip(), (r["last_name"] or "").strip()]
        if "suffix" in cols and (r["suffix"] or "").strip():
            parts.append(r["suffix"].strip())
        nm = " ".join(p for p in parts if p)
        if nm:
            out[r["customer_id"]] = nm
    return out


def _played_side(rnd: dict, ev: dict) -> str:
    holes = _round_holes(rnd)
    if holes and min(holes) >= 10:
        return "back"
    if (ev.get("nine_side") or "").strip().lower() == "back" and not any(h >= 10 for h in holes):
        return "back"          # a named nine numbered 1-9 played as the back
    return "front"


def _resolve_tee(conn, ev: dict, course_id, tee_value, is18: bool, side: str) -> dict:
    """{tee_id, how, note} for the player's `tee` (a TGF band like '50-64'
    or a tee name). REUSES database.event_tee_legend -- the ONE band->tee
    mapping the starter sheet, print pack and score-entry phone use -- for
    bands, and picks the concrete course_tees row the way the starter
    sheet's _event_tee_rows does (same master-name match via _gg_tee_parts;
    18 holes prefer the legend's own tee row; a nine needs the row
    labelled for the side played). Never guesses: an ambiguous or missing
    row returns tee_id None with the reason."""
    val = " ".join(str(tee_value or "").split())
    if not course_id:
        return {"tee_id": None, "how": None, "note": "no course on the round or the event"}
    if not val:
        return {"tee_id": None, "how": None, "note": "player has no tee on the card"}
    band = next((b for b in db.TEE_BANDS if b.lower() == val.lower()), None)
    want_id, ladies = None, None
    if band:
        legend = db.event_tee_legend(conn, ev.get("id"), {**ev, "course_id": course_id})
        entry = next((t for t in legend if t.get("band") == band), None)
        if not entry:
            return {"tee_id": None, "how": "band",
                    "note": f"band {band} has no tee on this course's legend"}
        want = db._gg_tee_parts(entry.get("tee_key") or entry.get("tee_name"))["master"].lower()
        want_id = entry.get("tee_id")
        ladies = bool(entry.get("ladies")) or band == "Forward"
        unmarked = False
        how = "band"
    else:
        parts = db._gg_tee_parts(val)
        want = parts["master"].lower()
        # A bare name ("Red") carries no gender mark, and _gg_tee_parts
        # reads unmarked as M. Only an explicit mark ("Red (L)") pins the
        # women's rows; an unmarked name prefers the men's rows but may
        # fall back to any row of that name below (3309: DelCarmen,
        # McCormick and Wade on "Red", whose only nine-hole Red rows are
        # the women's 557 / 2894; the men's Red row is 18 holes).
        explicit_f = bool(re.search(r"\((?:l|f|lady|ladies)\)|\bladies\b", val, re.I))
        ladies = True if explicit_f else False
        unmarked = not explicit_f
        how = "name"
    rows = [dict(r) for r in conn.execute(
        "SELECT tee_id, tee_name, gg_alias, gender, holes, nine, slope, rating "
        "FROM course_tees WHERE course_id = ? ORDER BY tee_id", (course_id,)).fetchall()]

    def _label(nm):
        return db._gg_tee_parts(nm)["master"].lower() if nm else ""

    named = [r for r in rows if _label(r["tee_name"]) == want or _label(r.get("gg_alias")) == want]
    all_named = named
    if ladies is not None:
        g = [r for r in named if (r.get("gender") == "F") == bool(ladies)]
        named = g or named

    def _is18(r):
        if r.get("rating") is not None:
            return r["rating"] >= 50
        return (r.get("holes") or 18) == 18

    cands = [r for r in named if _is18(r) == is18]
    if not cands and how == "name" and unmarked:
        # The preferred gender has no row of this length: take the
        # other gender's row of that name rather than drop the rating.
        named = all_named
        cands = [r for r in named if _is18(r) == is18]
    if not cands:
        if not named:
            return {"tee_id": None, "how": how, "note": f"no tee named {want!r} on the course"}
        return {"tee_id": None, "how": how,
                "note": (f"tee {want!r} has no {'18' if is18 else 'nine'}-hole row on the "
                         "course record (handicap posting will skip the round)")}
    if is18:
        pick = next((r for r in cands if r["tee_id"] == want_id), cands[0])
        return {"tee_id": pick["tee_id"], "how": how, "note": None}
    exact = [r for r in cands if (r.get("nine") or "") in (side, "both")]
    if len(exact) == 1:
        return {"tee_id": exact[0]["tee_id"], "how": how, "note": None}
    if len(exact) > 1:
        used = {r[0]: r[1] for r in conn.execute(
            "SELECT tee_id, COUNT(*) FROM scoring_rounds WHERE course_id = ? "
            "AND tee_id IS NOT NULL GROUP BY tee_id", (course_id,)).fetchall()}
        pick = sorted(exact, key=lambda r: (-(used.get(r["tee_id"], 0)), r["tee_id"]))[0]
        return {"tee_id": pick["tee_id"], "how": how, "note": None}
    if len(cands) == 1 and not cands[0].get("nine"):
        return {"tee_id": cands[0]["tee_id"], "how": how, "note": None}
    return {"tee_id": None, "how": how,
            "note": f"tee {want!r}: the course record does not say which nine row is the {side}"}



def _derived_dots(conn, rnd: dict, tee_id, ph, use_holes: list) -> dict:
    """{hole: strokes_received} for an entered card: the playing handicap
    allocated by stroke index under the RULED mode (Kerry, CA #771: a nine
    collapses its stroke indexes to 1-9, an 18 uses the full card) —
    `handicap_calc.ruled_allocation_mode`, the same call the game engine
    makes. Stroke index comes from the resolved tee's holes, else from the
    round's own card. No playing handicap or no stroke index -> {} (zeros),
    reported by the caller, never guessed.

    Before this (CA #865/#866/#868) every entered hole was written with
    strokes_received 0, so every reader that trusts stored pops (the
    handicap net-double-bogey cap, get_scorecard / MVP Stableford, the
    leaderboard) read net = gross."""
    if ph is None:
        return {}
    si = {}
    if tee_id:
        try:
            for h in db._ls_tee_holes(conn, tee_id):
                if h.get("stroke_index"):
                    si[int(h["hole_number"])] = int(h["stroke_index"])
        except Exception:
            si = {}
    if not all(h in si for h in use_holes):
        si = {int(h["hole"]): int(h["stroke_index"]) for h in (rnd.get("course") or [])
              if h.get("stroke_index")}
    si = {h: si[h] for h in use_holes if h in si}
    if len(si) != len(use_holes):
        return {}
    from email_parser.handicap_calc import allocate_strokes, ruled_allocation_mode
    return allocate_strokes(int(round(ph)), si, mode=ruled_allocation_mode("ruled", si))


def _existing_entry_row(conn, agg: str, cid: int):
    return conn.execute(
        "SELECT id, gross, holes_played, net, tee_id FROM scoring_rounds "
        "WHERE gg_aggregate_id = ? AND customer_id = ?", (agg, cid)).fetchone()


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

def _is_preview(rnd: dict) -> bool:
    """A PREVIEW (test) round is never published or diffed. score_entry
    labels them PREVIEW_LABEL, or PREVIEW_LABEL + " · 18 holes" when the
    hole count differs from the event's, so match the PREFIX, the same way
    score_entry itself does (an exact match let the 18-hole previews on
    s9.25 through as "would write", caught live 2026-09-28)."""
    lbl = getattr(se, "PREVIEW_LABEL", None)
    return bool(lbl) and (rnd.get("label") or "").startswith(lbl)


def _publish_round(conn, ev: dict, rnd: dict, mode: str, apply: bool, db_path=None) -> dict:
    rid = rnd["round_id"]
    agg = _agg_id(rid)
    write = bool(apply and mode == "authoritative")
    key = "written" if write else "would_write"
    out = {"round_id": rid, "label": rnd.get("label"), "date": rnd.get("date"),
           "holes": rnd.get("holes"), "status": rnd.get("status"),
           key: [], "held": [], "tee_unresolved": [], "stale": [], "tees": {}}
    if _is_preview(rnd):
        out["held"] = [{"customer_id": p.get("customer_id"), "name": p.get("name"),
                        "reason": "preview (test) round, never published"}
                       for p in rnd.get("players") or []]
        return out
    course_id = rnd.get("course_id") or ev.get("course_id")
    is18 = int(rnd.get("holes") or 9) == 18
    side = _played_side(rnd, ev)
    round_date = str(rnd.get("date") or ev.get("event_date") or "")[:10] or None
    names = _customer_names(conn, [p["customer_id"] for p in rnd.get("players") or []
                                   if p.get("customer_id")])
    holes = _round_holes(rnd)
    changed_any = False
    for p in rnd.get("players") or []:
        cid = p.get("customer_id")
        ok, why = publish_eligibility(rnd, p)
        name = names.get(cid) or (p.get("name") or "").strip() or f"customer {cid}"
        if ok and cid and round_date:
            # An UNLINKED GG card (event_id NULL) for this player on this
            # date would double him in every date-keyed reader.
            unl = conn.execute(
                "SELECT id FROM scoring_rounds WHERE customer_id = ? AND event_id IS NULL "
                "AND round_date = ? AND lower(COALESCE(source, 'gg')) <> lower(?) LIMIT 1",
                (cid, round_date, ENTRY_SOURCE)).fetchone()
            if unl:
                ok, why = False, (f"an unlinked Golf Genius card (scoring round {unl[0]}) "
                                  "exists for him on this date; link or remove it first")
        # Every player's tee is resolved, held or not, so a lane can prove the
        # tees BEFORE the round is played (Track A, 3304 on 9/28). Read-only.
        tee = _resolve_tee(conn, ev, course_id, p.get("tee"), is18, side)
        out["tees"].setdefault(str(p.get("tee")), {"tee_id": tee["tee_id"], "players": 0,
                                                   **({"why": tee["note"]} if tee["tee_id"] is None else {})})
        out["tees"][str(p.get("tee"))]["players"] += 1
        if tee["tee_id"] is None:
            out["tee_unresolved"].append({"customer_id": cid, "name": name,
                                          "tee": p.get("tee"), "why": tee["note"]})
        if not ok:
            out["held"].append({"customer_id": cid, "name": name, "reason": why})
            prev = _existing_entry_row(conn, agg, cid) if cid else None
            if prev:
                out["stale"].append({"customer_id": cid, "name": name,
                                     "scoring_round_id": prev["id"],
                                     "published_gross": prev["gross"],
                                     "note": "published earlier; now held, left as is"})
            continue
        scores = {int(h): int(v) for h, v in (p.get("scores") or {}).items() if v is not None}
        use_holes = holes or sorted(scores)
        gross = sum(scores[h] for h in use_holes)
        ph = p.get("playing_handicap")
        net = (gross - ph) if ph is not None else None
        dots = _derived_dots(conn, rnd, tee["tee_id"], ph, use_holes)
        if ph and not dots:
            out.setdefault("dots_unresolved", []).append(
                {"customer_id": cid, "name": name,
                 "why": "no stroke index for every hole played; pops written as 0"})
        row = {"customer_id": cid, "player_name": name, "event_id": ev["id"],
               "round_date": round_date, "course_id": course_id, "tee_id": tee["tee_id"],
               "tee": p.get("tee"), "holes_played": len(use_holes),
               "playing_handicap": ph, "gross": gross, "net": net,
               "holes": {str(h): scores[h] for h in use_holes},
               "strokes_received": {str(h): int(dots.get(h, 0) or 0) for h in use_holes}}
        prev = _existing_entry_row(conn, agg, cid)
        row["action"] = "update" if prev else "insert"
        if write:
            changed = (not prev or prev["gross"] != gross
                       or (prev["holes_played"] or 0) != len(use_holes)
                       or prev["net"] != net or prev["tee_id"] != tee["tee_id"])
            if prev and not changed:
                had = {r[0]: r[1] or 0 for r in conn.execute(
                    "SELECT hole_number, strokes_received FROM scoring_holes "
                    "WHERE scoring_round_id = ?", (prev["id"],)).fetchall()}
                changed = any(had.get(h, 0) != int(dots.get(h, 0) or 0) for h in use_holes)
            if prev:
                srid = prev["id"]
                conn.execute(
                    "UPDATE scoring_rounds SET customer_id = ?, player_name = ?, event_id = ?, "
                    "round_date = ?, course_id = ?, tee_id = ?, holes_played = ?, "
                    "playing_handicap = ?, gross = ?, net = ?, source = ? WHERE id = ?",
                    (cid, name, ev["id"], round_date, course_id, tee["tee_id"],
                     len(use_holes), ph, gross, net, ENTRY_SOURCE, srid))
                if changed:
                    conn.execute("UPDATE scoring_rounds SET imported_at = ? WHERE id = ?",
                                 (_now_utc(), srid))
            else:
                srid = conn.execute(
                    "INSERT INTO scoring_rounds (customer_id, player_name, event_id, "
                    "gg_aggregate_id, round_date, course_id, tee_id, holes_played, "
                    "playing_handicap, gross, net, source, imported_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
                    (cid, name, ev["id"], agg, round_date, course_id, tee["tee_id"],
                     len(use_holes), ph, gross, net, ENTRY_SOURCE, _now_utc())).fetchone()[0]
            # Holes: strokes = gross; strokes_received = the DERIVED dots
            # (_derived_dots), so readers that trust stored pops get the
            # same net as the game engine.
            conn.execute("DELETE FROM scoring_holes WHERE scoring_round_id = ?", (srid,))
            for h in use_holes:
                conn.execute(
                    "INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, "
                    "strokes_received) VALUES (?,?,?,?)",
                    (srid, h, scores[h], int(dots.get(h, 0) or 0)))
            row["scoring_round_id"] = srid
            changed_any = changed_any or changed
        out[key].append(row)
    # A player published earlier who is no longer on the round.
    on_round = {p.get("customer_id") for p in rnd.get("players") or []}
    for r in conn.execute("SELECT id, customer_id, player_name, gross FROM scoring_rounds "
                          "WHERE gg_aggregate_id = ?", (agg,)).fetchall():
        if r["customer_id"] not in on_round:
            out["stale"].append({"customer_id": r["customer_id"], "name": r["player_name"],
                                 "scoring_round_id": r["id"], "published_gross": r["gross"],
                                 "note": "published earlier; no longer on the round, left as is"})
    out["_changed"] = changed_any
    return out


def publish_entered_round(round_id: int | None = None, event_id: int | None = None,
                          apply: bool = False, db_path=None) -> dict:
    """Publish one score-entry round (or, with only event_id, every round of
    the event). Dry run by default: returns the mode, what would be written,
    who is held and why, unresolved tees, and in shadow mode the parity
    diff. apply=True writes only in authoritative mode."""
    if round_id is None:
        if event_id is None:
            return {"error": "round_id or event_id is required"}
        return publish_event(event_id, apply=apply, db_path=db_path)
    ev_id = se.round_event_id(int(round_id), db_path=db_path)
    if ev_id is None:
        return {"error": f"no score-entry round {round_id}"}
    if event_id is not None and int(event_id) != ev_id:
        return {"error": f"round {round_id} belongs to event {ev_id}, not {event_id}"}
    return _publish(ev_id, int(round_id), apply, db_path)


def publish_event(event_id: int, apply: bool = False, db_path=None) -> dict:
    return _publish(int(event_id), None, apply, db_path)


def _publish(event_id: int, round_id, apply: bool, db_path) -> dict:
    read = se.get_entered_scores(event_id, round_id=round_id, db_path=db_path)
    with db._connect(db_path) as conn:
        db._ensure_scoring_tables(conn)
        ev = _event(conn, event_id)
        if not ev:
            return {"error": f"no event {event_id}"}
        mode, mode_why = _mode(conn, ev, db_path)
        rounds = [_publish_round(conn, ev, r, mode, apply, db_path)
                  for r in read.get("rounds") or []]
        if apply and mode == "authoritative":
            conn.commit()
        else:
            conn.rollback()
    changed = any(r.pop("_changed", False) for r in rounds)
    out = {"event_id": event_id, "event": ev.get("item_name"),
           "event_date": ev.get("event_date"), "mode": mode, "mode_reason": mode_why,
           "cutover": cutover_date(db_path), "applied": bool(apply and mode == "authoritative"),
           "dry_run": not apply, "rounds": rounds}
    if not read.get("rounds"):
        out["note"] = "no score-entry rounds on this event"
    if mode == "shadow":
        if apply:
            out["note"] = "shadow mode: nothing written to scoring_rounds (see parity)"
        out["parity"] = entry_parity(event_id, db_path=db_path, _read=read)
    key = "written" if out["applied"] else "would_write"
    out["summary"] = {
        "players_" + key: sum(len(r.get(key) or []) for r in rounds),
        "held": sum(len(r["held"]) for r in rounds),
        "tee_unresolved": sum(len(r["tee_unresolved"]) for r in rounds),
        "stale": sum(len(r["stale"]) for r in rounds),
        "dots_unresolved": sum(len(r.get("dots_unresolved") or []) for r in rounds)}
    if out["applied"] and changed and ev.get("item_name"):
        # Same follow-on the GG import runs when scores land: refresh the
        # self-computed MVP badges for the event. Never fatal.
        try:
            db.recompute_computed_mvps(ev["item_name"], db_path=db_path)
        except Exception:
            logger.warning("MVP recompute after entry publish failed", exc_info=True)
    return out


# ---------------------------------------------------------------------------
# Parity: entered gross vs the GG scorecards for the same event
# ---------------------------------------------------------------------------

def entry_parity(event_id: int, db_path=None, _read: dict | None = None) -> dict:
    """Per player (matched by customer_id), per hole: entered gross vs the
    Golf Genius scoring_holes on the same event. Players on one side only,
    holes that differ, and totals. Read-only. Every entered player is
    compared, eligible or not (`eligible` says which)."""
    read = _read or se.get_entered_scores(int(event_id), db_path=db_path)
    with db._connect(db_path) as conn:
        db._ensure_scoring_tables(conn)
        gg = _gg_rows(conn, int(event_id))
        gg_holes = {}
        for r in gg:
            gg_holes[r["id"]] = {h[0]: h[1] for h in conn.execute(
                "SELECT hole_number, strokes FROM scoring_holes WHERE scoring_round_id = ?",
                (r["id"],)).fetchall()}
    rounds_out = []
    tot = {"players_compared": 0, "players_matching": 0, "players_differing": 0,
           "holes_differing": 0, "only_entered": 0, "only_gg": 0}
    rounds = read.get("rounds") or []
    for rnd in rounds:
        if _is_preview(rnd):
            continue
        rdate = str(rnd.get("date") or "")[:10]
        pool = [r for r in gg if str(r.get("round_date") or "")[:10] == rdate] if rdate else []
        if not pool and len(rounds) == 1:
            pool = gg                  # one round on the event: its GG cards, whatever the date stamp
        by_cid = {}
        for r in pool:
            if r["customer_id"]:
                by_cid.setdefault(r["customer_id"], r)
        entered = {p["customer_id"]: p for p in rnd.get("players") or []
                   if p.get("customer_id") and p.get("scores")}
        compared, only_e, only_g = [], [], []
        for cid, p in entered.items():
            ok, why = publish_eligibility(rnd, p)
            g = by_cid.get(cid)
            e_sc = {int(h): v for h, v in p["scores"].items() if v is not None}
            if not g:
                only_e.append({"customer_id": cid, "name": p.get("name"),
                               "entered_total": sum(e_sc.values()), "eligible": ok})
                continue
            g_sc = {h: v for h, v in gg_holes.get(g["id"], {}).items() if v is not None}
            diff = [{"hole": h, "entered": e_sc.get(h), "gg": g_sc.get(h)}
                    for h in sorted(set(e_sc) | set(g_sc)) if e_sc.get(h) != g_sc.get(h)]
            row = {"customer_id": cid, "name": p.get("name"), "gg_player_name": g["player_name"],
                   "scoring_round_id": g["id"], "eligible": ok, "held_reason": why,
                   "entered_total": sum(e_sc.values()), "gg_total": sum(g_sc.values()),
                   "gg_gross": g.get("gross"), "holes_differ": diff, "match": not diff}
            compared.append(row)
            tot["players_compared"] += 1
            tot["players_matching" if not diff else "players_differing"] += 1
            tot["holes_differing"] += len(diff)
        for cid, g in by_cid.items():
            if cid not in entered:
                only_g.append({"customer_id": cid, "name": g["player_name"],
                               "scoring_round_id": g["id"], "gg_gross": g.get("gross")})
        unlinked_gg = [{"scoring_round_id": r["id"], "name": r["player_name"]}
                       for r in pool if not r["customer_id"]]
        tot["only_entered"] += len(only_e)
        tot["only_gg"] += len(only_g)
        rounds_out.append({"round_id": rnd["round_id"], "date": rdate or None,
                           "label": rnd.get("label"), "players": compared,
                           "only_entered": only_e, "only_gg": only_g,
                           "gg_rows_without_customer_id": unlinked_gg})
    return {"event_id": int(event_id), "gg_rows": len(gg), "rounds": rounds_out,
            "summary": tot,
            "note": (None if gg else "no Golf Genius rows on this event: nothing to diff")}
