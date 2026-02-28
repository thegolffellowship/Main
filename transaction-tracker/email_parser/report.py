"""
Daily email digest — sends a full summary of transactions, events, RSVPs,
and feedback via Microsoft Graph API.
"""

import logging
import os
from datetime import datetime, timedelta

from .database import (
    get_connection,
    get_open_feedback,
    get_recent_feedback,
    get_recent_rsvps,
    get_upcoming_events,
)
from .fetcher import send_mail_graph

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared styles
# ---------------------------------------------------------------------------
STYLES = {
    "card": "background:#f0f7ff; padding:12px 20px; border-radius:8px; text-align:center;",
    "card_num": "font-size:24px; font-weight:700; color:#2563eb;",
    "card_label": "font-size:12px; color:#666; text-transform:uppercase;",
    "th": "padding:8px 10px; text-align:left; border-bottom:2px solid #e5e7eb; font-size:11px; text-transform:uppercase; color:#666;",
    "td": "padding:6px 10px; border-bottom:1px solid #eee;",
    "section": "margin-top:32px;",
    "h3": "color:#1e40af; border-bottom:2px solid #e5e7eb; padding-bottom:6px;",
    "empty": "color:#999; font-style:italic;",
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def get_recent_items(hours: int = 24) -> list[dict]:
    """Get items created within the last N hours."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT * FROM items WHERE created_at >= ? ORDER BY created_at DESC",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_transactions_section(items: list[dict]) -> str:
    """Build the transactions section of the digest."""
    if not items:
        return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">Transactions</h3>
  <p style="{STYLES['empty']}">No new transactions in the last 24 hours.</p>
</div>"""

    total_items = len(items)
    order_ids = set(r.get("order_id") for r in items if r.get("order_id"))
    total_orders = len(order_ids)
    total_spent = 0.0
    for r in items:
        try:
            total_spent += float((r.get("item_price") or "0").replace("$", "").replace(",", ""))
        except ValueError:
            pass

    table_rows = ""
    for r in items:
        table_rows += f"""\
<tr>
  <td style="{STYLES['td']}">{r.get('order_date') or '—'}</td>
  <td style="{STYLES['td']}">{r.get('customer') or '—'}</td>
  <td style="{STYLES['td']} font-weight:600;">{r.get('item_name') or '—'}</td>
  <td style="{STYLES['td']}">{r.get('item_price') or '—'}</td>
  <td style="{STYLES['td']}">{r.get('city') or '—'}</td>
  <td style="{STYLES['td']}">{r.get('side_games') or '—'}</td>
  <td style="{STYLES['td']}">{r.get('order_id') or '—'}</td>
</tr>"""

    return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">Transactions (Last 24 Hours)</h3>
  <div style="display:flex; gap:20px; margin-bottom:16px;">
    <div style="{STYLES['card']}">
      <div style="{STYLES['card_num']}">{total_items}</div>
      <div style="{STYLES['card_label']}">New Items</div>
    </div>
    <div style="{STYLES['card']}">
      <div style="{STYLES['card_num']}">{total_orders}</div>
      <div style="{STYLES['card_label']}">Orders</div>
    </div>
    <div style="{STYLES['card']}">
      <div style="{STYLES['card_num']}">${total_spent:,.2f}</div>
      <div style="{STYLES['card_label']}">Revenue</div>
    </div>
  </div>
  <table style="width:100%; border-collapse:collapse; font-size:13px;">
  <thead><tr style="background:#f9fafb;">
    <th style="{STYLES['th']}">Date</th>
    <th style="{STYLES['th']}">Customer</th>
    <th style="{STYLES['th']}">Item</th>
    <th style="{STYLES['th']}">Price</th>
    <th style="{STYLES['th']}">City</th>
    <th style="{STYLES['th']}">Side Games</th>
    <th style="{STYLES['th']}">Order ID</th>
  </tr></thead>
  <tbody>{table_rows}</tbody>
  </table>
</div>"""


def _build_rsvps_section(rsvps: list[dict]) -> str:
    """Build the RSVPs section of the digest."""
    if not rsvps:
        return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">RSVPs (Last 24 Hours)</h3>
  <p style="{STYLES['empty']}">No new RSVP activity.</p>
</div>"""

    playing = [r for r in rsvps if r.get("response") == "PLAYING"]
    not_playing = [r for r in rsvps if r.get("response") == "NOT PLAYING"]

    table_rows = ""
    for r in rsvps:
        resp = r.get("response", "—")
        color = "#16a34a" if resp == "PLAYING" else "#dc2626"
        table_rows += f"""\
<tr>
  <td style="{STYLES['td']}">{r.get('player_name') or '—'}</td>
  <td style="{STYLES['td']}">{r.get('matched_event') or r.get('gg_event_name') or '—'}</td>
  <td style="{STYLES['td']}"><span style="color:{color}; font-weight:600;">{resp}</span></td>
  <td style="{STYLES['td']}">{r.get('received_at') or '—'}</td>
</tr>"""

    return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">RSVPs (Last 24 Hours)</h3>
  <div style="display:flex; gap:20px; margin-bottom:16px;">
    <div style="{STYLES['card']}">
      <div style="{STYLES['card_num']}">{len(rsvps)}</div>
      <div style="{STYLES['card_label']}">Total RSVPs</div>
    </div>
    <div style="background:#f0fdf4; padding:12px 20px; border-radius:8px; text-align:center;">
      <div style="font-size:24px; font-weight:700; color:#16a34a;">{len(playing)}</div>
      <div style="{STYLES['card_label']}">Playing</div>
    </div>
    <div style="background:#fef2f2; padding:12px 20px; border-radius:8px; text-align:center;">
      <div style="font-size:24px; font-weight:700; color:#dc2626;">{len(not_playing)}</div>
      <div style="{STYLES['card_label']}">Not Playing</div>
    </div>
  </div>
  <table style="width:100%; border-collapse:collapse; font-size:13px;">
  <thead><tr style="background:#f9fafb;">
    <th style="{STYLES['th']}">Player</th>
    <th style="{STYLES['th']}">Event</th>
    <th style="{STYLES['th']}">Response</th>
    <th style="{STYLES['th']}">Received</th>
  </tr></thead>
  <tbody>{table_rows}</tbody>
  </table>
</div>"""


def _build_upcoming_events_section(events: list[dict]) -> str:
    """Build the upcoming events section of the digest."""
    if not events:
        return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">Upcoming Events</h3>
  <p style="{STYLES['empty']}">No upcoming events scheduled.</p>
</div>"""

    table_rows = ""
    for e in events:
        regs = e.get("registrations", 0)
        table_rows += f"""\
<tr>
  <td style="{STYLES['td']} font-weight:600;">{e.get('item_name') or '—'}</td>
  <td style="{STYLES['td']}">{e.get('event_date') or '—'}</td>
  <td style="{STYLES['td']}">{e.get('course') or '—'}</td>
  <td style="{STYLES['td']}">{e.get('city') or '—'}</td>
  <td style="{STYLES['td']}"><span style="font-weight:700; color:#2563eb;">{regs}</span></td>
</tr>"""

    return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">Upcoming Events</h3>
  <table style="width:100%; border-collapse:collapse; font-size:13px;">
  <thead><tr style="background:#f9fafb;">
    <th style="{STYLES['th']}">Event</th>
    <th style="{STYLES['th']}">Date</th>
    <th style="{STYLES['th']}">Course</th>
    <th style="{STYLES['th']}">City</th>
    <th style="{STYLES['th']}">Registrations</th>
  </tr></thead>
  <tbody>{table_rows}</tbody>
  </table>
</div>"""


def _build_feedback_section(recent: list[dict], open_tickets: list[dict]) -> str:
    """Build the feedback/tickets section of the digest."""
    if not recent and not open_tickets:
        return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">Support Tickets</h3>
  <p style="{STYLES['empty']}">No new tickets and no open tickets. All clear!</p>
</div>"""

    parts = []

    # New tickets in last 24h
    if recent:
        rows = ""
        for fb in recent:
            fb_type = fb.get("type", "bug")
            color = "#dc2626" if fb_type == "bug" else "#2563eb"
            label = "Bug" if fb_type == "bug" else "Feature"
            rows += f"""\
<tr>
  <td style="{STYLES['td']}"><span style="background:{color}; color:#fff; padding:2px 8px; border-radius:10px; font-size:11px;">{label}</span></td>
  <td style="{STYLES['td']}">{fb.get('message') or '—'}</td>
  <td style="{STYLES['td']}">{fb.get('page') or '—'}</td>
  <td style="{STYLES['td']}">{fb.get('role') or '—'}</td>
  <td style="{STYLES['td']}">{fb.get('created_at') or '—'}</td>
</tr>"""
        parts.append(f"""
  <h4 style="color:#333; margin-top:12px;">New Tickets (Last 24 Hours) — {len(recent)}</h4>
  <table style="width:100%; border-collapse:collapse; font-size:13px;">
  <thead><tr style="background:#f9fafb;">
    <th style="{STYLES['th']}">Type</th>
    <th style="{STYLES['th']}">Message</th>
    <th style="{STYLES['th']}">Page</th>
    <th style="{STYLES['th']}">Role</th>
    <th style="{STYLES['th']}">Submitted</th>
  </tr></thead>
  <tbody>{rows}</tbody>
  </table>""")
    else:
        parts.append(f'<p style="{STYLES["empty"]}">No new tickets in the last 24 hours.</p>')

    # Outstanding open tickets
    if open_tickets:
        rows = ""
        for fb in open_tickets:
            fb_type = fb.get("type", "bug")
            color = "#dc2626" if fb_type == "bug" else "#2563eb"
            label = "Bug" if fb_type == "bug" else "Feature"
            rows += f"""\
<tr>
  <td style="{STYLES['td']}"><span style="background:{color}; color:#fff; padding:2px 8px; border-radius:10px; font-size:11px;">{label}</span></td>
  <td style="{STYLES['td']}">{fb.get('message') or '—'}</td>
  <td style="{STYLES['td']}">{fb.get('page') or '—'}</td>
  <td style="{STYLES['td']}">{fb.get('created_at') or '—'}</td>
</tr>"""
        parts.append(f"""
  <h4 style="color:#333; margin-top:20px;">Outstanding Open Tickets — {len(open_tickets)}</h4>
  <table style="width:100%; border-collapse:collapse; font-size:13px;">
  <thead><tr style="background:#f9fafb;">
    <th style="{STYLES['th']}">Type</th>
    <th style="{STYLES['th']}">Message</th>
    <th style="{STYLES['th']}">Page</th>
    <th style="{STYLES['th']}">Submitted</th>
  </tr></thead>
  <tbody>{rows}</tbody>
  </table>""")

    inner = "\n".join(parts)
    return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">Support Tickets</h3>
  {inner}
</div>"""


# ---------------------------------------------------------------------------
# Main report builder & sender
# ---------------------------------------------------------------------------

def build_digest_html(items, rsvps, upcoming_events, recent_feedback, open_feedback) -> str:
    """Build the full daily digest HTML email."""
    now = datetime.now().strftime("%B %d, %Y")

    sections = [
        _build_transactions_section(items),
        _build_rsvps_section(rsvps),
        _build_upcoming_events_section(upcoming_events),
        _build_feedback_section(recent_feedback, open_feedback),
    ]

    body = "\n".join(sections)

    return f"""\
<html><body style="font-family: Arial, sans-serif; color: #333; max-width: 900px; margin: 0 auto;">
<h2 style="color: #2563eb;">TGF Daily Digest — {now}</h2>
<p style="color:#666; margin-top:-8px;">Here's everything that happened in the last 24 hours and where things stand.</p>
{body}
<hr style="margin-top:32px; border:none; border-top:1px solid #e5e7eb;">
<p style="margin-top:12px; font-size:12px; color:#999;">
  This is an automated digest from TGF Transaction Tracker.
</p>
</body></html>"""


# Keep the old function name for backwards compatibility with existing callers
def build_report_html(items: list[dict]) -> str:
    """Legacy wrapper — builds a transactions-only report."""
    return build_digest_html(items, [], [], [], [])


def send_daily_report():
    """Build and send the daily digest email via Microsoft Graph API."""
    report_to = os.getenv("DAILY_REPORT_TO")
    if not report_to:
        logger.info("DAILY_REPORT_TO not set — skipping daily report")
        return

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    email_address = os.getenv("EMAIL_ADDRESS")

    if not all([tenant_id, client_id, client_secret, email_address]):
        logger.warning("Azure AD credentials not set — cannot send report")
        return

    # Gather all data
    items = get_recent_items(hours=24)
    rsvps = get_recent_rsvps(hours=24)
    upcoming = get_upcoming_events()
    recent_fb = get_recent_feedback(hours=24)
    open_fb = get_open_feedback()

    html_body = build_digest_html(items, rsvps, upcoming, recent_fb, open_fb)

    # Build a summary subject line
    parts = []
    if items:
        parts.append(f"{len(items)} transaction(s)")
    if rsvps:
        parts.append(f"{len(rsvps)} RSVP(s)")
    if recent_fb:
        parts.append(f"{len(recent_fb)} ticket(s)")
    summary = ", ".join(parts) if parts else "No new activity"

    subject = f"TGF Daily Digest — {datetime.now().strftime('%b %d, %Y')} — {summary}"

    send_mail_graph(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        from_address=email_address,
        to_address=report_to,
        subject=subject,
        html_body=html_body,
    )
