"""A CONFIRMED CARD LOCKS, AND PAYOUTS RECORD THEMSELVES (Kerry 2026-10-13).

Kerry: "Payouts need to auto calculate and populate based on GAMES tabs
immediately after scores are all in" and "Time based. 15 minutes after
scorer confirms scorecard, it locks and is considered final
automatically".

- card_final_at: the latest submit + the lock minutes; an unlock voids
  earlier submits; no submit = never final.
- A final card refuses phone writes (refused_final, kept in se_audit) and
  publishes unsigned; an unlocked card takes writes again and is held.
- auto_payouts: waits while any card is held, records the assembled rows
  once, does nothing when they are unchanged, re-records when they change,
  and a dry run never writes.

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
chk = [{"group_id": 7, "at": "2026-10-14T01:00:00Z"}, {"group_id": 7, "at": "2026-10-14T01:05:00Z"},
       {"group_id": 8, "at": "2026-10-14T02:00:00Z"}]
check("latest submit + 15 minutes", se.card_final_at(chk, 7) == "2026-10-14T01:20:00Z",
      se.card_final_at(chk, 7))
check("no submit, never final", se.card_final_at(chk, 9) is None)
check("an unlock after the last submit voids it",
      se.card_final_at(chk, 7, {"7": "2026-10-14T01:06:00Z"}) is None)
check("a submit after the unlock starts the minutes over",
      se.card_final_at(chk, 7, {"7": "2026-10-14T01:02:00Z"}) == "2026-10-14T01:20:00Z")
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


for c in (301, 302):
    se.write_scores(gid, "dev", 301, ops(c, range(1, 10)), db_path=DB)

print("before the submit")
card = se.get_group_card(gid, "dev", db_path=DB)
check("not final, no final time", not card["final"] and card["final_at"] is None, card.get("final_at"))
pub = ep.publish_event(EV, db_path=DB)
check("both held (not submitted)", len(pub["rounds"][0]["held"]) == 2, pub["rounds"][0]["held"])
out = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("auto payouts wait while cards are held", out["state"] == "waiting", out)

print("submitted, inside the 15 minutes")
se.submit_card(gid, "dev", 301, print_scorer_name="Paper", db_path=DB)
card = se.get_group_card(gid, "dev", db_path=DB)
check("final time set, not final yet", card["final_at"] and not card["final"], card.get("final_at"))
check("lock minutes reported", card["lock_minutes"] == 15, card.get("lock_minutes"))
r = se.write_scores(gid, "dev", 301, ops(301, [1], 4), db_path=DB)
check("the scorer can still fix a score", r["results"][0]["result"] == "ok", r)
pub = ep.publish_event(EV, db_path=DB)
check("unsigned cards still held", len(pub["rounds"][0]["held"]) == 2, pub["rounds"][0]["held"])

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
check("both publish unsigned", len(pub["rounds"][0]["would_write"]) == 2 and not pub["rounds"][0]["held"],
      pub["rounds"][0]["held"])
grp = se.get_entered_scores(EV, db_path=DB)["rounds"][0]["groups"][0]
check("the read stamps the group final", grp["final"] is True and grp["final_at"], grp)

print("auto payouts")
CALLS = []
ROWS = [{"golferName": "Pat Youngs", "customer_id": 301, "category": "ctp", "amount": 23.0,
         "description": "CTP hole 16"}]
_real_asm, _real_rec = db.assemble_event_game_payouts, db.record_event_game_payouts
db.assemble_event_game_payouts = lambda name, db_path=None: {
    "rows": [dict(x) for x in ROWS], "notes": [], "total": sum(x["amount"] for x in ROWS)}


def _rec(name, rows, force=False, db_path=None):
    CALLS.append((name, len(rows), force))
    return {"payouts_added": len(rows)}


db.record_event_game_payouts = _rec
dry = ap.run(apply=False, event_id=EV, db_path=DB)["events"][0]
check("dry run says it would record", dry["state"] == "would_record", dry)
check("dry run writes nothing", not CALLS, CALLS)
check("dry run publishes nothing", sqlite3.connect(DB).execute(
    "SELECT COUNT(*) FROM scoring_rounds WHERE event_id = ?", (EV,)).fetchone()[0] == 0)
one = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("records once every card is final", one["state"] == "recorded" and len(CALLS) == 1, one)
check("re-record replaces auto rows (force)", CALLS and CALLS[0][2] is True, CALLS)
check("the final cards were published", sqlite3.connect(DB).execute(
    "SELECT COUNT(*) FROM scoring_rounds WHERE event_id = ?", (EV,)).fetchone()[0] == 2)
two = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("unchanged rows are not recorded again", two["state"] == "unchanged" and len(CALLS) == 1, two)
ROWS.append({"golferName": "Dan Stich", "customer_id": 302, "category": "skins", "amount": 10.0,
             "description": "Skins hole 3"})
with se._closing(se._conn(DB)) as _c:      # a card change (e.g. a CTP ruling) bumps the version
    se._bump(_c, EV)
    _c.commit()
three = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("changed rows re-record", three["state"] == "recorded" and len(CALLS) == 2, three)
fps = json.loads(db.get_app_setting(ap.FP_SETTING, DB) or "{}")
check("the fingerprint is kept per event", (fps.get(str(EV)) or {}).get("fp") == three["fingerprint"], fps)
ROWS.append({"golferName": "Pat Youngs", "customer_id": 301, "category": "skins", "amount": 5.0,
             "description": "Skins hole 4"})
four = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("no card change since the record: not re-run", four["state"] == "unchanged" and len(CALLS) == 2, four)

print("manager unlock")
db.set_app_setting(se.CARD_LOCK_SETTING, "15", DB)
se.unlock_card(gid, db_path=DB)
card = se.get_group_card(gid, "dev", db_path=DB)
check("unlocked card is not final", not card["final"] and card["final_at"] is None, card.get("final_at"))
r = se.write_scores(gid, "dev", 301, ops(301, [2], 3), db_path=DB)
check("the scorer can fix it again", r["results"][0]["result"] == "ok", r)
out = ap.run(apply=True, event_id=EV, db_path=DB)["events"][0]
check("payouts wait for the resubmit", out["state"] == "waiting" and len(CALLS) == 2, out)

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
