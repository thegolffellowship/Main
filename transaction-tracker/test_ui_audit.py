"""WHO DID IT (Kerry 2026-10-28: "we need a log of clicks and who did it so
you can easily see that I was the one that removed myself"). A delete from
an admin session logs ui:admin with the removed player's name; a manager's
credit logs ui:manager:<chapter>; an anonymous call and a failed call log
nothing.

Run: python3 test_ui_audit.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
os.environ["DISABLE_SCHEDULER"] = "1"
logging.disable(logging.ERROR)
from email_parser import database as db                           # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
import app as appmod                                               # noqa: E402
F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


with db._connect(DB) as c:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (18, 'Kerry', 'Niester')")
    kerry = c.execute("INSERT INTO items (customer, customer_id, item_name, item_price, transaction_status, "
                      "email_uid, merchant, order_date) VALUES ('Kerry Niester', 18, 's18.12 FALL CHAMPIONSHIP', "
                      "'$0.00 (comp)', 'active', 'manual-comp-1', 'Manual Entry', '2026-10-27') "
                      "RETURNING id").fetchone()[0]
    other = c.execute("INSERT INTO items (customer, customer_id, item_name, item_price, transaction_status, "
                      "email_uid, merchant, order_date) VALUES ('Kerry Niester', 18, 's9.30 X', "
                      "'$10.00', 'active', 'manual-comp-2', 'Manual Entry', '2026-10-27') "
                      "RETURNING id").fetchone()[0]
    db._ensure_pairing_tables(c)
    c.commit()


def logs():
    with db._connect(DB) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM agent_action_log WHERE agent_name LIKE 'ui:%' ORDER BY id")]


cl = appmod.app.test_client()
cl.delete(f"/api/events/delete-manual-player/{kerry}")
check("anonymous: refused, nothing logged", logs() == [], logs())

with cl.session_transaction() as s:
    s["role"] = "admin"
r = cl.delete(f"/api/events/delete-manual-player/{kerry}")
check("admin delete ok", r.status_code == 200, r.status_code)
L = logs()
check("one ui:admin line", len(L) == 1 and L[0]["agent_name"] == "ui:admin", L)
check("names who was removed and from what", L and "Kerry Niester" in L[0]["description"]
      and "FALL CHAMPIONSHIP" in L[0]["description"] and "was active" in L[0]["description"], L)
check("tied to the row", L and L[0]["related_item_id"] == kerry, L)

r = cl.delete(f"/api/events/delete-manual-player/{kerry}")
check("failed call (already gone) not logged", r.status_code >= 400 and len(logs()) == 1, (r.status_code, logs()))

with cl.session_transaction() as s:
    s["role"] = "manager"
    s["chapter"] = "San Antonio"
r = cl.post(f"/api/items/{other}/credit", json={"note": "not playing"})
L = logs()
check("manager credit logged with chapter + note", r.status_code == 200 and L[-1]["agent_name"] == "ui:manager:San Antonio"
      and "not playing" in L[-1]["description"], (r.status_code, L[-1:]))

print("FAILED: " + ", ".join(F) if F else "ALL PASS")
sys.exit(1 if F else 0)
