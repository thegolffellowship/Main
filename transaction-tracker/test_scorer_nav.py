"""Scorer navigation (v2.523.0, Kerry 2026-10-02, approved from the real-code
mockup, mailbox #1155/#1157/#1158 + his words in the Track A session).

API (Flask test client, no browser):
- /api/events-leaderboard and /event: member tier since v2.523.4 (anonymous
  and member sessions read every event),
  manager 200 (unchanged); a live scorer's group link (?t=) reads 200 and
  gets HIS event only (the list narrowed, another event's board 403).
- /member/score/board with a bad link falls back to the score page.

Screen (headless Chromium at 390x844, skips without Playwright):
- the SCORING | LEADERBOARD toggle is under the mark on the hole screen
  (Scoring active) and on the board (Leaderboard active, "Hole N" on the
  Scoring segment), and on no other member page;
- tapping LEADERBOARD lands on the scorer's event only, with the event bar,
  the seven game tabs fitting the width in two rows, the Won column HIDDEN
  while scores are out, every name cell one row high with its tee dot inside;
- tapping SCORING returns to the same hole;
- the hole screen still fits one screen with the toggle (no scrolling);
- a board whose field is complete shows the Won column again.
Run: python3 test_scorer_nav.py
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
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "ui-test")
os.environ["ADMIN_PIN"] = "4242"
os.environ["SA_MANAGER_PIN"] = "5151"
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


PARS = [4, 5, 3, 4, 5, 4, 3, 4, 4]
SI = [5, 1, 9, 3, 7, 2, 8, 4, 6]
YD = [340, 486, 150, 417, 531, 349, 179, 463, 373]
c = sqlite3.connect(DB)
c.execute("INSERT INTO events (id, item_name, event_date, chapter, format, course) VALUES (900, 's9.26 Olympia Hills', '2026-10-06', 'San Antonio', '9 Holes', 'Olympia Hills Golf Club')")
c.execute("INSERT INTO events (id, item_name, event_date, chapter, format, course) VALUES (901, 's9.25 Canyon Springs', '2026-09-29', 'San Antonio', '9 Holes', 'Canyon Springs Golf Club')")
cols = [r[1] for r in c.execute("PRAGMA table_info(courses)")]
c.execute("INSERT INTO courses (course_id, %s) VALUES (22371, 'Olympia Hills Golf Club')" % ("name" if "name" in cols else "course_name"))
c.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, gender, holes, rating, slope, tgf_bands) VALUES (493,22371,'Blue','M',9,35.6,128,'<50')")
for h in range(1, 10):
    c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) VALUES (493,?,?,?,?)", (h, PARS[h - 1], YD[h - 1], SI[h - 1]))
GROUP = [(9101, "Kerry", "Niester", 1), (9102, "Michael", "Mesa", 0), (9103, "Michael", "Murphy", 15), (9104, "Will", "Wallace", 11)]
for cid, fn, ln, ph in GROUP:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
# event 900 IN PLAY (holes out) — a long name to prove the one-row rule;
# event 901 COMPLETE (every hole in) — the Won column comes back there
FIELD = {"NIESTER, Kerry": (9101, 1, [4, 5]), "MESA, Michael": (9102, 0, [4, 5]),
         "MURPHY, Michael": (9103, 15, [5, 6]), "WALLACE, Will": (9104, 11, [5, 5]),
         "VANDERSCHOONHOVEN, Bartholomew": (9105, 5, [4, 5, 3, 5]), "YOUNG, Jeff": (9106, 1, [3, 6, 3, 4])}
for nm, (cid, ph, holes) in FIELD.items():
    if cid > 9104:
        c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, nm.split(", ")[1], nm.split(", ")[0].title()))
    for ev_id, hs, done in ((900, holes, False), (901, PARS, True)):
        g = sum(hs)
        rid_ = c.execute("INSERT INTO scoring_rounds (event_id, customer_id, player_name, source, gross, net, playing_handicap, round_date, holes_played, course_id, tee_id, imported_at, gg_aggregate_id) VALUES (?,?,?,'gg',?,?,?,'2026-10-06',?,22371,493,'2026-09-29 00:00:00',?) RETURNING id",
                         (ev_id, cid, nm, g, g - ph, ph, len(hs), f"t{ev_id}-{cid}")).fetchone()[0]
        for i, v in enumerate(hs):
            c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes) VALUES (?,?,?)", (rid_, i + 1, v))
for _n in dir(db):
    if _n.startswith("_ensure_") and callable(getattr(db, _n)):
        try:
            getattr(db, _n)(c)
        except Exception:
            pass
c.commit()
course = [{"hole": h, "par": PARS[h - 1], "stroke_index": SI[h - 1], "yardage": YD[h - 1]} for h in range(1, 10)]
rid = se.create_round(900, 9, label="s9.26 Olympia Hills", course_holes=course)["round_id"]
gid = se.upsert_group(rid, 4, label="Hole 3 | 5:00 PM", start_hole=3,
                      players=[{"customer_id": cid, "display_name": f"{fn} {ln}", "playing_handicap": ph, "seat": i + 1}
                               for i, (cid, fn, ln, ph) in enumerate(GROUP)])["group_id"]
db.set_app_setting("score_entry_live", "1")
db.set_app_setting("score_entry_events", "[900]")
TOK = se.make_group_token(gid)

print("API tier")
with appmod.app.test_client() as tc:
    r = tc.get("/api/events-leaderboard")
    check("anonymous: 200, every event (member tier since v2.523.4, #1146-1)", r.status_code == 200 and len(r.get_json()["events"]) == 2, str(r.status_code))
    r = tc.get(f"/api/events-leaderboard?t={TOK}")
    check("scorer's link: 200 and his event only", r.status_code == 200 and [e["id"] for e in r.get_json()["events"]] == [900], (r.status_code, r.get_data()[:120]))
    r = tc.get(f"/api/events-leaderboard/event?name=s9.26%20Olympia%20Hills&t={TOK}")
    check("scorer's link: his board 200, carries event.id", r.status_code == 200 and r.get_json()["event"]["id"] == 900, str(r.status_code))
    check("his board holds the money (scores out)", r.get_json()["money_visible"] is False)
    r = tc.get(f"/api/events-leaderboard/event?name=s9.25%20Canyon%20Springs&t={TOK}")
    check("scorer's link: another event's board 403", r.status_code == 403, str(r.status_code))
    r = tc.get("/api/events-leaderboard/event?name=s9.25%20Canyon%20Springs&t=not-a-link")
    check("bad link: read as the public member tier (200), never narrowed", r.status_code == 200, str(r.status_code))
    r = tc.get(f"/member/score/board?t={TOK}")
    check("board page renders for the link (SOLO_EVENT + SOLO_T)", r.status_code == 200 and b"window.SOLO_EVENT" in r.data and b"se-toggle" in r.data and b"evlb-solo-bar" in r.data, str(r.status_code))
    check("board page shows no tabs, no CTA, no chips", b'top-tabs-wrap" hidden' in r.data and b'contest-cta-row" hidden' in r.data)
    r = tc.get("/member/score/board?t=bad")
    check("bad link: the score page (explains itself), not a 500", r.status_code == 200 and b"se-app" in r.data, str(r.status_code))
    r = tc.get("/member/contests")
    check("the member Leaderboard page renders the Events tab, open to members (v2.523.4)", r.status_code == 200 and b'<button class="top-tab" data-top="events">' in r.data and b'evlb-official' in r.data)
    tc.post("/api/auth/login", json={"pin": "5151"})
    r = tc.get("/api/events-leaderboard")
    check("manager: 200, every event", r.status_code == 200 and len(r.get_json()["events"]) == 2, str(r.status_code))
    tc.post("/api/auth/logout")
    with tc.session_transaction() as s:
        s["role"] = "member"
    r = tc.get("/api/events-leaderboard")
    check("member session without a link: 200, every event (v2.523.4)", r.status_code == 200 and len(r.get_json()["events"]) == 2, str(r.status_code))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP screen checks: playwright not installed")
    sync_playwright = None
CHROME = next((p for p in ("/opt/pw-browsers/chromium",) if os.path.exists(p)), None)
if sync_playwright and CHROME:
    PORT = 5191
    threading.Thread(target=lambda: appmod.app.run(port=PORT, use_reloader=False), daemon=True).start()
    time.sleep(1.5)
    B = f"http://127.0.0.1:{PORT}"
    print("Screen")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--headless=new"])
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.goto(f"{B}/member/score?t={TOK}"); pg.wait_for_timeout(900)
        pg.click("[data-act=gate-score]"); pg.click("text=Kerry Niester"); pg.wait_for_timeout(900)
        dev = pg.evaluate("JSON.parse(localStorage.getItem('se_device'))")
        se.write_scores(gid, dev, 9101, [{"op_id": f"t{cid}-{h}", "customer_id": cid, "hole": h, "gross": PARS[h - 1]} for h in (3, 4) for cid, *_ in GROUP])
        pg.evaluate("localStorage.removeItem('se_hole_' + new URLSearchParams(location.search).get('t').slice(0,24))")
        pg.reload(); pg.wait_for_timeout(1200)
        # holes 3-4 were scored behind the page's back: an unanswered CTP hole
        # among them is asked first (Kerry 10/8: it can't be skipped)
        asked = 0
        while pg.locator("button[data-act=ctp][data-cid='']").count() and asked < 4:
            asked += 1; pg.click("button[data-act=ctp][data-cid='']"); pg.wait_for_timeout(700)
        tg = lambda: pg.evaluate("[...document.querySelectorAll('#se-toggle a')].map(a => a.className + '|' + a.innerText.replace(/\\n/g, ' '))")
        check("hole screen opens on Hole 5 with the toggle, Scoring active", pg.inner_text(".se-h1") == "Hole 5" and tg() == ["active|SCORING", "|LEADERBOARD"], str(tg()))
        hdr = pg.evaluate("document.querySelector('header.shell-nav').getBoundingClientRect().bottom")
        tgl = pg.evaluate("document.getElementById('se-toggle').getBoundingClientRect()")
        check("toggle sits under the mark, above the hole", tgl["top"] >= hdr and tgl["bottom"] <= pg.evaluate("document.querySelector('.se-h1').getBoundingClientRect().top"), str((hdr, tgl)))
        check("the hole screen still fits one screen", pg.evaluate("document.documentElement.scrollHeight <= window.innerHeight + 1"), str(pg.evaluate("[document.documentElement.scrollHeight, window.innerHeight]")))
        check("no Back-to-scoring bar anywhere", pg.evaluate("!document.querySelector('.se-backbar')"))
        pg.click("#se-tg-board"); pg.wait_for_timeout(2500)
        check("LEADERBOARD lands on /member/score/board for his link", pg.url.startswith(f"{B}/member/score/board?t="), pg.url)
        check("toggle: Leaderboard active, Scoring reads Hole 5", tg() == ["|SCORING Hole 5", "active|LEADERBOARD"], str(tg()))
        check("one event only, opened, with the event bar", pg.evaluate("document.querySelectorAll('details.evlb-ev').length") == 1
              and pg.evaluate("document.querySelectorAll('details.evlb-ev[open]').length") == 1
              and pg.inner_text(".evlb-solo-bar").replace("\n", " ") == "s9.26 Olympia Hills IN PLAY", pg.inner_text(".evlb-solo-bar"))
        check("no chapter chips, no eyebrow card, no summary on the scorer's board", pg.evaluate("!document.querySelector('details.evlb-ev > summary').offsetParent") and pg.evaluate("!document.querySelector('#evlb-chips').offsetParent"))
        seg = pg.evaluate("(() => { const s = document.querySelector('.evlb-seg-sub'); const r = s.getBoundingClientRect(); return {w: s.scrollWidth, cw: s.clientWidth, right: r.right, rows: new Set([...s.children].map(b => Math.round(b.getBoundingClientRect().top))).size, n: s.children.length}; })()")
        check("seven game tabs fit the phone width in two rows", seg["n"] == 7 and seg["rows"] == 2 and seg["w"] <= seg["cw"] and seg["right"] <= 390, str(seg))
        check("Won column hidden while scores are out (every board + proxies)", pg.evaluate("[...document.querySelectorAll('table.evlb-holes')].every(t => t.classList.contains('no-won') && getComputedStyle(t.querySelector('th.won')).display === 'none')")
              and pg.evaluate("[...document.querySelectorAll('table.evlb-prox')].every(t => t.classList.contains('no-won'))"))
        rows = pg.evaluate("""[...document.querySelectorAll('table.evlb-ovr[data-board] tbody td.nm')].map(td => {
            const r = td.getBoundingClientRect(); const d = td.querySelector('.evlb-tee-dot');
            const dr = d ? d.getBoundingClientRect() : null;
            return {h: r.height, name: td.innerText.trim(), dotIn: !d || (dr.top >= r.top && dr.bottom <= r.bottom && dr.right <= r.right + 0.5), lines: Math.round(r.height / parseFloat(getComputedStyle(td).lineHeight))};
        })""")
        check("every name cell is one row high with its tee dot inside it", rows and all(x["lines"] <= 1 and x["dotIn"] for x in rows), str([x for x in rows if not (x["lines"] <= 1 and x["dotIn"])][:3]))
        check("the long name is there, unwrapped", any("VANDERSCHOONHOVEN" in x["name"] for x in rows))
        # Kerry 2026-10-02: "pin to the top as a bar under the header and
        # allow scrolling underneath it. I want it to always be visible."
        # (a six-player board can be shorter than the screen: give the page
        # something to scroll so the pin itself is what gets tested)
        pg.evaluate("document.body.style.minHeight = '3000px'; window.scrollTo(0, 900)"); pg.wait_for_timeout(400)
        pin = pg.evaluate("""(() => { const h = document.querySelector('header.shell-nav').getBoundingClientRect();
            const t = document.getElementById('se-toggle').getBoundingClientRect();
            const under = document.elementFromPoint(195, t.top + t.height / 2);
            return {scrollY: window.scrollY, hdrBottom: h.bottom, top: t.top, bottom: t.bottom, opaque: getComputedStyle(document.getElementById('se-toggle')).backgroundColor,
                    onTop: !!under && !!under.closest('#se-toggle')}; })()""")
        check("scrolled to the bottom: the toggle stays pinned right under the header, on top of the page", pin["scrollY"] > 100 and abs(pin["top"] - pin["hdrBottom"]) <= 1 and pin["bottom"] > 0 and pin["onTop"] and pin["opaque"] not in ("rgba(0, 0, 0, 0)", "transparent"), str(pin))
        pg.evaluate("window.scrollTo(0, 0)"); pg.wait_for_timeout(200)
        pg.click("#se-tg-score"); pg.wait_for_timeout(1500)
        check("SCORING returns to Hole 5, toggle back to Scoring", pg.url.startswith(f"{B}/member/score?t=") and pg.inner_text(".se-h1") == "Hole 5" and tg()[0] == "active|SCORING", str((pg.url, tg())))
        pg.evaluate("() => { const s = JSON.parse(localStorage.getItem('se_live')); s.queued = 2; s.hole = 7; localStorage.setItem('se_live', JSON.stringify(s)); }")
        pg.goto(f"{B}/member/score/board?t={TOK}"); pg.wait_for_timeout(2000)
        check("holes waiting to sync: Scoring segment amber with the count", tg()[0] == "amber|SCORING Hole 7 · 2 to sync", str(tg()))
        pg.goto(f"{B}/member/contests"); pg.wait_for_timeout(800)
        check("no toggle on the member Leaderboard page", pg.evaluate("!document.querySelector('#se-toggle') || document.querySelector('#se-toggle').hidden"))
        # a COMPLETE event shows Won again (manager view of the shared board)
        pg.evaluate("fetch('/api/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({pin:'4242'})})"); pg.wait_for_timeout(500)
        pg.goto(f"{B}/contests#tab=events"); pg.wait_for_timeout(2500)
        done_el = pg.query_selector('details.evlb-ev[data-ev="s9.25 Canyon Springs"] summary')
        if done_el:
            done_el.click(); pg.wait_for_timeout(2500)
        check("a complete event's board shows the Won column", pg.evaluate("""(() => { const t = document.querySelector('details.evlb-ev[data-ev="s9.25 Canyon Springs"] table.evlb-holes'); return !!t && !t.classList.contains('no-won') && getComputedStyle(t.querySelector('th.won')).display !== 'none'; })()"""))
        # MEMBER RELEASE (v2.523.4, Kerry #1146-1): /member/results lands on
        # the Events tab with the Unofficial line, every event listed.
        mp = ctx.new_page()
        mp.goto(f"{B}/member/results"); mp.wait_for_timeout(2500)
        landed = mp.evaluate("""[!document.getElementById('section-events').classList.contains('section-hidden'),
            (document.querySelector('.top-tab.active') || {}).dataset?.top,
            document.querySelectorAll('#evlb-list details.evlb-ev').length,
            (document.getElementById('evlb-official') || {}).innerText || '']""")
        check("/member/results lands on Events, every event listed, Unofficial line shown",
              landed[0] and landed[1] == "events" and landed[2] == 2 and "official scorer" in landed[3], str(landed))
        mp.screenshot(path=os.path.join(tempfile.gettempdir(), "member-results-390.png"))
        b.close()
else:
    print("SKIP screen checks: no Chromium")

print("FAILED: " + ", ".join(FAILURES) if FAILURES else "ALL PASS")
sys.exit(1 if FAILURES else 0)
