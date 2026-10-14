"""2026 LOCKED ON OUR SIDE (Kerry 2026-10-13: "All needs to be hardened/locked
on our side to not rely on Golf Genius for anything related to 2026 without
losing ANY results"; "The hourly results check is not needed anymore"; "Tee
sheet grab - won't be needed"; "Definitely remove the Team net import").

  * a FROZEN championship board/card is served as captured, byte for byte,
    with no Golf Genius call, once points intake is off;
  * the freeze refuses an empty or stale board (never freezes a blank);
  * the hourly results job and the nightly tee-sheet grab do nothing unless
    gg_auto_jobs = on;
  * the GG Team Net import is retired;
  * live City Match Play polling stops with intake off;
  * the captured points ledger is in the nightly file backup;
  * Monthly rows carry the player's Fall card, so October's points expand.
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.WARNING)
import app as appmod                                    # noqa: E402
from email_parser import database as db                 # noqa: E402
from email_parser import gg_freeze, backups             # noqa: E402
import golf_genius_sync as ggs                          # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

calls = []
def _boom(*a, **k):
    calls.append(a[:1])
    raise RuntimeError("Golf Genius must not be called")
for name in ("fetch_public_page", "fetch_season_points_race", "fetch_points_race_member_detail"):
    setattr(ggs, name, _boom)

FROZEN = {"race": "players_cup_gross", "configured": True, "label": "Round 1 + Round 2",
          "boards": ["Round 1", "Round 2"], "field": 34, "scoring": 34, "stale": False,
          "players": [{"name": "STRAITON, Robert", "customer_id": 31, "points": 57.0},
                      {"name": "YOUNG, Jeff", "customer_id": 88, "points": 59.0}]}
db.save_gg_snapshot("frozen_champ_points:players_cup_gross", FROZEN, DB)
got = db.fetch_champ_points("players_cup_gross", db_path=DB)
check("frozen board is served exactly as captured (Young stays 59)",
      got.get("players") == FROZEN["players"] and got.get("label") == FROZEN["label"], got)
check("...without a Golf Genius call", not calls, calls)

CARD = {"race": "players_cup_gross", "configured": True, "holes": [{"hole": 1, "gross": 4}],
        "player": "YOUNG, Jeff"}
db.save_gg_snapshot("frozen_champ_cards:players_cup_gross", {"cards": {"88|Round 2|": CARD}}, DB)
c = db.fetch_champ_player_card("players_cup_gross", 88, db_path=DB, board_label="Round 2")
check("frozen card is served as captured", c == CARD, c)
c2 = db.fetch_champ_player_card("players_cup_gross", 999, db_path=DB)
check("a player not on the frozen board gets a clean not-found, not a GG call",
      c2.get("holes") == [] and "not on the championship board" in (c2.get("error") or "") and not calls, c2)

print("== the freeze refuses a blank ==")
_orig = db.fetch_champ_points
db.fetch_champ_points = lambda race, max_age=45.0, db_path=None, live=False: {
    "race": race, "configured": True, "players": [], "stale": False}
r = gg_freeze.freeze_points("fellowship_cup", apply=True, db_path=DB)
check("an empty live board is refused and nothing is written",
      r.get("refused") and not db.load_gg_snapshot("frozen_champ_points:fellowship_cup", DB), r)
db.fetch_champ_points = lambda race, max_age=45.0, db_path=None, live=False: dict(FROZEN, race=race, stale=True)
r = gg_freeze.freeze_points("fellowship_cup", apply=True, db_path=DB)
check("a stale board is refused", r.get("refused"), r)
db.fetch_champ_points = _orig

print("== automatic GG jobs off ==")
from email_parser import gg_untether as ggu
check("gg_auto_jobs is off by default", ggu.gg_auto_jobs_on(DB) is False)
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")).read()
check("the hourly results job and the tee-sheet grab both check gg_auto_jobs first",
      src.count("if not gg_auto_jobs_on():") >= 2)
check("the GG Team Net import is retired",
      db.import_gg_teamnet_round("sa", "1", apply=True, db_path=DB).get("retired") is True and not calls)
lm = db.cmp_fetch_live_match("San Antonio", "A", "B", db_path=DB)
check("live City Match Play polling is off with intake off", "polling is off" in (lm.get("error") or "") and not calls, lm)
check("the captured points ledger is in the nightly file backup", "gg_points_ledger" in backups.FILE_STORES)

print("== October Monthly rows expand ==")
from email_parser import tracker_points as tp
best = tp.monthly_best("2026-10", tracker_lines=[
    {"customer_id": 101, "player_name": "SALDANA, Jesse", "chapter": "San Antonio", "member": True,
     "date": "2026-10-06", "event_id": 3308, "points": 13.0}], cards={101: "c101"})
check("a monthly row carries the player's Fall card", best[101]["member_card_id"] == "c101", best)

print("\nALL PASS" if not F else f"\n{len(F)} FAILED: " + "; ".join(F))
sys.exit(1 if F else 0)
