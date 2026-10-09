"""UNTETHERED FROM GOLF GENIUS (Kerry 2026-10-08: "Golf Genius is not the
ruler on this or from now on. We need to untether for this event and all
future events unless I say." Earlier the same night: "There shouldn't be
anymore Golf Genius connections for future events including this weekend.
Only for past events and really only for the points we still need to post
from last Tuesday.").

ONE rule, read by every path that pulls from Golf Genius or lets Golf Genius
decide something for an event: an event dated ON OR AFTER the untether date
gets nothing from Golf Genius (no scorecards, results, flights, tee sheets,
RSVPs, payouts or monthly money). Events before it (through Tue 10/6) keep
their Golf Genius walks, so last Tuesday's points still post.

The date is the app setting `gg_untether_from` (YYYY-MM-DD), default
2026-10-07: Kerry moves it only if he says so.
"""
from __future__ import annotations

SETTING = "gg_untether_from"
DEFAULT = "2026-10-07"


def untether_from(db_path=None) -> str:
    try:
        from email_parser.database import get_app_setting
        v = (get_app_setting(SETTING, db_path=db_path) or "").strip()[:10]
    except Exception:
        v = ""
    return v or DEFAULT


def gg_allowed(event_date, db_path=None) -> bool:
    """May Golf Genius touch an event on this date? Only BEFORE the untether
    date. An event with no date is treated as current (not allowed): a GG
    pull must prove the event is past."""
    d = str(event_date or "").strip()[:10]
    return bool(d) and d < untether_from(db_path)


def gg_allowed_event(conn, event_id, db_path=None) -> bool:
    try:
        r = conn.execute("SELECT event_date FROM events WHERE id = ?", (int(event_id),)).fetchone()
    except Exception:
        return False
    return bool(r) and gg_allowed(r[0], db_path)


def gg_allowed_month(month: str, db_path=None) -> bool:
    """Monthly points money (YYYY-MM): only months that END before the
    untether date are Golf Genius's to settle."""
    m = str(month or "").strip()[:7]
    return bool(m) and m < untether_from(db_path)[:7]


REFUSAL = ("Golf Genius is untethered for this event (Kerry 10/8: \"Golf Genius is not the "
           "ruler on this or from now on\"). Events from {d} on are scored, paired and paid "
           "by the Tracker only; move the app setting gg_untether_from only on Kerry's word.")


def refusal(db_path=None) -> str:
    return REFUSAL.format(d=untether_from(db_path))
