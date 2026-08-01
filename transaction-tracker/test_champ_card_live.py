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

gg.fetch_public_page = _real_fetch
os.unlink(_bp)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILED"))
for f in F: print("  -", f)
sys.exit(1 if F else 0)
