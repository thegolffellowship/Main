"""Who is waiting to be attributed, and what naming someone does.

Kerry 2026-09-21: "if they're already tied to a lead campaign, then they
shouldn't be on the first timers list to attribute" and, on Hammond and
Hightower, "they still show as leads to track in the Leads center."

Real SQLite, minimal schema — the queries are the thing under test, so
faking the connection would test nothing.
"""
import os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FAIL = []
def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + str(detail) if not cond else ""))
    if not cond: FAIL.append(label)

TODAY = "2026-09-21"
RECENT = "2026-09-14"


def build(with_leads=True):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT,
            phone TEXT, chapter TEXT,
            referred_by_customer_id INTEGER, referred_by_source TEXT,
            referred_by_note TEXT, referred_at TEXT, found_us_via TEXT,
            acquisition_source TEXT);
        CREATE TABLE items (
            id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT,
            user_status TEXT, transaction_status TEXT DEFAULT 'active');
    """)
    if with_leads:
        conn.execute("CREATE TABLE leads (id INTEGER PRIMARY KEY, "
                     "customer_id INTEGER, campaign_id INTEGER, "
                     "source TEXT, merged_into INTEGER)")
    people = [
        (829, "Ty", "Bubela", "godaddy"),       # walk-in, nobody recorded
        (791, "Logan", "Billeaud", "godaddy"),  # came through a campaign
        (819, "Zac", "Hammond", "godaddy"),     # organic lead, no campaign
        (709, "Justin", "Angelone", "godaddy"), # already attributed
        # Hector Hinojosa: stamped by the lead pipe, lead row since gone.
        (759, "Hector", "Hinojosa", "facebook_lead"),
    ]
    for cid, f, l, src in people:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, "
                     "acquisition_source) VALUES (?,?,?,?)", (cid, f, l, src))
        conn.execute("INSERT INTO items (customer_id, order_date, user_status) "
                     "VALUES (?,?, '1st Timer')", (cid, RECENT))
    conn.execute("UPDATE customers SET referred_by_customer_id = 31, "
                 "referred_by_source = 'member_claim' WHERE customer_id = 709")
    if with_leads:
        conn.execute("INSERT INTO leads (customer_id, campaign_id, source) "
                     "VALUES (791, 1, 'hubspot')")
        conn.execute("INSERT INTO leads (customer_id, campaign_id, source) "
                     "VALUES (819, NULL, 'organic')")
    conn.commit()
    return conn


from email_parser.dashboard import _first_timers_to_attribute

print("The queue")
card = _first_timers_to_attribute(build(), TODAY)
names = [i["label"] for i in card["items"]]
check("an unattributed walk-in is waiting", "Ty Bubela" in names, names)
check("a CAMPAIGN lead is not — Facebook already answered it",
      "Logan Billeaud" not in names, names)
check("an ORGANIC lead still is — no campaign means nobody has said who brought them",
      "Zac Hammond" in names, names)
check("someone already attributed is not", "Justin Angelone" not in names, names)
check("a customer stamped 'facebook_lead' is not, even with NO lead row left "
      "(Kerry: 'Isn't Hector Hinojosa a campaign lead?')",
      "Hector Hinojosa" not in names, names)
check("the count matches the rows shown", card["count"] == len(card["items"]), card["count"])
check("each row carries the customer id the modal keys on",
      all(i.get("attribute_cid") for i in card["items"]), card["items"])
check("...and still carries an href, so the Customers page remains reachable",
      all(i.get("href") for i in card["items"]))

print("A Tracker with no leads table at all")
card = _first_timers_to_attribute(build(with_leads=False), TODAY)
check("the card still renders rather than the feed falling over rule 2",
      card is not None and "Ty Bubela" in [i["label"] for i in card["items"]], card)
check("...and the acquisition_source exclusion still applies without a leads table",
      "Hector Hinojosa" not in [i["label"] for i in card["items"]], card)

print("Nothing waiting")
conn = build()
conn.execute("UPDATE customers SET referred_by_customer_id = 31")
conn.commit()
check("an empty queue returns None, so the card does not render",
      _first_timers_to_attribute(conn, TODAY) is None)

print("Naming someone makes them a lead (Rick Billeaud's shape)")
import email_parser.database as db
import email_parser.leads as L

fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
c = sqlite3.connect(path)
c.executescript("""
    CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT,
        last_name TEXT, phone TEXT, chapter TEXT);
    CREATE TABLE lead_notes (id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER, author TEXT, note TEXT);
    INSERT INTO customers VALUES (829, 'Ty', 'Bubela', '210-555-0100', 'San Antonio');
    INSERT INTO customers VALUES (819, 'Zac', 'Hammond', '512-555-0199', 'Austin');
""")
c.commit(); c.close()
conn = sqlite3.connect(path); L.ensure_leads_table(conn)
conn.execute("INSERT INTO leads (source, first_name, last_name, phone, "
             "customer_id, status) VALUES ('organic','Zac','Hammond',"
             "'512-555-0199', 819, 'converted')")
conn.commit(); conn.close()

r = L.ensure_referral_lead(829, referrer_name="Justin Angelone", db_path=path)
check("a customer with no lead row gets one", r.get("ok") is True, r)
conn = sqlite3.connect(path); conn.row_factory = sqlite3.Row
row = conn.execute("SELECT * FROM leads WHERE customer_id = 829").fetchone()
check("source is 'referral', like Rick Billeaud's", row["source"] == "referral", dict(row))
check("campaign_id stays NULL — a referral is not Return on Ad Spend",
      row["campaign_id"] is None, dict(row))
check("it is linked by customer_id, the identity key (principle 6)",
      row["customer_id"] == 829)
check("status reflects reality: they are already a customer",
      row["status"] == "converted", row["status"])
check("their chapter comes along", row["chapter"] == "San Antonio", row["chapter"])
note = conn.execute("SELECT note FROM lead_notes WHERE lead_id = ?",
                    (row["id"],)).fetchone()
check("the note says who referred them", note and "Justin Angelone" in note["note"], note)
conn.close()

again = L.ensure_referral_lead(829, referrer_name="Justin Angelone", db_path=path)
check("running it twice does NOT mint a second row", again.get("ok") is False, again)
check("...and says why", again.get("reason") == "already a lead", again)

r = L.ensure_referral_lead(819, referrer_name="Somebody", db_path=path)
check("someone who is ALREADY a lead is left exactly as they were",
      r.get("ok") is False, r)
conn = sqlite3.connect(path)
n = conn.execute("SELECT COUNT(*) FROM leads WHERE customer_id = 819").fetchone()[0]
src = conn.execute("SELECT source FROM leads WHERE customer_id = 819").fetchone()[0]
conn.close()
check("...one row, and its organic source is not rewritten", n == 1 and src == "organic", (n, src))

r = L.ensure_referral_lead(99999, db_path=path)
check("an unknown customer is refused, not invented", r.get("ok") is False, r)
os.unlink(path)

print(f"\n{len(FAIL)} FAILURE(S): {FAIL}" if FAIL else "\nALL PASS")
sys.exit(1 if FAIL else 0)
