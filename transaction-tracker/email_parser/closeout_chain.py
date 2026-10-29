"""THE CLOSEOUT CHAIN, IN THE TRACKER (Kerry 2026-10-28, #2457 BUILD 1;
2026-10-29: "Build both now for Saturday").

Kerry: "I want Claude side auditing/review checking every step on the
outside as a step, but don't want our events to be Claude dependent." At
CLOSEOUT START (scoring_window.tick) the Tracker runs the closeout itself,
in order, each step guarded:

  publish    signed cards -> scorecards (entry_publish.publish_event)
  final      closeout_checks.closeout_final_check: no blockers
  payouts    the night's money is recorded (auto_payouts wrote it)
  flights    freeze/settle the flights board (close_event_flights)
  pairings   who played with whom (pairing_history_from_entry)
  handicaps  post the rounds: a nine as one round, an 18 as two nines
             (refused for an event on the NO HANDICAPS list -> skipped)
  points     tracker_points.rebuild (refused while a hold is open)
  pace       score_entry.rebuild_pace for each of the event's rounds
  recap      once EVERY event of the night is here: recap_writer writes and
             stores the recap, the staff drafts go to the senders, and the
             6:00 AM results email is scheduled with it

A step that fails HOLDS that step and every step after it, raises one COO
item (`CLOSEOUT HELD: <event>`) and posts once to Event Ops; the next tick
(5 minutes) tries again from the held step. Done steps are never re-run.
State: app setting `closeout_chain:<event_id>`. Dial `closeout_chain_auto`
(on unless "off"). Event Ops verifies from outside and is the fallback: if
the chain holds, they finish by hand exactly as before.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

STATE_KEY = "closeout_chain:{}"
NIGHT_KEY = "closeout_recap_night:{}"
DIAL = "closeout_chain_auto"
GRACE_MINUTES = 30
STEPS = ("publish", "final", "payouts", "flights", "pairings", "handicaps",
         "points", "pace", "recap")
AUTHORITY = ("Kerry 2026-10-29 (Tracker Build 5): \"Build both now for Saturday\" — the in-Tracker "
             "closeout chain and recap writer of #2457 BUILD 1/2, the 6:00 AM send per #1778.")


def enabled(db_path=None) -> bool:
    from . import database as db
    return (db.get_app_setting(DIAL, db_path=db_path) or "on").strip().lower() \
        not in ("off", "0", "false", "no")


def state(event_id: int, db_path=None) -> dict:
    from . import database as db
    raw = db.get_app_setting(STATE_KEY.format(int(event_id)), db_path=db_path)
    try:
        return json.loads(raw) if raw else {"steps": {}}
    except ValueError:
        return {"steps": {}}


def _save(event_id: int, st: dict, db_path=None) -> None:
    from . import database as db
    db.set_app_setting(STATE_KEY.format(int(event_id)), json.dumps(st, default=str), db_path=db_path)


def _event(event_id: int, db_path=None) -> dict | None:
    from . import database as db
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    return dict(r) if r else None


def _kw(db_path):
    return {"db_path": db_path} if db_path else {}


# ── the steps: each returns (ok, note); an exception is a hold ───────────
def step_publish(ev, db_path=None):
    from .entry_publish import publish_event
    r = publish_event(ev["id"], apply=True, db_path=db_path)
    if r.get("error"):
        return False, r["error"]
    return True, f"published ({r.get('mode') or r.get('state') or 'ok'})"


def step_final(ev, db_path=None):
    from .closeout_checks import closeout_final_check
    r = closeout_final_check(ev["id"], db_path=db_path)
    if r.get("error"):
        return False, r["error"]
    if not r.get("final"):
        return False, "not final: " + "; ".join(r.get("blocking") or [])
    return True, "final"


def step_payouts(ev, db_path=None):
    from . import database as db
    from . import auto_payouts as ap
    from .closeout_checks import _payout_rows
    held = ap.holds(db_path).get(str(int(ev["id"])))
    if held:
        return False, f"payouts on hold: {held.get('reason') if isinstance(held, dict) else held}"
    with db._connect(db_path) as conn:
        n = len(_payout_rows(conn, int(ev["id"])))
    if not n:
        return False, "no payouts recorded yet (auto payouts records them once every card is final)"
    return True, f"{n} payout rows recorded"


def step_flights(ev, db_path=None):
    from . import database as db
    r = db.close_event_flights(ev["id"], by="closeout chain", trigger="closeout", db_path=db_path)
    if not r.get("ok"):
        return False, r.get("error") or "flights did not settle"
    return True, f"flights {r.get('state') or 'settled'}"


def step_pairings(ev, db_path=None):
    from .closeout_checks import pairing_history_from_entry
    r = pairing_history_from_entry(ev["id"], apply=True, db_path=db_path)
    if r.get("error"):
        return False, r["error"]
    return True, "pairing history recorded"


def _holes(ev, db_path=None) -> int:
    from . import database as db
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT MAX(holes_played) FROM scoring_rounds WHERE event_id = ?",
                         (ev["id"],)).fetchone()
    return int(r[0] or 9)


def step_handicaps(ev, db_path=None):
    from . import database as db
    if str(ev["id"]) in {str(k) for k in (db.hcp_skip_events(**_kw(db_path)) or {})}:
        return True, "skipped: event is on the NO HANDICAPS list"
    if _holes(ev, db_path) >= 18:
        r = db.derive_18hole_rounds_as_two_nines(ev["item_name"], dry_run=False, **_kw(db_path))
    else:
        r = db.derive_handicap_rounds_from_scoring(ev["item_name"], dry_run=False, **_kw(db_path))
    if r.get("error"):
        return False, r["error"]
    n = r.get("written") or r.get("imported") or r.get("created") or len(r.get("rounds") or [])
    return True, f"handicap rounds posted ({n})"


def step_points(ev, db_path=None):
    from . import tracker_points as tp
    if not tp.tracker_source_on(db_path):
        return True, "skipped: points_source is not tracker"
    r = tp.rebuild(db_path=db_path, apply=True)
    if r.get("refused"):
        return False, f"points rebuild refused: {r['refused']}"
    if r.get("error"):
        return False, r["error"]
    return True, "points rebuilt"


def step_pace(ev, db_path=None):
    from . import database as db
    from . import score_entry as se
    with db._connect(db_path) as conn:
        try:
            rids = [int(x[0]) for x in conn.execute(
                "SELECT id FROM se_rounds WHERE event_id = ?", (ev["id"],))]
        except Exception:
            rids = []
    for rid in rids:
        se.rebuild_pace(rid, apply=True, db_path=db_path)
    return True, f"pace rebuilt for {len(rids)} round(s)"


def night_events(ev, db_path=None) -> list:
    """Every active event on the same date that is in Live Scoring."""
    from . import database as db
    from . import score_entry as se
    with db._connect(db_path) as conn:
        ids = [int(x[0]) for x in conn.execute(
            "SELECT id FROM events WHERE substr(event_date, 1, 10) = ? "
            "AND COALESCE(status, 'active') = 'active' ORDER BY id",
            (str(ev["event_date"])[:10],))]
    return [e for e in ids if se.event_enabled(e, db_path)] or [int(ev["id"])]


def step_recap(ev, db_path=None):
    """Waits (not a hold) until every event of the night reached this step;
    the first event to see them all writes the night's recap once."""
    from . import database as db
    from . import recap_writer as rw
    ids = night_events(ev, db_path)
    waiting = [e for e in ids if e != int(ev["id"])
               and state(e, db_path).get("at") not in ("recap", "done")]
    if waiting:
        return None, f"waiting for event(s) {waiting} to reach the recap"
    # The post-round interview answers (#2462): only while dial
    # ai_interview_email is on and invitations went out minutes ago.
    try:
        from . import ai_interview as _ai
        _w = _ai.recap_wait(ids, db_path=db_path)
    except Exception:
        _w = None
    if _w:
        return None, _w
    nk = NIGHT_KEY.format(str(ev["event_date"])[:10])
    done = db.get_app_setting(nk, db_path=db_path)
    if done:
        return True, f"night's recap already written: {done}"
    if not rw.enabled(db_path):
        return True, "skipped: recap_writer_auto is off (Event Ops writes it)"
    res = rw.write_and_store(ids, db_path=db_path)
    name = res["name"]
    db.set_app_setting(nk, name, db_path=db_path)
    notes = [f"stored {name} ({res['model']}, {res['attempts']} attempt(s))"]
    from . import recap_mail
    for sec in res["sections"]:
        try:
            d = recap_mail.send_recap_draft(name, sec, dry_run=False, db_path=db_path)
            notes.append(f"{sec} draft: {d.get('error') or d.get('status') or 'sent'}")
        except Exception as exc:
            logger.exception("closeout chain: recap draft %s failed", sec)
            notes.append(f"{sec} draft failed: {exc}")
    if (db.get_app_setting("recap_auto_schedule", db_path=db_path) or "on").strip().lower() \
            not in ("off", "0", "false", "no"):
        from . import results_email as re_
        s = re_.schedule_send(ids, re_.next_morning(ids, db_path=db_path), name, AUTHORITY,
                              db_path=db_path)
        notes.append(f"6:00 AM results email: {s.get('error') or 'scheduled ' + s.get('at', '')}")
    _post(f"RECAP WRITTEN: {name} for event(s) {', '.join(map(str, ids))}. "
          + " ".join(notes) + ". Event Ops: verify it; to hold the 6:00 AM send use "
          f"scoring-results-email:cancel|{','.join(map(str, ids))}. Do not write your own recap "
          "unless the chain holds.", db_path)
    return True, "; ".join(notes)


STEP_FN = {"publish": step_publish, "final": step_final, "payouts": step_payouts,
           "flights": step_flights, "pairings": step_pairings, "handicaps": step_handicaps,
           "points": step_points, "pace": step_pace, "recap": step_recap}


# ── holds ───────────────────────────────────────────────────────────────
def _post(body: str, db_path=None) -> None:
    from . import database as db
    from .timezone_utils import now_central
    text = (f"TO: Event Ops (closeout), front-desk\nCC: kerry\nFROM: the Tracker (closeout chain), "
            f"{now_central().strftime('%A %m/%d %-I:%M %p')}.\n\n{body}")
    try:
        db.post_platform_dialogue_entry("tracker-claude", text, "closeout", **_kw(db_path))
    except Exception:
        logger.exception("closeout chain: mailbox post failed")


def _hold(ev, step, why, st, db_path=None) -> None:
    from . import database as db
    first = st.get("held") != {"step": step, "why": why}
    st["held"] = {"step": step, "why": why}
    if not first:
        return
    try:
        db.save_action_item({
            "subject": f"CLOSEOUT HELD: {ev['item_name']}",
            "from_name": "Closeout chain",
            "summary": (f"The closeout stopped at '{step}'.\nWhy: {why}\nEvery later step waits. "
                        "Clear the cause and the next run (5 minutes) continues; or Event Ops "
                        "finishes this event by hand."),
            "urgency": "high", "category": "scoring"}, db_path=db_path)
    except Exception:
        logger.exception("closeout chain: COO item failed")
    _post(f"CLOSEOUT HELD: {ev['item_name']} (event {ev['id']}) at step '{step}': {why}. "
          "Later steps wait; the chain retries every 5 minutes.", db_path)


def run(event_id: int, db_path=None, until: str | None = None, now=None) -> dict:
    """Run the chain from where it stands. Idempotent; called every tick
    after CLOSEOUT START."""
    from .timezone_utils import now_central
    ev = _event(event_id, db_path)
    if not ev:
        return {"error": f"no event {event_id}"}
    st = state(event_id, db_path)
    steps = st.setdefault("steps", {})
    now = now or now_central()
    st.setdefault("started", now.strftime("%Y-%m-%d %H:%M"))
    try:
        age = (now - datetime.strptime(st["started"], "%Y-%m-%d %H:%M")).total_seconds() / 60
    except ValueError:
        age = GRACE_MINUTES
    for name in STEPS:
        if steps.get(name, {}).get("ok"):
            continue
        st["at"] = name
        try:
            ok, note = STEP_FN[name](ev, db_path=db_path)
        except Exception as exc:
            logger.exception("closeout chain: %s failed for %s", name, event_id)
            ok, note = False, f"{type(exc).__name__}: {exc}"
        if ok is None:          # waiting, not a fault
            st["waiting"] = note
            break
        if not ok and age < GRACE_MINUTES:
            # The first half hour: cards finalise and the money records on
            # their own minute jobs; a step that is merely early waits.
            st["waiting"] = note
            break
        if not ok:
            _hold(ev, name, note, st, db_path)
            break
        steps[name] = {"ok": True, "note": note, "at": now.strftime("%Y-%m-%d %H:%M")}
        st.pop("held", None)
        st.pop("waiting", None)
        if until and name == until:
            break
    else:
        st["at"] = "done"
    _save(event_id, st, db_path)
    return {"event_id": int(event_id), **st}


def tick_event(event_id: int, db_path=None, now=None) -> dict | None:
    """From scoring_window.tick once CLOSEOUT START is set."""
    if not enabled(db_path):
        return None
    if state(event_id, db_path).get("at") == "done":
        return None
    return run(event_id, db_path=db_path, now=now)


def reset(event_id: int, step: str | None = None, db_path=None) -> dict:
    """Forget a step (and every later one) so the next run does it again."""
    st = state(event_id, db_path)
    if step:
        for s in STEPS[STEPS.index(step):]:
            st.get("steps", {}).pop(s, None)
    else:
        st = {"steps": {}}
    st.pop("held", None)
    st["at"] = step or "publish"
    _save(event_id, st, db_path)
    return st
