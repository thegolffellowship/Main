"""Slot labels come from the ROSTER when Edit Event carries no group count
(Kerry 2026-09-15: "why aren't holes being assigned to the foursomes?").

tee_time_count is the manager's number and still wins when typed. When it
is 0 — the common case — `_pairing_time_slots(..., needed=N)` deals N
slots: hole labels for a shotgun, clock slots for tee times with a start
time, and "Group N" only when the event has neither.

Run: python3 test_pairing_slots.py
"""
import os, sys
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)

slots = db._pairing_time_slots
print("\n== count unset: the roster sizes the sheet ==")
sg = {"start_type": "Shotgun", "start_time": "17:00", "tee_time_count": 0}
check("shotgun, 5 groups needed -> 1A 1B 2A 2B 3A",
      slots(sg, "9", needed=5) == ["1A", "1B", "2A", "2B", "3A"], str(slots(sg, "9", needed=5)))
check("shotgun on the BACK nine starts at 10A",
      slots({**sg, "nine_side": "Back"}, "9", needed=3) == ["10A", "10B", "11A"],
      str(slots({**sg, "nine_side": "Back"}, "9", needed=3)))
tt = {"start_type": "Tee Times", "start_time": "17:00", "tee_time_count": 0, "tee_time_interval": 10}
check("tee times with a start time -> clock slots",
      slots(tt, "9", needed=3) == ["5:00 PM", "5:10 PM", "5:20 PM"], str(slots(tt, "9", needed=3)))
check("no start type, no start time -> Group N (unchanged fallback)",
      slots({"tee_time_count": 0}, "9", needed=2) == ["Group 1", "Group 2"],
      str(slots({"tee_time_count": 0}, "9", needed=2)))
check("nothing needed and nothing typed -> no slots",
      slots(sg, "9") == [] and slots(sg, "9", needed=0) == [])

print("\n== a typed count still wins ==")
check("count 6 with 2 needed deals 6", len(slots({**sg, "tee_time_count": 6}, "9", needed=2)) == 6)
check("count 2 with 5 needed deals 2 (the manager's number is the manager's)",
      len(slots({**sg, "tee_time_count": 2}, "9", needed=5)) == 2)

print("\n== combo events read the 18-hole leg's own settings ==")
combo = {"format": "9/18 Combo", "start_type": "Shotgun", "tee_time_count": 0,
         "start_type_18": "Tee Times", "start_time_18": "08:00", "tee_time_count_18": 0,
         "tee_time_interval": 9}
check("9-hole leg shotgun holes", slots(combo, "9", needed=2) == ["1A", "1B"], str(slots(combo, "9", needed=2)))
check("18-hole leg clock slots", slots(combo, "18", needed=2) == ["8:00 AM", "8:09 AM"], str(slots(combo, "18", needed=2)))

print("\n== groups needed ==")
need = db._pairing_groups_needed
check("18 players -> 5 foursomes", need(18) == 5)
check("18 players in fivesomes -> 4", need(18, 5) == 4)
check("never fewer than the seeds occupy", need(3, 4, seeded_slots=4) == 4)
check("never fewer than the saved sheet", need(3, 4, saved_groups=6) == 6)
check("empty roster -> 0", need(0) == 0)

print("\n" + ("FAILED: " + ", ".join(F) if F else "ALL PASSED"))
sys.exit(1 if F else 0)
