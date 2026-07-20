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

Never create customers implicitly: unmatched names become 'pending'
rows in gg_history_name_links, not shell profiles. ONE Kerry-directed
exception ("Absolutely yes, create them", 2026-07-11):
roster_create_members() creates profiles for the roster's unmatched
TGF/Former members — an explicit, bounded, admin-invoked operation.
Guests/Facebook Leads/Interest are never created.
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
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_name     TEXT NOT NULL,
        portal_id    INTEGER REFERENCES gg_history_portals(id),
        customer_id  INTEGER REFERENCES customers(customer_id),
        matched_by   TEXT NOT NULL,
        reviewed     INTEGER DEFAULT 0,
        gg_member_id TEXT NOT NULL DEFAULT '',
        UNIQUE(raw_name, portal_id, gg_member_id))""")
    _rebuild_name_links_3col(conn)
    # #123-amendment columns (retrofitted on prod in v2.73.1; ALTERs keep
    # fresh databases shape-identical)
    for ddl in (
        "ALTER TABLE gg_history_standings ADD COLUMN position_raw TEXT",
        "ALTER TABLE gg_history_standings ADD COLUMN contest_kind TEXT",
    ):
        try:
            conn.execute(ddl)
        except Exception:
            pass  # already present
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ggh_standings_cid "
                 "ON gg_history_standings(customer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ggh_standings_page "
                 "ON gg_history_standings(page_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ggh_results_cid "
                 "ON gg_history_results(customer_id)")


def _rebuild_name_links_3col(conn) -> None:
    """#123 amendment (b), deferred from v2.73.1 to the review-UI build:
    rebuild gg_history_name_links so uniqueness is (raw_name, portal_id,
    gg_member_id) — the same printed name CAN be two people when their GG
    member ids differ (the Kryszak class). gg_member_id becomes NOT NULL
    DEFAULT '' (SQLite treats NULLs as distinct in UNIQUE — '' keeps the
    no-id case deduped). Idempotent: detects the old shape via the
    column's notnull flag and rebuilds once, preserving row ids."""
    cols = {r["name"]: r for r in
            conn.execute("PRAGMA table_info(gg_history_name_links)")}
    gid = cols.get("gg_member_id")
    if gid is not None and gid["notnull"]:
        return  # already the 3-col shape
    # Recover from an interrupted attempt: python-sqlite3 runs CREATE
    # TABLE in autocommit but the INSERT below opens a transaction — a
    # caller that closed without committing (read-only paths) left the
    # empty _v2 shell committed while the copy/drop/rename rolled back.
    conn.execute("DROP TABLE IF EXISTS gg_history_name_links_v2")
    conn.execute("""CREATE TABLE gg_history_name_links_v2 (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_name     TEXT NOT NULL,
        portal_id    INTEGER REFERENCES gg_history_portals(id),
        customer_id  INTEGER REFERENCES customers(customer_id),
        matched_by   TEXT NOT NULL,
        reviewed     INTEGER DEFAULT 0,
        gg_member_id TEXT NOT NULL DEFAULT '',
        UNIQUE(raw_name, portal_id, gg_member_id))""")
    src_gid = "COALESCE(gg_member_id, '')" if gid is not None else "''"
    conn.execute(f"""INSERT INTO gg_history_name_links_v2
                         (id, raw_name, portal_id, customer_id, matched_by,
                          reviewed, gg_member_id)
                     SELECT id, raw_name, portal_id, customer_id, matched_by,
                            reviewed, {src_gid}
                     FROM gg_history_name_links""")
    conn.execute("DROP TABLE gg_history_name_links")
    conn.execute("ALTER TABLE gg_history_name_links_v2 "
                 "RENAME TO gg_history_name_links")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ggh_namelinks_ggid "
                 "ON gg_history_name_links(gg_member_id)")
    # commit HERE, unconditionally: read-only callers never commit, and a
    # rolled-back rebuild strands the committed _v2 shell (see above)
    conn.commit()
    logger.info("gg_history_name_links rebuilt to 3-col uniqueness "
                "(raw_name, portal_id, gg_member_id)")


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
    Records the outcome in gg_history_name_links (idempotent). The
    preferred match key (gg_member_id, #123 amendment b) is stamped when
    the printed handle maps to exactly one master-roster member; ''
    otherwise. Reviewed rows (Kerry's manual decisions) are never
    overwritten by later automated passes."""
    from email_parser.database import _resolve_scoring_player
    cid, how = None, "scoring_cascade"
    try:
        cid = _resolve_scoring_player(conn, name)
    except Exception:
        cid = None
    if cid is None:
        # roster map: the printed handle IS the roster handle; trust it
        # only when it maps to exactly one customer (collision-safe)
        try:
            rows = conn.execute(
                """SELECT DISTINCT customer_id FROM gg_member_map
                   WHERE handle = ? AND customer_id IS NOT NULL""",
                (name,)).fetchall()
            if len(rows) == 1:
                cid, how = rows[0][0], "roster"
        except Exception:
            pass
    if cid is None:
        # an earlier ruling (manual or automated) for this name+portal
        got = conn.execute(
            """SELECT customer_id, matched_by FROM gg_history_name_links
               WHERE raw_name = ? AND portal_id = ?
                 AND customer_id IS NOT NULL LIMIT 1""",
            (name, portal_id)).fetchone()
        if got:
            cid, how = got["customer_id"], got["matched_by"]
    gid = ""
    try:
        rows = conn.execute(
            """SELECT DISTINCT gg_member_id FROM gg_member_map
               WHERE handle = ? AND gg_member_id NOT LIKE '%:%'""",
            (name,)).fetchall()
        if len(rows) == 1:
            gid = rows[0][0] or ""
    except Exception:
        pass  # map table may not exist on a bare Phase-A ingest
    conn.execute(
        """INSERT INTO gg_history_name_links (raw_name, portal_id,
               customer_id, matched_by, gg_member_id)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(raw_name, portal_id, gg_member_id) DO UPDATE SET
               customer_id=COALESCE(excluded.customer_id,
                                    gg_history_name_links.customer_id),
               matched_by=CASE WHEN excluded.customer_id IS NOT NULL
                               THEN excluded.matched_by
                               ELSE gg_history_name_links.matched_by END
           WHERE gg_history_name_links.reviewed = 0""",
        (name, portal_id, cid, how if cid else "pending", gid))
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
        try:
            _sync_pending_action_item(conn)
        except Exception:
            pass  # action_items may not exist on a bare test DB
        conn.commit()  # page catalog + portal ids even if no page ingested
        stats["pages_remaining"] = remaining
        stats["league_id"] = league_id
        stats["elapsed_s"] = round(time.time() - t0, 1)
        return stats


# ── Phase B: hole-by-hole scorecard walk (Kerry's #1 data priority) ──────
#
# Recipe (proven during inventory + POC): the portal's tournament_results
# widget carries the season's full server-side round selector; each
# &round=<round_id> view lists that round's per-tournament boards. The
# ALL Net board carries the full field WITH playing handicaps; ALL Gross
# fills anyone left (the live auto-sync's proven ordering). Cards flow
# through the EXISTING import_gg_scorecards machinery (courses/tees,
# scoring_rounds/scoring_holes, raw archive, cid resolution, verification)
# with round_key=<round_id> (multi-round-day lesson) and round_date joined
# from the export-channel gg_history_events by round_index — archive
# events have no Tracker events row, and without a date the cross-
# tournament dedupe can't scope. Walk state lives in gg_history_pages as
# synthetic 'round:<round_id>' rows (page_kind='event_round') — no new
# tables, resumable, and a zero-card round (postponed events) is marked
# done instead of retrying forever.

_ROUND_SELECT_RE = re.compile(
    r'<select[^>]*name="round"[^>]*>(.*?)</select>', re.S)
_ROUND_OPTION_RE = re.compile(
    r'<option[^>]*value="(\d+)"[^>]*>(.*?)</option>', re.S)
_ROUND_INDEX_RE = re.compile(r"round_index=(\d+)")


def _pick_hole_boards(links: list) -> tuple:
    """(boards_to_import, all_board_labels) from a round page's links.
    Net FIRST (full field with handicaps), then Gross — the live
    auto-sync's proven ordering; prefix match covers 'ALL Net 18',
    'ALL Net 9', 'ALL Gross 18 (back)' etc."""
    v2t = [l for l in links
           if "/v2tournaments/" in (l.get("href") or "")
           and "total_purse" not in l["href"]]
    labels = [(l.get("text") or "").strip() for l in v2t]
    boards = [l for want in ("all net", "all gross") for l in v2t
              if (l.get("text") or "").strip().lower().startswith(want)]
    return boards, labels


def ingest_portal_holes(subdomain: str, budget_seconds: int = 240,
                        db_path=None) -> dict:
    """Phase-B hole-by-hole walk of one portal. Resumable + time-budgeted:
    repeat until rounds_left == 0. Rounds are atomic (budget checked at
    round start; both boards finish once a round begins)."""
    from email_parser.database import (_connect, DB_PATH,
                                       import_gg_scorecards)
    from golf_genius_sync import fetch_public_page, parse_page_structure

    t0 = time.time()
    base = f"https://{subdomain}.golfgenius.com"
    stats = {"subdomain": subdomain, "rounds_done": 0, "cards_imported": 0,
             "cards_replaced": 0, "cards_skipped_dup": 0, "unresolved": 0,
             "discrepancies": 0, "rounds_no_boards": [],
             "rounds_no_date": [], "rounds_detail": []}

    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        ensure_gg_member_map(conn)
        portal = conn.execute(
            "SELECT * FROM gg_history_portals WHERE subdomain = ?",
            (subdomain,)).fetchone()
        if portal is None:
            return {"error": f"unknown portal {subdomain!r} — seed first"}
        portal_id, league_id = portal["id"], portal["league_id"]
        source_tag = f"gg_history:{subdomain}"

        if not league_id:
            home = fetch_public_page(base + "/")
            m = _LEAGUE_ID_RE.search(home.get("html") or "")
            league_id = (m.group(1) or m.group(2)) if m else None
            if not league_id:
                return {"error": "league_id undiscoverable — run "
                                 "ingest=<subdomain> (Phase A) first"}
            conn.execute("UPDATE gg_history_portals SET league_id=? "
                         "WHERE id=?", (league_id, portal_id))
            conn.commit()

        widget_url = (f"{base}/leagues/{league_id}/widgets/"
                      f"tournament_results?shared=false")
        w = fetch_public_page(widget_url)
        if w["status_code"] != 200:
            return {"error": f"tournament_results widget HTTP "
                             f"{w['status_code']}"}
        sel = _ROUND_SELECT_RE.search(w["html"])
        options = _ROUND_OPTION_RE.findall(sel.group(1) if sel else "")
        if not options:
            return {"error": "no round selector in tournament_results "
                             "widget — portal may use a different results "
                             "layout (record for the era playbook)"}
        options = [(rid, " ".join(lbl.split())) for rid, lbl in options]
        options.reverse()  # selector is newest-first; walk chronologically

        # round_index → (date, label) from the export channel (channel 3)
        export_events = {}
        for r in conn.execute(
                """SELECT gg_round_index, event_date, event_label
                   FROM gg_history_events
                   WHERE portal_id=? AND gg_round_index IS NOT NULL""",
                (portal_id,)):
            export_events.setdefault(
                r["gg_round_index"], (r["event_date"], r["event_label"]))

        done = {r["gg_page_id"][len("round:"):] for r in conn.execute(
            """SELECT gg_page_id FROM gg_history_pages
               WHERE portal_id=? AND gg_page_id LIKE 'round:%'
                 AND fetch_status='done'""", (portal_id,))}

        pending = [(rid, lbl) for rid, lbl in options if rid not in done]
        for rid, label in pending:
            if time.time() - t0 > budget_seconds:
                break
            round_url = f"{widget_url}&round={rid}"
            pg = fetch_public_page(round_url)
            if pg["status_code"] != 200:
                stats["rounds_detail"].append(
                    {"round": rid, "error": f"http_{pg['status_code']}"})
                continue
            struct = parse_page_structure(pg["html"], round_url)
            links = struct.get("links") or []
            raw_id = _archive_raw(conn, round_url, pg["html"])
            # release the write lock NOW: import_gg_scorecards opens its
            # own writer connection per board, and WAL still allows only
            # one write txn — holding ours through the board loop would
            # 'database is locked' every card.
            conn.commit()

            ridx = None
            for l in links:
                m = _ROUND_INDEX_RE.search(l.get("href") or "")
                if m:
                    ridx = int(m.group(1))
                    break
            round_date, ev_label = export_events.get(ridx, (None, None))
            if round_date is None and portal["season"]:
                round_date = _export_date(label, portal["season"])
            if round_date is None:
                # No date → the dedupe can't scope; skip rather than
                # double-import, and surface for a manual date ruling.
                stats["rounds_no_date"].append({"round": rid, "label": label})
                conn.execute(
                    """INSERT INTO gg_history_pages (portal_id, gg_page_id,
                           page_title, page_kind, widget_type,
                           raw_archive_id, fetch_status, fetched_at)
                       VALUES (?, ?, ?, 'event_round', 'tournament_results',
                               ?, 'no_date', datetime('now'))
                       ON CONFLICT(portal_id, gg_page_id) DO UPDATE SET
                           page_title=excluded.page_title,
                           fetch_status='no_date',
                           fetched_at=excluded.fetched_at""",
                    (portal_id, f"round:{rid}", label or ev_label, raw_id))
                conn.commit()
                continue

            boards, all_labels = _pick_hole_boards(links)
            detail = {"round": rid, "index": ridx, "date": round_date,
                      "label": ev_label or label, "boards": []}
            if not boards:
                stats["rounds_no_boards"].append(
                    {"round": rid, "label": ev_label or label,
                     "board_labels": all_labels[:12]})
            for l in boards:
                href = l["href"]
                if href.startswith("/"):
                    href = base + href
                try:
                    res = import_gg_scorecards(
                        href, round_key=rid, round_date=round_date,
                        source=source_tag, db_path=db_path or DB_PATH)
                except Exception as exc:
                    detail["boards"].append(
                        {"board": (l.get("text") or "").strip(),
                         "error": str(exc)})
                    continue
                detail["boards"].append(
                    {"board": (l.get("text") or "").strip(),
                     "imported": res.get("imported"),
                     "replaced": res.get("replaced"),
                     "skipped_dup": res.get("skipped_other_tournament"),
                     "unresolved": res.get("unresolved_names"),
                     "discrepancies": len(res.get("discrepancies") or [])})
                stats["cards_imported"] += res.get("imported") or 0
                stats["cards_replaced"] += res.get("replaced") or 0
                stats["cards_skipped_dup"] += \
                    res.get("skipped_other_tournament") or 0
                stats["unresolved"] += res.get("unresolved_names") or 0
                stats["discrepancies"] += len(res.get("discrepancies") or [])

            # identity bookkeeping for the review queue: register this
            # round's unresolved names as pending links, then backfill via
            # the member map (roster handles ARE the printed names) when
            # the handle maps to exactly one customer.
            for r in conn.execute(
                    """SELECT DISTINCT player_name FROM scoring_rounds
                       WHERE gg_league_round_id=? AND source=?
                         AND customer_id IS NULL""", (rid, source_tag)):
                _resolve_identity(conn, portal_id, r["player_name"])
            conn.execute(
                """UPDATE scoring_rounds SET customer_id = (
                       SELECT m.customer_id FROM gg_member_map m
                       WHERE m.handle = scoring_rounds.player_name
                         AND m.customer_id IS NOT NULL
                       GROUP BY m.handle
                       HAVING COUNT(DISTINCT m.customer_id) = 1)
                   WHERE gg_league_round_id=? AND source=?
                     AND customer_id IS NULL
                     AND EXISTS (SELECT 1 FROM gg_member_map m
                                 WHERE m.handle = scoring_rounds.player_name
                                   AND m.customer_id IS NOT NULL)""",
                (rid, source_tag))
            # keep the review queue honest: a pending link whose name the
            # map just resolved must not linger as reviewable
            conn.execute(
                """UPDATE gg_history_name_links SET
                       customer_id = (
                           SELECT m.customer_id FROM gg_member_map m
                           WHERE m.handle = gg_history_name_links.raw_name
                             AND m.customer_id IS NOT NULL
                           GROUP BY m.handle
                           HAVING COUNT(DISTINCT m.customer_id) = 1),
                       matched_by = 'roster'
                   WHERE portal_id=? AND matched_by='pending'
                     AND customer_id IS NULL
                     AND (SELECT COUNT(DISTINCT m.customer_id)
                          FROM gg_member_map m
                          WHERE m.handle = gg_history_name_links.raw_name
                            AND m.customer_id IS NOT NULL) = 1""",
                (portal_id,))

            conn.execute(
                """INSERT INTO gg_history_pages (portal_id, gg_page_id,
                       page_title, page_kind, widget_type, raw_archive_id,
                       fetch_status, fetched_at)
                   VALUES (?, ?, ?, 'event_round', 'tournament_results',
                           ?, 'done', datetime('now'))
                   ON CONFLICT(portal_id, gg_page_id) DO UPDATE SET
                       page_title=excluded.page_title,
                       raw_archive_id=excluded.raw_archive_id,
                       fetch_status='done',
                       fetched_at=excluded.fetched_at""",
                (portal_id, f"round:{rid}", ev_label or label, raw_id))
            conn.commit()  # durable per round
            stats["rounds_done"] += 1
            stats["rounds_detail"].append(detail)
            time.sleep(1.0)  # polite pacing between rounds

        stats["rounds_total"] = len(options)
        stats["rounds_left"] = len(pending) - stats["rounds_done"] \
            - len(stats["rounds_no_date"])
        stats["elapsed_s"] = round(time.time() - t0, 1)
        try:
            stats["names_pending_review"] = _sync_pending_action_item(conn)
            conn.commit()
        except Exception:
            pass  # action_items may not exist on a bare test DB
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


# ── Export-pair ingest (Kerry-directed 2026-07-11: complete 2025+2026 as
#    the proof of concept before moving further back) ─────────────────────
#
# Reads the staged GG admin exports (email_parser/data/gg_exports/
# <prefix>__*.csv — Season Scores 9-sheet pairs + trimmed rosters) into
# gg_history_events (one row per league round) + gg_history_results (one
# row per player per round: gross/net/CH structured; AGS/index/purse/
# points carried in raw_row verbatim + purse/points structured).
# Idempotent per prefix via gg_round_id = 'export:<prefix>:r<N>'.

_EXPORT_DIR = "data/gg_exports"

# prefix → (portal subdomain, season, chapter). 2026 leagues map to the
# LIVE portals (tgf-sa / tgf-austin); hcm2026 has no known public portal
# — a registry row is created with source='export'.
EXPORT_PREFIXES = {
    "sa2026":       ("tgf-sa",            "2026", "San Antonio"),
    "austin2026":   ("tgf-austin",        "2026", "Austin"),
    "hcm2026":      ("hcm2026",           "2026", None),
    "sa2025":       ("tgf-sa2025",        "2025", "San Antonio"),
    "austin2025":   ("tgf-austin2025",    "2025", "Austin"),
    "champ2025":    ("tgf-champ25",       "2025", None),
    "lsc2025":      ("tgf-lonestarcup25", "2025", None),
    "roadtrip2025": ("tgf-roadtrip25",    "2025", None),
}

_MONTH_NUM = {m: i + 1 for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))}


def _export_date(raw: str, season: str):
    """'Sat, Feb 07' + season year → '2026-02-07' (None if unparseable)."""
    m = re.search(r"([A-Z][a-z]{2})\s+(\d{1,2})", str(raw or ""))
    if not m or m.group(1) not in _MONTH_NUM:
        return None
    return f"{season}-{_MONTH_NUM[m.group(1)]:02d}-{int(m.group(2)):02d}"


def _read_export_csv(prefix: str, sheet: str):
    import csv
    from pathlib import Path
    path = Path(__file__).parent / _EXPORT_DIR / f"{prefix}__{sheet}.csv"
    if not path.exists():
        return None
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


def _matrix_by_round(rows):
    """Score-matrix CSV → {player_name: {round_no: cell}} keyed by the
    'Round N' header labels (robust to deleted rounds like SA 2026 R13)."""
    if not rows:
        return {}
    hdr = rows[0]
    round_cols = {}
    for i, h in enumerate(hdr):
        m = re.match(r"Round (\d+)$", str(h).strip())
        if m:
            round_cols[i] = int(m.group(1))
    out = {}
    for r in rows[1:]:
        if not r or not str(r[0]).strip():
            continue
        name = str(r[0]).strip()
        vals = {}
        for i, rn in round_cols.items():
            if i < len(r) and str(r[i]).strip():
                vals[rn] = str(r[i]).strip()
        out[name] = vals
    return out


def ingest_export_pair(prefix: str, db_path=None) -> dict:
    """Ingest one staged export pair. Idempotent (replaces its own rows)."""
    from email_parser.database import _connect, DB_PATH
    if prefix not in EXPORT_PREFIXES:
        return {"error": f"unknown prefix {prefix!r} — known: "
                         f"{sorted(EXPORT_PREFIXES)}"}
    subdomain, season, chapter = EXPORT_PREFIXES[prefix]

    rounds_csv = _read_export_csv(prefix, "league_rounds")
    if rounds_csv is None:
        return {"error": f"no staged CSVs for {prefix} (deploy drift?)"}
    gross = _matrix_by_round(_read_export_csv(prefix, "gross_scores") or [])
    net = _matrix_by_round(_read_export_csv(prefix, "net_scores") or [])
    ags = _matrix_by_round(_read_export_csv(prefix, "adjusted_gross_score") or [])
    ch = _matrix_by_round(_read_export_csv(prefix, "course_handicap_history") or [])
    idx = _matrix_by_round(_read_export_csv(prefix, "handicap_index_history") or [])
    purse = _matrix_by_round(_read_export_csv(prefix, "purse_summary") or [])
    points = _matrix_by_round(_read_export_csv(prefix, "points_summary") or [])
    roster = _read_export_csv(prefix, "roster")

    stats = {"prefix": prefix, "events": 0, "results": 0, "matched": 0,
             "pending": 0, "roster_map_rows": 0}

    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        ensure_gg_member_map(conn)
        portal = conn.execute(
            "SELECT * FROM gg_history_portals WHERE subdomain=?",
            (subdomain,)).fetchone()
        if portal is None:
            conn.execute(
                """INSERT INTO gg_history_portals (subdomain, chapter,
                       season, kind, brand, source, status)
                   VALUES (?, ?, ?, 'season', 'TGF', 'export', 'alive')""",
                (subdomain, chapter, season))
            portal = conn.execute(
                "SELECT * FROM gg_history_portals WHERE subdomain=?",
                (subdomain,)).fetchone()
        portal_id = portal["id"]

        # roster → map enrichment (league-scoped ids are DISTINCT keys)
        if roster and len(roster) > 1:
            hdr = roster[0]
            for r in roster[1:]:
                row = dict(zip(hdr, r))
                if not row.get("league_member_id"):
                    continue
                cid = None
                em = (row.get("email") or "").strip().lower()
                if em:
                    got = conn.execute(
                        "SELECT customer_id FROM customer_emails WHERE "
                        "LOWER(email)=? LIMIT 1", (em,)).fetchone()
                    cid = got["customer_id"] if got else None
                if cid is None and row.get("handle"):
                    got = conn.execute(
                        "SELECT customer_id FROM gg_member_map WHERE "
                        "handle=? AND customer_id IS NOT NULL LIMIT 1",
                        (row["handle"],)).fetchone()
                    cid = got["customer_id"] if got else None
                conn.execute(
                    """INSERT INTO gg_member_map (gg_member_id, customer_id,
                           handle, email, affiliation, start_year,
                           member_guest, matched_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(gg_member_id) DO UPDATE SET
                           customer_id=COALESCE(excluded.customer_id,
                                                gg_member_map.customer_id)""",
                    (f"{prefix}:{row['league_member_id']}", cid,
                     row.get("handle"), row.get("email"),
                     row.get("affiliation"), row.get("start_year"),
                     row.get("member_guest"),
                     "league_roster_email" if (cid and em) else
                     ("league_roster_handle" if cid else "pending")))
                stats["roster_map_rows"] += 1

        # idempotent wipe of this prefix's prior rows
        conn.execute(
            """DELETE FROM gg_history_results WHERE gg_event_id IN (
                   SELECT id FROM gg_history_events
                   WHERE portal_id=? AND gg_round_id LIKE ?)""",
            (portal_id, f"export:{prefix}:%"))
        conn.execute(
            "DELETE FROM gg_history_events WHERE portal_id=? AND "
            "gg_round_id LIKE ?", (portal_id, f"export:{prefix}:%"))

        # league rounds → events
        event_ids = {}
        for r in rounds_csv[1:]:
            if len(r) < 3 or not str(r[0]).strip():
                continue
            try:
                rn = int(float(r[0]))
            except ValueError:
                continue
            cur = conn.execute(
                """INSERT INTO gg_history_events (portal_id, season,
                       chapter, event_label, event_date, brand,
                       gg_round_id, gg_round_index, raw_row)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (portal_id, season, chapter, str(r[1]).strip(),
                 _export_date(r[2], season), portal["brand"],
                 f"export:{prefix}:r{rn}", rn, json.dumps(r)))
            event_ids[rn] = cur.lastrowid
            stats["events"] += 1

        # per-player per-round results
        players = set(gross) | set(net) | set(purse) | set(points)
        for name in sorted(players):
            cid = _resolve_identity(conn, portal_id, name)
            rounds_for = (set(gross.get(name, {})) | set(net.get(name, {}))
                          | set(purse.get(name, {}))
                          | set(points.get(name, {})))
            for rn in sorted(rounds_for):
                if rn not in event_ids:
                    continue
                g = _to_float(gross.get(name, {}).get(rn))
                n = _to_float(net.get(name, {}).get(rn))
                p = _money_to_cents(purse.get(name, {}).get(rn))
                pt = _to_float(points.get(name, {}).get(rn))
                c = _to_float(ch.get(name, {}).get(rn))
                if g is None and n is None and p is None and pt is None:
                    continue
                conn.execute(
                    """INSERT INTO gg_history_results (gg_event_id,
                           game_label, player_name, customer_id,
                           playing_handicap, gross, net, points,
                           money_cents, raw_row)
                       VALUES (?, 'export_round', ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event_ids[rn], name, cid, c, g, n, pt, p,
                     json.dumps({"src": "export", "prefix": prefix,
                                 "round": rn, "gross": g, "net": n,
                                 "ags": _to_float(ags.get(name, {}).get(rn)),
                                 "course_handicap": c,
                                 "index_at_round":
                                     _to_float(idx.get(name, {}).get(rn)),
                                 "purse_cents": p, "points": pt})))
                stats["results"] += 1
                stats["matched" if cid else "pending"] += 1
        conn.commit()
    return stats


def audit_export_pair(prefix: str, db_path=None) -> dict:
    """Parity audit for one ingested export prefix.

    2026 prefixes: per-round gross/net vs scoring_rounds (scraped
    scorecards), joined by customer_id + date. 2025 prefixes: per-player
    export season purse totals vs the money already banked in Phase-A
    standings rows (money_leaders pages), joined by verbatim name — and
    once the Phase-B hole-by-hole walk has banked the season's
    scorecards, the SAME gross/net check the 2026 audit runs (reported
    under "scoring"): the channels prove each other on archive years too.
    """
    from email_parser.database import _connect, DB_PATH
    if prefix not in EXPORT_PREFIXES:
        return {"error": f"unknown prefix {prefix!r}"}
    subdomain, season, chapter = EXPORT_PREFIXES[prefix]
    out = {"prefix": prefix, "checked": 0, "matches": 0, "mismatches": []}

    def scoring_check(conn, sink):
        rows = conn.execute(
            """SELECT r.player_name, r.customer_id, r.gross AS xg,
                      r.net AS xn, e.event_date
               FROM gg_history_results r
               JOIN gg_history_events e ON e.id = r.gg_event_id
               WHERE e.portal_id = (SELECT id FROM gg_history_portals
                                    WHERE subdomain=?)
                 AND e.gg_round_id LIKE ?
                 AND r.customer_id IS NOT NULL AND r.gross IS NOT NULL""",
            (subdomain, f"export:{prefix}:%")).fetchall()
        for r in rows:
            sr = conn.execute(
                """SELECT gross, net FROM scoring_rounds
                   WHERE customer_id=? AND round_date=?""",
                (r["customer_id"], r["event_date"])).fetchall()
            if not sr:
                continue
            sink["checked"] += 1
            ok = any(s["gross"] == r["xg"] and
                     (r["xn"] is None or s["net"] == r["xn"])
                     for s in sr)
            if ok:
                sink["matches"] += 1
            elif len(sink["mismatches"]) < 25:
                sink["mismatches"].append(
                    {"player": r["player_name"], "date": r["event_date"],
                     "export_gross": r["xg"], "export_net": r["xn"],
                     "scraped": [dict(s) for s in sr]})

    with _connect(db_path or DB_PATH) as conn:
        if season == "2026":
            scoring_check(conn, out)
        else:
            sc = {"checked": 0, "matches": 0, "mismatches": []}
            scoring_check(conn, sc)
            if sc["checked"]:
                out["scoring"] = sc
            rows = conn.execute(
                """SELECT r.player_name, SUM(r.money_cents) AS xp
                   FROM gg_history_results r
                   JOIN gg_history_events e ON e.id = r.gg_event_id
                   WHERE e.portal_id = (SELECT id FROM gg_history_portals
                                        WHERE subdomain=?)
                     AND e.gg_round_id LIKE ?
                   GROUP BY r.player_name
                   HAVING xp IS NOT NULL""",
                (subdomain, f"export:{prefix}:%")).fetchall()
            for r in rows:
                st = conn.execute(
                    """SELECT MAX(s.money_cents) AS m
                       FROM gg_history_standings s
                       JOIN gg_history_pages g ON g.id = s.page_id
                       WHERE g.portal_id = (SELECT id FROM gg_history_portals
                                            WHERE subdomain=?)
                         AND g.page_kind='money_leaders'
                         AND s.player_name = ?""",
                    (subdomain, r["player_name"])).fetchone()
                if st is None or st["m"] is None:
                    continue
                out["checked"] += 1
                if st["m"] == r["xp"]:
                    out["matches"] += 1
                elif len(out["mismatches"]) < 25:
                    out["mismatches"].append(
                        {"player": r["player_name"],
                         "export_total_cents": r["xp"],
                         "standings_cents": st["m"]})
    return out


def _handle_to_names(handle: str):
    """'CRONIN, Alex' → ('Alex','Cronin'); preserves mixed-case particles
    (DeBORDE stays; ALL-UPPER words get title-cased). Suffixes after a
    second comma ride with the first name."""
    parts = [p.strip() for p in str(handle or "").split(",")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None, None
    def fix(word_str):
        return " ".join(
            w.title() if w.isupper() else w for w in word_str.split())
    last = fix(parts[0])
    first = fix(" ".join(parts[1:]))
    return first, last


_AFFIL_CHAPTER = {
    "TGF San Antonio": "San Antonio", "TGF San Antonio HC": "San Antonio",
    "TGF Austin": "Austin", "TGF DFW": "DFW", "TGF Houston": "Houston",
}


def roster_create_members(db_path=None) -> dict:
    """Create customer profiles for unmatched TGF/Former roster members
    (Kerry: 'Absolutely yes, create them' — 2026-07-11).

    Master-roster map rows only (league-scoped rows join by handle
    afterwards). Guests/Facebook Leads/Interest are NEVER created. Each
    creation: customers row (status expired_member, source gg_roster) +
    primary GG email + map/standings/results/name-links backfill by
    handle. Idempotent: rows that gained a customer_id are skipped.
    """
    from email_parser.database import _connect, DB_PATH, _resolve_scoring_player
    stats = {"created": 0, "relinked_rows": 0, "skipped_now_matched": 0,
             "standings_linked": 0, "results_linked": 0}
    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_member_map(conn)
        cands = conn.execute(
            """SELECT * FROM gg_member_map
               WHERE customer_id IS NULL
                 AND gg_member_id NOT LIKE '%:%'
                 AND (affiliation LIKE 'TGF%' OR affiliation = 'Former')
               ORDER BY handle""").fetchall()
        for m in cands:
            handle = (m["handle"] or "").strip()
            first, last = _handle_to_names(handle)
            if not first or not last:
                continue
            # someone may have matched since (or an earlier loop pass
            # created the same person under a variant handle)
            try:
                cid = _resolve_scoring_player(conn, handle)
            except Exception:
                cid = None
            if cid is None:
                cur = conn.execute(
                    """INSERT INTO customers (first_name, last_name,
                           chapter, current_player_status,
                           acquisition_source)
                       VALUES (?, ?, ?, 'expired_member', 'gg_roster')""",
                    (first, last, _AFFIL_CHAPTER.get(
                        (m["affiliation"] or "").strip())))
                cid = cur.lastrowid
                if m["email"]:
                    conn.execute(
                        """INSERT INTO customer_emails (customer_id, email,
                               is_primary, is_golf_genius, label)
                           VALUES (?, ?, 1, 1, 'gg_roster')""",
                        (cid, m["email"].strip()))
                stats["created"] += 1
            else:
                stats["skipped_now_matched"] += 1
            n = conn.execute(
                """UPDATE gg_member_map SET customer_id=?,
                       matched_by='roster_created'
                   WHERE handle=? AND customer_id IS NULL""",
                (cid, handle)).rowcount
            stats["relinked_rows"] += n
        # backfill history rows for every newly linked handle
        stats["standings_linked"] = conn.execute(
            """UPDATE gg_history_standings SET customer_id = (
                   SELECT m.customer_id FROM gg_member_map m
                   WHERE m.handle = gg_history_standings.player_name
                     AND m.customer_id IS NOT NULL)
               WHERE customer_id IS NULL AND EXISTS (
                   SELECT 1 FROM gg_member_map m
                   WHERE m.handle = gg_history_standings.player_name
                     AND m.customer_id IS NOT NULL)""").rowcount
        stats["results_linked"] = conn.execute(
            """UPDATE gg_history_results SET customer_id = (
                   SELECT m.customer_id FROM gg_member_map m
                   WHERE m.handle = gg_history_results.player_name
                     AND m.customer_id IS NOT NULL)
               WHERE customer_id IS NULL AND EXISTS (
                   SELECT 1 FROM gg_member_map m
                   WHERE m.handle = gg_history_results.player_name
                     AND m.customer_id IS NOT NULL)""").rowcount
        conn.execute(
            """UPDATE gg_history_name_links SET
                   customer_id = (SELECT m.customer_id FROM gg_member_map m
                                  WHERE m.handle = gg_history_name_links.raw_name
                                    AND m.customer_id IS NOT NULL),
                   matched_by = 'roster_created'
               WHERE customer_id IS NULL AND EXISTS (
                   SELECT 1 FROM gg_member_map m
                   WHERE m.handle = gg_history_name_links.raw_name
                     AND m.customer_id IS NOT NULL)""")
        conn.commit()
    return stats


# ── #123-amendment retrofit + #127 guardrails + #128 enrichment ──────────
# (Kerry's #123 ratification amendments crossed mid-flight with the
#  v2.70.0 build — mailbox #126 requires explicit retrofit before the
#  2024 wave; #127 adds option-b guardrails; #128 directs at-birth
#  contact enrichment from the roster data already held.)

def amendments_123_retrofit(db_path=None) -> dict:
    """Retrofit the three unshipped #123 amendments onto live data.

    (a) position verbatim: ADD gg_history_standings.position_raw TEXT,
        backfilled from raw_row (the verbatim rank cell, e.g. 'T6' —
        raw_row preserved it all along, so nothing was lost).
    (b) identity keys: ADD gg_history_name_links.gg_member_id TEXT
        (preferred match key, backfilled from the master map); true
        name collisions (same handle → multiple customer_ids) FORCED
        to pending. NOTE: the 3-col uniqueness rebuild is deferred to
        the review-UI build (SQLite table rebuild; flagged in the
        mailbox confirm — current writers depend on the 2-col target).
    (c) ADD gg_history_standings.contest_kind TEXT (nullable) +
        (season, chapter) index; customer_id index existed from v2.70.0.
    Plus the #127 guardrail-3 audit: created gg_roster profiles whose
    name collides with a pre-existing customer are flagged for Kerry's
    review lane (never auto-merged, never auto-split).
    """
    from email_parser.database import _connect, DB_PATH
    rep = {"position_raw_backfilled": 0, "gg_member_id_backfilled": 0,
           "collisions_forced_pending": 0, "dup_name_review": []}
    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        ensure_gg_member_map(conn)
        for ddl in (
            "ALTER TABLE gg_history_standings ADD COLUMN position_raw TEXT",
            "ALTER TABLE gg_history_standings ADD COLUMN contest_kind TEXT",
            "ALTER TABLE gg_history_name_links ADD COLUMN gg_member_id TEXT",
        ):
            try:
                conn.execute(ddl)
            except Exception:
                pass  # already applied
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ggh_standings_season "
                     "ON gg_history_standings(season, chapter)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ggh_namelinks_ggid "
                     "ON gg_history_name_links(gg_member_id)")

        # (a) verbatim rank backfill from raw_row
        rows = conn.execute(
            "SELECT id, position, raw_row FROM gg_history_standings "
            "WHERE position_raw IS NULL").fetchall()
        for r in rows:
            verbatim = None
            try:
                cells = json.loads(r["raw_row"])
                for c in cells:
                    s = str(c).strip()
                    if re.fullmatch(r"T?\d+", s) and _rank_to_int(s) == r["position"]:
                        verbatim = s
                        break
            except Exception:
                pass
            conn.execute(
                "UPDATE gg_history_standings SET position_raw=? WHERE id=?",
                (verbatim if verbatim is not None else
                 (str(r["position"]) if r["position"] is not None else None),
                 r["id"]))
            rep["position_raw_backfilled"] += 1

        # (b) preferred key backfill + collision forcing
        rep["gg_member_id_backfilled"] = conn.execute(
            """UPDATE gg_history_name_links SET gg_member_id = (
                   SELECT m.gg_member_id FROM gg_member_map m
                   WHERE m.handle = gg_history_name_links.raw_name
                     AND m.gg_member_id NOT LIKE '%:%')
               WHERE gg_member_id IS NULL""").rowcount
        collisions = conn.execute(
            """SELECT handle FROM gg_member_map
               WHERE customer_id IS NOT NULL AND handle IS NOT NULL
               GROUP BY handle HAVING COUNT(DISTINCT customer_id) > 1"""
        ).fetchall()
        for c in collisions:
            n = conn.execute(
                """UPDATE gg_history_name_links
                   SET matched_by='pending', customer_id=NULL
                   WHERE raw_name=? AND matched_by != 'pending'""",
                (c["handle"],)).rowcount
            rep["collisions_forced_pending"] += n

        # #127 guardrail 3: dup-name review lane for created profiles
        dups = conn.execute(
            """SELECT c.customer_id, c.first_name, c.last_name
               FROM customers c
               WHERE c.acquisition_source='gg_roster' AND EXISTS (
                   SELECT 1 FROM customers o
                   WHERE o.customer_id != c.customer_id
                     AND LOWER(o.first_name)=LOWER(c.first_name)
                     AND LOWER(o.last_name)=LOWER(c.last_name))""").fetchall()
        for d in dups:
            conn.execute(
                """UPDATE gg_member_map SET matched_by='review_dup_name'
                   WHERE customer_id=?""", (d["customer_id"],))
            rep["dup_name_review"].append(
                f"#{d['customer_id']} {d['first_name']} {d['last_name']}")
        conn.commit()
    return rep


def enrich_created_members(db_path=None) -> dict:
    """#128: fill phone + DOB on gg_roster-created profiles from the
    roster contact file. Never overwrites existing values; only touches
    acquisition_source='gg_roster' profiles (born tonight, all-NULL)."""
    import csv as _csv
    from pathlib import Path
    from email_parser.database import _connect, DB_PATH
    path = Path(__file__).parent / "data/gg_master_roster_v6_contact.csv"
    rep = {"phones_set": 0, "dobs_set": 0}
    with open(path, newline="", encoding="utf-8") as fh:
        contacts = {r["handle"]: r for r in _csv.DictReader(fh)}
    with _connect(db_path or DB_PATH) as conn:
        try:
            conn.execute("ALTER TABLE customers ADD COLUMN date_of_birth TEXT")
        except Exception:
            pass
        rows = conn.execute(
            """SELECT c.customer_id, m.handle
               FROM customers c
               JOIN gg_member_map m ON m.customer_id = c.customer_id
                    AND m.gg_member_id NOT LIKE '%:%'
               WHERE c.acquisition_source='gg_roster'""").fetchall()
        for r in rows:
            ct = contacts.get(r["handle"])
            if not ct:
                continue
            if ct.get("cell_phone"):
                n = conn.execute(
                    """UPDATE customers SET phone=?
                       WHERE customer_id=? AND (phone IS NULL OR phone='')""",
                    (ct["cell_phone"], r["customer_id"])).rowcount
                rep["phones_set"] += n
            if ct.get("dob"):
                n = conn.execute(
                    """UPDATE customers SET date_of_birth=?
                       WHERE customer_id=? AND (date_of_birth IS NULL
                                                OR date_of_birth='')""",
                    (ct["dob"], r["customer_id"])).rowcount
                rep["dobs_set"] += n
        conn.commit()
    return rep


# ── Phase B: per-game money walk ─────────────────────────────────────────
#
# Each round's per-tournament boards (INDIVIDUAL Net $, SKINS $, TEAM Net
# $, MVP $, Closest to Pin, …) carry that game's results WITH purses —
# the per-game money breakdown only Channel 1 has. Rows land in
# gg_history_results with the verbatim board label as game_label,
# attached to the SAME gg_history_events row the export channel created
# (matched by round_index) so export rows (game_label='export_round')
# and scrape rows sit side by side per event. ALL Net/ALL Gross boards
# are the hole-by-hole walk's job; Adjustments and the purse-summary
# link are skipped.

_GAMES_SKIP_RE = re.compile(r"^(all net|all gross|adjustments?)", re.I)


def _results_rows_from_tables(tables: list) -> list:
    """Generalized leaderboard parse: any table with a Player/Winner/Team
    header column yields result rows (verbatim raw_row + parsed fields).
    Single-cell rows (flight section headings) are skipped — flight
    membership is a separate concern."""
    out = []
    for t in tables or []:
        if not t or len(t) < 2:
            continue
        hdr_i = None
        for i, row in enumerate(t):
            low = [str(c).strip().lower() for c in row]
            if any(h in ("player", "players", "winner", "team", "name")
                   or "player" in h for h in low):
                hdr_i = i
                break
        if hdr_i is None:
            continue
        header = [str(c).strip().lower() for c in t[hdr_i]]

        def col(*needles, exclude=()):
            for i, h in enumerate(header):
                if any(n in h for n in needles) \
                        and not any(x in h for x in exclude):
                    return i
            return None

        c_player = col("player", "winner", "team", "name")
        c_pos = col("pos", "rank", "place")
        c_ph = col("handicap")
        c_gross = col("gross", exclude=("avg",))
        c_net = col("net", exclude=("avg", "to par"))
        c_points = col("point", exclude=("behind",))
        c_purse = col("purse", "money", "winnings")

        for row in t[hdr_i + 1:]:
            cells = [str(c).strip() for c in row]
            if len([c for c in cells if c]) <= 1:
                continue  # section heading / separator
            def cell(i):
                return cells[i] if i is not None and i < len(cells) else None
            name = cell(c_player)
            if not name or name.lower().startswith(("total", "hole")):
                continue
            is_team = bool(re.search(r"\s[+&/]\s", name))
            out.append({
                "player_name": name,
                "team_label": name if is_team else None,
                "position": cell(c_pos),
                "playing_handicap": _to_float(cell(c_ph)),
                "gross": _to_float(cell(c_gross)),
                "net": _to_float(cell(c_net)),
                "points": _to_float(cell(c_points)),
                "money_cents": _money_to_cents(cell(c_purse)),
                "raw_row": json.dumps(row),
            })
    return out


def ingest_portal_games(subdomain: str, budget_seconds: int = 240,
                        db_path=None) -> dict:
    """Phase-B per-game money walk of one portal. Resumable (walk state =
    gg_history_pages 'games:<round_id>' rows); repeat until
    rounds_left == 0. Rounds are atomic."""
    from email_parser.database import _connect, DB_PATH
    from golf_genius_sync import fetch_public_page, parse_page_structure

    t0 = time.time()
    base = f"https://{subdomain}.golfgenius.com"
    stats = {"subdomain": subdomain, "rounds_done": 0, "rows": 0,
             "boards": 0, "matched": 0, "pending": 0, "rounds_detail": []}

    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        ensure_gg_member_map(conn)
        portal = conn.execute(
            "SELECT * FROM gg_history_portals WHERE subdomain = ?",
            (subdomain,)).fetchone()
        if portal is None:
            return {"error": f"unknown portal {subdomain!r} — seed first"}
        portal_id, league_id = portal["id"], portal["league_id"]
        if not league_id:
            return {"error": "league_id unknown — run Phase A first"}

        widget_url = (f"{base}/leagues/{league_id}/widgets/"
                      f"tournament_results?shared=false")
        w = fetch_public_page(widget_url)
        if w["status_code"] != 200:
            return {"error": f"widget HTTP {w['status_code']}"}
        sel = _ROUND_SELECT_RE.search(w["html"])
        options = _ROUND_OPTION_RE.findall(sel.group(1) if sel else "")
        if not options:
            return {"error": "no round selector"}
        options = [(rid, " ".join(lbl.split())) for rid, lbl in options]
        options.reverse()

        export_events = {}
        for r in conn.execute(
                """SELECT id, gg_round_index, event_date, event_label
                   FROM gg_history_events
                   WHERE portal_id=? AND gg_round_index IS NOT NULL""",
                (portal_id,)):
            export_events.setdefault(r["gg_round_index"], dict(r))

        done = {r["gg_page_id"][len("games:"):] for r in conn.execute(
            """SELECT gg_page_id FROM gg_history_pages
               WHERE portal_id=? AND gg_page_id LIKE 'games:%'
                 AND fetch_status='done'""", (portal_id,))}

        pending = [(rid, lbl) for rid, lbl in options if rid not in done]
        for rid, label in pending:
            if time.time() - t0 > budget_seconds:
                break
            round_url = f"{widget_url}&round={rid}"
            pg = fetch_public_page(round_url)
            if pg["status_code"] != 200:
                stats["rounds_detail"].append(
                    {"round": rid, "error": f"http_{pg['status_code']}"})
                continue
            links = (parse_page_structure(pg["html"], round_url)
                     .get("links") or [])
            ridx = None
            for l in links:
                m = _ROUND_INDEX_RE.search(l.get("href") or "")
                if m:
                    ridx = int(m.group(1))
                    break
            boards = [l for l in links
                      if "/v2tournaments/" in (l.get("href") or "")
                      and "total_purse" not in l["href"]
                      and not _GAMES_SKIP_RE.match(
                          (l.get("text") or "").strip())]
            detail = {"round": rid, "index": ridx, "boards": []}

            # FETCH phase first — no open write txn across network I/O
            # (the holes bg-walk may be writing concurrently; WAL allows
            # one writer and the default busy timeout is short)
            fetched = []
            for l in boards:
                href = l["href"]
                if href.startswith("/"):
                    href = base + href
                blabel = (l.get("text") or "").strip()
                b = fetch_public_page(href)
                if b["status_code"] != 200:
                    detail["boards"].append(
                        {"board": blabel, "error": f"http_{b['status_code']}"})
                    continue
                fetched.append((blabel, href, b["html"]))
                time.sleep(0.3)

            # WRITE phase — short transaction
            ev = export_events.get(ridx)
            if ev is None:
                cur = conn.execute(
                    """INSERT INTO gg_history_events (portal_id, season,
                           chapter, event_label, event_date, brand,
                           gg_round_id, gg_round_index, raw_row)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (portal_id, portal["season"], portal["chapter"], label,
                     _export_date(label, portal["season"] or ""),
                     portal["brand"], str(rid), ridx,
                     json.dumps({"src": "games_walk", "label": label})))
                ev_id = cur.lastrowid
                if ridx is not None:
                    export_events[ridx] = {"id": ev_id}
            else:
                ev_id = ev["id"]
            # idempotent per event: scrape rows replaced, export rows kept
            conn.execute(
                """DELETE FROM gg_history_results
                   WHERE gg_event_id=? AND game_label != 'export_round'""",
                (ev_id,))
            for blabel, href, html in fetched:
                _archive_raw(conn, href, html)
                rows = _results_rows_from_tables(
                    parse_page_structure(html, href).get("tables") or [])
                for rec in rows:
                    cid = None
                    if not rec["team_label"]:
                        cid = _resolve_identity(conn, portal_id,
                                                rec["player_name"])
                    conn.execute(
                        """INSERT INTO gg_history_results (gg_event_id,
                               game_label, player_name, customer_id,
                               team_label, position, playing_handicap,
                               gross, net, points, money_cents, raw_row)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (ev_id, blabel, rec["player_name"], cid,
                         rec["team_label"], rec["position"],
                         rec["playing_handicap"], rec["gross"], rec["net"],
                         rec["points"], rec["money_cents"], rec["raw_row"]))
                    stats["rows"] += 1
                    stats["matched" if cid else "pending"] += 1
                stats["boards"] += 1
                detail["boards"].append({"board": blabel, "rows": len(rows)})

            conn.execute(
                """INSERT INTO gg_history_pages (portal_id, gg_page_id,
                       page_title, page_kind, widget_type, fetch_status,
                       fetched_at)
                   VALUES (?, ?, ?, 'event_games', 'tournament_results',
                           'done', datetime('now'))
                   ON CONFLICT(portal_id, gg_page_id) DO UPDATE SET
                       page_title=excluded.page_title, fetch_status='done',
                       fetched_at=excluded.fetched_at""",
                (portal_id, f"games:{rid}", label))
            conn.commit()
            stats["rounds_done"] += 1
            stats["rounds_detail"].append(detail)
            time.sleep(1.0)

        stats["rounds_total"] = len(options)
        stats["rounds_left"] = len(pending) - stats["rounds_done"]
        stats["elapsed_s"] = round(time.time() - t0, 1)
        try:
            stats["names_pending_review"] = _sync_pending_action_item(conn)
            conn.commit()
        except Exception:
            pass
        return stats


# ── Review UI backend (admin page /admin/gg-history) ─────────────────────
# Kerry's identity review queue: every pending name gets a human ruling —
# link to a customer, mark guest (never auto-created), or not-a-person
# (parse artifacts, team labels). Decisions are reviewed=1 rows that no
# automated pass may overwrite (_resolve_identity guards on reviewed=0).

_REVIEW_ACTION_SUBJECT = "GG History: names pending identity review"


def _sync_pending_action_item(conn) -> int:
    """Keep ONE aggregate COO action item in step with the pending count
    (121 names must not become 121 items). Returns the pending count."""
    n = conn.execute(
        "SELECT COUNT(*) FROM gg_history_name_links "
        "WHERE matched_by='pending' AND reviewed=0").fetchone()[0]
    open_item = conn.execute(
        "SELECT id FROM action_items WHERE subject=? AND status='open'",
        (_REVIEW_ACTION_SUBJECT,)).fetchone()
    if n:
        summary = (f"{n} player names from the GG archive await identity "
                   f"review at /admin/gg-history — link each to a customer, "
                   f"or mark it guest / not-a-person. Mostly guests; "
                   f"decisions backfill all banked history rows.")
        if open_item:
            conn.execute("UPDATE action_items SET summary=? WHERE id=?",
                         (summary, open_item["id"]))
        else:
            conn.execute(
                """INSERT INTO action_items (subject, from_name, summary,
                       urgency, category)
                   VALUES (?, 'GG History review queue', ?, 'low',
                           'scoring')""",
                (_REVIEW_ACTION_SUBJECT, summary))
    elif open_item:
        conn.execute(
            """UPDATE action_items SET status='completed',
                   completed_at=datetime('now'),
                   completed_by='gg-history-review'
               WHERE id=?""", (open_item["id"],))
    return n


def review_queue(db_path=None, limit: int = 300) -> dict:
    """The pending-names queue with per-name context + candidate matches."""
    from email_parser.database import _connect, DB_PATH
    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        ensure_gg_member_map(conn)
        rows = conn.execute(
            """SELECT l.id, l.raw_name, l.gg_member_id, l.portal_id,
                      p.subdomain, p.season, p.chapter, p.brand,
                      (SELECT COUNT(*) FROM gg_history_standings s
                       JOIN gg_history_pages g ON g.id = s.page_id
                       WHERE g.portal_id = l.portal_id
                         AND s.player_name = l.raw_name) AS standings_rows,
                      (SELECT COUNT(*) FROM gg_history_results r
                       JOIN gg_history_events e ON e.id = r.gg_event_id
                       WHERE e.portal_id = l.portal_id
                         AND r.player_name = l.raw_name) AS result_rows,
                      (SELECT COUNT(*) FROM scoring_rounds sr
                       WHERE sr.player_name = l.raw_name
                         AND sr.source = 'gg_history:' || p.subdomain)
                          AS hole_rounds,
                      (SELECT m.affiliation FROM gg_member_map m
                       WHERE m.handle = l.raw_name LIMIT 1) AS affiliation
               FROM gg_history_name_links l
               LEFT JOIN gg_history_portals p ON p.id = l.portal_id
               WHERE l.matched_by = 'pending' AND l.reviewed = 0
                 AND l.raw_name NOT LIKE 'Bl[%'
               ORDER BY (standings_rows + result_rows + hole_rounds) DESC,
                        l.raw_name
               LIMIT ?""", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            first, last = _handle_to_names(r["raw_name"])
            cands = []
            if last:
                # customer_name carries the display suffix (Jr/III) that
                # first/last don't — required to tell the Ariases apart.
                cands = [dict(c) for c in conn.execute(
                    f"""SELECT c.customer_id, c.first_name, c.last_name,
                               c.chapter, c.current_player_status,
                               {_DISPLAY_NAME_SQL}
                        FROM customers c
                        WHERE LOWER(c.last_name) = LOWER(?)
                        ORDER BY c.customer_id LIMIT 6""", (last,))]
            d["candidates"] = cands
            out.append(d)
        total = conn.execute(
            "SELECT COUNT(*) FROM gg_history_name_links "
            "WHERE matched_by='pending' AND reviewed=0 "
            "AND raw_name NOT LIKE 'Bl[%'").fetchone()[0]
        # Blind-draw entries ("Bl[NAME, First]") are set aside, not shown
        # and not dismissed (Kerry 2026-07-20): they stay pending in the
        # table so their rows survive, but the queue skips them.
        blinds = conn.execute(
            "SELECT COUNT(*) FROM gg_history_name_links "
            "WHERE matched_by='pending' AND reviewed=0 "
            "AND raw_name LIKE 'Bl[%'").fetchone()[0]
        reviewed = conn.execute(
            """SELECT matched_by, COUNT(*) AS n FROM gg_history_name_links
               WHERE reviewed=1 GROUP BY matched_by""").fetchall()
        return {"pending_total": total, "shown": len(out), "names": out,
                "blind_set_aside": blinds,
                "reviewed_counts": {r["matched_by"]: r["n"]
                                    for r in reviewed}}


def resolve_name_link(link_id: int, action: str,
                      customer_id: int | None = None,
                      db_path=None) -> dict:
    """Apply Kerry's ruling on one pending name.

    link          → customer_id required; backfills every banked row for
                    that (name, portal): standings, results, hole-by-hole
                    scoring_rounds.
    guest         → reviewed, no customer ever created (house rule).
    not_a_person  → parse artifact / team label; reviewed, excluded.
    reopen        → back to pending; a MANUAL link's backfilled rows are
                    un-linked (scoped to this name+portal+that customer),
                    automated resolutions are left alone.
    """
    from email_parser.database import _connect, DB_PATH
    if action not in ("link", "guest", "not_a_person", "reopen"):
        return {"error": f"unknown action {action!r}"}
    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        link = conn.execute(
            """SELECT l.*, p.subdomain FROM gg_history_name_links l
               LEFT JOIN gg_history_portals p ON p.id = l.portal_id
               WHERE l.id = ?""", (link_id,)).fetchone()
        if link is None:
            return {"error": f"name link {link_id} not found"}
        name, portal_id = link["raw_name"], link["portal_id"]
        src = f"gg_history:{link['subdomain']}" if link["subdomain"] else None
        out = {"id": link_id, "raw_name": name, "action": action}

        if action == "link":
            if not customer_id:
                return {"error": "link action requires customer_id"}
            cust = conn.execute(
                "SELECT customer_id, first_name, last_name FROM customers "
                "WHERE customer_id = ?", (customer_id,)).fetchone()
            if cust is None:
                return {"error": f"customer {customer_id} not found"}
            conn.execute(
                """UPDATE gg_history_name_links SET customer_id=?,
                       matched_by='manual', reviewed=1 WHERE id=?""",
                (customer_id, link_id))
            out["standings_linked"] = conn.execute(
                """UPDATE gg_history_standings SET customer_id=?
                   WHERE customer_id IS NULL AND player_name=?
                     AND page_id IN (SELECT id FROM gg_history_pages
                                     WHERE portal_id=?)""",
                (customer_id, name, portal_id)).rowcount
            out["results_linked"] = conn.execute(
                """UPDATE gg_history_results SET customer_id=?
                   WHERE customer_id IS NULL AND player_name=?
                     AND gg_event_id IN (SELECT id FROM gg_history_events
                                         WHERE portal_id=?)""",
                (customer_id, name, portal_id)).rowcount
            if src:
                out["hole_rounds_linked"] = conn.execute(
                    """UPDATE scoring_rounds SET customer_id=?
                       WHERE customer_id IS NULL AND player_name=?
                         AND source=?""",
                    (customer_id, name, src)).rowcount
            out["linked_to"] = (f"#{cust['customer_id']} "
                                f"{cust['first_name']} {cust['last_name']}")
        elif action in ("guest", "not_a_person"):
            conn.execute(
                """UPDATE gg_history_name_links SET matched_by=?,
                       reviewed=1, customer_id=NULL WHERE id=?""",
                (action, link_id))
        elif action == "reopen":
            if link["matched_by"] == "manual" and link["customer_id"]:
                old = link["customer_id"]
                out["standings_unlinked"] = conn.execute(
                    """UPDATE gg_history_standings SET customer_id=NULL
                       WHERE customer_id=? AND player_name=?
                         AND page_id IN (SELECT id FROM gg_history_pages
                                         WHERE portal_id=?)""",
                    (old, name, portal_id)).rowcount
                out["results_unlinked"] = conn.execute(
                    """UPDATE gg_history_results SET customer_id=NULL
                       WHERE customer_id=? AND player_name=?
                         AND gg_event_id IN (SELECT id FROM gg_history_events
                                             WHERE portal_id=?)""",
                    (old, name, portal_id)).rowcount
                if src:
                    out["hole_rounds_unlinked"] = conn.execute(
                        """UPDATE scoring_rounds SET customer_id=NULL
                           WHERE customer_id=? AND player_name=?
                             AND source=?""", (old, name, src)).rowcount
            conn.execute(
                """UPDATE gg_history_name_links SET matched_by='pending',
                       reviewed=0, customer_id=NULL WHERE id=?""",
                (link_id,))
        out["pending_remaining"] = _sync_pending_action_item(conn)
        conn.commit()
        return out


# Display name with generational suffix, for telling same-named customers
# apart (the Ariases). customers has no customer_name column: the suffixed
# label lives on customer_aliases.customer_name (parse-time snapshot);
# fall back to first + last + customers.suffix when no alias exists.
# Expects the customers table aliased as `c` in the enclosing query.
_DISPLAY_NAME_SQL = """
    COALESCE(
        (SELECT a2.customer_name FROM customer_aliases a2
          WHERE a2.customer_id = c.customer_id
            AND a2.alias_type = 'name'
            AND TRIM(COALESCE(a2.customer_name, '')) != ''
          ORDER BY LENGTH(a2.customer_name) DESC LIMIT 1),
        TRIM(c.first_name || ' ' || c.last_name
             || COALESCE(' ' || NULLIF(TRIM(c.suffix), ''), ''))
    ) AS customer_name
"""


def search_customers_for_link(q: str, limit: int = 10, db_path=None) -> list:
    """Name search behind the review UI's Link box (Kerry types letters,
    not customer numbers). Matches first/last/full name and name-type
    aliases, case-insensitive; digits-only input looks up that exact
    customer_id."""
    from email_parser.database import _connect, DB_PATH
    q = (q or "").strip()
    if not q:
        return []
    with _connect(db_path or DB_PATH) as conn:
        if q.isdigit():
            rows = conn.execute(
                f"""SELECT customer_id, first_name, last_name, chapter,
                           current_player_status, {_DISPLAY_NAME_SQL}
                    FROM customers c WHERE customer_id = ?""", (int(q),))
            return [dict(r) for r in rows]
        like = f"%{q}%"
        # NB: the alias join is by customer_id — customers has NO
        # customer_name column (joining on it 500'd this search).
        rows = conn.execute(
            f"""SELECT DISTINCT c.customer_id, c.first_name, c.last_name,
                       c.chapter, c.current_player_status,
                       {_DISPLAY_NAME_SQL}
                FROM customers c
                LEFT JOIN customer_aliases a
                  ON a.alias_type = 'name'
                 AND a.customer_id = c.customer_id
                WHERE c.first_name LIKE ? OR c.last_name LIKE ?
                   OR (c.first_name || ' ' || c.last_name) LIKE ?
                   OR (c.last_name || ', ' || c.first_name) LIKE ?
                   OR a.alias_value LIKE ?
                ORDER BY c.last_name, c.first_name LIMIT ?""",
            (like, like, like, like, like, limit)).fetchall()
        return [dict(r) for r in rows]


def hio_gross_field_counts(subdomain: str, start_date: str = "2025-08-11",
                           end_date: str = "2025-12-31",
                           budget_seconds: int = 150,
                           db_path=None) -> dict:
    """EXACT per-event field sizes from the LIVE 2025 GG portals, counted
    off the ALL GROSS leaderboards (Kerry 2026-07-20: the archive's
    result rows are winners-only for many events; 'Reference ALL Gross
    in each one of those to verify').

    Reuses the proven widget-route recipe: tournament_results round
    selector -> &round=<rid> page -> 'ALL Gross*' board links ->
    board tables -> distinct player names. Budget-aware and resumable:
    call again with the same window; already-returned events just
    recount (fetch-only, no writes)."""
    from email_parser.database import _connect, DB_PATH
    from golf_genius_sync import fetch_public_page, parse_page_structure

    t0 = time.time()
    base = f"https://{subdomain}.golfgenius.com"
    out = {"subdomain": subdomain, "window": [start_date, end_date],
           "events": [], "skipped": [], "pending": []}

    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        portal = conn.execute(
            "SELECT * FROM gg_history_portals WHERE subdomain = ?",
            (subdomain,)).fetchone()
        if portal is None:
            return {"error": f"unknown portal {subdomain!r}"}
        league_id = portal["league_id"]
        if not league_id:
            return {"error": "league_id missing — run Phase A ingest first"}
        targets = [dict(r) for r in conn.execute(
            """SELECT gg_round_id, event_date, event_label
                 FROM gg_history_events
                WHERE portal_id = ? AND gg_round_id IS NOT NULL
                  AND event_date >= ? AND event_date <= ?
                ORDER BY event_date""",
            (portal["id"], start_date, end_date))]

    def _board_names(board_url: str) -> set:
        pg = fetch_public_page(board_url)
        if pg["status_code"] != 200:
            return set()
        struct = parse_page_structure(pg["html"], board_url)
        names = set()
        _skip = {"player", "players", "pos", "position", "total", "gross",
                 "net", "purse", "points", "thru", "score", "team", "rank"}
        for tbl in (struct.get("tables") or []):
            rows = tbl.get("rows") if isinstance(tbl, dict) else tbl
            if not rows or len(rows) < 2:
                continue
            header = [str(c).strip().lower() for c in rows[0]]
            name_col = next((i for i, h in enumerate(header)
                             if "player" in h or "name" in h or "team" in h),
                            1 if len(header) > 1 else 0)
            for row in rows[1:]:
                if name_col >= len(row):
                    continue
                cell = " ".join(str(row[name_col]).split())
                low = cell.lower()
                if (not cell or low in _skip
                        or not re.search(r"[a-zA-Z]{2}", cell)
                        or re.fullmatch(r"[\d\s.$,+-]+", cell)):
                    continue
                names.add(cell)
        return names

    for ev in targets:
        if time.time() - t0 > budget_seconds:
            out["pending"].append(ev["event_label"])
            continue
        rid = str(ev["gg_round_id"])
        round_url = (f"{base}/leagues/{league_id}/widgets/"
                     f"tournament_results?shared=false&round={rid}")
        pg = fetch_public_page(round_url)
        if pg["status_code"] != 200:
            out["skipped"].append({"event": ev["event_label"],
                                   "why": f"http_{pg['status_code']}"})
            continue
        links = (parse_page_structure(pg["html"], round_url)
                 .get("links") or [])
        v2t = [l for l in links
               if "/v2tournaments/" in (l.get("href") or "")
               and "total_purse" not in l["href"]]
        gross = [l for l in v2t if (l.get("text") or "")
                 .strip().lower().startswith("all gross")]
        if not gross:
            out["skipped"].append(
                {"event": ev["event_label"], "why": "no ALL Gross board",
                 "boards": [(l.get("text") or "").strip()
                            for l in v2t][:10]})
            continue
        field = set()
        for l in gross:
            href = l["href"]
            if href.startswith("/"):
                href = base + href
            field |= _board_names(href)
        out["events"].append({
            "event": ev["event_label"], "date": ev["event_date"],
            "players": len(field),
            "boards": [(l.get("text") or "").strip() for l in gross]})
    return out


def hio_archive_events(subdomains: list, db_path=None) -> dict:
    """Per-event field sizes + games-matrix HIO contributions from the GG
    HISTORY archive — for reconstructing the 2025 HIO pot carry-in
    (Kerry 2026-07-20: how much did fall 2025 play add in Austin + SA
    after the Julius Jenkins payout?).

    players = distinct names on the event's ALL GROSS leaderboard —
              Kerry 2026-07-20: distinct names across every game
              leaderboard runs WAY over the real field (team labels,
              blinds, per-game artifacts); "Reference ALL Gross in each
              one of those to verify." Falls back to any gross-labeled
              game, then to all-games distinct (flagged) when the event
              has no gross leaderboard.
    players_all = the all-games distinct count, kept for reference.
    holes   = holes_played from banked hole-by-hole rounds when the
              event's gg_round_id was imported, else None (caller
              decides 9 vs 18).
    hio9/hio18 = the LIVE games matrix holeInOne amount at that player
              count under each assumption. The matrix is today's ratified
              rule — best available proxy for 2025."""
    from email_parser.database import _connect, DB_PATH, _load_games_matrix
    m9, m18 = _load_games_matrix(db_path=db_path)

    def _num(v):
        try:
            return float(str(v).replace("$", "").replace(",", "") or 0)
        except (TypeError, ValueError):
            return 0.0

    out = []
    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        marks = ",".join("?" * len(subdomains))
        rows = conn.execute(
            f"""SELECT e.id, e.event_label, e.event_date, e.course,
                       e.chapter, e.season, e.gg_round_id, p.subdomain,
                       (SELECT COUNT(DISTINCT r.player_name)
                          FROM gg_history_results r
                         WHERE r.gg_event_id = e.id) AS players_all,
                       (SELECT COUNT(DISTINCT r.player_name)
                          FROM gg_history_results r
                         WHERE r.gg_event_id = e.id
                           AND r.game_label LIKE '%all gross%') AS players_allgross,
                       (SELECT COUNT(DISTINCT r.player_name)
                          FROM gg_history_results r
                         WHERE r.gg_event_id = e.id
                           AND r.game_label LIKE '%gross%'
                           AND r.game_label NOT LIKE '%net%') AS players_gross
                FROM gg_history_events e
                JOIN gg_history_portals p ON p.id = e.portal_id
                WHERE p.subdomain IN ({marks})
                ORDER BY p.subdomain, e.event_date, e.id""",
            list(subdomains)).fetchall()
        for r in rows:
            players = r["players_allgross"] or r["players_gross"] or 0
            basis = ("all_gross" if r["players_allgross"]
                     else "gross" if r["players_gross"] else "all_games")
            if not players:
                players = r["players_all"] or 0
            holes = None
            if r["gg_round_id"]:
                h = conn.execute(
                    """SELECT holes_played, COUNT(*) AS n
                         FROM scoring_rounds
                        WHERE gg_round_id = ? AND holes_played IS NOT NULL
                        GROUP BY holes_played ORDER BY n DESC LIMIT 1""",
                    (str(r["gg_round_id"]),)).fetchone()
                if h:
                    holes = h["holes_played"]
            n = str(players)
            out.append({
                "subdomain": r["subdomain"], "event": r["event_label"],
                "date": r["event_date"], "course": r["course"],
                "season": r["season"], "players": players,
                "players_all": r["players_all"], "count_basis": basis,
                "holes": holes,
                "hio9": round(_num((m9.get(n) or {}).get("holeInOne")), 2),
                "hio18": round(_num((m18.get(n) or {}).get("holeInOne")), 2),
            })
    return {"events": out, "count": len(out)}


def portal_overview(db_path=None) -> dict:
    """Per-portal coverage for the review UI: pages, standings, events,
    results, hole-by-hole rounds, pending names."""
    from email_parser.database import _connect, DB_PATH
    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        portals = conn.execute(
            """SELECT p.id, p.subdomain, p.chapter, p.season, p.kind,
                      p.brand, p.status, p.league_id,
                      (SELECT COUNT(*) FROM gg_history_pages g
                       WHERE g.portal_id=p.id
                         AND g.gg_page_id NOT LIKE 'round:%') AS pages,
                      (SELECT COUNT(*) FROM gg_history_pages g
                       WHERE g.portal_id=p.id AND g.fetch_status='done'
                         AND g.gg_page_id NOT LIKE 'round:%')
                          AS pages_done,
                      (SELECT COUNT(*) FROM gg_history_pages g
                       WHERE g.portal_id=p.id
                         AND g.gg_page_id LIKE 'round:%') AS rounds,
                      (SELECT COUNT(*) FROM gg_history_pages g
                       WHERE g.portal_id=p.id AND g.fetch_status='done'
                         AND g.gg_page_id LIKE 'round:%') AS rounds_done,
                      (SELECT COUNT(*) FROM gg_history_standings s
                       JOIN gg_history_pages g ON g.id=s.page_id
                       WHERE g.portal_id=p.id) AS standings_rows,
                      (SELECT COUNT(*) FROM gg_history_events e
                       WHERE e.portal_id=p.id) AS events,
                      (SELECT COUNT(*) FROM gg_history_results r
                       JOIN gg_history_events e ON e.id=r.gg_event_id
                       WHERE e.portal_id=p.id) AS result_rows,
                      (SELECT COUNT(*) FROM scoring_rounds sr
                       WHERE sr.source='gg_history:'||p.subdomain)
                          AS hole_rounds,
                      (SELECT COUNT(*) FROM gg_history_name_links l
                       WHERE l.portal_id=p.id AND l.matched_by='pending'
                         AND l.reviewed=0) AS pending_names
               FROM gg_history_portals p
               ORDER BY p.season DESC, p.subdomain""").fetchall()
        totals = conn.execute(
            """SELECT
                   (SELECT COUNT(*) FROM gg_history_standings) AS standings,
                   (SELECT COUNT(customer_id) FROM gg_history_standings)
                       AS standings_linked,
                   (SELECT COUNT(*) FROM gg_history_results) AS results,
                   (SELECT COUNT(customer_id) FROM gg_history_results)
                       AS results_linked,
                   (SELECT COUNT(*) FROM scoring_rounds
                    WHERE source LIKE 'gg_history:%') AS hole_rounds,
                   (SELECT COUNT(*) FROM scoring_holes
                    WHERE scoring_round_id IN (SELECT id FROM scoring_rounds
                    WHERE source LIKE 'gg_history:%')) AS holes,
                   (SELECT COUNT(*) FROM gg_history_name_links
                    WHERE matched_by='pending' AND reviewed=0) AS pending
            """).fetchone()
        return {"totals": dict(totals),
                "portals": [dict(p) for p in portals]}


def standings_browser(portal: str | None = None, q: str | None = None,
                      contest: str | None = None, limit: int = 200,
                      db_path=None) -> dict:
    """Standings rows for the review UI browser (verbatim, with links)."""
    from email_parser.database import _connect, DB_PATH
    clauses, params = ["1=1"], []
    if portal:
        clauses.append("p.subdomain = ?"); params.append(portal)
    if contest:
        clauses.append("s.contest_label LIKE ?"); params.append(f"%{contest}%")
    if q:
        clauses.append("s.player_name LIKE ?"); params.append(f"%{q}%")
    with _connect(db_path or DB_PATH) as conn:
        ensure_gg_history_tables(conn)
        rows = conn.execute(
            f"""SELECT s.id, p.subdomain, s.season, s.chapter,
                       s.contest_label, s.position_raw, s.position,
                       s.player_name, s.customer_id,
                       c.first_name || ' ' || c.last_name AS customer_name,
                       s.points, s.money_cents
                FROM gg_history_standings s
                JOIN gg_history_pages g ON g.id = s.page_id
                JOIN gg_history_portals p ON p.id = g.portal_id
                LEFT JOIN customers c ON c.customer_id = s.customer_id
                WHERE {' AND '.join(clauses)}
                ORDER BY p.season DESC, s.contest_label, s.position
                LIMIT ?""", (*params, limit)).fetchall()
        contests = conn.execute(
            f"""SELECT DISTINCT p.subdomain, s.contest_label
                FROM gg_history_standings s
                JOIN gg_history_pages g ON g.id = s.page_id
                JOIN gg_history_portals p ON p.id = g.portal_id
                {'WHERE p.subdomain = ?' if portal else ''}
                ORDER BY 1, 2""",
            (portal,) if portal else ()).fetchall()
        return {"rows": [dict(r) for r in rows],
                "contests": [dict(c) for c in contests]}


def archive_widget_page(subdomain: str, gg_page_id: str, db_path=None) -> dict:
    """#126 item 3: archive a page's widget HTML verbatim (e.g. the LSC
    2025 money page whose content is an uploaded image). The image file
    itself lives on cloudfront, outside the SSRF allowlist — the archived
    HTML pins its URL; the money DATA is already banked via the export."""
    from email_parser.database import _connect, DB_PATH
    from golf_genius_sync import fetch_public_page
    base = f"https://{subdomain}.golfgenius.com"
    pg = fetch_public_page(f"{base}/pages/{gg_page_id}")
    if pg["status_code"] != 200:
        return {"error": f"page fetch {pg['status_code']}"}
    im = _IFRAME_WIDGET_RE.search(pg["html"])
    target_url, html = (f"{base}/pages/{gg_page_id}", pg["html"])
    if im:
        src = im.group(1)
        if src.startswith("/"):
            src = base + src
        w = fetch_public_page(src)
        if w["status_code"] == 200:
            target_url, html = src, w["html"]
    img = re.search(r"<img[^>]+src=[\"']([^\"']+cloudfront[^\"']+)[\"']",
                    html, re.I)
    with _connect(db_path or DB_PATH) as conn:
        raw_id = _archive_raw(conn, target_url, html)
        conn.execute(
            """UPDATE gg_history_pages SET raw_archive_id=?
               WHERE gg_page_id=? AND raw_archive_id IS NULL""",
            (raw_id, gg_page_id))
        conn.commit()
    return {"archived_url": target_url, "raw_archive_id": raw_id,
            "image_url": img.group(1) if img else None}
