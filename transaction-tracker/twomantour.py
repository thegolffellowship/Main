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
import json
import sqlite3
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


def _num(t):
    return int(t) if re.fullmatch(r"\d{1,3}", t or "") else None


def _parse_card(line):
    """Map a hole row into a scorecard dict. The row layout is
    holes 1-9, OUT, holes 10-18, IN, [Total], optionally preceded by a
    team-HC column — so instead of trusting one shape, try each offset
    and VALIDATE the running-total arithmetic (OUT == sum of scored
    front holes, IN == sum of scored back, Total == OUT+IN). Falls back
    to the raw row so the UI always has something to show."""
    m = _RE_PARENS_SCORE.search(line)
    vspar = m.group(1) if m else None
    body = _RE_PARENS_SCORE.sub("", line).strip()
    toks = body.split()

    def try_map(rem, hc):
        if len(rem) not in (19, 20, 21):
            return None
        front, out, back = rem[0:9], rem[9], rem[10:19]
        inn = rem[19] if len(rem) > 19 else None
        total = rem[20] if len(rem) > 20 else None
        fs = [_num(x) for x in front if _num(x) is not None]
        bs = [_num(x) for x in back if _num(x) is not None]
        ok_f = (_num(out) == sum(fs)) if _num(out) is not None else not fs
        ok_b = (True if inn is None else
                ((_num(inn) == sum(bs)) if _num(inn) is not None else not bs))
        ok_t = (True if (total is None or _num(total) is None) else
                _num(total) == (_num(out) or 0) + (_num(inn) or 0))
        if not (ok_f and ok_b and ok_t):
            return None
        if inn is None:
            inn = str(sum(bs)) if bs else "-"
        if total is None:
            played = (_num(out) or 0) + (_num(inn) or 0)
            total = str(played) if played else "-"
        return {"holes": front + back, "out": out, "inn": inn,
                "total": total, "vspar": vspar, "hc": hc}

    for off in (0, 1):
        r = try_map(toks[off:], toks[0] if off else None)
        if r:
            return r
    return {"raw": body, "vspar": vspar}


def parse_scorecard_blocks(lines):
    """Parse the per-team scorecard-block layout into teams. Returns
    [{name, score, raw}] — score is the (vs par) value when present.

    A bare line only becomes a team name once a player or hole row
    follows it (`pending` → `cur`), so page headings / nav junk before
    the first block are overwritten by the real team name and never
    emitted. A bare line inside an open block (the course) is ignored."""
    teams, cur, pending, cur_score, cur_raw, scored = [], None, None, None, "", False
    players, cur_card = [], None

    def flush():
        nonlocal cur, cur_score, cur_raw, scored, players, cur_card
        if cur:
            teams.append({"name": cur, "score": cur_score, "raw": cur_raw,
                          "players": players, "card": cur_card})
        cur, cur_score, cur_raw, scored, players, cur_card = (
            None, None, "", False, [], None)

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
                cur_card = _parse_card(line)
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
# Saved events (tag + save a board, reload it later)
#
# One isolated table in the Tracker's SQLite file (so it lives on the
# Railway persistent volume) — deliberately NO foreign keys or joins to
# any TGF table; the payload is the whole board as JSON (teams with
# players + scorecards, flight cuts, flight count, buy-in).
# ---------------------------------------------------------------------------
def _db():
    from email_parser.database import DB_PATH  # same file → persistent volume
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS twomantour_saves (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            tag        TEXT NOT NULL,
            event_id   TEXT,
            tour_id    TEXT,
            event_name TEXT,
            team_count INTEGER NOT NULL DEFAULT 0,
            payload    TEXT NOT NULL,
            saved_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )""")
    return conn


def _kv_get(key):
    with _db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS twomantour_kv"
                     " (key TEXT PRIMARY KEY, value TEXT)")
        row = conn.execute("SELECT value FROM twomantour_kv WHERE key = ?",
                           (key,)).fetchone()
        return row["value"] if row else None


def _kv_set(key, value):
    with _db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS twomantour_kv"
                     " (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO twomantour_kv (key, value) VALUES (?, ?)"
                     " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (key, value or ""))


def stored_cookie():
    return _kv_get("ug_cookie") or None


# ---------------------------------------------------------------------------
# Unknown Golf site login
#
# The event page sits behind a login wall (evidence: Kerry's live
# diagnostics 2026-08-08 — the server receives "Welcome back, player!"
# with an email/password form). The server performs the same form login
# a browser would, then stores ONLY the resulting session cookie in
# twomantour_kv (the password is never persisted anywhere). Fetches use
# the stored cookie until the site expires it, at which point the login
# wall is re-detected and the admin logs in again.
# ---------------------------------------------------------------------------
def _find_login_form(html):
    """Locate the form containing a password input; return
    (action, method, fields-dict, email_field, password_field)."""
    for fm in re.finditer(r"(?is)<form\b([^>]*)>(.*?)</form>", html):
        attrs, body = fm.group(1), fm.group(2)
        if not re.search(r'(?i)type=["\']?password', body):
            continue
        action_m = re.search(r'(?i)action=["\']([^"\']*)["\']', attrs)
        method_m = re.search(r'(?i)method=["\']([^"\']*)["\']', attrs)
        action = action_m.group(1) if action_m else ""
        method = (method_m.group(1) if method_m else "post").lower()
        fields, email_field, password_field = {}, None, None
        for im in re.finditer(r"(?is)<input\b[^>]*>", body):
            tag = im.group(0)
            name_m = re.search(r'(?i)name=["\']([^"\']+)["\']', tag)
            if not name_m:
                continue
            name = name_m.group(1)
            type_m = re.search(r'(?i)type=["\']?(\w+)', tag)
            itype = (type_m.group(1) if type_m else "text").lower()
            value_m = re.search(r'(?i)value=["\']([^"\']*)["\']', tag)
            value = unescape(value_m.group(1)) if value_m else ""
            if itype == "password":
                password_field = name
            elif itype == "email" or re.search(r"(?i)email|user|login", name):
                if not email_field:
                    email_field = name
            fields[name] = value
        if password_field:
            return action, method, fields, email_field, password_field
    return None


def _looks_logged_out(html):
    lines = _text_lines(html)
    joined = " ".join(lines[:60]).lower()
    return len(lines) < 45 and bool(
        re.search(r"password|log ?in|sign ?in", joined))


def _page_diag(url, html):
    """Evidence bundle for a page where no usable login form was found."""
    inputs = re.findall(r"(?is)<input\b[^>]*>", html)[:12]
    auth_urls = []
    for m in re.finditer(
            r'["\']([^"\'\s]{1,200}(?:login|signin|auth|session)[^"\'\s]{0,100})["\']',
            html, re.I):
        if m.group(1) not in auth_urls:
            auth_urls.append(m.group(1))
        if len(auth_urls) >= 10:
            break
    return {
        "url": url,
        "form_count": len(re.findall(r"(?i)<form\b", html)),
        "inputs": [i[:160] for i in inputs],
        "auth_urls": auth_urls,
    }


def _login_links(html, base_url):
    """Same-host login/signin links found in a page."""
    from urllib.parse import urljoin, urlparse
    out = []
    for m in re.finditer(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\']', html):
        href = m.group(1)
        if re.search(r"login|sign ?in", href, re.I):
            u = urljoin(base_url, unescape(href))
            if urlparse(u).netloc == ALLOWED_HOST:
                out.append(u)
    return out


# -- JS login discovery ------------------------------------------------------
# Evidence (Kerry's diagnostics, 2026-08-08): every UG login surface has
# <input id="idEmail"> / <input id="idPassword"> with NO <form> — a JS
# doLogin() submits them. So: locate doLogin's source (inline scripts,
# then same-host external scripts), pull the endpoint URL + parameter
# style out of it, and replay that call server-side.
def _script_srcs(html, base_url):
    from urllib.parse import urljoin, urlparse
    out = []
    for m in re.finditer(r'(?is)<script\b[^>]*src=["\']([^"\']+)["\']', html):
        u = urljoin(base_url, unescape(m.group(1)))
        if urlparse(u).netloc == ALLOWED_HOST and u not in out:
            out.append(u)
    return out


def _find_dologin_source(s, html, base_url):
    for sc in re.findall(r"(?is)<script\b[^>]*>(.*?)</script>", html):
        if re.search(r"function\s+doLogin|doLogin\s*=\s*function", sc):
            return sc, base_url
    for src in _script_srcs(html, base_url)[:8]:
        try:
            r = s.get(src, timeout=FETCH_TIMEOUT)
        except Exception:
            continue
        if re.search(r"function\s+doLogin|doLogin\s*=\s*function", r.text):
            return r.text, src
    return None, None


def _extract_login_call(js):
    """From doLogin's source, pull candidate endpoint URLs, the request
    data template (constants + which keys hold the email/password), and
    whether it sends JSON."""
    m = re.search(r"(?:function\s+doLogin|doLogin\s*=\s*function)[\s\S]{0,6000}", js)
    region = m.group(0) if m else js[:6000]
    urls = []
    for pat in (r'\.open\(\s*["\']\w+["\']\s*,\s*["\']([^"\']+)["\']',
                r'fetch\(\s*["\']([^"\']+)["\']',
                r'\burl\s*[:=]\s*["\']([^"\']+)["\']',
                r'\.post\(\s*["\']([^"\']+)["\']',
                r'\baction\s*[:=]\s*["\']([^"\']+)["\']'):
        for u in re.findall(pat, region):
            if u not in urls:
                urls.append(u)

    # Parse the jQuery-style `data : { "k" : v, ... }` object literal.
    # Each pair is either a constant ("a":"1") or a reference to the
    # email / password input ($('#idEmail').val()). Keeps constants so
    # the server sends the full payload the endpoint expects.
    template, email_key, pass_key = {}, None, None
    dm = re.search(r"data\s*:\s*\{(.*?)\}", region, re.S)
    if dm:
        for km in re.finditer(
                r'["\']?([A-Za-z_]\w{0,30})["\']?\s*:\s*([^,}]+)', dm.group(1)):
            key, val = km.group(1), km.group(2).strip()
            if re.search(r'idEmail|#idEmail|Email', val):
                email_key = key
                template[key] = None
            elif re.search(r'idPassword|#idPassword|Password|Psswd|Pass', val):
                pass_key = key
                template[key] = None
            else:
                template[key] = val.strip().strip("'\"")

    # Fallback: "userEmail=" + … style params if there was no data object.
    loose = []
    for p in re.findall(r'["\'&?]([A-Za-z_]\w{0,30})=["\']?\s*\+', region):
        if p not in loose:
            loose.append(p)
    # A jQuery `data:{...}` object is sent FORM-ENCODED unless the code
    # JSON.stringifies it or sets an explicit JSON contentType. dataType
    # only describes the RESPONSE, so it must not force a JSON request.
    json_mode = bool(re.search(r"JSON\.stringify", region) or
                     re.search(r"contentType\s*:\s*['\"]application/json", region))
    return urls, template, email_key, pass_key, loose, json_mode, region[:1800]


def _login_success(s, event_id, tour_id):
    check = (f"https://{ALLOWED_HOST}/event.jsp?eventId={event_id}"
             f"&tourId={tour_id}" if event_id and tour_id
             else f"https://{ALLOWED_HOST}/")
    try:
        r = s.get(check, timeout=FETCH_TIMEOUT)
    except Exception:
        return False
    return not _looks_logged_out(r.text)


def _js_login(s, html, base_url, email, password, event_id, tour_id):
    """Replay the site's doLogin() call. Returns ok-bool + diag dict."""
    from urllib.parse import urljoin, urlparse
    js, js_src = _find_dologin_source(s, html, base_url)
    if not js:
        return False, {"url": base_url,
                       "error": "doLogin() source not found",
                       "scripts": _script_srcs(html, base_url)[:8]}
    urls, template, email_key, pass_key, loose, json_mode, snippet = \
        _extract_login_call(js)
    endpoints = []
    for u in urls:
        full = urljoin(base_url, u)
        if urlparse(full).netloc == ALLOWED_HOST and full not in endpoints:
            endpoints.append(full)

    # Build candidate payloads. Preferred: the parsed data template with
    # its constants, filling the identified email/password keys. Then
    # fall back to loose param names and generic guesses.
    payloads = []
    if template and email_key and pass_key:
        base = dict(template)
        base[email_key] = email
        base[pass_key] = password
        # 'null' in the JS is the literal string, not a real null.
        payloads.append(base)
    if loose:
        ek = next((p for p in loose if re.search(r"mail|user|login", p, re.I)), None)
        pk = next((p for p in loose if re.search(r"pass|pwd|psswd", p, re.I)), None)
        if ek and pk:
            payloads.append({ek: email, pk: password})
    for ek, pk in (("userEmail", "userPsswd"), ("email", "password"),
                   ("emailAddress", "password"), ("username", "password")):
        payloads.append({ek: email, pk: password})

    tried = []
    for ep in endpoints[:3]:
        for data in payloads[:6]:
            keys = "+".join(k for k in data if data[k] in (email, password))
            try:
                if json_mode:
                    r = s.post(ep, json=data, timeout=FETCH_TIMEOUT)
                else:
                    r = s.post(ep, data=data, timeout=FETCH_TIMEOUT)
            except Exception as e:
                tried.append(f"{ep} [{keys}] -> {e}")
                continue
            # The endpoint answers 200 for both success and bad creds; the
            # JSON body / a post-login re-fetch is the real signal.
            body_ok = False
            try:
                j = r.json()
                body_ok = bool(j.get("urlRedirect")) or j.get("success") is True \
                    or j.get("result") in ("ok", "success", True)
            except Exception:
                pass
            tried.append(f"{ep} [{keys}] -> HTTP {r.status_code}"
                         f"{' body-ok' if body_ok else ''}")
            if r.status_code < 400 and (body_ok or _login_success(s, event_id, tour_id)):
                return True, {"endpoint": ep, "keys": list(data.keys())}
    return False, {"url": base_url, "error": "doLogin replay failed",
                   "dologin_from": js_src, "endpoints": endpoints,
                   "data_template": template, "email_key": email_key,
                   "pass_key": pass_key, "json_mode": json_mode,
                   "attempts": tried, "dologin_snippet": snippet}


def site_login(email, password, event_id=None, tour_id=None):
    """Form-login to Unknown Golf; on success store the session cookie.
    Returns {'status': 'ok'} or {'error': ..., 'diag': [...]}. Tries the
    entry page, the platform's known login URLs (/platform/login.jsp and
    /platform/signin/ — the event page draws its login with JS, so the
    raw HTML there has no form), and any same-host login links it sees.
    The password is used for this one request chain and never stored."""
    from urllib.parse import urljoin, urlparse
    s = requests.Session()
    s.headers.update({"User-Agent": _UA,
                      "Accept": "text/html,application/xhtml+xml"})
    entry = (f"https://{ALLOWED_HOST}/event.jsp?eventId={event_id}"
             f"&tourId={tour_id}" if event_id and tour_id
             else f"https://{ALLOWED_HOST}/")
    candidates = [entry,
                  f"https://{ALLOWED_HOST}/platform/login.jsp",
                  f"https://{ALLOWED_HOST}/platform/signin/"]
    tried, diag = set(), []
    i = 0
    while i < len(candidates) and len(tried) < 6:
        url = candidates[i]
        i += 1
        if url in tried:
            continue
        tried.add(url)
        try:
            r = s.get(url, timeout=FETCH_TIMEOUT)
        except Exception as e:
            diag.append({"url": url, "error": str(e)})
            continue
        form = _find_login_form(r.text)
        if not form:
            if url == entry and not _looks_logged_out(r.text):
                # Entry page already open (stale wall?) — keep cookies.
                _save_session_cookie(s)
                return {"status": "ok", "note": "page already open"}
            # Formless login (id-only inputs + doLogin()) — replay the JS call.
            if re.search(r'(?i)type=["\']?password', r.text):
                ok, js_diag = _js_login(s, r.text, r.url, email, password,
                                        event_id, tour_id)
                if ok:
                    _save_session_cookie(s)
                    return {"status": "ok", "via": "doLogin",
                            "endpoint": js_diag.get("endpoint")}
                diag.append(js_diag)
            else:
                diag.append(_page_diag(url, r.text))
            for link in _login_links(r.text, r.url):
                if link not in tried and link not in candidates:
                    candidates.append(link)
            continue
        action, method, fields, email_field, password_field = form
        if not email_field:
            diag.append({"url": url, "error": "password form but no email/username field",
                         **_page_diag(url, r.text)})
            continue
        fields[email_field] = email
        fields[password_field] = password
        post_url = urljoin(r.url, action or r.url)
        if urlparse(post_url).netloc != ALLOWED_HOST:
            diag.append({"url": url, "error": f"form posts off-site: {post_url}"})
            continue
        fn = s.post if method != "get" else s.get
        r2 = fn(post_url, data=fields, timeout=FETCH_TIMEOUT)
        if _find_login_form(r2.text) and _looks_logged_out(r2.text):
            return {"error": "Login didn't stick — check the email/password.",
                    "diag": [{"url": post_url, "note": "site returned the login form again"}]}
        _save_session_cookie(s)
        return {"status": "ok", "login_url": url}
    return {"error": "Couldn't find a usable login form on the site.",
            "diag": diag}


def _save_session_cookie(session):
    pairs = ["%s=%s" % (c.name, c.value) for c in session.cookies]
    _kv_set("ug_cookie", "; ".join(pairs))


def save_board(tag, event_id, tour_id, event_name, payload):
    """Insert a snapshot; returns the new save id."""
    tag = (tag or "").strip()[:120] or "untitled"
    team_count = len(payload.get("teams") or [])
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO twomantour_saves (tag, event_id, tour_id, event_name,"
            " team_count, payload) VALUES (?,?,?,?,?,?)",
            (tag, str(event_id or ""), str(tour_id or ""),
             (event_name or "")[:200], team_count,
             json.dumps(payload)))
        return cur.lastrowid


def list_saves():
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, tag, event_id, tour_id, event_name, team_count,"
            " saved_at FROM twomantour_saves ORDER BY id DESC LIMIT 200"
        ).fetchall()
        return [dict(r) for r in rows]


def get_save(save_id):
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM twomantour_saves WHERE id = ?", (save_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["payload"] = json.loads(d["payload"])
        return d


def delete_save(save_id):
    with _db() as conn:
        cur = conn.execute(
            "DELETE FROM twomantour_saves WHERE id = ?", (save_id,))
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
_SCORE_KW = r"score|leader|standing|live|card|result|board|team|tv"


def _gather_scoring_candidates(html, base_url, event_id, tour_id, cookie):
    """URLs that may carry the actual leaderboard data. The event page is
    a JS shell — the standings load from a separate feed — so we look in
    iframes, inline URLs, AND external script files (fetched and scanned),
    then add Unknown Golf's known display/leaderboard endpoints as
    explicit guesses. Host-locked, deduped, leaderboard-first, capped."""
    from urllib.parse import urlparse, urljoin
    found = []
    for m in re.finditer(r'<i?frame[^>]+src=["\']([^"\']+)["\']', html, re.I):
        found.append(m.group(1))
    url_pat = r'["\']([^"\'\s]{1,300}\.(?:jsp|ukg|do)[^"\'\s]{0,200})["\']'
    for m in re.finditer(url_pat, html, re.I):
        if re.search(_SCORE_KW, m.group(1), re.I):
            found.append(m.group(1))
    # external scripts — the leaderboard AJAX URL usually lives in a .js
    scanned = 0
    for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I):
        if scanned >= 6:
            break
        src = urljoin(base_url, unescape(m.group(1)))
        if urlparse(src).netloc != ALLOWED_HOST:
            continue
        scanned += 1
        try:
            js = _get(src, cookie).text
        except Exception:
            continue
        for jm in re.finditer(url_pat, js, re.I):
            if re.search(_SCORE_KW, jm.group(1), re.I):
                found.append(jm.group(1))
    # explicit high-probability guesses (display/TV leaderboards render
    # standalone HTML; result summaries sometimes do too)
    q = f"?eventId={event_id}" + (f"&tourId={tour_id}" if tour_id else "")
    found += ["/platform/tv/tvLeaderboard.jsp" + q,
              "/eventLeaderboard.jsp" + q,
              "/eventResultSummary.jsp" + q,
              "/eventLeaderboardStandings.jsp" + q,
              "/leaderboard.ukg" + q,
              "/eventLeaderboard.ukg" + q]
    out, seen = [], set()
    base = f"https://{ALLOWED_HOST}/"
    for u in found:
        full = urljoin(base_url or base, unescape(u.strip()))
        p = urlparse(full)
        if p.scheme != "https" or p.netloc != ALLOWED_HOST:
            continue
        if full not in seen:
            seen.add(full)
            out.append(full)
    out.sort(key=lambda u: 0 if re.search(r"leader|tv|standing|result", u, re.I) else 1)
    return out[:8]


def _parse_data_obj(block):
    """Parse a jQuery `data:{ "k": v, ... }` literal → {key: raw_value_str}."""
    out = {}
    dm = re.search(r"data\s*:\s*\{(.*?)\}", block, re.S)
    if not dm:
        return out
    for km in re.finditer(r'["\']?([A-Za-z_]\w{0,30})["\']?\s*:\s*([^,}]+)',
                          dm.group(1)):
        out[km.group(1)] = km.group(2).strip()
    return out


def _balanced_braces(s, open_idx):
    """Given the index of a '{', return the substring through its matching
    '}' (inclusive), respecting nesting and string literals."""
    depth, i, n = 0, open_idx, len(s)
    quote = None
    while i < n:
        c = s[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[open_idx:i + 1]
        i += 1
    return s[open_idx:]


def _extract_ajax_calls(js):
    """Every $.ajax/$.post/$.get call in a script → list of
    {url, data(raw), method, json_mode}, using balanced-brace matching so
    the nested data:{…} object doesn't truncate the block."""
    calls = []
    for m in re.finditer(r'\$\.(ajax|post|get)\s*\(\s*\{', js):
        brace = js.index("{", m.end() - 1)
        block = _balanced_braces(js, brace)
        um = re.search(r'url\s*:\s*["\']([^"\']+)["\']', block)
        if not um:
            continue
        tm = re.search(r'type\s*:\s*["\'](\w+)["\']', block)
        method = (tm.group(1) if tm else
                  ("GET" if m.group(1) == "get" else "POST")).upper()
        calls.append({
            "url": um.group(1),
            "data": _parse_data_obj(block),
            "method": method,
            "json_mode": bool(re.search(r'contentType\s*:\s*["\']application/json', block)),
        })
    # bare $.get("url", {data}) / $.post("url", {data})
    for m in re.finditer(r'\$\.(get|post)\s*\(\s*["\']([^"\']+)["\']\s*,\s*\{', js):
        brace = js.index("{", m.end() - 1)
        block = _balanced_braces(js, brace)
        calls.append({
            "url": m.group(2),
            "data": _parse_data_obj("data:" + block),
            "method": m.group(1).upper(),
            "json_mode": False,
        })
    return calls


def _resolve_data(raw_data, event_id, tour_id):
    """Fill a raw data template with the real ids. Keys/values referencing
    event → eventId, tour/round → tourId; quoted/numeric literals kept as
    constants; unknown JS variables dropped."""
    out = {}
    for k, raw in raw_data.items():
        v = (raw or "").strip()
        if re.search(r"event", k, re.I) or re.fullmatch(r"eventId", v):
            out[k] = str(event_id)
        elif re.search(r"tour|round", k, re.I) or re.fullmatch(r"tourId|roundId", v):
            out[k] = str(tour_id)
        elif re.fullmatch(r'["\'][^"\']*["\']|\d+', v):
            out[k] = v.strip("'\"")
        # else: an unresolved JS variable — omit it
    return out


def discover_data_feed(cookie, event_id, tour_id):
    """Fetch Unknown Golf's score-display pages, find the AJAX call each
    makes to a *.ukg data endpoint, replay it with the real ids, and parse
    a JSON leaderboard. Returns (teams, diag)."""
    from urllib.parse import urljoin, urlparse
    diag = []
    display_pages = [
        f"https://{ALLOWED_HOST}/platform/tv/tvLeaderboard.jsp"
        f"?eventId={event_id}" + (f"&tourId={tour_id}" if tour_id else ""),
        f"https://{ALLOWED_HOST}/event.jsp?eventId={event_id}&tourId={tour_id}",
    ]
    seen_calls = set()
    for page_url in display_pages:
        try:
            page = _get(page_url, cookie).text
        except Exception as e:
            diag.append({"page": page_url, "error": str(e)[:120]})
            continue
        # collect JS: inline + same-host external scripts
        blobs = re.findall(r"(?is)<script\b[^>]*>(.*?)</script>", page)
        for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', page, re.I):
            src = urljoin(page_url, unescape(m.group(1)))
            if urlparse(src).netloc == ALLOWED_HOST and re.search(
                    r"leader|score|tv|game|result|event", src, re.I):
                try:
                    blobs.append(_get(src, cookie).text)
                except Exception:
                    pass
        for js in blobs:
            for call in _extract_ajax_calls(js):
                if not re.search(r"\.ukg|leader|score|game|result|standing",
                                 call["url"], re.I):
                    continue
                ep = urljoin(page_url, call["url"])
                if urlparse(ep).netloc != ALLOWED_HOST:
                    continue
                data = _resolve_data(call["data"], event_id, tour_id)
                key = (ep, tuple(sorted(data.items())), call["method"])
                if key in seen_calls:
                    continue
                seen_calls.add(key)
                try:
                    if call["method"] == "GET":
                        r = _session_get(ep, data, cookie)
                    else:
                        r = _post(ep, data, cookie, as_json=call["json_mode"])
                except Exception as e:
                    diag.append({"endpoint": ep, "data": data, "error": str(e)[:120]})
                    continue
                sample = r.text[:300]
                teams = []
                try:
                    teams = _teams_from_json(r.json())
                except Exception:
                    pass
                if len(teams) >= 2:
                    return teams, {"endpoint": ep, "data": data, "method": call["method"]}
                diag.append({"endpoint": ep, "data": data,
                             "method": call["method"], "status": r.status_code,
                             "sample": sample})
    return [], diag


def _post(url, data, cookie=None, as_json=False):
    headers = {"User-Agent": _UA, "X-Requested-With": "XMLHttpRequest",
               "Accept": "application/json, text/plain, */*"}
    if cookie:
        headers["Cookie"] = cookie
    if as_json:
        resp = requests.post(url, json=data, headers=headers, timeout=FETCH_TIMEOUT)
    else:
        resp = requests.post(url, data=data, headers=headers, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    return resp


def _session_get(url, params, cookie=None):
    headers = {"User-Agent": _UA, "X-Requested-With": "XMLHttpRequest",
               "Accept": "application/json, text/plain, */*"}
    if cookie:
        headers["Cookie"] = cookie
    resp = requests.get(url, params=params, headers=headers, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    return resp


def _teams_from_json(obj):
    """Best-effort: find a list of team-ish records in a JSON payload —
    a list of dicts each carrying a name-ish string and a score-ish
    number. Returns [] when nothing plausible is found."""
    name_keys = ("teamName", "team", "name", "displayName", "player", "entry")
    score_keys = ("toPar", "vsPar", "score", "total", "net", "totalToPar",
                  "scoreDisplay", "thruScore")
    best = []

    def walk(node):
        nonlocal best
        if isinstance(node, list):
            teams = []
            for it in node:
                if not isinstance(it, dict):
                    break
                nm = next((str(it[k]) for k in name_keys if it.get(k)), None)
                sv = None
                for k in score_keys:
                    if k in it and it[k] is not None:
                        sv = parse_score_token(str(it[k]))
                        if sv is not None:
                            break
                if nm:
                    teams.append({"name": nm, "score": sv,
                                  "raw": "", "players": [], "card": None})
            if len(teams) > len(best) and len(teams) >= 2:
                best = teams
            for it in node:
                walk(it)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)

    walk(obj)
    return best


def _get(url, cookie=None):
    headers = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"}
    if cookie:
        headers["Cookie"] = cookie
    resp = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    return resp


def _parse_page(html):
    """Run both parsers over one page; returns (payload, lines)."""
    payload = extract_leaderboard(html)
    lines = _text_lines(html)
    blocks = parse_scorecard_blocks(lines)
    scored = [t for t in blocks if t["score"] is not None]
    if len(blocks) >= 2 and (len(scored) >= 2 or not payload["found"]):
        payload["teams"] = blocks
        payload["mode"] = "blocks"
    return payload, lines


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
    if not cookie:
        cookie = stored_cookie()
    resp = _get(url, cookie)
    payload, lines = _parse_page(resp.text)
    payload["source_url"] = url
    payload["http_status"] = resp.status_code
    tried = [url]

    # No teams on the top-level page? The standings load from a separate
    # feed (JS/AJAX) — chase same-host scoring candidates (incl. URLs
    # found inside external scripts) and Unknown Golf's known leaderboard
    # endpoints, parsing HTML blocks/tables or a JSON leaderboard.
    cand_diag = []
    if not payload.get("teams") and not payload["found"]:
        # First: discover the leaderboard DATA FEED — find the AJAX call
        # the score-display pages make to a *.ukg endpoint and replay it.
        try:
            feed_teams, feed_diag = discover_data_feed(cookie, event_id, tour_id)
        except Exception as e:
            feed_teams, feed_diag = [], [{"error": f"feed discovery: {e}"}]
        if len(feed_teams) >= 2:
            return {"event_name": payload.get("event_name", ""),
                    "found": True, "teams": feed_teams, "mode": "feed",
                    "source_url": feed_diag.get("endpoint") if isinstance(feed_diag, dict) else url,
                    "http_status": 200, "via_feed": True, "tried_urls": tried}
        if feed_diag:
            cand_diag.append({"feed_probes": feed_diag})
        for sub in _gather_scoring_candidates(resp.text, url, event_id, tour_id, cookie):
            if sub in tried:
                continue
            tried.append(sub)
            try:
                sub_resp = _get(sub, cookie)
            except Exception as e:
                cand_diag.append({"url": sub, "error": str(e)[:120]})
                continue
            ctype = sub_resp.headers.get("Content-Type", "")
            body = sub_resp.text
            # JSON feed?
            if "json" in ctype.lower() or body.lstrip()[:1] in "[{":
                try:
                    jteams = _teams_from_json(sub_resp.json())
                except Exception:
                    jteams = []
                if len(jteams) >= 2:
                    return {"event_name": payload.get("event_name", ""),
                            "found": True, "teams": jteams, "mode": "json",
                            "source_url": sub, "http_status": sub_resp.status_code,
                            "via_subpage": True, "tried_urls": tried}
                cand_diag.append({"url": sub, "type": "json",
                                  "sample": body[:400]})
                continue
            sub_payload, sub_lines = _parse_page(body)
            if sub_payload.get("teams") or sub_payload["found"]:
                sub_payload["source_url"] = sub
                sub_payload["http_status"] = sub_resp.status_code
                sub_payload["via_subpage"] = True
                sub_payload["tried_urls"] = tried
                if not sub_payload.get("event_name"):
                    sub_payload["event_name"] = payload.get("event_name", "")
                return sub_payload
            cand_diag.append({"url": sub, "type": "html",
                              "tables": sub_payload.get("table_count", 0),
                              "sample": " ".join(sub_lines[:12])[:400]})

    # Diagnostics: when neither parser produced anything, ship the first
    # chunk of page text so the failure is visible in the response
    # (admin-only endpoint) instead of guessing at the markup again.
    if not payload["found"] and not payload.get("teams"):
        payload["sample_lines"] = lines[:80]
        payload["tried_urls"] = tried
        if cand_diag:
            payload["candidate_diag"] = cand_diag
        if _looks_logged_out(resp.text):
            payload["login_wall_suspected"] = True
    return payload
