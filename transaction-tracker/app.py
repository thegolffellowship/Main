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
import shutil
import sqlite3
import threading
from datetime import datetime, timedelta
from functools import wraps

import anthropic as _anthropic
from flask import Flask, Response, jsonify, render_template, request, send_file, session
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
    wd_item,
    create_event,
    seed_events,
    add_player_to_event,
    upgrade_rsvp_to_paid,
    autofix_side_games,
    autofix_all,
    undo_autofix,
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
    get_all_rsvps_bulk,
    get_rsvp_stats,
    rematch_rsvps,
    manual_match_rsvp,
    unmatch_rsvp,
    get_rsvp_overrides,
    set_rsvp_override,
    get_rsvp_email_overrides,
    set_rsvp_email_override,
    merge_customers,
    update_customer_info,
    create_customer,
    create_customer_from_rsvp,
    link_rsvp_to_customer,
    import_roster,
    preview_roster_import,
    get_customer_aliases,
    add_customer_alias,
    delete_customer_alias,
    parse_names_ai,
    validate_email,
    validate_phone,
    add_custom_field,
    save_feedback,
    get_all_feedback,
    update_feedback_status,
    get_message_templates,
    get_message_template,
    create_message_template,
    update_message_template,
    delete_message_template,
    log_message,
    get_message_log,
)
from email_parser.database import DB_PATH, get_connection
from email_parser.fetcher import (
    fetch_transaction_emails, fetch_email_by_id, send_mail_graph,
    render_msg_template, send_bulk_emails,
)
from email_parser.parser import parse_email, parse_emails, _strip_html
from email_parser.report import send_daily_report
from email_parser.rsvp_parser import fetch_rsvp_emails, parse_rsvp_emails

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
_secret_key = os.getenv("SECRET_KEY")
if not _secret_key:
    logger.warning("SECRET_KEY not set — using insecure default. Set SECRET_KEY in environment for production.")
    _secret_key = "dev-secret-key"
app.secret_key = _secret_key


@app.errorhandler(500)
def handle_500(e):
    """Return JSON instead of HTML for unhandled server errors."""
    logger.exception("Unhandled server error: %s", e)
    return jsonify({"error": "Internal server error"}), 500


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
        msg = str(e)
        # Provide user-friendly messages for known Anthropic API errors
        if "credit balance is too low" in msg.lower():
            _inbox_check_status["error"] = (
                "Anthropic API credit balance is too low. "
                "Please visit console.anthropic.com to add credits."
            )
        elif isinstance(e, _anthropic.AuthenticationError):
            _inbox_check_status["error"] = (
                "Anthropic API key is invalid or expired. "
                "Please check your ANTHROPIC_API_KEY in the .env file."
            )
        else:
            _inbox_check_status["error"] = msg
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
# Input validation helper
# ---------------------------------------------------------------------------
MAX_STRING_LENGTH = 1000


def validate_json_fields(data: dict, required: list[str] = None,
                         max_len: int = MAX_STRING_LENGTH) -> str | None:
    """Validate JSON input fields. Returns an error message or None if valid."""
    if required:
        for field in required:
            if not data.get(field):
                return f"'{field}' is required."
    for key, value in data.items():
        if isinstance(value, str) and len(value) > max_len:
            return f"'{key}' exceeds maximum length of {max_len} characters."
    return None


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

    # Daily digest — runs at 6:00 AM US/Central by default
    report_hour = int(os.getenv("DAILY_REPORT_HOUR", "6"))
    report_tz = os.getenv("DAILY_REPORT_TZ", "US/Central")
    if os.getenv("DAILY_REPORT_TO"):
        scheduler.add_job(
            send_daily_report,
            "cron",
            hour=report_hour,
            minute=0,
            timezone=report_tz,
            id="daily_report",
            replace_existing=True,
        )
        logger.info("Daily digest scheduled for %02d:00 %s → %s",
                     report_hour, report_tz, os.getenv("DAILY_REPORT_TO"))

    # Auto payment reminders — every other day at 6:00 AM US/Central
    reminder_tz = os.getenv("DAILY_REPORT_TZ", "US/Central")
    scheduler.add_job(
        send_auto_payment_reminders,
        "cron",
        day="*/2",
        hour=6,
        minute=0,
        timezone=reminder_tz,
        id="auto_payment_reminders",
        replace_existing=True,
    )
    logger.info("Auto payment reminders scheduled every other day at 06:00 %s",
                reminder_tz)

    scheduler.start()
    logger.info("Scheduler started — checking inbox every %d minutes", interval)


def send_auto_payment_reminders():
    """Send payment reminders to all RSVP-only/gg_rsvp players for upcoming events."""
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_address = os.getenv("EMAIL_ADDRESS")
    if not all([tenant_id, client_id, client_secret, from_address]):
        logger.warning("Auto reminders: email credentials not configured, skipping")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    events = get_all_events()
    items = get_all_items()

    total_sent = 0
    total_failed = 0

    for ev in events:
        event_date = ev.get("event_date") or ""
        # Skip past events
        if event_date and event_date < today:
            continue
        event_name = ev.get("item_name") or ""
        if not event_name:
            continue

        # Find RSVP-only / gg_rsvp players for this event (case-insensitive)
        rsvp_players = [
            i for i in items
            if (i.get("item_name") or "").lower() == event_name.lower()
            and (i.get("transaction_status") or "active") in ("rsvp_only", "gg_rsvp")
            and i.get("customer_email")
        ]
        if not rsvp_players:
            continue

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
            try:
                ok = send_mail_graph(
                    tenant_id=tenant_id, client_id=client_id,
                    client_secret=client_secret, from_address=from_address,
                    to_address=to_email, subject=subject, html_body=html_body,
                )
                if ok:
                    total_sent += 1
                else:
                    total_failed += 1
            except Exception:
                logger.exception("Auto reminder failed for %s", to_email)
                total_failed += 1

    logger.info("Auto payment reminders: %d sent, %d failed", total_sent, total_failed)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
_MAX_FIELD_LEN = 1000  # max characters per field value in update requests


def _validate_update_fields(data: dict) -> str | None:
    """Return an error message if any field value is invalid, else None."""
    for key, value in data.items():
        if not isinstance(key, str):
            return f"Field name must be a string, got {type(key).__name__}"
        if isinstance(value, str) and len(value) > _MAX_FIELD_LEN:
            return f"Field '{key}' exceeds max length ({_MAX_FIELD_LEN} chars)"
    return None


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
    err = validate_json_fields(data)
    if err:
        return jsonify({"error": err}), 400
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
    db_path = str(DB_PATH)
    if not os.path.isfile(db_path):
        return jsonify({"error": "Database file not found"}), 404
    # Copy to a temp file to avoid streaming a locked WAL-mode DB
    backup_path = db_path + ".backup"
    shutil.copy2(db_path, backup_path)
    # Also checkpoint WAL into the backup
    try:
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
    db_path = str(DB_PATH)
    db_exists = os.path.isfile(db_path)
    db_dir_exists = os.path.isdir(os.path.dirname(db_path))
    try:
        conn = get_connection()
        row = conn.execute("SELECT COUNT(*) as cnt FROM items").fetchone()
        item_count = row["cnt"]
        conn.close()
        db_readable = True
    except Exception:
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
                for f in ["customer", "order_id", "item_name", "item_price", "event_date"]:
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


@app.route("/api/audit/undo-autofix", methods=["POST"])
@require_role("admin")
def api_undo_autofix():
    """Revert a previous autofix using the saved details."""
    try:
        data = request.get_json(force=True)
        details = data.get("details", [])
        if not details:
            return jsonify({"error": "No details provided"}), 400
        result = undo_autofix(details)
        return jsonify({"status": "ok", **result})
    except Exception as e:
        logger.exception("Undo autofix failed")
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


@app.route("/api/audit/re-extract-fields", methods=["POST"])
@require_role("admin")
def api_re_extract_fields():
    """Re-parse existing transaction emails to backfill new fields.

    Fetches original emails from Graph API, re-runs AI extraction,
    and updates only the specified fields (partner_request, fellowship_after,
    notes) on existing items without overwriting other data.
    """
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    email_address = os.getenv("EMAIL_ADDRESS")

    if not all([tenant_id, client_id, client_secret, email_address]):
        return jsonify({"error": "Azure AD credentials not configured"}), 400

    BACKFILL_FIELDS = ["partner_request", "fellowship_after", "notes"]

    items = get_all_items()
    # Find items missing any of the new fields
    candidates = [
        it for it in items
        if it.get("transaction_status") in (None, "active")
        and not it.get("email_uid", "").startswith("manual-")
        and not all(it.get(f) for f in BACKFILL_FIELDS)
    ]

    total = len(candidates)
    updated = 0
    skipped = 0
    errors = 0

    # Group by email_uid to avoid re-fetching the same email multiple times
    uid_groups = {}
    for it in candidates:
        uid = it.get("email_uid", "")
        if uid:
            uid_groups.setdefault(uid, []).append(it)

    for uid, group_items in uid_groups.items():
        try:
            email_data = fetch_email_by_id(
                tenant_id, client_id, client_secret, email_address, uid
            )
            if not email_data:
                skipped += len(group_items)
                continue

            parsed_rows = parse_email(email_data)
            if not parsed_rows:
                skipped += len(group_items)
                continue

            for it in group_items:
                idx = it.get("item_index", 0) or 0
                if idx < len(parsed_rows):
                    parsed = parsed_rows[idx]
                else:
                    # Try to find by matching item name
                    parsed = next(
                        (p for p in parsed_rows
                         if p.get("item_name") == it.get("item_name")),
                        parsed_rows[0] if len(parsed_rows) == 1 else None,
                    )

                if not parsed:
                    skipped += 1
                    continue

                changes = {}
                for field in BACKFILL_FIELDS:
                    new_val = parsed.get(field)
                    if new_val and not it.get(field):
                        changes[field] = new_val

                if changes:
                    update_item(it["id"], changes)
                    updated += 1
                else:
                    skipped += 1

        except Exception:
            logger.exception("Re-extract failed for email_uid=%s", uid)
            errors += len(group_items)

    return jsonify({
        "status": "ok",
        "total_candidates": total,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    })


# ---------------------------------------------------------------------------
# Routes — Events
# ---------------------------------------------------------------------------
@app.route("/events")
def events_page():
    return render_template("events.html")


@app.route("/customers")
def customers_page():
    return render_template("customers.html")


@app.route("/api/customers/update", methods=["POST"])
@require_role("manager")
def api_update_customer():
    """Update personal info fields across all items for a customer.

    Body: { customer_name: str, fields: {customer_email, customer_phone, chapter, ...} }
    Updates every item row matching this customer name.
    """
    data = request.get_json(force=True)
    customer_name = (data.get("customer_name") or "").strip()
    fields = data.get("fields") or {}
    if not customer_name:
        return jsonify({"error": "customer_name is required"}), 400
    if not fields:
        return jsonify({"error": "fields object is required"}), 400

    # Only allow personal-info columns, not transaction data
    allowed = {"customer_email", "customer_phone", "chapter", "handicap",
               "date_of_birth", "shirt_size", "customer",
               "first_name", "last_name", "middle_name", "suffix"}
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return jsonify({"error": "No valid fields to update"}), 400

    try:
        updated = update_customer_info(customer_name, safe)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "ok", "items_updated": updated})


@app.route("/api/customers/create", methods=["POST"])
@require_role("manager")
def api_create_customer():
    """Create a new standalone customer."""
    data = request.get_json(force=True)
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    name = (data.get("name") or "").strip()
    # Build name from parts if not given directly
    if not name and (first_name or last_name):
        name = " ".join(filter(None, [first_name, last_name]))
    if not name:
        return jsonify({"error": "name is required"}), 400
    result = create_customer(
        name,
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        chapter=data.get("chapter", ""),
        first_name=first_name,
        last_name=last_name,
        middle_name=data.get("middle_name", ""),
        suffix=data.get("suffix", ""),
    )
    if result is None:
        return jsonify({"error": "Customer already exists"}), 409
    return jsonify({"status": "ok", "item": result})


@app.route("/api/customers/parse-roster", methods=["POST"])
@require_role("manager")
def api_parse_roster():
    """Parse an uploaded Excel file and return headers + preview rows."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    import io
    from openpyxl import load_workbook
    try:
        wb = load_workbook(io.BytesIO(file.read()), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)

        # Read up to first 5 rows to find the actual header row.
        # Spreadsheets often have a title/metadata row before real headers.
        candidate_rows = []
        for raw_row in rows_iter:
            candidate_rows.append(raw_row)
            if len(candidate_rows) >= 5:
                break
        if not candidate_rows:
            return jsonify({"error": "Empty spreadsheet"}), 400

        # Heuristic: the header row is the first row where >40% of cells
        # are non-empty.  Title rows typically have only 1-2 filled cells.
        header_idx = 0
        total_cols = len(candidate_rows[0])
        for i, row in enumerate(candidate_rows):
            non_empty = sum(1 for c in row if c is not None and str(c).strip())
            if non_empty >= max(2, total_cols * 0.4):
                header_idx = i
                break

        header_row = candidate_rows[header_idx]
        headers = [str(h).strip() if h else f"Column {i+1}"
                   for i, h in enumerate(header_row)]

        # Data rows = remaining candidate rows after header + rest of sheet
        data_candidate = candidate_rows[header_idx + 1:]
        preview = []
        for row in data_candidate:
            preview.append([str(c).strip() if c is not None else "" for c in row])
        for row in rows_iter:
            if len(preview) >= 100:
                break
            preview.append([str(c).strip() if c is not None else "" for c in row])

        wb.close()
        return jsonify({"headers": headers, "preview": preview,
                        "total_rows": len(preview)})
    except Exception as e:
        return jsonify({"error": f"Failed to parse file: {str(e)}"}), 400


@app.route("/api/customers/import-roster", methods=["POST"])
@require_role("manager")
def api_import_roster():
    """Import roster data with column mapping.

    Body: { mapping: {db_field: excel_col_index, ...}, data: [[...], ...],
            new_fields: [{name: "field_name", col_index: N}, ...] }
    """
    data = request.get_json(force=True)
    mapping = data.get("mapping") or {}
    rows_data = data.get("data") or []
    new_fields = data.get("new_fields") or []
    if not mapping or not rows_data:
        return jsonify({"error": "mapping and data are required"}), 400

    # Create any new custom fields first
    fields_created = []
    for nf in new_fields:
        field_name = (nf.get("name") or "").strip().lower().replace(" ", "_")
        col_idx = nf.get("col_index")
        if field_name and col_idx is not None:
            try:
                created = add_custom_field(field_name)
                if created:
                    fields_created.append(field_name)
                # Add to the mapping
                mapping[field_name] = col_idx
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

    # mapping is like {"customer": 0, "customer_email": 2, ...}
    # rows_data is the array of arrays from the preview
    import_rows = []
    for row in rows_data:
        mapped = {}
        for db_field, col_idx in mapping.items():
            if col_idx is not None and 0 <= col_idx < len(row):
                val = str(row[col_idx]).strip() if row[col_idx] else ""
                if val:
                    mapped[db_field] = val
        # Support name from first+last OR full name
        if not mapped.get("customer"):
            first = mapped.get("first_name", "")
            last = mapped.get("last_name", "")
            if first or last:
                mapped["customer"] = " ".join(filter(None, [first, last]))
        if mapped.get("customer"):
            import_rows.append(mapped)

    if not import_rows:
        return jsonify({"error": "No valid rows to import (customer name required)"}), 400

    try:
        result = import_roster(import_rows)
    except Exception as e:
        logger.exception("Roster import failed")
        return jsonify({"error": f"Import failed: {str(e)}"}), 500
    result["fields_created"] = fields_created
    return jsonify(result)


@app.route("/api/customers/preview-roster", methods=["POST"])
@require_role("manager")
def api_preview_roster():
    """Preview a roster import with AI name parsing and duplicate detection.

    Body: { mapping: {db_field: excel_col_index, ...}, data: [[...], ...] }
    Returns enriched row data with parsed names, match status, and validation warnings.
    """
    data = request.get_json(force=True)
    mapping = data.get("mapping") or {}
    rows_data = data.get("data") or []
    if not mapping or not rows_data:
        return jsonify({"error": "mapping and data are required"}), 400

    # Build mapped rows
    preview_rows = []
    for row in rows_data:
        mapped = {}
        for db_field, col_idx in mapping.items():
            if col_idx is not None and 0 <= col_idx < len(row):
                val = str(row[col_idx]).strip() if row[col_idx] else ""
                if val:
                    mapped[db_field] = val
        # Support name from first+last OR full name
        if not mapped.get("customer"):
            first = mapped.get("first_name", "")
            last = mapped.get("last_name", "")
            if first or last:
                mapped["customer"] = " ".join(filter(None, [first, last]))
        if mapped.get("customer"):
            preview_rows.append(mapped)

    if not preview_rows:
        return jsonify({"error": "No valid rows"}), 400

    try:
        result = preview_roster_import(preview_rows)
    except Exception as e:
        logger.exception("Roster preview failed")
        return jsonify({"error": f"Preview analysis failed: {str(e)}"}), 500
    return jsonify(result)


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


@app.route("/api/customers/aliases", methods=["GET"])
@require_role("manager")
def api_get_aliases():
    """Get aliases for a customer. Query: ?customer_name=..."""
    customer_name = request.args.get("customer_name", "").strip()
    if not customer_name:
        return jsonify({"error": "customer_name is required"}), 400
    aliases = get_customer_aliases(customer_name)
    return jsonify({"aliases": aliases})


@app.route("/api/customers/aliases", methods=["POST"])
@require_role("manager")
def api_add_alias():
    """Add an alias for a customer."""
    data = request.get_json(force=True)
    customer_name = (data.get("customer_name") or "").strip()
    alias_type = (data.get("alias_type") or "").strip()
    alias_value = (data.get("alias_value") or "").strip()
    if not customer_name or not alias_type or not alias_value:
        return jsonify({"error": "customer_name, alias_type, and alias_value are required"}), 400
    try:
        result = add_customer_alias(customer_name, alias_type, alias_value)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result)


@app.route("/api/customers/aliases/<int:alias_id>", methods=["DELETE"])
@require_role("manager")
def api_delete_alias(alias_id):
    """Delete an alias by ID."""
    deleted = delete_customer_alias(alias_id)
    if not deleted:
        return jsonify({"error": "Alias not found"}), 404
    return jsonify({"status": "ok"})


@app.route("/api/customers/from-rsvp", methods=["POST"])
@require_role("manager")
def api_create_customer_from_rsvp():
    """Create a customer from an unmatched RSVP and link them."""
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    try:
        result = create_customer_from_rsvp(name, email)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Error creating customer from RSVP: %s", e)
        return jsonify({"error": f"Server error: {e}"}), 500


@app.route("/api/customers/link-rsvp", methods=["POST"])
@require_role("manager")
def api_link_rsvp_to_customer():
    """Link an unmatched RSVP email to an existing customer."""
    data = request.get_json(force=True)
    rsvp_email = (data.get("rsvp_email") or "").strip()
    target_name = (data.get("target_customer") or "").strip()
    rsvp_player_name = (data.get("rsvp_player_name") or "").strip()
    if not rsvp_email or not target_name:
        return jsonify({"error": "rsvp_email and target_customer are required"}), 400
    try:
        result = link_rsvp_to_customer(rsvp_email, target_name, rsvp_player_name)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Error linking RSVP to customer: %s", e)
        return jsonify({"error": f"Server error: {e}"}), 500


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
    err = _validate_update_fields(data)
    if err:
        return jsonify({"error": err}), 400
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
        chapter=data.get("chapter"),
        format=data.get("format"),
        start_type=data.get("start_type"),
        start_time=data.get("start_time"),
        tee_time_count=data.get("tee_time_count"),
        tee_time_interval=data.get("tee_time_interval"),
        start_time_18=data.get("start_time_18"),
        start_type_18=data.get("start_type_18"),
        tee_time_count_18=data.get("tee_time_count_18"),
        tee_direction=data.get("tee_direction"),
        tee_direction_18=data.get("tee_direction_18"),
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


@app.route("/api/sunset")
def api_sunset():
    """Return sunset and civil twilight times for a chapter + date, in Central Time."""
    import pytz
    import requests as _requests
    from datetime import datetime as _dt

    # TODO: pull chapter coordinates from a chapters table when full platform is built
    CHAPTER_COORDS = {
        "San Antonio": (29.4241, -98.4936),
        "Austin": (30.2672, -97.7431),
    }

    date_str = request.args.get("date")
    chapter = request.args.get("chapter")
    if not date_str or not chapter:
        return jsonify({"error": "date and chapter are required"}), 400
    coords = CHAPTER_COORDS.get(chapter)
    if not coords:
        return jsonify({"error": f"Unknown chapter: {chapter}"}), 400

    try:
        resp = _requests.get(
            "https://api.sunrise-sunset.org/json",
            params={"lat": coords[0], "lng": coords[1], "date": date_str, "formatted": 0},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != "OK":
            return jsonify({"error": "Sunrise-Sunset API error"}), 502

        results = data["results"]
        central = pytz.timezone("America/Chicago")

        def to_central_12h(iso_str):
            utc_dt = _dt.fromisoformat(iso_str.replace("Z", "+00:00"))
            local_dt = utc_dt.astimezone(central)
            return local_dt.strftime("%-I:%M %p"), local_dt.strftime("%H:%M")

        sunset_12h, sunset_24h = to_central_12h(results["sunset"])
        twilight_12h, twilight_24h = to_central_12h(results["civil_twilight_end"])

        return jsonify({
            "sunset": sunset_12h,
            "sunset_24h": sunset_24h,
            "civil_twilight_end": twilight_12h,
            "civil_twilight_end_24h": twilight_24h,
        })
    except _requests.RequestException:
        return jsonify({"error": "Failed to reach Sunrise-Sunset API"}), 502
    except Exception as exc:
        logger.exception("Sunset API error")
        return jsonify({"error": str(exc)}), 500


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


@app.route("/api/items/<int:item_id>/wd", methods=["POST"])
def api_wd_item(item_id):
    """Mark an item as WD (withdrawn) with optional partial credit."""
    data = request.get_json(silent=True) or {}
    note = data.get("note", "")
    credits = data.get("credits")  # dict like {"included_games": 14, ...}
    credit_amount = data.get("credit_amount", "")
    if wd_item(item_id, note=note, credits=credits, credit_amount=credit_amount):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Item not found or already credited/transferred/WD."}), 400


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
    err = validate_json_fields(data)
    if err:
        return jsonify({"error": err}), 400
    mode = data.get("mode", "comp")
    if mode not in ("comp", "rsvp", "paid_separately"):
        return jsonify({"error": "Invalid mode."}), 400
    try:
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
    except Exception as e:
        logger.exception("Error adding player: %s", e)
        return jsonify({"error": f"Server error: {e}"}), 500


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

    # Find all RSVP-only players for this event with email addresses (case-insensitive)
    items = get_all_items()
    rsvp_players = [
        i for i in items
        if (i.get("item_name") or "").lower() == event_name.lower()
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

    if sent == 0:
        return jsonify({"error": "All reminder emails failed to send", "sent": sent, "failed": failed, "total": len(rsvp_players)}), 500
    status = "ok" if failed == 0 else "partial"
    return jsonify({"status": status, "sent": sent, "failed": failed, "total": len(rsvp_players)})


# ---------------------------------------------------------------------------
# Routes — Messaging (Bulk Email Communications)
# ---------------------------------------------------------------------------

@app.route("/api/messages/templates", methods=["GET"])
def api_get_templates():
    """Return all message templates."""
    return jsonify(get_message_templates())


@app.route("/api/messages/templates", methods=["POST"])
@require_role("manager")
def api_create_template():
    """Create a new message template."""
    data = request.get_json(silent=True)
    if not data or not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    template = create_message_template(data)
    return jsonify(template), 201


@app.route("/api/messages/templates/<int:template_id>", methods=["PATCH"])
@require_role("manager")
def api_update_template(template_id):
    """Update a message template."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    result = update_message_template(template_id, data)
    if result is None:
        return jsonify({"error": "Template not found"}), 404
    return jsonify(result)


@app.route("/api/messages/templates/<int:template_id>", methods=["DELETE"])
@require_role("admin")
def api_delete_template(template_id):
    """Delete a non-system message template."""
    if delete_message_template(template_id):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Template not found or is a system template"}), 400


@app.route("/api/messages/send", methods=["POST"])
@require_role("manager")
def api_send_messages():
    """Send a message to a filtered audience for an event.

    Body: {
        event_name: str,
        template_id: int (optional — use template subject/body),
        subject: str (overrides template subject if provided),
        html_body: str (overrides template body if provided),
        audience: str (all|playing|rsvp_only|net|gross|both|not_playing|custom),
        custom_emails: [str] (required when audience=custom — specific email addresses),
        exclude_ids: [int] (optional — item IDs to exclude)
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    event_name = (data.get("event_name") or "").strip()
    if not event_name:
        return jsonify({"error": "event_name is required"}), 400

    # Resolve subject + body from template or direct input
    subject_tpl = data.get("subject") or ""
    body_tpl = data.get("html_body") or ""
    template_id = data.get("template_id")

    if template_id:
        tpl = get_message_template(template_id)
        if not tpl:
            return jsonify({"error": "Template not found"}), 404
        if not subject_tpl:
            subject_tpl = tpl.get("subject") or ""
        if not body_tpl:
            body_tpl = tpl.get("html_body") or ""

    if not subject_tpl or not body_tpl:
        return jsonify({"error": "subject and html_body are required (directly or via template)"}), 400

    # Build event variables for template rendering
    all_events = get_all_events()
    event_info = next((e for e in all_events if (e["item_name"] or "").lower() == event_name.lower()), {})
    event_vars = {
        "event_name": event_name,
        "event_date": event_info.get("event_date") or "",
        "course": event_info.get("course") or "",
        "chapter": event_info.get("chapter") or "",
    }

    # Filter audience
    audience = (data.get("audience") or "all").lower()
    custom_emails = set()
    if audience == "custom":
        raw = data.get("custom_emails") or []
        custom_emails = {e.strip().lower() for e in raw if isinstance(e, str) and e.strip()}
        if not custom_emails:
            return jsonify({"error": "custom_emails list is required for custom audience"}), 400
    exclude_ids = set(data.get("exclude_ids") or [])
    items = get_all_items()

    # Get event aliases for matching
    all_aliases = get_all_event_aliases()
    alias_to_canonical = {}
    for alias_name, canonical in all_aliases.items():
        alias_to_canonical[alias_name] = canonical

    def matches_event(item):
        iname = item.get("item_name") or ""
        if iname == event_name:
            return True
        if alias_to_canonical.get(iname) == event_name:
            return True
        return False

    registrants = [i for i in items if matches_event(i)]

    # Build email lookup by customer name (for resolving missing customer_email)
    email_by_name = {}
    for it in items:
        cname = (it.get("customer") or "").strip().lower()
        cemail = (it.get("customer_email") or "").strip()
        if cname and cemail and cname not in email_by_name:
            email_by_name[cname] = cemail

    def resolve_email(r):
        """Return email from item row, or look up from other items by customer name."""
        email = (r.get("customer_email") or "").strip()
        if email:
            return email
        cname = (r.get("customer") or "").strip().lower()
        if cname:
            return email_by_name.get(cname, "")
        return ""

    # Get RSVP override data for playing/not_playing filtering
    rsvp_overrides = {}
    try:
        overrides = get_rsvp_overrides(event_name)
        for ov in overrides:
            rsvp_overrides[ov["item_id"]] = ov["status"]
    except Exception:
        pass

    rsvps_for_event = {}
    rsvp_list = []
    try:
        rsvp_list = get_rsvps_for_event(event_name)
        for rv in rsvp_list:
            if rv.get("matched_item_id"):
                rsvps_for_event[rv["matched_item_id"]] = rv["response"]
    except Exception:
        pass

    # Build GG RSVP synthetic rows (unmatched RSVPs with player_email)
    email_overrides = {}
    try:
        email_overrides = get_rsvp_email_overrides(event_name)
    except Exception:
        pass

    reg_emails = {(r.get("customer_email") or "").strip().lower() for r in registrants if r.get("customer_email")}
    reg_names = {(r.get("customer") or "").strip().lower() for r in registrants if r.get("customer")}
    gg_rsvp_rows = []
    for rv in rsvp_list:
        if rv.get("response") != "PLAYING":
            continue
        if rv.get("matched_item_id"):
            continue
        email = (rv.get("player_email") or "").strip().lower()
        if email and email_overrides.get(email) == "not_playing":
            continue
        if email and email in reg_emails:
            continue
        resolved = (rv.get("resolved_name") or "").strip().lower()
        first_name = (rv.get("player_name") or "").strip().lower()
        if resolved and resolved in reg_names:
            continue
        if first_name and any(n.startswith(first_name) for n in reg_names):
            continue
        if not (rv.get("player_email") or "").strip():
            continue  # No email — can't message them
        gg_rsvp_rows.append({
            "id": f"gg-rsvp-{len(gg_rsvp_rows)}",
            "customer": rv.get("resolved_name") or rv.get("player_name") or "Unknown",
            "customer_email": (rv.get("player_email") or "").strip(),
            "item_name": event_name,
            "transaction_status": "gg_rsvp",
            "side_games": "",
        })

    all_registrants = registrants + gg_rsvp_rows

    def get_rsvp_status(item):
        item_id = item["id"]
        if isinstance(item_id, str) and item_id.startswith("gg-rsvp"):
            return "playing"  # GG RSVP players are playing by definition
        override = rsvp_overrides.get(item_id)
        if override and override != "none":
            return override  # playing, not_playing, manual_green
        rsvp_resp = rsvps_for_event.get(item_id)
        if rsvp_resp == "PLAYING":
            return "playing"
        if rsvp_resp == "NOT PLAYING":
            return "not_playing"
        return "unknown"

    def classify_side_games(sg):
        sg = (sg or "").strip().upper()
        if sg in ("NET", "GROSS", "BOTH", "NONE"):
            return sg
        return "NONE"

    filtered = []
    for r in all_registrants:
        rid = r["id"]
        if not (isinstance(rid, str) and rid.startswith("gg-rsvp")) and rid in exclude_ids:
            continue
        status = (r.get("transaction_status") or "active")
        # Skip credited/transferred
        if status in ("credited", "transferred"):
            continue
        email = resolve_email(r)
        if not email:
            continue

        sg = classify_side_games(r.get("side_games"))
        rsvp = get_rsvp_status(r)

        if audience == "all":
            filtered.append(r)
        elif audience == "playing":
            if rsvp in ("playing", "manual_green"):
                filtered.append(r)
        elif audience == "rsvp_only":
            if status in ("rsvp_only", "gg_rsvp"):
                filtered.append(r)
        elif audience == "net":
            if sg in ("NET", "BOTH"):
                filtered.append(r)
        elif audience == "gross":
            if sg in ("GROSS", "BOTH"):
                filtered.append(r)
        elif audience == "both":
            if sg == "BOTH":
                filtered.append(r)
        elif audience == "not_playing":
            if rsvp == "not_playing":
                filtered.append(r)
        elif audience == "custom":
            if email.lower() in custom_emails:
                filtered.append(r)
        else:
            filtered.append(r)

    # Build recipient list from filtered registrants
    recipients = [
        {"player_name": r.get("customer") or "Player", "email": resolve_email(r)}
        for r in filtered
    ]

    # Add extra recipients (manually entered emails not on the player list)
    extra_recipients = data.get("extra_recipients") or []
    seen_emails = {r["email"].lower() for r in recipients}
    for er in extra_recipients:
        email = (er.get("email") or "").strip()
        if email and email.lower() not in seen_emails:
            recipients.append({"player_name": er.get("name") or email.split("@")[0], "email": email})
            seen_emails.add(email.lower())

    if not recipients:
        return jsonify({"error": "No recipients found matching the audience filter", "sent": 0, "failed": 0}), 404

    # Send with throttle
    result = send_bulk_emails(
        recipients=recipients,
        subject_template=subject_tpl,
        body_template=body_tpl,
        event_vars=event_vars,
    )

    # Log each send
    role = session.get("role", "unknown")
    body_preview = render_msg_template(body_tpl, {**event_vars, "player_name": "..."})[:200]
    error_emails = [e["recipient"] for e in result.get("errors", [])]
    for r in recipients:
        email = r["email"]
        was_sent = email not in error_emails
        log_message({
            "event_name": event_name,
            "template_id": template_id,
            "channel": "email",
            "recipient_name": r.get("player_name"),
            "recipient_address": email,
            "subject": render_msg_template(subject_tpl, {**event_vars, "player_name": r.get("player_name") or "Player"}),
            "body_preview": body_preview,
            "status": "sent" if was_sent else "failed",
            "error_message": None if was_sent else "Send failed",
            "sent_by": role,
        })

    status = "ok" if result["failed"] == 0 else "partial"
    return jsonify({
        "status": status,
        "sent": result["sent"],
        "failed": result["failed"],
        "total": len(recipients),
        "errors": result["errors"],
    })


@app.route("/api/messages/preview", methods=["POST"])
@require_role("manager")
def api_preview_message():
    """Render a message template with sample data. Returns rendered subject + body."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    subject_tpl = data.get("subject") or ""
    body_tpl = data.get("html_body") or ""
    template_id = data.get("template_id")

    if template_id:
        tpl = get_message_template(template_id)
        if tpl:
            if not subject_tpl:
                subject_tpl = tpl.get("subject") or ""
            if not body_tpl:
                body_tpl = tpl.get("html_body") or ""

    variables = {
        "player_name": data.get("player_name", "John Doe"),
        "event_name": data.get("event_name", "Sample Event"),
        "event_date": data.get("event_date", "2026-03-15"),
        "course": data.get("course", "Sample Course"),
        "chapter": data.get("chapter", "San Antonio"),
    }

    return jsonify({
        "subject": render_msg_template(subject_tpl, variables),
        "html_body": render_msg_template(body_tpl, variables),
    })


@app.route("/api/messages/log", methods=["GET"])
@require_role("manager")
def api_message_log():
    """Return message send history, optionally filtered by event."""
    event_name = request.args.get("event_name")
    limit = min(int(request.args.get("limit", 200)), 1000)
    return jsonify(get_message_log(event_name=event_name, limit=limit))


@app.route("/api/messages/log/<path:event_name>", methods=["GET"])
@require_role("manager")
def api_message_log_event(event_name):
    """Return message log for a specific event."""
    return jsonify(get_message_log(event_name=event_name))


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


@app.route("/api/rsvps/bulk")
def api_rsvps_bulk():
    """Return all RSVPs, overrides, and email overrides grouped by event.

    Used by the events page to show accurate player counts on collapsed cards
    without requiring per-event fetches.
    """
    return jsonify(get_all_rsvps_bulk())


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
    """Return manual RSVP overrides for an event.

    Returns {"by_item": {item_id: status}, "by_email": {email: status}}.
    """
    return jsonify({
        "by_item": get_rsvp_overrides(event_name),
        "by_email": get_rsvp_email_overrides(event_name),
    })


@app.route("/api/rsvps/overrides", methods=["POST"])
def api_set_rsvp_override():
    """Set a manual RSVP override for a registrant (by item_id or player_email)."""
    data = request.get_json(force=True)
    item_id = data.get("item_id")
    player_email = data.get("player_email")
    event_name = data.get("event_name")
    status = data.get("status", "none")
    if not event_name:
        return jsonify({"error": "event_name required"}), 400
    if not item_id and not player_email:
        return jsonify({"error": "item_id or player_email required"}), 400
    if status not in ("none", "playing", "not_playing", "manual_green"):
        return jsonify({"error": "status must be none, playing, not_playing, or manual_green"}), 400
    if player_email:
        set_rsvp_email_override(player_email, event_name, status)
        return jsonify({"status": "ok", "player_email": player_email, "event_name": event_name, "rsvp_status": status})
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
# Routes — AI Support Chat & Feedback
# ---------------------------------------------------------------------------


def _send_feedback_notification(feedback: dict):
    """Send an instant email notification when a new bug/feature is submitted."""
    notify_to = os.getenv("FEEDBACK_NOTIFY_TO") or os.getenv("DAILY_REPORT_TO")
    if not notify_to:
        return

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_addr = os.getenv("EMAIL_ADDRESS")
    if not all([tenant_id, client_id, client_secret, from_addr]):
        return

    fb_type = feedback.get("type", "feedback").capitalize()
    label = "Bug Report" if feedback.get("type") == "bug" else "Feature Request"
    color = "#dc2626" if feedback.get("type") == "bug" else "#2563eb"
    page = feedback.get("page") or "Unknown"
    role = feedback.get("role") or "Unknown"
    created = feedback.get("created_at") or "—"
    message = feedback.get("message") or ""

    html = f"""\
<html><body style="font-family: Arial, sans-serif; color: #333; max-width: 600px;">
<h2 style="color: {color};">New {label} Submitted</h2>
<table style="font-size: 14px; margin-bottom: 16px;">
  <tr><td style="padding:4px 12px 4px 0; font-weight:600;">Type:</td>
      <td><span style="background:{color}; color:#fff; padding:2px 10px; border-radius:10px; font-size:12px;">{fb_type}</span></td></tr>
  <tr><td style="padding:4px 12px 4px 0; font-weight:600;">Page:</td><td>{page}</td></tr>
  <tr><td style="padding:4px 12px 4px 0; font-weight:600;">Submitted by:</td><td>{role}</td></tr>
  <tr><td style="padding:4px 12px 4px 0; font-weight:600;">Time:</td><td>{created}</td></tr>
</table>
<div style="background:#f9fafb; border-left:4px solid {color}; padding:12px 16px; margin-bottom:16px; white-space:pre-wrap;">{message}</div>
<p style="font-size:12px; color:#999;">This is an automated notification from TGF Transaction Tracker.</p>
</body></html>"""

    subject = f"[TGF {label}] New submission from {page} page"

    try:
        ok = send_mail_graph(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            from_address=from_addr,
            to_address=notify_to,
            subject=subject,
            html_body=html,
        )
        if not ok:
            logger.warning("Feedback notification email failed to send to %s", notify_to)
    except Exception:
        logger.exception("Failed to send feedback notification email")

_TGF_SYSTEM_PROMPT = """You are the TGF Assistant, an AI helper built into The Golf Fellowship's Transaction Tracker.
You help managers and admins understand and use the platform.

Key facts about the platform:
- Pages: Transactions (main item list), Events (event roster + RSVP circles), Customers (player directory with merge), RSVP Log, Matrix (admin pairings), Audit (email verification).
- Transaction items are parsed from emails via AI. Each row = one line item from a purchase.
- Events are auto-created from transaction item names when they match golf event patterns.
- Event aliases link variant item names to a canonical event (e.g. "San Antonio Kickoff NORTHERN HILLS" → "San Antonio Kickoff CEDAR CREEK").
- RSVP circles show player status: green = paid, yellow/dotted = RSVP only (no payment), red = not playing, gray = no response. Real Golf Genius RSVPs override manual green.
- Orphan banner appears when transaction items don't match any event — admins can create the event or add an alias.
- Customer merge combines two player records (e.g. "Jdub Wade" + "John Wade").
- Credits: items can be credited (money on account), transferred to another event, or reversed.
- Auth: PIN-based, two tiers — Admin (full access) and Manager (no audit/matrix).
- Bulk "Remind All" sends payment reminder emails to RSVP-only players on an event.
- Database backup is available at /admin/backup (admin only).

When answering:
- Be concise and helpful. Use specific page names and button labels.
- If you don't know something specific about TGF data, say so — don't guess at numbers.
- For bugs or feature requests, encourage the user to use the Report a Bug or Request a Feature buttons.
- You can explain any feature, workflow, or concept in the platform.
"""


@app.route("/api/support/chat", methods=["POST"])
def api_support_chat():
    """Streaming AI chat endpoint for the support widget."""
    user_role = session.get("role")
    if not user_role:
        return jsonify({"error": "Not authenticated."}), 401

    data = request.get_json(silent=True)
    if not data or not data.get("message"):
        return jsonify({"error": "Message is required."}), 400

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "AI not configured (missing API key)."}), 503

    messages = data.get("history", [])
    messages.append({"role": "user", "content": data.get("message", "")})

    page = data.get("page", "")
    role_context = f"\nThe user is a {user_role} currently on the {page} page." if page else f"\nThe user is a {user_role}."

    def generate():
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        try:
            with client.messages.stream(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                system=_TGF_SYSTEM_PROMPT + role_context,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"
            yield "data: {\"done\": true}\n\n"
        except Exception as e:
            logger.exception("Support chat error")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/support/feedback", methods=["POST"])
def api_support_feedback_post():
    """Log a bug report or feature request."""
    user_role = session.get("role")
    if not user_role:
        return jsonify({"error": "Not authenticated."}), 401

    data = request.get_json(silent=True)
    if not data or not data.get("message"):
        return jsonify({"error": "Message is required."}), 400
    err = validate_json_fields(data)
    if err:
        return jsonify({"error": err}), 400

    fb_type = data.get("type", "bug")
    if fb_type not in ("bug", "feature"):
        return jsonify({"error": "Type must be 'bug' or 'feature'."}), 400

    result = save_feedback(
        feedback_type=fb_type,
        message=data["message"],
        page=data.get("page", ""),
        role=user_role,
    )

    # Send instant email notification for new feedback
    _send_feedback_notification(result)

    return jsonify({"status": "ok", "feedback": result})


@app.route("/api/support/feedback", methods=["GET"])
@require_role("admin")
def api_support_feedback_get():
    """Return all feedback (admin only)."""
    rows = get_all_feedback()
    return jsonify({"feedback": rows})


@app.route("/api/support/feedback/<int:feedback_id>", methods=["PATCH"])
@require_role("admin")
def api_support_feedback_update(feedback_id):
    """Update feedback status (admin only)."""
    data = request.get_json(silent=True)
    if not data or not data.get("status"):
        return jsonify({"error": "Status is required."}), 400
    new_status = data.get("status", "")
    if new_status not in ("open", "resolved", "dismissed"):
        return jsonify({"error": "Status must be 'open', 'resolved', or 'dismissed'."}), 400
    ok = update_feedback_status(feedback_id, new_status)
    if not ok:
        return jsonify({"error": "Feedback not found."}), 404
    return jsonify({"status": "ok"})


@app.route("/api/support/test-digest", methods=["POST"])
@require_role("admin")
def api_test_digest():
    """Send the daily digest email right now (admin only)."""
    try:
        send_daily_report()
        return jsonify({"status": "ok", "message": "Daily digest sent."})
    except Exception as e:
        logger.exception("Test digest failed")
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

    pin = str(data.get("pin", "")).strip()
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
    {"item_name": "s9.1 The Quarry", "event_date": "2026-03-17", "course": "The Quarry", "chapter": "San Antonio"},
    {"item_name": "s9.2 Canyon Springs", "event_date": "2026-03-24", "course": "Canyon Springs", "chapter": "San Antonio"},
    {"item_name": "s9.3 Silverhorn", "event_date": "2026-03-31", "course": "Silverhorn", "chapter": "San Antonio"},
    {"item_name": "s9.4 Willow Springs", "event_date": "2026-04-07", "course": "Willow Springs", "chapter": "San Antonio"},
    {"item_name": "s18.4 LANDA PARK", "event_date": "2026-04-11", "course": "Landa Park", "chapter": "San Antonio"},
    {"item_name": "s9.5 Cedar Creek", "event_date": "2026-04-14", "course": "Cedar Creek", "chapter": "San Antonio"},
    {"item_name": "s9.6 The Quarry", "event_date": "2026-04-21", "course": "The Quarry", "chapter": "San Antonio"},
    {"item_name": "s9.7 Canyon Springs", "event_date": "2026-04-28", "course": "Canyon Springs", "chapter": "San Antonio"},
    {"item_name": "s18.5 WILLOW SPRINGS", "event_date": "2026-05-02", "course": "Willow Springs", "chapter": "San Antonio"},
    {"item_name": "s9.8 Silverhorn", "event_date": "2026-05-05", "course": "Silverhorn", "chapter": "San Antonio"},
    {"item_name": "s9.9 TPC San Antonio | Canyons", "event_date": "2026-05-12", "course": "TPC San Antonio - Canyons", "chapter": "San Antonio"},
    {"item_name": "HILL COUNTRY MATCHES | Comanche Trace", "event_date": "2026-05-16", "course": "Comanche Trace", "chapter": "San Antonio"},
    {"item_name": "s9.10 Brackenridge", "event_date": "2026-05-19", "course": "Brackenridge", "chapter": "San Antonio"},
    {"item_name": "s9.11 The Quarry", "event_date": "2026-05-26", "course": "The Quarry", "chapter": "San Antonio"},
    {"item_name": "s18.6 KISSING TREE", "event_date": "2026-05-30", "course": "Kissing Tree", "chapter": "San Antonio"},
    {"item_name": "s9.12 Canyon Springs", "event_date": "2026-06-02", "course": "Canyon Springs", "chapter": "San Antonio"},
]
_seed_result = seed_events(_SA_EVENTS)
if _seed_result["inserted"]:
    logger.info("Seeded %d SA events", _seed_result["inserted"])

# Only start the scheduler in one Gunicorn worker (or in dev mode).
# Gunicorn's --preload flag shares module-level state, but with forked workers
# each gets its own scheduler.  We use a PID-based guard so only one runs.
_scheduler_lock = threading.Lock()
with _scheduler_lock:
    _scheduler_pid = os.getenv("_SCHEDULER_STARTED_PID")
    _is_main_worker = _scheduler_pid is None or _scheduler_pid == str(os.getpid())
    if os.getenv("EMAIL_ADDRESS") and _is_main_worker:
        os.environ["_SCHEDULER_STARTED_PID"] = str(os.getpid())
        start_scheduler()
    elif not os.getenv("EMAIL_ADDRESS"):
        logger.info("Email not configured — scheduler not started. Set up .env to enable auto-checking.")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
