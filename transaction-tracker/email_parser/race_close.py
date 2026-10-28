"""FALL RACE PRIZES AND CHAMPIONS AT THE FINALE (Kerry 2026-10-28, Event Ops
#2473): "Yes record fall prizes at closeout, City Net ladder - We're already
showing projected winnings." and "Tied titles split the winnings and the
title. That's The Golf Fellowship".

At the finale's CLOSEOUT START (scoring_window.tick), for each race the
finale ends (the SA and Austin Fall Nets for the Fall Championship):

  1. the finale's cards must have published and not be HELD (card parity),
     so its championship line is in the standings;
  2. the race is rebuilt from the Tracker (tracker_points) so the standings
     include the finale;
  3. the prizes are recorded as TGF PAYOUTS rows (unpaid, with the usual Pay
     buttons) from season_race_payout_rows: the City Net ladder on the same
     entrant count the board projects, tied places splitting their combined
     money (record_season_contest_payouts, code = the race label, which the
     board's recorded strip already reads);
  4. the race is declared final (app setting gg_points_race_final), so the
     board shows WON and names the champion(s): the best-ranked bought-in
     player(s), co-champions on a tie, never a tiebreak.

Anything that refuses holds that race, raises one COO item, and the next tick
tries again. Nothing is paid. Once done, `race_close_done:<event_id>` stops it.
Read-only bridge `scoring-race-close:<event_id>` shows what it would record;
`|apply` records (the same call the tick makes).
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

DONE_KEY = "race_close_done:{}"
FINALE_SETTING = "race_finales"   # optional {event_id: [race_key, ...]} override
CATEGORY = "Fall Net"


def finale_races(ev: dict, db_path=None) -> list:
    """The races this event ends. The app setting wins; otherwise a FALL
    CHAMPIONSHIP ends the Tracker's fall races."""
    from email_parser import database as db
    from email_parser import tracker_points as tp
    try:
        over = json.loads(db.get_app_setting(FINALE_SETTING, db_path=db_path) or "{}")
        if str(ev.get("id")) in over:
            return list(over[str(ev["id"])] or [])
    except Exception:
        logger.warning("race_finales setting unreadable", exc_info=True)
    name = (ev.get("item_name") or "").lower()
    if "fall championship" in name:
        return list(tp.TRACKER_RACES)
    return []


def _set_final(race_key: str, day: str, db_path=None) -> None:
    from email_parser import database as db
    raw = db.get_app_setting("gg_points_race_final", db_path=db_path)
    try:
        cur = json.loads(raw) if raw else {}
    except Exception:
        cur = {}
    cur[race_key] = day
    db.set_app_setting("gg_points_race_final", json.dumps(cur), db_path=db_path)


def _alarm(ev: dict, why: str, db_path=None) -> None:
    from email_parser import database as db
    try:
        db.save_action_item({
            "subject": f"RACE PRIZES HELD: {ev.get('item_name')}",
            "from_name": "Race close",
            "summary": ("The fall race prizes were not recorded at closeout.\n"
                        f"Why: {why}\nNothing is paid. The next scoring-window run "
                        "tries again once the cause is cleared."),
            "urgency": "high", "category": "scoring"}, db_path=db_path)
    except Exception:
        logger.exception("race close alarm failed")


def run(event_id: int, apply: bool = False, db_path=None) -> dict:
    """Record the races' prizes and declare their champions for one finale.
    Dry run (default) records nothing and shows the rows."""
    from email_parser import database as db
    from email_parser import tracker_points as tp
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    if not r:
        return {"error": f"no event {event_id}"}
    ev = dict(r)
    races = finale_races(ev, db_path=db_path)
    out = {"event_id": ev["id"], "event": ev["item_name"], "apply": apply, "races": []}
    if not races:
        out["note"] = "this event ends no race"
        return out
    if db.get_app_setting(DONE_KEY.format(ev["id"]), db_path=db_path):
        out["note"] = "already recorded"
        return out

    # 1. The finale must be IN the standings: published, not held.
    lines, warnings = tp.event_lines(db_path=db_path)
    held = [w for w in tp.held_events(warnings) if (ev["item_name"] or "\0") in w]
    counted = any(int(l.get("event_id") or 0) == ev["id"] for l in lines)
    if held:
        out["held"] = f"the finale's points are HELD ({held[0]})"
    elif not counted:
        out["held"] = "the finale's cards have not published into the points yet"
    if out.get("held"):
        if apply:
            _alarm(ev, out["held"], db_path)
        return out

    done_all = True
    for rk in races:
        row = {"race": rk}
        try:
            if apply:
                # 2. Rebuild from the Tracker so the finale is counted.
                db.refresh_points_race_standings(rk, db_path=db_path)
            pr = db.season_race_payout_rows(rk, db_path=db_path)
        except Exception as e:
            logger.exception("race close: %s failed", rk)
            row["error"] = str(e)
            done_all = False
            out["races"].append(row)
            continue
        if pr.get("error"):
            row["error"] = pr["error"]
            done_all = False
            out["races"].append(row)
            continue
        champs = db._race_champions([{**x, "enrolled": True, "player_name": x["golferName"]}
                                     for x in pr["rows"]])
        row.update(label=pr["label"], chapter=pr["chapter"], entrants=pr["n_pot"],
                   pot=pr["pot_cents"] / 100.0,
                   ladder=[a / 100.0 for a in pr["amounts_cents"]],
                   prizes=[{"customer_id": x["customer_id"], "name": x["golferName"],
                            "rank": x["rank"], "points": x["total_points"],
                            "amount": x["amount_cents"] / 100.0} for x in pr["rows"]],
                   champions=[c["player_name"] for c in champs])
        if apply:
            # 3. Record the prizes (refuses a second copy).
            payouts = [{"golferName": x["golferName"], "customer_id": x["customer_id"],
                        "category": CATEGORY, "amount": x["amount_cents"] / 100.0,
                        "description": f"auto: {pr['label']} final standings — {x['rank']} place"}
                       for x in pr["rows"] if x["amount_cents"] > 0]
            rec = db.record_season_contest_payouts(pr["label"], pr["chapter"], payouts,
                                                   append_category=CATEGORY, db_path=db_path)
            row["recorded"] = rec
            if rec.get("error") and "already" not in rec["error"]:
                done_all = False
                out["races"].append(row)
                continue
            # 4. Final: the board shows WON and names the champion(s).
            _set_final(rk, str(ev.get("event_date") or "")[:10], db_path=db_path)
        out["races"].append(row)

    if apply:
        if done_all:
            from email_parser.timezone_utils import now_central
            db.set_app_setting(DONE_KEY.format(ev["id"]), now_central().strftime("%Y-%m-%d %H:%M"),
                               db_path=db_path)
            db.log_agent_action("race-close", "race_prizes_recorded",
                                f"event {ev['id']} ({ev['item_name']}): "
                                + "; ".join(f"{x.get('label')}: champion(s) {', '.join(x.get('champions') or [])}, "
                                            f"{len(x.get('prizes') or [])} paid places"
                                            for x in out["races"]), db_path=db_path)
            _post(ev, out, db_path)
        else:
            _alarm(ev, "; ".join(f"{x['race']}: {x.get('error') or (x.get('recorded') or {}).get('error')}"
                                 for x in out["races"] if x.get("error") or (x.get("recorded") or {}).get("error")),
                   db_path)
    out["done"] = bool(apply and done_all)
    return out


def _post(ev: dict, out: dict, db_path=None) -> None:
    from email_parser import database as db
    parts = []
    for x in out["races"]:
        lines = "\n".join(f"  {p['rank']}  {p['name']}  {p['points']} pts  ${p['amount']:.2f}"
                          for p in x.get("prizes") or [])
        parts.append(f"{x.get('label')}: {x.get('entrants')} entrants, ${x.get('pot'):.2f} pot. "
                     f"Champion(s): {', '.join(x.get('champions') or []) or 'none'}.\n{lines}")
    body = ("TO: front-desk, Event Ops\nCC: kerry, tracker-claude (CFO)\n"
            f"FROM: the Tracker (race close), {ev['item_name']}.\n\n"
            "FALL RACE PRIZES RECORDED at CLOSEOUT START (Kerry 10/28: \"Yes record fall prizes "
            "at closeout, City Net ladder\"; ties split the money and the title). Unpaid rows "
            "with Pay buttons on Payouts; nothing is paid. The races are now final.\n\n"
            + "\n\n".join(parts))
    try:
        kw = {"db_path": db_path} if db_path else {}
        db.post_platform_dialogue_entry("tracker-claude", body, "closeout", **kw)
    except Exception:
        logger.exception("race close: mailbox post failed")
