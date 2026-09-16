"""An ingest may not erase what it does not carry.

Kerry 2026-09-16, the morning after s9.23: "This shouldn't say Hole
Group 1. It should just say Hole 1. Where's that coming from? Also,
this lost the hole assignments that I had assigned yesterday. Why'd it
screw everything up? ... If the tees are in ROSTER, they should
automatically show up in PAIRINGS."

One cause. The closeout ran the Team Net board ingest on the finished
event; that board knows who rode together and in what FINISH order, and
nothing else. `_write_event_pairings_from_groups` deleted the sheet and
wrote the board back with `slot=None` -> "Group N", no tee, no
customer_id. Then the starter sheet prefixed "Hole " onto "Group 1",
the PAIRINGS tab read a blank tee for everyone, and the seat-keyed
blinds pointed at seats that no longer existed.

Four properties, checked here:
  1. the writer hands an existing hole label back to a group of the
     same people when the ingest brings none;
  2. the writer carries each player's tee (and customer_id) forward;
  3. `get_event_pairings` reads a blank tee from the ROSTER by
     customer_id, so the sheet and the ROSTER tab cannot disagree;
  4. a generic "Group N" label is never printed as "Hole Group N";
  and the repair (`relabel_event_pairings`) re-labels + re-orders
  through the normal save, so the blinds re-seat with it.

Run: python3 test_pairings_ingest_preserve.py
"""
import os, sys, tempfile, logging, re

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

EV = 3302
def seat(pos, name, cid, tee=None):
    return {"name": name, "cart_pos": pos, "customer_id": cid,
            "tee_choice": tee, "handicap_index": None}

with db._connect(DB) as conn:
    conn.executescript("""
        CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT,
                             event_date TEXT, chapter TEXT, status TEXT,
                             format TEXT);
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
                                first_name TEXT, last_name TEXT,
                                current_player_status TEXT, pace_rating INTEGER,
                                ambassador INTEGER, group_captain INTEGER,
                                solo_back_ok INTEGER, account_status TEXT);
        CREATE TABLE customer_aliases (id INTEGER PRIMARY KEY, alias_type TEXT,
                                       alias_value TEXT, customer_id INTEGER);
        CREATE TABLE items (id INTEGER PRIMARY KEY, customer TEXT,
                            customer_id INTEGER, item_name TEXT, event_id INTEGER,
                            holes TEXT, tee_choice TEXT, partner_request TEXT,
                            order_date TEXT, created_at TEXT, notes TEXT,
                            order_id TEXT, customer_email TEXT, user_status TEXT,
                            transaction_status TEXT, parent_item_id INTEGER,
                            email_uid TEXT, merchant TEXT);
        CREATE TABLE event_aliases (canonical_event_name TEXT, alias_name TEXT);
        CREATE TABLE customer_memberships (customer_id INTEGER, started_at TEXT);
        CREATE TABLE handicap_rounds (player_name TEXT, round_date TEXT);
        CREATE TABLE handicap_player_links (player_name TEXT, customer_id INTEGER);
        CREATE TABLE rsvps (id INTEGER PRIMARY KEY, matched_event TEXT,
                            event_id INTEGER, player_name TEXT, status TEXT,
                            rsvp_status TEXT, customer_id INTEGER,
                            player_email TEXT, received_at TEXT);
    """)
    db._ensure_pairing_tables(conn)
    conn.execute("""INSERT INTO events (id, item_name, event_date, chapter, status,
                    format) VALUES (3302, 's9.23 The Quarry', '2026-09-15',
                    'San Antonio', 'active', '9-hole shotgun')""")
    people = [(42, "Gus", "Vasquez", "50-64"), (802, "Christopher", "Espinosa", "<50"),
              (100, "Michelle", "Delcarmen", "Forward"), (136, "Pat", "Youngs", "65+"),
              (6, "Jeff", "Rideout", "50-64"), (23, "Mary", "Wade", "Forward"),
              (7, "Luke", "Mazanec", "<50")]
    for i, (cid, fn, ln, tee) in enumerate(people, start=1):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) "
                     "VALUES (?,?,?)", (cid, fn, ln))
        conn.execute("""INSERT INTO items (id, customer, customer_id, item_name,
                        event_id, holes, tee_choice, transaction_status, order_date)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                     (i, f"{fn} {ln}", cid, "s9.23 The Quarry", EV, "9", tee,
                      "active", "2026-09-10"))
    conn.commit()

# ── The sheet Kerry built: hole labels, tees on the rows ─────────────
db.save_event_pairings(EV, {"9": [
    {"group_num": 1, "slot_label": "3", "players": [
        seat(1, "Gus Vasquez", 42, "50-64"), seat(2, "Christopher Espinosa", 802, "<50"),
        seat(3, "Michelle Delcarmen", 100, "Forward")]},
    {"group_num": 2, "slot_label": "4", "players": [
        seat(1, "Jeff Rideout", 6, "50-64"), seat(3, "Mary Wade", 23, "Forward")]},
]}, db_path=DB)
with db._connect(DB) as conn:
    conn.execute("""INSERT INTO blind_draws (event_id, event_date, chapter, holes,
                    group_num, cart_pos, slot_key, customer_id, player_name, source)
                    VALUES (?, '2026-09-15', 'San Antonio', '9', 1, 4, '9:1:4',
                            136, 'Pat Youngs', 'app')""", (EV,))
    conn.commit()

print("1. The Team Net board ingest (finish order, no labels, no tees)")
with db._connect(DB) as conn:
    n = db._write_event_pairings_from_groups(conn, EV, [
        {"slot": None, "players": [{"name": "Jeff Rideout"}, {"name": "Mary Wade"}]},
        {"slot": None, "players": [{"name": "Gus Vasquez"},
                                   {"name": "Christopher Espinosa"},
                                   {"name": "Michelle Delcarmen"}]},
    ], holes="9")
    conn.commit()
    rows = conn.execute("""SELECT group_num, slot_label, player_name, tee_choice,
                           customer_id FROM event_pairings WHERE event_id=?
                           ORDER BY group_num, cart_pos""", (EV,)).fetchall()
check("five rows written", n == 5, n)
labels = {r["player_name"]: r["slot_label"] for r in rows}
check("Rideout's group keeps its hole label 4 through a label-less ingest",
      labels.get("Jeff Rideout") == "4", labels)
check("Vasquez's group keeps hole 3", labels.get("Gus Vasquez") == "3", labels)
tees = {r["player_name"]: r["tee_choice"] for r in rows}
check("tees carried forward on every row",
      tees == {"Jeff Rideout": "50-64", "Mary Wade": "Forward",
               "Gus Vasquez": "50-64", "Christopher Espinosa": "<50",
               "Michelle Delcarmen": "Forward"}, tees)
cids = {r["player_name"]: r["customer_id"] for r in rows}
check("customer_id carried forward (principle 6)",
      cids.get("Michelle Delcarmen") == 100 and cids.get("Jeff Rideout") == 6, cids)

print("2. A label the ingest DOES carry still wins")
with db._connect(DB) as conn:
    db._write_event_pairings_from_groups(conn, EV, [
        {"slot": "1A", "players": [{"name": "Jeff Rideout"}, {"name": "Mary Wade"}]},
    ], holes="9")
    conn.commit()
    lab = conn.execute("SELECT slot_label FROM event_pairings WHERE event_id=? "
                       "AND player_name='Jeff Rideout'", (EV,)).fetchone()[0]
check("tee-sheet label 1A overrides the remembered 4", lab == "1A", lab)

print("3. The tee is read from the ROSTER when the row is blank")
with db._connect(DB) as conn:
    conn.execute("UPDATE event_pairings SET tee_choice=NULL, customer_id=NULL "
                 "WHERE event_id=?", (EV,))
    conn.commit()
pr = db.get_event_pairings(EV, db_path=DB)
got = {p["name"]: p["tee_choice"] for g in pr["9"] for p in g["players"]}
check("blank row tee resolved from items by name/customer",
      got == {"Jeff Rideout": "50-64", "Mary Wade": "Forward"}, got)

print("4. 'Group N' is never printed as 'Hole Group N'")
src = open(os.path.join(os.path.dirname(__file__), "email_parser/database.py")).read()
src_nc = "\n".join(l.split("#")[0] for l in src.splitlines())
check("start_line guards a generic Group N label",
      re.search(r"_generic\s*=\s*bool\(re\.match\(r\"\^group", src_nc) is not None
      and "if _shotgun and _generic:" in src_nc)

print("5. The repair relabels + reorders through the normal save and re-seats")
db.save_event_pairings(EV, {"9": [
    {"group_num": 1, "slot_label": "Group 1", "players": [
        seat(1, "Jeff Rideout", 6), seat(3, "Mary Wade", 23)]},
    {"group_num": 2, "slot_label": "Group 2", "players": [
        seat(1, "Gus Vasquez", 42), seat(2, "Christopher Espinosa", 802),
        seat(3, "Michelle Delcarmen", 100)]},
]}, db_path=DB)
dry = db.relabel_event_pairings(EV, "9", {2: "3", 1: "4"}, apply=False, db_path=DB)
check("dry run does not apply", dry["applied"] is False
      and [p["now_label"] for p in dry["plan"]] == ["3", "4"], dry)
res = db.relabel_event_pairings(EV, "9", {2: "3", 1: "4"}, apply=True, db_path=DB)
pr = db.get_event_pairings(EV, db_path=DB)
order = [(g["group_num"], g["slot_label"], [p["name"] for p in g["players"]])
         for g in pr["9"]]
check("groups renumbered in hole order with hole labels",
      order[0][:2] == (1, "3") and "Gus Vasquez" in order[0][2]
      and order[1][:2] == (2, "4") and "Jeff Rideout" in order[1][2], order)
check("tees persisted by the repair (from the roster)",
      all(p["tee_choice"] for g in pr["9"] for p in g["players"]),
      [(p["name"], p["tee_choice"]) for g in pr["9"] for p in g["players"]])
with db._connect(DB) as conn:
    bl = conn.execute("SELECT slot_key FROM blind_draws WHERE event_id=? "
                      "AND customer_id=136", (EV,)).fetchone()[0]
check("Youngs' blind re-seated into hole 3's open seat (9:1:4)", bl == "9:1:4", bl)
check("unknown group in the map is refused",
      "error" in db.relabel_event_pairings(EV, "9", {9: "1A"}, db_path=DB))

print()
print(f"{'FAILED: ' + ', '.join(F) if F else 'ALL PASS'} "
      f"({12 - len(F)}/12)")
sys.exit(1 if F else 0)
