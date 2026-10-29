"""WINDOW OPEN / WINDOW CLOSED posted by the Tracker itself (Event Ops #2460-I).

Event Ops: "WINDOW OPEN / CLOSED, the deploy freeze, can be posted by the
Tracker itself from first tee minus 1 hour, last score plus 1 hour, and the
clean closeout." Until now the Front Desk posted both lines on the mailbox by
hand (CLAUDE.md "No-push window during live events").

From the scoring-window job (`scoring_window.tick`, every 5 minutes), for each
of today's live score-entry events:
- WINDOW OPEN once the time is first tee minus `window_open_minutes` (60):
  one mailbox line, author tracker-claude, topic front-desk, first line
  "TO: front-desk", naming the event and its first tee, and "no pushes to
  main until WINDOW CLOSED";
- WINDOW CLOSED once the close-out is clean (`closeout_final_check` final,
  checked only after CLOSEOUT START), or, while it is still not final, at
  the last score plus `window_close_fallback_minutes` (60). The line says
  which.
Once per event each: stamps `window_open_posted:<event_id>` and
`window_closed_posted:<event_id>`. It posts to the mailbox only: no email, no
public post, nothing about the pairings or any sheet.

Dial `window_posts_auto`, OFF unless it reads on. Read-only bridge
`scoring-window-posts[:<event_id>]` shows what would post now. Guard
test_window_posts.py.
"""
from __future__ import annotations

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

DIAL = "window_posts_auto"
OPEN_MIN_DIAL = "window_open_minutes"
CLOSE_FALLBACK_DIAL = "window_close_fallback_minutes"
OPEN_KEY = "window_open_posted:{}"
CLOSED_KEY = "window_closed_posted:{}"
AUTHOR = "tracker-claude"
TOPIC = "front-desk"


def dial_on(db_path=None) -> bool:
    from email_parser.database import get_app_setting
    return (get_app_setting(DIAL, db_path=db_path) or "").strip().lower() in ("1", "on", "true", "yes")


def _minutes(key: str, default: int, db_path=None) -> int:
    from email_parser.database import get_app_setting
    try:
        return max(0, int((get_app_setting(key, db_path=db_path) or "").strip() or default))
    except (TypeError, ValueError):
        return default


def _final(event_id: int, db_path=None) -> tuple:
    """(final, blockers) from closeout_final_check; (False, [why]) on error."""
    try:
        from email_parser.closeout_checks import closeout_final_check
        r = closeout_final_check(int(event_id), db_path=db_path)
        if r.get("error"):
            return False, [r["error"]]
        return bool(r.get("final")), list(r.get("blocking") or [])
    except Exception as exc:  # noqa: BLE001
        logger.exception("window posts: closeout_final_check failed for %s", event_id)
        return False, [f"closeout_final_check failed: {exc}"]


def plan_event(event_id: int, st: dict | None = None, now=None, db_path=None) -> dict:
    """What would post for one event now, and why. Writes nothing."""
    from email_parser import database as db
    from email_parser import scoring_window as sw
    from email_parser.timezone_utils import now_central
    now = now or now_central()
    eid = int(event_id)
    st = st if st is not None else sw.event_state(eid, now=now, db_path=db_path)
    if st.get("error"):
        return {"event_id": eid, "error": st["error"]}
    open_stamp = db.get_app_setting(OPEN_KEY.format(eid), db_path=db_path)
    closed_stamp = db.get_app_setting(CLOSED_KEY.format(eid), db_path=db_path)
    first = st.get("first_tee")
    open_at = first - timedelta(minutes=_minutes(OPEN_MIN_DIAL, 60, db_path)) if first else None
    last = st.get("last_score_at")
    fallback_at = last + timedelta(minutes=_minutes(CLOSE_FALLBACK_DIAL, 60, db_path)) if last else None
    out = {"event_id": eid, "event": st.get("event"), "first_tee": first,
           "open_at": open_at, "open_posted": open_stamp, "last_score_at": last,
           "closed_fallback_at": fallback_at, "closed_posted": closed_stamp,
           "post": None, "body": None}
    # WINDOW CLOSED first: a window that is already over never opens.
    if not closed_stamp and last:
        final, blockers = (False, ["closeout not started"])
        if db.get_app_setting(sw.CLOSEOUT_KEY.format(eid), db_path=db_path):
            final, blockers = _final(eid, db_path)
        out["closeout_final"] = final
        out["closeout_blocking"] = blockers
        if final:
            out["post"], out["how"] = "closed", "clean closeout"
        elif fallback_at and now >= fallback_at:
            out["post"], out["how"] = "closed", "last score + fallback"
        if out["post"]:
            out["body"] = _closed_body(st, now, out, blockers)
            return out
    if not open_stamp and not closed_stamp and open_at and now >= open_at:
        out["post"] = "open"
        out["body"] = _open_body(st, now, open_at)
    return out


def _open_body(st: dict, now, open_at) -> str:
    from email_parser.scoring_window import label
    late = "" if now - open_at < timedelta(minutes=10) else (
        f" (posted at {label(now)}; the window opened at {label(open_at)})")
    return (f"TO: front-desk\nCC: kerry, Event Ops\n"
            f"FROM: the Tracker (scoring window job), {now.strftime('%A %m/%d')}, {label(now)}.\n\n"
            f"WINDOW OPEN: {st.get('event')} (event {st['event_id']}), first tee "
            f"{label(st.get('first_tee'))}. No pushes to main until WINDOW CLOSED{late}. "
            f"An emergency fix needs CA's OK first (CLAUDE.md, No-push window).")


def _closed_body(st: dict, now, plan: dict, blockers: list) -> str:
    from email_parser.scoring_window import label
    if plan.get("how") == "clean closeout":
        why = "the close-out is clean (closeout_final_check: final)"
    else:
        why = (f"the last score was saved at {label(st.get('last_score_at'))}, more than "
               f"{int((plan['closed_fallback_at'] - st['last_score_at']).total_seconds() // 60)} "
               f"minutes ago; the close-out is NOT final yet"
               + (f" ({'; '.join(str(b) for b in blockers[:3])})" if blockers else ""))
    return (f"TO: front-desk\nCC: kerry, Event Ops\n"
            f"FROM: the Tracker (scoring window job), {now.strftime('%A %m/%d')}, {label(now)}.\n\n"
            f"WINDOW CLOSED: {st.get('event')} (event {st['event_id']}): {why}. "
            f"Pushes to main may resume.")


def tick_event(event_id: int, st: dict, now=None, db_path=None) -> str | None:
    """Called by scoring_window.tick for a live score-entry event of today.
    Posts at most one line per run. Returns 'open' / 'closed' / None."""
    if not dial_on(db_path):
        return None
    from email_parser import database as db
    p = plan_event(event_id, st=st, now=now, db_path=db_path)
    kind = p.get("post")
    if not kind:
        return None
    key = (OPEN_KEY if kind == "open" else CLOSED_KEY).format(int(event_id))
    if db.get_app_setting(key, db_path=db_path):
        return None
    from email_parser.timezone_utils import now_central
    stamp = (now or now_central()).strftime("%Y-%m-%d %H:%M")
    # Stamp first: a failed post is retried never rather than twice.
    db.set_app_setting(key, stamp, db_path=db_path)
    try:
        kw = {"db_path": db_path} if db_path else {}
        db.post_platform_dialogue_entry(AUTHOR, p["body"], TOPIC, **kw)
        db.log_agent_action("scoring-window", f"window_{kind}",
                            f"event {event_id} ({p.get('event')}): WINDOW {kind.upper()} posted"
                            + (f" ({p.get('how')})" if kind == "closed" else ""), db_path=db_path)
    except Exception:
        logger.exception("window posts: could not post WINDOW %s for %s", kind, event_id)
        return None
    return kind


def preview(event_id: int | None = None, now=None, db_path=None) -> dict:
    """The read-only bridge: today's live events (or one), what would post."""
    from email_parser import database as db
    from email_parser import score_entry as se
    from email_parser.timezone_utils import now_central
    now = now or now_central()
    if event_id is not None:
        ids = [int(event_id)]
    else:
        with db._connect(db_path) as conn:
            ids = [int(x[0]) for x in conn.execute(
                "SELECT id FROM events WHERE substr(event_date, 1, 10) = ? "
                "AND COALESCE(status, 'active') = 'active'", (now.date().isoformat(),))]
    rows = []
    for eid in ids:
        try:
            r = plan_event(eid, now=now, db_path=db_path)
        except Exception as exc:  # noqa: BLE001
            r = {"event_id": eid, "error": str(exc)}
        r["live_score_entry"] = bool(se.event_enabled(eid, db_path))
        rows.append(r)
    return {"dial": DIAL, "dial_on": dial_on(db_path), "now": now, "events": rows,
            "note": "read only; the scoring-window job posts only with the dial on, "
                    "once per event per line"}
