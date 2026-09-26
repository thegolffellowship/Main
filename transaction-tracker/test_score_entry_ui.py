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
    """Once every hole is in: CHECK THE CARD (Kerry 2026-09-25, option A)."""
    page.wait_for_selector("text=Check the card", timeout=5000)
    body = page.inner_text("body")
    check(f"{label}: no 'Save last hole' once every hole is saved", "Save last hole" not in body)
    cells = page.locator(".se-check.cur button.cell")
    check(f"{label}: one nine on screen, every number a button (2 players x 9)",
          cells.count() == 18, cells.count())
    check(f"{label}: the one primary action is Card matches paper",
          page.locator(".se-pill.go").count() == 1
          and "Card matches paper" in page.inner_text(".se-pill.go"))
    check(f"{label}: FRONT | BACK toggle only on an 18",
          page.locator(".se-seg").count() == (1 if n == 18 else 0))


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
    bars = pg.locator(".se-row .se-tee")
    check("every player row carries a tee bar", bars.count() == 2, bars.count())
    check("no tee on file shows the neutral grey bar, not a guessed tee",
          "rgb(156, 163, 175)" in bars.nth(0).evaluate("e => getComputedStyle(e).backgroundColor"))
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
    check("help text is hidden until How It Works is tapped", pg.locator(".se-helptext").count() == 0)
    hb = pg.locator("[data-act=help]")
    check("help is the How It Works standard: orange pill, white text",
          hb.inner_text().strip().upper() == "HOW IT WORKS"
          and hb.evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(232, 124, 62)"
          and hb.evaluate("e => getComputedStyle(e).color") == "rgb(255, 255, 255)",
          (hb.inner_text(), hb.evaluate("e => getComputedStyle(e).backgroundColor")))
    pg.click("[data-act=help]")
    check("How It Works shows the help", pg.locator(".se-helptext").count() == 1)
    pg.click("[data-act=help]")
    pg.click("button.cell[data-key='c:102'][data-h='4']")
    pg.wait_for_selector(".se-picker")
    picker_after_card = pg.evaluate("""() => {
        const t = document.querySelector('.se-check.cur'), p = document.querySelector('.se-picker');
        return !!(t.compareDocumentPosition(p) & Node.DOCUMENT_POSITION_FOLLOWING); }""")
    check("tapping a number opens the score row right under the card", picker_after_card)
    vals = [int(x) for x in pg.locator(".se-picker .row button").all_inner_texts()]
    check("the row runs 1 to par + 3 (hole 4 is a par 4: 1..7)", vals == list(range(1, 8)), vals)
    pg.click(".se-picker [data-act=cset][data-v='5']")
    pg.wait_for_timeout(1200)
    check("the changed number stays marked", pg.locator("button.cell.changed[data-key='c:102'][data-h='4']").count() == 1)
    review_ok(pg, 9, "nine, after an adjustment")
    got = se.get_entered_scores(900, rid9)["rounds"][0]["players"]
    mark = {x["customer_id"]: x["scores"] for x in got}[102]
    check("the adjustment reached the server", mark.get("4") == 5, mark)

    pg.evaluate("localStorage.setItem('se_hole_' + new URLSearchParams(location.search).get('t').slice(0,24), '9')")
    pg.reload()
    review_ok(pg, 9, "nine, reopened with a remembered hole")

    # Kerry 2026-09-25: "So are you saying I can tap a hole on that summary
    # scorecard to change it? Because that's not obvious". The sign screen
    # now makes your own row tappable and says so.
    pg.click("[data-act=matches]")
    pg.wait_for_selector("text=Photo of the paper card")
    check("submit waits for who kept the paper card",
          pg.locator("[data-act=submit]").is_disabled())
    pg.click("[data-act=ps][data-cid='101']")
    check("'Me' is a choice, with Kerry's note",
          "Next time, please have one person keep the paper card and another Live Scoring" in pg.inner_text("body"))
    pg.click("[data-act=ps][data-cid='102']")
    check("the note goes away for anyone else",
          "Next time, please have one person" not in pg.inner_text("body"))
    check("...and for a photo", pg.locator("[data-act=submit]").is_disabled())
    pg.click("[data-act=nophoto]")
    check("'Can't take a photo?' lets it go without one",
          not pg.locator("[data-act=submit]").is_disabled()
          and "without a photo" in pg.inner_text("[data-act=submit]"))
    pg.click("[data-act=submit]")
    pg.wait_for_selector("text=Sign your card")
    cc = se.get_group_card(gid9)["card_check"]
    check("submit records Mark as the print scorer, no photo, dial off: nobody signed for",
          cc and cc["print_scorer_customer_id"] == 102 and not cc["has_photo"]
          and not cc["signed_for_group"], cc)
    body = pg.inner_text("body")
    check("sign screen: the copy says to tap the number that's wrong",
          "tap that number" in body, body[:400])
    mine = pg.locator("tr.me button.hole[data-act=pickhole]")
    check("sign screen: every hole on your own row is a tappable button", mine.count() == 9, mine.count())
    check("sign screen: other players' rows are not tappable",
          pg.locator("tr:not(.me) button.hole").count() == 0)
    pg.click("tr.me button.hole[data-h='3']")
    pg.wait_for_selector("text=Is that wrong?")
    check("tapping a hole asks first: 'Hole 3 shows … Is that wrong?'",
          "Hole 3 shows" in pg.inner_text("body") and pg.locator("td.picked").count() == 1)
    check("the flag box says the maximum is triple bogey (Kerry: 'notify the player')",
          "Maximum allowed is triple bogey (6)" in pg.inner_text("body"))
    pg.click("[data-act=unflag]")
    pg.wait_for_timeout(200)
    check("Cancel leaves the card unflagged", "Is that wrong?" not in pg.inner_text("body")
          and not se.get_group_card(gid9)["flags"])
    pg.click("[data-act=flag]")
    check("Something's wrong outlines your row's holes", pg.locator(".se-card.picking").count() == 1)
    pg.click("tr.me button.hole[data-h='2']")
    pg.click("button[data-act=flaghole][data-h='2']")
    pg.wait_for_selector("text=flagged", timeout=5000)
    flags = se.get_group_card(gid9)["flags"]
    check("Flag hole 2 reaches the server as an open flag on hole 2 for Kerry",
          any(f["hole"] == 2 and f["customer_id"] == 101 for f in flags), flags)
    check("after flagging, the row is no longer tappable",
          pg.locator("tr.me button.hole").count() == 0)
    check("your own row stands out", pg.locator(".se-card tr.me td").first.evaluate(
          "e => getComputedStyle(e).backgroundColor") == "rgb(253, 235, 221)")
    check("the scorekeeper's finished card lists the flag with Fix it",
          "Kerry flagged hole 2" in pg.inner_text("body") and pg.locator("[data-act=fixflag]").count() == 1)
    pg.click("[data-act=fixflag]")
    pg.wait_for_selector(".se-picker")
    check("Fix it opens Check the card with that number's row open",
          "Hole 2" in pg.inner_text(".se-picker") and "Kerry" in pg.inner_text(".se-picker"))
    pg.click(".se-picker [data-act=cset][data-v='4']")
    pg.wait_for_timeout(1200)
    check("fixing the number resolves the flag", se.get_group_card(gid9)["flags"] == [])

    print("eighteen holes, start on 1 (the turn); the dial on: the scorekeeper signs for the group")
    se.set_keeper_signs(900, True)
    rid18, gid18, tok18 = make(18, 1, "eighteen")
    pg = open_as_kerry(tok18)
    for _ in range(9):
        pg.click("[data-act=save]")
        pg.wait_for_timeout(250)
        if pg.locator("button[data-act=ctp][data-cid='']").count():
            pg.click("button[data-act=ctp][data-cid='']")
            pg.wait_for_timeout(400)
    pg.wait_for_selector("text=Front nine done")
    check("the turn shows each player's nine under his name (2 x 9 tappable holes)",
          pg.locator(".se-turnrow .se-mini button[data-act=goto]").count() == 18)
    pg.click("[data-act=goto] >> text=Back to hole 9")
    pg.wait_for_selector("text=Hole 9")
    check("Back to hole 9 goes back a hole", "Hole 9" in pg.inner_text(".se-h1"))
    pg.click("[data-act=save]")
    pg.wait_for_selector("text=Front nine done")
    pg.locator(".se-turnrow").nth(1).locator(".se-mini button[data-h='3']").click()
    pg.wait_for_selector("h1:has-text('Hole 3')")
    check("tapping a hole at the turn opens it to edit", "Hole 3" in pg.inner_text(".se-h1"))
    pg.click(".se-cell[data-h='10']")
    pg.wait_for_selector("h1:has-text('Hole 10')")
    play(pg, 9)
    pg.wait_for_timeout(1500)
    review_ok(pg, 18, "eighteen")
    check("Check the card puts the last name under the first",
          pg.locator(".se-check.cur td.nm .ln").first.inner_text().strip() == "Niester")
    x_front = pg.evaluate("() => [...document.querySelectorAll('.se-check.cur thead th')].map(t => Math.round(t.getBoundingClientRect().left))")
    pg.click("[data-act=nine][data-n='1']")
    x_back = pg.evaluate("() => [...document.querySelectorAll('.se-check.cur thead th')].map(t => Math.round(t.getBoundingClientRect().left))")
    check("FRONT and BACK use the exact same column positions", x_front == x_back, (x_front, x_back))
    pg.click("[data-act=nine][data-n='0']")
    heads = pg.locator(".se-check.cur thead th").all_inner_texts()
    check("FRONT shows holes 1-9 and OUT (TOT column left blank so the nines line up)",
          heads[1] == "1" and heads[-2].upper() == "OUT" and heads[-1] == "", heads)
    pg.click("[data-act=nine][data-n='1']")
    heads = pg.locator(".se-check.cur thead th").all_inner_texts()
    check("BACK shows holes 10-18, IN and TOT", heads[1] == "10" and heads[-2].upper() == "IN"
          and heads[-1].upper() == "TOT", heads)
    pg.click("button.cell[data-key='c:101'][data-h='13']")
    vals = [int(x) for x in pg.locator(".se-picker .row button").all_inner_texts()]
    check("a par 5 row runs 2..8", vals == list(range(2, 9)), vals)
    pg.click("[data-act=cpick][data-key='c:101'][data-h='13']")
    check("tapping the same number again closes the row", pg.locator(".se-picker").count() == 0)
    pg.click("[data-act=matches]")
    pg.wait_for_selector("text=Photo of the paper card")
    from PIL import Image
    jp = tempfile.mktemp(suffix=".jpg")
    Image.new("RGB", (2400, 1800), (240, 240, 230)).save(jp, "JPEG")
    pg.set_input_files("input[data-photo]", jp)
    pg.wait_for_selector("img.se-shot", timeout=5000)
    pg.click("[data-act=ps][data-cid='']")
    pg.fill("#se-ps-name", "Joe Caddie")
    pg.click("[data-act=submit]")
    pg.wait_for_selector("text=Card submitted", timeout=5000)
    pg.wait_for_timeout(2500)
    cc = se.get_group_card(gid18)["card_check"]
    check("the photo arrived and is kept as a file, not in the database",
          cc and cc["has_photo"] and se.card_photo_path(cc["id"]) is not None, cc)
    if cc and se.card_photo_path(cc["id"]):
        with Image.open(se.card_photo_path(cc["id"])) as im:
            check("the phone shrank the photo to 1600 px on the long side", max(im.size) == 1600, im.size)
        check("...and to well under 1 MB", se.card_photo_path(cc["id"]).stat().st_size < 1_000_000,
              se.card_photo_path(cc["id"]).stat().st_size)
    check("someone outside the group is kept by name", cc and cc["print_scorer_name"] == "Joe Caddie"
          and cc["print_scorer_customer_id"] is None, cc)
    sig = {(x["customer_id"], x["kind"]): x for x in se.get_group_card(gid18)["signoffs"]}
    check("dial on: Mark's card is signed, by Kerry", sig.get((102, "player"), {}).get("signed_by_customer_id") == 101, sig)
    check("...and Kerry attested as scorekeeper", (101, "scorekeeper") in sig, sig)
    ctx2 = b.new_context(viewport={"width": 390, "height": 844})
    mk = ctx2.new_page()
    mk.goto(f"http://127.0.0.1:{PORT}/member/score?t={tok18}")
    mk.click("text=Mark Stich")
    mk.click("[data-act=follow]")
    mk.wait_for_selector("text=signed your card for the group", timeout=5000)
    check("Mark sees Kerry signed for him, and can still tap his own row",
          mk.locator("tr.me button.hole").count() == 18)
    mk.click("tr.me button.hole[data-h='7']")
    mk.click("button[data-act=flaghole][data-h='7']")
    mk.wait_for_selector("text=flagged", timeout=5000)
    sig = {(x["customer_id"], x["kind"]) for x in se.get_group_card(gid18)["signoffs"]}
    check("Mark's flag voids the signature Kerry made for him", (102, "player") not in sig, sig)
    se.set_keeper_signs(900, False)

    print("shotgun, nine holes starting on 4 (last hole is 3)")
    ridsg, gidsg, toksg = make(9, 4, "shotgun")
    pg = open_as_kerry(toksg)
    pg.wait_for_selector("text=Hole 4")
    play(pg, 9)
    pg.wait_for_timeout(1500)
    review_ok(pg, 9, "shotgun")
    print("tee mark standard: men solid (white outlined), women outlined")
    cz = sqlite3.connect(DB)
    if "gender" in [r[1] for r in cz.execute("PRAGMA table_info(customers)")]:
        cz.execute("INSERT INTO courses (course_id, name) VALUES (7790, 'Mark GC')")
        for tid, nm, gen, bands in [(77901, "Blue", "M", "<50"), (77902, "White", "M", "50-64,65+"),
                                    (77903, "Red (L)", "F", "Forward")]:
            cz.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, gender, holes, rating, slope, "
                       "yardage_total, tgf_bands) VALUES (?,?,?,?,18,70.1,125,6400,?)", (tid, 7790, nm, gen, bands))
        cz.execute("INSERT INTO events (id, item_name, event_date, course_id) VALUES (905, 'Mark test', '2026-09-29', 7790)")
        cz.execute("INSERT INTO customers (customer_id, first_name, last_name, gender) VALUES (107, 'Gus', 'Vasquez', 'M')")
        cz.execute("INSERT INTO customers (customer_id, first_name, last_name, gender) VALUES (108, 'Ann', 'Lee', 'F')")
        cz.commit()
        rt = se.create_round(905, 9, course_holes=course(9))["round_id"]
        gt = se.upsert_group(rt, 1, players=[
            {"customer_id": 107, "display_name": "Gus Vasquez", "tee": "Forward", "seat": 1},
            {"customer_id": 108, "display_name": "Ann Lee", "tee": "Forward", "seat": 2},
            {"customer_id": 102, "display_name": "Mark Stich", "tee": "50-64", "seat": 3}])["group_id"]
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        tp = ctx.new_page()
        tp.goto(f"http://127.0.0.1:{PORT}/member/score?t={se.make_group_token(gt)}")
        tp.click("text=Gus Vasquez")
        tp.wait_for_selector(".se-row .se-tee")
        cls = tp.locator(".se-row .se-tee").evaluate_all("els => els.map(e => e.className)")
        check("a man on the red tee is SOLID", "ring" not in cls[0], cls)
        check("a woman on the red tee is OUTLINED", "ring" in cls[1], cls)
        check("a man on white gets the dark outline (white is the exception)", "light" in cls[2], cls)
    cz.close()

    print("match play: no M tag (Kerry 2026-09-26), the max-triple notice, Ball in hole / Picked up")
    import json as _json
    ridm, gidm, tokm = make(9, 1, "match")
    # A regular-season (round-level) match keeps the Ball in hole / Picked up
    # prompt; a Lone Star Cup match uses X instead (tested below).
    se.set_round_matches(ridm, [{"id": "M1", "format": "singles", "sides": [[101], [102]]}])
    pg = open_as_kerry(tokm)
    check("the hole screen shows the match standing",
          pg.locator(".se-mcard").count() == 1 and "NIESTER" in pg.inner_text(".se-mcard").upper()
          and "Kerry v Mark" in pg.locator(".se-mc-head").get_attribute("aria-label"))
    check("no M tag; each match player reads 'vs' his opponent on the hole screen",
          pg.locator(".se-mtag").count() == 0 and "vs Mark" in pg.inner_text("body"))
    for _ in range(4):
        pg.locator(".se-row").nth(1).locator(".se-plus").click()
    body = pg.inner_text("body")
    check("pressing + past the max says so, with the match hint",
          "Maximum allowed is triple bogey (7)" in body and "mark it Picked up" in body, body[:300])
    pg.click("[data-act=save]")
    pg.wait_for_selector("text=Triple in a match", timeout=5000)
    check("a triple for a match player asks Ball in hole / Picked up (only for him)",
          pg.locator("[data-act=pu]").count() == 2 and pg.locator("[data-act=pudone]").is_disabled())
    pg.click("[data-act=pu][data-m=picked_up]")
    pg.click("[data-act=pudone]")
    pg.wait_for_selector("text=Hole 2", timeout=5000)
    pg.wait_for_timeout(1500)
    card = se.get_group_card(gidm)
    pg.wait_for_timeout(300)
    check("after hole 1 (Mark picked up) the standing reads Kerry 1 UP thru 1",
          "Kerry 1 UP thru 1" in pg.locator(".se-mc-head").get_attribute("aria-label")
          and pg.locator(".se-mc-bar.a").count() == 1 and pg.locator(".se-hd.a").count() == 1,
          pg.locator(".se-mc-head").get_attribute("aria-label"))
    pg.click("[data-act=mtoggle]")
    check("tapping the match opens its hole-by-hole card; hole 1 is circled for Kerry",
          pg.locator(".se-mc-grid").count() == 1 and pg.locator(".se-mc-grid .w.a").count() == 1)
    pg.click("[data-act=mtoggle]")
    check("tapping again closes it", pg.locator(".se-mc-grid").count() == 0)
    check("Picked up is stored beside the 7; the card still says 7",
          card["marks"].get("c:102") == {"1": "picked_up"} and card["scores"]["c:102"]["1"] == 7, card["marks"])
    play(pg, 8)
    pg.wait_for_timeout(1500)
    pg.wait_for_selector("text=Check the card")
    check("the check card rings the picked-up number and shows the legend",
          pg.locator("button.cell.pu[data-key='c:102'][data-h='1']").count() == 1
          and pg.locator("button.cell[data-key='c:102'][data-h='1'] .ring").evaluate("e => { const r = e.getBoundingClientRect(); return Math.abs(r.width - r.height) < 1; }")
          and pg.locator(".se-pukey .se-pu").count() == 1 and "Picked up" in pg.inner_text(".se-pukey"))
    pg.click("button.cell[data-key='c:101'][data-h='2']")
    check("the check picker shows the max notice", "Maximum allowed is triple bogey (8)" in pg.inner_text(".se-picker"))
    pg.click(".se-picker [data-act=cset][data-v='8']")
    pg.wait_for_selector("text=Triple in a match", timeout=5000)
    pg.click("[data-act=pu][data-m=holed]")
    pg.click("[data-act=pudone]")
    pg.wait_for_selector("text=Check the card")
    pg.wait_for_timeout(1500)
    check("changing to a triple on the check card asks too; Ball in hole is stored",
          se.get_group_card(gidm)["marks"].get("c:101") == {"2": "holed"}, se.get_group_card(gidm)["marks"])
    se.set_round_matches(ridm, None)

    print("Lone Star Cup: X past the triple, the banner in the leading team's colour")
    ridc, gidc, tokc = make(9, 1, "cup")
    db.set_app_setting("lsc_matches", _json.dumps({"event_id": 900, "sessions": [
        {"id": "s1", "format": "singles", "se_round": ridc, "n_holes": 9,
         "matches": [{"id": "M1", "austin": [101], "sa": [102]}]}]}))
    pc = open_as_kerry(tokc)
    for _ in range(4):
        pc.locator(".se-row").nth(1).locator(".se-plus").click()
    check("one tap past the triple shows X, marked Picked up",
          pc.locator(".se-row").nth(1).locator(".se-x").count() == 1
          and "Picked up" in pc.locator(".se-row").nth(1).inner_text())
    pc.click("[data-act=save]")
    pc.wait_for_selector("text=Hole 2", timeout=5000)
    check("a cup match never asks Ball in hole / Picked up", pc.locator("[data-act=pu]").count() == 0)
    pc.wait_for_timeout(1500)
    cc = se.get_group_card(gidc)
    check("X is stored as the triple with the Picked up mark",
          cc["scores"]["c:102"]["1"] == 7 and cc["marks"].get("c:102") == {"1": "picked_up"}, (cc["scores"], cc["marks"]))
    pc.reload(); pc.wait_for_selector("text=You're keeping score")
    ml = pc.locator(".se-mcard")
    check("Kerry (Austin) leads, so the banner is Austin's colour",
          "lead-austin" in ml.get_attribute("class")
          and pc.locator(".se-mc-bar.a").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(191, 87, 0)", ml.get_attribute("class"))
    play(pc, 8)
    pc.wait_for_selector("text=Check the card")
    pc.wait_for_timeout(1200)
    check("the check card shows X, not a ringed 7",
          pc.locator("button.cell[data-key='c:102'][data-h='1'] .se-x").count() == 1
          and pc.locator("button.cell.pu").count() == 0)
    pc.click("button.cell[data-key='c:102'][data-h='2']")
    check("the check picker offers X for a cup player", pc.locator(".se-picker [data-v='X']").count() == 1)
    pc.click(".se-picker [data-v='X']")
    pc.wait_for_timeout(1500)
    check("choosing X there stores the triple, picked up",
          se.get_group_card(gidc)["marks"].get("c:102") == {"1": "picked_up", "2": "picked_up"}
          and se.get_group_card(gidc)["scores"]["c:102"]["2"] == 8)
    pc.wait_for_timeout(800)
    wl = pc.locator(".se-mcard")
    check("a won cup match shimmers in the winner's colour",
          "won" in wl.get_attribute("class") and "lead-austin" in wl.get_attribute("class"), wl.get_attribute("class"))
    db.set_app_setting("lsc_matches", "")

    print("scoring off: a Tracker admin can sign in on the link's page to preview")
    os.environ["ADMIN_PIN"] = "4242"
    db.set_app_setting("score_entry_live", "")
    rz, gz, tokz = make(9, 1, "gate")
    gp_ = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    gp_.goto(f"http://127.0.0.1:{PORT}/member/score?t={tokz}")
    gp_.wait_for_selector("#se-pin")
    check("the closed page offers the admin sign-in", "isn't open to players yet" in gp_.inner_text("body"))
    gp_.fill("#se-pin", "1111"); gp_.click("[data-act=stafflogin]"); gp_.wait_for_timeout(800)
    check("a wrong PIN says so and stays closed", "Invalid PIN" in gp_.inner_text("body") and gp_.locator("#se-pin").count() == 1)
    gp_.fill("#se-pin", "4242"); gp_.click("[data-act=stafflogin]")
    gp_.wait_for_selector("text=Kerry Niester", timeout=5000)
    check("the admin PIN opens the card", gp_.locator("[data-act=pick]").count() == 2)
    db.set_app_setting("score_entry_live", "1")

    print("one screen, no scrolling (Kerry 2026-09-26): 4 players, 18 holes, a match, on a 390x660 phone")
    rf = se.create_round(900, 18, label=se.PREVIEW_LABEL + " · 18 holes", course_holes=course(18))["round_id"]
    gf = se.upsert_group(rf, 1, start_hole=1, players=[
        {"customer_id": c_, "display_name": n_, "playing_handicap": ph_, "seat": i_ + 1}
        for i_, (c_, n_, ph_) in enumerate([(101, "Kerry Niester", 1), (102, "Mark Stich", 29),
                                            (107, "Gus Vasquez", 13), (108, "Ann Lee", 10)])])["group_id"]
    se.set_round_matches(rf, [{"id": "F", "format": "singles", "sides": [[101], [102]]}])
    fpg = b.new_context(viewport={"width": 390, "height": 660}, has_touch=True).new_page()
    fpg.goto(f"http://127.0.0.1:{PORT}/member/score?t={se.make_group_token(gf)}")
    fpg.click("text=Kerry Niester"); fpg.wait_for_selector("text=You're keeping score")
    fh = fpg.evaluate("document.documentElement.scrollHeight")
    check("the hole screen fits without scrolling", fh <= 660, fh)
    check("the PREVIEW label is not on the scoring screen", "PREVIEW" not in fpg.inner_text(".se-eyebrow").upper())
    check("the save button is on screen", fpg.locator("[data-act=save]").bounding_box()["y"] + 50 <= 660)
    check("the site nav steps aside while scoring", not fpg.locator(".shell-nav").first.is_visible())
    fdev = fpg.evaluate("JSON.parse(localStorage.getItem('se_device'))")
    se.write_scores(gf, fdev, 101, [{"op_id": f"fit{c_}-{h}", "customer_id": c_, "hole": h, "gross": PARS[h - 1]}
                                    for h in range(1, 19) for c_ in (101, 102, 107, 108)])
    fpg.evaluate("localStorage.removeItem('se_hole_' + new URLSearchParams(location.search).get('t').slice(0,24))")
    fpg.reload(); fpg.wait_for_selector("text=Check the card"); fpg.wait_for_timeout(500)
    fh = fpg.evaluate("document.documentElement.scrollHeight")
    check("Check the card fits without scrolling", fh <= 660, fh)
    swipe_js = """(dx) => { const el = document.querySelector('.se-vp'); const r = el.getBoundingClientRect();
        const x0 = r.left + r.width / 2, y0 = r.top + r.height / 2;
        const mk = (x) => new Touch({identifier: 1, target: el, clientX: x, clientY: y0});
        el.dispatchEvent(new TouchEvent('touchstart', {bubbles: true, touches: [mk(x0)], changedTouches: [mk(x0)]}));
        el.dispatchEvent(new TouchEvent('touchmove', {bubbles: true, touches: [mk(x0 + dx / 2)], changedTouches: [mk(x0 + dx / 2)]}));
        el.dispatchEvent(new TouchEvent('touchmove', {bubbles: true, touches: [mk(x0 + dx)], changedTouches: [mk(x0 + dx)]}));
        el.dispatchEvent(new TouchEvent('touchend', {bubbles: true, touches: [], changedTouches: [mk(x0 + dx)]})); }"""
    drag_js = """(dx) => { const el = document.querySelector('.se-vp'); const r = el.getBoundingClientRect();
        const x0 = r.left + r.width / 2, y0 = r.top + r.height / 2;
        const mk = (x) => new Touch({identifier: 1, target: el, clientX: x, clientY: y0});
        el.dispatchEvent(new TouchEvent('touchstart', {bubbles: true, touches: [mk(x0)], changedTouches: [mk(x0)]}));
        el.dispatchEvent(new TouchEvent('touchmove', {bubbles: true, touches: [mk(x0 + dx)], changedTouches: [mk(x0 + dx)]}));
        return getComputedStyle(document.querySelector('.se-track')).transform; }"""
    tf = fpg.evaluate(drag_js, -40)
    check("mid-swipe the card follows the finger", tf not in ("none", "") and "-40" in tf, tf)
    fpg.evaluate("""() => { const el = document.querySelector('.se-vp'); const r = el.getBoundingClientRect();
        const t = new Touch({identifier: 1, target: el, clientX: r.left + r.width / 2 - 40, clientY: r.top + 10});
        el.dispatchEvent(new TouchEvent('touchend', {bubbles: true, touches: [], changedTouches: [t]})); }""")
    fpg.wait_for_timeout(400)
    check("a short drag springs back to the same nine", fpg.locator(".se-seg button.on").inner_text() == "FRONT")
    fpg.evaluate(drag_js, -120)
    bx = fpg.evaluate("document.querySelectorAll('.se-check')[1].getBoundingClientRect().left")
    check("mid-swipe the BACK nine is already sliding in beside the FRONT", 0 < bx < 390, bx)
    fpg.evaluate("""() => { const el = document.querySelector('.se-vp'); const r = el.getBoundingClientRect();
        const t = new Touch({identifier: 1, target: el, clientX: r.left + r.width / 2 - 120, clientY: r.top + r.height / 2});
        el.dispatchEvent(new TouchEvent('touchend', {bubbles: true, touches: [], changedTouches: [t]})); }""")
    fpg.wait_for_timeout(500)
    check("letting go past the line snaps to BACK", fpg.locator(".se-seg button.on").inner_text() == "BACK")
    fpg.click("[data-act=nine][data-n='0']")
    fpg.evaluate(swipe_js, -120); fpg.wait_for_timeout(500)
    check("swipe left on the card shows the BACK nine",
          fpg.locator(".se-seg button.on").inner_text() == "BACK" and fpg.locator(".se-check.cur th").nth(1).inner_text() == "10")
    fpg.evaluate(swipe_js, 20); fpg.wait_for_timeout(500)
    check("a small drag is not a swipe", fpg.locator(".se-seg button.on").inner_text() == "BACK")
    fpg.evaluate(swipe_js, 120); fpg.wait_for_timeout(500)
    check("swipe right goes back to FRONT", fpg.locator(".se-seg button.on").inner_text() == "FRONT")
    cellp = fpg.locator("button.cell[data-key='c:102'][data-h='1']").locator("xpath=..")
    g = cellp.locator(".se-pops.cell .g")
    check("in a card cell the PH pops sit above the number and the team pops below",
          g.count() == 2 and g.nth(0).locator(".se-pop:not(.t)").count() >= 1
          and g.nth(0).bounding_box()["y"] < cellp.locator("button.cell").bounding_box()["y"] + 10)

    print("CA #717: after a cup match is decided the phone keeps taking holes (skins)")
    rk, gk, tokk = make(9, 1, "closeout-ui")
    db.set_app_setting("lsc_matches", _json.dumps({"event_id": 900, "sessions": [
        {"id": "sK", "format": "singles", "se_round": rk, "n_holes": 9,
         "matches": [{"id": "K1", "austin": [101], "sa": [102]}]}]}))
    pk = open_as_kerry(tokk)
    kdev = pk.evaluate("JSON.parse(localStorage.getItem('se_device'))")
    se.write_scores(gk, kdev, 101, [{"op_id": f"k{c_}-{h}", "customer_id": c_, "hole": h,
                                     "gross": PARS[h - 1] - 1 if c_ == 101 else PARS[h - 1] + 1}
                                    for h in range(1, 6) for c_ in (101, 102)])
    pk.evaluate("localStorage.setItem('se_hole_' + new URLSearchParams(location.search).get('t').slice(0,24), '6')")
    pk.reload(); pk.wait_for_selector("h1:has-text('Hole 6')")
    check("the match reads final (5&4) on hole 6", "5&4" in pk.inner_text(".se-mcard") and "final" in pk.inner_text(".se-mcard").lower())
    check("hole 6 still has its steppers and Save after the close-out",
          pk.locator(".se-plus").count() == 2 and pk.locator("[data-act=save]").is_enabled())
    pk.locator(".se-row").nth(1).locator(".se-minus").click()
    pk.click("[data-act=save]"); pk.wait_for_selector("h1:has-text('Hole 7')"); pk.wait_for_timeout(1200)
    kc = se.get_group_card(gk)
    check("a hole after the close-out saves like any other",
          kc["scores"]["c:101"].get("6") == PARS[5] and kc["scores"]["c:102"].get("6") == PARS[5] - 1, kc["scores"])
    check("and the result stays 5&4", kc["match_status"][0]["margin"] == "5&4")
    db.set_app_setting("lsc_matches", "")

    print("pops as dots: black = PH at 100%, orange = Team/Cart Net")
    rp = se.create_round(900, 9, label="pops", course_holes=course(9))["round_id"]
    gp = se.upsert_group(rp, 1, players=[
        {"customer_id": 101, "display_name": "Kerry Niester", "seat": 1, "playing_handicap": 0},
        {"customer_id": 102, "display_name": "Mark Stich", "seat": 2, "playing_handicap": 4}])["group_id"]
    se.set_game_handicaps(rp, {101: 0, 102: 3}, unit="cart", basis="Cart Net 85%")
    pp = open_as_kerry(se.make_group_token(gp))
    row = pp.locator(".se-row").nth(1)
    check("hole 1 (index 1): Mark's score carries 1 black dot and 1 orange",
          row.locator(".se-pop:not(.t)").count() == 1 and row.locator(".se-pop.t").count() == 1,
          row.inner_html()[:400])
    check("the low man shows no dots", pp.locator(".se-row").nth(0).locator(".se-pop").count() == 0)
    check("no stroke text on the row", "stroke here" not in pp.inner_text("body"))
    check("a small key names the two dots",
          "PH pop" in pp.inner_text(".se-popkey") and "Cart Net pop" in pp.inner_text(".se-popkey"))
    play(pp, 9)
    pp.wait_for_selector("text=Check the card")
    pp.wait_for_timeout(800)
    check("a nine-hole card is one card: no swipe track", pp.locator(".se-vp").count() == 0 and pp.locator(".se-seg").count() == 0)
    cell = pp.locator("button.cell[data-key='c:102'][data-h='4']").locator("xpath=..")
    check("the check card puts the dots in the cell's corner (hole 4: 1 PH, 0 team)",
          cell.locator(".se-pops.cell .se-pop:not(.t)").count() == 1 and cell.locator(".se-pop.t").count() == 0,
          cell.inner_html())
    pp.screenshot(path=os.path.join(SHOTS, "pops-check-card.png"), full_page=True) if "SHOTS" in globals() else None
    b.close()

try:
    os.unlink(DB)
except OSError:
    pass
print("ALL PASS" if not FAILURES else f"{len(FAILURES)} FAILURE(S): {FAILURES}")
sys.exit(1 if FAILURES else 0)
