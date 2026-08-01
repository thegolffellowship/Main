"""Tests for the LIVE championship points overlay (Kerry 2026-07-31).

"The Championship is in addition to the regular season total, so everything
earned tomorrow adds on like we have setup in the top 10 totals +
championship value."

Boards: SA "sChampionship POINTS Net" (v2tournaments/4779202), Austin
"aChamp POINTS" (v2tournaments/4779168).

Run: python3 test_champ_points_live.py
"""
import os, sys
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

F = []
def check(l, c, d=""):
    print(("  PASS  " if c else "  FAIL  ") + l + ("" if c else "  " + d))
    if not c: F.append(l)

print("\n== the GG board parses ==")
# Verbatim shape of the live SA board via parse_page_structure.
tables = [[
    ["Pos.", "Player", "Stableford Points", "Thru"],
    ["", "FIEBER, Wade TGF San Antonio", "-", "9:00 AM"],
    [""],
    ["", "Bricco, Rowdy Guest", "-", "9:10 AM"],
    [""],
    ["1", "MORENO, Robert TGF San Antonio", "34", "F"],
    [""],
    ["2", "MURPHY, Mike TGF San Antonio", "28", "12"],
]]
rows = db._parse_champ_points_tables(tables)
check("every player row is read, spacer rows ignored", len(rows) == 4, str(len(rows)))
check("a player who has not started reads None, NOT zero",
      rows[0]["points"] is None, str(rows[0]))
check("that distinction matters: None != 0.0", rows[0]["points"] != 0.0)
check("a scoring player's points are numeric", rows[2]["points"] == 34.0, str(rows[2]))
check("thru is carried for the live display", rows[3]["thru"] == "12", str(rows[3]))

print("\n== FIRST LAST guests are kept (seen live, Austin board 2026-08-01) ==")
tables_g = [[
    ["Pos.", "Player", "Stableford Points", "Thru"],
    ["", "Matt Larson Guest", "-", "9:00 AM"],
    [""],
    ["", "MCDONNELL, Kaleb TGF Austin", "-", "9:00 AM"],
    ["", "Total", "44", ""],
]]
rows_g = db._parse_champ_points_tables(tables_g)
check("the comma-less guest row is read, the junk 'Total' row is not",
      len(rows_g) == 2, str(rows_g))
check("the guest's name survives the affiliation strip",
      rows_g[0]["name"] == "Matt Larson", str(rows_g[0]))

print("\n== the LIVE scoring format parses (seen 2026-08-01, pre-round test) ==")
# GG renders a scoring player's points as "3 (3/0)" — total (front/back).
# The original float() on the whole cell read every scoring player as
# not-started, so the overlay was silently inert on championship morning.
tables_live = [[
    ["Pos.", "Player", "Stableford Points", "Thru"],
    ["1", "WADE, Mary TGF San Antonio", "3 (3/0)", "1"],
    [""],
    ["T2", "MAZANEC, Luke TGF San Antonio", "22 (13/9)", "14"],
    [""],
    ["", "FIEBER, Wade TGF San Antonio", "-", "9:00 AM"],
]]
rows_l = db._parse_champ_points_tables(tables_live)
check("'3 (3/0)' parses to 3.0, not None", rows_l[0]["points"] == 3.0, str(rows_l[0]))
check("'22 (13/9)' parses to 22.0", rows_l[1]["points"] == 22.0, str(rows_l[1]))
check("a bare '-' still reads None — not-started rule untouched",
      rows_l[2]["points"] is None, str(rows_l[2]))
check("the overlay would now count 2 scoring",
      sum(1 for r in rows_l if r["points"] is not None) == 2)

print("\n== affiliations are stripped before identity resolution ==")
for raw, want in [("FIEBER, Wade TGF San Antonio", "FIEBER, Wade"),
                  ("Bricco, Rowdy Guest", "Bricco, Rowdy"),
                  ("McCRARY, Justin TGF Austin", "McCRARY, Justin"),
                  ("Williams, Jacob", "Williams, Jacob")]:
    check(f"{raw!r} -> {want!r}", db._strip_gg_affiliation(raw) == want,
          db._strip_gg_affiliation(raw))
check("an unknown affiliation still yields 'SURNAME, First'",
      db._strip_gg_affiliation("SMITH, John TGF Nowhere") == "SMITH, John",
      db._strip_gg_affiliation("SMITH, John TGF Nowhere"))

print("\n== the addition rule ==")
# Merge exactly as get_points_race_live does, without touching the network.
def merge(standings, live_players):
    import re as _re
    by_cid, by_name = {}, {}
    for p in live_players:                    # ALL board players — the
        if p.get("customer_id"):              # not-started carry tee times
            by_cid[p["customer_id"]] = p
        for cand in db._gg_name_candidates(p["name"]):
            by_name.setdefault(cand.strip().lower(), p)
    out = []
    for r in standings:
        row = dict(r)
        season = float(row.get("total_points") or 0)
        hit = by_cid.get(row.get("customer_id")) or \
            by_name.get((row.get("player_name") or "").strip().lower())
        champ = (float(hit["points"])
                 if hit and hit.get("points") is not None else None)
        row.update(season_points=round(season, 2),
                   season_rank=row.get("rank"),
                   champ_points=champ,
                   champ_thru=hit.get("thru") if hit else None,
                   live_total=round(season + (champ or 0.0), 2))
        out.append(row)
    out.sort(key=lambda r: (-r["live_total"], -(r["season_points"] or 0),
                            (r.get("player_name") or "").lower()))
    for i, r in enumerate(out, 1):
        r["total_points"] = r["live_total"]
    i = 0
    while i < len(out):
        j = i + 1
        while j < len(out) and out[j]["live_total"] == out[i]["live_total"]:
            j += 1
        label = ("T" if j - i > 1 else "") + str(i + 1)
        for g in range(i, j):
            out[g]["rank"] = label
            try:
                _was = int(_re.sub(r"[^0-9]", "", str(out[g].get("season_rank") or "")))
                out[g]["move"] = _was - (i + 1) if _was else None
            except (TypeError, ValueError):
                out[g]["move"] = None
        i = j
    return out

standings = [
    {"player_name": "Roberto Moreno", "customer_id": 11, "total_points": 51, "rank": 1},
    {"player_name": "Wade Fieber",    "customer_id": 13, "total_points": 45, "rank": 2},
    {"player_name": "Michael Murphy", "customer_id": 12, "total_points": 29, "rank": 3},
]
live = [
    {"name": "MORENO, Robert", "points": 34.0, "thru": "F",  "customer_id": 11},
    {"name": "MURPHY, Mike",   "points": 28.0, "thru": "12", "customer_id": 12},
    {"name": "FIEBER, Wade",   "points": None, "thru": "9:00 AM", "customer_id": 13},
]
m = {r["player_name"]: r for r in merge(standings, live)}
check("championship points ADD to the season total (51 + 34 = 85)",
      m["Roberto Moreno"]["live_total"] == 85.0, str(m["Roberto Moreno"]))
check("a player who has not teed off keeps his season total unchanged",
      m["Wade Fieber"]["live_total"] == 45.0, str(m["Wade Fieber"]))
check("...and shows no championship points rather than a zero",
      m["Wade Fieber"]["champ_points"] is None, str(m["Wade Fieber"]["champ_points"]))
check("the season figure stays visible beside the combined one",
      m["Roberto Moreno"]["season_points"] == 51.0, str(m["Roberto Moreno"]))

print("\n== the board re-ranks LIVE, which is the whole point ==")
# Murphy starts 3rd on season points and overtakes Fieber mid-round.
_rk = lambda r: int(str(r["rank"]).lstrip("T"))
check("Murphy climbs past Fieber on the day's points (29+28=57 vs 45)",
      _rk(m["Michael Murphy"]) < _rk(m["Wade Fieber"]),
      f'Murphy #{m["Michael Murphy"]["rank"]} vs Fieber #{m["Wade Fieber"]["rank"]}')
check("Moreno holds the lead", m["Roberto Moreno"]["rank"] == "1")
check("the table's own fields carry the combined figure",
      m["Michael Murphy"]["total_points"] == 57.0, str(m["Michael Murphy"]))

print("\n== PGA-style day columns (Kerry 2026-08-01) ==")
check("day movement: Murphy is UP 1 from his start-of-day rank (3 -> 2)",
      m["Michael Murphy"]["move"] == 1, str(m["Michael Murphy"].get("move")))
check("day movement: Fieber is DOWN 1 (2 -> 3)",
      m["Wade Fieber"]["move"] == -1, str(m["Wade Fieber"].get("move")))
check("no movement shows none, not zero-with-arrow",
      not m["Roberto Moreno"]["move"], str(m["Roberto Moreno"].get("move")))
check("a NOT-STARTED player still carries his TEE TIME in champ_thru",
      m["Wade Fieber"]["champ_thru"] == "9:00 AM", str(m["Wade Fieber"].get("champ_thru")))
check("...while his champ points stay None",
      m["Wade Fieber"]["champ_points"] is None)
check("a scoring player's thru is the hole count",
      m["Michael Murphy"]["champ_thru"] == "12", str(m["Michael Murphy"].get("champ_thru")))
check("start-of-day rank is preserved beside the live one",
      m["Wade Fieber"]["season_rank"] == 2, str(m["Wade Fieber"].get("season_rank")))

print("\n== ties label as ties (Kerry, live board 2026-08-01: 94/94/94 read 2,3,4) ==")
mt = {r["player_name"]: r for r in merge(
    [{"player_name": "A Lead",  "customer_id": 1, "total_points": 99, "rank": 1},
     {"player_name": "B South", "customer_id": 2, "total_points": 94, "rank": 2},
     {"player_name": "C Mazanec", "customer_id": 3, "total_points": 92, "rank": 3},
     {"player_name": "D Wade",  "customer_id": 4, "total_points": 91, "rank": 4},
     {"player_name": "E Next",  "customer_id": 5, "total_points": 90, "rank": 5}],
    [{"name": "MAZANEC, C", "points": 2.0, "thru": "1", "customer_id": 3},
     {"name": "WADE, D",    "points": 3.0, "thru": "1", "customer_id": 4}])}
check("three players on 94 all read T2",
      mt["B South"]["rank"] == "T2" and mt["C Mazanec"]["rank"] == "T2"
      and mt["D Wade"]["rank"] == "T2",
      f'{mt["B South"]["rank"]}/{mt["C Mazanec"]["rank"]}/{mt["D Wade"]["rank"]}')
check("the man behind the tie is 5th, not 4th",
      mt["E Next"]["rank"] == "5", str(mt["E Next"]["rank"]))
check("the leader stays a plain 1", mt["A Lead"]["rank"] == "1", str(mt["A Lead"]["rank"]))
check("MOVEMENT compares competition ranks: 4th into a T2 is UP 2 (the Mary case)",
      mt["D Wade"]["move"] == 2, str(mt["D Wade"].get("move")))
check("3rd into the same T2 is UP 1",
      mt["C Mazanec"]["move"] == 1, str(mt["C Mazanec"].get("move")))
check("2nd into a T2 is NO move — the label caught up, the rank didn't change",
      not mt["B South"]["move"], str(mt["B South"].get("move")))

print("\n== identity: GG's spelling must not lose a player ==")
# The exact pair that went missing before: GG says Robert/Mike, we say
# Roberto/Michael. Matched here by customer_id, not by name.
check("Moreno matched despite GG spelling him 'Robert'",
      m["Roberto Moreno"]["champ_points"] == 34.0)
check("Murphy matched despite GG spelling him 'Mike'",
      m["Michael Murphy"]["champ_points"] == 28.0)
# With NO customer_id, the name fallback must still catch the easy case.
m2 = {r["player_name"]: r for r in merge(
    [{"player_name": "Wade Fieber", "customer_id": None, "total_points": 45}],
    [{"name": "FIEBER, Wade", "points": 30.0, "thru": "F", "customer_id": None}])}
check("an unlinked player still matches on the name fallback",
      m2["Wade Fieber"]["live_total"] == 75.0, str(m2["Wade Fieber"]))

print("\n== plus handicaps read off the scorecard board (Kerry 2026-08-01) ==")
# Kerry, mid-round: "I have 3 SA players that have plus handicaps. Horton
# Griffin Youngs. I need there playing handicaps deducted from there total
# points in the points race." The plus values come off the companion
# scorecard board's PlayingHandicap™ column — verbatim live shape below —
# so nobody's name lives in code.
tables_ph = [[
    ["Pos.", "Player", "PlayingHandicap™", "TotalGross",
     "To ParNet", "Thru", "TotalNet"],
    ["T2", "YOUNGS, Pat TGF San Antonio", "+4", "-", "-1", "7", "- (-/-)"],
    [""],
    ["T12", "HORTON, Jay TGF San Antonio", "+4", "-", "+3", "7", "- (-/-)"],
    ["T22", "GRIFFIN, Matt TGF San Antonio", "+3", "-", "+4", "7", "- (-/-)"],
    ["1", "MORENO, Robert TGF San Antonio", "4", "-", "-3", "6", "- (-/-)"],
    ["T5", "RIDEOUT, Jeff TGF San Antonio", "22", "-", "+1", "7", "- (-/-)"],
]]
plus = db._parse_champ_plus_column(tables_ph)
check("exactly the three plus handicaps are found",
      plus == {"YOUNGS, Pat": 4.0, "HORTON, Jay": 4.0, "GRIFFIN, Matt": 3.0},
      str(plus))
check("an ordinary handicap ('4') deducts nothing", "MORENO, Robert" not in plus)
check("a big ordinary handicap ('22') is not misread", "RIDEOUT, Jeff" not in plus)
check("no header row -> nothing parsed (points boards carry no handicap col)",
      db._parse_champ_plus_column([[["Pos.", "Player", "Stableford Points",
                                     "Thru"],
                                    ["1", "YOUNGS, Pat TGF San Antonio",
                                     "+4", "7"]]]) == {})

print("\n== the reset projection follows the LIVE order (Kerry 2026-08-01) ==")
# "I'm currently 3rd for SA City Net, but I'm projecting at 97.5 and I
# should be 99 with 3rd" — the season pass laddered off the season order
# and the live merge carried those values through unchanged.
def _rows(*specs):
    # (name, live_total, eligible) in LIVE order; stale reset marks eligibility
    return [{"player_name": n, "live_total": t,
             "points_reset": (0.0 if e else None)} for n, t, e in specs]

rows_r = _rows(("A", 107.0, True), ("B", 102.0, True), ("Kerry", 100.0, True),
               ("D", 99.0, True), ("E", 97.0, True), ("F", 95.0, True))
db._reproject_points_reset(rows_r, {"anchor_count": 56, "eligible_count": 56})
check("live 3rd projects the 3rd-place reset (99, not the season-rank value)",
      rows_r[2]["points_reset"] == 99.0, str(rows_r[2]))
check("live 1st projects 100", rows_r[0]["points_reset"] == 100.0)
check("live 6th projects 97.5 — the value Kerry was wrongly shown for 3rd",
      rows_r[5]["points_reset"] == 97.5, str(rows_r[5]))

rows_t = _rows(("A", 100.0, True), ("B", 94.0, True), ("C", 94.0, True),
               ("D", 90.0, True))
db._reproject_points_reset(rows_t, {"anchor_count": 10, "eligible_count": 10})
check("a live tie shares the ladder position",
      rows_t[1]["points_reset"] == rows_t[2]["points_reset"] == 99.5,
      f'{rows_t[1]["points_reset"]}/{rows_t[2]["points_reset"]}')
check("the row after a tie takes its enumerated slot (4th -> 98.5)",
      rows_t[3]["points_reset"] == 98.5, str(rows_t[3]))

rows_i = _rows(("A", 100.0, True), ("Guest", 99.0, False), ("B", 98.0, True))
db._reproject_points_reset(rows_i, {"anchor_count": 5, "eligible_count": 5})
check("an ineligible row consumes no ladder slot and stays None",
      rows_i[1]["points_reset"] is None and rows_i[2]["points_reset"] == 99.5,
      str(rows_i))

rows_c = _rows(("A", 100.0, True), ("B", 98.0, True))
db._reproject_points_reset(rows_c, {"anchor_count": 12, "eligible_count": 8})
check("the prorated coefficient maps to the shared master ladder "
      "(coef 1.5: 2nd -> master 3 -> 99)",
      rows_c[1]["points_reset"] == 99.0, str(rows_c[1]))
rows_n = _rows(("A", 100.0, True))
before = rows_n[0]["points_reset"]
db._reproject_points_reset(rows_n, None)
check("no reset_info -> a no-op, never a crash",
      rows_n[0]["points_reset"] == before)

print("\n== movement history FREEZES during a live round ==")
import tempfile as _tf
fd2, _bp2 = _tf.mkstemp(suffix=".db"); os.close(fd2); db.init_db(_bp2)
A = [{"customer_id": 1, "player_name": "A", "rank": "1"},
     {"customer_id": 2, "player_name": "B", "rank": "2"}]
db._apply_rank_movement_history(A, "t_list", db_path=_bp2)   # seeds snapshot
B = [{"customer_id": 2, "player_name": "B", "rank": "1"},
     {"customer_id": 1, "player_name": "A", "rank": "2"}]
db._apply_rank_movement_history(B, "t_list", db_path=_bp2, freeze=True)
check("frozen: movement reads vs the last stored (pre-live) order",
      B[0]["prev_rank"] == "2" and B[1]["prev_rank"] == "1", str(B))
with db._connect(_bp2) as _c:
    n_snaps = _c.execute("SELECT COUNT(*) FROM rank_history_snapshots "
                         "WHERE list_key='t_list'").fetchone()[0]
check("frozen: NO new snapshot recorded — intra-round churn can't burn "
      "the history", n_snaps == 1, str(n_snaps))
db._apply_rank_movement_history(B, "t_list", db_path=_bp2)   # thaw -> rotates
with db._connect(_bp2) as _c:
    n_snaps = _c.execute("SELECT COUNT(*) FROM rank_history_snapshots "
                         "WHERE list_key='t_list'").fetchone()[0]
check("thawed: the normal rotation still records", n_snaps == 2, str(n_snaps))
os.unlink(_bp2)

print("\n== the double-count guard is CONTENT-based (Kerry: 'SA is not "
      "persisting now the round is over') ==")
# The old guard stood down on any same-day snapshot the moment the board
# read final — the morning's PRE-ROUND snapshot is also "fetched today",
# so the championship vanished from the standings hours before close-out.
import tempfile as _tf2
fd3, _bp3 = _tf2.mkstemp(suffix=".db"); os.close(fd3); db.init_db(_bp3)
_live_f = {"players": [
    {"name": "A", "customer_id": 1, "points": 20.0, "thru": "F"},
    {"name": "B", "customer_id": 2, "points": 15.0, "thru": "F"},
    {"name": "C", "customer_id": 3, "points": 12.0, "thru": "F"}]}
_base_pre = {"standings": [
    {"customer_id": 1, "total_points": 98.0},
    {"customer_id": 2, "total_points": 94.0},
    {"customer_id": 3, "total_points": 88.0}]}
check("first final read captures the baseline and KEEPS the overlay up",
      db._champ_absorbed_check("t_race", _base_pre, _live_f,
                               db_path=_bp3) is False)
check("a pre-close-out refresh (totals unchanged) keeps the overlay up",
      db._champ_absorbed_check("t_race", _base_pre, _live_f,
                               db_path=_bp3) is False)
_base_one = {"standings": [
    {"customer_id": 1, "total_points": 118.0},     # only one row moved
    {"customer_id": 2, "total_points": 94.0},
    {"customer_id": 3, "total_points": 88.0}]}
check("a single moved total is noise, not close-out (majority rule)",
      db._champ_absorbed_check("t_race", _base_one, _live_f,
                               db_path=_bp3) is False)
_base_post = {"standings": [
    {"customer_id": 1, "total_points": 118.0},
    {"customer_id": 2, "total_points": 109.0},
    {"customer_id": 3, "total_points": 100.0}]}
check("close-out (totals moved across the board) stands the overlay down",
      db._champ_absorbed_check("t_race", _base_post, _live_f,
                               db_path=_bp3) is True)
# a stale baseline from a PREVIOUS championship day must re-capture, not
# instantly absorb next year's final board
db.set_app_setting("gg_champ_absorb_baseline_t_race",
                   '{"date": "2025-08-02", "baseline": {"1": 1.0}}',
                   db_path=_bp3)
check("a prior-day baseline re-captures fresh instead of absorbing",
      db._champ_absorbed_check("t_race", _base_post, _live_f,
                               db_path=_bp3) is False)
check("no identified champ scorers -> never absorbed",
      db._champ_absorbed_check("t_race", _base_pre, {"players": []},
                               db_path=_bp3) is False)
# GG clears the Thru cells once the round completes (seen live ~4 PM
# 2026-08-01: points + BLANK thru, never "F") — the guard's final test
# must treat that as final or close-out could never stand the overlay
# down. Mirror of the _final expression in get_points_race_live.
def _mirror_final(players):
    return bool(players) and all(
        (str(p.get("thru") or "").strip().upper() in ("F", "18", "")
         or p.get("points") is None) for p in players)
check("a completed board with BLANK thru cells reads FINAL",
      _mirror_final([{"points": 39.0, "thru": ""},
                     {"points": 29.0, "thru": ""}]) is True)
check("a mid-round board (hole counts) does NOT read final",
      _mirror_final([{"points": 20.0, "thru": "13"},
                     {"points": 15.0, "thru": ""}]) is False)
os.unlink(_bp3)

print("\n== the board config is a dial, not code ==")
import tempfile
fd, _bp = tempfile.mkstemp(suffix=".db"); os.close(fd); db.init_db(_bp)
boards = db.champ_points_boards(db_path=_bp)
check("San Antonio board is configured", "san_antonio_net" in boards, str(list(boards)))
check("Austin board is configured", "austin_net" in boards, str(list(boards)))
check("SA points at the sChampionship POINTS Net tournament",
      "4779202" in boards["san_antonio_net"]["url"], boards["san_antonio_net"]["url"])
check("Austin points at the aChamp POINTS tournament",
      "4779168" in boards["austin_net"]["url"], boards["austin_net"]["url"])
check("an unconfigured race degrades quietly rather than erroring",
      db.fetch_champ_points("no_such_race", db_path=_bp).get("configured") is False)
check("a missing app_settings table falls back to the defaults, not a 500",
      "san_antonio_net" in db.champ_points_boards(db_path=":memory:"))
os.unlink(_bp)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILED"))
for f in F: print("  -", f)
sys.exit(1 if F else 0)
