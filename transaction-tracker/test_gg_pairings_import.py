"""Tests for the per-event 'pull pairings from Golf Genius' button
(Kerry 2026-07-31: "TGF AUSTIN CHAMPIONSHIP already has pairings on GG,
because Robert didn't use our generator").

Run: python3 test_gg_pairings_import.py
"""

import os
import sqlite3
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


def portrait(name):
    return ("<div class='players_portrait'>\n" + name
            + "  <span class='tee_abbr'></span>\n"
            + "<div class='division_and_flight'>\n</div>\n\n</div>\n"
            + "<div class='clearfix'></div>\n")


def cell(names):
    return "<td>\n" + "".join(portrait(n) for n in names) + "</td>\n"


def row(pairs, mobile=False):
    """pairs: [(time, hole, [names]), …] — GG lays two groups per desktop
    row and repeats each one in a single-column mobile row."""
    cls = ("search_rows visible-xs hidden-sm hidden-md hidden-lg" if mobile
           else "search_rows hidden-xs")
    out = f"<tr class='{cls}' data-course-id='1'>\n"
    for t, hole, names in pairs:
        out += f"<td> {t}</td>\n<td>\n{hole}\n</td>\n" + cell(names)
    return out + "</tr>\n"


def sheet(rows_html):
    return ("<table class='table by_tee_times_table'>\n<thead>\n"
            "<tr class='do_not_hide'><td colspan='6'><h5><center>"
            "Falconhead Golf Club</center></h5></td></tr>\n"
            "<tr class='header'><th>Time</th><th>Hole</th><th>Players</th>"
            "<th class='hidden-xs'>Time</th><th class='hidden-xs'>Hole</th>"
            "<th class='hidden-xs'>Players</th></tr>\n</thead>\n<tbody>\n"
            + rows_html + "</tbody>\n</table>\n")


print("\n== the structural parser keeps every seat, in GG's order ==")

# The load-bearing case: 'Matt Larson' is printed as a plain name, not
# 'SURNAME, First'. The old comma-splitting text parse dropped him, which
# silently shifted seats 2-4 up one and broke the cart pairs.
html = sheet(
    row([("9:00 AM", "10", ["Matt Larson", "MCDONNELL, Kaleb",
                            "REED, Paul", "SHARP, Matt"]),
         ("9:09 AM", "10", ["DOGGETT, Hayden", "McCORMICK, Sam",
                            "WADE, John", "DOGGETT, Bryce"])])
    + row([("9:00 AM", "10", ["Matt Larson", "MCDONNELL, Kaleb",
                              "REED, Paul", "SHARP, Matt"])], mobile=True)
    + row([("9:09 AM", "10", ["DOGGETT, Hayden", "McCORMICK, Sam",
                              "WADE, John", "DOGGETT, Bryce"])], mobile=True))

groups = db._parse_teesheet_groups_html(html)
check("both groups parsed, mobile duplicates dropped", len(groups) == 2,
      str(groups))
check("the plain-name player survives",
      groups[0]["players"] == ["Matt Larson", "MCDONNELL, Kaleb",
                              "REED, Paul", "SHARP, Matt"],
      str(groups[0]))
check("seat order is GG's, not alphabetical",
      groups[1]["players"][0] == "DOGGETT, Hayden", str(groups[1]))
check("the slot label is the tee time", groups[0]["slot"] == "9:00 AM",
      groups[0]["slot"])

parsed = db._parse_teesheet_groups(html)
check("the dispatcher prefers the structural parser",
      parsed.get("parser") == "html", str(parsed.get("parser")))

print("\n== fivesomes survive the parse ==")

five = sheet(row([("8:30 AM", "1", ["A, One", "B, Two", "C, Three",
                                    "D, Four", "E, Five"])]))
g5 = db._parse_teesheet_groups_html(five)
check("all five seats are read", len(g5[0]["players"]) == 5,
      str(g5))

print("\n== a shotgun sheet labels by hole, not by the one repeated time ==")

shot = sheet(row([("8:00 AM", "1", ["A, One", "B, Two"]),
                  ("8:00 AM", "2", ["C, Three", "D, Four"])]))
gs = db._parse_teesheet_groups_html(shot)
check("slots become hole labels",
      [g["slot"] for g in gs] == ["Hole 1", "Hole 2"], str(gs))

print("\n== round matching ==")

score = db._score_teesheet_round_label

# GG truncates long labels, so the date is often gone — name + course
# words have to carry it. This is the real AUSTIN CHAMPIONSHIP case.
best = score("a18.4 AUSTIN CHAMPIONSHIP | Falconhead (Sat, Au...",
             "TGF AUSTIN CHAMPIONSHIP", "Falconhead", "2026-08-01")
other = score("City Champ Practice Round - Falconhead (Sun, Ju...",
              "TGF AUSTIN CHAMPIONSHIP", "Falconhead", "2026-08-01")
unrelated = score("a9.12 Roy Kizer (Tue, June  2)",
                  "TGF AUSTIN CHAMPIONSHIP", "Falconhead", "2026-08-01")
check("the right round outscores the practice round at the same course",
      best > other, f"{best} vs {other}")
check("the right round clears the confidence floor", best >= 20, str(best))
check("an unrelated round scores nothing", unrelated <= 0, str(unrelated))

# When BOTH sides carry an event code the code is decisive, and a
# disagreeing code is a hard no — never a near-miss to be outweighed.
check("matching event codes win outright",
      score("a9.20 Avery Ranch (Tue, July 28)", "a9.20 AVERY RANCH",
            "Avery Ranch", "2026-07-28") == 1000)
check("a disagreeing event code is rejected",
      score("a9.19 Teravista (Tue, July 21)", "a9.20 AVERY RANCH",
            "Avery Ranch", "2026-07-28") < 0)

# A date that DID survive truncation should push the right round up and
# the wrong one down.
same_words = score("AUSTIN CHAMPIONSHIP Falconhead (Sat, August 1)",
                   "TGF AUSTIN CHAMPIONSHIP", "Falconhead", "2026-08-01")
wrong_date = score("AUSTIN CHAMPIONSHIP Falconhead (Sat, August 8)",
                   "TGF AUSTIN CHAMPIONSHIP", "Falconhead", "2026-08-01")
check("the matching date adds confidence", same_words > wrong_date,
      f"{same_words} vs {wrong_date}")

print("\n== writing groups into event_pairings ==")

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.execute("""CREATE TABLE events (id INTEGER PRIMARY KEY, format TEXT,
                                     item_name TEXT)""")
conn.execute("INSERT INTO events (id, format, item_name) VALUES "
             "(1, '9/18 Combo', 'TGF AUSTIN CHAMPIONSHIP')")
db._ensure_pairing_tables(conn)

nine = [{"slot": "8:00 AM", "players": [{"name": f"Nine {i}"} for i in range(4)]}]
eighteen = [{"slot": "9:00 AM",
             "players": [{"name": f"Big {i}"} for i in range(5)]}]

db._write_event_pairings_from_groups(conn, 1, nine, holes="9")
db._write_event_pairings_from_groups(conn, 1, eighteen, holes="18")

rows = conn.execute("SELECT holes, cart_pos, player_name, slot_label "
                    "FROM event_pairings ORDER BY holes, cart_pos").fetchall()
check("an explicit leg does not wipe the other one",
      {r["holes"] for r in rows} == {"9", "18"},
      str([dict(r) for r in rows]))
check("the fifth seat is written",
      max(r["cart_pos"] for r in rows if r["holes"] == "18") == 5,
      str([dict(r) for r in rows]))
check("the GG tee time becomes the slot label",
      {r["slot_label"] for r in rows} == {"8:00 AM", "9:00 AM"},
      str({r["slot_label"] for r in rows}))

# Re-importing the same leg replaces it rather than stacking rows.
db._write_event_pairings_from_groups(conn, 1, eighteen, holes="18")
n18 = conn.execute("SELECT COUNT(*) c FROM event_pairings "
                   "WHERE holes = '18'").fetchone()["c"]
check("re-importing a leg replaces it", n18 == 5, str(n18))

# No explicit leg keeps the old whole-event behaviour (the nightly grab).
db._write_event_pairings_from_groups(conn, 1, nine)
after = conn.execute("SELECT DISTINCT holes FROM event_pairings").fetchall()
check("an inferred leg still replaces the whole event",
      [r["holes"] for r in after] == ["9"], str([r["holes"] for r in after]))

print("\n" + ("ALL PASS" if not FAILURES else f"{len(FAILURES)} FAILED"))
for f in FAILURES:
    print("  -", f)
sys.exit(1 if FAILURES else 0)
