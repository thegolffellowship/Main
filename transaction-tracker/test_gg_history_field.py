"""Checks for the GG-history FIELD walk + participation series
(v2.464.0, the historical ingester lane, 2026-09-17): the calendar-widget
parser (round dates when GG truncates the selector), the round-kind
classifier, the field-board picker with its pre-ALL-boards fallback, the
affiliation split, and the season × chapter aggregation on a scratch DB.

Run: python3 test_gg_history_field.py
"""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, ".")
from email_parser import gg_history as ggh  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


# ── calendar widget ──────────────────────────────────────────────────────
CAL_HTML = """
<h4>Calendar</h4>
<table><thead><tr><th>Date</th><th>Round</th><th>Accepting Signups</th>
<th>Tee Sheet</th><th>Results</th><th>More Info</th></tr></thead><tbody>
<tr><td>Feb 24, 2024</td><td>TGF Meet &amp; Greet + Putting Contest</td>
<td>Yes</td><td></td><td></td><td><a href="#details-1232823">More Info</a>
<div id="details-1232823">Event was postponed</div></td></tr>
<tr><td class="date">Mar 26, 2024</td>
<td><div class="name">s9.1 THE QUARRY back</div>
<div class="details"><b>When</b>: Tuesday, March 26 | 5:00p Shotgun<br>
<b>Where</b>: The Quarry Golf Club<br><b>Format</b>: Individual</div></td>
<td></td><td><a href="/pages/4582853?round_id=1226498">Tee Sheet</a></td>
<td><a href="/pages/4582854?round_id=1226498">Results</a></td>
<td><a href="#details-1226498">More Info</a></td></tr>
<tr><td>Oct 15, 2024</td><td>s9.27 BRACKENRIDGE front</td><td></td>
<td><a href="/pages/4582853?round_id=1226540">Tee Sheet</a></td>
<td><a href="/pages/4582854?round_id=1226540">Results</a></td><td></td></tr>
</tbody></table>
"""
cal = ggh.parse_calendar_widget(CAL_HTML)
check("calendar: three rows parsed", len(cal) == 3, cal)
check("calendar: postponed row keeps no round id",
      cal[0]["gg_round_id"] is None and cal[0]["event_date"] == "2024-02-24")
check("calendar: full label + round id + date",
      cal[1] == {"gg_round_id": "1226498", "event_date": "2024-03-26",
                 "event_label": "s9.1 THE QUARRY back",
                 "course": "The Quarry Golf Club"}, cal[1])
check("calendar: plain row", cal[2]["gg_round_id"] == "1226540"
      and cal[2]["event_label"] == "s9.27 BRACKENRIDGE front"
      and cal[2]["event_date"] == "2024-10-15" and cal[2]["course"] is None,
      cal[2])
check("calendar: empty html → []", ggh.parse_calendar_widget("") == [])

# pagination: GG paginates the calendar ('Next →' to page=2); the fetcher
# follows page links until a page adds nothing new
PAGE2 = CAL_HTML.replace("1226540", "1226599").replace("s9.27 BRACKENRIDGE front",
                                                       "s9.28 SILVERHORN back") \
    .replace("Oct 15, 2024", "Oct 22, 2024")
NEXT = '<a href="/leagues/1/widgets/calendar?page=2&shared=false">Next</a>'
served = []


def _fake_fetch(url):
    served.append(url)
    if "page=1" in url:
        return {"status_code": 200, "final_url": url, "html": CAL_HTML + NEXT}
    if "page=2" in url:
        return {"status_code": 200, "final_url": url, "html": PAGE2}
    return {"status_code": 404, "final_url": url, "html": ""}


rounds, raws = ggh.fetch_calendar_rounds("https://x.golfgenius.com", "1", _fake_fetch)
check("pagination: page 2 followed, duplicates collapsed, 2 raw pages archived",
      len(raws) == 2 and len(served) == 2 and
      [r["gg_round_id"] for r in rounds] == [None, "1226498", "1226540", "1226599"],
      ([r["gg_round_id"] for r in rounds], served))
check("pagination: page 1 without a Next link stops after one fetch",
      len(ggh.fetch_calendar_rounds("https://x.golfgenius.com", "1",
          lambda u: {"status_code": 200, "final_url": u, "html": CAL_HTML})[1]) == 1)
check("pagination: HTTP error on page 1 → (None, status)",
      ggh.fetch_calendar_rounds("https://x.golfgenius.com", "1",
          lambda u: {"status_code": 500, "final_url": u, "html": ""})[0] is None)
check("calendar: course strips GG's leading pipe",
      ggh.parse_calendar_widget(CAL_HTML.replace("<b>Where</b>: The Quarry",
                                                 "<b>Where</b>: | The Quarry"))[1]["course"]
      == "The Quarry Golf Club")

# ── round classifier ─────────────────────────────────────────────────────
for label, want in [
    ("s9.27 BRACKENRIDGE front", "tuesday9"),
    ("a9.3 STAR RANCH back", "tuesday9"),
    ("s1 THE QUARRY back", "tuesday9"),
    ("s15 OLYMPIA HILLS back", "tuesday9"),
    ("s8f SILVERHORN back", "tuesday9"),
    ("a10 BLUEBONNET front", "tuesday9"),
    ("as18.6 DELAWARE SPRINGS", "saturday18"),
    ("s18.4 GOLF CLUB OF TEXAS", "saturday18"),
    ("a18.2 RIVERSIDE", "saturday18"),
    ("MATCH 63 - CHANDLER v TALAMANTEZ", "match"),
    ("MATCH - HANSON v CHANDLER", "match"),
    ("M61 - PLAYBACK SEMIFINAL", "match"),
    ("Match 34 | SCHLUETER v HALL", "match"),
    ("e1 THE QUARRY front", "tuesday9"),
    ("e12 CANYON SPRINGS back", "tuesday9"),
    ("THE HANDICAPPER 18", "other"),
    ("10th TGF CHAMPIONSHIP day one", "other"),
    ("7th HOPE CLASSIC", "other"),
    ("MATCH 64a - POWELL v TORRES", "match"),
    ("east | SILVERHORN front", "tuesday9"),
    ("west | THE QUARRY back", "tuesday9"),
    ("east/west | SILVERHORN front", "tuesday9"),
    ("north | STAR RANCH front", "tuesday9"),
    ("south | KIZER back", "tuesday9"),
    ("s9 OLMOS BASIN front | The Dogfather", "tuesday9"),
    ("a9 FOREST CREEK front", "tuesday9"),
    ("s18 FALL KICKOFF silverhorn", "saturday18"),
    ("SKINS NIGHT 3 | San Pedro", "other"),
    ("FALL CHAMPIONSHIP olympia hills", "other"),
    ("MATCHES - SAN ANTONIO Match Play", "other"),
    ("CHAMPIONSHIP MATCH FREUND v X", "match"),
    ("POINTS RESET", "admin"),
    ("SAN ANTONIO KICKOFF olmos basin", "other"),
    ("2019 TGF CHAMPIONSHIP | day 1", "other"),
    ("THE HANDICAPPER san antonio", "other"),
    ("TWO MAN 2 | OAKS", "other"),
    ("", "other"),
]:
    got = ggh.classify_round_label(label)
    check(f"classify {label!r} → {want}", got == want, got)

# ── board picker ─────────────────────────────────────────────────────────
def _links(*labels):
    return [{"text": t, "href": f"https://x.golfgenius.com/v2tournaments/{i}?round_index=1"}
            for i, t in enumerate(labels, 1)]

modern = _links("as18.6 FALL POINTS - SAN ANTONIO Fall", "as18.6 MVP 18 $",
                "CART Net 18 $", "INDIVIDUAL Net 18 $", "SKINS Gross 18 $",
                "ALL Net", "ALL Gross", "GROSS front", "Adjustments",
                "Closest to Pin #5")
boards, basis, labels = ggh._pick_field_boards(modern)
check("picker: modern round → ALL boards only",
      basis == "all_boards" and [b["text"] for b in boards] == ["ALL Net", "ALL Gross"],
      (basis, [b["text"] for b in boards]))
old = _links("Player Purse Summary", "s1 POINTS RACE", "s1 MVP $",
             "CART Net $", "TEAM Net $", "INDIVIDUAL Net $ - s1 MEMBER Games",
             "INDIVIDUAL Gross $ - s1 ALL PLAY Games", "SKINS 1/2 Net $",
             "s8f SCORES net - FALL POINTS net", "GROSS front", "NET back",
             "SAN ANTONIO Net", "THE FELLOWSHIP CUP", "JULY Points",
             "AUSTIN NET Points Race", "as18.6 FALL POINTS - SAN ANTONIO Fall",
             "Closest to Pin #13", "Longest Putt #2", "HOLE IN ONE #12",
             "Adjustments")
boards, basis, labels = ggh._pick_field_boards(old)
check("picker: pre-ALL era → per-round individual boards only (no cumulative "
      "standings, no team/MVP/proximity)",
      basis == "fallback" and [b["text"] for b in boards] == [
          "INDIVIDUAL Net $ - s1 MEMBER Games",
          "INDIVIDUAL Gross $ - s1 ALL PLAY Games", "SKINS 1/2 Net $",
          "s8f SCORES net - FALL POINTS net", "GROSS front", "NET back"],
      (basis, [b["text"] for b in boards]))
boards, basis, labels = ggh._pick_field_boards(_links("Team Points Summary", "MATCH 1"))
check("picker: nothing usable → none", basis == "none" and boards == [] and len(labels) == 2)

# ── affiliation split ────────────────────────────────────────────────────
for raw, want in [("ROHRMANN, Lance TGF San Antonio", ("ROHRMANN, Lance", "TGF San Antonio")),
                  ("Esselborn, Rob Former", ("Esselborn, Rob", "Former")),
                  ("Villa, Mark Guest", ("Villa, Mark", "Guest")),
                  ("NIESTER, Kerry", ("NIESTER, Kerry", ""))]:
    got = ggh._split_affiliation(raw)
    check(f"affiliation {raw!r}", got == want, got)

# ── participation series on a scratch DB ─────────────────────────────────
tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp.close()
conn = sqlite3.connect(tmp.name)
conn.row_factory = sqlite3.Row
conn.execute("CREATE TABLE gg_raw_archive (id INTEGER PRIMARY KEY, url TEXT, "
             "fetched_at TEXT, body_gz BLOB)")
conn.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, "
             "customer_name TEXT)")
ggh.ensure_gg_history_tables(conn)
conn.execute("INSERT INTO gg_history_portals (id, subdomain, chapter, season, "
             "kind, brand, status) VALUES (1,'tgf-sa2019','San Antonio','2019',"
             "'season','TGF','alive'), (2,'tgf-champ25',NULL,'2025','oneoff',"
             "'TGF','alive')")


def _event(eid, label, rid, basis, rows):
    conn.execute("INSERT INTO gg_history_events (id, portal_id, season, chapter, "
                 "event_label, event_date, gg_round_id) VALUES (?,1,'2019',"
                 "'San Antonio',?,?,?)", (eid, label, "2019-04-0" + str(eid), rid))
    conn.execute("INSERT INTO gg_history_pages (portal_id, gg_page_id, page_kind, "
                 "widget_type, fetch_status) VALUES (1, ?, 'event_field', ?, 'done')",
                 (f"field:{rid}", basis))
    for game, name, aff, cid, team in rows:
        conn.execute("INSERT INTO gg_history_results (gg_event_id, game_label, "
                     "player_name, customer_id, team_label, raw_row) VALUES "
                     "(?,?,?,?,?,?)", (eid, game, name, cid, team,
                                      json.dumps({"src": "field_walk", "aff": aff,
                                                  "row": []})))


# event 1: ALL boards, 3 players (one on both boards, one guest)
_event(1, "s1 THE QUARRY back", "r1", "all_boards", [
    ("ALL Net", "NIESTER, Kerry", "TGF San Antonio", 7, None),
    ("ALL Net", "Villa, Mark", "Guest", None, None),
    ("ALL Gross", "NIESTER, Kerry", "TGF San Antonio", 7, None),
    ("ALL Gross", "ANTHIS, Larry", "Former", 9, None),
    ("SKINS $", "SOMEONE, Else", "TGF San Antonio", None, None),  # not the field
    ("CART Net $", "A + B", "", None, "A + B"),
])
# event 2: fallback basis, 5 players across two boards
_event(2, "s2 SILVERHORN front", "r2", "fallback", [
    ("INDIVIDUAL Net $", "NIESTER, Kerry", "TGF San Antonio", 7, None),
    ("INDIVIDUAL Net $", "ANTHIS, Larry", "Former", 9, None),
    ("INDIVIDUAL Gross $", "ANTHIS, Larry", "Former", 9, None),
    ("INDIVIDUAL Gross $", "HOGUE, Jay", "TGF Austin", 11, None),
    ("INDIVIDUAL Gross $", "WHITE, John", "TGF San Antonio", None, None),
    ("INDIVIDUAL Gross $", "FEHLIS, Chuck", "TGF San Antonio", None, None),
    ("SAN ANTONIO Net", "SEASONLONG, Sue", "TGF San Antonio", None, None),  # cumulative: ignored
    ("THE FELLOWSHIP CUP", "SEASONLONG, Sue", "TGF San Antonio", None, None),
])
# event 3: Saturday 18, 2 players — counts in 'all' not 'tue'
_event(3, "s18.1 TAPATIO SPRINGS", "r3", "all_boards", [
    ("ALL Net", "NIESTER, Kerry", "TGF San Antonio", 7, None),
    ("ALL Net", "NEWGUY, Sam", "Guest", None, None),
])
# event 4: match-play round — excluded entirely
_event(4, "MATCH 12 - A v B", "r4", "fallback", [
    ("MATCH 12", "NIESTER, Kerry", "TGF San Antonio", 7, None)])
# event 5: walked, empty (postponed) — excluded
_event(5, "s3 OLMOS BASIN front", "r5", "none", [])
# event 6: NOT walked (no field: page) — excluded
conn.execute("INSERT INTO gg_history_events (id, portal_id, season, chapter, "
             "event_label, gg_round_id) VALUES (6,1,'2019','San Antonio',"
             "'s4 X','r6')")
conn.execute("INSERT INTO gg_history_pages (portal_id, gg_page_id, page_kind, "
             "fetch_status) VALUES (1,'field:r6','event_field','pending')")
conn.commit()
conn.close()

res = ggh.participation_series("2019", "2026", db_path=tmp.name)
rows = res["gg_history"]
check("series: one SA 2019 row (one-off portal excluded)",
      len(rows) == 1 and rows[0]["chapter"] == "San Antonio", rows)
r = rows[0]
check("series: events all=3 tue=2", r["events_all"] == 3 and r["events_tue"] == 2, r)
check("series: tuesday mean/median 4.0/4", r["mean_tue"] == 4.0 and r["median_tue"] == 4, r)
check("series: all mean 3.3 median 3", r["mean_all"] == 3.3 and r["median_all"] == 3, r)
check("series: player_rounds 10", r["player_rounds"] == 10, r)
check("series: distinct players 7 (SKINS-only name is not the field)",
      r["distinct_players"] == 7, r)
check("series: member-ever 5 (TGF*/Former), linked 3",
      r["distinct_member_ever"] == 5 and r["distinct_linked"] == 3, r)
check("series: fallback events flagged = 1", r["fallback_basis_events"] == 1, r)
check("series: unwalked rounds = 1", r["rounds_unwalked"] == 1, r)
# reset marks field rounds redo (nothing deleted)
_c = sqlite3.connect(tmp.name)
_before = _c.execute("SELECT COUNT(*) FROM gg_history_results").fetchone()[0]
_c.close()
rr = ggh.reset_portal_field("tgf-sa2019", db_path=tmp.name)
_c = sqlite3.connect(tmp.name)
_after = _c.execute("SELECT COUNT(*) FROM gg_history_results").fetchone()[0]
_redo = _c.execute("SELECT COUNT(*) FROM gg_history_pages WHERE fetch_status='redo'").fetchone()[0]
_c.close()
check("reset: 5 done rounds → redo, rows untouched",
      rr["rounds_reset"] == 5 and _redo == 5 and _before == _after, (rr, _redo, _before, _after))
check("series: tracker rows absent on bare DB → tracker_error, no crash",
      res["tracker"] == [] and "tracker_error" in res, res.get("tracker_error"))
check("series: median helper", ggh._median([]) is None and ggh._median([3, 1, 2]) == 2
      and ggh._median([1, 2, 3, 4]) == 2.5)

# ── Tracker rows on a scratch DB with items/events ───────────────────────
conn = sqlite3.connect(tmp.name)
conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, "
             "event_date TEXT, chapter TEXT)")
conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, customer_id INTEGER, "
             "event_id INTEGER, item_name TEXT, order_date TEXT, "
             "transaction_status TEXT, parent_item_id INTEGER)")
conn.execute("INSERT INTO events VALUES (1,'s9.1 THE QUARRY','2025-03-25','San Antonio'),"
             "(2,'a9.1 STAR RANCH','2025-03-25','Austin'),"
             "(3,'as18.1 VAALER','2025-04-05','San Antonio'),"
             "(4,'s9.99 FUTURE','2099-01-01','San Antonio')")
conn.executemany("INSERT INTO items (customer_id, event_id, item_name, order_date, "
                 "transaction_status, parent_item_id) VALUES (?,?,?,?,?,?)", [
    (1, 1, "s9.1 THE QUARRY", "2025-03-20", "active", None),
    (2, 1, "s9.1 THE QUARRY", "2025-03-20", "rsvp_only", None),
    (3, 1, "s9.1 THE QUARRY", "2025-03-20", "credit", None),      # excluded
    (1, None, "s9.1 the quarry ", "2025-03-21", "active", 1),   # child row excluded
    (4, 2, "a9.1 STAR RANCH", "2025-03-20", "active", None),
    (1, 3, "as18.1 VAALER", "2025-04-01", "active", None),
    (1, 4, "s9.99 FUTURE", "2025-04-01", "active", None),      # future excluded
    (1, None, "MEMBERSHIP 2025", "2025-01-10", "active", None),
    (2, None, "MEMBERSHIP 2023", "2023-01-10", "active", None),  # stale
    (None, 1, "s9.1 THE QUARRY", "2025-03-20", "active", None),  # anonymous
])
conn.commit()
conn.close()
res = ggh.participation_series("2025", "2026", db_path=tmp.name)
tr = {(t["season"], t["chapter"]): t for t in res["tracker"]}
check("tracker: two chapter rows for 2025", set(tr) == {("2025", "San Antonio"), ("2025", "Austin")}, tr)
sa = tr[("2025", "San Antonio")]
check("tracker SA: events all=2 tue=1, tue mean 2", sa["events_all"] == 2 and sa["events_tue"] == 1
      and sa["mean_tue"] == 2.0, sa)
check("tracker SA: distinct players 2, members 1 (stale membership not counted)",
      sa["distinct_players"] == 2 and sa["distinct_members"] == 1, sa)
check("tracker Austin: one event, one player", tr[("2025", "Austin")]["player_rounds"] == 1)
os.unlink(tmp.name)

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL PASS")
