"""PRIZE MONEY RUNS ITSELF; A CARD IS FINAL 15 MINUTES AFTER ITS LAST SCORE
(Kerry 2026-10-13).

Kerry: "Payouts need to auto calculate and populate based on GAMES tabs
immediately after scores are all in"; "15 minutes after last score entered
by each scorer"; "When last hole score is entered by last player in field,
won Columns should unhide and amounts should show but non-final until 15
minutes have passed".

- card_final_at: last score + the lock minutes, only on a complete card;
  an unlock later than the last score moves it.
- A final card refuses phone writes (refused_final, kept in se_audit) and
  publishes without a submit or signatures; an unlocked card takes writes.
- auto_payouts: waits (writes nothing) while any hole is out; once the
  field is in, publishes provisionally and stores the board preview marked
  not final; records once every card is final, never again while
  unchanged, again when the cards change; a dry run never writes.

Run: python3 test_auto_payouts.py
"""
import contextlib
import io
import json
import logging
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)
from email_parser import score_entry as se  # noqa: E402
from email_parser import entry_publish as ep  # noqa: E402
from email_parser import auto_payouts as ap  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


print("card_final_at (pure)")
check("last score + 15 minutes",
      se.card_final_at("2026-10-14T01:05:00Z", True) == "2026-10-14T01:20:00Z",
      se.card_final_at("2026-10-14T01:05:00Z", True))
check("an incomplete card is never final", se.card_final_at("2026-10-14T01:05:00Z", False) is None)
check("no score, never final", se.card_final_at(None, True) is None)
check("an unlock after the last score moves it",
      se.card_final_at("2026-10-14T01:05:00Z", True, "2026-10-14T01:30:00Z") == "2026-10-14T01:45:00Z")
check("an older unlock changes nothing",
      se.card_final_at("2026-10-14T01:05:00Z", True, "2026-10-14T01:00:00Z") == "2026-10-14T01:20:00Z")
check("final once the time has passed",
      se.card_is_final("2026-10-14T01:20:00Z", "2026-10-14T01:20:00Z")
      and not se.card_is_final("2026-10-14T01:20:00Z", "2026-10-14T01:19:59Z"))

conn = sqlite3.connect(DB)
for cid, fn, ln in [(301, "Pat", "Youngs"), (302, "Dan", "Stich")]:
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)",
                 (cid, fn, ln))
course_id = conn.execute("INSERT INTO courses (name, status) VALUES ('Lock Links', 'active') "
                         "RETURNING course_id").fetchone()[0]
conn.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, slope, "
             "tgf_bands, source) VALUES (?, 'White', 'M', 9, 'front', 34.0, 120, '50-64', 'admin')",
             (course_id,))
EV = 930
conn.execute("INSERT INTO events (id, item_name, event_date, course_id) VALUES (?,?,?,?)",
             (EV, "s10.13 Lock Links", "2026-10-13", course_id))
conn.commit()
conn.close()
NINE = [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 10)]
rid = se.create_round(EV, 9, round_date="2026-10-13", label="s10.13", course_holes=NINE,
                      course_id=course_id, db_path=DB)["round_id"]
gid = se.upsert_group(rid, 1, players=[
    {"customer_id": 301, "display_name": "Pat Y", "tee": "50-64", "playing_handicap": 2},
    {"customer_id": 302, "display_name": "Dan S", "tee": "50-64", "playing_handicap": 6}],
    db_path=DB)["group_id"]
se.claim_group(gid, "dev", 301, db_path=DB)
_n = [0]


def ops(cid, holes, gross=5):
    out = []
    for h in holes:
        _n[0] += 1
        out.append({"op_id": f"lk{_n[0]}", "hole": h, "gross": gross, "customer_id": cid})
    return out


CALLS = []
ROWS = [{"golferName": "Pat Youngs", "category": "team_net", "amount": 23.0,
         "description": "TEAM Net 1st (team split)"}]
_real_asm, _real_rec = db.assemble_event_game_payouts, db.record_event_game_payouts
db.assemble_event_game_payouts = lambda name, db_path=None: {
    "rows": [dict(x) for x in ROWS], "notes": [], "total": sum(x["amount"] for x in ROWS)}


def _rec(name, rows, force=False, db_path=None):
    CALLS.append((name, len(rows), force))
    return {"payouts_added": len(rows)}


db.record_event_game_payouts = _rec
check("recording is off unless the dial says on", ap.record_enabled(DB) is False)


def n_rounds():
    return sqlite3.connect(DB).execute(
        "SELECT COUNT(*) FROM scoring_rounds WHERE event_id = ?", (EV,)).fetchone()[0]


print("mid-round")
se.write_scores(gid, "dev", 301, ops(301, range(1, 10)), db_path=DB)
se.write_scores(gid, "dev", 301, ops(302, range(1, 9)), db_path=DB)
card = se.get_group_card(gid, "dev", db_path=DB)
check("a card with a blank hole has no final time", card["final_at"] is None and not card["final"], card.get("final_at"))
out = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("money waits while a hole is out", out["state"] == "waiting", out)
check("nothing published mid-round", n_rounds() == 0)
check("no preview mid-round", ap.preview_for(EV, DB) is None)

print("the last hole of the field is in")
se.write_scores(gid, "dev", 301, ops(302, [9]), db_path=DB)
card = se.get_group_card(gid, "dev", db_path=DB)
check("final time set 15 minutes out, not final yet", card["final_at"] and not card["final"], card.get("final_at"))
check("lock minutes reported", card["lock_minutes"] == 15, card.get("lock_minutes"))
r = se.write_scores(gid, "dev", 301, ops(301, [1], 4), db_path=DB)
check("the scorer can still fix a score", r["results"][0]["result"] == "ok", r)
dry = ap.run(apply=False, event_id=EV, db_path=DB)["events"][0]
check("dry run says provisional and writes nothing",
      dry["state"] == "provisional" and n_rounds() == 0 and ap.preview_for(EV, DB) is None, dry)
out = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("money shows now, not final", out["state"] == "provisional" and out["final"] is False, out)
pv = ap.preview_for(EV, DB)
check("the preview carries the rows, not final, with a final time",
      pv and pv["final"] is False and pv["final_at"] and len(pv["rows"]) == 1, pv)
check("a team split gets its customer_id from the field", pv and pv["rows"][0]["customer_id"] == 301, pv)
check("cards published provisionally", n_rounds() == 2)
_ev_list = {e["id"]: e for e in (db.get_events_leaderboard(db_path=DB) or {}).get("events") or []}
check("the events list shows the pot from the GAMES money before anything is recorded",
      (_ev_list.get(EV) or {}).get("pot") == 23.0, _ev_list.get(EV))
check("nothing recorded before final", not CALLS, CALLS)
again = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("no re-run while unchanged and not yet final", again["state"] == "unchanged", again)

print("15 minutes later (dial at 0): final")
db.set_app_setting(se.CARD_LOCK_SETTING, "0", DB)
card = se.get_group_card(gid, "dev", db_path=DB)
check("the card is final", card["final"] is True, card)
r = se.write_scores(gid, "dev", 301, ops(301, [2], 3), db_path=DB)
check("a phone write is refused as final", r.get("final") and r["results"][0]["result"] == "refused_final", r)
c = sqlite3.connect(DB)
kept = c.execute("SELECT result FROM se_audit WHERE op_id = ?", (r["results"][0]["op_id"],)).fetchone()
hole2 = c.execute("SELECT gross FROM se_hole_scores WHERE group_id = ? AND subject_key = 'c:301' "
                  "AND hole_number = 2", (gid,)).fetchone()
c.close()
check("the refused write is kept for the manager", kept and kept[0] == "refused_final", kept)
check("the card is unchanged", hole2 and hole2[0] == 5, hole2)
pub = ep.publish_event(EV, db_path=DB)
check("final cards publish with no submit or signature",
      len(pub["rounds"][0]["would_write"]) == 2 and not pub["rounds"][0]["held"], pub["rounds"][0]["held"])
grp = se.get_entered_scores(EV, db_path=DB)["rounds"][0]["groups"][0]
check("the read stamps the group final", grp["final"] is True and grp["final_at"], grp)
off = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("record dial off: final money shows, nothing recorded",
      off["state"] == "final_display_only" and not CALLS
      and (ap.preview_for(EV, DB) or {}).get("final") is True, off)
db.set_app_setting(ap.RECORD_DIAL, "on", DB)
check("the dial alone records nothing before 10/20 (CoS #1797)",
      ap.record_enabled(DB) and not ap.record_enabled(DB, "2026-10-13")
      and ap.record_enabled(DB, "2026-10-20"))
early = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("a 10/13 event stays display only with the dial on",
      early["state"] in ("final_display_only", "unchanged") and not CALLS, early)
db.set_app_setting(ap.RECORD_FROM, "2026-10-01", DB)
nxt = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("display-only is not sticky once recording is allowed for the event",
      nxt["state"] == "recorded" and len(CALLS) == 1, nxt)
CALLS.clear()
db.set_app_setting(ap.FP_SETTING, "{}", DB)
with se._closing(se._conn(DB)) as _c:
    se._bump(_c, EV)
    _c.commit()
one = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("records once every card is final", one["state"] == "recorded" and len(CALLS) == 1, one)
check("re-record replaces auto rows (force)", CALLS and CALLS[0][2] is True, CALLS)
check("the preview turns final", (ap.preview_for(EV, DB) or {}).get("final") is True)
two = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("unchanged: not recorded again", two["state"] == "unchanged" and len(CALLS) == 1, two)
ROWS.append({"golferName": "Dan Stich", "customer_id": 302, "category": "skins", "amount": 10.0,
             "description": "Skins hole 3"})
with se._closing(se._conn(DB)) as _c:      # a card change (e.g. a CTP ruling) bumps the version
    se._bump(_c, EV)
    _c.commit()
three = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("changed rows re-record", three["state"] == "recorded" and len(CALLS) == 2, three)
st = json.loads(db.get_app_setting(ap.FP_SETTING, DB) or "{}").get(str(EV)) or {}
check("the fingerprint is kept per event", st.get("fp") == three["fingerprint"], st)
ROWS.append({"golferName": "Pat Youngs", "customer_id": 301, "category": "skins", "amount": 5.0,
             "description": "Skins hole 4"})
four = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("no card change since the record: not re-run", four["state"] == "unchanged" and len(CALLS) == 2, four)

print("holds the verifier relies on (CoS #1797)")
_n_calls = len(CALLS)
_ver = lambda: (se._bump(_c2 := se._conn(DB), EV), _c2.commit(), _c2.close())
ap.hold(EV, "flight 2 tie needs a ruling", by="closeout", db_path=DB)
_ver()
h1 = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("a verifier hold stops the record", h1["state"] == "held" and len(CALLS) == _n_calls, h1)
check("the hold reaches Kerry as a COO item",
      sqlite3.connect(DB).execute("SELECT COUNT(*) FROM action_items WHERE subject LIKE "
                                  "'PAYOUTS HELD:%'").fetchone()[0] >= 1)
h2 = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("held: not re-run every minute", h2["state"] == "unchanged" and len(CALLS) == _n_calls, h2)
ap.release(EV, by="kerry", db_path=DB)
h3 = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("release: records on the next run", h3["state"] == "recorded" and len(CALLS) == _n_calls + 1, h3)

_real_holders = se.event_ctp_holders
se.event_ctp_holders = lambda eid, db_path=None: [
    {"hole": 7, "kind": "ctp", "customer_id": 302, "name": "Dan S",
     "needs_confirm": {"from": {"name": "Pat Y", "group_num": 2},
                       "to": {"name": "Dan S", "group_num": 1}}}]
_ver()
c1 = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("an unconfirmed CTP takeover holds the record", c1["state"] == "held"
      and "hole 7" in c1["why"] and len(CALLS) == _n_calls + 1, c1)
dry = ap.run(apply=False, event_id=EV, db_path=DB)["events"][0]
check("the dry run reports the same hold", dry["state"] == "held", dry)
se.event_ctp_holders = _real_holders
_ver()                                       # the manager's confirm bumps the version
c2 = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("confirmed: records", c2["state"] in ("recorded", "unchanged"), c2)

_good_rec = db.record_event_game_payouts
db.record_event_game_payouts = lambda name, rows, force=False, db_path=None: {
    "error": "2 manually recorded payout(s) exist for this event"}
ROWS.append({"golferName": "Dan Stich", "customer_id": 302, "category": "ctp", "amount": 7.0,
             "description": "CTP hole 7"})
_ver()
r1 = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("a refused record is reported", r1["state"] == "refused" and "manually" in r1["why"], r1)
r2 = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("refused: waits for a change or 15 minutes", r2["state"] == "unchanged", r2)
st = json.loads(db.get_app_setting(ap.FP_SETTING, DB))[str(EV)]
st["retry_at"] = "2000-01-01T00:00:00Z"
db.set_app_setting(ap.FP_SETTING, json.dumps({str(EV): st}), DB)
db.record_event_game_payouts = _good_rec
r3 = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("refused: retried after 15 minutes with no card change", r3["state"] == "recorded", r3)

print("manager unlock")
_n_unlock = len(CALLS)
db.set_app_setting(se.CARD_LOCK_SETTING, "15", DB)
se.unlock_card(gid, db_path=DB)
card = se.get_group_card(gid, "dev", db_path=DB)
check("unlocked card is not final", not card["final"], card.get("final_at"))
r = se.write_scores(gid, "dev", 301, ops(301, [2], 3), db_path=DB)
check("the scorer can fix it again", r["results"][0]["result"] == "ok", r)
out = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("money shows again, not final", out["state"] == "provisional" and len(CALLS) == _n_unlock, out)

print("dial")
db.set_app_setting(ap.DIAL, "off", DB)
check("dial off: the job does nothing", ap.run(apply=True, db_path=DB).get("skipped"))
db.assemble_event_game_payouts, db.record_event_game_payouts = _real_asm, _real_rec

print("source guards")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "email_parser", "auto_payouts.py")).read()
check("auto_payouts never names a score-entry table",
      not any(t in src for t in ("se_hole_scores", "se_card_checks", "se_rounds", "se_players")))
check("auto_payouts records through record_event_game_payouts only",
      "INSERT" not in src and "tgf_payouts" not in src.replace("auto_payouts", ""))

print()
print("ALL PASS" if not FAILURES else f"{len(FAILURES)} FAILURE(S)")
sys.exit(1 if FAILURES else 0)
