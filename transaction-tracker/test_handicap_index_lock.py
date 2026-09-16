"""The handicap lock, and ONE index on every surface.

Kerry 2026-09-16, the morning after s9.23 / a9.23:
  "ROSTER handicaps need to lock after an event begins. Past events
   should not update to current handicap indexes."
  "PAIRINGS handicap indexes are not matching those in ROSTER. PAIRINGS
   handicaps are not correct, which then affects the Starter Sheet
   handicaps."

Two defects. (1) `_roster_handicap_index_map` — the index PAIRINGS, the
generator and the starter sheet read — was its own query: a plain
AVERAGE of the last twenty differentials, while the ROSTER showed the
TGF index (`compute_handicap_index`: best-N of twenty, x0.96, WHS
adjustment). Always higher, and a two-round first-timer got a number
the ROSTER rightly refused him. (2) Every surface read TODAY's index,
so a past event's sheet drifted whenever a round was posted.

The fix: one computation, `get_all_handicap_players(as_of=...)`, and a
lock date per event (`_event_index_as_of`) — its own date once it has
teed off, None before — read by ROSTER (/api/events publishes it, the
page fetches that day's map), PAIRINGS, the generator, the starter
sheet and the flights report. Nothing is stored: the rounds posted
before a date do not change, so the number does not either.

Run: python3 test_handicap_index_lock.py
"""
import os, sys, tempfile, logging, re
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.WARNING)
from email_parser import database as db                          # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

TODAY = db.today_central()
EV_DATE = (TODAY - timedelta(days=1)).isoformat()        # played last night
FUTURE = (TODAY + timedelta(days=7)).isoformat()

with db._connect(DB) as conn:
    conn.executescript("""
        CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT,
                             event_date TEXT, chapter TEXT, status TEXT,
                             format TEXT, start_time TEXT);
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
            first_name TEXT, last_name TEXT, chapter TEXT,
            current_player_status TEXT, pace_rating INTEGER, ambassador INTEGER,
            group_captain INTEGER, solo_back_ok INTEGER, account_status TEXT,
            starting_handicap_18 REAL, starting_handicap_set_at TEXT,
            starting_handicap_set_by TEXT, starting_handicap_note TEXT);
        CREATE TABLE customer_aliases (id INTEGER PRIMARY KEY, alias_type TEXT,
                                       alias_value TEXT, customer_id INTEGER);
        CREATE TABLE handicap_player_links (player_name TEXT PRIMARY KEY,
                                            customer_id INTEGER, customer_name TEXT);
        CREATE TABLE handicap_rounds (id INTEGER PRIMARY KEY, player_name TEXT,
            differential REAL, round_date TEXT, nine TEXT, scoring_round_id INTEGER);
        CREATE TABLE handicap_settings (key TEXT PRIMARY KEY, value TEXT,
                                        updated_at TEXT);
        CREATE TABLE items (id INTEGER PRIMARY KEY, customer TEXT,
            customer_id INTEGER, item_name TEXT, event_id INTEGER, holes TEXT,
            tee_choice TEXT, partner_request TEXT, order_date TEXT, created_at TEXT,
            notes TEXT, order_id TEXT, customer_email TEXT, user_status TEXT,
            transaction_status TEXT, parent_item_id INTEGER, email_uid TEXT,
            merchant TEXT, chapter TEXT);
        CREATE TABLE event_aliases (canonical_event_name TEXT, alias_name TEXT);
        CREATE TABLE customer_memberships (customer_id INTEGER, started_at TEXT);
        CREATE TABLE rsvps (id INTEGER PRIMARY KEY, matched_event TEXT,
            event_id INTEGER, player_name TEXT, status TEXT, rsvp_status TEXT,
            customer_id INTEGER, player_email TEXT, received_at TEXT);
    """)
    db._ensure_pairing_tables(conn)
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format) "
                 "VALUES (1, 's9.23 The Quarry', ?, 'San Antonio', 'active', '9-hole')",
                 (EV_DATE,))
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format) "
                 "VALUES (2, 's9.24 Future', ?, 'San Antonio', 'active', '9-hole')",
                 (FUTURE,))
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (6, 'Jeff', 'Rideout')")
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (7, 'Jeff', 'King')")
    conn.execute("INSERT INTO handicap_player_links VALUES ('RIDEOUT, Jeff', 6, 'Jeff Rideout')")
    conn.execute("INSERT INTO handicap_player_links VALUES ('KING, Jeff', 7, 'Jeff King')")
    # Rideout: eight rounds BEFORE the event, spread so the average and the
    # best-N differ; one round posted ON event night (the round itself)
    # and one after.
    before = [(EV_DATE[:4] + "-01-%02d" % (d + 1), diff)
              for d, diff in enumerate([18.0, 12.0, 20.0, 11.0, 16.0, 13.0, 19.0, 10.0])]
    for i, (rd, diff) in enumerate(before, start=1):
        conn.execute("INSERT INTO handicap_rounds (id, player_name, differential, round_date) "
                     "VALUES (?, 'RIDEOUT, Jeff', ?, ?)", (i, diff, rd))
    conn.execute("INSERT INTO handicap_rounds (id, player_name, differential, round_date) "
                 "VALUES (90, 'RIDEOUT, Jeff', 2.0, ?)", (EV_DATE,))            # the night's round
    conn.execute("INSERT INTO handicap_rounds (id, player_name, differential, round_date) "
                 "VALUES (91, 'RIDEOUT, Jeff', 1.0, ?)", (TODAY.isoformat(),))  # posted today
    # King: two rounds only — no established index.
    conn.execute("INSERT INTO handicap_rounds (id, player_name, differential, round_date) "
                 "VALUES (95, 'KING, Jeff', 5.0, ?)", (before[0][0],))
    conn.execute("INSERT INTO handicap_rounds (id, player_name, differential, round_date) "
                 "VALUES (96, 'KING, Jeff', 6.4, ?)", (before[1][0],))
    for i, (nm, cid) in enumerate([("Jeff Rideout", 6), ("Jeff King", 7)], start=1):
        conn.execute("INSERT INTO items (id, customer, customer_id, item_name, event_id, holes, "
                     "tee_choice, transaction_status, order_date) VALUES (?,?,?,?,1,'9','50-64','active',?)",
                     (i, nm, cid, "s9.23 The Quarry", before[0][0]))
    conn.commit()

cfg = db.get_handicap_settings(DB)
idx_before = db.compute_handicap_index([d for _, d in before], cfg)
idx_now = db.compute_handicap_index([1.0, 2.0] + [d for _, d in before], cfg)

print("1. ONE computation, locked to a date")
cur = {p["player_name"]: p for p in db.get_all_handicap_players(DB)}
lock = {p["player_name"]: p for p in db.get_all_handicap_players(DB, as_of=EV_DATE)}
check("today's index counts the night's round and this morning's",
      cur["RIDEOUT, Jeff"]["handicap_index"] == idx_now,
      (cur["RIDEOUT, Jeff"]["handicap_index"], idx_now))
check("the as-of index is the one in effect that morning — rounds BEFORE the day only",
      lock["RIDEOUT, Jeff"]["handicap_index"] == idx_before,
      (lock["RIDEOUT, Jeff"]["handicap_index"], idx_before))
check("…and it differs from today's, so the lock is doing something",
      idx_before != idx_now, (idx_before, idx_now))
check("an as-of index carries no trend (a today-relative reading)",
      lock["RIDEOUT, Jeff"]["handicap_trend"] is None)
check("two rounds is not an index, as-of or not",
      cur["KING, Jeff"]["handicap_index"] is None and lock["KING, Jeff"]["handicap_index"] is None)

print("2. PAIRINGS reads the ROSTER's number, not an average")
with db._connect(DB) as conn:
    m = db._roster_handicap_index_map(conn, db_path=DB)
    ml = db._roster_handicap_index_map(conn, as_of=EV_DATE, db_path=DB)
avg_now = sum([1.0, 2.0] + [d for _, d in before]) / 10
check("the pairings map equals the roster index", m.get("jeff rideout") == idx_now, m.get("jeff rideout"))
check("…keyed by customer_id too (principle 6)", m.get(("c", 6)) == idx_now)
check("…and is NOT the old plain average", m.get("jeff rideout") != round(avg_now, 1), avg_now)
check("a two-round player has no index on PAIRINGS either", "jeff king" not in m)
check("the locked map carries the as-of index", ml.get(("c", 6)) == idx_before)

print("3. The lock date")
check("a past event locks to its own date", db._event_index_as_of({"event_date": EV_DATE}) == EV_DATE)
check("a future event is not locked", db._event_index_as_of({"event_date": FUTURE}) is None)
check("today, before the tee time, is not locked",
      db._event_index_as_of({"event_date": TODAY.isoformat(), "start_time": "23:59"}) is None)
check("no event, no lock", db._event_index_as_of(None) is None)
evs = {e["id"]: e for e in db.get_all_events(DB)}
check("/api/events publishes handicap_as_of on every event",
      evs[1]["handicap_as_of"] == EV_DATE and evs[2]["handicap_as_of"] is None,
      (evs[1].get("handicap_as_of"), evs[2].get("handicap_as_of")))

print("4. A saved sheet reads the locked index over its own snapshot")
db.save_event_pairings(1, {"9": [{"group_num": 1, "slot_label": "4", "players": [
    {"name": "Jeff Rideout", "cart_pos": 1, "customer_id": 6, "tee_choice": "50-64",
     "handicap_index": 16.3},     # the wrong average the old map saved
    {"name": "Jeff King", "cart_pos": 2, "customer_id": 7, "tee_choice": "50-64",
     "handicap_index": 5.7}]}]}, db_path=DB)
pr = db.get_event_pairings(1, db_path=DB)
got = {p["name"]: p["handicap_index"] for p in pr["9"][0]["players"]}
check("Rideout's sheet index is the as-of index, not the saved 16.3",
      got["Jeff Rideout"] == idx_before, got)
check("King keeps the snapshot only because nothing computable exists",
      got["Jeff King"] == 5.7, got)

print("5. Structure — the class, not the instance")
src = open(os.path.join(os.path.dirname(__file__), "email_parser/database.py"), encoding="utf-8").read()
i = src.index("def _roster_handicap_index_map"); body = src[i:src.index("\ndef ", i + 1)]
check("_roster_handicap_index_map no longer averages differentials itself",
      "AVG(differential)" not in body and "get_all_handicap_players(" in body)
for name, needle in (("get_event_pairings", "_event_index_as_of("),
                     ("generate_event_pairings", "_event_index_as_of(ev)"),
                     ("get_event_print_pack", "as_of=_event_index_as_of(ev)"),
                     ("event_flights_report", "as_of=_event_index_as_of(ev)"),
                     ("get_all_events", '"handicap_as_of"')):
    j = src.index(f"def {name}("); fb = src[j:src.index("\ndef ", j + 1)]
    check(f"{name} honours the lock", needle in fb)
app = open(os.path.join(os.path.dirname(__file__), "app.py"), encoding="utf-8").read()
check("the /pairings GET honours the lock", "_roster_handicap_index_map(\n                _pconn, as_of=_event_index_as_of(" in app)
check("/api/handicaps/index-map takes ?as_of=", 'request.args.get("as_of")' in app)
html = open(os.path.join(os.path.dirname(__file__), "templates/events.html"), encoding="utf-8").read()
check("the page fetches the locked map for a started event", "async function ensureHcpAsOf(ev)" in html
      and "index-map?as_of=" in html)
check("the ONE accessor takes the event", "function hcpEntryFor(name, customerId, ev)" in html)
check("no roster site reads the live map by name any more",
      "handicapIndexMap[(r.customer || \"\").toLowerCase()]" not in html)
check("the detail expand and the pairings panel both wait for it",
      html.count("ensureHcpAsOf(") >= 3)
check("an unlabelled nine is decided by the event's own scorecards (Avery Ranch)",
      "event_used" in src[src.index("def _print_pack_tee_basis") if "def _print_pack_tee_basis" in src
                          else src.index("event_used"):])

try:
    os.unlink(DB)
except OSError:
    pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
