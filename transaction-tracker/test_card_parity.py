"""The engine and the saved scorecards agree, or the money and points wait.

Kerry 10/14, after s9.27 The Quarry: the stored cards were right and the
payout engine was wrong for Dan Stich (net 41 vs the card's 38), because the
engine worked his strokes out a second time on the event's tee. Two fixes:

  1. ONE SOURCE: `event_engine_state` hands the engine the strokes saved on
     each card (placeholder zeros from before CA #865 are still derived).
  2. THE ALARM: `card_parity.engine_card_parity` checks every entered player
     (stored strokes vs the rule on his own tee; engine card vs stored card),
     and any difference holds `record_event_game_payouts`, the closeout's
     final check and the points rebuild.

Run: python3 test_card_parity.py
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402
from email_parser import card_parity as cp  # noqa: E402
from email_parser import live_scoring as ls  # noqa: E402
from email_parser.handicap_calc import ruled_dots  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


tmp = tempfile.mktemp(suffix=".db")
db.init_db(tmp)

PARS = {10: 4, 11: 4, 12: 3, 13: 4, 14: 4, 15: 5, 16: 3, 17: 4, 18: 5}
GOLD = {10: 4, 11: 18, 12: 14, 13: 10, 14: 2, 15: 16, 16: 12, 17: 6, 18: 8}
# The Blue card: odd indexes on the front, its own evens on the back.
BLUE = {h: 2 * h - 1 for h in range(1, 10)}
BLUE.update({10: 4, 11: 18, 12: 14, 13: 10, 14: 2, 15: 16, 16: 12, 17: 6, 18: 8})
BLUE_BACK = {10: 2, 11: 18, 12: 12, 13: 8, 14: 4, 15: 16, 16: 14, 17: 6, 18: 10}
BLUE.update(BLUE_BACK)

c = sqlite3.connect(tmp)
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES "
          "(3307, 's9.27 The Quarry', '2026-10-13', 'San Antonio', 'active')")
c.execute("INSERT INTO courses (course_id, name) VALUES (7, 'The Quarry')")
c.execute("INSERT INTO course_tees (tee_id, course_id, tee_name) VALUES (1, 7, 'Gold')")
c.execute("INSERT INTO course_tees (tee_id, course_id, tee_name) VALUES (2, 7, 'Blue')")
for h, si in GOLD.items():
    c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, stroke_index) VALUES (1, ?, ?, ?)",
              (h, PARS[h], si))
for h, si in BLUE.items():
    c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, stroke_index) VALUES (2, ?, ?, ?)",
              (h, PARS.get(h, 4), si))

PLAYERS = [  # cid, name, tee, ph, gross by hole 10-18
    (298, "Dan Stich", 2, 6, [6, 6, 4, 4, 4, 8, 2, 4, 6]),
    (87, "Adam Baker", 1, 5, [5, 4, 3, 5, 3, 6, 4, 4, 5]),
    (90, "Ann Able", 1, 10, [5, 5, 4, 5, 5, 6, 4, 5, 6]),
]
ROUND = {}
for cid, name, tee, ph, gross in PLAYERS:
    cur = c.execute(
        "INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, holes_played, "
        "gross, playing_handicap, source, tee_id, course_id) VALUES (?, ?, 3307, '2026-10-13', 9, ?, ?, 'entry', ?, 7)",
        (cid, name, sum(gross), ph, tee))
    ROUND[cid] = cur.lastrowid
    si = {h: (BLUE if tee == 2 else GOLD)[h] for h in PARS}
    dots = ruled_dots(ph, si)
    for h, g in zip(PARS, gross):
        c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, strokes_received) "
                  "VALUES (?, ?, ?, ?)", (ROUND[cid], h, g, int(dots.get(h, 0) or 0)))
c.commit()
c.close()


def stich_card(state=None):
    st = state or db.event_engine_state("s9.27 The Quarry", db_path=tmp)
    cards = ls.build_cards(st, db.get_scoring_formulas(tmp))
    return next(x for x in cards if x["customer_id"] == 298)


print("1. One source: the engine reads the strokes saved on the card")
st = db.event_engine_state("s9.27 The Quarry", db_path=tmp)
check("the event builds on its most-played tee (Gold)", not st.get("error"), st.get("error"))
s = stich_card(st)
saved = ruled_dots(6, {h: BLUE[h] for h in PARS})
check("Stich's engine card uses the saved strokes (allocation 'given')",
      s["allocation_source"] == "given", s["allocation_source"])
check("...on HIS tee's holes", {h["hole"] for h in s["holes"] if h["strokes_received"]} ==
      {h for h, n in saved.items() if n}, [(h["hole"], h["strokes_received"]) for h in s["holes"]])
check("engine net = card net = 44 - 6 = 38", s["net"] == 38, s["net"])

print("\n2. The check: clean event")
p = cp.engine_card_parity(3307, db_path=tmp)
check("every entered player checked, no mismatch", p["ok"] and p["checked"] == 3, p)
check("no blocking reason", cp.blocking_reason(p) is None)

print("\n3. The check catches a card saved with the wrong tee's strokes")
c = sqlite3.connect(tmp)
wrong = ruled_dots(6, {h: GOLD[h] for h in PARS})       # the event's tee, not his
for h in PARS:
    c.execute("UPDATE scoring_holes SET strokes_received = ? WHERE scoring_round_id = ? AND hole_number = ?",
              (int(wrong.get(h, 0) or 0), ROUND[298], h))
c.commit()
c.close()
p = cp.engine_card_parity(3307, db_path=tmp)
check("not ok, Stich named, kind stored_strokes_off_rule",
      not p["ok"] and any(m["customer_id"] == 298 and m["kind"] == "stored_strokes_off_rule"
                          for m in p["mismatches"]), p["mismatches"])
check("the others are clean", all(m["customer_id"] == 298 for m in p["mismatches"]), p["mismatches"])
rec = db.record_event_game_payouts("s9.27 The Quarry", [
    {"golferName": "Adam Baker", "category": "Individual Net", "amount": 21, "description": "x"}],
    force=True, db_path=tmp)
check("the payout writer refuses, naming the hold", "held" in (rec.get("error") or ""), rec)
c = sqlite3.connect(tmp)
n = c.execute("SELECT COUNT(*) FROM tgf_payouts").fetchone()[0]
item = c.execute("SELECT urgency FROM action_items WHERE subject LIKE 'SCORING HOLD:%s9.27%'").fetchall()
c.close()
check("...and wrote no payout row", n == 0, n)
check("one HIGH COO action item raised", item == [("high",)], item)
db.record_event_game_payouts("s9.27 The Quarry", [
    {"golferName": "Adam Baker", "category": "Individual Net", "amount": 21, "description": "x"}],
    force=True, db_path=tmp)
c = sqlite3.connect(tmp)
n_items = c.execute("SELECT COUNT(*) FROM action_items WHERE subject LIKE 'SCORING HOLD:%'").fetchone()[0]
c.close()
check("a second refusal does not raise a second item", n_items == 1, n_items)

# Put the right strokes back.
c = sqlite3.connect(tmp)
for h in PARS:
    c.execute("UPDATE scoring_holes SET strokes_received = ? WHERE scoring_round_id = ? AND hole_number = ?",
              (int(saved.get(h, 0) or 0), ROUND[298], h))
c.commit()
c.close()
check("fixed card: clean again", cp.engine_card_parity(3307, db_path=tmp)["ok"])

print("\n4. The check catches the ENGINE drifting from the card (the 10/13 class)")
st = db.event_engine_state("s9.27 The Quarry", db_path=tmp)
for pl in st["players"]:                 # the old engine: derive, on the event's tee
    pl["strokes_received"] = {}
    pl["stroke_index_by_hole"] = {}
p = cp.engine_card_parity(3307, db_path=tmp, state=st)
bad = [m for m in p["mismatches"] if m["kind"] == "engine_differs_from_card"]
check("an engine that works Stich's strokes out on the event's tee is flagged, hole by hole",
      any(m["customer_id"] == 298 and "hole 12: card 4/1 pops, engine 4/0 pops" in m["detail"]
          for m in bad), bad)
check("players on the event's tee are not flagged", {m["customer_id"] for m in bad} == {298}, bad)

print("\n5. Placeholder zeros (before CA #865) are still derived, and flagged")
c = sqlite3.connect(tmp)
c.execute("UPDATE scoring_holes SET strokes_received = 0 WHERE scoring_round_id = ?", (ROUND[90],))
c.commit()
c.close()
st = db.event_engine_state("s9.27 The Quarry", db_path=tmp)
a = next(x for x in ls.build_cards(st, db.get_scoring_formulas(tmp)) if x["customer_id"] == 90)
check("the engine derives a zero-stroke card with a handicap (net != gross)",
      a["allocation_source"] == "derived" and a["net"] == a["gross"] - 10, (a["allocation_source"], a["net"]))
p = cp.engine_card_parity(3307, db_path=tmp)
check("...and the check flags the card's zeros", any(m["customer_id"] == 90 for m in p["mismatches"]),
      p["mismatches"])

print("\n6. The hold reaches the closeout check and the points")
import email_parser.closeout_checks as cc  # noqa: E402
import email_parser.tracker_points as tp  # noqa: E402
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_parser", "closeout_checks.py")).read()
check("closeout_final_check blocks on a mismatch", "card_parity" in src and "blocking_reason" in src)
check("points: a held event is left out and apply refuses",
      tp.held_events(["HELD s9.27: x", "other"]) == ["HELD s9.27: x"]
      and "out[\"refused\"] = held" in open(tp.__file__).read())
m = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")).read()
check("bridge scoring-card-parity exists", 'cmd == "scoring-card-parity"' in m)
ep = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_parser", "entry_publish.py")).read()
check("every publish runs the check and raises the alarm", "engine_card_parity(event_id" in ep and "_cp.alarm" in ep)

os.unlink(tmp)
print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
