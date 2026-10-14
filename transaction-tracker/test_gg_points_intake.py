"""GG POINTS INTAKE OFF (Kerry 2026-10-13, via CoS #1693-1): "Can we generate
points on our side first for last Tuesday? Then I'll run Golf Genius for you to
check it against. However, you'll need to turn off the GG connector that
automates bringing them in."

Off unless app setting gg_points_intake = "on". While off: a board read serves
its saved snapshot and never refreshes, the monthly-points job keeps its saved
snapshot, the row-expansion proxy makes no GG call, and a refresh that would
overwrite the live standings is refused. Nothing is deleted.
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.WARNING)
import app as appmod                                   # noqa: E402
from email_parser import database as db                # noqa: E402
from email_parser import gg_untether as ggu            # noqa: E402
import golf_genius_sync as ggs                         # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

calls = []
ggs.fetch_season_points_race = lambda *a, **k: calls.append("race") or []
ggs.fetch_points_race_member_detail = lambda *a, **k: calls.append("detail") or {"tables": []}
db.get_monthly_points = lambda *a, **k: calls.append("monthly") or {"months": [], "errors": []}

check("off by default (no setting)", ggu.gg_points_intake_on(DB) is False)
race = next(iter(db._GG_POINTS_RACES))
try:
    db.refresh_points_race_standings(race, db_path=DB)
    refused = False
except RuntimeError as e:
    refused = "intake is OFF" in str(e)
check("a refresh that would overwrite the live standings is refused", refused and not calls, str(calls))

res = db.get_points_race_standings(race, db_path=DB)
res2 = db.get_points_race_standings(race, db_path=DB, force_refresh=True)
check("a board read (even forced, even with no snapshot) pulls nothing from GG",
      not calls and res.get("intake_paused") is True and not res.get("gg_error") and not res2.get("gg_error"),
      str((calls, res.get("gg_error"))))
res3 = db.get_points_race_standings(race, db_path=DB, no_network=True)
check("...and queues no background refresh", not res3.get("refresh_queued") and not calls)

db.save_gg_snapshot("monthly_points", {"months": [{"month": "2026-09"}], "errors": []}, DB)
m = db.refresh_monthly_points_snapshot(DB)
check("the monthly-points job keeps its saved snapshot and fetches nothing",
      not calls and m.get("months") == [{"month": "2026-09"}] and m.get("intake_paused"), str((calls, m)))

client = appmod.app.test_client()
r = client.get(f"/api/season-contests/points-race/detail?race={race}&card=123")
j = r.get_json() or {}
check("the row-expansion proxy answers without calling GG", r.status_code == 200 and j.get("paused") and j.get("tables") == [] and not calls,
      str((r.status_code, j, calls)))

db.set_app_setting("gg_points_intake", "on", db_path=DB)
check("on only when the setting is exactly 'on'", ggu.gg_points_intake_on(DB) is True)
db.refresh_points_race_standings(race, db_path=DB)
check("switched on, the refresh runs again", calls == ["race"], str(calls))
db.set_app_setting("gg_points_intake", "", db_path=DB)

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_parser/points_ledger.py")).read()
check("the manual capture (points_ledger) is not gated: Kerry runs GG on his word to compare",
      "gg_points_intake_on" not in src)

print("\nALL PASS" if not F else f"\n{len(F)} FAILED: " + "; ".join(F))
sys.exit(1 if F else 0)
