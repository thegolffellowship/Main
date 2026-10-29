"""THE POINTS TAB on Live Scoring (Kerry 2026-10-29, Event Ops #2460-F: "The
Leaderboard button on the scoring app will also need the ability to see those
point race standings too ... SCORING | LEADERBOARD | POINTS").

`points_context(group_id)` tells the tab what to read; the standings
themselves come from the same public endpoints the member LEADERBOARD reads
(`/api/season-contests/points-race?race=<key>` and
`/api/season-contests/monthly-points`), so the numbers cannot differ.

  Monthly       always (it is live at every event): the event's month;
  season races  each group player's home-chapter Fall race (tracker_points'
                home chapter), plus the event's own chapter race; a TGF
                event with no chapter shows both.

Ids only (the group's customer_ids, for highlighting); no names, no
contact data. Reads se_* only through score_entry.
"""
from __future__ import annotations

RACE_OF_CHAPTER = {"san antonio": "san_antonio_fall_net", "austin": "austin_fall_net"}


def points_context(group_id: int, db_path=None) -> dict:
    from email_parser import database as db
    from email_parser import score_entry as se
    from email_parser.tracker_points import _home_chapter
    ev_id = se.event_of("group", group_id, db_path)
    rid = se.event_of("round_of_group", group_id, db_path)
    cids: list = []
    if rid:
        for gid, ids in se._group_rosters(rid, db_path=db_path).values():
            if int(gid) == int(group_id):
                cids = sorted(int(c) for c in ids if c)
    ev = {}
    races: list = []
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT id, item_name, event_date, chapter FROM events WHERE id = ?",
                         (ev_id,)).fetchone() if ev_id else None
        ev = dict(r) if r else {}
        ev_ch = (ev.get("chapter") or "").strip().lower()
        chapters = []
        if ev_ch in RACE_OF_CHAPTER:
            chapters.append(ev_ch)
        for cid in cids:
            ch = (_home_chapter(conn, cid, "") or "").strip().lower()
            if ch in RACE_OF_CHAPTER and ch not in chapters:
                chapters.append(ch)
        if not chapters:
            chapters = list(RACE_OF_CHAPTER)
    for ch in chapters:
        key = RACE_OF_CHAPTER[ch]
        races.append({"key": key, "label": (db._GG_POINTS_RACES.get(key) or {}).get("label") or key,
                      "chapter": ch.title()})
    return {"event": {"id": ev.get("id"), "name": ev.get("item_name"),
                      "date": str(ev.get("event_date") or "")[:10]},
            "month": str(ev.get("event_date") or "")[:7],
            "races": races, "group_customer_ids": cids}
