"""LONE STAR CUP STAFF PREVIEW (Kerry 10/7, CoS #1398-B): demo rounds on
their own dial and PREVIEW rounds; the live dial, the live rounds and the
member board are never touched. Run: python3 test_lsc_preview.py"""
import contextlib, io, json, logging, os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)
from email_parser import score_entry as se, lsc_cup, lsc_preview, entry_publish as ep  # noqa: E402
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)

AUS = [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]
SA = [201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214]
c = sqlite3.connect(DB)
course_id = c.execute("INSERT INTO courses (name, status) VALUES ('The Hideout', 'active') RETURNING course_id").fetchone()[0]
tee = c.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, slope, tgf_bands, source) "
                "VALUES (?, 'Blue', 'M', 18, 'full', 71.7, 129, '<50,50-64,65+,Forward', 'admin') RETURNING tee_id", (course_id,)).fetchone()[0]
for h in range(1, 19):
    c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, stroke_index) VALUES (?,?,?,?)",
              (tee, h, 3 if h in (4, 13) else 5 if h in (7, 16) else 4, h))
c.execute("INSERT INTO events (id, item_name, event_date, course_id) VALUES (3329, 'LONE STAR CUP | The Hideout', '2026-10-10', ?)", (course_id,))
for cid in AUS + SA:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, 'P', ?)", (cid, str(cid)))
c.commit(); c.close()
pairs = {"austin": [{"id": f"A{i}", "cids": AUS[2*i:2*i+2], "combined_ch": i*5, "pool": "low" if i < 3 else "high"} for i in range(7)],
         "sa": [{"id": f"S{i}", "cids": SA[2*i:2*i+2], "combined_ch": i*5, "pool": "low" if i < 3 else "high"} for i in range(7)]}
live = {"event_id": 3329, "defending_champion": "sa", "board_live": False, "pairs": pairs,
        "tee_sheet": {"sat-am": ["8:30", "8:40", "8:50", "9:00", "9:10", "9:20", "9:30"],
                      "sat-pm": ["1:30", "1:40", "1:50", "2:00", "2:10", "2:20", "2:30"],
                      "sun": ["8:30", "8:40", "8:50", "9:00", "9:10", "9:20", "9:30"]},
        "sessions": [{"id": "sat-am", "label": "FOURBALL", "format": "fourball", "date": "2026-10-10",
                      "n_holes": 18, "se_round": None, "matches": [{"id": "SAT-AM-1", "austin": AUS[:2], "sa": SA[:2]}]}]}
db.set_app_setting("lsc_matches", json.dumps(live), db_path=DB)
db.set_app_setting("lsc_handicap_lock", json.dumps({"3329": {"players": {str(c_): {"ch": (c_ % 100) % 20} for c_ in AUS + SA}}}), db_path=DB)
db.set_app_setting("lsc_tees", json.dumps({"3329": {"course_id": course_id, "players": {str(c_): {"band": "50-64"} for c_ in AUS + SA}}}), db_path=DB)
live_before = db.get_app_setting("lsc_matches", db_path=DB)

dry = lsc_preview.seed(db_path=DB)
check("dry run writes nothing", dry.get("dry_run") and not db.get_app_setting(se.PREVIEW_DIAL, db_path=DB), dry)
check("dry run plans 7 / 7 / 14 matches", [s["matches"] for s in dry["sessions"]] == [7, 7, 14], dry)
res = lsc_preview.seed(apply=True, db_path=DB)
check("seed applies", res.get("seeded"), res)
check("session titles FOURBALL · FOURSOMES · SINGLES", list(res["rounds"]) == ["FOURBALL", "FOURSOMES", "SINGLES"], res)
check("the live dial is untouched", db.get_app_setting("lsc_matches", db_path=DB) == live_before)
read = se.get_entered_scores(3329, db_path=DB)
check("every round on the event is a PREVIEW round", read["rounds"] and all(ep._is_preview(r) for r in read["rounds"]),
      [r["label"] for r in read["rounds"]])
b = lsc_cup.preview_board_payload(db_path=DB)
sess = {s["id"]: s for s in b.get("sessions") or []}
check("preview board configured and flagged", b.get("configured") and b.get("preview"), b.get("configured"))
check("FOURBALL: all 7 matches final", [m["state"] for m in sess["sat-am"]["matches"]] == ["final"] * 7,
      [m["state"] for m in sess["sat-am"]["matches"]])
check("FOURSOMES: matches in play", all(m["state"] in ("live", "final") for m in sess["sat-pm"]["matches"])
      and any(m["state"] == "live" for m in sess["sat-pm"]["matches"]), [m["state"] for m in sess["sat-pm"]["matches"]])
pm1 = sess["sat-pm"]["matches"][0]
check("FOURSOMES match 1 closed out 2&1", pm1["state"] == "final" and "2&1" in json.dumps(pm1),
      {k: pm1.get(k) for k in ("state", "gg_margin", "status")})
check("SINGLES: not started", all(m["state"] == "upcoming" for m in sess["sun"]["matches"]))
mb = lsc_cup.lsc_board_payload(db_path=DB)
check("the member board never reads the demo", mb.get("source") != "entry" and not mb.get("preview"), mb.get("source"))
check("a picked-up mark was written", any(p.get("marks") for r in read["rounds"] for p in r["players"]))
check("publish refuses PREVIEW rounds", all(not r.get("written") and not r.get("would_write")
      for r in ep.publish_event(3329, db_path=DB).get("rounds") or []))
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    os.environ.setdefault("SECRET_KEY", "test-only"); os.environ["TGF_REHEARSAL"] = "1"
    import app as appmod
cs = appmod.cup_cart_signs_data(3329, preview=True, session_id="sat-am")
signs = [x for pg in cs["pages"] for x in pg]
check("cart signs: one per cart pair, two to a page, team-themed with the group's QR",
      cs["count"] == 14 and all(len(pg) <= 2 for pg in cs["pages"]) and {x["cls"] for x in signs} == {"aus", "sa"}
      and all(len(x["names"]) == 2 and x["qr_svg"] and "/member/score?t=" in x["url"] for x in signs), cs["count"])
check("cart sign start and match line", signs[0]["start"].endswith("Hole 1") and signs[0]["match"].startswith("Sat AM Fourball · Match 1 · v "),
      signs[0])
sun = [x for pg in appmod.cup_cart_signs_data(3329, preview=True, session_id="sun")["pages"] for x in pg]
check("Sunday signs name each player's own opponent", sun and all(" · v " in x["match"] for x in sun), sun[:1])
check("the live sign sheet never reads the demo rounds", appmod.cup_cart_signs_data(3329)["count"] == 0)
held = [g for r in read["rounds"] for g in r.get("groups") or [] if g.get("lock_state") == "held"]
check("exactly one demo group stays held (the HELD screen)", len(held) == 1, len(held))
td = lsc_preview.teardown(db_path=DB)
check("teardown closes the preview rounds and clears the dial", len(td["closed_rounds"]) == 3
      and not db.get_app_setting(se.PREVIEW_DIAL, db_path=DB), td)
res2 = lsc_preview.seed(apply=True, db_path=DB)
read2 = se.get_entered_scores(3329, db_path=DB)
check("a re-seed after teardown re-opens the same PREVIEW rounds",
      res2.get("seeded") and all(r.get("status") == "open" for r in read2["rounds"]), [r.get("status") for r in read2["rounds"]])
b2 = {s["id"]: s for s in lsc_cup.preview_board_payload(db_path=DB).get("sessions") or []}
check("after the re-seed FOURSOMES is in play again with match 1 closed 2&1",
      b2["sat-pm"]["matches"][0]["state"] == "final" and "2&1" in json.dumps(b2["sat-pm"]["matches"][0])
      and any(m["state"] == "live" for m in b2["sat-pm"]["matches"]), [m["state"] for m in b2["sat-pm"]["matches"]])
lsc_preview.teardown(db_path=DB)
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}"); sys.exit(1 if F else 0)
