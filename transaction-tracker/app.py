"""
Transaction Email Tracker — Flask application.

Automatically checks your email inbox for transaction/receipt emails,
parses purchase data with AI (Claude), and displays it in a web dashboard.
Includes a webhook connector for external integrations and a daily email report.
"""

import os
import re
import json
import secrets
import logging
import threading
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, render_template, request, send_file, session
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from email_parser.database import (
    init_db,
    get_all_items,
    get_item,
    get_known_email_uids,
    get_item_stats,
    get_audit_report,
    get_data_snapshot,
    save_items,
    update_item,
    delete_item,
    delete_manual_player,
    credit_item,
    transfer_item,
    reverse_credit,
    create_event,
    seed_events,
    add_player_to_event,
    upgrade_rsvp_to_paid,
    autofix_side_games,
    autofix_all,
    normalize_tee_choices,
    sync_events_from_items,
    get_all_events,
    update_event,
    delete_event,
    merge_events,
    get_orphaned_items,
    resolve_orphaned_items,
    get_all_event_aliases,
    get_known_rsvp_uids,
    save_rsvps,
    get_rsvps_for_event,
    get_all_rsvps,
    get_rsvp_stats,
    rematch_rsvps,
    manual_match_rsvp,
    unmatch_rsvp,
    get_rsvp_overrides,
    set_rsvp_override,
    merge_customers,
)
from email_parser.fetcher import fetch_transaction_emails, send_mail_graph
from email_parser.parser import parse_email, parse_emails
from email_parser.report import send_daily_report
from email_parser.rsvp_parser import fetch_rsvp_emails, parse_rsvp_emails

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

# ---------------------------------------------------------------------------
# Email check job (with background tracking)
# ---------------------------------------------------------------------------
_inbox_check_lock = threading.Lock()
_inbox_check_status = {
    "running": False,
    "error": None,
    "emails_fetched": 0,
    "emails_parsed": 0,
    "items_saved": 0,
    "message": None,
}


def check_inbox():
    """Fetch new transaction emails, parse them with AI, and save to DB."""
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    address = os.getenv("EMAIL_ADDRESS")

    if not all([tenant_id, client_id, client_secret, address]):
        logger.warning("Azure AD / email credentials not configured — skipping inbox check")
        _inbox_check_status["message"] = "Azure AD / email credentials not configured"
        return

    logger.info("Checking inbox for %s ...", address)
    emails = fetch_transaction_emails(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        email_address=address,
        since_date=datetime.now() - timedelta(days=90),
    )

    _inbox_check_status["emails_fetched"] = len(emails)

    if not emails:
        logger.info("No new transaction emails found")
        _inbox_check_status["message"] = "No transaction emails matched filters in the last 90 days"
        return

    # Skip emails already parsed — avoids burning AI credits on duplicates
    known_uids = get_known_email_uids()
    new_emails = [e for e in emails if e.get("uid") not in known_uids]
    logger.info(
        "Fetched %d transaction emails, %d already parsed, %d new to process",
        len(emails), len(emails) - len(new_emails), len(new_emails),
    )

    if not new_emails:
        _inbox_check_status["message"] = f"All {len(emails)} emails already parsed — nothing new"
        return

    # Parse and save one email at a time so items appear on the dashboard
    # incrementally instead of waiting for the entire batch to finish.
    import anthropic as _anthropic

    _inbox_check_status["emails_fetched"] = len(new_emails)
    total_saved = 0
    total_parsed = 0
    for i, email_data in enumerate(new_emails, 1):
        try:
            rows = parse_email(email_data)
            total_parsed += 1
            _inbox_check_status["emails_parsed"] = total_parsed
            if rows:
                count = save_items(rows)
                total_saved += count
                _inbox_check_status["items_saved"] = total_saved
                logger.info("Email %d/%d: saved %d items", i, len(new_emails), count)
            else:
                logger.info("Email %d/%d: no items extracted", i, len(new_emails))
        except (_anthropic.BadRequestError, _anthropic.AuthenticationError) as e:
            logger.error(
                "Stopping at email %d/%d — Anthropic API fatal error: %s",
                i, len(new_emails), e.message,
            )
            raise
        except Exception:
            logger.exception("Failed to parse email %d/%d uid=%s", i, len(new_emails), email_data.get("uid"))

    # Auto-sync: create event entries for any new event-like items
    if total_saved > 0:
        try:
            sync_result = sync_events_from_items()
            if sync_result.get("inserted"):
                logger.info("Auto-synced %d new events from incoming transactions", sync_result["inserted"])
        except Exception:
            logger.exception("Auto-sync events failed (non-fatal)")

    _inbox_check_status["message"] = f"Done — saved {total_saved} items from {len(new_emails)} new emails ({len(emails)} total scanned)"
    logger.info("Done — saved %d total new items from %d new emails", total_saved, len(new_emails))


def check_rsvp_inbox():
    """Fetch new RSVP emails from Golf Genius, parse them, and save to DB."""
    rsvp_address = os.getenv("RSVP_EMAIL_ADDRESS")
    if not rsvp_address:
        logger.info("RSVP_EMAIL_ADDRESS not configured — skipping RSVP check")
        return

    logger.info("Checking RSVP inbox for %s ...", rsvp_address)
    try:
        emails = fetch_rsvp_emails(
            since_date=datetime.now() - timedelta(days=90),
        )
    except Exception as e:
        logger.exception("Failed to fetch RSVP emails: %s", e)
        return

    if not emails:
        logger.info("No RSVP emails found")
        return

    # Skip already-processed
    known_uids = get_known_rsvp_uids()
    new_emails = [e for e in emails if e.get("uid") not in known_uids]
    logger.info(
        "RSVP: fetched %d emails, %d already processed, %d new",
        len(emails), len(emails) - len(new_emails), len(new_emails),
    )

    if not new_emails:
        return

    parsed = parse_rsvp_emails(new_emails)
    if parsed:
        saved = save_rsvps(parsed)
        logger.info("RSVP: saved %d new RSVPs from %d emails", saved, len(new_emails))

    # Also re-run matching for any previously unmatched RSVPs
    rematch_rsvps()


def _check_inbox_background():
    """Wrapper that runs check_inbox in a background thread with status tracking."""
    _inbox_check_status["emails_fetched"] = 0
    _inbox_check_status["emails_parsed"] = 0
    _inbox_check_status["items_saved"] = 0
    _inbox_check_status["message"] = None
    try:
        check_inbox()
        _inbox_check_status["error"] = None
    except Exception as e:
        logger.exception("Background inbox check failed")
        _inbox_check_status["error"] = str(e)
    finally:
        _inbox_check_status["running"] = False


# ---------------------------------------------------------------------------
# Connector API-key auth helper
# ---------------------------------------------------------------------------
def require_connector_key(f):
    """Decorator that validates the X-API-Key header against CONNECTOR_API_KEY."""
    @wraps(f)
    def decorated(*args, **kwargs):
        expected = os.getenv("CONNECTOR_API_KEY")
        if not expected:
            return jsonify({"error": "CONNECTOR_API_KEY not configured on server."}), 500
        provided = request.headers.get("X-API-Key", "")
        if not secrets.compare_digest(provided, expected):
            return jsonify({"error": "Invalid or missing API key."}), 401
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Role-based access helpers
# ---------------------------------------------------------------------------
def require_role(role):
    """Decorator that checks the session for a minimum role level."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_role = session.get("role")
            if not user_role:
                return jsonify({"error": "Not authenticated. Please log in."}), 401
            if role == "admin" and user_role != "admin":
                return jsonify({"error": "Admin access required."}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
scheduler = BackgroundScheduler(daemon=True)


def start_scheduler():
    interval = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))
    scheduler.add_job(
        check_inbox,
        "interval",
        minutes=interval,
        id="inbox_check",
        replace_existing=True,
    )

    # RSVP inbox check — same interval as transaction inbox
    if os.getenv("RSVP_EMAIL_ADDRESS"):
        scheduler.add_job(
            check_rsvp_inbox,
            "interval",
            minutes=interval,
            id="rsvp_inbox_check",
            replace_existing=True,
        )
        logger.info("RSVP scheduler: checking %s every %d minutes",
                     os.getenv("RSVP_EMAIL_ADDRESS"), interval)

    # Daily report — runs at the configured hour (default 7:00 AM)
    report_hour = int(os.getenv("DAILY_REPORT_HOUR", "7"))
    if os.getenv("DAILY_REPORT_TO"):
        scheduler.add_job(
            send_daily_report,
            "cron",
            hour=report_hour,
            minute=0,
            id="daily_report",
            replace_existing=True,
        )
        logger.info("Daily report scheduled for %02d:00 → %s", report_hour, os.getenv("DAILY_REPORT_TO"))

    scheduler.start()
    logger.info("Scheduler started — checking inbox every %d minutes", interval)


# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------
@app.route("/api/items")
def api_items():
    """Return all item rows as JSON."""
    items = get_all_items()
    return jsonify(items)


@app.route("/api/stats")
def api_stats():
    """Return summary statistics."""
    stats = get_item_stats()
    return jsonify(stats)


@app.route("/api/audit")
def api_audit():
    """Data-quality report: field fill-rates, missing-data flags, value distributions."""
    report = get_audit_report()
    return jsonify(report)


@app.route("/api/data-snapshot")
def api_data_snapshot():
    """Quick snapshot of recent items + stats for inspection."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify(get_data_snapshot(limit=limit))


@app.route("/api/items/<int:item_id>", methods=["PATCH"])
def api_update_item(item_id):
    """Update specific fields on an item row (for inline editing)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400
    updated = update_item(item_id, data)
    if updated:
        return jsonify({"status": "ok"})
    return jsonify({"error": "not found or no valid fields"}), 404


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
@require_role("admin")
def api_delete_item(item_id):
    """Delete an item row by ID. Admin only."""
    deleted = delete_item(item_id)
    if deleted:
        return jsonify({"status": "ok"})
    return jsonify({"error": "not found"}), 404


@app.route("/api/events/delete-manual-player/<int:item_id>", methods=["DELETE"])
def api_delete_manual_player(item_id):
    """Delete a manually added player. Only works for manual entries."""
    if delete_manual_player(item_id):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Not found or not a manually added player."}), 400


@app.route("/api/check-now", methods=["POST"])
def api_check_now():
    """Manually trigger an inbox check (runs in background to avoid timeout)."""
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    address = os.getenv("EMAIL_ADDRESS")
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not all([tenant_id, client_id, client_secret, address]):
        return jsonify({"error": "Azure AD credentials not configured. Create a .env file from .env.example."}), 400

    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured. Add it to your .env file."}), 400

    with _inbox_check_lock:
        if _inbox_check_status["running"]:
            return jsonify({"status": "already_running"})
        _inbox_check_status["running"] = True
        _inbox_check_status["error"] = None

    thread = threading.Thread(target=_check_inbox_background, daemon=True)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/check-status")
def api_check_status():
    """Poll this endpoint to check if the background inbox check is done."""
    running = _inbox_check_status["running"]
    error = _inbox_check_status["error"]

    progress = {
        "emails_fetched": _inbox_check_status["emails_fetched"],
        "emails_parsed": _inbox_check_status["emails_parsed"],
        "items_saved": _inbox_check_status["items_saved"],
    }

    if running:
        return jsonify({"status": "running", "progress": progress})

    if error:
        return jsonify({"status": "error", "error": error, "progress": progress})

    stats = get_item_stats()
    return jsonify({
        "status": "done",
        "stats": stats,
        "progress": progress,
        "message": _inbox_check_status.get("message"),
    })


@app.route("/admin/backup")
@require_role("admin")
def admin_backup():
    """Stream the SQLite database file as a download. Admin-only."""
    from email_parser.database import DB_PATH
    import shutil
    db_path = str(DB_PATH)
    if not os.path.isfile(db_path):
        return jsonify({"error": "Database file not found"}), 404
    # Copy to a temp file to avoid streaming a locked WAL-mode DB
    backup_path = db_path + ".backup"
    shutil.copy2(db_path, backup_path)
    # Also checkpoint WAL into the backup
    try:
        import sqlite3
        conn = sqlite3.connect(backup_path)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception:
        pass
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        backup_path,
        mimetype="application/x-sqlite3",
        as_attachment=True,
        download_name=f"tgf_transactions_{timestamp}.db",
    )


@app.route("/api/health")
def api_health():
    """Diagnostic endpoint for Railway troubleshooting."""
    from email_parser.database import DB_PATH
    db_path = str(DB_PATH)
    db_exists = os.path.isfile(db_path)
    db_dir_exists = os.path.isdir(os.path.dirname(db_path))
    try:
        from email_parser.database import get_connection
        conn = get_connection()
        row = conn.execute("SELECT COUNT(*) as cnt FROM items").fetchone()
        item_count = row["cnt"]
        conn.close()
        db_readable = True
    except Exception as e:
        item_count = 0
        db_readable = False
    env_keys = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
                "EMAIL_ADDRESS", "ANTHROPIC_API_KEY", "DATABASE_PATH",
                "SECRET_KEY", "ADMIN_PIN", "MANAGER_PIN", "RSVP_EMAIL_ADDRESS"]
    env_status = {k: ("set" if os.getenv(k) else "missing") for k in env_keys}
    return jsonify({
        "status": "ok" if db_readable else "error",
        "database_path": db_path,
        "database_exists": db_exists,
        "database_dir_exists": db_dir_exists,
        "database_readable": db_readable,
        "item_count": item_count,
        "env_vars": env_status,
    })


@app.route("/api/config-status")
def api_config_status():
    """Check whether email, AI, and connector credentials are configured."""
    email_ok = all([
        os.getenv("AZURE_TENANT_ID"),
        os.getenv("AZURE_CLIENT_ID"),
        os.getenv("AZURE_CLIENT_SECRET"),
        os.getenv("EMAIL_ADDRESS"),
    ])
    ai_ok = bool(os.getenv("ANTHROPIC_API_KEY"))
    connector_ok = bool(os.getenv("CONNECTOR_API_KEY"))
    report_ok = bool(os.getenv("DAILY_REPORT_TO"))
    rsvp_ok = bool(os.getenv("RSVP_EMAIL_ADDRESS"))
    return jsonify({
        "configured": email_ok and ai_ok,
        "email": email_ok,
        "ai": ai_ok,
        "connector": connector_ok,
        "daily_report": report_ok,
        "rsvp": rsvp_ok,
    })


# ---------------------------------------------------------------------------
# Routes — Connector / Webhook
# ---------------------------------------------------------------------------
@app.route("/api/connector/ingest", methods=["POST"])
@require_connector_key
def api_connector_ingest():
    """
    Webhook endpoint for external systems to push order data.

    Accepts JSON with one of two formats:

    1. Pre-structured items (direct insert):
       {
         "items": [
           { "email_uid": "ext-123", "item_index": 0, "merchant": "...",
             "customer": "...", "item_name": "...", ... }
         ]
       }

    2. Raw email text (parsed by AI):
       {
         "raw_email": {
           "uid": "ext-123",
           "subject": "New Order #...",
           "from": "noreply@store.com",
           "text": "... full email body ..."
         }
       }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    # Format 1: pre-structured items
    if "items" in data:
        items = data["items"]
        if not isinstance(items, list) or not items:
            return jsonify({"error": "'items' must be a non-empty array."}), 400
        count = save_items(items)
        return jsonify({"status": "ok", "inserted": count, "received": len(items)})

    # Format 2: raw email for AI parsing
    if "raw_email" in data:
        raw = data["raw_email"]
        if not isinstance(raw, dict) or not raw.get("text"):
            return jsonify({"error": "'raw_email' must have at least a 'text' field."}), 400

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return jsonify({"error": "ANTHROPIC_API_KEY not configured — cannot parse raw email."}), 500

        rows = parse_emails([raw])
        if rows:
            count = save_items(rows)
            return jsonify({"status": "ok", "inserted": count, "parsed_items": len(rows)})
        return jsonify({"status": "ok", "inserted": 0, "message": "No items could be parsed from the email."}), 200

    return jsonify({"error": "Request must contain 'items' or 'raw_email'."}), 400


@app.route("/api/connector/info")
def api_connector_info():
    """Return connector configuration (whether key is set, not the key itself)."""
    key_set = bool(os.getenv("CONNECTOR_API_KEY"))
    return jsonify({
        "enabled": key_set,
        "endpoint": "/api/connector/ingest",
        "methods": ["POST"],
        "auth": "X-API-Key header",
        "formats": ["pre-structured items", "raw email for AI parsing"],
    })


@app.route("/api/audit/emails")
@require_role("admin")
def api_audit_emails():
    """
    Fetch raw emails from inbox AND the corresponding parsed DB records,
    returning them side-by-side so the user can verify extraction accuracy.

    Query params:
        limit  — max emails to return (default 50)
        days   — how far back to look (default 90)
    """
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    address = os.getenv("EMAIL_ADDRESS")

    if not all([tenant_id, client_id, client_secret, address]):
        return jsonify({"error": "Azure AD / email credentials not configured."}), 400

    limit = request.args.get("limit", 50, type=int)
    days = request.args.get("days", 90, type=int)

    from email_parser.parser import _strip_html

    try:
        emails = fetch_transaction_emails(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            email_address=address,
            since_date=datetime.now() - timedelta(days=days),
        )
    except Exception as e:
        logger.exception("Audit: failed to fetch emails")
        return jsonify({"error": f"Failed to fetch emails: {e}"}), 500

    # Build a lookup of DB items keyed by email_uid
    all_items = get_all_items()
    db_by_uid: dict[str, list[dict]] = {}
    for item in all_items:
        uid = item.get("email_uid", "")
        if uid:
            db_by_uid.setdefault(uid, []).append(item)

    comparisons = []
    for email in emails[:limit]:
        uid = email.get("uid", "")
        body_text = email.get("text", "")
        if not body_text and email.get("html"):
            body_text = _strip_html(email["html"])

        # Truncate body for transport (keep first 2000 chars for review)
        body_preview = body_text[:2000] if body_text else "(empty)"

        db_rows = db_by_uid.get(uid, [])

        # Determine audit status
        if not db_rows:
            status = "missing"
            status_detail = "Email was fetched but no items were parsed/saved"
        else:
            # Check for missing critical fields
            issues = []
            for row in db_rows:
                missing = []
                for f in ["customer", "order_id", "item_name", "item_price", "event_date", "city"]:
                    if not row.get(f):
                        missing.append(f)
                if missing:
                    issues.append({"item_index": row.get("item_index", 0), "missing": missing})
            if issues:
                status = "incomplete"
                status_detail = f"{len(issues)} item(s) have missing fields"
            else:
                status = "ok"
                status_detail = f"{len(db_rows)} item(s) parsed successfully"

        comparisons.append({
            "email_uid": uid,
            "subject": email.get("subject", ""),
            "from": email.get("from", ""),
            "date": email.get("date", ""),
            "body_preview": body_preview,
            "status": status,
            "status_detail": status_detail,
            "parsed_items": db_rows,
        })

    # Summary counts
    total = len(comparisons)
    ok_count = sum(1 for c in comparisons if c["status"] == "ok")
    incomplete_count = sum(1 for c in comparisons if c["status"] == "incomplete")
    missing_count = sum(1 for c in comparisons if c["status"] == "missing")

    return jsonify({
        "total_emails": total,
        "ok": ok_count,
        "incomplete": incomplete_count,
        "missing": missing_count,
        "comparisons": comparisons,
    })


@app.route("/matrix")
def matrix_page():
    # Admin-only page
    if session.get("role") != "admin":
        return render_template("index.html")
    return render_template("matrix.html")


@app.route("/changelog")
def changelog_page():
    # Admin-only page — managers are redirected to home
    if session.get("role") != "admin":
        return render_template("index.html")
    return render_template("changelog.html")


@app.route("/audit")
def audit_page():
    # Admin-only page — managers are redirected to home
    if session.get("role") != "admin":
        return render_template("index.html")
    return render_template("audit.html")


@app.route("/api/matrix", methods=["PUT"])
@require_role("admin")
def api_matrix_save():
    """Save edits to the side-games matrix JS file."""
    try:
        data = request.get_json(force=True)
        changes = data.get("changes", {})
        if not changes:
            return jsonify({"error": "No changes provided"}), 400

        matrix_path = os.path.join(
            os.path.dirname(__file__), "static", "js", "games-matrix.js"
        )
        with open(matrix_path, "r") as f:
            content = f.read()

        # Parse existing matrices
        m9 = re.search(r"window\.GAMES_MATRIX_9\s*=\s*(\{.*?\});", content, re.DOTALL)
        m18 = re.search(r"window\.GAMES_MATRIX_18\s*=\s*(\{.*?\});", content, re.DOTALL)
        matrix9 = json.loads(m9.group(1))
        matrix18 = json.loads(m18.group(1))

        for change_key, new_val in changes.items():
            parts = change_key.split(":", 2)
            if len(parts) != 3:
                continue
            holes, pc, field_key = parts
            matrix = matrix9 if holes == "9" else matrix18
            if pc not in matrix:
                continue
            entry = matrix[pc]

            if field_key.startswith("skins."):
                idx = int(field_key.split(".")[1])
                if "skins" not in entry:
                    entry["skins"] = []
                while len(entry["skins"]) <= idx:
                    entry["skins"].append(None)
                entry["skins"][idx] = new_val
            else:
                entry[field_key] = new_val

        # Write back
        new_content = "// Auto-generated from 25-SideGame-PrizeMatrix.xlsx\n"
        new_content += "// Last edited via Matrix UI\n\n"
        new_content += "window.GAMES_MATRIX_9 = "
        new_content += json.dumps(matrix9, indent=2)
        new_content += ";\n\n"
        new_content += "window.GAMES_MATRIX_18 = "
        new_content += json.dumps(matrix18, indent=2)
        new_content += ";\n"

        with open(matrix_path, "w") as f:
            f.write(new_content)

        return jsonify({"status": "ok", "matrix9": matrix9, "matrix18": matrix18})
    except Exception as e:
        logger.exception("Matrix save failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit/autofix-side-games", methods=["POST"])
@require_role("admin")
def api_autofix_side_games():
    """Fix side_games misplacement in existing DB rows."""
    try:
        result = autofix_side_games()
        return jsonify({"status": "ok", **result})
    except Exception as e:
        logger.exception("Autofix failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit/autofix-all", methods=["POST"])
@require_role("admin")
def api_autofix_all():
    """Run all autofixes: side_games, customer names, course names, tee choices."""
    try:
        result = autofix_all()
        tee_fixed = normalize_tee_choices()
        result["tee_choices_fixed"] = tee_fixed
        return jsonify({"status": "ok", **result})
    except Exception as e:
        logger.exception("Autofix-all failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit/autofix-tee-choices", methods=["POST"])
@require_role("admin")
def api_autofix_tee_choices():
    """Normalize all tee_choice values to standard: <50, 50-64, 65+, Forward."""
    try:
        updated = normalize_tee_choices()
        return jsonify({"status": "ok", "tee_choices_fixed": updated})
    except Exception as e:
        logger.exception("Autofix tee choices failed")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Routes — Events
# ---------------------------------------------------------------------------
@app.route("/events")
def events_page():
    return render_template("events.html")


@app.route("/customers")
def customers_page():
    return render_template("customers.html")


@app.route("/api/customers/merge", methods=["POST"])
@require_role("admin")
def api_merge_customers():
    """Merge one customer into another."""
    data = request.get_json(force=True)
    source = (data.get("source") or "").strip()
    target = (data.get("target") or "").strip()
    if not source or not target:
        return jsonify({"error": "source and target customer names required"}), 400
    if source == target:
        return jsonify({"error": "source and target cannot be the same"}), 400
    result = merge_customers(source, target)
    return jsonify(result)


@app.route("/api/events")
def api_events():
    """Return all events with registration counts and aliases."""
    return jsonify(get_all_events())


@app.route("/api/events/aliases")
def api_event_aliases():
    """Return alias_name → canonical_event_name map."""
    return jsonify(get_all_event_aliases())


@app.route("/api/events/sync", methods=["POST"])
def api_sync_events():
    """Scan items and auto-create event entries for event-type items."""
    try:
        result = sync_events_from_items()
        return jsonify({"status": "ok", **result})
    except Exception as e:
        logger.exception("Event sync failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/events/<int:event_id>", methods=["PATCH"])
def api_update_event(event_id):
    """Update fields on an event."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400
    if update_event(event_id, data):
        return jsonify({"status": "ok"})
    return jsonify({"error": "not found or no valid fields"}), 404


@app.route("/api/events/<int:event_id>", methods=["DELETE"])
@require_role("admin")
def api_delete_event(event_id):
    """Delete an event. Admin only."""
    if delete_event(event_id):
        return jsonify({"status": "ok"})
    return jsonify({"error": "not found"}), 404


@app.route("/api/events", methods=["POST"])
def api_create_event():
    """Manually create a new event."""
    data = request.get_json(silent=True)
    if not data or not data.get("item_name"):
        return jsonify({"error": "item_name is required."}), 400
    event = create_event(
        item_name=data["item_name"],
        event_date=data.get("event_date"),
        course=data.get("course"),
        city=data.get("city"),
    )
    if event:
        return jsonify({"status": "ok", "event": event}), 201
    return jsonify({"error": "Event already exists with that name."}), 409


@app.route("/api/events/merge", methods=["POST"])
@require_role("admin")
def api_merge_events():
    """Merge source event into target event. Admin only.

    All items, RSVPs, and overrides from the source event are reassigned
    to the target event, then the source event is deleted.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required."}), 400
    source_id = data.get("source_id")
    target_id = data.get("target_id")
    if not source_id or not target_id:
        return jsonify({"error": "source_id and target_id are required."}), 400
    if source_id == target_id:
        return jsonify({"error": "Cannot merge an event into itself."}), 400
    result = merge_events(source_id, target_id)
    if result:
        return jsonify({"status": "ok", **result})
    return jsonify({"error": "Source or target event not found."}), 404


@app.route("/api/events/orphaned-items")
def api_orphaned_items():
    """Return items whose item_name doesn't match any event."""
    return jsonify(get_orphaned_items())


@app.route("/api/events/resolve-orphan", methods=["POST"])
@require_role("admin")
def api_resolve_orphan():
    """Reassign orphaned items to an existing event. Admin only."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required."}), 400
    old_name = data.get("old_item_name")
    target = data.get("target_event")
    if not old_name or not target:
        return jsonify({"error": "old_item_name and target_event are required."}), 400
    result = resolve_orphaned_items(old_name, target)
    return jsonify({"status": "ok", **result})


# ---------------------------------------------------------------------------
# Routes — Credit / Transfer
# ---------------------------------------------------------------------------
@app.route("/api/items/<int:item_id>/credit", methods=["POST"])
def api_credit_item(item_id):
    """Mark an item as credited (money held for future event)."""
    data = request.get_json(silent=True) or {}
    if credit_item(item_id, note=data.get("note", "")):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Item not found or already credited/transferred."}), 400


@app.route("/api/items/<int:item_id>/transfer", methods=["POST"])
def api_transfer_item(item_id):
    """Transfer an item to a different event."""
    data = request.get_json(silent=True)
    if not data or not data.get("target_event"):
        return jsonify({"error": "target_event is required."}), 400
    new_item = transfer_item(item_id, data["target_event"], note=data.get("note", ""))
    if new_item:
        return jsonify({"status": "ok", "new_item": new_item})
    return jsonify({"error": "Item not found or already credited/transferred."}), 400


@app.route("/api/items/<int:item_id>/reverse-credit", methods=["POST"])
def api_reverse_credit(item_id):
    """Reverse a credit or transfer, restoring the original item to active."""
    if reverse_credit(item_id):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Item not found or not in credited/transferred state."}), 400


@app.route("/api/events/add-player", methods=["POST"])
def api_add_player():
    """Add a player to an event (comp, RSVP only, or paid separately)."""
    data = request.get_json(silent=True)
    if not data or not data.get("event_name") or not data.get("customer"):
        return jsonify({"error": "event_name and customer are required."}), 400
    mode = data.get("mode", "comp")
    if mode not in ("comp", "rsvp", "paid_separately"):
        return jsonify({"error": "Invalid mode."}), 400
    item = add_player_to_event(
        event_name=data["event_name"],
        customer=data["customer"],
        mode=mode,
        side_games=data.get("side_games", ""),
        tee_choice=data.get("tee_choice", ""),
        handicap=data.get("handicap", ""),
        member_status=data.get("member_status", ""),
        payment_amount=data.get("payment_amount", ""),
        payment_source=data.get("payment_source", ""),
        customer_email=data.get("customer_email", ""),
        customer_phone=data.get("customer_phone", ""),
    )
    if item:
        return jsonify({"status": "ok", "item": item}), 201
    return jsonify({"error": "Failed to add player."}), 500


@app.route("/api/events/upgrade-rsvp", methods=["POST"])
def api_upgrade_rsvp():
    """Upgrade an RSVP-only placeholder to a full paid registration."""
    data = request.get_json(silent=True)
    if not data or not data.get("item_id"):
        return jsonify({"error": "item_id is required."}), 400
    item = upgrade_rsvp_to_paid(
        item_id=data["item_id"],
        payment_amount=data.get("payment_amount", ""),
        payment_source=data.get("payment_source", ""),
        side_games=data.get("side_games", ""),
        tee_choice=data.get("tee_choice", ""),
        handicap=data.get("handicap", ""),
        member_status=data.get("member_status", ""),
    )
    if item:
        return jsonify({"status": "ok", "item": item})
    return jsonify({"error": "Item not found or not in RSVP-only state."}), 400


@app.route("/api/events/send-reminder", methods=["POST"])
def api_send_reminder():
    """Send a payment reminder email to an RSVP-only player."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    to_email = (data.get("to_email") or "").strip()
    player_name = data.get("player_name", "Player")
    event_name = data.get("event_name", "the upcoming event")
    if not to_email:
        return jsonify({"error": "to_email is required"}), 400

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_address = os.getenv("EMAIL_ADDRESS")
    if not all([tenant_id, client_id, client_secret, from_address]):
        return jsonify({"error": "Email credentials not configured"}), 500

    subject = f"Payment Reminder — {event_name}"
    html_body = (
        f"<p>Hi {player_name},</p>"
        f"<p>This is a friendly reminder that we have you down for "
        f"<strong>{event_name}</strong>, but we haven't received your payment yet.</p>"
        f"<p>Please complete your registration at your earliest convenience.</p>"
        f"<p>Thanks,<br>The Golf Fellowship</p>"
    )

    ok = send_mail_graph(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        from_address=from_address,
        to_address=to_email,
        subject=subject,
        html_body=html_body,
    )
    if ok:
        return jsonify({"status": "ok", "message": f"Reminder sent to {to_email}"})
    return jsonify({"error": "Failed to send reminder email"}), 500


@app.route("/api/events/send-reminder-all", methods=["POST"])
def api_send_reminder_all():
    """Send payment reminder emails to ALL RSVP-only players for an event."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    event_name = (data.get("event_name") or "").strip()
    if not event_name:
        return jsonify({"error": "event_name is required"}), 400

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_address = os.getenv("EMAIL_ADDRESS")
    if not all([tenant_id, client_id, client_secret, from_address]):
        return jsonify({"error": "Email credentials not configured"}), 500

    # Find all RSVP-only players for this event with email addresses
    items = get_all_items()
    rsvp_players = [
        i for i in items
        if i.get("item_name") == event_name
        and (i.get("transaction_status") or "active") == "rsvp_only"
        and i.get("customer_email")
    ]

    if not rsvp_players:
        return jsonify({"error": "No RSVP-only players with emails found for this event"}), 404

    sent = 0
    failed = 0
    for player in rsvp_players:
        to_email = player["customer_email"].strip()
        player_name = player.get("customer") or "Player"
        subject = f"Payment Reminder — {event_name}"
        html_body = (
            f"<p>Hi {player_name},</p>"
            f"<p>This is a friendly reminder that we have you down for "
            f"<strong>{event_name}</strong>, but we haven't received your payment yet.</p>"
            f"<p>Please complete your registration at your earliest convenience.</p>"
            f"<p>Thanks,<br>The Golf Fellowship</p>"
        )
        ok = send_mail_graph(
            tenant_id=tenant_id, client_id=client_id,
            client_secret=client_secret, from_address=from_address,
            to_address=to_email, subject=subject, html_body=html_body,
        )
        if ok:
            sent += 1
        else:
            failed += 1

    return jsonify({"status": "ok", "sent": sent, "failed": failed, "total": len(rsvp_players)})


@app.route("/api/events/seed", methods=["POST"])
@require_role("admin")
def api_seed_events():
    """Batch-create events from a JSON list. Admin only."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("events"), list):
        return jsonify({"error": "Body must be JSON with 'events' array."}), 400
    result = seed_events(data["events"])
    return jsonify({"status": "ok", **result})


# ---------------------------------------------------------------------------
# Routes — RSVP
# ---------------------------------------------------------------------------
@app.route("/rsvps")
def rsvps_page():
    return render_template("rsvps.html")


@app.route("/api/rsvps")
def api_rsvps():
    """Return RSVPs, optionally filtered by event or response."""
    event = request.args.get("event", "")
    response = request.args.get("response", "")
    return jsonify(get_all_rsvps(event_name=event, response=response))


@app.route("/api/rsvps/event/<path:event_name>")
def api_rsvps_for_event(event_name):
    """Return the latest RSVP per player for a specific event."""
    return jsonify(get_rsvps_for_event(event_name))


@app.route("/api/rsvps/stats")
def api_rsvp_stats():
    """Return RSVP summary statistics."""
    return jsonify(get_rsvp_stats())


@app.route("/api/rsvps/check-now", methods=["POST"])
def api_rsvp_check_now():
    """Manually trigger an RSVP inbox check."""
    rsvp_address = os.getenv("RSVP_EMAIL_ADDRESS")
    if not rsvp_address:
        return jsonify({"error": "RSVP_EMAIL_ADDRESS not configured."}), 400

    try:
        check_rsvp_inbox()
        stats = get_rsvp_stats()
        return jsonify({"status": "ok", "stats": stats})
    except Exception as e:
        logger.exception("Manual RSVP check failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/rsvps/rematch", methods=["POST"])
def api_rsvp_rematch():
    """Re-run matching logic on unmatched RSVPs."""
    try:
        result = rematch_rsvps()
        return jsonify({"status": "ok", **result})
    except Exception as e:
        logger.exception("RSVP rematch failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/rsvps/<int:rsvp_id>/match", methods=["POST"])
@require_role("admin")
def api_manual_match_rsvp(rsvp_id):
    """Manually assign an RSVP to an event. Admin only."""
    data = request.get_json(silent=True)
    if not data or not data.get("event_name"):
        return jsonify({"error": "event_name is required."}), 400
    if manual_match_rsvp(rsvp_id, data["event_name"]):
        return jsonify({"status": "ok"})
    return jsonify({"error": "RSVP not found."}), 404


@app.route("/api/rsvps/<int:rsvp_id>/unmatch", methods=["POST"])
@require_role("admin")
def api_unmatch_rsvp(rsvp_id):
    """Clear the match for an RSVP. Admin only."""
    if unmatch_rsvp(rsvp_id):
        return jsonify({"status": "ok"})
    return jsonify({"error": "RSVP not found."}), 404


@app.route("/api/rsvps/overrides/<path:event_name>")
def api_rsvp_overrides(event_name):
    """Return manual RSVP overrides for an event as {item_id: status}."""
    return jsonify(get_rsvp_overrides(event_name))


@app.route("/api/rsvps/overrides", methods=["POST"])
def api_set_rsvp_override():
    """Set a manual RSVP override for a registrant."""
    data = request.get_json(force=True)
    item_id = data.get("item_id")
    event_name = data.get("event_name")
    status = data.get("status", "none")
    if not item_id or not event_name:
        return jsonify({"error": "item_id and event_name required"}), 400
    if status not in ("none", "playing", "not_playing", "manual_green"):
        return jsonify({"error": "status must be none, playing, or not_playing"}), 400
    set_rsvp_override(int(item_id), event_name, status)
    return jsonify({"status": "ok", "item_id": item_id, "event_name": event_name, "rsvp_status": status})


@app.route("/api/rsvps/config-status")
def api_rsvp_config_status():
    """Check whether RSVP email credentials are configured."""
    rsvp_ok = bool(os.getenv("RSVP_EMAIL_ADDRESS"))
    tenant_ok = bool(
        os.getenv("RSVP_AZURE_TENANT_ID") or os.getenv("AZURE_TENANT_ID")
    )
    return jsonify({
        "configured": rsvp_ok and tenant_ok,
        "rsvp_email": rsvp_ok,
        "azure_credentials": tenant_ok,
    })


@app.route("/api/report/send-now", methods=["POST"])
def api_send_report_now():
    """Manually trigger the daily report."""
    if not os.getenv("DAILY_REPORT_TO"):
        return jsonify({"error": "DAILY_REPORT_TO not configured in .env"}), 400
    try:
        send_daily_report()
        return jsonify({"status": "ok", "sent_to": os.getenv("DAILY_REPORT_TO")})
    except Exception as e:
        logger.exception("Manual report send failed")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Routes — Authentication
# ---------------------------------------------------------------------------
@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    """Authenticate with a PIN and set the session role."""
    # Re-read .env so PIN changes take effect without a server restart
    load_dotenv(override=True)

    data = request.get_json(silent=True)
    if not data or not data.get("pin"):
        return jsonify({"error": "PIN is required."}), 400

    pin = str(data["pin"]).strip()
    admin_pin = os.getenv("ADMIN_PIN", "")
    manager_pin = os.getenv("MANAGER_PIN", "")

    if admin_pin and secrets.compare_digest(pin, admin_pin):
        session["role"] = "admin"
        return jsonify({"status": "ok", "role": "admin"})
    elif manager_pin and secrets.compare_digest(pin, manager_pin):
        session["role"] = "manager"
        return jsonify({"status": "ok", "role": "manager"})
    else:
        return jsonify({"error": "Invalid PIN."}), 401


@app.route("/api/auth/role")
def api_auth_role():
    """Return the current session role (or null if not logged in)."""
    role = session.get("role")
    return jsonify({"role": role})


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Clear the session role."""
    session.pop("role", None)
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# App startup
# ---------------------------------------------------------------------------
init_db()

# Seed upcoming San Antonio events (idempotent — skips existing)
_SA_EVENTS = [
    {"item_name": "s9.1 The Quarry", "event_date": "2026-03-17", "course": "The Quarry", "city": "San Antonio"},
    {"item_name": "s9.2 Canyon Springs", "event_date": "2026-03-24", "course": "Canyon Springs", "city": "San Antonio"},
    {"item_name": "s9.3 Silverhorn", "event_date": "2026-03-31", "course": "Silverhorn", "city": "San Antonio"},
    {"item_name": "s9.4 Willow Springs", "event_date": "2026-04-07", "course": "Willow Springs", "city": "San Antonio"},
    {"item_name": "s18.4 LANDA PARK", "event_date": "2026-04-11", "course": "Landa Park", "city": "San Antonio"},
    {"item_name": "s9.5 Cedar Creek", "event_date": "2026-04-14", "course": "Cedar Creek", "city": "San Antonio"},
    {"item_name": "s9.6 The Quarry", "event_date": "2026-04-21", "course": "The Quarry", "city": "San Antonio"},
    {"item_name": "s9.7 Canyon Springs", "event_date": "2026-04-28", "course": "Canyon Springs", "city": "San Antonio"},
    {"item_name": "s18.5 WILLOW SPRINGS", "event_date": "2026-05-02", "course": "Willow Springs", "city": "San Antonio"},
    {"item_name": "s9.8 Silverhorn", "event_date": "2026-05-05", "course": "Silverhorn", "city": "San Antonio"},
    {"item_name": "s9.9 TPC San Antonio | Canyons", "event_date": "2026-05-12", "course": "TPC San Antonio - Canyons", "city": "San Antonio"},
    {"item_name": "HILL COUNTRY MATCHES | Comanche Trace", "event_date": "2026-05-16", "course": "Comanche Trace", "city": "San Antonio"},
    {"item_name": "s9.10 Brackenridge", "event_date": "2026-05-19", "course": "Brackenridge", "city": "San Antonio"},
    {"item_name": "s9.11 The Quarry", "event_date": "2026-05-26", "course": "The Quarry", "city": "San Antonio"},
    {"item_name": "s18.6 KISSING TREE", "event_date": "2026-05-30", "course": "Kissing Tree", "city": "San Antonio"},
    {"item_name": "s9.12 Canyon Springs", "event_date": "2026-06-02", "course": "Canyon Springs", "city": "San Antonio"},
]
_seed_result = seed_events(_SA_EVENTS)
if _seed_result["inserted"]:
    logger.info("Seeded %d SA events", _seed_result["inserted"])

# Only start the scheduler in one Gunicorn worker (or in dev mode).
# Gunicorn's --preload flag shares module-level state, but with forked workers
# each gets its own scheduler.  We use an env-based guard so only one runs.
_is_main_worker = not os.getenv("_SCHEDULER_STARTED")
if os.getenv("EMAIL_ADDRESS") and _is_main_worker:
    os.environ["_SCHEDULER_STARTED"] = "1"
    start_scheduler()
elif not os.getenv("EMAIL_ADDRESS"):
    logger.info("Email not configured — scheduler not started. Set up .env to enable auto-checking.")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
