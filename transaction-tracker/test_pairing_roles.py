"""Pairings rules 12 + 13 and the role flags (Kerry-ratified 2026-09-15).

12. No lone back tee: a <50 player is never the only <50 in a foursome
    unless flagged OK-alone-back. Forward / 65+ may be alone. Repaired
    after groups form, by the cheapest-history swap, never moving a
    locked player; no legal swap -> a note, not a silent override.
 7. Captains/ambassadors spread across groups (built here, soft).
13. Captain rides with the newest player and DRIVES (seats 1 and 3);
    a first-season player never drives.
Flags seed fill-only-if-NULL; a tap writes an explicit 0/1.

Run: python3 test_pairing_roles.py
"""
import os, sqlite3, sys
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
import logging; logging.getLogger("email_parser.database").setLevel(logging.ERROR)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

tee = {"Jesse": "<50", "Kerry": "<50", "Luke": "<50", "Adam": "<50",
       "Will": "50-64", "Gus": "50-64", "Mike": "65+", "Rob": "50-64",
       "Mary": "Forward", "Dan": "50-64", "Pat": "50-64", "Scott": "50-64"}
NOH = {}   # no history -> every swap is free

print("\n== rule 12: no lone back tee ==")
g = [["Jesse", "Will", "Gus", "Mike"], ["Kerry", "Luke", "Adam", "Rob"], ["Mary", "Dan", "Pat", "Scott"]]
out, notes = db._repair_lone_back_tee(g, tee, solo_ok=set(), locked=set(), pair_counts=NOH)
jesse = next(x for x in out if "Jesse" in x)
check("Jesse is no longer the only <50 in his group",
      sum(1 for n in jesse if db._is_back_tee(tee[n])) >= 2, str(out))
check("the donor group keeps two <50s (or none)",
      all(db._lone_back_offender(x, tee, set()) is None for x in out), str(out))
check("group sizes are preserved", sorted(len(x) for x in out) == [4, 4, 4])
check("no note when it was fixable", notes == [], str(notes))

out, notes = db._repair_lone_back_tee(
    [["Kerry", "Will", "Gus", "Mike"], ["Mary", "Dan", "Pat", "Scott"]], tee,
    solo_ok={"Kerry"}, locked=set(), pair_counts=NOH)
check("a flagged player may be alone on the back (Kerry, no swap)",
      out == [["Kerry", "Will", "Gus", "Mike"], ["Mary", "Dan", "Pat", "Scott"]] and notes == [], str((out, notes)))

out, notes = db._repair_lone_back_tee(
    [["Jesse", "Will", "Gus", "Mike"], ["Mary", "Dan", "Pat", "Scott"]], tee,
    solo_ok=set(), locked=set(), pair_counts=NOH)
check("no other <50 on the sheet -> left alone with a note", out[0] == ["Jesse", "Will", "Gus", "Mike"] and len(notes) == 1 and "Jesse" in notes[0], str(notes))

out, notes = db._repair_lone_back_tee(
    [["Jesse", "Will", "Gus", "Mike"], ["Kerry", "Luke", "Adam", "Rob"]], tee,
    solo_ok=set(), locked={"Will", "Gus", "Mike"}, pair_counts=NOH)
check("locked players are never moved -> note instead", out[0][0] == "Jesse" and set(out[0]) == {"Jesse", "Will", "Gus", "Mike"} and notes, str((out, notes)))

check("Forward alone is fine (Mary)",
      db._lone_back_offender(["Mary", "Dan", "Pat", "Scott"], tee, set()) is None)
check("<50 detection is strict", db._is_back_tee("<50") and db._is_back_tee("< 50") and not db._is_back_tee("50-64") and not db._is_back_tee("Back"))

# history is the tiebreak: prefer the <50 who has played these people least
hist = {tuple(sorted((db._pair_key_name(a), db._pair_key_name(b)))): 3
        for a, b in (("Luke", "Will"), ("Luke", "Gus"), ("Luke", "Mike"))}
out, _ = db._repair_lone_back_tee(
    [["Jesse", "Will", "Gus", "Mike"], ["Kerry", "Luke", "Adam", "Rob"], ["Mary", "Dan", "Pat", "Scott"]], tee,
    solo_ok=set(), locked=set(), pair_counts=hist)
jesse = next(x for x in out if "Jesse" in x)
check("the swap that repeats the fewest pairings wins (not Luke)", "Luke" not in jesse, str(out))

print("\n== rule 7: leaders spread ==")
leaders = {"Gus", "Kerry", "Mary"}
out, _ = db._spread_leaders([["Gus", "Kerry", "Will", "Mike"], ["Jesse", "Dan", "Pat", "Scott"], ["Mary", "Luke", "Adam", "Rob"]],
                            leaders, locked=set(), pair_counts=NOH, tee_map=tee, solo_ok=set())
check("a leaderless group receives one from a group holding two",
      all(any(n in leaders for n in x) for x in out), str(out))
check("spreading never creates a lone unflagged <50",
      all(db._lone_back_offender(x, tee, set()) is None for x in out), str(out))

print("\n== rule 13: captain rides with the newest and drives ==")
exp = {db._pair_key_name(n): e for n, e in (("Gus", 40), ("Will", 1), ("Mike", 25), ("Rob", 12))}
seats = db._arrange_group_seats(["Will", "Mike", "Rob", "Gus"], set(), set(), {},
                                captains={"Gus"}, newbies={"Will"}, experience=exp)
def cart_of(n): return 0 if seats.index(n) < 2 else 1
check("captain and the newest share a cart", cart_of("Gus") == cart_of("Will"), str(seats))
check("the captain drives (seat 1 or 3)", seats.index("Gus") in (0, 2), str(seats))
check("the new player never drives", seats.index("Will") in (1, 3), str(seats))
check("in the other cart the more experienced drives (Mike over Rob)",
      seats.index("Mike") in (0, 2) and seats.index("Rob") in (1, 3), str(seats))
# a partner request still beats captain-with-newest
adj = {frozenset((db._pair_key_name("Will"), db._pair_key_name("Rob")))}
seats2 = db._arrange_group_seats(["Will", "Mike", "Rob", "Gus"], set(), adj, {},
                                 captains={"Gus"}, newbies={"Will"}, experience=exp)
def cart2(n): return 0 if seats2.index(n) < 2 else 1
check("a partner request outranks captain-with-newest", cart2("Will") == cart2("Rob"), str(seats2))
check("…and the new player still does not drive", seats2.index("Will") in (1, 3), str(seats2))
check("the captain takes SEAT 1", seats.index("Gus") == 0, str(seats))
check("…with the newest beside them in seat 2 when unpartnered", seats.index("Will") == 1, str(seats))
# captain partnered: the partner rides in seat 2, the newest goes to the other cart
adjc = {frozenset((db._pair_key_name("Gus"), db._pair_key_name("Rob")))}
seats3 = db._arrange_group_seats(["Will", "Mike", "Rob", "Gus"], set(), adjc, {},
                                 captains={"Gus"}, newbies={"Will"}, experience=exp)
check("a partnered captain sits in seat 1 with their request in seat 2", seats3[:2] == ["Gus", "Rob"], str(seats3))
check("…and the new player still does not drive", seats3.index("Will") == 3, str(seats3))
check("no captains/newbies passed -> old behaviour unchanged",
      db._arrange_group_seats(["A", "B", "C", "D"], set(), set(), {}) == ["A", "B", "C", "D"])

print("\n== rule 14: a 1st timer rides with an ambassador, same tee when possible ==")
tee14 = {"Will": "50-64", "Mike": "65+", "Rob": "50-64", "Gus": "50-64", "Scott": "50-64", "Kerry": "<50", "Luke": "<50", "Adam": "<50"}
g14 = [["Will", "Mike", "Rob", "Adam"], ["Gus", "Scott", "Kerry", "Luke"]]
out, notes = db._pair_first_timers_with_ambassadors(g14, ambassadors={"Gus", "Scott", "Luke"}, first_timers={"Will"},
                                                   tee_map=tee14, locked=set(), pair_counts=NOH, solo_ok={"Kerry"})
wg = next(x for x in out if "Will" in x)
check("Will's group now holds an ambassador", any(n in ("Gus", "Scott", "Luke") for n in wg), str(out))
check("…a SAME-TEE one (50-64), not Luke on <50", "Luke" not in wg, str(out))
check("the donor group keeps its ambassadors and rule 12 holds", all(db._lone_back_offender(x, tee14, {"kerry"}) is None for x in out), str(out))
out2, notes2 = db._pair_first_timers_with_ambassadors([["Will", "Mike", "Rob", "Adam"], ["Kerry", "Luke", "Dan", "Pat"]],
                                                      ambassadors=set(), first_timers={"Will"}, tee_map=tee14,
                                                      locked=set(), pair_counts=NOH, solo_ok={"Kerry"})
check("no ambassador on the sheet -> left alone with a note", out2[0] == ["Will", "Mike", "Rob", "Adam"] and notes2 and "Will" in notes2[0], str(notes2))
seats14 = db._arrange_group_seats(["Will", "Mike", "Rob", "Gus"], set(), set(), tee14,
                                  ambassadors={"Gus"}, first_timers={"Will"}, experience=exp)
def c14(n): return 0 if seats14.index(n) < 2 else 1
check("in the cart: the first-timer rides with the ambassador", c14("Will") == c14("Gus"), str(seats14))
check("…and the ambassador drives (more experienced)", seats14.index("Gus") in (0, 2) and seats14.index("Will") in (1, 3), str(seats14))

print("\n== flags: seed fill-only-if-NULL, tap writes explicit ==")
conn = sqlite3.connect(":memory:"); conn.row_factory = sqlite3.Row
conn.executescript("""
 CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT);
 INSERT INTO customers VALUES (1,'Gus','Vasquez'),(2,'Jesse','Saldana'),(3,'Jeff','Young'),(4,'Kerry','Niester');
""")
n = db._seed_player_roles(conn)
row = lambda cid: conn.execute("SELECT ambassador, group_captain, solo_back_ok FROM customers WHERE customer_id=?", (cid,)).fetchone()
check("Gus seeds as ambassador + captain, not solo-back", tuple(row(1)) == (1, 1, None), str(tuple(row(1))))
check("Jeff Young seeds all three", tuple(row(3)) == (1, 1, 1))
check("Jesse seeds nothing", tuple(row(2)) == (None, None, None))
conn.execute("UPDATE customers SET group_captain = 0 WHERE customer_id = 1")   # a tap clears it
db._seed_player_roles(conn)
check("a cleared flag (explicit 0) is not re-seeded", row(1)["group_captain"] == 0)
check("seed counted the rows it set (Gus 2 + Jeff 3 + Kerry 3)", n == 8, str(n))
conn.close()

print("\n" + ("FAILED: " + ", ".join(F) if F else "ALL PASSED")); sys.exit(1 if F else 0)
