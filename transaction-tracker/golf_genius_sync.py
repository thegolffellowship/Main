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

        # ── Step 3: Find the upload form and endpoint ─────────────────
        # The upload form is in a sidebar panel on the members page itself
        # (opened by ?open_option=upload_roster_options). We need to find
        # the <form> with a file input that is NOT the photo upload form.
        csrf = _extract_csrf_token(page_html)

        # Log all forms on the page for debugging
        all_form_actions = re.findall(
            r'<form[^>]*action="([^"]*)"[^>]*>', page_html, re.IGNORECASE
        )
        logger.info("GG sync: all form actions on page: %s", all_form_actions)

        # Find ALL forms with their full tag + body up to next </form>
        form_blocks = re.findall(
            r'(<form[^>]*>)(.*?)</form>', page_html, re.DOTALL | re.IGNORECASE
        )
        logger.info("GG sync: found %d form blocks total", len(form_blocks))

        form_action = None
        file_input_name = "file"

        # Strategy 1: Find form blocks that contain a file input
        # but are NOT the photo upload form
        for form_tag, form_body in form_blocks:
            # Check if this form has a file input
            has_file = bool(re.search(
                r'<input[^>]*type=["\']file["\']', form_body, re.IGNORECASE
            ))
            if not has_file:
                continue

            # Extract action
            action_m = re.search(r'action="([^"]*)"', form_tag, re.IGNORECASE)
            action = action_m.group(1) if action_m else ""

            # Skip photo/avatar upload forms
            combined = (action + form_body[:500]).lower()
            if "photo" in combined or "avatar" in combined:
                logger.info("GG sync: skipping photo form: %s", action)
                continue

            form_action = action
            logger.info("GG sync: found file upload form: action=%s", action)

            # Extract file input name
            fi_m = re.search(
                r'<input[^>]*type=["\']file["\'][^>]*name=["\']([^"\']+)["\']',
                form_body, re.IGNORECASE,
            )
            if not fi_m:
                fi_m = re.search(
                    r'<input[^>]*name=["\']([^"\']+)["\'][^>]*type=["\']file["\']',
                    form_body, re.IGNORECASE,
                )
            if fi_m:
                file_input_name = fi_m.group(1)
                logger.info("GG sync: file input name: %s", file_input_name)

            # Log the form body snippet for debugging
            logger.info(
                "GG sync: form body (first 600 chars): %s",
                form_body[:600],
            )
            break

        # Strategy 2: If no form with file input found, look for
        # JavaScript upload endpoints or data attributes
        if not form_action:
            # Look for data-url or data-upload-url attributes
            data_urls = re.findall(
                r'data-(?:url|upload[_-]?url|action)=["\']([^"\']+)["\']',
                page_html, re.IGNORECASE,
            )
            logger.info("GG sync: data-url attributes: %s", data_urls)

            # Look for JS URLs referencing upload/spreadsheet
            js_urls = re.findall(
                r'["\'](/[^"\']*(?:spreadsheet_file|spreadsheetfile|upload_roster|import_roster)[^"\']*)["\']',
                page_html, re.IGNORECASE,
            )
            logger.info("GG sync: JS upload URLs: %s", js_urls)
            for url in js_urls:
                if "photo" not in url.lower():
                    form_action = url
                    logger.info("GG sync: using JS upload URL: %s", url)
                    break

        # Strategy 3: Try known GG endpoint patterns
        if not form_action:
            candidate_paths = [
                f"/leagues/{league_id}/spreadsheet_files",
                f"/leagues/{league_id}/members/spreadsheet_files",
                f"/leagues/{league_id}/members/upload_roster",
                f"/leagues/{league_id}/members/import_from_spreadsheet",
                f"/leagues/{league_id}/members/upload_spreadsheet",
                f"/leagues/{league_id}/members/import",
            ]
            for candidate in candidate_paths:
                test_url = GG_BASE_URL + candidate
                logger.info("GG sync: probing %s", test_url)
                try:
                    test_resp = sess.get(test_url, timeout=15, allow_redirects=False)
                    logger.info(
                        "GG sync: %s → status %d", candidate, test_resp.status_code
                    )
                    if test_resp.status_code in (200, 302, 405):
                        form_action = candidate
                        break
                except Exception as e:
                    logger.warning("GG sync: probe failed for %s: %s", candidate, e)

        # Log context around key HTML elements for debugging
        if not form_action:
            for keyword in ["Choose File", "spreadsheet", "upload_roster",
                            "file_field", "type=\"file\""]:
                idx = page_html.lower().find(keyword.lower())
                if idx >= 0:
                    snippet = page_html[max(0, idx - 300):idx + 300]
                    logger.info(
                        "GG sync: HTML context around '%s': ...%s...",
                        keyword, snippet,
                    )

        if not form_action:
            return {
                "status": "error",
                "message": (
                    f"Could not find the roster upload form. "
                    f"Page: {members_resp.url}. "
                    f"Forms found: {all_form_actions}."
                ),
                "rows_submitted": 0,
                "timestamp": timestamp,
            }

        if form_action.startswith("/"):
            form_action = GG_BASE_URL + form_action

        # ── Step 4: Upload the CSV file ───────────────────────────────
        logger.info(
            "GG sync: uploading CSV (%d rows) to %s", len(rows), form_action
        )

        upload_data = _extract_all_hidden_fields(page_html)
        if csrf:
            upload_data["authenticity_token"] = csrf

        csv_bytes = csv_content.encode("utf-8")
        files = {
            file_input_name: ("handicaps.csv", csv_bytes, "text/csv"),
        }

        upload_resp = sess.post(
            form_action,
            data=upload_data,
            files=files,
            timeout=60,
            allow_redirects=True,
        )
        upload_resp.raise_for_status()

        logger.info(
            "GG sync: upload response URL: %s (status %d)",
            upload_resp.url, upload_resp.status_code,
        )
        page_html = upload_resp.text

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
