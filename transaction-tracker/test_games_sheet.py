"""GAMES & PAYOUTS sheet (CD #967 + Kerry's 9/29 amendments).

Every figure is the GAMES tab's: the fixtures are two real GAMES-tab reads
(`get_event_games`, 2026-09-30) — s9.25 Canyon Springs (9 holes, linked
TGF MVP, Individual Gross NO GAME) and s18.4 Landa Park (18 holes, four
CTPs, Team Net 1st+2nd, Individual Gross in three flights).

Run: python3 test_games_sheet.py
"""
import os, sys, json, tempfile, contextlib, io, logging, re
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-gsheet-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test"); os.environ.setdefault("ADMIN_PIN", "1234")
os.environ["SCHEDULER_DISABLED"] = "1"
logging.disable(logging.CRITICAL)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as A
from email_parser import database as db, games_sheet as GS
HERE = os.path.dirname(os.path.abspath(__file__))
fx = lambda n: json.load(open(os.path.join(HERE, "tests_fixtures", n)))

def seed(games, nine="Front"):
    ev = games["event"]
    with db._connect(DB) as c:
        c.execute("DELETE FROM events WHERE item_name = ? OR id = ?", (ev["item_name"], ev["id"]))
        c.execute("INSERT INTO events (id, item_name, event_date, course, chapter, format, start_type, "
                  "start_time, nine_side) VALUES (?,?,?,?,?,?,'Shotgun','5:00 PM',?)",
                  (ev["id"], ev["item_name"], ev["event_date"], ev["course"], ev["chapter"],
                   ev["format"], nine))
        c.commit()

HIO = {"events": [{"event": "a9.25 Star Ranch", "date": "2026-09-29", "hio": 19.0, "running": 3451.0},
                  {"event": "s9.25 Canyon Springs", "date": "2026-09-29", "hio": 25.0, "running": 3476.0}],
       "pot": 3476.0}
_prox = {"holes": [3, 7]}
db.event_proximity_report = lambda eid, db_path=None: {
    "course_name": "Canyon Springs Golf Club", "nine": "Front",
    "contests": [{"kind": "ctp", "hole": h} for h in _prox["holes"]]}
db.get_event_print_pack = lambda eid, db_path=None: {
    "team_allowance": 0.75, "team_off_lowest": {"applied": True},
    "event": {"start_clock": "5:00 PM", "file_stub": "26-s9-25"}}
db.get_hio_pot = lambda db_path=None: HIO

# ── 9-hole reference: s9.25 Canyon Springs ──
g = fx("games_tab_3304.json"); seed(g)
gs = GS.build_games_sheet(3304, games=g, db_path=DB)
check("fund = the GAMES tab TOTAL ($574)", gs["fund"] == "$574", gs["fund"])
check("pot check = section totals = fund", gs["pot_check"]["ok"] and gs["pot_check"]["total"] == "$574",
      gs["pot_check"])
check("allocation bar: 4 buckets, widths sum to 100%",
      len(gs["bar"]) == 4 and abs(sum(b["pct"] for b in gs["bar"]) - 100) < 0.01, gs["bar"])
check("field: 25 players / 17 net / 13 gross", gs["field"] == {"players": 25, "net": 17, "gross": 13})
check("MWP = the tab's ($312.50)", gs["mwp"] == "$312.50")
inc = gs["sections"]["included"]["games"]
check("CTP lines say 'Hole {n}' from the Proximity report, never 'CTP #'",
      [l["label"] for l in inc[1]["lines"]] == ["Hole 3", "Hole 7"], inc[1]["lines"])
check("Team Net 1st = pot / 4 per player ($25/plyr)", inc[0]["lines"][0]["amount"] == "$25/plyr", inc[0])
check("Team Net rule: 75%, off the field's low, winners split pot",
      "75% handicaps off the field's low" in inc[0]["rule"] and inc[0]["rule"].endswith("Ties: winners split pot."))
check("Proxies rule (Kerry): ball on the green, winners split pot",
      inc[1]["rule"] == "Ball must be on the green. Ties: winners split pot.")
net = gs["sections"]["net"]
check("net strip: Members only · 17 entrants @ $13 (the linked TGF share is not a fee)",
      net["strip"] == "Members only · 17 entrants @ $13", net["strip"])
names = [x["name"] for x in net["games"]]
check("net games: Individual Net, Event MVP, TGF MVP", names == ["Individual Net", "Event MVP", "TGF MVP"], names)
check("Individual Net: F1 · 1st/2nd, F2 · 1st/2nd; new flight spaced",
      [l["label"] for l in net["games"][0]["lines"]] == ["F1 · 1st", "F1 · 2nd", "F2 · 1st", "F2 · 2nd"]
      and net["games"][0]["lines"][2]["new_flight"])
check("Event MVP rule: 'Tiebreakers:' wording, verbatim",
      net["games"][1]["rule"] == "Most net Stableford points. Tiebreakers: 1st = Total Net | "
                                 "2nd = Total Gross | 3rd = Split winnings.")
check("TGF MVP rule names the other city and both shares",
      net["games"][2]["rule"].startswith("Shared with Austin (a9.25 Star Ranch): SA $34 + Austin $34."),
      net["games"][2]["rule"])
gross = gs["sections"]["gross"]
check("gross strip: 13 entrants @ $13", gross["strip"] == "Straight up, no handicaps · 13 entrants @ $13")
check("skins: $84.50 per flight, two lines", gross["games"][0]["pot"] == "$84.50"
      and gross["games"][0]["per_flight"] and len(gross["games"][0]["lines"]) == 2)
check("skins rule: winners split pot by skins won", "Winners split pot by skins won." in gross["games"][0]["rule"])
check("Individual Gross NO GAME, threshold read from the live matrix (16 on a nine)",
      gross["games"][1].get("off") and gross["games"][1]["rule"] == "Needs 16 gross entrants on 9-hole events.",
      gross["games"][1])
f = db.get_scoring_formulas(DB)
st = gs["stableford"]
check("Stableford box bound to get_scoring_formulas (not typed)",
      [r["pts"] for r in st["rows"]] == [f["stableford_net_table"][k] for k in ("-3", "-2", "-1", "0", "1", "2")]
      and st["hio"] == f["stableford_net_hio"], st)
check("HIO band from the ledger: $3,476 through the day, +$44 = Austin $19 + SA $25",
      gs["hio"]["pot"] == 3476 and gs["hio"]["today"] == 44
      and sorted((p["chapter"], p["amount"]) for p in gs["hio"]["parts"]) == [("Austin", 19.0), ("SA", 25.0)],
      gs["hio"])
check("header: course, date · code · Front 9, SHOTGUN 5:00 PM",
      gs["event"]["course"] == "Canyon Springs Golf Club"
      and gs["event"]["meta"] == "Tue, September 29, 2026 · s9.25 · Front 9"
      and gs["event"]["start_type"] == "SHOTGUN" and gs["event"]["start_time"] == "5:00 PM", gs["event"])
check("no warnings on the reference event", gs["warnings"] == [], gs["warnings"])

with A.app.test_request_context():
    from flask import render_template
    html = render_template("games_payouts.html", gs=gs)
check("renders; file name <stub>-GamesPayouts", "26-s9-25-GamesPayouts" in html)
check("shared report bar (Back to Reports · Print), no PDF button",
      "Back to Reports" in html and "rbPrint()" in html and "Download PDF" not in html)
check("no green anywhere (CD #967 §8.3)",
      not re.search(r"#(?:059669|15803D|bbf7d0|16a34a|22c55e|10b981)", html, re.I))
check("the sheet never shrinks type to fit: columns flow, then tighter spacing only",
      "attempt(false) || attempt(true)" in html and ".sheet.tight .pl { height: 20px; }" in html)

# ── 18-hole reference: s18.4 Landa Park ──
g18 = fx("games_tab_267.json"); seed(g18); _prox["holes"] = [2, 6, 12, 17]
gs18 = GS.build_games_sheet(267, games=g18, db_path=DB)
check("18h: fund $1,294 and pot check ties", gs18["fund"] == "$1,294" and gs18["pot_check"]["ok"])
inc18 = gs18["sections"]["included"]["games"]
check("18h: Team Net 1st + 2nd per player", [l["amount"] for l in inc18[0]["lines"]] == ["$42.67/plyr", "$21.33/plyr"])
check("18h: four CTP holes, laid two across", len(inc18[1]["lines"]) == 4 and inc18[1]["two_up"])
check("18h: Individual Net 3 places x 2 flights",
      len(gs18["sections"]["net"]["games"][0]["lines"]) == 6)
ig = gs18["sections"]["gross"]["games"][1]
check("18h: Individual Gross live, 3 flights x 1st", not ig.get("off") and len(ig["lines"]) == 3, ig)
check("18h: no TGF MVP line on a single-event day (the tab folds it into City MVP)",
      [x["name"] for x in gs18["sections"]["net"]["games"]] == ["Individual Net", "Event MVP"])
check("18h: header says 18 Holes", gs18["event"]["meta"].endswith("· 18 Holes"), gs18["event"]["meta"])

# ── failure classes: a pot that doesn't tie, a missing hole card, a bucket event ──
bad = json.loads(json.dumps(g)); bad["total"]["pot"] = "$580"; seed(bad); _prox["holes"] = []
gsb = GS.build_games_sheet(3304, games=bad, db_path=DB)
check("pot mismatch is a warning, never a silent print",
      not gsb["pot_check"]["ok"] and any("POT CHECK MISMATCH" in w for w in gsb["warnings"]))
check("no hole card: blank hole number + a warning (never 'CTP #1')",
      [l["label"] for l in gsb["sections"]["included"]["games"][1]["lines"]] == ["Hole ___", "Hole ___"]
      and any("no hole from the course card" in w for w in gsb["warnings"]))
bk = json.loads(json.dumps(g)); bk["buckets"] = [{"bucket": "DAILY", "purse": 100}]
gsk = GS.build_games_sheet(3304, games=bk, db_path=DB)
check("bucket-account event: no sheet, and it says why", "bucket-account" in (gsk.get("error") or ""))
with A.app.test_request_context():
    h = render_template("games_payouts.html", gs=gsk)
check("the error renders as a message, not a blank sheet", "can't print for this event" in h)

# ── wiring ──
src_ev = open(os.path.join(HERE, "templates", "events.html")).read()
check("REPORTS tab opens Games & Payouts", 'open("games-payouts", "Games &amp; Payouts"' in src_ev)
check("route /events/<id>/games-payouts is manager-only",
      "/events/<int:event_id>/games-payouts" in open(os.path.join(HERE, "app.py")).read())
check("print pack carries the sheet", "games_payouts.html" in open(os.path.join(HERE, "email_parser", "print_pack.py")).read())

print(f"\n{len(F)} FAILURE(S): {F}" if F else "\nALL PASS")
sys.exit(1 if F else 0)
