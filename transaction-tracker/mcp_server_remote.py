"""
TGF Transaction Tracker — Remote MCP Server

Lightweight MCP server that connects to the Railway-hosted API.
Run this on your local machine (Windows/Mac) to give Claude Desktop
direct access to your live transaction data.

Setup:
    pip install "mcp[cli]" requests
    python mcp_server_remote.py

Environment variables:
    TGF_API_URL   — Base URL of the Railway app (default: https://main-production-b95c.up.railway.app)
    TGF_ADMIN_PIN — Admin PIN for write operations that require admin auth
"""

import json
import os
import sys

import requests
from mcp.server.fastmcp import FastMCP

API_URL = os.environ.get("TGF_API_URL", "https://main-production-b95c.up.railway.app").rstrip("/")
ADMIN_PIN = os.environ.get("TGF_ADMIN_PIN", "")

mcp = FastMCP("TGF Transaction Tracker")

# ── Helpers ─────────────────────────────────────────────────────────────

_session = requests.Session()


def _login_if_needed():
    """Ensure we have an admin session cookie for write operations."""
    if not ADMIN_PIN:
        return
    if _session.cookies.get("session"):
        return
    _session.post(f"{API_URL}/api/auth/login", json={"pin": ADMIN_PIN})


def _get(path, params=None):
    resp = _session.get(f"{API_URL}{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path, data=None):
    _login_if_needed()
    resp = _session.post(f"{API_URL}{path}", json=data or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _patch(path, data=None):
    _login_if_needed()
    resp = _session.patch(f"{API_URL}{path}", json=data or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _delete(path):
    _login_if_needed()
    resp = _session.delete(f"{API_URL}{path}", timeout=30)
    resp.raise_for_status()
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════
#  READ TOOLS
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_transactions(
    customer: str = "",
    event: str = "",
    status: str = "",
    city: str = "",
    limit: int = 100,
) -> str:
    """Get all transactions from the live database. Returns the full list — use customer/event/city/status to narrow results.

    Args:
        customer: Filter by customer name (checked client-side, partial match)
        event: Filter by event/item name (checked client-side, partial match)
        status: Filter by status: active, credited, or transferred
        city: Filter by city (partial match)
        limit: Max rows to return (default 100)
    """
    items = _get("/api/items")
    # Client-side filtering (the API returns all items)
    if customer:
        items = [i for i in items if customer.lower() in (i.get("customer") or "").lower()]
    if event:
        items = [i for i in items if event.lower() in (i.get("item_name") or "").lower()]
    if status:
        items = [i for i in items if (i.get("transaction_status") or "active") == status]
    if city:
        items = [i for i in items if city.lower() in (i.get("city") or "").lower()]
    return json.dumps(items[:limit], indent=2)


@mcp.tool()
def get_transaction_by_id(transaction_id: int) -> str:
    """Get a single transaction by its ID.

    Args:
        transaction_id: The item/transaction ID
    """
    items = _get("/api/items")
    for item in items:
        if item.get("id") == transaction_id:
            return json.dumps(item, indent=2)
    return json.dumps({"error": f"Transaction {transaction_id} not found"})


@mcp.tool()
def get_statistics() -> str:
    """Get summary statistics: total transactions, orders, spending, date range."""
    return json.dumps(_get("/api/stats"), indent=2)


@mcp.tool()
def get_data_quality_report() -> str:
    """Get a data quality audit: field fill rates, rows with missing data, value distributions."""
    return json.dumps(_get("/api/audit"), indent=2)


@mcp.tool()
def get_recent_snapshot(limit: int = 50) -> str:
    """Quick snapshot: stats + most recent transactions.

    Args:
        limit: Number of recent transactions to include (default 50)
    """
    return json.dumps(_get("/api/data-snapshot", {"limit": limit}), indent=2)


@mcp.tool()
def list_events() -> str:
    """List all events with their registration counts."""
    return json.dumps(_get("/api/events"), indent=2)


@mcp.tool()
def get_event_registrations(event_name: str) -> str:
    """Get all active registrations for a specific event.

    Args:
        event_name: The exact event/item name
    """
    items = _get("/api/items")
    matches = [
        i for i in items
        if i.get("item_name") == event_name
        and (i.get("transaction_status") or "active") == "active"
    ]
    matches.sort(key=lambda x: (x.get("customer") or "").lower())
    return json.dumps(matches, indent=2)


@mcp.tool()
def list_customers() -> str:
    """List all unique customers with transaction count and date range."""
    items = _get("/api/items")
    customers = {}
    for i in items:
        name = i.get("customer") or ""
        if not name:
            continue
        if name not in customers:
            customers[name] = {
                "customer": name,
                "customer_email": i.get("customer_email"),
                "customer_phone": i.get("customer_phone"),
                "transaction_count": 0,
                "first_order": i.get("order_date"),
                "last_order": i.get("order_date"),
            }
        customers[name]["transaction_count"] += 1
        od = i.get("order_date") or ""
        if od < (customers[name]["first_order"] or "9999"):
            customers[name]["first_order"] = od
        if od > (customers[name]["last_order"] or ""):
            customers[name]["last_order"] = od
    result = sorted(customers.values(), key=lambda x: x["customer"].lower())
    return json.dumps(result, indent=2)


@mcp.tool()
def get_customer_details(customer_name: str) -> str:
    """Get all transactions for a specific customer.

    Args:
        customer_name: Customer name (case-insensitive match)
    """
    items = _get("/api/items")
    matches = [i for i in items if (i.get("customer") or "").lower() == customer_name.lower()]
    if not matches:
        return json.dumps({"error": f"No transactions found for '{customer_name}'"})
    return json.dumps(matches, indent=2)


@mcp.tool()
def search_transactions(query: str, limit: int = 50) -> str:
    """Full-text search across customer, item name, course, city, order ID.

    Args:
        query: Search term
        limit: Max results (default 50)
    """
    items = _get("/api/items")
    q = query.lower()
    matches = [
        i for i in items
        if q in (i.get("customer") or "").lower()
        or q in (i.get("item_name") or "").lower()
        or q in (i.get("course") or "").lower()
        or q in (i.get("city") or "").lower()
        or q in (i.get("order_id") or "").lower()
        or q in (i.get("subject") or "").lower()
    ]
    return json.dumps(matches[:limit], indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  WRITE TOOLS
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def update_transaction(transaction_id: int, fields: dict) -> str:
    """Update fields on a transaction.

    Args:
        transaction_id: The transaction ID to update
        fields: Dict of field names to new values (customer, item_name, city, etc.)
    """
    return json.dumps(_patch(f"/api/items/{transaction_id}", fields), indent=2)


@mcp.tool()
def credit_transaction(transaction_id: int, note: str = "") -> str:
    """Mark a transaction as credited (money held for future event).

    Args:
        transaction_id: The transaction ID to credit
        note: Optional note explaining the credit
    """
    return json.dumps(_post(f"/api/items/{transaction_id}/credit", {"note": note}), indent=2)


@mcp.tool()
def transfer_transaction(transaction_id: int, target_event: str, note: str = "") -> str:
    """Transfer a transaction to a different event.

    Args:
        transaction_id: The original transaction ID
        target_event: The exact event name to transfer to
        note: Optional note
    """
    return json.dumps(
        _post(f"/api/items/{transaction_id}/transfer", {"target_event": target_event, "note": note}),
        indent=2,
    )


@mcp.tool()
def undo_credit_or_transfer(transaction_id: int) -> str:
    """Reverse a credit or transfer, restoring the transaction to active.

    Args:
        transaction_id: The credited/transferred transaction ID
    """
    return json.dumps(_post(f"/api/items/{transaction_id}/reverse-credit"), indent=2)


@mcp.tool()
def create_new_event(event_name: str, event_date: str = "", course: str = "", city: str = "") -> str:
    """Create a new event.

    Args:
        event_name: The event name (must be unique)
        event_date: Event date YYYY-MM-DD
        course: Golf course name
        city: City
    """
    return json.dumps(
        _post("/api/events", {"item_name": event_name, "event_date": event_date, "course": course, "city": city}),
        indent=2,
    )


@mcp.tool()
def update_existing_event(event_id: int, fields: dict) -> str:
    """Update fields on an event.

    Args:
        event_id: The event ID
        fields: Dict of fields (item_name, event_date, course, city, event_type)
    """
    return json.dumps(_patch(f"/api/events/{event_id}", fields), indent=2)


@mcp.tool()
def delete_existing_event(event_id: int) -> str:
    """Delete an event. Requires admin PIN.

    Args:
        event_id: The event ID to delete
    """
    return json.dumps(_delete(f"/api/events/{event_id}"), indent=2)


@mcp.tool()
def add_player(
    event_name: str,
    customer: str,
    side_games: str = "",
    tee_choice: str = "",
    handicap: str = "",
    member_status: str = "",
) -> str:
    """Add a comp'd player to an event ($0 registration).

    Args:
        event_name: The exact event name
        customer: Player's full name
        side_games: NET, GROSS, BOTH, or NONE
        tee_choice: <50, 50-64, 65+, or Forward
        handicap: Numeric handicap
        member_status: MEMBER or NON-MEMBER
    """
    return json.dumps(
        _post("/api/events/add-player", {
            "event_name": event_name,
            "customer": customer,
            "side_games": side_games,
            "tee_choice": tee_choice,
            "handicap": handicap,
            "member_status": member_status,
        }),
        indent=2,
    )


@mcp.tool()
def delete_transaction(transaction_id: int) -> str:
    """Permanently delete a transaction. Requires admin PIN. Cannot be undone.

    Args:
        transaction_id: The transaction ID to delete
    """
    return json.dumps(_delete(f"/api/items/{transaction_id}"), indent=2)


@mcp.tool()
def sync_events() -> str:
    """Auto-create events from transaction data."""
    return json.dumps(_post("/api/events/sync"), indent=2)


@mcp.tool()
def run_autofix() -> str:
    """Run all data quality autofixes on the live database."""
    return json.dumps(_post("/api/audit/autofix-all"), indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)
