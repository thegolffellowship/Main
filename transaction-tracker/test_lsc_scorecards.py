"""THE LONE STAR CUP SCORECARD THEME (design-claude #1467, Kerry-approved;
Kerry 10/8: "Reports aren't showing with the updated Lone Star Cup
formatting. See CD's direction on scorecards for LSC too").

Pins: the theme turns on from data (the Cup = lsc_matches.event_id, the
practice round = the Cup's `friday` add-on event), never from the day;
the Cup's cards are its drawn matches in the load-bearing seat order;
the format math matches CD's spot-checks; only orange OFF pops on the
match formats, only black PH pops on practice; foursomes merge the two
partners' cells; a missing format or a broken seat pattern stops the
print; a regular TGF event is untouched.

Run: python3 test_lsc_scorecards.py
"""
import contextlib
import io
import json
import logging
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)
from email_parser import scorecards as scm, lsc_cup  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


conn = sqlite3.connect(DB)
course = conn.execute("INSERT INTO courses (name, status) VALUES ('The Hideout Golf Club', 'active') "
                      "RETURNING course_id").fetchone()[0]
TEES = [("Blue", "<50", "M"), ("White", "50-64", "M"), ("Red", "65+", "M"), ("Teal", "forward", "F")]
tee_ids = {}
for name, band, g in TEES:
    tid = conn.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, rating, slope, "
                       "tgf_bands, source) VALUES (?,?,?,18,70.1,125,?,'admin') RETURNING tee_id",
                       (course, name, g, band)).fetchone()[0]
    tee_ids[band] = tid
    for h in range(1, 19):
        si = (2 * h - 1) if h <= 9 else 2 * (h - 9)
        par = 3 if h in (3, 7, 12, 16) else (5 if h in (5, 14) else 4)
        conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) "
                     "VALUES (?,?,?,?,?)", (tid, h, par, 300 + h * 4, si))
NAMES = {13: ("Luke", "Youngs"), 438: ("Chris", "Cannon"), 136: ("Pat", "Youngs"), 88: ("Jeff", "Young"),
         7: ("Matt", "Jenkins"), 294: ("Mike", "Jenkins"), 18: ("Kerry", "Niester"), 703: ("Michael", "Mesa"),
         672: ("David", "Wetz"), 23: ("Mary", "Wade"), 1: ("Other", "Player")}
for c, (f, l) in NAMES.items():
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (c, f, l))
for eid, name, date in ((3329, "LONE STAR CUP | The Hideout", "2026-10-10"),
                        (3330, "LSC PRACTICE ROUND | The Hideout", "2026-10-09"),
                        (3304, "s9.25 Canyon Springs", "2026-09-29")):
    conn.execute("INSERT INTO events (id, item_name, event_date, course_id, chapter, start_type, "
                 "start_time, format) VALUES (?,?,?,?,'TGF','Tee Times','13:30','18 Holes')",
                 (eid, name, date, course))
conn.commit()
conn.close()

# CD's design sample: PH 1,2,1,4 (#1467 §7-4)
LOCK = {"13": ("austin", "Blue", 1), "438": ("austin", "Blue", 2), "136": ("sa", "Blue", 1),
        "88": ("sa", "Teal", 4), "7": ("austin", "Blue", 3), "294": ("austin", "White", 15),
        "18": ("sa", "Blue", 1), "703": ("sa", "Blue", 0)}
db.set_app_setting("lsc_handicap_lock", json.dumps({"3329": {"players": {
    c: {"name": " ".join(NAMES[int(c)]), "team": t, "tee": tee, "ch": ch, "index": float(ch)}
    for c, (t, tee, ch) in LOCK.items()}}}), db_path=DB)
db.set_app_setting("lsc_tees", json.dumps({"3329": {"bands": {"<50": "Blue", "50-64": "White",
                                                              "65+": "Red", "Forward": "Teal"},
                                                    "players": {"88": {"band": "Forward"}}}}), db_path=DB)
db.set_app_setting("oneoff_charges", json.dumps({"3329": {"default": 250, "addons": [
    {"key": "friday", "label": "FRI", "amount": 110, "event_id": 3330}]}}), db_path=DB)
DIAL = {"event_id": 3329, "board_live": False, "sessions": [
    {"id": "sat-am", "format": "fourball", "date": "2026-10-10", "n_holes": 18, "matches": [
        {"id": "SAT-AM-1", "tee_time": "8:30", "austin": [13, 438], "sa": [136, 88]}]},
    {"id": "sat-pm", "format": "chapman", "date": "2026-10-10", "n_holes": 18, "matches": [
        {"id": "SAT-PM-1", "tee_time": "1:30", "austin": [13, 438], "sa": [136, 88]}]},
    {"id": "sun", "format": "singles", "date": "2026-10-11", "n_holes": 18, "matches": [
        {"id": "SUN-1", "tee_time": "8:30", "austin": [13], "sa": [438]},
        {"id": "SUN-2", "tee_time": "8:30", "austin": [136], "sa": [88]},
        {"id": "SUN-3", "tee_time": "8:40", "austin": [7], "sa": [18]}]}]}
db.set_app_setting("lsc_matches", json.dumps(DIAL), db_path=DB)


def make_pack(eid, groups):
    return {"event": {"id": eid, "start_clock": "1:30 PM", "file_stub": f"ev{eid}"},
            "groups": groups, "holes_key": "18",
            "tee_legend": [{"band": b, "tee_name": n, "tee_id": tee_ids[b], "ladies": g == "F"}
                           for n, b, g in TEES],
            "team_unit": "cart", "team_allowance": 0.85,
            "team_off_lowest": {"low": 0, "applied": False}, "team_basis": "test",
            # the real pack's display fields the Starter Sheet reads
            "tee_swatches": {b: "#2F5FA6" for _, b, _ in TEES}, "tee_ladies": {"forward": True},
            "tee_colors": {}, "alpha": [], "player_count": 0, "ph_basis": "", "ph_note": "",
            "brand": {"lsc": "cup", "logo": "/static/lsc-logo.png", "alt": "Lone Star Cup"}}


def P(cid_, pos, band, ph, net=None):
    return {"customer_id": cid_, "name": " ".join(NAMES[cid_]), "cart_pos": pos, "tee_choice": band,
            "playing_handicap": ph, "team_handicap": net, "team_allowed": net,
            "handicap_index_display": 4.2, "course_handicap_raw": ph}


PRACTICE = [{"holes": "18", "group_num": 1, "slot_label": "1:30", "ggid": "ABC",
             "players": [P(7, 1, "<50", 3, 2), P(672, 2, "<50", 8, 7), P(438, 3, "<50", 7, 6)]}]
TGF = [{"holes": "18", "group_num": 1, "slot_label": "1:30", "ggid": "XYZ",
        "players": [P(1, 1, "<50", 5, 4), P(23, 2, "65+", 12, 10)]}]
db.get_event_print_pack = lambda eid, db_path=None: make_pack(
    eid, {3329: [], 3330: PRACTICE, 3304: TGF}[int(eid)])
db._event_tee_rows = lambda conn, ev, legend: (
    {t["band"]: {"rating": 70.1, "slope": 125, "par": 72, "tee_name": t["tee_name"]}
     for t in legend}, "18", "")

print("which events are LSC rounds (from data, not the day)")
check("the Cup", lsc_cup.lsc_report_context(3329, db_path=DB) == {"kind": "cup", "cup_event_id": 3329})
check("the Friday practice round", lsc_cup.lsc_report_context(3330, db_path=DB)["kind"] == "practice")
check("a regular TGF event is not", lsc_cup.lsc_report_context(3304, db_path=DB) is None)

print("CD's math spot-checks (#1467 §7-4)")
R = lambda phs, teams: [{"cid": i, "ph": p, "team": t} for i, (p, t) in enumerate(zip(phs, teams))]
check("Singles M1 1/2 -> OFF 0/1, M2 1/4 -> 0/3",
      [m["off"] for m in lsc_cup.lsc_card_math("singles", R([1, 2, 1, 4], ["austin", "sa"] * 2))] == [0, 1, 0, 3])
fb = lsc_cup.lsc_card_math("fourball", R([1, 2, 1, 4], ["austin", "austin", "sa", "sa"]))
check("Fourball 1,2,1,4 -> HCP 1,2,1,4 -> OFF 0,1,0,3",
      [m["hcp"] for m in fb] == [1, 2, 1, 4] and [m["off"] for m in fb] == [0, 1, 0, 3], fb)
fs = lsc_cup.lsc_card_math("chapman", R([1, 2, 1, 4], ["austin", "austin", "sa", "sa"]))
check("Foursomes (1,2),(1,4) -> TEAM 1, 2 -> OFF 0, 1",
      [m["hcp"] for m in fs] == [1, 1, 2, 2] and [m["off"] for m in fs] == [0, 0, 1, 1], fs)
check("a plus handicap keeps its sign through 90%",
      lsc_cup.lsc_card_math("fourball", R([-2, 3, 3, 3], ["austin", "austin", "sa", "sa"]))[0]["hcp"] == -2)

print("the Cup's cards")
sc = scm.build_scorecards(3329, "3up", "team", qr="on", db_path=DB)
check("no gaps", sc["gaps"] == [], sc["gaps"])
check("one card per fourball/foursomes match, singles two matches a card",
      [c["lsc"]["title"] for c in sc["cards"]] == ["FOURBALL", "FOURSOMES", "SINGLES", "SINGLES"]
      and [len(c["rows"]) for c in sc["cards"]] == [4, 4, 4, 2], [len(c["rows"]) for c in sc["cards"]])
check("the Cup prints no QR and no GGID", all(c["qr"] is None and c["ggid"] is None for c in sc["cards"]))
f4 = sc["cards"][0]
check("fourball seats: Austin rows 1-2, SA rows 3-4, team bars in the team colours",
      [r["team"] for r in f4["rows"]] == ["austin", "austin", "sa", "sa"]
      and [r["team_bar"] for r in f4["rows"]] == ["#BF5700", "#BF5700", "#44596B", "#44596B"])
check("fourball HCP/OFF on the card = 1,2,1,4 / 0,1,0,3",
      [r["ph"] for r in f4["rows"]] == ["1", "2", "1", "4"] and [r["net"] for r in f4["rows"]] == ["0", "1", "0", "3"],
      [(r["ph"], r["net"]) for r in f4["rows"]])
check("only orange OFF pops: no black dots, the low man gets none",
      all(not r["ph_dots"] for r in f4["rows"]) and not any(f4["rows"][0]["net_dots"].values())
      and sum(f4["rows"][3]["net_dots"].values()) == 3, f4["rows"][3]["net_dots"])
check("OFF pops fall on the stroke index even on a par 3 (no par-3 rule)",
      lsc_cup.lsc_card_math("fourball", R([0, 0, 0, 20], ["austin", "austin", "sa", "sa"]))[3]["off"] == 18
      and True)
check("Jeff Young's pops follow HIS tee (Teal, from lsc_tees)", f4["rows"][3]["band"].lower() == "forward")
check("the split + shade above row 3", f4["split_after"] == 2 and [r["rider"] for r in f4["rows"]] == [False, False, True, True])
check("the lead cell and labels", f4["lsc"]["lead"] == "2 v 2 · AUSTIN v SAN ANTONIO"
      and (f4["lsc"]["ul"], f4["lsc"]["lr"]) == ("H", "O"))
fsc = sc["cards"][1]
check("foursomes: one merged cell per team, TEAM 1 / 2, OFF 0 / 1",
      [r.get("fs_span") for r in fsc["rows"]] == [2, None, 2, None]
      and [bool(r.get("fs_skip")) for r in fsc["rows"]] == [False, True, False, True]
      and [fsc["rows"][0]["ph"], fsc["rows"][2]["ph"], fsc["rows"][2]["net"]] == ["1", "2", "1"],
      [(r.get("fs_span"), r["ph"], r["net"]) for r in fsc["rows"]])
check("foursomes labels T / O at 18", (fsc["lsc"]["ul"], fsc["lsc"]["lr"]) == ("T", "O"))
sg = sc["cards"][2]
check("singles: M1 rows 1-2, M2 rows 3-4, Austin first, OFF within each match",
      [r["mprefix"] for r in sg["rows"]] == ["M1", "M1", "M2", "M2"]
      and [r["team"] for r in sg["rows"]] == ["austin", "sa", "austin", "sa"]
      and [r["net"] for r in sg["rows"]] == ["0", "1", "0", "3"], [(r["mprefix"], r["net"]) for r in sg["rows"]])
check("Sunday's card carries Sunday's date", sg["lsc"]["date"] == "Sun, October 11, 2026", sg["lsc"]["date"])
check("the course prints in capitals from the course record", sc["lsc"]["course"] == "THE HIDEOUT GOLF CLUB")
one = scm.build_scorecards(3329, "3up", "team", qr="off", db_path=DB, session="sun")
check("?session=sun prints Sunday only", [c["lsc"]["title"] for c in one["cards"]] == ["SINGLES", "SINGLES"])

print("practice round")
pr = scm.build_scorecards(3330, "3up", "team", qr="off", db_path=DB)
pc = pr["cards"][0]
check("PRACTICE ROUND title, single PH, black dots only, team bars (Kerry 10/8), no GGID",
      pc["lsc"]["title"] == "PRACTICE ROUND" and pc["lsc"]["single"] and pc["ggid"] is None
      and all(not r["net_dots"] and not r["net"] for r in pc["rows"])
      and [r.get("team_bar") for r in pc["rows"]] == ["#BF5700", None, "#BF5700"]
      and sum(pc["rows"][1]["ph_dots"].values()) == 8, pc["rows"][1])
check("practice lead + key", pc["lsc"]["lead"] == "PRACTICE · INDIVIDUAL"
      and pc["lsc"]["key"] == [("lk", "PH — Playing Handicap (100%)")])

print("stops the print")
bad = json.loads(json.dumps(DIAL))
bad["sessions"][0]["format"] = ""
db.set_app_setting("lsc_matches", json.dumps(bad), db_path=DB)
g = scm.build_scorecards(3329, "3up", "team", qr="off", db_path=DB)
check("an LSC round with no format: named warning, no print", "LSC round has no format (sat-am)." in g["gaps"], g["gaps"])
bad = json.loads(json.dumps(DIAL))
bad["sessions"][2]["matches"][0]["sa"] = [438, 88]
db.set_app_setting("lsc_matches", json.dumps(bad), db_path=DB)
g = scm.build_scorecards(3329, "3up", "team", qr="off", db_path=DB)
check("a broken seat pattern stops the print", any("seat" in x for x in g["gaps"]), g["gaps"])
empty = json.loads(json.dumps(DIAL))
for s in empty["sessions"]:
    s["matches"] = []
db.set_app_setting("lsc_matches", json.dumps(empty), db_path=DB)
g = scm.build_scorecards(3329, "3up", "team", qr="off", db_path=DB)
check("an undrawn Cup says so", any("no drawn matches" in x for x in g["gaps"]), g["gaps"])
db.set_app_setting("lsc_preview_matches", json.dumps(DIAL), db_path=DB)
g = scm.build_scorecards(3329, "3up", "team", qr="off", db_path=DB, preview=True)
check("the staff preview prints from the demo dial", g["gaps"] == [] and len(g["cards"]) == 4, g["gaps"])
db.set_app_setting("lsc_matches", json.dumps(DIAL), db_path=DB)

print("a regular TGF event is unchanged")
t = scm.build_scorecards(3304, "3up", "team", qr="off", db_path=DB)
check("no LSC block, GGID kept, net game kept",
      t["lsc"] is None and t["cards"][0]["lsc"] is None and t["cards"][0]["ggid"] == "XYZ"
      and t["cards"][0]["rows"][0]["net"] == "4")

print("renders")
from jinja2 import Environment, FileSystemLoader  # noqa: E402
env = Environment(loader=FileSystemLoader(os.path.join(HERE, "templates")))
env.globals["print_stamp"] = lambda: "test"   # a Flask global in the app
for eid, kw in ((3329, {}), (3330, {}), (3304, {})):
    for lay in ("3up", "2up", "2land"):
        for holes in ("9", "18"):
            s = scm.build_scorecards(eid, lay, "team", qr="off", db_path=DB, holes_override=holes, **kw)
            html = env.get_template("scorecards.html").render(sc=s)
            if eid == 3329:
                ok = "lsc-logo.png" in html and "FOURSOMES · 1 BALL PER TEAM" not in html and 'rowspan="2"' in html \
                    and "tgf-logo-r.svg" not in html.split("<body>")[1].split("class=\"sheet\"")[1]
            elif eid == 3330:
                ok = "PRACTICE ROUND" in html and "GGID codes" not in html
            else:
                ok = "lsc-logo.png" not in html and "GGID" in html
            check(f"{eid} {lay} {holes}-hole renders", ok)
            if eid in (3329, 3330) and lay == "3up" and holes == "18" and os.environ.get("LSC_RENDER_DIR"):
                open(os.path.join(os.environ["LSC_RENDER_DIR"], f"lsc-{eid}.html"), "w").write(
                    html.replace('src="/static/', f'src="file://{HERE}/static/'))

print("the other reports carry the Cup logo (Kerry 10/8: Starter Sheet, Proxy logos)")
check("report_brand: the Cup and the practice round print the Cup logo, TGF events TGF's",
      db.report_brand(3329, db_path=DB)["logo"] == "/static/lsc-logo.png"
      and db.report_brand(3330, db_path=DB)["lsc"] == "practice"
      and db.report_brand(3304, db_path=DB)["logo"] == "/static/tgf-logo-r.svg")
for tpl, var in (("proximity_markers.html", "rep"), ("cart_signs.html", "pack")):
    src = open(os.path.join(HERE, "templates", tpl)).read()
    check(f"{tpl} reads the brand's logo", f"{var}.get('brand')" in src and "brand.get('logo')" in src)
for tpl in ("starter_sheet.html", "divisions_flights.html", "games_payouts.html"):
    src = open(os.path.join(HERE, "templates", tpl)).read()
    check(f"{tpl} reads the brand's logo", "brand.get('logo')" in src)

print("each round's Starter Sheet and cart signs fill from THE DRAW (Kerry 10/8)")
rp = lsc_cup.cup_round_pack(3329, "sat-am", db_path=DB)
check("FOURBALL starter sheet: one group per match, tee time, seats, locked PH, team colour",
      rp["event"]["item_name"] == "LONE STAR CUP · FOURBALL" and len(rp["groups"]) == 1
      and rp["groups"][0]["slot_label"] == "8:30"
      and [p["playing_handicap"] for p in rp["groups"][0]["players"]] == [1, 2, 1, 4]
      and rp["groups"][0]["players"][2]["team_color"] == "#44596B" and rp["games_off"]
      and len(rp["alpha"]) == 4, rp["groups"])
html = env.get_template("starter_sheet.html").render(pack=rp)
check("the starter sheet renders the round, no Cart/Team column", 'class="atn"' not in html and "8:30" in html)
check("its header is ROUND NAME, then COURSE · DATE (Kerry 10/8)",
      rp["heading"] == {"title": "FOURBALL", "course": "THE HIDEOUT GOLF CLUB", "date": "Sat, October 10, 2026"}
      and '<h1 class="lsc-h">FOURBALL</h1>' in html and "<b>THE HIDEOUT GOLF CLUB</b>" in html, rp["heading"])
check("the practice round's header", db.report_heading({"id": 3330, "event_date": "2026-10-09", "course": "x"},
                                                        db_path=DB)["title"] == "PRACTICE ROUND")
check("a regular TGF event has no Cup header", db.report_heading({"id": 3304}, db_path=DB) is None)
sg = lsc_cup.cup_round_cart_signs(3329, "sun", db_path=DB)
check("SINGLES cart signs from the draw: one per side per card",
      [s_["team"] for s_ in sg] == ["AUSTIN", "SAN ANTONIO", "AUSTIN", "SAN ANTONIO"]
      and len(sg[0]["riders"]) == 2, [s_["team"] for s_ in sg])
check("an undrawn round says so on its starter sheet",
      "isn't drawn yet" in env.get_template("starter_sheet.html").render(
          pack={**rp, "groups": [], "alpha": [], "lsc_round": {**rp["lsc_round"], "gaps": []}}))

print("ALL PASS" if not FAILURES else f"{len(FAILURES)} FAILED: {FAILURES}")
sys.exit(1 if FAILURES else 0)
