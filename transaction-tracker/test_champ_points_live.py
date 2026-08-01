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
        try:
            _was = int(_re.sub(r"[^0-9]", "", str(r.get("season_rank") or "")))
            r["move"] = _was - i if _was else None
        except (TypeError, ValueError):
            r["move"] = None
        r["total_points"] = r["live_total"]
    i = 0
    while i < len(out):
        j = i + 1
        while j < len(out) and out[j]["live_total"] == out[i]["live_total"]:
            j += 1
        label = ("T" if j - i > 1 else "") + str(i + 1)
        for g in range(i, j):
            out[g]["rank"] = label
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
