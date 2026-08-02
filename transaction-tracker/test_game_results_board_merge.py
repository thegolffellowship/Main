"""Tests for the per-buyer board-row merge in determine_event_game_results.

An 18-hole event imports TWO GG boards (ALL Net + ALL Gross) into
scoring_rounds, so each buyer has two rows for the same physical round:
the Net-board row carries net + playing_handicap, the Gross-board row has
them NULL. Last-row-wins used to pick whichever board imported last and
reported Individual Net as awaiting_results on a fully-scored event (the
2026-08-01 championships). The fix merges rows per buyer — later rows only
fill fields still missing, never overwrite a value with NULL.

Run: python3 test_game_results_board_merge.py
"""
import os
import sqlite3
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

F = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "  " + detail))
    if not cond:
        F.append(label)


path = os.path.join(tempfile.mkdtemp(prefix="tgf-merge-test-"), "t.db")
conn = sqlite3.connect(path)
conn.executescript("""
CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT,
                     event_date TEXT, format TEXT, course TEXT);
CREATE TABLE event_aliases (alias_name TEXT, canonical_event_name TEXT);
CREATE TABLE items (id INTEGER PRIMARY KEY, parent_item_id INTEGER,
                    customer_id INTEGER, customer TEXT, side_games TEXT,
                    transaction_status TEXT, wd_credits TEXT, item_name TEXT);
""")
conn.commit()
conn.close()

with db._connect(path) as c:
    db._ensure_scoring_tables(c)
    c.execute("INSERT INTO events (id, item_name, event_date, format) "
              "VALUES (1, 'TGF TEST CHAMPIONSHIP', '2026-08-01', '18 Holes')")
    for cid, name in ((10, "ALPHA, Al"), (11, "BRAVO, Bo"), (12, "CHARLIE, Cy")):
        c.execute("INSERT INTO items (customer_id, customer, side_games, "
                  "transaction_status, item_name) VALUES (?, ?, 'BOTH', "
                  "'active', 'TGF TEST CHAMPIONSHIP')", (cid, name))
    # Net-board rows first (lower ids): net + playing_handicap present.
    for cid, name, gross, ph in ((10, "ALPHA, Al", 86, 8),
                                 (11, "BRAVO, Bo", 92, 15),
                                 (12, "CHARLIE, Cy", 99, 20)):
        c.execute("INSERT INTO scoring_rounds (customer_id, player_name, "
                  "event_id, gross, net, playing_handicap, source) "
                  "VALUES (?, ?, 1, ?, ?, ?, 'gg')",
                  (cid, name, gross, gross - ph, ph))
    # Gross-board rows second (higher ids): net/playing_handicap NULL —
    # exactly what the ALL Gross import writes.
    for cid, name, gross in ((10, "ALPHA, Al", 86), (11, "BRAVO, Bo", 92),
                             (12, "CHARLIE, Cy", 99)):
        c.execute("INSERT INTO scoring_rounds (customer_id, player_name, "
                  "event_id, gross, source) VALUES (?, ?, 1, ?, 'gg')",
                  (cid, name, gross))
    c.commit()

print("\n== Individual Net survives a later NULL-net board row ==")
d = db.determine_event_game_results("TGF TEST CHAMPIONSHIP",
                                    "individual_net", flights=1, db_path=path)
check("status is determined (was awaiting_results before the merge fix)",
      d.get("status") == "determined", str(d.get("status")))
check("all three buyers scored", d.get("rounds_matched") == 3,
      str(d.get("rounds_matched")))
rank = (d.get("flights") or [{}])[0].get("ranking") or []
check("ladder ranks all three by merged net (BRAVO 77 first)",
      [r["player"] for r in rank]
      == ["BRAVO, Bo", "ALPHA, Al", "CHARLIE, Cy"], str(rank))
nets = {r["player"]: r.get("net") for r in rank}
check("ALPHA's merged net is 78 (from the Net-board row, not NULL)",
      nets.get("ALPHA, Al") == 78, str(nets))
check("BRAVO's merged net is 77", nets.get("BRAVO, Bo") == 77, str(nets))
check("CHARLIE's merged net is 79", nets.get("CHARLIE, Cy") == 79, str(nets))

print("\n== Individual Gross still works off the same merged rows ==")
g = db.determine_event_game_results("TGF TEST CHAMPIONSHIP",
                                    "individual_gross", flights=1,
                                    db_path=path)
check("gross game is determined", g.get("status") == "determined",
      str(g.get("status")))

print()
if F:
    print(f"{len(F)} FAILURE(S)")
    sys.exit(1)
print("ALL PASS")
