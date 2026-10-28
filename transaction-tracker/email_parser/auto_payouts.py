"""PRIZE MONEY RUNS ITSELF (Kerry 2026-10-13).

Kerry, verbatim: "Payouts need to auto calculate and populate based on
GAMES tabs immediately after scores are all in"; "15 minutes after last
score entered by each scorer because scorer may not finalize how they
should"; and "When last hole score is entered by last player in field,
won Columns should unhide and amounts should show but non-final until 15
minutes have passed".

For a Tracker-scored event (untethered from Golf Genius, score entry on),
every run of the job (each minute):
  1. once EVERY player in the field has every hole, publishes the complete
     cards (provisional) and assembles the payouts the GAMES tab's Record
     Payouts button would (`assemble_event_game_payouts`);
  2. stores them as the board's PREVIEW (app setting auto_payouts_preview:
     rows with customer_id, final, final_at). The EVENTS board shows them
     in the WON column at once, marked not final;
  3. when every card is final (15 minutes after its group's last score,
     score_entry.card_final_at), records them as auto rows
     (`record_event_game_payouts`), and again whenever they change. A
     re-record never un-pays a paid row; an event with manually recorded
     payouts is left alone.

Dials: app setting `auto_payouts` (on unless it reads "off") runs the job;
`auto_payouts_record` (OFF unless it reads "on") lets step 3 record — off
for 10/13 by CoS #1760/#1761, on from 10/20 once the dry-run diff against
the hand-recorded rows matches to the cent (it did, #1781). It records only
events dated on or after `auto_payouts_record_from` (default 2026-10-20).

ONE WRITER, CLOSEOUT VERIFIES (CoS #1797): this job is the only thing that
records; nothing is ever paid by it. It does not record while any hold the
verifier relies on is open, and each reaches Kerry as one COO item
"PAYOUTS HELD: <event>" (card parity raises its own "SCORING HOLD"):
  - card parity (engine vs saved card) and manually recorded rows, both
    refused inside `record_event_game_payouts`;
  - a closest-to-the-pin takeover the manager has not confirmed;
  - a hold placed by the verifier or Kerry (app setting `auto_payouts_hold`,
    bridge `scoring-auto-payouts:hold|<event_id>|<reason>` / `release|<id>`).
A held or refused event is re-checked when its cards change and every
15 minutes. Per-event
state (fingerprint, score-entry version, final) in app setting
`auto_payouts_fp`; an event is not re-run until its version moves or its
provisional money turns final. Bridge
`scoring-auto-payouts[:apply][|<event_id>]` (dry run by default).
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

DIAL = "auto_payouts"
FP_SETTING = "auto_payouts_fp"
PREVIEW_SETTING = "auto_payouts_preview"
LOOKBACK_DAYS = 3


RECORD_DIAL = "auto_payouts_record"
RECORD_FROM = "auto_payouts_record_from"
RECORD_FROM_DEFAULT = "2026-10-20"
HOLD_SETTING = "auto_payouts_hold"
RETRY_MINUTES = 15


def record_enabled(db_path=None, event_date: str | None = None) -> bool:
    """Step 3 (recording) has its own dial, OFF unless it reads "on"
    (CoS #1760/#1761, Kerry "Go with your conditions": 10/13 is display
    only; auto-record turns on from 10/20 once a dry run matches the
    hand-recorded rows to the cent). With an event date, the event must
    also fall on or after app setting `auto_payouts_record_from` (default
    2026-10-20, CoS #1797), so turning the dial on never reaches back to an
    event closed out by hand."""
    from email_parser.database import get_app_setting
    if (get_app_setting(RECORD_DIAL, db_path) or "off").strip().lower() != "on":
        return False
    if event_date is None:
        return True
    start = (get_app_setting(RECORD_FROM, db_path) or RECORD_FROM_DEFAULT).strip()
    return (event_date or "")[:10] >= start


def holds(db_path=None) -> dict:
    """Per-event holds placed by the verifier (Closeout) or Kerry (CoS
    #1797: "Any hold goes to Kerry. Kerry keeps the Unlock and override"):
    {event_id: {reason, by, at}}."""
    from email_parser.database import get_app_setting
    try:
        return json.loads(get_app_setting(HOLD_SETTING, db_path) or "{}") or {}
    except (ValueError, TypeError):
        return {}


def hold(event_id: int, reason: str, by: str = "", db_path=None) -> dict:
    """Stop the job recording one event (the preview still shows). Rows
    already recorded stay as they are, pending; only Kerry pays."""
    from email_parser import score_entry as se
    reason = (reason or "").strip()
    if not reason:
        return {"error": "a hold needs a reason"}
    _save(HOLD_SETTING, int(event_id), {"reason": reason, "by": by, "at": se._now()}, db_path)
    _alarm(int(event_id), f"held by {by or 'the verifier'}: {reason}", db_path)
    return {"held": int(event_id), "reason": reason}


def release(event_id: int, by: str = "", db_path=None) -> dict:
    """Lift a hold; the next run re-checks the event at once."""
    was = holds(db_path).get(str(int(event_id)))
    _save(HOLD_SETTING, int(event_id), None, db_path)
    _save(FP_SETTING, int(event_id), None, db_path)
    return {"released": int(event_id), "was": was, "by": by}


def _alarm(event_id: int, why: str, db_path=None) -> None:
    """One COO action item per event while open (deduped by subject): every
    hold reaches Kerry (CoS #1797)."""
    from email_parser import database as db
    try:
        with db._connect(db_path) as conn:
            r = conn.execute("SELECT item_name FROM events WHERE id = ?", (event_id,)).fetchone()
        name = r["item_name"] if r else f"event {event_id}"
        db.save_action_item({
            "subject": f"PAYOUTS HELD: {name}",
            "from_name": "Auto payouts",
            "summary": ("The payouts for this event were not recorded automatically.\n"
                        f"Why: {why}\nNothing is paid. Clear the cause (or release the "
                        "hold) and the job records on its next run."),
            "urgency": "high", "category": "scoring"}, db_path=db_path)
    except Exception:
        logger.exception("auto payouts alarm failed for %s", event_id)


def _ctp_pending(event_id: int, db_path=None) -> list[str]:
    """Contest holes whose holder took them from another group and the
    manager has not confirmed (CTP verification, Kerry 10/13). The money is
    not recorded while any is open: recording without that hole would look
    final."""
    from email_parser import score_entry as se
    out = []
    for h in se.event_ctp_holders(event_id, db_path=db_path):
        nc = h.get("needs_confirm")
        if nc:
            out.append(f"hole {h['hole']}: {nc['to'].get('name')} took it from "
                       f"{nc['from'].get('name')}; confirm it on Live Scoring")
    return out


def enabled(db_path=None) -> bool:
    from email_parser.database import get_app_setting
    return (get_app_setting(DIAL, db_path) or "on").strip().lower() != "off"


def fingerprint(rows: list) -> str:
    key = sorted(((r.get("golferName") or "").strip().lower(),
                  r.get("customer_id") or 0, r.get("category") or "",
                  round(float(r.get("amount") or 0), 2),
                  r.get("description") or "") for r in rows or [])
    return hashlib.sha256(json.dumps(key).encode()).hexdigest()[:16]


def _fps(db_path=None) -> dict:
    from email_parser.database import get_app_setting
    try:
        return json.loads(get_app_setting(FP_SETTING, db_path) or "{}") or {}
    except (ValueError, TypeError):
        return {}


def candidate_events(db_path=None, event_id: int | None = None) -> list[dict]:
    """Score-entry events in the last few days that the Tracker scores."""
    from email_parser import database as db
    from email_parser import score_entry as se
    from email_parser.gg_untether import gg_allowed
    from email_parser.timezone_utils import today_central_str
    today = today_central_str()
    since = (date.fromisoformat(today) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    ids = {int(event_id)} if event_id else set(se.enabled_events(db_path))
    out = []
    with db._connect(db_path) as conn:
        for eid in sorted(ids):
            r = conn.execute("SELECT id, item_name, event_date FROM events WHERE id = ?",
                             (eid,)).fetchone()
            if not r:
                continue
            d = r["event_date"] or ""
            if not event_id and not (since <= d <= today):
                continue
            if gg_allowed(d, db_path):
                continue
            out.append(dict(r))
    return out


def _field_cids(read: dict) -> list[int]:
    return sorted({int(p["customer_id"]) for r in read.get("rounds") or []
                   for p in r.get("players") or [] if p.get("customer_id")})


def _with_ids(rows: list, read: dict, db_path=None) -> list:
    """Every preview row carries the customer_id (team splits arrive by
    name): the field's own players first, then the scoring resolver."""
    from email_parser import database as db
    cids = _field_cids(read)
    out = []
    with db._connect(db_path) as conn:
        names = {}
        for cid in cids:
            c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                             (cid,)).fetchone()
            if c:
                names[f"{c['first_name'] or ''} {c['last_name'] or ''}".strip().lower()] = cid
        for r in rows:
            cid = r.get("customer_id")
            nm = (r.get("golferName") or "").strip()
            if not cid:
                cid = names.get(nm.lower())
            if not cid and nm:
                try:
                    cid = db._resolve_scoring_player(conn, nm)
                except Exception:
                    cid = None
            out.append({"customer_id": cid, "name": nm, "category": r.get("category"),
                        "amount": round(float(r.get("amount") or 0), 2),
                        "description": r.get("description") or ""})
    return out


def _event_final(read: dict) -> tuple[bool, str | None]:
    """(every card final, when the last one is/was final)."""
    from email_parser.score_entry import scored_groups
    gs = [g for r in read.get("rounds") or [] for g in scored_groups(r)]
    if not gs or any(not g.get("final_at") for g in gs):
        return False, None
    return all(g.get("final") for g in gs), max(g["final_at"] for g in gs)


def _save(key: str, eid, value, db_path=None):
    from email_parser.database import get_app_setting, set_app_setting
    try:
        m = json.loads(get_app_setting(key, db_path) or "{}") or {}
    except (ValueError, TypeError):
        m = {}
    if value is None:
        m.pop(str(eid), None)
    else:
        m[str(eid)] = value
    set_app_setting(key, json.dumps(m, sort_keys=True), db_path)


def _later(minutes: int) -> str:
    from datetime import datetime, timezone
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _due(at: str | None) -> bool:
    from email_parser import score_entry as se
    return not at or at <= se._now()


def preview_for(event_id, db_path=None) -> dict | None:
    """The board's money before (and after) the record: {rows, final,
    final_at}. None when the field is not complete."""
    from email_parser.database import get_app_setting
    try:
        return (json.loads(get_app_setting(PREVIEW_SETTING, db_path) or "{}") or {}).get(
            str(event_id))
    except (ValueError, TypeError):
        return None


def run_event(ev: dict, apply: bool = False, db_path=None) -> dict:
    from email_parser import database as db
    from email_parser import entry_publish as ep
    from email_parser import score_entry as se
    name, eid = ev["item_name"], int(ev["id"])
    res = {"event_id": eid, "event": name}
    # Nothing to do until a card changes or a provisional field turns final:
    # the score-entry version bumps on every score, unlock and CTP ruling.
    version = se.event_version(eid, db_path=db_path)
    last = _fps(db_path).get(str(eid))
    last = last if isinstance(last, dict) else {"fp": last}
    _rec_now = record_enabled(db_path, ev.get("event_date"))
    _waiting = (last.get("refused") or last.get("held")) and not _due(last.get("retry_at"))
    if apply and last.get("v") == version and (
            (last.get("final") and not (last.get("display_only") and _rec_now)
             and not last.get("held") and not last.get("refused"))
            or _waiting
            or (last.get("final_at") and not se.card_is_final(last["final_at"])
                and last.get("mins") == se.card_lock_minutes(db_path))):
        return {**res, "state": "unchanged", "fingerprint": last.get("fp")}
    # The whole field in first: publish every complete card (provisional).
    # A dry run first, so nothing is written while the round is still on.
    pub = ep.publish_event(eid, apply=False, db_path=db_path, provisional=True)
    if pub.get("error"):
        return {**res, "state": "error", "why": pub["error"]}
    held = [h for r in pub.get("rounds") or [] for h in r.get("held") or []]
    if not held and apply:
        pub = ep.publish_event(eid, apply=True, db_path=db_path, provisional=True)
        held = [h for r in pub.get("rounds") or [] for h in r.get("held") or []]
    res["published"] = (pub.get("summary") or {})
    if held:
        if apply and preview_for(eid, db_path):
            _save(PREVIEW_SETTING, eid, None, db_path)
        return {**res, "state": "waiting",
                "why": f"{len(held)} player(s) still to finish",
                "held": [{"name": h.get("name"), "reason": h.get("reason")} for h in held]}
    read = se.get_entered_scores(eid, db_path=db_path)
    final, final_at = _event_final(read)
    asm = db.assemble_event_game_payouts(name, db_path=db_path)
    if asm.get("error"):
        return {**res, "state": "error", "why": asm["error"]}
    rows = asm.get("rows") or []
    res.update(total=asm.get("total"), rows=len(rows), notes=asm.get("notes") or [],
               final=final, final_at=final_at)
    fp = fingerprint(rows)
    preview = {"rows": _with_ids(rows, read, db_path), "final": final, "final_at": final_at,
               "total": asm.get("total"), "fp": fp, "at": se._now()}
    if not apply and not final:
        return {**res, "state": "provisional", "fingerprint": fp, "payouts": preview["rows"]}
    if apply:
        _save(PREVIEW_SETTING, eid, preview, db_path)
    if not final:
        _save(FP_SETTING, eid, {"fp": last.get("fp"), "v": version, "final": False,
                                "final_at": final_at, "recorded": last.get("recorded"),
                                "mins": se.card_lock_minutes(db_path)}, db_path)
        return {**res, "state": "provisional", "fingerprint": fp}
    if not rows:
        if apply:
            _save(FP_SETTING, eid, {"fp": fp, "v": version, "final": True}, db_path)
        return {**res, "state": "nothing", "why": "nothing determined to pay"}
    if not _rec_now:
        if apply:
            _save(FP_SETTING, eid, {"fp": last.get("fp"), "v": version, "final": True,
                                    "recorded": last.get("recorded"),
                                    "display_only": True}, db_path)
        return {**res, "state": "final_display_only", "fingerprint": fp,
                "why": "auto_payouts_record is off for this event: shown on the board, not recorded",
                **({} if apply else {"payouts": preview["rows"]})}
    # Every hold the verifier relies on, checked before the one writer
    # (CoS #1797). Card parity / SCORING HOLD and manual rows are refused
    # inside record_event_game_payouts itself.
    why = None
    h = holds(db_path).get(str(eid))
    if h:
        why = f"held by {h.get('by') or 'the verifier'}: {h.get('reason')}"
    else:
        pend = _ctp_pending(eid, db_path)
        if pend:
            why = "closest to the pin waits for the manager: " + "; ".join(pend)
    if why:
        if not apply:
            return {**res, "state": "held", "why": why, "fingerprint": fp}
        _save(FP_SETTING, eid, {"fp": last.get("fp"), "v": version, "held": why,
                                "recorded": last.get("recorded"),
                                "retry_at": _later(RETRY_MINUTES)}, db_path)
        if not h:
            _alarm(eid, why, db_path)
        return {**res, "state": "held", "why": why, "fingerprint": fp}
    if not apply:
        return {**res, "state": "would_record", "fingerprint": fp, "payouts": preview["rows"]}
    if last.get("fp") == fp and last.get("recorded"):
        _save(FP_SETTING, eid, {"fp": fp, "v": version, "final": True, "recorded": True}, db_path)
        return {**res, "state": "unchanged", "fingerprint": fp}
    rec = db.record_event_game_payouts(name, rows, force=True, db_path=db_path)
    if rec.get("error"):
        _save(FP_SETTING, eid, {"fp": last.get("fp"), "v": version, "refused": rec["error"],
                                "recorded": last.get("recorded"),
                                "retry_at": _later(RETRY_MINUTES)}, db_path)
        if not rec.get("parity"):          # card parity raises its own SCORING HOLD
            _alarm(eid, rec["error"], db_path)
        return {**res, "state": "refused", "why": rec["error"]}
    _save(FP_SETTING, eid, {"fp": fp, "v": version, "final": True, "recorded": True}, db_path)
    try:
        db.log_agent_action("auto-payouts", "auto_payouts_recorded",
                            f"{name}: {len(rows)} payouts, ${asm.get('total')}",
                            outcome="recorded", db_path=db_path)
    except Exception:
        logger.debug("auto-payouts action log failed", exc_info=True)
    return {**res, "state": "recorded", "fingerprint": fp,
            "payouts_added": rec.get("payouts_added")}


def run(apply: bool = False, event_id: int | None = None, db_path=None) -> dict:
    if apply and not event_id and not enabled(db_path):
        return {"skipped": "auto_payouts dial is off", "events": []}
    out = []
    for ev in candidate_events(db_path, event_id):
        try:
            out.append(run_event(ev, apply=apply, db_path=db_path))
        except Exception as e:
            logger.exception("auto payouts failed for %s", ev.get("item_name"))
            out.append({"event_id": ev["id"], "event": ev["item_name"],
                        "state": "error", "why": str(e)})
    return {"dry_run": not apply, "events": out}
