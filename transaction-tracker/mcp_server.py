"""
TGF Transaction Tracker — MCP Server

Model Context Protocol server that gives Claude direct read/write access
to the transaction database.  Works with both Claude Code (CLI) and
Claude Desktop.

Start:
    python mcp_server.py          # stdio transport (default, for Claude Code)
    python mcp_server.py --sse    # SSE  transport  (for remote / Desktop)
"""

import json
import os
import sys
from pathlib import Path

# Ensure the transaction-tracker package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP

from email_parser.database import (
    DB_PATH,
    get_connection,
    get_all_items,
    get_item,
    get_item_stats,
    get_audit_report,
    get_data_snapshot,
    get_all_events,
    update_item,
    delete_item,
    credit_item,
    transfer_item,
    reverse_credit,
    create_event,
    update_event,
    delete_event,
    add_player_to_event,
    sync_events_from_items,
    autofix_all,
    init_db,
    get_rsvps_for_event,
    get_all_rsvps,
    get_rsvp_stats,
    rematch_rsvps,
)

# ── Initialise ──────────────────────────────────────────────────────────
init_db()
mcp = FastMCP("TGF Transaction Tracker")


# ═══════════════════════════════════════════════════════════════════════
#  READ TOOLS
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_transactions(
    customer: str = "",
    event: str = "",
    status: str = "",
    chapter: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 100,
) -> str:
    """Search and filter transactions.

    Args:
        customer: Filter by customer name (partial match, case-insensitive)
        event: Filter by event/item name (partial match, case-insensitive)
        status: Filter by transaction status: active, credited, or transferred
        chapter: Filter by chapter (partial match, case-insensitive)
        date_from: Earliest order date (YYYY-MM-DD)
        date_to: Latest order date (YYYY-MM-DD)
        limit: Max rows to return (default 100)
    """
    conn = get_connection()
    # Always exclude non-transaction placeholder rows
    clauses = [
        "merchant NOT IN ('Roster Import', 'Customer Entry', "
        "'RSVP Import', 'RSVP Email Link')"
    ]
    params = []

    if customer:
        clauses.append("customer LIKE ?")
        params.append(f"%{customer}%")
    if event:
        clauses.append("item_name LIKE ?")
        params.append(f"%{event}%")
    if status:
        clauses.append("COALESCE(transaction_status, 'active') = ?")
        params.append(status)
    if chapter:
        clauses.append("chapter LIKE ?")
        params.append(f"%{chapter}%")
    if date_from:
        clauses.append("order_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("order_date <= ?")
        params.append(date_to)

    where = " WHERE " + " AND ".join(clauses)
    sql = f"SELECT * FROM items{where} ORDER BY order_date DESC, id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2)


@mcp.tool()
def get_transaction_by_id(transaction_id: int) -> str:
    """Get a single transaction by its ID.

    Args:
        transaction_id: The item/transaction ID
    """
    item = get_item(transaction_id)
    if not item:
        return json.dumps({"error": f"Transaction {transaction_id} not found"})
    return json.dumps(item, indent=2)


@mcp.tool()
def get_statistics() -> str:
    """Get summary statistics: total transactions, orders, spending, date range."""
    return json.dumps(get_item_stats(), indent=2)


@mcp.tool()
def get_data_quality_report() -> str:
    """Get a data quality audit: field fill rates, rows with missing data, value distributions."""
    return json.dumps(get_audit_report(), indent=2)


@mcp.tool()
def get_recent_snapshot(limit: int = 50) -> str:
    """Quick snapshot of the database: stats + most recent transactions.

    Args:
        limit: Number of recent transactions to include (default 50)
    """
    return json.dumps(get_data_snapshot(limit), indent=2)


@mcp.tool()
def list_events(chapter: str = "", upcoming_only: bool = False) -> str:
    """List all events with pricing and registration data.

    Args:
        chapter: Filter by chapter (e.g. "San Antonio", "Austin"). Empty = all.
        upcoming_only: If True, only return events where event_date >= today.

    Returns per event: item_name, event_date, course, chapter, course_cost,
    course_cost_9, course_cost_18, tgf_markup (Member rate), tgf_markup_9, tgf_markup_18,
    side_game_fee (Inc. Games admin fee), transaction_fee_pct, course_surcharge, registrations.

    Pricing notes: tgf_markup is the Member rate. Guest = Member + $10 (9h/combo) or +$15
    (18h standalone). 1st Timer = Guest - $25. side_game_fee is the included games admin fee
    (part of Event Only base price). Course cost rounds up to nearest dollar.
    """
    from datetime import date as _date
    events = get_all_events()
    if chapter:
        events = [e for e in events if (e.get("chapter") or "").lower() == chapter.lower()]
    if upcoming_only:
        today = _date.today().isoformat()
        events = [e for e in events if (e.get("event_date") or "") >= today]
    # Return pricing-relevant fields
    fields = [
        "id", "item_name", "event_date", "course", "chapter",
        "course_cost", "course_cost_9", "course_cost_18",
        "tgf_markup", "tgf_markup_9", "tgf_markup_18",
        "side_game_fee", "transaction_fee_pct", "course_surcharge",
        "registrations",
    ]
    result = [{k: e.get(k) for k in fields} for e in events]
    return json.dumps(result, indent=2)


@mcp.tool()
def get_event_registrations(event_name: str) -> str:
    """Get all registrations (active transactions) for a specific event.

    Args:
        event_name: The exact event/item name
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM items
           WHERE item_name = ? COLLATE NOCASE AND COALESCE(transaction_status, 'active') = 'active'
           ORDER BY customer ASC""",
        (event_name,),
    ).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2)


@mcp.tool()
def list_customers() -> str:
    """List all unique customers with their transaction count and total spend."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT
               customer,
               customer_email,
               customer_phone,
               COUNT(*) as transaction_count,
               MIN(order_date) as first_order,
               MAX(order_date) as last_order
           FROM items
           WHERE customer IS NOT NULL AND customer != ''
           GROUP BY customer
           ORDER BY customer ASC"""
    ).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2)


@mcp.tool()
def get_customer_details(customer_name: str) -> str:
    """Get all transactions for a specific customer.

    Args:
        customer_name: Customer name (exact match, case-insensitive)
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM items WHERE customer LIKE ? ORDER BY order_date DESC",
        (customer_name,),
    ).fetchall()
    conn.close()
    if not rows:
        return json.dumps({"error": f"No transactions found for '{customer_name}'"})
    return json.dumps([dict(r) for r in rows], indent=2)


@mcp.tool()
def search_transactions(query: str, limit: int = 50) -> str:
    """Full-text search across customer, item name, course, chapter, order ID, and email subject.

    Args:
        query: Search term
        limit: Max results (default 50)
    """
    conn = get_connection()
    like = f"%{query}%"
    rows = conn.execute(
        """SELECT * FROM items
           WHERE customer LIKE ? OR item_name LIKE ? OR course LIKE ?
              OR chapter LIKE ? OR order_id LIKE ? OR subject LIKE ?
           ORDER BY order_date DESC LIMIT ?""",
        (like, like, like, like, like, like, limit),
    ).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  WRITE TOOLS
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def update_transaction(transaction_id: int, fields: dict) -> str:
    """Update fields on a transaction.

    Args:
        transaction_id: The item/transaction ID to update
        fields: Dict of field names to new values. Allowed fields:
                customer, customer_email, customer_phone, order_id,
                item_name, item_price, quantity, chapter, course,
                handicap, side_games, tee_choice, user_status,
                post_game, returning_or_new, shirt_size,
                guest_name, date_of_birth, net_points_race,
                gross_points_race, city_match_play, fellowship,
                notes, holes
    """
    ok = update_item(transaction_id, fields)
    if ok:
        return json.dumps({"status": "ok", "updated_id": transaction_id})
    return json.dumps({"error": f"Transaction {transaction_id} not found or no valid fields"})


@mcp.tool()
def credit_transaction(transaction_id: int, note: str = "") -> str:
    """Mark a transaction as credited (money held for future event).

    Args:
        transaction_id: The transaction ID to credit
        note: Optional note explaining the credit
    """
    ok = credit_item(transaction_id, note)
    if ok:
        return json.dumps({"status": "ok", "credited_id": transaction_id})
    return json.dumps({"error": f"Transaction {transaction_id} not found or already credited/transferred"})


@mcp.tool()
def transfer_transaction(transaction_id: int, target_event: str, note: str = "") -> str:
    """Transfer a transaction to a different event. Creates a new $0 registration at the target event.

    Args:
        transaction_id: The original transaction ID to transfer
        target_event: The exact event name to transfer to
        note: Optional note
    """
    result = transfer_item(transaction_id, target_event, note)
    if result:
        return json.dumps({"status": "ok", "original_id": transaction_id, "new_item": result})
    return json.dumps({"error": f"Transfer failed — transaction {transaction_id} not found or already credited/transferred"})


@mcp.tool()
def undo_credit_or_transfer(transaction_id: int) -> str:
    """Reverse a credit or transfer, restoring the original transaction to active status.

    Args:
        transaction_id: The credited/transferred transaction ID
    """
    ok = reverse_credit(transaction_id)
    if ok:
        return json.dumps({"status": "ok", "restored_id": transaction_id})
    return json.dumps({"error": f"Transaction {transaction_id} not found or not in credited/transferred state"})


@mcp.tool()
def create_new_event(
    event_name: str,
    event_date: str = "",
    course: str = "",
    chapter: str = "",
    course_cost: float = None,
    tgf_markup: float = None,
    side_game_fee: float = None,
    transaction_fee_pct: float = None,
) -> str:
    """Create a new event.

    Args:
        event_name: The event name (must be unique)
        event_date: Event date in YYYY-MM-DD format
        course: Golf course name
        chapter: Chapter/city where event is held
        course_cost: Course/vendor cost per player (rounds up to nearest dollar in pricing calc)
        tgf_markup: TGF markup per player (Member rate; Guest/1st Timer derived automatically)
        side_game_fee: Included games admin fee (part of base Event Only price, labeled "Inc. Games" in UI)
        transaction_fee_pct: Transaction fee percentage (default 3.5)
    """
    ev = create_event(event_name, event_date or None, course or None, chapter or None,
                      course_cost=course_cost, tgf_markup=tgf_markup,
                      side_game_fee=side_game_fee, transaction_fee_pct=transaction_fee_pct)
    if ev:
        return json.dumps({"status": "ok", "event": ev})
    return json.dumps({"error": f"Event '{event_name}' already exists"})


@mcp.tool()
def update_existing_event(event_id: int, fields: dict) -> str:
    """Update fields on an event.

    Args:
        event_id: The event ID to update
        fields: Dict of fields to update. Allowed: item_name, event_date, course, chapter,
                event_type, course_cost, tgf_markup (Member rate), side_game_fee (Inc. Games),
                transaction_fee_pct. For combo events also: course_cost_9, course_cost_18,
                tgf_markup_9, tgf_markup_18, side_game_fee_9, side_game_fee_18.
    """
    ok = update_event(event_id, fields)
    if ok:
        return json.dumps({"status": "ok", "updated_id": event_id})
    return json.dumps({"error": f"Event {event_id} not found or no valid fields"})


@mcp.tool()
def delete_existing_event(event_id: int) -> str:
    """Delete an event by ID.

    Args:
        event_id: The event ID to delete
    """
    ok = delete_event(event_id)
    if ok:
        return json.dumps({"status": "ok", "deleted_id": event_id})
    return json.dumps({"error": f"Event {event_id} not found"})


@mcp.tool()
def add_player(
    event_name: str,
    customer: str,
    side_games: str = "",
    tee_choice: str = "",
    handicap: str = "",
    user_status: str = "",
) -> str:
    """Add a comp'd player to an event (creates a $0 transaction).

    Args:
        event_name: The exact event name
        customer: Player's full name
        side_games: NET, GROSS, BOTH, or NONE
        tee_choice: <50, 50-64, 65+, or Forward
        handicap: Numeric handicap value
        user_status: MEMBER, 1st TIMER, GUEST, MANAGER, etc.
    """
    item = add_player_to_event(
        event_name, customer, side_games=side_games, tee_choice=tee_choice,
        handicap=handicap, user_status=user_status,
    )
    if item:
        return json.dumps({"status": "ok", "item": item})
    return json.dumps({"error": "Failed to add player"})


@mcp.tool()
def delete_transaction(transaction_id: int) -> str:
    """Permanently delete a transaction. This cannot be undone.

    Args:
        transaction_id: The transaction ID to delete
    """
    ok = delete_item(transaction_id)
    if ok:
        return json.dumps({"status": "ok", "deleted_id": transaction_id})
    return json.dumps({"error": f"Transaction {transaction_id} not found"})


@mcp.tool()
def sync_events() -> str:
    """Auto-create events from transaction data. Scans items and creates event records for any new events found."""
    result = sync_events_from_items()
    return json.dumps({"status": "ok", **result})


@mcp.tool()
def run_autofix() -> str:
    """Run all data quality autofixes: normalize side games, customer names, course names, and item names."""
    result = autofix_all()
    return json.dumps({"status": "ok", **result})


@mcp.tool()
def reextract_order(order_id: str) -> str:
    """Re-parse an order's original email to backfill coupon and other missing fields.

    Fetches the original email from Microsoft Graph, re-runs AI extraction,
    and updates coupon_code, coupon_amount, and other backfill fields on all
    rows sharing this order_id. Useful for backfilling coupon data on
    historical orders for sales tax reporting.

    Args:
        order_id: The GoDaddy order ID (e.g. "R854482675")
    """
    import requests as _requests

    base_url = os.environ.get("TRACKER_URL", "https://tgf-tracker.up.railway.app")
    admin_pin = os.environ.get("ADMIN_PIN", "")

    # Call the Flask endpoint which handles email fetching + AI extraction
    session = _requests.Session()
    # Login first
    session.post(f"{base_url}/api/login", json={"pin": admin_pin})
    resp = session.post(
        f"{base_url}/api/audit/reextract-order",
        json={"order_id": order_id},
    )
    if resp.status_code != 200:
        return json.dumps({"error": resp.text, "status_code": resp.status_code})
    return json.dumps(resp.json(), indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  RSVP TOOLS
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_event_rsvps(event_name: str) -> str:
    """Get the latest RSVP status (PLAYING/NOT PLAYING) for each player at an event.

    Args:
        event_name: The exact event/item name
    """
    rsvps = get_rsvps_for_event(event_name)
    if not rsvps:
        return json.dumps({"message": f"No RSVPs found for '{event_name}'"})
    return json.dumps(rsvps, indent=2)


@mcp.tool()
def search_rsvps(event: str = "", response: str = "") -> str:
    """Search RSVPs with optional filters.

    Args:
        event: Filter by event name (partial match)
        response: Filter by response: PLAYING or NOT PLAYING
    """
    return json.dumps(get_all_rsvps(event_name=event, response=response), indent=2)


@mcp.tool()
def get_rsvp_summary() -> str:
    """Get RSVP summary statistics: total, playing, not playing, matched, unmatched."""
    return json.dumps(get_rsvp_stats(), indent=2)


@mcp.tool()
def rematch_all_rsvps() -> str:
    """Re-run matching logic on all unmatched RSVPs. Useful after adding new events or transactions."""
    result = rematch_rsvps()
    return json.dumps({"status": "ok", **result})


# ── Expense & Action Item Tools ──────────────────────────────────────

@mcp.tool()
def get_expense_transactions(date_from: str = "", date_to: str = "",
                             source_type: str = "", review_status: str = "",
                             limit: int = 50) -> str:
    """Get expense transactions (Chase alerts, Venmo, receipts).

    Args:
        date_from: Start date YYYY-MM-DD
        date_to: End date YYYY-MM-DD
        source_type: Filter by source (chase_alert, venmo, receipt, manual)
        review_status: Filter by status (pending, approved, corrected, ignored)
        limit: Max results (default 50)
    """
    from email_parser.database import get_expense_transactions as _get
    return json.dumps(_get(
        date_from=date_from or None, date_to=date_to or None,
        source_type=source_type or None, review_status=review_status or None,
        limit=limit,
    ), indent=2)


@mcp.tool()
def get_action_items(status: str = "", category: str = "", limit: int = 50) -> str:
    """Get action items that need attention (contracts, inquiries, etc.).

    Args:
        status: Filter by status (open, in_progress, completed, dismissed)
        category: Filter by category (contract, payment, member_inquiry, course_correspondence, other)
        limit: Max results (default 50)
    """
    from email_parser.database import get_action_items as _get
    return json.dumps(_get(
        status=status or None, category=category or None, limit=limit,
    ), indent=2)


@mcp.tool()
def get_pending_review_count() -> str:
    """Get count of items needing review across all queues (expenses, actions, uncategorized accounting)."""
    from email_parser.database import get_pending_review_count as _get
    return json.dumps(_get(), indent=2)


# ── Reconciliation Tools ─────────────────────────────────────────────

@mcp.tool()
def get_reconciliation_summary(month: str) -> str:
    """Get bank reconciliation summary for a month: matched/unmatched counts and dollar totals.

    Args:
        month: Month in YYYY-MM format (e.g. "2026-04")
    """
    from email_parser.database import get_reconciliation_summary as _get
    return json.dumps(_get(month), indent=2)


@mcp.tool()
def get_ledger_entries(account_code: str = "", date_from: str = "", date_to: str = "") -> str:
    """Get general ledger entries with optional filters.

    Args:
        account_code: Filter by account code (e.g. "4000" for Event Revenue)
        date_from: Start date YYYY-MM-DD
        date_to: End date YYYY-MM-DD
    """
    from email_parser.database import get_ledger_entries as _get
    return json.dumps(_get(
        account_code=account_code or None,
        date_from=date_from or None,
        date_to=date_to or None,
    ), indent=2)


# ── Agent Tools ──────────────────────────────────────────────────────

@mcp.tool()
def get_agent_action_log(agent_name: str = "", date_from: str = "",
                         date_to: str = "", limit: int = 50) -> str:
    """Get recent COO agent actions — what each agent did and why.

    Args:
        agent_name: Filter by agent (Chief of Staff, Financial Agent, etc.)
        date_from: Start date YYYY-MM-DD
        date_to: End date YYYY-MM-DD
        limit: Max results (default 50)
    """
    from email_parser.database import get_agent_action_log as _get
    return json.dumps(_get(
        agent_name=agent_name or None,
        date_from=date_from or None,
        date_to=date_to or None,
        limit=limit,
    ), indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)
