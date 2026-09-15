"""A saved tee sheet is linked to the PERSON, not to a name string.

Kerry 2026-09-15: "I updated a Customer name and alias Jose to Joe Mejia.
It updated on the ROSTER but not in the pairings. It needs to be directly
linked in PAIRINGS to the ROSTER and Customer ID so it changes immediately
if customer profile is changed."

`event_pairings.player_name` was a snapshot taken at save time, so the
rename moved the roster and left the sheet reading "Jose Mejia" — which
then missed every name-keyed lookup downstream: his handicap fell to a
dash and his badges went with it. One root cause, four symptoms.

Run: python3 test_pairings_identity.py
"""
import os, sqlite3, sys, tempfile, contextlib, io, logging
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
logging.getLogger("email_parser.database").setLevel(logging.ERROR)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-pid-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
EV = 3302
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (?, 's9.23 The Quarry', '2026-09-15', 'San Antonio', 'active')", (EV,))
c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) VALUES (729, 'Jose', 'Mejia', 'San Antonio', 'active')")
c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) VALUES (87, 'Adam', 'Baker', 'San Antonio', 'active')")
c.commit()

sheet = {"9": [{"group_num": 1, "slot_label": "1B", "players": [
    {"name": "Jose Mejia", "cart_pos": 1, "tee_choice": "50-64", "handicap_index": None},
    {"name": "Adam Baker", "cart_pos": 2, "tee_choice": "<50", "handicap_index": 6.6},
    {"name": "Randy Guest", "cart_pos": 3, "tee_choice": "50-64", "handicap_index": None},
]}]}
db.save_event_pairings(EV, sheet, db_path=tmp)

print("\n== the sheet stores the person ==")
rows = {r["player_name"]: r for r in c.execute(
    "SELECT player_name, customer_id FROM event_pairings WHERE event_id = ?", (EV,))}
check("a seated player is saved with his customer_id", rows["Jose Mejia"]["customer_id"] == 729)
check("…for every seat", rows["Adam Baker"]["customer_id"] == 87)
check("a name nobody owns is saved as typed, with no id", rows["Randy Guest"]["customer_id"] is None)

print("\n== renaming the customer moves the sheet with him ==")
c.execute("UPDATE customers SET first_name = 'Joe' WHERE customer_id = 729"); c.commit()
got = db.get_event_pairings(EV, db_path=tmp)
players = {p["name"]: p for p in got["9"][0]["players"]}
check("the sheet reads the NEW name immediately", "Joe Mejia" in players, str(sorted(players)))
check("…and the old spelling is gone", "Jose Mejia" not in players, str(sorted(players)))
check("the customer_id travels to the page, for the roster match", players["Joe Mejia"]["customer_id"] == 729)
check("the guest is untouched", "Randy Guest" in players and players["Randy Guest"]["customer_id"] is None)
check("seats and tees are unchanged by the rename",
      players["Joe Mejia"]["cart_pos"] == 1 and players["Joe Mejia"]["tee_choice"] == "50-64")

print("\n== sheets saved before the column existed ==")
c.execute("UPDATE event_pairings SET customer_id = NULL WHERE event_id = ?", (EV,))
c.execute("UPDATE event_pairings SET player_name = 'Jose Mejia' WHERE player_name = 'Joe Mejia'")
c.execute("INSERT INTO customer_aliases (customer_name, alias_value, alias_type, customer_id) VALUES ('Joe Mejia', 'Jose Mejia', 'name', 729)")
c.commit()
got2 = db.get_event_pairings(EV, db_path=tmp)
p2 = {p["name"]: p for p in got2["9"][0]["players"]}
check("a legacy row is linked by NAME ALIAS on the next read", "Joe Mejia" in p2, str(sorted(p2)))
check("…and the link is written back, not re-derived every time",
      c.execute("SELECT customer_id FROM event_pairings WHERE player_name = 'Jose Mejia'").fetchone()["customer_id"] == 729)
check("a row nobody owns stays NULL and is simply retried later",
      c.execute("SELECT customer_id FROM event_pairings WHERE player_name = 'Randy Guest'").fetchone()["customer_id"] is None)
check("the whole-table boot backfill is idempotent",
      db._backfill_customer_id_on_event_pairings(c) == 0)

print("\n== the handicap map follows the rename too ==")
c.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES ('Mejia, Jose', 'Jose Mejia', 729)")
for d, diff in (("2026-08-01", 10.2), ("2026-08-15", 9.8)):
    c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) VALUES ('Mejia, Jose', ?, 88, 71.2, 128, ?)", (d, diff))
c.commit()
hmap = db._roster_handicap_index_map(c)
check("the index is keyed on the CANONICAL name, not the stale link row",
      "joe mejia" in hmap and "jose mejia" not in hmap, str(sorted(hmap)))
check("…and it is the right number", round(hmap["joe mejia"], 1) == 10.0, str(hmap))

print("\nALL PASSED" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
