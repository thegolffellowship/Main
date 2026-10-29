"""THE CLOSEOUT CHAIN + THE RECAP WRITER (Kerry 2026-10-29, #2457 BUILD 1/2:
"Build both now for Saturday"). The chain runs in order, holds at the first
failed step (after a 30-minute grace) with one COO item, never re-runs a done
step, and writes the night's recap once every event of the night arrives;
the writer's draft is linted (blanks, unlinked names, unknown ids, stray
dollars) and re-asked once. The Claude call is mocked.

Run: python3 test_closeout_chain.py
"""
import os, sys, tempfile, logging, json
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-chain-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import database as db                        # noqa: E402
from email_parser import closeout_chain as cc                  # noqa: E402
from email_parser import recap_writer as rw                    # noqa: E402
from email_parser import recap_store as rs                     # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

db.init_db(DB)
with db._connect(DB) as c:
    db._ensure_scoring_tables(c)
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
              "VALUES (87, 'Adam', 'Baker', 'active_member')")
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
              "VALUES (88, 'Gus', 'Guest', 'active_guest')")
    e1 = c.execute("INSERT INTO events (item_name, event_date, course, chapter) VALUES "
                   "('s9.31 Test', '2026-10-31', 'Test GC', 'San Antonio')").lastrowid
    e2 = c.execute("INSERT INTO events (item_name, event_date, course, chapter) VALUES "
                   "('a9.31 Test', '2026-10-31', 'Test2 GC', 'Austin')").lastrowid
    c.execute("INSERT INTO scoring_rounds (player_name, customer_id, event_id, holes_played, "
              "playing_handicap, source, gross, net) VALUES ('Adam Baker', 87, ?, 9, 5, 'entry', 43, 38)", (e1,))
    c.commit()

print("== the facts (Tracker data only) ==")
f = rw.event_facts(e1, db_path=DB)
p = next((x for x in f["players"] if x["customer_id"] == 87), {})
check("a member is written as a Spotlight link", p.get("write_as") == "[[Adam BAKER|87]]", p)
check("section from the chapter", f["section"] == "SAN ANTONIO", f["section"])
nf = rw.night_facts([e1], db_path=DB)
check("known ids carry the night's players", 87 in nf["known_customer_ids"], nf["known_customer_ids"])

print("== the lint ==")
GOOD = ("# Recap DRAFTS — test\n\n## VERIFY BEFORE SENDING\n- ok\n\n---\n\n## SAN ANTONIO — s9.31 Test\n\n"
        "**Subject:** TGF Results | test\n\nGood Morning, %first_name%!\n\n**[[Adam BAKER|87]]** shot 43.\n")
check("a clean draft passes", rw.validate(GOOD, nf) == [], rw.validate(GOOD, nf))
bad = GOOD + "\n**Paul CLEARY** won $999 and [__blank__]. See [[Joe X|4444]].\n"
probs = " ".join(rw.validate(bad, nf))
check("an unlinked bold name is caught", "CLEARY" in probs, probs)
check("a dollar figure not in the facts is caught", "$999" in probs, probs)
check("a blank is caught", "blank" in probs, probs)
check("a link to an unknown customer id is caught", "4444" in probs, probs)
check("a missing section is caught",
      any("SAN ANTONIO" in x for x in rw.validate(GOOD.replace("## SAN ANTONIO", "## X"), nf)))

print("== the writer: re-asked once, then held ==")
calls = []
def fake(drafts):
    def _f(system, user, model_id):
        calls.append(user)
        return drafts[min(len(calls) - 1, len(drafts) - 1)]
    return _f
rw._client_create = fake([bad, GOOD])
res = rw.write_and_store([e1], db_path=DB)
check("second draft accepted after the problems are fed back",
      res["attempts"] == 2 and "FAILED THESE CHECKS" in calls[1], res)
check("stored as db:<date-key>", res["name"].startswith("db:2026-10-31"), res["name"])
check("recap_store reads it back", "Adam BAKER" in rs.read_text(res["name"], db_path=DB))
check("the house rules go in the system prompt",
      "Good Morning" in rw.build_prompt(nf)[0] or len(rw.build_prompt(nf)[0]) > 1000)
calls.clear()
rw._client_create = fake([bad])
try:
    rw.write([e1], db_path=DB)
    check("two failed drafts raise WriterError", False)
except rw.WriterError as exc:
    check("two failed drafts raise WriterError", "failed its checks" in str(exc), exc)

from email_parser import results_email as re_
s = re_.schedule_send([e1], re_.next_morning([e1], db_path=DB), res["name"], "test", db_path=DB)
check("the 6:00 AM send accepts a stored recap", s.get("at") == "2026-11-01T06:00", s)

print("== the chain ==")
order = []
FAIL = {"step": None}
def mk(name):
    def _s(ev, db_path=None):
        order.append((ev["id"], name))
        if FAIL["step"] == name:
            return False, "boom"
        return True, name
    return _s
for n in cc.STEPS:
    if n != "recap":
        cc.STEP_FN[n] = mk(n)
real_recap = cc.step_recap
written = []
def fake_write(ids, db_path=None):
    written.append(list(ids))
    return {"name": "db:2026-10-31-test", "model": "m", "attempts": 1, "sections": ["SAN ANTONIO", "AUSTIN"]}
rw.write_and_store = fake_write
from email_parser import recap_mail
drafts = []
recap_mail.send_recap_draft = lambda name, sec, **k: drafts.append((name, sec, k.get("dry_run"))) or {"status": "sent"}
scheduled = []
re_.schedule_send = lambda ids, at, name, why, db_path=None, who=None: scheduled.append((ids, at, name)) or {"at": at}
from email_parser import score_entry as se
se.event_enabled = lambda e, db_path=None: True

t0 = datetime(2026, 10, 31, 13, 0)
FAIL["step"] = "flights"
r = cc.run(e1, db_path=DB, now=t0)
check("inside the grace a failed step waits, no hold",
      r.get("waiting") == "boom" and not r.get("held"), r)
check("steps ran in order up to the failure",
      [n for _, n in order] == ["publish", "final", "payouts", "flights"], order)
order.clear()
r = cc.run(e1, db_path=DB, now=t0 + timedelta(minutes=40))
check("after the grace the step holds", (r.get("held") or {}).get("step") == "flights", r)
check("done steps are not re-run", [n for _, n in order] == ["flights"], order)
with db._connect(DB) as c:
    n = c.execute("SELECT COUNT(*) FROM action_items WHERE subject LIKE 'CLOSEOUT HELD:%'").fetchone()[0]
check("one COO item", n == 1, n)
cc.run(e1, db_path=DB, now=t0 + timedelta(minutes=45))
with db._connect(DB) as c:
    n = c.execute("SELECT COUNT(*) FROM action_items WHERE subject LIKE 'CLOSEOUT HELD:%'").fetchone()[0]
check("the same hold raises no second item", n == 1, n)
FAIL["step"] = None
r = cc.run(e1, db_path=DB, now=t0 + timedelta(minutes=50))
check("cleared: the chain continues and waits at the recap for the other event",
      r.get("at") == "recap" and "waiting" in (r.get("waiting") or "") and not written, r)
r2 = cc.run(e2, db_path=DB, now=t0 + timedelta(minutes=55))
check("the last event of the night writes the recap once",
      r2.get("at") == "done" and written == [[e1, e2]], (r2, written))
check("staff drafts for both sections, really sent",
      sorted(d[1] for d in drafts) == ["AUSTIN", "SAN ANTONIO"] and all(d[2] is False for d in drafts), drafts)
check("the 6:00 AM send is scheduled with the stored recap",
      scheduled and scheduled[-1][2] == "db:2026-10-31-test", scheduled)
r = cc.run(e1, db_path=DB, now=t0 + timedelta(minutes=60))
check("the first event finishes without a second recap",
      r.get("at") == "done" and len(written) == 1, (r, written))
check("tick does nothing once done", cc.tick_event(e1, db_path=DB) is None)
db.set_app_setting(cc.DIAL, "off", db_path=DB)
cc.reset(e1, db_path=DB)
check("the dial turns it off", cc.tick_event(e1, db_path=DB) is None)

src = open("email_parser/scoring_window.py", encoding="utf-8").read()
check("scoring_window.tick runs the chain after CLOSEOUT START", "closeout_chain" in src)
m = open("mcp_server.py", encoding="utf-8").read()
check("bridges exist", 'cmd == "scoring-closeout-chain"' in m and 'cmd == "scoring-recap-writer"' in m)

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
