"""The printed scorecard (design-claude #890-#897, CA #898, Kerry 9/28).

A 3304-shaped fixture: a nine-hole shotgun, 7 groups incl. two threesomes,
four designated tees. The pack is the Starter Sheet's own reader, stubbed
here so the test pins what the CARD does with it: dots from the ruled
allocator, plus handicaps with no dots, threesomes of 3 rows, Cart Net
cards, sheet counts per layout, gaps that stop the print, and (when
Chromium is present) one Letter page per sheet in every layout.

Run: python3 test_scorecards.py
"""
import contextlib
import io
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
from email_parser import scorecards as scm  # noqa: E402
from email_parser.handicap_calc import ruled_dots  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


conn = sqlite3.connect(DB)
cid = conn.execute("INSERT INTO courses (name, status) VALUES ('Canyon Springs Golf Club', 'active') "
                   "RETURNING course_id").fetchone()[0]
TEES = [("Gold", "<50", "M"), ("Blue", "50-64", "M"), ("Red", "65+", "M"), ("Red", "Forward", "F")]
tee_ids = {}
for name, band, g in TEES:
    tid = conn.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, rating, slope, "
                       "tgf_bands, source) VALUES (?,?,?,18,70.1,125,?,'admin') RETURNING tee_id",
                       (cid, name, g, band)).fetchone()[0]
    tee_ids[band] = tid
    for h in range(1, 19):
        si = (2 * h - 1) if h <= 9 else 2 * (h - 9)          # front odd, back even
        par = 3 if h in (3, 7, 12, 16) else (5 if h in (5, 14) else 4)
        conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) "
                     "VALUES (?,?,?,?,?)", (tid, h, par, 300 + h * (4 if g == "M" else 2), si))
for i, (f, l) in enumerate([("Kerry", "Niester"), ("Jeff", "Young"), ("Pat", "Youngs"),
                            ("Mary", "Wade"), ("Luke", "Mazanec")], start=1):
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (i, f, l))
conn.execute("INSERT INTO events (id, item_name, event_date, course_id, chapter, start_type, "
             "start_time, format) VALUES (3304, 's9.25 Canyon Springs', '2026-09-29', ?, "
             "'San Antonio', 'Shotgun', '17:00', '9 Holes')", (cid,))
conn.commit()
conn.close()


def P(cid_, name, pos, band, ph, net):
    return {"customer_id": cid_, "name": name, "cart_pos": pos, "tee_choice": band,
            "playing_handicap": ph, "team_handicap": net, "team_allowed": net,
            "handicap_index_display": 4.2, "course_handicap_raw": ph}


def make_pack(groups):
    return {
        "event": {"id": 3304, "start_clock": "5:00 PM", "file_stub": "s9.25"},
        "groups": groups, "holes_key": "9",
        "tee_legend": [{"band": b, "tee_name": n, "tee_id": tee_ids[b], "ladies": g == "F"}
                       for n, b, g in TEES],
        "team_unit": "group", "team_allowance": 0.75,
        "team_off_lowest": {"low": 0, "applied": False}, "team_basis": "test",
    }


slots = ["1", "2", "3", "4", "5B", "6", "7"]
groups = []
for gi, slot in enumerate(slots, start=1):
    n = 3 if gi in (5, 7) else 4
    players = [P(1, "Kerry Niester", 1, "<50", 5, 4), P(2, "Jeff Young", 2, "50-64", -2, 0),
               P(3, "Pat Youngs", 3, "65+", 12, 9), P(4, "Mary Wade", 4, "Forward", 8, 6)][:n]
    groups.append({"holes": "9", "group_num": gi, "slot_label": f"HOLE {slot}", "players": players})

db.get_event_print_pack = lambda eid, db_path=None: make_pack(groups)
db._event_tee_rows = lambda conn, ev, legend: (
    {t["band"]: {"rating": 35.1, "slope": 125, "par": 36, "tee_name": t["tee_name"]}
     for t in legend}, "front nine card", "")

print("one card per group, 3-up")
sc = scm.build_scorecards(3304, "3up", "team", qr="off", db_path=DB)
check("no gaps", sc["gaps"] == [], sc["gaps"])
check("7 cards on 3 sheets", len(sc["cards"]) == 7 and len(sc["sheets"]) == 3,
      (len(sc["cards"]), len(sc["sheets"])))
c1 = sc["cards"][0]
kerry = c1["rows"][0]
si_front = {h: 2 * h - 1 for h in range(1, 10)}
check("black dots = the ruled allocator on the player's own tee",
      {h for h, v in kerry["ph_dots"].items() if v} == {h for h, v in ruled_dots(5, si_front).items() if v},
      kerry["ph_dots"])
check("PH 5 on a nine gets 5 dots on the 5 hardest (subset)",
      sorted(h for h, v in kerry["ph_dots"].items() if v) == [1, 2, 3, 4, 5], kerry["ph_dots"])
jeff = c1["rows"][1]
check("a plus handicap prints +2 and no dots", jeff["ph"] == "+2" and not any(jeff["ph_dots"].values()),
      jeff)
check("net value is the engine's, printed as given", kerry["net"] == "4")
check("rider split before row 3", c1["split_after"] == 2 and c1["rows"][2]["rider"])
t5 = sc["cards"][4]
check("threesome: 3 rows, no blank 4th", len(t5["rows"]) == 3)
check("shotgun 5B: start hole 5B, highlight 5, time = the shotgun",
      t5["start_hole"] == "5B" and t5["hl_hole"] == 5 and t5["start_time"] == "5:00 PM", t5)
check("Forward band prints 'Forward' (CA #898-7)",
      [t["band_text"] for t in sc["tees"]][-1] == "Forward", [t["band_text"] for t in sc["tees"]])
_flag = scm._team_no_par3_pops()
check("par-3 net dots follow the engine rule, and the log says when they print",
      sc["net"]["par3_suppressed"] is _flag and (_flag or any("par 3" in l for l in sc["log"])),
      sc["log"])
check("decode label is TEAM at 75%", sc["net"]["word"] == "TEAM" and sc["net"]["pct"] == 75)
check("source dump carries every printed player with ids", len(sc["dump"]) == 26
      and all(d["customer_id"] and d["tee_id"] for d in sc["dump"]))

print("Cart Net (pairs)")
cc = scm.build_scorecards(3304, "3up", "cart", qr="off", db_path=DB)
check("14 cards on 5 sheets", len(cc["cards"]) == 14 and len(cc["sheets"]) == 5,
      (len(cc["cards"]), len(cc["sheets"])))
check("threesome = a 2-card + a 1-card",
      [len(c["rows"]) for c in cc["cards"] if c["group_num"] == 5] == [2, 1])
check("no shading or split on a pairs card",
      all(not r["rider"] for c in cc["cards"] for r in c["rows"]) and
      all(c["split_after"] is None for c in cc["cards"]))
for lay, n in (("2up", 4), ("2land", 4)):
    s2 = scm.build_scorecards(3304, lay, "team", qr="off", db_path=DB)
    check(f"{lay}: 7 cards on {n} sheets", len(s2["sheets"]) == n, len(s2["sheets"]))

print("gaps stop the print")
groups[0]["players"][0]["playing_handicap"] = None
g = scm.build_scorecards(3304, "3up", "team", qr="off", db_path=DB)
check("a player with no PH is a named gap", any("Kerry Niester" in x and "playing handicap" in x
                                                 for x in g["gaps"]), g["gaps"])
groups[0]["players"][0]["playing_handicap"] = 5
groups[1]["players"][0]["tee_choice"] = "Purple"
g = scm.build_scorecards(3304, "3up", "team", qr="off", db_path=DB)
check("a tee not designated is a named gap", any("'Purple'" in x for x in g["gaps"]), g["gaps"])
groups[1]["players"][0]["tee_choice"] = "<50"

print("print anyway, flagged (CA #915)")
groups[0]["players"][0]["playing_handicap"] = None
groups[0]["players"][0]["team_handicap"] = None
fa = scm.build_scorecards(3304, "3up", "team", qr="off", allow_gaps=True, db_path=DB)
check("a no-PH player no longer blocks the set", fa["gaps"] == [] and len(fa["cards"]) == 7, fa["gaps"])
k = fa["cards"][0]["rows"][0]
check("his card prints PH/net blank and no dots", k["ph"] == "" and k["net"] == ""
      and not any(k["ph_dots"].values()), k)
check("the print log names him", any("PRINTED ANYWAY" in l and "Kerry Niester" in l for l in fa["log"]),
      fa["log"])
bad = dict(groups[1]["players"][0]); groups[1]["players"][0]["tee_choice"] = "Purple"
fb = scm.build_scorecards(3304, "3up", "team", qr="off", allow_gaps=True, db_path=DB)
check("an undesignated tee still stops the print", any("'Purple'" in x for x in fb["gaps"]), fb["gaps"])
groups[1]["players"][0]["tee_choice"] = "<50"
groups[0]["players"][0]["playing_handicap"] = 5
groups[0]["players"][0]["team_handicap"] = 4

print("GGID per group (Kerry #900/#912)")
r = db.set_group_codes(3304, {("9", 1): " AB-12 ", ("9", 2): "C3"}, db_path=DB)
check("codes save trimmed", r["ok"] and db.get_group_codes(3304, db_path=DB) == {("9", 1): "AB-12",
                                                                                 ("9", 2): "C3"}, r)
r = db.set_group_codes(3304, {("9", 2): "bad code!"}, db_path=DB)
check("a code with junk is refused, nothing written", not r["ok"]
      and db.get_group_codes(3304, db_path=DB)[("9", 2)] == "C3", r)
db.set_group_codes(3304, {("9", 2): ""}, db_path=DB)
check("blank clears", ("9", 2) not in db.get_group_codes(3304, db_path=DB))
for g in groups:
    g["ggid"] = db.get_group_codes(3304, db_path=DB).get((g["holes"], g["group_num"]))
gg = scm.build_scorecards(3304, "3up", "team", qr="off", db_path=DB)
check("the card header carries the group's code; others collapse",
      gg["cards"][0]["ggid"] == "AB-12" and gg["cards"][1]["ggid"] is None, gg["cards"][0]["ggid"])

print("par-3 net dots follow the engine flag (Kerry #912-2)")
from email_parser import live_scoring as _ls  # noqa: E402
_ls.SEED_LIVE_SCORING_CONFIG["games"]["team_net"]["no_pops_on_par3"] = True
p3 = scm.build_scorecards(3304, "3up", "team", qr="off", db_path=DB)
pat = p3["cards"][0]["rows"][2]
check("no orange dot on any par 3 (holes 3, 7)", pat["net_dots"].get(3, 0) == 0
      and pat["net_dots"].get(7, 0) == 0 and pat["ph_dots"].get(3, 0) > 0, pat)
check("decode says so", "no pops on par 3s" in p3["net"]["pct_note"], p3["net"])
_ls.SEED_LIVE_SCORING_CONFIG["games"]["team_net"]["no_pops_on_par3"] = _flag

print("render")
from jinja2 import Environment, FileSystemLoader, StrictUndefined  # noqa: E402
env = Environment(loader=FileSystemLoader(os.path.join(HERE, "templates")), autoescape=True,
                  undefined=StrictUndefined)
html_gap = env.get_template("scorecards.html").render(sc=g if False else scm.build_scorecards(
    3304, "3up", "team", qr="off", db_path=DB))
check("renders", "<table>" in html_gap and "NIESTER, Kerry" in html_gap)
h18 = scm.build_scorecards(3304, "2land", "team", qr="off", holes_override="18", db_path=DB)
html18 = env.get_template("scorecards.html").render(sc=h18)
check("18-hole: two panels, Init column, T header", "Init" in html18 and ">T<" in html18
      and "TOT" in html18, "")

try:
    from email_parser.print_pack import _chromium_executable
    exe = _chromium_executable()
except Exception:
    exe = None
if exe and os.getenv("SKIP_PDF") != "1":
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader
    static = os.path.join(HERE, "static")
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=exe, headless=False, args=["--headless=new", "--no-sandbox", "--disable-gpu"])
        pg = b.new_page()
        for lay in ("3up", "2up", "2land"):
            for grp in ("team", "cart"):
                for hk in ("9", "18"):
                    s = scm.build_scorecards(3304, lay, grp, qr="off",
                                             holes_override=hk, db_path=DB)
                    html = env.get_template("scorecards.html").render(sc=s).replace(
                        'src="/static/', f'src="file://{static}/')
                    pg.set_content(html, wait_until="load")
                    over = pg.evaluate("""() => [...document.querySelectorAll('.card')].filter(
                        c => c.scrollHeight > c.clientHeight + 1).length""")
                    pdf = pg.pdf(prefer_css_page_size=True, print_background=True)
                    pages = len(PdfReader(io.BytesIO(pdf)).pages)
                    check(f"{lay}/{grp}/{hk}: {len(s['sheets'])} sheets = {pages} Letter pages, "
                          f"no card overflows", pages == len(s["sheets"]) and over == 0,
                          f"pages {pages}, overflowing cards {over}")
        b.close()
else:
    print("  (Chromium not present: PDF page checks skipped)")

print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
