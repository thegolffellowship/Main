"""UPCOMING CARD: REGISTERED vs RSVP'D (Kerry 2026-10-28: "This registered
list should not include those unpaid. It should have REGISTERED and then
RSVP'd so everyone is shown but not in the same list.").

Run: python3 test_upcoming_rsvp_split.py
"""
import os, sys, io, contextlib, logging, tempfile, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

EID, NAME = 9821, "s18.99 UPCOMING TEST"
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, course) "
                 "VALUES (?, ?, '2099-12-19', 'San Antonio', 'active', '18 Holes', 'Test Links')", (EID, NAME))
    for i, (st, price) in enumerate((("active", "150.00"), ("active", "150.00"), ("rsvp_only", "0"))):
        cid = 894000 + i
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                     "VALUES (?, ?, 'Split', 'active_member')", (cid, f"P{i}"))
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, transaction_status, item_price, "
                     "order_date, order_id, email_uid, merchant) VALUES (?, ?, ?, ?, '18', ?, ?, '2099-12-01', ?, ?, 'GoDaddy')",
                     (f"P{i} Split", cid, NAME, EID, st, price, f"RU{i}", f"manual-u{i}"))
    conn.commit()

ups = db._evlb_upcoming("2099-01-01", None, None, set(), db_path=DB)
ev = next((e for e in ups if e["id"] == EID), None)
check("the upcoming event is listed", ev is not None, ups)
if ev:
    check("registered counts paid players only", ev["registered"] == 2, ev["registered"])
    check("RSVP-only counted apart", ev["rsvp_only"] == 1, ev.get("rsvp_only"))
    check("each player carries rsvp_only", sorted(p["rsvp_only"] for p in ev["players"]) == [False, False, True])

html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "contests.html")).read()
fn = html[html.index("function evlbUpcomingCardHtml"):html.index("function evlbUpcomingHtml")]
check("the card splits the list", "p.rsvp_only" in fn and "RSVP'D, NOT YET PAID" in fn)
check("the REGISTERED heading counts the paid list", "REGISTERED &middot; ${ps.length}" in fn and "!p.rsvp_only" in fn)

try:
    os.remove(DB)
except OSError:
    pass
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
