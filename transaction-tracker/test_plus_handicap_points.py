"""A plus handicap comes off the ROUND, never off a hole.

Kerry 2026-09-16, on Pat Youngs:

  "For MVP nobody is allowed to have to add strokes on any given hole, so
   there should be no pluses on any holes. But his +3 PH still stands.
   The way it works on our side is that his total points gets deducted
   that 3 strokes. It's not fair to make a player have to perform on any
   one hole, but it should be applied across a round."

Golf Genius allocates a plus handicap onto the easiest holes, which makes
a specific hole harder than the card says. The arithmetic lands in the
same place either way; what changes is that no single hole decides it.

Run: python3 test_plus_handicap_points.py
"""
import os, sys, sqlite3, tempfile, contextlib, io, logging
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
from email_parser import live_scoring as ls  # noqa: E402
logging.getLogger("email_parser.database").setLevel(logging.ERROR)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

PAR = [4, 4, 3, 4, 5, 4, 4, 3, 4]
SI = [5, 3, 9, 1, 11, 7, 13, 17, 15]

print("\n== the engine: no hole is made harder ==")
HOLES = [{"hole": h, "par": PAR[h - 1], "stroke_index": SI[h - 1],
          "yardage": 350} for h in range(1, 10)]
scores = {h: PAR[h - 1] for h in range(1, 10)}       # level par every hole
FORMULAS = db.get_scoring_formulas()

def _card(ph):
    state = {"holes": HOLES,
             "players": [{"key": "p1", "name": "Pat Youngs",
                          "playing_handicap": ph, "scores": scores,
                          "buys_net": True, "buys_gross": True}]}
    return ls.build_cards(state, FORMULAS)[0]

plus, scratch = _card(-3), _card(0)

check("no hole POINTS differently for a plus player",
      [h.get("stableford_net") for h in plus["holes"]]
      == [h.get("stableford_net") for h in scratch["holes"]],
      str([h.get("stableford_net") for h in plus["holes"]]))
check("the plus is taken off the TOTAL, once",
      plus["stableford_net"] == scratch["stableford_net"] - 3,
      f'{plus["stableford_net"]} vs {scratch["stableford_net"]}')
check("…and the card says so, so the board can show the arithmetic",
      plus.get("points_plus_adjust") == -3, str(plus.get("points_plus_adjust")))
check("stroke-play NET still carries the real allocation",
      plus["net"] == scratch["net"] + 3,
      f'{plus["net"]} vs {scratch["net"]}')

print("\n== the leaderboard: same rule, same answer ==")
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-plus-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
EV, COURSE, TEE = 991, 9910, 99100
with db._connect(tmp) as conn:
    db._ensure_scoring_tables(conn)
    db._ensure_gg_game_flights_tables(conn)
    db._ensure_gg_game_results_tables(conn)
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, format) "
                 "VALUES (?, 's9.98 Plus Test', '2026-09-16', 'San Antonio', '9 Holes')", (EV,))
    conn.execute("INSERT INTO courses (course_id, name) VALUES (?, 'Plus Test GC')", (COURSE,))
    conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope, rating, "
                 "yardage_total) VALUES (?, ?, '1 - Gold Tee', 120, 35.0, 3000)", (TEE, COURSE))
    for h in range(1, 10):
        conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, "
                     "stroke_index) VALUES (?,?,?,?,?)", (TEE, h, PAR[h - 1], 350, SI[h - 1]))
    # Two players on identical level-par rounds: one scratch, one +3. GG
    # has already written the give-back strokes onto the plus player's
    # easiest holes, exactly as it does live.
    for rid, nm, ph in ((1, "Scratch Sam", 0.0), (2, "Pat Youngs", -3.0)):
        conn.execute("INSERT INTO scoring_rounds (id, player_name, event_id, round_date, "
                     "course_id, tee_id, holes_played, playing_handicap, gross, net, source) "
                     "VALUES (?,?,?, '2026-09-16', ?, ?, 9, ?, 35, ?, 'gg')",
                     (rid, nm, EV, COURSE, TEE, ph, 35 - ph))
        give = {8: -1, 15: -1, 11: -1}     # GG's easiest-first allocation
        for h in range(1, 10):
            sr = -1 if (ph < 0 and SI[h - 1] in (17, 15, 13)) else 0
            conn.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, "
                         "strokes, strokes_received) VALUES (?,?,?,?)",
                         (rid, h, PAR[h - 1], sr))
    conn.commit()

lb = db.get_event_leaderboard("s9.98 Plus Test", db_path=tmp)
rows = {r["player_name"]: r for r in (lb.get("overall_board") or [])}
check("both players posted", set(rows) == {"Scratch Sam", "Pat Youngs"}, str(sorted(rows)))
if len(rows) == 2:
    check("the plus player's points are the scratch player's, less 3",
          rows["Pat Youngs"]["net_pts"] == rows["Scratch Sam"]["net_pts"] - 3,
          f'{rows["Pat Youngs"]["net_pts"]} vs {rows["Scratch Sam"]["net_pts"]}')
    check("…and the board carries the adjustment so it can be shown",
          rows["Pat Youngs"]["pts_plus_adjust"] == -3,
          str(rows["Pat Youngs"].get("pts_plus_adjust")))
    check("the scratch player has no adjustment",
          rows["Scratch Sam"].get("pts_plus_adjust") in (None, 0))
    hp = (lb.get("hole_pts") or {}).get("2") or {}
    hp0 = (lb.get("hole_pts") or {}).get("1") or {}
    check("no HOLE scored differently for the plus player",
          hp == hp0, f"{hp} vs {hp0}")

_cts = open("templates/contests.html", encoding="utf-8").read()
check("the PTS row shows the deduction rather than looking like bad maths",
      "pts_plus_adjust" in _cts and "comes off the round" in _cts)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
