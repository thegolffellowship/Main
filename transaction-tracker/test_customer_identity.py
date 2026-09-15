"""Identity across a lead, a GG RSVP and a GoDaddy order (Kerry 2026-09-15:
"Jose Mejia should have removed/merged with the Joe Mejia RSVP").

A Facebook lead created "Joe Mejia" (yahoo email, phone); the same man
ordered as "Jose Mejia" with a mac.com email. Two rungs were missing:
  1. order-time resolution had no PHONE + SURNAME rung, so it minted a
     second profile;
  2. RSVP → item matching had no IDENTITY rung (rule 6), so the RSVP
     under the yahoo email could not find the order under the mac email
     even once both pointed at one customer_id.
Plus the one-shot repair that merges 824 → 729 on the live DB.

Run: python3 test_customer_identity.py
"""
import os, sqlite3, sys, tempfile, contextlib, io, logging
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
logging.getLogger("email_parser.database").setLevel(logging.WARNING)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

print("\n== phone + surname rung ==")
check("digits: +1 and punctuation stripped", db._phone_digits("+17033098234") == "7033098234" and db._phone_digits("(703) 309-8234") == "7033098234")
check("digits: non-US or short -> ''", db._phone_digits("309-8234") == "" and db._phone_digits(None) == "")
# The full schema: _lookup_customer_id and the create path read columns
# (company_name, customer_statuses…) a hand-rolled fixture keeps missing.
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-id-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
conn = sqlite3.connect(tmp); conn.row_factory = sqlite3.Row
conn.executescript("""
 INSERT INTO customers (customer_id, first_name, last_name, phone, chapter, acquisition_source, account_status)
   VALUES (729, 'Joe', 'Mejia', '+17033098234', 'San Antonio', 'facebook_lead', 'active');
 INSERT INTO customer_emails (customer_id, email, is_primary, is_golf_genius, label) VALUES (729, 'jmejiasat@yahoo.com', 1, 1, 'lead');
 INSERT INTO customers (customer_id, first_name, last_name, phone, chapter, acquisition_source, account_status)
   VALUES (5, 'Ana', 'Mejia', '(703) 309-8234', 'San Antonio', 'godaddy', 'active');
""")
conn.commit()
cid = db._resolve_or_create_customer(conn, "Jose Mejia", "jmejiasat@mac.com", phone="(703) 309-8234", first_name="Jose", last_name="Mejia")
check("same phone but TWO Mejias on it -> ambiguous, a new profile is created (not guessed)", cid not in (729, 5) and cid is not None, str(cid))
conn.execute("DELETE FROM customers WHERE customer_id = ?", (cid,)); conn.execute("DELETE FROM customer_emails WHERE customer_id = ?", (cid,))
conn.execute("DELETE FROM customers WHERE customer_id = 5")
cid = db._resolve_or_create_customer(conn, "Jose Mejia", "jmejiasat@mac.com", phone="(703) 309-8234", first_name="Jose", last_name="Mejia")
check("unique phone + surname resolves to the lead's profile (729)", cid == 729, str(cid))
check("the new email is filed on that profile", conn.execute("SELECT 1 FROM customer_emails WHERE customer_id = 729 AND email = 'jmejiasat@mac.com'").fetchone() is not None)
cid2 = db._resolve_or_create_customer(conn, "Jose Mejia", "jmejiasat@mac.com", phone=None, first_name="Jose", last_name="Mejia")
check("…so the next order matches by email with no phone at all", cid2 == 729, str(cid2))
cid3 = db._resolve_or_create_customer(conn, "Pat Mejia", "pat@x.com", phone="(210) 555-0000", first_name="Pat", last_name="Mejia")
check("a different phone is a different person", cid3 not in (729,), str(cid3))

print("\n== RSVP -> item by identity ==")
conn.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_email, customer_id, item_name, order_date, transaction_status) VALUES (2880, 'u', 'The Golf Fellowship', 'Jose Mejia', 'jmejiasat@mac.com', 729, 's9.23 THE QUARRY', '2026-09-15', 'active')")
conn.execute("INSERT INTO event_aliases (alias_name, canonical_event_name) VALUES ('s9.23 THE QUARRY', 's9.23 The Quarry')")
conn.commit()
mid = db.match_rsvp_to_item("jmejiasat@yahoo.com", "Jose", "s9.23 The Quarry", db_path=tmp)
check("an RSVP under the yahoo email finds the order under the mac email through customer_id", mid == 2880, str(mid))
check("an unknown email and a first name nobody has -> no match", db.match_rsvp_to_item("nobody@x.com", "Zed", "s9.23 The Quarry", db_path=tmp) is None)
conn.close()

print("\n== one-shot repair on the full schema ==")
tmp2 = os.path.join(tempfile.mkdtemp(prefix="tgf-mejia-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp2)
c = sqlite3.connect(tmp2); c.row_factory = sqlite3.Row
c.execute("INSERT INTO customers (customer_id, first_name, last_name, phone, chapter, acquisition_source, account_status) VALUES (729, 'Joe', 'Mejia', '+17033098234', 'San Antonio', 'facebook_lead', 'active')")
c.execute("INSERT INTO customers (customer_id, first_name, last_name, phone, chapter, acquisition_source, account_status, current_player_status) VALUES (824, 'Jose', 'Mejia', '(703) 309-8234', 'San Antonio', 'godaddy', 'active', 'first_timer')")
c.execute("INSERT INTO customer_emails (customer_id, email, is_primary, label) VALUES (729, 'jmejiasat@yahoo.com', 1, 'lead')")
c.execute("INSERT INTO customer_emails (customer_id, email, is_primary, label) VALUES (824, 'jmejiasat@mac.com', 1, 'godaddy')")
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (3302, 's9.23 The Quarry', '2026-09-15', 'San Antonio', 'active')")
c.execute("INSERT INTO event_aliases (alias_name, canonical_event_name) VALUES ('s9.23 THE QUARRY', 's9.23 The Quarry')")
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_email, customer_id, item_name, order_date, transaction_status, event_id) VALUES (2880, 'u', 'The Golf Fellowship', 'Jose Mejia', 'jmejiasat@mac.com', 824, 's9.23 THE QUARRY', '2026-09-15', 'active', 3302)")
c.execute("INSERT INTO rsvps (id, email_uid, player_name, player_email, matched_event, response, received_at, customer_id) VALUES (1816, 'r', 'Jose', 'jmejiasat@yahoo.com', 's9.23 The Quarry', 'PLAYING', '2026-09-15T15:57:50Z', 729)")
c.commit()
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    n = db._repair_mejia_identity(c, tmp2)
row = lambda q, *a: c.execute(q, a).fetchone()
check("824 is gone", row("SELECT 1 FROM customers WHERE customer_id = 824") is None)
check("the order now points at 729", row("SELECT customer_id FROM items WHERE id = 2880")["customer_id"] == 729)
check("canonical first name is Jose, Joe is an alias", row("SELECT first_name FROM customers WHERE customer_id = 729")["first_name"] == "Jose"
      and row("SELECT 1 FROM customer_aliases WHERE alias_value = 'Joe Mejia' AND customer_id = 729") is not None)
check("both emails live on 729", row("SELECT COUNT(*) AS n FROM customer_emails WHERE customer_id = 729 AND email IN ('jmejiasat@yahoo.com','jmejiasat@mac.com')")["n"] == 2)
check("his GG RSVP is bound to the order", row("SELECT matched_item_id FROM rsvps WHERE id = 1816")["matched_item_id"] == 2880)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    n2 = db._repair_mejia_identity(c, tmp2)
check("second run is a no-op", n2 == 0)
c.close()
print("\n" + ("FAILED: " + ", ".join(F) if F else "ALL PASSED")); sys.exit(1 if F else 0)
