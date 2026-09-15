"""Divisions & Flights + Proximity Markers (Kerry 2026-09-15, with the
two Golf Genius originals):

  "Create a Divisions & Flights report (per ROSTER buy ins, GAMES matrix,
   and flighting standards) and Proximity Markers per GAMES setup and
   course identification of par 3s. Add logos to these two. Divisions &
   Flights should produce all on one page for NET, SKINS, and GROSS as
   applicable."

The flighting standard itself lives in live_scoring.flight_plan and is
guarded there; what is pinned here is that the REPORT feeds it the right
field (roster buy-ins, index of record by customer_id), reports a game
that is not running instead of faking flights, and that the CTP rule is
applied as ratified in side-games.md.

Run: python3 test_event_reports.py
"""
import os, sqlite3, sys, tempfile, contextlib, io, logging
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
logging.getLogger("email_parser.database").setLevel(logging.ERROR)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-rep-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
EV, COURSE = 4100, 9100
c.execute("INSERT INTO courses (course_id, name, short_name, status) VALUES (?, 'The Quarry Golf Club', 'The Quarry', 'active')", (COURSE,))
c.execute("INSERT INTO events (id, item_name, event_date, chapter, course, course_id, status, format, nine_side) "
          "VALUES (?, 's9.23 The Quarry', '2026-09-15', 'San Antonio', 'The Quarry Golf Club', ?, 'active', '9 Holes', 'Front')", (EV, COURSE))
# Two tees, same pars, different yardages — par 3s at 3 and 8, and a
# THIRD par 3 at 5 so the "more par-3s than slots" rule has something to
# choose between.
PAR  = {1: 4, 2: 5, 3: 3, 4: 4, 5: 3, 6: 4, 7: 4, 8: 3, 9: 5}
YD_A = {1: 380, 2: 510, 3: 165, 4: 400, 5: 205, 6: 355, 7: 420, 8: 140, 9: 495}
for tee_id, tee, bump in ((1, 'Gold', 0), (2, 'Blue', -20)):
    c.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope, rating) VALUES (?, ?, ?, 120, 34.5)", (tee_id, COURSE, tee))
    for h in PAR:
        c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) VALUES (?, ?, ?, ?, ?)",
                  (tee_id, h, PAR[h], YD_A[h] + bump, h))
c.commit()

print("\n== proximity markers: the ratified CTP rule ==")
rep = db.event_proximity_report(EV, db_path=tmp)
check("two CTP slots on a nine", rep["slots"] == 2)
check("the course's par 3s are found", rep["par3_found"] == 3, str(rep["par3_found"]))
holes = [x["hole"] for x in rep["contests"]]
check("more par-3s than slots -> the SHORTEST are taken (8 at 130/140, 3 at 145/165)",
      holes == [3, 8], str(holes))
check("…and the 205-yard par 3 is left out", 5 not in holes, str(holes))
check("markers print in hole order", holes == sorted(holes))
check("the sheet titles read like the Golf Genius original",
      rep["contests"][0]["title"] == "Closest to the Pin - Hole 3", rep["contests"][0]["title"])
check("the yardage rides along for the tee sign", rep["contests"][0]["yardage"] is not None)
check("the choice is explained on the sheet",
      any("shortest" in n for n in rep["notes"]), str(rep["notes"]))

# Fewer par-3s than slots -> the leftover entry becomes a Longest Putt.
c.execute("UPDATE course_tee_holes SET par = 4 WHERE hole_number IN (5, 8)"); c.commit()
rep2 = db.event_proximity_report(EV, db_path=tmp)
kinds = [x["kind"] for x in rep2["contests"]]
check("one par 3 and two slots -> CTP + Longest Putt", kinds == ["ctp", "longest_putt"], str(kinds))
check("the Longest Putt is on the LAST hole of the nine",
      rep2["contests"][1]["hole"] == 9, str(rep2["contests"][1]))
check("…and that is explained too", any("Longest Putt" in n for n in rep2["notes"]), str(rep2["notes"]))

# No card on file -> say so, print nothing.
c.execute("DELETE FROM course_tee_holes"); c.commit()
rep3 = db.event_proximity_report(EV, db_path=tmp)
check("no course card -> nothing is printed and the reason is given",
      rep3["contests"] == [] and any("par-3s cannot be identified" in n for n in rep3["notes"]),
      str(rep3["notes"]))

print("\n== divisions & flights ==")
names = [(201, "Pat", "Youngs", -1.4), (202, "Luke", "Mazanec", 7.6), (203, "Adam", "Baker", 8.6),
         (204, "Gus", "Vasquez", 11.0), (205, "Chris", "Espinosa", 12.0), (206, "Scott", "Marroquin", 12.4),
         (207, "Mary", "Wade", 15.0), (208, "Richard", "Palacios", 15.2), (209, "Dan", "Stich", 16.0),
         (210, "Larry", "Anthis", 16.2), (211, "Rob", "Burlingame", 18.4), (212, "Mike", "Murphy", 33.6)]
for i, (cid, f, l, idx18) in enumerate(names):
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) VALUES (?, ?, ?, 'San Antonio', 'active')", (cid, f, l))
    # The index of record is the WHS computation, not a raw differential:
    # with three rounds it is best-1-of-3 x multiplier 1.0, adjustment
    # -2.0, then doubled for the 18-hole scale. Post three identical
    # differentials solved back from the index this player should carry,
    # so the fixture states its intent in the flighting's own units.
    c.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES (?, ?, ?)", (f"{l}, {f}", f"{f} {l}", cid))
    diff = idx18 / 2.0 + 2.0
    for _d in (10, 20, 30):
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) "
                  "VALUES (?, date('now', ?), 45, 34.5, 120, ?)", (f"{l}, {f}", f"-{_d} days", diff))
    # everyone buys NET; the first three also buy GROSS
    sg = "NET & GROSS" if i < 3 else "NET"
    c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, side_games, user_status) "
              "VALUES (?, ?, 'The Golf Fellowship', ?, ?, 's9.23 The Quarry', '2026-09-10', 'active', ?, ?, 'MEMBER')",
              (700 + i, f"u{700+i}", f"{f} {l}", cid, EV, sg))
c.commit()
_idx = db._handicap_index_18_by_customer(tmp)
check("the fixture posts the indexes it meant to (index of record, 18-hole scale)",
      all(abs(_idx.get(cid, -99) - t) < 0.051 for cid, _f, _l, t in names),
      str({cid: _idx.get(cid) for cid, _f, _l, _t in names}))
rep = db.event_flights_report(EV, db_path=tmp)
g = {x["game"]: x for x in rep["games"]}
check("the report covers NET, SKINS and GROSS", set(g) == {"individual_net", "skins", "individual_gross"}, str(sorted(g)))
check("NET buyers come from the roster", g["individual_net"]["buyers"] == 12, str(g["individual_net"]["buyers"]))
check("GROSS buyers are counted separately", g["skins"]["buyers"] == 3, str(g["skins"]["buyers"]))
check("12 NET buyers -> 2 flights per the matrix", len(g["individual_net"]["flights"]) == 2, str(g["individual_net"]))
check("the flight label names the break like Golf Genius does",
      g["individual_net"]["flights"][0]["name"].endswith("(HCP <12.0)"),
      g["individual_net"]["flights"][0]["name"])
check("…and the upper flight reads as a floor",
      g["individual_net"]["flights"][1]["name"].endswith("(HCP 12.0+)"),
      g["individual_net"]["flights"][1]["name"])
f1 = [m["name"] for m in g["individual_net"]["flights"][0]["members"]]
check("12.0 goes UP — Espinosa is not in the low flight", "Chris Espinosa" not in f1, str(f1))
check("the low flight holds everyone under 12.0", set(f1) == {"Pat Youngs", "Luke Mazanec", "Adam Baker", "Gus Vasquez"}, str(f1))
check("names print LAST, First", g["individual_net"]["flights"][0]["members"][0]["sort_name"] == "YOUNGS, Pat",
      g["individual_net"]["flights"][0]["members"][0]["sort_name"])
check("a plus handicap prints as +1.4, not -1.4",
      g["individual_net"]["flights"][0]["members"][0]["index_text"] == "+1.4",
      g["individual_net"]["flights"][0]["members"][0]["index_text"])
check("Individual Gross is REPORTED as not running, not faked",
      g["individual_gross"]["active"] is False and "16 buyers" in (g["individual_gross"]["inactive_reason"] or ""),
      str(g["individual_gross"]["inactive_reason"]))
check("…and it prints no flights", g["individual_gross"]["flights"] == [])
check("Skins below 8 buyers runs as one flight, not two",
      g["skins"]["active"] and len(g["skins"]["flights"]) == 1, str(g["skins"]["flights"]))
check("the inactive line reads 'a 9-hole event', not 'an 9-hole event'",
      "a 9-hole event" in (g["individual_gross"]["inactive_reason"] or ""),
      str(g["individual_gross"]["inactive_reason"]))
check("the index basis is stated on the sheet", "18-hole" in rep["index_basis"], rep["index_basis"])

# A buyer with no rounds cannot be flighted and must be named, not hidden.
c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) VALUES (299, 'Jeff', 'Rideout', 'San Antonio', 'active')")
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, side_games, user_status) "
          "VALUES (799, 'u799', 'The Golf Fellowship', 'Jeff Rideout', 299, 's9.23 The Quarry', '2026-09-10', 'active', ?, 'NET', 'MEMBER')", (EV,))
c.commit()
rep4 = db.event_flights_report(EV, db_path=tmp)
gn = {x["game"]: x for x in rep4["games"]}["individual_net"]
check("a buyer with no index is listed apart, never dropped into a flight",
      [u["sort_name"] for u in gn["unflighted"]] == ["RIDEOUT, Jeff"], str(gn["unflighted"]))
check("…and he still counts as a buyer", gn["buyers"] == 13, str(gn["buyers"]))

print("\n== a fixed-band label states the RULE, not the field ==")
# 8 GROSS buyers -> Skins runs 2 fixed bands at <12.0. Nobody sits
# between 12.0 and 12.4, and the label must still say 12.0: a player at
# 12.1 reading "<12.4" would place himself in the wrong flight.
for i in range(3, 8):
    cid = 300 + i
    f, l, t = "Gross", f"Buyer{i}", 12.4 + i
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) VALUES (?, ?, ?, 'San Antonio', 'active')", (cid, f, l))
    c.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES (?, ?, ?)", (f"{l}, {f}", f"{f} {l}", cid))
    for _d in (10, 20, 30):
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) "
                  "VALUES (?, date('now', ?), 45, 34.5, 120, ?)", (f"{l}, {f}", f"-{_d} days", t / 2.0 + 2.0))
    c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, side_games, user_status) "
              "VALUES (?, ?, 'The Golf Fellowship', ?, ?, 's9.23 The Quarry', '2026-09-10', 'active', ?, 'NET & GROSS', 'MEMBER')",
              (810 + i, f"u{810+i}", f"{f} {l}", cid, EV))
c.commit()
_sk = {x["game"]: x for x in db.event_flights_report(EV, db_path=tmp)["games"]}["skins"]
check("skins now runs two flights", len(_sk["flights"]) == 2, str(_sk["buyers"]))
check("the band label is the configured 12.0, not the field's 12.4",
      _sk["flights"][0]["name"] == "Flight 1 (HCP <12.0)", _sk["flights"][0]["name"])
check("…and the upper flight names the same edge",
      _sk["flights"][1]["name"] == "Flight 2 (HCP 12.0+)", _sk["flights"][1]["name"])

print("\n== the sheets carry the logo ==")
for t in ("divisions_flights.html", "proximity_markers.html"):
    src = open(f"templates/{t}", encoding="utf-8").read()
    check(f"{t} prints the official full logo", "/static/tgf-logo-r.svg" in src)
    check(f"{t} keeps its margin out of @page", "@page { size: letter" in src and "margin: 0; }" in src)
# Kerry 2026-09-15, looking at the first print: "Space the name lines out
# to fill each card. Make logo centered and 1.5x larger. Move Course and
# date info directly below logo. Remove yardage ... remove that whole line
# with Par 3 (obvious) and Closest to the hole wins (obvious). Make the
# bottom notes larger and include Only for participants of The Golf
# Fellowship's event in larger red letters on top of those notes. Also,
# 'Ball must be on the green.'"
_mk = open("templates/proximity_markers.html", encoding="utf-8").read()
check("the logo is centred and half again as big (58 -> 87px)",
      "width: 87px; height: 87px; display: block; margin: 0 auto" in _mk)
check("course and date sit directly under the logo, centred",
      ".mk-head { text-align: center;" in _mk
      and _mk.index('class="mk-logo"') < _mk.index('class="mk-course"') < _mk.index('class="mk-event"'))
check("the yardage / par-3 / closest-wins line is gone",
      "mk-sub" not in _mk and "yards" not in _mk and "closest to the hole wins" not in _mk)
check("the name lines spread to fill the card",
      ".line { flex: 1 1 0;" in _mk and ".lines { flex: 1; display: flex; flex-direction: column;" in _mk)
check("the red line names who the contest is for, above the notes",
      "Only for participants of The Golf Fellowship" in _mk
      and ".mk-warn {" in _mk and "color: #B91C1C" in _mk
      and _mk.index('class="mk-warn"') < _mk.index('class="mk-notes"'))
check("...and it prints red rather than dropping to grey",
      ".mk-title, .mk-warn { -webkit-print-color-adjust: exact" in _mk)
check("the bottom line is the green rule ALONE, at the same size as the red line",
      "Ball must be on the green." in _mk
      and "font-size: 14px; color: #111" in _mk
      and "inside the marker" not in _mk, "marker mechanics should be gone")
# House type (Kerry 2026-09-15: "We need to use more of our standard
# fonts"). The ratified rule, mailbox #44: Bitter for headings, nav/CTA
# labels, eyebrows and large stat numerals; dense data stays system sans
# with tabular figures. "Be judicious with Bitter."
_BIT = '"Bitter", Georgia, serif'
check("the marker's display type is all Bitter — course, event, title, both footer lines",
      all(f'.{k} {{' in _mk for k in ("mk-course", "mk-event", "mk-warn", "mk-notes"))
      and _mk.count(_BIT) >= 5, str(_mk.count(_BIT)))
check("…and the numbered seats stay sans with tabular figures",
      ".line .num {" in _mk and "font-variant-numeric: tabular-nums;" in _mk
      and _BIT not in _mk.split(".line .num {")[1].split("}")[0])
_df = open("templates/divisions_flights.html", encoding="utf-8").read()
check("the flights sheet sets its eyebrow and event name in Bitter too",
      _BIT in _df.split(".sheet-head .sub {")[1].split("}")[0]
      and _BIT in _df.split(".sheet-head .meta strong {")[1].split("}")[0])
check("…and every roster row stays system sans — dense data, not display",
      _BIT not in _df.split(".prow {")[1].split("}")[0]
      and "font-variant-numeric: tabular-nums" in _df)

check("proximity markers print landscape, two to a page",
      "letter landscape" in open("templates/proximity_markers.html", encoding="utf-8").read()
      and "batch(2)" in open("templates/proximity_markers.html", encoding="utf-8").read())
app = open("app.py", encoding="utf-8").read()
check("both reports are manager-gated routes",
      '@app.route("/events/<int:event_id>/divisions-flights")' in app
      and '@app.route("/events/<int:event_id>/proximity-markers")' in app
      and app.count('@require_role("manager")') >= 4)
ev_html = open("templates/events.html", encoding="utf-8").read()
check("both sit with the other PAIRINGS print buttons",
      "/divisions-flights','_blank')" in ev_html and "/proximity-markers','_blank')" in ev_html)

print("\nALL PASSED" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
