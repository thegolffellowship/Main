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
        "tee_swatches": {"<50": "#2F5FA6", "50-64": "#FFFFFF", "65+": "#C99A2E", "Forward": "#C0392B"},
        "tee_ladies": {"Forward": True},
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

print("one tee-colour resolver (Kerry 9/28, Star Ranch)")
r = db.resolve_tee_color(1, "Champ - Blue", {})
check("a colour word anywhere in the name resolves", r["word"] == "blue" and r["source"] == "name", r)
check("no colour word = unresolved", db.resolve_tee_color(2, "Forward - Ladies", {})["hex"] is None)
check("an explicit colour wins", db.resolve_tee_color(2, "Forward - Ladies", {2: "red"})["word"] == "red")
check("scorecard rows use the design shade for a known word",
      scm._row_colour(1, "Champ - Blue", {}) == scm.TEE_TOKENS["blue"])
check("an unknown-to-design word still colours, with readable ink",
      scm._row_colour(1, "Executive - Teal", {}) == ("#0F766E", "#FFFFFF"))
r = db.set_tee_colors({tee_ids["Forward"]: "red"}, db_path=DB)
check("set_tee_colors stores by tee_id", r["ok"] and db.tee_color_overrides(db_path=DB)[tee_ids["Forward"]] == "red", r)
check("junk colour refused", not db.set_tee_colors({1: "sparkly"}, db_path=DB)["ok"])
aud = db.tee_color_audit(db_path=DB)
check("audit lists every designated tee", aud["designated_tees"] == 4 and aud["unresolved"] == [], aud)

print("scorecards in the print pack (Kerry 9/29)")
from email_parser import print_pack as pp  # noqa: E402
check("off by default", not pp.scorecards_in_pack(3304, db_path=DB))
db.set_app_setting("print_pack_scorecards", "3304", db_path=DB)
check("on for a listed event only", pp.scorecards_in_pack(3304, db_path=DB)
      and not pp.scorecards_in_pack(3317, db_path=DB))
db.set_app_setting("print_pack_scorecards", "all", db_path=DB)
check("'all' turns every event on", pp.scorecards_in_pack(3317, db_path=DB))
_parts_saved, _pdf_saved = pp.PRINT_PACK_PARTS, pp._render_pdf_chromium
pp.PRINT_PACK_PARTS = (("starter-sheet", "x", "get_event_print_pack", "pack"),
                       ("cart-signs", "x", "get_event_print_pack", "pack"),
                       ("proximity-markers", "x", "get_event_print_pack", "pack"))
pp._render_pdf_chromium = lambda htmls, sd: (b"%PDF", [{"slug": sl, "pages": 1} for sl, _ in htmls], "chromium")
_orig_all = db.get_all_events
db.get_all_events = lambda db_path=None: [{"id": 3304, "item_name": "s9.25", "event_date": "2026-09-29"}]
built = pp.build_event_print_pack(lambda t, **k: "<html>" + t + "</html>", 3304, "/tmp", db_path=DB)
db.get_all_events = _orig_all
pp.PRINT_PACK_PARTS, pp._render_pdf_chromium = _parts_saved, _pdf_saved
check("the scorecards part sits right after the cart signs",
      [p["slug"] for p in built["parts"]] == ["starter-sheet", "cart-signs", "scorecards", "proximity-markers"],
      built["parts"])
check("the pack reports the scorecards (Team Net, 7 cards, no gaps)",
      built["scorecards"]["grouping"] == "team" and built["scorecards"]["cards"] == 7
      and built["scorecards"]["gaps"] == [], built["scorecards"])
db.set_app_setting("print_pack_scorecards", "", db_path=DB)

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

check("a Back link to the REPORTS tab, top and bottom (Kerry 9/28, 9/29)",
      html_gap.count("view=reports") == 2 and "Back to Reports" in html_gap)
check("Print and PDF, top and bottom (Kerry 9/28: every report)",
      html_gap.count("window.print()") == 2 and html_gap.count("scPdf(false)") == 2)
groups[0]["players"][0]["playing_handicap"] = None
_hf = env.get_template("scorecards.html").render(sc=scm.build_scorecards(3304, "3up", "team", qr="off", db_path=DB))
check("with a player gap, the buttons offer print/PDF anyway, flagged",
      _hf.count("return scFlagged()") == 2 and _hf.count("scPdf(true)") == 2)
groups[0]["players"][0]["playing_handicap"] = 5

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

print("dot geometry is whole CSS px (Kerry 9/29: equal insets off both lines)")
_tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "scorecards.html")).read()
_dotcss = _tpl[_tpl.index(".dk, .do {"):_tpl.index(".dk i { background")]
check("dot inset / size / spacing read the whole-px vars, no mm and no half-stroke",
      "var(--dg)" in _dotcss and "var(--dd)" in _dotcss and "mm" not in _dotcss and "--hb" not in _dotcss,
      _dotcss)
import re as _re
for _v in ("--dd", "--dg"):
    _vals = _re.findall(_v + r": \{\{ (.*?) \}\}", _tpl)
    check(f"{_v} is set per layout in whole px", bool(_vals) and all(
        _re.fullmatch(r"\d+px", x) for x in _re.findall(r"'([^']+)'", _vals[0]) if x not in ("3up", "2up", "2land")), _vals)
check("thick dividers are a whole 2px (print rounds 2.5px down anyway)", "2.5px" not in _tpl)

_ss = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "starter_sheet.html")).read()
_head = _ss[_ss.index('<div class="gbox-head">'):_ss.index('</div>', _ss.index('<div class="gbox-head">'))]
check("Starter Sheet GGID rides in the group header line, never its own row (it pushed 3304 to 2 pages)",
      "g.ggid" in _head and "gbox-foot" not in _ss)

print("Kerry 9/29: par-3 would-be team pops as outlines; hole-width Total/Net; heavy rules")
_s9 = scm.build_scorecards(3304, "3up", "team", qr="off", db_path=DB)
_par = _s9["grids"]["9"]["par"] if "grids" in _s9 else None
_rows = [r for c in _s9["cards"] for r in c["rows"]]
_gh = [(h, r) for r in _rows for h in (r.get("net_ghost") or {})]
check("par-3 team pops the rule removed come back as net_ghost, on par 3s only, never in net_dots",
      bool(_gh) and all((r["net_dots"].get(h) or 0) == 0 for h, r in _gh), len(_gh))
# autoescape ON, as Flask renders it (a |replace on escaped text escapes the tag)
_h9 = env.get_template("scorecards.html").render(sc=_s9)
check("par-3 removed strokes render, and the one-line legend reads as Kerry wrote it",
      '<i class="g"></i>' in _h9
      and "PH &ndash; Playing Handicap Stroke (&ldquo;Pops&rdquo;) at 100%" in _h9
      and (("Team Net Stroke at 75%, off the field&rsquo;s low" in _h9) == bool(_s9["net"].get("off_low")))
      and "Team Net Stroke at 75%" in _h9
      and '<i class="lx"></i>No Team Net Strokes on par 3s' in _h9, _h9[_h9.find('class="decode"'):][:400])
_s9o = dict(_s9); _s9o["net"] = dict(_s9["net"], off_low=True)
check("off the field's low prints when the rule applies it",
      "Team Net Stroke at 75%, off the field&rsquo;s low" in env.get_template("scorecards.html").render(sc=_s9o))
check("the par-3 removed stroke is an orange × (two strokes, corner to corner)", "width: 141%" in _tpl and "rotate(45deg)" in _tpl and "rotate(-45deg)" in _tpl and "border-radius: 0;" in _tpl)
check("9-hole card: Total and Net are hole-width, PH/TEAM narrower",
      '<col style="width:6.45%"><col style="width:5.05%"><col style="width:6.45%">' in _h9)
for _rule in ("table { border: 2px solid #374151; }", "tr.hd th { border-bottom: 2px solid #374151; }",
              "tr.par td { border-top: 2px solid #374151; }", "tr.hcp td { border-bottom: 2px solid #374151; }"):
    check(f"heavy rule: {_rule}", _rule in _tpl)

print("tee circle = tee row colour; outline only when a women's tee shares a colour (Kerry 9/29)")
for _lay in ("3up", "2up", "2land"):
    _sx = scm.build_scorecards(3304, _lay, "team", qr="off", db_path=DB)
    _bg = {t["band"]: t["bg"] for t in _sx["tees"]}
    _bad = [(r["name"], r["chip"], _bg.get(b)) for c in _sx["cards"] for r in c["rows"]
            for b in [next((p["band"] for p in _sx.get("dump") or [] if p["customer_id"] == r["customer_id"]), None)]
            if b in _bg and (r["chip"] or "").lower() != (_bg[b] or "").lower()]
    check(f"{_lay}: every name circle is its tee row's exact colour", not _bad, _bad[:3])
_T = lambda band, bg, ladies=False: {"band": band, "bg": bg, "ladies": ladies}
_bgm, _out = scm.chip_styles([_T("<50", "#2F5FA6"), _T("65+", "#FFCF40"), _T("Forward", "#C0392B", True)])
check("women on their own colour (Red) print SOLID", _out["Forward"] is False and _bgm["Forward"] == "#C0392B")
_bgm, _out = scm.chip_styles([_T("<50", "#2F5FA6"), _T("65+", "#FFCF40"), _T("Forward", "#ffcf40", True)])
check("women sharing Gold with 65+ print as an OUTLINE (the men's row stays solid)",
      _out["Forward"] is True and _out["65+"] is False)
check("the circle's edge is its own colour, not a darker ring",
      "border:1px solid {{ r.chip or '#1B1B1B' }}" in _tpl and "rgba(0,0,0,.25)" not in _tpl)

check("column heads read TOTAL and NET (Kerry 9/29: \"Capitalize TOTAL and NET\")",
      '<th class="thick">TOTAL</th>' in _tpl and "<th>NET</th>" in _tpl and ">Total<" not in _tpl and ">Net<" not in _tpl)
check("the GGID code prints large (1.75em; 1.4em on the 18's half-width column)",
      "font-size: 1.75em" in _tpl and ".card.h18 tr.hd th.lead .gc { font-size: 1.4em" in _tpl)

check("double-dot spacing is a whole 2px", "--dsp: 2px;" in _tpl)
check("dots at 75% of the 9/29 size (Kerry, CD #962 ruling a): 4 / 6 / 5 px",
      "--dd: {{ '4px' if sc.layout == '3up' else ('6px' if sc.layout == '2up' else '5px') }};" in _tpl)

print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
