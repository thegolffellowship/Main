"""Golf Genius handicap sync via HTTP requests.

Logs into golfgenius.com, navigates to the handicap spreadsheet upload page
for the specified league, uploads a CSV (Email, Handicap Index, Player Name),
maps columns, and submits the import.

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


def sync_handicaps_to_league(
    rows: list[dict],
    league_id: str,
    email: str,
    password: str,
    screenshot_dir: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Upload handicap indexes to a Golf Genius league via HTTP requests.

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
        # ── Step 1: Get login page and CSRF token ─────────────────────
        logger.info("GG sync: fetching login page")
        login_page = sess.get(GG_LOGIN_URL, timeout=30)
        login_page.raise_for_status()

        csrf = _extract_csrf_token(login_page.text)
        if not csrf:
            return {
                "status": "error",
                "message": "Could not find CSRF token on Golf Genius login page",
                "rows_submitted": 0,
                "timestamp": timestamp,
            }

        # ── Step 2: Submit login form ─────────────────────────────────
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

        # Check if login succeeded — if we're back on sign_in, it failed
        if "sign_in" in login_resp.url:
            # Check for error message in response
            error_match = re.search(
                r'class="[^"]*(?:alert|error|flash)[^"]*"[^>]*>([^<]+)', login_resp.text
            )
            error_msg = error_match.group(1).strip() if error_match else "Invalid email or password"
            return {
                "status": "error",
                "message": f"Login failed: {error_msg}",
                "rows_submitted": 0,
                "timestamp": timestamp,
            }

        logger.info("GG sync: logged in, redirected to %s", login_resp.url)

        # ── Step 3: Navigate to handicap upload page ──────────────────
        upload_url = (
            f"{GG_BASE_URL}/leagues/{league_id}/golfers/update_hcps_from_spreadsheet"
        )
        logger.info("GG sync: navigating to %s", upload_url)
        upload_page = sess.get(upload_url, timeout=30)

        if upload_page.status_code == 404:
            return {
                "status": "error",
                "message": f"Handicap upload page not found for league {league_id}. "
                           "Check the league ID.",
                "rows_submitted": 0,
                "timestamp": timestamp,
            }
        upload_page.raise_for_status()

        if "update_hcps" not in upload_page.url:
            return {
                "status": "error",
                "message": (
                    f"Redirected away from handicap upload page to {upload_page.url}. "
                    f"Check league ID ({league_id}) and GG account permissions."
                ),
                "rows_submitted": 0,
                "timestamp": timestamp,
            }

        # Extract CSRF token from upload page
        csrf = _extract_csrf_token(upload_page.text)

        # ── Step 4: Find the form action and upload CSV ───────────────
        # The form action is typically the same URL or a related endpoint
        # Look for the form action on the page
        form_match = re.search(
            r'<form[^>]*action="([^"]*)"[^>]*enctype="multipart/form-data"',
            upload_page.text,
        )
        if not form_match:
            # Try without enctype
            form_match = re.search(
                r'<form[^>]*action="([^"]*update_hcps[^"]*)"', upload_page.text
            )

        form_action = form_match.group(1) if form_match else upload_url
        if form_action.startswith("/"):
            form_action = GG_BASE_URL + form_action

        logger.info("GG sync: uploading CSV (%d rows) to %s", len(rows), form_action)

        # Build multipart form data
        upload_data = {}
        if csrf:
            upload_data["authenticity_token"] = csrf

        # Check for any hidden fields in the form
        hidden_fields = re.findall(
            r'<input\s+type="hidden"\s+name="([^"]+)"\s+value="([^"]*)"',
            upload_page.text,
        )
        for name, value in hidden_fields:
            upload_data[name] = value

        csv_bytes = csv_content.encode("utf-8")
        files = {
            "file": ("handicaps.csv", csv_bytes, "text/csv"),
        }

        # Also try common GG file field names
        file_input_match = re.search(
            r'<input[^>]*type="file"[^>]*name="([^"]+)"', upload_page.text
        )
        if file_input_match:
            file_field_name = file_input_match.group(1)
            if file_field_name != "file":
                files = {file_field_name: ("handicaps.csv", csv_bytes, "text/csv")}

        upload_resp = sess.post(
            form_action,
            data=upload_data,
            files=files,
            timeout=60,
            allow_redirects=True,
        )
        upload_resp.raise_for_status()

        logger.info("GG sync: upload response URL: %s (status %d)",
                     upload_resp.url, upload_resp.status_code)

        # ── Step 5: Handle column mapping page ────────────────────────
        # After upload, GG may show a column mapping page with dropdowns.
        # We need to detect if we're on the mapping page and submit it.
        page_html = upload_resp.text

        # Check if the response contains column mapping selects
        has_mapping = bool(re.search(r'<select[^>]*>', page_html))
        mapping_form_match = re.search(
            r'<form[^>]*action="([^"]*)"[^>]*>', page_html
        )

        if has_mapping and mapping_form_match:
            logger.info("GG sync: column mapping page detected, submitting mapping")
            mapping_action = mapping_form_match.group(1)
            if mapping_action.startswith("/"):
                mapping_action = GG_BASE_URL + mapping_action

            # Get the new CSRF token
            new_csrf = _extract_csrf_token(page_html)

            # Parse select elements and their options to build form data
            mapping_data = {}
            if new_csrf:
                mapping_data["authenticity_token"] = new_csrf

            # Extract hidden fields
            hidden_fields = re.findall(
                r'<input\s+type="hidden"\s+name="([^"]+)"\s+value="([^"]*)"',
                page_html,
            )
            for name, value in hidden_fields:
                mapping_data[name] = value

            # Parse select elements
            selects = re.findall(
                r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>',
                page_html,
                re.DOTALL,
            )

            for sel_name, sel_body in selects:
                # Find the label/context for this select
                # Look backwards in the HTML for a label
                sel_pos = page_html.find(f'name="{sel_name}"')
                context_chunk = page_html[max(0, sel_pos - 500):sel_pos].lower()

                # Parse options
                options = re.findall(
                    r'<option\s+value="([^"]*)"[^>]*>([^<]*)</option>',
                    sel_body,
                )

                # Determine what this select should be mapped to
                option_dict = {text.strip().lower(): val for val, text in options}
                option_texts = [text.strip().lower() for _, text in options]

                if any(kw in context_chunk for kw in ("unique", "identifier", "match", "player id")):
                    # Map to Email
                    for label in ("email", "e-mail"):
                        if label in option_dict:
                            mapping_data[sel_name] = option_dict[label]
                            logger.info("GG sync: mapped '%s' → Email", sel_name)
                            break
                elif any(kw in context_chunk for kw in ("handicap", "index", "hcp")):
                    # Map to Handicap Index
                    for label in ("handicap index", "handicap_index", "index"):
                        if label in option_dict:
                            mapping_data[sel_name] = option_dict[label]
                            logger.info("GG sync: mapped '%s' → Handicap Index", sel_name)
                            break
                elif any("email" in t for t in option_texts):
                    # Fallback: if has Email option, assume it's the identifier select
                    for label in ("email", "e-mail"):
                        if label in option_dict:
                            mapping_data[sel_name] = option_dict[label]
                            break
                elif any("handicap" in t for t in option_texts):
                    # Fallback: if has Handicap option, assume it's the HCP select
                    for label in ("handicap index", "handicap_index", "index"):
                        if label in option_dict:
                            mapping_data[sel_name] = option_dict[label]
                            break

            # Look for submit button value
            submit_match = re.search(
                r'<input[^>]*type="submit"[^>]*value="([^"]*[Ii]mport[^"]*)"[^>]*name="([^"]*)"',
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
            logger.info("GG sync: mapping submitted, response URL: %s", mapping_resp.url)

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
            result_text = f"Import submitted for {len(rows)} players"

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
