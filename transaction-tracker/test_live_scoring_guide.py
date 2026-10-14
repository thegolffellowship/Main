"""The Live Scoring how-to page (Kerry 2026-10-13): public at
/member/live-scoring, every step's screenshot exists, and the par note is on
the Enter-each-hole step.

Run: python3 test_live_scoring_guide.py
"""
import contextlib
import io
import logging
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "guide-test")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(os.environ["DATABASE_PATH"])
    import app as appmod

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


c = appmod.app.test_client()
r = c.get("/member/live-scoring")
html = r.get_data(as_text=True)
check("public page answers 200 with no login", r.status_code == 200, r.status_code)
imgs = re.findall(r'/static/img/live-scoring/([\w-]+\.jpg)\?v=', html)
check("eleven steps, thirteen pictures (step 1 shows the three ways in)", len(imgs) == 13, imgs)
folder = os.path.join(appmod.app.static_folder, "img", "live-scoring")
missing = [i for i in imgs if not os.path.exists(os.path.join(folder, i))]
check("every screenshot the page names exists", not missing, missing)
sizes = set()
phones = [i for i in imgs if i not in ("00-cart-sign.jpg", "00-scorecard.jpg")]
for i in phones:
    with open(os.path.join(folder, i), "rb") as fh:
        b = fh.read()
    j = 2
    while j < len(b):  # read the JPEG frame header for width x height
        if b[j] == 0xFF and b[j + 1] in (0xC0, 0xC1, 0xC2):
            sizes.add((int.from_bytes(b[j + 7:j + 9], "big"), int.from_bytes(b[j + 5:j + 7], "big")))
            break
        j += 2 + int.from_bytes(b[j + 2:j + 4], "big")
check("every screenshot is the same full phone screen, 780x1688", sizes == {(780, 1688)}, sizes)
check("the par note: a par needs no tap", "Made par? Don't tap anything." in html)
check("the Take over warning is on the page", "Don't tap Take over." in html)
check("every step prints its text (a key named copy would print dict.copy)",
      html.count('<p class="copy">') == 11 and "built-in method" not in html
      and "Tap <b>Keep score on your phone</b>" in html)
check("the three ways in: cart sign, scorecard, pairing email",
      all(f"{n}.jpg?v=" in html for n in ("00-cart-sign", "00-scorecard", "00-email")))
check("no email address or phone number on the public page",
      not re.search(r"[\w.+-]+@[\w-]+\.\w+|\(\d{3}\) \d{3}-\d{4}", html))
print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
