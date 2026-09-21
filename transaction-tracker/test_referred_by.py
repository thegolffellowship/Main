"""WHO BROUGHT THEM — the widened referral relationship.

Kerry 2026-09-21, looking at Ty Bubela on the dashboard: "How am I
supposed to attribute him to Justin Angelone?" The column existed and
meant only "I paid for this person's spot" because one code path wrote
it. It now means who brought them, with the provenance beside it.

A RELATIONSHIP only. Referral FEES arise from a redeemed coupon or a
payout receipt and live in referral_fees; recording this must never mint
one (ratified 2026-07-30).
"""
import os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db

FAIL = []
def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + str(detail) if not cond else ""))
    if not cond: FAIL.append(label)

p = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
conn = sqlite3.connect(p)
conn.executescript("""
CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT,
  acquisition_source TEXT, referred_by_customer_id INTEGER, referred_at TEXT,
  referred_by_source TEXT, referred_by_note TEXT, found_us_via TEXT);
CREATE TABLE referral_fees (id INTEGER PRIMARY KEY, referred_customer_id INTEGER);
INSERT INTO customers (customer_id, first_name, last_name, acquisition_source)
  VALUES (829,'Ty','Bubela','godaddy'), (709,'Justin','Angelone','godaddy');
""")
conn.commit(); conn.close()

print("set_referred_by")
r = db.set_referred_by(829, 709, source="member_claim", note="Kerry, 2026-09-21", db_path=p)
check("Ty is attributed to Justin", r.get("referred_by_customer_id") == 709, r)
check("the referrer's name comes back for the UI", r.get("referred_by_name") == "Justin Angelone", r)
check("the provenance is stored beside the id", r.get("referred_by_source") == "member_claim", r)

with sqlite3.connect(p) as c:
    c.row_factory = sqlite3.Row
    row = dict(c.execute("SELECT * FROM customers WHERE customer_id=829").fetchone())
    fees = c.execute("SELECT COUNT(*) FROM referral_fees").fetchone()[0]
check("referred_at is stamped", bool(row["referred_at"]), row)
check("the note is kept", row["referred_by_note"] == "Kerry, 2026-09-21", row)
check("RECORDING A RELATIONSHIP MINTS NO FEE — the 2026-07-30 rule", fees == 0, fees)
check("acquisition_source is NOT touched — channel and person are "
      "independent facts", row["acquisition_source"] == "godaddy", row)

print("guards")
check("a player cannot refer themselves",
      "error" in db.set_referred_by(829, 829, db_path=p))
check("an unknown referrer is refused",
      "error" in db.set_referred_by(829, 99999, db_path=p))
check("an unknown customer is refused",
      "error" in db.set_referred_by(99999, 709, db_path=p))
check("a bogus source is refused rather than stored",
      "error" in db.set_referred_by(829, 709, source="vibes", db_path=p))
r = db.set_referred_by(829, 709, db_path=p)
check("naming a person with no source defaults to member_claim — never "
      "WHO without HOW WE KNOW", r.get("referred_by_source") == "member_claim", r)

print("clearing")
r = db.set_referred_by(829, None, db_path=p)
check("clearing reports it", r.get("cleared") is True, r)
with sqlite3.connect(p) as c:
    c.row_factory = sqlite3.Row
    row = dict(c.execute("SELECT * FROM customers WHERE customer_id=829").fetchone())
check("clearing wipes the id, the source, the note and the stamp together",
      row["referred_by_customer_id"] is None and row["referred_by_source"] is None
      and row["referred_by_note"] is None and row["referred_at"] is None, row)

print("found_us_via — 'not a referral' is a real answer")
r = db.set_found_us_via(829, "facebook_ad", db_path=p)
check("a channel is stored", r.get("found_us_via") == "facebook_ad", r)
check("free text is refused — a column of one-off spellings cannot be counted",
      "error" in db.set_found_us_via(829, "saw it somewhere", db_path=p))
db.set_referred_by(829, 709, db_path=p)
with sqlite3.connect(p) as c:
    c.row_factory = sqlite3.Row
    row = dict(c.execute("SELECT * FROM customers WHERE customer_id=829").fetchone())
check("naming a person does NOT clear the channel — a person can be "
      "brought by a friend AND have seen the ad",
      row["found_us_via"] == "facebook_ad" and row["referred_by_customer_id"] == 709, row)
check("clearing the channel is allowed", db.set_found_us_via(829, None, db_path=p).get("found_us_via") is None)

os.unlink(p)
print(("\nALL PASS" if not FAIL else f"\n{len(FAIL)} FAILURE(S): {FAIL}"))
sys.exit(1 if FAIL else 0)
