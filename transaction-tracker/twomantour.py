"""
Two Man Tour — live-scoring fetch + parse for the admin Flight Board.

Completely separate from TGF: this module knows nothing about the Tracker
database, customers, or events. It fetches a public live-scoring page from
league.unknowngolf.com, extracts every HTML table it can find, and returns
a structured payload the Flight Board UI turns into a team leaderboard.

The parser is deliberately heuristic — the unknowngolf event.jsp markup is
not under our control — so instead of hard-coding one table shape it:
  1. pulls EVERY table (including nested layout tables) as rows of cell text,
  2. scores each table by how many rows look like (team name + numeric score),
  3. returns the best table's headers + rows, plus name/score column guesses.
The UI keeps a column picker and a paste-import fallback for the night some
markup change breaks the guesses.
"""

import re
import logging
from html import unescape
from html.parser import HTMLParser

import requests

logger = logging.getLogger(__name__)

ALLOWED_HOST = "league.unknowngolf.com"
FETCH_TIMEOUT = 20
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


# ---------------------------------------------------------------------------
# HTML table extraction (stdlib only — no bs4 dependency)
# ---------------------------------------------------------------------------
class _TableExtractor(HTMLParser):
    """Collects every <table> in the document (nested tables included) as a
    list of rows, each row a list of stripped cell strings. Also grabs the
    page <title> and first <h1>/<h2> for an event-name guess."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []          # finished tables: {"rows": [...], "header_flags": [...]}
        self._stack = []          # open tables (innermost last)
        self.title = ""
        self.heading = ""
        self._text_target = None  # "title" | "heading" | None
        self._skip_depth = 0      # inside <script>/<style>

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip_depth += 1
            return
        if tag == "table":
            self._stack.append({"rows": [], "row": None, "cell": None, "flags": []})
        elif self._stack:
            t = self._stack[-1]
            if tag == "tr":
                t["row"], t["cell"] = [], None
                t["flags"].append(False)
            elif tag in ("td", "th"):
                if t["row"] is None:
                    t["row"], t["flags"] = [], t["flags"] + [False]
                t["cell"] = []
                if tag == "th" and t["flags"]:
                    t["flags"][-1] = True
            elif tag == "br" and t.get("cell") is not None:
                t["cell"].append(" ")
        if tag == "title":
            self._text_target = "title"
        elif tag in ("h1", "h2") and not self.heading:
            self._text_target = "heading"

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in ("title", "h1", "h2"):
            self._text_target = None
        if not self._stack:
            return
        t = self._stack[-1]
        if tag in ("td", "th") and t.get("cell") is not None:
            text = re.sub(r"\s+", " ", "".join(t["cell"])).strip()
            if t["row"] is None:
                t["row"] = []
            t["row"].append(text)
            t["cell"] = None
        elif tag == "tr" and t.get("row") is not None:
            t["rows"].append(t["row"])
            t["row"] = None
        elif tag == "table":
            done = self._stack.pop()
            if done.get("row"):          # unclosed final row
                done["rows"].append(done["row"])
            rows = [r for r in done["rows"] if any(c.strip() for c in r)]
            if rows:
                flags = (done["flags"] + [False] * len(rows))[:len(rows)]
                self.tables.append({"rows": rows, "header_flags": flags})

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._text_target == "title":
            self.title += data
        elif self._text_target == "heading":
            self.heading += data
        if self._stack and self._stack[-1].get("cell") is not None:
            self._stack[-1]["cell"].append(data)


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------
_NON_SCORES = {"wd", "dq", "ns", "dns", "cut", "--", "-", ""}


def parse_score_token(s):
    """'E'->0, '+3'->3, '-5'->-5, '71'->71, '68.5'->68.5; None if not a score."""
    s = (s or "").strip().rstrip("*")
    if s.lower() in _NON_SCORES:
        return None
    if s.upper() == "E":
        return 0
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", s):
        return float(s) if "." in s else int(s)
    return None


def _is_namelike(s):
    """A cell that plausibly holds a team/player name."""
    s = (s or "").strip()
    if len(s) < 3 or parse_score_token(s) is not None:
        return False
    return len(re.findall(r"[A-Za-z]", s)) >= 3


def _score_table(rows):
    """How many rows look like leaderboard rows (a name cell + a score cell)."""
    n = 0
    for r in rows:
        if any(_is_namelike(c) for c in r) and any(
                parse_score_token(c) is not None for c in r):
            n += 1
    return n


def _column_profile(rows):
    """For the data rows of a table, guess the name column and the numeric
    columns. Returns (name_col, numeric_cols)."""
    width = max((len(r) for r in rows), default=0)
    name_hits = [0] * width
    num_hits = [0] * width
    for r in rows:
        for i in range(width):
            c = r[i] if i < len(r) else ""
            if parse_score_token(c) is not None:
                num_hits[i] += 1
            elif _is_namelike(c):
                name_hits[i] += 1
    threshold = max(2, len(rows) // 2)
    numeric_cols = [i for i in range(width) if num_hits[i] >= threshold]
    name_col = max(range(width), key=lambda i: name_hits[i], default=0) if width else 0
    return name_col, numeric_cols


def extract_leaderboard(html):
    """Parse the page and return the best-guess leaderboard payload."""
    ex = _TableExtractor()
    try:
        ex.feed(html)
        ex.close()
    except Exception:
        logger.exception("Two Man Tour: HTML parse error")

    best, best_score = None, 0
    for t in ex.tables:
        s = _score_table(t["rows"])
        if s > best_score:
            best, best_score = t, s

    payload = {
        "event_name": unescape((ex.heading or ex.title or "").strip()),
        "found": False,
        "headers": [],
        "rows": [],
        "name_col": None,
        "numeric_cols": [],
        "table_count": len(ex.tables),
    }
    if not best or best_score < 2:
        return payload

    rows = best["rows"]
    flags = best["header_flags"]
    # Header = first row if it's flagged <th> or has no score-looking cells
    # while later rows do.
    header, data = [], rows
    if rows and (flags[0] or not any(parse_score_token(c) is not None for c in rows[0])):
        header, data = rows[0], rows[1:]
    # Drop repeated header rows and blank/section rows inside the data.
    data = [r for r in data
            if r != header and (any(_is_namelike(c) for c in r)
                                or any(parse_score_token(c) is not None for c in r))]
    if not data:
        return payload

    name_col, numeric_cols = _column_profile(data)

    def _is_position_col(i):
        # Header says position, or (headerless) the column counts 1,2,3…
        h = (header[i] if i < len(header) else "").strip().lower()
        if re.fullmatch(r"pos\.?|#|rank|place|thru|holes?", h):
            return True
        if h:
            return False
        vals = [parse_score_token(re.sub(r"^t", "", (r[i] if i < len(r) else "").strip(), flags=re.I))
                for r in data]
        vals = [v for v in vals if v is not None]
        return (len(vals) >= len(data) - 1 and vals and vals[0] == 1
                and all(b >= a for a, b in zip(vals, vals[1:])))

    numeric_cols = [i for i in numeric_cols if not _is_position_col(i)] or numeric_cols
    payload.update({
        "found": True,
        "headers": header,
        "rows": data,
        "name_col": name_col,
        "numeric_cols": numeric_cols,
    })
    return payload


# ---------------------------------------------------------------------------
# Scorecard-block format (what the real event page turned out to be,
# per Kerry's screenshot 2026-08-08): each team renders as a block —
#   Weapons of Grass Destruction        <- team name (bare line)
#   Todd Albert (0)                     <- players, handicap in parens
#   Josiah Prindle (0)
#   Tpc San Antonio - Canyons           <- course (bare line, ignored)
#   - - - - - - 3 3 4 3 4 - 17 17 (-2)  <- hole row; (vs par) at the end
#   Unofficial Score                    <- block terminator
# ---------------------------------------------------------------------------
_RE_HEADER = re.compile(r"^player\s+HC\b", re.I)
_RE_STATUS = re.compile(r"^((un)?official\s+score|thru\b.*|hole|out|in|total)$", re.I)
_RE_PLAYER = re.compile(r"\([+-]?\d+\)\s*$")
_RE_PARENS_SCORE = re.compile(r"\(([+-]?\d+(?:\.\d+)?|E)\)\s*$", re.I)


def _tokens(line):
    return line.split()


def _is_hole_row(line):
    toks = _tokens(line)
    if len(toks) < 5:
        return False
    holeish = sum(1 for t in toks
                  if re.fullmatch(r"-+|\d{1,3}|F|\([+-]?\d+\)|\(E\)", t, re.I))
    return holeish >= 5 and holeish >= len(toks) - 1


def _hole_row_score(line):
    m = _RE_PARENS_SCORE.search(line)
    if m:
        return parse_score_token(m.group(1)), "(" + m.group(1) + ")"
    toks = _tokens(line)
    # last signed/E token, else last plain number (gross total)
    for t in reversed(toks):
        if re.fullmatch(r"[+-]\d+|E", t, re.I):
            return parse_score_token(t), t
    for t in reversed(toks):
        v = parse_score_token(t)
        if v is not None:
            return v, t
    return None, ""


def parse_scorecard_blocks(lines):
    """Parse the per-team scorecard-block layout into teams. Returns
    [{name, score, raw}] — score is the (vs par) value when present.

    A bare line only becomes a team name once a player or hole row
    follows it (`pending` → `cur`), so page headings / nav junk before
    the first block are overwritten by the real team name and never
    emitted. A bare line inside an open block (the course) is ignored."""
    teams, cur, pending, cur_score, cur_raw, scored = [], None, None, None, "", False
    players = []

    def flush():
        nonlocal cur, cur_score, cur_raw, scored, players
        if cur:
            teams.append({"name": cur, "score": cur_score, "raw": cur_raw,
                          "players": players})
        cur, cur_score, cur_raw, scored, players = None, None, "", False, []

    def open_block():
        nonlocal cur, pending
        if cur is None and pending is not None:
            cur, pending = pending, None

    for raw_line in lines:
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line or _RE_HEADER.search(line):
            continue
        if _RE_STATUS.fullmatch(line):
            flush()
            pending = None
            continue
        if _is_hole_row(line):
            open_block()
            if cur:
                v, tok = _hole_row_score(line)
                if v is not None:
                    cur_score, cur_raw, scored = v, tok, True
            continue
        if _RE_PLAYER.search(line):
            open_block()
            if cur is not None:
                pname = _RE_PLAYER.sub("", line).strip()
                if pname and pname not in players:
                    players.append(pname)
            continue
        if _is_namelike(line):
            name = re.sub(r"^T?\d+[.)]?\s+", "", line)
            if cur is not None and scored:
                flush()
            if cur is None:
                pending = name
    flush()
    return teams


# ---------------------------------------------------------------------------
# Page text extraction (for block parsing + diagnostics)
# ---------------------------------------------------------------------------
def _text_lines(html):
    """Flatten the page to text lines: a table row becomes ONE line
    (cells joined by spaces), block-level tags break lines — matching
    what a drag-copy of the page looks like."""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    s = re.sub(r"(?i)</t[dh]>", " ", s)
    s = re.sub(r"(?i)<(br|/tr|/div|/p|/li|/h[1-6]|/table|/section)[^>]*>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = unescape(s)
    lines = []
    for ln in s.splitlines():
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln:
            lines.append(ln)
    return lines


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
def fetch_live(event_id, tour_id, cookie=None):
    """Fetch the unknowngolf event page and return the parsed payload.
    Raises ValueError on bad ids; network errors bubble up as
    requests.RequestException for the route to report."""
    if not re.fullmatch(r"\d{1,12}", str(event_id) or ""):
        raise ValueError("eventId must be numeric")
    if not re.fullmatch(r"\d{1,12}", str(tour_id) or ""):
        raise ValueError("tourId must be numeric")
    url = (f"https://{ALLOWED_HOST}/event.jsp"
           f"?eventId={event_id}&tourId={tour_id}")
    headers = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"}
    if cookie:
        headers["Cookie"] = cookie
    resp = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    payload = extract_leaderboard(resp.text)
    payload["source_url"] = url
    payload["http_status"] = resp.status_code

    # The real event page (seen 2026-08-08) renders per-team scorecard
    # blocks, not a name+score table — try the block parser on the page
    # text and prefer it when it finds a real field of teams.
    lines = _text_lines(resp.text)
    blocks = parse_scorecard_blocks(lines)
    scored = [t for t in blocks if t["score"] is not None]
    if len(blocks) >= 2 and (len(scored) >= 2 or not payload["found"]):
        payload["teams"] = blocks
        payload["mode"] = "blocks"

    # Diagnostics: when neither parser produced anything, ship the first
    # chunk of page text so the failure is visible in the response
    # (admin-only endpoint) instead of guessing at the markup again.
    if not payload["found"] and not payload.get("teams"):
        payload["sample_lines"] = lines[:80]
    return payload
