"""TRACKER POINTS STANDINGS (Kerry 2026-10-13: "we're not running Golf Genius
at all tonight, so I'm relying on you and what we've built to make it all
happen now"; the 10/6 blind test ruled "Yes, 54 is right for Baker").

PARITY: Golf Genius's frozen lines through 9/29 + the Tracker's ruled 10/6
points must rebuild Golf Genius's OWN current Fall boards (10/6 awarded by
Kerry in GG) total for total, for every player, with exactly one difference:
Baker 54 (Tracker, locked PH 5) vs 53 (GG, PH 4). Mark Parker, a 1st Timer,
earns nothing (GG awarded him nothing). Then: an entered event's points
come from the engine, by home chapter, best 6; the Monthly month is built;
and the GG refresh path rebuilds from the Tracker while intake is off.
"""
import os, sys, json, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.WARNING)
import app as _appmod                                   # noqa: E402,F401
from email_parser import database as db                 # noqa: E402
from email_parser import tracker_points as tp           # noqa: E402
from email_parser import timezone_utils as tz           # noqa: E402
from datetime import date                               # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

GG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "data/points_baseline/fall_2026_gg_standings_1013.json")))["standings"]
RULED = json.load(open(tp.RULED_FILE))["events"]
LAST = {101: "SALDANA", 6: "RIDEOUT", 298: "STICH", 142: "MARROQUIN", 125: "MILLER", 82: "MAZANEC",
        313: "JOHNSON", 21: "PALACIOS", 87: "BAKER", 18: "NIESTER", 136: "YOUNGS, Pat", 131: "MURPHY",
        19: "THOMPSON", 24: "SOUTH", 709: "ANGELONE", 33: "WICKER", 103: "BOURQUIN", 93: "SKINNER",
        817: "LEWIS", 765: "McCORMICK, Michele", 38: "SHARITZ",
        439: "ZAPATA", 22: "BARTZ", 821: "AREVALO", 31: "STRAITON", 99: "VASQUEZ", 61: "MELCHOR",
        187: "GWIN", 13: "YOUNGS, Luke", 49: "POST", 166: "Compton", 10: "WILLIAMS", 438: "CANNON",
        85: "SCHNEIDER"}
SA = {str(c) for c in RULED["3308"]["points"]}
with db._connect(DB) as c:
    def gg_name(cid):
        race = "san_antonio_fall_net" if str(cid) in SA else "austin_fall_net"
        key = LAST[cid].lower()
        for r in GG[race]:
            if r["player_name"].lower().startswith(key):
                return r["player_name"]
        raise SystemExit(f"no GG name for {cid}")
    c.execute("DELETE FROM customers")
    c.execute("DELETE FROM gg_points_standings") if c.execute(
        "SELECT name FROM sqlite_master WHERE name = 'gg_points_standings'").fetchone() else None
    for cid in LAST:
        nm = gg_name(cid)
        last, first = [x.strip() for x in nm.split(",", 1)]
        c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, current_player_status) "
                  "VALUES (?, ?, ?, ?, 'active_member')",
                  (cid, first, last.title(), "San Antonio" if str(cid) in SA else "Austin"))
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, current_player_status) "
              "VALUES (833, 'Mark', 'Parker', 'Austin', 'first_timer')")
    # the live snapshot (GG's last rows) carries card -> customer_id, as production does
    db._ensure_gg_points_table(c)
    cards = {"12351479": 6, "12135103": 82, "11311131": 87, "183496": 18, "11126866": 24,
             "7144556": 142, "183850": 38, "13012450": 817, "9079869": 13, "12628130": 438}
    for rk, rows in GG.items():
        for r in rows:
            cid = cards.get(str(r["member_card_id"]))
            if rk == "austin_fall_net" and r["member_card_id"] == "12347458":
                c.execute("INSERT INTO gg_points_standings (race_key, rank, player_name, customer_id, tournaments, "
                          "wins, total_points, member_card_id, merged_from) VALUES (?,?,?,?,?,?,?,?,?)",
                          (rk, r["rank"], r["player_name"], 85, 6, 0, 36, "12347458",
                           json.dumps({"method": "sum", "records": [{"member_card_id": "12347458"},
                                                                     {"member_card_id": "13085037"}]})))
                continue
            if rk == "austin_fall_net" and r["member_card_id"] == "13085037":
                continue
            c.execute("INSERT INTO gg_points_standings (race_key, rank, player_name, customer_id, tournaments, "
                      "wins, total_points, member_card_id) VALUES (?,?,?,?,?,?,?,?)",
                      (rk, r["rank"], r["player_name"], cid, r["tournaments"], r["wins"],
                       r["total_points"], r["member_card_id"]))
    for eid, e in RULED.items():
        c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (?, ?, ?, ?, 'active')",
                  (int(eid), f"{e['code']} X", e["date"], e["chapter"]))
    c.commit()

tz.today_central = lambda: date(2026, 10, 13)
tz.today_central_str = lambda: "2026-10-13"

print("== parity with Golf Genius's own 10/13 boards ==")
lines, warns = tp.event_lines(db_path=DB)
check("the ruled 10/6 events give 35 lines", len(lines) == 35, (len(lines), warns))
check("Parker (1st Timer) is not a member line", [l["member"] for l in lines if l["customer_id"] == 833] == [False])
for rk in tp.TRACKER_RACES:
    b = tp.build_race(rk, db_path=DB, tracker_lines=lines)
    ours = {}
    for r in b["rows"]:
        for card in (r["cards"] or [r["member_card_id"]]):
            ours[str(card)] = r
    diffs = []
    seen_ids = set()
    for g in GG[rk]:
        r = ours.get(str(g["member_card_id"]))
        if r is None:
            diffs.append(("missing", g["player_name"]))
            continue
        if id(r) in seen_ids:
            continue
        seen_ids.add(id(r))
        gg_total = g["total_points"]
        if rk == "austin_fall_net" and g["player_name"].startswith("SCHNEIDER"):
            gg_total = 37        # GG shows two records (31 + 6); one person = one row
        if abs(r["total_points"] - gg_total) > 0.001:
            diffs.append((g["player_name"], r["total_points"], gg_total))
    expect = [("BAKER, Adam", 54.0, 53)] if rk == "san_antonio_fall_net" else []
    check(f"{rk}: every total matches GG except the ruled Baker", diffs == expect, diffs)
    check(f"{rk}: nobody extra (row count = GG's people)",
          len(b["rows"]) == len({str(g["member_card_id"]) for g in GG[rk]}) - (1 if rk == "austin_fall_net" else 0),
          (len(b["rows"]), len(GG[rk])))
sa = tp.build_race("san_antonio_fall_net", db_path=DB, tracker_lines=lines)
miller = next(r for r in sa["rows"] if r["customer_id"] == 125)
check("Miller (no GG line before 10/6) appears with his 9", miller["total_points"] == 9.0 and miller["tournaments"] == 1, miller)
rid = next(r for r in sa["rows"] if r["customer_id"] == 6)
check("Rideout: 10 tournaments, a 6 drops, 60", rid["total_points"] == 60 and rid["tournaments"] == 10
      and sum(1 for l in rid["lines"] if l["counted"]) == 6, rid)
check("the top of SA Fall reads Rideout 60, Mazanec 55, Baker 54",
      [(r["player_name"], r["total_points"]) for r in sa["rows"][:3]]
      == [("RIDEOUT, Jeff", 60.0), ("MAZANEC, Luke", 55.0), ("BAKER, Adam", 54.0)], sa["rows"][:3])

print("== row expansion from our own lines ==")
d = tp.member_detail("san_antonio_fall_net", "12351479", db_path=DB)
t = d["tables"][0]
check("GG-shaped table: header, 6 counted, separator, the rest",
      t[0][0] == "Event" and t[7] == ["The following points are not counted in standings"] and len(t) == 1 + 6 + 1 + 4, t)
check("the 10/6 line is marked as the Tracker's", any("s9.26" in row[1] and "(Tracker)" in row[1] for row in t[1:]), t)

print("== an entered event scores from the engine ==")
with db._connect(DB) as c:
    c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES "
              "(3307, 's9.27 The Quarry', '2026-10-13', 'San Antonio', 'active')")
    c.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, holes_played, "
              "playing_handicap, source) VALUES (101, 'Jesse Saldana', 3307, '2026-10-13', 9, 15, 'entry')")
    c.commit()
_es = db.event_engine_state
db.event_engine_state = lambda name, db_path=None: {"meta": {"event_id": 3307, "event_name": name, "holes": 9,
    "championship": False}, "holes": [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 10)],
    "players": [{"key": "1", "customer_id": 101, "name": "SALDANA, Jesse", "playing_handicap": 9,
                 "scores": {h: 4 for h in range(1, 10)}},
                {"key": "2", "customer_id": 833, "name": "PARKER, Mark", "playing_handicap": 0,
                 "scores": {h: 4 for h in range(1, 10)}}]}
lines2, w2 = tp.event_lines(db_path=DB)
q = [l for l in lines2 if l["event_id"] == 3307]
check("net birdie on all 9 (PH 9) = 18 points for Saldana", any(l["customer_id"] == 101 and l["points"] == 18 for l in q), q)
sa2 = tp.build_race("san_antonio_fall_net", db_path=DB, tracker_lines=lines2)
sal = next(r for r in sa2["rows"] if r["customer_id"] == 101)
check("Saldana's 18 lands in SA Fall (home chapter)", 18.0 in [l["points"] for l in sal["lines"]], sal["lines"])
oct_ = tp.monthly_best("2026-10", tracker_lines=lines2)
check("October Monthly sums every point in the month (13 + 18)", oct_[101]["points"] == 31 and oct_[101]["rounds"] == 2, oct_.get(101))
check("...members only", 833 not in oct_)
db.event_engine_state = _es

print("== the refresh path rebuilds from the Tracker while intake is off ==")
try:
    db.refresh_points_race_standings("san_antonio_fall_net", db_path=DB)
    refused = False
except RuntimeError:
    refused = True
check("without points_source=tracker the GG refresh is still refused", refused)
db.set_app_setting("points_source", "tracker", db_path=DB)
n = db.refresh_points_race_standings("san_antonio_fall_net", db_path=DB)
with db._connect(DB) as c:
    top = c.execute("SELECT player_name, total_points FROM gg_points_standings WHERE race_key = "
                    "'san_antonio_fall_net' ORDER BY total_points DESC LIMIT 1").fetchone()
check("with points_source=tracker it writes the Tracker's rows", n > 40 and top and top[1] >= 60, (n, tuple(top) if top else None))
snap = db.load_gg_snapshot("monthly_points", DB) or {}
check("...and the Tracker's October lands in the monthly snapshot",
      any(m.get("month") == "2026-10" and m.get("source") == "tracker" for m in snap.get("months") or []), snap)
st = db.get_points_race_standings("austin_fall_net", db_path=DB, force_refresh=True)
check("a forced board read rebuilds Austin from the Tracker, no GG error", not st.get("gg_error"), st.get("gg_error"))

print("\nALL PASS" if not F else f"\n{len(F)} FAILED: " + "; ".join(F))
sys.exit(1 if F else 0)
