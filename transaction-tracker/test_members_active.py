"""ACTIVE members on the Customers snapshot (Kerry 2026-09-21: "counts of
number (per chapter) of who's played in the last 60 days, and a
percentage").

Run: python3 test_members_active.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)

TODAY = "2026-09-21"
with db._connect(DB) as conn:
    conn.executemany("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (?,?,?,?,?)", [
        (1, "s9.20 Recent", "2026-09-01", "San Antonio", "active"),
        (2, "s9.12 Old", "2026-06-02", "San Antonio", "active"),
        (3, "s9.25 Future", "2026-09-29", "San Antonio", "active"),
        (4, "s9.21 Cancelled", "2026-09-08", "San Antonio", "cancelled")])
    for cid in (101, 102, 103, 104, 105, 106):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, 'P', ?)", (cid, str(cid)))
    rows = [
        (101, 1, "s9.20 Recent", "active"),      # played 20 days ago → active
        (102, 2, "s9.12 Old", "active"),         # played 111 days ago → not active
        (103, 3, "s9.25 Future", "active"),      # only a future registration → not active
        (104, 1, "s9.20 Recent", "credited"),    # credited out → did not play
        (105, 4, "s9.21 Cancelled", "active"),   # cancelled event → did not play
    ]
    for i, (cid, evid, name, st) in enumerate(rows):
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, transaction_status, order_date, order_id, email_uid, merchant) VALUES (?,?,?,?,?,?,?,?,?)",
                     (f"P {cid}", cid, name, evid, st, "2026-08-01", f"R{i}", f"manual-{i}", "GoDaddy"))
    # 106: no order row at all, but a handicap round posted 10 days ago through the link
    conn.execute("INSERT INTO handicap_player_links (player_name, customer_id) VALUES ('P, 106', 106)")
    conn.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) VALUES ('P, 106', '2026-09-11', 40, 35.0, 120, 4.7)")
    conn.commit()

act = db.customers_activity(db_path=DB, today=TODAY)
cs = act["customers"]
check("the window is the dial's 60 days by default", act["days"] == 60 and act["cutoff"] == "2026-07-23", act)
check("a member who played 20 days ago is active", cs.get("101", {}).get("active") is True and cs["101"]["last_played"] == "2026-09-01", cs.get("101"))
check("111 days ago is not", cs.get("102", {}).get("active") is False, cs.get("102"))
check("a FUTURE registration is not 'played'", "103" not in cs, cs.get("103"))
check("a credited registration is not 'played'", "104" not in cs, cs.get("104"))
check("a cancelled event is not 'played'", "105" not in cs, cs.get("105"))
check("a posted round counts through the player link (customer_id, principle 6)", cs.get("106", {}).get("active") is True, cs.get("106"))
db.set_app_setting(db.MEMBERS_ACTIVE_DAYS_KEY, "120", db_path=DB)
check("the window is a DIAL — at 120 days the June player is active", db.customers_activity(db_path=DB, today=TODAY)["customers"]["102"]["active"] is True)
check("…and ?days= overrides it", db.customers_activity(days=10, db_path=DB, today=TODAY)["customers"]["101"]["active"] is False)

import app as appmod                                              # noqa: E402
c = appmod.app.test_client()
with c.session_transaction() as s_:
    s_["role"] = "view-only"; s_["authenticated"] = True
r = c.get("/api/customers/activity")
check("GET /api/customers/activity serves it (PII-free, view-only)", r.status_code == 200 and "customers" in r.get_json(), (r.status_code, r.get_data()[:120]))
html = open("templates/customers.html").read()
check("the snapshot card renders active counts and shares per chapter", "loadMemberActivity();" in html and "active</span>" in html and "pct(r.active, r.n)" in html)
try: os.unlink(DB)
except OSError: pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
