"""The Add Player modal offers what THIS event actually has (Kerry
2026-09-21: "responsive to what is actually available based on the event,
rather than a standard list of selections that make me choose").

Run: python3 test_add_player_options.py
"""
import os, sys, tempfile, logging, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)

with db._connect(DB) as conn:
    conn.execute("INSERT INTO courses (course_id, name) VALUES (501, 'Brackenridge Park')")
    conn.executemany("INSERT INTO course_tees (course_id, tee_name, gender, holes, rating, slope, tgf_bands) VALUES (?,?,?,?,?,?,?)", [
        (501, "Blue", "M", 18, 69.1, 118, "<50"), (501, "White", "M", 18, 67.0, 112, "50-64,65+"),
        (501, "Red", "F", 18, 69.5, 115, "Forward")])
    conn.executemany("INSERT INTO events (id, item_name, event_date, chapter, status, format, course, course_id, side_game_fee, side_game_fee_9, per_game_addon) VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        (9101, "s9.24 Brackenridge", "2026-09-22", "San Antonio", "active", "9 Holes", "Brackenridge Park", 501, 7.0, None, None),
        (9102, "s18.12 Somewhere", "2026-10-03", "San Antonio", "active", "18 Holes", "No Card GC", None, 14.0, None, None),
        (9103, "a9.27 Combo Night", "2026-10-06", "Austin", "active", "Combo", "No Card GC", None, None, 7.0, None),
        (9104, "2026 TGF CHAMPIONSHIP", "2026-08-14", "San Antonio", "active", "18 Holes", "Lost Pines", None, 14.0, None, None),
        (9105, "SOCIAL | Range Night", "2026-10-10", "San Antonio", "active", "9 Holes", "No Card GC", None, None, None, None)])
    for i, (cid, sg, st) in enumerate([(1, "NET", "active"), (2, "BOTH", "active"), (3, "NONE", "active"),
                                       (4, "GROSS", "credited"), (5, "Net", "active")]):
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, side_games, transaction_status, order_date, order_id, email_uid, merchant) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (f"P {cid}", 700 + cid, "s9.24 Brackenridge", 9101, "9", sg, st, "2026-09-10", f"R{i}", f"manual-{i}", "GoDaddy"))
    conn.commit()
db.set_event_packages(9104, [{"label": "Both Days + Games", "price": 300}, {"label": "One Day", "price": 150, "holes": 18}], db_path=DB)

o = db.add_player_options(9101, DB)
check("a nine offers 9 and only 9", o["holes"] == ["9"], o["holes"])
check("side games follow the EVENT SETUP: a games fee on the event offers Net / Gross / Both / None whatever the roster has bought so far",
      o["side_games"] == ["Net", "Gross", "Both", "None"], o["side_games"])
check("an event with NO games fee in its setup offers None only", db.add_player_options(9105, DB)["side_games"] == ["None"], db.add_player_options(9105, DB))
check("a combo's per-nine fee counts as a games fee", db.add_player_options(9103, DB)["side_games"] == ["Net", "Gross", "Both", "None"])
check("tees = the course record's designated bands, each with its tee name",
      [t["value"] for t in o["tees"]] == ["<50", "50-64", "65+", "Forward"] and o["tees"][0]["label"] == "Men <50 · Blue Tees", o["tees"])
check("sources say where each list came from", o["sources"] == {"holes": "format", "side_games": "event setup: games offered NET/GROSS/BOTH", "tees": "course record"}, o["sources"])
o2 = db.add_player_options(9102, DB)
check("an 18 offers 18 only", o2["holes"] == ["18"], o2["holes"])
check("an empty roster offers the same four", o2["side_games"] == ["Net", "Gross", "Both", "None"], o2["side_games"])
check("no course card → the standard four bands", [t["value"] for t in o2["tees"]] == list(db.TEE_BANDS), o2["tees"])
o3 = db.add_player_options(9103, DB)
check("a combo offers both nines and eighteens", o3["holes"] == ["9", "18"], o3["holes"])
o4 = db.add_player_options(9104, DB)
check("packages add the hole counts they sell (36 from the label, 18 explicit)", o4["holes"] == ["18", "36"], o4["holes"])
check("unknown event → None", db.add_player_options(424242, DB) is None)
check("side-games spellings normalise", [db._norm_side_games(v) for v in ("Net + Gross", "gross", "", "NONE", "Both", "??")]
      == ["Both", "Gross", "None", "None", "Both", None])

import app as appmod                                              # noqa: E402
c = appmod.app.test_client()
with c.session_transaction() as s_:
    s_["role"] = "manager"; s_["authenticated"] = True
r = c.get("/api/events/9101/add-player-options")
check("GET /api/events/<id>/add-player-options serves it to a manager", r.status_code == 200 and r.get_json()["holes"] == ["9"], (r.status_code, r.get_data()[:120]))
check("…404 for an unknown event", c.get("/api/events/424242/add-player-options").status_code == 404)
try: os.unlink(DB)
except OSError: pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
