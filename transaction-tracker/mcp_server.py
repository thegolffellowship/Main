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
    city: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 100,
) -> str:
    """Search and filter transactions.

    Args:
        customer: Filter by customer name (partial match, case-insensitive)
        event: Filter by event/item name (partial match, case-insensitive)
        status: Filter by transaction status: active, credited, or transferred
        city: Filter by city (partial match, case-insensitive)
        date_from: Earliest order date (YYYY-MM-DD)
        date_to: Latest order date (YYYY-MM-DD)
        limit: Max rows to return (default 100)
    """
    conn = get_connection()
    clauses = []
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
    if city:
        clauses.append("city LIKE ?")
        params.append(f"%{city}%")
    if date_from:
        clauses.append("order_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("order_date <= ?")
        params.append(date_to)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
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
def list_events() -> str:
    """List all events with their registration counts."""
    return json.dumps(get_all_events(), indent=2)


@mcp.tool()
def get_event_registrations(event_name: str) -> str:
    """Get all registrations (active transactions) for a specific event.

    Args:
        event_name: The exact event/item name
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM items
           WHERE item_name = ? AND COALESCE(transaction_status, 'active') = 'active'
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
    """Full-text search across customer, item name, course, city, order ID, and email subject.

    Args:
        query: Search term
        limit: Max results (default 50)
    """
    conn = get_connection()
    like = f"%{query}%"
    rows = conn.execute(
        """SELECT * FROM items
           WHERE customer LIKE ? OR item_name LIKE ? OR course LIKE ?
              OR city LIKE ? OR order_id LIKE ? OR subject LIKE ?
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
                item_name, event_date, item_price, quantity, city, course,
                handicap, side_games, tee_choice, member_status,
                post_game, returning_or_new, shirt_size,
                guest_name, date_of_birth, net_points_race,
                gross_points_race, city_match_play
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
    city: str = "",
) -> str:
    """Create a new event.

    Args:
        event_name: The event name (must be unique)
        event_date: Event date in YYYY-MM-DD format
        course: Golf course name
        city: City where event is held
    """
    ev = create_event(event_name, event_date or None, course or None, city or None)
    if ev:
        return json.dumps({"status": "ok", "event": ev})
    return json.dumps({"error": f"Event '{event_name}' already exists"})


@mcp.tool()
def update_existing_event(event_id: int, fields: dict) -> str:
    """Update fields on an event.

    Args:
        event_id: The event ID to update
        fields: Dict of fields to update. Allowed: item_name, event_date, course, city, event_type
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
    member_status: str = "",
) -> str:
    """Add a comp'd player to an event (creates a $0 transaction).

    Args:
        event_name: The exact event name
        customer: Player's full name
        side_games: NET, GROSS, BOTH, or NONE
        tee_choice: <50, 50-64, 65+, or Forward
        handicap: Numeric handicap value
        member_status: MEMBER or NON-MEMBER
    """
    item = add_player_to_event(
        event_name, customer, side_games=side_games, tee_choice=tee_choice,
        handicap=handicap, member_status=member_status,
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


# ═══════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)
