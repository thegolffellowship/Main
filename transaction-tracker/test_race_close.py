"""FALL RACE PRIZES + CHAMPIONS AT THE FINALE (Kerry 2026-10-28, #2473: "Yes
record fall prizes at closeout, City Net ladder" / "Tied titles split the
winnings and the title"). The finale's CLOSEOUT START records each fall race's
prizes as unpaid payout rows on the race label, declares the race final, and
names co-champions on a tie. Unpublished or HELD finale: nothing recorded, a COO
item. Second run: nothing twice.

Run: python3 test_race_close.py
"""
import os, sys, tempfile, logging, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                           # noqa: E402
from email_parser import tracker_points as tp                     # noqa: E402
from email_parser import race_close as rc                          # noqa: E402
from email_parser import cup_titles as ct                          # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


with db._connect(DB) as c:
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format) "
              "VALUES (3305,'s18.12 FALL CHAMPIONSHIP | Kissing Tree','2026-10-31','TGF','active','18 Holes')")
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format) "
              "VALUES (3303,'s9.29 SILVERHORN','2026-10-27','San Antonio','active','9 Holes')")
    for cid, fn, ln in ((87, "Adam", "Baker"), (6, "Jeff", "Rideout"), (82, "Luke", "Mazanec"),
                        (13, "Luke", "Youngs"), (438, "Chris", "Cannon")):
        c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
    c.commit()

# SA: Baker and Rideout tie for 1st (co-champions, split $240 + $180), 15 entrants.
SA = [{"customer_id": 87, "golferName": "Adam Baker", "rank": "T1", "total_points": 70},
      {"customer_id": 6, "golferName": "Jeff Rideout", "rank": "T1", "total_points": 70},
      {"customer_id": 82, "golferName": "Luke Mazanec", "rank": "3", "total_points": 60}]
AU = [{"customer_id": 13, "golferName": "Luke Youngs", "rank": "1", "total_points": 66},
      {"customer_id": 438, "golferName": "Chris Cannon", "rank": "2", "total_points": 50}]


def fake_rows(rk, db_path=None):
    from email_parser import season_payouts as sp
    rows, n = (SA, 15) if rk == "san_antonio_fall_net" else (AU, 4)
    pp = sp.city_net_payouts(n)
    return {"race": rk, "label": "SAN ANTONIO Fall Net 2026" if rk == "san_antonio_fall_net" else "AUSTIN Fall Net 2026",
            "chapter": "San Antonio" if rk == "san_antonio_fall_net" else "Austin",
            "race_final": False, "n_pot": n, "pot_cents": pp["pot_cents"], "n_places": len(pp["amounts_cents"]),
            "amounts_cents": pp["amounts_cents"], "rows": db._split_down_ladder(rows, pp["amounts_cents"])}


refreshed = []
_r = (tp.event_lines, db.season_race_payout_rows, db.refresh_points_race_standings)
db.season_race_payout_rows = fake_rows
db.refresh_points_race_standings = lambda rk, db_path=None: refreshed.append(rk) or 0
try:
    check("a Fall Championship ends both fall races", rc.finale_races({"id": 3305, "item_name": "s18.12 FALL CHAMPIONSHIP"})
          == list(tp.TRACKER_RACES))
    check("a Tuesday nine ends none", rc.finale_races({"id": 3303, "item_name": "s9.29 SILVERHORN"}) == [])

    tp.event_lines = lambda db_path=None, through=None: ([], [])
    r = rc.run(3305, apply=True, db_path=DB)
    check("finale not published yet: held, nothing recorded", "not published" in (r.get("held") or "")
          and not r.get("done"), r)
    tp.event_lines = lambda db_path=None, through=None: ([{"event_id": 3305}], ["HELD s18.12 FALL CHAMPIONSHIP | Kissing Tree: parity"])
    r = rc.run(3305, apply=True, db_path=DB)
    check("finale HELD by card parity: held", "HELD" in (r.get("held") or ""), r)
    with db._connect(DB) as c:
        n_items = c.execute("SELECT COUNT(*) FROM action_items WHERE subject LIKE 'RACE PRIZES HELD%'").fetchone()[0]
    check("a hold raises a COO item", n_items >= 1, n_items)

    tp.event_lines = lambda db_path=None, through=None: ([{"event_id": 3305}], [])
    d = rc.run(3305, apply=False, db_path=DB)
    sa = next(x for x in d["races"] if x["race"] == "san_antonio_fall_net")
    check("dry run: SA ladder $240/$180/$120/$60 on a $600 pot", sa["pot"] == 600 and sa["ladder"] == [240, 180, 120, 60], sa)
    check("dry run: the T1 pair splits 1st + 2nd ($210 each), 3rd gets $120",
          [p["amount"] for p in sa["prizes"]] == [210, 210, 120], sa["prizes"])
    check("co-champions on a tie, never a tiebreak", sa["champions"] == ["Adam Baker", "Jeff Rideout"], sa["champions"])
    with db._connect(DB) as c:
        check("dry run records nothing", c.execute("SELECT COUNT(*) FROM tgf_payouts").fetchone()[0] == 0)

    a = rc.run(3305, apply=True, db_path=DB)
    check("apply: done", a.get("done") is True, a)
    check("the races were rebuilt from the Tracker first", refreshed == list(tp.TRACKER_RACES), refreshed)
    with db._connect(DB) as c:
        rows = [dict(x) for x in c.execute(
            "SELECT e.code, p.customer_id, p.amount, p.category, p.acct_transaction_id FROM tgf_payouts p "
            "JOIN tgf_events e ON e.id = p.event_id ORDER BY p.id")]
    sa_rows = [x for x in rows if x["code"] == "SAN ANTONIO Fall Net 2026"]
    check("SA prizes recorded under the race label, by customer_id",
          [(x["customer_id"], x["amount"]) for x in sa_rows] == [(87, 210.0), (6, 210.0), (82, 120.0)], sa_rows)
    check("category Fall Net", all(x["category"] == "Fall Net" for x in rows), rows)
    final = json.loads(db.get_app_setting("gg_points_race_final", db_path=DB))
    check("both races declared final on the finale date",
          final.get("san_antonio_fall_net") == "2026-10-31" and final.get("austin_fall_net") == "2026-10-31", final)
    n_before = len(rows)
    b = rc.run(3305, apply=True, db_path=DB)
    with db._connect(DB) as c:
        n_after = c.execute("SELECT COUNT(*) FROM tgf_payouts").fetchone()[0]
    check("a second run records nothing twice", b.get("note") == "already recorded" and n_after == n_before, (b, n_after))
finally:
    tp.event_lines, db.season_race_payout_rows, db.refresh_points_race_standings = _r

t = ct.cup_titles(87, 2026, {"san_antonio_fall_net": [87, 6]})
check("Spotlight title: 'San Antonio Fall Net - 2026 Champion'",
      [x["line"] for x in t] == ["San Antonio Fall Net - 2026 Champion"], t)

try:
    os.remove(DB)
except OSError:
    pass
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
