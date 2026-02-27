"""
Daily email report — sends a summary of recent transactions via Microsoft Graph API.
"""

import logging
import os
from datetime import datetime, timedelta

from .database import get_connection
from .fetcher import send_mail_graph

logger = logging.getLogger(__name__)


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


def build_report_html(items: list[dict]) -> str:
    """Build an HTML email body with a summary of recent items."""
    now = datetime.now().strftime("%B %d, %Y")

    if not items:
        return f"""\
<html><body style="font-family: Arial, sans-serif; color: #333;">
<h2>TGF Daily Transaction Report — {now}</h2>
<p>No new transactions in the last 24 hours.</p>
</body></html>"""

    # Summary stats
    total_items = len(items)
    order_ids = set(r.get("order_id") for r in items if r.get("order_id"))
    total_orders = len(order_ids)
    total_spent = 0.0
    for r in items:
        try:
            total_spent += float((r.get("item_price") or "0").replace("$", "").replace(",", ""))
        except ValueError:
            pass

    # Build table rows
    table_rows = ""
    for r in items:
        table_rows += f"""\
<tr>
  <td style="padding:6px 10px; border-bottom:1px solid #eee;">{r.get('order_date') or '—'}</td>
  <td style="padding:6px 10px; border-bottom:1px solid #eee;">{r.get('customer') or '—'}</td>
  <td style="padding:6px 10px; border-bottom:1px solid #eee; font-weight:600;">{r.get('item_name') or '—'}</td>
  <td style="padding:6px 10px; border-bottom:1px solid #eee;">{r.get('item_price') or '—'}</td>
  <td style="padding:6px 10px; border-bottom:1px solid #eee;">{r.get('city') or '—'}</td>
  <td style="padding:6px 10px; border-bottom:1px solid #eee;">{r.get('side_games') or '—'}</td>
  <td style="padding:6px 10px; border-bottom:1px solid #eee;">{r.get('member_status') or '—'}</td>
  <td style="padding:6px 10px; border-bottom:1px solid #eee;">{r.get('order_id') or '—'}</td>
</tr>"""

    return f"""\
<html><body style="font-family: Arial, sans-serif; color: #333; max-width: 900px;">
<h2 style="color: #2563eb;">TGF Daily Transaction Report — {now}</h2>

<div style="display:flex; gap:20px; margin-bottom:20px;">
  <div style="background:#f0f7ff; padding:12px 20px; border-radius:8px;">
    <div style="font-size:24px; font-weight:700; color:#2563eb;">{total_items}</div>
    <div style="font-size:12px; color:#666; text-transform:uppercase;">New Items</div>
  </div>
  <div style="background:#f0f7ff; padding:12px 20px; border-radius:8px;">
    <div style="font-size:24px; font-weight:700; color:#2563eb;">{total_orders}</div>
    <div style="font-size:12px; color:#666; text-transform:uppercase;">Orders</div>
  </div>
  <div style="background:#f0f7ff; padding:12px 20px; border-radius:8px;">
    <div style="font-size:24px; font-weight:700; color:#2563eb;">${total_spent:,.2f}</div>
    <div style="font-size:12px; color:#666; text-transform:uppercase;">Revenue</div>
  </div>
</div>

<table style="width:100%; border-collapse:collapse; font-size:13px;">
<thead>
<tr style="background:#f9fafb;">
  <th style="padding:8px 10px; text-align:left; border-bottom:2px solid #e5e7eb; font-size:11px; text-transform:uppercase; color:#666;">Date</th>
  <th style="padding:8px 10px; text-align:left; border-bottom:2px solid #e5e7eb; font-size:11px; text-transform:uppercase; color:#666;">Customer</th>
  <th style="padding:8px 10px; text-align:left; border-bottom:2px solid #e5e7eb; font-size:11px; text-transform:uppercase; color:#666;">Item</th>
  <th style="padding:8px 10px; text-align:left; border-bottom:2px solid #e5e7eb; font-size:11px; text-transform:uppercase; color:#666;">Price</th>
  <th style="padding:8px 10px; text-align:left; border-bottom:2px solid #e5e7eb; font-size:11px; text-transform:uppercase; color:#666;">City</th>
  <th style="padding:8px 10px; text-align:left; border-bottom:2px solid #e5e7eb; font-size:11px; text-transform:uppercase; color:#666;">Side Games</th>
  <th style="padding:8px 10px; text-align:left; border-bottom:2px solid #e5e7eb; font-size:11px; text-transform:uppercase; color:#666;">Status</th>
  <th style="padding:8px 10px; text-align:left; border-bottom:2px solid #e5e7eb; font-size:11px; text-transform:uppercase; color:#666;">Order ID</th>
</tr>
</thead>
<tbody>
{table_rows}
</tbody>
</table>

<p style="margin-top:20px; font-size:12px; color:#999;">
  This is an automated report from TGF Transaction Tracker.
</p>
</body></html>"""


def send_daily_report():
    """Build and send the daily report email via Microsoft Graph API."""
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

    items = get_recent_items(hours=24)
    html_body = build_report_html(items)
    subject = f"TGF Daily Report — {datetime.now().strftime('%b %d, %Y')} — {len(items)} new item(s)"

    send_mail_graph(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        from_address=email_address,
        to_address=report_to,
        subject=subject,
        html_body=html_body,
    )
