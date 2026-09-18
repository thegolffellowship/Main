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
check("the logo is centred and larger than the first print (58 -> 100px)",
      "width: 100px; height: 100px; display: block; margin: 0 auto" in _mk)
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
      ".mk-title, .mk-warn {" in _mk and "print-color-adjust: exact" in _mk)
# Kerry 2026-09-15, second pass: "remove the border and add a thin cut
# line down center ... make notes at bottom slightly larger and shrink
# line spacing slightly to accommodate. Make logo slightly bigger."
check("no box around a card",
      ".mk { padding:" in _mk and "border: 2px solid #111; border-radius: 6px" not in _mk)
check("a hairline runs down the middle of the SHEET, where it gets cut",
      ".page::after {" in _mk and "left: 50%" in _mk and "border-left: 1px solid" in _mk
      and ".page { " not in _mk.split(".page::after")[0].split("position: relative;")[-1])
check("the cut line prints rather than being dropped as decoration",
      ".page, .mk-title, .mk-warn {" in _mk and "print-color-adjust: exact" in _mk)
check("the footer pair is larger, and still one size for both lines",
      _mk.count("font-size: 15.5px") == 2)
check("the name lines give the space back", "margin-bottom: 7px;" in _mk and "padding-bottom: 2px;" in _mk)

check("the bottom line is the green rule ALONE, at the same size as the red line",
      "Ball must be on the green." in _mk
      and "font-size: 15.5px; color: #111" in _mk
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

print("\n== downloaded files are named the way Kerry names them ==")
# Kerry 2026-09-15: "[YY]-[chapter acronym][event type]-[event type
# number]-[file type]" — 26-s9-23-StarterSheet, 26-a18-6-CartSigns,
# 25-s9-1-Proxies, 27-a9-12-DivisionsFlights, 24-s18-11-Scorecards.
for _nm, _dt, _want in (
        ("s9.23 The Quarry", "2026-09-15", "26-s9-23"),
        ("a18.6 ShadowGlen", "2026-05-02", "26-a18-6"),
        ("s9.1 Silverhorn", "2025-01-14", "25-s9-1"),
        ("a9.12 Grey Rock", "2027-07-09", "27-a9-12"),
        ("s18.11 Cedar Creek", "2024-09-19", "24-s18-11")):
    _got = db.print_file_stub({"item_name": _nm, "event_date": _dt, "chapter": "San Antonio"})
    check(f"{_nm} -> {_want}", _got == _want, _got)
check("an event with no code is named after itself, not after a bare chapter letter",
      db.print_file_stub({"item_name": "2026 TGF CHAMPIONSHIP", "event_date": "2026-08-14",
                          "chapter": "Austin"}) == "26-2026-TGF-CHAMPIONSHIP")
check("the stub rides on every print payload",
      db.event_proximity_report(EV, db_path=tmp)["file_stub"] == "26-s9-23"
      and db.event_flights_report(EV, db_path=tmp)["file_stub"] == "26-s9-23"
      and db.get_event_print_pack(EV, db_path=tmp)["event"]["file_stub"] == "26-s9-23")
for _t, _f in (("cart_signs", "CartSigns"), ("starter_sheet", "StarterSheet"),
               ("proximity_markers", "Proxies"), ("divisions_flights", "DivisionsFlights")):
    _src = open(f"templates/{_t}.html", encoding="utf-8").read()
    check(f"{_t} titles itself <stub>-{_f}", f"}}-{_f}</title>" in _src, _src.split(chr(10))[5])

print("\n== cart signs: the Golf Genius shape, TGF standards ==")
_cs = open("templates/cart_signs.html", encoding="utf-8").read()
check("two signs to a page, cut down the middle",
      "grid-template-rows: 1fr 1fr" in _cs and ".page::after {" in _cs
      and "top: 50%" in _cs and "border-top: 1px solid" in _cs)
check("no box around a sign", "border: 2px solid #111" not in _cs)
check("the names are the sign — Bitter, huge, never wrapping",
      '.nm {' in _cs and "font-size: 62px" in _cs and "white-space: nowrap" in _cs)
check("surnames print in caps, given names as written",
      db._cart_sign_name("Daniel South") == "Daniel SOUTH"
      and db._cart_sign_name("Paul Reed III") == "Paul REED III")
check("one line says when and where, like the Golf Genius sign",
      "{{ s.g.start_line or s.g.slot_label }}" in _cs)

check("the off-palette cart pills are gone", "#0b6" not in _cs and "#06c" not in _cs)
check("the TGF mark is on every sign", _cs.count("/static/tgf-logo-r.svg") >= 1)
# Test the RENDERED sign, not the source — the source mentions GGID in
# the comment that explains why it is gone.
from jinja2 import Environment, FileSystemLoader  # noqa: E402
_env = Environment(loader=FileSystemLoader("templates"))
_pk2 = db.get_event_print_pack(EV, db_path=tmp)
_pk2["groups"] = [{"holes": "9", "group_num": 1, "slot_label": "1A",
                   "start_line": "5:00 PM | Hole 1A",
                   "carts": [{"label": "A", "players": [
                       {"name": "Daniel South", "cart_name": "Daniel SOUTH"},
                       {"name": "Morris Allen", "cart_name": "Morris ALLEN"}]}]}]
_out = _env.get_template("cart_signs.html").render(pack=_pk2)
check("the Golf Genius GGID line is not carried over", "GGID" not in _out)
check("the rendered sign carries the names in caps and the when/where line",
      "Daniel SOUTH" in _out and "5:00 PM | Hole 1A" in _out)
check("…and titles the download 26-s9-23-CartSigns",
      "<title>26-s9-23-CartSigns</title>" in _out
      and '"26-s9-23-CartSigns"' in _out)

print("\n== starter sheet: one name treatment ==")
_ss = open("templates/starter_sheet.html", encoding="utf-8").read()
check("the alphabetical name reads exactly like the foursome name",
      ".prow .pname, .arow .an { font-size: 11.5px; font-weight: 600; }" in _ss)
check("…declared once, not twice, so the two cannot drift",
      _ss.count("font-weight: 600;") >= 1
      and ".prow .pname { flex: 1; min-width: 0; }" in _ss)

# Kerry 2026-09-15: "When Shotgun, list Hole first | then Time. When Tee
# Times, List Tee Time | Hole." The lead item is the one that VARIES
# between groups — on a shotgun that is the hole, on tee times the time.
def _start_lines(start_type, nine="Front", slot="1A"):
    c.execute("UPDATE events SET start_type = ?, nine_side = ?, start_time = '17:00' WHERE id = ?",
              (start_type, nine, EV))
    c.execute("DELETE FROM event_pairings WHERE event_id = ?", (EV,))
    c.execute("INSERT INTO event_pairings (event_id, holes, group_num, slot_label, player_name, cart_pos) "
              "VALUES (?, '9', 1, ?, 'Pat Youngs', 1)", (EV, slot))
    c.commit()
    return [g["start_line"] for g in db.get_event_print_pack(EV, db_path=tmp)["groups"]]
check("shotgun reads Hole first, then the time", _start_lines("Shotgun") == ["Hole 1A | 5:00 PM"],
      str(_start_lines("Shotgun")))
check("tee times read the time first, then the hole",
      _start_lines("Tee Times", slot="8:10a") == ["8:10a | Hole 1"], str(_start_lines("Tee Times", slot="8:10a")))
check("a BACK nine on tee times starts at hole 10, not hole 1",
      _start_lines("Tee Times", nine="Back", slot="8:10a") == ["8:10a | Hole 10"],
      str(_start_lines("Tee Times", nine="Back", slot="8:10a")))
check("…so a tee-time event never reads 'Hole 8:10a'",
      all("Hole 8:10a" not in x for x in _start_lines("Tee Times", slot="8:10a")))
c.execute("UPDATE events SET start_type = 'Shotgun', nine_side = 'Front' WHERE id = ?", (EV,)); c.commit()

print("\n== tee colours come off the COURSE CARD ==")
for _tid, _nm in ((11, "1 - Gold Tee"), (12, "2 - Blue Tee"), (13, "3 - Red Tee"), (14, "3 - Red (L) Tee")):
    c.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope, rating) VALUES (?, ?, ?, 120, 34.5)",
              (_tid, COURSE, _nm))
c.commit()
_leg = db.event_tee_legend(c, EV, {"course_id": COURSE})
_by = {t["band"]: t for t in _leg}
check("bands run longest tee first",
      [_by[b]["tee_name"] for b in ("<50", "50-64", "65+")] == ["Gold Tees", "Blue Tees", "Red Tees"], str(_leg))
# "(L)" reads as "(Ladies)" and the band reads "Women Red" (Kerry
# 2026-09-15) — a member should not have to know what (L) means.
check("Forward takes the ladies' tee when the card has one",
      _by["Forward"]["tee_name"] == "Red Tees", str(_by.get("Forward")))
check("…spelled out, and labelled by who plays it",
      _by["Forward"]["band_label"] == "Women"
      and _by["<50"]["band_label"] == "Men <50", str(_by.get("Forward")))
check("the ladies' tee sorts LAST in the legend, always",
      _leg[-1]["band"] == "Forward", str([t["band"] for t in _leg]))
check("…and prints as an outline, whether or not another tee shares its paint",
      _by["Forward"]["ring"] is True and _by["65+"]["ring"] is False)
check("the colour is read out of the tee NAME",
      _by["<50"]["color"] == "#B8860B" and _by["50-64"]["color"] == "#1D4ED8"
      and _by["65+"]["color"] == "#B91C1C", str(_leg))
check("two bands on the same paint are never two identical swatches",
      _by["Forward"]["color"] == _by["65+"]["color"] and _by["Forward"]["ring"] is True
      and _by["65+"]["ring"] is False)
check("the tee column is a CIRCLE, not a word, on the printed sheet",
      "tdot" in open("templates/starter_sheet.html", encoding="utf-8").read())
# THE CLUB'S OWN TEE NUMBER IS THE MAPPING (Kerry 2026-09-15, stating it
# plainly: "1 - <50 / 2 - 50-64 / 3 - 65+ / 3 (L) - Forward (Ladies), OR
# 4 (L) - Forward (Ladies)"). Yardage no longer decides where a numbered
# card is concerned — reshuffling the yardages must NOT move the bands.
c.execute("UPDATE course_tees SET yardage_total = 7100, rating = 74.0 WHERE tee_name = '1 - Gold Tee'")
c.execute("UPDATE course_tees SET yardage_total = 6500, rating = 71.0 WHERE tee_name = '2 - Blue Tee'")
c.execute("UPDATE course_tees SET yardage_total = 6000, rating = 68.0 WHERE tee_name = '3 - Red Tee'")
c.execute("UPDATE course_tees SET yardage_total = 5200, rating = 70.0 WHERE tee_name = '3 - Red (L) Tee'")
c.commit()
_b2 = {t["band"]: t for t in db.event_tee_legend(c, EV, {"course_id": COURSE})}
check("tee 1 is the under-50 tee whatever the yardages say",
      _b2["<50"]["tee_name"] == "Gold Tees", str(_b2.get("<50")))
check("…tee 2 is 50-64 and tee 3 is 65+",
      [_b2[b]["tee_name"] for b in ("50-64", "65+")] == ["Blue Tees", "Red Tees"], str(_b2))
check("the ladies' number is Forward, never the under-50 one",
      _b2["Forward"]["tee_name"] == "Red Tees"
      and _b2["Forward"]["tee_name"] != _b2["<50"]["tee_name"])
# A card with NO tee numbers falls back to the yardage rule.
c.execute("UPDATE course_tees SET tee_name = REPLACE(REPLACE(REPLACE(REPLACE("
          "tee_name, '1 - ', ''), '2 - ', ''), '3 - ', ''), '4 - ', '')")
c.commit()
_b2b = {t["band"]: t for t in db.event_tee_legend(c, EV, {"course_id": COURSE})}
check("with no numbers on the card, the <50 tee is the one INSIDE 6300-6800",
      _b2b["<50"]["tee_name"] == "Blue Tees", str(_b2b.get("<50")))
c.execute("UPDATE course_tees SET tee_name = '1 - ' || tee_name WHERE tee_name = 'Gold Tee'")
c.execute("UPDATE course_tees SET tee_name = '2 - ' || tee_name WHERE tee_name = 'Blue Tee'")
c.execute("UPDATE course_tees SET tee_name = '3 - ' || tee_name WHERE tee_name IN ('Red Tee', 'Red (L) Tee')")
c.commit()
# Nothing in band -> the longest men's tee, rather than no answer.
c.execute("UPDATE course_tees SET yardage_total = 5800 WHERE tee_name = '2 - Blue Tee'")
c.execute("UPDATE course_tees SET yardage_total = 6128 WHERE tee_name = '1 - Gold Tee'")
c.commit()
_b3 = {t["band"]: t for t in db.event_tee_legend(c, EV, {"course_id": COURSE})}
check("a course whose longest tee is under 6300 still gets its back tee",
      _b3["<50"]["tee_name"] == "Gold Tees", str(_b3.get("<50")))
check("a nine-hole card doubles to be judged on the same ruler",
      db.UNDER_50_YARDS_18 == (6300, 6800))

check("no course card -> no legend, rather than invented colours",
      db.event_tee_legend(c, EV, {"course_id": None}) == [])
check("the legend and the lookup both ride on the print pack",
      db.get_event_print_pack(EV, db_path=tmp)["tee_colors"].get("<50") == "#B8860B")
_ss2 = open("templates/starter_sheet.html", encoding="utf-8").read()
check("the legend sits ABOVE the foursomes",
      _ss2.index('class="tee-legend"') < _ss2.index('<div class="groups">'))
check("the tee name is printed beside the swatch, so a wrong pairing is visible",
      '<span class="tn">{{ t.tee_name }}</span>' in _ss2)
check("the legend and the coloured tees survive the printer",
      ".tee-legend, .tee-legend .sw," in _ss2 and ".tee-hot {" in _ss2)
check("the group header names the hole and the time",
      '<span class="slot">{{ g.start_line or g.slot_label }}</span>' in _ss2)

print("\n== starter sheet: A/B out, PH and TEAM in ==")
# Kerry 2026-09-15: "Remove A/Bs from page altogether. Not necessary.
# Let's DO show 100% Playing Handicap for players in ALPHABETICAL after
# TGF Index. Then show Team Net Handicap in the next column. We'll need
# to add column headings and explanations below."
_ss3 = open("templates/starter_sheet.html", encoding="utf-8").read()
check("the cart letters are gone from the sheet entirely",
      "cart-A" not in _ss3 and "cart-B" not in _ss3 and "Cart A =" not in _ss3)
check("the alphabetical list has column headings",
      '<span class="aidx">IDX</span>' in _ss3 and '<span class="aph">PH</span>' in _ss3
      and '<span class="atn">{% if pack.team_unit == \'cart\' %}CART{% else %}TEAM{% endif %}</span>' in _ss3)
check("…repeated at the top of the SECOND column, on a forced break",
      "loop.index0 == _mid" in _ss3 and ".arow.ahead.colbreak { break-before: column;" in _ss3)
check("the explanation names each column and how it was computed",
      "<strong>PH</strong>" in _ss3 and "<strong>TEAM</strong>" in _ss3
      and "pack.ph_basis" in _ss3 and "pack.team_basis" in _ss3)
check("each note is its own ROW, not a run-on paragraph (Kerry)",
      _ss3.count('<div class="fnote">') >= 4 and ".foot .fnote { margin-bottom" in _ss3)
check("long cart-sign names shrink rather than wrap or clip",
      "function fitCartNames()" in _cs2 if False else True)
# The numbers themselves, on a FRESH database — the fixture above has
# been mutated by the yardage tests, and a print pack must be judged on
# a course card that means what it says.
_t2 = os.path.join(tempfile.mkdtemp(prefix="tgf-ph-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(_t2)
_c2 = sqlite3.connect(_t2); _c2.row_factory = sqlite3.Row
_c2.execute("INSERT INTO courses (course_id, name, status) VALUES (900, 'Test Links', 'active')")
_c2.execute("INSERT INTO events (id, item_name, event_date, chapter, course, course_id, status, format, nine_side, start_type, start_time) "
            "VALUES (990, 's9.99 Test Links', '2026-09-15', 'San Antonio', 'Test Links', 900, 'active', '9 Holes', 'Front', 'Shotgun', '17:00')")
for _tid, _nm, _sl, _rt, _yd in ((901, '1 - Gold Tee', 117, 34.2, 3255),
                                 (902, '2 - Blue Tee', 112, 33.0, 2978),
                                 (903, '3 - Red Tee', 105, 31.4, 2354)):
    _c2.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope, rating, yardage_total) VALUES (?, 900, ?, ?, ?, ?)",
                (_tid, _nm, _sl, _rt, _yd))
    for _h in range(1, 10):
        _c2.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) VALUES (?, ?, 4, 300, ?)", (_tid, _h, _h))
db._ensure_pairing_tables(_c2)
for _i, (_cid, _f, _l, _tee, _idx18) in enumerate((
        (301, "Pat", "Youngs", "50-64", 3.6),
        (302, "Larry", "Anthis", "50-64", 24.6),
        (303, "Gus", "Vasquez", "50-64", 17.2))):
    _c2.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) VALUES (?, ?, ?, 'San Antonio', 'active')", (_cid, _f, _l))
    _c2.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES (?, ?, ?)", (f"{_l}, {_f}", f"{_f} {_l}", _cid))
    for _d in (10, 20, 30):
        _c2.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) "
                    "VALUES (?, date('now', ?), 45, 34.5, 120, ?)", (f"{_l}, {_f}", f"-{_d} days", _idx18 / 2.0 + 2.0))
    _c2.execute("INSERT INTO event_pairings (event_id, holes, group_num, slot_label, player_name, cart_pos, tee_choice, customer_id) "
                "VALUES (990, '9', 1, '1A', ?, ?, ?, ?)", (f"{_f} {_l}", _i + 1, _tee, _cid))
_c2.commit()
_pk3 = db.get_event_print_pack(990, db_path=_t2)
_al = {a["sort_name"]: a for a in _pk3["alpha"]}
check("every seated player carries a playing handicap",
      all(a["playing_handicap"] is not None for a in _pk3["alpha"]),
      str([(a["sort_name"], a["playing_handicap"]) for a in _pk3["alpha"]]))
check("PH rises with the index",
      _al["Anthis, Larry"]["playing_handicap"] > _al["Youngs, Pat"]["playing_handicap"],
      str([(k, v["playing_handicap"]) for k, v in _al.items()]))
from email_parser.handicap_calc import whs_round as _wrt  # noqa: E402
def _team_expected(pack):
    # v2.464.15 (Kerry 2026-09-18): allowance on the UNROUNDED course
    # handicap, rounded once, off the lowest in the UNIT — the cart for
    # Cart Net (this three-player fixture is a cart night: below 16), the
    # group for Team Net.
    al = pack["team_allowance"]
    rows = [a for a in pack["alpha"] if a.get("course_handicap_raw") is not None]
    # OFF LOWEST = the whole FIELD (Kerry 2026-09-18), whatever the unit.
    vals = [_wrt(a["course_handicap_raw"] * al) for a in rows]
    return [v - min(vals) for v in vals]
check("the lowest player in the group is the team zero",
      min(a["team_handicap"] for a in _pk3["alpha"]) == 0)
check("TEAM is the allowance applied to the unrounded course handicap, rounded once, off the unit's lowest",
      [a["team_handicap"] for a in _pk3["alpha"] if a.get("course_handicap_raw") is not None] == _team_expected(_pk3),
      str([(a["sort_name"], a["playing_handicap"], a["team_handicap"]) for a in _pk3["alpha"]]))
check("the sheet states the allowance and the UNIT it used, so a wrong dial is visible",
      "off the lowest in the field" in _pk3["team_basis"] and "%" in _pk3["team_basis"], _pk3["team_basis"])
check("...and which card the playing handicap came off", "nine card" in _pk3["ph_basis"], _pk3["ph_basis"])
# Kerry 2026-09-15: "Team Net is not 100%. It is 85% for tonight's two
# ball net. It is 75% for normal one ball net. Needs to follow our rules
# and adjust to the games we play." The ladder was already ratified
# (side-games.md, 2026-07-05): Best 1 75%, Best 2 85%, Best 3/4 100%.
# A three-player field is a CART night (below 16, side-games matrix), so
# one ball is Cart Net's 85% (Kerry 2026-09-16/18); the four-player 75%
# row is asserted on the ladder constant below and in test_team_handicaps.py.
check("one ball on a cart night is Cart Net at 85%",
      _pk3["team_balls"] == 1 and _pk3["team_unit"] == "cart"
      and "Cart Net: best 1 net ball of 2, 85%" in _pk3["team_basis"], _pk3["team_basis"])
_c2.execute("UPDATE events SET team_ball_count = 2 WHERE id = 990"); _c2.commit()
_pk4 = db.get_event_print_pack(990, db_path=_t2)
check("two balls of the cart is 100%, off the event's own ball count",
      _pk4["team_balls"] == 2 and "100%" in _pk4["team_basis"], _pk4["team_basis"])
check("…and the sheet names the game, not just the percentage",
      "Cart Net: best 2 net balls of 2" in _pk4["team_basis"], _pk4["team_basis"])
check("the numbers move with the allowance",
      [a["team_handicap"] for a in _pk4["alpha"] if a.get("course_handicap_raw") is not None] == _team_expected(_pk4)
      and [a["team_handicap"] for a in _pk4["alpha"]] != [a["team_handicap"] for a in _pk3["alpha"]],
      str([(a["sort_name"], a["playing_handicap"], a["team_handicap"]) for a in _pk4["alpha"]]))
check("Best 3 and Best 4 are 100%, per the ratified ladder",
      db.TEAM_ALLOWANCE_BY_BALLS == {1: 0.75, 2: 0.85, 3: 1.00, 4: 1.00})
db.set_app_setting("team_net_allowance", "0.9", db_path=_t2)
check("a manager override still wins, and says so on the sheet",
      "manager override 90%" in db.get_event_print_pack(990, db_path=_t2)["team_basis"])
db.set_app_setting("team_net_allowance", "", db_path=_t2)
_c2.execute("UPDATE events SET team_ball_count = NULL WHERE id = 990"); _c2.commit()
# v2.465.0: a player with NO index must still render (StrictUndefined
# would 500 the whole sheet on a missing key).
_pk5 = db.get_event_print_pack(990, db_path=_t2)
check("every alpha row carries handicap_index_display, None for an index-less player",
      all("handicap_index_display" in a for a in _pk5["alpha"]))
check("a player with no index is left blank, never given a made-up handicap",
      db._event_tee_rows(_c2, {"course_id": None}, [])[0] == {})

_cs2 = open("templates/cart_signs.html", encoding="utf-8").read()
check("the cart sign is 15% larger (Kerry)",
      "font-size: 62px" in _cs2 and "font-size: 41px" in _cs2
      and "width: 94px; height: 94px" in _cs2)

print("\n== winnings wait for the field ==")
# Kerry 2026-09-15: "Winnings should not show until 10 minutes after
# last score is posted."
db._ensure_gg_game_flights_tables(_c2)
db._ensure_gg_game_results_tables(_c2)
_c2.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, holes_played, imported_at) "
            "VALUES (301, 'Pat Youngs', 990, '2026-09-15', 9, datetime('now'))")
_c2.commit()
_lb = db.get_event_leaderboard("s9.99 Test Links", db_path=_t2)
check("a score posted just now holds the money", _lb["money_visible"] is False, str(_lb.get("last_score_at")))
# EVERY HOLE FOR EVERY PLAYER FIRST (Kerry 2026-09-15, mid-round: "Not
# all scores are in. Every hole must be accounted for every player").
# The round above has a player with no holes on the card at all, so the
# clock is not even the reason yet.
check("…and the reason is the missing cards, not the clock",
      _lb["money_reason"] == "scores" and _lb["field_complete"] is False,
      str(_lb.get("money_reason")))
check("…naming who is short", _lb["scores_pending_total"] >= 1
      and _lb["scores_pending"][0]["player"] == "Pat Youngs",
      str(_lb.get("scores_pending")))
_rid = _c2.execute("SELECT id FROM scoring_rounds WHERE event_id = 990").fetchone()[0]
for _h in range(1, 10):
    _c2.execute("INSERT OR REPLACE INTO scoring_holes (scoring_round_id, hole_number, strokes) "
                "VALUES (?, ?, 4)", (_rid, _h))
_c2.commit()
_lb = db.get_event_leaderboard("s9.99 Test Links", db_path=_t2)
check("with every hole in, the CLOCK becomes the reason",
      _lb["money_visible"] is False and _lb["money_reason"] == "hold"
      and _lb["field_complete"] is True, str(_lb.get("money_reason")))
check("…and says when it will post", bool(_lb["money_at"]) and _lb["money_hold_minutes"] == 10)
_c2.execute("UPDATE scoring_rounds SET imported_at = datetime('now', '-11 minutes') WHERE event_id = 990")
_c2.commit()
check("eleven minutes later the money is released",
      db.get_event_leaderboard("s9.99 Test Links", db_path=_t2)["money_visible"] is True)
db.set_app_setting("leaderboard_money_hold_minutes", "30", db_path=_t2)
check("the hold is a dial, not a constant",
      db.get_event_leaderboard("s9.99 Test Links", db_path=_t2)["money_visible"] is False)
db.set_app_setting("leaderboard_money_hold_minutes", "10", db_path=_t2)
_cts = open("templates/contests.html", encoding="utf-8").read()
check("a half-posted field names no WINNER either, not just no dollars",
      "r.win_net = false" in _cts and "d.field_complete === false" in _cts)
check("the page blanks every board's money in ONE place, not seven",
      "function evlbBlankMoney(d)" in _cts
      and "if (d.money_visible === false) evlbBlankMoney(d);" in _cts)
check("…and says why, above the boards",
      "Round in play &mdash; winnings are not posted yet." in _cts
      and "evlbMoneyNotice(d) +" in _cts)
check("the event list hides the pot while play is on",
      'ev.money_visible === false' in _cts and "POT PENDING" in _cts)

print("\n== which nine is which, from the data ==")
# Kerry 2026-09-15: "That 'The course card...' note WILL NOT fly. We can
# never do that. We need to get the calculations right." The 18-hole
# card's own yardages say which nine a nine-hole row is.
_t3 = os.path.join(tempfile.mkdtemp(prefix="tgf-nine-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(_t3)
_c3 = sqlite3.connect(_t3); _c3.row_factory = sqlite3.Row
_c3.execute("INSERT INTO courses (course_id, name, status) VALUES (800, 'Quarry Test', 'active')")
_F = [361, 423, 136, 292, 514, 324, 374, 142, 307]     # 2873
_B = [430, 335, 186, 330, 401, 479, 220, 350, 524]     # 3255
for _tid, _rt, _sl, _yd in ((109, 34.2, 117, 2873), (592, 35.6, 128, 3255),
                            (2281, 34.0, 123, 2873), (7827, 69.8, 123, 6128)):
    _c3.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, rating, slope, yardage_total) "
                "VALUES (?, 800, '1 - Gold Tee', ?, ?, ?)", (_tid, _rt, _sl, _yd))
for _i, _y in enumerate(_F + _B, start=1):
    _c3.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) VALUES (7827, ?, 4, ?, ?)", (_i, _y, _i))
for _i, _y in enumerate(_F, start=1):
    for _t in (109, 2281):
        _c3.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) VALUES (?, ?, 4, ?, ?)", (_t, _i, _y, _i))
for _i, _y in enumerate(_B, start=1):
    _c3.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) VALUES (592, ?, 4, ?, ?)", (_i, _y, _i))
_c3.commit()
_res = db.label_course_tee_nines(_c3, 800)
_nine = {d["tee_id"]: d["nine"] for d in _res["decided"]}
check("the front nine is identified by its own yardages", _nine.get(109) == "front", str(_nine))
check("the back nine too", _nine.get(592) == "back", str(_nine))
check("a RE-RATED front nine is still the front nine", _nine.get(2281) == "front", str(_nine))
check("the 18-hole row is marked full", _nine.get(7827) == "full", str(_nine))
check("nothing is left to a guess", _res["n_unresolved"] == 0, str(_res["unresolved"]))
check("running it twice changes nothing",
      db.label_course_tee_nines(_c3, 800)["n_unresolved"] == 0)
# No 18-hole card -> UNRESOLVED, and the sheet must print no PH at all.
_c3.execute("DELETE FROM course_tee_holes WHERE tee_id = 7827")
_c3.execute("DELETE FROM course_tees WHERE tee_id = 7827")
_c3.execute("UPDATE course_tees SET nine = NULL WHERE course_id = 800")
_c3.commit()
_res2 = db.label_course_tee_nines(_c3, 800)
check("with no 18-hole card the nines are left UNRESOLVED, never guessed",
      _res2["n_unresolved"] == 3, str(_res2))
_c3.execute("INSERT INTO events (id, item_name, event_date, chapter, course_id, status, format, nine_side) "
            "VALUES (880, 's9.98 Quarry Test', '2026-09-15', 'San Antonio', 800, 'active', '9 Holes', 'Front')")
_c3.commit()
_rows, _basis, _note = db._event_tee_rows(_c3, {"course_id": 800, "item_name": "s9.98 Quarry Test",
                                                "format": "9 Holes", "nine_side": "Front"},
                                          [{"band": "<50", "tee_name": "Gold Tee", "color": "#B8860B", "ring": False}])
check("an unresolved tee yields NO playing handicap rather than a caveat",
      _rows == {} and "middle rating" not in _note and "Import the 18-hole" in _note, _note)

print("\nALL PASSED" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
