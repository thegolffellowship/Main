"""Tests for recording / changing / CLEARING the 3rd-place consolation match
(Kerry 2026-07-31, for Robert on the Austin bracket).

"Robert would like to have a winner takes all third place match rather than
just splitting the total out between as a tie for third place. He populated
the third place match, but can't figure out how to undo it."

Winner-takes-all was already the behaviour once a winner is recorded — the
even split is only the FALLBACK. The gap was that the UI hid the control the
moment a result existed, so a mis-tap could not be undone even though
`cmp_record_consolation(..., winner_name=None)` has always meant "clear".

Run: python3 test_cmp_consolation_undo.py
"""

import os
import sys

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
from email_parser import match_play as mp  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


print("\n== winner-takes-all vs the fallback split, on the ratified ladder ==")

# N=8-10 band: [50, 30, 20] on the adjusted pot. Three places, so the
# semifinal losers jointly occupy 3rd only.
structure = mp.structure_for_n(mp.SEED_MATCH_PLAY_CONFIG, 8)
amounts = structure["ladder_amounts_cents"]
check("the 8-player ladder pays three places", len(amounts) == 3, str(amounts))

split_rows = mp.ladder_payout_rows(
    structure, [["Champ"], ["Runner"], ["LoserA", "LoserB"]])
third_split = {r["player_name"]: r["amount"]
               for r in split_rows if r["player_name"].startswith("Loser")}
check("with no consolation the two losers split 3rd evenly",
      third_split["LoserA"] == third_split["LoserB"], str(third_split))

wta_rows = mp.ladder_payout_rows(
    structure, [["Champ"], ["Runner"], ["LoserA"], ["LoserB"]])
wta = {r["player_name"]: r["amount"] for r in wta_rows}
check("a played 3rd-place match pays the winner MORE than the split",
      wta["LoserA"] > third_split["LoserA"],
      f'{wta["LoserA"]} vs {third_split["LoserA"]}')
check("the 3rd-place winner takes the whole 3rd-place amount",
      round(wta["LoserA"] * 100) == amounts[2], str(wta["LoserA"]))
check("the loser of the 3rd-place match gets nothing on a 3-place ladder",
      wta["LoserB"] == 0.0, str(wta["LoserB"]))
check("the ladder total is identical either way — money is moved, not made",
      round(sum(r["amount"] for r in split_rows), 2)
      == round(sum(r["amount"] for r in wta_rows), 2),
      f'{sum(r["amount"] for r in split_rows)} vs {sum(r["amount"] for r in wta_rows)}')

# N>=11 band pays four places, so the consolation decides 3rd vs 4th and
# BOTH losers are still paid.
s11 = mp.structure_for_n(mp.SEED_MATCH_PLAY_CONFIG, 12)
a11 = s11["ladder_amounts_cents"]
check("the 12-player ladder pays four places", len(a11) == 4, str(a11))
wta11 = {r["player_name"]: r["amount"] for r in mp.ladder_payout_rows(
    s11, [["Champ"], ["Runner"], ["LoserA"], ["LoserB"]])}
check("on a four-place ladder the 3rd-place loser still gets 4th money",
      wta11["LoserB"] > 0 and wta11["LoserA"] > wta11["LoserB"],
      str(wta11))

print("\n== record -> change -> CLEAR round trip ==")

import sqlite3  # noqa: E402
import tempfile  # noqa: E402

fd, path = tempfile.mkstemp(suffix=".db")
os.close(fd)
db.init_db(path)

SEASON, CHAPTER = "2026", "Austin"
conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row
pool = db.cmp_create_pool(SEASON, CHAPTER, "Pool A", db_path=path)
for nm in ("Loser A", "Loser B"):
    db.cmp_add_member(pool["id"], nm, None, db_path=path)


def consolation_row():
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    r = c.execute(
        """SELECT player_name, opponent_name, winner_name FROM cmp_bracket
           WHERE season=? AND chapter=? AND round='consolation'""",
        (SEASON, CHAPTER)).fetchone()
    c.close()
    return dict(r) if r else None


res = db.cmp_record_consolation(SEASON, CHAPTER, "Loser A", "Loser B",
                                winner_name="Loser A", db_path=path)
check("recording returns the winner", res["winner"] == "Loser A", str(res))
check("recording is not flagged as a clear", res["cleared"] is False, str(res))
check("the bracket row holds the winner",
      (consolation_row() or {}).get("winner_name") == "Loser A",
      str(consolation_row()))

# Robert's actual problem: he picked the wrong player. Changing it must work.
res = db.cmp_record_consolation(SEASON, CHAPTER, "Loser A", "Loser B",
                                winner_name="Loser B", db_path=path)
check("the winner can be CHANGED without clearing first",
      (consolation_row() or {}).get("winner_name") == "Loser B",
      str(consolation_row()))
check("changing does not create a second row",
      len([1 for _ in [consolation_row()] if _]) == 1)

# The undo: an empty winner clears it.
res = db.cmp_record_consolation(SEASON, CHAPTER, "Loser A", "Loser B",
                                winner_name=None, db_path=path)
check("clearing reports cleared", res["cleared"] is True, str(res))
check("clearing reports no winner", res["winner"] is None, str(res))
check("the bracket row survives with a NULL winner, so the pairing stays",
      consolation_row() is not None
      and consolation_row()["winner_name"] is None,
      str(consolation_row()))
check("both players are still named on the cleared row",
      (consolation_row() or {}).get("player_name") == "Loser A"
      and (consolation_row() or {}).get("opponent_name") == "Loser B",
      str(consolation_row()))

# And it can be re-recorded after a clear.
db.cmp_record_consolation(SEASON, CHAPTER, "Loser A", "Loser B",
                          winner_name="Loser A", db_path=path)
check("a cleared match can be recorded again",
      (consolation_row() or {}).get("winner_name") == "Loser A",
      str(consolation_row()))

print("\n== guardrails ==")

try:
    db.cmp_record_consolation(SEASON, CHAPTER, "Loser A", "Loser B",
                              winner_name="Somebody Else", db_path=path)
    check("a winner who did not play the match is rejected", False, "no raise")
except ValueError as e:
    check("a winner who did not play the match is rejected", True, str(e))

try:
    db.cmp_record_consolation(SEASON, CHAPTER, "Loser A", "Loser A",
                              db_path=path)
    check("the same player cannot play themselves", False, "no raise")
except ValueError as e:
    check("the same player cannot play themselves", True, str(e))

check("the failed writes did not disturb the recorded result",
      (consolation_row() or {}).get("winner_name") == "Loser A",
      str(consolation_row()))

os.unlink(path)

print("\n" + ("ALL PASS" if not FAILURES else f"{len(FAILURES)} FAILED"))
for f in FAILURES:
    print("  -", f)
sys.exit(1 if FAILURES else 0)
