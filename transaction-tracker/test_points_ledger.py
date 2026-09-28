"""GO 6 ledger capture — resume/chunk logic with Golf Genius stubbed.

The live capture runs on the deployed app (this sandbox cannot reach GG).
What this file proves is the part that can silently lose data: that chunks
resume at the right player, that a player with no member card is recorded as
an error rather than dropped, that raw tables are kept verbatim, and that the
race's event list is the union across players.

Run: python3 test_points_ledger.py
"""
import sys
import golf_genius_sync as ggs
from email_parser import points_ledger as pl

FAILURES = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)

STANDINGS = [{"player_name": f"P{i}", "member_card_id": (None if i == 2 else str(100 + i)),
              "rank": str(i + 1), "total_points": 30 - i, "tournaments": 3}
             for i in range(5)]
CALLS = []
def fake_standings(page_id, league_id, host):
    return STANDINGS
def fake_detail(page_id, card, league_id, host, effective_date):
    CALLS.append((card, effective_date))
    return {"tables": [[["Tournament", "Date", "Points"],
                        [f"s9.2{card[-1]} Course", "2026-09-0" + card[-1], "7"],
                        ["s9.19 Other", "2026-08-29", "5"]]],
            "headings": ["detail"]}
ggs.fetch_season_points_race = fake_standings
ggs.fetch_points_race_member_detail = fake_detail

# time budget 0 -> exactly one player per chunk; walk to the end
chunks, start = [], 0
while start is not None:
    c = pl.capture_race_ledger("page:tgf-sa.golfgenius.com:514047:999",
                               start=start, effective_date="2026-09-27",
                               time_budget=0.0)
    chunks.append(c); start = c["next"]
players = [p for c in chunks for p in c["players"]]

print("\n== chunking and resume ==")
check("every standings row is captured exactly once",
      [p["index"] for p in players] == list(range(len(STANDINGS))))
check("the walk ends with next=None", chunks[-1]["next"] is None)
check("effective_date is passed through to GG",
      all(e == "2026-09-27" for _, e in CALLS))

print("\n== nothing dropped silently ==")
p2 = next(p for p in players if p["index"] == 2)
check("a player with no member card is RECORDED with an error, not dropped",
      "error" in p2 and p2["player_name"] == "P2")
check("GG's raw tables are kept verbatim",
      players[0]["raw_tables"][0][0] == ["Tournament", "Date", "Points"])
check("a normalised per-round view is derived alongside",
      players[0]["rounds"][0]["Points"] == "7")

print("\n== #790: the race's exact event list ==")
ev = pl.race_event_list(players)
check("event list is the union across players", "s9.19 Other" in ev and len(ev) >= 4, ev)

print("\n== refs ==")
try:
    pl._resolve("page:evil.example.com:1:2")
    check("a non-GG host is refused", False)
except ValueError:
    check("a non-GG host is refused", True)


print("\n== persisted bundle on the data volume ==")
import tempfile
root = tempfile.mkdtemp()
st = None
for c in chunks:
    st = pl.persist_chunk(c, root=root)
check("after every chunk, the bundle has every player", st["have"] == 5 and not st["missing"], st)
check("  ...but it is NOT complete while a player errored (P2 had no card)",
      st["complete"] is False and st["errors"] == ["P2"], st)
fixed = dict(chunks[2], players=[dict(chunks[2]["players"][0], error=None,
                                      raw_tables=[[["T","Points"],["x","1"]]])])
fixed["players"][0].pop("error")
st = pl.persist_chunk(fixed, root=root)
check("re-running a slice REPAIRS it in place (later chunk wins)",
      st["complete"] is True and st["errors"] == [], st)
check("status lists the race", pl.bundle_status("2026-09-27", root=root)[0]["complete"])
doc = pl.read_bundle("2026-09-27", "page:tgf-sa.golfgenius.com:514047:999", root=root)
check("the stored bundle reads back with raw tables intact",
      doc["players"]["0"]["raw_tables"][0][0] == ["Tournament", "Date", "Points"])

print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}"); sys.exit(1)
print("ALL POINTS-LEDGER TESTS PASSED")
