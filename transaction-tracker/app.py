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
import time
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
    add_payment_to_event,
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
    save_parse_warnings,
    get_parse_warnings,
    dismiss_parse_warning,
    resolve_parse_warning,
    get_all_event_aliases,
    get_known_rsvp_uids,
    save_rsvps,
    get_rsvps_for_event,
    get_all_rsvps,
    get_all_rsvps_bulk,
    get_rsvp_stats,
    rematch_rsvps,
    audit_event_rsvps,
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
    get_all_handicap_players,
    get_handicap_rounds,
    import_handicap_rounds,
    delete_handicap_round,
    delete_all_handicap_rounds_for_player,
    get_handicap_settings,
    update_handicap_settings,
    get_handicap_export_data,
    build_handicap_card_data,
    build_handicap_card_html,
    relink_all_unlinked_players,
    mark_email_processed,
    clear_failed_processed,
    refund_item,
    set_event_status,
    can_restore_event,
    get_cancellation_players,
    get_player_credits,
    get_rsvp_credit_info,
    get_event_rsvp_credit_map,
    mark_rsvp_credit_notified,
    apply_credit_to_rsvp,
    create_rsvp_only_item,
    reverse_credit_application,
    get_app_setting,
    set_app_setting,
    # Accounting module
    get_all_acct_entities,
    create_acct_entity,
    update_acct_entity,
    get_acct_categories,
    create_acct_category,
    update_acct_category,
    delete_acct_category,
    get_acct_accounts,
    create_acct_account,
    update_acct_account,
    get_acct_account_balances,
    get_acct_transactions,
    get_acct_transaction,
    _create_acct_ledger_entry,
    update_acct_transaction,
    delete_acct_transaction,
    reconcile_acct_transaction,
    get_acct_tags,
    create_acct_tag,
    delete_acct_tag,
    get_acct_summary,
    get_acct_monthly_totals,
    get_acct_category_breakdown,
    preview_acct_csv,
    import_acct_csv,
    get_acct_recurring,
    create_acct_recurring,
    delete_acct_recurring,
    auto_categorize_transactions,
    get_acct_review_queue,
    get_acct_categorization_stats,
    reset_acct_data,
    get_acct_account_rules,
    set_acct_account_rule,
    get_all_acct_account_rules,
    calculate_order_allocation,
    get_acct_allocations,
    get_event_financial_summary,
    backfill_financial_entries,
    backfill_acct_transactions,
    migrate_item_to_order_entries,
    backup_database,
    scan_price_games_mismatches,
    save_expense_transaction,
    get_expense_transactions,
    get_unified_transactions,
    update_expense_transaction,
    get_blocked_merchants,
    block_merchant,
    dismiss_bank_deposit,
    record_internal_transfer,
    save_action_item,
    get_action_items,
    update_action_item,
    get_pending_review_count,
    get_coo_financial_snapshot,
    get_coo_review_queue,
    get_all_coo_manual_values,
    set_coo_manual_value,
    get_chart_of_accounts,
    get_ledger_entries,
    import_bank_statement,
    run_bank_reconciliation,
    close_period,
    get_reconciliation_summary,
    # Bank deposit reconciliation (new)
    get_bank_accounts,
    import_bank_deposits,
    import_venmo_statement,
    run_deposit_auto_match,
    manual_match_deposit,
    batch_match_deposit,
    merge_transactions,
    get_match_suggestions,
    unmatch_deposit,
    get_bank_deposits,
    get_unreconciled_transactions,
    get_reconciliation_dashboard,
    get_monthly_reconciliation,
    get_event_reconciliation_status,
    get_cashflow_data,
    get_coo_agents,
    get_agent_action_log,
    batch_dismiss_action_items,
    consolidate_action_items,
    # Keyword rules
    get_acct_keyword_rules,
    create_acct_keyword_rule,
    update_acct_keyword_rule,
    delete_acct_keyword_rule,
    # Batch categorization preview + promotion
    get_expense_batch_preview,
    batch_approve_expenses,
    # Create ledger entry from orphaned bank deposit
    create_entry_from_deposit,
    # Liabilities Dashboard
    get_accounting_liabilities,
    # Month Close
    get_month_close_status,
    # Contractor tracking
    get_contractor_payouts,
    get_contractor_managers,
    add_contractor_payout,
    update_contractor_payout,
    delete_contractor_payout,
    # TGF Payouts
    get_tgf_data,
    add_tgf_event,
    add_tgf_golfer,
    import_tgf_golfers,
    update_tgf_event,
    delete_tgf_event,
    # MVP linking
    get_mvp_unlinked_events,
    set_mvp_unlink,
    # COO Chat persistence
    get_chat_sessions,
    get_chat_session,
    create_chat_session,
    add_chat_message,
    update_chat_session_title,
    update_chat_session_summary,
    get_chat_master_context,
    build_coo_full_context,
    delete_chat_session,
)
from email_parser.database import DB_PATH, get_connection
from email_parser.fetcher import (
    fetch_transaction_emails, fetch_all_emails, fetch_email_by_id,
    send_mail_graph, render_msg_template, send_bulk_emails,
)
from email_parser.parser import parse_email, parse_emails, _strip_html
from email_parser.expense_parser import (
    classify_email, parse_chase_alert, parse_venmo_payment,
    parse_expense_receipt, parse_action_required,
    match_event_from_memo, match_customer_from_name,
    match_event_from_customer,
    get_merchant_context,
)
from email_parser.coo_email import build_coo_email_html
from email_parser.report import send_daily_report
from email_parser.rsvp_parser import fetch_rsvp_emails, parse_rsvp_emails

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Simple in-memory rate limiter for login endpoint
# ---------------------------------------------------------------------------
_login_attempts: dict[str, list[float]] = {}  # IP → list of timestamps
_LOGIN_MAX_ATTEMPTS = 10
_LOGIN_WINDOW_SECONDS = 15 * 60  # 15 minutes


def _check_login_rate_limit() -> bool:
    """Return True if the request IP is within rate limits, False if exceeded."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    ip = ip.split(",")[0].strip()  # first IP in X-Forwarded-For chain
    now = time.time()
    cutoff = now - _LOGIN_WINDOW_SECONDS
    # Clean old entries
    attempts = [t for t in _login_attempts.get(ip, []) if t > cutoff]
    _login_attempts[ip] = attempts
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        return False
    attempts.append(now)
    return True


app = Flask(__name__)
_secret_key = os.getenv("SECRET_KEY")
if not _secret_key:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\" "
        "and add SECRET_KEY=<value> to your .env file or Railway environment variables."
    )
app.secret_key = _secret_key


@app.errorhandler(500)
def handle_500(e):
    """Return JSON instead of HTML for unhandled server errors."""
    logger.exception("Unhandled server error: %s", e)
    return jsonify({"error": "Internal server error"}), 500


@app.route("/health")
def health_check():
    """Health check endpoint for Railway / monitoring. No auth required."""
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return jsonify({"status": "ok", "db": "ok"}), 200
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return jsonify({"status": "error", "db": "error", "detail": str(e)}), 500


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
                # Persist any parse warnings (e.g. item_name is just a course name)
                try:
                    save_parse_warnings(rows)
                except Exception:
                    logger.exception("Failed to save parse warnings (non-fatal)")
            else:
                logger.info("Email %d/%d: no items extracted", i, len(new_emails))
            # Always mark as processed so we don't re-parse next cycle
            mark_email_processed(email_data.get("uid", ""), len(rows))
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


def send_coo_daily_email():
    """Send the daily COO briefing email. Runs compliance checks first."""
    from email_parser.database import run_compliance_checks, log_agent_action
    try:
        checks = run_compliance_checks()
        if checks:
            logger.info("Compliance checks created %d action items: %s", len(checks), checks)
            log_agent_action("Compliance Agent", "daily_compliance_run",
                             f"Created {len(checks)} items: {json.dumps(checks)}",
                             outcome="completed")
    except Exception:
        logger.exception("Compliance checks failed (non-fatal)")

    coo_to = os.getenv("COO_EMAIL_TO")
    if not coo_to:
        logger.info("COO_EMAIL_TO not set — skipping daily email")
        return False

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_address = os.getenv("EMAIL_ADDRESS")

    if not all([tenant_id, client_id, client_secret, from_address]):
        logger.warning("Azure AD / email not configured — skipping COO email")
        return False

    try:
        subject, html_body = build_coo_email_html()
        ok = send_mail_graph(
            tenant_id=tenant_id, client_id=client_id,
            client_secret=client_secret, from_address=from_address,
            to_address=coo_to, subject=subject, html_body=html_body,
        )
        if ok:
            logger.info("COO daily email sent to %s", coo_to)
        else:
            logger.error("COO daily email failed to send to %s", coo_to)
        return ok
    except Exception:
        logger.exception("COO daily email error")
        return False


def check_expense_inbox(force=False, days_back=14):
    """Classify and extract data from non-order emails (Chase alerts, Venmo, receipts).

    Args:
        force: If True, reprocess ALL emails (ignore already-processed check)
        days_back: How many days of emails to fetch (default 14)
    """
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    # Expense emails (Chase/Venmo) go to kerry@, not admin@
    address = os.getenv("EXPENSE_EMAIL_ADDRESS") or os.getenv("RSVP_EMAIL_ADDRESS") or os.getenv("EMAIL_ADDRESS")

    if not all([tenant_id, client_id, client_secret, address]):
        return {"error": "Azure AD credentials not configured"}

    try:
        emails = fetch_all_emails(
            tenant_id=tenant_id, client_id=client_id, client_secret=client_secret,
            email_address=address, since_date=datetime.now() - timedelta(days=days_back),
            max_emails=300,
            include_subfolders=["2025 Chase", "2025 Venmo", "Payouts", "Invoices"],
        )
    except Exception:
        logger.exception("Failed to fetch emails for expense classification")
        return {"error": "Failed to fetch emails"}

    if not emails:
        return {"fetched": 0, "new": 0, "processed": 0}

    # Skip already-processed emails (check both processed_emails and expense_transactions)
    known_uids = get_known_email_uids()
    conn = get_connection()
    try:
        expense_uids = {r["email_uid"] for r in conn.execute(
            "SELECT email_uid FROM expense_transactions WHERE email_uid IS NOT NULL"
        ).fetchall()}
        action_uids = {r["email_uid"] for r in conn.execute(
            "SELECT email_uid FROM action_items WHERE email_uid IS NOT NULL"
        ).fetchall()}
    finally:
        conn.close()

    all_known = known_uids | expense_uids | action_uids
    if force:
        # In force mode, only skip order emails (processed_emails) — reprocess expense/action
        new_emails = [e for e in emails if e.get("uid") not in known_uids]
    else:
        new_emails = [e for e in emails if e.get("uid") not in all_known]

    if not new_emails:
        return {"fetched": len(emails), "new": 0, "processed": 0,
                "note": f"All {len(emails)} fetched emails already processed"}

    logger.info("Classifying %d new emails for expense processing", len(new_emails))
    processed = 0
    conn = get_connection()

    for email_data in new_emails:
        try:
            body_text = _strip_html(email_data.get("html") or email_data.get("text", ""))
            classification = classify_email(
                email_data.get("subject", ""),
                email_data.get("from", ""),
                body_text,
            )
            email_type = classification["type"]
            confidence = classification["confidence"]

            if email_type == "godaddy_order" or email_type == "golf_genius_rsvp":
                continue  # Handled by existing parsers

            if email_type == "unknown":
                continue

            if email_type == "chase_transaction_alert":
                merchant_ctx = None
                extracted = parse_chase_alert(
                    email_data.get("subject", ""),
                    email_data.get("from", ""),
                    body_text, merchant_ctx,
                )
                if extracted.get("confidence", 0) > 0:
                    merchant_name = (extracted.get("merchant") or "").strip()
                    # Auto-ignore Chase Credit Card Statement notifications
                    # (monthly statement alerts, not actual transactions)
                    if merchant_name.upper() in (
                        "CHASE CREDIT CARD STATEMENT",
                        "CREDIT CARD STATEMENT",
                        "CHASE CREDIT CRD AUTOPAY",
                    ):
                        review_status = "ignored"
                        notes = "Auto-ignored: monthly statement notification"
                    else:
                        review_status = "approved" if extracted["confidence"] >= 95 else "pending"
                        notes = None
                    save_expense_transaction({
                        "email_uid": email_data["uid"],
                        "source_type": "chase_alert",
                        "merchant": merchant_name,
                        "amount": extracted.get("amount"),
                        "transaction_date": extracted.get("transaction_date"),
                        "account_last4": extracted.get("account_last4"),
                        "account_name": extracted.get("account_name"),
                        "transaction_type": extracted.get("transaction_type", "expense"),
                        "confidence": extracted["confidence"],
                        "review_status": review_status,
                        "notes": notes,
                        "raw_extract": json.dumps(extracted),
                    })
                    processed += 1

            elif email_type == "venmo_payment":
                extracted = parse_venmo_payment(
                    email_data.get("subject", ""),
                    email_data.get("from", ""),
                    body_text,
                )
                if extracted.get("confidence", 0) > 0:
                    event_name = match_event_from_memo(extracted.get("memo", ""), conn)
                    customer_id = match_customer_from_name(extracted.get("recipient_name", ""), conn)
                    # Fallback: if no event from memo but customer was found, check their registrations
                    if not event_name and customer_id:
                        event_name = match_event_from_customer(customer_id, conn)
                    review_status = "approved" if extracted["confidence"] >= 95 else "pending"
                    venmo_email_date = (email_data.get("date") or "")[:10]
                    save_expense_transaction({
                        "email_uid": email_data["uid"],
                        "source_type": "venmo",
                        "merchant": extracted.get("recipient_name"),
                        "amount": extracted.get("amount"),
                        "transaction_date": extracted.get("transaction_date") or venmo_email_date or None,
                        "transaction_type": extracted.get("transaction_type", "payout"),
                        "event_name": event_name,
                        "customer_id": customer_id,
                        "confidence": extracted["confidence"],
                        "review_status": review_status,
                        "notes": extracted.get("memo"),
                        "raw_extract": json.dumps(extracted),
                    })
                    processed += 1

            elif email_type == "expense_receipt":
                raw_email_date = (email_data.get("date") or "")[:10]
                extracted = parse_expense_receipt(
                    email_data.get("subject", ""),
                    email_data.get("from", ""),
                    body_text,
                    email_date=raw_email_date or None,
                )
                if extracted.get("confidence", 0) > 0:
                    review_status = "approved" if extracted["confidence"] >= 95 else "pending"
                    save_expense_transaction({
                        "email_uid": email_data["uid"],
                        "source_type": "receipt",
                        "merchant": extracted.get("merchant"),
                        "amount": extracted.get("amount"),
                        "transaction_date": extracted.get("transaction_date") or raw_email_date or None,
                        "account_last4": extracted.get("account_last4"),
                        "category": extracted.get("category"),
                        "entity": extracted.get("entity", "TGF"),
                        "confidence": extracted["confidence"],
                        "review_status": review_status,
                        "notes": extracted.get("description"),
                        "raw_extract": json.dumps(extracted),
                    })
                    processed += 1

            elif email_type == "action_required":
                extracted = parse_action_required(
                    email_data.get("subject", ""),
                    email_data.get("from", ""),
                    body_text,
                )
                if extracted.get("confidence", 0) > 0:
                    save_action_item({
                        "email_uid": email_data["uid"],
                        "subject": extracted.get("subject", email_data.get("subject")),
                        "from_name": extracted.get("from_name"),
                        "from_email": extracted.get("from_email", email_data.get("from")),
                        "summary": extracted.get("summary"),
                        "urgency": extracted.get("urgency", "medium"),
                        "category": extracted.get("category", "other"),
                        "email_date": (email_data.get("date") or "")[:10],
                        "confidence": extracted["confidence"],
                    })
                    processed += 1

        except Exception:
            logger.exception("Error processing email uid=%s for expense classification",
                             email_data.get("uid"))

    conn.close()
    if processed:
        logger.info("Expense email processing: %d items saved from %d emails", processed, len(new_emails))
    return {"fetched": len(emails), "new": len(new_emails), "processed": processed}


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

    # Check for credited players who just RSVPd and send admin alert emails
    _send_rsvp_credit_alerts()


def _send_rsvp_credit_alerts():
    """Find newly matched RSVPs for credited players and send admin alert emails."""
    from email_parser.database import _connect as _db_connect
    from email_parser.fetcher import send_mail_graph

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_address = os.getenv("EMAIL_ADDRESS")
    # All credit alerts go here during testing — remove override to go live
    alert_to = os.getenv("CREDIT_ALERT_EMAIL_OVERRIDE", "kerry@thegolffellowship.com")

    if not all([tenant_id, client_id, client_secret, from_address]):
        logger.warning("Email credentials not configured — skipping credit alerts")
        return

    # Find RSVPs that: (a) are matched to an event, (b) haven't been notified yet
    with _db_connect() as conn:
        pending = conn.execute(
            """SELECT id FROM rsvps
               WHERE matched_event IS NOT NULL
                 AND response = 'PLAYING'
                 AND credit_notified_at IS NULL""",
        ).fetchall()

    for row in pending:
        rsvp_id = row["id"]
        try:
            info = get_rsvp_credit_info(rsvp_id)
            if not info:
                # No credits — stamp it anyway so we skip next time
                mark_rsvp_credit_notified(rsvp_id)
                continue

            # Build email
            player = info["player_name"]
            event_name = info["event_name"]
            event_date = info["event_date"]
            course = info["course"]
            total_credit = info["total_credit"]
            new_price = info["new_event_price"]
            amount_owed = info["amount_owed"]
            can_calc = info["can_calculate"]
            sel = info["selections"]

            credit_lines = "".join(
                f"<li>${c['credit_amount']:.2f} from <em>{c['event_name']}</em></li>"
                for c in info["credits"]
            )

            if can_calc:
                scenario = (
                    f"<strong style='color:#dc2626;'>Balance due: ${amount_owed:.2f}</strong>"
                    if amount_owed > 0
                    else f"<strong style='color:#16a34a;'>Excess credit: ${abs(amount_owed):.2f}</strong>"
                    if amount_owed < 0
                    else "<strong style='color:#6b7280;'>Credit covers exactly</strong>"
                )
                price_table = f"""
                <table style="border-collapse:collapse; margin:0.75rem 0; font-size:0.9rem;">
                  <tr><td style="padding:3px 12px 3px 0; color:#6b7280;">New event cost</td>
                      <td style="padding:3px 0;"><strong>${new_price:.2f}</strong></td></tr>
                  <tr><td style="padding:3px 12px 3px 0; color:#6b7280;">Credit applied</td>
                      <td style="padding:3px 0;">−${total_credit:.2f}</td></tr>
                  <tr style="border-top:1px solid #e5e7eb;">
                      <td style="padding:6px 12px 3px 0;">Result</td>
                      <td style="padding:6px 0;">{scenario}</td></tr>
                </table>"""
                action_note = (
                    f"<p><strong>Action:</strong> Player owes ${amount_owed:.2f} — "
                    f"apply credit in the admin UI and request Venmo payment of "
                    f"<strong>${amount_owed:.2f} to @tgf-payments</strong>.</p>"
                    if amount_owed > 0
                    else f"<p><strong>Action:</strong> Credit more than covers this event. "
                    f"Apply credit in admin UI. Excess ${abs(amount_owed):.2f} stays on account.</p>"
                    if amount_owed < 0
                    else "<p><strong>Action:</strong> Credit covers exactly — apply in admin UI.</p>"
                )
            else:
                price_table = "<p style='color:#d97706;'>⚠ Event pricing not configured — calculate manually.</p>"
                action_note = "<p>Apply credit manually via the Events admin page.</p>"

            subject = (
                f"[CREDIT ALERT] {player} RSVPd for {event_name}"
                + (" — owes ${:.2f}".format(amount_owed) if (can_calc and amount_owed > 0) else
                   " — credit covers it" if can_calc else " — pricing unknown")
            )

            html_body = f"""
<p>Hi Kerry,</p>
<p>A credited player has RSVPd for an upcoming event.</p>
<table style="border-collapse:collapse; background:#f9fafb; border:1px solid #e5e7eb;
              border-radius:6px; padding:0.75rem; margin:0.75rem 0; font-size:0.9rem; width:100%;">
  <tr><td style="padding:3px 12px 3px 0; color:#6b7280; width:130px;">Player</td>
      <td><strong>{player}</strong></td></tr>
  <tr><td style="padding:3px 12px 3px 0; color:#6b7280;">Event</td>
      <td><strong>{event_name}</strong></td></tr>
  <tr><td style="padding:3px 12px 3px 0; color:#6b7280;">Date / Course</td>
      <td>{event_date} &bull; {course}</td></tr>
  <tr><td style="padding:3px 12px 3px 0; color:#6b7280;">Previous selections</td>
      <td>{sel['holes']}h &bull; {sel['side_games']} &bull; {sel['user_status']}</td></tr>
</table>
<p><strong>Credits on account:</strong></p>
<ul>{credit_lines}</ul>
<p><strong>Total credit: ${total_credit:.2f}</strong></p>
{price_table}
{action_note}
<p style="font-size:0.8rem; color:#9ca3af;">
  This alert was sent to kerry@thegolffellowship.com instead of the player for testing.
  Remove CREDIT_ALERT_EMAIL_OVERRIDE env var to route to players.
</p>
<p>— TGF System</p>"""

            ok = send_mail_graph(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                from_address=from_address,
                to_address=alert_to,
                subject=subject,
                html_body=html_body,
            )
            if ok:
                logger.info("Credit alert sent for RSVP %s (%s)", rsvp_id, player)
                from email_parser.database import log_message
                log_message({
                    "event_name": event_name,
                    "channel": "email",
                    "recipient_name": player,
                    "recipient_address": alert_to,
                    "subject": subject,
                    "body_preview": f"Credit alert: {player} RSVPd for {event_name}. Credit: ${total_credit:.2f}",
                    "status": "sent",
                    "sent_by": "system",
                })
            else:
                logger.warning("Credit alert email failed for RSVP %s", rsvp_id)

            mark_rsvp_credit_notified(rsvp_id)
        except Exception:
            logger.warning("Credit alert check failed for RSVP %s", rsvp_id, exc_info=True)
            mark_rsvp_credit_notified(rsvp_id)  # stamp it to avoid retry loops


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

    # Expense email classifier — runs on same interval as inbox check
    scheduler.add_job(
        check_expense_inbox,
        "interval",
        minutes=interval,
        id="expense_inbox_check",
        replace_existing=True,
    )
    logger.info("Expense email classifier scheduled every %d minutes", interval)

    # COO daily email — runs at 7:00 AM US/Central
    coo_email_to = os.getenv("COO_EMAIL_TO")
    if coo_email_to:
        scheduler.add_job(
            send_coo_daily_email,
            "cron",
            hour=7,
            minute=0,
            timezone="US/Central",
            id="coo_daily_email",
            replace_existing=True,
        )
        logger.info("COO daily email scheduled for 07:00 US/Central → %s", coo_email_to)

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

    # Golf Genius handicap sync — daily at configurable hour (default 2 AM Central)
    gg_sync_hour = int(os.getenv("GOLF_GENIUS_SYNC_HOUR", "2"))
    gg_sync_tz = os.getenv("DAILY_REPORT_TZ", "US/Central")
    if os.getenv("GOLF_GENIUS_EMAIL") and os.getenv("GOLF_GENIUS_PASSWORD"):
        from golf_genius_sync import run_scheduled_sync
        scheduler.add_job(
            run_scheduled_sync,
            "cron",
            hour=gg_sync_hour,
            minute=0,
            timezone=gg_sync_tz,
            id="gg_handicap_sync",
            replace_existing=True,
        )
        logger.info(
            "Golf Genius handicap sync scheduled daily at %02d:00 %s",
            gg_sync_hour, gg_sync_tz,
        )
    else:
        logger.info("Golf Genius sync not scheduled — GOLF_GENIUS_EMAIL/PASSWORD not set")

    # Weekly cleanup: prune old processed_emails records (>90 days)
    scheduler.add_job(
        prune_processed_emails,
        "cron",
        day_of_week="sun",
        hour=3,
        minute=0,
        timezone="US/Central",
        id="prune_processed_emails",
        replace_existing=True,
    )
    logger.info("Processed emails pruning scheduled Sundays at 03:00 US/Central")

    # Run one-time startup prune
    try:
        pruned = prune_processed_emails()
        logger.info("Startup prune: deleted %d processed_emails older than 90 days", pruned)
    except Exception:
        logger.exception("Startup prune failed (non-fatal)")

    scheduler.start()
    logger.info("Scheduler started — checking inbox every %d minutes", interval)


def prune_processed_emails(days=90):
    """Delete processed_emails records older than N days.

    These records only exist to prevent re-parsing the same email. After 90 days
    the email is long gone from the inbox anyway, so the record is dead weight.
    Returns the number of rows deleted.
    """
    from email_parser.database import _connect
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM processed_emails WHERE processed_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        conn.commit()
        deleted = cursor.rowcount
    if deleted:
        logger.info("Pruned %d processed_emails older than %d days", deleted, days)
    return deleted


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


@app.route("/api/migrate-customers-preview")
@require_role("admin")
def api_migrate_customers_preview():
    """Dry-run preview of customer migration — read-only, no inserts."""
    from migrate_customers import dry_run_json
    from email_parser.database import get_connection
    conn = get_connection()
    try:
        return jsonify(dry_run_json(conn))
    finally:
        conn.close()


@app.route("/api/migrate-customers", methods=["POST"])
@require_role("admin")
def api_migrate_customers():
    """Run the customer migration (idempotent)."""
    from migrate_customers import migrate
    from email_parser.database import get_connection
    conn = get_connection()
    try:
        stats = migrate(conn)
        return jsonify(stats)
    finally:
        conn.close()


@app.route("/api/data-snapshot")
def api_data_snapshot():
    """Quick snapshot of recent items + stats for inspection."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify(get_data_snapshot(limit=limit))


@app.route("/api/items/<int:item_id>", methods=["PATCH"])
@require_role("admin")
def api_update_item(item_id):
    """Update specific fields on an item row (for inline editing). Admin only."""
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


@app.route("/api/items/<int:item_id>/assign-guest", methods=["POST"])
@require_role("manager")
def api_assign_guest(item_id):
    """Assign the actual guest player name to a GUEST registration.

    When a member buys a guest registration, both items initially show the
    buyer as the customer. This endpoint swaps the customer to the actual
    guest and records the buyer in a 'Purchased by' note.
    """
    data = request.get_json(silent=True)
    guest_name = (data.get("guest_name") or "").strip() if data else ""
    if not guest_name:
        return jsonify({"error": "guest_name is required."}), 400
    err = validate_json_fields(data)
    if err:
        return jsonify({"error": err}), 400

    conn = get_connection()
    try:
        item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            return jsonify({"error": "Item not found."}), 404
        item = dict(item)
        buyer = item["customer"] or ""

        from email_parser.parser import _normalize_customer_name
        normalized = _normalize_customer_name(guest_name)

        changes = {
            "customer": normalized,
            "guest_name": normalized,
            "notes": f"Purchased by {buyer}",
            "customer_email": None,
            "customer_phone": None,
            "customer_id": None,
        }
        update_item(item_id, changes)

        return jsonify({"status": "ok", "customer": normalized, "buyer": buyer})
    finally:
        conn.close()


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
@require_role("admin")
def api_delete_item(item_id):
    """Delete an item row by ID. Admin only."""
    deleted = delete_item(item_id)
    if deleted:
        return jsonify({"status": "ok"})
    return jsonify({"error": "not found"}), 404


@app.route("/api/events/delete-manual-player/<int:item_id>", methods=["DELETE"])
@require_role("manager")
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
        logger.debug("WAL checkpoint on backup copy failed (non-fatal)", exc_info=True)
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
                for f in ["customer", "order_id", "item_name", "item_price"]:
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
    matrix9, matrix18 = _load_matrix()
    return render_template("matrix.html", matrix9=matrix9, matrix18=matrix18)


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


@app.route("/database")
def database_page():
    if session.get("role") != "admin":
        return render_template("index.html")
    return render_template("database.html")


@app.route("/api/database/tables")
@require_role("admin")
def api_database_tables():
    """List all user tables and their row counts."""
    conn = get_connection()
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        result = []
        for t in tables:
            name = t["name"]
            count = conn.execute(f'SELECT COUNT(*) AS c FROM "{name}"').fetchone()["c"]
            result.append({"name": name, "row_count": count})
        return jsonify(result)
    finally:
        conn.close()


@app.route("/api/database/table/<table_name>")
@require_role("admin")
def api_database_table(table_name):
    """Return rows from a specific table with pagination."""
    conn = get_connection()
    try:
        # Validate table name exists (prevent SQL injection)
        valid = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        if not valid:
            return jsonify({"error": "Table not found"}), 404

        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        search = request.args.get("search", "").strip()
        sort_col = request.args.get("sort", "").strip()
        sort_dir = request.args.get("dir", "asc").strip().lower()

        # Get column names
        cols_info = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        columns = [c["name"] for c in cols_info]

        # Build query
        where_clause = ""
        params: list = []
        if search:
            # Search across all text columns
            conditions = [f'CAST("{col}" AS TEXT) LIKE ?' for col in columns]
            where_clause = "WHERE " + " OR ".join(conditions)
            params = [f"%{search}%"] * len(columns)

        # Total count (with search filter)
        total = conn.execute(
            f'SELECT COUNT(*) AS c FROM "{table_name}" {where_clause}', params
        ).fetchone()["c"]

        # Sort
        order_clause = ""
        if sort_col and sort_col in columns:
            direction = "DESC" if sort_dir == "desc" else "ASC"
            order_clause = f'ORDER BY "{sort_col}" {direction}'
        else:
            order_clause = "ORDER BY rowid DESC"

        rows = conn.execute(
            f'SELECT * FROM "{table_name}" {where_clause} {order_clause} LIMIT ? OFFSET ?',
            params + [limit, offset],
        ).fetchall()

        return jsonify({
            "table": table_name,
            "columns": columns,
            "rows": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        })
    finally:
        conn.close()


def _load_matrix_from_file() -> tuple[dict, dict]:
    """Parse the static games-matrix.js file and return (matrix9, matrix18)."""
    matrix_path = os.path.join(
        os.path.dirname(__file__), "static", "js", "games-matrix.js"
    )
    with open(matrix_path, "r") as f:
        content = f.read()
    m9 = re.search(r"window\.GAMES_MATRIX_9\s*=\s*(\{.*?\});", content, re.DOTALL)
    m18 = re.search(r"window\.GAMES_MATRIX_18\s*=\s*(\{.*?\});", content, re.DOTALL)
    return json.loads(m9.group(1)), json.loads(m18.group(1))


def _load_matrix() -> tuple[dict, dict]:
    """Load matrices from DB if saved, otherwise from the static JS file."""
    db9 = get_app_setting("games_matrix_9")
    db18 = get_app_setting("games_matrix_18")
    if db9 and db18:
        return json.loads(db9), json.loads(db18)
    return _load_matrix_from_file()


@app.route("/api/matrix", methods=["GET"])
def api_matrix_get():
    """Return the current games matrix (from DB if edited, else from static file)."""
    matrix9, matrix18 = _load_matrix()
    return jsonify({"matrix9": matrix9, "matrix18": matrix18})


@app.route("/api/matrix", methods=["PUT"])
@require_role("admin")
def api_matrix_save():
    """Save edits to the side-games matrix (persisted in DB)."""
    try:
        data = request.get_json(force=True)
        changes = data.get("changes", {})
        if not changes:
            return jsonify({"error": "No changes provided"}), 400

        matrix9, matrix18 = _load_matrix()

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

        # Recalculate skins values for any entry where skinsTotal or skinsFlights changed
        for change_key in changes:
            parts = change_key.split(":", 2)
            if len(parts) != 3:
                continue
            holes, pc, field_key = parts
            if field_key in ("skinsTotal", "skinsFlights"):
                m = matrix9 if holes == "9" else matrix18
                entry = m.get(pc)
                if entry:
                    st = entry.get("skinsTotal") or 0
                    sf = entry.get("skinsFlights") or 0
                    if st and sf:
                        if "skins" not in entry:
                            entry["skins"] = [None] * 9
                        while len(entry["skins"]) < 9:
                            entry["skins"].append(None)
                        for i in range(9):
                            entry["skins"][i] = round(st / sf / (i + 1), 2)

        # Persist to database (survives Railway redeploys)
        set_app_setting("games_matrix_9", json.dumps(matrix9))
        set_app_setting("games_matrix_18", json.dumps(matrix18))

        # Also update the static file as a cache (best-effort, may be read-only)
        try:
            matrix_path = os.path.join(
                os.path.dirname(__file__), "static", "js", "games-matrix.js"
            )
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
        except Exception:
            logger.debug("Could not update static matrix file (non-fatal)")

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
    and updates backfill fields (partner_request, fellowship, notes, holes,
    address, transaction_fees) on existing items. Also overwrites item_name
    if the AI returns an improved value.
    """
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    email_address = os.getenv("EMAIL_ADDRESS")

    if not all([tenant_id, client_id, client_secret, email_address]):
        return jsonify({"error": "Azure AD credentials not configured"}), 400

    BACKFILL_FIELDS = ["partner_request", "fellowship", "notes", "holes",
                       "address", "address2", "city", "state", "zip",
                       "transaction_fees", "coupon_code", "coupon_amount",
                       "guest_name"]
    # Fields where re-extract should overwrite existing (possibly wrong) values
    OVERWRITE_FIELDS = {"item_name"}

    items = get_all_items()
    # Find items missing any backfill fields; since transaction_fees is new,
    # this will pick up virtually all existing items, and the OVERWRITE_FIELDS
    # logic below will also correct item_name where the AI now returns better data.
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
                # Overwrite fields — update even if existing value is present
                for field in OVERWRITE_FIELDS:
                    new_val = parsed.get(field)
                    if new_val and new_val != it.get(field):
                        changes[field] = new_val

                # Guest-swap: if parser promoted the guest to customer,
                # overwrite customer + guest_name on the existing item
                parsed_customer = (parsed.get("customer") or "").strip()
                current_customer = (it.get("customer") or "").strip()
                parsed_notes = parsed.get("notes") or ""
                if (parsed_customer and parsed_customer.lower() != current_customer.lower()
                        and "Purchased by" in parsed_notes):
                    changes["customer"] = parsed_customer
                    changes["guest_name"] = parsed.get("guest_name") or parsed_customer
                    changes["notes"] = parsed_notes
                    changes["customer_email"] = None
                    changes["customer_phone"] = None
                    changes["customer_id"] = None

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


@app.route("/api/audit/reextract-order", methods=["POST"])
@require_role("admin")
def api_reextract_order():
    """Re-parse a single order's email to backfill coupon (or any missing) fields.

    Accepts JSON body: {"order_id": "R854482675"}
    Re-fetches the original email, re-runs AI extraction, and updates
    coupon_code and coupon_amount (plus other backfill fields) on all rows
    sharing that order_id.
    """
    data = request.get_json(force=True) or {}
    order_id = data.get("order_id", "").strip()
    if not order_id:
        return jsonify({"error": "order_id is required"}), 400

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    email_address = os.getenv("EMAIL_ADDRESS")
    if not all([tenant_id, client_id, client_secret, email_address]):
        return jsonify({"error": "Azure AD credentials not configured"}), 400

    BACKFILL_FIELDS = ["coupon_code", "coupon_amount", "transaction_fees",
                       "partner_request", "fellowship", "notes", "holes",
                       "address", "address2", "city", "state", "zip"]
    # Fields where re-extract should overwrite even if existing value differs
    FORCE_UPDATE_FIELDS = ["side_games", "holes", "item_price"]

    items = get_all_items()
    order_items = [it for it in items if it.get("order_id") == order_id]
    if not order_items:
        return jsonify({"error": f"No items found for order_id={order_id}"}), 404

    # All rows in an order share the same email_uid
    uid = order_items[0].get("email_uid", "")
    if not uid or uid.startswith("manual-"):
        return jsonify({"error": "Order has no parseable email (manual entry)"}), 400

    try:
        email_data = fetch_email_by_id(
            tenant_id, client_id, client_secret, email_address, uid
        )
        if not email_data:
            return jsonify({"error": f"Could not fetch email {uid} from Graph API"}), 404

        parsed_rows = parse_email(email_data)
        if not parsed_rows:
            return jsonify({"error": "AI extraction returned no results"}), 500

        updated = 0
        changes_detail = []
        for it in order_items:
            # Skip manual entries (Add Payment, comp, etc.)
            uid = it.get("email_uid") or ""
            if uid.startswith("manual-"):
                continue

            idx = it.get("item_index", 0) or 0
            if idx < len(parsed_rows):
                parsed = parsed_rows[idx]
            else:
                # Fallback: match by item_name (case-insensitive)
                parsed = next(
                    (p for p in parsed_rows
                     if (p.get("item_name") or "").lower() == (it.get("item_name") or "").lower()),
                    parsed_rows[0] if len(parsed_rows) == 1 else None,
                )
            if not parsed:
                continue

            changes = {}
            for field in BACKFILL_FIELDS:
                new_val = parsed.get(field)
                if new_val and not it.get(field):
                    changes[field] = new_val

            # Force-update fields: overwrite if parsed value differs
            for field in FORCE_UPDATE_FIELDS:
                new_val = parsed.get(field)
                if new_val and str(new_val).strip().upper() != str(it.get(field) or "").strip().upper():
                    changes[field] = new_val

            # Guest-swap: if parser promoted the guest to customer,
            # overwrite customer on the existing item (not guest_name — that
            # field belongs to whoever the player requested as a partner)
            parsed_customer = (parsed.get("customer") or "").strip()
            current_customer = (it.get("customer") or "").strip()
            parsed_notes = parsed.get("notes") or ""
            if (parsed_customer and parsed_customer.lower() != current_customer.lower()
                    and "Purchased by" in parsed_notes):
                changes["customer"] = parsed_customer
                changes["notes"] = parsed_notes
                changes["customer_email"] = None
                changes["customer_phone"] = None
                changes["customer_id"] = None

            if changes:
                update_item(it["id"], changes)
                updated += 1
                changes_detail.append({"id": it["id"], "fields": list(changes.keys())})

        return jsonify({
            "status": "ok",
            "order_id": order_id,
            "items_in_order": len(order_items),
            "items_updated": updated,
            "changes": changes_detail,
            "parsed_count": len(parsed_rows),
        })

    except Exception as exc:
        logger.exception("reextract-order failed for %s", order_id)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/audit/retry-failed", methods=["POST"])
@require_role("admin")
def api_retry_failed():
    """Re-process emails that previously parsed 0 items.

    Clears 0-item entries from processed_emails, then re-runs check_inbox
    which will pick them up as 'new' emails and re-parse them.
    """
    cleared = clear_failed_processed()
    if cleared == 0:
        return jsonify({"status": "ok", "cleared": 0, "message": "No failed emails to retry"})

    # Now re-run inbox check to pick up the cleared emails
    try:
        check_inbox()
    except Exception:
        logger.exception("Retry failed: inbox check error")
        return jsonify({"status": "partial", "cleared": cleared,
                        "message": f"Cleared {cleared} entries but inbox check failed"}), 500

    return jsonify({
        "status": "ok",
        "cleared": cleared,
        "message": f"Cleared {cleared} failed entries and re-processed inbox",
    })


@app.route("/api/audit/expand-quantities", methods=["POST"])
@require_role("admin")
def api_expand_quantities():
    """Find items with quantity > 1 and create missing partner rows.

    For each item with qty > 1, checks if partner rows already exist
    (same email_uid, consecutive item_index). If not, creates them using
    the partner_request name or 'Guest of <buyer>'.

    This is a one-time backfill for orders placed before quantity expansion
    was added to the parser.
    """
    from email_parser.parser import _normalize_customer_name

    conn = get_connection()
    try:
        # Find items with quantity > 1
        qty_items = conn.execute(
            "SELECT * FROM items WHERE quantity > 1 ORDER BY id"
        ).fetchall()

        created = 0
        skipped = 0
        details = []

        for item in qty_items:
            item = dict(item)
            qty = item["quantity"]
            email_uid = item["email_uid"]
            base_index = item["item_index"]
            buyer = item["customer"] or "Unknown"

            # Check how many rows already exist for this email_uid
            existing = conn.execute(
                "SELECT item_index FROM items WHERE email_uid = ? ORDER BY item_index",
                (email_uid,),
            ).fetchall()
            existing_indices = {r["item_index"] for r in existing}

            # Find the next available item_index
            max_idx = max(existing_indices) if existing_indices else -1

            partner_name = (item.get("partner_request") or "").strip()

            for extra_i in range(1, qty):
                new_idx = max_idx + extra_i
                if new_idx in existing_indices:
                    skipped += 1
                    continue

                # Build the partner row from the original
                partner_row = dict(item)
                partner_row["item_index"] = new_idx
                partner_row["quantity"] = 1
                partner_row["customer_email"] = None
                partner_row["customer_phone"] = None
                partner_row["address"] = None
                partner_row["address2"] = None
                partner_row["city"] = None
                partner_row["state"] = None
                partner_row["zip"] = None
                # Remove DB-generated fields
                partner_row.pop("id", None)
                partner_row.pop("created_at", None)

                if extra_i == 1 and partner_name:
                    partner_row["customer"] = _normalize_customer_name(partner_name)
                    partner_row["partner_request"] = None
                    partner_row["notes"] = f"Purchased by {buyer}"
                else:
                    partner_row["customer"] = f"Guest of {buyer}"
                    partner_row["notes"] = f"Purchased by {buyer}"

                # Insert the partner row
                cols = [c for c in partner_row.keys() if c not in ("id", "created_at")]
                placeholders = ", ".join("?" for _ in cols)
                col_names = ", ".join(cols)
                values = tuple(partner_row.get(c) for c in cols)

                try:
                    conn.execute(
                        f"INSERT OR IGNORE INTO items ({col_names}) VALUES ({placeholders})",
                        values,
                    )
                    created += 1
                    details.append(f"{buyer} → {partner_row['customer']} ({item['item_name']})")
                except Exception as e:
                    logger.warning("Failed to create partner row: %s", e)
                    skipped += 1

            # Update original row quantity to 1
            conn.execute(
                "UPDATE items SET quantity = 1 WHERE id = ?", (item["id"],)
            )

        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "status": "ok",
        "found_qty_items": len(qty_items),
        "created": created,
        "skipped": skipped,
        "details": details,
    })


@app.route("/api/audit/fix-guest-customers", methods=["POST"])
@require_role("admin")
def api_fix_guest_customers():
    """Fix GUEST items where the customer is still the buyer instead of the guest.

    Finds items with user_status containing 'GUEST' and a non-empty guest_name
    that differs from the current customer. Swaps the customer to the guest_name
    and adds a 'Purchased by <buyer>' note.
    """
    from email_parser.parser import _normalize_customer_name

    conn = get_connection()
    try:
        guests = conn.execute(
            """SELECT id, customer, guest_name, notes
               FROM items
               WHERE user_status LIKE '%GUEST%'
                 AND guest_name IS NOT NULL AND guest_name != ''
                 AND COALESCE(transaction_status, 'active') = 'active'"""
        ).fetchall()

        fixed = 0
        details = []

        for row in guests:
            row = dict(row)
            guest = _normalize_customer_name(row["guest_name"])
            buyer = (row["customer"] or "").strip()
            if not guest or guest.lower() == buyer.lower():
                continue

            conn.execute(
                """UPDATE items
                   SET customer = ?, notes = ?,
                       customer_email = NULL, customer_phone = NULL,
                       address = NULL, address2 = NULL,
                       city = NULL, state = NULL, zip = NULL,
                       customer_id = NULL
                   WHERE id = ?""",
                (guest, f"Purchased by {buyer}", row["id"]),
            )
            fixed += 1
            details.append(f"{buyer} → {guest} (id={row['id']})")

        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "status": "ok",
        "fixed": fixed,
        "details": details,
    })


# ---------------------------------------------------------------------------
# Routes — Events
# ---------------------------------------------------------------------------
@app.route("/events")
def events_page():
    matrix9, matrix18 = _load_matrix()
    return render_template("events.html", matrix9=matrix9, matrix18=matrix18)


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
               "first_name", "last_name", "middle_name", "suffix",
               "archived", "venmo_username"}
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return jsonify({"error": "No valid fields to update"}), 400

    try:
        updated = update_customer_info(customer_name, safe)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "ok", "items_updated": updated})


@app.route("/api/customers/venmo-handles")
@require_role("view-only")
def api_customer_venmo_handles():
    """Return all customers with Venmo handles set."""
    from email_parser.database import get_customer_venmo_handles
    return jsonify(get_customer_venmo_handles())


@app.route("/api/customer-roles")
@require_role("view-only")
def api_customer_roles():
    """Return a map of customer_id → {roles: [...], first_timer_ever: bool}.

    Used by frontend pages (Customers, Events, Transactions) to display
    role badges and flag STATUS mismatches between self-selected
    items.user_status and authoritative customer_roles.
    """
    from email_parser.database import _connect
    result = {}
    with _connect() as conn:
        # Build role lists per customer
        role_rows = conn.execute(
            "SELECT customer_id, role_type FROM customer_roles ORDER BY customer_id, role_type"
        ).fetchall()
        for r in role_rows:
            cid = str(r["customer_id"])
            if cid not in result:
                result[cid] = {"roles": [], "first_timer_ever": True}
            result[cid]["roles"].append(r["role_type"])

        # Add first_timer_ever for every customer (even those without roles)
        customer_rows = conn.execute(
            "SELECT customer_id, first_timer_ever FROM customers"
        ).fetchall()
        for c in customer_rows:
            cid = str(c["customer_id"])
            if cid not in result:
                result[cid] = {"roles": [], "first_timer_ever": bool(c["first_timer_ever"])}
            else:
                result[cid]["first_timer_ever"] = bool(c["first_timer_ever"])

    return jsonify(result)


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


@app.route("/api/customers/winnings")
@require_role("view-only")
def api_customer_winnings():
    """Get payout/winnings history for a customer."""
    from email_parser.database import get_customer_winnings
    name = request.args.get("customer_name", "").strip()
    if not name:
        return jsonify({"error": "customer_name required"}), 400
    return jsonify(get_customer_winnings(name))


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


@app.route("/api/chapters")
def api_chapters():
    """Return all chapters with their IDs."""
    from email_parser.database import _connect
    with _connect() as conn:
        rows = conn.execute(
            "SELECT chapter_id, name, short_code, timezone, status FROM chapters ORDER BY name"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/courses")
def api_courses():
    """Return all courses with chapter linkage and aliases."""
    from email_parser.database import _connect
    with _connect() as conn:
        rows = conn.execute(
            """SELECT c.course_id, c.name, c.chapter_id, c.city, c.state, c.status,
                      ch.name as chapter_name
               FROM courses c
               LEFT JOIN chapters ch ON ch.chapter_id = c.chapter_id
               ORDER BY c.name"""
        ).fetchall()
        courses = [dict(r) for r in rows]

        # Attach aliases
        alias_map: dict[int, list[str]] = {}
        for a in conn.execute("SELECT course_id, alias_name FROM course_aliases").fetchall():
            alias_map.setdefault(a["course_id"], []).append(a["alias_name"])
        for c in courses:
            c["aliases"] = alias_map.get(c["course_id"], [])

    return jsonify(courses)


@app.route("/api/courses", methods=["POST"])
@require_role("manager")
def api_create_course():
    """Create a new course. Body: {name, chapter_id?, city?, state?}."""
    from email_parser.database import _connect
    d = request.json or {}
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Course name required"}), 400
    with _connect() as conn:
        existing = conn.execute(
            "SELECT course_id FROM courses WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if existing:
            return jsonify({"error": f"Course '{name}' already exists", "course_id": existing["course_id"]}), 409
        cur = conn.execute(
            """INSERT INTO courses (name, chapter_id, city, state)
               VALUES (?, ?, ?, ?)""",
            (name, d.get("chapter_id"), d.get("city"), d.get("state")),
        )
        conn.commit()
        return jsonify({"course_id": cur.lastrowid, "name": name})


@app.route("/api/events")
def api_events():
    """Return all events with registration counts and aliases."""
    return jsonify(get_all_events())


@app.route("/api/events/aliases")
def api_event_aliases():
    """Return alias_name → canonical_event_name map."""
    return jsonify(get_all_event_aliases())


@app.route("/api/events/sync", methods=["POST"])
@require_role("manager")
def api_sync_events():
    """Scan items and auto-create event entries for event-type items."""
    try:
        result = sync_events_from_items()
        return jsonify({"status": "ok", **result})
    except Exception as e:
        logger.exception("Event sync failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/events/<int:event_id>", methods=["PATCH"])
@require_role("manager")
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


@app.route("/api/events/<int:event_id>/cancel", methods=["POST"])
@require_role("admin")
def api_cancel_event(event_id):
    """Cancel or postpone an event, silently removing comps and RSVP-only players."""
    data = request.get_json(silent=True) or {}
    status = data.get("status", "cancelled")
    reason = data.get("reason", "").strip()
    if status not in ("cancelled", "postponed"):
        return jsonify({"error": "status must be 'cancelled' or 'postponed'"}), 400
    if not reason:
        return jsonify({"error": "reason is required"}), 400

    # Set the event status
    if not set_event_status(event_id, status, reason):
        return jsonify({"error": "Event not found"}), 404

    # Silently credit comps and RSVP-only players
    players = get_cancellation_players(event_id)
    silent_note = f"Event {status} — {reason}"
    silent_count = 0
    for item in players.get("silent", []):
        try:
            credit_item(item["id"], note=silent_note)
            silent_count += 1
        except Exception:
            pass

    return jsonify({
        "status": "ok",
        "silent_removed": silent_count,
        "paid_players": len(players.get("paid", [])),
    })


@app.route("/api/events/<int:event_id>/restore", methods=["POST"])
@require_role("admin")
def api_restore_event(event_id):
    """Restore a cancelled/postponed event to active. Only allowed if no player actions taken."""
    if not can_restore_event(event_id):
        return jsonify({"error": "Cannot restore: player actions have already been applied."}), 400
    if set_event_status(event_id, "active", ""):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Event not found"}), 404


@app.route("/api/events/<int:event_id>/cancellation-players", methods=["GET"])
@require_role("admin")
def api_get_cancellation_players(event_id):
    """Return paid players who need a credit/refund action after cancellation."""
    players = get_cancellation_players(event_id)
    return jsonify(players.get("paid", []))


@app.route("/api/events/<int:event_id>/cancel-bulk", methods=["POST"])
@require_role("admin")
def api_cancel_bulk(event_id):
    """Apply credit or refund to all eligible paid players for a cancelled event."""
    data = request.get_json(silent=True) or {}
    action = data.get("action")  # 'credit' or 'refund'
    note = data.get("note", "").strip() or "Event cancelled"
    if action not in ("credit", "refund"):
        return jsonify({"error": "action must be 'credit' or 'refund'"}), 400

    players = get_cancellation_players(event_id)
    results = {"ok": [], "failed": []}
    for item in players.get("paid", []):
        item_id = item["id"]
        try:
            if action == "credit":
                success = credit_item(item_id, note=note)
            else:
                method = item.get("auto_refund_method", "")
                success = refund_item(item_id, method=method, note=note)
            if success:
                results["ok"].append(item_id)
            else:
                results["failed"].append({"id": item_id, "reason": "already actioned"})
        except Exception as e:
            results["failed"].append({"id": item_id, "reason": str(e)})

    return jsonify({"status": "ok", "results": results})


@app.route("/api/events/<int:event_id>/cancel-apply", methods=["POST"])
@require_role("admin")
def api_cancel_apply(event_id):
    """Apply per-player actions from the one-by-one staging list.

    Body: { "actions": [{"item_id": 123, "action": "credit"|"refund"|"skip", "note": "..."}] }
    """
    data = request.get_json(silent=True) or {}
    actions = data.get("actions", [])
    if not actions:
        return jsonify({"error": "No actions provided"}), 400

    results = {"ok": [], "skipped": [], "failed": []}
    for entry in actions:
        item_id = entry.get("item_id")
        action = entry.get("action")
        note = (entry.get("note") or "Event cancelled").strip()
        method = (entry.get("method") or "").strip()

        if action == "skip":
            results["skipped"].append(item_id)
            continue
        try:
            if action == "credit":
                success = credit_item(item_id, note=note)
            elif action == "refund":
                success = refund_item(item_id, method=method, note=note)
            else:
                results["skipped"].append(item_id)
                continue
            if success:
                results["ok"].append(item_id)
            else:
                results["failed"].append({"id": item_id, "reason": "already actioned or not found"})
        except Exception as e:
            results["failed"].append({"id": item_id, "reason": str(e)})

    return jsonify({"status": "ok", "results": results})


@app.route("/api/players/<path:customer_name>/credits", methods=["GET"])
@require_role("manager")
def api_player_credits(customer_name):
    """Return all credited items for a player."""
    credits = get_player_credits(customer_name)
    total = sum(c["credit_amount"] for c in credits)
    return jsonify({"credits": credits, "total_credit": total})


@app.route("/api/events/<path:event_name>/rsvp-credits", methods=["GET"])
@require_role("manager")
def api_event_rsvp_credits(event_name):
    """Return credit info for all RSVP-only players in an event."""
    credit_map = get_event_rsvp_credit_map(event_name)
    return jsonify(credit_map)


@app.route("/api/rsvps/<int:item_id>/credit-info", methods=["GET"])
@require_role("manager")
def api_rsvp_credit_info_by_item(item_id):
    """Return full credit analysis for an RSVP-only item (by items.id)."""
    from email_parser.database import _connect, _calc_event_price_for_player
    with _connect() as conn:
        item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            return jsonify({"error": "Item not found"}), 404
        item = dict(item)

        credits = get_player_credits(item["customer"])
        if not credits:
            return jsonify({"error": "No credits on file for this player"}), 404

        total_credit = sum(c["credit_amount"] for c in credits)

        event_row = conn.execute(
            "SELECT * FROM events WHERE item_name = ? COLLATE NOCASE",
            (item["item_name"],),
        ).fetchone()
        event = dict(event_row) if event_row else {}

        most_recent = credits[0]
        prev = {
            "user_status": most_recent.get("user_status") or "MEMBER",
            "holes": most_recent.get("holes") or "9",
            "side_games": most_recent.get("side_games") or "NONE",
            "tee_choice": most_recent.get("tee_choice") or "",
        }

        event_price = _calc_event_price_for_player(
            event, prev["user_status"], prev["holes"], prev["side_games"]
        )
        amount_owed = round((event_price or 0.0) - total_credit, 2) if event_price is not None else None

    return jsonify({
        "item_id": item_id,
        "customer": item["customer"],
        "credits": [
            {
                "id": c["id"],
                "item_name": c.get("item_name") or "",
                "item_price": f"${c.get('credit_amount', 0):.2f}",
                "order_date": c.get("order_date") or "",
            }
            for c in credits
        ],
        "total_credit": total_credit,
        "event_price": event_price,
        "amount_owed": amount_owed,
        "previous_selections": prev,
    })


@app.route("/api/rsvps/<int:item_id>/apply-credit", methods=["POST"])
@require_role("admin")
def api_apply_credit_to_rsvp(item_id):
    """Apply a player's credits to their RSVP-only registration."""
    data = request.get_json(silent=True) or {}
    credited_item_ids = data.get("credited_item_ids", [])
    excess_action = data.get("excess_action", "keep")
    holes = data.get("holes", "")
    side_games = data.get("side_games", "")
    tee_choice = data.get("tee_choice", "")
    user_status = data.get("user_status", "")

    if not credited_item_ids:
        return jsonify({"error": "credited_item_ids required"}), 400
    if excess_action not in ("keep", "note"):
        return jsonify({"error": "excess_action must be 'keep' or 'note'"}), 400

    result = apply_credit_to_rsvp(
        rsvp_item_id=item_id,
        credited_item_ids=credited_item_ids,
        excess_action=excess_action,
        holes=holes,
        side_games=side_games,
        tee_choice=tee_choice,
        user_status=user_status,
    )
    if not result.get("ok"):
        return jsonify({"error": result.get("error", "Failed")}), 400
    return jsonify(result)


@app.route("/api/rsvps/trigger-credit-alerts", methods=["POST"])
@require_role("admin")
def api_trigger_credit_alerts():
    """Manually trigger credit alert email scan (for testing)."""
    try:
        _send_rsvp_credit_alerts()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/rsvps/gg/<int:rsvp_id>/credit-info", methods=["GET"])
@require_role("manager")
def api_gg_rsvp_credit_info(rsvp_id):
    """Return full credit analysis for a GG RSVP (by rsvps.id, not items.id)."""
    from email_parser.database import _connect, _calc_event_price_for_player
    with _connect() as conn:
        rsvp = conn.execute("SELECT * FROM rsvps WHERE id = ?", (rsvp_id,)).fetchone()
        if not rsvp:
            return jsonify({"error": "RSVP not found"}), 404
        rsvp = dict(rsvp)

        event_name = rsvp.get("matched_event") or ""
        player_email = (rsvp.get("player_email") or "").strip().lower()
        player_name = rsvp.get("player_name") or ""

        # Resolve canonical customer name via email
        customer = player_name
        if player_email:
            card = conn.execute(
                """SELECT customer FROM items WHERE LOWER(customer_email) = ?
                   AND customer IS NOT NULL AND customer != ''
                   ORDER BY order_date DESC LIMIT 1""",
                (player_email,),
            ).fetchone()
            if card:
                customer = card["customer"]

        credits = get_player_credits(customer)
        if not credits:
            return jsonify({"error": "No credits on file for this player"}), 404

        total_credit = sum(c["credit_amount"] for c in credits)

        event_row = conn.execute(
            "SELECT * FROM events WHERE item_name = ? COLLATE NOCASE", (event_name,)
        ).fetchone()
        event = dict(event_row) if event_row else {}

        most_recent = credits[0]
        prev = {
            "user_status": most_recent.get("user_status") or "MEMBER",
            "holes": most_recent.get("holes") or "9",
            "side_games": most_recent.get("side_games") or "NONE",
            "tee_choice": most_recent.get("tee_choice") or "",
        }

        event_price = _calc_event_price_for_player(
            event, prev["user_status"], prev["holes"], prev["side_games"]
        )
        amount_owed = round((event_price or 0.0) - total_credit, 2) if event_price is not None else None

    return jsonify({
        "rsvp_id": rsvp_id,
        "customer": customer,
        "credits": [
            {
                "id": c["id"],
                "item_name": c.get("item_name") or "",
                "item_price": f"${c.get('credit_amount', 0):.2f}",
                "order_date": c.get("order_date") or "",
            }
            for c in credits
        ],
        "total_credit": total_credit,
        "event_price": event_price,
        "amount_owed": amount_owed,
        "previous_selections": prev,
    })


@app.route("/api/rsvps/gg/<int:rsvp_id>/apply-credit", methods=["POST"])
@require_role("admin")
def api_gg_rsvp_apply_credit(rsvp_id):
    """Apply credits for a GG RSVP (synthetic row): creates rsvp_only item then applies credit."""
    from email_parser.database import _connect
    data = request.get_json(silent=True) or {}
    credited_item_ids = data.get("credited_item_ids", [])
    excess_action = data.get("excess_action", "keep")
    holes = data.get("holes", "")
    side_games = data.get("side_games", "")
    tee_choice = data.get("tee_choice", "")
    user_status = data.get("user_status", "")

    if not credited_item_ids:
        return jsonify({"error": "credited_item_ids required"}), 400

    with _connect() as conn:
        rsvp = conn.execute("SELECT * FROM rsvps WHERE id = ?", (rsvp_id,)).fetchone()
        if not rsvp:
            return jsonify({"error": "RSVP not found"}), 404
        rsvp = dict(rsvp)

    event_name = rsvp.get("matched_event") or ""
    player_email = rsvp.get("player_email") or ""
    player_name = rsvp.get("player_name") or ""

    # Create the rsvp_only item (idempotent)
    new_item_id = create_rsvp_only_item(
        event_name=event_name,
        player_name=player_name,
        player_email=player_email,
        rsvp_id=rsvp_id,
    )

    result = apply_credit_to_rsvp(
        rsvp_item_id=new_item_id,
        credited_item_ids=credited_item_ids,
        excess_action=excess_action,
        holes=holes,
        side_games=side_games,
        tee_choice=tee_choice,
        user_status=user_status,
    )
    if not result.get("ok"):
        return jsonify({"error": result.get("error", "Failed")}), 400
    return jsonify({**result, "item_id": new_item_id})


@app.route("/api/items/<int:item_id>/reverse-credit-application", methods=["POST"])
@require_role("admin")
def api_reverse_credit_application(item_id):
    """Undo a credit application: restore source credits, revert registration to RSVP."""
    result = reverse_credit_application(item_id)
    if not result.get("ok"):
        return jsonify({"error": result.get("error", "Failed")}), 400
    return jsonify(result)


@app.route("/api/events", methods=["POST"])
@require_role("manager")
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
        course_cost=data.get("course_cost"),
        tgf_markup=data.get("tgf_markup"),
        side_game_fee=data.get("side_game_fee"),
        transaction_fee_pct=data.get("transaction_fee_pct"),
        course_cost_9=data.get("course_cost_9"),
        course_cost_18=data.get("course_cost_18"),
        tgf_markup_9=data.get("tgf_markup_9"),
        tgf_markup_18=data.get("tgf_markup_18"),
        side_game_fee_9=data.get("side_game_fee_9"),
        side_game_fee_18=data.get("side_game_fee_18"),
        tgf_markup_final=data.get("tgf_markup_final"),
        tgf_markup_final_9=data.get("tgf_markup_final_9"),
        tgf_markup_final_18=data.get("tgf_markup_final_18"),
        course_cost_breakdown=data.get("course_cost_breakdown"),
        course_cost_breakdown_9=data.get("course_cost_breakdown_9"),
        course_cost_breakdown_18=data.get("course_cost_breakdown_18"),
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


@app.route("/api/events/mvp-unlinks")
@require_role("manager")
def api_mvp_unlinks():
    """Return list of event names explicitly unlinked from same-day TGF MVP combining."""
    return jsonify(get_mvp_unlinked_events())


@app.route("/api/events/mvp-unlink", methods=["POST"])
@require_role("admin")
def api_mvp_unlink():
    """Unlink an event from same-day TGF MVP combining."""
    data = request.get_json(silent=True)
    if not data or not data.get("event_name"):
        return jsonify({"error": "event_name required"}), 400
    set_mvp_unlink(data["event_name"], unlink=True)
    return jsonify({"status": "ok"})


@app.route("/api/events/mvp-relink", methods=["POST"])
@require_role("admin")
def api_mvp_relink():
    """Re-link a previously unlinked event for same-day TGF MVP combining."""
    data = request.get_json(silent=True)
    if not data or not data.get("event_name"):
        return jsonify({"error": "event_name required"}), 400
    set_mvp_unlink(data["event_name"], unlink=False)
    return jsonify({"status": "ok"})


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


@app.route("/api/parse-warnings")
def api_parse_warnings():
    """Return open parse warnings (items flagged during parsing)."""
    status = request.args.get("status", "open")
    return jsonify(get_parse_warnings(status))


@app.route("/api/action-items")
@require_role("manager")
def api_notification_action_items():
    """Return pending action items for admin/manager review.

    Aggregates parse warnings and GUEST registrations needing guest names.
    """
    items = []

    # 1. Parse warnings
    for w in get_parse_warnings("open"):
        items.append({
            "type": "parse_warning",
            "id": f"pw-{w['id']}",
            "pw_id": w["id"],
            "title": w.get("item_name") or "Unknown item",
            "message": w.get("message", ""),
            "customer": w.get("customer"),
            "order_id": w.get("order_id"),
            "item_id": w.get("item_id"),
            "code": w.get("warning_code"),
            "created_at": w.get("created_at"),
        })

    # 2. GUEST registrations needing guest name assignment
    #    Only flag when: same buyer has another item in the same order (multi-item purchase)
    #    AND no guest_name or partner_request is available to identify the guest.
    conn = get_connection()
    try:
        guests = conn.execute(
            """SELECT i.id, i.customer, i.item_name, i.order_date, i.user_status, i.notes
               FROM items i
               WHERE i.user_status LIKE '%GUEST%'
                 AND COALESCE(i.transaction_status, 'active') = 'active'
                 AND (i.notes IS NULL OR i.notes NOT LIKE '%Purchased by%')
                 AND i.email_uid NOT LIKE 'manual-%'
                 AND EXISTS (
                     SELECT 1 FROM items peer
                     WHERE peer.email_uid = i.email_uid
                       AND peer.id != i.id
                       AND peer.customer = i.customer COLLATE NOCASE
                 )
                 AND COALESCE(i.guest_name, '') = ''
                 AND COALESCE(i.partner_request, '') = ''
               ORDER BY i.order_date DESC"""
        ).fetchall()
        for g in guests:
            g = dict(g)
            items.append({
                "type": "guest_name_needed",
                "id": f"guest-{g['id']}",
                "item_id": g["id"],
                "title": g.get("item_name") or "Unknown event",
                "message": f"GUEST registration under \"{g['customer']}\" — confirm or enter the actual guest player's name.",
                "customer": g.get("customer"),
                "created_at": g.get("order_date"),
            })
    finally:
        conn.close()

    return jsonify(items)


@app.route("/api/parse-warnings/<int:warning_id>/dismiss", methods=["POST"])
@require_role("manager")
def api_dismiss_parse_warning(warning_id):
    """Dismiss a parse warning."""
    if dismiss_parse_warning(warning_id):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Warning not found."}), 404


@app.route("/api/parse-warnings/<int:warning_id>/resolve", methods=["POST"])
@require_role("manager")
def api_resolve_parse_warning(warning_id):
    """Mark a parse warning as resolved."""
    if resolve_parse_warning(warning_id):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Warning not found."}), 404


# ---------------------------------------------------------------------------
# Routes — Credit / Transfer
# ---------------------------------------------------------------------------
@app.route("/api/items/<int:item_id>/credit", methods=["POST"])
@require_role("admin")
def api_credit_item(item_id):
    """Mark an item as credited (money held for future event)."""
    data = request.get_json(silent=True) or {}
    if credit_item(item_id, note=data.get("note", "")):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Item not found or already credited/transferred."}), 400


@app.route("/api/items/<int:item_id>/wd", methods=["POST"])
@require_role("admin")
def api_wd_item(item_id):
    """Mark an item as WD (withdrawn) with optional partial credit."""
    data = request.get_json(silent=True) or {}
    note = data.get("note", "")
    credits = data.get("credits")  # dict like {"included_games": 14, ...}
    credit_amount = data.get("credit_amount", "")
    if wd_item(item_id, note=note, credits=credits, credit_amount=credit_amount):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Item not found or already credited/transferred/WD."}), 400


@app.route("/api/items/<int:item_id>/refund", methods=["POST"])
@require_role("admin")
def api_refund_item(item_id):
    """Mark an item as refunded via GoDaddy or Venmo."""
    data = request.get_json(silent=True) or {}
    method = data.get("method", "")
    if method and method not in ("GoDaddy", "Venmo", "Zelle"):
        return jsonify({"error": "Invalid refund method. Must be GoDaddy, Venmo, or Zelle."}), 400
    if refund_item(item_id, method=method, note=data.get("note", "")):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Item not found or already credited/transferred."}), 400


@app.route("/api/items/<int:item_id>/partial-refund", methods=["POST"])
@require_role("admin")
def api_partial_refund_item(item_id):
    """Partially refund specific components (e.g., one side game) while keeping player active.

    Creates a -PAY child row showing the refund, and updates the parent's side_games.
    """
    data = request.get_json(silent=True) or {}
    method = data.get("method", "")
    if method and method not in ("GoDaddy", "Venmo", "Zelle"):
        return jsonify({"error": "Invalid refund method."}), 400
    refunded_components = data.get("components", {})  # e.g. {"gross_games": 30}
    new_side_games = data.get("new_side_games")  # e.g. "NET" (after removing GROSS)
    note = data.get("note", "")
    total = sum(refunded_components.values())

    # Build description
    comp_labels = ", ".join(f"{k.replace('_', ' ').title()}" for k in refunded_components.keys())
    refund_desc = f"Refund {comp_labels} via {method}" if method else f"Refund {comp_labels}"

    import time as _time
    from email_parser.database import _connect
    uid = f"manual-refund-{int(_time.time() * 1000)}"
    with _connect() as conn:
        parent = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not parent:
            return jsonify({"error": "Item not found."}), 404
        parent = dict(parent)

        # Snapshot parent's mutable fields BEFORE modifying
        parent_snap = {}
        for fld in ("side_games", "holes", "tee_choice", "user_status"):
            if parent.get(fld) is not None:
                parent_snap[fld] = parent[fld]

        # Compute new side_games from current DB value based on refunded components
        current_sg = (parent.get("side_games") or "NONE").strip().upper()
        refunding_net = "net_games" in refunded_components
        refunding_gross = "gross_games" in refunded_components
        computed_new_sg = current_sg
        if current_sg == "BOTH":
            if refunding_net and refunding_gross:
                computed_new_sg = "NONE"
            elif refunding_net:
                computed_new_sg = "GROSS"
            elif refunding_gross:
                computed_new_sg = "NET"
        elif current_sg == "NET" and refunding_net:
            computed_new_sg = "NONE"
        elif current_sg == "GROSS" and refunding_gross:
            computed_new_sg = "NONE"

        # Update parent side_games if changed
        if computed_new_sg != current_sg:
            conn.execute("UPDATE items SET side_games = ? WHERE id = ?",
                         (computed_new_sg, item_id))

        # Create -PAY child row with parent snapshot
        cur = conn.execute(
            """INSERT INTO items (email_uid, merchant, customer, item_name, item_price,
               side_games, notes, parent_item_id, parent_snapshot, transaction_status, order_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
            (uid, f"Refund ({method})" if method else "Partial Refund",
             parent["customer"], parent["item_name"],
             f"-${total:.2f}",
             None,
             refund_desc + (f" — {note}" if note else ""),
             item_id,
             json.dumps(parent_snap) if parent_snap else None,
             datetime.now().strftime("%Y-%m-%d")),
        )
        new_child_id = cur.lastrowid

        # ── Accounting: flat entry for partial refund ──
        try:
            from email_parser.database import _write_acct_entry
            refund_source = method.lower().replace(" ", "_") if method else "manual"
            refund_account = "Venmo" if "venmo" in (method or "").lower() else "TGF Checking"
            _write_acct_entry(
                conn,
                item_id=new_child_id,
                event_name=parent["item_name"],
                customer=parent["customer"],
                order_id=parent.get("order_id", ""),
                entry_type="expense",
                category="refund",
                source=refund_source,
                amount=float(total),
                description=f"Partial refund ({method}): {parent['customer']} — {parent['item_name']}",
                account=refund_account,
                source_ref=f"partial-refund-{new_child_id}",
                date=datetime.now().strftime("%Y-%m-%d"),
            )
        except Exception:
            logger.warning("Failed to create accounting entry for partial refund %d", item_id, exc_info=True)

        conn.commit()

    return jsonify({"status": "ok", "refunded": total, "new_side_games": computed_new_sg})


@app.route("/api/items/<int:item_id>/transfer", methods=["POST"])
@require_role("admin")
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
@require_role("admin")
def api_reverse_credit(item_id):
    """Reverse a credit or transfer, restoring the original item to active."""
    if reverse_credit(item_id):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Item not found or not in credited/transferred state."}), 400


@app.route("/api/events/add-player", methods=["POST"])
@require_role("manager")
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
            user_status=data.get("user_status", data.get("member_status", "")),
            payment_amount=data.get("payment_amount", ""),
            payment_source=data.get("payment_source", ""),
            customer_email=data.get("customer_email", ""),
            customer_phone=data.get("customer_phone", ""),
            holes=data.get("holes", ""),
            order_date=data.get("order_date", ""),
        )
        if item:
            return jsonify({"status": "ok", "item": item}), 201
        return jsonify({"error": "Failed to add player."}), 500
    except Exception as e:
        logger.exception("Error adding player: %s", e)
        return jsonify({"error": f"Server error: {e}"}), 500


@app.route("/api/events/add-payment", methods=["POST"])
@require_role("manager")
def api_add_payment():
    """Add an additional payment record for an existing event player."""
    data = request.get_json(silent=True)
    if not data or not data.get("event_name") or not data.get("customer"):
        return jsonify({"error": "event_name and customer are required."}), 400
    if not data.get("payment_amount") or not data.get("payment_source"):
        return jsonify({"error": "payment_amount and payment_source are required."}), 400
    err = validate_json_fields(data)
    if err:
        return jsonify({"error": err}), 400
    try:
        item = add_payment_to_event(
            event_name=data["event_name"],
            customer=data["customer"],
            payment_item=data.get("payment_item", ""),
            payment_amount=data.get("payment_amount", ""),
            payment_source=data.get("payment_source", ""),
            note=data.get("note", ""),
            order_date=data.get("order_date", ""),
        )
        if item:
            return jsonify({"status": "ok", "item": item}), 201
        return jsonify({"error": "Failed to add payment."}), 500
    except Exception as e:
        logger.exception("Error adding payment: %s", e)
        return jsonify({"error": f"Server error: {e}"}), 500


@app.route("/api/events/upgrade-rsvp", methods=["POST"])
@require_role("manager")
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
        user_status=data.get("user_status", data.get("member_status", "")),
    )
    if item:
        return jsonify({"status": "ok", "item": item})
    return jsonify({"error": "Item not found or not in RSVP-only state."}), 400


@app.route("/api/events/send-reminder", methods=["POST"])
@require_role("manager")
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
@require_role("manager")
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
        logger.warning("Failed to load RSVP overrides for %s", event_name, exc_info=True)

    rsvps_for_event = {}
    rsvp_list = []
    try:
        rsvp_list = get_rsvps_for_event(event_name)
        for rv in rsvp_list:
            if rv.get("matched_item_id"):
                rsvps_for_event[rv["matched_item_id"]] = rv["response"]
    except Exception:
        logger.warning("Failed to load RSVPs for event %s", event_name, exc_info=True)

    # Build GG RSVP synthetic rows (unmatched RSVPs with player_email)
    email_overrides = {}
    try:
        email_overrides = get_rsvp_email_overrides(event_name)
    except Exception:
        logger.warning("Failed to load RSVP email overrides for %s", event_name, exc_info=True)

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
@require_role("manager")
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
@require_role("manager")
def api_rsvp_rematch():
    """Re-run matching logic on unmatched RSVPs."""
    try:
        result = rematch_rsvps()
        return jsonify({"status": "ok", **result})
    except Exception as e:
        logger.exception("RSVP rematch failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/rsvps/audit-event/<path:event_name>", methods=["POST"])
@require_role("manager")
def api_audit_event_rsvps(event_name):
    """Audit and fix RSVP matches for a specific event.

    Clears bad matches (email mismatch) and re-attempts matching.
    """
    try:
        result = audit_event_rsvps(event_name)
        return jsonify({"status": "ok", **result})
    except Exception as e:
        logger.exception("RSVP audit failed for event: %s", event_name)
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
@require_role("manager")
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
@require_role("manager")
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
# Routes — Handicap Calculator
# ---------------------------------------------------------------------------
@app.route("/handicaps")
def page_handicaps():
    return render_template("handicaps.html")


@app.route("/api/handicaps/players")
def api_handicap_players():
    """Return all players with their current handicap index.

    Also runs a quick auto-link pass for any unlinked players so that
    newly added customers are matched to their handicap records.
    """
    try:
        relink_all_unlinked_players()
    except Exception:
        logger.debug("Auto-link pass failed (non-critical)", exc_info=True)
    players = get_all_handicap_players()
    return jsonify(players)


@app.route("/api/handicaps/rounds")
def api_handicap_rounds():
    """Return rounds for a single player (?player=Name) or all rounds."""
    player_name = request.args.get("player")
    rounds = get_handicap_rounds(player_name=player_name)
    return jsonify(rounds)


@app.route("/api/handicaps/for-customer")
def api_handicap_for_customer():
    """Return handicap data for a customer by looking up their linked player name.

    Query: ?customer_name=John+Smith
    Returns: {player_name, handicap_index, rounds: [...], settings: {...}}
    or {error: "not linked"} if no handicap player is linked to this customer.
    """
    customer_name = request.args.get("customer_name", "").strip()
    if not customer_name:
        return jsonify({"error": "customer_name required"}), 400

    conn = get_connection()
    try:
        # Find linked player name for this customer
        link = conn.execute(
            "SELECT player_name FROM handicap_player_links "
            "WHERE LOWER(customer_name) = LOWER(?)",
            (customer_name,),
        ).fetchone()
        if not link:
            return jsonify({"error": "not linked", "customer_name": customer_name})

        player_name = link["player_name"]
    finally:
        conn.close()

    # Get their handicap index from the players list
    all_players = get_all_handicap_players()
    player_info = next((p for p in all_players if p["player_name"] == player_name), None)

    # Get their rounds
    rounds = get_handicap_rounds(player_name=player_name)

    # Get settings for the frontend calc
    cfg = get_handicap_settings()

    return jsonify({
        "player_name": player_name,
        "handicap_index": player_info["handicap_index"] if player_info else None,
        "active_rounds": player_info["active_rounds"] if player_info else 0,
        "total_rounds": player_info["total_rounds"] if player_info else 0,
        "rounds": rounds,
        "settings": cfg,
    })


@app.route("/api/handicaps/index-map")
def api_handicap_index_map():
    """Return a map of customer_name (lowercase) → handicap_index for all linked players.

    Lightweight endpoint used by the events page to display live HCP values.
    """
    players = get_all_handicap_players()
    index_map = {}
    for p in players:
        cname = p.get("customer_name")
        if cname and p.get("handicap_index") is not None:
            idx9 = p["handicap_index"]
            index_map[cname.lower()] = {
                "index_9": idx9,
                "index_18": round(idx9 * 2, 1),
            }
    return jsonify(index_map)


@app.route("/api/handicaps/rounds/<int:round_id>", methods=["DELETE"])
@require_role("manager")
def api_delete_handicap_round(round_id):
    """Delete a single round by id. Manager or admin."""
    if delete_handicap_round(round_id):
        return jsonify({"status": "ok"})
    return jsonify({"error": "not found"}), 404


@app.route("/api/handicaps/purge-invalid", methods=["POST"])
@require_role("admin")
def api_purge_invalid_rounds():
    """Delete all rounds with 18-hole ratings (rating > 50). Admin only."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, player_name, round_date, course_name, rating "
            "FROM handicap_rounds WHERE rating > 50"
        ).fetchall()
        for row in rows:
            conn.execute("DELETE FROM handicap_rounds WHERE id = ?", (row["id"],))
        conn.commit()
        return jsonify({"status": "ok", "deleted": len(rows),
                        "rounds": [dict(r) for r in rows]})
    finally:
        conn.close()


@app.route("/api/handicaps/players/<path:player_name>", methods=["DELETE"])
@require_role("admin")
def api_delete_handicap_player(player_name):
    """Delete all rounds for a player. Admin only."""
    count = delete_all_handicap_rounds_for_player(player_name)
    return jsonify({"status": "ok", "deleted": count})


@app.route("/api/handicaps/settings", methods=["GET"])
def api_get_handicap_settings():
    """Return current handicap calculation settings."""
    return jsonify(get_handicap_settings())


@app.route("/api/handicaps/settings", methods=["PATCH"])
@require_role("admin")
def api_update_handicap_settings():
    """Update handicap calculation settings. Admin only."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400
    allowed = {"lookback_months", "min_rounds", "multiplier"}
    filtered = {k: v for k, v in data.items() if k in allowed}
    if not filtered:
        return jsonify({"error": f"No valid settings keys. Allowed: {', '.join(allowed)}"}), 400
    # Validate types
    try:
        if "lookback_months" in filtered:
            v = int(filtered["lookback_months"])
            if v < 1 or v > 120:
                return jsonify({"error": "lookback_months must be 1–120"}), 400
        if "min_rounds" in filtered:
            v = int(filtered["min_rounds"])
            if v < 1 or v > 20:
                return jsonify({"error": "min_rounds must be 1–20"}), 400
        if "multiplier" in filtered:
            v = float(filtered["multiplier"])
            if v <= 0 or v > 2:
                return jsonify({"error": "multiplier must be between 0 and 2"}), 400
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid value: {e}"}), 400
    update_handicap_settings(filtered)
    return jsonify({"status": "ok", "settings": get_handicap_settings()})


@app.route("/api/handicaps/import-preview", methods=["POST"])
@require_role("manager")
def api_handicap_import_preview():
    """Parse uploaded Excel and return headers + first 10 data rows for mapping."""
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file uploaded"}), 400

    import io
    from openpyxl import load_workbook
    try:
        wb = load_workbook(io.BytesIO(file.read()), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)

        # Read first few rows to detect header
        candidate_rows = []
        for raw_row in rows_iter:
            candidate_rows.append(raw_row)
            if len(candidate_rows) >= 5:
                break
        if not candidate_rows:
            return jsonify({"error": "Empty spreadsheet"}), 400

        # Find header row: first row where >40% of cells are non-empty
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

        # Collect preview rows (up to 10)
        preview = []
        for row in candidate_rows[header_idx + 1:]:
            preview.append([str(c).strip() if c is not None else "" for c in row])
        for row in rows_iter:
            if len(preview) >= 10:
                break
            preview.append([str(c).strip() if c is not None else "" for c in row])

        # Count total data rows (re-open for accurate count)
        wb.close()

        # Auto-detect column mapping from header names
        def _find_col(candidates):
            for cand in candidates:
                for idx, h in enumerate(headers):
                    if h.lower() == cand.lower():
                        return idx
            return None

        auto_mapping = {
            "player_name":     _find_col(["name", "player", "player_name", "player name"]),
            "player_email":    _find_col(["email", "player_email", "player email", "e-mail"]),
            "round_date":      _find_col(["play at", "date", "round_date", "played"]),
            "round_id":        _find_col(["round id", "round_id", "roundid"]),
            "course_name":     _find_col(["course name", "course", "course_name"]),
            "tee_name":        _find_col(["tee name", "tee", "tee_name", "tees"]),
            "adjusted_score":  _find_col(["adjusted score", "adj score", "score", "adjusted_score"]),
            "rating":          _find_col(["rating", "course rating"]),
            "slope":           _find_col(["slope", "slope rating"]),
            "differential":    _find_col(["differential", "diff"]),
        }

        return jsonify({
            "headers": headers,
            "preview": preview,
            "auto_mapping": auto_mapping,
        })
    except Exception as e:
        logger.exception("Handicap import preview failed")
        return jsonify({"error": f"Failed to parse file: {str(e)}"}), 400


@app.route("/api/handicaps/import", methods=["POST"])
@require_role("manager")
def api_handicap_import():
    """Import handicap rounds from uploaded Excel with column mapping.

    Accepts multipart/form-data with:
      - file: the Excel file
      - mapping: JSON object {field_name: col_index, ...}
    """
    file = request.files.get("file")
    mapping_json = request.form.get("mapping", "{}")
    if not file or not file.filename:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        mapping = json.loads(mapping_json)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid mapping JSON"}), 400

    required = {"player_name", "round_date", "adjusted_score", "rating", "slope"}
    missing = required - set(k for k, v in mapping.items() if v is not None)
    if missing:
        return jsonify({"error": f"Required column mapping missing: {', '.join(missing)}"}), 400

    import io
    from openpyxl import load_workbook
    try:
        wb = load_workbook(io.BytesIO(file.read()), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)

        # Skip to header row (same detection as preview)
        candidate_rows = []
        for raw_row in rows_iter:
            candidate_rows.append(raw_row)
            if len(candidate_rows) >= 5:
                break
        header_idx = 0
        if candidate_rows:
            total_cols = len(candidate_rows[0])
            for i, row in enumerate(candidate_rows):
                non_empty = sum(1 for c in row if c is not None and str(c).strip())
                if non_empty >= max(2, total_cols * 0.4):
                    header_idx = i
                    break

        # Build list of data rows
        all_data_rows = list(candidate_rows[header_idx + 1:]) + list(rows_iter)
        wb.close()

        # Parse date helper — handles datetime objects, MM/DD/YYYY, YYYY-MM-DD,
        # and sparse "D-Mon" / "D-Mon-YY" strings (e.g. "7-Feb", "7-Feb-25")
        def _parse_date(val):
            if val is None:
                return ""
            s = str(val).strip()
            # openpyxl may return a datetime object directly
            if hasattr(val, "strftime"):
                return val.strftime("%Y-%m-%d")
            # MM/DD/YYYY
            if "/" in s:
                parts = s.split("/")
                if len(parts) == 3:
                    m, d, y = parts
                    return f"{y.zfill(4)}-{m.zfill(2)}-{d.zfill(2)}"
            # D-Mon-YY or D-Mon (e.g. "7-Feb-25" or "7-Feb")
            if "-" in s:
                from datetime import datetime as _dt
                for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d-%b"):
                    try:
                        parsed = _dt.strptime(s, fmt)
                        if fmt == "%d-%b":
                            # No year supplied — use current year
                            parsed = parsed.replace(year=_dt.now().year)
                        return parsed.strftime("%Y-%m-%d")
                    except ValueError:
                        continue
            return s  # already YYYY-MM-DD or unknown format

        rounds = []
        last_player_name = None  # support fill-down name format
        last_player_email = None  # support fill-down email format
        for row in all_data_rows:
            def _get(field):
                idx = mapping.get(field)
                if idx is None or idx >= len(row):
                    return None
                val = row[idx]
                return str(val).strip() if val is not None else None

            player_name = _get("player_name")
            if player_name:
                last_player_name = player_name
            elif last_player_name:
                player_name = last_player_name

            if not player_name:
                continue

            # Email: fill-down like player_name (email only appears on first row per player)
            player_email = _get("player_email")
            if player_email:
                last_player_email = player_email
            elif not player_email and player_name == last_player_name:
                player_email = last_player_email

            rounds.append({
                "player_name": player_name,
                "player_email": player_email,
                "round_date":  _parse_date(row[mapping["round_date"]] if mapping.get("round_date") is not None and mapping["round_date"] < len(row) else None),
                "round_id":    _get("round_id"),
                "course_name": _get("course_name"),
                "tee_name":    _get("tee_name"),
                "adjusted_score": _get("adjusted_score"),
                "rating":      _get("rating"),
                "slope":       _get("slope"),
                "differential": _get("differential"),
            })

        if not rounds:
            return jsonify({"error": "No data rows found in the file"}), 400

        result = import_handicap_rounds(rounds)
        return jsonify(result)

    except Exception as e:
        logger.exception("Handicap import failed")
        return jsonify({"error": f"Import failed: {str(e)}"}), 500


# ---------------------------------------------------------------------------
# Routes — Golf Genius Sync
# ---------------------------------------------------------------------------

@app.route("/api/handicaps/auto-link", methods=["POST"])
@require_role("admin")
def api_handicap_auto_link():
    """Re-attempt matching all unlinked handicap players to customer records."""
    result = relink_all_unlinked_players()
    return jsonify(result)


@app.route("/api/handicaps/link-player", methods=["POST"])
@require_role("manager")
def api_handicap_link_player():
    """Link a single handicap player to a customer name."""
    data = request.get_json(force=True)
    player_name = (data.get("player_name") or "").strip()
    customer_name = (data.get("customer_name") or "").strip()
    if not player_name:
        return jsonify({"error": "player_name required"}), 400
    if not customer_name:
        return jsonify({"error": "customer_name required"}), 400

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO handicap_player_links (player_name, customer_name) VALUES (?, ?) "
            "ON CONFLICT(player_name) DO UPDATE SET customer_name = excluded.customer_name, "
            "linked_at = datetime('now')",
            (player_name, customer_name),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "player_name": player_name, "customer_name": customer_name})


@app.route("/api/handicaps/repair-swapped-links", methods=["POST"])
@require_role("admin")
def api_repair_swapped_links():
    """Fix links where player_name and customer_name were swapped due to a bug.

    Detection: if the stored player_name exists as a customer in items but NOT
    in handicap_rounds, and the stored customer_name exists in handicap_rounds
    but NOT as a customer in items — the link is backwards and needs swapping.
    """
    conn = get_connection()
    try:
        links = conn.execute(
            "SELECT player_name, customer_name FROM handicap_player_links "
            "WHERE customer_name IS NOT NULL"
        ).fetchall()

        # Build lookup sets
        hcp_players = {r["player_name"].lower() for r in conn.execute(
            "SELECT DISTINCT player_name FROM handicap_rounds"
        ).fetchall()}
        item_customers = {r["customer"].lower() for r in conn.execute(
            "SELECT DISTINCT customer FROM items WHERE customer IS NOT NULL"
        ).fetchall()}

        swapped = []
        for lnk in links:
            pn = lnk["player_name"]
            cn = lnk["customer_name"]
            pn_l = pn.lower()
            cn_l = cn.lower()

            # If stored player_name looks like a customer (in items) but not a
            # handicap player, AND stored customer_name looks like a handicap
            # player but not a customer — they're swapped.
            if (pn_l in item_customers and pn_l not in hcp_players and
                    cn_l in hcp_players and cn_l not in item_customers):
                swapped.append((pn, cn))

        # Fix the swapped links
        for old_pn, old_cn in swapped:
            # Delete the wrong row, insert corrected one
            conn.execute(
                "DELETE FROM handicap_player_links WHERE player_name = ?",
                (old_pn,),
            )
            conn.execute(
                "INSERT INTO handicap_player_links (player_name, customer_name) "
                "VALUES (?, ?) ON CONFLICT(player_name) DO UPDATE SET "
                "customer_name = excluded.customer_name, linked_at = datetime('now')",
                (old_cn, old_pn),
            )

        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "status": "ok",
        "repaired": len(swapped),
        "details": [f"{pn} ↔ {cn}" for pn, cn in swapped],
    })


@app.route("/api/handicaps/unlink-player", methods=["POST"])
@require_role("manager")
def api_handicap_unlink_player():
    """Unlink a handicap player from their customer."""
    data = request.get_json(force=True)
    player_name = (data.get("player_name") or "").strip()
    if not player_name:
        return jsonify({"error": "player_name required"}), 400

    conn = get_connection()
    try:
        conn.execute(
            "UPDATE handicap_player_links SET customer_name = NULL WHERE player_name = ?",
            (player_name,),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "player_name": player_name})


@app.route("/api/customers/names")
def api_customer_names():
    """Return a sorted list of unique customer names for autocomplete/linking."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT customer FROM items WHERE customer IS NOT NULL AND TRIM(customer) != '' ORDER BY customer COLLATE NOCASE"
        ).fetchall()
    finally:
        conn.close()
    return jsonify([r["customer"] for r in rows])


@app.route("/api/handicaps/link-debug")
@require_role("admin")
def api_handicap_link_debug():
    """Full export diagnostic: show every handicap player's link status, email, chapter, and index."""
    from email_parser.database import _connect, get_all_handicap_players
    all_players = get_all_handicap_players()
    player_map = {p["player_name"]: p for p in all_players}

    with _connect() as conn:
        links = conn.execute(
            "SELECT player_name, customer_name FROM handicap_player_links ORDER BY player_name"
        ).fetchall()
        link_map = {r["player_name"]: r["customer_name"] for r in links}

        details = []
        for pname in sorted(player_map.keys(), key=str.lower):
            p = player_map[pname]
            cname = link_map.get(pname)
            email_items = None
            email_alias = None
            chapter = None
            if cname:
                row = conn.execute(
                    "SELECT customer_email FROM items WHERE LOWER(customer)=LOWER(?) "
                    "AND customer_email IS NOT NULL AND TRIM(customer_email) != '' "
                    "ORDER BY id DESC LIMIT 1", (cname,)
                ).fetchone()
                email_items = row["customer_email"].strip().lower() if row else None
                row2 = conn.execute(
                    "SELECT alias_value FROM customer_aliases "
                    "WHERE LOWER(customer_name)=LOWER(?) AND alias_type='email' LIMIT 1",
                    (cname,)
                ).fetchone()
                email_alias = row2["alias_value"].strip().lower() if row2 else None
                row3 = conn.execute(
                    "SELECT chapter FROM items WHERE LOWER(customer)=LOWER(?) "
                    "AND chapter IS NOT NULL AND TRIM(chapter) != '' "
                    "ORDER BY id DESC LIMIT 1", (cname,)
                ).fetchone()
                chapter = row3["chapter"] if row3 else None

            email = email_items or email_alias or None
            idx = p["handicap_index"]
            would_export = bool(cname and email and idx is not None)

            details.append({
                "player_name": pname,
                "customer_name": cname,
                "linked": bool(cname),
                "email_from_items": email_items,
                "email_from_aliases": email_alias,
                "email": email,
                "chapter": chapter,
                "handicap_index_9": idx,
                "handicap_index_18": round(idx * 2, 1) if idx is not None else None,
                "would_export": would_export,
                "missing": (
                    "not linked" if not cname else
                    "no email" if not email else
                    "no index" if idx is None else
                    None
                ),
            })

        summary = {
            "total_players": len(details),
            "linked": sum(1 for d in details if d["linked"]),
            "unlinked": sum(1 for d in details if not d["linked"]),
            "have_email": sum(1 for d in details if d["email"]),
            "have_index": sum(1 for d in details if d["handicap_index_9"] is not None),
            "would_export": sum(1 for d in details if d["would_export"]),
            "missing_email": [d["player_name"] for d in details if d["linked"] and not d["email"]],
            "missing_index": [d["player_name"] for d in details if d["linked"] and d["email"] and d["handicap_index_9"] is None],
        }

    return jsonify({"summary": summary, "players": details})


@app.route("/api/handicaps/unlinked-players")
@require_role("admin")
def api_handicap_unlinked_players():
    """Return handicap players with no linked customer record."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT l.player_name, l.customer_name
               FROM handicap_player_links l
               WHERE l.customer_name IS NULL"""
        ).fetchall()
    finally:
        conn.close()
    return jsonify([{"player_name": r["player_name"]} for r in rows])


@app.route("/api/handicaps/create-customers-for-unlinked", methods=["POST"])
@require_role("admin")
def api_create_customers_for_unlinked():
    """Auto-create archived customer records for all unlinked handicap players."""
    conn = get_connection()
    try:
        unlinked = conn.execute(
            "SELECT player_name FROM handicap_player_links WHERE customer_name IS NULL"
        ).fetchall()
    finally:
        conn.close()

    created = 0
    linked = 0
    skipped = 0
    for row in unlinked:
        player_name = row["player_name"]
        # Try to find an existing customer with this name
        conn2 = get_connection()
        try:
            existing = conn2.execute(
                "SELECT customer FROM items WHERE customer = ? COLLATE NOCASE LIMIT 1",
                (player_name,)
            ).fetchone()
        finally:
            conn2.close()

        if existing:
            # Link to existing customer, update link
            conn3 = get_connection()
            try:
                conn3.execute(
                    "UPDATE handicap_player_links SET customer_name = ? WHERE player_name = ?",
                    (existing["customer"], player_name)
                )
                conn3.commit()
            finally:
                conn3.close()
            linked += 1
        else:
            # Create a new archived customer record
            parts = player_name.split(None, 1)
            first_name = parts[0] if parts else player_name
            last_name = parts[1] if len(parts) > 1 else ""
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")

            conn3 = get_connection()
            try:
                conn3.execute(
                    """INSERT INTO items (email_uid, item_index, merchant, customer, first_name,
                       last_name, order_date, item_name, archived)
                       VALUES (?, 0, 'Handicap Import', ?, ?, ?, ?, 'Handicap Import', 1)""",
                    (f"handicap_import_{player_name}_{today}", player_name,
                     first_name, last_name, today)
                )
                # Now link them
                conn3.execute(
                    "UPDATE handicap_player_links SET customer_name = ? WHERE player_name = ?",
                    (player_name, player_name)
                )
                conn3.commit()
            finally:
                conn3.close()
            created += 1

    return jsonify({"created": created, "linked": linked, "total": len(unlinked)})


@app.route("/api/handicaps/export-preview")
@require_role("manager")
def api_handicap_export_preview():
    """JSON preview of what the CSV export would contain, with diagnostics."""
    chapter = request.args.get("chapter", "").strip()
    data = get_handicap_export_data(chapter=chapter if chapter else None)
    return jsonify(data)


@app.route("/api/handicaps/export-csv")
@require_role("manager")
def api_handicap_export_csv():
    """Download a Golf Genius-ready CSV for the given chapter.

    Query params:
        chapter: "San Antonio" | "Austin" | (omit for all)
    """
    chapter = request.args.get("chapter", "").strip()
    data = get_handicap_export_data(chapter=chapter if chapter else None)

    import io as _io, csv as _csv
    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow(["Last", "First", "Suffix", "Chapter", "Handicap Index", "Email"])
    for row in data["rows"]:
        writer.writerow([row["last_name"], row["first_name"], row["suffix"],
                         row["chapter"], row["handicap_index"], row["email"]])

    chapter_slug = chapter.lower().replace(" ", "_") if chapter else "all"
    filename = f"tgf_handicaps_{chapter_slug}_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Track running sync jobs (chapter key → {"status", "message", "timestamp"})
_gg_sync_jobs: dict[str, dict] = {}


@app.route("/api/handicaps/sync-golf-genius", methods=["POST"])
@require_role("admin")
def api_sync_golf_genius():
    """Trigger an on-demand Golf Genius handicap sync for a chapter.

    Body JSON:
        {"chapter": "San Antonio" | "Austin" | "all",
         "test_player_email": "email@example.com"}   # optional: limit to 1 player for testing
    """
    from golf_genius_sync import sync_handicaps_to_league
    import threading

    body = request.get_json(silent=True) or {}
    chapter = body.get("chapter", "").strip()
    test_player_email = (body.get("test_player_email") or "").strip().lower() or None

    gg_email = os.getenv("GOLF_GENIUS_EMAIL", "").strip()
    gg_password = os.getenv("GOLF_GENIUS_PASSWORD", "").strip()
    sa_league_id = os.getenv("GOLF_GENIUS_SA_LEAGUE_ID", "514047").strip()
    austin_league_id = os.getenv("GOLF_GENIUS_AUSTIN_LEAGUE_ID", "514705").strip()

    if not gg_email or not gg_password:
        return jsonify({
            "status": "error",
            "message": "GOLF_GENIUS_EMAIL and GOLF_GENIUS_PASSWORD environment variables are not set",
        }), 400

    chapters_to_sync = []
    if chapter.lower() in ("san antonio", "sa", ""):
        chapters_to_sync.append(("San Antonio", sa_league_id, "san_antonio"))
    if chapter.lower() in ("austin", "atx", ""):
        chapters_to_sync.append(("Austin", austin_league_id, "austin"))

    if not chapters_to_sync:
        return jsonify({"status": "error", "message": f"Unknown chapter: {chapter}"}), 400

    # Mark jobs as running
    for _, _, key in chapters_to_sync:
        _gg_sync_jobs[key] = {
            "status": "running",
            "message": "Sync in progress…",
            "timestamp": datetime.utcnow().isoformat(),
            "rows_submitted": 0,
        }

    def _run_sync():
        for chap, league_id, key in chapters_to_sync:
            try:
                export = get_handicap_export_data(
                    chapter=chap,
                    test_player_email=test_player_email,
                )
                rows = export["rows"]
                if not rows:
                    msg = (
                        f"No player found with email '{test_player_email}' in {chap}"
                        if test_player_email
                        else f"No players with email + handicap index for {chap}"
                    )
                    _gg_sync_jobs[key] = {
                        "status": "skipped",
                        "message": msg,
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
                _gg_sync_jobs[key] = result
            except Exception as exc:
                logger.exception("GG sync error for %s", chap)
                _gg_sync_jobs[key] = {
                    "status": "error",
                    "message": str(exc),
                    "rows_submitted": 0,
                    "timestamp": datetime.utcnow().isoformat(),
                }

        # Persist results
        try:
            update_handicap_settings({"last_gg_sync": json.dumps(_gg_sync_jobs)})
        except Exception:
            logger.warning("Failed to persist GG sync results", exc_info=True)

    threading.Thread(target=_run_sync, daemon=True).start()
    return jsonify({"status": "started", "chapters": [c[0] for c in chapters_to_sync]})


@app.route("/api/handicaps/sync-status")
@require_role("manager")
def api_handicap_sync_status():
    """Return the current/last Golf Genius sync status."""
    # Merge in-memory jobs with persisted last result
    persisted = {}
    try:
        settings = get_handicap_settings()
        raw = settings.get("last_gg_sync")
        if raw:
            persisted = json.loads(raw)
    except Exception:
        logger.debug("Failed to load persisted GG sync results", exc_info=True)

    merged = {**persisted, **_gg_sync_jobs}
    return jsonify(merged)


# ---------------------------------------------------------------------------
# Routes — Handicap Email Cards
# ---------------------------------------------------------------------------

@app.route("/api/handicaps/preview-email", methods=["POST"])
@require_role("manager")
def api_handicap_preview_email():
    """Preview a handicap card email for a player."""
    data = request.get_json(silent=True) or {}
    player_name = (data.get("player_name") or "").strip()
    if not player_name:
        return jsonify({"error": "player_name is required"}), 400

    card_data = build_handicap_card_data(player_name)
    html = build_handicap_card_html(card_data)

    first = card_data.get("first_name") or ""
    last = card_data.get("last_name") or ""
    display = f"{first} {last}".strip() or player_name
    subject = f"TGF Handicap Update \u2014 {display}"

    return jsonify({
        "html": html,
        "subject": subject,
        "email": card_data.get("email") or "",
        "has_email": bool(card_data.get("email")),
        "has_index": card_data.get("handicap_index_9") is not None,
        "player_name": player_name,
    })


@app.route("/api/handicaps/send-email", methods=["POST"])
@require_role("manager")
def api_handicap_send_email():
    """Send a handicap card email to a single player."""
    data = request.get_json(silent=True) or {}
    player_name = (data.get("player_name") or "").strip()
    if not player_name:
        return jsonify({"error": "player_name is required"}), 400

    card_data = build_handicap_card_data(player_name)

    email = card_data.get("email") or ""
    if not email:
        return jsonify({"error": f"No email address found for {player_name}"}), 400

    if card_data.get("handicap_index_9") is None:
        return jsonify({"error": f"{player_name} does not have a handicap index yet"}), 400

    html = build_handicap_card_html(card_data)

    first = card_data.get("first_name") or ""
    last = card_data.get("last_name") or ""
    display = f"{first} {last}".strip() or player_name
    subject = f"TGF Handicap Update \u2014 {display}"

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_address = os.getenv("EMAIL_ADDRESS")

    if not all([tenant_id, client_id, client_secret, from_address]):
        return jsonify({"error": "Email credentials not configured on server"}), 500

    ok = send_mail_graph(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        from_address=from_address,
        to_address=email,
        subject=subject,
        html_body=html,
    )

    status = "sent" if ok else "failed"
    try:
        log_message({
            "event_name": "handicap-card",
            "channel": "email",
            "recipient_name": player_name,
            "recipient_address": email,
            "subject": subject,
            "body_preview": f"Handicap card: {card_data.get('handicap_index_9')}N",
            "status": status,
            "sent_by": session.get("role", "unknown"),
        })
    except Exception:
        logger.warning("Failed to log handicap card email", exc_info=True)

    if ok:
        return jsonify({"status": "ok", "email": email})
    return jsonify({"error": "Failed to send email — check server logs"}), 500


@app.route("/api/handicaps/send-bulk-email", methods=["POST"])
@require_role("manager")
def api_handicap_send_bulk_email():
    """Send handicap card emails to eligible players.

    Filters: chapter (optional), event_name (optional).
    When event_name is given, only players registered for that event
    who also have an established TGF handicap will receive cards.
    """
    import time as _time

    data = request.get_json(silent=True) or {}
    chapter = (data.get("chapter") or "").strip() or None
    event_name = (data.get("event_name") or "").strip() or None

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_address = os.getenv("EMAIL_ADDRESS")

    if not all([tenant_id, client_id, client_secret, from_address]):
        return jsonify({"error": "Email credentials not configured on server"}), 500

    export = get_handicap_export_data(chapter=chapter)
    eligible_rows = export.get("rows") or []

    # If filtering by event, restrict to players registered for that event
    # and compute event-specific skip counts
    skipped_no_email = 0
    skipped_no_index = 0
    if event_name:
        all_items = get_all_items()
        aliases = get_all_event_aliases()
        # Collect customer names registered for this event (active only)
        event_customers = set()
        for item in all_items:
            iname = item.get("item_name") or ""
            if iname.lower() == event_name.lower() or (aliases.get(iname) or "").lower() == event_name.lower():
                if item.get("transaction_status") in (None, "active", "rsvp_only", "gg_rsvp"):
                    cname = (item.get("customer") or "").strip().lower()
                    if cname:
                        event_customers.add(cname)

        # Build player_name → customer_name map from handicap links
        conn = get_connection()
        try:
            links = conn.execute(
                "SELECT player_name, customer_name FROM handicap_player_links "
                "WHERE customer_name IS NOT NULL"
            ).fetchall()
        finally:
            conn.close()
        player_to_customer = {r["player_name"]: r["customer_name"] for r in links}

        # Filter eligible rows to only those whose linked customer is in the event
        eligible_rows = [
            r for r in eligible_rows
            if player_to_customer.get(r["player_name"], "").strip().lower() in event_customers
        ]

        # Count event-specific skips: event registrants not in eligible list
        eligible_customers = {
            player_to_customer.get(r["player_name"], "").strip().lower()
            for r in eligible_rows
        }
        for cname_l in event_customers:
            if cname_l not in eligible_customers:
                skipped_no_index += 1  # no handicap, no link, or no email
    else:
        skipped_no_email = len(export.get("no_email") or [])
        skipped_no_index = len(export.get("no_index") or [])

    sent = 0
    failed = 0
    errors = []
    role = session.get("role", "unknown")

    for i, row in enumerate(eligible_rows):
        pname = row["player_name"]
        email = row.get("email") or ""
        if not email:
            continue

        try:
            card_data = build_handicap_card_data(pname)
            if card_data.get("handicap_index_9") is None:
                continue

            html = build_handicap_card_html(card_data)
            first = card_data.get("first_name") or ""
            last = card_data.get("last_name") or ""
            display = f"{first} {last}".strip() or pname
            subject = f"TGF Handicap Update \u2014 {display}"

            ok = send_mail_graph(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                from_address=from_address,
                to_address=email,
                subject=subject,
                html_body=html,
            )

            status = "sent" if ok else "failed"
            if ok:
                sent += 1
            else:
                failed += 1
                errors.append({"player": pname, "email": email, "error": "send_mail_graph returned False"})

            try:
                log_message({
                    "event_name": "handicap-card",
                    "channel": "email",
                    "recipient_name": pname,
                    "recipient_address": email,
                    "subject": subject,
                    "body_preview": f"Handicap card: {card_data.get('handicap_index_9')}N",
                    "status": status,
                    "sent_by": role,
                })
            except Exception:
                logger.warning("Failed to log handicap card email for %s", pname, exc_info=True)

        except Exception as exc:
            failed += 1
            errors.append({"player": pname, "email": email, "error": str(exc)})

        # Throttle to avoid rate limiting (300ms between sends)
        if i < len(eligible_rows) - 1:
            _time.sleep(0.3)

    return jsonify({
        "status": "ok" if failed == 0 else "partial",
        "sent": sent,
        "failed": failed,
        "skipped_no_email": skipped_no_email,
        "skipped_no_index": skipped_no_index,
        "total_eligible": len(eligible_rows),
        "errors": errors[:20],  # limit error details
    })


# ---------------------------------------------------------------------------
# Routes — Season Contests
# ---------------------------------------------------------------------------

@app.route("/api/season-contests")
@require_role("manager")
def api_season_contests():
    """List season contest enrollments with optional filters."""
    from email_parser.database import get_season_contest_enrollments
    contest_type = request.args.get("contest_type")
    chapter = request.args.get("chapter")
    season = request.args.get("season")
    enrollments = get_season_contest_enrollments(contest_type, chapter, season)
    return jsonify(enrollments)


@app.route("/api/season-contests/sync", methods=["POST"])
@require_role("manager")
def api_sync_season_contests():
    """Scan all items and enroll customers in season contests."""
    from email_parser.database import sync_season_contests_from_items
    result = sync_season_contests_from_items()
    return jsonify(result)


@app.route("/api/season-contests/customer/<path:customer_name>")
@require_role("manager")
def api_customer_season_contests(customer_name):
    """Get season contest enrollments for a specific customer."""
    from email_parser.database import get_customer_season_contests
    enrollments = get_customer_season_contests(customer_name)
    return jsonify(enrollments)


# ---------------------------------------------------------------------------
# Routes — Authentication
# ---------------------------------------------------------------------------
@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    """Authenticate with a PIN and set the session role."""
    if not _check_login_rate_limit():
        return jsonify({"error": "Too many login attempts. Please try again in 15 minutes."}), 429

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


# ═══════════════════════════════════════════════════════════════════════════
# Accounting Module — Multi-Entity Bookkeeping
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/accounting")
def accounting_page():
    """Multi-entity accounting dashboard (admin only)."""
    if session.get("role") != "admin":
        return render_template("index.html")
    return render_template("accounting.html")


# ── Entities ──────────────────────────────────────────────────────────────

@app.route("/api/accounting/entities")
@require_role("admin")
def api_acct_entities():
    return jsonify(get_all_acct_entities())


@app.route("/api/accounting/entities", methods=["POST"])
@require_role("admin")
def api_acct_create_entity():
    d = request.json or {}
    if not d.get("name") or not d.get("short_name"):
        return jsonify({"error": "name and short_name required"}), 400
    try:
        return jsonify(create_acct_entity(d["name"], d["short_name"], d.get("color", "#2563eb")))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/accounting/entities/<int:eid>", methods=["PATCH"])
@require_role("admin")
def api_acct_update_entity(eid):
    d = request.json or {}
    return jsonify(update_acct_entity(eid, **d))


# ── Categories ────────────────────────────────────────────────────────────

@app.route("/api/accounting/categories")
@require_role("admin")
def api_acct_categories():
    entity_id = request.args.get("entity_id", type=int)
    cat_type = request.args.get("type")
    return jsonify(get_acct_categories(entity_id=entity_id, cat_type=cat_type))


@app.route("/api/accounting/categories", methods=["POST"])
@require_role("admin")
def api_acct_create_category():
    d = request.json or {}
    if not d.get("name") or not d.get("type"):
        return jsonify({"error": "name and type required"}), 400
    return jsonify(create_acct_category(
        d["name"], d["type"], d.get("entity_id"), d.get("parent_id"), d.get("icon"),
    ))


@app.route("/api/accounting/categories/<int:cid>", methods=["PATCH"])
@require_role("admin")
def api_acct_update_category(cid):
    d = request.json or {}
    return jsonify(update_acct_category(cid, **d))


@app.route("/api/accounting/categories/<int:cid>", methods=["DELETE"])
@require_role("admin")
def api_acct_delete_category(cid):
    delete_acct_category(cid)
    return jsonify({"status": "ok"})


# ── Accounts ──────────────────────────────────────────────────────────────

@app.route("/api/accounting/accounts")
@require_role("admin")
def api_acct_accounts():
    entity_id = request.args.get("entity_id", type=int)
    return jsonify(get_acct_accounts(entity_id=entity_id))


@app.route("/api/accounting/accounts", methods=["POST"])
@require_role("admin")
def api_acct_create_account():
    d = request.json or {}
    if not d.get("name") or not d.get("account_type"):
        return jsonify({"error": "name and account_type required"}), 400
    return jsonify(create_acct_account(
        d["name"], d["account_type"], d.get("entity_id"),
        d.get("institution"), d.get("last_four"), d.get("opening_balance", 0),
    ))


@app.route("/api/accounting/accounts/<int:aid>", methods=["PATCH"])
@require_role("admin")
def api_acct_update_account(aid):
    d = request.json or {}
    return jsonify(update_acct_account(aid, **d))


@app.route("/api/accounting/accounts/balances")
@require_role("admin")
def api_acct_account_balances():
    return jsonify(get_acct_account_balances())


# ── Transactions ──────────────────────────────────────────────────────────

@app.route("/api/accounting/vendors", methods=["POST"])
@require_role("admin")
def api_acct_create_vendor():
    """Create a new vendor (customer with vendor role) for transaction linking."""
    from email_parser.database import _connect
    d = request.json or {}
    name = (d.get("name") or "").strip()
    phone = (d.get("phone") or "").strip() or None
    if not name:
        return jsonify({"error": "name is required"}), 400

    with _connect() as conn:
        # Check if a vendor with this company name already exists
        existing = conn.execute(
            "SELECT customer_id FROM customers WHERE LOWER(COALESCE(company_name,'')) = LOWER(?) LIMIT 1",
            (name,),
        ).fetchone()

        if existing:
            cid = existing["customer_id"]
        else:
            cursor = conn.execute(
                """INSERT INTO customers
                       (first_name, last_name, company_name, phone, acquisition_source, account_status)
                   VALUES ('', ?, ?, ?, 'vendor', 'active')""",
                (name, name, phone),
            )
            cid = cursor.lastrowid

        conn.execute(
            "INSERT OR IGNORE INTO customer_roles (customer_id, role_type) VALUES (?, 'vendor')",
            (cid,),
        )
        conn.commit()

        row = conn.execute(
            """SELECT c.customer_id, c.first_name, c.last_name, c.company_name,
                      c.current_player_status, c.chapter, 1 as is_vendor
               FROM customers c WHERE c.customer_id = ?""",
            (cid,),
        ).fetchone()

    data = dict(row)
    data["display_name"] = data.get("company_name") or f"{data.get('first_name','')} {data.get('last_name','')}".strip()
    return jsonify(data), 201


@app.route("/api/accounting/customers")
@require_role("admin")
def api_acct_customers():
    """Return all customers and vendors for transaction linking."""
    from email_parser.database import _connect
    with _connect() as conn:
        rows = conn.execute(
            """SELECT c.customer_id, c.first_name, c.last_name,
                      c.company_name, c.current_player_status, c.chapter,
                      EXISTS(
                          SELECT 1 FROM customer_roles r
                          WHERE r.customer_id = c.customer_id AND r.role_type = 'vendor'
                      ) as is_vendor
               FROM customers c
               WHERE c.account_status = 'active'
               ORDER BY c.last_name COLLATE NOCASE, c.first_name COLLATE NOCASE"""
        ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["display_name"] = d.get("company_name") or f"{d.get('first_name','')} {d.get('last_name','')}".strip()
        result.append(d)
    return jsonify(result)


@app.route("/api/accounting/smart-fill", methods=["POST"])
@require_role("admin")
def api_acct_smart_fill():
    """Auto-assign accounts and default splits to unsplit transactions."""
    from email_parser.database import _connect
    d = request.json or {}
    dry_run = d.get("dry_run", True)

    with _connect() as conn:
        # Find transactions with no splits
        unsplit = conn.execute(
            """SELECT t.id, t.type, t.source, t.total_amount, t.account_id,
                      t.event_name, t.description
               FROM acct_transactions t
               WHERE t.total_amount > 0
                 AND t.type IN ('income', 'expense')
                 AND COALESCE(t.status, 'active') = 'active'
                 AND NOT EXISTS (SELECT 1 FROM acct_splits s WHERE s.transaction_id = t.id)
               ORDER BY t.date DESC"""
        ).fetchall()

        # Look up TGF Checking account id
        tgf_checking = conn.execute(
            "SELECT id FROM acct_accounts WHERE LOWER(name) LIKE '%tgf checking%' LIMIT 1"
        ).fetchone()
        tgf_checking_id = tgf_checking["id"] if tgf_checking else None

        # Look up Venmo account
        venmo_acct = conn.execute(
            "SELECT id FROM acct_accounts WHERE LOWER(name) LIKE '%venmo%' OR account_type='venmo' LIMIT 1"
        ).fetchone()
        venmo_id = venmo_acct["id"] if venmo_acct else None

        # Look up TGF entity
        tgf_entity = conn.execute(
            "SELECT id FROM acct_entities WHERE LOWER(short_name) = 'tgf' LIMIT 1"
        ).fetchone()
        tgf_entity_id = tgf_entity["id"] if tgf_entity else None

        default_entity = conn.execute("SELECT id FROM acct_entities LIMIT 1").fetchone()
        default_entity_id = default_entity["id"] if default_entity else None

        # Look up "Event Revenue" income category
        event_rev_cat = conn.execute(
            "SELECT id FROM acct_categories WHERE type='income' AND LOWER(name) LIKE '%event revenue%' LIMIT 1"
        ).fetchone()
        event_rev_cat_id = event_rev_cat["id"] if event_rev_cat else None

        applied = []
        for t in unsplit:
            source = (t["source"] or "").lower()
            desc = (t["description"] or "").lower()

            # Determine account to assign
            new_account_id = t["account_id"]
            if not new_account_id:
                if source == "godaddy" or desc.startswith("godaddy order"):
                    new_account_id = tgf_checking_id
                elif source == "venmo":
                    new_account_id = venmo_id

            # Determine split params
            entity_id = tgf_entity_id if t["type"] == "income" else default_entity_id
            category_id = event_rev_cat_id if t["type"] == "income" else None

            info = {
                "id": t["id"],
                "description": t["description"],
                "amount": t["total_amount"],
                "type": t["type"],
                "source": t["source"],
                "new_account_id": new_account_id,
                "entity_id": entity_id,
                "category_id": category_id,
            }
            applied.append(info)

            if not dry_run:
                # Update account if changed
                if new_account_id and new_account_id != t["account_id"]:
                    conn.execute("UPDATE acct_transactions SET account_id=? WHERE id=?",
                                 (new_account_id, t["id"]))
                # Create a single split for the full amount
                conn.execute(
                    """INSERT INTO acct_splits (transaction_id, entity_id, category_id, amount, memo)
                       VALUES (?, ?, ?, ?, '')""",
                    (t["id"], entity_id, category_id, t["total_amount"])
                )

        if not dry_run:
            conn.commit()

    return jsonify({"count": len(applied), "transactions": applied if dry_run else []})


@app.route("/api/accounting/transactions")
@require_role("admin")
def api_acct_transactions():
    return jsonify(get_acct_transactions(
        entity_id=request.args.get("entity_id", type=int),
        account_id=request.args.get("account_id", type=int),
        category_id=request.args.get("category_id", type=int),
        start_date=request.args.get("start_date"),
        end_date=request.args.get("end_date"),
        search=request.args.get("search"),
        txn_type=request.args.get("type"),
        limit=request.args.get("limit", 200, type=int),
        offset=request.args.get("offset", 0, type=int),
    ))


@app.route("/api/accounting/transactions/unified")
@require_role("admin")
def api_acct_unified_transactions():
    return jsonify(get_unified_transactions(
        entity_id=request.args.get("entity_id", type=int),
        account_id=request.args.get("account_id", type=int),
        category_id=request.args.get("category_id", type=int),
        start_date=request.args.get("start_date"),
        end_date=request.args.get("end_date"),
        search=request.args.get("search"),
        txn_type=request.args.get("type"),
        source=request.args.get("source"),
        review_status=request.args.get("review_status"),
        ledger_status=request.args.get("ledger_status"),
        limit=request.args.get("limit", 200, type=int),
        offset=request.args.get("offset", 0, type=int),
    ))


@app.route("/api/accounting/transactions/<int:tid>")
@require_role("admin")
def api_acct_transaction(tid):
    txn = get_acct_transaction(tid)
    if not txn:
        return jsonify({"error": "not found"}), 404
    return jsonify(txn)


@app.route("/api/accounting/transactions", methods=["POST"])
@require_role("admin")
def api_acct_create_transaction():
    d = request.json or {}
    required = ["date", "description", "total_amount", "type"]
    for f in required:
        if f not in d:
            return jsonify({"error": f"{f} is required"}), 400
    splits = d.get("splits", [])
    if not splits:
        return jsonify({"error": "At least one split is required"}), 400
    # Validate split total matches transaction total
    split_total = sum(s.get("amount", 0) for s in splits)
    if abs(split_total - float(d["total_amount"])) > 0.01:
        return jsonify({"error": f"Split total ({split_total:.2f}) doesn't match transaction amount ({d['total_amount']})"}), 400
    try:
        txn = _create_acct_ledger_entry(
            date=d["date"], description=d["description"],
            total_amount=float(d["total_amount"]), txn_type=d["type"],
            account_id=d.get("account_id"), transfer_to_account_id=d.get("transfer_to_account_id"),
            notes=d.get("notes"), receipt_path=d.get("receipt_path"),
            source=d.get("source", "manual"), source_ref=d.get("source_ref"),
            splits=splits, tag_ids=d.get("tag_ids"),
            customer_id=d.get("customer_id"),
        )
        return jsonify(txn), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/accounting/transactions/<int:tid>", methods=["PUT"])
@require_role("admin")
def api_acct_update_transaction(tid):
    d = request.json or {}
    splits = d.get("splits")
    if splits is not None and "total_amount" in d:
        split_total = sum(s.get("amount", 0) for s in splits)
        if abs(split_total - float(d["total_amount"])) > 0.01:
            return jsonify({"error": f"Split total ({split_total:.2f}) doesn't match transaction amount ({d['total_amount']})"}), 400
    try:
        txn = update_acct_transaction(tid, **d)
        return jsonify(txn)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/accounting/transactions/<int:tid>", methods=["DELETE"])
@require_role("admin")
def api_acct_delete_transaction(tid):
    delete_acct_transaction(tid)
    return jsonify({"status": "ok"})


@app.route("/api/accounting/transactions/<int:tid>/reconcile", methods=["POST"])
@require_role("admin")
def api_acct_reconcile(tid):
    d = request.json or {}
    return jsonify(reconcile_acct_transaction(tid, d.get("reconciled", True)))


# ── Tags ──────────────────────────────────────────────────────────────────

@app.route("/api/accounting/tags")
@require_role("admin")
def api_acct_tags():
    return jsonify(get_acct_tags())


@app.route("/api/accounting/tags", methods=["POST"])
@require_role("admin")
def api_acct_create_tag():
    d = request.json or {}
    if not d.get("name"):
        return jsonify({"error": "name required"}), 400
    try:
        return jsonify(create_acct_tag(d["name"], d.get("color", "#6b7280")))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/accounting/tags/<int:tid>", methods=["DELETE"])
@require_role("admin")
def api_acct_delete_tag(tid):
    delete_acct_tag(tid)
    return jsonify({"status": "ok"})


# ── Reports ───────────────────────────────────────────────────────────────

@app.route("/api/accounting/reports/summary")
@require_role("admin")
def api_acct_report_summary():
    return jsonify(get_acct_summary(
        entity_id=request.args.get("entity_id", type=int),
        start_date=request.args.get("start_date"),
        end_date=request.args.get("end_date"),
    ))


@app.route("/api/accounting/reports/monthly")
@require_role("admin")
def api_acct_report_monthly():
    return jsonify(get_acct_monthly_totals(
        entity_id=request.args.get("entity_id", type=int),
        months=request.args.get("months", 12, type=int),
    ))


@app.route("/api/accounting/reports/categories")
@require_role("admin")
def api_acct_report_categories():
    return jsonify(get_acct_category_breakdown(
        entity_id=request.args.get("entity_id", type=int),
        txn_type=request.args.get("type", "expense"),
        start_date=request.args.get("start_date"),
        end_date=request.args.get("end_date"),
    ))


# ── CSV Import ────────────────────────────────────────────────────────────

@app.route("/api/accounting/import/preview", methods=["POST"])
@require_role("admin")
def api_acct_import_preview():
    if "file" in request.files:
        csv_text = request.files["file"].read().decode("utf-8", errors="replace")
    elif request.json and "csv_text" in request.json:
        csv_text = request.json["csv_text"]
    else:
        return jsonify({"error": "No CSV data provided"}), 400
    # Auto-detect columns from headers; caller can override with explicit indices
    d = request.form if request.files else (request.json or {})
    overrides = {}
    for key in ("date_col", "description_col", "amount_col", "category_col", "memo_col"):
        val = d.get(key)
        if val is not None and val != "":
            overrides[key] = int(val)
    result = preview_acct_csv(csv_text, **overrides)
    return jsonify(result)


@app.route("/api/accounting/import/commit", methods=["POST"])
@require_role("admin")
def api_acct_import_commit():
    d = request.json or {}
    if not d.get("rows") or not d.get("account_id") or not d.get("entity_id"):
        return jsonify({"error": "rows, account_id, and entity_id required"}), 400
    result = import_acct_csv(
        d["rows"], d["account_id"], d["entity_id"],
        transfer_account_id=d.get("transfer_account_id"),
    )
    return jsonify(result)


# ── Recurring ─────────────────────────────────────────────────────────────

@app.route("/api/accounting/recurring")
@require_role("admin")
def api_acct_recurring():
    return jsonify(get_acct_recurring())


@app.route("/api/accounting/recurring", methods=["POST"])
@require_role("admin")
def api_acct_create_recurring():
    d = request.json or {}
    required = ["description", "amount", "type", "entity_id", "frequency", "next_date"]
    for f in required:
        if f not in d:
            return jsonify({"error": f"{f} required"}), 400
    return jsonify(create_acct_recurring(
        d["description"], float(d["amount"]), d["type"], d["entity_id"],
        d["frequency"], d["next_date"], d.get("category_id"), d.get("account_id"),
    ))


@app.route("/api/accounting/recurring/<int:rid>", methods=["DELETE"])
@require_role("admin")
def api_acct_delete_recurring(rid):
    delete_acct_recurring(rid)
    return jsonify({"status": "ok"})


# ── Receipt Upload ────────────────────────────────────────────────────────

@app.route("/api/accounting/upload-receipt", methods=["POST"])
@require_role("admin")
def api_acct_upload_receipt():
    """Upload a receipt image/PDF and return the file path."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No filename"}), 400
    # Save to receipts directory
    receipts_dir = os.path.join(os.path.dirname(DB_PATH), "receipts")
    os.makedirs(receipts_dir, exist_ok=True)
    safe_name = f"{secrets.token_hex(8)}_{f.filename}"
    path = os.path.join(receipts_dir, safe_name)
    f.save(path)
    return jsonify({"path": path, "filename": safe_name})


# ── AI Bookkeeper ─────────────────────────────────────────────────────────

@app.route("/api/accounting/ai/categorize", methods=["POST"])
@require_role("admin")
def api_acct_ai_categorize():
    """Auto-categorize transactions using learned rules + AI."""
    d = request.json or {}
    descriptions = d.get("descriptions", [])
    txn_types = d.get("types", [])
    if not descriptions:
        return jsonify({"error": "descriptions required"}), 400
    results = auto_categorize_transactions(descriptions, txn_types)
    return jsonify(results)


@app.route("/api/accounting/ai/review-queue")
@require_role("admin")
def api_acct_ai_review_queue():
    """Return transactions needing categorization."""
    return jsonify(get_acct_review_queue())


@app.route("/api/accounting/ai/stats")
@require_role("admin")
def api_acct_ai_stats():
    """Return categorization coverage stats."""
    return jsonify(get_acct_categorization_stats())


@app.route("/api/accounting/ai/batch")
@require_role("admin")
def api_acct_ai_batch():
    """Return a batch of pending expense_transactions with AI suggestions pre-populated."""
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))
    return jsonify(get_expense_batch_preview(limit=limit, offset=offset))


@app.route("/api/accounting/ai/batch-approve", methods=["POST"])
@require_role("admin")
def api_acct_ai_batch_approve():
    """Approve and promote selected expense_transactions into the ledger."""
    d = request.json or {}
    items = d.get("items", [])
    if not items:
        return jsonify({"error": "items required"}), 400
    result = batch_approve_expenses(items)
    return jsonify(result)


@app.route("/api/accounting/liabilities")
@require_role("admin")
def api_accounting_liabilities():
    """Return all liability buckets for the Liabilities Dashboard."""
    return jsonify(get_accounting_liabilities())


@app.route("/api/accounting/month-close")
@require_role("admin")
def api_accounting_month_close():
    """Return month-close checklist status and financial position."""
    return jsonify(get_month_close_status())


@app.route("/api/accounting/liabilities/update", methods=["POST"])
@require_role("admin")
def api_accounting_liabilities_update():
    """Update a manual liability value."""
    d = request.json or {}
    key = d.get("key", "").strip()
    value = d.get("value")
    allowed_keys = {
        "hio_pot", "season_contests_total", "lone_star_cup_shirts",
        "chapter_manager_payouts", "grandparent_loan", "member_credits_2025",
        "irs_balance", "chase_biz_7680", "chase_sapphire_6159",
    }
    if not key or key not in allowed_keys:
        return jsonify({"error": "invalid key"}), 400
    try:
        value = float(value)
    except (TypeError, ValueError):
        return jsonify({"error": "value must be a number"}), 400
    set_coo_manual_value(key, value)
    return jsonify({"ok": True, "key": key, "value": value})


# ── Contractor Payouts ────────────────────────────────────────────────────────

@app.route("/api/accounting/contractors")
@require_role("admin")
def api_contractors_list():
    return jsonify(get_contractor_payouts())


@app.route("/api/accounting/contractors/managers")
@require_role("admin")
def api_contractors_managers():
    return jsonify(get_contractor_managers())


@app.route("/api/accounting/contractors", methods=["POST"])
@require_role("admin")
def api_contractors_add():
    d = request.json or {}
    mgr_id = d.get("manager_customer_id")
    if not mgr_id:
        return jsonify({"error": "manager_customer_id required"}), 400
    try:
        amount = float(d.get("amount_owed", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "amount_owed must be a number"}), 400
    new_id = add_contractor_payout(
        manager_customer_id=int(mgr_id),
        event_name=d.get("event_name") or None,
        event_date=d.get("event_date") or None,
        amount_owed=amount,
        chapter_id=d.get("chapter_id") or None,
        notes=d.get("notes") or None,
    )
    return jsonify({"ok": True, "id": new_id})


@app.route("/api/accounting/contractors/<int:payout_id>", methods=["PATCH"])
@require_role("admin")
def api_contractors_update(payout_id):
    d = request.json or {}
    amount_paid = d.get("amount_paid")
    if amount_paid is not None:
        try:
            amount_paid = float(amount_paid)
        except (TypeError, ValueError):
            return jsonify({"error": "amount_paid must be a number"}), 400
    ok = update_contractor_payout(
        payout_id=payout_id,
        amount_paid=amount_paid,
        status=d.get("status") or None,
        payment_method=d.get("payment_method") or None,
        notes=d.get("notes"),
    )
    return jsonify({"ok": ok})


@app.route("/api/accounting/contractors/<int:payout_id>", methods=["DELETE"])
@require_role("admin")
def api_contractors_delete(payout_id):
    ok = delete_contractor_payout(payout_id)
    return jsonify({"ok": ok})


@app.route("/api/accounting/ai/bulk-categorize", methods=["POST"])
@require_role("admin")
def api_acct_ai_bulk_categorize():
    """AI-categorize all uncategorized transactions in one shot."""
    queue = get_acct_review_queue()
    if not queue:
        return jsonify({"updated": 0, "message": "All transactions are categorized"})

    descriptions = [t["description"] for t in queue]
    types = [t["type"] for t in queue]
    suggestions = auto_categorize_transactions(descriptions, types)

    updated = 0
    for txn, suggestion in zip(queue, suggestions):
        if not suggestion or suggestion["confidence"] == "none":
            continue
        cat_id = suggestion.get("category_id")
        ent_id = suggestion.get("entity_id")
        if not cat_id:
            continue

        # Update the first split with the suggested category + entity
        from email_parser.database import _connect
        with _connect() as conn:
            split = conn.execute(
                "SELECT id, entity_id FROM acct_splits WHERE transaction_id = ? LIMIT 1",
                (txn["id"],),
            ).fetchone()
            if split:
                updates = {"category_id": cat_id}
                if ent_id:
                    updates["entity_id"] = ent_id
                evt_id = suggestion.get("event_id")
                if evt_id:
                    updates["event_id"] = evt_id
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE acct_splits SET {set_clause} WHERE id = ?",
                    (*updates.values(), split["id"]),
                )
                conn.commit()
                updated += 1

    return jsonify({"updated": updated, "total": len(queue)})


# ── Reset & Account Rules ─────────────────────────────────────────────────

@app.route("/api/accounting/reset", methods=["POST"])
@require_role("admin")
def api_acct_reset():
    """Wipe all accounting data and re-seed entities + categories."""
    result = reset_acct_data()
    return jsonify(result)


@app.route("/api/accounting/accounts/<int:aid>/rules")
@require_role("admin")
def api_acct_get_rules(aid):
    return jsonify(get_acct_account_rules(aid))


@app.route("/api/accounting/accounts/<int:aid>/rules", methods=["POST"])
@require_role("admin")
def api_acct_set_rule(aid):
    d = request.json or {}
    if not d.get("rule_type") or "rule_value" not in d:
        return jsonify({"error": "rule_type and rule_value required"}), 400
    set_acct_account_rule(aid, d["rule_type"], d["rule_value"])
    return jsonify({"status": "ok"})


@app.route("/api/accounting/keyword-rules")
@require_role("admin")
def api_acct_keyword_rules():
    return jsonify(get_acct_keyword_rules())


@app.route("/api/accounting/keyword-rules", methods=["POST"])
@require_role("admin")
def api_acct_create_keyword_rule():
    d = request.json or {}
    if not d.get("keyword"):
        return jsonify({"error": "keyword is required"}), 400
    return jsonify(create_acct_keyword_rule(
        keyword=d["keyword"],
        match_type=d.get("match_type", "contains"),
        category_id=d.get("category_id"),
        entity_id=d.get("entity_id"),
    ))


@app.route("/api/accounting/keyword-rules/<int:rule_id>", methods=["PATCH"])
@require_role("admin")
def api_acct_update_keyword_rule(rule_id):
    return jsonify(update_acct_keyword_rule(rule_id, request.json or {}))


@app.route("/api/accounting/keyword-rules/<int:rule_id>", methods=["DELETE"])
@require_role("admin")
def api_acct_delete_keyword_rule(rule_id):
    return jsonify(delete_acct_keyword_rule(rule_id))


@app.route("/api/accounting/events-list")
@require_role("admin")
def api_acct_events_list():
    """Return events from the events directory for linking to accounting transactions."""
    events = get_all_events()
    return jsonify([{
        "id": e["id"], "item_name": e["item_name"],
        "event_date": e.get("event_date"), "course": e.get("course"),
        "chapter": e.get("chapter"),
    } for e in events])


# ── Allocations ───────────────────────────────────────────────────────────

@app.route("/api/accounting/allocations")
@require_role("admin")
def api_acct_allocations():
    """Return allocation records with totals grouped by bucket."""
    return jsonify(get_acct_allocations(
        month=request.args.get("month"),
        event=request.args.get("event"),
        chapter=request.args.get("chapter"),
    ))


@app.route("/api/accounting/allocations/calculate", methods=["POST"])
@require_role("admin")
def api_acct_calculate_allocation():
    """Calculate allocation for a specific order."""
    d = request.json or {}
    order_id = d.get("order_id")
    if not order_id:
        return jsonify({"error": "order_id required"}), 400
    try:
        result = calculate_order_allocation(order_id)
        if not result:
            return jsonify({"error": f"No active items found for order {order_id}"}), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/accounting/allocations/calculate-all", methods=["POST"])
@require_role("admin")
def api_acct_calculate_all_allocations():
    """Calculate allocations for all orders that don't have allocations yet."""
    from email_parser.database import _connect
    with _connect() as conn:
        order_ids = conn.execute(
            """SELECT DISTINCT order_id FROM items
               WHERE order_id IS NOT NULL AND order_id != ''
                 AND COALESCE(transaction_status, 'active') = 'active'
                 AND order_id NOT IN (SELECT DISTINCT order_id FROM acct_allocations)
               ORDER BY order_date DESC"""
        ).fetchall()
    calculated = 0
    errors = 0
    for row in order_ids:
        try:
            calculate_order_allocation(row["order_id"])
            calculated += 1
        except Exception:
            errors += 1
    return jsonify({"calculated": calculated, "errors": errors, "total_orders": len(order_ids)})


# ── Event Financial Summary (Unified Financial Model, Issue #242) ─────────

@app.route("/api/events/<event_name>/financial-summary")
@require_role("manager")
def api_event_financial_summary(event_name):
    """Return unified financial summary for an event from the accounting system."""
    try:
        return jsonify(get_event_financial_summary(event_name))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/accounting/backfill", methods=["POST"])
@require_role("admin")
def api_backfill_financials():
    """Backfill accounting entries for existing items missing them (Issue #242)."""
    try:
        result = backfill_financial_entries()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/accounting/backfill-acct-transactions", methods=["POST"])
@require_role("admin")
def api_backfill_acct_transactions():
    """Backfill flat acct_transactions entries for all 2026 items."""
    try:
        result = backfill_acct_transactions()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/accounting/verify-event/<event_name>")
@require_role("manager")
def api_verify_event_accounting(event_name):
    """Verify acct_transactions totals for an event."""
    from email_parser.database import _connect
    try:
        with _connect() as conn:
            rows = conn.execute(
                """SELECT entry_type, category, source,
                          COUNT(*) as count,
                          COALESCE(SUM(amount), 0) as total
                   FROM acct_transactions
                   WHERE event_name = ? COLLATE NOCASE
                   AND COALESCE(status, 'active') = 'active'
                   AND entry_type IS NOT NULL
                   GROUP BY entry_type, category, source
                   ORDER BY entry_type, category""",
                (event_name,),
            ).fetchall()
            breakdown = [dict(r) for r in rows]

            income = sum(r["total"] for r in breakdown if r["entry_type"] == "income")
            fees = sum(r["total"] for r in breakdown if r["entry_type"] == "expense" and r["category"] == "processing_fee")
            refunds = sum(r["total"] for r in breakdown if r["entry_type"] == "expense" and r["category"] == "refund")
            contra = sum(r["total"] for r in breakdown if r["entry_type"] == "contra")
            net = round(income - fees - refunds - contra, 2)

            summary = get_event_financial_summary(event_name)

            return jsonify({
                "event_name": event_name,
                "acct_transactions_breakdown": breakdown,
                "totals": {
                    "income": round(income, 2),
                    "processing_fees": round(fees, 2),
                    "refunds": round(refunds, 2),
                    "contra": round(contra, 2),
                    "net": net,
                },
                "financial_summary": summary,
                "accounting_verified": summary.get("accounting_verified", False),
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit/scan-price-mismatches", methods=["POST"])
@require_role("admin")
def api_scan_price_mismatches():
    """Scan all items for side_games / item_price mismatches and create parse warnings."""
    try:
        result = scan_price_games_mismatches()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Expense Transactions & Action Items ───────────────────────────────────

@app.route("/api/accounting/expense-transactions")
@require_role("admin")
def api_expense_transactions():
    return jsonify(get_expense_transactions(
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        source_type=request.args.get("source_type"),
        review_status=request.args.get("review_status"),
        event_name=request.args.get("event_name"),
        limit=request.args.get("limit", 100, type=int),
    ))


@app.route("/api/accounting/expense-transactions/<int:tid>")
@require_role("admin")
def api_get_expense_transaction(tid):
    from email_parser.database import _connect, get_expense_suggestions, suggest_for_merchant
    with _connect() as conn:
        row = conn.execute("SELECT * FROM expense_transactions WHERE id = ?", (tid,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        result = dict(row)
        # Add AI suggestion for pending expenses
        if result.get("review_status") == "pending" and result.get("merchant"):
            suggestion_data = get_expense_suggestions(conn)
            result["suggestion"] = suggest_for_merchant(result["merchant"], suggestion_data)
    return jsonify(result)


@app.route("/api/accounting/expense-transactions/<int:tid>", methods=["PATCH"])
@require_role("admin")
def api_update_expense_transaction(tid):
    d = request.json or {}
    return jsonify(update_expense_transaction(tid, d))


@app.route("/api/accounting/expense-transactions/<int:tid>", methods=["DELETE"])
@require_role("admin")
def api_delete_expense_transaction(tid):
    from email_parser.database import _connect
    with _connect() as conn:
        conn.execute("DELETE FROM expense_transactions WHERE id = ?", (tid,))
        conn.commit()
    return jsonify({"deleted": True})


@app.route("/api/accounting/block-merchant", methods=["POST"])
@require_role("admin")
def api_block_merchant():
    d = request.json or {}
    merchant = (d.get("merchant") or "").strip()
    if not merchant:
        return jsonify({"error": "merchant required"}), 400
    blocked = block_merchant(merchant)
    return jsonify({"blocked": blocked})


@app.route("/api/accounting/action-items")
@require_role("admin")
def api_action_items():
    return jsonify(get_action_items(
        status=request.args.get("status"),
        category=request.args.get("category"),
        limit=request.args.get("limit", 100, type=int),
    ))


@app.route("/api/accounting/action-items/<int:aid>", methods=["PATCH"])
@require_role("admin")
def api_update_action_item(aid):
    d = request.json or {}
    return jsonify(update_action_item(aid, d))


@app.route("/api/accounting/pending-review")
@require_role("admin")
def api_pending_review():
    return jsonify(get_pending_review_count())


@app.route("/api/accounting/classify-email", methods=["POST"])
@require_role("admin")
def api_classify_email():
    """Classify an email (for testing)."""
    d = request.json or {}
    result = classify_email(
        d.get("subject", ""), d.get("from_addr", ""), d.get("body_text", ""),
    )
    return jsonify(result)


@app.route("/api/accounting/check-expense-inbox", methods=["POST"])
@require_role("admin")
def api_check_expense_inbox():
    """Manually trigger expense email processing.

    JSON body options:
        force: true — reprocess all emails (skip dedup for expenses/actions)
        days_back: 7 — how many days to look back (default 14)
    """
    data = request.get_json(silent=True) or {}
    force = data.get("force", False)
    days_back = data.get("days_back", 14)
    try:
        result = check_expense_inbox(force=force, days_back=days_back)
        return jsonify({"status": "ok", "result": result})
    except Exception as e:
        logger.exception("Manual expense inbox check failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/accounting/mail-folders", methods=["GET"])
@require_role("admin")
def api_list_mail_folders():
    """Debug: list all mail folders visible to Graph API."""
    from email_parser.fetcher import _get_graph_token, _request_with_retry, GRAPH_BASE
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    address = os.getenv("EXPENSE_EMAIL_ADDRESS") or os.getenv("RSVP_EMAIL_ADDRESS") or os.getenv("EMAIL_ADDRESS")
    token = _get_graph_token(tenant_id, client_id, client_secret)
    if not token:
        return jsonify({"error": "Could not get token"}), 500
    headers = {"Authorization": f"Bearer {token}"}

    def _list(parent_id=None, depth=0):
        url = (f"{GRAPH_BASE}/users/{address}/mailFolders/{parent_id}/childFolders"
               if parent_id else f"{GRAPH_BASE}/users/{address}/mailFolders")
        try:
            resp = _request_with_retry("get", url, headers=headers, params={"$top": "100"}, timeout=15)
            if resp.status_code != 200:
                return []
            results = []
            for f in resp.json().get("value", []):
                entry = {"name": f["displayName"], "id": f["id"],
                         "total": f.get("totalItemCount", 0), "depth": depth}
                results.append(entry)
                if f.get("childFolderCount", 0) > 0:
                    results.extend(_list(f["id"], depth + 1))
            return results
        except Exception as e:
            return [{"error": str(e)}]

    folders = _list()
    return jsonify({"folders": folders})


@app.route("/api/accounting/expense-inbox-audit", methods=["POST"])
@require_role("admin")
def api_expense_inbox_audit():
    """Preview what's in the inbox without processing — classify only.

    Returns a list of emails with their classification and whether they were already processed.
    JSON body: { days_back: 7 }
    """
    data = request.get_json(silent=True) or {}
    days_back = data.get("days_back", 7)

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    address = os.getenv("EXPENSE_EMAIL_ADDRESS") or os.getenv("RSVP_EMAIL_ADDRESS") or os.getenv("EMAIL_ADDRESS")
    if not all([tenant_id, client_id, client_secret, address]):
        return jsonify({"error": "Azure AD credentials not configured"}), 400

    try:
        emails = fetch_all_emails(
            tenant_id=tenant_id, client_id=client_id, client_secret=client_secret,
            email_address=address, since_date=datetime.now() - timedelta(days=days_back),
            max_emails=300,
            include_subfolders=["2025 Chase", "2025 Venmo", "Payouts", "Invoices"],
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    known_uids = get_known_email_uids()
    conn = get_connection()
    try:
        expense_uids = {r["email_uid"] for r in conn.execute(
            "SELECT email_uid FROM expense_transactions WHERE email_uid IS NOT NULL"
        ).fetchall()}
        action_uids = {r["email_uid"] for r in conn.execute(
            "SELECT email_uid FROM action_items WHERE email_uid IS NOT NULL"
        ).fetchall()}
    finally:
        conn.close()

    results = []
    for e in emails:
        uid = e.get("uid", "")
        status = "new"
        if uid in known_uids:
            status = "order"
        elif uid in expense_uids:
            status = "expense_saved"
        elif uid in action_uids:
            status = "action_saved"
        results.append({
            "subject": e.get("subject", ""),
            "from": e.get("from", ""),
            "date": (e.get("date") or "")[:10],
            "status": status,
        })

    counts = {"order": 0, "expense_saved": 0, "action_saved": 0, "new": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    return jsonify({"total": len(results), "counts": counts, "emails": results})


# ═══════════════════════════════════════════════════════════════════════════
# COO Dashboard
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/coo")
@require_role("admin")
def coo_page():
    return render_template("coo.html")


@app.route("/api/coo/action-items")
@require_role("admin")
def api_coo_action_items():
    return jsonify(get_action_items(
        status=request.args.get("status"),
        category=request.args.get("category"),
    ))


@app.route("/api/coo/action-items/<int:aid>", methods=["PATCH"])
@require_role("admin")
def api_coo_update_action_item(aid):
    d = request.json or {}
    return jsonify(update_action_item(aid, d))


@app.route("/api/coo/action-items/batch-dismiss", methods=["POST"])
@require_role("admin")
def api_coo_batch_dismiss():
    d = request.json or {}
    return jsonify(batch_dismiss_action_items(
        item_ids=d.get("item_ids"),
        category=d.get("category"),
        status_filter=d.get("status_filter", "open"),
    ))


@app.route("/api/coo/action-items/consolidate", methods=["POST"])
@require_role("admin")
def api_coo_consolidate():
    return jsonify(consolidate_action_items())


@app.route("/api/coo/financial-snapshot")
@require_role("admin")
def api_coo_financial_snapshot():
    return jsonify(get_coo_financial_snapshot())


@app.route("/api/coo/manual-values", methods=["POST"])
@require_role("admin")
def api_coo_manual_values():
    d = request.json or {}
    if "key" not in d or "value" not in d:
        return jsonify({"error": "key and value required"}), 400
    set_coo_manual_value(d["key"], float(d["value"]))
    return jsonify({"status": "ok"})


@app.route("/api/coo/review-queue")
@require_role("admin")
def api_coo_review_queue():
    return jsonify(get_coo_review_queue())


@app.route("/api/coo/chat", methods=["POST"])
@require_role("admin")
def api_coo_chat():
    """COO Chat — routes to specialist agent, responds as Chief of Staff.
    Now persists all messages to coo_chat_sessions/coo_chat_messages so the AI
    retains full conversation context across page reloads and sessions."""
    from email_parser.database import route_to_agent, get_coo_agent, log_agent_action
    d = request.json or {}
    user_message = d.get("message", "")
    session_id = d.get("session_id")
    context = d.get("context", {})

    # Legacy support: if caller sends "messages" array instead of "message" string
    if not user_message and d.get("messages"):
        msgs = d["messages"]
        user_message = msgs[-1].get("content", "") if msgs else ""

    if not user_message:
        return jsonify({"error": "message required"}), 400

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500

    # Create or load session
    if session_id:
        session = get_chat_session(session_id)
        if not session:
            session = create_chat_session()
    else:
        session = create_chat_session()
    session_id = session["id"]

    # Save the user message
    add_chat_message(session_id, "user", user_message)

    # Auto-title the session from the first user message
    if session.get("title") == "New Chat" and user_message:
        short_title = user_message[:60] + ("..." if len(user_message) > 60 else "")
        update_chat_session_title(session_id, short_title)

    # Build message history from the DB (full session context for the AI)
    session = get_chat_session(session_id)
    messages = [{"role": m["role"], "content": m["content"]} for m in session.get("messages", [])]

    try:
        # Build full business context from all tracker modules
        try:
            full_context = build_coo_full_context()
        except Exception:
            full_context = "(Business intelligence temporarily unavailable)"

        # Build master context — summaries of ALL past sessions
        try:
            master_context = get_chat_master_context(exclude_session_id=session_id)
        except Exception:
            master_context = ""

        # Route the latest user message to a specialist agent
        routed_agent = route_to_agent(user_message)

        # Get the specialist's system prompt
        agent = get_coo_agent(routed_agent)
        specialist_prompt = agent["system_prompt"] if agent else ""

        # Always respond as Chief of Staff, with specialist context
        cos_agent = get_coo_agent("Chief of Staff")
        cos_prompt = cos_agent["system_prompt"] if cos_agent else ""

        system_prompt = f"""{cos_prompt}

--- SPECIALIST CONTEXT ---
For this question, the {routed_agent} provided analysis context:
{specialist_prompt}

--- FULL BUSINESS INTELLIGENCE ---
Live data from the TGF Transaction Tracker as of {datetime.now().strftime('%Y-%m-%d %H:%M')}:

{full_context}"""

        if master_context:
            system_prompt += f"""

--- PERSISTENT MEMORY ---
{master_context}"""

        client = _anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1500,
            system=system_prompt,
            messages=messages,
        )

        assistant_content = resp.content[0].text

        # Save the assistant response
        add_chat_message(session_id, "assistant", assistant_content, routed_to=routed_agent)

        # Auto-summarize the session after each exchange (lightweight — no extra AI call)
        # Build summary from key topics discussed: all user messages, condensed
        updated_session = get_chat_session(session_id)
        user_msgs = [m["content"] for m in updated_session.get("messages", []) if m["role"] == "user"]
        asst_msgs = [m["content"] for m in updated_session.get("messages", []) if m["role"] == "assistant"]
        # Summary = first 3 user questions + last assistant key points
        topics = "; ".join(msg[:80] for msg in user_msgs[:5])
        last_answer = asst_msgs[-1][:150] if asst_msgs else ""
        auto_summary = f"Topics: {topics}. Last response: {last_answer}"
        update_chat_session_summary(session_id, auto_summary[:500])

        # Log the routing decision
        log_agent_action(routed_agent, "chat_routing",
                         f"Routed question to {routed_agent}: {user_message[:100]}",
                         outcome="response_generated")

        return jsonify({
            "role": "assistant",
            "content": assistant_content,
            "routed_to": routed_agent,
            "session_id": session_id,
        })
    except Exception as e:
        return jsonify({"error": str(e), "session_id": session_id}), 500


# ── COO Chat Session Management ────────────────────────────

@app.route("/api/coo/chat-sessions", methods=["GET"])
@require_role("admin")
def api_coo_chat_sessions():
    """List recent chat sessions."""
    return jsonify(get_chat_sessions(limit=30))


@app.route("/api/coo/chat-sessions", methods=["POST"])
@require_role("admin")
def api_coo_create_chat_session():
    """Create a new chat session."""
    d = request.json or {}
    return jsonify(create_chat_session(title=d.get("title", "New Chat")))


@app.route("/api/coo/chat-sessions/<int:sid>", methods=["GET"])
@require_role("admin")
def api_coo_get_chat_session(sid):
    """Get a chat session with all messages."""
    sess = get_chat_session(sid)
    if not sess:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(sess)


@app.route("/api/coo/chat-sessions/<int:sid>", methods=["DELETE"])
@require_role("admin")
def api_coo_delete_chat_session(sid):
    """Delete a chat session."""
    return jsonify(delete_chat_session(sid))


@app.route("/api/coo/chat-sessions/<int:sid>", methods=["PATCH"])
@require_role("admin")
def api_coo_rename_chat_session(sid):
    """Rename a chat session."""
    d = request.json or {}
    title = d.get("title", "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    update_chat_session_title(sid, title)
    return jsonify({"status": "ok", "title": title})


@app.route("/api/coo/send-daily-email", methods=["POST"])
@require_role("admin")
def api_coo_send_daily_email():
    """Manually trigger the COO daily email for testing."""
    coo_to = os.getenv("COO_EMAIL_TO", "kerry@thegolffellowship.com")
    ok = send_coo_daily_email()
    if ok:
        return jsonify({"sent": True, "to": coo_to})
    # If Azure not configured, still return the HTML for preview
    try:
        subject, html_body = build_coo_email_html()
        return jsonify({"sent": False, "preview": True, "subject": subject, "html": html_body, "to": coo_to})
    except Exception as e:
        return jsonify({"sent": False, "error": str(e)}), 500


@app.route("/api/coo/agents")
@require_role("admin")
def api_coo_agents():
    return jsonify(get_coo_agents())


@app.route("/api/coo/agent-log")
@require_role("admin")
def api_coo_agent_log():
    return jsonify(get_agent_action_log(
        agent_name=request.args.get("agent_name"),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        limit=request.args.get("limit", 50, type=int),
    ))


# ═══════════════════════════════════════════════════════════════════════════
# Bank Reconciliation
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/accounting/chart-of-accounts")
@require_role("admin")
def api_chart_of_accounts():
    return jsonify(get_chart_of_accounts())


@app.route("/api/accounting/ledger")
@require_role("admin")
def api_ledger_entries():
    return jsonify(get_ledger_entries(
        account_code=request.args.get("account_code"),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        reconciled=request.args.get("reconciled", type=int),
    ))


@app.route("/api/accounting/bank-import", methods=["POST"])
@require_role("admin")
def api_bank_import():
    """Upload and import a bank statement CSV."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    csv_text = request.files["file"].read().decode("utf-8", errors="replace")
    bank = request.form.get("bank", "Chase")
    account_last4 = request.form.get("account_last4", "")
    result = import_bank_statement(csv_text, bank, account_last4)
    return jsonify(result)


@app.route("/api/accounting/reconcile", methods=["POST"])
@require_role("admin")
def api_reconcile():
    """Run auto-match on imported bank rows."""
    d = request.json or {}
    result = run_bank_reconciliation(
        import_id=d.get("import_id"),
        account_last4=d.get("account_last4"),
        month=d.get("month"),
    )
    return jsonify(result)


@app.route("/api/accounting/reconcile/match", methods=["POST"])
@require_role("admin")
def api_reconcile_match():
    """Manually confirm a match between a bank row and a Tracker record."""
    d = request.json or {}
    bank_row_id = d.get("bank_row_id")
    matched_source = d.get("matched_source")
    matched_id = d.get("matched_id")
    if not bank_row_id:
        return jsonify({"error": "bank_row_id required"}), 400
    from email_parser.database import _connect
    with _connect() as conn:
        conn.execute(
            """UPDATE bank_statement_rows
               SET reconciled = 1, matched_source = ?, matched_id = ?
               WHERE id = ?""",
            (matched_source, matched_id, bank_row_id),
        )
        conn.commit()
    return jsonify({"status": "ok"})


@app.route("/api/accounting/reconciliation-summary")
@require_role("admin")
def api_reconciliation_summary():
    month = request.args.get("month")
    if not month:
        return jsonify({"error": "month parameter required (YYYY-MM)"}), 400
    return jsonify(get_reconciliation_summary(month))


@app.route("/api/accounting/close-period", methods=["POST"])
@require_role("admin")
def api_close_period():
    d = request.json or {}
    period = d.get("period")
    if not period:
        return jsonify({"error": "period required (YYYY-MM)"}), 400
    return jsonify(close_period(period))


# ── Bank Deposit Reconciliation Routes ──────────────────────────────────

@app.route("/accounting/reconcile")
@require_role("admin")
def page_reconcile():
    return render_template("reconcile.html")


@app.route("/accounting/cashflow")
@require_role("admin")
def page_cashflow():
    return render_template("cashflow.html")


@app.route("/api/reconciliation/accounts")
@require_role("admin")
def api_recon_accounts():
    return jsonify(get_bank_accounts())


@app.route("/api/reconciliation/dashboard")
@require_role("admin")
def api_recon_dashboard():
    return jsonify(get_reconciliation_dashboard())


@app.route("/api/reconciliation/import", methods=["POST"])
@require_role("admin")
def api_recon_import():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    account_id = request.form.get("account_id", type=int)
    if not account_id:
        return jsonify({"error": "account_id required"}), 400
    file_bytes = f.read()
    # Detect Venmo statement format before default import path
    csv_text = file_bytes.decode("utf-8", errors="replace")
    first_line = csv_text.split("\n", 1)[0].strip()
    if "Account Statement" in first_line or first_line.lower().startswith("transaction id"):
        result = import_venmo_statement(csv_text, "Venmo")
        # Auto-match after import
        if result.get("imported", 0) > 0:
            match_result = run_deposit_auto_match()
            result["auto_match"] = match_result
        return jsonify(result)
    result = import_bank_deposits(file_bytes, f.filename or "upload.csv", account_id)
    # Auto-match after import
    if result.get("imported", 0) > 0:
        match_result = run_deposit_auto_match(account_id)
        result["auto_match"] = match_result
    return jsonify(result)


@app.route("/api/reconciliation/auto-match", methods=["POST"])
@require_role("admin")
def api_recon_auto_match():
    d = request.json or {}
    account_id = d.get("account_id")
    return jsonify(run_deposit_auto_match(account_id))


@app.route("/api/reconciliation/match", methods=["POST"])
@require_role("admin")
def api_recon_match():
    d = request.json or {}
    bank_deposit_id = d.get("bank_deposit_id")
    acct_transaction_id = d.get("acct_transaction_id")
    if not bank_deposit_id or not acct_transaction_id:
        return jsonify({"error": "bank_deposit_id and acct_transaction_id required"}), 400
    return jsonify(manual_match_deposit(bank_deposit_id, acct_transaction_id))


@app.route("/api/reconciliation/match-batch", methods=["POST"])
@require_role("admin")
def api_recon_match_batch():
    """Match multiple acct_transactions to a single bank deposit (1:many)."""
    d = request.json or {}
    bank_deposit_id = d.get("bank_deposit_id")
    acct_transaction_ids = d.get("acct_transaction_ids", [])
    if not bank_deposit_id or not acct_transaction_ids:
        return jsonify({"error": "bank_deposit_id and acct_transaction_ids required"}), 400
    return jsonify(batch_match_deposit(bank_deposit_id, acct_transaction_ids))


@app.route("/api/reconciliation/unmatch", methods=["POST"])
@require_role("admin")
def api_recon_unmatch():
    d = request.json or {}
    bank_deposit_id = d.get("bank_deposit_id")
    acct_transaction_id = d.get("acct_transaction_id")
    if not bank_deposit_id:
        return jsonify({"error": "bank_deposit_id required"}), 400
    return jsonify(unmatch_deposit(bank_deposit_id, acct_transaction_id))


@app.route("/api/reconciliation/create-entry", methods=["POST"])
@require_role("admin")
def api_recon_create_entry():
    """Create a ledger entry from an unmatched bank deposit and immediately reconcile it."""
    d = request.json or {}
    deposit_id = d.get("deposit_id")
    if not deposit_id:
        return jsonify({"error": "deposit_id required"}), 400
    result = create_entry_from_deposit(
        deposit_id=deposit_id,
        txn_type=d.get("txn_type", "expense"),
        category_name=d.get("category_name"),
        entity_name=d.get("entity_name"),
        notes=d.get("notes"),
        description=d.get("description"),
        date_override=d.get("date"),
        amount_override=d.get("amount"),
        event_name=d.get("event_name"),
        entry_type=d.get("entry_type"),
    )
    return jsonify(result)


@app.route("/api/reconciliation/deposits")
@require_role("admin")
def api_recon_deposits():
    account_id = request.args.get("account_id", type=int)
    status = request.args.get("status")
    month = request.args.get("month")
    include_dismissed = request.args.get("include_dismissed", "false").lower() == "true"
    return jsonify(get_bank_deposits(account_id, status, month, include_dismissed))


@app.route("/api/reconciliation/dismiss-deposit", methods=["POST"])
@require_role("admin")
def api_dismiss_deposit():
    d = request.json or {}
    deposit_id = d.get("deposit_id")
    reason = d.get("reason", "not_applicable")
    if not deposit_id:
        return jsonify({"error": "deposit_id required"}), 400
    return jsonify(dismiss_bank_deposit(deposit_id, reason))


@app.route("/api/reconciliation/record-transfer", methods=["POST"])
@require_role("admin")
def api_record_transfer():
    d = request.json or {}
    deposit_id = d.get("deposit_id")
    from_account = d.get("from_account", "TGF Checking")
    to_account = d.get("to_account", "Venmo")
    notes = d.get("notes", "")
    if not deposit_id:
        return jsonify({"error": "deposit_id required"}), 400
    return jsonify(record_internal_transfer(deposit_id, from_account, to_account, notes))


@app.route("/api/reconciliation/unreconciled")
@require_role("admin")
def api_recon_unreconciled():
    account = request.args.get("account")
    month = request.args.get("month")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    source = request.args.get("source")
    return jsonify(get_unreconciled_transactions(account, month,
                                                 date_from=date_from, date_to=date_to,
                                                 source=source))


@app.route("/api/reconciliation/suggestions/<int:deposit_id>")
@require_role("admin")
def api_recon_suggestions(deposit_id):
    return jsonify(get_match_suggestions(deposit_id))


@app.route("/api/reconciliation/matched/<int:deposit_id>")
@require_role("admin")
def api_recon_matched(deposit_id):
    """Return the acct_transactions matched to a specific bank deposit."""
    from email_parser.database import _connect
    with _connect() as conn:
        rows = conn.execute(
            """SELECT t.*, rm.match_confidence, rm.match_type
               FROM acct_transactions t
               JOIN reconciliation_matches rm ON rm.acct_transaction_id = t.id
               WHERE rm.bank_deposit_id = ?
               ORDER BY t.date""",
            (deposit_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@app.route("/api/reconciliation/reconciled-items")
@require_role("admin")
def api_recon_reconciled_items():
    """Return item_id → bank_deposit_id mapping for reconciled items."""
    from email_parser.database import _connect
    with _connect() as conn:
        rows = conn.execute(
            """SELECT DISTINCT t.item_id, rm.bank_deposit_id
               FROM acct_transactions t
               JOIN reconciliation_matches rm ON rm.acct_transaction_id = t.id
               WHERE t.item_id IS NOT NULL"""
        ).fetchall()
        # Also get item_ids from order-level entries via splits
        split_rows = conn.execute(
            """SELECT DISTINCT s.item_id, rm.bank_deposit_id
               FROM godaddy_order_splits s
               JOIN reconciliation_matches rm ON rm.acct_transaction_id = s.transaction_id
               WHERE s.item_id IS NOT NULL"""
        ).fetchall()
        mapping = {}
        for r in rows:
            mapping[r["item_id"]] = r["bank_deposit_id"]
        for r in split_rows:
            mapping[r["item_id"]] = r["bank_deposit_id"]
        return jsonify(mapping)


@app.route("/api/reconciliation/monthly")
@require_role("admin")
def api_recon_monthly():
    month = request.args.get("month")
    if not month:
        return jsonify({"error": "month required (YYYY-MM)"}), 400
    return jsonify(get_monthly_reconciliation(month))


@app.route("/api/reconciliation/event/<event_name>")
@require_role("manager")
def api_recon_event(event_name):
    return jsonify(get_event_reconciliation_status(event_name))


@app.route("/api/reconciliation/cashflow")
@require_role("admin")
def api_cashflow():
    weeks = request.args.get("weeks", 13, type=int)
    return jsonify(get_cashflow_data(weeks))


@app.route("/api/reconciliation/migrate-to-order-level", methods=["POST"])
@require_role("admin")
def api_migrate_to_order_level():
    """Migrate old per-item GoDaddy entries to order-level format."""
    results = migrate_item_to_order_entries()
    return jsonify(results)


@app.route("/api/reconciliation/merge-transactions", methods=["POST"])
@require_role("admin")
def api_merge_transactions():
    """Merge multiple GoDaddy order transactions into a single batch entry."""
    d = request.json or {}
    ids = d.get("acct_transaction_ids", [])
    if len(ids) < 2:
        return jsonify({"error": "Need at least 2 transaction IDs"}), 400
    return jsonify(merge_transactions(ids))


# ---------------------------------------------------------------------------
# TGF Payouts
# ---------------------------------------------------------------------------

@app.route("/tgf")
def tgf_page():
    return render_template("tgf.html")


@app.route("/api/tgf")
def api_tgf_data():
    return jsonify(get_tgf_data())


@app.route("/api/tgf", methods=["POST"])
@require_role("manager")
def api_tgf_action():
    d = request.json or {}
    action = d.get("action")
    if action == "add_event":
        return jsonify(add_tgf_event(d))
    elif action == "add_golfer":
        return jsonify(add_tgf_golfer(d))
    elif action == "import_payouts":
        from email_parser.database import import_tgf_payouts
        if not d.get("event_id"):
            return jsonify({"error": "event_id required"}), 400
        return jsonify(import_tgf_payouts(d["event_id"], d.get("payouts", [])))
    elif action == "import_golfers":
        return jsonify(import_tgf_golfers(d.get("golfers", [])))
    elif action == "update_event":
        return jsonify(update_tgf_event(d["event_id"], d))
    elif action == "delete_event":
        return jsonify(delete_tgf_event(d["event_id"]))
    else:
        return jsonify({"error": f"Unknown action: {action}"}), 400


@app.route("/api/tgf/dedup-audit", methods=["GET"])
@require_role("admin")
def api_tgf_dedup_audit():
    """Diagnostic: list customers created by the tgf_golfers migration and
    find likely duplicates of existing customers (name-format mismatches).

    For each customer with acquisition_source IN ('tgf_payout','tgf_payout_migration'),
    try to find an existing customer whose name matches in reversed format
    ("LAST, First" ↔ "First Last") or normalized form.
    """
    from email_parser.database import _connect

    def normalize(s: str) -> str:
        return " ".join((s or "").strip().split()).lower()

    def parse_commaed(name: str) -> tuple[str, str] | None:
        """Parse 'LAST, First' → ('First', 'LAST'). Returns None if not that format."""
        if "," not in name:
            return None
        parts = [p.strip() for p in name.split(",", 1)]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return None
        # LAST, First → return (First, Last)
        return parts[1], parts[0]

    results = []
    with _connect() as conn:
        # All customers created from tgf_golfers migration
        migrated_rows = conn.execute(
            """SELECT customer_id, first_name, last_name, venmo_username, chapter,
                      acquisition_source, created_at
               FROM customers
               WHERE acquisition_source IN ('tgf_payout', 'tgf_payout_migration')
               ORDER BY customer_id"""
        ).fetchall()

        for mr in migrated_rows:
            mr_d = dict(mr)
            full_name = f"{mr_d['first_name']} {mr_d['last_name']}".strip()

            # How many payouts point to this customer?
            payout_stats = conn.execute(
                """SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
                   FROM tgf_payouts WHERE customer_id = ?""",
                (mr_d["customer_id"],),
            ).fetchone()

            # Try to find candidate matches in the customers table
            candidates = []

            # Case 1: stored as "LAST, First" with last_name containing comma format
            # e.g., first_name="CAMPOS" last_name="Roland" (because parser split incorrectly)
            # Try the reversed interpretation: treat last_name as first, first_name as last
            reversed_candidates = conn.execute(
                """SELECT customer_id, first_name, last_name, venmo_username, chapter,
                          acquisition_source
                   FROM customers
                   WHERE customer_id != ?
                     AND acquisition_source IS NOT 'tgf_payout_migration'
                     AND acquisition_source IS NOT 'tgf_payout'
                     AND (
                       (LOWER(first_name) = LOWER(?) AND LOWER(last_name) = LOWER(?))
                       OR (LOWER(first_name) = LOWER(?) AND LOWER(last_name) = LOWER(?))
                     )""",
                (
                    mr_d["customer_id"],
                    # interpretation 1: first_name/last_name swapped (comma form)
                    mr_d["last_name"], mr_d["first_name"],
                    # interpretation 2: same as stored (exact match)
                    mr_d["first_name"], mr_d["last_name"],
                ),
            ).fetchall()

            for rc in reversed_candidates:
                candidates.append({
                    "match_type": "reversed_exact",
                    **dict(rc),
                })

            # Case 2: fuzzy — same last name, either first name matches as initial or shared prefix
            if not candidates and mr_d["last_name"]:
                fuzzy = conn.execute(
                    """SELECT customer_id, first_name, last_name, venmo_username, chapter,
                              acquisition_source
                       FROM customers
                       WHERE customer_id != ?
                         AND acquisition_source IS NOT 'tgf_payout_migration'
                         AND acquisition_source IS NOT 'tgf_payout'
                         AND (
                           LOWER(last_name) = LOWER(?)
                           OR LOWER(first_name) = LOWER(?)
                         )
                       LIMIT 5""",
                    (mr_d["customer_id"], mr_d["last_name"], mr_d["last_name"]),
                ).fetchall()
                for f in fuzzy:
                    candidates.append({
                        "match_type": "fuzzy_lastname",
                        **dict(f),
                    })

            # Case 3: "LAST, First" parsing bug — the comma stayed in first_name.
            # The REAL last name is first_name with comma stripped. Search for that.
            first_stripped = (mr_d["first_name"] or "").rstrip(",").strip()
            if first_stripped and first_stripped != mr_d["last_name"]:
                comma_bug = conn.execute(
                    """SELECT customer_id, first_name, last_name, venmo_username, chapter,
                              acquisition_source
                       FROM customers
                       WHERE customer_id != ?
                         AND acquisition_source IS NOT 'tgf_payout_migration'
                         AND acquisition_source IS NOT 'tgf_payout'
                         AND LOWER(last_name) = LOWER(?)
                         AND LOWER(first_name) = LOWER(?)
                       LIMIT 5""",
                    (mr_d["customer_id"], first_stripped, mr_d["last_name"]),
                ).fetchall()
                for c in comma_bug:
                    # Avoid duplicates from previous cases
                    if not any(cand.get("customer_id") == c["customer_id"] for cand in candidates):
                        candidates.append({
                            "match_type": "comma_bug_reversed_exact",
                            **dict(c),
                        })

                # Broader: same real last name, any first name
                comma_bug_fuzzy = conn.execute(
                    """SELECT customer_id, first_name, last_name, venmo_username, chapter,
                              acquisition_source
                       FROM customers
                       WHERE customer_id != ?
                         AND acquisition_source IS NOT 'tgf_payout_migration'
                         AND acquisition_source IS NOT 'tgf_payout'
                         AND LOWER(last_name) = LOWER(?)
                       LIMIT 5""",
                    (mr_d["customer_id"], first_stripped),
                ).fetchall()
                for c in comma_bug_fuzzy:
                    if not any(cand.get("customer_id") == c["customer_id"] for cand in candidates):
                        candidates.append({
                            "match_type": "comma_bug_lastname_match",
                            **dict(c),
                        })

            # Also look for intra-migration duplicates (two customers both created by migration)
            intra_candidates = conn.execute(
                """SELECT customer_id, first_name, last_name, venmo_username, chapter,
                          acquisition_source
                   FROM customers
                   WHERE customer_id != ?
                     AND acquisition_source IN ('tgf_payout', 'tgf_payout_migration')
                     AND (
                       (LOWER(first_name) = LOWER(?) AND LOWER(last_name) = LOWER(?))
                       OR (LOWER(first_name) = LOWER(?) AND LOWER(last_name) = LOWER(?))
                     )""",
                (
                    mr_d["customer_id"],
                    mr_d["last_name"], mr_d["first_name"],
                    mr_d["first_name"], mr_d["last_name"],
                ),
            ).fetchall()
            for ic in intra_candidates:
                candidates.append({
                    "match_type": "intra_migration_reversed",
                    **dict(ic),
                })

            results.append({
                "migrated_customer_id": mr_d["customer_id"],
                "migrated_name": full_name,
                "first_name": mr_d["first_name"],
                "last_name": mr_d["last_name"],
                "venmo_username": mr_d["venmo_username"],
                "chapter": mr_d["chapter"],
                "acquisition_source": mr_d["acquisition_source"],
                "payout_count": payout_stats["cnt"],
                "payout_total": round(payout_stats["total"] or 0, 2),
                "candidate_matches": candidates,
            })

        summary = {
            "total_migrated_customers": len(migrated_rows),
            "with_candidates": sum(1 for r in results if r["candidate_matches"]),
            "without_candidates": sum(1 for r in results if not r["candidate_matches"]),
        }

    return jsonify({"summary": summary, "customers": results})


@app.route("/api/tgf/match-diagnostic", methods=["GET"])
@require_role("admin")
def api_tgf_match_diagnostic():
    """Diagnostic: for each pending payout, show WHY it didn't match a Venmo payment.

    Groups pending payouts by (customer_id, event_id) and for each group shows:
      - expected sum
      - event date & 7-day window
      - customer name as stored in customers table
      - candidate Venmo prize_payout transactions (all, not just matches)
      - reason for non-match (amount / customer / date / already linked)
    """
    from email_parser.database import _connect
    with _connect() as conn:
        # Get all pending payout groups (those with source='pending' acct_transaction)
        pending = conn.execute(
            """SELECT p.id as payout_id, p.event_id, p.customer_id, p.amount, p.category,
                      p.acct_transaction_id, t.source as txn_source,
                      e.event_date, e.name as event_name,
                      (c.first_name || ' ' || c.last_name) as customer_name
               FROM tgf_payouts p
               JOIN tgf_events e ON e.id = p.event_id
               JOIN customers c ON c.customer_id = p.customer_id
               LEFT JOIN acct_transactions t ON t.id = p.acct_transaction_id
               WHERE p.paid_at IS NULL"""
        ).fetchall()

        # Group by (event_id, customer_id)
        groups = {}
        for p in pending:
            key = (p["event_id"], p["customer_id"])
            if key not in groups:
                groups[key] = {
                    "event_name": p["event_name"],
                    "event_date": p["event_date"],
                    "customer_id": p["customer_id"],
                    "customer_name": p["customer_name"],
                    "payouts": [],
                }
            groups[key]["payouts"].append({
                "payout_id": p["payout_id"],
                "amount": p["amount"],
                "category": p["category"],
                "txn_source": p["txn_source"],
            })

        results = []
        for (event_id, customer_id), g in groups.items():
            group_sum = round(sum(p["amount"] for p in g["payouts"]), 2)
            event_date = g["event_date"]

            # List ALL Venmo prize_payouts for this customer (any amount/date)
            all_venmo = conn.execute(
                """SELECT id, date, amount, customer, description,
                          COALESCE(status, 'active') as status,
                          (SELECT existing.id FROM tgf_payouts existing
                           WHERE existing.acct_transaction_id = t.id LIMIT 1) as already_linked_to
                   FROM acct_transactions t
                   WHERE source = 'venmo' AND category = 'prize_payout'
                     AND LOWER(customer) = LOWER(?)
                   ORDER BY date DESC""",
                (g["customer_name"],),
            ).fetchall()

            candidates = []
            for v in all_venmo:
                v_dict = dict(v)
                # Compute why this venmo didn't match (or did)
                reasons = []
                if round(abs(v_dict["amount"]), 2) != group_sum:
                    reasons.append(f"amount: venmo ${abs(v_dict['amount']):.2f} vs needed ${group_sum:.2f}")
                if v_dict["status"] != "active":
                    reasons.append(f"status: {v_dict['status']}")
                if v_dict["already_linked_to"]:
                    reasons.append(f"already linked to payout {v_dict['already_linked_to']}")
                # Date check
                date_ok = conn.execute(
                    "SELECT DATE(?) >= DATE(?) AND DATE(?) <= DATE(?, '+7 days') as ok",
                    (v_dict["date"], event_date, v_dict["date"], event_date),
                ).fetchone()
                if not date_ok or not date_ok["ok"]:
                    reasons.append(f"date: {v_dict['date']} outside {event_date} to +7d")
                v_dict["match_blockers"] = reasons or ["would match ✓"]
                candidates.append(v_dict)

            # Also search for venmo transactions where customer name might differ
            name_variants = conn.execute(
                """SELECT id, date, amount, customer, description
                   FROM acct_transactions
                   WHERE source = 'venmo' AND category = 'prize_payout'
                     AND ROUND(ABS(amount), 2) = ?
                     AND DATE(date) >= DATE(?)
                     AND DATE(date) <= DATE(?, '+7 days')
                     AND LOWER(customer) != LOWER(?)""",
                (group_sum, event_date, event_date, g["customer_name"]),
            ).fetchall()

            results.append({
                "event_name": g["event_name"],
                "event_date": g["event_date"],
                "customer_name": g["customer_name"],
                "customer_id": g["customer_id"],
                "payout_sum": group_sum,
                "payout_count": len(g["payouts"]),
                "payouts": g["payouts"],
                "all_venmo_for_this_customer": candidates,
                "venmo_amount_matches_but_different_customer_name": [dict(v) for v in name_variants],
            })

    return jsonify({
        "total_pending_groups": len(results),
        "groups": results,
    })


@app.route("/api/tgf/mark-paid", methods=["POST"])
@require_role("manager")
def api_tgf_mark_paid():
    """Mark a group of payouts as paid via non-Venmo method.

    Body: {event_id, customer_id, payment_method, paid_date?, reference?}

    Creates a real acct_transaction (expense/prize_payout) with the
    specified source, reverses the pending placeholder, and links all
    matching tgf_payouts rows.
    """
    from email_parser.database import _connect
    d = request.json or {}
    event_id = d.get("event_id")
    customer_id = d.get("customer_id")
    payment_method = (d.get("payment_method") or "").strip().lower()
    paid_date = d.get("paid_date")  # YYYY-MM-DD, defaults to today
    reference = d.get("reference") or ""

    if not event_id or not customer_id or not payment_method:
        return jsonify({"error": "event_id, customer_id, and payment_method required"}), 400

    # Whitelist allowed sources
    ALLOWED_SOURCES = {"paypal", "cashapp", "cash", "check", "zelle", "other"}
    if payment_method not in ALLOWED_SOURCES:
        return jsonify({"error": f"payment_method must be one of {sorted(ALLOWED_SOURCES)}"}), 400

    if not paid_date:
        from datetime import date as _date
        paid_date = _date.today().isoformat()

    with _connect() as conn:
        # Find all pending payouts for this customer+event
        pending = conn.execute(
            """SELECT p.id as payout_id, p.amount, p.acct_transaction_id,
                      t.source as txn_source, t.status as txn_status,
                      e.name as event_name,
                      (c.first_name || ' ' || c.last_name) as customer_name
               FROM tgf_payouts p
               JOIN tgf_events e ON e.id = p.event_id
               JOIN customers c ON c.customer_id = p.customer_id
               LEFT JOIN acct_transactions t ON t.id = p.acct_transaction_id
               WHERE p.event_id = ? AND p.customer_id = ?
                 AND (p.paid_at IS NULL OR t.source = 'pending')""",
            (event_id, customer_id),
        ).fetchall()

        if not pending:
            return jsonify({"error": "No pending payouts found for this customer+event"}), 404

        total_amount = round(sum(float(p["amount"]) for p in pending), 2)
        customer_name = pending[0]["customer_name"]
        event_name = pending[0]["event_name"]

        # Create the real acct_transaction for the payment
        description = f"{payment_method.upper()} payout: {customer_name} — {event_name}"
        if reference:
            description += f" (ref: {reference})"

        cur = conn.execute(
            """INSERT INTO acct_transactions
                   (date, description, total_amount, type, source, source_ref,
                    customer, order_id, entry_type, category, amount, account, status, event_name)
               VALUES (?, ?, ?, 'expense', ?, ?, ?, ?, 'expense', 'prize_payout',
                       ?, ?, 'active', ?)""",
            (
                paid_date, description, total_amount, payment_method,
                f"manual-payout-{event_id}-{customer_id}",
                customer_name,
                f"MANUAL-PAYOUT-{event_id}-{customer_id}",
                -total_amount,
                payment_method.capitalize(),
                event_name,
            ),
        )
        new_txn_id = cur.lastrowid

        # Reverse the pending placeholders + link payouts to the new entry
        linked = 0
        for p in pending:
            if p["acct_transaction_id"] and p["txn_source"] == "pending":
                conn.execute(
                    "UPDATE acct_transactions SET status = 'reversed' WHERE id = ?",
                    (p["acct_transaction_id"],),
                )
            conn.execute(
                "UPDATE tgf_payouts SET acct_transaction_id = ?, paid_at = ? WHERE id = ?",
                (new_txn_id, paid_date, p["payout_id"]),
            )
            linked += 1

        conn.commit()
        return jsonify({
            "ok": True, "linked_payouts": linked,
            "amount": total_amount, "payment_method": payment_method,
            "acct_transaction_id": new_txn_id,
        })


@app.route("/api/tgf/parse-screenshot", methods=["POST"])
@require_role("manager")
def api_tgf_parse_screenshot():
    """Accept a base64 image, send to Claude vision, return parsed payouts JSON."""
    d = request.json or {}
    image_data = d.get("image")
    if not image_data:
        return jsonify({"error": "No image data provided"}), 400

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500

    # Strip data URL prefix if present
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]

    media_type = d.get("media_type", "image/png")

    client = _anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_data},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Parse this Golf Genius payout screenshot. Return ONLY valid JSON with:\n"
                            "{\n"
                            '  "event": {"code": "s9.X ...", "name": "Event Name", "date": "YYYY-MM-DD", "course": "Course Name"},\n'
                            '  "payouts": [\n'
                            '    {"golferName": "First Last", "category": "team_net|individual_net|individual_gross|skins|closest_to_pin|hole_in_one|mvp|other", "amount": 12.50, "description": "Game description"}\n'
                            "  ]\n"
                            "}\n\n"
                            "Categories: team_net, individual_net, individual_gross, skins, closest_to_pin, hole_in_one, mvp, other.\n"
                            "Extract every payout line. Amount should be a number (no $ sign).\n"
                            "Return ONLY the JSON — no markdown, no explanation."
                        ),
                    },
                ],
            }],
        )
        text = resp.content[0].text.strip()
        # Try to parse JSON from the response
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        return jsonify(parsed)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse AI response as JSON", "raw": text}), 422
    except Exception as e:
        logger.exception("Screenshot parse failed")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# App startup
# ---------------------------------------------------------------------------
init_db()

# ── Run acct_transactions backfill once if unfilled entries exist ──
try:
    from email_parser.database import _connect as _startup_connect
    with _startup_connect() as _conn:
        _acct_count = _conn.execute(
            "SELECT COUNT(*) as cnt FROM acct_transactions WHERE entry_type IS NOT NULL"
        ).fetchone()["cnt"]
    if _acct_count == 0:
        _bf_result = backfill_acct_transactions()
        logger.info("Startup backfill: %s", _bf_result)
    else:
        logger.info("Accounting entries exist (%d), skipping backfill", _acct_count)

    # ── Auto-migrate old per-item GoDaddy entries to order-level ──
    try:
        with _startup_connect() as _mig_conn:
            _old_format_count = _mig_conn.execute(
                "SELECT COUNT(*) as cnt FROM acct_transactions WHERE source_ref LIKE 'godaddy-income-%' AND COALESCE(status, 'active') = 'active'"
            ).fetchone()["cnt"]
        if _old_format_count > 0:
            logger.info("Found %d old-format per-item GoDaddy entries — running migration", _old_format_count)
            _mig_result = migrate_item_to_order_entries()
            logger.info("Order-level migration: %s", _mig_result)
        else:
            logger.info("No old-format GoDaddy entries — order-level migration not needed")
    except Exception:
        logger.warning("Order-level migration check failed", exc_info=True)

    # ── One-time fix: recalculate merchant fees from 2.7% to 2.9% ──
    try:
        with _startup_connect() as _fee_conn:
            # Check if any orders still have the old 2.7% rate
            # Signature: old rate gives merchant_fee ≈ amount * 0.027 + 0.30
            # New rate gives merchant_fee ≈ amount * 0.029 + 0.30
            _sample = _fee_conn.execute(
                """SELECT id, amount, merchant_fee FROM acct_transactions
                   WHERE category = 'godaddy_order' AND merchant_fee IS NOT NULL
                   AND amount > 0 AND COALESCE(status, 'active') NOT IN ('reversed', 'merged')
                   LIMIT 1"""
            ).fetchone()
            if _sample:
                _expected_29 = round(_sample["amount"] * 0.029 + 0.30, 2)
                _expected_27 = round(_sample["amount"] * 0.027 + 0.30, 2)
                if abs(_sample["merchant_fee"] - _expected_27) < 0.02 and abs(_sample["merchant_fee"] - _expected_29) > 0.02:
                    logger.info("Detected old 2.7%% merchant fees — recalculating to 2.9%%")
                    _orders = _fee_conn.execute(
                        """SELECT id, amount FROM acct_transactions
                           WHERE category = 'godaddy_order' AND amount > 0
                           AND COALESCE(status, 'active') NOT IN ('reversed', 'merged')"""
                    ).fetchall()
                    _updated = 0
                    for _ord in _orders:
                        _new_fee = round(_ord["amount"] * 0.029 + 0.30, 2)
                        _new_net = round(_ord["amount"] - _new_fee, 2)
                        _fee_conn.execute(
                            "UPDATE acct_transactions SET merchant_fee = ?, net_deposit = ? WHERE id = ?",
                            (_new_fee, _new_net, _ord["id"]),
                        )
                        _updated += 1
                    # Also update merchant_fee splits in godaddy_order_splits
                    _splits = _fee_conn.execute(
                        """SELECT s.id, s.transaction_id, t.amount as order_amount, s.amount as split_amount
                           FROM godaddy_order_splits s
                           JOIN acct_transactions t ON t.id = s.transaction_id
                           WHERE s.split_type = 'merchant_fee'"""
                    ).fetchall()
                    for _sp in _splits:
                        _item_count = _fee_conn.execute(
                            "SELECT COUNT(*) as cnt FROM godaddy_order_splits WHERE transaction_id = ? AND split_type = 'registration'",
                            (_sp["transaction_id"],),
                        ).fetchone()["cnt"] or 1
                        _total_fee = round(_sp["order_amount"] * 0.029 + 0.30, 2)
                        _per_item = round(_total_fee / _item_count, 2)
                        _fee_conn.execute(
                            "UPDATE godaddy_order_splits SET amount = ? WHERE id = ?",
                            (-_per_item, _sp["id"]),
                        )
                    _fee_conn.commit()
                    logger.info("Recalculated merchant fees for %d orders (2.7%% → 2.9%%)", _updated)
                else:
                    logger.info("Merchant fees already at 2.9%% rate — no recalculation needed")
    except Exception:
        logger.warning("Merchant fee recalculation failed", exc_info=True)

    # ── One-time fix: recalculate doubled order totals for multi-item orders ──
    # Bug: _write_godaddy_order_entry() summed total_amount across all items,
    # but total_amount stores the FULL ORDER total on each item row.  Multi-item
    # orders got their amount doubled/tripled, causing wrong net_deposit values.
    try:
        from email_parser.database import _parse_dollar as _pd
        with _startup_connect() as _otf:
            _gd_orders = _otf.execute(
                """SELECT t.id, t.source_ref, t.amount
                   FROM acct_transactions t
                   WHERE t.category = 'godaddy_order'
                   AND COALESCE(t.status, 'active') NOT IN ('reversed', 'merged')
                   AND t.source_ref LIKE 'godaddy-order-%'"""
            ).fetchall()

            _recalc_count = 0
            for _gdo in _gd_orders:
                _oid = _gdo["source_ref"].replace("godaddy-order-", "")

                # Get items for this order (same filter as backfill)
                _order_items = _otf.execute(
                    """SELECT id, item_price, transaction_fees, total_amount,
                              item_name, customer, coupon_amount, coupon_code
                       FROM items
                       WHERE order_id = ?
                       AND COALESCE(transaction_status, 'active') NOT IN
                           ('rsvp_only', 'credited', 'refunded', 'transferred')
                       AND parent_item_id IS NULL
                       AND transferred_from_id IS NULL
                       ORDER BY item_index""",
                    (_oid,),
                ).fetchall()
                _order_items = [
                    dict(i) for i in _order_items if _pd(dict(i).get("item_price")) > 0
                ]

                if len(_order_items) < 2:
                    continue  # Single-item orders unaffected by the doubling bug

                # Correct order_total: total_amount from first item
                _first_ta = _pd(_order_items[0].get("total_amount"))
                _computed = sum(
                    _pd(i.get("item_price")) + _pd(i.get("transaction_fees"))
                    for i in _order_items
                )
                _correct_total = _first_ta if _first_ta > 0 else _computed

                # Skip if already correct (within $1)
                if abs(_gdo["amount"] - _correct_total) < 1.0:
                    continue

                # Update entry in-place (preserves ID → keeps reconciliation_matches)
                _new_mf = round(_correct_total * 0.029 + 0.30, 2)
                _new_nd = round(_correct_total - _new_mf, 2)
                _otf.execute(
                    "UPDATE acct_transactions SET amount = ?, merchant_fee = ?, net_deposit = ? WHERE id = ?",
                    (_correct_total, _new_mf, _new_nd, _gdo["id"]),
                )

                # Recreate splits with correct proportions
                _otf.execute(
                    "DELETE FROM godaddy_order_splits WHERE transaction_id = ?",
                    (_gdo["id"],),
                )
                for _oi in _order_items:
                    _ip = _pd(_oi.get("item_price"))
                    _tf = _pd(_oi.get("transaction_fees"))
                    _it = _ip + _tf  # per-item contribution

                    if _ip > 0:
                        _otf.execute(
                            """INSERT INTO godaddy_order_splits
                               (transaction_id, item_id, event_name, customer, split_type, amount)
                               VALUES (?, ?, ?, ?, 'registration', ?)""",
                            (_gdo["id"], _oi["id"], _oi.get("item_name", ""),
                             _oi.get("customer", ""), _ip),
                        )
                    if _tf > 0:
                        _otf.execute(
                            """INSERT INTO godaddy_order_splits
                               (transaction_id, item_id, event_name, customer, split_type, amount)
                               VALUES (?, ?, ?, ?, 'transaction_fee', ?)""",
                            (_gdo["id"], _oi["id"], _oi.get("item_name", ""),
                             _oi.get("customer", ""), _tf),
                        )
                    _coupon = _pd(_oi.get("coupon_amount"))
                    if _coupon > 0 and _oi.get("coupon_code"):
                        _otf.execute(
                            """INSERT INTO godaddy_order_splits
                               (transaction_id, item_id, event_name, customer, split_type, amount)
                               VALUES (?, ?, ?, ?, 'coupon', ?)""",
                            (_gdo["id"], _oi["id"], _oi.get("item_name", ""),
                             _oi.get("customer", ""), -_coupon),
                        )
                    if _it > 0 and _correct_total > 0:
                        _item_mf = round(_new_mf * _it / _computed, 2)
                        _otf.execute(
                            """INSERT INTO godaddy_order_splits
                               (transaction_id, item_id, event_name, customer, split_type, amount)
                               VALUES (?, ?, ?, ?, 'merchant_fee', ?)""",
                            (_gdo["id"], _oi["id"], _oi.get("item_name", ""),
                             _oi.get("customer", ""), -_item_mf),
                        )

                _recalc_count += 1

            if _recalc_count > 0:
                _otf.commit()
                logger.info("Fixed doubled order totals for %d multi-item orders", _recalc_count)
            else:
                logger.info("No doubled order totals found — all multi-item orders correct")
    except Exception:
        logger.warning("Order total recalculation failed", exc_info=True)

    # ── Verify s18.4 LANDA PARK numbers ──
    # Works with both old (registration + processing_fee) and new (godaddy_order) formats.
    try:
        with _startup_connect() as _vconn:
            _landa = _vconn.execute(
                """SELECT entry_type, category,
                          COALESCE(SUM(amount), 0) as total,
                          COALESCE(SUM(merchant_fee), 0) as total_merchant_fee,
                          COALESCE(SUM(net_deposit), 0) as total_net_deposit
                   FROM acct_transactions
                   WHERE event_name = 's18.4 LANDA PARK'
                   AND COALESCE(status, 'active') = 'active'
                   AND entry_type IS NOT NULL
                   GROUP BY entry_type, category""",
            ).fetchall()
            # Also check splits for multi-event orders where event_name on the
            # parent entry might differ from the item's event
            _landa_splits = _vconn.execute(
                """SELECT COALESCE(SUM(s.amount), 0) as reg_total,
                          COALESCE(SUM(CASE WHEN s.split_type = 'merchant_fee' THEN s.amount ELSE 0 END), 0) as mf_total
                   FROM godaddy_order_splits s
                   WHERE s.event_name = 's18.4 LANDA PARK'
                   AND s.split_type IN ('registration', 'merchant_fee')""",
            ).fetchone()

            if _landa:
                # Old format: separate registration income + processing_fee expense entries
                _old_income = sum(r["total"] for r in _landa if r["entry_type"] == "income" and r["category"] == "registration")
                _old_fees = sum(r["total"] for r in _landa if r["entry_type"] == "expense" and r["category"] == "processing_fee")

                # New format: godaddy_order entries with merchant_fee column
                _new_income = sum(r["total"] for r in _landa if r["entry_type"] == "income" and r["category"] == "godaddy_order")
                _new_merchant = sum(r["total_merchant_fee"] for r in _landa if r["category"] == "godaddy_order")
                _new_net = sum(r["total_net_deposit"] for r in _landa if r["category"] == "godaddy_order")

                _landa_income = _old_income + _new_income
                _landa_fees = _old_fees + _new_merchant
                _landa_refunds = sum(r["total"] for r in _landa if r["entry_type"] == "expense" and r["category"] == "refund")
                _landa_net_deposit = _new_net if _new_net > 0 else round(_landa_income - _landa_fees, 2)

                logger.info(
                    "LANDA PARK verification: income=$%.2f, merchant_fees=$%.2f, refunds=$%.2f, net_deposit=$%.2f",
                    _landa_income, _landa_fees, _landa_refunds, _landa_net_deposit,
                )
                for r in _landa:
                    logger.info("  %s/%s: amount=$%.2f merchant_fee=$%.2f net_deposit=$%.2f",
                                r["entry_type"], r["category"], r["total"],
                                r["total_merchant_fee"], r["total_net_deposit"])
    except Exception:
        logger.warning("LANDA PARK verification query failed", exc_info=True)
except Exception:
    logger.warning("Startup backfill failed", exc_info=True)

# Seed upcoming San Antonio events (idempotent — skips existing)
_SA_EVENTS = [
    {"item_name": "s9.1 The Quarry", "event_date": "2026-03-17", "course": "The Quarry", "chapter": "San Antonio"},
    {"item_name": "s9.2 Canyon Springs", "event_date": "2026-03-24", "course": "Canyon Springs", "chapter": "San Antonio"},
    {"item_name": "s9.3 Silverhorn", "event_date": "2026-03-31", "course": "Silverhorn", "chapter": "San Antonio"},
    {"item_name": "s9.4 The Quarry", "event_date": "2026-04-07", "course": "The Quarry", "chapter": "San Antonio"},
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

# Seed TGF payout data — s9.4 The Quarry (April 7, 2026)
_s94_result = add_tgf_event({
    "code": "s9.4 The Quarry",
    "name": "The Quarry",
    "event_date": "2026-04-07",
    "course": "The Quarry",
    "chapter": "San Antonio",
    "total_purse": 894.00,
    "winners_count": 14,
    "payouts": [
        {"golferName": "Gilbert Ellis", "category": "mvp", "amount": 84.00, "description": "TGF MVP"},
        {"golferName": "Gilbert Ellis", "category": "individual_net", "amount": 65.25, "description": "Individual Net"},
        {"golferName": "Gilbert Ellis", "category": "other", "amount": 58.00, "description": "s9.4 MVP Net"},
        {"golferName": "Gilbert Ellis", "category": "individual_gross", "amount": 21.00, "description": "Individual Gross"},
        {"golferName": "Pat Youngs", "category": "skins", "amount": 37.80, "description": "Skins Gross"},
        {"golferName": "Pat Youngs", "category": "closest_to_pin", "amount": 31.00, "description": "Closest to Pin #16"},
        {"golferName": "Pat Youngs", "category": "individual_net", "amount": 26.10, "description": "Individual Net"},
        {"golferName": "Pat Youngs", "category": "individual_gross", "amount": 21.00, "description": "Individual Gross"},
        {"golferName": "Pat Youngs", "category": "team_net", "amount": 19.50, "description": "Team Net"},
        {"golferName": "Jeff Young", "category": "skins", "amount": 56.70, "description": "Skins Gross"},
        {"golferName": "Jeff Young", "category": "closest_to_pin", "amount": 31.00, "description": "Closest to Pin #12"},
        {"golferName": "Jeff Young", "category": "team_net", "amount": 19.50, "description": "Team Net"},
        {"golferName": "Roland Campos", "category": "individual_net", "amount": 65.25, "description": "Individual Net"},
        {"golferName": "Roland Campos", "category": "individual_gross", "amount": 21.00, "description": "Individual Gross"},
        {"golferName": "Roland Campos", "category": "team_net", "amount": 19.50, "description": "Team Net"},
        {"golferName": "Jeff Rideout", "category": "skins", "amount": 47.25, "description": "Skins Gross"},
        {"golferName": "Jeff Rideout", "category": "individual_gross", "amount": 21.00, "description": "Individual Gross"},
        {"golferName": "Fred Wicker", "category": "skins", "amount": 47.25, "description": "Skins Gross"},
        {"golferName": "Adam Baker", "category": "individual_net", "amount": 39.15, "description": "Individual Net"},
        {"golferName": "Rob Callaway", "category": "individual_net", "amount": 39.15, "description": "Individual Net"},
        {"golferName": "Joe Decker", "category": "individual_net", "amount": 26.10, "description": "Individual Net"},
        {"golferName": "Jordan Bastin", "category": "team_net", "amount": 19.50, "description": "Team Net"},
        {"golferName": "Eric Taft", "category": "team_net", "amount": 19.50, "description": "Team Net"},
        {"golferName": "Steven Hunt", "category": "team_net", "amount": 19.50, "description": "Team Net"},
        {"golferName": "Jeff Greenwell", "category": "team_net", "amount": 19.50, "description": "Team Net"},
        {"golferName": "Brian Thompson", "category": "team_net", "amount": 19.50, "description": "Team Net"},
    ],
})
if "event_id" in _s94_result and "error" not in _s94_result:
    logger.info("Seeded TGF payout event s9.4 The Quarry (event_id=%d)", _s94_result["event_id"])

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
