"""
Transaction Email Tracker — Flask application.

Automatically checks your email inbox for transaction/receipt emails,
parses purchase data with AI (Claude), and displays it in a web dashboard.
Includes a webhook connector for external integrations and a daily email report.
"""

import os
import secrets
import logging
import threading
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from email_parser.database import (
    init_db,
    get_all_items,
    get_item_stats,
    get_audit_report,
    get_data_snapshot,
    save_items,
    delete_item,
)
from email_parser.fetcher import fetch_transaction_emails
from email_parser.parser import parse_email, parse_emails
from email_parser.report import send_daily_report

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

    # Parse and save one email at a time so items appear on the dashboard
    # incrementally instead of waiting for the entire batch to finish.
    import anthropic as _anthropic

    total_saved = 0
    total_parsed = 0
    for i, email_data in enumerate(emails, 1):
        try:
            rows = parse_email(email_data)
            total_parsed += 1
            _inbox_check_status["emails_parsed"] = total_parsed
            if rows:
                count = save_items(rows)
                total_saved += count
                _inbox_check_status["items_saved"] = total_saved
                logger.info("Email %d/%d: saved %d items", i, len(emails), count)
            else:
                logger.info("Email %d/%d: no items extracted", i, len(emails))
        except (_anthropic.BadRequestError, _anthropic.AuthenticationError) as e:
            logger.error(
                "Stopping at email %d/%d — Anthropic API fatal error: %s",
                i, len(emails), e.message,
            )
            raise
        except Exception:
            logger.exception("Failed to parse email %d/%d uid=%s", i, len(emails), email_data.get("uid"))

    _inbox_check_status["message"] = f"Done — saved {total_saved} items from {len(emails)} emails"
    logger.info("Done — saved %d total new items from %d emails", total_saved, len(emails))


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


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def api_delete_item(item_id):
    """Delete an item row by ID."""
    deleted = delete_item(item_id)
    if deleted:
        return jsonify({"status": "ok"})
    return jsonify({"error": "not found"}), 404


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
    return jsonify({
        "configured": email_ok and ai_ok,
        "email": email_ok,
        "ai": ai_ok,
        "connector": connector_ok,
        "daily_report": report_ok,
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
# App startup
# ---------------------------------------------------------------------------
init_db()

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
