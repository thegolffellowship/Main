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
`EMAIL_ADDRESS`), plus the chapter's extra recipients (dial
`print_pack_chapter_recipients`; Austin → Robert Straiton). A content hash of the rendered parts is recorded in
`app_settings` (`print_pack_sent:<event_id>`), so a pack is sent once —
and sent AGAIN only if the sheet changed after the first send. Kerry
sends nothing here; the pack goes to Kerry.
"""
from __future__ import annotations

import hashlib
import logging
import html as html_mod
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


def scorecards_in_pack(event_id: int, db_path=None) -> bool:
    """Does this event's pack carry scorecards? App setting
    `print_pack_scorecards`: "all" or a comma/space list of event ids."""
    from email_parser import database as db
    raw = (db.get_app_setting("print_pack_scorecards", db_path) or "").strip().lower()
    if raw == "all":
        return True
    return str(int(event_id)) in {t for t in re.split(r"[\s,\[\]\"']+", raw) if t}


def build_event_print_pack(render, event_id: int, static_dir: str,
                           db_path=None, allow_gaps: bool = False,
                           force_scorecards: bool = False) -> dict | None:
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
    sheet_pack = None
    _no_games = db.event_games_off(ev)
    for slug, template, builder, key in PRINT_PACK_PARTS:
        if _no_games and slug in ("divisions-flights", "proximity-markers"):
            continue   # no games at this event: no game sheets (Kerry 10/8)
        ctx = getattr(db, builder)(int(event_id), db_path=db_path)
        if not ctx:
            continue
        if slug == "starter-sheet":
            sheet_pack = ctx
            if (ctx.get("brand") or {}).get("lsc") == "practice":
                # The practice round prints the Cup's starter sheet (#1481)
                try:
                    from email_parser import lsc_starter
                    htmls.append((slug, render("lsc_starter_sheet.html",
                                               s=lsc_starter.build(int(event_id), db_path=db_path))))
                except Exception:
                    logger.exception("print pack: LSC starter sheet failed for event %s", event_id)
                continue
        if slug == "cart-signs":
            # The Lone Star Cup's practice round prints the Cup's design 3e
            # sign (Kerry 10/8), not the TGF one.
            if (ctx.get("brand") or {}).get("lsc") == "practice":
                try:
                    from email_parser.lsc_cup import practice_cart_signs
                    htmls.append((slug, render("cup_cart_signs.html",
                                               d=practice_cart_signs(int(event_id), db_path=db_path))))
                except Exception:
                    logger.exception("print pack: LSC cart signs failed for event %s", event_id)
                continue
            # Score-entry QR for the groups the `score_entry_qr` dial enables.
            from email_parser.score_entry import attach_cart_sign_qr
            attach_cart_sign_qr(ctx, db_path=db_path)
        try:
            htmls.append((slug, render(template, **{key: ctx})))
        except Exception:
            logger.exception("print pack: %s failed to render for event %s", slug, event_id)
    # SCORECARDS IN THE PACK (Kerry 2026-09-29: "Include the scorecards in
    # the print pack now"), right after the cart signs. Which events is a
    # dial, `print_pack_scorecards`: "all", or event ids ("3304,3317").
    # Defaults: 3-up, the grouping the engine's net game uses (Cart Net ->
    # one card per cart), the event's holes, QR only per the score-entry
    # dials, the saved GGID codes. A named gap does not print a guessed
    # card: the part is the gap sheet, and `scorecards.gaps` says why.
    sc_info = None
    if htmls and (force_scorecards or scorecards_in_pack(int(event_id), db_path=db_path)):
        try:
            from email_parser.scorecards import build_scorecards
            unit = (sheet_pack or {}).get("team_unit")
            sc = build_scorecards(int(event_id), "3up", "cart" if unit == "cart" else "team",
                                  qr="on", allow_gaps=allow_gaps, db_path=db_path)
            if sc:
                at = next((i + 1 for i, (sl, _) in enumerate(htmls) if sl == "cart-signs"),
                          len(htmls))
                htmls.insert(at, ("scorecards", render("scorecards.html", sc=sc)))
                sc_info = {"grouping": sc["grouping"], "cards": len(sc["cards"]),
                           "sheets": len(sc["sheets"]), "gaps": sc["gaps"],
                           "flagged": sc.get("flagged") or []}
        except Exception:
            logger.exception("print pack: scorecards failed for event %s", event_id)
            sc_info = {"error": "scorecards failed to render; see the log"}
    # GAMES & PAYOUTS (CD #967, Kerry 2026-09-29: "go in the print pack"),
    # right after the scorecards (or the cart signs). Its figures are the
    # GAMES tab's own; an event with no regular games (bucket accounts)
    # prints no sheet and says why in `games_sheet`.
    gs_info = None
    if htmls:
        try:
            from email_parser.games_sheet import build_games_sheet
            gs = build_games_sheet(int(event_id), db_path=db_path)
            if gs and not gs.get("error"):
                after = "scorecards" if any(sl == "scorecards" for sl, _ in htmls) else "cart-signs"
                at = next((i + 1 for i, (sl, _) in enumerate(htmls) if sl == after), len(htmls))
                htmls.insert(at, ("games-payouts", render("games_payouts.html", gs=gs)))
                gs_info = {"fund": gs["fund"], "pot_check_ok": gs["pot_check"]["ok"],
                           "warnings": gs["warnings"]}
            elif gs:
                gs_info = {"skipped": gs.get("error")}
        except Exception:
            logger.exception("print pack: games & payouts failed for event %s", event_id)
            gs_info = {"error": "games & payouts failed to render; see the log"}
    if not htmls:
        return None
    sha = hashlib.sha256("\n".join(_hash_view(h) for _, h in htmls).encode("utf-8")).hexdigest()[:16]
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
    from email_parser.database import print_file_stub as _pfs
    return {"pdf": pdf, "parts": parts, "sha": sha, "event": ev, "engine": engine,
            "scorecards": sc_info, "games_sheet": gs_info,
            "engine_note": engine_note, "pack": sheet_pack,
            "assets": sorted(set(getattr(_render_pdf_chromium, "last_served", []))) if engine == "chromium" else None,
            # <stub>-PrintPack.pdf, the report file-name convention (Kerry 9/29).
            "filename": f"{_pfs(ev) or code}-PrintPack.pdf"}


PRINT_STATIC_ORIGIN = "http://tgf-print.local"   # never fetched: the route answers it


_STAMP_RE = re.compile(r'<span class="pstamp">.*?</span>', re.S)


def _hash_view(html: str) -> str:
    """The HTML as the once-per-change routine compares it: the printed-at
    stamp removed, so a sheet that has not changed keeps its hash from
    one hour to the next and is not mailed again."""
    return _STAMP_RE.sub("", html or "")


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


# Per-CHAPTER extra recipients (Kerry 2026-09-22: "Make sure AUSTIN Send
# Pack sends to Robert Straiton at robert@thegolffellowship.com as well as
# me"). The app_settings dial `print_pack_chapter_recipients` is a JSON
# object {chapter: "addr[, addr]"}; unset, the seed below applies. The
# configured recipient (Kerry) is always first; extras are appended.
PRINT_PACK_CHAPTER_RECIPIENTS_KEY = "print_pack_chapter_recipients"
PRINT_PACK_CHAPTER_RECIPIENTS_DEFAULT = {"Austin": "robert@thegolffellowship.com"}


def print_pack_chapter_recipients(db_path=None) -> dict:
    """{chapter: [addr, ...]} — the dial, else the seed."""
    import json
    raw = None
    try:
        from email_parser import database as db
        raw = db.get_app_setting(PRINT_PACK_CHAPTER_RECIPIENTS_KEY, db_path=db_path)
    except Exception:
        raw = None
    src = PRINT_PACK_CHAPTER_RECIPIENTS_DEFAULT
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                src = parsed
        except (TypeError, ValueError):
            pass
    out = {}
    for ch, v in src.items():
        addrs = v if isinstance(v, list) else str(v or "").split(",")
        out[str(ch).strip().lower()] = [a.strip() for a in addrs if a and a.strip()]
    return out


def print_pack_recipient(ev: dict | None = None, db_path=None) -> str | None:
    """Comma-separated To: line — the configured recipient, then the
    event's chapter extras (none for a chapter-less or TGF-wide event)."""
    base = (os.getenv("PRINT_PACK_EMAIL_TO") or os.getenv("DAILY_REPORT_TO")
            or os.getenv("EMAIL_ADDRESS"))
    addrs = [a.strip() for a in (base or "").split(",") if a.strip()]
    if ev:
        for a in print_pack_chapter_recipients(db_path).get(
                (ev.get("chapter") or "").strip().lower(), []):
            if a.lower() not in {x.lower() for x in addrs}:
                addrs.append(a)
    return ", ".join(addrs) or None


def _esc(v) -> str:
    return html_mod.escape("" if v is None else str(v), quote=True)


def _fmt_num(v):
    if v is None or v == "":
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return _esc(v)
    return f"{f:g}" if f != int(f) else str(int(f))


def print_pack_email_body(built: dict) -> str:
    """The sheet's essentials IN THE MAIL (Kerry 2026-09-21: "Yes, build the
    email body for the next pack"): first tee, every group with its
    players — index · PH · cart/team — the blinds, and the badge notes,
    so the night reads on a phone without opening the PDF. The PDF is
    unchanged and stays the thing to print."""
    ev = built.get("event") or {}
    pack = built.get("pack") or {}
    pev = pack.get("event") or {}
    unit = "CART" if pack.get("team_unit") == "cart" else "TEAM"
    holes_key = pack.get("holes_key") or ""
    parts = ", ".join(f"{p['slug'].replace('-', ' ')} ({p['pages']} pp)" for p in built.get("parts") or [])
    out = [f'<p style="margin:0 0 1em;"><strong>{_esc(ev.get("item_name"))}</strong> — '
           f'{_esc(ev.get("event_date"))} · {_esc(ev.get("course") or "")}'
           f'{" · " + _esc(pev.get("chapter")) if pev.get("chapter") else ""}</p>']
    if pev.get("start_label"):
        out.append(f'<p style="margin:0 0 1em;font-size:1.1em;"><strong>{_esc(pev["start_label"])}</strong>'
                   f'{" · " + _esc(pev.get("start_type")) if pev.get("start_type") else ""}'
                   f'{" · 18s " + _esc(pev.get("start_label_18")) if pev.get("start_label_18") else ""}</p>')
    groups = pack.get("groups") or []
    if groups:
        rows = []
        _offlow = bool((pack.get("team_off_lowest") or {}).get("applied"))

        def _team_cell(pl):
            if pl.get("team_handicap") is None:
                return "—"
            if _offlow:
                return (f'{_fmt_num(pl.get("team_allowed"))} / '
                        f'<span style="color:#B91C1C;font-weight:700;">{_fmt_num(pl.get("team_handicap"))}</span>')
            return _fmt_num(pl.get("team_handicap"))
        for g in groups:
            label = g.get("start_line") or g.get("hole_label") or g.get("slot_label") or ""
            names = []
            for pl in g.get("players") or []:
                badges = ("".join(
                    f' <span style="font-size:0.75em;font-weight:700;color:#fff;background:{c};'
                    f'padding:0 4px;border-radius:3px;">{t}</span>'
                    for t, c, on in (("1T", "#E87C3E", pl.get("is_first_timer")),
                                     ("NEW", "#15803D", pl.get("is_new"))) if on))
                # Name on its own line, the numbers under it — at phone
                # width a one-line row wrapped mid-number.
                names.append(
                    f'<div style="padding:0 0 5px;"><strong>{_esc(pl.get("name"))}</strong>{badges}'
                    f'<br><span style="color:#6B7280;font-size:12px;">'
                    f'{_esc(pl.get("tee_choice") or "")} · idx {_fmt_num(pl.get("handicap_index_display", pl.get("handicap_index")))}'
                    f' · PH {_fmt_num(pl.get("playing_handicap"))} · {unit} {_team_cell(pl)}</span></div>')
            for b in g.get("blinds") or []:
                names.append(f'<div style="color:#6B7280;font-style:italic;">BLIND · {_esc(b.get("name"))}</div>')
            rows.append(f'<tr><td style="padding:8px 12px 8px 0;vertical-align:top;white-space:nowrap;border-top:1px solid #E5E7EB;">'
                        f'<strong>{_esc(label)}</strong></td>'
                        f'<td style="padding:8px 0 4px;vertical-align:top;border-top:1px solid #E5E7EB;">{"".join(names)}</td></tr>')
        out.append('<table style="border-collapse:collapse;font-family:-apple-system,Helvetica,Arial,sans-serif;'
                   'font-size:14px;margin:0 0 1em;">' + "".join(rows) + "</table>")
    notes = [f"<strong>1T</strong> first TGF event ever · <strong>NEW</strong> new member playing their first event as a member (both can show)",
             f"<strong>idx</strong> TGF index ({holes_key}-hole) · <strong>PH</strong> playing handicap at 100%"
             + (f" ({_esc(pack['ph_basis'])})" if pack.get("ph_basis") else "")]
    if pack.get("team_basis"):
        notes.append(f"<strong>{unit}</strong> {_esc(pack['team_basis'])}")
    _ol = pack.get("team_off_lowest") or {}
    if _ol.get("applied"):
        _n = abs(int(_ol["low"]))
        notes.append(f'<span style="color:#B91C1C;font-weight:600;">{unit} prints as allowance / OFF THE LOWEST — the number in red '
                     f'is the one you play: {_n} stroke{"" if _n == 1 else "s"} {"less" if _ol["low"] > 0 else "more"}, because the field\'s lowest '
                     f'({_esc(", ".join(_ol.get("lowest") or []))}{", a plus " + str(_n) if _ol["low"] < 0 else ""}) plays at 0 and everyone else plays off them.</span>')
    if pack.get("ph_note"):
        notes.append(f'<span style="color:#B45309;">{_esc(pack["ph_note"])}</span>')
    out.append('<p style="margin:0 0 1em;font-size:12px;color:#6B7280;">' + "<br>".join(notes) + "</p>")
    out.append(f'<p style="margin:0 0 1em;font-size:12px;color:#6B7280;">Attached: {_esc(parts)}, bound in print order. '
               f'Sent the evening before; sent again only if the sheet changes. Print from the attachment.</p>')
    return "".join(out)


PART_FILE_NAMES = {"starter-sheet": "StarterSheet", "cart-signs": "CartSigns",
                   "scorecards": "Scorecards", "games-payouts": "GamesPayouts",
                   "divisions-flights": "DivisionsFlights", "proximity-markers": "Proximity"}


def split_print_pack(built: dict) -> list[tuple[str, bytes]]:
    """The bound pack cut back into one PDF per report, by the page count
    each part printed (Kerry 2026-10-09: "Can you have the practice round
    reports sent to me in separate PDF files right now? I need to send to
    course for printing"). [(filename, pdf bytes)] in print order, named
    <stub>-<Report>.pdf like the per-report downloads."""
    import io
    from pypdf import PdfReader, PdfWriter
    from email_parser.database import print_file_stub as _pfs
    reader = PdfReader(io.BytesIO(built["pdf"]))
    stub = _pfs(built.get("event") or {}) or f"event-{(built.get('event') or {}).get('id')}"
    out, at = [], 0
    for part in built.get("parts") or []:
        n = int(part.get("pages") or 0)
        if n <= 0:
            continue
        w = PdfWriter()
        for pg in reader.pages[at:at + n]:
            w.add_page(pg)
        at += n
        buf = io.BytesIO(); w.write(buf)
        name = PART_FILE_NAMES.get(part["slug"]) or part["slug"].title().replace("-", "")
        out.append((f"{stub}-{name}.pdf", buf.getvalue()))
    if at != len(reader.pages):
        raise ValueError(f"page counts {at} do not match the pack's {len(reader.pages)} pages")
    return out


def send_print_pack_files(built: dict, to_address: str | None = None, db_path=None) -> dict:
    """Mail every report of a built pack as its OWN PDF attachment, one
    email. Does not touch the evening-before pack's sent hash."""
    from email_parser.fetcher import send_mail_graph
    files = split_print_pack(built)
    to_address = to_address or print_pack_recipient(built.get("event"), db_path=db_path)
    creds = {k: os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                       "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")}
    listing = [{"filename": f, "bytes": len(b)} for f, b in files]
    if not to_address or not all(creds.values()):
        return {"sent": False, "why": "mail credentials or recipient not set", "files": listing}
    ev = built["event"]
    rows = "".join(f"<li>{_esc(f)}</li>" for f, _ in files)
    html = (f'<p style="margin:0 0 1em;">Print files for <b>{_esc(ev.get("item_name"))}</b>, '
            f'{_esc(ev.get("event_date"))}: one PDF per report, ready to forward to the course.</p>'
            f'<ul style="margin:0 0 1em;">{rows}</ul>')
    ok = send_mail_graph(tenant_id=creds["AZURE_TENANT_ID"], client_id=creds["AZURE_CLIENT_ID"],
                         client_secret=creds["AZURE_CLIENT_SECRET"],
                         from_address=creds["EMAIL_ADDRESS"], to_address=to_address,
                         subject=f"Print files — {ev.get('item_name')} — {ev.get('event_date')}",
                         html_body=html,
                         attachments=[(f, b, "application/pdf") for f, b in files])
    return {"sent": bool(ok), "to": to_address, "files": listing}


def send_event_print_pack(built: dict, to_address: str | None = None,
                          db_path=None) -> dict:
    """Mail a built pack as an attachment and record its hash."""
    from email_parser import database as db
    from email_parser.fetcher import send_mail_graph
    to_address = to_address or print_pack_recipient(built.get("event"), db_path=db_path)
    creds = {k: os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                       "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")}
    if not to_address or not all(creds.values()):
        return {"sent": False, "why": "mail credentials or recipient not set"}
    ev = built["event"]
    html = print_pack_email_body(built)
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
    """Active events dated TODAY (Central). Kerry 2026-09-21: the packs
    "probably shouldn't be sent until 6:00a day of" — the routine runs
    from 6 AM on the event day, not the evening before (v2.465.0)."""
    from email_parser import database as db
    from email_parser.timezone_utils import today_central
    today = today_central().isoformat()
    return [e for e in db.get_all_events(db_path)
            if (e.get("event_date") or "")[:10] == today
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
