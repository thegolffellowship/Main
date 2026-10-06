"""The EVENTS leaderboard's Team Net plays the drawn blinds (v2.525.9).

Kerry 2026-10-06, Olympia Hills (event 3308) in play: "The team totals
are screwed up and aren't considering the blinds." The board read a blind
only off Golf Genius's recorded team string ("Bl[LAST, First]"); a phone-
scored event has no GG result, so every short team played without its
blind. `blind_draws` is the draw of record; the blind plays the drawn
player's own card. Also: a seat is matched to its card by customer_id,
so a sheet that says "Michael Murphy" finds the card "MURPHY, Mike".

Run: python3 test_events_board_blinds.py
"""
import os, sys, tempfile, contextlib, io, logging
os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
from email_parser import database as db  # noqa: E402
logging.disable(logging.ERROR)
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


PAR = [4, 4, 3, 4, 5, 4, 4, 3, 4]
SI = [5, 3, 9, 1, 11, 7, 13, 17, 15]
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-blinds-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
EV, COURSE, TEE = 992, 9920, 99200
NAME = "s9.97 Blind Test"
# 19 players → foursomes (below 16 the matrix runs CART Net). Group 5 is a
# threesome; its blind is Daniel Miller from group 1. Seat 2 of group 5 is
# "Michael Murphy" on the sheet and "MURPHY, Mike" on the card.
CARDS = {}       # customer_id -> (card name, sheet name, group, cart_pos, gross per hole)
cid = 100
for g in range(1, 6):
    for cp in range(1, 5):
        if g == 5 and cp == 4:
            continue
        cid += 1
        card = f"PLAYER{cid}, Pat"
        sheet = f"Pat Player{cid}"
        if cid == 101:
            card, sheet = "MILLER, Daniel", "Daniel Miller"
        if g == 5 and cp == 2:
            card, sheet = "MURPHY, Mike", "Michael Murphy"
        # group 5 shoots bogeys; Miller shoots par; everyone else par+2
        gross = ([p + 1 for p in PAR] if g == 5 else
                 (PAR if cid == 101 else [p + 2 for p in PAR]))
        CARDS[cid] = (card, sheet, g, cp, gross)

with db._connect(tmp) as conn:
    db._ensure_scoring_tables(conn)
    db._ensure_pairing_tables(conn)
    db._ensure_gg_game_flights_tables(conn)
    db._ensure_gg_game_results_tables(conn)
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, format, "
                 "course_id, course) VALUES (?, ?, '2026-10-06', 'San Antonio', "
                 "'9 Holes', ?, 'Blind Test GC')", (EV, NAME, COURSE))
    conn.execute("INSERT INTO courses (course_id, name) VALUES (?, 'Blind Test GC')", (COURSE,))
    conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope, rating, "
                 "yardage_total) VALUES (?, ?, '1 - Gold Tee', 120, 35.0, 3000)", (TEE, COURSE))
    for h in range(1, 10):
        conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, "
                     "stroke_index) VALUES (?,?,?,?,?)", (TEE, h, PAR[h - 1], 350, SI[h - 1]))
    rid = 0
    for c, (card, sheet, g, cp, gross) in CARDS.items():
        rid += 1
        fn, ln = sheet.split(" ", 1)
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) "
                     "VALUES (?,?,?)", (c, fn, ln))
        conn.execute("INSERT INTO scoring_rounds (id, customer_id, player_name, event_id, "
                     "round_date, course_id, tee_id, holes_played, playing_handicap, gross, "
                     "net, source) VALUES (?,?,?,?, '2026-10-06', ?, ?, 9, 2, ?, ?, 'entry')",
                     (rid, c, card, EV, COURSE, TEE, sum(gross), sum(gross) - 2))
        for h in range(1, 10):
            conn.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, "
                         "strokes, strokes_received) VALUES (?,?,?,?)",
                         (rid, h, gross[h - 1], 1 if SI[h - 1] <= 2 else 0))
        conn.execute("INSERT INTO event_pairings (event_id, holes, group_num, slot_label, "
                     "player_name, cart_pos, customer_id) VALUES (?, '9', ?, ?, ?, ?, ?)",
                     (EV, g, str(g), sheet, cp, c))
    conn.execute("INSERT INTO blind_draws (event_id, event_date, chapter, holes, group_num, "
                 "slot_label, cart_pos, customer_id, player_name, slot_key, source) "
                 "VALUES (?, '2026-10-06', 'San Antonio', '9', 5, '5', 4, 101, "
                 "'Daniel Miller', '9:5:4', 'app')", (EV,))
    conn.commit()

lb = db.get_event_leaderboard(NAME, db_path=tmp)
teams = {str(t["team_num"]): t for t in (lb or {}).get("teams") or []}
check("five foursome teams on the board", set(teams) == {"1", "2", "3", "4", "5"}, str(sorted(teams)))
t4 = teams.get("5") or {"players": []}
names = [p["player_name"] for p in t4["players"]]
check("team 5 carries its blind as Bl[MILLER, Daniel]", "Bl[MILLER, Daniel]" in names, str(names))
bl = next((p for p in t4["players"] if p.get("blind")), None)
check("the blind plays Miller's own card", bool(bl) and bl["scoring_round_id"] == 1
      and bl["customer_id"] == 101, str(bl))
mm = next((p for p in t4["players"] if p["player_name"] == "MURPHY, Mike"), None)
check("'Michael Murphy' on the sheet is matched to the card 'MURPHY, Mike' by customer_id",
      bool(mm) and mm["scoring_round_id"] is not None, str([p for p in t4["players"]]))
check("no unmatched 'Michael Murphy' row remains", "Michael Murphy" not in names, str(names))
# best ball: Miller's par beats the threesome's bogeys on every hole;
# his pop on the SI-1 hole makes it a net birdie.
check("team 5's total is the blind's best ball (par less one pop = 34)",
      t4.get("total_net") == sum(PAR) - 1, str(t4.get("total_net")))
check("team 5's team handicaps include the blind", bl is not None and "team_hcp" in bl, str(bl))
t1 = teams.get("1") or {"players": []}
check("Miller still plays on his own team 1 as himself",
      any(p["player_name"] == "MILLER, Daniel" and not p.get("blind") for p in t1["players"]),
      str([p["player_name"] for p in t1["players"]]))
check("team 1's total is Miller's best ball too (34)", t1.get("total_net") == sum(PAR) - 1,
      str(t1.get("total_net")))

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
