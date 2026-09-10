"""TGF Insider auto-draft (mailbox #381 ratified, #453 routed, v2.369.0).

The Wednesday job fills docs/claude/templates/public-recap-template.html
from Tracker data and parks a Brevo DRAFT. Here: gather → compose →
render → lint on a two-chapter fixture, no network.

Run: python3 test_insider.py
"""

import os
import sys
import tempfile
from datetime import date

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
from email_parser import insider  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.executescript("""
            CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT);
            CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, event_date TEXT, course TEXT,
                chapter TEXT, start_time TEXT, registration_url TEXT, fellowship_spot TEXT, status TEXT);
            CREATE TABLE tgf_events (id INTEGER PRIMARY KEY, events_id INTEGER);
            CREATE TABLE tgf_payouts (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER,
                customer_id INTEGER, category TEXT, amount REAL, paid_at TEXT);
            INSERT INTO events VALUES (3306, 's9.22 Silverhorn', '2026-09-08', 'Silverhorn', 'San Antonio',
                NULL, NULL, 'the Silverhorn grill', 'active');
            INSERT INTO events VALUES (3313, 'a9.22 ShadowGlen', '2026-09-08', 'ShadowGlen', 'Austin',
                NULL, NULL, NULL, 'active');
            INSERT INTO events VALUES (3320, 's9.23 Canyon Springs', '2026-09-15', 'Canyon Springs', 'San Antonio',
                '17:30', 'https://thegolffellowship.com/product/s9-23/', NULL, 'active');
            INSERT INTO events VALUES (3321, 'a9.23 Teravista', '2026-09-15', 'Teravista', 'Austin',
                NULL, NULL, NULL, 'active');
            INSERT INTO events VALUES (3322, 's18.11 Forest Creek', '2026-09-26', 'Forest Creek', 'San Antonio',
                NULL, NULL, NULL, 'active');
            INSERT INTO events VALUES (3323, 'a18.05 Old Course', '2026-09-19', 'Old Course', 'Austin',
                NULL, NULL, NULL, 'cancelled');
            INSERT INTO events VALUES (3299, 's9.21 Old Round', '2026-09-01', 'Olmos', 'San Antonio',
                NULL, NULL, NULL, 'active');
            CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, event_id INTEGER,
                user_status TEXT, guest_name TEXT, transaction_status TEXT, customer TEXT);
            INSERT INTO items (customer_id, event_id, user_status, transaction_status) VALUES
                (1, 3306, 'MEMBER', 'active'), (2, 3306, '1st TIMER', 'active'), (3, 3306, 'MEMBER', 'active'),
                (4, 3306, '1st TIMER', 'active'), (7, 3306, 'MEMBER', 'active'),
                (5, 3313, 'MEMBER', 'active'), (6, 3313, '1st TIMER', 'active');
            INSERT INTO tgf_events VALUES (1, 3306);
            INSERT INTO tgf_events VALUES (2, 3313);
        """)
        db._ensure_scoring_tables(conn)
        db._ensure_gg_game_results_tables(conn)
        names = [(1, 'Robert', 'Rideout'), (2, 'Kannon', 'Bell'), (3, 'Ken', 'Carter'),
                 (4, 'Hector', 'Aguilera'), (5, 'Dan', 'Tarr'), (6, 'Luke', 'Mazanec'),
                 (7, 'Michele', 'Member')]
        conn.executemany("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", names)
        # Older round for 1, 3, 5 so only 2, 4, 6 are first-timers.
        for cid in (1, 3, 5):
            conn.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, "
                         "holes_played, playing_handicap) VALUES (?,?,3299,'2026-09-01',9,10)",
                         (cid, f"P{cid}"))
        # Silverhorn: 1,2,3,4 ; ShadowGlen: 5,6
        # 7 = a MEMBER-tagged registrant with no earlier card: NOT a first-timer.
        for cid, eid, ph in ((1, 3306, 4), (2, 3306, 18), (3, 3306, 12), (4, 3306, 9), (7, 3306, 11),
                             (5, 3313, 7), (6, 3313, 15)):
            conn.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, "
                         "holes_played, playing_handicap, gg_league_round_id) VALUES (?,?,?,'2026-09-08',9,?,?)",
                         (cid, f"P{cid}", eid, ph, "R1" if eid == 3306 else "R2"))
        # Payouts: Rideout + Bell (first-timer) at Silverhorn; Tarr at ShadowGlen.
        conn.executemany("INSERT INTO tgf_payouts (event_id, customer_id, category, amount) VALUES (?,?,?,?)",
                         [(1, 1, 'skins', 40), (1, 2, 'ctp', 20), (1, 1, 'net', 25), (2, 5, 'skins', 30)])
        conn.execute("INSERT INTO gg_game_results (event_id, gg_round_id, game, game_label, player_name, "
                     "detail, purse, chapter) VALUES (3306, 'R1', 'skins', 'Skins', 'Rideout, Robert', "
                     "'Bogey on 7', 40, 'San Antonio')")
        conn.commit()
    return p


db.get_hio_pot = lambda db_path=None: {"pot": 1175.0}

print("\n== 1. gather ==")
p = fresh_db()
data = insider.gather_week(db_path=p, as_of=date(2026, 9, 10))
evs = {e["chapter"]: e for e in data["events"]}
check("both chapters found, most recent only", set(evs) == {"San Antonio", "Austin"}
      and evs["San Antonio"]["name"] == "s9.22 Silverhorn", str([e["name"] for e in data["events"]]))
check("field = cards", evs["San Antonio"]["field"] == 5 and evs["Austin"]["field"] == 2)
check("cashed = distinct payout recipients", evs["San Antonio"]["cashed"] == 2
      and evs["Austin"]["cashed"] == 1)
firsts = sorted(f["short"] for e in data["events"] for f in e["first_timers"])
check("first-timers = played + tagged 1st TIMER, first name + last initial (Michele M. is MEMBER-tagged)",
      firsts == ["Hector A.", "Kannon B.", "Luke M."], str(firsts))
check("first-timer who cashed is marked", any(f["cashed"] and f["short"] == "Kannon B."
                                              for f in evs["San Antonio"]["first_timers"]))
check("results link uses the chapter page + gg round id",
      evs["San Antonio"]["results_url"] == "https://tgf-sa.golfgenius.com/pages/5783307?round_id=R1"
      and evs["Austin"]["results_url"] == "https://tgf-austin.golfgenius.com/pages/5790752?round_id=R2",
      str([e["results_url"] for e in data["events"]]))
check("skins story: bogey on 7", evs["San Antonio"]["skins_story"] == {"score": "bogey", "hole": 7,
                                                                        "player": "Rideout, Robert"},
      str(evs["San Antonio"]["skins_story"]))
check("next Tuesday per chapter, registration_url first then derived",
      data["next_tuesday"]["San Antonio"]["url"] == "https://thegolffellowship.com/product/s9-23/"
      and data["next_tuesday"]["Austin"]["label"] == "Teravista · Tue Sep 15"
      and "thegolffellowship.com" in data["next_tuesday"]["Austin"]["url"],
      str(data["next_tuesday"]))
check("Saturday 18s listed, cancelled skipped", [s["name"] for s in data["saturdays"]] == ["s18.11 Forest Creek"],
      str(data["saturdays"]))
check("HIO pot read", data["hio_pot"] == 1175.0)

print("\n== 2. compose + render + lint ==")
slots = insider.compose(data)
check("headline follows first-timer payday", slots["HEADLINE"] == "First round. First payday.", slots["HEADLINE"])
check("beat 2 names Kannon B. only by initial", "Kannon B." in slots["BEAT_2_BODY"]
      and "Bell" not in slots["BEAT_2_BODY"])
check("beat 2 counts the other first-timers who did not cash", "one of 3 first-timers" in slots["BEAT_2_BODY"],
      slots["BEAT_2_BODY"])
with db._connect(p) as conn:   # Hector A. (4) cashes too → "and so did 1 of the other 2"
    conn.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount) VALUES (1, 4, 'team', 12)")
    conn.commit()
_s2 = insider.compose(insider.gather_week(db_path=p, as_of=date(2026, 9, 10)))
check("beat 2 counts the other first-timers who cashed", "and so did 1 of the other 2 first-timers" in _s2["BEAT_2_BODY"],
      _s2["BEAT_2_BODY"])
check("beat 3 tells the bogey skin", "bogey" in slots["BEAT_3_LEAD"] and "7th" in slots["BEAT_3_BODY"],
      slots["BEAT_3_BODY"])
check("HIO pot formatted", slots["HIO_POT"] == "$1,175")
check("celebrate uses fellowship spot", "Silverhorn grill" in slots["CELEBRATE_PROOF"])
check("proper nouns keep their case", "San Antonio" in slots["BEAT_1_BODY"] and "Tuesday night" in slots["BEAT_2_BODY"]
      and "san antonio" not in slots["BEAT_1_BODY"], slots["BEAT_1_BODY"] + slots["BEAT_2_BODY"])
html_out = insider.render(slots)
problems = insider.lint(html_out)
check("lint clean", problems == [], str(problems))
check("no unfilled placeholders (Brevo merge tags like {{ contact.FIRSTNAME }} stay)",
      not __import__("re").findall(r"\{\{[A-Z0-9_]+\}\}", html_out) and "{{ unsubscribe }}" in html_out)
check("both RESULTS links present", html_out.count("round_id=") == 2)
check("Saturday 18 rendered bold city + date", "<strong>San Antonio · Sat Sep 26</strong>" in html_out)
check("offer line verbatim", "$25 off your first event, plus a drink on us." in html_out)

print("\n== 3. lint catches the rules ==")
bad = html_out.replace("Jump in any time.", "Our league purse is $500 this week in Houston.")
probs = insider.lint(bad)
check("banned words + stray dollars flagged",
      any("league" in x for x in probs) and any("purse" in x for x in probs)
      and any("Houston" in x for x in probs) and any("$500" in x for x in probs), str(probs))
check("unfilled slot flagged", "unfilled slot {{X}}" in insider.lint(html_out + "{{X}}"))

print("\n== 4. build: dry run never touches Brevo; empty window skips ==")
called = []
insider.create_brevo_draft = lambda *a, **k: called.append(a) or {"campaign_id": 1}
res = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=date(2026, 9, 10))
check("dry run returns html + subject", res["dry_run"] and res["html"].startswith("<!DOCTYPE")
      and res["subject"] == "TGF Insider | First round. First payday.", res.get("subject"))
check("dry run made no Brevo call", called == [])
res = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=date(2026, 10, 10))
check("no events in window → skipped", res.get("skipped"), str(res.get("skipped")))

print("\n== 4b. no store items → no-earlier-card fallback ==")
with db._connect(p) as conn:
    conn.execute("DELETE FROM items WHERE event_id = 3313")
    conn.commit()
d = insider.gather_week(db_path=p, as_of=date(2026, 9, 10))
aus = [e for e in d["events"] if e["chapter"] == "Austin"][0]
check("fallback finds Luke M. by first-ever card", [f["short"] for f in aus["first_timers"]] == ["Luke M."],
      str(aus["first_timers"]))

print("\n== 4c. review mode: preview to Kerry + mailbox, nothing in Brevo ==")
import email_parser.fetcher as _fetcher
sent = []
_fetcher.send_mail_graph = lambda **k: sent.append(k) or True
os.environ["AZURE_TENANT_ID"] = "t"; os.environ["AZURE_CLIENT_ID"] = "c"
os.environ["AZURE_CLIENT_SECRET"] = "s"; os.environ["EMAIL_ADDRESS"] = "tracker@tgf.test"
os.environ["COO_EMAIL_TO"] = "kerry@tgf.test"
with db._connect(p) as conn:
    conn.executescript("""CREATE TABLE IF NOT EXISTS message_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name TEXT, channel TEXT, recipient_name TEXT, recipient_address TEXT, subject TEXT,
        body_preview TEXT, status TEXT, sent_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);""")
    conn.commit()
res = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=date(2026, 9, 10))
rv = insider.send_review_preview(res, db_path=p)
check("preview emailed to Kerry with REVIEW subject", rv["emailed"] and sent and sent[0]["to_address"] == "kerry@tgf.test"
      and sent[0]["subject"].startswith("REVIEW: TGF Insider |"), str(rv))
check("preview body is the banner + the rendered Insider", "INSIDER DRAFT FOR REVIEW" in sent[0]["html_body"]
      and "$25 off your first event" in sent[0]["html_body"])
with db._connect(p) as conn:
    mb = conn.execute("SELECT topic, body FROM platform_dialogue ORDER BY id DESC LIMIT 1").fetchone()
check("mailbox post under insider-review names the beats", mb and mb[0] == "insider-review" and "Beat 2:" in mb[1],
      str(mb))
check("still no Brevo call", called == [])
check("mode defaults to review", insider.insider_mode(db_path=p) == "review")
os.environ["INSIDER_AUTODRAFT"] = "0"
check("INSIDER_AUTODRAFT=0 is off", insider.insider_mode(db_path=p) == "off")
del os.environ["INSIDER_AUTODRAFT"]

print("\n== 5. single-chapter week ==")
with db._connect(p) as conn:
    conn.execute("DELETE FROM scoring_rounds WHERE event_id = 3313")
    conn.commit()
data1 = insider.gather_week(db_path=p, as_of=date(2026, 9, 10))
slots1 = insider.compose(data1)
h1 = insider.render(slots1)
check("one chapter renders and lints clean", len(data1["events"]) == 1 and insider.lint(h1) == [],
      str(insider.lint(h1)))
check("Austin next-Tuesday still linked", "Teravista" in h1)

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL PASSED")
