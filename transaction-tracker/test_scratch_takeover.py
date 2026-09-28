"""Scratch entry takeover (CA #811, GO #829): the guards refuse anything
that is not the rehearsal copy; on a scratch file the shadow diff is saved
FIRST, GG rows are parked (same ids) inside the file, the cutover moves back,
entered scores publish authoritatively, and --undo puts it all back.

Run: python3 test_scratch_takeover.py
"""
import contextlib
import io
import json
import logging
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
TMP = Path(tempfile.mkdtemp())
(TMP / "rehearsal").mkdir()
DB = TMP / "rehearsal" / "transactions.db"
os.environ["DATABASE_PATH"] = str(DB)
os.environ["TGF_REHEARSAL"] = "1"
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(str(DB))
from email_parser import score_entry as se  # noqa: E402
import scratch_entry_takeover as tk  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


def refused(path, argv, env):
    try:
        tk.refuse_unless_scratch(str(path), argv, env)
    except SystemExit as e:
        return str(e)
    return None


def q(sql, args=()):
    c = sqlite3.connect(DB)
    try:
        return c.execute(sql, args).fetchall()
    finally:
        c.close()


print("guards")
prod_like = TMP / "transactions.db"
prod_like.write_bytes(b"")
check("no --i-am-scratch is refused", "i-am-scratch" in (refused(DB, [], {}) or ""))
check("a file outside rehearsal/ without 'scratch' is refused",
      "rehearsal" in (refused(prod_like, ["--i-am-scratch"], {}) or ""))
check("the environment's live DATABASE_PATH is refused",
      "DATABASE_PATH" in (refused(DB, ["--i-am-scratch"], {"DATABASE_PATH": str(DB)}) or ""))
check("a missing file is refused", refused(TMP / "rehearsal" / "nope.db", ["--i-am-scratch"], {}))
named = TMP / "copy-scratch.db"
named.write_bytes(b"")
check("a file named *scratch* is accepted", refused(named, ["--i-am-scratch"], {}) is None)
check("the rehearsal copy is accepted",
      refused(DB, ["--i-am-scratch"], {"DATABASE_PATH": "/data/transactions.db"}) is None)

print("fixture: a played event (9/24) with GG rows and an entered, signed card")
EV = 3309
conn = sqlite3.connect(DB)
conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (301,'Kerry','Niester')")
cid_course = conn.execute("INSERT INTO courses (name, status) VALUES ('Brack', 'active') "
                          "RETURNING course_id").fetchone()[0]
conn.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, slope, "
             "tgf_bands, source) VALUES (?, 'White', 'M', 9, 'front', 34.0, 120, '50-64', 'admin')",
             (cid_course,))
conn.execute("INSERT INTO events (id, item_name, event_date, course_id) VALUES (?,?,?,?)",
             (EV, "s9.24 Brackenridge", "2026-09-24", cid_course))
gg_id = conn.execute(
    "INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, holes_played, "
    "gross, source) VALUES (301, 'Kerry Niester', ?, '2026-09-24', 9, 42, 'gg') RETURNING id",
    (EV,)).fetchone()[0]
for h in range(1, 10):
    conn.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes) VALUES (?,?,?)",
                 (gg_id, h, 5 if h == 3 else 4 + (h == 9)))
conn.commit()
conn.close()
NINE = [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 10)]
CARD = {h: 4 for h in range(1, 10)}
CARD[9] = 6                                                   # 38 entered vs GG 42
rid = se.create_round(EV, 9, round_date="2026-09-24", label="s9.24", course_holes=NINE,
                      course_id=cid_course, db_path=str(DB))["round_id"]
gid = se.upsert_group(rid, 1, players=[{"customer_id": 301, "display_name": "Kerry N",
                                         "tee": "50-64", "playing_handicap": 5}],
                      db_path=str(DB))["group_id"]
se.claim_group(gid, "d1", 301, db_path=str(DB))
se.write_scores(gid, "d1", 301, [{"op_id": f"o{h}", "hole": h, "gross": g, "customer_id": 301}
                                 for h, g in CARD.items()], db_path=str(DB))
se.sign_card(gid, "d1", 301, "player", db_path=str(DB))
se.submit_card(gid, "d1", 301, print_scorer_name="P", db_path=str(DB))
before_cut = db.get_app_setting("entry_record_from", str(DB))

print("takeover")
with contextlib.redirect_stdout(io.StringIO()):
    rep = tk.run(DB, [EV])
shadow = json.loads(Path(rep["shadow_diff_file"]).read_text())
s = shadow[str(EV)]
check("shadow diff saved first: it was a shadow run",
      s["publish_dry_run"]["mode"] == "shadow", s["publish_dry_run"].get("mode_reason"))
check("shadow diff carries the per-hole parity (holes 3 and 9 differ)",
      s["parity"]["summary"]["players_differing"] == 1 and s["parity"]["summary"]["holes_differing"] == 2, s["parity"])
sp = rep["shadow_parity"][EV]
check("the report itself carries the parity (the runner returns stdout, not the file)",
      sp["summary"]["holes_differing"] == 2 and sp["differing"][0]["customer_id"] == 301
      and len(sp["differing"][0]["holes_differ"]) == 2, sp)
check("GG round parked with its holes",
      rep["per_event"][EV]["park"] == {"rounds_parked": 1, "holes_parked": 9,
                                       "handicap_rounds_pointing": 0}, rep["per_event"][EV])
check("parked row keeps its id",
      q(f"SELECT id FROM {tk.PARKED_ROUNDS}") == [(gg_id,)])
check("cutover moved back to the event date", rep["cutover"]["now"] == "2026-09-24", rep["cutover"])
check("publish ran authoritative and wrote the player",
      rep["per_event"][EV]["mode"] == "authoritative" and rep["per_event"][EV]["applied"]
      and rep["per_event"][EV]["summary"].get("players_written") == 1, rep["per_event"][EV])
live = q("SELECT source, gross FROM scoring_rounds WHERE event_id = ?", (EV,))
check("only the entered row is live now", live == [("entry", 38)], live)

print("a second takeover is idempotent")
with contextlib.redirect_stdout(io.StringIO()):
    rep2 = tk.run(DB, [EV])
check("nothing more to park", rep2["per_event"][EV]["park"]["rounds_parked"] == 0, rep2)
check("still one entered row",
      q("SELECT COUNT(*) FROM scoring_rounds WHERE event_id = ?", (EV,)) == [(1,)])

print("undo")
un = tk.run(DB, [EV], undo=True)
check("undo removes the entry row and restores GG",
      un["per_event"][EV] == {"entry_rounds_removed": 1, "rounds_restored": 1}, un)
live = q("SELECT id, source, gross FROM scoring_rounds WHERE event_id = ?", (EV,))
check("GG row back under its own id", live == [(gg_id, "gg", 42)], live)
check("its holes are back", q("SELECT COUNT(*) FROM scoring_holes WHERE scoring_round_id = ?",
                               (gg_id,)) == [(9,)])
check("cutover restored", db.get_app_setting("entry_record_from", str(DB)) == before_cut
      or (before_cut is None and un.get("cutover_restored_to") is not None), un)

print("the app never imports the tool")
import subprocess  # noqa: E402
hits = subprocess.run(["grep", "-rln", "--include=*.py", "scratch_entry_takeover", "app.py", "mcp_server.py",
                       "email_parser"], cwd=HERE, capture_output=True, text=True).stdout.split()
# The ONE sanctioned caller: Health's Railway rehearsal runner (CA #829/#832,
# Kerry's B) LAUNCHES the tool as a separate secret-free TGF_REHEARSAL=1
# process on the scratch copy. It never imports it.
check("no app/bridge reference except the rehearsal runner",
      [h for h in hits if h != "email_parser/rehearsal.py"] == [], hits)
imports = subprocess.run(["grep", "-rnE", "--include=*.py", r"(import|from)\s+[\w.]*scratch_entry_takeover",
                          "app.py", "mcp_server.py", "email_parser"], cwd=HERE,
                         capture_output=True, text=True).stdout.strip()
check("nothing in the app imports the tool", imports == "", imports)

print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
