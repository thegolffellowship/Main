"""Team Net 1-, 2- and 3-ball on the EVENTS board and in the engine
(Kerry 10/19, leaderboard review 12.4 / 12.6, build B9).

Kerry: "we need to build in TEAM Net 2 and 3 ball options too, where we're
adding cumulative of the two best or three best net scores." The board took
the single low ball (Best 1) while the event's dial said Best 2, so a Best 2
night would have paid on one thing and shown another. Now:

- `get_event_leaderboard` sums the N lowest nets on each hole (N from
  `event_team_net_dial`, sent as `team_balls`), counts a hole only once every
  player on the team has a score there (a blind never holds a hole), and
  ranks on ± (against par for each counted ball), then holes played, then
  name. The untethered payouts rank on this same `teams[]` list.
- `live_scoring.game_team_net` takes the same N, so the engine agrees.

Run: python3 test_team_net_nball.py
"""
import os, sys, tempfile, contextlib, io, logging
os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
from email_parser import database as db  # noqa: E402
from email_parser import live_scoring as ls  # noqa: E402
logging.disable(logging.ERROR)
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


PAR = [4, 4, 3, 5, 4, 4, 3, 4, 5]
SI = [5, 3, 9, 1, 11, 7, 13, 17, 15]


def build(balls, missing=None):
    """Four foursomes, PH 0 everywhere (no pops), so nets are gross.
    Team 1 (cids 101-104) and team 2 (cids 105-108). `missing` = (cid, hole)
    left unposted."""
    tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-nball-"), "t.db")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        db.init_db(tmp)
    EV, COURSE, TEE = 993, 9930, 99300
    name = f"s9.98 NBall {balls}"
    # gross relative to par per player per hole
    rel = {
        101: [0] * 9,                 # par golfer
        102: [-1] + [1] * 8,          # birdie on 1, bogeys after
        103: [-1] + [2] * 8,          # birdie on 1 too: a TIE at the cutoff
        104: [3] * 9,
        105: [1] * 9,
        106: [1] * 9,
        107: [1] * 9,
        108: [1] * 9,
    }
    # 16 players so the matrix runs foursomes (below 16 it is CART Net)
    for c in range(109, 117):
        rel[c] = [1] * 9
    with db._connect(tmp) as conn:
        db._ensure_scoring_tables(conn)
        db._ensure_pairing_tables(conn)
        db._ensure_gg_game_flights_tables(conn)
        db._ensure_gg_game_results_tables(conn)
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, format, "
                     "course_id, course) VALUES (?, ?, '2026-10-20', 'San Antonio', "
                     "'9 Holes', ?, 'NBall GC')", (EV, name, COURSE))
        try:
            conn.execute("ALTER TABLE events ADD COLUMN team_ball_count INTEGER")
        except Exception:
            pass
        conn.execute("UPDATE events SET team_ball_count = ? WHERE id = ?", (balls, EV))
        conn.execute("INSERT INTO courses (course_id, name) VALUES (?, 'NBall GC')", (COURSE,))
        conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope, rating, "
                     "yardage_total) VALUES (?, ?, '1 - Gold Tee', 113, 36.0, 3000)", (TEE, COURSE))
        for h in range(1, 10):
            conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, "
                         "stroke_index) VALUES (?,?,?,?,?)", (TEE, h, PAR[h - 1], 350, SI[h - 1]))
        rid = 0
        for c, r in rel.items():
            rid += 1
            g = (c - 101) // 4 + 1
            cp = (c - 101) % 4 + 1
            gross = [PAR[i] + r[i] for i in range(9)]
            conn.execute("INSERT INTO customers (customer_id, first_name, last_name) "
                         "VALUES (?, 'Pat', ?)", (c, f"P{c}"))
            conn.execute("INSERT INTO scoring_rounds (id, customer_id, player_name, event_id, "
                         "round_date, course_id, tee_id, holes_played, playing_handicap, gross, "
                         "net, source) VALUES (?,?,?,?, '2026-10-20', ?, ?, 9, 0, ?, ?, 'entry')",
                         (rid, c, f"P{c}, Pat", EV, COURSE, TEE, sum(gross), sum(gross)))
            for h in range(1, 10):
                if missing and missing == (c, h):
                    continue
                conn.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, "
                             "strokes, strokes_received) VALUES (?,?,?,0)",
                             (rid, h, gross[h - 1]))
            conn.execute("INSERT INTO event_pairings (event_id, holes, group_num, slot_label, "
                         "player_name, cart_pos, customer_id) VALUES (?, '9', ?, ?, ?, ?, ?)",
                         (EV, g, str(g), f"Pat P{c}", cp, c))
        conn.commit()
    return db.get_event_leaderboard(name, db_path=tmp)


# ── Best 2 ─────────────────────────────────────────────────────────────
lb = build(2)
check("the board says the ball count (team_balls = 2)", (lb or {}).get("team_balls") == 2,
      str((lb or {}).get("team_balls")))
check("…and the unit", (lb or {}).get("team_unit") in ("team", "cart"), str((lb or {}).get("team_unit")))
teams = {str(t["team_num"]): t for t in (lb or {}).get("teams") or []}
t1, t2 = teams.get("1") or {}, teams.get("2") or {}
# team 1 per hole: hole 1 -> two birdies = 2*3 under? nets: 101 par(4), 102 3, 103 3, 104 7
# -> best two 3+3 = 6 (par 8, -2). Holes 2-9: 101 par, 102 +1 -> 2*par + 1.
want1 = 6 + sum(2 * PAR[i] + 1 for i in range(1, 9))
check("Best 2: team NET is the sum of the two lowest nets on every hole",
      t1.get("total_net") == want1, f"{t1.get('total_net')} != {want1}")
check("± is against 2 x par for the holes counted (-2 on hole 1, +1 on each of 8)",
      t1.get("to_par") == -2 + 8, str(t1.get("to_par")))
check("team 2: two bogeys a hole = +2 x 9", t2.get("to_par") == 18 and
      t2.get("total_net") == sum(2 * p + 2 for p in PAR), str((t2.get("to_par"), t2.get("total_net"))))
check("THRU counts the holes every player has posted (9)", t1.get("thru") == 9 and t1.get("complete") is True,
      str((t1.get("thru"), t1.get("complete"))))
h1 = (t1.get("team_holes") or {}).get("1") or {}
check("hole 1 counts two balls", h1.get("net") == 6 and h1.get("balls") == 2, str(h1))
h2 = (t1.get("team_holes") or {}).get("2") or {}
check("hole 2: the par and the bogey counted (rids 1 and 2)", sorted(h2.get("counted") or []) == [1, 2], str(h2))
check("ranked on ±: team 1 first", [str(t["team_num"]) for t in lb["teams"]][:1] == ["1"],
      str([t["team_num"] for t in lb["teams"]]))
check("positions: 1, then the three level teams share T2",
      [t["position"] for t in lb["teams"]] == ["1", "T2", "T2", "T2"],
      str([t["position"] for t in lb["teams"]]))

# ── Best 1: a tie at the cutoff names every tied ball ─────────────────
lb1 = build(1)
t1b = {str(t["team_num"]): t for t in lb1["teams"]}["1"]
check("Best 1 still sums one ball a hole", t1b.get("total_net") == 3 + sum(PAR[1:]),
      str(t1b.get("total_net")))
c1 = sorted(((t1b.get("team_holes") or {}).get("1") or {}).get("counted") or [])
check("Best 1, hole 1: two birdies tie for the low ball, both are counted balls", c1 == [2, 3], str(c1))

# ── Best 3 ─────────────────────────────────────────────────────────────
lb3 = build(3)
t13 = {str(t["team_num"]): t for t in lb3["teams"]}["1"]
want3 = (4 + 3 + 3) + sum(3 * PAR[i] + 1 + 2 for i in range(1, 9))
check("Best 3 sums the three lowest", t13.get("total_net") == want3, f"{t13.get('total_net')} != {want3}")
check("Best 3 ± is against 3 x par", t13.get("to_par") == -2 + 8 * 3, str(t13.get("to_par")))

# ── a hole waits for the whole team ────────────────────────────────────
lbm = build(2, missing=(104, 9))
t1m = {str(t["team_num"]): t for t in lbm["teams"]}["1"]
check("a hole one player has not posted does not count for the team (THRU 8)",
      t1m.get("thru") == 8 and "9" not in (t1m.get("team_holes") or {}), str(t1m.get("thru")))
check("…so the team total leaves hole 9 out entirely",
      t1m.get("total_net") == want1 - (2 * PAR[8] + 1), str(t1m.get("total_net")))
check("…and the team is not complete", t1m.get("complete") is False)

# ── the engine agrees ──────────────────────────────────────────────────
cfg = ls.SEED_LIVE_SCORING_CONFIG


def card(name, team, rel):
    return {"name": name, "team": team, "key": name,
            "holes": [{"hole": h, "par": PAR[h - 1], "strokes": PAR[h - 1] + rel[h - 1],
                       "strokes_received": 0} for h in range(1, 10)]}


cards = [card("A", 1, [0] * 9), card("B", 1, [-1] + [1] * 8),
         card("C", 1, [-1] + [2] * 8), card("D", 1, [3] * 9)]
e2 = ls.game_team_net(cards, cfg, balls=2)
check("engine Best 2: vs_par is the same +6", e2["teams"][0]["vs_par"] == 6, str(e2["teams"][0]["vs_par"]))
check("engine reports its ball count", e2.get("balls") == 2)
e1 = ls.game_team_net(cards, cfg)
check("engine default is still Best 1 (-1 + 0*8)", e1["teams"][0]["vs_par"] == -1, str(e1["teams"][0]["vs_par"]))
check("engine names both tied balls on hole 1", sorted(e1["teams"][0]["holes"][0]["counted"]) == ["B", "C"],
      str(e1["teams"][0]["holes"][0]))
e3 = ls.game_team_net(cards, cfg, balls=3)
check("engine Best 3", e3["teams"][0]["vs_par"] == -2 + 24, str(e3["teams"][0]["vs_par"]))
check("compute_leaderboard reads team_balls from the state meta",
      "team_balls" in open(ls.__file__).read())

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
