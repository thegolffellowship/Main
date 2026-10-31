"""ONE EMAIL PER PERSON from the composer (Kerry 2026-10-31: "Why is Larry on
there twice?" ... "Build it now"). Larry Anthis had his registration plus a
"balance due" payment row (parent_item_id) on the same event and got two
copies of the 7:18 AM notice. Graph is mocked: nothing leaves.

Run: python3 test_composer_one_per_person.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PIN", "4242")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import fetcher
    db.init_db(DB)
    import app as _app

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

SENT = []
def fake_send(**kw):
    SENT.append(kw); return True
fetcher.send_mail_graph = fake_send
for k, v in (("AZURE_TENANT_ID", "t"), ("AZURE_CLIENT_ID", "c"), ("AZURE_CLIENT_SECRET", "s"),
             ("EMAIL_ADDRESS", "tracker@example.test")):
    os.environ[k] = v

EV, NAME = 9501, "s18.50 ONE PER PERSON"
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                 "start_time, course) VALUES (?, ?, '2026-12-20', 'San Antonio', 'active', '18-hole', "
                 "'Shotgun', '08:30', 'Test Links GC')", (EV, NAME))
    for cid, fn, em in ((890001, "Larry", "larry@example.test"), (890002, "Mia", "mia@example.test")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status, "
                     "chapter) VALUES (?, ?, 'Test', 'active_member', 'San Antonio')", (cid, fn))
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?, ?, 1)", (cid, em))
    def item(cust, cid, em, uid, parent=None):
        cur = conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, transaction_status, "
                           "order_date, order_id, email_uid, merchant, customer_email, parent_item_id) VALUES "
                           "(?, ?, ?, ?, 'active', '2026-10-01', ?, ?, 'GoDaddy', ?, ?)",
                           (cust, cid, NAME, EV, uid, uid, em, parent))
        return cur.lastrowid
    larry = item("Larry Test", 890001, "larry@example.test", "L1")
    item("Larry Test", 890001, "larry@example.test", "L2", parent=larry)   # balance-due row
    item("Mia Test", 890002, "mia@example.test", "M1")
    item("Mia Test", 890002, "mia@example.test", "M2")                    # a second registration row
    # Two guests with no card sharing one inbox each still get theirs.
    item("Guest One", None, "shared@example.test", "G1")
    item("Guest Two", None, "shared@example.test", "G2")
    conn.commit()

tid = next(t["id"] for t in db.get_message_templates() if t["name"] != "Payment Reminder")
cl = _app.app.test_client()
with cl.session_transaction() as s_:
    s_["role"] = "manager"; s_["authenticated"] = True

print("1. The send route")
rv = cl.post("/api/messages/send", json={"template_id": tid, "event_name": NAME, "audience": "all"})
to = sorted(s["to_address"] for s in SENT)
check("the route answers", rv.status_code == 200, (rv.status_code, rv.get_json()))
check("Larry gets one email, not two (payment row skipped)", to.count("larry@example.test") == 1, to)
check("Mia gets one email from two registration rows", to.count("mia@example.test") == 1, to)
check("two guests sharing an inbox each still get theirs", to.count("shared@example.test") == 2, to)
check("four emails total", len(to) == 4, to)

print("2. The composer's recipient list (events.html)")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "events.html")).read()
i = src.find("function getComposeRecipients")
body = src[i:i + 6000]
check("skips payment-only child rows", "if (r.parent_item_id) return false;" in body)
check("dedupes by customer, then email + name", "_seenPeople.has(_k)" in body and "c${r.customer_id}" in body)

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
