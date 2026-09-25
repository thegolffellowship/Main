"""Score entry screen, driven in headless Chromium at phone size.

Kerry, 2026-09-25: "Save last hole shouldn't be available after you saved
the last hole. The last hole should show a green check and it should only
display FINISH & SIGN or you can click on any individual hole to adjust."
And: "We do Max Triple ... hole in ones wouldn't be possible on Par 5s."

Checked for a 9-hole round, an 18-hole round (with the turn), and a shotgun
start where the last hole is 3:
- once every hole is saved: every cell mint, no current ring, no "Save last
  hole", one primary action "Finish & sign";
- tapping a cell opens that hole with "Save hole N"; saving returns to the
  review and the change reaches the server;
- the stepper stops at par + 3, and at 2 on a par 5.

Needs Playwright + Chromium; skips (exit 0) when either is missing.
Run: python3 test_score_entry_ui.py
"""
import contextlib
import io
import logging
import os
import sqlite3
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP: playwright not installed")
    sys.exit(0)
CHROME = next((p for p in ("/opt/pw-browsers/chromium",) if os.path.exists(p)), None)

DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "ui-test")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)
    import app as appmod
from email_parser import score_entry as se  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


c = sqlite3.connect(DB)
for cid, f, l in [(101, "Kerry", "Niester"), (102, "Mark", "Stich")]:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, f, l))
c.execute("INSERT INTO events (id, item_name, event_date) VALUES (900, 'UI test', '2026-09-29')")
c.commit()
PARS = [4, 5, 3, 4, 4, 4, 3, 5, 4, 4, 4, 3, 5, 4, 4, 3, 4, 5]


def course(n):
    return [{"hole": h, "par": PARS[h - 1], "stroke_index": h} for h in range(1, n + 1)]


def make(holes, start, label):
    rid = se.create_round(900, holes, label=label, course_holes=course(holes))["round_id"]
    gid = se.upsert_group(rid, 1, start_hole=start, players=[
        {"customer_id": 101, "display_name": "Kerry Niester", "seat": 1},
        {"customer_id": 102, "display_name": "Mark Stich", "seat": 2}])["group_id"]
    return rid, gid, se.make_group_token(gid)


db.set_app_setting("score_entry_live", "1")
PORT = 5093
threading.Thread(target=lambda: appmod.app.run(port=PORT, use_reloader=False), daemon=True).start()
time.sleep(2)


def play(page, n):
    """Save n holes, answering any CTP prompt and the turn along the way."""
    for _ in range(n):
        page.click("[data-act=save]")
        page.wait_for_timeout(250)
        if page.locator("button[data-act=ctp][data-cid='']").count():
            page.click("button[data-act=ctp][data-cid='']")
            page.wait_for_timeout(400)
        if page.locator("[data-act=turn]").count():
            page.click("[data-act=turn]")
            page.wait_for_timeout(200)


def review_ok(page, n, label):
    page.wait_for_selector("text=Every hole is in", timeout=5000)
    body = page.inner_text("body")
    check(f"{label}: no 'Save last hole' once every hole is saved", "Save last hole" not in body)
    check(f"{label}: all {n} cells are mint ✓, none is the current ring",
          page.locator(".se-cell.saved").count() == n and page.locator(".se-cell.cur").count() == 0,
          (page.locator(".se-cell.saved").count(), page.locator(".se-cell.cur").count()))
    check(f"{label}: the one primary action is Finish & sign",
          page.locator(".se-pill.go").count() == 1
          and "Finish" in page.inner_text(".se-pill.go"))


if not CHROME:
    print("SKIP: no Chromium at /opt/pw-browsers/chromium")
    sys.exit(0)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=["--headless=new"])

    def open_as_kerry(tok):
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        pg.goto(f"http://127.0.0.1:{PORT}/member/score?t={tok}")
        pg.click("text=Kerry Niester")
        pg.wait_for_selector("text=You're keeping score")
        return pg

    print("nine holes, start on 1")
    rid9, gid9, tok9 = make(9, 1, "nine")
    pg = open_as_kerry(tok9)
    # max triple on hole 1 (par 4): + stops at 7
    for _ in range(6):
        pg.locator(".se-row").nth(0).locator(".se-plus").click()
    check("par 4: the + button stops at 7 (max triple)", pg.inner_text(".se-row >> nth=0 >> .se-score .v") == "7")
    for _ in range(6):
        pg.locator(".se-row").nth(0).locator(".se-minus").click()
    play(pg, 1)
    pg.wait_for_selector("text=Hole 2")
    for _ in range(6):
        pg.locator(".se-row").nth(0).locator(".se-minus").click()
    check("par 5: the - button stops at 2 (no ace on a par 5)",
          pg.inner_text(".se-row >> nth=0 >> .se-score .v") == "2")
    for _ in range(6):
        pg.locator(".se-row").nth(0).locator(".se-plus").click()
    play(pg, 8)
    pg.wait_for_timeout(1200)
    review_ok(pg, 9, "nine")
    pg.click(".se-cell[data-h='4']")
    pg.wait_for_selector("text=Hole 4")
    check("tapping a cell opens that hole to adjust, with 'Save hole 4'",
          "Save hole 4" in pg.inner_text(".se-pill.go"))
    pg.locator(".se-row").nth(1).locator(".se-plus").click()
    pg.click("[data-act=save]")
    pg.wait_for_timeout(1200)
    review_ok(pg, 9, "nine, after an adjustment")
    got = se.get_entered_scores(900, rid9)["rounds"][0]["players"]
    mark = {x["customer_id"]: x["scores"] for x in got}[102]
    check("the adjustment reached the server", mark.get("4") == 5, mark)

    pg.evaluate("localStorage.setItem('se_hole_' + new URLSearchParams(location.search).get('t').slice(0,24), '9')")
    pg.reload()
    review_ok(pg, 9, "nine, reopened with a remembered hole")

    print("eighteen holes, start on 1 (the turn)")
    rid18, gid18, tok18 = make(18, 1, "eighteen")
    pg = open_as_kerry(tok18)
    play(pg, 18)
    pg.wait_for_timeout(1500)
    review_ok(pg, 18, "eighteen")

    print("shotgun, nine holes starting on 4 (last hole is 3)")
    ridsg, gidsg, toksg = make(9, 4, "shotgun")
    pg = open_as_kerry(toksg)
    pg.wait_for_selector("text=Hole 4")
    play(pg, 9)
    pg.wait_for_timeout(1500)
    review_ok(pg, 9, "shotgun")
    b.close()

try:
    os.unlink(DB)
except OSError:
    pass
print("ALL PASS" if not FAILURES else f"{len(FAILURES)} FAILURE(S): {FAILURES}")
sys.exit(1 if FAILURES else 0)
