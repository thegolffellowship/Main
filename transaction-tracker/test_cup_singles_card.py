"""Sunday singles: one 4-player card per tee time (Kerry 2026-10-09: "Singles
match live scoring needs to have all four players from the group still in one
interface so one person can score the group even though there's two
matches").

cup_seed puts two singles matches that share a tee time on ONE card
("SUN-1 + SUN-2"). Re-seeding a round that was seeded one match per card:
players (and any scores) move to the merged card, a card number that now
holds different players gets a new link and a free scorer's seat, and the
emptied leftover cards are dropped. Anything that still holds a score is kept.

Run: python3 test_cup_singles_card.py
"""
import os, sys, json, tempfile, contextlib, io, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-cupsingles-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
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


EV = 3329
CIDS = [7, 87, 109, 136, 672, 703, 13, 82]
with db._connect(tmp) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, format, course) VALUES "
                 "(?, 'LONE STAR CUP 2026', '2026-10-11', '18 Holes', 'The Hideout')", (EV,))
    for c in CIDS:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)",
                     (c, f"F{c}", f"L{c}"))
    conn.commit()
course = [{"hole": h, "par": 4, "stroke_index": h, "yardage": 380} for h in range(1, 19)]
M = [("SUN-1", "8:30", 7, 87), ("SUN-2", "8:30", 109, 136), ("SUN-3", "8:40", 672, 703),
     ("SUN-4", "8:40", 13, 82)]
dial = {"event_id": EV, "sessions": [{"id": "sun", "label": "SINGLES", "date": "2026-10-11",
        "format": "singles", "matches": [{"id": i, "tee_time": t, "austin": [a], "sa": [s]} for i, t, a, s in M]}]}
db.set_app_setting("lsc_matches", json.dumps(dial), tmp)

print("dry run: two singles matches off one tee time are one card")
with contextlib.redirect_stdout(io.StringIO()):
    dr = se.cup_seed(EV, db_path=tmp)
gs = dr["sessions"][0]["groups"]
check("4 matches at 2 tee times -> 2 cards", len(gs) == 2, gs)
check("the 8:30 card carries both matches' four players, match by match",
      gs[0]["label"] == "SUN-1 + SUN-2" and gs[0]["tee_time"] == "8:30"
      and [p["customer_id"] for p in gs[0]["players"]] == [7, 87, 109, 136], gs[0])
check("the 8:40 card", gs[1]["label"] == "SUN-3 + SUN-4"
      and [p["customer_id"] for p in gs[1]["players"]] == [672, 703, 13, 82], gs[1])

print("the live round was seeded one match per card: re-seed it")
rid = se.create_round(EV, 18, round_date="2026-10-11", label="LONE STAR CUP · SINGLES",
                      course_holes=course, pairings_holes="lsc:sun", created_by="test", db_path=tmp)["round_id"]
old = []
for n, (i, t, a, s) in enumerate(M, 1):
    old.append(se.upsert_group(rid, n, label=i, tee_time=t, players=[
        {"customer_id": a, "display_name": f"F{a} L{a}", "seat": 1},
        {"customer_id": s, "display_name": f"F{s} L{s}", "seat": 2}], db_path=tmp)["group_id"])
tok_before = {g: se.make_group_token(g, db_path=tmp) for g in old}
# a phone holds the 9:00-style card (group 3) and a score sits on group 2's player
with db._connect(tmp) as conn:
    conn.execute("INSERT INTO se_group_locks (group_id, device_id, claimed_at, heartbeat_at) "
                 "VALUES (?, 'dev-kerry', '2026-10-09', '2026-10-09')", (old[2],))
    conn.execute("INSERT INTO se_hole_scores (round_id, group_id, subject_key, customer_id, hole_number, gross, "
                 "device_id, op_id, server_ts) VALUES (?, ?, 'c:109', 109, 1, 4, 'dev', 'op1', '2026-10-09')", (rid, old[1]))
    conn.commit()
dial["sessions"][0]["se_round"] = rid
db.set_app_setting("lsc_matches", json.dumps(dial), tmp)
with contextlib.redirect_stdout(io.StringIO()):
    ap = se.cup_seed(EV, apply=True, db_path=tmp)
sv = ap["sessions"][0]
with db._connect(tmp) as conn:
    groups = conn.execute("SELECT id, group_num, label, tee_time FROM se_groups WHERE round_id = ? "
                          "ORDER BY group_num", (rid,)).fetchall()
    where = {r[0]: r[1] for r in conn.execute("SELECT customer_id, group_id FROM se_players WHERE round_id = ?", (rid,))}
    score_gid = conn.execute("SELECT group_id FROM se_hole_scores WHERE subject_key = 'c:109'").fetchone()[0]
    locks = conn.execute("SELECT COUNT(*) FROM se_group_locks").fetchone()[0]
check("the round now has two cards, one per tee time",
      [(g[1], g[2], g[3]) for g in groups] == [(1, "SUN-1 + SUN-2", "8:30"), (2, "SUN-3 + SUN-4", "8:40")],
      [tuple(g) for g in groups])
check("same round reused", sv.get("round_id") == rid, sv)
check("all four 8:30 players sit on card 1, all four 8:40 players on card 2",
      {c for c, g in where.items() if g == old[0]} == {7, 87, 109, 136}
      and {c for c, g in where.items() if g == old[1]} == {672, 703, 13, 82}, where)
check("a player's score moved with him to his new card", score_gid == old[0], score_gid)
check("the emptied cards 3 and 4 are dropped", sv.get("dropped_empty_groups") == [old[2], old[3]], sv)
check("the phone's seat on the dropped card is gone", locks == 0, locks)
check("card 2 holds different players now: new link, the old one is dead",
      old[1] in (sv.get("relinked_groups") or []) and se.verify_group_token(tok_before[old[1]], db_path=tmp) is None
      and se.verify_group_token(se.make_group_token(old[1], db_path=tmp), db_path=tmp) == old[1], sv)
check("card 1 changed too (two players joined): new link",
      old[0] in (sv.get("relinked_groups") or []) and se.verify_group_token(tok_before[old[0]], db_path=tmp) is None, sv)

print("a second re-seed changes nothing")
tok_now = {g: se.make_group_token(g, db_path=tmp) for g in old[:2]}
with contextlib.redirect_stdout(io.StringIO()):
    ap2 = se.cup_seed(EV, apply=True, db_path=tmp)
sv2 = ap2["sessions"][0]
check("no relink, no drop on an unchanged round",
      not sv2.get("relinked_groups") and not sv2.get("dropped_empty_groups"), sv2)
check("the links handed out after the regroup still work",
      all(se.verify_group_token(t, db_path=tmp) == g for g, t in tok_now.items()))

print("a leftover card that still holds a score is kept, never dropped")
with db._connect(tmp) as conn:
    g9 = conn.execute("INSERT INTO se_groups (round_id, group_num, label) VALUES (?, 9, 'stray')", (rid,)).lastrowid
    conn.execute("INSERT INTO se_hole_scores (round_id, group_id, subject_key, customer_id, hole_number, gross, "
                 "device_id, op_id, server_ts) VALUES (?, ?, 'c:7', 7, 2, 5, 'dev', 'op2', '2026-10-09')", (rid, g9))
    conn.commit()
with contextlib.redirect_stdout(io.StringIO()):
    ap3 = se.cup_seed(EV, apply=True, db_path=tmp)
check("the stray card with a score is reported, not deleted",
      ap3["sessions"][0].get("leftover_groups_kept") == [g9], ap3["sessions"][0])

print("Fourball is untouched: matches at different tee times stay one card each")
dial2 = {"event_id": EV, "sessions": [{"id": "sat-am", "label": "FOURBALL", "date": "2026-10-10",
         "format": "fourball", "matches": [{"id": "A1", "tee_time": "8:30", "austin": [7, 87], "sa": [109, 136]},
                                           {"id": "A2", "tee_time": "8:40", "austin": [672, 703], "sa": [13, 82]}]}]}
db.set_app_setting("lsc_matches", json.dumps(dial2), tmp)
with contextlib.redirect_stdout(io.StringIO()):
    fb = se.cup_seed(EV, db_path=tmp)
check("two fourball matches, two cards", [g["label"] for g in fb["sessions"][0]["groups"]] == ["A1", "A2"], fb)

print("the scoring screen boxes each singles match on a two-match card")
tpl = open("templates/score_entry.html", encoding="utf-8").read()
check("teamGroups boxes a two-match singles card by match",
      'x.format === "singles"' in tpl and '"MATCH " + (m.match_no' in tpl, "")

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
