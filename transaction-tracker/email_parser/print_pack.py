"""The event PRINT PACK — every print sheet for an event bound into ONE
PDF, and the routine that emails it the evening before (v2.465.0).

Kerry 2026-09-18: "Are you able to build a routine that automatically
emails me the PDF reports for an event? Or perhaps a bound PDF with all
of them in one that I could print, rather than each separately?" —
"Build the PDF routine and have it emailed to me."

Parts, in print order: Starter Sheet, Cart Signs, Divisions & Flights,
Proximity Markers — the same templates the browser prints, rendered
server-side by WeasyPrint (paged-media CSS, the `@page` rules the
templates already carry). The PDF engine is imported lazily so a deploy
without it still boots; the route and the bridge then say so instead of
failing silently.

The routine (`send_due_print_packs`) runs hourly 5–10 PM Central and
mails the pack for every active event dated TOMORROW to
`PRINT_PACK_EMAIL_TO` (falls back to `DAILY_REPORT_TO`, then
`EMAIL_ADDRESS`). A content hash of the rendered parts is recorded in
`app_settings` (`print_pack_sent:<event_id>`), so a pack is sent once —
and sent AGAIN only if the sheet changed after the first send. Kerry
sends nothing here; the pack goes to Kerry.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import timedelta

logger = logging.getLogger(__name__)

# (slug, template, builder-name) — builders live in database.py
PRINT_PACK_PARTS = (
    ("starter-sheet", "starter_sheet.html", "get_event_print_pack", "pack"),
    ("cart-signs", "cart_signs.html", "get_event_print_pack", "pack"),
    ("divisions-flights", "divisions_flights.html", "event_flights_report", "rep"),
    ("proximity-markers", "proximity_markers.html", "event_proximity_report", "rep"),
)


def _static_url_fetcher(static_dir: str):
    """Serve the templates' `/static/...` references (the round logo) from
    disk; everything else (Google Fonts) goes through WeasyPrint's own
    fetcher. No request context is needed, so the scheduler can render."""
    import mimetypes
    from weasyprint import default_url_fetcher

    def fetch(url, *args, **kwargs):
        marker = "/static/"
        i = url.find(marker)
        if i >= 0 and (url.startswith("file:") or url.startswith("/") or
                       url.startswith("http")):
            rel = url[i + len(marker):].split("?")[0]
            path = os.path.normpath(os.path.join(static_dir, rel))
            if path.startswith(os.path.normpath(static_dir)) and os.path.isfile(path):
                mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
                return {"file_obj": open(path, "rb"), "mime_type": mime}
        return default_url_fetcher(url, *args, **kwargs)
    return fetch


def build_event_print_pack(render, event_id: int, static_dir: str,
                           db_path=None) -> dict | None:
    """Render every part and bind them into one PDF.

    `render(template_name, **context) -> str` is the caller's template
    renderer (Flask's `render_template` inside an app context). Returns
    {"pdf": bytes, "parts": [{"slug", "pages"}], "sha": content hash,
    "filename", "event"} — or None for an unknown event, or a dict with
    "error" when the PDF engine is missing.
    """
    from email_parser import database as db
    ev = db.get_all_events(db_path)
    ev = next((e for e in ev if e["id"] == int(event_id)), None)
    if not ev:
        return None
    htmls: list[tuple[str, str]] = []
    for slug, template, builder, key in PRINT_PACK_PARTS:
        ctx = getattr(db, builder)(int(event_id), db_path=db_path)
        if not ctx:
            continue
        try:
            htmls.append((slug, render(template, **{key: ctx})))
        except Exception:
            logger.exception("print pack: %s failed to render for event %s", slug, event_id)
    if not htmls:
        return None
    sha = hashlib.sha256("\n".join(h for _, h in htmls).encode("utf-8")).hexdigest()[:16]
    code = (ev.get("item_name") or f"event-{event_id}").replace("/", "-")
    # CHROMIUM FIRST (v2.465.8, Kerry 2026-09-18: "Formatting for your PDF
    # email is really bad compared to the PDF downloads on the Tracker").
    # The Tracker's own Download PDF is the browser's print pipeline; the
    # print templates lean on flex/grid that WeasyPrint lays out wrong
    # (collapsed columns, broken cart signs). Rendering through the same
    # engine the browser uses makes the pack identical to the download.
    # WeasyPrint stays as the fallback when no Chromium is on the box.
    engine_note = None
    try:
        pdf, parts, engine = _render_pdf_chromium(htmls, static_dir)
    except Exception as exc:
        # Kept on the result (and the bridge) so a lane can see WHY the
        # pack fell back without reading the Railway log.
        engine_note = f"chromium unavailable: {type(exc).__name__}: {str(exc)[:600]} " \
                      f"(executable={_chromium_executable()!r})"
        logger.warning("print pack: %s; trying weasyprint", engine_note)
        try:
            pdf, parts, engine = _render_pdf_weasyprint(htmls, static_dir)
        except Exception as exc2:                  # engine absent on this deploy
            return {"error": f"PDF engine unavailable: {exc2}", "sha": sha, "engine_note": engine_note,
                    "parts": [{"slug": s_, "pages": None} for s_, _ in htmls], "event": ev}
    return {"pdf": pdf, "parts": parts, "sha": sha, "event": ev, "engine": engine,
            "engine_note": engine_note,
            "assets": sorted(set(getattr(_render_pdf_chromium, "last_served", []))) if engine == "chromium" else None,
            "filename": f"{code} — print pack — {ev.get('event_date')}.pdf"}


PRINT_STATIC_ORIGIN = "http://tgf-print.local"   # never fetched: the route answers it


def _chromium_executable() -> str | None:
    import glob, shutil
    env = os.getenv("CHROMIUM_PATH")
    if env and os.path.isfile(env):
        return env
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome")):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def _render_pdf_chromium(htmls, static_dir: str):
    """Each part printed by headless Chromium with print media and the
    template's own @page size, then bound with pypdf. Runs in its own
    thread because Playwright's sync API refuses to start inside an
    asyncio loop (the MCP bridge runs in one)."""
    import concurrent.futures, mimetypes
    exe = _chromium_executable()
    if not exe:
        raise RuntimeError("no Chromium executable on this deploy")
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter
    import io

    served: list = []

    def _serve_static(route, request):
        url = request.url
        i = url.find("/static/")
        if i >= 0:
            rel = url[i + len("/static/"):].split("?")[0]
            path = os.path.normpath(os.path.join(static_dir, rel))
            if path.startswith(os.path.normpath(static_dir)) and os.path.isfile(path):
                served.append(rel)
                route.fulfill(path=path, content_type=mimetypes.guess_type(path)[0] or "application/octet-stream")
                return
            route.abort(); return
        route.continue_()

    # set_content() loads the document at about:blank, where a ROOT-RELATIVE
    # reference (`src="/static/tgf-logo-r.svg"`) resolves to nothing and no
    # request is ever made — the first Chromium pack printed the logo's alt
    # text (Kerry 2026-09-18: "the logo is not rendering"). Give every
    # /static/ reference a host so it becomes a request the route serves.
    _abs = re.compile(r"""(["'(])/static/""")
    htmls = [(slug, _abs.sub(r"\1" + PRINT_STATIC_ORIGIN + "/static/", html)) for slug, html in htmls]

    def _run():
        writer, parts = PdfWriter(), []
        with sync_playwright() as pw:
            # A current Chrome has dropped the OLD headless mode Playwright
            # asks for by default; request the new one explicitly.
            browser = pw.chromium.launch(executable_path=exe, headless=False,
                                         args=["--headless=new", "--no-sandbox", "--disable-gpu",
                                               "--disable-dev-shm-usage"])
            try:
                page = browser.new_page()
                page.route("**/*", _serve_static)
                for slug, html in htmls:
                    page.set_content(html, wait_until="networkidle")
                    page.emulate_media(media="print")
                    data = page.pdf(prefer_css_page_size=True, print_background=True)
                    reader = PdfReader(io.BytesIO(data))
                    for pg in reader.pages:
                        writer.add_page(pg)
                    parts.append({"slug": slug, "pages": len(reader.pages)})
            finally:
                browser.close()
        out = io.BytesIO(); writer.write(out)
        _render_pdf_chromium.last_served = list(served)
        return out.getvalue(), parts, "chromium"
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(_run).result(timeout=180)


def _render_pdf_weasyprint(htmls, static_dir: str):
    from weasyprint import HTML
    fetcher = _static_url_fetcher(static_dir)
    docs, parts = [], []
    for slug, html in htmls:
        doc = HTML(string=html, base_url=static_dir, url_fetcher=fetcher).render()
        docs.append(doc)
        parts.append({"slug": slug, "pages": len(doc.pages)})
    pages = [p for d in docs for p in d.pages]
    return docs[0].copy(pages).write_pdf(), parts, "weasyprint"


def print_pack_recipient() -> str | None:
    return (os.getenv("PRINT_PACK_EMAIL_TO") or os.getenv("DAILY_REPORT_TO")
            or os.getenv("EMAIL_ADDRESS"))


def send_event_print_pack(built: dict, to_address: str | None = None,
                          db_path=None) -> dict:
    """Mail a built pack as an attachment and record its hash."""
    from email_parser import database as db
    from email_parser.fetcher import send_mail_graph
    to_address = to_address or print_pack_recipient()
    creds = {k: os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                       "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")}
    if not to_address or not all(creds.values()):
        return {"sent": False, "why": "mail credentials or recipient not set"}
    ev = built["event"]
    parts = ", ".join(f"{p['slug']} ({p['pages']} pp)" for p in built["parts"])
    html = (f"<p>Print pack for <strong>{ev.get('item_name')}</strong> — "
            f"{ev.get('event_date')} · {ev.get('course') or ''}.</p>"
            f"<p>Bound in print order: {parts}.</p>"
            f"<p>Sent automatically the evening before; you get it again only if the "
            f"sheet changes. Print from the attachment.</p>")
    ok = send_mail_graph(tenant_id=creds["AZURE_TENANT_ID"], client_id=creds["AZURE_CLIENT_ID"],
                         client_secret=creds["AZURE_CLIENT_SECRET"],
                         from_address=creds["EMAIL_ADDRESS"], to_address=to_address,
                         subject=f"Print pack — {ev.get('item_name')} — {ev.get('event_date')}",
                         html_body=html,
                         attachments=[(built["filename"], built["pdf"], "application/pdf")])
    if ok:
        db.set_app_setting(f"print_pack_sent:{ev['id']}", built["sha"], db_path=db_path)
    return {"sent": bool(ok), "to": to_address, "sha": built["sha"],
            "filename": built["filename"], "bytes": len(built["pdf"])}


def print_packs_due(db_path=None) -> list[dict]:
    """Active events dated TOMORROW (Central)."""
    from email_parser import database as db
    from email_parser.timezone_utils import today_central
    tomorrow = (today_central() + timedelta(days=1)).isoformat()
    return [e for e in db.get_all_events(db_path)
            if (e.get("event_date") or "")[:10] == tomorrow
            and (e.get("status") or "active") == "active"]


def send_due_print_packs(render, static_dir: str, db_path=None) -> list[dict]:
    """The routine: build each due pack, send if never sent or changed."""
    from email_parser import database as db
    out = []
    for ev in print_packs_due(db_path):
        built = build_event_print_pack(render, ev["id"], static_dir, db_path=db_path)
        if not built or built.get("error"):
            out.append({"event_id": ev["id"], "sent": False,
                        "why": (built or {}).get("error") or "nothing to print"})
            continue
        last = db.get_app_setting(f"print_pack_sent:{ev['id']}", db_path=db_path)
        if last == built["sha"]:
            out.append({"event_id": ev["id"], "sent": False, "why": "unchanged since last send"})
            continue
        res = send_event_print_pack(built, db_path=db_path)
        res["event_id"] = ev["id"]
        out.append(res)
    return out
