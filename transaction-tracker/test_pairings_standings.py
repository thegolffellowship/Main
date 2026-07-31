"""Tests for STANDINGS pairing order (Kerry 2026-07-30).

"Need the ability to Generate Pairings by standings in a Chapter's Point
Race. In this case I want the leaders paired last just like in the PGA.
However, I still want to honor Player Requests for this one. Order should
just pick up after their requests are accounted for."

Run: python3 test_pairings_standings.py
"""

import os
import sys

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def groups(players, ranks, partners=None, protect=True):
    g, notes = db._standings_groups(players, ranks, partners or {}, protect)
    return g, notes


print("\n== leaders go off LAST ==")

# 8 players, ranked 1 (leader) .. 8.
P = [f"P{i}" for i in range(1, 9)]
RANK = {f"p{i}": i for i in range(1, 9)}
g, notes = groups(P, RANK)
check("two foursomes from eight players",
      [len(x) for x in g] == [4, 4], str([len(x) for x in g]))
check("the LEADER is in the final group", "P1" in g[-1], str(g))
check("the top four are all in the final group",
      set(g[-1]) == {"P1", "P2", "P3", "P4"}, str(g[-1]))
check("the back of the standings tees off first",
      set(g[0]) == {"P5", "P6", "P7", "P8"}, str(g[0]))

print("\n== unranked players tee off earliest ==")

mixed = ["Leader", "Second", "Guest A", "Guest B", "Mid", "Guest C"]
rank2 = {"leader": 1, "second": 2, "mid": 12}
g, notes = groups(mixed, rank2)
check("the leader is in the last group", "Leader" in g[-1], str(g))
check("unranked players are in the first group",
      all(p.startswith("Guest") for p in g[0]), str(g[0]))
check("the note says how many are in the standings",
      any("3 of 6 players are in the standings" in n for n in notes), str(notes))

print("\n== partner requests are honored, order picks up around them ==")

# The load-bearing case: the LEADER requests an UNRANKED partner. Ordering
# the unit by its weaker member would drag the leader to an early tee time.
field = ["Leader", "Rookie", "A", "B", "C", "D", "E", "F"]
rank3 = {"leader": 1, "a": 2, "b": 3, "c": 4, "d": 5, "e": 6, "f": 7}
g, notes = groups(field, rank3, partners={"Leader": "Rookie"})
lead_group = next(x for x in g if "Leader" in x)
check("the requested pair is kept together",
      "Rookie" in lead_group, str(g))
check("the LEADER still goes off last despite an unranked partner",
      lead_group is g[-1], str(g))

# A pair in the middle of the standings stays together without disturbing
# the leaders-last property.
g, notes = groups(P, RANK, partners={"P6": "P3"})
pair_group = next(x for x in g if "P6" in x)
check("a mid-field request keeps both players together",
      "P3" in pair_group, str(g))
check("the leader is still last", "P1" in g[-1], str(g))
check("every player is placed exactly once",
      sorted(p for x in g for p in x) == sorted(P), str(g))

# Turning the protection off must break the pair, not error.
g_off, _ = groups(P, RANK, partners={"P6": "P3"}, protect=False)
check("with requests off the pair is not forced together",
      sorted(p for x in g_off for p in x) == sorted(P), str(g_off))

print("\n== group shapes ==")

# 9 players -> sizes [4,3,2] etc.; short groups must go EARLIEST so the
# leaders land in a full foursome at the back, as on tour.
for n in range(2, 25):
    pl = [f"Q{i}" for i in range(1, n + 1)]
    rk = {f"q{i}": i for i in range(1, n + 1)}
    g, _ = groups(pl, rk)
    placed = sorted(p for x in g for p in x)
    if placed != sorted(pl):
        check(f"n={n}: every player placed exactly once", False, str(g))
        break
    if any(len(x) > 4 for x in g):
        check(f"n={n}: no group exceeds four", False, str([len(x) for x in g]))
        break
    sizes = [len(x) for x in g]
    if sizes != sorted(sizes):
        check(f"n={n}: short groups go earliest", False, str(sizes))
        break
    if "Q1" not in g[-1]:
        check(f"n={n}: leader in the last group", False, str(g))
        break
else:
    check("every field size 2-24 places all players, max four per group, "
          "short groups earliest, leader always last", True)

print("\n== no standings at all ==")

g, notes = groups(["X", "Y", "Z"], {})
check("an empty rank map still places everyone",
      sorted(p for x in g for p in x) == ["X", "Y", "Z"], str(g))
check("...and says nobody was in the standings",
      any("0 of 3 players are in the standings" in n for n in notes), str(notes))

print("\n== point-of-use refresh (Kerry 2026-07-30) ==")

# Pairings lock when an event tees off, so the only moment the standings
# must be current is the moment Generate is pressed — including day 2 of a
# two-day event, where the second day's order comes off day 1's results.
check("the staleness window is short enough that yesterday never survives",
      0 < db._STANDINGS_PAIRING_MAX_AGE_HOURS <= 1.0,
      str(db._STANDINGS_PAIRING_MAX_AGE_HOURS))

calls = []
_real = db.get_points_race_standings


def _fake(race_key, auto_refresh_hours=12, force_refresh=False,
          db_path=None, **kw):
    calls.append({"race_key": race_key, "auto_refresh_hours": auto_refresh_hours})
    return {"standings": [
        {"player_name": "Leader", "position": 1},
        {"player_name": "Chaser", "position": 2},
    ], "fetched_at": "2026-07-30 18:00:00", "gg_error": None}


db.get_points_race_standings = _fake
try:
    rm, key, notes = db._standings_rank_map("San Antonio")
    check("the chapter resolves to its NET points race",
          key == "san_antonio_net", str(key))
    check("the refresh window is passed down, not the 12-hour default",
          calls and calls[0]["auto_refresh_hours"] == db._STANDINGS_PAIRING_MAX_AGE_HOURS,
          str(calls))
    check("positions are read off the standings",
          rm == {"leader": 1, "chaser": 2}, str(rm))
    check("the notes state how current the numbers are",
          any("Standings as of 2026-07-30 18:00:00" in n for n in notes), str(notes))

    # Austin resolves to its own race, not San Antonio's.
    calls.clear()
    _, key2, _ = db._standings_rank_map("Austin")
    check("Austin resolves to the Austin race", key2 == "austin_net", str(key2))

    # An unknown chapter must not silently borrow another chapter's race.
    _, key3, notes3 = db._standings_rank_map("Houston")
    check("an unknown chapter yields no race rather than the wrong one",
          key3 is None and any("No points race found" in n for n in notes3),
          f"{key3} {notes3}")

    # GG DOWN — the stale fallback must be announced, never swallowed.
    def _down(race_key, auto_refresh_hours=12, force_refresh=False,
              db_path=None, **kw):
        return {"standings": [{"player_name": "Leader", "position": 1}],
                "fetched_at": "2026-07-29 06:00:00",
                "gg_error": "connection timed out"}

    db.get_points_race_standings = _down
    rm4, _, notes4 = db._standings_rank_map("San Antonio")
    check("a GG outage still yields usable standings", rm4 == {"leader": 1})
    check("...but WARNS that they are a stale snapshot",
          any(n.startswith("WARNING: Golf Genius could not be reached")
              for n in notes4), str(notes4))
    check("...and names how old they are",
          any("2026-07-29 06:00:00" in n for n in notes4), str(notes4))

    # A hard failure must not take the generator down with it.
    def _boom(*a, **kw):
        raise RuntimeError("portal exploded")

    db.get_points_race_standings = _boom
    rm5, _, notes5 = db._standings_rank_map("San Antonio")
    check("a hard GG failure degrades instead of raising",
          rm5 == {} and any("portal exploded" in n for n in notes5), str(notes5))
finally:
    db.get_points_race_standings = _real

print("\n== the race must be the chapter's NET race, not merely its chapter ==")

# THE TRAP: players_cup_gross is tagged chapter = "San Antonio" (it is
# cross-chapter, enroll_chapter=None, but carries an SA chapter tag). A
# chapter-only match would therefore pick the GROSS Players Cup for every
# San Antonio event and pair the field off the wrong race entirely.
_cfg = db._GG_POINTS_RACES
_sa_races = [k for k, c in _cfg.items()
             if (c.get("chapter") or "").strip().lower() == "san antonio"]
check("more than one configured race is tagged San Antonio — so chapter "
      "alone cannot identify the race", len(_sa_races) > 1, str(_sa_races))
check("...and one of them is a GROSS race",
      any((_cfg[k].get("contest_type") or "").upper().startswith("GROSS")
          for k in _sa_races), str(_sa_races))

_real2 = db.get_points_race_standings
db.get_points_race_standings = lambda key, **kw: {
    "standings": [], "fetched_at": None, "gg_error": None}
try:
    _, sa_key, _ = db._standings_rank_map("San Antonio")
    check("San Antonio resolves to the NET race, NOT the Players Cup",
          sa_key == "san_antonio_net", str(sa_key))
    check("...and specifically never to a GROSS race",
          not (_cfg.get(sa_key, {}).get("contest_type") or "")
          .upper().startswith("GROSS"), str(sa_key))

    _, au_key, _ = db._standings_rank_map("Austin")
    check("Austin resolves to its own NET race", au_key == "austin_net", str(au_key))
    check("...and never borrows San Antonio's", au_key != "san_antonio_net")

    # Chapter matching is case- and whitespace-insensitive.
    for variant in ["san antonio", "SAN ANTONIO", "  San Antonio  "]:
        _, k, _ = db._standings_rank_map(variant)
        check(f"chapter '{variant}' still resolves to san_antonio_net",
              k == "san_antonio_net", str(k))

    # An explicit race_key overrides the chapter default — that is how the
    # Players Cup would be used deliberately rather than by accident.
    _, forced, _ = db._standings_rank_map("San Antonio",
                                          race_key="players_cup_gross")
    check("an explicit race_key overrides the chapter default",
          forced == "players_cup_gross", str(forced))

    # A chapter with no race must yield nothing rather than the nearest match.
    for ch in ["Houston", "DFW", None, ""]:
        _, k, _ = db._standings_rank_map(ch)
        check(f"chapter '{ch}' yields no race rather than a wrong one",
              k is None, str(k))
finally:
    db.get_points_race_standings = _real2

print("\n== race is CHOSEN, with a sensible default (Kerry 2026-07-30) ==")

# "A pulldown ... should default to the Chapter Net contest. Though we'll be
# doing the TGF Championship based on The Fellowship Cup standings."
check("a chapter event defaults to its own City NET race",
      db._default_pairing_race("San Antonio") == "san_antonio_net")
check("Austin likewise", db._default_pairing_race("Austin") == "austin_net")
# Kerry 2026-07-30 (correction): ONLY the TGF Championship defaults to the
# Fellowship Cup. A TGF-chapter event that is not the championship gets no
# default rather than a guess.
check("the TGF Championship defaults to THE FELLOWSHIP CUP",
      db._default_pairing_race("TGF", "2026 TGF CHAMPIONSHIP")
      == db.FELLOWSHIP_CUP_RACE_KEY,
      str(db._default_pairing_race("TGF", "2026 TGF CHAMPIONSHIP")))
check("a non-championship TGF event gets NO default, not the Cup",
      db._default_pairing_race("TGF", "TGF Fall Outing") is None,
      str(db._default_pairing_race("TGF", "TGF Fall Outing")))
# The city championships contain both "TGF" and "CHAMPIONSHIP" in their
# names but carry a CHAPTER, so the chapter rule must catch them first.
check("the SA City Championship stays on the SA City NET race",
      db._default_pairing_race("San Antonio", "TGF SAN ANTONIO CHAMPIONSHIP")
      == "san_antonio_net")
check("the Austin City Championship stays on the Austin race",
      db._default_pairing_race("Austin", "TGF AUSTIN CHAMPIONSHIP") == "austin_net")
check("an unknown chapter has no default rather than a wrong one",
      db._default_pairing_race("Houston") is None)

opts = db.pairing_race_options("San Antonio")
keys = [o["race_key"] for o in opts]
check("every configured race is offered", set(keys) >= set(db._GG_POINTS_RACES))
check("...plus the Fellowship Cup", db.FELLOWSHIP_CUP_RACE_KEY in keys, str(keys))
check("exactly one option is flagged default",
      sum(1 for o in opts if o["is_default"]) == 1, str(opts))
check("the default is listed first",
      opts[0]["is_default"] and opts[0]["race_key"] == "san_antonio_net",
      str(opts[0]))
check("the GROSS Players Cup is selectable but NOT the default",
      any(o["race_key"] == "players_cup_gross" and not o["is_default"]
          for o in opts))

tgf_opts = db.pairing_race_options("TGF", "2026 TGF CHAMPIONSHIP")
check("for the TGF Championship the Cup is default and listed first",
      tgf_opts[0]["race_key"] == db.FELLOWSHIP_CUP_RACE_KEY
      and tgf_opts[0]["is_default"], str(tgf_opts[0]))
plain = db.pairing_race_options("TGF", "TGF Fall Outing")
check("a non-championship TGF event flags no default",
      not any(o["is_default"] for o in plain), str(plain[:2]))

# The Fellowship Cup routes to its own projection, not a City race.
_realp, _realf = db.get_points_race_standings, db.get_fellowship_cup_projection
seen = []
db.get_points_race_standings = lambda k, **kw: (seen.append(("city", k)), {
    "standings": [], "fetched_at": None, "gg_error": None})[1]
db.get_fellowship_cup_projection = lambda **kw: (seen.append(("cup", None)), {
    "standings": [{"player_name": "Cup Leader"}], "fetched_at": "t", "gg_error": None})[1]
try:
    rm, key, _ = db._standings_rank_map("TGF", event_name="2026 TGF CHAMPIONSHIP")
    check("the TGF Championship reads the Fellowship Cup projection",
          seen and seen[-1][0] == "cup", str(seen))
    check("...and its ordering becomes the rank map",
          rm == {"cup leader": 1}, str(rm))
    seen.clear()
    db._standings_rank_map("San Antonio")
    check("a chapter event still reads its City race",
          seen and seen[-1] == ("city", "san_antonio_net"), str(seen))
    seen.clear()
    db._standings_rank_map("San Antonio", race_key=db.FELLOWSHIP_CUP_RACE_KEY)
    check("an explicit Fellowship Cup choice overrides the chapter default",
          seen and seen[-1][0] == "cup", str(seen))
finally:
    db.get_points_race_standings, db.get_fellowship_cup_projection = _realp, _realf

print("\n== GG names must match the ROSTER (Kerry 2026-07-31) ==")
# The SA Championship generated a pairing sheet that said "0 of 32 players
# are in the standings" and was therefore random order wearing a STANDINGS
# label. Cause: the rank map keyed on a plain lowercased name, but the GG
# portal stores "LAST, First". customer_id is on BOTH sides — use it.
GG = {"standings": [
    {"player_name": "SOUTH, Daniel",  "customer_id": 7,  "position": 1},
    {"player_name": "VASQUEZ, Gus",   "customer_id": 2,  "position": 2},
    {"player_name": "ARIAS, Victor Jr", "customer_id": None, "position": 3},
    {"player_name": "NOPROFILE, Ann", "customer_id": None, "position": 4},
], "fetched_at": "2026-07-31 18:00:00", "gg_error": None}
_rp = db.get_points_race_standings
db.get_points_race_standings = lambda k, **kw: GG
try:
    rm, key, notes = db._standings_rank_map("San Antonio")
finally:
    db.get_points_race_standings = _rp

check("the race resolved to the SA City NET race", key == "san_antonio_net", str(key))
check("customer_id keys are present", rm.get(7) == 1 and rm.get(2) == 2, str(rm))
check("the raw portal spelling is keyed too",
      rm.get("south, daniel") == 1, str(rm.get("south, daniel")))
check("...and so is the 'First Last' form it implies",
      rm.get("daniel south") == 1, str(rm.get("daniel south")))
# "ARIAS, Victor Jr" implies "Victor Arias Jr" (and "Victor Jr Arias").
# A bare "Victor Arias" is deliberately NOT generated — dropping a suffix
# is how you conflate a Jr with his father; customer_id is the answer for
# that case, not a looser name rule.
check("a suffixed GG name resolves as well",
      rm.get("victor arias jr") == 3, str(rm.get("victor arias jr")))
check("...but the suffix is not silently dropped",
      rm.get("victor arias") is None, str(rm.get("victor arias")))

# The whole point: a roster keyed by customer_id now ranks.
roster = ["Daniel South", "Gus Vasquez", "Victor Arias Jr", "Wade Fieber"]
ids = {"Daniel South": 7, "Gus Vasquez": 2, "Victor Arias Jr": 44, "Wade Fieber": 55}
groups, gnotes = db._standings_groups(roster, rm, {}, False, id_map=ids)
line = next((n for n in gnotes if "in the standings" in n), "")
check("3 of the 4 rank — not 0 of 4",
      "3 of 4 players are in the standings" in line, line)
check("the unranked player is NAMED so a mismatch is diagnosable",
      any("Wade Fieber" in n for n in gnotes), str(gnotes))
check("no bogus all-missed warning when matching works",
      not any("NONE of the field" in n for n in gnotes), str(gnotes))

# LEADERS LAST: Daniel South (position 1) must be in the final group.
flat_last = groups[-1] if groups else []
check("the points leader goes off LAST",
      "Daniel South" in flat_last, str(groups))
check("the unranked player goes off FIRST",
      "Wade Fieber" in (groups[0] if groups else []), str(groups))

# A roster row with NO customer_id still matches on the name fallback.
g2, n2 = db._standings_groups(["Daniel South", "Wade Fieber"], rm, {}, False,
                              id_map={"Wade Fieber": 55})
check("a roster row without a customer_id falls back to the name",
      "2 of 2 players" not in " ".join(n2)
      and "1 of 2 players are in the standings" in " ".join(n2), str(n2))

# And the failure mode itself is now loud rather than silent.
_g3, n3 = db._standings_groups(["Nobody One", "Nobody Two"], rm, {}, False,
                               id_map={})
check("a total miss is called out as NOT a standings order",
      any("NONE of the field" in n for n in n3), str(n3))

print("\n== the sheet packs cleanly and the leader really is LAST ==")
# The SA Championship: 32 players, which is exactly 8 foursomes, yet two
# players "matched no slot" and were dumped into the smallest group
# (Kerry 2026-07-31). Cause: the fill cursor only ever moved FORWARD, so a
# pair arriving at a group of 3 skipped that group permanently and left a
# hole nothing could reuse.
FIELD32 = [f"P{i:02d}" for i in range(32)]
RANK32 = {p.lower(): i + 1 for i, p in enumerate(FIELD32)}   # P00 = leader
PAIRS32 = {"P00": "P17", "P03": "P22", "P09": "P28", "P14": "P31"}
g32, n32 = db._standings_groups(FIELD32, RANK32, PAIRS32, True)

check("32 players make exactly 8 foursomes",
      [len(x) for x in g32] == [4] * 8, str([len(x) for x in g32]))
check("nobody 'matched no slot'",
      not any("no slot" in n for n in n32),
      str([n for n in n32 if "no slot" in n]))
check("every player is placed exactly once",
      sorted(x for u in g32 for x in u) == sorted(FIELD32))
check("the points LEADER is in the last group",
      "P00" in g32[-1], str(g32[-1]))
check("the tail of the standings goes off FIRST",
      "P30" in g32[0] and "P29" in g32[0], str(g32[0]))
for a, b in PAIRS32.items():
    check(f"partner pair {a}+{b} is not split",
          any(a in u and b in u for u in g32), str(g32))

# Uneven fields are where the old cursor lost the leader entirely: a hole
# left in a late group got backfilled by the leader, pulling them off the
# final tee time. Filling from the BACK makes leaders-last exact.
for n in (13, 22, 25, 31, 43):
    pl = [f"X{i:02d}" for i in range(n)]
    rk = {p.lower(): i + 1 for i, p in enumerate(pl)}
    pm = {pl[i]: pl[-(i + 1)] for i in range(0, min(4, n // 4))}
    gg, _nt = db._standings_groups(pl, rk, pm, True)
    check(f"n={n}: leader goes off last", "X00" in gg[-1], str(gg[-1]))
    check(f"n={n}: nobody is lost or duplicated",
          sorted(x for u in gg for x in u) == sorted(pl))
    check(f"n={n}: no group exceeds a foursome",
          all(len(u) <= 4 for u in gg), str([len(u) for u in gg]))

print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL STANDINGS-PAIRING TESTS PASSED")
