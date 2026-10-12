"""Lone Star Cup record on the Spotlight (Kerry 2026-10-12) and this season's
contests staying in the main WHERE X STANDS list.

Run: python3 test_lsc_record.py
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from email_parser import lsc_record as R   # noqa: E402
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


def side(name, *cids):
    return {"name": name, "customer_ids": list(cids), "lines": name.split(" & ")}


def match(mid, au, sa, win, margin="3&2", state="final"):
    pts = {"austin": 1.0 if win == "au" else (0.5 if win == "h" else 0.0),
           "sa": 1.0 if win == "sa" else (0.5 if win == "h" else 0.0)}
    return {"match_id": mid, "state": state, "points": pts, "gg_margin": margin, "players": [au, sa]}


board = {"configured": True, "source": "final",
         "cup": {"winner": "sa", "defending_champion": "sa", "status": "won"},
         "teams": {"austin": {"points": 10.5}, "sa": {"points": 17.5}},
         "sessions": [
             {"id": "sat-am", "title": "FOURBALL", "date": "2026-10-10", "matches": [
                 match("SAT-AM-4", side("Julius Jenkins & Kaleb McDonnell", 304, 688),
                       side("Gus Vasquez & Chuck Fehlis", 42, 130), "au", "3&2")]},
             {"id": "sat-pm", "title": "FOURSOMES", "date": "2026-10-10", "matches": [
                 match("SAT-PM-4", side("Jay Hogue & Walter Hogue", 37, 834),
                       side("Gus Vasquez & Chuck Fehlis", 42, 130), "sa", "1 UP"),
                 match("SAT-PM-1", side("Matt Jenkins & Mike Jenkins", 1, 2),
                       side("Kerry Niester & Michael Mesa", 18, 3), "h", None)]},
             {"id": "sun", "title": "SINGLES", "date": "2026-10-11", "matches": [
                 match("SUN-8", side("Kaleb McDonnell", 688), side("Gus Vasquez", 42), "sa", "5&3"),
                 match("SUN-LIVE", side("A", 9), side("B", 8), "sa", "1 UP", state="live")]}]}

g = R.player_record(board, 42, 2026)
check("Gus: 2-1 from the final board, one line per match in play order",
      g and g["text"] == "2–1" and [m["match_id"] for m in g["matches"]] == ["SAT-AM-4", "SAT-PM-4", "SUN-8"], str(g))
check("results read from the player's own side (side 0 is Austin, side 1 San Antonio)",
      [m["result"] for m in g["matches"]] == ["L", "W", "W"] and g["team"] == "sa" and g["team_name"] == "San Antonio")
check("margins, partners and opponents come with each match",
      g["matches"][0]["margin"] == "3&2" and g["matches"][0]["partners"] == ["Chuck Fehlis"]
      and g["matches"][0]["opponents"] == ["Julius Jenkins", "Kaleb McDonnell"]
      and g["matches"][2]["partners"] == [] and g["matches"][2]["opponents"] == ["Kaleb McDonnell"])
check("the official session titles are used (FOURBALL / FOURSOMES / SINGLES), never 'Chapman'",
      [m["format"] for m in g["matches"]] == ["FOURBALL", "FOURSOMES", "SINGLES"])
check("the cup line says retained for the defending champion and orders the score high to low",
      g["cup_line"] == "Team San Antonio retained the Cup, 17½–10½", g["cup_line"])
check("Gus, whose SUN-8 win delivered the clinching point, is the clincher; his partner Chuck is not",
      g["clinched"] and g["clinch_team"] == "San Antonio" and not R.player_record(board, 130, 2026)["clinched"])
k = R.player_record(board, 18, 2026)
check("a halved match counts as a half and shows in the record as 0-0-1", k["h"] == 1 and k["text"] == "0–0–1"
      and k["matches"][0]["result"] == "H" and k["matches"][0]["margin"] is None, str(k))
a = R.player_record(board, 688, 2026)
check("an Austin player reads from the other side and does not clinch",
      a["team"] == "austin" and a["text"] == "1–1" and not a["clinched"], str(a))
check("a live match is not counted", R.player_record(board, 9, 2026) is None)
check("no record before the board is the final snapshot, or for someone who never played",
      R.player_record({**board, "source": "live"}, 42, 2026) is None and R.player_record(board, 999, 2026) is None
      and R.player_record({"configured": False}, 42, 2026) is None and R.player_record(None, 42, 2026) is None)
check("the cup's own season is read from its sessions, not today's date", R.player_record(board, 42, 2031)["year"] == 2026)

src = open(os.path.join(HERE, "templates", "spotlight.html")).read()
check("the LSC row shows the record where the seat was, with the clinch note and a link per match",
      "if (l.record)" in src and 'class="r${String(rc.text).length > 3 ? " long" : ""}">${esc(rc.text)}' in src and "cup record" in src
      and "?match=${encodeURIComponent(m.match_id)}" in src and "spt-lsc-clinch" in src and "clinched the" in src)
check("this season's completed contests stay in the main list and only earlier seasons fold into PAST CONTESTS",
      "seasonDone" in src and "if (y === curYear) { seasonDone.push(html); return; }" in src
      and "${esc(curYear)} Season" in src and "seasonMo" in src)
check("this season's monthly results fold into one collapsed line, and a decided cup reads Champion instead of a gap to 1st",
      "moFold" in src and "Monthly Results" in src and "spt-mo" in src and "isCupChamp" in src
      and 'metaBits.push("Champion")' in src)
db = open(os.path.join(HERE, "email_parser", "database.py")).read()
check("get_player_spotlight attaches the record from the shared cached board",
      "_spotlight_lsc_record(customer_id, db_path)" in db and '_spotlight_shared("lsc_board"' in db)
check("the LSC match lines fold under the record row behind the house chevron (right shut, down open) and a 1-1-1 record stays on one line",
      '<details class="spt-lsc-wrap">' in src and "details.spt-lsc-wrap[open] > summary .spt-win-chev { transform: rotate(90deg); }" in src
      and 'String(rc.text).length > 3 ? " long" : ""' in src and ".spt-stand .rk .r.long" in src and "white-space: nowrap" in src)
print("ALL PASS" if not F else f"FAILED: {F}")
sys.exit(1 if F else 0)
