"""Golf Genius handicap sync via Playwright browser automation.

Logs into golfgenius.com, navigates to the handicap spreadsheet upload page
for the specified league, uploads a CSV (Email, Handicap Index, Player Name),
maps columns, and clicks Import.

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
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GG_BASE_URL = "https://www.golfgenius.com"
GG_LOGIN_URL = f"{GG_BASE_URL}/users/sign_in"


def _build_csv(rows: list[dict]) -> str:
    """Build a CSV string from export rows.

    Column names are chosen to match Golf Genius's expected field labels
    so GG can auto-detect the mapping where possible.
      Email          — unique identifier GG matches against
      Handicap Index — the 18-hole index value (9-hole × 2)
      Player Name    — informational only, not used by GG import
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Email", "Handicap Index", "Player Name"])
    for row in rows:
        writer.writerow([row["email"], row["handicap_index"], row["player_name"]])
    return buf.getvalue()


def sync_handicaps_to_league(
    rows: list[dict],
    league_id: str,
    email: str,
    password: str,
    screenshot_dir: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Upload handicap indexes to a Golf Genius league via browser automation.

    Args:
        rows: list of {"email": ..., "handicap_index": ..., "player_name": ...}
        league_id: Golf Genius league ID (numbers only)
        email: Golf Genius account email
        password: Golf Genius account password
        screenshot_dir: if set, saves debug screenshots here

    Returns:
        {"status": "ok"|"error", "message": str, "rows_submitted": int,
         "timestamp": ISO str}
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return {
            "status": "error",
            "message": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            "rows_submitted": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }

    if dry_run:
        return {
            "status": "dry_run",
            "message": f"Dry run — would submit {len(rows)} player(s): "
                       + ", ".join(r["player_name"] for r in rows[:5])
                       + ("…" if len(rows) > 5 else ""),
            "rows_submitted": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }

    csv_content = _build_csv(rows)
    timestamp = datetime.utcnow().isoformat()

    # Write CSV to a temp file — Playwright needs a real path for file input
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(csv_content)
        tmp_path = tmp.name

    def _screenshot(page, name: str) -> None:
        if screenshot_dir:
            Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
            path = os.path.join(screenshot_dir, f"{name}_{int(time.time())}.png")
            try:
                page.screenshot(path=path)
                logger.info("Screenshot saved: %s", path)
            except Exception:
                pass

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()
            page.set_default_timeout(20_000)

            # ── Step 1: Login ────────────────────────────────────────────────
            logger.info("GG sync: navigating to login page")
            page.goto(GG_LOGIN_URL)
            page.wait_for_load_state("networkidle")
            _screenshot(page, "01_login")

            page.fill('input[name="user[email]"]', email)
            page.fill('input[name="user[password]"]', password)
            page.click('input[type="submit"], button[type="submit"]')

            # Wait until we're off the sign-in page
            try:
                page.wait_for_url(
                    lambda url: "sign_in" not in url and "sign_up" not in url,
                    timeout=15_000,
                )
            except PWTimeout:
                _screenshot(page, "02_login_fail")
                return {
                    "status": "error",
                    "message": "Login failed — check GOLF_GENIUS_EMAIL and GOLF_GENIUS_PASSWORD",
                    "rows_submitted": 0,
                    "timestamp": timestamp,
                }

            logger.info("GG sync: logged in, current URL: %s", page.url)
            _screenshot(page, "02_logged_in")

            # ── Step 2: Navigate to handicap update page ─────────────────────
            update_url = (
                f"{GG_BASE_URL}/leagues/{league_id}/golfers/update_hcps_from_spreadsheet"
            )
            logger.info("GG sync: navigating to %s", update_url)
            page.goto(update_url)
            page.wait_for_load_state("networkidle")
            _screenshot(page, "03_update_page")

            # Fallback: if we got redirected away, try navigating via menu
            if "update_hcps" not in page.url:
                logger.info("GG sync: direct URL failed, trying menu navigation")
                page.goto(f"{GG_BASE_URL}/leagues/{league_id}")
                page.wait_for_load_state("networkidle")

                # Try to find and click "Golfers" menu
                try:
                    page.click('text="Golfers"', timeout=5_000)
                    page.click('text="Update Handicaps from Spreadsheet"', timeout=5_000)
                    page.wait_for_load_state("networkidle")
                    _screenshot(page, "03b_via_menu")
                except PWTimeout:
                    _screenshot(page, "03_nav_fail")
                    return {
                        "status": "error",
                        "message": (
                            "Could not navigate to 'Update Handicaps from Spreadsheet' "
                            f"for league {league_id}. Check league ID and GG permissions."
                        ),
                        "rows_submitted": 0,
                        "timestamp": timestamp,
                    }

            # ── Step 3: Upload CSV file ──────────────────────────────────────
            logger.info("GG sync: uploading CSV (%d rows)", len(rows))
            try:
                file_input = page.locator('input[type="file"]').first
                file_input.set_input_files(tmp_path)
            except Exception as exc:
                _screenshot(page, "04_file_fail")
                return {
                    "status": "error",
                    "message": f"Could not find file upload input: {exc}",
                    "rows_submitted": 0,
                    "timestamp": timestamp,
                }

            # Click Upload button
            try:
                page.click('input[value="Upload"], button:has-text("Upload")', timeout=5_000)
            except PWTimeout:
                page.click('text="Upload"', timeout=5_000)

            page.wait_for_load_state("networkidle")
            _screenshot(page, "04_after_upload")

            # ── Step 4: Map columns ──────────────────────────────────────────
            # After upload, Golf Genius shows a mapping form with two dropdowns:
            #   - Unique identifier → select "Email"
            #   - Handicap Index    → select "Handicap Index"
            # Our CSV headers are "Email", "Handicap Index", "Player Name"
            # GG may auto-match on exact header names; we also set them explicitly.
            logger.info("GG sync: mapping columns")
            try:
                # GG typically renders the mapping form with labeled <select> elements.
                # Strategy: find each <select>, inspect its associated <label> text,
                # then choose the right CSV column from its options.
                selects = page.locator("select").all()
                logger.info("GG sync: found %d select elements for mapping", len(selects))

                for sel in selects:
                    # Get the label text for this select
                    sel_id = sel.get_attribute("id") or ""
                    sel_name = sel.get_attribute("name") or ""
                    label_text = ""
                    if sel_id:
                        lbl = page.locator(f'label[for="{sel_id}"]')
                        if lbl.count():
                            label_text = lbl.first.inner_text().strip().lower()
                    if not label_text:
                        label_text = (sel_name or "").lower()

                    logger.debug("GG sync: select id=%s name=%s label=%r", sel_id, sel_name, label_text)

                    # Get available options for this dropdown
                    option_values = [o.get_attribute("value") or "" for o in sel.locator("option").all()]
                    option_texts  = [o.inner_text().strip() for o in sel.locator("option").all()]
                    logger.debug("GG sync: options %s", option_texts)

                    def _pick(sel, choices: list[str]) -> bool:
                        """Try each choice in order; return True if one matched."""
                        for choice in choices:
                            for val, txt in zip(option_values, option_texts):
                                if choice.lower() in txt.lower() or choice.lower() in val.lower():
                                    try:
                                        sel.select_option(value=val)
                                        logger.info("GG sync: mapped select '%s' → '%s'", label_text, txt)
                                        return True
                                    except Exception:
                                        pass
                        return False

                    # Map the unique-identifier dropdown to Email
                    if any(kw in label_text for kw in ("unique", "identifier", "match", "player id")):
                        _pick(sel, ["Email", "email"])

                    # Map the handicap-index dropdown to our "Handicap Index" column
                    elif any(kw in label_text for kw in ("handicap", "index", "hcp")):
                        _pick(sel, ["Handicap Index", "handicap index", "index"])

                    # Fallback: if a select has "Email" as an option but no clear label,
                    # assume it's the unique-ID field
                    elif any("email" in t.lower() for t in option_texts):
                        _pick(sel, ["Email", "email"])

                    # Fallback: if a select has "Handicap Index" as an option
                    elif any("handicap" in t.lower() for t in option_texts):
                        _pick(sel, ["Handicap Index", "handicap index", "index"])

            except Exception as exc:
                logger.warning("GG sync: column mapping issue: %s", exc)
                _screenshot(page, "05_map_fail")

            _screenshot(page, "05_mapped")

            # ── Step 5: Click Import Handicaps ───────────────────────────────
            logger.info("GG sync: clicking Import Handicaps")
            try:
                page.click(
                    'input[value="Import Handicaps"], button:has-text("Import Handicaps")',
                    timeout=10_000,
                )
            except PWTimeout:
                try:
                    page.click('text="Import Handicaps"', timeout=5_000)
                except PWTimeout:
                    _screenshot(page, "06_import_btn_fail")
                    return {
                        "status": "error",
                        "message": "Could not find 'Import Handicaps' button — column mapping may need manual adjustment",
                        "rows_submitted": 0,
                        "timestamp": timestamp,
                    }

            page.wait_for_load_state("networkidle")
            _screenshot(page, "06_after_import")

            # ── Step 6: Read result message ──────────────────────────────────
            result_text = ""
            for selector in [".flash", ".alert", ".notice", "#flash", '[class*="flash"]', '[class*="notice"]']:
                try:
                    el = page.locator(selector).first
                    if el.is_visible(timeout=3_000):
                        result_text = el.inner_text().strip()
                        break
                except Exception:
                    continue

            if not result_text:
                result_text = f"Import submitted for {len(rows)} players"

            logger.info("GG sync: result — %s", result_text)
            browser.close()

            return {
                "status": "ok",
                "message": result_text,
                "rows_submitted": len(rows),
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
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


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
