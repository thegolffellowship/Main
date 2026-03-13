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
    """Build a CSV string from export rows."""
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
            # Golf Genius shows dropdowns to pick which column is the unique ID
            # and which column is the Handicap Index.
            # Column headers in our CSV: "Email" (col 0), "Handicap Index" (col 1), "Player Name" (col 2)
            logger.info("GG sync: mapping columns")
            try:
                # Find all <select> elements on the page
                selects = page.locator("select").all()
                for sel in selects:
                    options = sel.locator("option").all()
                    option_texts = [o.inner_text().strip() for o in options]
                    logger.debug("Select options: %s", option_texts)

                    # Pick "Email" as the unique identifier
                    if any("email" in t.lower() for t in option_texts):
                        # Check if this is the "unique identifier" select
                        label_text = ""
                        try:
                            sel_id = sel.get_attribute("id") or ""
                            label = page.locator(f'label[for="{sel_id}"]')
                            label_text = label.inner_text().strip().lower() if label.count() else ""
                        except Exception:
                            pass
                        if "unique" in label_text or "identifier" in label_text or not label_text:
                            sel.select_option(label="Email")

                    # Pick "Handicap Index" column
                    if any("handicap" in t.lower() for t in option_texts):
                        sel.select_option(label="Handicap Index")

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
