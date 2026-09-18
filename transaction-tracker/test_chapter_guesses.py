"""Chapter guesses are listed with their evidence, and only Kerry's
per-person confirmation turns one into the record.

Kerry 2026-09-16 (item B): "Give me a list of customers you guessed on
that didn't already have chapters and I'll confirm" / "Do it".

`customers.chapter` is the HOME chapter and is never written from
`items.chapter` (an order's chapter is where the event was). The card
falls back to the latest order's chapter when the profile is blank —
a guess. This lists them; `confirm` writes only blank profiles, only
for the ids given, only to a real chapter.

Run: python3 test_chapter_guesses.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db"); os.environ["DATABASE_PATH"] = DB
logging.disable(logging.WARNING)
from email_parser import database as db                          # noqa: E402
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)

with db._connect(DB) as conn:
    conn.executescript("""
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT,
            last_name TEXT, chapter TEXT, current_player_status TEXT);
        CREATE TABLE handicap_player_links (player_name TEXT PRIMARY KEY,
            customer_id INTEGER, customer_name TEXT);
        CREATE TABLE items (id INTEGER PRIMARY KEY, customer_id INTEGER,
            chapter TEXT, order_date TEXT);
    """)
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", [
        (1, "Ana", "Blank", None, "active_member"),      # SA twice, Austin once, latest Austin
        (2, "Ben", "Set", "Austin", "active_member"),    # profile set — not a guess
        (3, "Cal", "Solo", "", "guest"),                 # one chapter only
        (4, "Dee", "NoOrders", None, "guest"),           # linked, no orders
    ])
    conn.executemany("INSERT INTO handicap_player_links VALUES (?,?,?)", [
        ("BLANK, Ana", 1, "Ana Blank"), ("SET, Ben", 2, "Ben Set"),
        ("SOLO, Cal", 3, "Cal Solo"), ("NOORDERS, Dee", 4, "Dee NoOrders")])
    conn.executemany("INSERT INTO items (customer_id, chapter, order_date) VALUES (?,?,?)", [
        (1, "San Antonio", "2026-05-01"), (1, "San Antonio", "2026-06-01"),
        (1, "Austin", "2026-09-01"), (2, "Austin", "2026-09-01"),
        (3, "Austin", "2026-09-01")])
    conn.commit()

r = db.audit_chapter_guesses(db_path=DB)
by = {g["customer_id"]: g for g in r["guessed"]}
check("only blank-profile linked customers with orders are listed", set(by) == {1, 3}, sorted(by))
check("the guess is the LATEST order's chapter (what the card uses)", by[1]["guess"] == "Austin", by[1])
check("…with the evidence: orders by chapter and the majority",
      by[1]["orders_by_chapter"] == {"San Antonio": 2, "Austin": 1} and by[1]["majority"] == "San Antonio"
      and by[1]["unanimous"] is False, by[1])
check("a one-chapter history is unanimous", by[3]["unanimous"] is True)

r2 = db.audit_chapter_guesses({1: "San Antonio", 2: "San Antonio", 3: "Mars", 99: "Austin"}, db_path=DB)
check("Kerry's confirmation writes the blank profile", any(c["customer_id"] == 1 for c in r2["confirmed"]))
with db._connect(DB) as conn:
    ch = {r["customer_id"]: r["chapter"] for r in conn.execute("SELECT customer_id, chapter FROM customers")}
check("…and it is now the record", ch[1] == "San Antonio", ch)
check("a profile that already has a chapter is refused, never overwritten",
      ch[2] == "Austin" and any(x["customer_id"] == 2 for x in r2["refused"]))
check("an unknown chapter is refused", ch[3] == "" and any(x["customer_id"] == 3 for x in r2["refused"]))
check("an unknown customer is refused", any(x["customer_id"] == 99 for x in r2["refused"]))
check("a confirmed customer leaves the guess list", 1 not in {g["customer_id"] for g in r2["guessed"]})
try: os.unlink(DB)
except OSError: pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
