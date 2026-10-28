"""EMAIL BUTTONS KEEP THEIR COLOUR (Kerry 10/26, an Outlook quoted reply):
Outlook drops the background of a link when it quotes an email (and in some
desktop versions), which left the white "I'm in" text invisible on white.
Every email button whose link carries a background must sit in a cell that
carries the same colour as bgcolor. This scans the email builders.

Run: python3 test_email_buttons.py
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
FILES = [os.path.join(HERE, "email_parser", f) for f in sorted(os.listdir(os.path.join(HERE, "email_parser")))
         if f.endswith(".py")]
bad = []
for path in FILES:
    lines = open(path, encoding="utf-8").read().splitlines()
    for i, line in enumerate(lines):
        if "display:inline-block" not in line.replace(" ", "") or "<a" not in "".join(lines[max(0, i - 1):i + 1]):
            continue
        m = re.search(r"background:\s*([^;'\"]+);", line)
        if not m:
            continue
        window = "".join(lines[max(0, i - 4):i + 1])
        if "bgcolor=" not in window:
            bad.append(f"{os.path.basename(path)}:{i + 1}")
print("  PASS  every coloured email button has a bgcolor cell" if not bad else f"  FAIL  link-only button background at {bad}")
print("ALL PASS" if not bad else "1 FAILURE")
sys.exit(1 if bad else 0)
