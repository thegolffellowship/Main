"""12-HOUR TIMES (Kerry 2026-10-26, CoS #2325: "Please don't use Military
Time"). Every time a member, manager or course READS is 12-hour Central with
AM/PM; code, cron strings, logs, stored stamps and ISO API values stay 24-hour.

The guard: the shared helpers convert correctly (Python clock12/stamp12, JS
tgfTime12), the shell nav loads the JS one, and no NEW person-facing 24-hour
pattern appears:
  - a page cutting a stamp to HH:MM with .slice(11, 16) / .slice(0, 16) for
    display without tgfTime12 on the same line (a form or stored value is
    marked `24h-ok` on its line);
  - hour12:false / hourCycle h23 in a page or script;
  - a display strftime with %H:%M (no :%S) in a module that writes emails or
    print sheets, outside the stored-stamp allow-list below.

Run: python3 test_twelve_hour_times.py
"""
import os, re, shutil, subprocess, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from email_parser.timezone_utils import clock12, stamp12  # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

def read(rel):
    return open(os.path.join(HERE, rel), encoding="utf-8").read()

print("1. The Python helpers")
for v, want in (("16:30", "4:30 PM"), ("08:05", "8:05 AM"), ("00:15", "12:15 AM"), ("12:00", "12:00 PM"),
                ("16:30:00", "4:30 PM"), ("4:30 PM", "4:30 PM"), ("", ""), ("TBD", "TBD"), (None, "")):
    check(f"clock12({v!r}) = {want!r}", clock12(v) == want, clock12(v))
check("clock12(datetime) = 1:07 PM", clock12(datetime(2026, 1, 1, 13, 7)) == "1:07 PM")
for v, want in (("2026-10-26 15:40", "2026-10-26 3:40 PM"), ("2026-10-26T15:40:12", "2026-10-26 3:40 PM"),
                ("2026-10-26 09:03:44.123", "2026-10-26 9:03 AM"), ("Saved 3:40 PM", "Saved 3:40 PM"),
                ("2026-10-26", "2026-10-26"), ("score 25:30", "score 25:30")):
    check(f"stamp12({v!r}) = {want!r}", stamp12(v) == want, stamp12(v))
check("stamp12(datetime)", stamp12(datetime(2026, 10, 26, 21, 5)) == "2026-10-26 9:05 PM")

print("2. The JS helper, loaded app-wide")
nav = read("templates/_shell_nav.html")
check("_shell_nav.html loads time12.js", "/static/js/time12.js" in nav)
node = shutil.which("node")
if node:
    js = ("const f=require(process.argv[1]);console.log(JSON.stringify(["
          "f('16:30'),f('2026-10-26T15:40:12Z'),f('4:30 PM'),f('2026-10-26 00:05'),f(null)]))")
    out = subprocess.run([node, "-e", js, os.path.join(HERE, "static/js/time12.js")],
                         capture_output=True, text=True).stdout.strip()
    check("tgfTime12 converts like stamp12", out == '["4:30 PM","2026-10-26 3:40 PM","4:30 PM","2026-10-26 12:05 AM",""]', out)
else:
    print("  SKIP  node not installed")

print("3. No new 24-hour display in pages or scripts")
CUT = re.compile(r"\.slice\(\s*(11|0)\s*,\s*16\s*\)")
H24 = re.compile(r"hour12\s*:\s*false|hourCycle\s*:\s*['\"]h2[34]")
bad_cut, bad_h24 = [], []
for root in ("templates", "static/js"):
    for dp, _, files in os.walk(os.path.join(HERE, root)):
        for fn in files:
            if not fn.endswith((".html", ".js")) or fn == "time12.js":
                continue
            rel = os.path.relpath(os.path.join(dp, fn), HERE)
            for i, line in enumerate(open(os.path.join(dp, fn), encoding="utf-8", errors="replace"), 1):
                if CUT.search(line) and "tgfTime12" not in line and "24h-ok" not in line:
                    bad_cut.append(f"{rel}:{i}")
                if H24.search(line):
                    bad_h24.append(f"{rel}:{i}")
check("every HH:MM cut of a stamp goes through tgfTime12", not bad_cut, bad_cut)
check("no hour12:false / hourCycle h23", not bad_h24, bad_h24)

print("4. No new 24-hour strftime in the modules that write emails and print sheets")
PERSON_FACING = ("scorecards", "screens_capture", "health", "event_day_email", "teetimes_email", "results_email",
                 "invitations", "course_update", "payment_reminder", "report", "admin_payout_report",
                 "games_sheet", "print_pack", "member_teesheet", "after_lock", "pairings_approval",
                 "course_files_noon", "handicap_ask", "payout_ask", "pace_report", "seat_fill",
                 "lsc_recap", "recap_mail")
# Stored stamps (never shown as written): file -> substrings on the line.
STORED = {"course_update": ("sent[eid] =",), "admin_payout_report": ("set_app_setting(",)}
DISPLAY = re.compile(r"strftime\(\s*[\"'][^\"']*%H:%M(?!:%S)[^\"']*[\"']")
bad = []
for mod in PERSON_FACING:
    rel = f"email_parser/{mod}.py"
    if not os.path.exists(os.path.join(HERE, rel)):
        continue
    for i, line in enumerate(read(rel).split("\n"), 1):
        if DISPLAY.search(line) and not any(s in line for s in STORED.get(mod, ())):
            bad.append(f"{rel}:{i}: {line.strip()[:100]}")
check("display times use clock12 / stamp12 / %-I:%M %p", not bad, bad)

print("5. The places fixed on 10/26 stay fixed")
check("printed scorecards stamp 12-hour Central", 'stamp12(now_central()) + " CT"' in read("email_parser/scorecards.py"))
check("Screens capture label 12-hour", '"%Y-%m-%d %-I:%M %p CT"' in read("email_parser/screens_capture.py"))
check("health digest 'generated' 12-hour", '"generated_at": now_central().strftime("%Y-%m-%d %-I:%M %p")' in read("email_parser/health.py"))
check("Games & Payouts sheet start time via clock12", 'clock12(ev.get("start_time"))' in read("email_parser/games_sheet.py"))
check("Events 'Saved' chip carries AM/PM", "`Saved ${t.getHours() % 12 || 12}:${String(t.getMinutes()).padStart(2, '0')} ${t.getHours() >= 12 ? 'PM' : 'AM'}`" in read("templates/events.html"))
check("score-entry admin loads time12.js itself (no shell nav)", "/static/js/time12.js" in read("templates/score_entry_admin.html"))

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
