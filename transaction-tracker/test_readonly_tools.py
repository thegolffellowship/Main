"""Read-only event views for the lanes (Kerry 2026-09-29, Front Desk #954).

Kerry: "Why can't you see the games tab info? You need to create a tool
that allows you to see it and any other tools if you're blind to any
other stuff." Each tool must read through the page's own code, carry
customer_id on every person row, write nothing, and log via _audit.

Run: python3 test_readonly_tools.py
"""
import os, sqlite3, sys, tempfile, contextlib, io, json, logging
from datetime import datetime
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-rotools-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test")
logging.disable(logging.WARNING)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

from email_parser import database as db  # noqa: E402
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(DB)
    import mcp_server  # noqa: E402
    import app  # noqa: E402,F401  — booted first, as in production (its boot seeding is not the tools')
c = sqlite3.connect(DB)
TODAY = datetime.now().strftime("%Y-%m-%d")
EV = 4401
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status, start_type, start_time) "
          "VALUES (?, 's9.25 Test Springs', ?, 'San Antonio', 'active', 'Shotgun', '17:00')", (EV, TODAY))
for cid, fn, ln in [(9001, "Fred", "Wicker"), (9002, "Steve", "Kulawik"), (9003, "Mary", "Wade")]:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status, "
              "current_player_status) VALUES (?,?,?, 'San Antonio', 'active', 'active_member')", (cid, fn, ln))
    c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, event_id, "
              "transaction_status, holes, order_date, user_status) VALUES (?,?, 'The Golf Fellowship', ?,?, "
              "'s9.25 Test Springs', ?, 'active', '9', ?, 'MEMBER')",
              (90000 + cid, f"u{90000+cid}", f"{fn} {ln}", cid, EV, TODAY))
c.commit()
db.save_event_pairings(EV, {"9": [{"group_num": 1, "slot_label": "1A", "players": [
    {"name": "Fred Wicker", "customer_id": 9001, "cart_pos": 1, "tee_choice": "50-64", "handicap_index": 7.6},
    {"name": "Steve Kulawik", "customer_id": 9002, "cart_pos": 2, "tee_choice": "50-64", "handicap_index": 12.7},
    {"name": "Mary Wade", "customer_id": 9003, "cart_pos": 3, "tee_choice": "Forward", "handicap_index": 7.6}]}]},
    db_path=DB)
db.set_group_codes(EV, {("9", 1): "EJEF8D"}, db_path=DB) if hasattr(db, "set_group_codes") else None

def counts():
    k = sqlite3.connect(DB)
    out = {t: k.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
           for t in ("events", "items", "customers", "event_pairings")}
    k.close(); return out

before = counts()
logs_before = sqlite3.connect(DB).execute("SELECT COUNT(*) FROM agent_action_log").fetchone()[0]

print("\n== get_event_pairings ==")
p = json.loads(mcp_server.get_event_pairings(EV))
g = (p.get("groups") or [{}])[0]
check("one group, slot 1, label 1A, three players", p.get("group_count") == 1 and g.get("slot") == 1
      and g.get("label") == "1A" and len(g.get("players") or []) == 3, p)
check("every player carries customer_id", not p.get("missing_customer_id")
      and all(x.get("customer_id") for x in g.get("players") or []), p.get("missing_customer_id"))
check("cart seats: 1-2 = A, 3 = B", [x["cart"] for x in g["players"]] == ["A", "A", "B"])
check("an unknown event says so", "error" in json.loads(mcp_server.get_event_pairings(999999)))

print("\n== get_event_flights / payouts / score entry (the pages' own GETs) ==")
f = json.loads(mcp_server.get_event_flights(EV))
check("flights board comes from the FLIGHTS tab's endpoint", f.get("status") == 200 and isinstance(f.get("board"), dict), f.get("status"))
pay = json.loads(mcp_server.get_event_payouts(EV))
check("payouts tab read (none recorded yet, said plainly)", pay.get("status") == 200 and pay.get("payouts_tab") is None
      and "No payouts recorded" in (pay.get("note") or ""), pay)
se = json.loads(mcp_server.get_score_entry_status(EV))
check("score entry: the Live Scoring page's read answers, switches reported",
      se.get("status") in (200, 404) and "member_switch_on" in se and "qr_on" in se, se.get("status"))

print("\n== get_live_version / get_hio_pot ==")
v = json.loads(mcp_server.get_live_version())
top = open("static/js/version.js").read().split('"')[1]
check("running version is this build's version.js", v.get("running_version") == top, v)
h = json.loads(mcp_server.get_hio_pot())
check("HIO pot reads the banner's own reader", isinstance(h, dict) and h, h)

print("\n== read-only, and logged ==")
check("no event / item / customer / pairing row changed", counts() == before, (before, counts()))
logs_after = sqlite3.connect(DB).execute("SELECT COUNT(*) FROM agent_action_log").fetchone()[0]
check("each call left an _audit line", logs_after - logs_before >= 7, logs_after - logs_before)

print("\nALL PASSED" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
