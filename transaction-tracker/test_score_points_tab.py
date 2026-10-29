"""THE POINTS TAB on Live Scoring (Kerry 2026-10-29, Event Ops #2460-F:
"SCORING | LEADERBOARD | POINTS").

- Dial `scoring_points_tab` OFF (the default): the scorer's page and board are
  exactly as before (no third segment), /member/score/points falls back to the
  score page, /api/score-entry/points is 404.
- ON: the toggle carries Points on the score page, the board and the points
  page (active there); the context names the event, the Monthly month, the
  season race of the event's chapter AND of each group player's home chapter,
  and the group's customer_ids (ids only, no names, no emails).
- The page reads the member LEADERBOARD's own public endpoints.
Run: python3 test_score_points_tab.py
"""
import contextlib, io, logging, os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "ui-test")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)
    import app as appmod
from email_parser import score_entry as se          # noqa: E402
from email_parser import score_points as sp         # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

c = sqlite3.connect(DB)
c.execute("INSERT INTO events (id, item_name, event_date, chapter) VALUES (900, 's9.31 Test', '2026-10-31', 'San Antonio')")
for cid, fn, ln, ch in ((9101, "Kerry", "Niester", "San Antonio"), (9102, "Rob", "Straiton", "Austin")):
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter) VALUES (?,?,?,?)", (cid, fn, ln, ch))
c.commit()
rid = se.create_round(900, 9, label="s9.31 Test",
                      course_holes=[{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 10)])["round_id"]
gid = se.upsert_group(rid, 1, label="Hole 1", players=[{"customer_id": 9101, "display_name": "Kerry N", "seat": 1},
                                                       {"customer_id": 9102, "display_name": "Rob S", "seat": 2}])["group_id"]
db.set_app_setting("score_entry_live", "1")
db.set_app_setting("score_entry_events", "[900]")
TOK = se.make_group_token(gid)

print("== dial off (default) ==")
with appmod.app.test_client() as tc:
    h = tc.get(f"/member/score?t={TOK}").get_data(as_text=True)
    check("score page: no Points segment", 'id="se-tg-points"' not in h and "se-tg-board" in h)
    h = tc.get(f"/member/score/board?t={TOK}").get_data(as_text=True)
    check("board: no Points segment", 'id="se-tg-points"' not in h)
    h = tc.get(f"/member/score/points?t={TOK}").get_data(as_text=True)
    check("points page falls back to the score page", "pt-body" not in h)
    check("context API 404", tc.get(f"/api/score-entry/points?t={TOK}").status_code == 404)

print("== dial on ==")
db.set_app_setting("scoring_points_tab", "on")
with appmod.app.test_client() as tc:
    check("score page: Points segment", 'id="se-tg-points"' in tc.get(f"/member/score?t={TOK}").get_data(as_text=True))
    check("board: Points segment", 'id="se-tg-points"' in tc.get(f"/member/score/board?t={TOK}").get_data(as_text=True))
    h = tc.get(f"/member/score/points?t={TOK}").get_data(as_text=True)
    check("points page renders under the toggle", "pt-body" in h and "se-tg-points" in h)
    check("reads the member LEADERBOARD's public endpoints",
          "/api/season-contests/monthly-points" in h and "/api/season-contests/points-race?race=" in h)
    check("bad link: falls back", "pt-body" not in tc.get("/member/score/points?t=bad").get_data(as_text=True))
    r = tc.get(f"/api/score-entry/points?t={TOK}")
    j = r.get_json() or {}
    check("context 200", r.status_code == 200, r.status_code)
    check("group customer_ids, ids only", j.get("group_customer_ids") == [9101, 9102], j)
    check("event + month", j.get("event", {}).get("id") == 900 and j.get("month") == "2026-10", j)
    keys = [x["key"] for x in j.get("races") or []]
    check("event chapter race first, then a player's home-chapter race",
          keys == ["san_antonio_fall_net", "austin_fall_net"], keys)
    import json as _json
    blob = _json.dumps(j)
    check("PII-free: no names, no emails", "Niester" not in blob and "Straiton" not in blob and "@" not in blob)
    check("context API needs the group link", tc.get("/api/score-entry/points").status_code in (401, 404))

print("== a TGF event with one home chapter ==")
c.execute("UPDATE events SET chapter = 'TGF' WHERE id = 900")
c.execute("UPDATE customers SET chapter = 'San Antonio' WHERE customer_id = 9102")
c.commit()
keys = [x["key"] for x in sp.points_context(gid)["races"]]
check("only the players' home-chapter race", keys == ["san_antonio_fall_net"], keys)

print("== the toggle script marks Points active on its page ==")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "_shell_nav.html")).read()
check("Points segment rendered only under SE_POINTS_TAB", "{% if SE_POINTS_TAB %}" in src)
check("active on /member/score/points", "/member/score/points" in src and "onPoints" in src)

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
