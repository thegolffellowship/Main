"""THE BETTER-DIFFERENTIAL RULE (Kerry 10/28, Event Ops #2479/#2480, CoS #2505):
a new player on a temporary handicap who shoots a better differential drops to
it at once (the Adam Wilson step: a nine x 2), only down, only until 27 holes
are posted.

Run: python3 test_better_diff.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-bd-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import database as db      # noqa: E402
from email_parser import better_diff as bd   # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

db.init_db(DB)
with db._connect(DB) as c:
    db._ensure_scoring_tables(c)
    for cid, f, l, st in ((846, "Adam", "Wilson", 9.4), (847, "Slow", "Guy", 9.4), (848, "Old", "Hand", 9.4)):
        c.execute("INSERT INTO customers (customer_id, first_name, last_name, starting_handicap_18) VALUES (?,?,?,?)",
                  (cid, f, l, st))
    eid = c.execute("INSERT INTO events (item_name, event_date) VALUES ('s9.28 TPC Canyons', '2026-10-20') RETURNING id").fetchone()[0]
    def card(cid, diffs):
        rid = c.execute("INSERT INTO scoring_rounds (player_name, customer_id, event_id, holes_played, source) "
                        "VALUES ('x', ?, ?, ?, 'entry') RETURNING id", (cid, eid, 9 * len(diffs))).fetchone()[0]
        for d in diffs:
            c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential, "
                      "scoring_round_id, customer_id) VALUES (?, '2026-10-20', 38, 34.7, 122, ?, ?, ?)",
                      (f"p{cid}", d, rid, cid))
    card(846, [3.1])          # Wilson: 3.1 for 9 -> 6.2 < 9.4
    card(847, [6.0])          # 12.0 > 9.4: no change
    card(848, [2.0])
    for _ in range(3):        # 848 already has 27 holes on file: established
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential, customer_id) "
                  "VALUES ('p848', '2026-09-01', 40, 34.7, 122, 5.0, 848)")
    c.commit()

p = bd.plan([eid], DB)
check("Wilson: a nine x 2, 3.1 -> 6.2 beats 9.4", [(x["customer_id"], x["was"], x["now"]) for x in p] == [(846, 9.4, 6.2)], p)
check("a worse round changes nothing; an established player is left to his index",
      not any(x["customer_id"] in (847, 848) for x in p))
r = bd.after_post(["s9.28 TPC Canyons"], DB)
with db._connect(DB) as c:
    row = c.execute("SELECT starting_handicap_18, starting_handicap_set_by, starting_handicap_note FROM customers "
                    "WHERE customer_id = 846").fetchone()
check("applied at the post, set by the rule, the note names the event",
      row[0] == 6.2 and row[1] == "rule:better_differential" and "TPC Canyons" in row[2], tuple(row))
check("only down: running it again changes nothing", bd.plan([eid], DB) == [])
with db._connect(DB) as c:
    eid2 = c.execute("INSERT INTO events (item_name, event_date) VALUES ('s18 X', '2026-10-31') RETURNING id").fetchone()[0]
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, starting_handicap_18) VALUES (849, 'Two', 'Nines', 12.0)")
    rid = c.execute("INSERT INTO scoring_rounds (player_name, customer_id, event_id, holes_played, source) "
                    "VALUES ('y', 849, ?, 18, 'entry') RETURNING id", (eid2,)).fetchone()[0]
    for d in (4.0, 5.0):
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential, "
                  "scoring_round_id, customer_id) VALUES ('p849', '2026-10-31', 40, 34.7, 122, ?, ?, 849)", (d, rid))
    c.commit()
p2 = bd.plan([eid2], DB)
check("an 18 as two nines: the nines summed (4.0 + 5.0 = 9.0 < 12.0)",
      p2 and p2[0]["now"] == 9.0, p2)
db.set_app_setting("better_differential_rule", "off", db_path=DB)
check("the dial turns it off", bd.apply_for_events([eid2], db_path=DB).get("skipped"))
src = open("email_parser/database.py").read()
check("both posting paths call it", src.count("from email_parser.better_diff import after_post") == 2)
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
