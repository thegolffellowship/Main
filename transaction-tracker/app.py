"""
Transaction Email Tracker — Flask application.

Automatically checks your email inbox for transaction/receipt emails,
parses purchase data with AI (Claude), and displays it in a web dashboard.
"""

import os
import logging
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from email_parser.database import (
    init_db,
    get_all_items,
    get_item_stats,
    save_items,
    delete_item,
)
from email_parser.fetcher import fetch_transaction_emails
from email_parser.parser import parse_emails

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

# ---------------------------------------------------------------------------
# Email check job
# ---------------------------------------------------------------------------
def check_inbox():
    """Fetch new transaction emails, parse them with AI, and save to DB."""
    host = os.getenv("EMAIL_HOST")
    port = os.getenv("EMAIL_PORT", "993")
    address = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")

    if not all([host, address, password]):
        logger.warning("Email credentials not configured — skipping inbox check")
        return

    logger.info("Checking inbox for %s ...", address)
    emails = fetch_transaction_emails(
        host=host,
        port=int(port),
        email_address=address,
        password=password,
        since_date=datetime.now() - timedelta(days=90),
    )

    if not emails:
        logger.info("No new transaction emails found")
        return

    rows = parse_emails(emails)
    if rows:
        count = save_items(rows)
        logger.info("Saved %d new item rows", count)


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


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def api_delete_item(item_id):
    """Delete an item row by ID."""
    deleted = delete_item(item_id)
    if deleted:
        return jsonify({"status": "ok"})
    return jsonify({"error": "not found"}), 404


@app.route("/api/check-now", methods=["POST"])
def api_check_now():
    """Manually trigger an inbox check."""
    host = os.getenv("EMAIL_HOST")
    address = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not all([host, address, password]):
        return jsonify({"error": "Email credentials not configured. Create a .env file from .env.example."}), 400

    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured. Add it to your .env file."}), 400

    try:
        check_inbox()
        stats = get_item_stats()
        return jsonify({"status": "ok", "stats": stats})
    except Exception as e:
        logger.exception("Manual inbox check failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/config-status")
def api_config_status():
    """Check whether email and AI credentials are configured."""
    email_ok = all([
        os.getenv("EMAIL_HOST"),
        os.getenv("EMAIL_ADDRESS"),
        os.getenv("EMAIL_PASSWORD"),
    ])
    ai_ok = bool(os.getenv("ANTHROPIC_API_KEY"))
    return jsonify({"configured": email_ok and ai_ok, "email": email_ok, "ai": ai_ok})


# ---------------------------------------------------------------------------
# App startup
# ---------------------------------------------------------------------------
init_db()

if os.getenv("EMAIL_ADDRESS"):
    start_scheduler()
else:
    logger.info("Email not configured — scheduler not started. Set up .env to enable auto-checking.")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
