"""
Daily email digest — sends a full summary of transactions, events, RSVPs,
and feedback via Microsoft Graph API.
"""

import logging
import os
from datetime import datetime, timedelta

from .database import (
    get_connection,
    get_db_health_metrics,
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
    "card": "background:#f0f7ff; padding:14px 10px; border-radius:8px; text-align:center; width:33%;",
    "card_num": "font-size:22px; font-weight:700; color:#2563eb;",
    "card_label": "font-size:12px; color:#666; text-transform:uppercase; white-space:nowrap;",
    "th": "padding:8px 10px; text-align:left; border-bottom:2px solid #e5e7eb; font-size:12px; text-transform:uppercase; color:#666; white-space:nowrap;",
    "td": "padding:8px 10px; border-bottom:1px solid #eee; font-size:14px;",
    "td_nowrap": "padding:8px 10px; border-bottom:1px solid #eee; font-size:14px; white-space:nowrap;",
    "section": "margin-top:32px;",
    "h3": "color:#1e40af; border-bottom:2px solid #e5e7eb; padding-bottom:6px; font-size:18px;",
    "empty": "color:#999; font-style:italic; font-size:14px;",
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
  <td style="{STYLES['td_nowrap']}">{r.get('order_date') or '—'}</td>
  <td style="{STYLES['td']}">{r.get('customer') or '—'}</td>
  <td style="{STYLES['td']} font-weight:600;">{r.get('item_name') or '—'}</td>
  <td style="{STYLES['td_nowrap']}">{r.get('item_price') or '—'}</td>
</tr>"""

    return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">Transactions (Last 24 Hours)</h3>
  <table cellpadding="0" cellspacing="0" border="0" style="width:100%; margin-bottom:16px;">
  <tr>
    <td style="{STYLES['card']}" width="33%">
      <div style="{STYLES['card_num']}">{total_items}</div>
      <div style="{STYLES['card_label']}">New Items</div>
    </td>
    <td width="10">&nbsp;</td>
    <td style="{STYLES['card']}" width="33%">
      <div style="{STYLES['card_num']}">{total_orders}</div>
      <div style="{STYLES['card_label']}">Orders</div>
    </td>
    <td width="10">&nbsp;</td>
    <td style="{STYLES['card']}" width="33%">
      <div style="{STYLES['card_num']}">${total_spent:,.2f}</div>
      <div style="{STYLES['card_label']}">Revenue</div>
    </td>
  </tr>
  </table>
  <table style="width:100%; border-collapse:collapse; font-size:14px;">
  <thead><tr style="background:#f9fafb;">
    <th style="{STYLES['th']}">Date</th>
    <th style="{STYLES['th']}">Customer</th>
    <th style="{STYLES['th']}">Event</th>
    <th style="{STYLES['th']}">Price</th>
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
  <td style="{STYLES['td']}"><span style="color:{color}; font-weight:700;">{resp}</span></td>
</tr>"""

    return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">RSVPs (Last 24 Hours)</h3>
  <table cellpadding="0" cellspacing="0" border="0" style="width:100%; margin-bottom:16px;">
  <tr>
    <td style="{STYLES['card']}" width="33%">
      <div style="{STYLES['card_num']}">{len(rsvps)}</div>
      <div style="{STYLES['card_label']}">Total RSVPs</div>
    </td>
    <td width="10">&nbsp;</td>
    <td style="background:#f0fdf4; padding:14px 10px; border-radius:8px; text-align:center; width:33%;" width="33%">
      <div style="font-size:22px; font-weight:700; color:#16a34a;">{len(playing)}</div>
      <div style="{STYLES['card_label']}">Playing</div>
    </td>
    <td width="10">&nbsp;</td>
    <td style="background:#fef2f2; padding:14px 10px; border-radius:8px; text-align:center; width:33%;" width="33%">
      <div style="font-size:22px; font-weight:700; color:#dc2626;">{len(not_playing)}</div>
      <div style="{STYLES['card_label']}">Not Playing</div>
    </td>
  </tr>
  </table>
  <table style="width:100%; border-collapse:collapse; font-size:14px;">
  <thead><tr style="background:#f9fafb;">
    <th style="{STYLES['th']}">Player</th>
    <th style="{STYLES['th']}">Event</th>
    <th style="{STYLES['th']}">Response</th>
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
        paid = e.get("registrations", 0)
        total = e.get("total_playing", 0) + e.get("gg_rsvp_count", 0)
        course_city = e.get('course') or e.get('chapter') or '—'
        table_rows += f"""\
<tr>
  <td style="{STYLES['td']} font-weight:600;">{e.get('item_name') or '—'}</td>
  <td style="{STYLES['td_nowrap']}">{e.get('event_date') or '—'}</td>
  <td style="{STYLES['td']}">{course_city}</td>
  <td style="{STYLES['td']} text-align:center;"><span style="font-weight:700; color:#2563eb;">{total}</span><span style="color:#666;"> / </span><span style="font-weight:700; color:#16a34a;">{paid}</span></td>
</tr>"""

    return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">Upcoming Events</h3>
  <table style="width:100%; border-collapse:collapse; font-size:14px;">
  <thead><tr style="background:#f9fafb;">
    <th style="{STYLES['th']}">Event</th>
    <th style="{STYLES['th']}">Date</th>
    <th style="{STYLES['th']}">Course</th>
    <th style="{STYLES['th']} text-align:center;">Total / Paid</th>
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
  <td style="{STYLES['td']}"><span style="background:{color}; color:#fff; padding:3px 10px; border-radius:10px; font-size:12px; white-space:nowrap;">{label}</span></td>
  <td style="{STYLES['td']}">{fb.get('message') or '—'}</td>
  <td style="{STYLES['td']}">{fb.get('page') or '—'}</td>
</tr>"""
        parts.append(f"""
  <h4 style="color:#333; margin-top:12px; font-size:16px;">New Tickets (Last 24 Hours) — {len(recent)}</h4>
  <table style="width:100%; border-collapse:collapse; font-size:14px;">
  <thead><tr style="background:#f9fafb;">
    <th style="{STYLES['th']}">Type</th>
    <th style="{STYLES['th']}">Message</th>
    <th style="{STYLES['th']}">Page</th>
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
  <td style="{STYLES['td']}"><span style="background:{color}; color:#fff; padding:3px 10px; border-radius:10px; font-size:12px; white-space:nowrap;">{label}</span></td>
  <td style="{STYLES['td']}">{fb.get('message') or '—'}</td>
  <td style="{STYLES['td']}">{fb.get('page') or '—'}</td>
</tr>"""
        parts.append(f"""
  <h4 style="color:#333; margin-top:20px; font-size:16px;">Outstanding Open Tickets — {len(open_tickets)}</h4>
  <table style="width:100%; border-collapse:collapse; font-size:14px;">
  <thead><tr style="background:#f9fafb;">
    <th style="{STYLES['th']}">Type</th>
    <th style="{STYLES['th']}">Message</th>
    <th style="{STYLES['th']}">Page</th>
  </tr></thead>
  <tbody>{rows}</tbody>
  </table>""")

    inner = "\n".join(parts)
    return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">Support Tickets</h3>
  {inner}
</div>"""


def _build_health_section(metrics: dict) -> str:
    """Build the DB health check section of the digest."""
    deltas = metrics.get("deltas", {})
    prev_date = metrics.get("previous_date")

    def delta_html(key: str) -> str:
        d = deltas.get(key)
        if d is None:
            return ""
        if d > 0:
            return f' <span style="color:#dc2626; font-size:11px;">&#9650;{d}</span>'
        if d < 0:
            return f' <span style="color:#16a34a; font-size:11px;">&#9660;{abs(d)}</span>'
        return ' <span style="color:#aaa; font-size:11px;">&#8212;</span>'

    problems = []
    if metrics.get("credited_duplicates", 0) > 0:
        problems.append(f"{metrics['credited_duplicates']} credited duplicate(s) — active copy should be deleted")
    if metrics.get("membership_mashups", 0) > 0:
        problems.append(f"{metrics['membership_mashups']} membership row(s) with event fields set (parser mashup)")
    if metrics.get("null_customer_items", 0) > 0:
        problems.append(f"{metrics['null_customer_items']} item(s) missing customer ID")
    if metrics.get("open_parse_warnings", 0) > 0:
        problems.append(f"{metrics['open_parse_warnings']} open parse warning(s)")

    status_color = "#16a34a" if not problems else "#dc2626"
    status_bg = "#f0fdf4" if not problems else "#fef2f2"
    status_label = "&#10003; All Clear" if not problems else "&#9888; Issues Found"

    problems_html = ""
    if problems:
        li = "".join(
            f'<li style="margin:4px 0; font-size:13px; color:#dc2626;">{p}</li>'
            for p in problems
        )
        problems_html = f'<ul style="margin:8px 0 0 0; padding-left:18px;">{li}</ul>'

    prev_note = (
        f'<p style="font-size:11px; color:#aaa; margin:8px 0 0 0;">Deltas vs {prev_date}</p>'
        if prev_date else ""
    )

    rows_html = "".join(f"""\
<tr>
  <td style="{STYLES['td']}">{label}</td>
  <td style="{STYLES['td']}; text-align:right; font-weight:600;">{metrics.get(key, '—')}{delta_html(key)}</td>
</tr>""" for label, key in [
        ("Total Items", "total_items"),
        ("Active Items", "active_items"),
        ("Open Parse Warnings", "open_parse_warnings"),
        ("Open Action Items", "open_action_items"),
        ("Credited Duplicates", "credited_duplicates"),
        ("Membership Mashups", "membership_mashups"),
        ("Items Missing Customer ID", "null_customer_items"),
    ])

    return f"""
<div style="{STYLES['section']}">
  <h3 style="{STYLES['h3']}">DB Health Check</h3>
  <div style="background:{status_bg}; border-radius:8px; padding:12px 16px; margin-bottom:14px;">
    <span style="font-weight:700; color:{status_color}; font-size:15px;">{status_label}</span>
    {problems_html}
  </div>
  <table style="width:100%; border-collapse:collapse; font-size:14px;">
  <thead><tr style="background:#f9fafb;">
    <th style="{STYLES['th']}">Metric</th>
    <th style="{STYLES['th']}; text-align:right;">Value</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
  </table>
  {prev_note}
</div>"""


# ---------------------------------------------------------------------------
# Main report builder & sender
# ---------------------------------------------------------------------------

def build_digest_html(items, rsvps, upcoming_events, recent_feedback, open_feedback,
                      health_metrics: dict | None = None) -> str:
    """Build the full daily digest HTML email."""
    now = datetime.now().strftime("%B %d, %Y")

    sections = [
        _build_transactions_section(items),
        _build_rsvps_section(rsvps),
        _build_upcoming_events_section(upcoming_events),
        _build_feedback_section(recent_feedback, open_feedback),
        _build_health_section(health_metrics) if health_metrics is not None else "",
    ]

    body = "\n".join(sections)

    return f"""\
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<style>
  body {{ margin: 0; padding: 0; }}
  table {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
  @media only screen and (max-width: 600px) {{
    .email-wrap {{ padding: 12px !important; }}
    h2 {{ font-size: 20px !important; }}
    h3 {{ font-size: 16px !important; }}
  }}
</style>
</head>
<body style="font-family: Arial, Helvetica, sans-serif; color: #333; margin: 0; padding: 0; background: #f5f7fa;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f5f7fa;">
<tr><td align="center" style="padding: 16px 8px;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:640px; background:#ffffff; border-radius:8px; overflow:hidden;">
<tr><td class="email-wrap" style="padding: 24px 20px;">

<h2 style="color: #2563eb; font-size: 22px; margin:0 0 4px 0;">TGF Daily Digest — {now}</h2>
<p style="color:#666; margin:0 0 8px 0; font-size:14px;">Here's everything that happened in the last 24 hours and where things stand.</p>
{body}
<hr style="margin-top:32px; border:none; border-top:1px solid #e5e7eb;">
<p style="margin-top:12px; font-size:12px; color:#999;">
  This is an automated digest from TGF Transaction Tracker.
</p>

</td></tr>
</table>
</td></tr>
</table>
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
    try:
        health = get_db_health_metrics()
    except Exception as e:
        logger.warning("DB health check failed — skipping section: %s", e)
        health = None

    html_body = build_digest_html(items, rsvps, upcoming, recent_fb, open_fb, health)

    # Build a summary subject line
    parts = []
    if items:
        parts.append(f"{len(items)} transaction(s)")
    if rsvps:
        parts.append(f"{len(rsvps)} RSVP(s)")
    if recent_fb:
        parts.append(f"{len(recent_fb)} ticket(s)")
    if health:
        problem_count = (
            (health.get("credited_duplicates") or 0)
            + (health.get("membership_mashups") or 0)
            + (health.get("null_customer_items") or 0)
            + (health.get("open_parse_warnings") or 0)
        )
        if problem_count:
            parts.append(f"⚠ {problem_count} DB issue(s)")
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
