"""Tests for the LIVE championship hole-by-hole card (Kerry's ask, 2026-08-01).

The CITY CHAMPIONSHIP line in the player drill-down expands to a per-hole
card read straight off GG's scorecard board ("ALL Net 18"): gross + dots
from the player's details partial, pars from the tee (nets) partial, NET
and championship-scale Stableford computed by US — with the champ board's
own total carried beside ours so a disagreement is visible.

Run: python3 test_champ_card_live.py
"""
import json
import os
import sys

os.environ.setdefault("DATABASE_PATH", ":memory:")
import golf_genius_sync as gg               # noqa: E402
from email_parser import database as db     # noqa: E402

F = []
def check(l, c, d=""):
    print(("  PASS  " if c else "  FAIL  ") + l + ("" if c else "  " + d))
    if not c: F.append(l)

print("\n== the championship Stableford scale is the ratified chart ==")
for label, nvp, gross, want in [
        ("par pays 2", 0, 4, 2),
        ("birdie pays 3", -1, 3, 3),
        ("eagle pays 4", -2, 2, 4),
        ("double eagle pays 5", -3, 2, 5),
        ("bogey pays 1", 1, 5, 1),
        ("double bogey pays 0 — never negative", 2, 6, 0),
        ("triple pays 0", 3, 7, 0),
        ("a GROSS ace pays 9 regardless of net", -2, 1, 9)]:
    got = db._champ_stableford(nvp, gross)
    check(label, got == want, f"got {got}")
check("no par resolved -> no points, not a zero",
      db._champ_stableford(None, 4) is None)

print("\n== full card fetch against a faked GG ==")
# The three pages the card path walks, in the shapes the real parsers
# expect (details/nets are JS partials — one big string argument).
BOARDS = db.champ_card_boards(db_path=":memory:")
CARD_BOARD_URL = BOARDS["san_antonio_net"]["url"]
POINTS_BOARD_URL = db.champ_points_boards(db_path=":memory:")["san_antonio_net"]["url"]

CARD_BOARD_HTML = """<html><body>
<a href='https://tgf-sa.golfgenius.com/tournaments2/details?adjusting=false&event_id=4779120'>Expand All</a>
<a href='https://tgf-sa.golfgenius.com/tournaments2/details/111'>MORENO, Robert</a>
<a href='https://tgf-sa.golfgenius.com/tournaments2/details/112'>Villa, Mark</a>
</body></html>"""

POINTS_BOARD_HTML = """<html><body><table>
<tr><td>Pos.</td><td>Player</td><td>Stableford Points</td><td>Thru</td></tr>
<tr><td>1</td><td>MORENO, Robert TGF San Antonio</td><td>24</td><td>13</td></tr>
</table></body></html>"""

_details_inner = (
    "<table><tr class='net-line' data-net-name='MORENO, Robert'><td>x</td></tr>"
    "<tr><td><a class='expand-tee-details' href=\"/tournaments2/nets/77?event_id=88\">Gold (14)</a></td>"
    "<td class='hole1'><span class='score_box'>4</span>●</td>"
    "<td class='hole2'><span class='score_box'>3</span></td>"
    "<td class='hole3'><span class='score_box'>1</span>●</td>"
    "<td class='sum'>8</td>"
    "</tr></table>")
DETAILS_PARTIAL = "$('#agg').html(" + json.dumps(_details_inner) + ");"

_nets_inner = (
    "<table><tr class='tee_data'><td colspan='24'>1 - Gold Tee / SLOPE®: 135 /"
    " Course Rating™: 71.2 / The Quarry</td></tr>"
    "<tr class='par_row'><td>Par</td>"
    "<td>4</td><td>3</td><td>3</td><td>4</td><td>5</td><td>4</td><td>3</td><td>4</td><td>5</td><td>35</td>"
    "<td>4</td><td>4</td><td>3</td><td>5</td><td>4</td><td>4</td><td>3</td><td>4</td><td>5</td><td>36</td><td>71</td>"
    "</tr></table>")
NETS_PARTIAL = "$('#tee').html(" + json.dumps(_nets_inner) + ");"

_real_fetch = gg.fetch_public_page
def fake_fetch(url, timeout=20, xhr=False):
    if url == CARD_BOARD_URL:
        return {"status_code": 200, "final_url": url, "html": CARD_BOARD_HTML}
    if url == POINTS_BOARD_URL:
        return {"status_code": 200, "final_url": url, "html": POINTS_BOARD_HTML}
    if "/tournaments2/details/111" in url:
        return {"status_code": 200, "final_url": url, "html": DETAILS_PARTIAL}
    if "/tournaments2/nets/77" in url:
        return {"status_code": 200, "final_url": url, "html": NETS_PARTIAL}
    raise AssertionError("unexpected GG fetch: " + url)
gg.fetch_public_page = fake_fetch

import tempfile
fd, _bp = tempfile.mkstemp(suffix=".db"); os.close(fd)
db.init_db(_bp)
with db._connect(_bp) as conn:
    conn.execute("INSERT INTO customers (first_name, last_name)"
                 " VALUES ('Roberto', 'Moreno')")
    CID = conn.execute("SELECT customer_id FROM customers WHERE last_name='Moreno'").fetchone()[0]
    conn.commit()

card = db.fetch_champ_player_card("san_antonio_net", CID, db_path=_bp)
check("the card fetch works end to end", not card.get("error"), str(card))
check("GG's spelling resolved to OUR customer (Robert -> Roberto, by id)",
      card.get("customer_id") == CID, str(card.get("customer_id")))
h = {x["hole"]: x for x in card.get("holes", [])}
check("gross + dots come off the details partial",
      h[1]["gross"] == 4 and h[1]["dots"] == 1, str(h.get(1)))
check("pars come off the nets partial", h[1]["par"] == 4, str(h.get(1)))
check("net = gross - dots", h[1]["net"] == 3, str(h.get(1)))
check("net birdie on hole 1 pays 3", h[1]["pts"] == 3, str(h.get(1)))
check("net par on hole 2 pays 2", h[2]["pts"] == 2, str(h.get(2)))
check("the GROSS ace on hole 3 pays 9", h[3]["pts"] == 9, str(h.get(3)))
check("an unplayed hole reads None, never zero",
      h[4]["gross"] is None and h[4]["pts"] is None, str(h.get(4)))
check("our computed total sums the played holes (3+2+9)",
      card.get("computed_points") == 14, str(card.get("computed_points")))
check("the champ board's own figure rides along for the parity line",
      card.get("board_points") == 24.0 and card.get("board_thru") == "13",
      f"{card.get('board_points')} thru {card.get('board_thru')}")
check("playing handicap read off the tee link", card.get("playing_handicap") == 14.0,
      str(card.get("playing_handicap")))

print("\n== caching + failure behavior ==")
gg.fetch_public_page = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("GG down"))
again = db.fetch_champ_player_card("san_antonio_net", CID, db_path=_bp)
check("a hot cache serves without touching GG",
      again.get("computed_points") == 14 and not again.get("stale"), str(again))
# expire the cache: GG is down -> the last good card comes back marked stale
k = ("san_antonio_net", CID)
db._CHAMP_CARD_CACHE[k] = (0.0, db._CHAMP_CARD_CACHE[k][1])
db._CHAMP_ROSTER_CACHE.clear()
stale = db.fetch_champ_player_card("san_antonio_net", CID, db_path=_bp)
check("GG failing re-serves the last good card marked STALE",
      stale.get("stale") is True and stale.get("computed_points") == 14, str(stale))

gg.fetch_public_page = fake_fetch
db._CHAMP_ROSTER_CACHE.clear()
missing = db.fetch_champ_player_card("san_antonio_net", 99999, db_path=_bp)
check("a player not on the board degrades to a clean error",
      "not on the championship" in (missing.get("error") or ""), str(missing))
check("an unconfigured race degrades quietly",
      db.fetch_champ_player_card("no_such_race", 1, db_path=_bp).get("configured") is False)

print("\n== plus-handicap deduction, board to card (Kerry 2026-08-01) ==")
# Kerry, mid-round: plus players' playing handicaps come OFF their champ
# points. The plus values are read from the scorecard board's
# PlayingHandicap™ column; the deduction lands in fetch_champ_points (so
# standings/banner/drill-down all inherit it) and the card carries the
# same adjustment so the two never read as a disagreement.
CARD_BOARD_HTML2 = """<html><body>
<a href='https://tgf-sa.golfgenius.com/tournaments2/details/211'>YOUNGS, Pat</a>
<a href='https://tgf-sa.golfgenius.com/tournaments2/details/111'>MORENO, Robert</a>
<table>
<tr><td>Pos.</td><td>Player</td><td>PlayingHandicap™</td><td>TotalGross</td><td>To ParNet</td><td>Thru</td><td>TotalNet</td></tr>
<tr><td>1</td><td>YOUNGS, Pat TGF San Antonio</td><td>+4</td><td>-</td><td>-1</td><td>7</td><td>- (-/-)</td></tr>
<tr><td>2</td><td>MORENO, Robert TGF San Antonio</td><td>4</td><td>-</td><td>-3</td><td>6</td><td>- (-/-)</td></tr>
<tr><td>3</td><td>GRIFFIN, Matt TGF San Antonio</td><td>+3</td><td>-</td><td>-</td><td>1:00 PM</td><td>- (-/-)</td></tr>
</table></body></html>"""
POINTS_BOARD_HTML2 = """<html><body><table>
<tr><td>Pos.</td><td>Player</td><td>Stableford Points</td><td>Thru</td></tr>
<tr><td>1</td><td>YOUNGS, Pat TGF San Antonio</td><td>17 (0/17)</td><td>7</td></tr>
<tr><td>2</td><td>MORENO, Robert TGF San Antonio</td><td>15 (0/15)</td><td>6</td></tr>
<tr><td></td><td>GRIFFIN, Matt TGF San Antonio</td><td>-</td><td>1:00 PM</td></tr>
</table></body></html>"""
_details_inner2 = (
    "<table><tr class='net-line' data-net-name='YOUNGS, Pat'><td>x</td></tr>"
    "<tr><td><a class='expand-tee-details' href=\"/tournaments2/nets/78?event_id=88\">Gold (+4)</a></td>"
    "<td class='hole1'><span class='score_box'>4</span></td>"
    "<td class='hole2'><span class='score_box'>3</span></td>"
    "</tr></table>")
DETAILS_PARTIAL2 = "$('#agg').html(" + json.dumps(_details_inner2) + ");"

def fake_fetch2(url, timeout=20, xhr=False):
    if url == CARD_BOARD_URL:
        return {"status_code": 200, "final_url": url, "html": CARD_BOARD_HTML2}
    if url == POINTS_BOARD_URL:
        return {"status_code": 200, "final_url": url, "html": POINTS_BOARD_HTML2}
    if "/tournaments2/details/211" in url:
        return {"status_code": 200, "final_url": url, "html": DETAILS_PARTIAL2}
    if "/tournaments2/details/111" in url:
        return {"status_code": 200, "final_url": url, "html": DETAILS_PARTIAL}
    if "/tournaments2/nets/" in url:
        return {"status_code": 200, "final_url": url, "html": NETS_PARTIAL}
    raise AssertionError("unexpected GG fetch: " + url)
gg.fetch_public_page = fake_fetch2
db._CHAMP_POINTS_CACHE.clear()
db._CHAMP_ROSTER_CACHE.clear()
db._CHAMP_CARD_CACHE.clear()
with db._connect(_bp) as conn:
    conn.execute("INSERT INTO customers (first_name, last_name)"
                 " VALUES ('Pat', 'Youngs')")
    YCID = conn.execute("SELECT customer_id FROM customers"
                        " WHERE last_name='Youngs'").fetchone()[0]
    conn.commit()

live = db.fetch_champ_points("san_antonio_net", db_path=_bp)
py = {p["name"]: p for p in live.get("players", [])}
check("Youngs' board 17 reads 13 after the +4 comes off",
      py["YOUNGS, Pat"]["points"] == 13.0, str(py.get("YOUNGS, Pat")))
check("the raw board figure + deduction ride along",
      py["YOUNGS, Pat"].get("points_raw") == 17.0
      and py["YOUNGS, Pat"].get("plus_adjustment") == 4.0,
      str(py.get("YOUNGS, Pat")))
check("an ordinary handicap is untouched",
      py["MORENO, Robert"]["points"] == 15.0
      and "plus_adjustment" not in py["MORENO, Robert"],
      str(py.get("MORENO, Robert")))
check("a not-started plus player stays None — the deduction waits for "
      "their first hole",
      py["GRIFFIN, Matt"]["points"] is None
      and "plus_adjustment" not in py["GRIFFIN, Matt"],
      str(py.get("GRIFFIN, Matt")))
check("scoring count unchanged by the deduction (2 of 3)",
      live.get("scoring") == 2, str(live.get("scoring")))

ycard = db.fetch_champ_player_card("san_antonio_net", YCID, db_path=_bp)
check("the card carries the plus adjustment", ycard.get("plus_adjustment") == 4.0,
      str(ycard.get("plus_adjustment")))
check("per-hole PTS stay the raw Stableford (2 pars = 4)",
      ycard.get("computed_points") == 4, str(ycard.get("computed_points")))
check("adjusted computed total = raw - plus (may floor through zero)",
      ycard.get("computed_points_adj") == 0,
      str(ycard.get("computed_points_adj")))
check("the board figure rides along ALREADY adjusted (17 -> 13)",
      ycard.get("board_points") == 13.0, str(ycard.get("board_points")))
check("the details partial's '(+4)' parses NEGATIVE — the fallback source",
      ycard.get("playing_handicap") == -4.0,
      str(ycard.get("playing_handicap")))

print("\n== a scorecard-board outage must not un-adjust the standings ==")
gg.fetch_public_page = lambda url, timeout=20, xhr=False: (
    {"status_code": 200, "final_url": url, "html": POINTS_BOARD_HTML2}
    if url == POINTS_BOARD_URL
    else (_ for _ in ()).throw(RuntimeError("GG down")))
db._CHAMP_POINTS_CACHE.clear()
# roster cache is WARM (120s) — the adjustment must serve from it
live2 = db.fetch_champ_points("san_antonio_net", db_path=_bp)
py2 = {p["name"]: p for p in live2.get("players", [])}
check("warm roster cache keeps the deduction through a board hiccup",
      py2["YOUNGS, Pat"]["points"] == 13.0, str(py2.get("YOUNGS, Pat")))
# roster cache EXPIRED + GG down -> last good roster still serves the maps
db._CHAMP_ROSTER_CACHE["san_antonio_net"] = (
    0.0, db._CHAMP_ROSTER_CACHE["san_antonio_net"][1])
db._CHAMP_POINTS_CACHE.clear()
live3 = db.fetch_champ_points("san_antonio_net", db_path=_bp)
py3 = {p["name"]: p for p in live3.get("players", [])}
check("an expired roster + GG failure falls back to the last good maps",
      py3["YOUNGS, Pat"]["points"] == 13.0, str(py3.get("YOUNGS, Pat")))

print("\n== a DECLARED-FINAL board survives GG (Kerry: 'like the event "
      "never happened. That shouldn't occur in any situation') ==")
POINTS_BOARD_FINAL = """<html><body><table>
<tr><td>Pos.</td><td>Player</td><td>Stableford Points</td><td>Details</td></tr>
<tr><td>1</td><td>YOUNGS, Pat TGF San Antonio</td><td>43 (22/21)</td><td></td></tr>
<tr><td>2</td><td>MORENO, Robert TGF San Antonio</td><td>38 (19/19)</td><td></td></tr>
<tr><td>3</td><td>GRIFFIN, Matt TGF San Antonio</td><td>34 (19/15)</td><td></td></tr>
</table></body></html>"""
EMPTY_BOARD = "<html><body><p>Tournament not available.</p></body></html>"
_board_html = {"points": POINTS_BOARD_FINAL}
def fake_fetch3(url, timeout=20, xhr=False):
    if url == CARD_BOARD_URL:
        return {"status_code": 200, "final_url": url, "html": CARD_BOARD_HTML2}
    if url == POINTS_BOARD_URL:
        return {"status_code": 200, "final_url": url, "html": _board_html["points"]}
    raise AssertionError("unexpected GG fetch: " + url)
gg.fetch_public_page = fake_fetch3
db._CHAMP_POINTS_CACHE.clear(); db._CHAMP_ROSTER_CACHE.clear()
db.set_app_setting("gg_points_race_final",
                   '{"san_antonio_net": "2026-08-01"}', db_path=_bp)

live_fin = db.fetch_champ_points("san_antonio_net", db_path=_bp)
pf = {p["name"]: p for p in live_fin.get("players", [])}
check("the final board serves normally, plus deductions applied (43 -> 39)",
      pf["YOUNGS, Pat"]["points"] == 39.0, str(pf.get("YOUNGS, Pat")))
check("the finished board was PERSISTED on the first final read",
      bool(db.get_app_setting("gg_champ_final_board_san_antonio_net",
                              db_path=_bp)))

_board_html["points"] = EMPTY_BOARD
db._CHAMP_POINTS_CACHE.clear()
live_empty = db.fetch_champ_points("san_antonio_net", db_path=_bp)
pe = {p["name"]: p for p in live_empty.get("players", [])}
check("GG emptying the board serves the persisted final result",
      live_empty.get("source") == "final_snapshot"
      and pe.get("YOUNGS, Pat", {}).get("points") == 39.0
      and live_empty.get("field") == 3, str(live_empty.get("source")))

gg.fetch_public_page = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError("GG down"))
db._CHAMP_POINTS_CACHE.clear(); db._CHAMP_ROSTER_CACHE.clear()
live_down = db.fetch_champ_points("san_antonio_net", db_path=_bp)
check("GG fully down (no cache) still serves the persisted final result",
      live_down.get("source") == "final_snapshot"
      and live_down.get("field") == 3, str(live_down.get("source")))

# clearing the FINAL dial closes the fallback window — next season's
# empty board must never resurrect this year's championship
gg.fetch_public_page = fake_fetch3
db.set_app_setting("gg_points_race_final", "{}", db_path=_bp)
db._CHAMP_POINTS_CACHE.clear()
live_reset = db.fetch_champ_points("san_antonio_net", db_path=_bp)
check("dial cleared -> the empty board stays empty (no resurrection)",
      not live_reset.get("players") and live_reset.get("source") != "final_snapshot",
      str(live_reset.get("field")))

gg.fetch_public_page = _real_fetch
os.unlink(_bp)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILED"))
for f in F: print("  -", f)
sys.exit(1 if F else 0)
