"""The personal results email (Kerry 10/13-14).

Run: python3 test_results_email.py
"""
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402
from email_parser import results_email as rx  # noqa: E402
from email_parser import event_day_email as ede  # noqa: E402
from email_parser.handicap_calc import ruled_dots  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {str(detail)[:600]}"))
    if not cond:
        FAILURES.append(label)


RECAP = "2026-10-13-s9.27-the-quarry-a9.27-forest-creek-v4.md"
tmp = tempfile.mktemp(suffix=".db")
db.init_db(tmp)
PARS = {10: 4, 11: 4, 12: 3, 13: 4, 14: 4, 15: 5, 16: 3, 17: 4, 18: 5}
SI = {10: 4, 11: 18, 12: 14, 13: 10, 14: 2, 15: 16, 16: 12, 17: 6, 18: 8}
c = sqlite3.connect(tmp)
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status, course) VALUES "
          "(3307, 's9.27 The Quarry', '2026-10-13', 'San Antonio', 'active', 'The Quarry Golf Club')")
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status, course, start_type, start_time, registration_url) VALUES "
          "(3301, 's9.28 TPC Canyons', '2026-10-20', 'San Antonio', 'active', 'TPC San Antonio - Canyons', 'Shotgun', '16:30', "
          "'https://thegolffellowship.com/shop/ols/products/s9-28-tpc-canyons')")
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status, course, registration_url) VALUES "
          "(3319, 'a9.28 Avery Ranch', '2026-10-20', 'Austin', 'active', 'Avery Ranch Golf Club', 'https://x/a9-28')")
c.execute("INSERT INTO courses (course_id, name) VALUES (7, 'The Quarry')")
c.execute("INSERT INTO course_tees (tee_id, course_id, tee_name) VALUES (1, 7, 'Gold')")
for h in PARS:
    c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) VALUES (1, ?, ?, ?, ?)",
              (h, PARS[h], 300 + h, SI[h]))
PEOPLE = [  # cid, first, last, chapter, status, email, played gross or None, ph
    (18, "Kerry", "Niester", "San Antonio", "active_member", "kerry@example.com", [5, 3, 4, 4, 5, 4, 4, 5, 7], 0),
    (298, "Dan", "Stich", "San Antonio", "active_member", "dan@example.com", [6, 6, 4, 4, 4, 8, 2, 4, 6], 6),
    (50, "Sam", "Home", "San Antonio", "active_member", "sam@example.com", None, None),
    (60, "Ann", "Austin", "Austin", "active_member", "ann@example.com", None, None),
    (70, "Ned", "Noemail", "San Antonio", "active_member", None, None, None),
]
for cid, f, l, ch, st, em, gross, ph in PEOPLE:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, current_player_status) "
              "VALUES (?, ?, ?, ?, ?)", (cid, f, l, ch, st))
    if em:
        c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?, ?, 1)", (cid, em))
    if gross:
        cur = c.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, holes_played, "
                        "gross, playing_handicap, source, tee_id, course_id) VALUES (?, ?, 3307, '2026-10-13', 9, ?, ?, "
                        "'entry', 1, 7)", (cid, f"{f} {l}", sum(gross), ph))
        dots = ruled_dots(ph, SI)
        for h, g in zip(PARS, gross):
            c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, strokes_received) "
                      "VALUES (?, ?, ?, ?)", (cur.lastrowid, h, g, int(dots.get(h, 0) or 0)))
c.execute("INSERT INTO tgf_events (id, code, name, event_date, events_id) VALUES (91, 's9.27', 's9.27 The Quarry', '2026-10-13', 3307)")
c.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, description) VALUES "
          "(91, 18, 'skins', 13, 'auto: Skins F1 ×1 holes 11')")
c.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, description) VALUES "
          "(91, 298, 'individual_net', 21, 'auto: Ind Net F2 place 1 (T)')")
c.commit()
c.close()

print("Building the message")
facts = rx.event_facts(3307, db_path=tmp)
k = rx.build_message(facts, {"customer_id": 18, "first_name": "Kerry", "name": "Kerry Niester"}, RECAP)
h = k["html"]
check("a player's email is clean (no blank, tag or None)", k["held"] == [], k["held"])
check("...is his own night: gross 41 on the Gold tees", ">41<" in h and "Gold tees · +5" in h, h[:2000])
check("...birdies listed with yardage", "a <b>3 on the 311-yard 11th</b>" in h, h[h.find("highlight"):][:300])
check("...his winnings from the recorded rows", "Skins · Flight 1 · hole 11" in h and "$13.00" in h)
check("...links go to the specific places",
      "/member/results/3307" in h and "/member/spotlight?player=18" in h)
check("...the San Antonio recap story, without its UP NEXT list", "first chapter night" in h and "UP NEXT." not in h)
check("...UP NEXT from the event rows with the start time", "TPC Canyons" in h and "4:30 PM shotgun" in h, h[h.find("UP NEXT"):][:600])
check("...not signed up yet, with the I'm in button", "You’re not signed up yet" in h and "I’m in for TPC Canyons" in h)
check("...signed by Kerry, see you next Tuesday", "See you next Tuesday!" in h and "Kerry Niester<br>The Golf Fellowship" in h)
d = rx.build_message(facts, {"customer_id": 298, "first_name": "Dan", "name": "Dan Stich"}, RECAP)
check("a player with pops shows them", "&#9679;" in d["html"] and "handicap pop" in d["html"])
check("a tie reads T1", "Individual Net · Flight 2 · T1" in d["html"], d["html"][d["html"].find("WINNINGS"):][:500])
s = rx.build_message(facts, {"customer_id": 50, "first_name": "Sam", "name": "Sam Home"}, RECAP)
check("a member who didn't play gets the recap and up next, no card",
      not s["played"] and "We missed you at" in s["html"] and "YOUR NIGHT" not in s["html"] and s["held"] == [], s["held"])

print("\nLint")
check("a blank is caught", rx.lint("<p>[__ count __] came</p>"))
check("an unrendered player link is caught", rx.lint("<p>[[Adam BAKER|87]]</p>"))
check("a leftover tag is caught", rx.lint("<p>Hi %first_name%</p>"))
check("clean text passes", rx.lint("<p>Good morning, Kerry!</p>") == [])

print("\nAudience")
a = rx.audience(3307, db_path=tmp)
ids = {p["customer_id"] for p in a["people"]}
check("players and the chapter's members, with an address", ids == {18, 298, 50}, a)
check("another chapter's member is left out", 60 not in ids, ids)
check("no email is counted, not sent", a["counts"]["excluded"]["no_email"] == 1, a["counts"])

print("\nPreview goes to staff or a manager's own address only")
check("a member's address is refused", rx._preview_allowed(["dan@example.com"], db_path=tmp) == ["dan@example.com"])
check("a staff address is allowed", rx._preview_allowed(["kerry@thegolffellowship.com"], db_path=tmp) == [])

print("\nGuards and the schedule")
sent = []
ede._graph_send = lambda creds, to, subj, html: sent.append((to, subj)) or True
ede._creds = lambda: ("t", "c", "s", "from@thegolffellowship.com")
r = rx.schedule_send([3307], "2026-10-14T06:00", RECAP, "test", db_path=tmp)
check("scheduled", r.get("scheduled") == "3307", r)
out = rx.auto_check(now=datetime(2026, 10, 14, 5, 59), db_path=tmp)
check("nothing before 6:00", out == {} and not sent, out)
out = rx.auto_check(now=datetime(2026, 10, 14, 6, 0), db_path=tmp)
check("at 6:00 the guards run first and hold (no score-entry rounds: not final)",
      out.get("3307", {}).get("state") == "held" and not sent, out)
sch = json.loads(db.get_app_setting(rx.SCHEDULE_KEY, tmp))
check("the hold is on the schedule and retried later, not every minute",
      sch["3307"]["state"] == "held" and rx.auto_check(now=datetime(2026, 10, 14, 6, 5), db_path=tmp) == {}, sch)
c = sqlite3.connect(tmp)
items = c.execute("SELECT COUNT(*) FROM action_items WHERE subject LIKE 'RESULTS EMAIL HELD%'").fetchone()[0]
c.close()
check("one HIGH COO item for the hold", items == 1, items)

# Guards cleared: deliver sends once per person.
rx.guards = lambda event_id, db_path=None: []
res = rx.deliver([3307], RECAP, confirm=True, db_path=tmp)
check("cleared guards: one email per person", res.get("sent") == 3 and len(sent) == 3, res)
res = rx.deliver([3307], RECAP, confirm=True, db_path=tmp)
check("never twice", res.get("sent") == 0 and res.get("already_sent") == 3 and len(sent) == 3, res)

m = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")).read()
check("bridge scoring-results-email exists, members only through a schedule",
      'cmd == "scoring-results-email"' in m and "_kerry_ok" in m[m.find('cmd == "scoring-results-email"'):][:3000])
a_ = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")).read()
check("the every-minute job is registered", 'id="results_email_auto"' in a_)

os.unlink(tmp)
print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
