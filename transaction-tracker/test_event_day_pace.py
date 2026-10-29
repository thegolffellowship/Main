"""PACE OF PLAY on the Event Info email (Kerry 10/29): the course's standard,
the group's in-by time, and the three-colour bar the results email will show.

Run: python3 test_event_day_pace.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="tgf-edp-"), "t.db")
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import event_day_email as ede   # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

check("8:30 AM + 4:00 = 12:30 PM", ede._finish("Hole 1B | 8:30 AM", 240) == "12:30 PM")
check("5:10 PM + 2:15 = 7:25 PM", ede._finish("5:10 PM", 135) == "7:25 PM")
check("no time, no in-by line", ede._finish("Hole 3", 240) is None)
h = ede.pace_card(240, 270, 18, "Kissing Tree Golf Club", "Hole 1B | 8:30 AM")
for want in ("PACE OF PLAY", "Kissing Tree Golf Club expects 18 holes in <b>4:00</b>", "in by <b>12:30 PM</b>",
             "4:00 or under", "4:00 to 4:30", "over 4:30", "YOUR GROUP", "#22C55E", "#FACC15", "#EF4444"):
    check(f"card carries {want!r}", want in h)
check("dial off by default: nothing in the email", ede.PACE_DIAL == "event_day_pace_card")
print(f"\n{'ALL PASS' if not F else f'{len(F)} FAILED: {F}'}")
sys.exit(1 if F else 0)
