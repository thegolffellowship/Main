"""Partner-request rules (Kerry 2026-07-30), modelled on the SA Championship.

Three rules:
 1. A RECIPROCAL request is not a loser. "Chuck Fehlis -> Gus Vasquez" after
    "Gus Vasquez -> Chuck Fehlis" is the same pairing restated -> CONFIRMED.
 2. If someone PAID for another player, assume they should be paired.
 3. "A member can bring as many guests as they want and play with up to 3",
    so a host and three guests are one approved foursome, not three
    competing requests where the last two lose.

Run: python3 test_partner_requests.py
"""
import os, sqlite3, sys, tempfile
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


def _refused(fn):
    try:
        fn()
        return False
    except ValueError:
        return True


# Force the name -> customer_id index to rebuild off THIS fixture DB.
db._PARTNER_IDENTITY_CACHE.update({"at": 0.0, "map": {}})
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-pr-"), "t.db")
conn = sqlite3.connect(tmp)
conn.executescript("""
 CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, chapter TEXT);
 CREATE TABLE event_aliases (alias_name TEXT, canonical_event_name TEXT);
 CREATE TABLE items (id INTEGER PRIMARY KEY, customer TEXT, customer_id INTEGER,
   item_name TEXT, holes TEXT, partner_request TEXT, order_date TEXT,
   created_at TEXT, notes TEXT, transaction_status TEXT, parent_item_id INTEGER,
   event_id INTEGER);
 CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT,
   last_name TEXT, company_name TEXT, account_status TEXT);
 CREATE TABLE customer_aliases (id INTEGER PRIMARY KEY, customer_id INTEGER,
   customer_name TEXT, alias_type TEXT, alias_value TEXT);
""")
conn.execute("INSERT INTO events (id, item_name, chapter) VALUES "
             "(1,'TGF SAN ANTONIO CHAMPIONSHIP','San Antonio')")
# (customer, request, order_date, purchased-by note)
FIELD = [
    ("Gus Vasquez",     "Chuck Fehlis",   "2026-07-15", None),
    ("Pat Youngs",      "John White",     "2026-07-24", None),
    ("Chuck Fehlis",    "Gus Vasquez",    "2026-07-27", None),
    ("Richard Palacios","Larry Anthis",   "2026-07-28", None),
    ("Larry Anthis",    "Michael Murphy", "2026-07-29", None),
    ("Michael Murphy",  None,             "2026-07-29", None),
    ("Daniel South",    None,             "2026-07-19", None),
    ("Mark Villa",      "Dan South",      "2026-07-31", "Purchased by Daniel South"),
    ("Orlando Kypuros", "Dan South",      "2026-07-31", "Purchased by Daniel South"),
    ("Jacob Williams",  None,             "2026-07-31", "Purchased by Daniel South"),
]
for i, (nm, req, od, note) in enumerate(FIELD, start=1):
    conn.execute("INSERT INTO items (id, customer, customer_id, item_name, holes,"
                 " partner_request, order_date, created_at, notes,"
                 " transaction_status) VALUES (?,?,?,?,'18',?,?,?,?, 'active')",
                 (i, nm, i, 'TGF SAN ANTONIO CHAMPIONSHIP', req, od, od, note))
    parts = nm.split()
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name,"
                 " account_status) VALUES (?,?,?, 'active')",
                 (i, parts[0], parts[-1]))
# "Dan South" is a real alias on Daniel South's PROFILE (customer_id 7), so
# the guests' requests resolve id-to-id rather than by string resemblance
# (Kerry 2026-07-30: "reference actual aliases in customer_id profiles").
conn.execute("INSERT INTO customer_aliases (customer_id, customer_name,"
             " alias_type, alias_value) VALUES (7,'Daniel South','name','Dan South')")
conn.commit(); conn.close()

out = db.get_event_partner_requests(1, db_path=tmp)["requests"]
by = {r["requester"]: r for r in out}
print("\n== reciprocal requests are CONFIRMED, not outranked ==")
check("Gus -> Chuck is the first claim and stays active",
      by["Gus Vasquez"]["status"] == "active", str(by["Gus Vasquez"]))
check("Chuck -> Gus is CONFIRMED, not OUTRANKED",
      by["Chuck Fehlis"]["status"] == "confirmed", str(by["Chuck Fehlis"]))
check("...and is not flagged locked_out", not by["Chuck Fehlis"]["locked_out"])
check("...with a reason that reads as agreement",
      "confirms it" in (by["Chuck Fehlis"]["locked_reason"] or ""),
      str(by["Chuck Fehlis"]["locked_reason"]))

print("\n== a genuine conflict is still outranked ==")
check("Palacios -> Anthis claims first", by["Richard Palacios"]["status"] == "active")
check("Anthis -> Murphy is genuinely outranked (different partner)",
      by["Larry Anthis"]["status"] == "outranked", str(by["Larry Anthis"]))

print("\n== paying for someone implies a pairing ==")
check("Jacob Williams gets an IMPLIED request despite writing none",
      "Jacob Williams" in by and by["Jacob Williams"]["implied"],
      str(by.get("Jacob Williams")))
check("...resolved to the person who paid",
      by["Jacob Williams"]["partner"] == "Daniel South",
      str(by.get("Jacob Williams", {}).get("partner")))

print("\n== a host plus three guests all play together ==")
for g in ("Mark Villa", "Orlando Kypuros", "Jacob Williams"):
    check(f"{g} is CONFIRMED with Daniel South, not outranked",
          by[g]["status"] == "confirmed" and not by[g]["locked_out"],
          f"{by[g]['status']} / {by[g]['locked_reason']}")
    check(f"...and {g} resolves 'Dan South' to Daniel South",
          by[g]["partner"] == "Daniel South", str(by[g]["partner"]))
check("all three are flagged as a host group",
      all(by[g]["host_group"] for g in
          ("Mark Villa", "Orlando Kypuros", "Jacob Williams")))

print("\n== the fourth guest does not fit a foursome ==")
conn = sqlite3.connect(tmp)
conn.execute("INSERT INTO items (id, customer, customer_id, item_name, holes,"
             " partner_request, order_date, created_at, notes, transaction_status)"
             " VALUES (99,'Fourth Guest',99,'TGF SAN ANTONIO CHAMPIONSHIP','18',"
             "'Dan South','2026-08-01','2026-08-01','Purchased by Daniel South','active')")
conn.commit(); conn.close()
by2 = {r["requester"]: r for r in db.get_event_partner_requests(1, db_path=tmp)["requests"]}
check("a fourth guest IS outranked — a foursome is full",
      by2["Fourth Guest"]["status"] == "outranked", str(by2["Fourth Guest"]))
check("...with a reason naming the limit",
      "foursome is full" in (by2["Fourth Guest"]["locked_reason"] or ""),
      str(by2["Fourth Guest"]["locked_reason"]))
check("the first three guests are unaffected",
      all(by2[g]["status"] == "confirmed" for g in
          ("Mark Villa", "Orlando Kypuros", "Jacob Williams")))

print("\n== unmatched text still surfaces for the manager ==")
check("Pat Youngs -> John White stays unmatched (not on roster)",
      not by["Pat Youngs"]["matched"], str(by["Pat Youngs"]))

print("\n== a manager can ADD a request that never came in ==")
# Kerry 2026-07-30: "I also need the ability to add a Playing Partner
# Request in the requests drop down."
check("Michael Murphy has no request to begin with",
      "Michael Murphy" not in by)
added = db.set_partner_request_match(1, "Michael Murphy", "Pat Youngs",
                                     db_path=tmp)["requests"]
by3 = {r["requester"]: r for r in added}
check("...and now he has one", "Michael Murphy" in by3, str(list(by3)))
check("...pointed at the player the manager picked",
      by3.get("Michael Murphy", {}).get("partner") == "Pat Youngs",
      str(by3.get("Michael Murphy")))
check("...badged as manager-added, not as a signup request",
      by3["Michael Murphy"]["added"] and by3["Michael Murphy"]["manual"],
      str(by3["Michael Murphy"]))
check("...and it does NOT jump the queue — it sits at his signup position",
      list(by3).index("Michael Murphy") < list(by3).index("Mark Villa"),
      f"{list(by3)}")
check("adding one for a player who isn't on the roster is refused",
      _refused(lambda: db.set_partner_request_match(
          1, "Ghost Player", "Pat Youngs", db_path=tmp)))
check("clearing it removes the request again",
      "Michael Murphy" not in {
          r["requester"] for r in db.set_partner_request_match(
              1, "Michael Murphy", None, db_path=tmp)["requests"]})

print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL PARTNER-REQUEST TESTS PASSED")
