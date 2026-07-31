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

print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL STANDINGS-PAIRING TESTS PASSED")
