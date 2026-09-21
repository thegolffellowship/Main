"""NEW = a member playing their FIRST EVENT AS A MEMBER (Kerry 2026-09-18,
confirmed: "Correct on your NEW badge understanding. Ship it.").

Not "joined since our last event" (missed Bear Clarkson, who joined
earlier but had not played as a member); not "first-year member"
(tagged Lewis, Wallace and Schneider, who had all played as members).
1T is independent: first TGF event ever. Both can show.

Run: python3 test_new_badge.py
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
        CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, event_date TEXT);
        CREATE TABLE items (id INTEGER PRIMARY KEY, customer_id INTEGER, event_id INTEGER,
            item_name TEXT, parent_item_id INTEGER, transaction_status TEXT);
        CREATE TABLE handicap_rounds (id INTEGER PRIMARY KEY, player_name TEXT, round_date TEXT);
        CREATE TABLE handicap_player_links (player_name TEXT, customer_id INTEGER);
    """)
    conn.executemany("INSERT INTO events VALUES (?,?,?)", [
        (1, "a9.23 The Quarry", "2026-09-15"), (2, "s18.11 CEDAR CREEK", "2026-09-19"), (3, "a9.20", "2026-08-25")])
    # Wade Lewis: member since 2026-09-01, played a9.23 as a member -> NOT new
    conn.execute("INSERT INTO items VALUES (1, 817, 1, 'a9.23 The Quarry', NULL, 'active')")
    # Bear Clarkson: member since 2026-09-05, no event since -> NEW
    # Louis Schneider: member since 2026-03-01, a round posted in June -> NOT new
    conn.execute("INSERT INTO handicap_player_links VALUES ('SCHNEIDER, Louis', 85)")
    conn.execute("INSERT INTO handicap_rounds (player_name, round_date) VALUES ('SCHNEIDER, Louis', '2026-06-10')")
    # Justin Angelone: played a9.20 as a GUEST (before membership 2026-09-10), nothing since -> NEW
    conn.execute("INSERT INTO items VALUES (2, 709, 3, 'a9.20', NULL, 'active')")
    # A credited registration does not count as played
    conn.execute("INSERT INTO items VALUES (3, 767, 1, 'a9.23 The Quarry', NULL, 'credited')")
    conn.commit()
    EV = "2026-09-19"
    rows = {
        "Lewis":    {"customer_id": 817, "first_member_start": "2026-09-01"},
        "Clarkson": {"customer_id": 767, "first_member_start": "2026-09-05"},
        "Schneider":{"customer_id": 85,  "first_member_start": "2026-03-01"},
        "Angelone": {"customer_id": 709, "first_member_start": "2026-09-10"},
        "Future":   {"customer_id": 900, "first_member_start": "2026-09-20"},
        "Guest":    {"customer_id": 901, "first_member_start": None},
    }
    got = {k: db._first_event_as_member(conn, v, EV) for k, v in rows.items()}
check("a member who played an event since joining is NOT new (Lewis)", got["Lewis"] is False, got)
check("a member who joined earlier but has not played as a member IS new (Clarkson)", got["Clarkson"] is True, got)
check("a posted round since joining counts as having played (Schneider)", got["Schneider"] is False, got)
check("play BEFORE the membership started does not count (Angelone)", got["Angelone"] is True, got)
check("a membership starting after the event is not new yet", got["Future"] is False, got)
check("no membership, no NEW badge", got["Guest"] is False, got)
try: os.unlink(DB)
except OSError: pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
