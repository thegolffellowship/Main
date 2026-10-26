"""SCREENS STAY CURRENT BY THEMSELVES (Kerry 2026-10-26: "When we make an
update to anything, the screenshots are set to update too, correct? If not,
that's an absolute requirement.").

A catalogued step may carry a `capture` recipe (catalog.json):
- {"url": "/member/handicaps"}  a public page, loaded from the site itself;
- {"render": "<name>"}           HTML from the SAME code that sends it
                                  (RENDERS below), never a copy;
- {"demo": "<scenario>", "path": "/member/score?t={t}"}  a live page served
                                  by the Tracker's own code from a THROWAWAY
                                  database with demo people
                                  (tools/screens_demo.py, run as its own
                                  process with every credential stripped),
                                  for pages that need an event, a round or a
                                  link: score entry, the member tee sheet.
                                  Never production data.
Any recipe may add "click": [css selectors] (each first match is tapped, in
order, before the picture) and "wait" (ms after the clicks).
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
}
EMAIL_RENDERS = {"invitation_email", "lastcall_email", "payment_reminder",
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


def capture_all(out_for, base_url: str, only: str = "", db_path=None, demo: dict | None = None) -> dict:
    """Take every recipe on three devices. out_for(sequence) -> folder.
    `demo` = {"base": local server, "vars": {...}} runs ONLY the demo
    recipes (tools/screens_demo.py); without it demo recipes are left for
    that runner."""
    from email_parser.print_pack import _chromium_executable
    import concurrent.futures
    exe = _chromium_executable()
    todo = [(s, st) for s, st in recipes(only=only) if bool(demo) == ("demo" in st["capture"])]
    ctx = _context(db_path) if any("render" in st["capture"] for _, st in todo) else None
    jobs, errors = [], []
    for s, st in todo:
        cap = st["capture"]
        acts = {"click": list(cap.get("click") or []), "wait": int(cap.get("wait") or 2500)}
        try:
            if "demo" in cap:
                path = cap.get("path", "/").format(**(demo.get("vars") or {}))
                jobs.append((s, st, {"url": demo["base"].rstrip("/") + path, "_out": str(out_for(s)), **acts}, False))
                continue
            if "render" in cap and ctx is None:
                errors.append({"sequence": s["id"], "step": st["file"], "error": "no upcoming event to render"})
                continue
            if "render" in cap:
                html = RENDERS[cap["render"]](ctx)
                html = re.sub(r"""(["'(])/static/""", r"\1" + base_url.rstrip("/") + "/static/", html)
                jobs.append((s, st, {"html": html, "_out": str(out_for(s))}, cap["render"] in EMAIL_RENDERS))
            elif "url" in cap:
                jobs.append((s, st, {"url": base_url.rstrip("/") + cap["url"], "_out": str(out_for(s)), **acts}, False))
        except Exception as e:
            logger.exception("screens capture: render failed for %s/%s", s["id"], st["file"])
            errors.append({"sequence": s["id"], "step": st["file"], "error": f"{type(e).__name__}: {e}"})

    def _run():
        from playwright.sync_api import sync_playwright
        if not exe:
            raise RuntimeError("no Chromium executable on this deploy")
        done = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=exe, headless=False,
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
                                for sel in src.get("click") or []:
                                    page.locator(sel).first.click(timeout=8000)
                                    page.wait_for_timeout(src.get("wait") or 2500)
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
    if not jobs:
        return {"captured": [], "errors": errors}
    try:
        import playwright.sync_api  # noqa: F401  (production has it; print_pack uses it)
        node = not exe
    except ImportError:
        node = True
    if node:
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
                         "click": src.get("click") or [], "wait": src.get("wait") or 2500,
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
    try:
        res = capture_all(lambda s: root / s["id"], _base_url(), db_path=db_path)
        dres = capture_demos(str(root), live=True)
        res["captured"] = list(res.get("captured") or []) + list(dres.get("captured") or [])
        res["errors"] = list(res.get("errors") or []) + list(dres.get("errors") or [])
        if dres.get("error"):
            res["errors"].append({"error": f"demo runner: {dres['error']}"})
    except Exception as e:
        logger.exception("screens capture failed")
        res = {"error": f"{type(e).__name__}: {str(e)[:300]}", "captured": [], "errors": []}
    if not res.get("error"):
        meta = {"version": ver, "at": _now_label(), "errors": res["errors"]}
        root.mkdir(parents=True, exist_ok=True)
        (root / "_meta.json").write_text(json.dumps(meta))
        if ver:
            db.set_app_setting(VERSION_KEY, ver, db_path=db_path)
        db.log_agent_action("screens-capture", "screens_capture",
                            f"v{ver}: {len(res['captured'])} shots, {len(res['errors'])} errors", db_path=db_path)
    # A missed or partial capture must show where the lanes look (Kerry 10/26:
    # screens mirror what's live); before this a failure logged nothing.
    if res.get("error") or res.get("errors"):
        first = res.get("error") or json.dumps((res.get("errors") or [{}])[0])[:300]
        try:
            db.log_agent_action("screens-capture", "screens_capture_failed",
                                f"v{ver}: {'FAILED' if res.get('error') else 'partial'}, "
                                f"{len(res.get('errors') or [])} errors; first: {first}", db_path=db_path)
        except Exception:
            logger.exception("screens capture: could not log the failure")
    return res


# Credentials a demo runner must never hold: it runs the Tracker's code on a
# throwaway database, and nothing in it may reach mail, money or a member.
_SECRET_PREFIXES = ("AZURE_", "EMAIL_", "ANTHROPIC", "HUBSPOT", "BREVO", "META_", "TWILIO",
                    "LITESTREAM", "PAYPAL", "STRIPE", "GODADDY", "RAILWAY", "OPENAI", "MCP_",
                    "COO_EMAIL", "RSVP_EMAIL", "VENMO", "GG_", "GOLF_GENIUS")


def capture_demos(out_root: str, live: bool, only: str = "", timeout: int = 900) -> dict:
    """Run tools/screens_demo.py as its OWN process on a throwaway database
    with every credential stripped. live=True writes <out_root>/<sequence>/
    (production's screens_live); live=False writes each sequence's repo
    folder (out_root ignored)."""
    import subprocess, sys, tempfile
    if not any("demo" in st["capture"] for _, st in recipes(only=only)):
        return {"captured": [], "errors": []}
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(_SECRET_PREFIXES)
           and not k.upper().endswith(("_PIN", "_TOKEN", "_KEY", "_SECRET", "PASSWORD"))}
    env["SECRET_KEY"] = os.urandom(16).hex()
    env["DATABASE_PATH"] = tempfile.mktemp(prefix="screens-demo-", suffix=".db")
    env["SCREENS_DEMO"] = "1"
    env.pop("_SCHEDULER_STARTED_PID", None)
    args = [sys.executable, str(REPO / "tools/screens_demo.py")]
    args += (["--live", out_root] if live else ["--repo"]) + ([only] if only else [])
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env, cwd=str(REPO))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "captured": [], "errors": []}
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": f"demo runner exited {r.returncode}: {(r.stderr or '')[-300:]}",
                "captured": [], "errors": []}


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
