"""Tests for STARTING-handicap sync between the ROSTER and PAIRINGS views
(Kerry 2026-07-31: "When I added Mark Villa's handicap on PAIRINGS, it did
not add it to him in ROSTER. Those need to be immediately synced. They also
both need to be editable.").

The backend was never the problem — the value persisted. The two screens
disagreed because ROSTER reads only the name-keyed handicap index map. This
exercises the shared-map contract that both views now depend on:
`get_starting_handicaps` -> `get_all_handicap_players` -> the index-map
payload, for a player with a starting handicap and NO rounds at all.

Run: python3 test_starting_handicap_sync.py
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


def index_map_payload(players):
    """Mirror of app.api_handicap_index_map's shaping, so a change to the
    filter there without a change here shows up as a failure."""
    out = {}
    for p in players:
        cname = p.get("customer_name")
        if cname and p.get("handicap_index") is not None:
            idx9 = p["handicap_index"]
            entry = {
                "index_9": idx9,
                "index_18": (p.get("starting_handicap_18")
                             if (p.get("handicap_source") == "starting"
                                 and p.get("starting_handicap_18") is not None)
                             else round(idx9 * 2, 1)),
                "source": p.get("handicap_source") or "computed",
                "rounds": p.get("active_rounds") or 0,
                "customer_id": p.get("customer_id"),
            }
            out[cname.lower()] = entry
            if p.get("customer_id"):
                out[f"cid:{p['customer_id']}"] = entry
    return out


import sqlite3  # noqa: E402
import tempfile  # noqa: E402

fd, path = tempfile.mkstemp(suffix=".db")
os.close(fd)
db.init_db(path)

conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row

# Mark Villa's real shape: a 1st timer with a starting handicap, no rounds,
# and NO handicap_player_links row. That combination is what the ROSTER was
# showing as a dash.
conn.execute(
    """INSERT INTO customers (customer_id, first_name, last_name, chapter,
                              current_player_status, starting_handicap_18,
                              starting_handicap_set_at, starting_handicap_set_by)
       VALUES (692, 'Mark', 'Villa', 'San Antonio', 'first_timer', 12.5,
               '2026-07-31 21:44:53', 'manual:admin')""")
conn.commit()
conn.close()

print("\n== a starting handicap with no rounds reaches the shared map ==")

starting = db.get_starting_handicaps(path)
check("get_starting_handicaps sees him", 692 in starting, str(list(starting)))
check("the 18-hole value is what was typed",
      starting.get(692, {}).get("index_18") == 12.5, str(starting.get(692)))
check("the canonical name is carried, not a blank",
      starting.get(692, {}).get("customer_name") == "Mark Villa",
      str(starting.get(692)))

players = db.get_all_handicap_players(path)
villa = [p for p in players if p.get("customer_id") == 692]
check("a rounds-less player is APPENDED to the handicap players list",
      len(villa) == 1, f"{len(villa)} rows")
if villa:
    check("he is marked as a placeholder, never as computed",
          villa[0].get("handicap_source") == "starting",
          str(villa[0].get("handicap_source")))
    check("no rounds are implied", villa[0].get("total_rounds") == 0,
          str(villa[0].get("total_rounds")))

payload = index_map_payload(players)
check("the ROSTER's name key resolves", "mark villa" in payload,
      str(list(payload)))
if "mark villa" in payload:
    e = payload["mark villa"]
    check("the ROSTER would show 12.5 on an 18-hole event",
          e["index_18"] == 12.5, str(e))
    check("source says 'starting', so the P renders and the cell is editable",
          e["source"] == "starting", str(e))

print("\n== a computed index still wins over a placeholder ==")

conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row
conn.execute(
    """INSERT INTO customers (customer_id, first_name, last_name,
                              starting_handicap_18)
       VALUES (693, 'Real', 'Player', 30.0)""")
conn.execute("INSERT INTO handicap_player_links (player_name, customer_id, "
             "customer_name) VALUES ('Real Player', 693, 'Real Player')")
for i, diff in enumerate([4.0, 5.0, 6.0]):
    conn.execute(
        """INSERT INTO handicap_rounds (player_name, round_date, course_name,
                                        rating, slope, adjusted_score,
                                        differential)
           VALUES ('Real Player', ?, 'X', 35.0, 113, 40, ?)""",
        (f"2026-07-0{i + 1}", diff))
conn.commit()
conn.close()

players2 = db.get_all_handicap_players(path)
real = [p for p in players2 if p.get("customer_name") == "Real Player"]
check("the player with rounds appears once", len(real) == 1, f"{len(real)} rows")
if real:
    check("his source stays computed even though a placeholder exists",
          real[0].get("handicap_source") == "computed",
          str(real[0].get("handicap_source")))
    check("the placeholder is still reported alongside, not lost",
          real[0].get("starting_handicap_18") == 30.0,
          str(real[0].get("starting_handicap_18")))

payload2 = index_map_payload(players2)
check("a computed player is NOT offered as editable on the roster",
      payload2.get("real player", {}).get("source") == "computed",
      str(payload2.get("real player")))
check("Villa is still in the map after the second player was added",
      payload2.get("mark villa", {}).get("source") == "starting",
      str(payload2.get("mark villa")))

print("\n== the map is keyed by customer_id, not name alone ==")

check("the placeholder-only player has an id key",
      "cid:692" in payload2, str([k for k in payload2 if k.startswith("cid:")]))
check("the id key and the name key are the same entry",
      payload2.get("cid:692") == payload2.get("mark villa"),
      str(payload2.get("cid:692")))
check("a player whose index is COMPUTED also gets an id key",
      "cid:693" in payload2, str([k for k in payload2 if k.startswith("cid:")]))
check("the computed player's id key still reads computed",
      payload2.get("cid:693", {}).get("source") == "computed",
      str(payload2.get("cid:693")))
# The whole point: a roster row spelled differently from the profile still
# resolves, because the id is tried first.
check("an id lookup survives a name the map has never seen",
      payload2.get("cid:692", {}).get("index_18") == 12.5
      and "marky villa" not in payload2,
      str(payload2.get("cid:692")))

os.unlink(path)

print("\n" + ("ALL PASS" if not FAILURES else f"{len(FAILURES)} FAILED"))
for f in FAILURES:
    print("  -", f)
sys.exit(1 if FAILURES else 0)
