"""THE MAX PLAYING HANDICAP (Kerry 2026-10-16): 18 on a nine, 36 on an
eighteen, whatever the tee or gender, so nobody gets more than two pops a
hole; with the max-triple rule a triple with two pops is a net bogey and
earns no points. Forward only (app setting ph_cap_from, default 2026-10-20).

Run: python3 test_ph_cap.py
"""
import contextlib, io, logging, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    DB = os.environ["DATABASE_PATH"]
    db.init_db(DB)
from email_parser.handicap_calc import (playing_handicap, max_playing_handicap,
                                        allocate_strokes, MAX_POPS_PER_HOLE)

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


print("the rule")
check("two pops a hole", MAX_POPS_PER_HOLE == 2)
check("18 on a nine, 36 on an eighteen", max_playing_handicap(9) == 18 and max_playing_handicap(18) == 36)
# A 9-hole index of 19.1 on a slope-130 nine rated 36.5 / par 36: PH 22 uncapped.
raw = playing_handicap(19.1, 130, 36.5, 36)
check("an index that would give 22 on a nine", raw == 22, raw)
check("is capped at 18", playing_handicap(19.1, 130, 36.5, 36, max_hcp=18) == 18)
check("an 18 capped at 36", playing_handicap(38.2, 130, 73.0, 72, max_hcp=36) == 36)
check("a handicap under the cap is untouched", playing_handicap(8.0, 130, 36.5, 36, max_hcp=18)
      == playing_handicap(8.0, 130, 36.5, 36))
check("a plus handicap is untouched", playing_handicap(-1.5, 130, 36.5, 36, max_hcp=18) < 0)
si = {h: h for h in range(1, 10)}
check("18 on a nine is exactly two pops on every hole",
      set(allocate_strokes(18, si).values()) == {2})

print("forward only")
check("an event on/after 10/20 is capped (nine)", db.event_ph_cap({"event_date": "2026-10-20"}, True, db_path=DB) == 18)
check("an event on/after 10/20 is capped (eighteen)", db.event_ph_cap({"event_date": "2026-10-24"}, False, db_path=DB) == 36)
check("a past event keeps its handicaps", db.event_ph_cap({"event_date": "2026-10-13"}, True, db_path=DB) is None)
db.set_app_setting("ph_cap_from", "2026-10-01", db_path=DB)
check("the start date is a dial", db.event_ph_cap({"event_date": "2026-10-13"}, True, db_path=DB) == 18)

print("every source of a playing handicap carries the cap")
here = os.path.dirname(os.path.abspath(__file__))
dbsrc = open(os.path.join(here, "email_parser", "database.py")).read()
sesrc = open(os.path.join(here, "email_parser", "score_entry.py")).read()
check("the Starter Sheet / print pack PH (feeds score entry, cards, dots, the engine)",
      dbsrc.count("max_hcp=event_ph_cap(ev,") >= 2)
check("the FLIGHTS tab PH", "def _event_player_ph_map" in dbsrc
      and "max_hcp=event_ph_cap(ev, (tee[\"rating\"] or 0) < 50))" in dbsrc)
check("the score-entry preview PH", "max_hcp=db.event_ph_cap(ev, holes == 9" in sesrc)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILED: {F}"))
sys.exit(1 if F else 0)
