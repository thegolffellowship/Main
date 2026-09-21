"""The person in a seat is decided by the NAME the manager sees.

Kerry 2026-09-18: "pairings switched Jeff Rideout and Justin Angelone's
tees when I swapped their cart assignments." The page moved the name and
not the id; the save trusted the id; the read resolved tee and index by
that id. Two boundary checks now hold: the save resolves the seat's
customer_id from the name (a payload id is kept only when it names the
same person), and the read corrects a stale id already on file.

Run: python3 test_pairings_seat_identity.py
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
        CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, event_date TEXT,
                             chapter TEXT, status TEXT);
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT,
                                last_name TEXT, account_status TEXT);
        CREATE TABLE customer_aliases (id INTEGER PRIMARY KEY, alias_type TEXT,
                                       alias_value TEXT, customer_id INTEGER);
    """)
    db._ensure_pairing_tables(conn)
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status) "
                 "VALUES (1, 's18.11 CEDAR CREEK', '2026-09-19', 'San Antonio', 'active')")
    conn.executemany("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)",
                     [(6, "Jeff", "Rideout"), (900, "Justin", "Angelone"), (729, "Joe", "Mejia")])
    conn.execute("INSERT INTO customer_aliases (alias_type, alias_value, customer_id) VALUES ('name', 'Jose Mejia', 729)")
    conn.commit()

def seat(pos, name, cid, tee):
    return {"name": name, "cart_pos": pos, "customer_id": cid, "tee_choice": tee, "handicap_index": None}

print("1. The save resolves the seat by NAME")
# The swapped-but-stale payload: names moved, ids did not.
db.save_event_pairings(1, {"18": [{"group_num": 1, "slot_label": "8:20 AM", "players": [
    seat(1, "Jeff Rideout", 900, "50-64"), seat(2, "Justin Angelone", 6, "<50"),
    seat(3, "Jose Mejia", 6, "50-64"),          # alias name, wrong id
    seat(4, "Randy Guest", None, "<50"),        # a guest, no profile
]}]}, db_path=DB)
with db._connect(DB) as conn:
    got = {r["player_name"]: r["customer_id"] for r in conn.execute(
        "SELECT player_name, customer_id FROM event_pairings WHERE event_id = 1")}
check("Rideout's seat stores Rideout's id, not the payload's", got["Jeff Rideout"] == 6, got)
check("Angelone's seat stores Angelone's id", got["Justin Angelone"] == 900, got)
check("an alias resolves to the same person", got["Jose Mejia"] == 729, got)
check("a guest stays unlinked", got["Randy Guest"] is None, got)

print("2. The read corrects a stale id already on file")
with db._connect(DB) as conn:
    conn.execute("UPDATE event_pairings SET customer_id = 900 WHERE player_name = 'Jeff Rideout'")
    conn.commit()
pr = db.get_event_pairings(1, db_path=DB)
byname = {p["name"]: p["customer_id"] for p in pr["18"][0]["players"]}
check("a stale id is corrected on read", byname.get("Jeff Rideout") == 6, byname)
with db._connect(DB) as conn:
    n = db._backfill_customer_id_on_event_pairings(conn, 1)
check("idempotent once corrected", n == 0, n)

print("3. A renamed profile keeps its id (the id is the truth, the name the snapshot)")
with db._connect(DB) as conn:
    conn.execute("UPDATE customers SET first_name = 'Jeffrey' WHERE customer_id = 6")
    conn.commit()
pr = db.get_event_pairings(1, db_path=DB)
byname = {p["name"]: p["customer_id"] for p in pr["18"][0]["players"]}
check("the seat reads the NEW name through its id, id untouched",
      byname.get("Jeffrey Rideout") == 6, byname)
print("4. swap_event_seats moves the whole person through the normal save")
with db._connect(DB) as conn:
    conn.execute("UPDATE customers SET first_name = 'Jeff' WHERE customer_id = 6")
    conn.commit()
db.save_event_pairings(1, {"18": [
    {"group_num": 1, "slot_label": "8:20 AM", "players": [seat(1, "Justin Angelone", 900, "<50"), seat(2, "Jeff Rideout", 6, "50-64")]},
    {"group_num": 2, "slot_label": "8:30 AM", "players": [seat(1, "Joe Mejia", 729, "<50")]}]}, db_path=DB)
dry = db.swap_event_seats(1, "joe mejia", "Justin Angelone", db_path=DB)
check("dry run plans and does not apply", dry["applied"] is False and dry["plan"]["a"]["to"] == "8:20 AM seat 1", dry)
res = db.swap_event_seats(1, "Joe Mejia", "Justin Angelone", apply=True, db_path=DB)
pr = db.get_event_pairings(1, db_path=DB)
seats = {(g["slot_label"], p["cart_pos"]): (p["name"], p["customer_id"]) for g in pr["18"] for p in g["players"]}
check("the people swapped seats, ids with them",
      seats[("8:20 AM", 1)] == ("Joe Mejia", 729) and seats[("8:30 AM", 1)] == ("Justin Angelone", 900), seats)
check("an unknown name is refused", "error" in db.swap_event_seats(1, "Nobody Here", "Jeff Rideout", db_path=DB))
try: os.unlink(DB)
except OSError: pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
