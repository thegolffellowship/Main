"""SCREENS STAY CURRENT BY THEMSELVES (Kerry 2026-10-26: "When we make an
update to anything, the screenshots are set to update too, correct? If not,
that's an absolute requirement.").

A catalogued step may carry a `capture` recipe (catalog.json):
- {"url": "/member/handicaps"}  a public page, loaded from the site itself;
- {"render": "<name>"}           HTML from the SAME code that sends it
                                  (RENDERS below), never a copy.
`capture_all()` takes every recipe on desktop / tablet / mobile with
headless Chromium (print_pack._chromium_executable) and writes
`<name>.png` / `<name>.tablet.png` / `<name>.desktop.png` into a folder:
- production: `<data dir>/screens_live/<sequence id>/` (job `screens_capture`
  after each deploy and nightly); the Screens page shows these first;
- the repo: `tools/screens_refresh.py` writes into the sequence's own folder
  under docs/claude/screenshots and refreshes its `watch_hash`, which
  `test_screens.py` checks: a change to a watched file with no refresh fails
  the tests.

Nothing here sends, records or writes a member row. Renders use the staff
preview person (invitations.PREVIEW_CID_KEY) and PREVIEW links, which
record nothing; RSVP pages are fetched in-process on preview tokens.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DEVICES = {"mobile": (390, 844, 2), "tablet": (820, 1180, 1), "desktop": (1280, 900, 1)}
EMAIL_DEVICES = {"mobile": (420, 600, 2), "tablet": (820, 1180, 1), "desktop": (1280, 800, 1)}
VERSION_KEY = "screens_capture_version"
REPO = Path(__file__).resolve().parent.parent


def live_root() -> Path:
    from email_parser import database as db
    return Path(db.DB_PATH).resolve().parent / "screens_live"


def _watched_bytes(entry: str) -> bytes:
    """A watched file's bytes, or with "path::name" just that top-level
    function's source (app.py changes all day; one route does not)."""
    rel, _, fn = entry.partition("::")
    p = REPO / rel
    if not p.is_file():
        return b"<missing>"
    if not fn:
        return p.read_bytes()
    text = p.read_text()
    m = re.search(rf"^def {re.escape(fn)}\(.*?(?=^(?:def |class |@app\.route|# ----)|\Z)", text,
                  re.S | re.M)
    return m.group(0).encode() if m else b"<missing function>"


def watch_hash(paths) -> str:
    """One hash over the watched files (or functions), repo-relative."""
    h = hashlib.sha256()
    for entry in sorted(paths or []):
        h.update(entry.encode())
        h.update(_watched_bytes(entry))
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------
# Context: the event and person a render is made for
# --------------------------------------------------------------------------

# Only tools/screens_refresh.py (a throwaway database) may invent an event.
ALLOW_DEMO = False


def _context(db_path=None) -> dict | None:
    """The next upcoming active event (and one with a usable store link)
    plus the staff preview person. Production: real rows. A sandbox with
    no events gets a demo event so the repo refresh still renders."""
    from email_parser import database as db
    from email_parser import invitations as inv
    from email_parser.event_links import event_url_for_message
    from email_parser.timezone_utils import today_central_str
    today = today_central_str()
    evs = sorted((e for e in db.get_all_events(db_path=db_path)
                  if (e.get("event_date") or "") >= today and (e.get("status") or "active") == "active"
                  and e.get("chapter")), key=lambda e: e.get("event_date") or "")
    if not evs:
        if not ALLOW_DEMO:
            return None          # production with nothing upcoming: renders wait
        _seed_demo(db_path)
        return _context(db_path)
    linked = next((e for e in evs if event_url_for_message(e)[0]), evs[0])
    pcid = int(inv._setting(inv.PREVIEW_CID_KEY, db_path) or inv.DEFAULT_PREVIEW_CID)
    conn = db.get_connection(db_path)
    try:
        r = conn.execute("SELECT first_name FROM customers WHERE customer_id = ?", (pcid,)).fetchone()
        ev = inv._event(conn, int(evs[0]["id"]))
        lev = inv._event(conn, int(linked["id"]))
    finally:
        conn.close()
    return {"event": ev, "linked": lev, "cid": pcid, "first": (r[0] if r else "") or "Kerry"}


def _seed_demo(db_path=None) -> None:
    from email_parser import database as db
    t = date.today() + timedelta(days=28)
    d = (t + timedelta(days=(1 - t.weekday()) % 7)).isoformat()   # a Tuesday, like a real nine
    with db._connect(db_path) as c:
        c.execute("INSERT INTO events (item_name, event_date, chapter, status, format, start_type, start_time, "
                  "course, registration_url, registration_url_status) VALUES ('s9.99 Silverhorn', ?, "
                  "'San Antonio', 'active', '9-hole', 'Shotgun', '16:30', 'Silverhorn Golf Club', "
                  "'https://www.thegolffellowship.com/product-page/s9-99-silverhorn', 'verified')", (d,))
        c.execute("INSERT OR IGNORE INTO customers (customer_id, first_name, last_name) VALUES (18, 'Kerry', 'Niester')")
        c.commit()


# --------------------------------------------------------------------------
# Renders: the same builders the Tracker sends with
# --------------------------------------------------------------------------

def _rsvp_page(ctx, action: str, method: str = "GET", browser: bool = True, path_tail: str = "",
               form=None) -> str:
    import app as _app
    from email_parser import invitations as inv
    ev = ctx["event"]
    tok = inv.make_token(ctx["cid"], int(ev["id"]), action,
                         date.fromisoformat(str(ev["event_date"])[:10]), preview=True)
    cl = _app.app.test_client()
    if browser:
        cl.environ_base.update({
            "HTTP_USER_AGENT": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
            "HTTP_ACCEPT_LANGUAGE": "en-US,en;q=0.9"})
    url = f"/rsvp/{tok}{path_tail}"
    r = cl.post(url, data=form or {}) if method == "POST" else cl.get(url)
    return r.get_data(as_text=True)


def _confirm_page(ctx) -> str:
    import app as _app
    from email_parser import invitations as inv
    ev = ctx["event"]
    tok = inv.make_token(ctx["cid"], int(ev["id"]), "in",
                         date.fromisoformat(str(ev["event_date"])[:10]), preview=True)
    with _app.app.test_request_context():
        return _app._rsvp_confirm_page(inv.describe_token(tok))


def _r_invite(ctx, kind):
    from email_parser import invitations as inv
    return inv.build_message(ctx["event"], {"customer_id": ctx["cid"], "first_name": ctx["first"]},
                             kind, preview=True)["html"]


def _r_payment(ctx):
    from email_parser import payment_reminder as pr
    return pr.preview(int(ctx["linked"]["id"]), ctx["cid"])["html"]


def _r_deadline(ctx, kind):
    from email_parser import rsvp_deadline as rd
    return rd.build(ctx["linked"], {"first_name": ctx["first"], "customer_id": ctx["cid"],
                                    "preview": True}, kind)["html"]


# NO-SHOW (Kerry 9/30 #1021, built 10/26): the real /member/score page and
# the real card JSON (score_entry.get_group_card) from a round seeded in a
# THROWAWAY database of its own (never the Tracker's, production included),
# with the page's fetch answered from that card and its taps replayed.
_NS_CACHE: dict = {}


def _ns_seed() -> dict:
    if _NS_CACHE:
        return _NS_CACHE
    import contextlib, io, tempfile
    from email_parser import database as db
    from email_parser import score_entry as se
    from email_parser import no_show_notice as nsn
    path = tempfile.mktemp(suffix=".screens-noshow.db")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        db.init_db(path)
    with db._connect(path) as c:
        for cid, fn, ln in [(401, "Sam", "Keller"), (402, "Mike", "Ruiz"), (403, "Ned", "Owens"), (404, "Al", "Brandt")]:
            c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, ?)", (cid, fn, ln))
        d = (date.today() + timedelta(days=1)).isoformat()
        c.execute("INSERT INTO events (id, item_name, event_date, chapter, course, status, format) VALUES "
                  "(9901, 's9.99 Silverhorn', ?, 'San Antonio', 'Silverhorn Golf Club', 'active', '9-hole')", (d,))
        c.commit()
    holes = [{"hole": h, "par": pr, "stroke_index": si, "yardage": y} for h, pr, si, y in
             [(1, 4, 5, 382), (2, 3, 9, 164), (3, 5, 1, 512), (4, 4, 3, 401), (5, 4, 7, 356),
              (6, 3, 8, 175), (7, 4, 2, 418), (8, 5, 4, 498), (9, 4, 6, 390)]]
    rid = se.create_round(9901, 9, round_date=d, label="s9.99", course_holes=holes, db_path=path)["round_id"]
    gid = se.upsert_group(rid, 1, players=[
        {"customer_id": 401, "display_name": "Sam Keller", "playing_handicap": 6},
        {"customer_id": 402, "display_name": "Mike Ruiz", "playing_handicap": 11},
        {"customer_id": 403, "display_name": "Ned Owens", "playing_handicap": 9},
        {"customer_id": 404, "display_name": "Al Brandt", "playing_handicap": 14}], db_path=path)["group_id"]
    se.claim_group(gid, "screens-demo", 401, db_path=path)
    before = se.get_group_card(gid, "screens-demo", db_path=path)
    se.mark_player_missing(gid, "screens-demo", 403, "absent", hole=1, entered_by=401, db_path=path)
    n = 0
    ops = []
    for cid, row in ((401, (5, 3, 5)), (402, (4, 4, 6)), (404, (6, 3, 5))):
        for h, g in zip((1, 2, 3), row):
            n += 1
            ops.append({"op_id": f"scr{n}", "hole": h, "gross": g, "customer_id": cid})
    se.write_scores(gid, "screens-demo", 401, ops, db_path=path)
    for h in (1, 2, 3):          # the group answered any CTP / longest-putt question
        se.claim_ctp(gid, "screens-demo", h, None, db_path=path)
    after = se.get_group_card(gid, "screens-demo", db_path=path)
    notice = nsn.build(9901, db_path=path)
    _NS_CACHE.update(before=before, after=after, notice=notice, path=path)
    return _NS_CACHE


def _r_no_show(ctx, which: str, clicks=(), hole=None) -> str:
    import app as _app
    data = _ns_seed()
    card = data["after" if which == "after" else "before"]
    page = _app.app.test_client().get("/member/score?t=screens").get_data(as_text=True)
    mem = {"se_device": json.dumps("screens-demo"), "se_who_screens": "401", "se_gate_screens": "true"}
    if hole is not None:
        mem["se_hole_screens"] = str(hole)
    stub = ("<script>(function(){var G=URLSearchParams.prototype.get;URLSearchParams.prototype.get="
            "function(k){var v=G.call(this,k);return (k==='t'&&!v)?'screens':v};"
            "var M=" + json.dumps(mem) + ";"
            "var S={getItem:function(k){return k in M?M[k]:null},setItem:function(k,v){M[k]=String(v)},"
            "removeItem:function(k){delete M[k]},clear:function(){M={}},key:function(){return null},length:0};"
            "try{Object.defineProperty(window,'localStorage',{value:S,configurable:true})}catch(e){}"
            "try{Object.defineProperty(window,'sessionStorage',{value:S,configurable:true})}catch(e){}"
            "var C=" + json.dumps(card, default=str).replace("</", "<\\/") + ";"
            "var J=function(o){return Promise.resolve(new Response(JSON.stringify(o),{status:200,"
            "headers:{'Content-Type':'application/json'}}))};"
            "window.fetch=function(u){u=String(u);if(u.indexOf('/api/score-entry/card')>=0)return J(C);"
            "if(u.indexOf('/api/player-photos')>=0)return J({h:{},t:{}});return J({})};"
            "var K=" + json.dumps(list(clicks)) + ";"
            "window.addEventListener('load',function(){setTimeout(function(){K.forEach(function(q){"
            "var b=document.querySelector(q);if(b)b.click()})},120)});})();</script>")
    return page.replace("<head>", "<head>" + stub, 1)


def _r_no_show_notice(ctx) -> str:
    b = _ns_seed()["notice"]
    return ('<div style="font-family:\'Helvetica Neue\',Helvetica,Arial,sans-serif;color:#1B1B1B;'
            'padding:16px;max-width:560px;font-size:15px;line-height:1.5;">' + b["html"] + "</div>")


RENDERS = {
    "invitation_email": lambda c: _r_invite(c, "invite"),
    "lastcall_email": lambda c: _r_invite(c, "lastcall"),
    "rsvp_one_more_tap": lambda c: _confirm_page(c),
    "rsvp_cant_make_it": lambda c: _rsvp_page(c, "out", "POST"),
    "rsvp_reason_thanks": lambda c: _rsvp_page(c, "out", "POST", path_tail="/reason", form={"r": "Schedule"}),
    "rsvp_remove_confirm": lambda c: _rsvp_page(c, "unsub"),
    "rsvp_remove_done": lambda c: _rsvp_page(c, "unsub", "POST"),
    "payment_reminder": _r_payment,
    "rsvp_deadline_warn": lambda c: _r_deadline(c, "warn"),
    "rsvp_deadline_release": lambda c: _r_deadline(c, "release"),
    "no_show_hole": lambda c: _r_no_show(c, "before"),
    "no_show_who": lambda c: _r_no_show(c, "before", ['[data-act="missing"]']),
    "no_show_ask": lambda c: _r_no_show(c, "before", ['[data-act="missing"]', '[data-act="mwho"][data-cid="403"]']),
    "no_show_absent": lambda c: _r_no_show(c, "after", hole=4),
    "no_show_course_notice": _r_no_show_notice,
}
EMAIL_RENDERS = {"invitation_email", "lastcall_email", "payment_reminder", "no_show_course_notice",
                 "rsvp_deadline_warn", "rsvp_deadline_release"}


# --------------------------------------------------------------------------
# Capture
# --------------------------------------------------------------------------

def recipes(cat: dict | None = None, only: str = "") -> list:
    """[(sequence, step)] for every step with a capture recipe."""
    from email_parser import screens as scr
    cat = cat or scr._load()
    return [(s, st) for s in cat.get("sequences", []) if not only or s["id"] == only
            for st in s.get("steps", []) if st.get("capture")]


def capture_all(out_for, base_url: str, only: str = "", db_path=None) -> dict:
    """Take every recipe on three devices. out_for(sequence) -> folder."""
    from email_parser.print_pack import _chromium_executable
    import concurrent.futures
    exe = _chromium_executable()
    todo = recipes(only=only)
    ctx = _context(db_path) if any("render" in st["capture"] for _, st in todo) else None
    jobs, errors = [], []
    for s, st in todo:
        cap = st["capture"]
        try:
            if "render" in cap and ctx is None:
                errors.append({"sequence": s["id"], "step": st["file"], "error": "no upcoming event to render"})
                continue
            if "render" in cap:
                html = RENDERS[cap["render"]](ctx)
                html = re.sub(r"""(["'(])/static/""", r"\1" + base_url.rstrip("/") + "/static/", html)
                jobs.append((s, st, {"html": html, "_out": str(out_for(s))}, cap["render"] in EMAIL_RENDERS))
            elif "url" in cap:
                jobs.append((s, st, {"url": base_url.rstrip("/") + cap["url"], "_out": str(out_for(s))}, False))
        except Exception as e:
            logger.exception("screens capture: render failed for %s/%s", s["id"], st["file"])
            errors.append({"sequence": s["id"], "step": st["file"], "error": f"{type(e).__name__}: {e}"})

    def _run():
        from playwright.sync_api import sync_playwright
        if not exe:
            raise RuntimeError("no Chromium executable on this deploy")
        done = []
        with sync_playwright() as pw:
            # A sandbox reaches the web (the Tracker's /static, Google Fonts)
            # only through its HTTPS proxy; production sets none.
            _px = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
            browser = pw.chromium.launch(executable_path=exe, headless=False,
                                         proxy={"server": _px} if _px else None,
                                         args=["--headless=new", "--no-sandbox", "--disable-gpu",
                                               "--disable-dev-shm-usage"])
            try:
                for s, st, src, email in jobs:
                    folder = Path(out_for(s))
                    folder.mkdir(parents=True, exist_ok=True)
                    base = os.path.splitext(st["file"])[0]
                    for dev, (w, h, scale) in (EMAIL_DEVICES if email else DEVICES).items():
                        ctx_b = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=scale,
                                                    is_mobile=(dev == "mobile" and not email))
                        ctx_b.add_init_script("try{sessionStorage.setItem('tgf_session_active','1')}catch(e){}")
                        page = ctx_b.new_page()
                        try:
                            if "html" in src:
                                page.set_content(src["html"], wait_until="load")
                                page.wait_for_timeout(300)
                            else:
                                page.goto(src["url"], wait_until="domcontentloaded", timeout=45000)
                                page.wait_for_timeout(5000)
                            page.evaluate("document.fonts.ready")
                            # The live Tracker's fonts or no picture (Kerry 10/26).
                            if page.evaluate("[...document.querySelectorAll('link[href*=\"fonts.googleapis\"]')].length > 0"
                                             " && !document.fonts.check('700 16px Bitter')"):
                                raise RuntimeError("Bitter did not load")
                            name = f"{base}.png" if dev == "mobile" else f"{base}.{dev}.png"
                            page.screenshot(path=str(folder / name), full_page=(email and dev == "mobile"))
                            done.append(f"{s['id']}/{name}")
                        except Exception as e:
                            errors.append({"sequence": s["id"], "step": st["file"], "device": dev,
                                           "error": f"{type(e).__name__}: {str(e)[:200]}"})
                        finally:
                            ctx_b.close()
            finally:
                browser.close()
        return done
    try:
        import playwright.sync_api  # noqa: F401  (production has it; print_pack uses it)
    except ImportError:
        done = _run_node(jobs, errors)
        return {"captured": done, "errors": errors}
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        done = ex.submit(_run).result(timeout=900)
    return {"captured": done, "errors": errors}


def _run_node(jobs, errors) -> list:
    """The same captures through tools/screens_capture.js (Node Playwright),
    for a sandbox without Python Playwright."""
    import subprocess, tempfile
    tmp = Path(tempfile.mkdtemp(prefix="screens-"))
    flat = []
    for n, (s, st, src, email) in enumerate(jobs):
        folder = Path(src.get("_out") or "")
        base = os.path.splitext(st["file"])[0]
        html_file = None
        if "html" in src:
            html_file = tmp / f"{n}.html"
            html_file.write_text(src["html"])
        for dev, (w, h, scale) in (EMAIL_DEVICES if email else DEVICES).items():
            name = f"{base}.png" if dev == "mobile" else f"{base}.{dev}.png"
            flat.append({"w": w, "h": h, "scale": scale, "mobile": dev == "mobile" and not email,
                         "full": bool(email and dev == "mobile"), "url": src.get("url"),
                         "html_file": str(html_file) if html_file else None,
                         "path": str(folder / name), "name": f"{s['id']}/{name}"})
    jf = tmp / "jobs.json"
    jf.write_text(json.dumps(flat))
    r = subprocess.run(["node", str(REPO / "tools/screens_capture.js"), str(jf)], capture_output=True,
                       text=True, timeout=900, cwd=str(tmp))
    try:
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        errors.append({"error": f"node runner failed: {r.stderr[-300:]}"})
        return []
    errors.extend(res.get("errors") or [])
    return res.get("done") or []


def capture_live(force: bool = False, db_path=None) -> dict:
    """Production: every recipe into the volume's screens_live/<sequence>/,
    once per deployed version unless force (the nightly run forces)."""
    from email_parser import database as db
    from email_parser.score_entry import _base_url
    ver = _deployed_version()
    if not force and ver and db.get_app_setting(VERSION_KEY, db_path=db_path) == ver:
        return {"skipped": f"already captured for v{ver}"}
    root = live_root()
    res = capture_all(lambda s: root / s["id"], _base_url(), db_path=db_path)
    if not res.get("error"):
        meta = {"version": ver, "at": _now_label(), "errors": res["errors"]}
        root.mkdir(parents=True, exist_ok=True)
        (root / "_meta.json").write_text(json.dumps(meta))
        if ver:
            db.set_app_setting(VERSION_KEY, ver, db_path=db_path)
        db.log_agent_action("screens-capture", "screens_capture",
                            f"v{ver}: {len(res['captured'])} shots, {len(res['errors'])} errors")
    return res


def _deployed_version() -> str:
    try:
        m = re.search(r'TGF_VERSION\s*=\s*"([^"]+)"', (REPO / "static/js/version.js").read_text())
        return m.group(1) if m else ""
    except OSError:
        return ""


def _now_label() -> str:
    from email_parser.timezone_utils import now_central
    return now_central().strftime("%Y-%m-%d %H:%M CT")


def live_meta() -> dict:
    try:
        return json.loads((live_root() / "_meta.json").read_text())
    except (OSError, ValueError):
        return {}
