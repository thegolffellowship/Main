"""WHAT IF HE HAD PLAYED OFF HIS OWN HANDICAP (Kerry 2026-10-29): the
event's engine re-run in memory with one player's playing handicap
replaced; his pops are re-laid by the ruled allocator, points move, and
nothing is written.

Run: python3 test_whatif_handicap.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-whatif-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import database as db              # noqa: E402
from email_parser.whatif_handicap import whatif      # noqa: E402
from email_parser.handicap_calc import ruled_dots    # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

db.init_db(DB)
SI = {1: 13, 2: 5, 3: 7, 4: 1, 5: 11, 6: 9, 7: 17, 8: 15, 9: 3}
PAR = {1: 5, 2: 4, 3: 4, 4: 4, 5: 3, 6: 5, 7: 3, 8: 4, 9: 4}
GROSS = {1: 5, 2: 4, 3: 6, 4: 5, 5: 4, 6: 6, 7: 3, 8: 5, 9: 5}   # Baker 10/27
with db._connect(DB) as c:
    db._ensure_scoring_tables(c)
    c.execute("INSERT INTO course_tees (course_id, tee_name) VALUES (900002, 'Gold')")
    tee = c.execute("SELECT max(tee_id) FROM course_tees").fetchone()[0]
    for h in range(1, 10):
        c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, stroke_index) "
                  "VALUES (?, ?, ?, ?)", (tee, h, PAR[h], SI[h]))
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (87, 'Adam', 'Baker')")
    eid = c.execute("INSERT INTO events (item_name, event_date) VALUES "
                    "('s9.29 Silverhorn', '2026-10-27')").lastrowid
    r = c.execute("INSERT INTO scoring_rounds (player_name, customer_id, event_id, holes_played, "
                  "playing_handicap, tee_id, source, gross, net) VALUES ('Adam Baker', 87, ?, 9, 5, ?, 'entry', 43, 38)",
                  (eid, tee)).lastrowid
    pops5 = ruled_dots(5, SI)
    for h in range(1, 10):
        c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, "
                  "strokes_received) VALUES (?, ?, ?, ?)", (r, h, GROSS[h], pops5.get(h, 0)))
    c.commit()

out = whatif(eid, {87: 4}, db_path=DB)
check("no error", not out.get("error"), out.get("error"))
ch = (out.get("changed_players") or [{}])[0]
check("Baker's handicap 5 -> 4", ch.get("ph_was") == 5 and ch.get("ph_now") == 4, ch)
check("one pop comes off, on stroke index 9 (hole 6)",
      sum(ch["pops_was"].values()) == 5 and sum(ch["pops_now"].values()) == 4
      and ch["pops_was"].get(6) == 1 and ch["pops_now"].get(6, 0) == 0, ch)
pts = out["points"][0]
check("his points drop by one (7 -> 6), as hand-counted from his 10/27 card",
      pts["was"] == 7 and pts["now"] == 6, pts)
check("says it writes nothing", out["writes"] == "none")
with db._connect(DB) as c:
    ph = c.execute("SELECT playing_handicap FROM scoring_rounds WHERE id = ?", (r,)).fetchone()[0]
    p6 = c.execute("SELECT strokes_received FROM scoring_holes WHERE scoring_round_id = ? "
                   "AND hole_number = 6", (r,)).fetchone()[0]
check("...and the stored card is untouched", ph == 5 and p6 == 1, (ph, p6))
check("a customer with no card is refused",
      "none of those" in (whatif(eid, {12345: 4}, db_path=DB).get("error") or ""))
print("== the correction (Kerry: \"Leave the paid money alone, but correct the points\") ==")
from email_parser.ph_correct import correct
dry = correct(eid, 87, 4, note="test", db_path=DB)
with db._connect(DB) as c:
    still = c.execute("SELECT playing_handicap FROM scoring_rounds WHERE id = ?", (r,)).fetchone()[0]
check("dry run changes nothing", not dry.get("applied") and still == 5, (dry, still))
done = correct(eid, 87, 4, apply=True, note="test", db_path=DB)
with db._connect(DB) as c:
    row = c.execute("SELECT playing_handicap, net FROM scoring_rounds WHERE id = ?", (r,)).fetchone()
    p6 = c.execute("SELECT strokes_received FROM scoring_holes WHERE scoring_round_id = ? "
                   "AND hole_number = 6", (r,)).fetchone()[0]
check("the card now reads 4, net 39, no pop on hole 6",
      tuple(row) == (4.0, 39.0) and p6 == 0, (tuple(row), p6))
from email_parser import live_scoring as ls
st = db.event_engine_state("s9.29 Silverhorn", db_path=DB)
card = ls.build_cards(st, db.get_scoring_formulas(DB))[0]
check("the points read off the card are 6", card["stableford_net"] == 6, card["stableford_net"])
check("the correction is recorded with its note",
      '"note": "test"' in (db.get_app_setting("ph_corrections", db_path=DB) or ""))
check("the module never writes a payout",
      "tgf_payouts" not in open("email_parser/ph_correct.py").read())
_m = open("mcp_server.py", encoding="utf-8").read()
check("bridge scoring-ph-correct exists", 'cmd == "scoring-ph-correct"' in _m)
check("bridge scoring-whatif-ph exists", 'cmd == "scoring-whatif-ph"' in _m)

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
