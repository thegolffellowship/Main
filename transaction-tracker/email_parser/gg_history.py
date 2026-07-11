"""GG History ingest engine — archive portals → gg_history_* tables.

Kerry-ratified 2026-07-11 (mailbox #113/#116 + in-session "let's start"):
walk the 59 archived Golf Genius portals newest-first and bank standings/
results verbatim, identity-linked by customer_id, raw-archived BEFORE
parsing (the GG-prune hedge). Coverage map + schema of record:
docs/claude/gg-history.md.

Phase A (this module, v2.70.0): the STANDINGS layer — season standings,
cups, money lists, monthly points. Phase B (event-by-event results via
tournament_results round enumeration + /v2tournaments partials) reuses
gg_history_pages and lands next.

Brand rule (Kerry): 'TwoManTour' rows are a HARD-SEPARATED lane — banked
and identity-linked for the future Two Man Tour partner build, but never
computed into TGF career stats, trophy case, or member surfaces. The
2020–2023 Two Man leagues predate the Tour and are TGF (flagged
interpretation, mailbox #116 item 1).

Never create customers here: unmatched names become 'pending' rows in
gg_history_name_links (surfaced on COO action items), not shell profiles.
"""
from __future__ import annotations

import json
import logging
import re
import time
import zlib

logger = logging.getLogger(__name__)

# ── Portal registry seed (the coverage map as data) ──────────────────────
# (subdomain, chapter, season, kind, brand, status)
SEED_PORTALS = [
    # San Antonio seasons
    *[(f"tgf-sa{y}", "San Antonio", str(y), "season", "TGF", "alive")
      for y in range(2016, 2026)],
    # Austin seasons
    *[(f"tgf-austin{y}", "Austin", str(y), "season", "TGF", "alive")
      for y in range(2019, 2026)],
    # DFW / Houston (closed chapters)
    *[(f"tgf-dfw{y}", "DFW", str(y), "season", "TGF", "alive")
      for y in range(2020, 2025)],
    *[(f"tgf-houston{y}", "Houston", str(y), "season", "TGF", "alive")
      for y in range(2021, 2025)],
    # TGF Championships
    *[(f"tgf-champ{y}", None, f"20{y}", "oneoff", "TGF", "alive")
      for y in (20, 21, 22, 23, 24, 25)],
    # Lone Star Cups (naming chaos is real — see gg-history.md)
    ("tgf-lonestarcup21", None, "2021", "oneoff", "TGF", "alive"),
    ("tgf-lonestarcup22", None, "2022", "oneoff", "TGF", "alive"),
    ("lonestarcup",       None, "2023", "oneoff", "TGF", "alive"),
    ("lonestarcup24",     None, "2024", "oneoff", "TGF", "alive"),
    ("tgf-lonestarcup25", None, "2025", "oneoff", "TGF", "alive"),
    # Road Trips
    ("tgf-roadtrip2020", None, "2020", "oneoff", "TGF", "alive"),
    ("tgf-roadtrip2021", None, "2021", "oneoff", "TGF", "alive"),
    ("tgf-roadtrip2022", None, "2022", "oneoff", "TGF", "alive"),
    ("tgf-roadtrip2023", None, "2023", "oneoff", "TGF", "alive"),
    ("tgf-roadtrip24",   None, "2024", "oneoff", "TGF", "alive"),  # hybrid: one TwoManTour event inside
    ("tgf-roadtrip25",   None, "2025", "oneoff", "TGF", "alive"),
    # Hill Country family
    ("tgf-2020hccup",       None, "2020", "oneoff", "TGF", "alive"),
    ("tgf-hcc21",           None, "2021", "oneoff", "TGF", "alive"),
    ("tgf-hcc22",           None, "2022", "oneoff", "TGF", "alive"),
    ("tgf-hc",              None, "2022", "oneoff", "TGF", "alive"),   # TGF Hill Country 2022
    ("tgf-hillcountry",     None, "2023", "oneoff", "TGF", "alive"),   # TGF Hill Country 2023
    ("tgf-hcm",             None, "2023", "oneoff", "TGF", "alive"),   # Hill Country Matches 2023
    ("hillcountrymatches",  None, "2024", "oneoff", "TGF", "alive"),   # Hill Country Matches 2024
    # Other TGF one-offs
    ("redblue",     None, "2023", "oneoff", "TGF", "alive"),
    ("tgf-trinity", None, "2022", "oneoff", "TGF", "alive"),  # DFW v Houston Ryder Cup
    # Two Man — pre-Tour era = TGF (flagged interpretation, #116 item 1)
    ("tgf-twoman2020", None, "2020", "oneoff", "TGF", "alive"),
    ("tgf-twoman2021", None, "2021", "oneoff", "TGF", "alive"),
    ("tgf-twoman2022", None, "2022", "oneoff", "TGF", "alive"),
    ("tgf-twoman",     None, "2023", "oneoff", "TGF", "alive"),
    # Two Man Tour — SEPARATE BRAND (hard filter)
    ("tgf-twomantour",     None, None,   "oneoff", "TwoManTour", "alive"),
    ("hillcountry2man-1",  None, "2023", "oneoff", "TwoManTour", "alive"),
    ("hillcountry2man",    None, "2023", "oneoff", "TwoManTour", "alive"),
    # Dead mains (registry completeness)
    ("tgf-dfw",     "DFW",     None, "season", "TGF", "gone"),
    ("tgf-houston", "Houston", None, "season", "TGF", "gone"),
]

# Ingest-order weight: newest season first; season portals before one-offs
# within a year (Kerry: slowly, backwards chronologically).


def ensure_gg_history_tables(conn) -> None:
    """Idempotent DDL for the Kerry-ratified gg_history_* schema."""
    conn.execute("""CREATE TABLE IF NOT EXISTS gg_history_portals (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        subdomain      TEXT UNIQUE NOT NULL,
        chapter        TEXT,
        season         TEXT,
        kind           TEXT NOT NULL,
        brand          TEXT NOT NULL,
        source         TEXT NOT NULL DEFAULT 'recon',
        status         TEXT NOT NULL DEFAULT 'alive',
        website_id     TEXT,
        league_id      TEXT,
        last_probed_at TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gg_history_pages (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        portal_id      INTEGER NOT NULL REFERENCES gg_history_portals(id),
        gg_page_id     TEXT NOT NULL,
        page_title     TEXT,
        page_kind      TEXT,
        widget_type    TEXT,
        raw_archive_id INTEGER REFERENCES gg_raw_archive(id),
        fetch_status   TEXT,
        fetched_at     TEXT,
        UNIQUE(portal_id, gg_page_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gg_history_standings (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        page_id       INTEGER NOT NULL REFERENCES gg_history_pages(id),
        contest_label TEXT NOT NULL,
        season        TEXT,
        chapter       TEXT,
        position      INTEGER,
        player_name   TEXT NOT NULL,
        customer_id   INTEGER REFERENCES customers(customer_id),
        points        REAL,
        money_cents   INTEGER,
        gg_member_ids TEXT,
        raw_row       TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gg_history_events (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        portal_id        INTEGER NOT NULL REFERENCES gg_history_portals(id),
        season           TEXT,
        chapter          TEXT,
        event_label      TEXT,
        event_date       TEXT,
        course           TEXT,
        brand            TEXT,
        gg_round_id      TEXT,
        gg_round_index   INTEGER,
        tracker_event_id INTEGER REFERENCES events(id),
        raw_row          TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gg_history_results (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        gg_event_id      INTEGER NOT NULL REFERENCES gg_history_events(id),
        game_label       TEXT,
        player_name      TEXT NOT NULL,
        customer_id      INTEGER REFERENCES customers(customer_id),
        team_label       TEXT,
        position         TEXT,
        playing_handicap REAL,
        gross            REAL,
        net              REAL,
        points           REAL,
        money_cents      INTEGER,
        gg_aggregate_id  TEXT,
        gg_member_ids    TEXT,
        raw_row          TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gg_history_name_links (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_name    TEXT NOT NULL,
        portal_id   INTEGER REFERENCES gg_history_portals(id),
        customer_id INTEGER REFERENCES customers(customer_id),
        matched_by  TEXT NOT NULL,
        reviewed    INTEGER DEFAULT 0,
        UNIQUE(raw_name, portal_id))""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ggh_standings_cid "
                 "ON gg_history_standings(customer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ggh_standings_page "
                 "ON gg_history_standings(page_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ggh_results_cid "
                 "ON gg_history_results(customer_id)")


def seed_portal_registry(db_path=None) -> dict:
    """Create tables + upsert the 61-row portal registry. Idempotent."""
    from email_parser.database import _connect, DB_PATH
    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        inserted = 0
        for sub, chapter, season, kind, brand, status in SEED_PORTALS:
            cur = conn.execute(
                """INSERT INTO gg_history_portals
                       (subdomain, chapter, season, kind, brand, source, status)
                   VALUES (?, ?, ?, ?, ?, 'recon', ?)
                   ON CONFLICT(subdomain) DO UPDATE SET
                       chapter=excluded.chapter, season=excluded.season,
                       kind=excluded.kind, brand=excluded.brand,
                       status=excluded.status""",
                (sub, chapter, season, kind, brand, status))
            inserted += cur.rowcount
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM gg_history_portals").fetchone()[0]
        return {"portals_in_registry": n, "rows_touched": inserted}


# ── Page classification ──────────────────────────────────────────────────

_MONTHS = ("JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY",
           "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER")

_SKIP_KINDS = {"schedule", "directory", "analytics", "other"}


def classify_page(title: str) -> str:
    t = (title or "").upper()
    if any(m in t for m in _MONTHS) and "POINT" in t:
        return "monthly_points"
    if "MONEY" in t:
        return "money_leaders"
    if "MATCH PLAY" in t or "BRACKET" in t:
        return "match_play"
    if "EVENT RESULTS" in t or "TOURNAMENT RESULTS" in t or t == "RESULTS":
        return "event_results"
    if any(k in t for k in ("CUP", "POINTS RACE", "STANDINGS", " NET",
                            " GROSS", "FALL", "TEAM RACE", "LEADERBOARD",
                            "MATCHES")):
        return "season_standings"
    if any(k in t for k in ("DIRECTORY", "MEMBERS", "ROSTER", "PLAYERS")):
        return "directory"
    if any(k in t for k in ("SCHEDULE", "TEE SHEET", "ITINERARY", "MAP")):
        return "schedule"
    if any(k in t for k in ("ANALYTIC", "IMPROVED", "PAIRING", "TIMES "
                            "TOGETHER", "HOLE BY HOLE", "HANDICAP",
                            "DASHBOARD", "CREDITS")):
        return "analytics"
    return "other"


# ── Parsing helpers ──────────────────────────────────────────────────────

def _money_to_cents(s: str):
    m = re.search(r"-?\$?\s*([\d,]+(?:\.\d{1,2})?)", str(s or ""))
    if not m:
        return None
    try:
        return int(round(float(m.group(1).replace(",", "")) * 100))
    except ValueError:
        return None


def _to_float(s: str):
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _rank_to_int(s: str):
    m = re.match(r"T?(\d+)", str(s or "").strip())
    return int(m.group(1)) if m else None


def parse_standings_table(rows: list) -> list:
    """Map a widget table (list of row lists, first = header) to dicts."""
    if not rows or len(rows) < 2:
        return []
    header = [str(h).strip().lower() for h in rows[0]]

    def col(*needles, exclude=()):
        for i, h in enumerate(header):
            if any(n in h for n in needles) and not any(x in h for x in exclude):
                return i
        return None

    c_player = col("player")
    if c_player is None:
        return []
    c_rank = col("current rank", "rank", "number", "pos")
    c_points = col("point", exclude=("behind", "part."))
    c_purse = col("purse", "money")
    out = []
    for r in rows[1:]:
        if c_player >= len(r):
            continue
        name = str(r[c_player]).strip()
        if not name or name.lower().startswith("total"):
            continue
        def cell(i):
            return r[i] if i is not None and i < len(r) else None
        out.append({
            "player_name": name,
            "position": _rank_to_int(cell(c_rank)) if c_rank is not None
                        else len(out) + 1,
            "points": _to_float(cell(c_points)),
            "money_cents": _money_to_cents(cell(c_purse)),
            "raw_row": json.dumps(r),
        })
    return out


# ── Portal ingest (Phase A: standings layer) ─────────────────────────────

_LEAGUE_ID_RE = re.compile(
    r"id=\"current_league_id\"\s+value=\"(\d+)\"|"
    r"id='current_league_id'\s+value='(\d+)'")
_WEBSITE_ID_RE = re.compile(
    r"id=\"website_id\"\s+value=\"(\d+)\"|id='website_id'\s+value='(\d+)'")
_IFRAME_WIDGET_RE = re.compile(
    r"<iframe[^>]+src=[\"']([^\"']*/widgets/([a-z_0-9]+)[^\"']*)[\"']", re.I)

_INGEST_KINDS = ("season_standings", "monthly_points", "money_leaders")


def _archive_raw(conn, url: str, body: str) -> int:
    cur = conn.execute(
        "INSERT INTO gg_raw_archive (url, body_gz) VALUES (?, ?)",
        (url, zlib.compress(body.encode("utf-8"))))
    return cur.lastrowid


def _resolve_identity(conn, portal_id: int, name: str):
    """customer_id via the scoring cascade; never creates customers.
    Records the outcome in gg_history_name_links (idempotent)."""
    from email_parser.database import _resolve_scoring_player
    cid = None
    try:
        cid = _resolve_scoring_player(conn, name)
    except Exception:
        cid = None
    conn.execute(
        """INSERT INTO gg_history_name_links (raw_name, portal_id,
               customer_id, matched_by)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(raw_name, portal_id) DO UPDATE SET
               customer_id=COALESCE(excluded.customer_id,
                                    gg_history_name_links.customer_id),
               matched_by=CASE WHEN excluded.customer_id IS NOT NULL
                               THEN excluded.matched_by
                               ELSE gg_history_name_links.matched_by END""",
        (name, portal_id, cid, "scoring_cascade" if cid else "pending"))
    return cid


def ingest_portal(subdomain: str, budget_seconds: int = 240,
                  db_path=None) -> dict:
    """Phase-A walk of one portal: discover league/pages, then fetch +
    archive + parse every standings-kind page. Resumable: pages already
    'done' are skipped; call repeatedly until pages_remaining == 0.
    """
    from email_parser.database import _connect, DB_PATH
    from golf_genius_sync import fetch_public_page, parse_page_structure

    t0 = time.time()
    base = f"https://{subdomain}.golfgenius.com"
    stats = {"subdomain": subdomain, "pages_done": 0, "rows": 0,
             "matched": 0, "pending": 0, "skipped_kinds": 0}

    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        portal = conn.execute(
            "SELECT * FROM gg_history_portals WHERE subdomain = ?",
            (subdomain,)).fetchone()
        if portal is None:
            return {"error": f"unknown portal {subdomain!r} — run "
                             "gg-history-seed first"}
        if portal["status"] == "gone":
            return {"error": f"{subdomain} is registered as gone/dead"}
        portal_id = portal["id"]

        # 1) Home fetch: league_id + website_id + nav page catalog
        home = fetch_public_page(base + "/")
        if home["status_code"] != 200 or "golfgenius.com" not in home["final_url"]:
            return {"error": f"home fetch failed ({home['status_code']})"}
        if "www.golfgenius.com" in home["final_url"]:
            conn.execute("UPDATE gg_history_portals SET status='gone', "
                         "last_probed_at=datetime('now') WHERE id=?",
                         (portal_id,))
            conn.commit()
            return {"error": f"{subdomain} now redirects to corporate — "
                             "marked gone"}
        html = home["html"]
        m = _LEAGUE_ID_RE.search(html)
        league_id = (m.group(1) or m.group(2)) if m else portal["league_id"]
        m = _WEBSITE_ID_RE.search(html)
        website_id = (m.group(1) or m.group(2)) if m else portal["website_id"]
        conn.execute(
            "UPDATE gg_history_portals SET league_id=COALESCE(?, league_id), "
            "website_id=COALESCE(?, website_id), "
            "last_probed_at=datetime('now') WHERE id=?",
            (league_id, website_id, portal_id))

        parsed = parse_page_structure(html, home["final_url"])
        seen_pages = {}
        for lk in parsed["links"]:
            pm = re.match(rf"{re.escape(base)}/pages/(\d+)$", lk["href"])
            if not pm or not lk["text"].strip():
                continue
            pid, title = pm.group(1), lk["text"].strip()
            # keep the most specific (longest) label for a page id
            if pid not in seen_pages or len(title) > len(seen_pages[pid]):
                seen_pages[pid] = title
        for pid, title in seen_pages.items():
            conn.execute(
                """INSERT INTO gg_history_pages (portal_id, gg_page_id,
                       page_title, page_kind)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(portal_id, gg_page_id) DO UPDATE SET
                       page_title=excluded.page_title,
                       page_kind=excluded.page_kind""",
                (portal_id, pid, title, classify_page(title)))

        # 2) Standings-kind pages not yet done
        todo = conn.execute(
            f"""SELECT * FROM gg_history_pages
                WHERE portal_id=? AND page_kind IN ({','.join('?'*len(_INGEST_KINDS))})
                  AND (fetch_status IS NULL OR fetch_status != 'done')
                ORDER BY id""",
            (portal_id, *_INGEST_KINDS)).fetchall()

        for page in todo:
            if time.time() - t0 > budget_seconds:
                break
            page_url = f"{base}/pages/{page['gg_page_id']}"
            pg = fetch_public_page(page_url)
            if pg["status_code"] != 200:
                conn.execute("UPDATE gg_history_pages SET fetch_status=? "
                             "WHERE id=?", (f"http_{pg['status_code']}",
                                            page["id"]))
                continue
            # widget discovery: the page names its own widget in an iframe
            im = _IFRAME_WIDGET_RE.search(pg["html"])
            candidates = []
            if im:
                src = im.group(1)
                if src.startswith("/"):
                    src = base + src
                candidates.append((src, im.group(2)))
            if league_id:
                for wt in ("season_points_v2", "season_points"):
                    candidates.append((
                        f"{base}/leagues/{league_id}/widgets/{wt}"
                        f"?page_id={page['gg_page_id']}&shared=false", wt))

            got = None
            for wurl, wtype in candidates:
                if wtype == "images":
                    got = ("images", wurl, None, [])
                    break
                w = fetch_public_page(wurl)
                if w["status_code"] != 200:
                    continue
                wp = parse_page_structure(w["html"], w["final_url"])
                if wp["tables"]:
                    got = (wtype, wurl, w["html"], wp["tables"])
                    break
            if got is None:
                conn.execute(
                    "UPDATE gg_history_pages SET fetch_status='no_widget_data',"
                    " fetched_at=datetime('now') WHERE id=?", (page["id"],))
                continue

            wtype, wurl, whtml, tables = got
            raw_id = _archive_raw(conn, wurl, whtml) if whtml else None

            # idempotent re-import: replace this page's standings rows
            conn.execute("DELETE FROM gg_history_standings WHERE page_id=?",
                         (page["id"],))
            page_rows = 0
            for tbl in tables:
                for rec in parse_standings_table(tbl):
                    cid = _resolve_identity(conn, portal_id,
                                            rec["player_name"])
                    conn.execute(
                        """INSERT INTO gg_history_standings
                               (page_id, contest_label, season, chapter,
                                position, player_name, customer_id, points,
                                money_cents, raw_row)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (page["id"], page["page_title"], portal["season"],
                         portal["chapter"], rec["position"],
                         rec["player_name"], cid, rec["points"],
                         rec["money_cents"], rec["raw_row"]))
                    page_rows += 1
                    stats["matched" if cid else "pending"] += 1
            conn.execute(
                """UPDATE gg_history_pages SET widget_type=?,
                       raw_archive_id=?, fetch_status='done',
                       fetched_at=datetime('now') WHERE id=?""",
                (wtype, raw_id, page["id"]))
            stats["pages_done"] += 1
            stats["rows"] += page_rows
            conn.commit()  # durable per page — a crash never loses a page
            time.sleep(1.0)  # polite pacing — never look like a load problem

        remaining = conn.execute(
            f"""SELECT COUNT(*) FROM gg_history_pages
                WHERE portal_id=? AND page_kind IN ({','.join('?'*len(_INGEST_KINDS))})
                  AND (fetch_status IS NULL OR fetch_status != 'done')""",
            (portal_id, *_INGEST_KINDS)).fetchone()[0]
        conn.commit()  # page catalog + portal ids even if no page ingested
        stats["pages_remaining"] = remaining
        stats["league_id"] = league_id
        stats["elapsed_s"] = round(time.time() - t0, 1)
        return stats


def gg_history_status(db_path=None) -> dict:
    """Coverage/progress across the registry."""
    from email_parser.database import _connect, DB_PATH
    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        portals = conn.execute(
            """SELECT p.subdomain, p.season, p.brand, p.status, p.league_id,
                      COUNT(g.id) AS pages,
                      SUM(CASE WHEN g.fetch_status='done' THEN 1 ELSE 0 END)
                          AS pages_done
               FROM gg_history_portals p
               LEFT JOIN gg_history_pages g ON g.portal_id = p.id
               GROUP BY p.id ORDER BY p.season DESC, p.subdomain""").fetchall()
        rows = conn.execute(
            "SELECT COUNT(*), COUNT(customer_id) FROM gg_history_standings"
        ).fetchone()
        pending = conn.execute(
            "SELECT COUNT(*) FROM gg_history_name_links "
            "WHERE matched_by='pending' AND reviewed=0").fetchone()[0]
        return {
            "standings_rows": rows[0],
            "rows_identity_linked": rows[1],
            "names_pending_review": pending,
            "portals": [dict(p) for p in portals],
        }


# ── Master roster ingest (Kerry-directed 2026-07-11: "master roster first") ─
#
# Seed file: email_parser/data/gg_master_roster_v6.csv — trimmed from
# Kerry's GG admin export (The_Golf_Fellowship_Golfer_Spreadsheet_V6.xlsx,
# 1,089 golfers). Columns kept: gg_id (unique GG member id), handle (the
# EXACT "LAST, First" string GG prints in standings tables — the join
# key), email, affiliation, start_year, member_guest. Phones/DOBs were
# deliberately NOT committed; they stay in Kerry's xlsx and can layer in
# later through the review UI.

_ROSTER_FILE = "data/gg_master_roster_v6.csv"


def ensure_gg_member_map(conn) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS gg_member_map (
        gg_member_id TEXT PRIMARY KEY,
        customer_id  INTEGER REFERENCES customers(customer_id),
        handle       TEXT,
        email        TEXT,
        affiliation  TEXT,
        start_year   TEXT,
        member_guest TEXT,
        matched_by   TEXT,
        created_at   TEXT DEFAULT (datetime('now')))""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gg_member_map_cid "
                 "ON gg_member_map(customer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gg_member_map_handle "
                 "ON gg_member_map(handle)")


def _load_roster_rows():
    import csv
    from pathlib import Path
    path = Path(__file__).parent / _ROSTER_FILE
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def roster_ingest(apply: bool = False, db_path=None) -> dict:
    """Match the master roster to customers; report first, write on apply.

    Cascade per golfer: email → customers.customer_email /
    customer_emails (exact, case-insensitive) → handle through the
    scoring resolver (_resolve_scoring_player handles "LAST, First" +
    suffixes + curated links). NEVER creates customers. On apply=True:
    upserts gg_member_map, then backfills gg_history_standings rows and
    gg_history_name_links whose names now resolve through the map.
    """
    from email_parser.database import _connect, DB_PATH, _resolve_scoring_player
    rows = _load_roster_rows()
    rep = {"roster_rows": len(rows), "email_matched": 0, "handle_matched": 0,
           "unmatched": 0, "unmatched_members": [], "apply": apply}
    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        ensure_gg_member_map(conn)

        # Emails live ONLY in customer_emails (customers has no email
        # column). Primary emails win map collisions via the ORDER BY.
        email_map = {}
        for r in conn.execute(
                "SELECT customer_id, email FROM customer_emails "
                "WHERE email IS NOT NULL AND email != '' "
                "ORDER BY is_primary DESC"):
            email_map.setdefault(r["email"].strip().lower(),
                                 r["customer_id"])

        matches = []
        for g in rows:
            cid, how = None, None
            em = (g.get("email") or "").strip().lower()
            if em and em in email_map:
                cid, how = email_map[em], "email"
                rep["email_matched"] += 1
            else:
                handle = (g.get("handle") or "").strip()
                if handle:
                    try:
                        cid = _resolve_scoring_player(conn, handle)
                    except Exception:
                        cid = None
                if cid is not None:
                    how = "handle"
                    rep["handle_matched"] += 1
                else:
                    rep["unmatched"] += 1
                    aff = (g.get("affiliation") or "").strip()
                    if aff.startswith("TGF") or aff == "Former":
                        rep["unmatched_members"].append(
                            f"{g.get('handle')} <{g.get('email') or 'no email'}>"
                            f" [{aff}]")
            matches.append((g, cid, how))

        rep["unmatched_member_count"] = len(rep["unmatched_members"])
        rep["unmatched_members"] = rep["unmatched_members"][:60]

        if not apply:
            return rep

        for g, cid, how in matches:
            conn.execute(
                """INSERT INTO gg_member_map (gg_member_id, customer_id,
                       handle, email, affiliation, start_year, member_guest,
                       matched_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(gg_member_id) DO UPDATE SET
                       customer_id=COALESCE(excluded.customer_id,
                                            gg_member_map.customer_id),
                       handle=excluded.handle, email=excluded.email,
                       affiliation=excluded.affiliation,
                       start_year=excluded.start_year,
                       member_guest=excluded.member_guest,
                       matched_by=COALESCE(excluded.matched_by,
                                           gg_member_map.matched_by)""",
                (g.get("gg_id"), cid, g.get("handle"), g.get("email"),
                 g.get("affiliation"), g.get("start_year"),
                 g.get("member_guest"), how))

        # Backfill: standings rows + name-links that the map now resolves
        backfilled = conn.execute(
            """UPDATE gg_history_standings SET customer_id = (
                   SELECT m.customer_id FROM gg_member_map m
                   WHERE m.handle = gg_history_standings.player_name
                     AND m.customer_id IS NOT NULL)
               WHERE customer_id IS NULL AND EXISTS (
                   SELECT 1 FROM gg_member_map m
                   WHERE m.handle = gg_history_standings.player_name
                     AND m.customer_id IS NOT NULL)""").rowcount
        relinked = conn.execute(
            """UPDATE gg_history_name_links SET
                   customer_id = (SELECT m.customer_id FROM gg_member_map m
                                  WHERE m.handle = gg_history_name_links.raw_name
                                    AND m.customer_id IS NOT NULL),
                   matched_by = 'roster'
               WHERE matched_by = 'pending' AND EXISTS (
                   SELECT 1 FROM gg_member_map m
                   WHERE m.handle = gg_history_name_links.raw_name
                     AND m.customer_id IS NOT NULL)""").rowcount
        conn.commit()
        rep["standings_backfilled"] = backfilled
        rep["name_links_resolved"] = relinked
        rep["map_rows"] = conn.execute(
            "SELECT COUNT(*) FROM gg_member_map").fetchone()[0]
        return rep
