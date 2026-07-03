"""Golf Genius handicap sync via HTTP requests.

Logs into golfgenius.com, navigates to GOLFERS → Upload Roster from
Spreadsheet, confirms authorization, uploads a CSV with (Email,
Handicap Index, Player Name), handles column mapping, and submits.

Uses requests.Session (no browser/Playwright required) so this works on
Railway and other minimal server environments.

Environment variables required:
    GOLF_GENIUS_EMAIL          — GG login email
    GOLF_GENIUS_PASSWORD       — GG login password
    GOLF_GENIUS_SA_LEAGUE_ID   — San Antonio league ID (e.g. 514047)
    GOLF_GENIUS_AUSTIN_LEAGUE_ID — Austin league ID (e.g. 514705)
"""

from __future__ import annotations

import csv
import io
import json as _json
from html import unescape as _unescape
import logging
import os
import re
from datetime import datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)

GG_BASE_URL = "https://www.golfgenius.com"
GG_LOGIN_URL = f"{GG_BASE_URL}/users/sign_in"

# Common headers to mimic a real browser
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _build_csv(rows: list[dict]) -> str:
    """Build a CSV string from export rows.

    Column names are chosen to match Golf Genius's expected field labels
    so GG can auto-detect the mapping where possible.
      Email          — unique identifier GG matches against
      Handicap Index — the 18-hole index value (9-hole x 2)
      Player Name    — informational only, not used by GG import
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Email", "Handicap Index", "Player Name"])
    for row in rows:
        writer.writerow([row["email"], row["handicap_index"], row["player_name"]])
    return buf.getvalue()


def _extract_csrf_token(html: str) -> str | None:
    """Extract the Rails CSRF authenticity token from page HTML."""
    # Try <meta name="csrf-token" content="...">
    m = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
    if m:
        return m.group(1)
    # Try <input name="authenticity_token" value="...">
    m = re.search(r'name="authenticity_token"[^>]*value="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'value="([^"]+)"[^>]*name="authenticity_token"', html)
    if m:
        return m.group(1)
    return None


def _extract_all_hidden_fields(html: str) -> dict[str, str]:
    """Extract all hidden input fields from HTML."""
    fields = {}
    for m in re.finditer(
        r'<input[^>]*type=["\']hidden["\'][^>]*>', html, re.IGNORECASE
    ):
        tag = m.group(0)
        name_m = re.search(r'name=["\']([^"\']+)["\']', tag)
        val_m = re.search(r'value=["\']([^"\']*)["\']', tag)
        if name_m:
            fields[name_m.group(1)] = val_m.group(1) if val_m else ""
    return fields


def _gg_login(sess: requests.Session, email: str, password: str) -> dict | None:
    """Log into Golf Genius. Returns None on success, error dict on failure."""
    logger.info("GG sync: fetching login page")
    login_page = sess.get(GG_LOGIN_URL, timeout=30)
    login_page.raise_for_status()

    csrf = _extract_csrf_token(login_page.text)
    if not csrf:
        return {
            "status": "error",
            "message": "Could not find CSRF token on Golf Genius login page",
        }

    logger.info("GG sync: logging in as %s", email)
    login_data = {
        "authenticity_token": csrf,
        "user[email]": email,
        "user[password]": password,
        "user[remember_me]": "0",
        "commit": "Log in",
    }
    login_resp = sess.post(
        GG_LOGIN_URL,
        data=login_data,
        timeout=30,
        allow_redirects=True,
    )

    if "sign_in" in login_resp.url:
        error_match = re.search(
            r'class="[^"]*(?:alert|error|flash)[^"]*"[^>]*>([^<]+)',
            login_resp.text,
        )
        error_msg = (
            error_match.group(1).strip() if error_match
            else "Invalid email or password"
        )
        return {"status": "error", "message": f"Login failed: {error_msg}"}

    logger.info("GG sync: logged in, redirected to %s", login_resp.url)
    return None  # success


def sync_handicaps_to_league(
    rows: list[dict],
    league_id: str,
    email: str,
    password: str,
    screenshot_dir: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Upload handicap indexes to a Golf Genius league via HTTP requests.

    Flow (mirrors the manual browser steps):
      1. Login to golfgenius.com
      2. Navigate to GOLFERS → Upload Roster from Spreadsheet
         URL: /leagues/{league_id}/members?open_option=upload_roster_options
      3. Parse the page for the upload form, confirm authorization
      4. POST the CSV file
      5. Handle column mapping if presented
      6. Read result

    Args:
        rows: list of {"email": ..., "handicap_index": ..., "player_name": ...}
        league_id: Golf Genius league ID (numbers only)
        email: Golf Genius account email
        password: Golf Genius account password
        screenshot_dir: unused (kept for API compatibility)
        dry_run: if True, return without actually uploading

    Returns:
        {"status": "ok"|"error", "message": str, "rows_submitted": int,
         "timestamp": ISO str}
    """
    timestamp = datetime.utcnow().isoformat()

    if dry_run:
        return {
            "status": "dry_run",
            "message": f"Dry run — would submit {len(rows)} player(s): "
                       + ", ".join(r["player_name"] for r in rows[:5])
                       + ("..." if len(rows) > 5 else ""),
            "rows_submitted": 0,
            "timestamp": timestamp,
        }

    csv_content = _build_csv(rows)
    sess = requests.Session()
    sess.headers.update(_HEADERS)

    try:
        # ── Step 1: Login ─────────────────────────────────────────────
        login_err = _gg_login(sess, email, password)
        if login_err:
            return {**login_err, "rows_submitted": 0, "timestamp": timestamp}

        # ── Step 2: Navigate to the roster upload page ────────────────
        # This is GOLFERS → Upload Roster from Spreadsheet
        members_url = (
            f"{GG_BASE_URL}/leagues/{league_id}/members"
            f"?open_option=upload_roster_options"
        )
        logger.info("GG sync: navigating to %s", members_url)
        members_resp = sess.get(members_url, timeout=30)

        if members_resp.status_code == 404:
            return {
                "status": "error",
                "message": (
                    f"Members page not found for league {league_id}. "
                    f"URL: {members_url}"
                ),
                "rows_submitted": 0,
                "timestamp": timestamp,
            }
        members_resp.raise_for_status()
        page_html = members_resp.text

        logger.info(
            "GG sync: members page loaded (url=%s, %d bytes)",
            members_resp.url, len(page_html),
        )

        # ── Step 3: Upload CSV to the spreadsheetfiles endpoint ───────
        # Confirmed endpoint: POST /leagues/{id}/spreadsheetfiles
        # This creates a spreadsheet file record, then redirects to
        # /leagues/{id}/spreadsheetfiles/{file_id}/post_prepare
        csrf = _extract_csrf_token(page_html)

        upload_url = f"{GG_BASE_URL}/leagues/{league_id}/spreadsheetfiles"
        csv_bytes = csv_content.encode("utf-8")

        upload_data = {}
        if csrf:
            upload_data["authenticity_token"] = csrf

        # Try several possible file field names
        possible_field_names = [
            "spreadsheet_file[file]",
            "file",
            "spreadsheet_file",
            "spreadsheetfile[file]",
        ]

        # Check if there's a file input on the page to determine field name
        file_inputs = re.findall(
            r'<input[^>]*type=["\']file["\'][^>]*>', page_html, re.IGNORECASE
        )
        for fi in file_inputs:
            name_m = re.search(r'name=["\']([^"\']+)["\']', fi)
            if name_m and "photo" not in fi.lower():
                found_name = name_m.group(1)
                if found_name not in possible_field_names:
                    possible_field_names.insert(0, found_name)
                logger.info("GG sync: file input name from page: %s", found_name)

        upload_resp = None
        for field_name in possible_field_names:
            files = {
                field_name: ("handicaps.csv", csv_bytes, "text/csv"),
            }
            logger.info(
                "GG sync: POST %s (field=%s, %d rows)",
                upload_url, field_name, len(rows),
            )
            resp = sess.post(
                upload_url,
                data=upload_data,
                files=files,
                timeout=60,
                allow_redirects=True,
            )
            logger.info(
                "GG sync: POST → status %d, final url: %s",
                resp.status_code, resp.url,
            )
            # Success: 200 or redirect followed to post_prepare page
            if resp.status_code in (200, 201):
                upload_resp = resp
                logger.info("GG sync: upload succeeded with field=%s", field_name)
                break
            elif resp.status_code == 422:
                logger.info("GG sync: 422 with field=%s, trying next", field_name)
                continue
            else:
                logger.info(
                    "GG sync: status %d with field=%s, response: %s",
                    resp.status_code, field_name, resp.text[:500],
                )
                # If we got a non-404 error, the endpoint exists
                if resp.status_code != 404:
                    continue
                # 404 means wrong endpoint entirely, stop trying field names
                break

        if not upload_resp:
            return {
                "status": "error",
                "message": (
                    f"CSV upload failed to {upload_url}. "
                    f"Tried field names: {possible_field_names}."
                ),
                "rows_submitted": 0,
                "timestamp": timestamp,
            }

        page_html = upload_resp.text

        # ── Step 4: Handle post_prepare page ─────────────────────────
        # After upload, GG shows a post_prepare page. For active leagues,
        # it shows a warning: "This league has started and we cannot replace
        # the player roster" with options: "Cancel" or "Add New Golfers".
        # We need to click "Add New Golfers" to proceed.

        if "post_prepare" in upload_resp.url or "post_prepare" in page_html:
            logger.info("GG sync: on post_prepare page: %s", upload_resp.url)

            # Check for the "Add New Golfers" button/link
            add_new_match = re.search(
                r'href="([^"]*)"[^>]*>(?:[^<]*Add New Golfers[^<]*)</a>',
                page_html, re.IGNORECASE,
            )
            if not add_new_match:
                # Try as a form button
                add_new_match = re.search(
                    r'<(?:a|button)[^>]*(?:href|formaction)="([^"]*)"[^>]*>[^<]*Add New[^<]*',
                    page_html, re.IGNORECASE,
                )

            if add_new_match:
                add_url = add_new_match.group(1)
                if add_url.startswith("/"):
                    add_url = GG_BASE_URL + add_url
                logger.info("GG sync: clicking 'Add New Golfers': %s", add_url)

                new_csrf = _extract_csrf_token(page_html) or csrf
                add_data = _extract_all_hidden_fields(page_html)
                if new_csrf:
                    add_data["authenticity_token"] = new_csrf

                add_resp = sess.get(add_url, timeout=30)
                logger.info(
                    "GG sync: 'Add New Golfers' → status %d, url: %s",
                    add_resp.status_code, add_resp.url,
                )
                if add_resp.status_code == 200:
                    page_html = add_resp.text
                else:
                    add_resp.raise_for_status()
            else:
                # No "Add New Golfers" — might be a new league where replace is OK
                # Look for any continue/submit button
                logger.info("GG sync: no 'Add New Golfers' found, checking for other options")

                # Log the page content for debugging
                logger.info(
                    "GG sync: post_prepare page (first 1000 chars): %s",
                    page_html[:1000],
                )

        # ── Step 5: Handle column mapping page ────────────────────────
        # After upload, GG may show a column mapping page with dropdowns
        # where you map CSV columns to GG fields.
        has_mapping = bool(re.search(r'<select[^>]*>', page_html))
        mapping_form_match = re.search(
            r'<form[^>]*action="([^"]*)"[^>]*>', page_html
        )

        if has_mapping and mapping_form_match:
            logger.info("GG sync: column mapping page detected, submitting mapping")
            mapping_action = mapping_form_match.group(1)
            if mapping_action.startswith("/"):
                mapping_action = GG_BASE_URL + mapping_action

            new_csrf = _extract_csrf_token(page_html)
            mapping_data = _extract_all_hidden_fields(page_html)
            if new_csrf:
                mapping_data["authenticity_token"] = new_csrf

            # Parse select elements and map columns intelligently
            selects = re.findall(
                r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>',
                page_html, re.DOTALL,
            )

            for sel_name, sel_body in selects:
                sel_pos = page_html.find(f'name="{sel_name}"')
                context = page_html[max(0, sel_pos - 500):sel_pos].lower()

                options = re.findall(
                    r'<option\s+value="([^"]*)"[^>]*>([^<]*)</option>',
                    sel_body,
                )
                opt_dict = {t.strip().lower(): v for v, t in options}
                opt_texts = [t.strip().lower() for _, t in options]

                # Map identifier/unique field → Email
                if any(kw in context for kw in (
                    "unique", "identifier", "match", "player id"
                )):
                    for label in ("email", "e-mail"):
                        if label in opt_dict:
                            mapping_data[sel_name] = opt_dict[label]
                            logger.info("GG sync: mapped '%s' → Email", sel_name)
                            break
                # Map handicap field → Handicap Index
                elif any(kw in context for kw in ("handicap", "index", "hcp")):
                    for label in ("handicap index", "handicap_index", "index"):
                        if label in opt_dict:
                            mapping_data[sel_name] = opt_dict[label]
                            logger.info(
                                "GG sync: mapped '%s' → Handicap Index", sel_name
                            )
                            break
                # Fallback: if option list has "email", use it
                elif any("email" in t for t in opt_texts):
                    for label in ("email", "e-mail"):
                        if label in opt_dict:
                            mapping_data[sel_name] = opt_dict[label]
                            break
                elif any("handicap" in t for t in opt_texts):
                    for label in ("handicap index", "handicap_index", "index"):
                        if label in opt_dict:
                            mapping_data[sel_name] = opt_dict[label]
                            break

            # Look for submit button
            submit_match = re.search(
                r'<input[^>]*type="submit"[^>]*value="([^"]*)"[^>]*name="([^"]*)"',
                page_html,
            )
            if submit_match:
                mapping_data[submit_match.group(2)] = submit_match.group(1)

            mapping_resp = sess.post(
                mapping_action,
                data=mapping_data,
                timeout=60,
                allow_redirects=True,
            )
            mapping_resp.raise_for_status()
            page_html = mapping_resp.text
            logger.info(
                "GG sync: mapping submitted, response URL: %s",
                mapping_resp.url,
            )

        # ── Step 6: Read result message ───────────────────────────────
        result_text = ""
        for pattern in [
            r'class="[^"]*(?:flash|alert|notice|success)[^"]*"[^>]*>([^<]+)',
            r'id="flash"[^>]*>([^<]+)',
            r'<div[^>]*class="[^"]*message[^"]*"[^>]*>([^<]+)',
        ]:
            m = re.search(pattern, page_html)
            if m:
                result_text = m.group(1).strip()
                if result_text:
                    break

        if not result_text:
            result_text = f"Upload submitted for {len(rows)} players"

        logger.info("GG sync: result — %s", result_text)

        return {
            "status": "ok",
            "message": result_text,
            "rows_submitted": len(rows),
            "timestamp": timestamp,
        }

    except requests.Timeout:
        logger.error("GG sync: request timed out")
        return {
            "status": "error",
            "message": "Request timed out connecting to Golf Genius",
            "rows_submitted": 0,
            "timestamp": timestamp,
        }
    except requests.ConnectionError as exc:
        logger.error("GG sync: connection error: %s", exc)
        return {
            "status": "error",
            "message": f"Could not connect to Golf Genius: {exc}",
            "rows_submitted": 0,
            "timestamp": timestamp,
        }
    except requests.HTTPError as exc:
        logger.error("GG sync: HTTP error: %s", exc)
        return {
            "status": "error",
            "message": f"Golf Genius returned an error: {exc}",
            "rows_submitted": 0,
            "timestamp": timestamp,
        }
    except Exception as exc:
        logger.exception("GG sync: unexpected error")
        return {
            "status": "error",
            "message": str(exc),
            "rows_submitted": 0,
            "timestamp": timestamp,
        }


def run_scheduled_sync(db_path=None) -> dict[str, Any]:
    """Run handicap sync for both SA and Austin leagues.

    Called by the APScheduler job. Reads credentials and league IDs
    from environment variables.

    Returns a dict with results for both chapters:
        {"san_antonio": {...}, "austin": {...}}
    """
    from email_parser.database import get_handicap_export_data, update_handicap_settings

    gg_email = os.getenv("GOLF_GENIUS_EMAIL", "").strip()
    gg_password = os.getenv("GOLF_GENIUS_PASSWORD", "").strip()
    sa_league_id = os.getenv("GOLF_GENIUS_SA_LEAGUE_ID", "514047").strip()
    austin_league_id = os.getenv("GOLF_GENIUS_AUSTIN_LEAGUE_ID", "514705").strip()

    if not gg_email or not gg_password:
        msg = "GOLF_GENIUS_EMAIL and GOLF_GENIUS_PASSWORD env vars not set"
        logger.warning("GG sync skipped: %s", msg)
        return {"san_antonio": {"status": "skipped", "message": msg},
                "austin": {"status": "skipped", "message": msg}}

    results: dict[str, Any] = {}

    for chapter, league_id, key in [
        ("San Antonio", sa_league_id, "san_antonio"),
        ("Austin", austin_league_id, "austin"),
    ]:
        logger.info("GG sync: starting %s (league %s)", chapter, league_id)
        export = get_handicap_export_data(chapter=chapter, db_path=db_path)
        rows = export["rows"]

        if not rows:
            results[key] = {
                "status": "skipped",
                "message": f"No players with email + handicap index for {chapter}",
                "rows_submitted": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }
            continue

        result = sync_handicaps_to_league(
            rows=rows,
            league_id=league_id,
            email=gg_email,
            password=gg_password,
        )
        results[key] = result
        logger.info("GG sync %s: %s", chapter, result)

    # Persist last sync result in settings for the UI
    import json
    update_handicap_settings({"last_gg_sync": json.dumps(results)}, db_path=db_path)

    return results


# ─────────────────────────────────────────────────────────────────────────
#  Public-page probe (read-only, no login)
#
#  Powers the MCP `probe_golf_genius` tool: fetch a public GG portal page
#  from the Railway side (which has open egress to golfgenius.com) and
#  return a parsed structure. This is the exploration path for importing
#  results/standings data into the tracker.
# ─────────────────────────────────────────────────────────────────────────

def _require_gg_host(url: str) -> None:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only https:// URLs are allowed")
    host = (parsed.hostname or "").lower()
    if host != "golfgenius.com" and not host.endswith(".golfgenius.com"):
        raise ValueError("Only golfgenius.com URLs are allowed")


def fetch_public_page(url: str, timeout: int = 20, xhr: bool = False) -> dict:
    """Fetch a public Golf Genius page without logging in.

    The host allowlist is a hard requirement: this function is exposed
    through an MCP tool, so without it the tool would be an open proxy
    into the Railway network (SSRF). Redirect targets are re-validated.

    xhr=True mimics jQuery's dataType:"script" ajax — GG's widget detail
    routes (e.g. season_points_v2/individual_info) return a JS partial
    only for XHR requests and fall back to a full page otherwise.
    """
    _require_gg_host(url)
    headers = dict(_HEADERS)
    if xhr:
        headers["Accept"] = "text/javascript, application/javascript, */*; q=0.01"
        headers["X-Requested-With"] = "XMLHttpRequest"
    resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    _require_gg_host(resp.url)
    return {"status_code": resp.status_code, "final_url": resp.url, "html": resp.text}


def parse_page_structure(html: str, base_url: str) -> dict:
    """Extract title, headings, links, tables, and visible text from a page.

    Stdlib-only (html.parser) — the app has no bs4/lxml dependency and a
    tolerant rough parse is all the probe needs.
    """
    from html.parser import HTMLParser
    from urllib.parse import urljoin

    class _P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.title = ""
            self.headings: list = []
            self.links: list = []
            self.tables: list = []
            self.text_parts: list = []
            self._skip_depth = 0          # inside <script>/<style>
            self._in_title = False
            self._heading: list | None = None   # [tag, buf]
            self._link: list | None = None      # [href, buf]
            self._table_stack: list = []        # nested tables
            self._cell: list | None = None

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag in ("script", "style", "noscript"):
                self._skip_depth += 1
            elif tag == "title":
                self._in_title = True
            elif tag in ("h1", "h2", "h3", "h4"):
                self._heading = [tag, []]
            elif tag == "a" and a.get("href"):
                self._link = [a["href"], []]
            elif tag == "table":
                self._table_stack.append([])
            elif tag == "tr" and self._table_stack:
                self._table_stack[-1].append([])
            elif tag in ("td", "th") and self._table_stack:
                if not self._table_stack[-1]:
                    self._table_stack[-1].append([])
                self._cell = []

        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript"):
                self._skip_depth = max(0, self._skip_depth - 1)
            elif tag == "title":
                self._in_title = False
            elif tag in ("h1", "h2", "h3", "h4") and self._heading:
                text = " ".join("".join(self._heading[1]).split())
                if text:
                    self.headings.append({"tag": self._heading[0], "text": text})
                self._heading = None
            elif tag == "a" and self._link:
                text = " ".join("".join(self._link[1]).split())
                self.links.append({"text": text, "href": urljoin(base_url, self._link[0])})
                self._link = None
            elif tag in ("td", "th") and self._cell is not None:
                if self._table_stack and self._table_stack[-1]:
                    self._table_stack[-1][-1].append(
                        " ".join("".join(self._cell).split()))
                self._cell = None
            elif tag == "table" and self._table_stack:
                rows = [r for r in self._table_stack.pop() if r]
                if rows:
                    self.tables.append(rows)

        def handle_data(self, data):
            if self._skip_depth:
                return
            if self._in_title:
                self.title += data
            if self._heading is not None:
                self._heading[1].append(data)
            if self._link is not None:
                self._link[1].append(data)
            if self._cell is not None:
                self._cell.append(data)
            if data.strip():
                self.text_parts.append(data.strip())

    p = _P()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass  # tolerate malformed HTML — return whatever was collected

    # Dedup links preserving order
    seen = set()
    links = []
    for lk in p.links:
        key = (lk["text"], lk["href"])
        if key in seen:
            continue
        seen.add(key)
        links.append(lk)

    return {
        "title": " ".join(p.title.split()),
        "headings": p.headings,
        "links": links,
        "tables": p.tables,
        "text": "\n".join(p.text_parts),
    }


def fetch_season_points_race(page_id: str, league_id: str = "514047",
                             host: str = "tgf-sa.golfgenius.com") -> list:
    """Fetch and normalize a season_points_v2 widget (points race standings).

    The portal's curated race pages (e.g. SAN ANTONIO Net 2026) embed this
    widget in an iframe keyed by page_id. Returns one dict per player:
    rank, prev_rank, player_name, affiliation, tournaments, wins,
    total_points, points_behind.
    """
    url = (f"https://{host}/leagues/{league_id}/widgets/season_points_v2"
           f"?page_id={page_id}&shared=false")
    page = fetch_public_page(url)
    if page["status_code"] != 200:
        raise RuntimeError(f"Golf Genius widget returned HTTP {page['status_code']}")
    parsed = parse_page_structure(page["html"], page["final_url"])

    def _num(s):
        s = str(s).strip()
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return None

    for table in parsed["tables"]:
        header = [c.lower() for c in table[0]] if table else []
        if not any("total points" in h for h in header):
            continue
        idx = {}
        for i, h in enumerate(header):
            if "current rank" in h or h == "pos.":
                idx["rank"] = i
            elif "previous rank" in h:
                idx["prev_rank"] = i
            elif "player" in h:
                idx["player"] = i
            elif "affiliation" in h:
                idx["affiliation"] = i
            elif "tournaments" in h:
                idx["tournaments"] = i
            elif "wins" in h:
                idx["wins"] = i
            elif "total points" in h:
                idx["points"] = i
            elif "behind" in h:
                idx["behind"] = i
        if "player" not in idx:
            continue

        def cell(r, key):
            i = idx.get(key)
            return r[i].strip() if i is not None and i < len(r) else ""

        # Player rows carry data-member-card-id on the expandable name link —
        # the key GG's individual_info endpoint needs for per-round detail
        card_ids = dict(re.findall(
            r'data-member-card-id="(\d+)"[^>]*>\s*([^<]+?)\s*</a>',
            page["html"],
        ))
        card_by_name = {name: cid for cid, name in card_ids.items()}

        rows = []
        for r in table[1:]:
            player = cell(r, "player")
            if not player:
                continue
            rows.append({
                "rank": cell(r, "rank"),
                "prev_rank": cell(r, "prev_rank"),
                "player_name": player,
                "affiliation": cell(r, "affiliation"),
                "tournaments": _num(cell(r, "tournaments")),
                "wins": _num(cell(r, "wins")),
                "total_points": _num(cell(r, "points")),
                "points_behind": _num(cell(r, "behind")),
                "member_card_id": card_by_name.get(player),
            })
        if rows:
            return rows
    raise RuntimeError("No points-race table found in widget HTML")


def fetch_points_race_member_detail(page_id: str, member_card_id: str,
                                    league_id: str = "514047",
                                    host: str = "tgf-sa.golfgenius.com",
                                    effective_date: str | None = None) -> dict:
    """Fetch one player's per-round points breakdown (the row expansion).

    GG's widget loads this via XHR: GET season_points_v2/individual_info
    with member_card_id (+ optional effective_date), answered as a JS
    partial that injects an HTML fragment. We unwrap the fragment and
    return its parsed tables; if GG ever answers with plain HTML we parse
    that directly — refusing the result if it looks like the standings
    page instead of a per-player breakdown.
    """
    if not str(member_card_id).isdigit():
        raise ValueError("member_card_id must be numeric")
    from datetime import date as _date
    eff = effective_date or _date.today().isoformat()
    url = (f"https://{host}/leagues/{league_id}/widgets/season_points_v2/"
           f"individual_info?page_id={page_id}&shared=false"
           f"&member_card_id={member_card_id}&effective_date={eff}")
    page = fetch_public_page(url, xhr=True)
    if page["status_code"] != 200:
        raise RuntimeError(f"Golf Genius returned HTTP {page['status_code']}")
    body = page["html"]

    # JS-partial shape: $("#info_<id>").append("<escaped fragment>") — GG
    # uses .append() here; accept the other jQuery injectors too
    frag = None
    m = re.search(
        r'\.(?:append|html|prepend|replaceWith)\(\s*"((?:\\.|[^"\\])*)"',
        body, re.S)
    if m:
        s = m.group(1).replace("\\'", "'")
        try:
            import json as _json
            frag = _json.loads('"' + s + '"')
        except ValueError:
            frag = (s.replace('\\"', '"').replace("\\n", "\n")
                     .replace("\\t", "\t").replace("\\/", "/"))
    parsed = parse_page_structure(frag if frag else body, page["final_url"])

    tables = parsed["tables"]
    # Guard: a full standings page means the XHR shape wasn't honored
    for t in tables:
        header = " ".join(t[0]).lower() if t else ""
        if "current rank" in header and "points behind" in header:
            raise RuntimeError(
                "Unexpected response (standings page, not player detail) — "
                "GG may have changed the individual_info endpoint")
    return {
        "member_card_id": str(member_card_id),
        "headings": parsed["headings"],
        "tables": tables,
    }


# ─────────────────────────────────────────────────────────────────────────
#  Scorecard extraction (Phase 1 of the scoring-records project)
#
#  GG's tournament pages expose per-player XHR partials:
#    /tournaments2/details/<aggregate_id>  → hole-by-hole strokes, handicap
#        dots (strokes received per hole), par-relative result classes,
#        playing handicap, gross/net sums
#    /tournaments2/nets/<net_id>?event_id= → tee block: course, tee, slope,
#        rating, per-hole yardage/par/stroke index
#  Everything parsed here is committed to tracker-owned tables — GG is an
#  input, never the system of record.
# ─────────────────────────────────────────────────────────────────────────

def _unwrap_js_string(body: str) -> str | None:
    """Extract the longest JS string literal from a script partial and
    decode it (GG partials wrap their HTML payload in one big argument)."""
    best = None
    for m in re.finditer(r'"((?:\\.|[^"\\])*)"', body, re.S):
        if best is None or len(m.group(1)) > len(best):
            best = m.group(1)
    if not best or len(best) < 50:
        return None
    s = best.replace("\\'", "'")
    try:
        import json as _json
        return _json.loads('"' + s + '"')
    except ValueError:
        return (s.replace('\\"', '"').replace("\\n", "\n")
                 .replace("\\t", "\t").replace("\\/", "/"))


def parse_tournament_aggregates(html: str) -> list:
    """Aggregate (player-row) ids from a v2tournaments page."""
    return list(dict.fromkeys(re.findall(r"/tournaments2/details/(\d+)", html)))


# Par-relative result classes GG stamps on hole cells
_RESULT_CLASSES = ("double_circle", "simple_circle", "double_square",
                   "simple_square")


def parse_scorecard_details(fragment: str) -> dict:
    """Parse a details partial: one or more net-line player rows.

    Returns {"flight": str|None, "players": [
        {"player_name", "playing_handicap", "net_id", "gg_event_id",
         "gg_profile_id", "holes": {n: {"strokes", "dots", "result"}},
         "sum_front", "sum_back", "gross", "net"}]}
    """
    flight = None
    m = re.search(r"<td colspan='\d+'>\s*(Flight[^<]*)</td>", fragment)
    if m:
        flight = _unescape(" ".join(m.group(1).split()))
    prof = re.search(r"/profiles/(\d+)", fragment)

    players = []
    # Split on net-line rows; each carries data-net-name
    chunks = re.split(r"(<tr class='net-line'[^>]*>)", fragment)
    for i in range(1, len(chunks), 2):
        head, body = chunks[i], chunks[i + 1]
        nm = re.search(r"data-net-name='([^']*)'", head)
        name = _unescape(nm.group(1)) if nm else None
        ph = None
        link = re.search(
            r"expand-tee-details[^>]*href=\"(/tournaments2/nets/(\d+)\?event_id=(\d+))\"[^>]*>([^<]*)",
            body)
        net_id = gg_event_id = None
        if link:
            net_id, gg_event_id = link.group(2), link.group(3)
            # Plus handicaps render as "(+1)" — stored NEGATIVE so the
            # arithmetic stays uniform: net = gross - ph (36 - (-1) = 37)
            phm = re.search(r"\((\+?\d+(?:\.\d+)?)\)", link.group(4))
            if phm:
                raw_ph = phm.group(1)
                ph = -float(raw_ph[1:]) if raw_ph.startswith("+") else float(raw_ph)
        holes = {}
        for hm in re.finditer(
                r"<td class='([^']*\bhole(\d+)\b[^']*)'[^>]*>(.*?)</td>",
                body, re.S):
            classes, hole_no, cell = hm.group(1), int(hm.group(2)), hm.group(3)
            sm = re.search(r"score_box'>\s*([0-9]+)\s*<", cell)
            strokes = int(sm.group(1)) if sm else None
            dots = cell.count("●")
            result = next((c for c in _RESULT_CLASSES if c in classes), None)
            holes[hole_no] = {"strokes": strokes, "dots": dots,
                              "result": result}
        def _num(cls):
            m2 = re.search(r"<td class='%s'[^>]*>\s*([0-9.]+)" % cls, body)
            return float(m2.group(1)) if m2 else None
        players.append({
            "player_name": name,
            "playing_handicap": ph,
            "net_id": net_id,
            "gg_event_id": gg_event_id,
            "gg_profile_id": prof.group(1) if prof else None,
            "holes": holes,
            "sum_front": _num("sum_front"),
            "sum_back": _num("sum_back"),
            "gross": _num("sum"),
            "net": _num("net_sum"),
        })
    return {"flight": flight, "players": players}


def parse_tee_block(fragment: str) -> dict | None:
    """Parse a nets partial: course/tee/slope/rating + per-hole rows."""
    hm = re.search(
        r"tee_data[^>]*>\s*<td[^>]*>\s*([^<]*SLOPE[^<]*)</td>", fragment)
    if not hm:
        return None
    header = _unescape(" ".join(hm.group(1).split()))
    # "1 - Blue Tee / SLOPE®: 135 / Course Rating™: 36.6 / TPC San Antonio - Oaks"
    parts = [p.strip() for p in header.split("/")]
    tee_name = parts[0] if parts else header
    slope = rating = None
    course = parts[-1] if len(parts) >= 4 else None
    sm = re.search(r"SLOPE[^:]*:\s*([0-9]+)", header)
    if sm:
        slope = int(sm.group(1))
    rm = re.search(r"Rating[^:]*:\s*([0-9.]+)", header)
    if rm:
        rating = float(rm.group(1))

    def row_vals(row_class):
        rm2 = re.search(r"<tr class='%s[^']*'>(.*?)</tr>" % row_class,
                        fragment, re.S)
        if not rm2:
            return []
        cells = re.findall(r"<td[^>]*>\s*([^<]*?)\s*</td>", rm2.group(1))
        vals = []
        for c in cells[1:]:          # skip label cell
            c = c.strip()
            vals.append(int(c) if c.isdigit() else None)
        return vals

    def per_hole(vals):
        # Cells run holes 1-9, Out, 10-18, In, Total — keep hole cells only
        out = {}
        hole = 1
        for idx, v in enumerate(vals):
            if idx in (9, 19, 20, 21):   # Out, In, Total, extra
                continue
            if hole > 18:
                break
            if v is not None:
                out[hole] = v
            hole += 1
        return out

    return {
        "course": course,
        "tee_name": tee_name,
        "slope": slope,
        "rating": rating,
        "yardage": per_hole(row_vals("yardage_row")),
        "par": per_hole(row_vals("par_row")),
        "stroke_index": per_hole(row_vals("handicap_row")),
    }


def fetch_tournament_scorecards(tournament_url: str,
                                pause: float = 0.15) -> dict:
    """Walk a v2tournaments page: every player's scorecard + tee blocks.

    Returns {"players": [merged detail dicts + "tee" key], "raw": [(url, body)]}
    — raw responses are returned so the caller can archive them.
    """
    import time as _time
    _require_gg_host(tournament_url)
    from urllib.parse import urlparse
    base = "https://" + urlparse(tournament_url).hostname

    page = fetch_public_page(tournament_url)
    if page["status_code"] != 200:
        raise RuntimeError(f"GG returned HTTP {page['status_code']} for tournament page")
    raw = [(tournament_url, page["html"])]
    agg_ids = parse_tournament_aggregates(page["html"])

    players = []
    tee_cache: dict = {}
    for agg in agg_ids:
        url = f"{base}/tournaments2/details/{agg}"
        resp = fetch_public_page(url, xhr=True)
        raw.append((url, resp["html"]))
        frag = _unwrap_js_string(resp["html"])
        if not frag:
            continue
        parsed = parse_scorecard_details(frag)
        for p in parsed["players"]:
            p["flight"] = parsed["flight"]
            p["gg_aggregate_id"] = agg
            tee = None
            if p.get("net_id"):
                if p["net_id"] in tee_cache:
                    tee = tee_cache[p["net_id"]]
                else:
                    nurl = (f"{base}/tournaments2/nets/{p['net_id']}"
                            f"?event_id={p.get('gg_event_id') or ''}")
                    nresp = fetch_public_page(nurl, xhr=True)
                    raw.append((nurl, nresp["html"]))
                    nfrag = _unwrap_js_string(nresp["html"])
                    tee = parse_tee_block(nfrag) if nfrag else None
                    tee_cache[p["net_id"]] = tee
            p["tee"] = tee
            players.append(p)
        if pause:
            _time.sleep(pause)
    return {"players": players, "raw": raw}
