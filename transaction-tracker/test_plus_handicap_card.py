"""The plus rule on the SURFACES — the card, not just the leaderboard.

Kerry, 2026-09-15 ~9:15 PM, looking at Pat Youngs' Quarry Front card on
/handicaps: "We just determined this isn't how we do Net Points with
pluses on holes."

The rule he ratified the same evening: "For MVP nobody is allowed to have
to add strokes on any given hole, so there should be no pluses on any
holes. But his +3 PH still stands… his total points gets deducted that 3
strokes. It's not fair to make a player have to perform on any one hole,
but it should be applied across a round."

v2.450.0 applied that at TWO of the eleven `compute_hole_derivations`
call sites, locally, rather than at the mechanism — so the `/handicaps`
scorecard and the Players Cup card still added a plus stroke hole by
hole the next day. v2.458.0 moves the rule INTO the mechanism behind an
explicit `game=` flag.

FIXTURE: Pat Youngs, scoring_round 3500, 2026-09-15, The Quarry front
nine off 2-Blue (slope 103 / rating 32.5), playing handicap -3. His real
card, hole for hole, taken from the live round.

The second half of this file is the REGRESSION that matters most: the
five WHS / index call sites must KEEP the plus stroke. USGA net double
bogey is `par + 2 + strokes_received`, and for a plus that legitimately
lowers the cap. His adjusted gross, his differential (0.5) and his index
(-0.5N) must come out of this change completely unchanged.

Run: python3 test_plus_handicap_card.py
"""
import os, sys, tempfile, logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.INFO)
from email_parser import database as db                          # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


# Pat Youngs, 2026-09-15, The Quarry front, 2-Blue.
# (hole, par, yardage, stroke_index, strokes, strokes_received)
CARD = [
    (1, 4, 330,  9, 4,  0),
    (2, 4, 385,  3, 4,  0),
    (3, 3, 106, 15, 3, -1),
    (4, 4, 258, 17, 3, -1),
    (5, 5, 474,  1, 5,  0),
    (6, 4, 293, 11, 4,  0),
    (7, 4, 360,  7, 4,  0),
    (8, 3, 125, 13, 2, -1),
    (9, 4, 267,  5, 4,  0),
]
GROSS = sum(c[4] for c in CARD)          # 33
SLOPE, RATING, PH = 103, 32.5, -3.0

# CLAUDE.md, customers.md: never hold `_connect(...).__enter__()` without
# the contextmanager reference — the connection closes under you.
with db._connect(DB) as conn:
    conn.executescript("""
        CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT,
                             event_date TEXT, chapter TEXT, status TEXT);
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
                                first_name TEXT, last_name TEXT);
        CREATE TABLE handicap_player_links (player_name TEXT PRIMARY KEY,
                                            customer_name TEXT,
                                            customer_id INTEGER);
        -- the canonical course registry; the scoring layer enriches it
        -- with tees rather than duplicating it
        CREATE TABLE courses (course_id INTEGER PRIMARY KEY, name TEXT,
                              short_name TEXT);
    """)
    db._ensure_scoring_tables(conn)
    conn.execute("""INSERT INTO events (id, item_name, event_date, chapter, status)
                    VALUES (3302, 's9.23 The Quarry', '2026-09-15',
                            'San Antonio', 'active')""")
    conn.execute("""INSERT INTO courses (course_id, name)
                    VALUES (22361, 'The Quarry Golf Club')""")
    conn.execute("""INSERT INTO course_tees (tee_id, course_id, tee_name,
                                             slope, rating)
                    VALUES (112, 22361, '2 - Blue Tee', ?, ?)""", (SLOPE, RATING))
    for hole, par, yds, si, _s, _sr in CARD:
        conn.execute("""INSERT INTO course_tee_holes (tee_id, hole_number, par,
                                                      yardage, stroke_index)
                        VALUES (112, ?, ?, ?, ?)""", (hole, par, yds, si))
    conn.execute("""INSERT INTO scoring_rounds (id, customer_id, player_name,
                        event_id, round_date, course_id, tee_id, holes_played,
                        playing_handicap, gross, net, source)
                    VALUES (3500, 136, 'YOUNGS, Pat', 3302, '2026-09-15', 22361,
                            112, 9, ?, ?, ?, 'gg')""", (PH, GROSS, GROSS - PH))
    for hole, _p, _y, _si, strokes, sr in CARD:
        conn.execute("""INSERT INTO scoring_holes (scoring_round_id, hole_number,
                                                   strokes, strokes_received)
                        VALUES (3500, ?, ?, ?)""", (hole, strokes, sr))
    conn.commit()

formulas = db.get_scoring_formulas(DB)


print("\n== the MECHANISM carries the rule, not each caller ==")
# Hole 3: par 3, 3 strokes, one stroke GIVEN BACK.
whs = db.compute_hole_derivations(3, 3, -1, formulas)
game = db.compute_hole_derivations(3, 3, -1, formulas, game=True)
check("unflagged, the give-back still lands on the hole (WHS behaviour kept)",
      whs["net_vs_par"] == 1, str(whs))
check("game=True never makes a hole harder than the card says",
      game["net_vs_par"] == 0, str(game))
check("…so the hole's points stop being docked",
      game["stableford_net"] == 1 and whs["stableford_net"] == 0,
      f'game={game["stableford_net"]} whs={whs["stableford_net"]}')
check("adjusted_strokes keeps the TRUE allocation in BOTH modes",
      game["adjusted_strokes"] == whs["adjusted_strokes"],
      f'{game["adjusted_strokes"]} vs {whs["adjusted_strokes"]}')
check("the WHS cap on a plus hole is still par + 2 + (-1)",
      db.compute_hole_derivations(3, 9, -1, formulas,
                                  game=True)["adjusted_strokes"] == 4)
check("a stroke RECEIVED is untouched by the flag",
      db.compute_hole_derivations(4, 5, 1, formulas, game=True)
      == db.compute_hole_derivations(4, 5, 1, formulas))
check("the default is OFF, so a WHS caller keeps its behaviour by doing nothing",
      db.compute_hole_derivations(3, 3, -1, formulas)["net_vs_par"] == 1)

print("\n== the round deduction has ONE implementation ==")
check("a plus handicap gives back its strokes across the round",
      db.plus_round_deduction(-3.0) == 3)
check("a regular handicap gives back nothing",
      db.plus_round_deduction(7.0) == 0 and db.plus_round_deduction(0) == 0)
check("no handicap is not an error", db.plus_round_deduction(None) == 0)
# ONE implementation: the only EXECUTABLE occurrence of the deduction
# arithmetic in the codebase is the return inside plus_round_deduction.
# (Docstrings and the audit's note text quote it deliberately, so the
# check looks for assignment/return forms, not the substring.)
src = (open("email_parser/database.py", encoding="utf-8").read()
       + open("email_parser/live_scoring.py", encoding="utf-8").read()
       + open("app.py", encoding="utf-8").read())
import re as _re
code = [ln.strip() for ln in src.splitlines()
        if _re.match(r"\s*(return|\S+\s*=|\S+\[[^\]]*\]\s*=)\s*.*int\(round\(abs\(", ln)]
check("the round deduction is written once, and only once",
      len(code) == 1 and code[0].strip().startswith("return int(round(abs(ph)))"),
      f"{len(code)} executable copies: {code}")


print("\n== Pat Youngs' card, the surface Kerry was looking at ==")
card = db.get_scorecard(3500, db_path=DB)
holes = {h["hole_number"]: h for h in card["holes"] if h["strokes"] is not None}
t = card["derived_totals"]

check("the card is the right one", len(holes) == 9 and
      sum(h["strokes"] for h in holes.values()) == 33)
check("no hole carries a give-back stroke any more",
      all(h["game_strokes_received"] == 0 for h in holes.values()),
      str({k: v["game_strokes_received"] for k, v in holes.items()}))
check("the give-back is still on the record, just not on the hole",
      [holes[h]["strokes_given_back"] for h in (3, 4, 8)] == [1, 1, 1])
check("the NET row now equals the GROSS row",
      t["game_net"] == 33, str(t["game_net"]))
check("hole 3 stops reading NET 4 on a GROSS 3",
      holes[3]["strokes"] - holes[3]["game_strokes_received"] == 3)
check("hole 3's net points go 0 -> 1",
      holes[3]["game_stableford_net"] == 1 and holes[3]["stableford_net"] == 0,
      f'{holes[3]["game_stableford_net"]} / {holes[3]["stableford_net"]}')
check("hole 4's birdie is scored as a birdie",
      holes[4]["game_stableford_net"] == 2, str(holes[4]["game_stableford_net"]))
check("hole 8's birdie too",
      holes[8]["game_stableford_net"] == 2, str(holes[8]["game_stableford_net"]))
check("the hole-by-hole points now add to 11",
      t["game_stableford_net"] == 11, str(t["game_stableford_net"]))
check("his +3 still stands — taken off the ROUND, once",
      t["plus_points_adjust"] == -3 and t["plus_strokes_adjust"] == 3, str(t))
check("NET PTS after the plus is 8",
      t["game_stableford_net_after_plus"] == 8,
      str(t["game_stableford_net_after_plus"]))
check("NET after the plus is 36 — the handicap has not been given away",
      t["game_net_after_plus"] == 36, str(t["game_net_after_plus"]))
check("the round states its own deduction so the card can show it",
      card["round"]["plus_round_deduction"] == 3)
check("the TRUE WHS derivation is still published beside it",
      t["stableford_net"] == 8 and holes[3]["net_vs_par"] == 1,
      "the parity/verify path lost its real values")

print("\n== a player with no plus is untouched ==")
with db._connect(DB) as conn:
    conn.execute("""INSERT INTO scoring_rounds (id, customer_id, player_name,
                        event_id, round_date, course_id, tee_id, holes_played,
                        playing_handicap, gross, net, source)
                    VALUES (3501, 137, 'YOUNG, Jeff', 3302, '2026-09-15', 22361,
                            112, 9, 0.0, 33, 33, 'gg')""")
    for hole, _p, _y, _si, strokes, _sr in CARD:
        conn.execute("""INSERT INTO scoring_holes (scoring_round_id, hole_number,
                                                   strokes, strokes_received)
                        VALUES (3501, ?, ?, 0)""", (hole, strokes))
    conn.commit()
plain = db.get_scorecard(3501, db_path=DB)
pt = plain["derived_totals"]
check("no adjustment line for a scratch player",
      pt["plus_points_adjust"] == 0 and pt["plus_strokes_adjust"] == 0)
check("game and WHS totals agree when nothing was given back",
      pt["game_stableford_net"] == pt["stableford_net"], str(pt))


print("\n== WHS REGRESSION: the index math is deliberately UNTOUCHED ==")
# USGA net double bogey adjusted gross, computed exactly as the five
# WHS call sites do — no `game=` flag anywhere near them.
adj = sum(db.compute_hole_derivations(p, s, sr, formulas)["adjusted_strokes"]
          for _h, p, _y, _si, s, sr in CARD)
check("his adjusted gross is his gross — nothing was capped",
      adj == 33, str(adj))
check("the card's adjusted gross agrees",
      card["derived_totals"]["adjusted_gross"] == 33,
      str(card["derived_totals"]["adjusted_gross"]))
dbsrc = open("email_parser/database.py", encoding="utf-8").read()
differential = round((113 / SLOPE) * (adj - RATING), 1)
check("his 9-hole differential is still 0.5", differential == 0.5,
      str(differential))
# The index is a pure function of the differentials — it never sees a
# hole, a stroke received or the game flag, which is exactly why the
# change above cannot move it. Pinned on a fixed set that includes this
# round's 0.5 so a future edit to the WHS path shows up here.
check("the index is computed from differentials alone",
      db.compute_handicap_index([differential, -1.0, -1.2]) == -3.2,
      str(db.compute_handicap_index([differential, -1.0, -1.2])))
check("…and a plus index still comes out negative, unrounded away",
      db.compute_handicap_index([0.5, 0.5, 0.5]) == -1.5,
      str(db.compute_handicap_index([0.5, 0.5, 0.5])))
check("the index function cannot see a hole at all",
      "strokes_received" not in dbsrc[
          dbsrc.index("def compute_handicap_index"):
          dbsrc.index("def compute_handicap_index") + 1400])
check("the plus stroke is STILL in the WHS cap, where it belongs",
      db.compute_hole_derivations(3, 9, -1, formulas)["adjusted_strokes"] == 4,
      "net double bogey stopped reading the give-back")

# The five WHS/index call sites must not have acquired the flag.
whs_sites = ("get_differential_parity", "get_scoring_handicap_preview",
             "_two_nine_recap_rows", "derive_18hole_rounds_as_two_nines",
             "_nine_totals_for_card")
for name in whs_sites:
    i = dbsrc.index(f"def {name}")
    j = dbsrc.find("\ndef ", i + 1)
    body = dbsrc[i:j if j > 0 else len(dbsrc)]
    check(f"{name} still computes WHS with the real allocation",
          "game=True" not in body,
          "a WHS call site acquired the game flag — differentials would move")

try:
    os.unlink(DB)
except OSError:
    pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
