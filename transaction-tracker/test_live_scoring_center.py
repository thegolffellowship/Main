"""Integration tests for the Live Scoring Test Center data layer.

Builds a throwaway SQLite database, plants a real-shaped event (course +
tee + imported GG scorecards + pairings + NET/GROSS purchases), then drives
the sandbox end to end: seed from the event, score by hand, autoplay,
recompute the leaderboard, and run the parity diff against GG's numbers.

The load-bearing assertion is the LAST one: seeding from a real event and
recomputing every game from raw gross scores must reproduce GG exactly.
That is the Stage-1 confidence gate from docs/claude/game-engine.md.

Run: python3 test_live_scoring_center.py
"""

import os
import sqlite3
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


NINE = [(1, 4, 380, 3), (2, 3, 155, 9), (3, 5, 520, 1), (4, 4, 400, 5),
        (5, 4, 365, 7), (6, 3, 190, 8), (7, 4, 430, 2), (8, 4, 375, 6),
        (9, 5, 505, 4)]
PAR = {h: p for h, p, _, _ in NINE}
PAR_TOTAL = sum(PAR.values())  # 36

# name, playing handicap, gross offset vs par per hole, buys NET, buys GROSS
FIELD = [
    ("Kerry Niester", 4, 0, True, True),
    ("Luke Mazanec", 9, 1, True, True),
    ("Adam Baker", 14, 1, True, False),
    ("Chris Best", 0, 0, False, True),
    ("Stuart Kirksey", 18, 2, True, True),
    ("Robert Hogue", 7, 1, True, True),
    ("Texas Terry", -1, 0, False, False),
    ("Guest Player", 12, 2, False, False),
]


def build_fixture(path):
    """A minimal but REAL-shaped database: only the tables the sandbox reads."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        -- Mirrors the REAL schema: first_name/last_name, NO customer_name.
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
                                first_name TEXT, last_name TEXT, chapter TEXT);
        CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT,
                             event_date TEXT, format TEXT, course TEXT);
        CREATE TABLE event_aliases (alias_name TEXT, canonical_event_name TEXT);
        CREATE TABLE items (id INTEGER PRIMARY KEY, parent_item_id INTEGER,
                            customer_id INTEGER, customer TEXT, item_name TEXT,
                            side_games TEXT, transaction_status TEXT,
                            wd_credits TEXT, holes TEXT, user_status TEXT);
        CREATE TABLE courses (course_id INTEGER PRIMARY KEY, name TEXT,
                              short_name TEXT, city TEXT, state TEXT,
                              status TEXT, chapter_id INTEGER);
        CREATE TABLE course_aliases (alias_name TEXT, course_id INTEGER);
        CREATE TABLE course_tees (tee_id INTEGER PRIMARY KEY, course_id INTEGER,
                                  tee_name TEXT, slope REAL, rating REAL,
                                  yardage_total INTEGER);
        CREATE TABLE course_tee_holes (tee_id INTEGER, hole_number INTEGER,
                                       par INTEGER, yardage INTEGER,
                                       stroke_index INTEGER,
                                       PRIMARY KEY (tee_id, hole_number));
        CREATE TABLE scoring_rounds (
            id INTEGER PRIMARY KEY, customer_id INTEGER, player_name TEXT,
            event_id INTEGER, gg_aggregate_id TEXT, round_date TEXT,
            course_id INTEGER, tee_id INTEGER, holes_played INTEGER,
            playing_handicap REAL, gross REAL, net REAL, flight TEXT,
            source TEXT);
        CREATE TABLE scoring_holes (
            id INTEGER PRIMARY KEY, scoring_round_id INTEGER,
            hole_number INTEGER, strokes INTEGER,
            strokes_received INTEGER DEFAULT 0, gg_result TEXT);
        CREATE TABLE event_pairings (
            id INTEGER PRIMARY KEY, event_id INTEGER, holes TEXT,
            group_num INTEGER, slot_label TEXT, player_name TEXT,
            cart_pos INTEGER, tee_choice TEXT, handicap_index REAL);
        CREATE TABLE handicap_settings (key TEXT PRIMARY KEY, value TEXT);
    """)
    conn.execute("INSERT INTO events (id, item_name, event_date, format, course)"
                 " VALUES (1, 's9.21 Test Center Open', '2026-07-25', '9 Hole',"
                 " 'Olympia Hills')")
    conn.execute("INSERT INTO courses (course_id, name) VALUES (1, 'Olympia Hills')")
    conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope,"
                 " rating, yardage_total) VALUES (1, 1, 'White', 121, 34.6, 3220)")
    for h, par, yd, si in NINE:
        conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par,"
                     " yardage, stroke_index) VALUES (1, ?, ?, ?, ?)",
                     (h, par, yd, si))

    for i, (name, ph, offset, net_buy, gross_buy) in enumerate(FIELD, start=1):
        _fn, _ln = name.split(" ", 1)
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name)"
                     " VALUES (?, ?, ?)", (i, _fn, _ln))
        sg = ("BOTH" if net_buy and gross_buy else "NET" if net_buy
              else "GROSS" if gross_buy else "NONE")
        conn.execute("INSERT INTO items (id, customer_id, customer, item_name,"
                     " side_games, transaction_status) VALUES (?, ?, ?, ?, ?,"
                     " 'active')", (i, i, name, 's9.21 Test Center Open', sg))
        conn.execute("INSERT INTO event_pairings (event_id, holes, group_num,"
                     " slot_label, player_name, cart_pos) VALUES"
                     " (1, '9', ?, 'A', ?, ?)",
                     ((i - 1) // 4 + 1, name, (i - 1) % 4 + 1))

        # GG's own dots, allocated by stroke index exactly as GG would.
        from email_parser.handicap_calc import allocate_strokes
        dots = allocate_strokes(int(ph), {h: si for h, _, _, si in NINE})
        gross = sum(PAR[h] + offset for h in PAR)
        conn.execute(
            "INSERT INTO scoring_rounds (id, customer_id, player_name, event_id,"
            " gg_aggregate_id, round_date, course_id, tee_id, holes_played,"
            " playing_handicap, gross, net, source) VALUES"
            " (?, ?, ?, 1, ?, '2026-07-25', 1, 1, 9, ?, ?, ?, 'gg')",
            (i, i, name, f"agg{i}", ph, gross, gross - ph))
        for h in sorted(PAR):
            strokes = PAR[h] + offset
            net_vs_par = strokes - dots[h] - PAR[h]
            marking = ("double_circle" if net_vs_par <= -2 else
                       "simple_circle" if net_vs_par == -1 else
                       "simple_square" if net_vs_par == 1 else
                       "double_square" if net_vs_par >= 2 else None)
            conn.execute(
                "INSERT INTO scoring_holes (scoring_round_id, hole_number,"
                " strokes, strokes_received, gg_result) VALUES (?, ?, ?, ?, ?)",
                (i, h, strokes, dots[h], marking))
    conn.commit()
    conn.close()


tmp = tempfile.mkdtemp(prefix="tgf-ls-test-")
DB = os.path.join(tmp, "test.db")
build_fixture(DB)

# ---------------------------------------------------------------------------
print("\n== session lifecycle ==")

created = db.ls_create_session("Synthetic nine", holes=9, db_path=DB)
sid = created["session_id"]
check("synthetic session created", sid > 0)

got = db.ls_get_session(sid, db_path=DB)
check("a synthetic session gets a default nine",
      len(got["holes"]) == 9, f"got {len(got['holes'])}")
check("default nine is par 36",
      sum(h["par"] for h in got["holes"]) == 36)
check("no players yet", got["players"] == [])

sessions = db.ls_list_sessions(db_path=DB)
check("session appears in the list", any(s["id"] == sid for s in sessions))

db.ls_update_session(sid, {"name": "Renamed", "championship": True}, db_path=DB)
check("session fields update",
      db.ls_get_session(sid, db_path=DB)["session"]["name"] == "Renamed")

created18 = db.ls_create_session("Synthetic eighteen", holes=18, db_path=DB)
got18 = db.ls_get_session(created18["session_id"], db_path=DB)
check("an 18-hole synthetic session gets 18 holes", len(got18["holes"]) == 18)
check("the back nine carries distinct stroke indexes",
      sorted(h["stroke_index"] for h in got18["holes"]) == list(range(1, 19)))

# ---------------------------------------------------------------------------
print("\n== players, scoring, autoplay ==")

p1 = db.ls_add_player(sid, "Ignored Name", customer_id=1, playing_handicap=4,
                      team_num=1, db_path=DB)
check("a linked player takes the CANONICAL name (Principle 6)",
      p1["player_name"] == "Kerry Niester", p1["player_name"])
p2 = db.ls_add_player(sid, "Walk On", playing_handicap=12, team_num=1,
                      is_member=False, db_path=DB)
check("an unlinked player keeps the typed name", p2["player_name"] == "Walk On")

db.ls_set_score(sid, p1["player_id"], 1, 4, db_path=DB)
db.ls_set_score(sid, p1["player_id"], 2, 3, db_path=DB)
state = db.ls_build_state(sid, db_path=DB)
kerry = next(p for p in state["players"] if p["key"] == str(p1["player_id"]))
check("hand-entered scores land in the state", kerry["scores"] == {1: 4, 2: 3},
      str(kerry["scores"]))
check("no dots stored -> the engine will DERIVE them",
      kerry["strokes_received"] == {})

db.ls_set_score(sid, p1["player_id"], 2, 5, db_path=DB)
check("a score can be corrected",
      db.ls_build_state(sid, db_path=DB)["players"][0]["scores"][2] == 5)
db.ls_set_score(sid, p1["player_id"], 2, None, db_path=DB)
check("a score can be cleared",
      2 not in db.ls_build_state(sid, db_path=DB)["players"][0]["scores"])

auto = db.ls_autoplay(sid, through_hole=5, seed=42, db_path=DB)
check("autoplay fills the field through the named hole",
      auto["through_hole"] == 5 and auto["scores_written"] > 0, str(auto))
st = db.ls_build_state(sid, db_path=DB)
check("autoplay never scores past the through-hole",
      all(max(p["scores"]) <= 5 for p in st["players"] if p["scores"]))
check("autoplay does NOT overwrite a hand-entered score",
      st["players"][0]["scores"][1] == 4, str(st["players"][0]["scores"]))

before = dict(st["players"][0]["scores"])
db.ls_autoplay(sid, through_hole=9, seed=42, db_path=DB)
after = db.ls_build_state(sid, db_path=DB)["players"][0]["scores"]
check("advancing the through-hole extends the same round",
      all(after[h] == before[h] for h in before) and len(after) == 9,
      f"{before} -> {after}")

db.ls_autoplay(sid, through_hole=9, seed=7, overwrite=True, db_path=DB)
check("overwrite replays the whole round",
      db.ls_build_state(sid, db_path=DB)["players"][0]["scores"] != after)

lb = db.ls_leaderboard(sid, db_path=DB)
check("leaderboard computes off the sandbox", lb["players"] == 2)
check("championship flag selects the championship schedule",
      lb["formulas_used"] == "championship", lb["formulas_used"])

db.ls_clear_scores(sid, db_path=DB)
check("scores clear", not any(p["scores"] for p in
                              db.ls_build_state(sid, db_path=DB)["players"]))

# ---------------------------------------------------------------------------
print("\n== seeding from a real event ==")

bad = db.ls_seed_session_from_event("no such event", db_path=DB)
check("seeding an unknown event errors cleanly", "error" in bad)

seed = db.ls_seed_session_from_event("s9.21 Test Center Open", db_path=DB)
ssid = seed["session_id"]
check("all eight cards seeded", seed["players_seeded"] == 8, str(seed))
check("NET buyers detected from purchases", seed["net_buyers"] == 5,
      f"got {seed['net_buyers']}")
check("GROSS buyers detected from purchases", seed["gross_buyers"] == 5,
      f"got {seed['gross_buyers']}")
check("teams came from the saved pairings", seed["teams_from_pairings"])

sdata = db.ls_get_session(ssid, db_path=DB)
check("the real tee's holes were copied", len(sdata["holes"]) == 9)
check("real par came across",
      sum(h["par"] for h in sdata["holes"]) == PAR_TOTAL)
check("every seeded player remembers its GG round",
      all(p["source_round_id"] for p in sdata["players"]))
check("GG's own dots came across",
      any(v["strokes_received"] for p in sdata["players"]
          for v in p["scores"].values()))
check("playing handicaps came across",
      sorted(p["playing_handicap"] for p in sdata["players"])
      == sorted(f[1] for f in FIELD))
check("pairings became teams",
      sorted({p["team_num"] for p in sdata["players"]}) == [1, 2])

# Production data must be untouched by any of this.
conn = sqlite3.connect(DB)
check("seeding wrote nothing to scoring_rounds",
      conn.execute("SELECT COUNT(*) FROM scoring_rounds").fetchone()[0] == 8)
check("seeding wrote nothing to scoring_holes",
      conn.execute("SELECT COUNT(*) FROM scoring_holes").fetchone()[0] == 72)
conn.close()

# ---------------------------------------------------------------------------
print("\n== leaderboard on seeded data ==")

board = db.ls_leaderboard(ssid, db_path=DB)
check("the whole field is on the board", board["players"] == 8)
check("regular formulas by default", board["formulas_used"] == "regular")
check("nine-hole rule set selected", board["holes_key"] == "9")

net = board["games"]["individual_net"]
check("Individual Net counts only NET buyers", net["buyers"] == 5,
      f"got {net['buyers']}")
check("5 net buyers on a nine -> 1 flight", len(net["flights"]) == 1)
gross = board["games"]["individual_gross"]
check("Individual Gross is inactive at 5 gross buyers",
      gross["active"] is False)

team = board["games"]["team_net"]
check("two foursomes scored", len(team["teams"]) == 2, str(len(team["teams"])))
check("teams are ranked", team["teams"][0]["place"] == 1)

mvp = board["games"]["mvp"]
check("MVP is decided on a complete field", mvp["status"] == "determined",
      mvp["status"])
# The MVP is decided on POINTS, not the low net score — which is exactly
# why it needs its own test. Adam Baker plays bogey golf off a 14: that is
# 2 pops on five holes and 1 on four, so his card reads five net birdies
# (2 pts) + four net pars (1 pt) = 14. Kerry shoots even par off a 4 for
# four net birdies + five pars = 13. The higher handicap wins the MVP with
# the worse gross score, and the engine must not "correct" that.
check("MVP is the top net-Stableford NET buyer, not the low gross",
      mvp["winners"][0]["name"] == "Adam Baker"
      and mvp["winners"][0]["points"] == 14, str(mvp["winners"]))
check("the MVP field is ranked by points",
      [f["name"] for f in mvp["field"][:2]] == ["Adam Baker", "Kerry Niester"],
      str([(f["name"], f["points"]) for f in mvp["field"]]))
check("a non-NET-buyer cannot be MVP",
      all(f["name"] not in ("Chris Best", "Texas Terry", "Guest Player")
          for f in mvp["field"]), str([f["name"] for f in mvp["field"]]))

ctp = board["games"]["ctp"]
check("both par-3s carry a CTP", len(ctp["slots"]) == 2)
check("CTP winners start empty", all(s["winner"] is None for s in ctp["slots"]))

pid = sdata["players"][0]["id"]
db.ls_record_contest(ssid, "ctp", 2, pid, note="6 ft", db_path=DB)
ctp2 = db.ls_leaderboard(ssid, db_path=DB)["games"]["ctp"]
check("a recorded CTP winner shows on the slot",
      next(s for s in ctp2["slots"] if s["hole"] == 2)["winner"] is not None)
db.ls_record_contest(ssid, "ctp", 2, None, db_path=DB)
check("a CTP slot can be cleared",
      next(s for s in db.ls_leaderboard(ssid, db_path=DB)["games"]["ctp"]["slots"]
           if s["hole"] == 2)["winner"] is None)
check("an unknown contest kind is rejected",
      "error" in db.ls_record_contest(ssid, "nearest_the_tree", 2, pid,
                                      db_path=DB))

# ---------------------------------------------------------------------------
print("\n== PARITY: our engine vs Golf Genius (the Stage-1 gate) ==")

syn_parity = db.ls_parity(sid, db_path=DB)
check("parity refuses a synthetic session", "error" in syn_parity)

par_res = db.ls_parity(ssid, db_path=DB)
check("every seeded player has a GG row to diff against",
      par_res["source_rounds"] == 8 and par_res["players_without_gg"] == 0,
      str(par_res.get("source_rounds")))
check("parity actually checked something", par_res["checked"] > 0)
check("PARITY: engine reproduces GG exactly on every player",
      par_res["parity"] is True,
      "mismatches: " + str([r for r in par_res["rows"]
                            if r["status"] == "mismatch"]))
check("all eight players clean", par_res["players_clean"] == 8,
      f"got {par_res['players_clean']}")

# Break one stored score and confirm the harness catches it — a parity
# report that cannot fail is worthless.
conn = sqlite3.connect(DB)
victim = conn.execute(
    "SELECT id, player_id FROM ls_test_holes WHERE session_id = ? AND"
    " hole_number = 1 LIMIT 1", (ssid,)).fetchone()
conn.execute("UPDATE ls_test_holes SET strokes = strokes + 3 WHERE id = ?",
             (victim[0],))
conn.commit()
conn.close()
broken = db.ls_parity(ssid, db_path=DB)
check("a corrupted score BREAKS parity", broken["parity"] is False)
check("exactly the corrupted player is flagged",
      broken["players_mismatched"] == 1, str(broken["players_mismatched"]))
flagged = next(r for r in broken["rows"] if r["status"] == "mismatch")
check("the diff names the fields that moved",
      {d["field"] for d in flagged["deltas"]} >= {"gross", "net"},
      str(flagged["deltas"]))

# ---------------------------------------------------------------------------
print("\n== deletion ==")

db.ls_delete_player(sdata["players"][0]["id"], db_path=DB)
check("deleting a player drops their scores",
      len(db.ls_get_session(ssid, db_path=DB)["players"]) == 7)
db.ls_delete_session(ssid, db_path=DB)
check("deleting a session removes it", db.ls_get_session(ssid, db_path=DB) is None)
conn = sqlite3.connect(DB)
check("deleting a session leaves no orphan holes",
      conn.execute("SELECT COUNT(*) FROM ls_test_holes WHERE session_id = ?",
                   (ssid,)).fetchone()[0] == 0)
check("production scoring rows survive session deletion",
      conn.execute("SELECT COUNT(*) FROM scoring_rounds").fetchone()[0] == 8)
conn.close()

# ---------------------------------------------------------------------------
print("\n== course coverage: the silently-half-scored board ==")

# The Quarry case, exactly: TGF has only ever played its BACK nine, so an
# 18-hole round there has par/stroke-index on 10-18 and NOTHING on 1-9.
# A hole with no par derives nothing and scores zero in every game while
# looking perfectly normal — the most dangerous failure this surface has.
conn = sqlite3.connect(DB)
conn.executescript("""
    INSERT INTO courses (course_id, name) VALUES (2, 'The Quarry Golf Club');
    INSERT INTO course_tees (tee_id, course_id, tee_name, slope, rating)
        VALUES (9, 2, '1 - Gold Tee', 128, 35.6);
""")
for h, par, yd, si in [(10, 4, 437, 4), (11, 4, 351, 18), (12, 3, 164, 14),
                       (13, 4, 331, 10), (14, 4, 410, 2), (15, 5, 495, 16),
                       (16, 3, 201, 12), (17, 4, 357, 6), (18, 5, 509, 8)]:
    conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par,"
                 " yardage, stroke_index) VALUES (9, ?, ?, ?, ?)", (h, par, yd, si))
conn.commit()
conn.close()

q = db.ls_create_session("Quarry back only", holes=18, tee_id=9, db_path=DB)
qsid = q["session_id"]
qp = db.ls_add_player(qsid, "Front Niner", playing_handicap=9, db_path=DB)
qhole = db.ls_get_session(qsid, db_path=DB)["holes"]
check("a back-nine-only tee seeds only the holes it knows",
      len(qhole) == 9 and min(h["hole_number"] for h in qhole) == 10,
      f"got {[h['hole_number'] for h in qhole]}")

# Now simulate the real event shape: the session covers 1-18 but the front
# nine has no par, and players post scores there.
for h in range(1, 10):
    db.ls_set_course_hole(qsid, h, db_path=DB)  # creates the row, par stays NULL
for h in range(1, 19):
    db.ls_set_score(qsid, qp["player_id"], h, 5, db_path=DB)

qb = db.ls_leaderboard(qsid, db_path=DB)
cov = qb["course_coverage"]
check("missing par is detected", cov["missing_par"] == list(range(1, 10)),
      str(cov["missing_par"]))
check("missing stroke index is detected separately",
      cov["missing_stroke_index"] == list(range(1, 10)))
check("holes with SCORES but no par are called out as urgent",
      cov["scored_but_no_par"] == list(range(1, 10)))
check("coverage is not ok", cov["ok"] is False)
check("the warning says the board is short, not just incomplete",
      any("silently short" in w for w in cov["warnings"]), str(cov["warnings"]))
check("and it warns NET games are wrong without a stroke index",
      any("every NET game" in w for w in cov["warnings"]))
# Prove the damage is real: 18 scores posted, only the back nine counted.
card = qb["cards"][0]
check("a par-less hole really does contribute nothing",
      card["thru"] == 18 and card["gross"] == 90
      and sum(1 for x in card["holes"] if x["stableford_net"] is not None) == 9,
      f"thru={card['thru']} gross={card['gross']}")

# Filling par clears the alarm.
for h, par in zip(range(1, 10), [4, 3, 5, 4, 4, 3, 4, 4, 5]):
    db.ls_set_course_hole(qsid, h, par=par, stroke_index=2 * h - 1, db_path=DB)
cov2 = db.ls_leaderboard(qsid, db_path=DB)["course_coverage"]
check("filling par and stroke index clears the alarm",
      cov2["ok"] is True and not cov2["warnings"], str(cov2["warnings"]))
check("and the full round now scores",
      sum(1 for x in db.ls_leaderboard(qsid, db_path=DB)["cards"][0]["holes"]
          if x["stableford_net"] is not None) == 18)

# ---------------------------------------------------------------------------
print("\n== per-nine tee ratings merge into one 18-hole course ==")

# The REAL Quarry shape. TGF plays nines and GG rates each nine separately,
# so one physical tee is several course_tees rows each holding only its own
# nine. "1 - Gold Tee" is the front (slope 117 / rating 34.2, holes 1-9 with
# the ODD stroke indexes) and the back (128 / 35.6, holes 10-18 with the
# EVENS). Reading one tee_id returns half a golf course.
conn = sqlite3.connect(DB)
conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope,"
             " rating) VALUES (20, 2, '1 - Gold Tee', 117, 34.2)")   # front nine
conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope,"
             " rating) VALUES (21, 2, '1 - Gold Tee', 128, 35.6)")   # back nine
conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope,"
             " rating) VALUES (22, 2, '2 - Blue Tee', 115, 34.2)")   # other tee
for h, par, yd, si in [(1, 4, 361, 9), (2, 4, 423, 3), (3, 3, 136, 15),
                       (4, 4, 292, 17), (5, 5, 514, 1), (6, 4, 324, 11),
                       (7, 4, 374, 7), (8, 3, 142, 13), (9, 4, 307, 5)]:
    conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par,"
                 " yardage, stroke_index) VALUES (20, ?, ?, ?, ?)", (h, par, yd, si))
for h, par, yd, si in [(10, 4, 437, 4), (11, 4, 351, 18), (12, 3, 164, 14),
                       (13, 4, 331, 10), (14, 4, 410, 2), (15, 5, 495, 16),
                       (16, 3, 201, 12), (17, 4, 357, 6), (18, 5, 509, 8)]:
    conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par,"
                 " yardage, stroke_index) VALUES (21, ?, ?, ?, ?)", (h, par, yd, si))
# A different tee name must NOT leak in.
conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage,"
             " stroke_index) VALUES (22, 1, 9, 99, 99)")
conn.commit()
conn.close()

# Seeding off EITHER nine's tee row must yield all 18 holes.
for tee, label in ((21, "back-nine row"), (20, "front-nine row")):
    s = db.ls_create_session(f"Quarry via {label}", holes=18, tee_id=tee, db_path=DB)
    hs = db.ls_get_session(s["session_id"], db_path=DB)["holes"]
    check(f"seeding off the {label} still gets all 18 holes",
          [h["hole_number"] for h in hs] == list(range(1, 19)),
          f"got {[h['hole_number'] for h in hs]}")
    check(f"...with par on every hole ({label})",
          all(h["par"] is not None for h in hs))
    check(f"...and a complete 1-18 stroke index ({label})",
          sorted(h["stroke_index"] for h in hs) == list(range(1, 19)),
          str(sorted(h["stroke_index"] for h in hs)))
    check(f"...par totals 71 ({label})",
          sum(h["par"] for h in hs) == 71, str(sum(h["par"] for h in hs)))
    check(f"...and no other tee's data leaked in ({label})",
          next(h for h in hs if h["hole_number"] == 1)["par"] == 4,
          str(next(h for h in hs if h["hole_number"] == 1)))
    lb = db.ls_leaderboard(s["session_id"], db_path=DB)
    check(f"...coverage reports clean ({label})",
          lb["course_coverage"]["ok"] is True,
          str(lb["course_coverage"]["warnings"]))

# The front nine carries the ODD stroke indexes and the back the EVENS — the
# merged set is what makes an 18-hole handicap allocation correct.
s18 = db.ls_create_session("Quarry SI check", holes=18, tee_id=21, db_path=DB)
hs = db.ls_get_session(s18["session_id"], db_path=DB)["holes"]
front_si = sorted(h["stroke_index"] for h in hs if h["hole_number"] <= 9)
back_si = sorted(h["stroke_index"] for h in hs if h["hole_number"] > 9)
check("front nine holds the odd stroke indexes",
      front_si == [1, 3, 5, 7, 9, 11, 13, 15, 17], str(front_si))
check("back nine holds the even stroke indexes",
      back_si == [2, 4, 6, 8, 10, 12, 14, 16, 18], str(back_si))

# An 18 handicap over 18 holes = one stroke per hole; a 9 = the nine hardest,
# which must straddle both nines rather than landing all on one side.
p18 = db.ls_add_player(s18["session_id"], "Eighteen", playing_handicap=18, db_path=DB)
p9 = db.ls_add_player(s18["session_id"], "Niner", playing_handicap=9, db_path=DB)
for h in range(1, 19):
    db.ls_set_score(s18["session_id"], p18["player_id"], h, 5, db_path=DB)
    db.ls_set_score(s18["session_id"], p9["player_id"], h, 5, db_path=DB)
cards = {c["name"]: c for c in db.ls_leaderboard(s18["session_id"], db_path=DB)["cards"]}
check("an 18 handicap gets one stroke on all 18 holes",
      all(x["strokes_received"] == 1 for x in cards["Eighteen"]["holes"]))
nine_dots = {x["hole"] for x in cards["Niner"]["holes"] if x["strokes_received"]}
check("a 9 handicap's strokes land on stroke index 1-9, straddling both nines",
      len(nine_dots) == 9 and any(h <= 9 for h in nine_dots)
      and any(h > 9 for h in nine_dots), str(sorted(nine_dots)))

# ---------------------------------------------------------------------------
print("\n== live refresh from GG (in place) ==")

seed2 = db.ls_seed_session_from_event("s9.21 Test Center Open", db_path=DB)
rsid = seed2["session_id"]
check("a CHAMPIONSHIP event does not auto-flag a normal event",
      seed2["championship"] is False)

# Manager work that a mid-round refresh must not destroy.
rdata = db.ls_get_session(rsid, db_path=DB)
victim = rdata["players"][0]
db.ls_update_player(victim["id"], {"team_num": 9, "flight": "X",
                                   "buys_net": False, "is_member": False},
                    db_path=DB)
db.ls_update_session(rsid, {"championship": True}, db_path=DB)
db.ls_record_contest(rsid, "ctp", 2, victim["id"], note="8 ft", db_path=DB)

# Simulate the round progressing: GG posts two more strokes for someone.
conn = sqlite3.connect(DB)
conn.execute("UPDATE scoring_holes SET strokes = strokes + 1 WHERE"
             " scoring_round_id = 1 AND hole_number = 1")
conn.execute("UPDATE scoring_rounds SET gross = gross + 1, net = net + 1"
             " WHERE id = 1")
conn.commit()
conn.close()

ref = db.ls_refresh_session_from_gg(rsid, db_path=DB)
check("refresh re-syncs every GG card", ref["gg_cards"] == 8, str(ref))
check("refresh updates in place rather than duplicating",
      ref["players_updated"] == 8 and ref["players_added"] == 0, str(ref))
check("refresh rewrites hole scores", ref["hole_scores"] == 72,
      str(ref["hole_scores"]))

after = db.ls_get_session(rsid, db_path=DB)
check("no duplicate players after refresh", len(after["players"]) == 8)
kept = next(p for p in after["players"] if p["id"] == victim["id"])
check("manager team assignment SURVIVES a refresh", kept["team_num"] == 9)
check("manager flight override SURVIVES a refresh", kept["flight"] == "X")
check("manager buyer flag SURVIVES a refresh", kept["buys_net"] == 0)
check("manager member flag SURVIVES a refresh", kept["is_member"] == 0)
check("championship toggle SURVIVES a refresh",
      after["session"]["championship"] == 1)
check("recorded CTP SURVIVES a refresh",
      any(c["kind"] == "ctp" and c["hole_number"] == 2
          for c in after["contests"]))
check("the new GG score came through",
      db.ls_build_state(rsid, db_path=DB)["players"][0]["scores"] is not None)
moved = [p for p in after["players"] if p["source_round_id"] == 1][0]
check("the changed card reflects GG's new stroke",
      after and moved["scores"][1]["strokes"] is not None)

# A brand-new GG card mid-round must be picked up, not ignored.
conn = sqlite3.connect(DB)
conn.execute("INSERT INTO customers (customer_id, first_name, last_name)"
             " VALUES (99, 'Late', 'Entry')")
conn.execute("INSERT INTO scoring_rounds (id, customer_id, player_name, event_id,"
             " gg_aggregate_id, round_date, course_id, tee_id, holes_played,"
             " playing_handicap, gross, net, source) VALUES"
             " (99, 99, 'Late Entry', 1, 'agg99', '2026-07-25', 1, 1, 3, 10, 20, 10, 'gg')")
for h in (1, 2, 3):
    conn.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number,"
                 " strokes, strokes_received) VALUES (99, ?, 5, 1)", (h,))
conn.commit()
conn.close()
ref2 = db.ls_refresh_session_from_gg(rsid, db_path=DB)
check("a card that appears mid-round is added", ref2["players_added"] == 1,
      str(ref2))
check("the late card's scores land",
      any(p["player_name"] == "Late Entry" and len(p["scores"]) == 3
          for p in db.ls_get_session(rsid, db_path=DB)["players"]))

# A player who vanishes from GG (re-keyed aggregate) must NOT be dropped.
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM scoring_holes WHERE scoring_round_id = 99")
conn.execute("DELETE FROM scoring_rounds WHERE id = 99")
conn.commit()
conn.close()
db.ls_refresh_session_from_gg(rsid, db_path=DB)
check("a player who disappears from GG is KEPT, not silently dropped",
      any(p["player_name"] == "Late Entry"
          for p in db.ls_get_session(rsid, db_path=DB)["players"]))

check("refresh refuses a synthetic session",
      "error" in db.ls_refresh_session_from_gg(qsid, db_path=DB))

# ---------------------------------------------------------------------------
print("\n== championship auto-detect ==")

conn = sqlite3.connect(DB)
conn.execute("INSERT INTO events (id, item_name, event_date, format, course)"
             " VALUES (7, 'TGF SAN ANTONIO CHAMPIONSHIP', '2026-08-01',"
             " '18 Hole', 'The Quarry')")
conn.execute("INSERT INTO scoring_rounds (id, customer_id, player_name, event_id,"
             " gg_aggregate_id, round_date, course_id, tee_id, holes_played,"
             " playing_handicap, gross, net, source) VALUES"
             " (70, 1, 'Kerry Niester', 7, 'agg70', '2026-08-01', 1, 1, 9, 4, 40, 36, 'gg')")
for h in range(1, 10):
    conn.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number,"
                 " strokes, strokes_received) VALUES (70, ?, ?, 0)",
                 (h, PAR[h]))
conn.commit()
conn.close()
champ = db.ls_seed_session_from_event("TGF SAN ANTONIO CHAMPIONSHIP", db_path=DB)
check("a CHAMPIONSHIP event auto-selects the championship schedule",
      champ["championship"] is True, str(champ))
cb = db.ls_leaderboard(champ["session_id"], db_path=DB)
check("and the board actually uses it",
      cb["formulas_used"] == "championship", cb["formulas_used"])
check("championship net points are +1 per category (9 pars = 18, not 9)",
      cb["cards"][0]["stableford_net"] == 18,
      str(cb["cards"][0]["stableford_net"]))

# ---------------------------------------------------------------------------
print("\n== seeding an UPCOMING event from registrations ==")

# The pre-flight case, which was impossible before: an event with a full
# field of registrations but no scorecards, days before it is played. The
# old code errored with "no imported scorecards", so the only events you
# could shadow were ones already finished.
conn = sqlite3.connect(DB)
conn.execute("INSERT INTO events (id, item_name, event_date, format, course)"
             " VALUES (9, 'TGF UPCOMING CHAMPIONSHIP', '2026-08-01', '18 Hole',"
             " 'Olympia Hills')")
for i, (nm, sg, status) in enumerate([
        ("Alpha Player", "BOTH", "MEMBER"), ("Bravo Player", "NET", "MEMBER"),
        ("Charlie Player", "GROSS", "MEMBER"), ("Delta Player", "NONE", "MEMBER"),
        ("Echo Guest", "BOTH", "GUEST"), ("Foxtrot Player", "NET", "MEMBER")],
        start=200):
    _fn, _ln = nm.split(" ", 1)
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name)"
                 " VALUES (?, ?, ?)", (i, _fn, _ln))
    conn.execute("INSERT INTO items (id, customer_id, customer, item_name,"
                 " side_games, transaction_status, holes, user_status) VALUES"
                 " (?, ?, ?, 'TGF UPCOMING CHAMPIONSHIP', ?, 'active', '18', ?)",
                 (i, i, nm, sg, status))
# One credited registration must NOT be seeded.
conn.execute("INSERT INTO customers (customer_id, first_name, last_name)"
             " VALUES (299, 'Gone', 'Player')")
conn.execute("INSERT INTO items (id, customer_id, customer, item_name, side_games,"
             " transaction_status, holes, user_status) VALUES"
             " (299, 299, 'Gone Player', 'TGF UPCOMING CHAMPIONSHIP', 'BOTH',"
             " 'credited', '18', 'MEMBER')")
conn.commit(); conn.close()

up = db.ls_seed_session_from_event("TGF UPCOMING CHAMPIONSHIP", db_path=DB)
check("an upcoming event seeds instead of erroring",
      "error" not in up and up.get("source") == "registrations", str(up))
check("the whole active field is seeded", up["players_seeded"] == 6,
      str(up["players_seeded"]))
check("18 holes derived from the registrations", up["holes"] == 18)
check("championship auto-detected on an upcoming event",
      up["championship"] is True)

updata = db.ls_get_session(up["session_id"], db_path=DB)
names = {p["player_name"] for p in updata["players"]}
check("a credited registration is NOT seeded", "Gone Player" not in names,
      str(sorted(names)))
check("buyer flags come from what each player bought",
      {p["player_name"]: (p["buys_net"], p["buys_gross"]) for p in updata["players"]}
      == {"Alpha Player": (1, 1), "Bravo Player": (1, 0),
          "Charlie Player": (0, 1), "Delta Player": (0, 0),
          "Echo Guest": (1, 1), "Foxtrot Player": (1, 0)},
      str({p["player_name"]: (p["buys_net"], p["buys_gross"]) for p in updata["players"]}))
check("a GUEST is flagged not-a-member (cannot win HIO)",
      next(p for p in updata["players"] if p["player_name"] == "Echo Guest")["is_member"] == 0)
check("no scores yet", all(not p["scores"] for p in updata["players"]))
check("no playing handicaps yet — those arrive with Pull from GG",
      all(p["playing_handicap"] is None for p in updata["players"]))

lb = db.ls_leaderboard(up["session_id"], db_path=DB)
check("the board renders on a field with no scores", lb["players"] == 6)
check("...and MVP correctly says it is awaiting results",
      lb["games"]["mvp"]["status"] == "awaiting_results",
      lb["games"]["mvp"]["status"])
check("...and the session is refreshable from GG (it is seeded)",
      "error" not in db.ls_refresh_session_from_gg(up["session_id"], db_path=DB))


print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL TEST-CENTER INTEGRATION TESTS PASSED")
