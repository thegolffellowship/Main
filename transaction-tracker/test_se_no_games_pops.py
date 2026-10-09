"""NO GAMES, NO TEAM POPS (Kerry 2026-10-08, the LSC practice round card
showed "85% Cart Stroke": "The only thing we should be showing is 100% PH
pops. No Cart/Team Net pops because there's no games in the practice
round"). An event whose included-games price is $0 (database.event_games_off)
draws only handicap pops; an event with games keeps its team pops.

Run: python3 test_se_no_games_pops.py
"""
import os, sys, tempfile, contextlib, io, logging, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-nogames-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser import score_entry as se                        # noqa: E402
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


c = sqlite3.connect(tmp)
for cid, fn, ln in ((18, "Kerry", "Niester"), (703, "Michael", "Mesa")):
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
for eid, name, fee in ((3330, "LSC PRACTICE ROUND | Test", 0), (4400, "s10.13 Test", 8)):
    c.execute("INSERT INTO events (id, item_name, event_date, format, side_game_fee) VALUES (?,?,?,?,?)",
              (eid, name, "2026-10-09", "18 Holes", fee))
c.commit()
c.close()
course = [{"hole": h, "par": 3 if h in (2, 5) else 4, "stroke_index": h} for h in range(1, 19)]


def card_for(eid):
    rid = se.create_round(eid, 18, round_date="2026-10-09", label="r", course_holes=course,
                          created_by="test", db_path=tmp)["round_id"]
    gid = se.upsert_group(rid, 1, players=[{"customer_id": 18, "playing_handicap": 6, "seat": 1},
                                           {"customer_id": 703, "playing_handicap": 3, "seat": 2}],
                          db_path=tmp)["group_id"]
    # a team handicap snapshotted the way the seed does (before the rule)
    se.set_game_handicaps(rid, {18: 5, 703: 5}, unit="cart", basis="85% of the cart's combined PH",
                          db_path=tmp)
    return se.get_group_card(gid, db_path=tmp)


print("no games (side_game_fee $0)")
k = card_for(3330)
check("100% handicap pops still drawn", sum((k.get("strokes") or {}).get("18", {}).values()) == 6, k.get("strokes"))
check("no team / cart pops", not (k.get("team_strokes") or {}) and not k.get("team_game"),
      (k.get("team_strokes"), k.get("team_game")))
check("no par-3 ghost marks either", not (k.get("team_par3_ghost") or {}))

print("an event with games keeps its team pops")
k2 = card_for(4400)
check("team pops present", bool(k2.get("team_strokes")) and (k2.get("team_game") or {}).get("pct") == 85,
      (k2.get("team_strokes"), k2.get("team_game")))

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILED: {F}"))
sys.exit(1 if F else 0)
