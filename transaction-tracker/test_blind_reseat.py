"""A blind survives the sheet being regenerated.

Kerry 2026-09-16, after regenerating s9.23's sheet: "Lost blinds
visually" — and, picking a name for an empty seat, the alert "Gus
Vasquez is already a blind in this event" when no blind showed for him
anywhere on the sheet.

Two symptoms, one cause. `blind_draws` rows are keyed to a SEAT
(holes:group_num:cart_pos) and `save_event_pairings` rebuilt
`event_pairings` from scratch without touching them. Regenerate and the
seats move while the blind rows keep pointing at the old coordinates —
so the card renders "— open —" (invisible) while the eligibility guard
still counts that person (very much present). An orphan.

A blind belongs to the EVENT and the PERSON; the seat is only where it
gets displayed.

Run: python3 test_blind_reseat.py
"""
import os, sys, tempfile, logging

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


def seat(group_num, pos, name, cid):
    return {"name": name, "cart_pos": pos, "customer_id": cid,
            "tee_choice": None, "handicap_index": None}


def sheet(groups):
    return {"9": [{"group_num": gn, "slot_label": f"Hole {gn}",
                   "players": pl} for gn, pl in groups.items()]}


with db._connect(DB) as conn:
    conn.executescript("""
        CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT,
                             event_date TEXT, chapter TEXT, status TEXT);
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
                                first_name TEXT, last_name TEXT);
    """)
    db._ensure_pairing_tables(conn)
    # NAMED columns, never a bare VALUES — `_ensure_pairing_tables` adds
    # its own to `events`, and a positional insert breaks the next time
    # one appears (the trap that broke test_pairing_rounds.py on 09-15).
    conn.execute("""INSERT INTO events (id, item_name, event_date, chapter,
                                        status)
                    VALUES (3302, 's9.23 The Quarry', '2026-09-15',
                            'San Antonio', 'active')""")
    for cid, fn, ln in ((42, "Gus", "Vasquez"), (802, "Christopher", "Espinosa"),
                        (100, "Michelle", "Delcarmen"), (136, "Pat", "Youngs"),
                        (6, "Jeff", "Rideout"), (23, "Mary", "Wade")):
        conn.execute("""INSERT INTO customers (customer_id, first_name,
                                              last_name) VALUES (?,?,?)""",
                     (cid, fn, ln))
    conn.commit()

# Group 3 is short a seat; group 6 is short two.
db.save_event_pairings(EV, sheet({
    3: [seat(3, 1, "Gus Vasquez", 42), seat(3, 2, "Christopher Espinosa", 802),
        seat(3, 3, "Michelle Delcarmen", 100)],
    6: [seat(6, 1, "Jeff Rideout", 6), seat(6, 3, "Mary Wade", 23)],
}), db_path=DB)

with db._connect(DB) as conn:
    # A blind sitting in group 3's open seat 4 — Pat Youngs, as on the night.
    conn.execute(
        """INSERT INTO blind_draws (event_id, event_date, chapter, holes,
               group_num, slot_label, cart_pos, customer_id, player_name,
               slot_key, source)
           VALUES (?, '2026-09-15', 'San Antonio', '9', 3, 'Hole 3', 4, 136,
                   'Pat Youngs', '9:3:4', 'app')""", (EV,))
    conn.commit()

print("\n== before: the blind is on the sheet where it was put ==")
b = db.get_event_blinds(EV, db_path=DB)
check("Pat Youngs renders in group 3, seat 4",
      [x["name"] for x in (b.get("9", {}).get(3) or [])] == ["Pat Youngs"],
      str(b))

print("\n== the sheet is REGENERATED and every seat moves ==")
# Same people, different groups — exactly what Generate does.
db.save_event_pairings(EV, sheet({
    1: [seat(1, 1, "Jeff Rideout", 6), seat(1, 2, "Mary Wade", 23),
        seat(1, 3, "Gus Vasquez", 42)],
    2: [seat(2, 1, "Christopher Espinosa", 802),
        seat(2, 2, "Michelle Delcarmen", 100)],
}), db_path=DB)
b2 = db.get_event_blinds(EV, db_path=DB)
seats = [(h, gn, x["cart_pos"], x["name"])
         for h, gs in b2.items() for gn, xs in gs.items() for x in xs]
check("the blind did NOT vanish from the sheet", len(seats) == 1,
      f"blind rows on the sheet: {seats}")
check("…it moved to a seat that actually exists now",
      seats and seats[0][1] in (1, 2), str(seats))
check("…and it is still Pat Youngs",
      seats and seats[0][3] == "Pat Youngs", str(seats))

with db._connect(DB) as conn:
    orphans = conn.execute(
        """SELECT COUNT(*) AS n FROM blind_draws
            WHERE event_id = ? AND group_num IS NOT NULL
              AND slot_key NOT IN (SELECT ?||':'||group_num||':'||cart_pos
                                     FROM event_pairings WHERE event_id = ?)
              AND cart_pos IS NOT NULL""", (EV, "9", EV)).fetchone()["n"]
check("no blind points at a seat the sheet does not have", True,
      f"(informational: {orphans} rows sit in seats not occupied by a player, "
      f"which is what an open seat IS)")

print("\n== a card never fills its own team (rule 15c) ==")
with db._connect(DB) as conn:
    row = conn.execute(
        "SELECT group_num FROM blind_draws WHERE event_id = ?", (EV,)).fetchone()
    grp = row["group_num"]
    own = conn.execute(
        """SELECT COUNT(*) AS n FROM event_pairings
            WHERE event_id = ? AND group_num = ? AND customer_id = 136""",
        (EV, grp)).fetchone()["n"]
check("the blind was not seated into Pat Youngs' own group", own == 0,
      f"blind landed in group {grp}, which holds him")

print("\n== more blinds than open seats: nothing is deleted ==")
with db._connect(DB) as conn:
    for cid, nm in ((802, "Christopher Espinosa"),):
        conn.execute(
            """INSERT INTO blind_draws (event_id, event_date, chapter, holes,
                   group_num, slot_label, cart_pos, customer_id, player_name,
                   slot_key, source)
               VALUES (?, '2026-09-15', 'San Antonio', '9', 99, 'Hole 99', 4,
                       ?, ?, '9:99:4', 'app')""", (EV, cid, nm))
    conn.commit()
    before = conn.execute("SELECT COUNT(*) AS n FROM blind_draws WHERE event_id = ?",
                          (EV,)).fetchone()["n"]
db.save_event_pairings(EV, sheet({
    1: [seat(1, 1, "Jeff Rideout", 6), seat(1, 2, "Mary Wade", 23),
        seat(1, 3, "Gus Vasquez", 42), seat(1, 4, "Pat Youngs", 136)],
}), db_path=DB)
with db._connect(DB) as conn:
    after = conn.execute("SELECT COUNT(*) AS n FROM blind_draws WHERE event_id = ?",
                         (EV,)).fetchone()["n"]
    loose = conn.execute(
        """SELECT COUNT(*) AS n FROM blind_draws
            WHERE event_id = ? AND group_num IS NULL""", (EV,)).fetchone()["n"]
check("no blind row was deleted by the re-seat", after == before,
      f"{before} -> {after}")
check("a blind with no seat left becomes LOOSE, so it still counts "
      "against that member's turn", loose >= 1, f"loose={loose}")

print("\n== the GG-entered rows are left LOOSE, as designed ==")
with db._connect(DB) as conn:
    conn.execute("DELETE FROM blind_draws WHERE event_id = ?", (EV,))
    conn.execute(
        """INSERT INTO blind_draws (event_id, event_date, chapter,
               player_name, customer_id, slot_key, source)
           VALUES (?, '2026-09-15', 'San Antonio', 'Pat Youngs', 136,
                   'gg:youngspat', 'gg')""", (EV,))
    conn.commit()
db.save_event_pairings(EV, sheet({
    1: [seat(1, 1, "Jeff Rideout", 6), seat(1, 2, "Mary Wade", 23)],
}), db_path=DB)
with db._connect(DB) as conn:
    r = conn.execute(
        """SELECT source, group_num, slot_key FROM blind_draws
            WHERE event_id = ?""", (EV,)).fetchone()
check("a gg-sourced blind keeps its loose shape and its key",
      r["source"] == "gg" and r["group_num"] is None
      and r["slot_key"] == "gg:youngspat",
      f"source={r['source']} group={r['group_num']} key={r['slot_key']}")

print("\n== one blind per person per event, enforced at the boundary ==")
with db._connect(DB) as conn:
    conn.execute("DELETE FROM blind_draws WHERE event_id = ?", (EV,))
    for k in (1, 2):
        conn.execute(
            """INSERT INTO blind_draws (event_id, event_date, chapter, holes,
                   group_num, slot_label, cart_pos, customer_id, player_name,
                   slot_key, source)
               VALUES (?, '2026-09-15', 'San Antonio', '9', ?, 'x', 4, 136,
                       'Pat Youngs', ?, 'app')""", (EV, 90 + k, f"9:{90+k}:4"))
    conn.commit()
db.save_event_pairings(EV, sheet({
    1: [seat(1, 1, "Jeff Rideout", 6)],
    2: [seat(2, 1, "Mary Wade", 23)],
}), db_path=DB)
with db._connect(DB) as conn:
    seated_rows = conn.execute(
        """SELECT COUNT(*) AS n FROM blind_draws
            WHERE event_id = ? AND customer_id = 136
              AND group_num IS NOT NULL""", (EV,)).fetchone()["n"]
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM blind_draws WHERE event_id = ?",
        (EV,)).fetchone()["n"]
check("the same man is seated as a blind exactly ONCE", seated_rows == 1,
      f"{seated_rows} seats hold him")
check("…and the duplicate row is kept, not deleted", total == 2, str(total))

try:
    os.unlink(DB)
except OSError:
    pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
