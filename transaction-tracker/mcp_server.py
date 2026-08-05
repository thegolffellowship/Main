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
import re
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
    # Financial & reconciliation
    get_event_financial_summary as _get_event_financial_summary,
    get_cashflow_data as _get_cashflow_data,
    get_chart_of_accounts as _get_chart_of_accounts,
    get_ledger_entries as _get_ledger_entries,
    _connect,
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
        "'RSVP Import', 'RSVP Email Link', 'Handicap Import')"
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
def send_entry_confirmation(item_id: int) -> str:
    """Send (or re-send) the 'you're entered' confirmation email for a player's
    registered event item whose applied credit covered the entry fee — the
    manual / retroactive path for registrations made before the auto-email
    (Kerry 2026-07-16). force=True, so it sends regardless of balance.

    Args:
        item_id: items.id of the player's registered event item.
    """
    from email_parser import database as db
    return json.dumps(db.send_entry_confirmation_email(item_id, force=True),
                      indent=2, default=str)


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
        event_name: The event/item name (canonical or any registered alias)
    """
    conn = get_connection()
    # Resolve through event_aliases both directions, like the UI roster does:
    # the given name may be an alias of a canonical event, and roster rows may
    # carry alias spellings (e.g. "TGF CHAMPIONSHIP" vs "2026 TGF CHAMPIONSHIP").
    row = conn.execute(
        "SELECT canonical_event_name FROM event_aliases WHERE alias_name = ? COLLATE NOCASE",
        (event_name,),
    ).fetchone()
    canonical = row["canonical_event_name"] if row else event_name
    alias_rows = conn.execute(
        "SELECT alias_name FROM event_aliases WHERE canonical_event_name = ? COLLATE NOCASE",
        (canonical,),
    ).fetchall()
    names = {canonical.lower()} | {r["alias_name"].lower() for r in alias_rows}
    placeholders = ",".join("?" for _ in names)
    rows = conn.execute(
        f"""SELECT * FROM items
            WHERE LOWER(item_name) IN ({placeholders})
              AND COALESCE(transaction_status, 'active') = 'active'
            ORDER BY customer ASC""",
        tuple(names),
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


@mcp.tool()
def get_season_contest_enrollments(
    contest_type: str = "", chapter: str = "", season: str = ""
) -> str:
    """List season contest enrollments (NET Points Race, GROSS Points Race, City Match Play).

    Args:
        contest_type: Exact contest name: 'NET Points Race', 'GROSS Points Race', or 'City Match Play' (empty = all)
        chapter: Exact chapter name, e.g. 'Austin' (empty = all)
        season: Season year, e.g. '2026' (empty = all)
    """
    from email_parser.database import get_season_contest_enrollments as _enr
    rows = _enr(contest_type or None, chapter or None, season or None)
    return json.dumps(rows, indent=2)


@mcp.tool()
def get_season_contest_removals(
    contest_type: str = "", chapter: str = "", season: str = ""
) -> str:
    """List season contest removal records — the permanent audit trail of
    enrollments removed via the Enrollment tab (who, when, why, refund
    amount/method, note).

    Args:
        contest_type: Exact contest name: 'NET Points Race', 'GROSS Points Race', or 'City Match Play' (empty = all)
        chapter: Exact chapter name, e.g. 'Austin' (empty = all)
        season: Season year, e.g. '2026' (empty = all)
    """
    from email_parser.database import get_season_contest_removals as _rem
    rows = _rem(contest_type or None, chapter or None, season or None)
    return json.dumps(rows, indent=2)


@mcp.tool()
def get_customer_profile(customer_name: str = "", customer_id: int = 0) -> str:
    """Full identity snapshot for one customer: the canonical customers row,
    emails, aliases, status history, membership terms, handicap link, contest
    enrollments + removals, and a transaction summary. Use this to diagnose
    identity problems (split profiles, nameless shells, wrong links) —
    get_customer_details only returns items rows.

    Args:
        customer_name: Canonical or partial name (used when customer_id is 0)
        customer_id: Exact customer_id (takes precedence over name)
    """
    conn = get_connection()
    try:
        if customer_id:
            cust = conn.execute(
                "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
            ).fetchone()
            if not cust:
                return json.dumps({"error": f"No customer with id {customer_id}"})
        else:
            if not (customer_name or "").strip():
                return json.dumps({"error": "Provide customer_name or customer_id"})
            matches = conn.execute(
                """SELECT * FROM customers
                   WHERE LOWER(TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))) = LOWER(TRIM(?))
                      OR TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) LIKE ?
                   ORDER BY customer_id""",
                (customer_name, f"%{customer_name.strip()}%"),
            ).fetchall()
            if not matches:
                return json.dumps({"error": f"No customer matching '{customer_name}'"})
            if len(matches) > 1:
                return json.dumps({
                    "error": f"{len(matches)} customers match '{customer_name}' — call again with customer_id",
                    "candidates": [
                        {"customer_id": m["customer_id"],
                         "name": ((m["first_name"] or "") + " " + (m["last_name"] or "")).strip(),
                         "chapter": m["chapter"]}
                        for m in matches
                    ],
                }, indent=2)
            cust = matches[0]

        cid = cust["customer_id"]
        canonical_name = ((cust["first_name"] or "") + " " + (cust["last_name"] or "")).strip()
        profile = {"customer": dict(cust), "canonical_name": canonical_name}
        if not canonical_name:
            profile["warning"] = (
                "NAMELESS SHELL PROFILE — blank first/last names. Rows linked "
                "to this id display blank; likely needs naming or merging."
            )

        def _rows(sql, params=()):
            try:
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
            except Exception as e:  # table may not exist on old DBs
                return [{"error": str(e)}]

        profile["emails"] = _rows(
            "SELECT * FROM customer_emails WHERE customer_id = ? ORDER BY is_primary DESC", (cid,))
        profile["aliases"] = _rows(
            "SELECT * FROM customer_aliases WHERE customer_id = ?", (cid,))
        profile["status_history"] = _rows(
            """SELECT s.status_name, cs.set_at, cs.notes
               FROM customer_statuses cs JOIN statuses s ON s.status_id = cs.status_id
               WHERE cs.customer_id = ? ORDER BY cs.set_at DESC LIMIT 5""", (cid,))
        profile["memberships"] = _rows(
            "SELECT * FROM customer_memberships WHERE customer_id = ? ORDER BY started_at DESC", (cid,))
        profile["handicap_links"] = _rows(
            "SELECT * FROM handicap_player_links WHERE customer_id = ?", (cid,))
        profile["season_contests"] = _rows(
            "SELECT * FROM season_contests WHERE customer_id = ? ORDER BY season DESC, contest_type", (cid,))
        profile["season_contest_removals"] = _rows(
            "SELECT * FROM season_contest_removals WHERE customer_id = ? ORDER BY removed_at DESC", (cid,))
        summary = conn.execute(
            """SELECT COUNT(*) AS n_items, MIN(order_date) AS first_order,
                      MAX(order_date) AS last_order
               FROM items WHERE customer_id = ?""", (cid,)).fetchone()
        profile["items_summary"] = dict(summary)
        return json.dumps(profile, indent=2)
    finally:
        conn.close()


@mcp.tool()
def list_customer_contacts(chapter: str = "", status: str = "") -> str:
    """Bulk contact export for cross-referencing against external rosters
    (Golf Genius, spreadsheets): one compact row per non-vendor customer
    with customer_id, name, chapter, status, primary email, Venmo handle,
    and phone.

    Args:
        chapter: Exact chapter filter, e.g. 'Austin' (empty = all)
        status: current_player_status filter, e.g. 'active_member' (empty = all)
    """
    conn = get_connection()
    try:
        clauses = ["""NOT EXISTS (SELECT 1 FROM customer_roles r
                      WHERE r.customer_id = c.customer_id AND r.role_type = 'vendor')"""]
        params = []
        if chapter:
            clauses.append("c.chapter = ?")
            params.append(chapter)
        if status:
            clauses.append("c.current_player_status = ?")
            params.append(status)
        rows = conn.execute(
            f"""SELECT c.customer_id,
                       TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')) AS name,
                       c.chapter, c.current_player_status AS status,
                       ce.email AS primary_email, c.venmo_username AS venmo, c.phone
                FROM customers c
                LEFT JOIN customer_emails ce
                       ON ce.customer_id = c.customer_id AND ce.is_primary = 1
                WHERE {' AND '.join(clauses)}
                ORDER BY c.last_name COLLATE NOCASE, c.first_name COLLATE NOCASE""",
            params,
        ).fetchall()
        return json.dumps([dict(r) for r in rows], indent=1)
    finally:
        conn.close()


@mcp.tool()
def get_customer_data_audit() -> str:
    """Identity-health audit across ALL customers in one call — the checks
    get_customer_profile runs for one person, swept over everyone:
    nameless shell profiles, same-name profile groups (potential unmerged
    splits), customers with no email / no primary email, emails shared by
    multiple profiles, dangling customer_id references (rows pointing at
    deleted profiles), and unlinked rows (NULL customer_id) per identity
    table. Row lists are capped at 25 each; every section carries its full
    count. An empty section means that check is clean.
    """
    from email_parser.database import _KNOWN_DISTINCT_SAME_NAME
    conn = get_connection()
    try:
        report = {}

        def _section(sql, params=(), cap=25):
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
            return {"count": len(rows), "rows": rows[:cap]}

        # 1. Nameless shell profiles (the Stu Kirksey failure shape)
        report["nameless_profiles"] = _section(
            """SELECT customer_id, phone, chapter, current_player_status,
                      (SELECT COUNT(*) FROM items i WHERE i.customer_id = c.customer_id) AS n_items
               FROM customers c
               WHERE TRIM(COALESCE(first_name,'') || COALESCE(last_name,'')) = ''"""
        )

        # 2. Same-name profile groups — potential unmerged splits.
        groups = conn.execute(
            """SELECT LOWER(TRIM(first_name)) || ' ' || LOWER(TRIM(last_name)) AS k,
                      GROUP_CONCAT(customer_id) AS cids, COUNT(*) AS n
               FROM customers
               WHERE TRIM(COALESCE(first_name,'')) != '' AND TRIM(COALESCE(last_name,'')) != ''
               GROUP BY k HAVING n > 1"""
        ).fetchall()
        dupes = []
        for g in groups:
            cid_set = frozenset(int(x) for x in g["cids"].split(","))
            entry = {"name": g["k"], "customer_ids": sorted(cid_set)}
            if cid_set in _KNOWN_DISTINCT_SAME_NAME:
                entry["note"] = "confirmed distinct people — OK"
            dupes.append(entry)
        report["same_name_profiles"] = {"count": len(dupes), "rows": dupes[:25]}

        # 3. Customers with no email anywhere / no primary email.
        #    Uncapped list, annotated with any email still recoverable from
        #    their old order rows (candidates for promotion to the profile),
        #    and with the vendor role where assigned.
        report["no_email"] = _section(
            """SELECT c.customer_id,
                      TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')) AS name,
                      c.chapter, c.current_player_status,
                      (SELECT COUNT(*) FROM items i WHERE i.customer_id = c.customer_id) AS n_items,
                      (SELECT i.customer_email FROM items i
                       WHERE i.customer_id = c.customer_id
                         AND TRIM(COALESCE(i.customer_email, '')) != ''
                       ORDER BY i.order_date DESC LIMIT 1) AS items_email_candidate,
                      (SELECT GROUP_CONCAT(role_type) FROM customer_roles r
                       WHERE r.customer_id = c.customer_id) AS roles
               FROM customers c
               WHERE NOT EXISTS (SELECT 1 FROM customer_emails e WHERE e.customer_id = c.customer_id)
               ORDER BY c.customer_id""",
            cap=100,
        )
        report["no_primary_email"] = _section(
            """SELECT c.customer_id,
                      TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')) AS name
               FROM customers c
               WHERE EXISTS (SELECT 1 FROM customer_emails e WHERE e.customer_id = c.customer_id)
                 AND NOT EXISTS (SELECT 1 FROM customer_emails e
                                 WHERE e.customer_id = c.customer_id AND e.is_primary = 1)"""
        )

        # 4. Emails attached to multiple profiles (cross-person contamination)
        report["shared_emails"] = _section(
            """SELECT email, GROUP_CONCAT(customer_id) AS customer_ids, COUNT(*) AS n
               FROM customer_emails GROUP BY LOWER(TRIM(email)) HAVING n > 1"""
        )

        # 5. Dangling customer_id references (rows pointing at deleted profiles)
        dangling = {}
        for table, col in (
            ("items", "customer_id"), ("customer_emails", "customer_id"),
            ("customer_aliases", "customer_id"), ("season_contests", "customer_id"),
            ("season_contest_removals", "customer_id"),
            ("handicap_player_links", "customer_id"), ("handicap_rounds", "customer_id"),
            ("rsvps", "customer_id"), ("customer_memberships", "customer_id"),
            ("customer_statuses", "customer_id"), ("acct_transactions", "customer_id"),
            ("tgf_payouts", "customer_id"), ("cmp_pool_members", "customer_id"),
        ):
            try:
                n = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {table} WHERE {col} IS NOT NULL "
                    f"AND {col} NOT IN (SELECT customer_id FROM customers)"
                ).fetchone()["c"]
                if n:
                    dangling[table] = n
            except Exception:
                pass
        report["dangling_customer_ids"] = dangling  # empty dict = clean

        # 6. Unlinked rows (NULL customer_id) per identity table — active
        #    items only; placeholder merchants excluded like the dashboard.
        unlinked = {}
        try:
            unlinked["items_active"] = conn.execute(
                """SELECT COUNT(*) AS c FROM items
                   WHERE customer_id IS NULL
                     AND COALESCE(transaction_status, 'active') = 'active'
                     AND merchant NOT IN ('Roster Import', 'Customer Entry',
                                          'RSVP Import', 'RSVP Email Link', 'Handicap Import')"""
            ).fetchone()["c"]
        except Exception:
            pass
        for table in ("season_contests", "handicap_player_links", "rsvps",
                      "customer_aliases"):
            try:
                unlinked[table] = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {table} WHERE customer_id IS NULL"
                ).fetchone()["c"]
            except Exception:
                pass
        report["unlinked_rows"] = {k: v for k, v in unlinked.items() if v}

        # 6b. The unlinked RSVP rows themselves — names/emails/events so the
        #     admin can identify who each belongs to. Known FB-ad-lead
        #     senders (never played, no profile wanted) are segregated into
        #     their own count instead of being flagged.
        from email_parser.database import _RSVP_KNOWN_NON_CUSTOMERS
        all_unlinked = conn.execute(
            """SELECT id, player_name, player_email, gg_event_name, event_date,
                      response, matched_event
               FROM rsvps WHERE customer_id IS NULL
               ORDER BY event_date DESC, player_name"""
        ).fetchall()
        actionable, known_leads = [], []
        for r in all_unlinked:
            d = dict(r)
            if (d.get("player_email") or "").strip().lower() in _RSVP_KNOWN_NON_CUSTOMERS:
                known_leads.append(d)
            else:
                actionable.append(d)
        report["unlinked_rsvp_rows"] = {"count": len(actionable),
                                        "rows": actionable[:50]}
        report["known_lead_rsvps"] = {
            "count": len(known_leads),
            "senders": sorted({(d.get("player_email") or "").lower()
                               for d in known_leads}),
        }

        # 7. Name aliases that equal ANOTHER customer's canonical name —
        #    orders under that name resolve to the alias owner, not the
        #    person (fine when intentional, e.g. spouse payment accounts —
        #    listed for review, not necessarily wrong).
        report["aliases_shadowing_other_customers"] = _section(
            """SELECT ca.alias_value, ca.customer_id AS alias_owner_cid,
                      TRIM(COALESCE(o.first_name,'') || ' ' || COALESCE(o.last_name,'')) AS alias_owner,
                      c2.customer_id AS shadowed_cid
               FROM customer_aliases ca
               JOIN customers o ON o.customer_id = ca.customer_id
               JOIN customers c2
                 ON LOWER(TRIM(COALESCE(c2.first_name,'') || ' ' || COALESCE(c2.last_name,''))) =
                    LOWER(TRIM(ca.alias_value))
                AND c2.customer_id != ca.customer_id
               WHERE ca.alias_type = 'name'"""
        )

        report["total_customers"] = conn.execute(
            "SELECT COUNT(*) AS c FROM customers").fetchone()["c"]
        return json.dumps(report, indent=2)
    finally:
        conn.close()


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
                transaction_fee_pct, nine_side ('Front'|'Back' — which nine the 9-hole leg
                plays; shotgun pairing labels follow, Back = 10A/10B...).
                For combo events also: course_cost_9, course_cost_18,
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
def sync_season_contests() -> str:
    """Scan purchases and sync season contest enrollments (same as the
    Enrollment tab's 'Sync from Purchases' button). Idempotent — returns
    {enrolled, linked}; enrolled should be 0 when nothing new was purchased."""
    from email_parser.database import sync_season_contests_from_items
    result = sync_season_contests_from_items()
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
def get_reconciliation_dashboard() -> str:
    """Per-account reconciliation status: last import date, bank balance,
    book balance, variance, and count of unmatched/partial deposits."""
    from email_parser.database import get_reconciliation_dashboard as _get
    return json.dumps(_get(), indent=2)


@mcp.tool()
def get_reconciliation_summary(month: str) -> str:
    """Monthly P&L summary from the reconciliation system: income by category,
    expenses by category, total transactions, reconciled transaction count,
    and reconciliation percentage.

    Args:
        month: Month in YYYY-MM format (e.g. "2026-04")
    """
    from email_parser.database import get_monthly_reconciliation as _get
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
#  FINANCIAL & RECONCILIATION TOOLS
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_event_financial_summary(event_name: str) -> str:
    """Get full financial picture for an event: income, contra, net revenue, course fees,
    prize pool, projected profit, reconciliation count, and verified/fallback path indicator.

    Args:
        event_name: The exact event name (case-insensitive)
    """
    result = _get_event_financial_summary(event_name)
    return json.dumps(result, indent=2)


@mcp.tool()
def get_acct_transactions(
    event_name: str = "",
    category: str = "",
    entry_type: str = "",
    status: str = "active",
    limit: int = 100,
) -> str:
    """Query accounting transactions (the single-source-of-truth ledger).

    Args:
        event_name: Filter by event name (exact, case-insensitive)
        category: Filter by category (registration, processing_fee, addon, refund,
                  godaddy_order, godaddy_batch, transfer_in, transfer_out, comp, credit_issued)
        entry_type: Filter by type (income, expense, contra, liability)
        status: Filter by status (active, reversed, reconciled, merged). Default: active
        limit: Max rows (default 100)
    """
    clauses = []
    params = []
    if event_name:
        clauses.append("event_name = ? COLLATE NOCASE")
        params.append(event_name)
    if category:
        clauses.append("category = ?")
        params.append(category)
    if entry_type:
        clauses.append("entry_type = ?")
        params.append(entry_type)
    if status:
        clauses.append("COALESCE(status, 'active') = ?")
        params.append(status)
    else:
        # Default: exclude soft-deleted Duplicate Detective rows and
        # reversed entries so callers don't unknowingly aggregate them.
        clauses.append("COALESCE(status, 'active') NOT IN ('reversed', 'merged')")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT id, date, description, entry_type, category, amount,
                       net_deposit, merchant_fee, source, source_ref,
                       event_name, customer, customer_id, order_id, status
                FROM acct_transactions{where}
                ORDER BY date DESC, id DESC LIMIT ?""",
            params,
        ).fetchall()
    return json.dumps([dict(r) for r in rows], indent=2)


@mcp.tool()
def get_bank_deposits(
    account_id: int = 0,
    status: str = "",
    month: str = "",
    limit: int = 100,
) -> str:
    """Query imported bank statement deposits with match status.

    Args:
        account_id: Filter by bank account ID (0 = all)
        status: Filter by match status (unmatched, partial, matched)
        month: Filter by month in YYYY-MM format
        limit: Max rows (default 100)
    """
    clauses = []
    params = []
    if account_id:
        clauses.append("d.account_id = ?")
        params.append(account_id)
    if status:
        clauses.append("d.status = ?")
        params.append(status)
    if month:
        clauses.append("d.deposit_date LIKE ?")
        params.append(f"{month}%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT d.id, ba.name as account_name, ba.account_type,
                       d.deposit_date, d.description, d.amount,
                       d.status, d.raw_data as source_ref
                FROM bank_deposits d
                LEFT JOIN acct_accounts ba ON ba.id = d.account_id
                {where}
                ORDER BY d.deposit_date DESC, d.id DESC LIMIT ?""",
            params,
        ).fetchall()
    return json.dumps([dict(r) for r in rows], indent=2)


@mcp.tool()
def get_reconciliation_detail(month: str) -> str:
    """Get full reconciliation detail for a month: matched/unmatched deposits and transactions,
    dollar totals, and period close status.

    Args:
        month: Month in YYYY-MM format (e.g. "2026-04")
    """
    with _connect() as conn:
        # All deposits for the month
        deposits = conn.execute(
            """SELECT d.id, d.deposit_date, d.description, d.amount, d.status,
                      ba.name as account_name
               FROM bank_deposits d
               LEFT JOIN acct_accounts ba ON ba.id = d.account_id
               WHERE d.deposit_date LIKE ?
               ORDER BY d.deposit_date""",
            (f"{month}%",),
        ).fetchall()

        # Matches for those deposits
        deposit_ids = [d["id"] for d in deposits]
        matches = []
        if deposit_ids:
            placeholders = ",".join("?" * len(deposit_ids))
            matches = conn.execute(
                f"""SELECT rm.bank_deposit_id, rm.acct_transaction_id,
                           rm.match_confidence, rm.match_type,
                           t.amount as txn_amount, t.description as txn_description,
                           t.category, t.source_ref
                    FROM reconciliation_matches rm
                    JOIN acct_transactions t ON t.id = rm.acct_transaction_id
                    WHERE rm.bank_deposit_id IN ({placeholders})""",
                deposit_ids,
            ).fetchall()

        # Unmatched accounting transactions for the month
        unmatched_txns = conn.execute(
            """SELECT id, date, description, amount, category, source_ref, entry_type
               FROM acct_transactions
               WHERE date LIKE ? AND entry_type = 'income'
                 AND COALESCE(status, 'active') = 'active'
                 AND id NOT IN (SELECT acct_transaction_id FROM reconciliation_matches)
               ORDER BY date""",
            (f"{month}%",),
        ).fetchall()

        # Period close status
        period_close = conn.execute(
            "SELECT * FROM period_closings WHERE period = ?",
            (month,),
        ).fetchone()

    # Build match map
    match_map = {}
    for m in matches:
        dep_id = m["bank_deposit_id"]
        if dep_id not in match_map:
            match_map[dep_id] = []
        match_map[dep_id].append(dict(m))

    matched_dollars = sum(d["amount"] for d in deposits if d["status"] == "matched")
    unmatched_dollars = sum(d["amount"] for d in deposits if d["status"] != "matched")

    return json.dumps({
        "month": month,
        "deposits": [
            {**dict(d), "matches": match_map.get(d["id"], [])}
            for d in deposits
        ],
        "unmatched_transactions": [dict(r) for r in unmatched_txns],
        "summary": {
            "total_deposits": len(deposits),
            "matched_deposits": sum(1 for d in deposits if d["status"] == "matched"),
            "unmatched_deposits": sum(1 for d in deposits if d["status"] != "matched"),
            "matched_dollars": matched_dollars,
            "unmatched_dollars": unmatched_dollars,
            "unmatched_transactions": len(unmatched_txns),
        },
        "period_closed": bool(period_close),
    }, indent=2)


@mcp.tool()
def get_cashflow_summary() -> str:
    """Get weekly cash flow data: expected income, confirmed income, projected expenses,
    actual expenses, net, running balance, and warning flags. Returns ~13 weeks by default."""
    result = _get_cashflow_data()
    return json.dumps(result, indent=2)


@mcp.tool()
def get_acct_allocations(
    event_name: str = "",
    month: str = "",
    limit: int = 100,
) -> str:
    """Query per-player cost allocations: course payable, prize pool, TGF operating,
    GoDaddy fee, tax reserve, total collected.

    Args:
        event_name: Filter by event name (exact, case-insensitive)
        month: Filter by month in YYYY-MM format (matches allocation_date)
        limit: Max rows (default 100)
    """
    clauses = []
    params = []
    if event_name:
        clauses.append("event_name = ? COLLATE NOCASE")
        params.append(event_name)
    if month:
        clauses.append("allocation_date LIKE ?")
        params.append(f"{month}%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT order_id, item_id, event_name, chapter, allocation_date,
                       course_payable, prize_pool, tgf_operating, godaddy_fee,
                       tax_reserve, total_collected, allocation_status, payment_method
                FROM acct_allocations{where}
                ORDER BY allocation_date DESC, id DESC LIMIT ?""",
            params,
        ).fetchall()
    return json.dumps([dict(r) for r in rows], indent=2)


@mcp.tool()
def get_godaddy_order_splits(
    event_name: str = "",
    split_type: str = "",
    limit: int = 100,
) -> str:
    """Query GoDaddy order split details: registration, transaction fee, merchant fee,
    and coupon components per order.

    Args:
        event_name: Filter by event name (exact, case-insensitive)
        split_type: Filter by split type (registration, transaction_fee, merchant_fee, coupon)
        limit: Max rows (default 100)
    """
    clauses = []
    params = []
    if event_name:
        clauses.append("s.event_name = ? COLLATE NOCASE")
        params.append(event_name)
    if split_type:
        clauses.append("s.split_type = ?")
        params.append(split_type)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT s.id, s.transaction_id, s.item_id, s.event_name,
                       s.customer, s.split_type, s.amount,
                       t.date as transaction_date, t.status as transaction_status
                FROM godaddy_order_splits s
                JOIN acct_transactions t ON t.id = s.transaction_id
                {where}
                ORDER BY t.date DESC, s.id DESC LIMIT ?""",
            params,
        ).fetchall()
    return json.dumps([dict(r) for r in rows], indent=2)


@mcp.tool()
def get_chart_of_accounts() -> str:
    """Get the full chart of accounts: code, name, account type, Schedule C line, active status."""
    result = _get_chart_of_accounts()
    return json.dumps(result, indent=2)


@mcp.tool()
def get_mcp_ledger_entries(
    account_code: str = "",
    date_from: str = "",
    date_to: str = "",
    reconciled: int = -1,
    limit: int = 200,
) -> str:
    """Get general ledger entries with optional filters.

    Args:
        account_code: Filter by account code (e.g. "4000" for Event Revenue)
        date_from: Start date YYYY-MM-DD
        date_to: End date YYYY-MM-DD
        reconciled: Filter by reconciled status (0=no, 1=yes, -1=all). Default: all
        limit: Max rows (default 200)
    """
    result = _get_ledger_entries(
        account_code=account_code or None,
        date_from=date_from or None,
        date_to=date_to or None,
        reconciled=reconciled if reconciled >= 0 else None,
        limit=limit,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def get_venmo_transactions(
    direction: str = "",
    category: str = "",
    month: str = "",
    limit: int = 100,
) -> str:
    """Query Venmo accounting transactions (source = 'venmo').

    Args:
        direction: Filter by direction: 'in' (income) or 'out' (expense/contra)
        category: Filter by category (addon, prize_payout, refund, event_expense, miscellaneous)
        month: Filter by month in YYYY-MM format
        limit: Max rows (default 100)
    """
    clauses = ["source = 'venmo'"]
    params = []
    if direction == "in":
        clauses.append("entry_type = 'income'")
    elif direction == "out":
        clauses.append("entry_type IN ('expense', 'contra')")
    if category:
        clauses.append("category = ?")
        params.append(category)
    if month:
        clauses.append("date LIKE ?")
        params.append(f"{month}%")
    clauses.append("COALESCE(status, 'active') = 'active'")
    where = " WHERE " + " AND ".join(clauses)
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT date, description, customer, amount, category,
                       entry_type, source_ref, status
                FROM acct_transactions{where}
                ORDER BY date DESC, id DESC LIMIT ?""",
            params,
        ).fetchall()
    return json.dumps([dict(r) for r in rows], indent=2)


# Background GG-history walks (v2.74.1): MCP clients time out around 60s,
# but a portal's hole-by-hole walk wants minutes. holes-bg= runs the walk
# in a daemon thread inside the web process; holes-status polls it. One
# walk per subdomain at a time (guarded), last result kept for pickup.
_GGH_BG: dict = {}


def _scoring_dispatch(url: str, extract: str):
    """Bridge for MCP sessions whose cached tool inventory predates the
    v2.23 scoring tools (client sessions freeze the tool list at session
    start). Special extract values on probe_golf_genius reach the scoring
    layer through a tool every session already has. Remove once stale
    sessions have aged out.

      scoring-import:<event_code>  import_gg_scorecards(url, event_code)
      scoring-rounds:<event>       list imported rounds for an event
      scoring-verify:<round_id>    verify one round vs GG's numbers
      scoring-card:<round_id>      full scorecard with derivations
      scoring-courses              course/tee database listing
      scoring-mvp-import           import_gg_event_mvps(widget_url)
      scoring-mvp-recompute[:event] self-compute City/TGF MVP badges (split -> Co-)
      scoring-games-import         import_gg_game_results(widget_url) — GG-recorded CTP/LP/HIO/TEAM Net winners
      scoring-flights-import       import_gg_game_flights(widget_url) — per-game flight membership
      scoring-game-results:<event>|<game>|<flights>  shadow-computed winners for one game
      scoring-gg-results:<event>   GG-recorded winners for one event
      scoring-hcp-preview:<event>  read-only self-derived handicap preview
      scoring-hcp-import:<event>[|apply]  self-derive handicap rounds (WHS NDB)
                                   |apply also auto-emails the chapter recap
      scoring-hcp-recap:<event>    (re)send the chapter-manager recap email
      scoring-mp-reconcile75[:<season>|<chapter>|<allow>]  match-play reconcile
                                   with off-lowest per-chapter allowance
      scoring-mp-lock-one:<chapter>|<A>|<B>[|apply]  manually lock one
                                   Kerry-confirmed match with no GG card
      scoring-import-event:<event_code>[@<round_id>][|refresh=<A>[,<B>]]
                                   targeted scorecard backfill for one past
                                   event (ALL Net → ALL Gross); refresh=
                                   force-replaces named players' stale cards;
                                   url = the portal widget
      scoring-facilities           facility census (course registry v1)
      scoring-mp-import-gg[:<round>|verify[:<round>]]  snapshot GG's own
                                   match-play detail (start hole + NET per-hole
                                   winner/strokes) onto cmp_matches; url = the
                                   tournament_results widget
    """
    if not extract.startswith("scoring-"):
        return None
    cmd, _, arg = extract.partition(":")
    arg = arg.strip()
    from email_parser import database as db
    try:
        if cmd == "scoring-champ-live":
            # Read-only diagnostic: what the live-overlay endpoint computes
            # RIGHT NOW in this process — champ scoring/field/errors + the
            # top rows, or the exact exception. Added championship morning
            # 2026-08-01 when member landings kept falling back to the
            # season view and nothing outside the process could see why.
            race = (arg or "san_antonio_net").strip()
            try:
                d = db.get_points_race_live(race)
                rows = (d.get("standings") or [])[:5]
                live = db.fetch_champ_points(race)
                return json.dumps({
                    "race": race,
                    "champ_scoring": d.get("champ_scoring"),
                    "champ_field": d.get("champ_field"),
                    "champ": d.get("champ"),
                    "champ_absorbed": d.get("champ_absorbed"),
                    "race_final": d.get("race_final"),
                    "n_standings": len(d.get("standings") or []),
                    "top": [{k: r.get(k) for k in
                             ("player_name", "rank", "total_points",
                              "season_points", "champ_points", "champ_thru",
                              "move", "points_reset")} for r in rows],
                    # plus-handicap deductions in force (Kerry 2026-08-01)
                    "plus_adjusted": [
                        {"name": p.get("name"),
                         "plus": p.get("plus_adjustment"),
                         "board_raw": p.get("points_raw"),
                         "points": p.get("points")}
                        for p in live.get("players", [])
                        if p.get("plus_adjustment")],
                }, indent=2, default=str)
            except Exception as e:
                import traceback
                return json.dumps({"race": race, "EXCEPTION": repr(e),
                                   "trace": traceback.format_exc()[-1500:]},
                                  indent=2)
        if cmd == "scoring-import":
            # "scoring-import:<event_code>" or, for multi-round days,
            # "scoring-import:<event_code>@<gg_league_round_id>"
            code, _, rkey = arg.partition("@")
            return json.dumps(
                db.import_gg_scorecards(url, event_code=code.strip() or None,
                                        round_key=rkey.strip() or None), indent=2)
        if cmd == "scoring-rounds":
            return json.dumps(
                db.get_scoring_rounds_list(None, arg or None, None, 200), indent=2)
        if cmd == "scoring-verify":
            return json.dumps(db.verify_scoring_round(int(arg)), indent=2)
        if cmd == "scoring-card":
            card = db.get_scorecard(int(arg))
            return json.dumps(card if card else {"error": "not found"}, indent=2)
        if cmd == "scoring-courses":
            return json.dumps(db.list_courses(), indent=2)
        if cmd == "scoring-parity":
            return json.dumps(db.get_differential_parity(), indent=2)
        if cmd == "scoring-mvp-import":
            # url = tournament_results widget (optionally &round=<id>);
            # time-budgeted — call repeatedly until rounds_left == 0
            return json.dumps(db.import_gg_event_mvps(url), indent=2)
        if cmd == "scoring-print-pack":
            # GATE-1 dry-run: return the assembled Starter Sheet / Cart Signs
            # data for an event (get_event_print_pack) so the printables can be
            # rendered + fitness-checked against real saved pairings. Read-only.
            return json.dumps(db.get_event_print_pack(int(arg.strip())),
                              indent=2, default=str)
        if cmd == "scoring-audit-mvp":
            # H-1 results hardening: our City MVP vs GG's recorded MVP for
            # every event before the retroactivity boundary. arg = cutoff date
            # (default 2026-07-14). Read-only; returns the mismatch list.
            return json.dumps(
                db.audit_pre_boundary_mvp(arg.strip() or "2026-07-14"),
                indent=2, default=str)
        if cmd == "scoring-mp-standings-diff":
            # #217 step 1 (READ-ONLY): recompute both chapters' Match Play
            # pool standings under the ratified D-MP-09 rule (first-3-by-date
            # counting, points-of-3 w/ ½-ties, aggregate H2H) and diff against
            # the live standings used to seed the knockouts. verdict='clean'
            # iff no advancer/winner-runnerup change anywhere. Changes nothing.
            return json.dumps(db.cmp_standings_diff_dmp09(), indent=2,
                              default=str)
        if cmd == "scoring-mp-reconcile":
            # READ-ONLY (Kerry 2026-07-17): derive each Match Play match's
            # result from imported GG per-hole scores (net = gross-pops) and
            # diff vs our stored winner/margin. Reports the non-aligning ones.
            # arg: "" (all) or "<season>|<chapter>".
            _s, _sep, _c = (arg or "").partition("|")
            return json.dumps(db.cmp_reconcile_hole_results(
                season=(_s.strip() or None), chapter=(_c.strip() or None)),
                indent=2, default=str)
        if cmd == "scoring-mp-relabel-extrahole":
            # Kerry 2026-07-17: relabel the two a9.17 extra-hole margins stored
            # as '1 UP' → '10H' (Ryder Cup: holes played + H). Winner/records/
            # seeding untouched. arg "apply" writes; anything else is dry-run.
            # GENERAL FORM (v2.125.2): a "|"-separated arg relabels ONE match:
            #   <chapter>|<playerA>|<playerB>|<to>|<expect_margin>[|apply][|force]
            # ("force" relabels even a result-locked row and refreshes its lock
            # note — for Kerry-directed label corrections like 1Up → Putt Off).
            a2 = (arg or "").strip()
            if "|" in a2:
                _p = [x.strip() for x in a2.split("|")]
                if len(_p) < 5:
                    return json.dumps({"error": "need <chapter>|<A>|<B>|<to>|"
                                       "<expect_margin>[|apply][|force]"})
                flags = [f.lower() for f in _p[5:]]
                _upd = [{"players": [_p[1], _p[2]], "to": _p[3],
                         "expect_margin": _p[4] or None,
                         "force": "force" in flags}]
                return json.dumps(db.cmp_relabel_margins(
                    _upd, chapter=_p[0] or None,
                    apply="apply" in flags), indent=2, default=str)
            _apply = a2.lower() == "apply"
            _upd = [
                {"players": ["Luke Youngs", "Mike Marques"], "to": "10H",
                 "expect_margin": "1 UP", "expect_winner": "Luke Youngs"},
                {"players": ["Kelly Barna", "Neal Cloer"], "to": "10H",
                 "expect_margin": "1 UP", "expect_winner": "Kelly Barna"},
            ]
            return json.dumps(db.cmp_relabel_margins(
                _upd, chapter="Austin", apply=_apply), indent=2, default=str)
        if cmd == "scoring-mp-live":
            # Test the live GG match-play fetch. arg: "<chapter>|<A>|<B>"
            _p = [x.strip() for x in (arg or "").split("|")]
            if len(_p) < 3:
                return json.dumps({"error": "need <chapter>|<A>|<B>"})
            return json.dumps(db.cmp_fetch_live_match(_p[0], _p[1], _p[2],
                              max_age=0), indent=2, default=str)
        if cmd == "scoring-mp-detail":
            # READ-ONLY dump of a stored gg_match_detail.
            # arg: "<chapter>|<playerA>|<playerB>"
            _p = [x.strip() for x in (arg or "").split("|")]
            if len(_p) < 3:
                return json.dumps({"error": "need <chapter>|<A>|<B>"})
            return json.dumps(db.cmp_gg_detail_dump(_p[0], _p[1], _p[2]),
                              indent=2, default=str)
        if cmd == "scoring-mp-lock":
            # Harden GG-verified results (Kerry 2026-07-20). arg:
            # "<season>|<chapter>[|apply]" — default dry-run; "apply" writes
            # result_locked_at/note on every match whose stored result matches
            # GG's own card (or is the recorded extra-holes outcome of a GG
            # AS). Conflicts/no-card rows are reported, never locked.
            _p = [x.strip() for x in (arg or "").split("|")]
            _season = _p[0] if len(_p) > 0 and _p[0] else None
            _chapter = _p[1] if len(_p) > 1 and _p[1] else None
            _apply = len(_p) > 2 and _p[2].lower() == "apply"
            return json.dumps(db.cmp_lock_verified_results(
                _season, _chapter, apply=_apply), indent=2, default=str)
        if cmd == "scoring-mp-lock-one":
            # Manual lock for a played match GG never published a card for
            # (no_gg_card class) — the result is Kerry-confirmed, not
            # GG-verified (Kerry 2026-07-20, the last 2 of 30). arg:
            # "<chapter>|<playerA>|<playerB>[|apply]" — default dry-run.
            _p = [x.strip() for x in (arg or "").split("|")]
            if len(_p) < 3:
                return json.dumps({"error": "need <chapter>|<A>|<B>[|apply]"})
            return json.dumps(db.cmp_lock_match_manual(
                _p[0], _p[1], _p[2],
                apply=(len(_p) > 3 and _p[3].lower() == "apply")),
                indent=2, default=str)
        if cmd == "scoring-import-event":
            # Targeted scorecard backfill for ONE past event (older than the
            # auto-sync's newest-N window): find the event's round on the
            # widget's round selector and import ALL Net → ALL Gross.
            # arg: "<event_code>[@<gg_round_id>][|refresh=<A>[,<B>...]]";
            # refresh= force-replaces the named players' STALE stored cards
            # (GG post-import score corrections — deletes their round +
            # holes + bridged handicap rows first, then re-imports fresh).
            # url = the portal's tournament_results widget.
            a1, _, rest = arg.partition("|")
            code, _, rkey = a1.partition("@")
            refresh = None
            if rest.strip().lower().startswith("refresh="):
                refresh = [p.strip() for p in
                           rest.strip()[8:].split(",") if p.strip()]
            return json.dumps(db.import_event_scorecards_by_code(
                url, code.strip(), only_round=(rkey.strip() or None),
                refresh_players=refresh), indent=2, default=str)
        if cmd == "scoring-mp-encode-allowance":
            # Author the uniform allowance config version (Kerry-ratified
            # 2026-07-20). arg: "[<value>][|apply]" — default 0.75, dry-run.
            _p = [x.strip() for x in (arg or "").split("|")]
            _v = float(_p[0]) if _p and _p[0] else 0.75
            return json.dumps(db.cmp_encode_uniform_allowance(
                _v, apply=("apply" in [x.lower() for x in _p])),
                indent=2, default=str)
        if cmd == "scoring-payouts-unlink":
            # Repair: unlink a wrongly-matched receipt from payout rows —
            # "<acct_transaction_id>". Rows revert to unpaid; the ledger
            # row itself is untouched.
            _aid = int(arg.strip())
            with db._connect(None) as _c:
                _n = _c.execute(
                    "UPDATE tgf_payouts SET acct_transaction_id = NULL, "
                    "paid_at = NULL WHERE acct_transaction_id = ?",
                    (_aid,)).rowcount
                _c.commit()
            return json.dumps({"acct_transaction_id": _aid,
                               "payout_rows_unlinked": _n}, indent=2)
        if cmd == "scoring-payouts-restore":
            # Repair: rebuild deleted tgf_payouts rows from their surviving
            # bulk-confirm ledger mirrors — "<tgf_events code>[|apply]".
            # rpartition + mode check: event codes themselves contain pipes
            # ("s18.3 SAN ANTONIO KICKOFF | Cedar Creek"), so only a LAST
            # segment that literally reads "apply" is treated as the mode.
            _ev, _sep, _mode = arg.rpartition("|")
            if _mode.strip().lower() == "apply" and _sep:
                _apply = True
            else:
                _ev, _apply = arg, False
            return json.dumps(db.restore_tgf_payouts_from_ledger(
                _ev.strip(), apply=_apply), indent=2, default=str)
        if cmd == "scoring-payouts-restore-explicit":
            # Stage-2 repair for rows with no ledger mirror: arg is a JSON
            # list of {id, event_code, customer_id, customer_name,
            # category, amount, date} optionally followed by "|apply".
            _payload, _sep, _mode = arg.rpartition("|")
            if _mode.strip().lower() == "apply" and _sep:
                _rows, _apply2 = json.loads(_payload), True
            else:
                _rows, _apply2 = json.loads(arg), False
            return json.dumps(db.restore_tgf_payouts_explicit(
                _rows, apply=_apply2), indent=2, default=str)
        if cmd == "scoring-item-note":
            # Repair: set an item's credit_note — "<item_id>|<note>".
            # Built for stamping 'balance_due:X.XX' on credit-transfer
            # rows whose apply ran under the fee-inclusive math bug
            # (John White s9.20: server said owed $0, truth $17).
            _iid, _, _note = arg.partition("|")
            with db._connect(None) as _c:
                _n2 = _c.execute(
                    "UPDATE items SET credit_note = ? WHERE id = ?",
                    (_note.strip(), int(_iid.strip()))).rowcount
                _c.commit()
            return json.dumps({"item_id": int(_iid.strip()),
                               "updated": _n2}, indent=2)
        if cmd == "scoring-refund-sweep":
            # Run the refund auto-matcher on demand over ALL ingested
            # P2P receipts (watch verification + the watchless pass) —
            # for receipts that landed while the sweep was unreachable.
            return json.dumps(db.auto_match_refund_watches(),
                              indent=2, default=str)
        if cmd == "scoring-credit-payout":
            # Record an already-sent credit refund — "<item_id>|<method>|
            # <date>|<note>". Delegates to db.payout_credit (same stamp +
            # ledger entry as the in-app Refund flow). Kerry 2026-07-20:
            # the Jeff Rideout $19.15 was Venmo'd under his alias 'Paul
            # Rideout', so the console never saw it complete.
            _p = [x.strip() for x in arg.split("|")]
            return json.dumps(db.payout_credit(
                int(_p[0]), method=_p[1] if len(_p) > 1 else "Venmo",
                refund_date=_p[2] if len(_p) > 2 else "",
                note=_p[3] if len(_p) > 3 else ""), indent=2, default=str)
        if cmd == "scoring-hio-gross":
            # "<subdomain>[|<start>][|<end>][|<budget_s>]" — EXACT field
            # sizes counted off the live GG ALL Gross boards (2025 HIO
            # pot reconstruction). Fetch-only, resumable.
            from email_parser import gg_history as _ggh
            _p = [x.strip() for x in arg.split("|")]
            return json.dumps(_ggh.hio_gross_field_counts(
                _p[0],
                start_date=_p[1] if len(_p) > 1 and _p[1] else "2025-08-11",
                end_date=_p[2] if len(_p) > 2 and _p[2] else "2025-12-31",
                budget_seconds=int(_p[3]) if len(_p) > 3 and _p[3] else 150),
                indent=2, default=str)
        if cmd == "scoring-south-ledger-repair":
            # One-off (2026-07-20): my mistaken 7/16 payout_credit on item
            # 2270 double-booked $74 next to the receipt-promoted entry,
            # and Daniel's real 7/16 payment ($18.59 excess credit) has no
            # ledger entry (its receipt #1626 was misparsed). Idempotent.
            with db._connect(None) as _c:
                _del = _c.execute(
                    "DELETE FROM acct_transactions "
                    "WHERE source_ref = 'credit-payout-2270'").rowcount
                _dup = _c.execute(
                    "SELECT id FROM acct_transactions "
                    "WHERE source_ref = 'south-excess-20260716'").fetchone()
                if not _dup:
                    db._write_acct_entry(
                        _c, item_id=2270, event_name="s9.18 CEDAR CREEK",
                        customer="Daniel South", customer_id=24,
                        order_id="R882685638",
                        entry_type="expense", category="refund",
                        source="venmo", amount=18.59,
                        description=("Excess credit refund (Venmo): Daniel "
                                     "South — s9.18 CEDAR CREEK (paid "
                                     "2026-07-16; receipt #1626 misparsed)"),
                        account="Venmo",
                        source_ref="south-excess-20260716",
                        date="2026-07-16")
                _c.commit()
            return json.dumps({"deleted_duplicate_74_entries": _del,
                               "added_18_59_entry": not _dup})
        if cmd == "scoring-hio-pot":
            # Live pot audit: full get_hio_pot payload (carry-in, per-event
            # lines with player counts, paid out, total).
            return json.dumps(db.get_hio_pot(), indent=2, default=str)
        if cmd == "scoring-setting-set":
            # "<key>|<value>" — write an app_settings dial ("stored as a
            # setting is our standard for everything" — Kerry).
            _k, _, _v = arg.partition("|")
            db.set_app_setting(_k.strip(), _v.strip())
            return json.dumps({"key": _k.strip(), "value": _v.strip(),
                               "saved": True})
        if cmd == "scoring-setting-get":
            # "<key>" — read an app_settings dial (null when unset, i.e.
            # the code default applies).
            _k = arg.strip()
            return json.dumps({"key": _k,
                               "value": db.get_app_setting(_k)})
        if cmd == "scoring-champ-card":
            # "<race_key>|<customer_id>" — one player's championship
            # hole-by-hole card (same payload as the member champ-card
            # endpoint; lets a session verify the card path end-to-end).
            _race, _, _cid = arg.partition("|")
            return json.dumps(db.fetch_champ_player_card(
                _race.strip(), int(_cid.strip())), indent=2, default=str)
        if cmd == "scoring-credit-stamp":
            # "<item_id>|<method>|<date>|<note>" — stamp refunded WITHOUT
            # a ledger write (receipt already promoted to acct_transactions;
            # payout_credit here would double-book).
            _p = [x.strip() for x in arg.split("|")]
            return json.dumps(db.stamp_credit_refunded(
                int(_p[0]), method=_p[1] if len(_p) > 1 else "Venmo",
                refund_date=_p[2] if len(_p) > 2 else "",
                note=_p[3] if len(_p) > 3 else ""), indent=2, default=str)
        if cmd == "scoring-hio-archive":
            # "<subdomain>[,<subdomain>...]" — per-event field sizes +
            # games-matrix HIO contributions from the GG History archive
            # (2025 pot carry-in reconstruction, Kerry 2026-07-20).
            from email_parser import gg_history as _ggh
            _subs = [s.strip() for s in arg.split(",") if s.strip()]
            return json.dumps(_ggh.hio_archive_events(_subs),
                              indent=2, default=str)
        if cmd == "scoring-alias-add":
            # "<customer canonical name>|<alias name>" — records a NAME
            # alias (e.g. the Venmo account name a member pays under).
            _canon, _, _alias = arg.partition("|")
            with db._connect(None) as _c:
                _dup = _c.execute(
                    "SELECT id FROM customer_aliases WHERE customer_name = ? "
                    "AND alias_type = 'name' AND alias_value = ? COLLATE NOCASE",
                    (_canon.strip(), _alias.strip())).fetchone()
                if not _dup:
                    _c.execute(
                        "INSERT INTO customer_aliases (customer_name, "
                        "alias_type, alias_value) VALUES (?, 'name', ?)",
                        (_canon.strip(), _alias.strip()))
                    _c.commit()
            return json.dumps({"customer": _canon.strip(),
                               "alias": _alias.strip(),
                               "added": not bool(_dup)}, indent=2)
        if cmd == "scoring-refund-watch-cancel":
            # Cancel an open (unverified) refund watch — "<name>|<amount>
            # [|apply]". Kerry 2026-07-20: an In-Flight row for a Venmo
            # he never actually sent needed clearing; watches had no
            # cancel path.
            _parts = [x.strip() for x in arg.split("|")]
            _nm = _parts[0] if _parts else ""
            _amt = float(_parts[1]) if len(_parts) > 1 and _parts[1] else None
            _apply3 = len(_parts) > 2 and _parts[2].lower() == "apply"
            with db._connect(None) as _c:
                db._ensure_refund_watch_table(_c)
                _q = ("SELECT id, customer_name, amount, method, handle, "
                      "initiated_at FROM refund_watches "
                      "WHERE verified_at IS NULL")
                _ws = [dict(w) for w in _c.execute(_q).fetchall()
                       if _nm.lower() in (w["customer_name"] or "").lower()
                       and (_amt is None
                            or abs(float(w["amount"]) - _amt) < 0.005)]
                if _apply3:
                    for w in _ws:
                        _c.execute("DELETE FROM refund_watches WHERE id = ?",
                                   (w["id"],))
                    _c.commit()
            return json.dumps({"matched": _ws, "cancelled": _apply3},
                              indent=2, default=str)
        if cmd == "scoring-credit-info":
            # Debug: run the SAME credit analysis the Apply Credit modal
            # uses for a GG RSVP — "<rsvp_id>". Returns the payload or
            # the traceback, so player-specific failures are diagnosable
            # without the phone.
            import traceback as _tb
            try:
                _res = db.get_rsvp_credit_info(int(arg.strip()))
                return json.dumps({"rsvp_id": int(arg.strip()),
                                   "result": _res}, indent=2, default=str)
            except Exception:
                return json.dumps({"rsvp_id": arg.strip(),
                                   "traceback": _tb.format_exc()}, indent=2)
        if cmd == "scoring-rainout-audit":
            # READ-ONLY: unlabeled shut-down candidates (active status,
            # >=50% credited registrations) + already-labeled events.
            return json.dumps(db.rainout_audit(), indent=2, default=str)
        if cmd == "scoring-rainout-label":
            # Stamp a washout: "<event>[|<badge>][|apply]" (badge default
            # RAINED OUT; dry-run default).
            _p = [x.strip() for x in arg.split("|")]
            _badge = _p[1] if len(_p) > 1 and _p[1].lower() != "apply" \
                else "RAINED OUT"
            return json.dumps(db.label_event_rainout(
                _p[0], badge=_badge,
                apply=("apply" in [x.lower() for x in _p])),
                indent=2, default=str)
        if cmd == "scoring-hio-pot":
            # READ-ONLY: running Hole-In-One pot (per-event matrix
            # contributions minus recorded HIO payouts).
            return json.dumps(db.get_hio_pot(), indent=2, default=str)
        if cmd == "scoring-payouts-clear-auto":
            # Remove an event's auto-recorded payout rows + their PENDING
            # ledger entries (matched Venmo never touched). For wrongly
            # auto-recorded events, e.g. the s9.18 Cedar Creek rain-out.
            # "<event>|all" ALSO removes manual/screenshot rows
            # (Kerry-directed only).
            _ev, _, _mode = arg.partition("|")
            return json.dumps(db.clear_event_auto_payouts(
                _ev.strip(), include_manual=(_mode.strip().lower() == "all")),
                indent=2, default=str)
        if cmd == "scoring-referrals":
            # Referral fee tracking (v2.140.0): sync (coupon scan => comped
            # — the redeemed coupon IS the compensation, Kerry 2026-07-28;
            # receipt scan => paid) then return the console payload.
            sync = db.sync_referral_fees()
            return json.dumps({"sync": sync, **db.get_referral_fees()},
                              indent=2, default=str)
        if cmd == "scoring-referral-link":
            # "<fee_id>|<customer_id>" — set the referrer on a fee whose
            # coupon token was ambiguous ('jesse' → which Jesse).
            _p = [x.strip() for x in arg.split("|")]
            return json.dumps(db.link_referral_fee_referrer(
                int(_p[0]), int(_p[1])), indent=2)
        if cmd == "scoring-referral-paid":
            # "<fee_id>|<method>|<date>|<note>" — manual completion for a
            # fee paid outside the receipt flow (cash / unreadable memo).
            _p = [x.strip() for x in arg.split("|")]
            return json.dumps(db.mark_referral_fee_paid(
                int(_p[0]), method=_p[1] if len(_p) > 1 and _p[1] else "Venmo",
                paid_date=_p[2] if len(_p) > 2 and _p[2] else None,
                note=_p[3] if len(_p) > 3 else ""), indent=2)
        if cmd == "scoring-refunds-overview":
            # READ-ONLY: the REFUNDS console payload (outstanding / in-flight
            # / completed) — incl. season-contest removal refunds.
            return json.dumps(db.get_refunds_overview(), indent=2, default=str)
        if cmd == "scoring-recurring":
            # Recurring payment registry: sync from expense history + list
            # with overdue/due-soon flags and monthly/annual totals.
            return json.dumps(db.get_recurring_payments(), indent=2, default=str)
        if cmd == "scoring-recurring-set":
            # "<merchant>|<monthly|annual>|<amount>|<category>|<notes>"
            _p = [x.strip() for x in arg.split("|")]
            return json.dumps(db.set_recurring_payment(
                _p[0], _p[1],
                amount=float(_p[2]) if len(_p) > 2 and _p[2] else None,
                category=_p[3] if len(_p) > 3 and _p[3] else None,
                notes=_p[4] if len(_p) > 4 and _p[4] else None),
                indent=2, default=str)
        if cmd == "scoring-expense-patch":
            # JSON: {"id": <expense_id>, "fields": {category, event_name,
            #   transaction_type, customer_id, merchant, append_note}}
            _p = json.loads(arg)
            return json.dumps(db.patch_expense_row(
                int(_p["id"]), _p.get("fields") or {}), indent=2, default=str)
        if cmd == "scoring-add-payment":
            # JSON: {"event": <event name>, "customer": <player>,
            #   "item": "BOTH Games", "amount": "$100.00", "source": "Venmo",
            #   "date": "YYYY-MM-DD", "note": ...} — records a +PAY child on
            # the player's active registration, same path as the UI Add
            # Payment modal (alias-aware parent lookup, allocation + addon
            # ledger entry). Mailbox #276 item C (Robert Straiton) is the
            # first use.
            _p = json.loads(arg)
            _r = db.add_payment_to_event(
                event_name=_p["event"], customer=_p["customer"],
                payment_item=_p.get("item", ""),
                payment_amount=_p.get("amount", ""),
                payment_source=_p.get("source", ""),
                note=_p.get("note", ""),
                order_date=_p.get("date", ""))
            if _r is None:
                _r = {"error": "no active registration found for that "
                               "customer on that event"}
            return json.dumps(_r, indent=2, default=str)
        if cmd == "scoring-acct-patch":
            # JSON: {"id": <acct_transaction_id>, "fields": {entity,
            #   category, event, append_note}} — connectivity patch for
            # ledger rows with no backing expense row (old imports).
            _p = json.loads(arg)
            return json.dumps(db.patch_acct_row(
                int(_p["id"]), _p.get("fields") or {}), indent=2, default=str)
        if cmd == "scoring-statement-reconcile":
            # JSON payload: {"account": "7680", "statement": "chase 2026-01",
            #   "create_missing": true, "lines": [{date, desc, amount, kind}]}
            # Matches actual statement lines against the books; unmatched
            # lines become ledger entries (idempotent per account+date+amt).
            _p = json.loads(arg)
            return json.dumps(db.reconcile_statement_lines(
                str(_p.get("account") or ""), str(_p.get("statement") or ""),
                _p.get("lines") or [],
                create_missing=bool(_p.get("create_missing", True)),
                account_name=_p.get("account_name"),
                account_type=_p.get("account_type") or "credit_card",
                institution=_p.get("institution")),
                indent=2, default=str)
        if cmd == "scoring-money-flow":
            # "<YYYY-MM>[|austin|sa][|ytd][|debug]" — Monthly Money Flow
            # waterfall (mailbox #242): pass-through vs TGF-keep,
            # allocation-bucket rollup, optional chapter scope + YTD.
            _parts = [p.strip().lower() for p in arg.split("|") if p.strip()]
            _m = _parts[0] if _parts else ""
            _dbg = "debug" in _parts[1:]
            _ytd = "ytd" in _parts[1:]
            _ch = next((p for p in _parts[1:] if p not in ("debug", "ytd")), None)
            if _ch in ("sa", "san antonio"):
                _ch = "San Antonio"
            elif _ch == "austin":
                _ch = "Austin"
            return json.dumps(db.get_monthly_money_flow(
                _m, debug=_dbg, chapter=_ch, ytd=_ytd), indent=2, default=str)
        if cmd == "scoring-overpayments":
            # Overpaid-winnings ledger (v2.141.0): runs the inbound-receipt
            # recovery scan, then returns open + recently resolved rows.
            _rec = db.recover_tgf_overpayments()
            return json.dumps({"recovery_scan": _rec,
                               "overpayments": db.get_tgf_overpayments()},
                              indent=2, default=str)
        if cmd == "scoring-overpay-resolve":
            # "<id>|<status>|<method>|<date>|<note>" — manually close (or
            # reopen) an overpayment: status recovered | waived | open.
            _p = [x.strip() for x in arg.split("|")]
            return json.dumps(db.resolve_tgf_overpayment(
                int(_p[0]),
                status=_p[1] if len(_p) > 1 and _p[1] else "recovered",
                method=_p[2] if len(_p) > 2 and _p[2] else None,
                date=_p[3] if len(_p) > 3 and _p[3] else None,
                note=_p[4] if len(_p) > 4 and _p[4] else None),
                indent=2, default=str)
        if cmd == "scoring-facilities":
            # READ-ONLY: facilities + their courses (course registry v1).
            with db._connect(None) as _c:
                _rows = [dict(r) for r in _c.execute(
                    """SELECT f.facility_id, f.name AS facility, f.city,
                              f.state, COUNT(c.course_id) AS courses,
                              GROUP_CONCAT(c.name, ' | ') AS course_names
                         FROM facilities f
                         LEFT JOIN courses c ON c.facility_id = f.facility_id
                        GROUP BY f.facility_id
                        HAVING COUNT(c.course_id) != 1
                        ORDER BY courses DESC, f.name""").fetchall()]
                _tot = _c.execute("SELECT COUNT(*) n FROM facilities").fetchone()["n"]
            return json.dumps({"total_facilities": _tot,
                               "non_1to1_facilities": _rows}, indent=2,
                              default=str)
        if cmd == "scoring-mp-pools-audit":
            # READ-ONLY: distinct (chapter, season) in cmp_pools + counts.
            return json.dumps(db.cmp_pools_audit(), indent=2, default=str)
        if cmd == "scoring-mp-import-gg":
            # Kerry 2026-07-17 (schema-ratified): walk the tournament_results
            # widget (url = .../leagues/<lid>/widgets/tournament_results?
            # shared=false), pull GG's OWN match-play detail (starting hole +
            # per-hole NET winner/strokes + margin) for every match, snapshot
            # it onto cmp_matches.gg_match_detail, and report gg-vs-stored.
            # Time-budgeted — repeat until rounds_left == 0. arg forms:
            #   ""            store + verify, all rounds (budgeted)
            #   "<round_id>"  one round only
            #   "verify"      verify-only, do not store
            #   "verify:<r>"  verify-only, one round
            a = (arg or "").strip()
            store = True
            rnd = None
            reset = False
            if a.startswith("verify"):
                store = False
                rnd = a.partition(":")[2].strip() or None
            elif a == "reset":
                reset = True
            elif a:
                rnd = a
            return json.dumps(db.cmp_import_gg_match_play(
                url, only_round=rnd, store=store, reset=reset),
                indent=2, default=str)
        if cmd == "scoring-mp-reconcile75":
            # READ-ONLY (Kerry 2026-07-17): the CORRECT match-play reconciler.
            # Re-derives each match from imported GG per-hole GROSS using TGF's
            # real OFF-LOWEST pops with PER-CHAPTER allowance (San Antonio 75%,
            # Austin 100%). Supersedes scoring-mp-reconcile (which used the
            # stroke-play 100% full-field strokes_received). arg: "" (all) or
            # "<season>|<chapter>" or "<season>|<chapter>|<forced_allowance>".
            _p = [x.strip() for x in (arg or "").split("|")]
            _s = _p[0] if len(_p) > 0 and _p[0] else None
            _c = _p[1] if len(_p) > 1 and _p[1] else None
            _a = float(_p[2]) if len(_p) > 2 and _p[2] else None
            return json.dumps(db.cmp_reconcile_match_play_75(
                season=_s, chapter=_c, allowance=_a), indent=2, default=str)
        if cmd == "scoring-sweep-i2":
            # I-2 (READ-ONLY): ×0.96 multiplier-removal impact — per-player
            # index with/without the 0.96 factor, delta, and whole-number PH
            # crossings at reference slopes 113/125. Decision package; gates R1.
            return json.dumps(db.sweep_i2_multiplier_removal(), indent=2,
                              default=str)
        if cmd == "scoring-mp-repin":
            # #223 (Kerry-approved 2026-07-17): author the D-MP-01..09 config
            # version and pin both 2026 season snapshots (SA + Austin) to it.
            # WRITE — gated by Kerry's explicit re-pin approval. Returns the
            # new version id/no + the pinned (season, chapter) list.
            return json.dumps(
                db.cmp_repin_2026_to_dmp_register(by=(arg.strip() or None)),
                indent=2, default=str)
        if cmd == "scoring-mvp-recompute":
            # Self-computed City MVP / TGF MVP (Kerry-ratified 2026-07-16):
            # materialize determine_tgf_mvp winners + split -> Co- into
            # event_mvp_computed so the badges read our own determination.
            # arg = event name to scope one day; empty = recompute every date.
            return json.dumps(
                db.recompute_computed_mvps(arg.strip() or None), indent=2)
        if cmd == "scoring-games-import":
            # GG-recorded CTP / Longest Putt / HIO / TEAM Net winners;
            # same widget-url contract + time budget as scoring-mvp-import.
            # "[rewalk][|event=<name>]" — event= attaches an unmapped
            # round's winners to the named calendar event (championship
            # rounds carry no [sa]N.N code; v2.188.5)
            _p = [x.strip() for x in (arg or "").split("|") if x.strip()]
            _rw = 2 if any(x.lower().startswith("rewalk") for x in _p) else 0
            _fe = next((x[6:].strip() for x in _p
                        if x.lower().startswith("event=")), None)
            return json.dumps(db.import_gg_game_results(
                url, rewalk_recent=_rw, force_event=_fe), indent=2)
        if cmd == "scoring-flight-lab":
            # "scoring-flight-lab:<event>|<game>[|min=<n>][|scale=9|18]"
            # Both flighting modes on one event's real field, graded against
            # GG's captured flights where they exist. Read-only.
            ev, _, rest = arg.partition("|")
            parts = [p.strip() for p in rest.split("|") if p.strip()]
            game = parts[0] if parts and "=" not in parts[0] else "individual_net"
            over = {}
            for p in parts:
                if p.startswith("min="):
                    over["min_flight_size"] = int(p[4:])
                elif p.startswith("scale="):
                    over["index_scale"] = p[6:]
                elif p.startswith("tie="):
                    over["tie_direction"] = p[4:]
            return json.dumps(db.ls_flight_lab(ev.strip(), game, over),
                              indent=2, default=str)
        if cmd == "scoring-flight-audit":
            # "scoring-flight-audit[:min=<n>][|scale=9|18][|limit=<n>]"
            # Grades BOTH modes against gg_game_flights across ALL past
            # multi-flight events — the empirical derivation of the flighting
            # rule (CA method option C step 2, mailbox #253). Read-only.
            over, lim = {}, 400
            for p in [x.strip() for x in arg.split("|") if x.strip()]:
                if p.startswith("min="):
                    over["min_flight_size"] = int(p[4:])
                elif p.startswith("scale="):
                    over["index_scale"] = p[6:]
                elif p.startswith("limit="):
                    lim = int(p[6:])
            return json.dumps(db.ls_flight_audit(over, limit=lim),
                              indent=2, default=str)
        if cmd == "scoring-flights-import":
            # Per-game flight membership from each flighted game's own GG
            # leaderboard (Ind Net / Ind Gross via detail fragments; Skins
            # via the Expand-All membership view); widget-url contract,
            # time-budgeted — call repeatedly until rounds_left == 0.
            # arg "reset" re-walks already-done rounds (safe upserts).
            return json.dumps(db.import_gg_game_flights(
                url, reset=(arg.strip().lower() == "reset")), indent=2)
        if cmd == "scoring-game-results":
            # Verify the shadow-computed winners for one event+game:
            # "scoring-game-results:<event>|<game>|<flights>"
            ev, _, rest = arg.partition("|")
            game, _, fl = rest.partition("|")
            return json.dumps(db.determine_event_game_results(
                ev.strip(), game.strip() or "individual_net",
                flights=int(fl or 1)), indent=2)
        if cmd == "scoring-gg-results":
            # GG-recorded winners (CTP/LP/HIO/TEAM Net) for one event
            return json.dumps(db.get_gg_game_results(arg), indent=2)
        if cmd == "scoring-rounds-orphans":
            # READ-ONLY: scoring_rounds with NO event link on a date —
            # shows exactly what identity fields the rows DO carry.
            _dt = (arg or "").strip()
            with db._connect() as conn:
                rows = [dict(r) for r in conn.execute(
                    "SELECT id, player_name, round_date, course_id, "
                    "gg_event_id, gg_round_id, gg_league_round_id, "
                    "holes_played, source, imported_at "
                    "FROM scoring_rounds WHERE event_id IS NULL "
                    + ("AND round_date LIKE ? " if _dt else "")
                    + "ORDER BY imported_at DESC LIMIT 60",
                    ((_dt + "%",) if _dt else ())).fetchall()]
            return json.dumps({"n": len(rows), "rows": rows}, indent=2,
                              default=str)
        if cmd == "scoring-link-rounds":
            # "<event name>|<YYYY-MM-DD>|<course substring>" — stamp
            # event_id on UNLINKED scoring_rounds from that date at that
            # course (repair for rounds imported before v2.188.6's
            # exact-name event resolution; the round-scan importer also
            # didn't stamp gg_league_round_id, so date+course is the
            # reliable identity). Only NULL event_id rows are touched.
            _p = [x.strip() for x in (arg or "").split("|")]
            if len(_p) != 3 or not all(_p):
                return json.dumps({"error": "need <event name>|<YYYY-MM-DD>"
                                            "|<course substring OR "
                                            "gg_event=<id,id,...>>"})
            _en, _dt, _sel = _p
            with db._connect() as conn:
                ev = conn.execute(
                    "SELECT id, item_name FROM events WHERE LOWER(item_name)"
                    " = LOWER(?)", (_en,)).fetchone()
                if not ev:
                    return json.dumps({"error": f"event {_en!r} not found"})
                if _sel.lower().startswith("gg_event="):
                    ids = [x.strip() for x in _sel[9:].split(",") if x.strip()]
                    ph = ",".join("?" * len(ids))
                    n = conn.execute(
                        f"UPDATE scoring_rounds SET event_id = ? "
                        f"WHERE round_date LIKE ? AND event_id IS NULL "
                        f"AND gg_event_id IN ({ph})",
                        (ev["id"], _dt + "%", *ids)).rowcount
                else:
                    n = conn.execute(
                        "UPDATE scoring_rounds SET event_id = ? "
                        "WHERE round_date LIKE ? AND event_id IS NULL "
                        "AND course_id IN (SELECT course_id FROM courses "
                        "WHERE name LIKE '%' || ? || '%')",
                        (ev["id"], _dt + "%", _sel)).rowcount
                conn.commit()
            return json.dumps({"event": ev["item_name"],
                               "event_id": ev["id"], "date": _dt,
                               "selector": _sel, "rounds_linked": n})
        if cmd == "scoring-tgf-event-rename":
            # "<old code>|<new code>" — rename a tgf_events row (refuses
            # to merge onto an existing code)
            _old, _, _new = arg.partition("|")
            return json.dumps(db.rename_tgf_event(_old, _new), indent=2)
        if cmd == "scoring-season-payouts":
            # Season-contest FINAL payouts (Kerry, championship evening
            # 2026-08-01). Preview by default; append |record to write.
            #   scoring-season-payouts:net|<race_key>[|record]
            #   scoring-season-payouts:mp|<chapter>|<1st>|<2nd>|<3rd>[|record]
            parts = [x.strip() for x in (arg or "").split("|") if x.strip()]
            mode = parts[0].lower() if parts else ""
            do_record = bool(parts) and parts[-1].lower() == "record"
            if do_record:
                parts = parts[:-1]
            if mode == "net" and len(parts) == 2:
                prev = db.season_race_payout_rows(parts[1])
                if prev.get("error") or not do_record:
                    return json.dumps(prev, indent=2, default=str)
                payouts = [{"golferName": r["golferName"],
                            "category": "City Net",
                            "amount": r["amount_cents"] / 100.0,
                            "description": (f"auto: {prev['label']} final "
                                            f"standings — {r['rank']} place")}
                           for r in prev["rows"]]
                rec = db.record_season_contest_payouts(
                    prev["label"], prev.get("chapter"), payouts,
                    append_category="City Net")
                return json.dumps({"assembled": prev, "recorded": rec},
                                  indent=2, default=str)
            if mode == "mp-pools" and len(parts) == 2:
                chapter = parts[1]
                prev = db.matchplay_pool_bonus_rows(chapter)
                if prev.get("error") or not do_record:
                    return json.dumps(prev, indent=2, default=str)
                payouts = [{"golferName": r["golferName"],
                            "category": "Match Play Pool",
                            "amount": r["amount_cents"] / 100.0,
                            "description": (f"auto: {chapter} City Match "
                                            f"Play — {r['rank']} bonus")}
                           for r in prev["rows"]]
                rec = db.record_season_contest_payouts(
                    f"{chapter.upper()} MATCH PLAY 2026", chapter,
                    payouts, append_category="Match Play Pool")
                return json.dumps({"assembled": prev, "recorded": rec},
                                  indent=2, default=str)
            if mode == "mp" and len(parts) >= 3:
                chapter = parts[1]
                prev = db.matchplay_final_payout_rows(chapter, parts[2:])
                if prev.get("error") or not do_record:
                    return json.dumps(prev, indent=2, default=str)
                payouts = [{"golferName": r["golferName"],
                            "category": "Match Play",
                            "amount": r["amount_cents"] / 100.0,
                            "description": (f"auto: {chapter} City Match Play "
                                            f"final — {r['rank']} place")}
                           for r in prev["rows"]]
                rec = db.record_season_contest_payouts(
                    f"{chapter.upper()} MATCH PLAY 2026", chapter,
                    payouts, append_category="Match Play")
                return json.dumps({"assembled": prev, "recorded": rec},
                                  indent=2, default=str)
            return json.dumps({"error": "usage: scoring-season-payouts:"
                                        "net|<race_key>[|record] or "
                                        "mp|<chapter>|<1st>|<2nd>|<3rd>"
                                        "[|record]"})
        if cmd == "scoring-record-payouts":
            # "scoring-record-payouts:<event>" records one event's assembled
            # winners into the PAYOUTS tab; ":ALL" bulk-populates every past
            # event (time-budgeted — repeat until events_left == 0; skips
            # events with manual payouts or already-auto-recorded ones).
            # ":ALL!" also re-records already-auto-recorded events.
            if arg.strip().upper().startswith("ALL"):
                return json.dumps(db.record_all_event_game_payouts(
                    force=arg.strip().endswith("!")), indent=2)
            asm = db.assemble_event_game_payouts(arg)
            if asm.get("error") or not asm.get("rows"):
                return json.dumps(asm, indent=2)
            return json.dumps({"assembled": asm,
                               "result": db.record_event_game_payouts(
                                   arg, asm["rows"], force=True)}, indent=2)
        if cmd == "scoring-payouts-preview":
            # assemble without writing — inspect what would be recorded
            return json.dumps(db.assemble_event_game_payouts(arg), indent=2)
        if cmd == "scoring-hcp-preview":
            # READ-ONLY: the handicap rounds we WOULD self-derive from our
            # scorecards for one event (differential + index impact per
            # player, NDB-cap vs raw-gross variants side by side). The
            # export-free path shown before it's trusted — writes nothing.
            return json.dumps(db.get_scoring_handicap_preview(arg),
                              indent=2, default=str)
        if cmd == "scoring-hcp-project":
            # READ-ONLY Task #16 parity: project each player's playing
            # handicap + per-hole stroke allocation from OUR index + the
            # selected tee (no GG input) and compare to GG's own playing
            # handicap + stored dots. Syntax:
            # scoring-hcp-project:<event>[|<allow>[|<cap>]]
            # (allowance default 1.0 = 100%, cap default none).
            parts = [p.strip() for p in arg.split("|")]
            allow = float(parts[1]) if len(parts) > 1 and parts[1] else 1.0
            cap = float(parts[2]) if len(parts) > 2 and parts[2] else None
            return json.dumps(db.project_playing_handicaps(
                parts[0], allowance=allow, max_hcp=cap),
                indent=2, default=str)
        if cmd == "scoring-entry-confirm":
            # Manual/retroactive entry-confirmation email (Kerry 2026-07-16),
            # reachable here because a session's MCP tool inventory freezes at
            # start. arg = "<item_id>[|<override_to>[|<cc>]]": item_id is the
            # registered event item; override_to redirects the send (e.g. a
            # copy to Kerry); cc overrides the admin CC — pass an empty third
            # field to suppress the default admin CC on a copy. force-sends.
            _parts = [p.strip() for p in arg.split("|")]
            _iid = int(_parts[0])
            _override = _parts[1] if len(_parts) > 1 and _parts[1] else None
            _cc = _parts[2] if len(_parts) > 2 else None
            return json.dumps(db.send_entry_confirmation_email(
                _iid, force=True, override=_override, cc=_cc),
                indent=2, default=str)
        if cmd == "scoring-pairings":
            # GG tee-sheet pairings ingest (Kerry overnight 2026-07-14).
            # Sub-commands (| separated):
            #   scoring-pairings:rounds|<sa|austin|page_url>
            #   scoring-pairings:round|<portal>|<round_id>[|apply]
            #   scoring-pairings:all|<portal>[|apply]
            # TEAM/CART Net board route (tee-sheet archive is login-gated;
            # the played rounds' team boards carry the actual groups):
            #   scoring-pairings:teamrounds|<portal>
            #   scoring-pairings:team|<portal>|<round_id>[|apply[|<event>]]
            #     (<event> = events.id or item_name fragment, for rounds
            #      whose selector label is truncated past matching)
            #   scoring-pairings:teamall|<portal>[|apply]
            parts = [p.strip() for p in arg.split("|")]
            sub = (parts[0] or "").lower()
            if sub == "rounds" and len(parts) >= 2:
                return json.dumps(db.gg_pairings_rounds(parts[1]), indent=2)
            if sub == "teamrounds" and len(parts) >= 2:
                return json.dumps(db.gg_teamnet_rounds(parts[1]), indent=2)
            if sub == "team" and len(parts) >= 3:
                return json.dumps(db.import_gg_teamnet_round(
                    parts[1], parts[2],
                    apply=(len(parts) > 3 and parts[3].lower() == "apply"),
                    event_override=(parts[4] if len(parts) > 4 else None)),
                    indent=2, default=str)
            if sub == "teamall" and len(parts) >= 2:
                return json.dumps(db.import_gg_teamnet_all(
                    parts[1],
                    apply=(len(parts) > 2 and parts[2].lower() == "apply")),
                    indent=2, default=str)
            if sub == "manual" and len(parts) >= 3:
                # manual|<event_id>|<json groups>[|apply] — groups from a
                # tee sheet / starter sheet (lists of names, seat order)
                groups = json.loads(parts[2])
                return json.dumps(db.import_manual_pairing_groups(
                    int(parts[1]), groups,
                    apply=(len(parts) > 3 and parts[3].lower() == "apply")),
                    indent=2, default=str)
            if sub == "playerstaging":
                # read-only: per-player staging positions (pace ranking)
                return json.dumps(db.analyze_player_staging(),
                                  indent=None, default=str)
            if sub == "pace":
                # read-only: customers with a stored pace_rating
                # (unlisted players read as the default 2)
                return json.dumps(db.list_pace_ratings(), indent=2)
            if sub == "staging" and len(parts) >= 1:
                # read-only: 9-hole events' actual groups in staging order
                # with pace proxies (Kerry's staging-pattern side quest)
                return json.dumps(db.analyze_pairing_staging(),
                                  indent=1, default=str)
            if sub == "gen" and len(parts) >= 2 and parts[1].isdigit():
                # read-only: run the generator seedless + show repeat math
                return json.dumps(db.debug_generate_pairings(int(parts[1])),
                                  indent=2, default=str)
            if sub == "mp" and len(parts) >= 2 and parts[1].isdigit():
                # read-only: potential Match Play matches on an event's
                # roster (rule 8 amendment detection — Task #25)
                return json.dumps(db.detect_match_play_pairings(int(parts[1])),
                                  indent=2, default=str)
            if sub == "hist" and len(parts) >= 2:
                # read-only: pairing_history rows by event id or name
                # fragment + 2026 totals by source
                return json.dumps(db.debug_pairing_history(parts[1]),
                                  indent=2, default=str)
            if sub == "clear" and len(parts) >= 2 and parts[1].isdigit():
                # undo a mis-matched apply: deletes ONLY source='gg_teamnet'
                # pairing_history rows for the event
                return json.dumps(db.clear_gg_teamnet_pairings(int(parts[1])),
                                  indent=2)
            if sub == "round" and len(parts) >= 3:
                return json.dumps(db.import_gg_teesheet_round(
                    parts[1], parts[2],
                    apply=(len(parts) > 3 and parts[3].lower() == "apply"),
                    event_override=(parts[4] if len(parts) > 4 else None)),
                    indent=2, default=str)
            if sub == "all" and len(parts) >= 2:
                return json.dumps(db.import_gg_teesheets_all(
                    parts[1],
                    apply=(len(parts) > 2 and parts[2].lower() == "apply")),
                    indent=2, default=str)
            return json.dumps({"error": "usage: scoring-pairings:rounds|<portal> "
                               "or round|<portal>|<id>[|apply] or all|<portal>[|apply]"})
        if cmd == "scoring-hcp-audit":
            # READ-ONLY full-table audit: every handicap record classified
            # by how it reconciles with its scorecard (Kerry 2026-07-14).
            return json.dumps(db.audit_handicap_bridges(), indent=2, default=str)
        if cmd == "scoring-fin-audit":
            # READ-ONLY whole-DB financial / customer_id / FK integrity
            # audit (financial-audit-charter.md Deliverable 1). arg = one
            # of tables|customer|fks|ledger|money|dupes, comma-separated,
            # or empty/"summary" for everything. Pure SELECT/PRAGMA.
            from email_parser import fin_audit
            return json.dumps(fin_audit.run(arg), indent=1, default=str)
        if cmd == "scoring-hcp-repair":
            # Repair Composer-import handicap rounds (adjusted stored as raw
            # gross) using GG's true Adjusted Gross from the season-scores
            # workbooks. arg = JSON list of {name,date,gross,adjusted};
            # append |apply (after the JSON) to write.
            payload, _, mode = arg.rpartition("|")
            if mode.strip().lower() == "apply" and payload:
                cells, dr = json.loads(payload), False
            else:
                cells, dr = json.loads(arg), True
            return json.dumps(db.repair_handicap_adjusted_scores(cells, dry_run=dr),
                              indent=2, default=str)
        if cmd == "scoring-hcp-import":
            # Self-derive handicap rounds from our scorecards for one event
            # (WHS NDB adjusted gross — Kerry-ratified 2026-07-14).
            # "<event>" dry-runs the plan; "<event>|apply" writes it and
            # auto-emails the chapter manager recap (Kerry 2026-07-29).
            ev_arg, _, mode = arg.partition("|")
            return json.dumps(db.derive_handicap_rounds_from_scoring(
                ev_arg.strip(), dry_run=(mode.strip().lower() != "apply")),
                indent=2, default=str)
        if cmd == "scoring-hcp-recap":
            # Manual (re)send of the chapter-manager recap email for one
            # ALREADY-POSTED event (the apply path sends it automatically).
            return json.dumps(db.send_handicap_recap_for_event(arg.strip()),
                              indent=2, default=str)
        if cmd == "scoring-courses-audit":
            # READ-ONLY: duplicate clusters in `courses` + handicap course
            # names with no courses row (Kerry 2026-07-19).
            return json.dumps(db.audit_courses(), indent=2, default=str)
        if cmd == "scoring-courses-ensure":
            # Insert a courses row (course_id) for each handicap course name
            # not already present (dup-aware). ":dry" (default) previews;
            # ":apply" writes.
            mode = arg.strip().lower()
            return json.dumps(db.ensure_courses_from_history(
                dry_run=(mode != "apply")), indent=2, default=str)
        if cmd == "scoring-unenroll":
            # Remove a season-contest enrollment + record the removal (same
            # flow as the Enrollment tab's remove): pot/N recompute from the
            # remaining entrants. "scoring-unenroll:<enrollment_id>|<reason>
            # |<refund_amount>|<refund_method>|<note>" — trailing parts optional.
            parts = [p.strip() for p in arg.split("|")]
            if not parts or not parts[0].isdigit():
                return json.dumps({"error": "enrollment_id|reason|refund_amount|refund_method|note"})
            amt = None
            if len(parts) > 2 and parts[2]:
                try:
                    amt = float(parts[2])
                except ValueError:
                    return json.dumps({"error": f"bad refund_amount {parts[2]!r}"})
            res = db.remove_season_contest_enrollment(
                int(parts[0]),
                reason=(parts[1] if len(parts) > 1 else None),
                refund_amount=amt,
                refund_method=(parts[3] if len(parts) > 3 else None),
                note=(parts[4] if len(parts) > 4 else None))
            return json.dumps(res if res is not None
                              else {"error": "enrollment not found"},
                              indent=2, default=str)
        if cmd == "scoring-mp-wd":
            # Record/clear a pool member's withdrawal:
            # "scoring-mp-wd:<chapter>|<season>|<player>|<1/0>[|reason]"
            parts = [p.strip() for p in arg.split("|")]
            if len(parts) < 3:
                return json.dumps({"error": "chapter|season|player[|1/0][|reason]"})
            flag = (parts[3] if len(parts) > 3 else "1") not in ("0", "false")
            reason = parts[4] if len(parts) > 4 else None
            return json.dumps(db.cmp_set_withdrawn_by_name(
                parts[1], parts[0], parts[2], flag, reason=reason),
                indent=2, default=str)
        if cmd == "scoring-hcp-dump":
            # READ-ONLY diagnostic: handicap_rounds for a player (arg =
            # "<player>" or "<player>|<date>").
            p, _, d = arg.partition("|")
            return json.dumps(db.debug_dump_handicap_rounds(
                p.strip(), d.strip() or None), indent=2, default=str)
        if cmd == "scoring-hcp-nines":
            # Persist the played side (front/back) onto handicap_rounds.nine
            # from each round's scorecard (Kerry 2026-07-19). ":dry" (default)
            # previews the counts; ":apply" writes.
            mode = arg.strip().lower()
            return json.dumps(db.persist_handicap_round_nines(
                dry_run=(mode != "apply")), indent=2, default=str)
        if cmd == "scoring-hcp-nine-order":
            # "<event>|<front|back>[|apply]" — record which nine an
            # 18-hole event played FIRST: stamps scoring_rounds.first_hole
            # and reorders each player's two-nine handicap pair so lists
            # and scorecards read in play order (Kerry 2026-08-03).
            _p = [x.strip() for x in arg.split("|")]
            if len(_p) < 2:
                return json.dumps({"error": "<event>|<front|back>[|apply]"})
            return json.dumps(db.set_event_nine_order(
                _p[0], _p[1],
                dry_run=not (len(_p) > 2 and _p[2].lower() == "apply")),
                indent=2, default=str)
        if cmd == "scoring-spotlight":
            # "<customer_id>" — the full Player Spotlight payload (same
            # data the member page renders); lets a session verify the
            # WHERE-PLAYER-STANDS / LSC / winnings shapes end-to-end.
            return json.dumps(db.get_player_spotlight(int(arg.strip())),
                              indent=2, default=str)
        if cmd == "scoring-snapshot-targets":
            # "[<window_pts>|<seat_window>]" — the snapshot-email
            # targeting queue: push_entry (in the window, not bought in)
            # vs defend (in the window, bought in) vs normal. Review
            # queue only — nothing sends.
            _p = [x.strip() for x in (arg or "").split("|") if x.strip()]
            return json.dumps(db.snapshot_center_queue()
                              if not _p else db.snapshot_target_list(
                window_points=float(_p[0]),
                seat_window=float(_p[1]) if len(_p) > 1 else 15.0),
                indent=2, default=str)
        if cmd == "scoring-snapshot-email":
            # "<customer_id>[|<to>][|send]" — YOUR TGF SNAPSHOT mock
            # (Kerry 2026-08-03): personalized reset-comeback email built
            # from the live spotlight payload. Default is a dry-run
            # returning the HTML preview; "|send" mails it to <to> (or
            # the admin recap recipient) — NEVER to the player in mock
            # phase (member sends await Kerry rule-3b ratification).
            _p = [x.strip() for x in arg.split("|")]
            _to = next((x for x in _p[1:] if "@" in x), None)
            _send = any(x.lower() == "send" for x in _p[1:])
            return json.dumps(db.build_player_snapshot_email(
                int(_p[0]), to_address=_to, send=_send),
                indent=2, default=str)
        if cmd == "scoring-hcp-r1-impact":
            # R1 sweep (ratified 2026-07-16, 'sweep first -> report ->
            # apply'): recompute all indexes without the x0.96 multiplier
            # and report the movement. ":apply" flips the dial to 1.0.
            return json.dumps(db.r1_multiplier_impact(
                apply=(arg.strip().lower() == "apply")), indent=2, default=str)
        if cmd == "scoring-hcp-ghin-compare":
            # READ-ONLY comparable-GHIN analysis (Kerry 2026-08-03):
            # combine-9s 18-hole indexes from TGF scores vs TGF index x2,
            # plus the 75% onboarding-rule validation.
            return json.dumps(db.ghin_comparison_analysis(),
                              indent=2, default=str)
        if cmd == "scoring-hcp-2nines":
            # "<event>|<per_nine_json>[|apply]" — post any 18-hole event as
            # TWO 9-hole handicap rounds per player (front + back), each
            # nine with its OWN course rating + slope (TGF is a 9-hole
            # index league). per_nine_json maps tee_id ->
            # {"front": [rating, slope], "back": [rating, slope]} — values
            # read off GG course setup, never guessed (Vaaler precedent,
            # Kerry 2026-07-18). Default is a dry-run preview; "|apply"
            # writes. Generic successor to scoring-hcp-2nines-vaaler.
            _p = arg.split("|")
            if len(_p) < 2:
                return json.dumps({"error": "<event>|<per_nine_json>[|apply]"})
            _pn = {int(k): {"front": tuple(v["front"]), "back": tuple(v["back"])}
                   for k, v in json.loads(_p[1]).items()}
            _apply = len(_p) > 2 and _p[2].strip().lower() == "apply"
            return json.dumps(db.derive_18hole_rounds_as_two_nines(
                _p[0].strip(), _pn, dry_run=not _apply), indent=2, default=str)
        if cmd == "scoring-hcp-2nines-vaaler":
            # Post the s18.8 Vaaler Creek 18-hole event as TWO 9-hole handicap
            # rounds per player (front + back), each with that nine's own course
            # rating + slope from GG's course setup (Kerry-provided 2026-07-18).
            # ":dry" (default) previews; ":apply" writes.
            mode = arg.strip().lower()
            return json.dumps(db.derive_18hole_rounds_as_two_nines(
                "s18.8", db._VAALER_PER_NINE, dry_run=(mode != "apply")),
                indent=2, default=str)
        if cmd == "scoring-gg-drift":
            # D1 drift report (Kerry #150): GG roster tag vs Tracker financial
            # status. NO ARG (default): compares the affiliation tags already
            # ingested with the boards — covers everyone ranked, no scraping
            # (the GG member directory is login-gated). Optional arg = public
            # roster page URL(s), |-separated, for a page-scrape comparison.
            urls = [u.strip() for u in arg.split("|") if u.strip()]
            return json.dumps(db.gg_roster_drift_report(urls), indent=2, default=str)
        if cmd == "scoring-heal-holes":
            # Align items.holes to the event's hole count on single-format
            # events (fixes the 'a9.18' -> holes=18 parser mis-read).
            return json.dumps(db.heal_item_holes_from_event(), indent=2, default=str)
        if cmd == "scoring-teamnet-repair":
            # Partial repair of a Team Net blind-draw over-distribution
            # (v2.79.3, Kerry-scoped): "<event>" dry-runs the plan,
            # "<event>|apply" writes it. Only UNPAID rows change; paid
            # teammates are left untouched.
            ev_arg, _, mode = arg.partition("|")
            return json.dumps(db.repair_teamnet_blind_draw_shares(
                ev_arg.strip(), dry_run=(mode.strip().lower() != "apply")),
                indent=2, default=str)
        if cmd == "scoring-gg-history":
            # GG HISTORY ingest bridge (Kerry-ratified 2026-07-11; see
            # docs/claude/gg-history.md). Sub-commands via arg:
            #   scoring-gg-history:seed              create tables + seed registry
            #   scoring-gg-history:status            coverage/progress report
            #   scoring-gg-history:ingest=<subdomain>[@<budget_s>]
            #       Phase-A standings walk of one portal; resumable —
            #       repeat until pages_remaining == 0. url param unused.
            from email_parser import gg_history as ggh
            sub, _, rest = arg.partition("=")
            sub = sub.strip().lower()
            if sub == "seed":
                return json.dumps(ggh.seed_portal_registry(), indent=2)
            if sub == "status":
                return json.dumps(ggh.gg_history_status(), indent=2)
            if sub == "ingest" and rest:
                dom, _, budget = rest.partition("@")
                return json.dumps(ggh.ingest_portal(
                    dom.strip(), budget_seconds=int(budget or 240)), indent=2)
            if sub == "holes" and rest:
                # Phase B: hole-by-hole scorecard walk (Kerry's #1 data
                # priority). holes=<subdomain>[@<budget_s>] — resumable,
                # repeat until rounds_left == 0.
                dom, _, budget = rest.partition("@")
                return json.dumps(ggh.ingest_portal_holes(
                    dom.strip(), budget_seconds=int(budget or 240)), indent=2)
            if sub == "games" and rest:
                # Phase B: per-game money walk. games=<subdomain>[@budget]
                dom, _, budget = rest.partition("@")
                return json.dumps(ggh.ingest_portal_games(
                    dom.strip(), budget_seconds=int(budget or 240)), indent=2)
            if sub in ("holes-bg", "games-bg") and rest:
                # Same walks in a daemon thread (MCP clients time out
                # ~60s; a portal walk wants minutes). Poll: holes-status.
                import threading
                fn = (ggh.ingest_portal_holes if sub == "holes-bg"
                      else ggh.ingest_portal_games)
                dom, _, budget = rest.partition("@")
                dom, budget_s = dom.strip(), int(budget or 600)
                key = f"{sub}:{dom}"
                ent = _GGH_BG.get(key)
                if ent and ent["thread"].is_alive():
                    return json.dumps({"already_running": key})

                def _run(fn=fn, dom=dom, budget_s=budget_s, key=key):
                    try:
                        _GGH_BG[key]["result"] = fn(
                            dom, budget_seconds=budget_s)
                    except Exception as exc:  # keep the error visible
                        _GGH_BG[key]["result"] = {"error": str(exc)}

                t = threading.Thread(target=_run, daemon=True, name=key)
                _GGH_BG[key] = {"thread": t, "result": None}
                t.start()
                return json.dumps({"started": key, "budget_s": budget_s})
            if sub == "holes-status":
                return json.dumps(
                    {dom: {"running": e["thread"].is_alive(),
                           "result": e["result"]}
                     for dom, e in _GGH_BG.items()}, indent=2)
            if sub == "overview":
                # per-portal coverage incl. Phase-B rounds + hole counts
                return json.dumps(ggh.portal_overview(), indent=2)
            if sub == "roster":
                # roster=report (dry-run match report) | roster=apply
                # (write gg_member_map + backfill standings/name-links)
                return json.dumps(
                    ggh.roster_ingest(apply=(rest.strip() == "apply")),
                    indent=2)
            if sub == "retrofit-123":
                # mailbox #126: retrofit Kerry's #123 ratification
                # amendments that crossed mid-flight with the v2.70 build
                return json.dumps(ggh.amendments_123_retrofit(), indent=2)
            if sub == "enrich-contacts":
                # mailbox #128: at-birth contact enrichment for the
                # gg_roster-created profiles (phone + DOB from the roster)
                return json.dumps(ggh.enrich_created_members(), indent=2)
            if sub == "archive-page" and rest:
                dom, _, pid = rest.partition(":")
                return json.dumps(
                    ggh.archive_widget_page(dom.strip(), pid.strip()),
                    indent=2)
            if sub == "roster-create-members":
                # Kerry-directed 2026-07-11: create customer profiles for
                # unmatched TGF/Former roster members (never guests/leads)
                return json.dumps(ggh.roster_create_members(), indent=2)
            if sub == "export":
                # export=<prefix> | export=ALL — ingest staged export pairs
                if rest.strip().upper() == "ALL":
                    return json.dumps([ggh.ingest_export_pair(p)
                                       for p in ggh.EXPORT_PREFIXES], indent=2)
                return json.dumps(ggh.ingest_export_pair(rest.strip()),
                                  indent=2)
            if sub == "audit":
                # audit=<prefix> | audit=ALL — parity checks vs the other channel
                if rest.strip().upper() == "ALL":
                    return json.dumps([ggh.audit_export_pair(p)
                                       for p in ggh.EXPORT_PREFIXES], indent=2)
                return json.dumps(ggh.audit_export_pair(rest.strip()),
                                  indent=2)
            return json.dumps({"error": "usage: scoring-gg-history:seed | "
                               "status | ingest=<subdomain>[@<budget_s>] | "
                               "holes=<subdomain>[@<budget_s>] | "
                               "roster=report|apply"})
        if cmd == "scoring-payouts-bulk-paid":
            # "scoring-payouts-bulk-paid:<YYYY-MM-DD>" — one-time cleanup:
            # mark every pending payout group from events before the date
            # as PAID (link unconsumed receipts, convert placeholders)
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", arg.strip()):
                return json.dumps({"error": "arg must be YYYY-MM-DD"})
            return json.dumps(db.bulk_mark_payouts_paid(arg.strip()), indent=2)
        if cmd == "scoring-traffic-reset":
            # One-time member-analytics wipe (Kerry, 2026-07-10): flush the
            # launch-day testing clicks so the counters start clean.
            with db._connect() as conn:
                db._ensure_member_analytics_table(conn)
                n = conn.execute("SELECT COUNT(*) FROM member_analytics").fetchone()[0]
                conn.execute("DELETE FROM member_analytics")
                conn.commit()
            return json.dumps({"deleted": n})
        if cmd == "scoring-raw-order" and arg:
            # Return the raw order-email text for an item (server-side
            # Graph fetch) — used to learn new order-form field labels
            # (e.g. the fall points option) before teaching the parser.
            item_id = int(arg)
            with db._connect() as conn:
                row = conn.execute(
                    "SELECT email_uid, subject FROM items WHERE id = ?",
                    (item_id,)).fetchone()
            if not row or not row["email_uid"] or row["email_uid"].startswith("manual"):
                return json.dumps({"error": "no fetchable email for that item"})
            from email_parser.fetcher import fetch_email_by_id
            from email_parser.parser import _strip_html
            email_data = fetch_email_by_id(
                os.getenv("AZURE_TENANT_ID", ""), os.getenv("AZURE_CLIENT_ID", ""),
                os.getenv("AZURE_CLIENT_SECRET", ""), os.getenv("EMAIL_ADDRESS", ""),
                row["email_uid"])
            if not email_data:
                return json.dumps({"error": "Graph fetch failed"})
            body = email_data.get("html") or email_data.get("text") or ""
            if "<" in body[:500]:
                body = _strip_html(body)
            return json.dumps({"subject": row["subject"], "body": body[:6000]},
                              indent=2)
        if cmd == "scoring-fall-enroll" and arg:
            # Parameterized fall NET enrollment (Kerry, 2026-07-10):
            # scoring-fall-enroll:<customer_id>[:<source_item_id>]
            # customer_id keyed per Guiding Principle 6; chapter from the
            # canonical customer row. manually_enrolled=1 until the fall
            # products + sync exist.
            parts = arg.split(":")
            cid = int(parts[0])
            item_id = int(parts[1]) if len(parts) > 1 and parts[1] else None
            with db._connect() as conn:
                row = conn.execute(
                    """SELECT customer_id, chapter,
                              TRIM(COALESCE(NULLIF(company_name,''),
                                   NULLIF(TRIM(first_name || ' ' || last_name), ''))) AS name
                       FROM customers WHERE customer_id = ?""",
                    (cid,),
                ).fetchone()
            if not row or not row["name"]:
                return json.dumps({"error": f"customer_id {cid} not found"})
            enr = db.enroll_season_contest(
                row["name"], "NET Points Race",
                row["chapter"] or "San Antonio", "2026 Fall",
                manually_enrolled=True, source_item_id=item_id)
            return json.dumps(enr, indent=2, default=str)
        if cmd == "scoring-fall-enroll":
            # One-shot fall NET enrollments (Kerry, 2026-07-10): Luke
            # Mazanec (this morning's SEASON CONTESTS order) + Kerry
            # Niester into the SA Fall NET. manually_enrolled=1 protects
            # them until the fall products/sync exist.
            out = {"enrolled": [], "not_found": []}
            with db._connect() as conn:
                for pat, item_id in (("%Mazanec%", 2258), ("%Niester%", None)):
                    row = conn.execute(
                        """SELECT customer_id,
                                  TRIM(COALESCE(NULLIF(company_name,''),
                                       NULLIF(TRIM(first_name || ' ' || last_name), ''))) AS name
                           FROM customers
                           WHERE TRIM(first_name || ' ' || last_name) LIKE ?
                           ORDER BY customer_id LIMIT 1""",
                        (pat,),
                    ).fetchone()
                    if not row or not row["name"]:
                        out["not_found"].append(pat)
                        continue
                    enr = db.enroll_season_contest(
                        row["name"], "NET Points Race", "San Antonio",
                        "2026 Fall", manually_enrolled=True,
                        source_item_id=item_id)
                    out["enrolled"].append(enr)
            return json.dumps(out, indent=2, default=str)
        if cmd == "scoring-course-short-pins":
            # Kerry's ratified course short names (2026-07-10) — one-shot
            # apply; /courses UI edits afterwards are never overwritten
            return json.dumps(db.apply_course_short_name_pins(), indent=2)
        if cmd == "scoring-payouts-unpaid":
            # Every non-paid payout group + the customer's recent Venmo
            # payout receipts (linked flag + amounts) for match diagnosis
            return json.dumps(db.get_unpaid_payout_groups(), indent=2)
        if cmd == "scoring-payouts-inspect":
            # READ-ONLY (v2.139.1, Kerry: "Tracker says Paul Reed is
            # already paid — track why"): every tgf_payouts row for one
            # event with the FULL acct link (source/ref/date/status), so
            # a wrong paid state is traceable to the exact ledger row.
            # "<event-or-code>[|<player substring>]"
            _ev, _, _pl = arg.partition("|")
            return json.dumps(db.inspect_event_payouts(
                _ev.strip(), player=_pl.strip() or None), indent=2, default=str)
        if cmd == "scoring-payouts-venmo-match":
            # Sweep outbound Venmo payout receipts (expense inbox) against
            # pending tgf_payouts and mark matches PAID (v2.50.0)
            return json.dumps(db.auto_match_venmo_payouts_to_tgf(), indent=2)
        if cmd == "scoring-monthly-payouts":
            # Record completed months' Monthly Points winners as SEASON
            # CONTEST payout accounts (v2.51.0); ":force" re-records
            return json.dumps(db.record_monthly_points_payouts(
                force=arg.strip().lower() == "force"), indent=2)
        if cmd == "scoring-auto-sync":
            # one on-demand pass of the close-event-in-GG pipeline:
            # scorecards + winners + flights for the newest rounds of BOTH
            # portals, then a payout refresh (recent events force-updated).
            # The hourly scheduler runs the same thing automatically.
            return json.dumps(db.auto_gg_results_sync(), indent=2)
        if cmd == "scoring-fc-seed":
            # One-time Fellowship Cup rank-history backfill: reconstruct
            # the pre-latest-event Cup ordering from the NET races' GG
            # Previous Rank columns, seed it as the prior snapshot, and
            # rotate the current order on top — movement chips show the
            # last event's effect immediately.
            return json.dumps(db.seed_fellowship_cup_history(), indent=2)
        if cmd == "scoring-portal-link":
            tok = db.make_portal_token(int(arg))
            if not tok:
                return json.dumps({"error": f"no customer {arg}"})
            base = os.getenv("PUBLIC_BASE_URL", "https://tgf-tracker.up.railway.app")
            return json.dumps({"customer_id": int(arg),
                               "url": f"{base}/me?t={tok}"}, indent=2)
        if cmd == "scoring-resolve":
            # Identity debugging: how does a GG name resolve to a customer?
            with db._connect() as conn:
                cands = db._gg_name_candidates(arg)
                link_hits = []
                for c in cands:
                    for row in conn.execute(
                            """SELECT customer_id, player_name
                               FROM handicap_player_links
                               WHERE LOWER(player_name) = LOWER(?)""", (c,)):
                        link_hits.append({"candidate": c,
                                          "customer_id": row["customer_id"],
                                          "link_name": row["player_name"]})
                cid = db._resolve_scoring_player(conn, arg)
                canonical = None
                if cid:
                    r = conn.execute(
                        """SELECT first_name || ' ' || last_name AS nm
                           FROM customers WHERE customer_id = ?""",
                        (cid,)).fetchone()
                    canonical = r["nm"] if r else None
            return json.dumps({"gg_name": arg, "candidates": cands,
                               "handicap_link_hits": link_hits,
                               "resolved_customer_id": cid,
                               "canonical_name": canonical}, indent=2)
        return json.dumps({"error": f"unknown scoring command: {cmd}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def probe_golf_genius(url: str, extract: str = "summary", max_chars: int = 60000,
                      xhr: bool = False) -> str:
    """Fetch a PUBLIC Golf Genius portal page server-side and return its parsed
    structure. Read-only, no login, restricted to *.golfgenius.com URLs. Built
    to explore what league data (events, results, standings) is available for
    import into the tracker — start from a public page URL and follow links.

    Args:
        url: Full https URL on golfgenius.com, e.g.
            https://tgf-sa.golfgenius.com/pages/5783305
        extract: 'summary' (title, headings, all links, first rows of each
            table), 'links' (links only), 'tables' (all tables in full),
            'text' (visible text), or 'raw' (raw HTML, truncated).
            Sessions predating the scoring tools may also pass the
            scoring-* bridge values (see _scoring_dispatch).
        max_chars: Truncation cap for text/raw output (default 60000)
        xhr: Send XMLHttpRequest headers (for GG widget detail routes that
            answer XHR with a JS partial instead of a full page)
    """
    from golf_genius_sync import fetch_public_page, parse_page_structure

    dispatched = _scoring_dispatch(url, extract)
    if dispatched is not None:
        return dispatched

    try:
        page = fetch_public_page(url, xhr=xhr)
    except Exception as e:
        return json.dumps({"error": str(e)})
    if page["status_code"] != 200:
        return json.dumps({
            "error": f"HTTP {page['status_code']}",
            "final_url": page["final_url"],
        })

    if extract == "raw":
        html = page["html"]
        return json.dumps({
            "final_url": page["final_url"],
            "truncated": len(html) > max_chars,
            "html": html[:max_chars],
        })

    parsed = parse_page_structure(page["html"], page["final_url"])
    out: dict = {"final_url": page["final_url"], "title": parsed["title"]}

    if extract == "links":
        out["links"] = parsed["links"][:500]
    elif extract == "tables":
        out["n_tables"] = len(parsed["tables"])
        out["tables"] = parsed["tables"][:25]
    elif extract == "text":
        text = parsed["text"]
        out["truncated"] = len(text) > max_chars
        out["text"] = text[:max_chars]
    else:  # summary
        out["headings"] = parsed["headings"][:60]
        out["n_links"] = len(parsed["links"])
        out["links"] = parsed["links"][:300]
        out["n_tables"] = len(parsed["tables"])
        out["table_previews"] = [
            {"n_rows": len(t), "first_rows": t[:6]} for t in parsed["tables"][:15]
        ]

    result = json.dumps(out, indent=2)
    if len(result) > max_chars * 2:
        result = result[: max_chars * 2] + '\n... (truncated — narrow with extract/links or a deeper URL)'
    return result


@mcp.tool()
def import_gg_scorecards(tournament_url: str, event_code: str = "") -> str:
    """Import every player's hole-by-hole scorecard from a Golf Genius
    tournament page into tracker-owned tables (scoring_rounds/scoring_holes,
    plus the course database which accretes from tee blocks). Idempotent —
    re-import replaces existing cards. Raw responses are archived gzipped.

    Args:
        tournament_url: Full v2tournaments URL, e.g.
            https://tgf-sa.golfgenius.com/v2tournaments/4739997?player_stats_for_portal=true&round_index=29
        event_code: Tracker event code to link rounds to (e.g. 's9.16') —
            resolves event_id and round_date from the events table
    """
    from email_parser.database import import_gg_scorecards as _imp
    try:
        return json.dumps(_imp(tournament_url, event_code=event_code or None), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_scoring_rounds(player: str = "", event: str = "",
                       customer_id: int = 0, limit: int = 100) -> str:
    """List imported scoring rounds (scorecard headers) with course/tee/event
    context. Filter by partial player name, partial event name, or exact
    customer_id.
    """
    from email_parser.database import get_scoring_rounds_list
    return json.dumps(get_scoring_rounds_list(
        player or None, event or None, customer_id or None, limit), indent=2)


@mcp.tool()
def get_scorecard_detail(scoring_round_id: int) -> str:
    """One full scorecard: per-hole strokes, strokes received (handicap
    dots), par/yardage/stroke index from the course DB, plus DERIVED values
    computed through the admin formula settings (vs par, adjusted strokes
    per WHS net double bogey, net + gross stableford points) and derived
    totals. Facts and derivations are kept separate by design.

    Args:
        scoring_round_id: scoring_rounds.id (from get_scoring_rounds)
    """
    from email_parser.database import get_scorecard
    card = get_scorecard(scoring_round_id)
    return json.dumps(card if card else {"error": "not found"}, indent=2)


@mcp.tool()
def verify_scoring_round_tool(scoring_round_id: int) -> str:
    """Parallel-run verification against Golf Genius's own numbers: hole
    sums vs GG gross, net vs gross-minus-handicap, and GG's par-relative
    markings (circles/squares) vs our course par data. Use after imports
    to prove the tracker computes what GG computes.

    Args:
        scoring_round_id: scoring_rounds.id
    """
    from email_parser.database import verify_scoring_round
    return json.dumps(verify_scoring_round(scoring_round_id), indent=2)


@mcp.tool()
def get_differential_parity_tool() -> str:
    """Phase 2 parity proof: recompute every bridged handicap round's
    adjusted gross + WHS differential from tracker-owned scorecard facts
    and compare against the values imported from GG's handicap export.
    When this holds at 100%, the handicap layer can derive from
    scoring_rounds directly and the manual export/import ritual dies."""
    from email_parser.database import get_differential_parity
    return json.dumps(get_differential_parity(), indent=2)


@mcp.tool()
def get_courses() -> str:
    """The tracker's own course database (accreted from scorecard imports):
    courses with their tees (slope/rating/yardage) and imported round counts.
    """
    from email_parser.database import list_courses
    return json.dumps(list_courses(), indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════
#  PLATFORM COLLABORATION TOOLS
#  Bridge between tracker-claude (Claude Code building this repo) and
#  platform-claude (the claude.ai Golf Fellowship Project planning the
#  TGF Platform). Docs are the architecture picture; the dialogue table
#  is the durable two-way mailbox — no copy/paste relaying needed.
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def snapshot_command_center(action: str, customer_id: int = 0,
                            window_points: float = 15.0,
                            seat_window: float = 15.0,
                            status: str = "", note: str = "") -> str:
    """The Snapshot Command Center — TGF's member-outreach engine, opened
    up for CA's optimization session (Kerry 2026-08-03). One tool, full
    access to everything the system computes and can do: the personalized
    "Your TGF Snapshot" email (reset comeback story, Freund 2024 proof,
    seat-line math, buy-in + TGF Championship CTAs) and the targeting
    queue that decides who gets pushed on entry vs a normalized email.

    READ docs first: get_tracker_docs('snapshot-command-center.md') is
    the spec of record — strategy, email anatomy, criteria, governance,
    and the optimization levers Kerry wants worked.

    Actions:
      overview  — system state in one payload: live queue counts +
                  criteria, championship event + signup coverage, dials
                  (LSC deadline, reset date), and the spec doc pointer.
      queue     — full Command Center queue (push_entry / defend /
                  normal segments with per-path points_back,
                  gap_to_seat, tgf_champ_signed_up, and Kerry's marks).
                  Tune window_points / seat_window per call.
      targets   — raw snapshot_target_list with custom windows (same
                  data, no marks).
      preview   — customer_id required: the exact email (subject + full
                  HTML + computed fields) built live from the boards.
      mark      — customer_id + status (approved|skipped|deferred|clear,
                  note optional): set Kerry's review marks. Marks are
                  reversible and drive the send gate.
      send_test — customer_id required: mail that player's snapshot to
                  the ADMIN (Kerry) inbox for review. Unrestricted.
      send      — customer_id required: REAL member send to the player's
                  primary email. Hard-gated: refuses unless the player
                  carries an APPROVED mark (Kerry's approval IS the
                  per-send ratification; there is no bulk send).

    Args:
        action: overview | queue | targets | preview | mark | send_test | send
        customer_id: player (required for preview/mark/send_test/send)
        window_points: points-back window for queue/targets (default 15)
        seat_window: seat-line window for queue/targets (default 15)
        status: for mark — approved | skipped | deferred | clear
        note: optional mark note (e.g. "in Hawaii until Sept")
    """
    import email_parser.database as db
    a = (action or "").strip().lower()
    try:
        if a == "overview":
            q = db.snapshot_center_queue()
            marks = db._snapshot_marks(None)
            return json.dumps({
                "spec_doc": "get_tracker_docs('snapshot-command-center.md')",
                "counts": q.get("counts"),
                "criteria": q.get("criteria"),
                "championship_events": q.get("championship_events"),
                "champ_signup_coverage": {
                    seg: {
                        "signed_up": sum(1 for e in q.get(seg) or []
                                         if e.get("tgf_champ_signed_up")),
                        "total": len(q.get(seg) or []),
                    } for seg in ("push_entry", "defend", "normal")},
                "marks_set": len(marks),
                "dials": {
                    "lsc_selection_deadline":
                        db.get_app_setting("lsc_selection_deadline")
                        or "2026-08-14",
                    "gg_points_reset_official":
                        db.get_app_setting("gg_points_reset_official"),
                },
                "surfaces": {
                    "admin_ui": "/admin/snapshot-center",
                    "email_builder": "build_player_snapshot_email",
                    "member_deep_links":
                        "/member/contests#race=<tfc|gross|net|austin>"
                        "&player=<cid>",
                },
            }, indent=2, default=str)
        if a == "queue":
            q = db.snapshot_center_queue()
            if window_points != 15.0 or seat_window != 15.0:
                q = db.snapshot_target_list(window_points=window_points,
                                            seat_window=seat_window)
            return json.dumps(q, indent=2, default=str)
        if a == "targets":
            return json.dumps(db.snapshot_target_list(
                window_points=window_points, seat_window=seat_window),
                indent=2, default=str)
        if a == "preview":
            return json.dumps(db.build_player_snapshot_email(
                int(customer_id), send=False), indent=2, default=str)
        if a == "mark":
            return json.dumps(db.snapshot_center_mark(
                int(customer_id), (status or "").strip().lower(),
                note=note or None), indent=2, default=str)
        if a == "send_test":
            return json.dumps(db.snapshot_center_send(
                int(customer_id), test=True), indent=2, default=str)
        if a == "send":
            return json.dumps(db.snapshot_center_send(
                int(customer_id), test=False), indent=2, default=str)
        return json.dumps({"error": f"unknown action {action!r}",
                           "actions": ["overview", "queue", "targets",
                                       "preview", "mark", "send_test",
                                       "send"]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_tracker_docs(name: str = "") -> str:
    """Read the Tracker's living documentation (CLAUDE.md + docs/claude/*.md).

    Call with no arguments to list available docs; pass a doc name (e.g.
    'state-of-the-tracker.md', 'scoring.md', 'member-portal.md',
    'CLAUDE.md') to get its full text. These docs are kept current by the
    Tracker's dev workflow after every change, so they are the
    authoritative picture of what is built. Start with
    'state-of-the-tracker.md' — the Platform-facing brief.

    Args:
        name: Doc filename to fetch; empty lists all docs
    """
    root = Path(__file__).resolve().parent
    docs_dir = root / "docs" / "claude"
    gov_dir = root / "docs" / "governance"
    available = {"CLAUDE.md": root / "CLAUDE.md"}
    if docs_dir.is_dir():
        for f in sorted(docs_dir.glob("*.md")):
            available[f.name] = f
    # Governance library (Kerry-approved 2026-07-16): OneDrive is
    # authoritative, the Tracker copy is the enforcement mirror. Governance
    # docs are namespaced 'governance/<name>' so they never collide with a
    # docs/claude name.
    if gov_dir.is_dir():
        for f in sorted(gov_dir.glob("*.md")):
            available[f"governance/{f.name}"] = f
    if not name:
        return json.dumps({
            "docs": [{"name": k, "bytes": v.stat().st_size}
                     for k, v in available.items() if v.is_file()],
            "hint": "Call again with name='<doc>.md' for full text. "
                    "Start with state-of-the-tracker.md.",
        }, indent=2)
    raw = name.strip().lstrip("/")
    # Accept the namespaced 'governance/<name>' form as well as a bare basename.
    f = available.get(raw)
    if not f:
        base = raw.split("/")[-1]
        f = available.get(base) or available.get(f"governance/{base}")
    if not f or not f.is_file():
        return json.dumps({"error": f"Unknown doc {name!r}",
                           "docs": sorted(available)})
    return f.read_text(encoding="utf-8")


# ── Read-only MCP access (Kerry-approved 2026-07-16, mailbox #194/#198) ──
# All read-only. get_tracker_source is HARD whitelisted; secrets, the DB
# file, and app.py/database.py stay OUT by construction.

# Prefix-whitelisted directories (POSIX, relative to repo root).
# handoffs/ added #212 (Kerry): opens the design-claude canvas handoffs to
# MCP read so platform-claude's visual-pass review pipeline can pull them.
_SOURCE_DIR_WHITELIST = ("templates/", "static/css/", "static/js/", "docs/",
                         "handoffs/")
# Individually-allowed pure engine modules (no DB/Flask, no secrets by design).
_SOURCE_FILE_WHITELIST = {
    "email_parser/handicap_calc.py",
    "email_parser/match_play.py",
    "email_parser/season_payouts.py",
}


@mcp.tool()
def get_tracker_source(path: str) -> str:
    """Read a whitelisted Tracker source file (read-only).

    Whitelist (Kerry-approved #198): templates/**, static/css/**,
    static/js/**, docs/**, plus the pure engine modules
    email_parser/handicap_calc.py, match_play.py, season_payouts.py. Anything
    else — .env, the DB file, mcp_server.py, app.py, database.py, credentials
    — is HARD-DENIED. The scoring formula VALUES are exposed as data via
    get_app_settings / get_scorecard_detail, not as source here.

    LIST MODE (#220): pass a whitelisted directory (e.g. 'handoffs/' or
    'docs/') and it returns the filenames in that dir instead of file text —
    so special-character filenames don't have to be guessed byte-for-byte.

    Args:
        path: repo-relative file path (e.g. 'static/js/points-render.js')
              or a whitelisted directory (e.g. 'handoffs/') for a listing.
    """
    root = Path(__file__).resolve().parent
    rel = path.strip().lstrip("/")
    # Resolve and confirm the target stays inside the repo (no ../ escape).
    target = (root / rel).resolve()
    try:
        rel_posix = target.relative_to(root).as_posix()
    except ValueError:
        return json.dumps({"error": "path escapes repo root", "path": path})
    is_dir = target.is_dir() or path.strip().endswith("/")
    rel_check = (rel_posix + "/") if is_dir else rel_posix
    allowed = (rel_posix in _SOURCE_FILE_WHITELIST
               or any(rel_check.startswith(p) for p in _SOURCE_DIR_WHITELIST))
    if not allowed:
        return json.dumps({
            "error": "path not in read-only whitelist",
            "path": rel_posix,
            "whitelist_dirs": list(_SOURCE_DIR_WHITELIST),
            "whitelist_files": sorted(_SOURCE_FILE_WHITELIST)})
    if is_dir:
        if not target.is_dir():
            return json.dumps({"error": "directory not found",
                               "path": rel_posix + "/"})
        files = sorted(p.relative_to(root).as_posix()
                       for p in target.rglob("*") if p.is_file())
        return json.dumps({"dir": rel_posix + "/", "count": len(files),
                           "files": files}, indent=2)
    if not target.is_file():
        return json.dumps({"error": "file not found", "path": rel_posix})
    try:
        return target.read_text(encoding="utf-8")
    except Exception as e:  # binary / unreadable
        return json.dumps({"error": f"unreadable: {e}", "path": rel_posix})


@mcp.tool()
def get_app_settings(key: str = "") -> str:
    """Read the app_settings table (live config the UI edits). Read-only.

    Call with no argument to list every non-secret key + value; pass a key
    for just that value. Secret-ish keys (anything containing pin/secret/
    token/password/key/credential) are redacted to protect config that
    should never leave the server.

    Args:
        key: one setting key, or empty to dump all (redacted)
    """
    from email_parser import database as _db
    _SECRET = ("pin", "secret", "token", "password", "credential", "apikey",
               "api_key")
    def _is_secret(k: str) -> bool:
        kl = k.lower()
        return any(s in kl for s in _SECRET)
    if key.strip():
        k = key.strip()
        if _is_secret(k):
            return json.dumps({"key": k, "value": "<redacted>"})
        return json.dumps({"key": k, "value": _db.get_app_setting(k)}, default=str)
    with _db._connect(None) as conn:
        rows = conn.execute(
            "SELECT key, value, updated_at FROM app_settings ORDER BY key").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if _is_secret(d["key"]):
            d["value"] = "<redacted>"
        out.append(d)
    return json.dumps({"count": len(out), "settings": out}, indent=2, default=str)


@mcp.tool()
def get_gg_snapshots(key: str = "") -> str:
    """Read the gg_data_snapshots cache (GG-derived payloads). Read-only.

    Supports results-hardening spot-checks (H-1 pattern) from this side. Call
    with no argument to list snapshot keys + their fetched_at stamps; pass a
    key to get that payload. Note: this table is a display CACHE (keys like
    'monthly_points'), refreshed daily — it is not a per-event frozen results
    ledger. For per-event GG-recorded results use the scoring/MVP/game reads.

    Args:
        key: one snapshot_key, or empty to list all keys
    """
    from email_parser import database as _db
    if key.strip():
        data = _db.load_gg_snapshot(key.strip())
        return json.dumps(data if data is not None else {"error": "no such snapshot"},
                          indent=2, default=str)
    with _db._connect(None) as conn:
        _db._ensure_gg_snapshot_table(conn)
        rows = conn.execute(
            "SELECT snapshot_key, fetched_at, length(payload) AS bytes "
            "FROM gg_data_snapshots ORDER BY snapshot_key").fetchall()
    return json.dumps({"count": len(rows), "snapshots": [dict(r) for r in rows]},
                      indent=2, default=str)


@mcp.tool()
def project_playing_handicaps(event: str, allowance: float = 1.0,
                              max_hcp: float = 0.0) -> str:
    """Project each player's PLAYING HANDICAP + per-hole allocation from OUR
    index and the round's selected tee, and compare to GG (Task #16 parity
    sweep; read-only). Promotes the scoring-hcp-project bridge to a first-class
    tool. Reports alloc-vs-GG-dots (index-independent, the 100% target) and
    playing-hcp-exact (also requires our index == GG's).

    Args:
        event: event name / code substring (e.g. 's9.17 Silverhorn')
        allowance: game allowance as a fraction (1.0 = 100%, 0.85 = 85%)
        max_hcp: Max Playing Handicap cap; 0 or negative means no cap
    """
    from email_parser import database as _db
    cap = max_hcp if max_hcp and max_hcp > 0 else None
    return json.dumps(_db.project_playing_handicaps(event, allowance=allowance,
                                                    max_hcp=cap),
                      indent=2, default=str)


@mcp.tool()
def determine_tgf_mvp(event_name: str) -> str:
    """Determine City MVP and TGF MVP for an event's day from imported scorecards.

    Automates the manual GG-impossible step (admin, 2026-07-05): for the
    event and its linked same-day events, City MVP = highest NET
    Stableford POINTS among NET-bundle buyers (tiebreakers: Individual
    Net stroke score, then Gross, then split), and TGF MVP = the City
    MVP with the higher points across the day's events (tie splits).
    Reports awaiting_results / single_event_day states, per-event buyer
    counts, the top-5 field, and GG-recorded MVP names for cross-check.

    Args:
        event_name: the event's item_name (e.g. "s9.16 TPC San Antonio | Oaks")
    """
    from email_parser.database import determine_tgf_mvp as _det
    return json.dumps(_det(event_name), indent=2, default=str)


@mcp.tool()
def get_side_games_matrix(holes: int = 0) -> str:
    """Return the LIVE side-games prize matrix (both hole counts).

    Reads the app_settings copy that the Matrix UI edits — the
    authoritative version. The static games-matrix.js in the repo is
    only a seed: UI saves rewrite it on the deployed container's
    EPHEMERAL disk, so the repo copy silently drifts from live. Always
    read this tool for current thresholds and payouts.

    Args:
        holes: 9 or 18 for one matrix; 0 (default) for both
    """
    import re as _re
    from email_parser.database import get_app_setting

    def _seed():
        root = Path(__file__).resolve().parent
        content = (root / "static" / "js" / "games-matrix.js").read_text()
        m9 = _re.search(r"window\.GAMES_MATRIX_9\s*=\s*(\{.*?\});", content, _re.DOTALL)
        m18 = _re.search(r"window\.GAMES_MATRIX_18\s*=\s*(\{.*?\});", content, _re.DOTALL)
        return json.loads(m9.group(1)), json.loads(m18.group(1))

    db9 = get_app_setting("games_matrix_9")
    db18 = get_app_setting("games_matrix_18")
    if db9 and db18:
        m9, m18 = json.loads(db9), json.loads(db18)
        source = "app_settings (live — carries Matrix UI edits)"
    else:
        m9, m18 = _seed()
        source = "static seed (matrix never saved via UI)"
    out = {"source": source}
    if holes == 9:
        out["matrix9"] = m9
    elif holes == 18:
        out["matrix18"] = m18
    else:
        out["matrix9"], out["matrix18"] = m9, m18
    return json.dumps(out, indent=2)


def _central_clock() -> dict:
    """Current time in TGF's home timezone — mailbox post #81 (Kerry):
    give the MCP a clock so no Claude misreads UTC as local again."""
    import pytz
    from datetime import datetime, timezone as _tz
    tz = pytz.timezone("America/Chicago")
    now_utc = datetime.now(_tz.utc)
    now_c = now_utc.astimezone(tz)
    friendly = now_c.strftime("%A, %B %d, %Y · %I:%M %p %Z")
    # strip leading zeros portably (no %-d/%-I on all platforms)
    import re as _re
    friendly = _re.sub(r"\b0(\d)", r"\1", friendly)
    return {
        "local_iso": now_c.isoformat(),
        "friendly": friendly,
        "utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "day_of_week": now_c.strftime("%A"),
        "timezone": "America/Chicago",
    }


@mcp.tool()
def get_current_time() -> str:
    """Current date and time in TGF's home timezone (America/Chicago).

    Returns local ISO timestamp, a friendly string (e.g. "Friday, July 10,
    2026 · 1:29 PM CDT"), the UTC equivalent, and the day of week. Check
    this before any time-of-day-dependent statement — mailbox created_at
    fields and most stored timestamps are UTC, NOT local (post #81).
    """
    return json.dumps(_central_clock(), indent=2)


@mcp.tool()
def read_platform_dialogue(limit: int = 20, topic: str = "", since_id: int = 0) -> str:
    """Read the tracker-claude <-> platform-claude planning mailbox (newest first).

    The durable two-way channel between the Claude building the Tracker
    codebase ('tracker-claude') and the claude.ai Golf Fellowship Project
    planning the TGF Platform ('platform-claude'). Check it at the start
    of a planning discussion or working session; reply with
    post_platform_dialogue.

    Args:
        limit: Max entries to return (default 20, cap 200)
        topic: Filter by topic substring (e.g. 'live-scoring')
        since_id: Only entries with id greater than this (catch-up reads)
    """
    from email_parser.database import read_platform_dialogue_entries
    clock = _central_clock()
    return json.dumps({
        "server_time_local": clock["friendly"],
        "server_time_utc": clock["utc"],
        "note": "post created_at fields are UTC — current local time is server_time_local (post #81)",
        "posts": read_platform_dialogue_entries(limit, topic, since_id),
    }, indent=2)


@mcp.tool()
def post_platform_dialogue(body: str, topic: str = "", author: str = "platform-claude") -> str:
    """Post to the tracker-claude <-> platform-claude planning mailbox.

    Write questions, decisions, proposals, and session digests here so
    the other side reads them directly — no copy/paste relaying. Sign
    with who you are: author='platform-claude' (claude.ai Project),
    'tracker-claude' (Claude Code on the Tracker repo), or 'kerry' when
    the admin dictates a message verbatim.

    Args:
        body: The message (markdown welcome)
        topic: Short topic tag (e.g. 'live-scoring', 'app-roadmap')
        author: Who is posting (default 'platform-claude')
    """
    from email_parser.database import post_platform_dialogue_entry
    try:
        return json.dumps(post_platform_dialogue_entry(author, body, topic), indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)
