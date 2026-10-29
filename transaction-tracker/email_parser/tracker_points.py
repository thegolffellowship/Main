"""TRACKER POINTS STANDINGS — the Fall races and Monthly without Golf Genius.

Kerry 2026-10-13: "Can we generate points on our side first for last
Tuesday? ... I want to make sure we're calculating them correctly." Then,
after the blind test matched Golf Genius on 33 of 35 players (the one
difference his ruling: "Yes, 54 is right for Baker"): "we're not running
Golf Genius at all tonight, so I'm relying on you and what we've built to
make it all happen now."

Where each line comes from
  * BEFORE the cutover (2026-10-06): Golf Genius's own per-event lines,
    frozen in `data/points_baseline/fall_2026_gg_through_0929.json`
    (captured read-only 10/13, effective 9/30). Past events are frozen.
  * RULED events (`ruled_events.json`): events whose cards are GG imports
    carrying GG's playing handicap; the Tracker computed them and Kerry
    ruled the numbers (10/6).
  * Every later event: the engine on the event's published entered cards
    (`event_engine_state` + `live_scoring.build_cards`) — net Stableford,
    floored at 0, the plus off the round once; an 18 makes two entries
    (front, back) per `points_by_nine`.

Who and where
  * Members only: a 1st Timer or a guest earns no race points (Golf
    Genius awarded none to Mark Parker, a 1st Timer, on 10/6).
  * A line goes to the Fall race of the player's HOME chapter (GG credited
    s18.10 to Austin players' Austin race and a18.5 to Mazanec's San
    Antonio race); no home chapter -> the event's chapter.
  * Best N per the race (`best_n`); a CHAMPIONSHIP line always counts.

Nothing here talks to Golf Genius. `rebuild` writes the race rows into
`gg_points_standings` in the shape Golf Genius did, so every board,
projection and Spotlight reads them unchanged; it runs only while app
setting `points_source` = "tracker".
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent / "data" / "points_baseline"
FALL_FILE = BASE_DIR / "fall_2026_gg_through_0929.json"
RULED_FILE = BASE_DIR / "ruled_events.json"
SOURCE_SETTING = "points_source"
TRACKER_RACES = ("san_antonio_fall_net", "austin_fall_net")
EVENT_CODE_RE = re.compile(r"^\s*([sa])(9|18)\.(\d+)\b", re.I)
_MONTHLY_ACTIVE = {3, 4, 5, 6, 7, 9, 10}


def tracker_source_on(db_path=None) -> bool:
    try:
        from .database import get_app_setting
        return (get_app_setting(SOURCE_SETTING, db_path=db_path) or "").strip().lower() == "tracker"
    except Exception:
        return False


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def cutover() -> str:
    return _load(FALL_FILE).get("cutover") or "2026-10-06"


def _non_member(status) -> bool:
    s = (status or "").strip().lower()
    return s in ("first_timer", "1st_timer") or "guest" in s


def _person(conn, cid) -> dict:
    r = conn.execute("SELECT first_name, last_name, chapter, current_player_status "
                     "FROM customers WHERE customer_id = ?", (cid,)).fetchone()
    if not r:
        return {}
    first, last = (r["first_name"] or "").strip(), (r["last_name"] or "").strip()
    return {"name": f"{last.upper()}, {first}".strip(", ") if last else first,
            "chapter": (r["chapter"] or "").strip(),
            "status": r["current_player_status"]}


def _home_chapter(conn, cid, fallback: str) -> str:
    try:
        from .home_chapter import home_chapter_id_of
        hid = home_chapter_id_of(conn, cid)
        if hid:
            row = conn.execute("SELECT name FROM chapters WHERE chapter_id = ?", (hid,)).fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    p = _person(conn, cid)
    return p.get("chapter") or fallback


HELD_PREFIX = "HELD "


def held_events(warnings: list) -> list:
    """The warnings that hold the points (engine vs card mismatch)."""
    return [w for w in warnings or [] if str(w).startswith(HELD_PREFIX)]


def event_lines(db_path=None, through: str | None = None,
                since: str | None = None) -> tuple[list, list]:
    """Every Tracker points line from the cutover on: [{customer_id,
    player_name, chapter (race chapter), date, event_id, code, nine,
    points, member}] plus warnings. Read-only."""
    from . import database as db
    from . import live_scoring as ls
    from .timezone_utils import today_central_str
    ruled = (_load(RULED_FILE).get("events") or {})
    lines, warnings = [], []
    upto = through or today_central_str()
    with db._connect(db_path) as conn:
        evs = [dict(r) for r in conn.execute(
            "SELECT id, item_name, event_date, chapter FROM events "
            "WHERE event_date >= ? AND event_date <= ? AND event_date > ? "
            "AND lower(COALESCE(status, 'active')) NOT IN ('cancelled', 'canceled') "
            "ORDER BY event_date, id", (cutover(), upto, since or "")).fetchall()]
    for ev in evs:
        m = EVENT_CODE_RE.match(ev["item_name"] or "")
        if not m:
            continue                      # not a chapter points event (Cup, etc.)
        code = f"{m.group(1).lower()}{m.group(2)}.{m.group(3)}"
        ev_chapter = ev.get("chapter") or ("San Antonio" if m.group(1).lower() == "s" else "Austin")
        raw: list = []
        live = False
        r = ruled.get(str(ev["id"]))
        if r:
            for cid, pts in (r.get("points") or {}).items():
                raw.append((int(cid), None, float(pts)))
        else:
            with db._connect(db_path) as conn:
                srcs = {x[0] for x in conn.execute(
                    "SELECT DISTINCT COALESCE(source, 'gg') FROM scoring_rounds "
                    "WHERE event_id = ?", (ev["id"],)).fetchall()}
            if not srcs:
                # LIVE (Kerry 10/28: "Shouldn't we know the points standings
                # updates during the event too? Live? So when the last score
                # is entered we already know the winners"): today's entered
                # event, not published yet, scores from the strokes saved so
                # far. Lines carry live=True; season races use them only at a
                # finale (#2462-F), Monthly at every event (#2466-F).
                lv = _live_lines(ev, db_path)
                if lv is None:
                    continue              # not published yet, not live
                raw, live = lv, True
            elif srcs != {"entry"}:
                warnings.append(f"{ev['item_name']}: cards from {sorted(srcs)} — only published "
                                f"entered cards (or a ruled event) score points; skipped")
                continue
        if not r and not live:
            st = db.event_engine_state(ev["item_name"], db_path=db_path)
            if st.get("error"):
                warnings.append(f"{ev['item_name']}: {st['error']}")
                continue
            # No points from an event whose engine and saved cards disagree
            # (Kerry 10/14, after s9.27). The event is left out and the
            # rebuild refuses to apply until it is fixed (HELD_PREFIX).
            from .card_parity import engine_card_parity, blocking_reason
            held = blocking_reason(engine_card_parity(ev["id"], db_path=db_path, state=st))
            if held:
                warnings.append(f"{HELD_PREFIX}{ev['item_name']}: {held}")
                continue
            formulas = (db.get_championship_formulas(db_path=db_path)
                        if st["meta"].get("championship") else db.get_scoring_formulas(db_path))
            for c in ls.build_cards(st, formulas):
                if not c.get("customer_id"):
                    warnings.append(f"{ev['item_name']}: {c.get('name')} has no customer_id — no points")
                    continue
                if c.get("incomplete_round"):
                    # A SHORT ROUND (late arrival, WD; Kerry 10/26: "A short
                    # round should still count toward points races"): net
                    # Stableford on the holes he played, zero on the rest.
                    from .score_entry import incomplete_round_plays
                    if not incomplete_round_plays("points"):
                        warnings.append(f"{ev['item_name']}: {c.get('name')} short round — no points "
                                        f"(INCOMPLETE_ROUND_GAMES points is off)")
                        continue
                if not c.get("complete"):
                    warnings.append(f"{ev['item_name']}: {c.get('name')} card not complete — no points")
                    continue
                nines = c.get("points_by_nine")
                if nines:
                    for n in nines:
                        raw.append((int(c["customer_id"]), n["nine"], float(n["points"] or 0)))
                    if c.get("points_plus_adjust"):
                        warnings.append(f"{ev['item_name']}: {c.get('name')} plus on an 18 has no "
                                        f"ruled nine (open with Kerry) — not deducted")
                else:
                    raw.append((int(c["customer_id"]), None, float(c.get("stableford_net") or 0)))
        with db._connect(db_path) as conn:
            for cid, nine, pts in raw:
                p = _person(conn, cid)
                lines.append({
                    "customer_id": cid, "player_name": p.get("name") or str(cid),
                    "chapter": _home_chapter(conn, cid, ev_chapter),
                    "member": not _non_member(p.get("status")),
                    "date": ev["event_date"], "event_id": ev["id"], "code": code,
                    "championship": "championship" in (ev["item_name"] or "").lower(),
                    "live": live,
                    "nine": nine, "points": max(0.0, pts)})
    return lines, warnings


def _live_lines(ev: dict, db_path=None) -> list | None:
    """Points SO FAR for today's entered event that has not published:
    [(customer_id, nine, points)] from the strokes saved on each card (net
    Stableford on the holes played; an 18 by nine). None when the event is
    not live today. Provisional and display-only: nothing is paid off it,
    and the published cards replace it at closeout."""
    from . import database as db
    from . import live_scoring as ls
    from .timezone_utils import today_central_str
    if str(ev.get("event_date") or "")[:10] != today_central_str():
        return None
    try:
        from .score_entry import event_enabled
        if not event_enabled(int(ev["id"]), db_path):
            return None
        st = db.event_engine_state(ev["item_name"], db_path=db_path)
        if st.get("error"):
            return None
        formulas = (db.get_championship_formulas(db_path=db_path)
                    if st["meta"].get("championship") else db.get_scoring_formulas(db_path))
        out = []
        for c in ls.build_cards(st, formulas):
            if not c.get("customer_id") or not c.get("thru"):
                continue
            nines = c.get("points_by_nine")
            if nines:
                for n in nines:
                    if n.get("thru"):
                        out.append((int(c["customer_id"]), n["nine"], float(n["points"] or 0)))
            else:
                out.append((int(c["customer_id"]), None, float(c.get("stableford_net") or 0)))
        return out
    except Exception:
        logger.exception("live points for %s failed (left out)", ev.get("item_name"))
        return None


def _wins(position) -> int:
    return 1 if re.fullmatch(r"T?1", str(position or "").strip(), re.I) else 0


def _rank_labels(values: list) -> list:
    """Competition ranks with T for ties, highest value first."""
    order = sorted(range(len(values)), key=lambda i: -values[i])
    out = [""] * len(values)
    rank, last = 0, object()
    for pos, i in enumerate(order, 1):
        if values[i] != last:
            rank, last = pos, values[i]
        tied = values.count(values[i]) > 1
        out[i] = f"T{rank}" if tied else str(rank)
    return out


def build_race(race_key: str, db_path=None, tracker_lines: list | None = None) -> dict:
    """One Fall race's standings from the frozen GG lines + the Tracker's
    lines. Returns {race_key, rows: [GG-shaped standings rows + lines],
    warnings}. Read-only."""
    from . import database as db
    race = db._GG_POINTS_RACES[race_key]
    best_n = race.get("best_n")
    chapter = race.get("chapter")
    base = (_load(FALL_FILE).get("races") or {}).get(race_key) or {}
    warnings: list = []
    # THE REGULAR SEASON LOCK (Kerry 10/28: "The regular season is over as of
    # yesterday so the current scores (best 6) should be locked. So there's an
    # automatic starting point that won't update"). With a lock, every line up
    # to its date comes from the lock and only later events (the finale) are
    # read, so a rebuild is one event's work.
    lock = season_lock(race_key, db_path=db_path)
    if tracker_lines is None:
        tracker_lines, w = event_lines(db_path=db_path, since=(lock or {}).get("through"))
        warnings += w
    elif lock:
        tracker_lines = [l for l in tracker_lines if str(l.get("date") or "") > lock["through"]]
    # Season races move live only at a finale (Kerry #2462-F: "Regular season
    # events ... would only show post event updates (as opposed to season
    # finales like the City Championships and Fall City Championships which
    # would be real-time"). Monthly keeps every live line (#2466-F).
    tracker_lines = [l for l in tracker_lines if not l.get("live") or l.get("championship")]
    people: dict = {}
    with db._connect(db_path) as conn:
        db._ensure_gg_points_table(conn)
        snap = [dict(r) for r in conn.execute(
            "SELECT player_name, customer_id, member_card_id, merged_from, rank, affiliation "
            "FROM gg_points_standings WHERE race_key = ?", (race_key,)).fetchall()]
        card_cid: dict = {}
        prev_rank: dict = {}
        aff: dict = {}
        for s in snap:
            if s["customer_id"] is not None:
                prev_rank[int(s["customer_id"])] = s["rank"]
                aff[int(s["customer_id"])] = s["affiliation"]
            cards = [s["member_card_id"]]
            try:
                mf = json.loads(s["merged_from"]) if s["merged_from"] else None
                recs = mf.get("records") if isinstance(mf, dict) else mf
                cards += [r.get("member_card_id") for r in recs or []]
            except Exception:
                pass
            for c in cards:
                if c and s["customer_id"] is not None:
                    card_cid[str(c)] = int(s["customer_id"])
        for lp in (lock or {}).get("people") or []:
            key = lp["customer_id"] if lp.get("customer_id") is not None else f"n:{(lp.get('player_name') or '').lower()}"
            people[key] = {"customer_id": lp.get("customer_id"), "player_name": lp.get("player_name"),
                           "cards": list(lp.get("cards") or []),
                           "lines": [dict(l) for l in lp.get("lines") or []]}
        for p in ([] if lock else base.get("players") or []):
            card = str(p.get("member_card_id") or "")
            cid = card_cid.get(card)
            if cid is None:
                try:
                    cid, _how = db._resolve_gg_person(conn, p.get("player_name") or "")
                except Exception:
                    cid = None
            key = cid if cid is not None else f"n:{(p.get('player_name') or '').lower()}"
            person = people.setdefault(key, {"customer_id": cid, "player_name": p.get("player_name"),
                                             "cards": [], "lines": []})
            if card:
                person["cards"].append(card)
            for ln in p.get("lines") or []:
                person["lines"].append({"date": ln["date"], "event": ln.get("event"),
                                        "tournament": ln.get("tournament"),
                                        "position": ln.get("position"),
                                        "points": float(ln.get("points") or 0), "source": "gg"})
    # Tracker lines for this race: members of this race's chapter. A rank
    # per (event, nine) among the race's players — the position column.
    mine = [ln for ln in tracker_lines if ln["member"] and ln["chapter"] == chapter]
    groups: dict = {}
    for ln in mine:
        groups.setdefault((ln["event_id"], ln["nine"]), []).append(ln)
    for (_eid, _nine), grp in groups.items():
        for ln, pos in zip(grp, _rank_labels([g["points"] for g in grp])):
            ln["position"] = pos
    for ln in mine:
        key = ln["customer_id"]
        person = people.setdefault(key, {"customer_id": key, "player_name": ln["player_name"],
                                         "cards": [], "lines": []})
        nine = f" - {ln['nine'].title()}" if ln["nine"] else ""
        person["lines"].append({
            "date": ln["date"], "event": f"TGF {chapter} {ln['date'][:4]}",
            "tournament": f"{ln['code']} POINTS Net{nine} - {race.get('label', '').replace(' 2026', '')} (Tracker)",
            "position": ln["position"], "points": ln["points"], "source": "tracker",
            "championship": ln.get("championship", False)})
    rows = []
    for person in people.values():
        lines = sorted(person["lines"], key=lambda l: (-l["points"], l["date"]))
        champ = [l for l in lines if l.get("championship") or "CHAMPIONSHIP" in (l.get("tournament") or "").upper()]
        rest = [l for l in lines if l not in champ]
        counted = champ + (rest[:best_n] if best_n else rest)
        for l in lines:
            l["counted"] = l in counted
        cid = person["customer_id"]
        rows.append({
            "player_name": person["player_name"], "customer_id": cid,
            "member_card_id": (person["cards"][0] if person["cards"]
                               else (f"c{cid}" if cid is not None else None)),
            "cards": person["cards"],
            "affiliation": (aff.get(cid) if cid is not None else None) or f"TGF {chapter}",
            "tournaments": len(lines), "wins": sum(_wins(l.get("position")) for l in lines),
            "total_points": round(sum(l["points"] for l in counted), 2),
            "prev_rank": prev_rank.get(cid) if cid is not None else None,
            "lines": lines})
    rows.sort(key=lambda r: (-r["total_points"], (r["player_name"] or "").lower()))
    ranks = _rank_labels([r["total_points"] for r in rows])
    top = rows[0]["total_points"] if rows else 0
    for r, rk in zip(rows, ranks):
        r["rank"] = rk
        r["points_behind"] = round(top - r["total_points"], 2) if r["total_points"] != top else None
    return {"race_key": race_key, "rows": rows, "warnings": warnings}


def write_race(race_key: str, built: dict, db_path=None) -> int:
    """Replace one race's rows in gg_points_standings with the Tracker's,
    in the shape Golf Genius's refresh wrote (delete + insert, one commit)."""
    from . import database as db
    rows = built["rows"]
    with db._connect(db_path) as conn:
        db._ensure_gg_points_table(conn)
        conn.execute("DELETE FROM gg_points_standings WHERE race_key = ?", (race_key,))
        conn.executemany(
            """INSERT INTO gg_points_standings
                   (race_key, rank, prev_rank, player_name, customer_id,
                    affiliation, tournaments, wins, total_points,
                    points_behind, member_card_id, merged_from)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(race_key, r["rank"], r["prev_rank"], r["player_name"], r["customer_id"],
              r["affiliation"], r["tournaments"], r["wins"], r["total_points"],
              r["points_behind"], r["member_card_id"],
              json.dumps({"method": "tracker", "records": [{"member_card_id": c} for c in r["cards"]]})
              if len(r["cards"]) > 1 else None) for r in rows])
        conn.commit()
    return len(rows)


def member_detail(race_key: str, card: str, db_path=None) -> dict | None:
    """The row expansion for a Tracker-built row, in the GG table shape the
    page already renders: counted lines, GG's separator sentence, the rest."""
    built = build_race(race_key, db_path=db_path)
    for r in built["rows"]:
        if str(card) == str(r["member_card_id"]) or str(card) in r["cards"]:
            head = ["Event", "Tournament", "Awarded Date", "Position", "Points"]
            fmt = lambda l: [l.get("event") or "", l.get("tournament") or "", l["date"],
                             l.get("position") or "", f"{l['points']:g}"]
            counted = [fmt(l) for l in r["lines"] if l["counted"]]
            rest = [fmt(l) for l in r["lines"] if not l["counted"]]
            table = [head] + counted
            if rest:
                table += [["The following points are not counted in standings"]] + rest
            return {"tables": [table], "headings": [], "source": "tracker"}
    return None


def monthly_best(month_key: str, db_path=None, tracker_lines: list | None = None,
                 cards: dict | None = None) -> dict:
    """One month's Monthly Points `best` dict (TGF-wide, every point in the
    month, members only) for `_monthly_month_entry`."""
    if tracker_lines is None:
        tracker_lines, _ = event_lines(db_path=db_path)
    best: dict = {}
    for ln in tracker_lines:
        if not ln["member"] or not (ln["date"] or "").startswith(month_key):
            continue
        b = best.setdefault(ln["customer_id"], {
            "player_name": ln["player_name"], "customer_id": ln["customer_id"],
            "chapter": ln["chapter"], "rounds": 0, "points": 0.0,
            "member_card_id": (cards or {}).get(ln["customer_id"]), "_events": set()})
        b["points"] = round(b["points"] + ln["points"], 2)
        b["_events"].add(ln["event_id"])
        b["rounds"] = len(b["_events"])
    for b in best.values():
        b.pop("_events", None)
    return best


def rebuild(db_path=None, apply: bool = False) -> dict:
    """Rebuild the Fall races and the Tracker's Monthly months. Dry run by
    default: returns what would be written and the diff against the rows
    there now. `apply` writes (Fall rows + the monthly snapshot)."""
    from . import database as db
    from .timezone_utils import today_central
    lines, warnings = event_lines(db_path=db_path)
    out = {"apply": apply, "races": {}, "monthly": {}, "warnings": warnings,
           "lines": len(lines)}
    held = held_events(warnings)
    if held and apply:
        # Writing standings without a held event would drop its points from
        # every player; keep the standings as they are until it is fixed.
        out["refused"] = held
        apply = False
        out["apply"] = False
    for rk in TRACKER_RACES:
        built = build_race(rk, db_path=db_path, tracker_lines=lines)
        with db._connect(db_path) as conn:
            db._ensure_gg_points_table(conn)
            now = {(r["customer_id"] if r["customer_id"] is not None else r["player_name"]):
                   r["total_points"] for r in conn.execute(
                       "SELECT customer_id, player_name, total_points FROM gg_points_standings "
                       "WHERE race_key = ?", (rk,)).fetchall()}
        changes = []
        for r in built["rows"]:
            k = r["customer_id"] if r["customer_id"] is not None else r["player_name"]
            if now.get(k) != r["total_points"]:
                changes.append({"player": r["player_name"], "customer_id": r["customer_id"],
                                "was": now.get(k), "now": r["total_points"], "rank": r["rank"]})
        out["races"][rk] = {"rows": len(built["rows"]), "changes": changes,
                            "top": [(r["rank"], r["player_name"], r["total_points"])
                                    for r in built["rows"][:8]]}
        if apply:
            write_race(rk, built, db_path=db_path)
    out["monthly"] = rebuild_monthly(db_path=db_path, apply=apply, tracker_lines=lines)
    return out


def rebuild_monthly(db_path=None, apply: bool = False, tracker_lines: list | None = None) -> dict:
    """The Tracker's Monthly months (cutover's month to today) written into
    the monthly_points snapshot beside Golf Genius's earlier months."""
    from . import database as db
    from .timezone_utils import today_central
    lines = tracker_lines
    out: dict = {}
    if lines is None:
        lines, _w = event_lines(db_path=db_path)
        if held_events(_w) and apply:
            out["refused"] = held_events(_w)
            apply = False
    t = today_central()
    start = cutover()[:7]
    keys = []
    y, mth = int(start[:4]), int(start[5:7])
    while (y, mth) <= (t.year, t.month):
        if mth in _MONTHLY_ACTIVE:
            keys.append(f"{y:04d}-{mth:02d}")
        y, mth = (y + 1, 1) if mth == 12 else (y, mth + 1)
    # Each monthly row carries the player's Fall-race card so its row
    # expansion can show the month's points lines (Kerry 10/13: "The event
    # scoring records/points details aren't showing for October").
    cards: dict = {}
    for rk in TRACKER_RACES:
        for r in build_race(rk, db_path=db_path, tracker_lines=lines)["rows"]:
            if r["customer_id"] is not None and r["member_card_id"]:
                cards.setdefault(r["customer_id"], r["member_card_id"])
    snap = db.load_gg_snapshot("monthly_points", db_path) or {"months": [], "errors": []}
    snap.pop("fetched_at", None)
    months = [m for m in snap.get("months") or [] if m.get("month") not in keys]
    with db._connect(db_path) as conn:
        for k in keys:
            entry = db._monthly_month_entry(conn, k, monthly_best(k, tracker_lines=lines,
                                                                  cards=cards))
            entry["source"] = "tracker"
            months.append(entry)
            out[k] = [(s["rank_label"], s["player_name"], s["points"])
                      for s in entry["standings"][:8]]
    months.sort(key=lambda m: m.get("month") or "")
    if apply:
        snap["months"] = months
        db.save_gg_snapshot("monthly_points", snap, db_path)
    return out


def bundle_detail(race_key: str, card: str, db_path=None) -> dict | None:
    """Row expansion for a race the Tracker does not rebuild (the concluded
    City and Players Cup races) while GG intake is off: GG's own per-event
    table for that member card, from the newest captured points ledger on
    the data volume (GO 6). Read-only; None when no capture holds it."""
    from .database import DB_PATH
    base = Path(db_path or DB_PATH).parent / "gg_points_ledger"
    if not base.exists():
        return None
    for d in sorted((x for x in base.iterdir() if x.is_dir()), reverse=True):
        f = d / f"{race_key}.json"
        if not f.exists():
            continue
        try:
            doc = json.loads(f.read_text())
        except Exception:
            continue
        for p in (doc.get("players") or {}).values():
            if str(p.get("member_card_id")) == str(card) and p.get("raw_tables"):
                return {"tables": p["raw_tables"], "headings": p.get("headings") or [],
                        "source": f"gg capture {d.name}"}
    return None



LOCK_KEY = "race_season_lock:{}"


def season_lock(race_key: str, db_path=None) -> dict | None:
    """The race's locked regular season: {through, at, people: [{customer_id,
    player_name, cards, lines}]} or None."""
    from . import database as db
    raw = db.get_app_setting(LOCK_KEY.format(race_key), db_path=db_path)
    if not raw:
        return None
    try:
        d = json.loads(raw)
        return d if d.get("through") else None
    except Exception:
        logger.warning("season lock for %s unreadable; ignored", race_key)
        return None


def lock_season(race_key: str, through: str, apply: bool = False, db_path=None) -> dict:
    """Lock the regular season through `through` (YYYY-MM-DD): every player's
    lines up to that date, as built now. Refuses while any of those events
    is HELD (its points are not settled). Dry run shows the totals."""
    from . import database as db
    from .timezone_utils import now_central
    if race_key not in TRACKER_RACES:
        return {"error": f"{race_key} is not a Tracker race"}
    lines, warnings = event_lines(db_path=db_path, through=through)
    held = held_events(warnings)
    if held:
        return {"error": "events are HELD; their points are not settled", "held": held}
    with db._connect(db_path) as conn:
        cur = conn.execute("SELECT 1 FROM app_settings WHERE key = ?",
                           (LOCK_KEY.format(race_key),)).fetchone()
    if cur and apply:
        db.set_app_setting(LOCK_KEY.format(race_key), "", db_path=db_path)  # rebuild unlocked first
    built = build_race(race_key, db_path=db_path, tracker_lines=lines)
    people = [{"customer_id": r["customer_id"], "player_name": r["player_name"],
               "cards": r.get("cards") or [],
               "lines": [{k: l.get(k) for k in ("date", "event", "tournament", "position",
                                                "points", "source", "championship")}
                         for l in r["lines"]]} for r in built["rows"]]
    out = {"race_key": race_key, "through": through, "apply": apply,
           "players": len(people),
           "top": [(r["rank"], r["player_name"], r["total_points"]) for r in built["rows"][:8]],
           "warnings": warnings}
    if apply:
        db.set_app_setting(LOCK_KEY.format(race_key), json.dumps(
            {"through": through, "at": now_central().strftime("%Y-%m-%d %H:%M"),
             "people": people}), db_path=db_path)
        db.log_agent_action("tracker-points", "season_locked",
                            f"{race_key} locked through {through}: {len(people)} players", db_path=db_path)
    return out


def unlock_season(race_key: str, db_path=None) -> dict:
    from . import database as db
    db.set_app_setting(LOCK_KEY.format(race_key), "", db_path=db_path)
    return {"race_key": race_key, "unlocked": True}



# MONTHLY ADDS IMMEDIATELY (Kerry 10/28: "October is adding all the month so
# it's not throwing any out so whatever points are collected to date are a
# baseline and won't change. So it should be able to add immediately too").
# Lines from events before today are read once and kept (re-read every 30
# minutes in case a past card is corrected); only today's event is re-read,
# so Monthly can rebuild every minute beside the locked races.
_PAST_LINES: dict = {}
PAST_LINES_TTL_SEC = 1800


def fast_lines(db_path=None) -> tuple[list, list]:
    """(lines, warnings) = the cached baseline before today + today's lines."""
    import time
    from datetime import timedelta
    from .timezone_utils import today_central
    today = today_central()
    yday = (today - timedelta(days=1)).isoformat()
    key = (str(db_path), today.isoformat())
    hit = _PAST_LINES.get(key)
    if not hit or time.time() - hit[2] > PAST_LINES_TTL_SEC:
        past, pw = event_lines(db_path=db_path, through=yday)
        _PAST_LINES.clear()
        hit = _PAST_LINES[key] = (past, pw, time.time())
    now_lines, nw = event_lines(db_path=db_path, since=yday)
    return [dict(l) for l in hit[0]] + now_lines, list(hit[1]) + nw
