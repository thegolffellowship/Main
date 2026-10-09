"""Start one group's card over (Kerry 2026-10-08: "Can you also clear
scoring for my group tomorrow?") and a re-seed that moves a Foursomes pair
takes its team row with it (Saturday re-sequenced after seeding).

Run: python3 test_se_clear_group.py
"""
import os, sys, json, tempfile, contextlib, io, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-seclear-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser import score_entry as se                        # noqa: E402
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


EV = 3330
with db._connect(tmp) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, format, course) VALUES "
                 "(?, 'LSC PRACTICE ROUND', '2026-10-09', 'San Antonio', '18 Holes', 'The Hideout')", (EV,))
    for cid, fn, ln in ((18, "Kerry", "Niester"), (703, "Michael", "Mesa"), (88, "Jeff", "Young"),
                        (136, "Pat", "Youngs"), (7, "Matthew", "Jenkins")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
    conn.commit()
course = [{"hole": h, "par": 4, "stroke_index": h, "yardage": 380} for h in range(1, 19)]
rid = se.create_round(EV, 18, round_date="2026-10-09", label="PRACTICE", course_holes=course,
                      created_by="test", db_path=tmp)["round_id"]
g = se.upsert_group(rid, 2, tee_time="1:40 PM", players=[
    {"customer_id": c, "seat": i + 1} for i, c in enumerate((18, 703, 88, 136))], db_path=tmp)["group_id"]
other = se.upsert_group(rid, 1, tee_time="1:30 PM", players=[{"customer_id": 7, "seat": 1}],
                        db_path=tmp)["group_id"]

print("── a tested card ──")
check("claim", se.claim_group(g, "kerry-phone", 18, db_path=tmp).get("granted") is not False)
res = se.write_scores(g, "kerry-phone", 18, [
    {"op_id": f"o{c}", "hole": 1, "gross": 4, "customer_id": c} for c in (18, 703, 88, 136)], db_path=tmp)
check("hole 1 written for four", all(r["result"] == "ok" for r in res["results"]), res)
se.claim_group(other, "jenkins-phone", 7, db_path=tmp)
se.write_scores(other, "jenkins-phone", 7, [{"op_id": "j1", "hole": 1, "gross": 5, "customer_id": 7}], db_path=tmp)

print("── dry run ──")
d = se.clear_group(g, db_path=tmp)
check("dry run says what it would clear", d["dry_run"] and d["scores"] == 4 and d["holes"] == [1]
      and d["scorer_lock"] == {"holder_customer_id": 18}, d)
with db._connect(tmp) as conn:
    check("dry run writes nothing", conn.execute(
        "SELECT COUNT(*) FROM se_hole_scores WHERE group_id = ?", (g,)).fetchone()[0] == 4)

print("── apply ──")
a = se.clear_group(g, apply=True, db_path=tmp)
check("cleared", a.get("cleared") is True, a)
# Kerry 10/9: the card tells the phone when it was cleared, so stale queued
# holes are dropped and the phone opens on the starting hole
_c = se.get_group_card(g, db_path=tmp)
check("the card carries cleared_at after a clear", bool((_c or {}).get("cleared_at")), (_c or {}).get("cleared_at"))
with db._connect(tmp) as conn:
    check("no scores left on the card", conn.execute(
        "SELECT COUNT(*) FROM se_hole_scores WHERE group_id = ?", (g,)).fetchone()[0] == 0)
    check("scorer lock released", conn.execute(
        "SELECT COUNT(*) FROM se_group_locks WHERE group_id = ?", (g,)).fetchone()[0] == 0)
    check("players and group stay", conn.execute(
        "SELECT COUNT(*) FROM se_players WHERE group_id = ?", (g,)).fetchone()[0] == 4)
    row = conn.execute("SELECT detail FROM se_audit WHERE group_id = ? AND kind = 'admin_clear'",
                       (g,)).fetchone()
    det = json.loads(row[0]) if row else {}
    check("the cleared scores stay on record", len(det.get("scores") or []) == 4
          and det.get("lock_holder") == 18, det)
    check("the other group is untouched", conn.execute(
        "SELECT gross FROM se_hole_scores WHERE group_id = ?", (other,)).fetchone()[0] == 5)
    check("other group's lock kept", conn.execute(
        "SELECT COUNT(*) FROM se_group_locks WHERE group_id = ?", (other,)).fetchone()[0] == 1)
check("a fresh phone claims the card with no take-over",
      se.claim_group(g, "new-phone", 703, db_path=tmp).get("granted") is not False)
check("the old phone's queued op does not come back as a write",
      se.write_scores(g, "kerry-phone", 18, [{"op_id": "o18", "hole": 1, "gross": 4, "customer_id": 18}],
                      db_path=tmp)["results"][0]["result"] == "dup")

print("── a SUBMITTED test card (Kerry 10/9: \"Reset the scores on my card now\") ──")
se.write_scores(g, "new-phone", 703, [{"op_id": "s2", "hole": 2, "gross": 4, "customer_id": 18}], db_path=tmp)
with db._connect(tmp) as conn:
    conn.execute("INSERT INTO se_card_checks (round_id, group_id, scorekeeper_customer_id, at) "
                 "VALUES (?, ?, 18, '2026-10-09T05:00:00Z')", (rid, g))
    conn.commit()
dr = se.clear_group(g, apply=True, db_path=tmp)
check("a submitted card is refused without |checks", dr.get("refused") and not dr.get("cleared"), dr)
ok = se.clear_group(g, apply=True, include_checks=True, db_path=tmp)
check("with include_checks it clears", ok.get("cleared") and ok.get("card_checks") == 1, ok)
with db._connect(tmp) as conn:
    check("the scores and the card check are gone", conn.execute(
        "SELECT COUNT(*) FROM se_hole_scores WHERE group_id = ?", (g,)).fetchone()[0] == 0
        and conn.execute("SELECT COUNT(*) FROM se_card_checks WHERE group_id = ?", (g,)).fetchone()[0] == 0)
    det = json.loads(conn.execute("SELECT detail FROM se_audit WHERE group_id = ? AND kind = 'admin_clear' "
                                  "ORDER BY id DESC LIMIT 1", (g,)).fetchone()[0])
    check("the cleared check is kept in the audit row", len(det.get("card_checks") or []) == 1, det)

print("── refusals ──")
check("unknown group", "error" in se.clear_group(999999, db_path=tmp))
se.close_round(rid, db_path=tmp)
check("closed round refused", "error" in se.clear_group(g, apply=True, db_path=tmp))

print("── a re-seed moves a Foursomes pair's team row ──")
r2 = se.create_round(EV, 18, round_date="2026-10-10", label="PM", course_holes=course,
                     created_by="test", db_path=tmp)["round_id"]
ga = se.upsert_group(r2, 1, players=[{"customer_id": 136}, {"customer_id": 88}], db_path=tmp)["group_id"]
gb = se.upsert_group(r2, 2, players=[{"customer_id": 18}, {"customer_id": 703}], db_path=tmp)["group_id"]
tid = se.add_team(r2, ga, 136, 88, db_path=tmp)["team_id"]
se.claim_group(ga, "p", 136, db_path=tmp)
se.write_scores(ga, "p", 136, [{"op_id": "t1", "hole": 1, "gross": 4, "team_id": tid}], db_path=tmp)
# re-sequenced: Youngs & Young now tee in group 2, Niester & Mesa in group 1
se.upsert_group(r2, 1, players=[{"customer_id": 18}, {"customer_id": 703}], db_path=tmp)
se.upsert_group(r2, 2, players=[{"customer_id": 136}, {"customer_id": 88}], db_path=tmp)
with db._connect(tmp) as conn:
    check("team row follows the pair", conn.execute(
        "SELECT group_id FROM se_teams WHERE id = ?", (tid,)).fetchone()[0] == gb)
    check("team's score follows the pair", conn.execute(
        "SELECT group_id FROM se_hole_scores WHERE subject_key = ?", (f"t:{tid}",)).fetchone()[0] == gb)

print()
if F:
    print(f"FAILED: {len(F)}")
    sys.exit(1)
print("ALL PASS")
