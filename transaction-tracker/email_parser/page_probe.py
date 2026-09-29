"""Read a page's numbers by running the PAGE's own code (Kerry 2026-09-29).

Kerry: "Why can't you see the games tab info? You need to create a tool
that allows you to see it." The GAMES tab is computed in the browser from
the live matrix, the roster and same-day MVP links; no server function
produces its numbers. A server port would be a second copy that can
drift, so this module loads the real Events page in headless Chromium and
calls the page's own `renderGamesPanel` / `computeGameStats` — the tool
and the screen cannot disagree.

Every request the page makes is answered IN-PROCESS by the Flask test
client (the app runs one worker, so an HTTP call back to itself could
deadlock). Only GET / HEAD are forwarded; anything else the page tries
(a beacon, a keepalive POST) is answered with an empty 204 and never
reaches the app — the probe cannot write. Off-origin requests (fonts,
CDNs) are aborted.
"""
from __future__ import annotations

import concurrent.futures
import logging

logger = logging.getLogger(__name__)

ORIGIN = "http://tracker.probe"

_EXTRACT_JS = r"""
(evId) => {
  const ev = (typeof allEvents !== 'undefined') ? allEvents.find(e => e.id === evId) : null;
  if (!ev) return {error: 'event not on the Events page', event_id: evId};
  const name = ev.item_name;
  const regs = getRegistrants(name);
  const stats = computeGameStats(regs, name);
  const holder = document.createElement('div');
  holder.innerHTML = renderGamesPanel(ev);
  const txt = el => (el ? el.textContent.replace(/\s+/g, ' ').trim() : null);
  const out = {
    event: {id: ev.id, item_name: name, event_date: ev.event_date, course: ev.course,
            chapter: ev.chapter, format: ev.format},
    holes: extractHolesType(name, ev.format),
    counts: {players: stats.players, net: stats.net, gross: stats.gross,
             no_games: stats.noGames, not_playing: stats.notPlaying},
    header: txt(holder.querySelector('.games-panel-header')),
    hole_in_one: [...holder.querySelectorAll('.hole-in-one-banner .hio-line')].map(txt),
    sections: [], total: null, buckets: null, empty: txt(holder.querySelector('.games-panel-empty')),
  };
  const b = (typeof EVENT_BUCKETS !== 'undefined') ? EVENT_BUCKETS[String(ev.id)] : null;
  if (b && b.length) out.buckets = b;
  let sec = null;
  const cols = ['game', 'pot', 'mwp', 'flights', '1st', '2nd', '3rd', '4th'];
  holder.querySelectorAll('table.games-table tbody tr').forEach(tr => {
    if (tr.classList.contains('games-section-row')) {
      sec = {section: txt(tr), rows: [], subtotal: null}; out.sections.push(sec); return;
    }
    if (tr.classList.contains('games-winner-row')) return;   // hydrated later from GG results
    const cells = [...tr.children].map(txt);
    const row = {};
    if (cells.length === 1 || tr.classList.contains('games-row-disabled')) {
      row.game = cells[0]; row.note = cells.slice(1).join(' ').trim() || null; row.disabled = true;
    } else {
      cols.forEach((k, i) => { if (cells[i]) row[k] = cells[i]; });
    }
    if (tr.classList.contains('games-row-sub')) row.sub = true;
    if (!sec) { sec = {section: null, rows: [], subtotal: null}; out.sections.push(sec); }
    if (tr.classList.contains('games-row-total')) sec.subtotal = row; else sec.rows.push(row);
  });
  const tot = holder.querySelector('table.games-table tfoot tr');
  if (tot) { const c = [...tot.children].map(txt); out.total = {pot: c[1], mwp: c[2]}; }
  // WHO COUNTS — the page's own classifier, one player (and his child
  // rows) at a time, so the lists come from computeGameStats itself.
  const buyers = {players: [], net: [], gross: [], no_games: [], not_playing: []};
  regs.filter(r => !r.parent_item_id).forEach(r => {
    const s = computeGameStats(regs.filter(x => x === r || x.parent_item_id === r.id), name);
    const who = {customer_id: r.customer_id || null, name: r.customer, item_id: r.id,
                 status: r.transaction_status || 'active'};
    if (s.players) buyers.players.push(who);
    if (s.net) buyers.net.push(who);
    if (s.gross) buyers.gross.push(who);
    if (s.noGames) buyers.no_games.push(who);
    if (s.notPlaying) buyers.not_playing.push(who);
  });
  out.buyers = buyers;
  out.buyer_lists_match_counts = buyers.players.length === stats.players
    && buyers.net.length === stats.net && buyers.gross.length === stats.gross;
  return out;
}
"""


def event_games_tab(event_id: int, timeout_s: int = 90) -> dict:
    """The GAMES tab for one event, computed by the Events page itself."""
    import app as _app
    from email_parser.print_pack import _chromium_executable
    exe = _chromium_executable()
    if not exe:
        return {"error": "no Chromium on this deploy"}
    from playwright.sync_api import sync_playwright

    client = _app.app.test_client()
    with client.session_transaction() as sess:
        sess["role"] = "admin"
        sess["authenticated"] = True
    refused: list[str] = []

    def _answer(route, request):
        url = request.url
        if not url.startswith(ORIGIN):
            route.abort(); return
        path = url[len(ORIGIN):] or "/"
        if request.method not in ("GET", "HEAD"):
            refused.append(f"{request.method} {path.split('?')[0]}")
            route.fulfill(status=204, body=""); return
        r = client.open(path, method=request.method,
                        headers={"Accept": request.headers.get("accept", "*/*")})
        hdrs = {k: v for k, v in r.headers.items()
                if k.lower() in ("content-type", "cache-control", "location")}
        route.fulfill(status=r.status_code, headers=hdrs, body=r.get_data())

    def _run():
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=exe, headless=False,
                                         args=["--headless=new", "--no-sandbox", "--disable-gpu",
                                               "--disable-dev-shm-usage"])
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.route("**/*", _answer)
                page.goto(f"{ORIGIN}/events", wait_until="networkidle", timeout=timeout_s * 1000)
                page.wait_for_function(
                    "(id) => typeof allEvents !== 'undefined' && allEvents.some(e => e.id === id)"
                    " && typeof renderGamesPanel === 'function'",
                    arg=int(event_id), timeout=timeout_s * 1000)
                page.wait_for_load_state("networkidle")
                out = page.evaluate(_EXTRACT_JS, int(event_id))
            finally:
                browser.close()
        out["source"] = "the Events page's own renderGamesPanel / computeGameStats, run headless"
        out["refused_writes"] = refused
        return out

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(_run).result(timeout=timeout_s + 30)
