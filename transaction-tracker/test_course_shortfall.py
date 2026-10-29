"""THE COURSE SHORTFALL EMAIL (Kerry 2026-10-28, Event Ops #2474-A, #2475-3,
#2476-1 "Approved"): a course charge over (played x course rate) by at least
half a player's rate -> one credit request to the course contact, manager and
Kerry CC'd. Teravista 10/27 ($433.00 at $54.13, 6 played) asks for 2 players;
Silverhorn ($1,169.10 at $48.71, 24 played, $0.06 over) sends nothing.

Run: python3 test_course_shortfall.py
"""
import os, sys, tempfile, logging, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-csf-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import database as db              # noqa: E402
from email_parser import course_shortfall as csf     # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

db.init_db(DB)
with db._connect(DB) as c:
    db._ensure_scoring_tables(c)
    try:   # production carries expense_transactions.event_id; a fresh test DB may not
        c.execute("ALTER TABLE expense_transactions ADD COLUMN event_id INTEGER")
    except Exception:
        pass
    tv = c.execute("INSERT INTO courses (name) VALUES ('Teravista Golf Club') RETURNING course_id").fetchone()[0]
    sh = c.execute("INSERT INTO courses (name) VALUES ('Silverhorn Golf Club') RETURNING course_id").fetchone()[0]
    sky = c.execute("INSERT INTO customers (first_name, last_name) VALUES ('Skyler', 'Morrow') RETURNING customer_id").fetchone()[0]
    c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?, 'skyler@teravista.example', 1)", (sky,))
    c.execute("INSERT INTO course_staff (course_id, customer_id, role, is_primary, active) VALUES (?, ?, 'tgf_contact', 1, 1)",
              (tv, sky))
    ev_tv = c.execute("INSERT INTO events (item_name, event_date, course, chapter, course_cost, course_id) "
                      "VALUES ('a9.29 Teravista', '2026-10-27', 'Teravista', 'Austin', 54.13, ?) RETURNING id",
                      (tv,)).fetchone()[0]
    ev_sh = c.execute("INSERT INTO events (item_name, event_date, course, chapter, course_cost, course_id) "
                      "VALUES ('s9.29 Silverhorn', '2026-10-27', 'Silverhorn', 'San Antonio', 48.71, ?) RETURNING id",
                      (sh,)).fetchone()[0]
    for i in range(6):
        cid = c.execute("INSERT INTO customers (first_name, last_name) VALUES ('P', ?) RETURNING customer_id",
                        (f"T{i}",)).fetchone()[0]
        c.execute("INSERT INTO scoring_rounds (player_name, customer_id, event_id, holes_played, source) "
                  "VALUES ('x', ?, ?, 9, 'entry')", (cid, ev_tv))
    for i in range(24):
        cid = c.execute("INSERT INTO customers (first_name, last_name) VALUES ('S', ?) RETURNING customer_id",
                        (f"H{i}",)).fetchone()[0]
        c.execute("INSERT INTO scoring_rounds (player_name, customer_id, event_id, holes_played, source) "
                  "VALUES ('y', ?, ?, 9, 'entry')", (cid, ev_sh))
    tv_row = c.execute("INSERT INTO expense_transactions (email_uid, source_type, merchant, amount, transaction_date, "
                       "transaction_type, category, event_name, review_status, event_id) VALUES "
                       "('u-2883', 'chase_alert', 'Teravista Golf Club', 433.0, '2026-10-27', 'expense', "
                       "'Course Fees', 'a9.29 Teravista', 'approved', ?) RETURNING id", (ev_tv,)).fetchone()[0]
    c.execute("INSERT INTO expense_transactions (email_uid, source_type, merchant, amount, transaction_date, "
              "transaction_type, category, event_name, review_status, event_id) VALUES "
              "('u-2882', 'chase_alert', 'Silverhorn Golf Club', 1169.1, '2026-10-27', 'expense', "
              "'Course Fees', 's9.29 Silverhorn', 'approved', ?)", (ev_sh,))
    # a meal on the same event is not a course charge
    c.execute("INSERT INTO expense_transactions (email_uid, merchant, amount, transaction_date, transaction_type, "
              "category, review_status, event_id) VALUES ('u-2884', 'Diner', 47.41, '2026-10-27', 'expense', "
              "'Meals & Entertainment', 'approved', ?)", (ev_sh,))
    c.commit()

print("the arithmetic")
b = csf.build(ev_tv, DB)
check("Teravista: charged 433.00, 6 played, expected 324.78, over 108.22",
      b["charged"] == 433.0 and b["played"] == 6 and b["expected"] == 324.78 and b["overcharge"] == 108.22, b)
check("charged for 8 players, credit for 2", b["charged_players"] == 8 and b["credit_players"] == 2, b)
check("Teravista would send", b["status"] == "would send", b.get("held"))
s = csf.build(ev_sh, DB)
check("Silverhorn: $0.06 over is under half a player, no email (Kerry #2475-3)",
      s["status"] == "within half a player" and abs(s["overcharge"] - 0.06) < 0.001 and "html" not in s, s)
check("the meal row is not counted as a course charge", len(s["charges"]) == 1)
half = csf.compute({"course_cost": 54.13}, [{"amount": 54.13 * 6 + 27.07, "id": 1}], [{"holes": 9}] * 6)
check("exactly half a player's rate sends", half["due"])
under = csf.compute({"course_cost": 54.13}, [{"amount": 54.13 * 6 + 27.0, "id": 1}], [{"holes": 9}] * 6)
check("a little under half does not", not under["due"])
combo = csf.compute({"course_cost_9": 30.0, "course_cost_18": 55.0},
                    [{"amount": 30 + 55 + 55, "id": 1}], [{"holes": 9}, {"holes": 18}])
check("a 9/18 combo prices each card by its holes (an unplayed 18 seat = $55 over)",
      combo["expected"] == 85.0 and combo["overcharge"] == 55.0 and combo["due"], combo)

print("the email (the approved mockup, #2475-3)")
check("subject", b["subject"] == "Credit request: The Golf Fellowship, Tuesday, October 27 (2 players)", b["subject"])
h = b["html"]
check("a thank-you line, then charged for 8 but 6 played",
      "Thanks for hosting The Golf Fellowship on Tuesday, October 27." in h
      and "We were charged for 8 players, but 6 played." in h
      and h.index("Thanks for hosting") < h.index("We were charged"))
check("a table: Date / Charged / Played / Credit requested",
      all(x in h for x in (">Date<", ">Charged<", ">Played<", ">Credit requested<"))
      and "$433.00" in h and "$108.22" in h)
check("then the reply line, then the signature",
      h.index("We were charged") < h.index("If we&#x27;ve missed something on our side, just reply.")
      < h.index("Kerry Niester"))
check("To the course contact; CC the chapter manager and Kerry",
      b["to"] == "skyler@teravista.example"
      and b["cc"] == ["robert@thegolffellowship.com", "kerry@thegolffellowship.com"], (b["to"], b["cc"]))

print("the dial, once per charge, holds")
r = csf.run_event(ev_tv, confirm=False, db_path=DB)
check("a dry run sends nothing", r.get("dry_run") and r["status"] == "would send")
sent = []
snd = lambda to, s_, h_, cc: sent.append((to, s_, cc)) or True   # noqa: E731
r = csf.run_event(ev_tv, confirm=True, db_path=DB, sender=snd)
check("dial OFF by default: nothing goes even with confirm", r["status"] == "off" and not sent, r)
check("the job does nothing while off", csf.check(today="2026-10-29", db_path=DB, sender=snd) == {"status": "off"})
db.set_app_setting("course_shortfall_email", "on", db_path=DB)
out = csf.check(today="2026-10-29", db_path=DB, sender=snd)
check("dial on: the job sends Teravista only", len(sent) == 1 and sent[0][0] == "skyler@teravista.example"
      and out["events"] == {ev_tv: "sent"}, (sent, out))
csf.check(today="2026-10-29", db_path=DB, sender=snd)
check("once per event per charge: the next run sends nothing", len(sent) == 1)
check("recorded with the charge ids", json.loads(db.get_app_setting(f"course_shortfall_sent:{ev_tv}", db_path=DB))
      ["charge_ids"] == [tv_row])
with db._connect(DB) as c:
    c.execute("INSERT INTO expense_transactions (email_uid, merchant, amount, transaction_date, transaction_type, "
              "category, review_status, event_id) VALUES ('u-cr', 'Teravista Golf Club', 108.22, '2026-10-30', "
              "'refund', 'Course Fees', 'approved', ?)", (ev_tv,))
    c.commit()
b2 = csf.build(ev_tv, DB)
check("a course credit on the same event counts against the charge (now even)",
      b2["status"] == "within half a player" and abs(b2["overcharge"]) < 0.01, b2)
with db._connect(DB) as c:
    c.execute("DELETE FROM course_staff")
    c.execute("DELETE FROM expense_transactions WHERE email_uid = 'u-cr'")
    c.execute("INSERT INTO expense_transactions (email_uid, merchant, amount, transaction_date, transaction_type, "
              "category, review_status, event_id) VALUES ('u-2', 'Teravista Golf Club', 54.13, '2026-10-28', "
              "'expense', 'Course Fees', 'approved', ?)", (ev_tv,))
    c.commit()
b3 = csf.build(ev_tv, DB)
check("a new charge re-checks; the COMPLETED event keeps its frozen contact even with course_staff emptied",
      b3["status"] == "would send" and b3["to"] == "skyler@teravista.example", (b3["status"], b3.get("to")))
with db._connect(DB) as c:
    c.execute("UPDATE events SET chapter = 'Nowhere' WHERE id = ?", (ev_tv,))
    c.commit()
b4 = csf.build(ev_tv, DB)
check("no chapter manager address HOLDS (a blank never sends)",
      b4["status"] == "held" and any("manager" in x for x in b4["held"]), b4.get("held"))
with db._connect(DB) as c:
    ev_new = c.execute("INSERT INTO events (item_name, event_date, course, chapter, course_cost, course_id) "
                       "VALUES ('a9.30 Teravista', '2026-11-03', 'Teravista', 'Austin', 54.13, ?) RETURNING id",
                       (tv,)).fetchone()[0]
    cid = c.execute("INSERT INTO customers (first_name, last_name) VALUES ('Z', 'Z') RETURNING customer_id").fetchone()[0]
    c.execute("INSERT INTO scoring_rounds (player_name, customer_id, event_id, holes_played, source) "
              "VALUES ('z', ?, ?, 9, 'entry')", (cid, ev_new))
    c.execute("INSERT INTO expense_transactions (email_uid, merchant, amount, transaction_date, transaction_type, "
              "category, review_status, event_id) VALUES ('u-n', 'Teravista Golf Club', 108.26, '2026-11-03', "
              "'expense', 'Course Fees', 'approved', ?)", (ev_new,))
    c.commit()
b5 = csf.build(ev_new, DB)
check("an upcoming event with no course contact on file HOLDS",
      b5["status"] == "held" and any("primary TGF contact" in x for x in b5["held"]), b5.get("held"))
check("a staff-only preview refuses a course address",
      "error" in csf.send_preview(ev_tv, "skyler@teravista.example", db_path=DB))

src = open("mcp_server.py").read()
check("bridge scoring-course-shortfall exists", 'cmd == "scoring-course-shortfall"' in src)
check("the job is on the scheduler", 'id="course_shortfall"' in open("app.py").read())
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
