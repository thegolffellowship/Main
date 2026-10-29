"""THE CLOSED-EVENT REACTIVATION CHECK (Kerry 2026-10-28, Event Ops #2477-3):
REVERSE on item 3162 (Peter) on closed event 3303 made him active again and
moved the GAMES tab from 24/$505 to 25/$511. Reactivating an item on a closed
event now warns in the confirm and raises one COO item; it is never blocked.

Run: python3 test_closed_event_guard.py
"""
import contextlib, io, logging, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="tgf-ceg-"), "t.db")
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    DB = os.environ["DATABASE_PATH"]
    db.init_db(DB)
    import app as appmod  # noqa: E402
from email_parser import closed_event_guard as ceg  # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

with db._connect(DB) as c:
    peter = c.execute("INSERT INTO customers (first_name, last_name) VALUES ('Peter', 'Rundqvist') RETURNING customer_id").fetchone()[0]
    closed = c.execute("INSERT INTO events (item_name, event_date, course, chapter) "
                       "VALUES ('s9.29 Silverhorn', '2026-10-27', 'Silverhorn', 'San Antonio') RETURNING id").fetchone()[0]
    openev = c.execute("INSERT INTO events (item_name, event_date, course, chapter) "
                       "VALUES ('s9.30 Brackenridge', '2099-11-03', 'Brackenridge', 'San Antonio') RETURNING id").fetchone()[0]
    c.commit()
# tgf_events.events_id is added by a later step; insert with whatever columns exist
with db._connect(DB) as c:
    try:
        c.execute("ALTER TABLE tgf_events ADD COLUMN events_id INTEGER")
    except Exception:
        pass
    te = c.execute("INSERT INTO tgf_events (code, name, event_date, events_id) VALUES ('s929', 's9.29 Silverhorn', "
                   "'2026-10-27', ?) RETURNING id", (closed,)).fetchone()[0]
    c.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount) VALUES (?, ?, 'team', 26.0)", (te, peter))
    i_closed = c.execute("INSERT INTO items (email_uid, item_index, customer, customer_id, item_name, event_id, "
                         "transaction_status, credit_amount, merchant, order_date) VALUES ('t-3162', 0, 'Peter Rundqvist', ?, "
                         "'s9.29 Silverhorn', ?, 'credited', '$49.00', 'GoDaddy', '2026-10-20') RETURNING id",
                         (peter, closed)).fetchone()[0]
    i_open = c.execute("INSERT INTO items (email_uid, item_index, customer, customer_id, item_name, event_id, "
                       "transaction_status, credit_amount, merchant, order_date) VALUES ('t-9', 0, 'Peter Rundqvist', ?, "
                       "'s9.30 Brackenridge', ?, 'credited', '$49.00', 'GoDaddy', '2026-10-20') RETURNING id",
                       (peter, openev)).fetchone()[0]
    i_wd = c.execute("INSERT INTO items (email_uid, item_index, customer, customer_id, item_name, "
                     "transaction_status, merchant, order_date) VALUES ('t-10', 0, 'Peter Rundqvist', ?, "
                     "'s9.29 Silverhorn', 'wd', 'GoDaddy', '2026-10-20') RETURNING id", (peter,)).fetchone()[0]
    c.commit()

print("the check")
k = ceg.check(i_closed, DB)
check("an event with payouts recorded is closed, with the warning",
      k["closed"] and k["warning"] == "This event is closed: reactivating changes its field count and games."
      and k["event_id"] == closed, k)
check("an upcoming event is not", not ceg.check(i_open, DB)["closed"])
check("found by name when the row has no event_id", ceg.check(i_wd, DB)["closed"])

def open_items():
    with db._connect(DB) as c:
        return [dict(r) for r in c.execute(
            "SELECT subject, summary FROM action_items WHERE subject LIKE 'CLOSED EVENT REACTIVATED%'").fetchall()]

print("the routes")
cl = appmod.app.test_client()
with cl.session_transaction() as s:
    s["role"] = "admin"
r = cl.get(f"/api/items/{i_closed}/reactivation-check")
check("GET reactivation-check answers closed", r.status_code == 200 and r.get_json()["closed"])
r = cl.post(f"/api/items/{i_closed}/reverse-credit")
check("Reverse on a closed event still runs (never blocked)", r.status_code == 200, r.data[:200])
with db._connect(DB) as c:
    st = c.execute("SELECT transaction_status FROM items WHERE id = ?", (i_closed,)).fetchone()[0]
check("...the row is active again", st == "active")
ai = open_items()
check("one COO item naming the event and the item", len(ai) == 1 and "s9.29 Silverhorn" in ai[0]["subject"]
      and str(i_closed) in ai[0]["subject"] and "Peter Rundqvist" in ai[0]["summary"], ai)
check("the answer carries the flag for the page", r.get_json().get("closed_event"))
r = cl.post(f"/api/items/{i_open}/reverse-credit")
check("Reverse on an open event raises nothing", r.status_code == 200 and len(open_items()) == 1)
r = cl.patch(f"/api/items/{i_wd}", json={"transaction_status": "active"})
check("a status set back to active on a closed event raises one item too",
      r.status_code == 200 and len(open_items()) == 2, (r.status_code, open_items()))
r = cl.patch(f"/api/items/{i_wd}", json={"transaction_status": "active"})
check("setting active on an already-active row raises nothing more", len(open_items()) == 2)

print("the confirms and the MCP tool")
for p in ("templates/events.html", "templates/customers.html", "static/js/dashboard.js"):
    src = open(p).read()
    check(f"{p}: the Reverse confirm carries the closed-event warning",
          "reactivation-check" in src and "confirm(await tgfReactivationWarning(itemId) +" in src)
src = open("mcp_server.py").read()
check("MCP undo_credit_or_transfer warns in its preview and raises the item after",
      "_ceg.WARNING" in src and "_ceg.after_reactivate(transaction_id" in src)
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
