"""THE NO-SHOW SCORER SEQUENCE, items 1-3 (Kerry 2026-09-30, mailbox #1021,
ratified; Pairings Spec v1.4 12.2; built 10/26 for 10/27).

Kerry 9/30: "on the first hole there needs to be an obvious red player
missing button at the bottom. Then that opens up a prompt of who it is.
Then follows up with the three answers" ... "It should ask each hole until
after 4 holes and then the player is taken off card." Kerry 10/26, for
both N's: "Both should be at 3p" -> 3 holes.

1. The scorer's answers: only the phone keeping score, only its own
   players; late / unknown / absent / present ("+ Player"); se_audit rows;
   "Don't know yet" counts holes and turns absent after N (dial
   no_show_absent_after_holes, default 3), and also once his group has
   scored N holes while he has none.
2. An absent player never holds the night: the card's final time, the
   entered-scores feed (no individual / MVP / points / handicap round from
   him), and his blank holes are never filled with par.
3. The course notice: one email per event after 3 holes, all names, manager
   CC'd, logged, once; "Running late" never counts; the dial stops it.
Plus the wiring: route, job, bridge, the red button on the hole screen.

Run: python3 test_no_show.py
"""
import contextlib
import io
import logging
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)
from email_parser import score_entry as se  # noqa: E402
from email_parser import no_show_notice as nsn  # noqa: E402
from email_parser import print_pack as pp  # noqa: E402
from email_parser import after_lock as al  # noqa: E402
from email_parser import pairings_approval as pa  # noqa: E402

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


conn = sqlite3.connect(DB)
for cid, fn, ln in [(401, "Sam", "Keeper"), (402, "Mo", "Late"), (403, "Ned", "Noshow"),
                    (404, "Al", "Unsure"), (411, "Other", "Scorer"), (412, "Ollie", "Other")]:
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
EV = 940
conn.execute("INSERT INTO events (id, item_name, event_date, chapter, course, status) "
             "VALUES (?, 's10.27 No Show Links', '2099-10-27', 'San Antonio', 'No Show Links', 'active')", (EV,))
conn.commit()
conn.close()
NINE = [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 10)]
rid = se.create_round(EV, 9, round_date="2099-10-27", label="s10.27", course_holes=NINE, db_path=DB)["round_id"]
gid = se.upsert_group(rid, 1, players=[
    {"customer_id": 401, "display_name": "Sam Keeper", "playing_handicap": 5},
    {"customer_id": 402, "display_name": "Mo Late", "playing_handicap": 8},
    {"customer_id": 403, "display_name": "Ned Noshow", "playing_handicap": 10},
    {"customer_id": 404, "display_name": "Al Unsure", "playing_handicap": 12}], db_path=DB)["group_id"]
gid2 = se.upsert_group(rid, 2, players=[
    {"customer_id": 411, "display_name": "Other Scorer", "playing_handicap": 3},
    {"customer_id": 412, "display_name": "Ollie Other", "playing_handicap": 4}], db_path=DB)["group_id"]
se.claim_group(gid, "dev1", 401, db_path=DB)
se.claim_group(gid2, "dev2", 411, db_path=DB)
_n = [0]


def ops(cid, holes, gross=5):
    out = []
    for h in holes:
        _n[0] += 1
        out.append({"op_id": f"ns{_n[0]}", "hole": h, "gross": gross, "customer_id": cid})
    return out


print("1. The scorer's button and questions")
r = se.mark_player_missing(gid, "dev2", 403, "absent", hole=1, db_path=DB)
check("another phone can't answer for this card", "error" in r, r)
r = se.mark_player_missing(gid2, "dev2", 403, "absent", hole=1, db_path=DB)
check("a scorer can't take a player off another card", "error" in r and "isn't on this card" in r["error"], r)
r = se.mark_player_missing(gid, "dev1", 403, "maybe", hole=1, db_path=DB)
check("only the three answers (and present)", "error" in r, r)
r = se.mark_player_missing(gid, "dev1", 403, "absent", hole=1, entered_by=401, db_path=DB)
check("No, take him off this card: absent", r.get("ok") and r["effective"] == "absent", r)
r = se.mark_player_missing(gid, "dev1", 402, "late", hole=1, db_path=DB)
check("Running late: stays on the card", r.get("ok") and r["effective"] == "late", r)
r = se.mark_player_missing(gid, "dev1", 404, "unknown", hole=1, db_path=DB)
check("Don't know yet: asked once", r.get("ok") and r["effective"] == "unknown", r)
se.mark_player_missing(gid, "dev1", 404, "unknown", hole=1, db_path=DB)
c = sqlite3.connect(DB)
asked = c.execute("SELECT holes_asked FROM se_no_shows WHERE customer_id = 404").fetchone()[0]
n_audit = c.execute("SELECT COUNT(*) FROM se_audit WHERE kind = 'no_show'").fetchone()[0]
c.close()
check("asking again on the same hole doesn't count twice", asked == 1, asked)
check("every answer is in se_audit", n_audit == 4, n_audit)
card = se.get_group_card(gid, "dev1", db_path=DB)
ns = {n["customer_id"]: n for n in card["no_shows"]}
check("the card carries the no-shows and N", set(ns) == {402, 403, 404} and card["no_show_after_holes"] == 3, card["no_shows"])
for h in (2,):
    se.mark_player_missing(gid, "dev1", 404, "unknown", hole=h, db_path=DB)
check("2 holes of don't know yet: still unknown",
      {n["customer_id"]: n for n in se.get_group_card(gid, "dev1", db_path=DB)["no_shows"]}[404]["effective"] == "unknown")
se.mark_player_missing(gid, "dev1", 404, "unknown", hole=3, db_path=DB)
check("after 3 holes he is off the card (Kerry 10/26)",
      {n["customer_id"]: n for n in se.get_group_card(gid, "dev1", db_path=DB)["no_shows"]}[404]["effective"] == "absent")
db.set_app_setting(se.NO_SHOW_HOLES_SETTING, "5", DB)
check("the dial sets N", se.no_show_after_holes(DB) == 5)
db.set_app_setting(se.NO_SHOW_HOLES_SETTING, "", DB)
check("blank dial: 3 (Kerry 10/26: \"Both should be at 3p\")", se.no_show_after_holes(DB) == 3)
r = se.mark_player_missing(gid, "dev1", 404, "present", hole=5, db_path=DB)
check("+ Player puts him back", r.get("ok") and r["effective"] == "present"
      and 404 not in {n["customer_id"] for n in se.get_group_card(gid, "dev1", db_path=DB)["no_shows"]}, r)
se.mark_player_missing(gid, "dev1", 404, "absent", hole=5, db_path=DB)

print("2. Absent players don't hold the night")
se.write_scores(gid, "dev1", 401, ops(401, range(1, 10)) + ops(402, range(1, 10), 6), db_path=DB)
card = se.get_group_card(gid, "dev1", db_path=DB)
check("blank holes of absent players don't hold the card's final time", card["final_at"] is not None, card.get("final_at"))
c = sqlite3.connect(DB)
filled = c.execute("SELECT COUNT(*) FROM se_hole_scores WHERE subject_key IN ('c:403','c:404')").fetchone()[0]
c.close()
check("never filled with par", filled == 0, filled)
rnd = se.get_entered_scores(EV, db_path=DB)["rounds"][0]
fed = {p["customer_id"] for p in rnd["players"]}
check("absent players leave the entered-scores feed (no individual, MVP, points, handicap)",
      403 not in fed and 404 not in fed and {401, 402} <= fed, fed)
check("the feed names them as absent", {a["customer_id"] for a in rnd["absent"]} == {403, 404}, rnd.get("absent"))
g1 = next(g for g in rnd["groups"] if g.get("group_id") == gid) if rnd.get("groups") and "group_id" in rnd["groups"][0] else None
if g1 is not None:
    check("the group goes final in the feed", g1.get("final_at") is not None, g1)

# A "don't know yet" with no scores turns absent once his group has scored N holes.
c = sqlite3.connect(DB)
for cid, fn in [(421, "Zed"), (422, "Quinn")]:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,'Three')", (cid, fn))
c.commit()
c.close()
gid3 = se.upsert_group(rid, 3, players=[
    {"customer_id": 421, "display_name": "Zed Three", "playing_handicap": 1},
    {"customer_id": 422, "display_name": "Quinn Three", "playing_handicap": 2}], db_path=DB)["group_id"]
se.claim_group(gid3, "dev3", 421, db_path=DB)
se.mark_player_missing(gid3, "dev3", 422, "unknown", hole=1, db_path=DB)
se.write_scores(gid3, "dev3", 421, ops(421, range(1, 3)), db_path=DB)
check("2 group holes, none of his: still unknown",
      se.get_group_card(gid3, "dev3", db_path=DB)["no_shows"][0]["effective"] == "unknown")
se.write_scores(gid3, "dev3", 421, ops(421, [3]), db_path=DB)
check("3 group holes, none of his: off the card even if no one answered again",
      se.get_group_card(gid3, "dev3", db_path=DB)["no_shows"][0]["effective"] == "absent")

print("3. The course notice")
pp.course_recipients_for_event = lambda ev, db_path=None: {"ok": True, "to": "pro@course.test",
                                                           "cc": ["shop@course.test"], "course_id": 1}
al._manager_cc = lambda chapter, db_path=None: "manager@thegolffellowship.com"
pa.manager_for = lambda chapter, db_path=None: {"name": "Kerry", "email": "manager@thegolffellowship.com"}
SENT = []


def fake(to, s, h, cc):
    SENT.append({"to": to, "subject": s, "html": h, "cc": cc})
    return True


b = nsn.build(EV, DB)
check("names every no-show whose group has played 3 holes, never the late player",
      b["names"] == ["Al Unsure", "Ned Noshow", "Quinn Three"], b["names"])
check("the wording", "No-shows today at No Show Links: Al Unsure, Ned Noshow and Quinn Three." in b["html"]
      and "Thanks,<br>Kerry" in b["html"], b["html"])
d = nsn.run_event(EV, confirm=False, db_path=DB, sender=fake)
check("dry run sends nothing", d["status"] == "would send" and not SENT, d)
r = nsn.check(now=datetime(2099, 10, 27, 16, 0), db_path=DB, sender=fake)
check("the job sends one email to the course", len(SENT) == 1 and SENT[0]["to"] == "pro@course.test", (r, SENT))
check("manager CC'd with the course's other contacts",
      SENT and "manager@thegolffellowship.com" in SENT[0]["cc"] and "shop@course.test" in SENT[0]["cc"], SENT)
nsn.check(now=datetime(2099, 10, 27, 16, 5), db_path=DB, sender=fake)
check("once per event", len(SENT) == 1, SENT)
c = sqlite3.connect(DB)
n_log = c.execute("SELECT COUNT(*) FROM message_log WHERE sent_by = 'no-show-notice'").fetchone()[0]
n_act = c.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type = 'no_show_notice'").fetchone()[0]
c.close()
check("logged", n_log == 1 and n_act == 1, (n_log, n_act))
db.set_app_setting(nsn.DIAL, "off", DB)
check("dial off stops it", nsn.check(now=datetime(2099, 10, 27, 16, 10), db_path=DB, sender=fake)["status"] == "off")
db.set_app_setting(nsn.DIAL, "", DB)
check("dial on by default, notice after 3 holes (Kerry 10/26)", nsn.dial_on(DB) and nsn.notice_holes(DB) == 3)

print("4. Wiring")
here = os.path.dirname(os.path.abspath(__file__))
_a = open(os.path.join(here, "app.py"), encoding="utf-8").read()
check("route /api/score-entry/missing", '"/api/score-entry/missing"' in _a and "mark_player_missing(" in _a)
check("the notice job is registered", 'id="no_show_notice"' in _a)
check("the read-only bridge", 'cmd == "scoring-no-show-notice"' in open(os.path.join(here, "mcp_server.py"), encoding="utf-8").read())
_t = open(os.path.join(here, "templates", "score_entry.html"), encoding="utf-8").read()
check("the red Player missing button sits in the hole screen's bottom bar",
      'data-act="missing">Player missing</button>' in _t and "se-missrow" in _t and "#B91C1C" in _t)
check("the three answers, word for word",
      "Running late, keep him on the card" in _t and "No, take him off this card" in _t and "Don't know yet" in _t)
check("Who's missing? and Is <Name> coming?", "Who's missing?" in _t and "Is ${esc(first(nm) || nm)} coming?" in _t)
check("+ Player on the absent chip", 'data-act="unmiss"' in _t and "+ Player" in _t)
check("Save leaves a late / not-here-yet player's hole blank", "!(s.cid != null && nsWaiting(s.cid))) draft[s.key] = h.par" in _t)
check("absent players leave the hole rows", "if (isAbsent(p.customer_id)) continue;" in _t)
mig = open(os.path.join(here, "migrations", "0040_se_no_shows.sql"), encoding="utf-8").read()
check("migration 0040: keyed by customer_id, portable", re.search(r"customer_id\s+INTEGER NOT NULL REFERENCES customers\(customer_id\)", mig)
      and "INSERT OR REPLACE" not in mig and "COLLATE NOCASE" not in mig)
check("the notice never queries se_* itself",
      "se_no_shows" not in open(os.path.join(here, "email_parser", "no_show_notice.py"), encoding="utf-8").read())

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
