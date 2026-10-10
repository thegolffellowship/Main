"""The combined Saturday cart sign (Kerry 2026-10-09: "Don't need Sat PM Cart
signs because players will have the same cart ... combined cart sign for
Saturday where everything is the same except both morning and afternoon
times show" / "1. Combined"). One sign per cart pair: the AM row (weekend
match no., tee, hole, AM group QR) over the PM row; the Cup print files carry
it instead of separate Sat AM and Sat PM signs.

Run: python3 test_cup_sat_combined_signs.py
"""
import os, sys, json, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="tgf-satsign-"), "t.db")
os.environ.setdefault("SECRET_KEY", "x")
logging.disable(logging.ERROR)
import app as A                                        # noqa: E402
from email_parser import score_entry                   # noqa: E402
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


DIAL = {"sessions": [
    {"id": "sat-am", "matches": [{"austin": [7, 294], "sa": [136, 88]}, {"austin": [13, 438], "sa": [18, 703]}]},
    {"id": "sat-pm", "matches": [{"austin": [7, 294], "sa": [18, 703]}, {"austin": [13, 438], "sa": [136, 88]}]}]}


def sign(sid, side, cids, last, tee, qr):
    return {"team": side.upper(), "color": "#000", "side": side, "cids": cids, "session": sid,
            "riders": [{"first": "X", "last": l} for l in last], "tee_time": tee, "hole": "1",
            "qr_svg": f"<svg>{qr}</svg>", "url": qr}


FAKE = {
    "sat-am": [sign("sat-am", "austin", [7, 294], ["JENKINS", "JENKINS"], "8:30", "am1"),
               sign("sat-am", "sa", [136, 88], ["YOUNGS", "YOUNG"], "8:30", "am1"),
               sign("sat-am", "austin", [13, 438], ["YOUNGS", "CANNON"], "8:40", "am2"),
               sign("sat-am", "sa", [18, 703], ["NIESTER", "MESA"], "8:40", "am2")],
    "sat-pm": [sign("sat-pm", "austin", [7, 294], ["JENKINS", "JENKINS"], "1:30", "pm1"),
               sign("sat-pm", "sa", [18, 703], ["NIESTER", "MESA"], "1:30", "pm1"),
               sign("sat-pm", "austin", [13, 438], ["YOUNGS", "CANNON"], "1:40", "pm2"),
               sign("sat-pm", "sa", [136, 88], ["YOUNGS", "YOUNG"], "1:40", "pm2")]}
A.cup_cart_signs_data = lambda eid, preview=False, session_id=None: {
    "event": {"id": eid}, "pages": [FAKE[session_id][i:i + 2] for i in range(0, 4, 2)],
    "count": 4, "qr_on": True, "problems": []}
score_entry._json_setting = lambda key, db_path=None: DIAL if key == "lsc_matches" else {}

d = A.cup_saturday_combined_signs_data(3329)
signs = [s for pg in d["pages"] for s in pg]
check("one sign per cart pair (4), two to a sheet", d["count"] == 4 and len(d["pages"]) == 2 and not d["problems"], d)
yy = next(s for s in signs if s["riders"][0]["last"] == "YOUNGS" and s["side"] == "sa")
check("Youngs & Young: AM 8:30 Match 1 with the AM QR, PM 1:40 Match 4 with the PM QR",
      [(x["tee_time"], x["lab"], x["qr_svg"]) for x in yy["slots"]] == [
          ("8:30", "SAT AM · FOURBALL · MATCH 1", "<svg>am1</svg>"),
          ("1:40", "SAT PM · FOURSOMES · MATCH 4", "<svg>pm2</svg>")], yy["slots"])
nm = next(s for s in signs if s["riders"][0]["last"] == "NIESTER")
check("Niester & Mesa: AM Match 2 8:40, PM Match 3 1:30",
      [(x["tee_time"], x["lab"][-7:]) for x in nm["slots"]] == [("8:40", "MATCH 2"), ("1:30", "MATCH 3")], nm["slots"])
with A.app.app_context():
    html = A._print_pack_render("cup_cart_signs.html", d=d)
check("the template prints both rows and both QRs on a combined sign",
      html.count('class="slot"') == 8 and "SCAN AM SCORE" in html and "SCAN PM SCORE" in html
      and "<svg>pm2</svg>" in html and 'class="band two"' in html)
FAKE["sat-pm"] = FAKE["sat-pm"][:3]
d2 = A.cup_saturday_combined_signs_data(3329)
check("a pair missing from the PM is a problem, never a half sign",
      d2["count"] == 3 and any("no Sat PM sign" in p for p in d2["problems"]), d2["problems"])
src = open("app.py", encoding="utf-8").read()
check("the Cup print files carry the combined sign, no separate Sat PM signs",
      "combine_saturday: bool = True" in src and 'cup_saturday_combined_signs_data(int(event_id))' in src
      and '"Sat-AM-PM-CartSigns"' in src)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
