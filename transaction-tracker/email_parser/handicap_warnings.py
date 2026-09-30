"""MISSING-HANDICAP WARNING (Kerry 2026-09-30, CoS #1064-1 / #1067-3).

Kerry: "There needs to be a warning to the manager that either a handicap
index needs to be entered ... Robert just added them into GG without adding
them to the Tracker and that's why there was a discrepancy."

A roster row for an upcoming event with no TGF index and no manual starting
handicap is MISSING. The warning names the players and, per player, which
case applies and what fixes it:

  new         no rounds on file: ask for their current index and enter 75% of
              it as the starting handicap (the Handicap Standard's intro rule);
  few_rounds  rounds on file but not enough for a TGF index yet: same fix;
  no_identity a Golf Genius RSVP that matches no customer: link or add the
              player first, then set the handicap.

With no index at all the player plays N/H; how N/H plays out in the money
(a blind stands in, #1064/#1067/#1068) is Side Games' build, so the warning
says so and does not pretend it is automatic yet.

ONE computation: the index comes from `_roster_handicap_index_map` (the same
map the ROSTER, PAIRINGS and Starter Sheet read, starting handicaps
included, locked to the event's as-of date) and the roster from
`_event_roster_rows` (THE pairings roster). The events page, the MCP tool and
the Front Desk brief all read this module. Read-only.
"""
from __future__ import annotations

FIX_75 = ("enter a starting handicap: 75% of their current index "
          "(the Handicap Standard's intro rule)")
NH_NOTE = ("With no handicap they play N/H; the blind that stands in for an N/H "
           "player's money is being built by Side Games (#1064, #1067).")


def _rounds_on_file(conn, cid) -> int:
    if not cid:
        return 0
    try:
        r = conn.execute(
            """SELECT COUNT(*) FROM handicap_rounds hr
               JOIN handicap_player_links l ON lower(l.player_name) = lower(hr.player_name)
               WHERE l.customer_id = ?""", (int(cid),)).fetchone()
        return int(r[0] or 0)
    except Exception:
        return 0


def missing_handicaps(event_id: int, db_path=None) -> dict:
    from email_parser import database as db
    with db._connect(db_path) as conn:
        ev = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
        if not ev:
            return {"error": f"no event {event_id}"}
        ev = dict(ev)
        hcp = db._roster_handicap_index_map(conn, as_of=db._event_index_as_of(ev), db_path=db_path)
        seen, players = set(), []
        for r in db._event_roster_rows(conn, int(event_id)):
            cid = r.get("customer_id")
            name = (r.get("customer") or r.get("name") or "").strip()
            key = ("c", int(cid)) if cid else ("n", name.lower())
            if not name or key in seen:
                continue
            seen.add(key)
            has = (cid and ("c", int(cid)) in hcp) or (name.lower() in hcp)
            if has:
                continue
            n_rounds = _rounds_on_file(conn, cid)
            if not cid:
                case = "no_identity"
                fix = ("this Golf Genius RSVP matches no customer: link or add the player, "
                       "then " + FIX_75)
            elif n_rounds:
                case = "few_rounds"
                fix = (f"{n_rounds} round{'s' if n_rounds != 1 else ''} on file, not enough "
                       f"for a TGF index yet: " + FIX_75)
            else:
                case = "new"
                fix = "no rounds on file: ask for their current index and " + FIX_75
            players.append({"customer_id": cid, "name": name, "case": case,
                            "rounds_on_file": n_rounds,
                            "status": r.get("current_player_status") or r.get("user_status"),
                            "rsvp_only": bool(r.get("rsvp_only")), "fix": fix})
    from email_parser.timezone_utils import today_central_str
    upcoming = str(ev.get("event_date") or "")[:10] >= today_central_str()
    players.sort(key=lambda p: p["name"].lower())
    n = len(players)
    msg = (f"{n} player{'s' if n != 1 else ''} ha{'ve' if n != 1 else 's'} no handicap: "
           + ", ".join(p["name"] for p in players)) if n else ""
    return {"event_id": int(event_id), "event": ev.get("item_name"),
            "event_date": ev.get("event_date"), "upcoming": upcoming, "count": n, "message": msg,
            "players": players, "nh_note": NH_NOTE if n else ""}


def upcoming_missing_handicaps(days: int = 14, db_path=None) -> dict:
    """Every upcoming event (today through `days` ahead, Central) with at
    least one player missing a handicap — the Front Desk brief's read."""
    from email_parser import database as db
    from email_parser.timezone_utils import today_central
    from datetime import timedelta
    today = today_central()
    end = today + timedelta(days=max(0, int(days or 14)))
    with db._connect(db_path) as conn:
        evs = [dict(r) for r in conn.execute(
            """SELECT id, item_name, event_date FROM events
               WHERE substr(event_date, 1, 10) BETWEEN ? AND ?
               ORDER BY event_date, id""", (today.isoformat(), end.isoformat()))]
    out = []
    for e in evs:
        try:
            m = missing_handicaps(e["id"], db_path=db_path)
        except Exception as exc:  # one bad event must not hide the rest
            out.append({"event_id": e["id"], "event": e["item_name"], "error": str(exc)})
            continue
        if m.get("count"):
            out.append(m)
    return {"from": today.isoformat(), "through": end.isoformat(),
            "events_checked": len(evs), "events_with_missing": len(out),
            "players_missing": sum(e.get("count", 0) for e in out), "events": out}
