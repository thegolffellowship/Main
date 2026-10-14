"""PAYOUTS RECORD THEMSELVES when every card is final (Kerry 2026-10-13).

Kerry, verbatim: "Payouts need to auto calculate and populate based on
GAMES tabs immediately after scores are all in", and on what "in" means:
"Time based. 15 minutes after scorer confirms scorecard, it locks and is
considered final automatically".

For a Tracker-scored event (untethered from Golf Genius, score entry on),
every run of the job:
  1. publishes the entered cards that are final (entry_publish, which now
     treats a card 15 minutes past its confirm as final, signed or not);
  2. waits until NO player is held (every card in the field final);
  3. assembles the payouts the GAMES tab's Record Payouts button would
     (`assemble_event_game_payouts`, the single source of truth);
  4. records them as auto rows (`record_event_game_payouts`) when they
     differ from what was last recorded. A re-record never un-pays a paid
     row, and an event with manually recorded payouts is left alone.

Dial: app setting `auto_payouts` (on unless it reads "off"). The last
recorded fingerprint and score-entry version per event live in app setting
`auto_payouts_fp`; an event is not touched again until its version moves.
Bridge `scoring-auto-payouts[:apply][|<event_id>]` (dry run by default).
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

DIAL = "auto_payouts"
FP_SETTING = "auto_payouts_fp"
LOOKBACK_DAYS = 3


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


def run_event(ev: dict, apply: bool = False, db_path=None) -> dict:
    from email_parser import database as db
    from email_parser import entry_publish as ep
    from email_parser import score_entry as se
    name = ev["item_name"]
    res = {"event_id": ev["id"], "event": name}
    # Once recorded (or refused), an event is left alone until something on
    # its cards changes: the score-entry version bumps on every write,
    # submit, unlock and Closest to Pin ruling.
    version = se.event_version(int(ev["id"]), db_path=db_path)
    fps = _fps(db_path)
    last = fps.get(str(ev["id"]))
    last = last if isinstance(last, dict) else {"fp": last}
    if apply and last.get("v") == version:
        return {**res, "state": "unchanged", "fingerprint": last.get("fp")}
    pub = ep.publish_event(int(ev["id"]), apply=apply, db_path=db_path)
    if pub.get("error"):
        return {**res, "state": "error", "why": pub["error"]}
    held = [h for r in pub.get("rounds") or [] for h in r.get("held") or []]
    res["published"] = (pub.get("summary") or {})
    if held:
        return {**res, "state": "waiting",
                "why": f"{len(held)} card(s) not final yet",
                "held": [{"name": h.get("name"), "reason": h.get("reason")} for h in held]}
    asm = db.assemble_event_game_payouts(name, db_path=db_path)
    if asm.get("error"):
        return {**res, "state": "error", "why": asm["error"]}
    rows = asm.get("rows") or []
    res.update(total=asm.get("total"), rows=len(rows), notes=asm.get("notes") or [])
    if not rows:
        return {**res, "state": "nothing", "why": "nothing determined to pay"}
    fp = fingerprint(rows)
    if last.get("fp") == fp:
        if apply:
            fps[str(ev["id"])] = {"fp": fp, "v": version}
            db.set_app_setting(FP_SETTING, json.dumps(fps, sort_keys=True), db_path)
        return {**res, "state": "unchanged", "fingerprint": fp}
    if not apply:
        return {**res, "state": "would_record", "fingerprint": fp,
                "payouts": [{k: r.get(k) for k in ("golferName", "category", "amount",
                                                   "description")} for r in rows]}
    rec = db.record_event_game_payouts(name, rows, force=True, db_path=db_path)
    if rec.get("error"):
        fps[str(ev["id"])] = {"fp": None, "v": version, "refused": rec["error"]}
        db.set_app_setting(FP_SETTING, json.dumps(fps, sort_keys=True), db_path)
        return {**res, "state": "refused", "why": rec["error"]}
    fps[str(ev["id"])] = {"fp": fp, "v": version}
    db.set_app_setting(FP_SETTING, json.dumps(fps, sort_keys=True), db_path)
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
