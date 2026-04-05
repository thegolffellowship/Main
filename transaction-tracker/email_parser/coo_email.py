"""
COO Daily Email — Morning briefing for TGF operations.

Builds and sends an HTML email with:
1. Action items checklist
2. Financial snapshot
3. Upcoming events (14 days)
4. AI-generated observations
"""

import json
import logging
import os
from datetime import datetime, timedelta

import anthropic as _anthropic

from email_parser.database import (
    get_action_items,
    get_coo_financial_snapshot,
    get_pending_review_count,
    get_all_events,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://tgf-tracker.up.railway.app"
_NAVY = "#1A2E5A"
_GREEN = "#059669"
_RED = "#dc2626"
_AMBER = "#d97706"
_GRAY = "#6b7280"
_BG = "#f5f7fa"


def _fmt(n):
    """Format number as $X,XXX.XX"""
    if n is None:
        n = 0
    return f"${n:,.2f}"


def _urgency_emoji(u):
    return {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\u26aa"}.get(u, "\u26aa")


def build_coo_email_html() -> tuple[str, str]:
    """Build the COO daily email. Returns (subject, html_body)."""
    today = datetime.now()
    day_str = today.strftime("%A, %B %d")

    # ── Gather data ──
    action_items = get_action_items(status="open")
    snapshot = get_coo_financial_snapshot()
    review = get_pending_review_count()
    all_events = get_all_events()

    # Upcoming events (next 14 days)
    today_str = today.strftime("%Y-%m-%d")
    future_str = (today + timedelta(days=14)).strftime("%Y-%m-%d")
    upcoming = [
        e for e in all_events
        if e.get("event_date") and today_str <= e["event_date"] <= future_str
    ]
    upcoming.sort(key=lambda e: e.get("event_date", ""))

    # Subject
    action_count = len(action_items)
    subject = f"TGF Daily Briefing \u2014 {day_str} | {action_count} Action Item{'s' if action_count != 1 else ''}"

    # ── Build HTML ──
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:{_BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">

<!-- Header -->
<table width="100%" cellpadding="0" cellspacing="0" style="background:{_NAVY};padding:24px 20px;">
<tr><td>
  <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">TGF Daily Briefing</h1>
  <p style="margin:4px 0 0;color:#94a3b8;font-size:13px;">{day_str}</p>
</td></tr>
</table>

<table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:0 auto;padding:20px;">
<tr><td>
"""

    # ── Section 1: Action Required ──
    html += _section_header("\U0001f534 Action Required")
    if not action_items:
        html += _info_box("\u2705 No open action items")
    else:
        for item in sorted(action_items, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("urgency", "low"), 2)):
            emoji = _urgency_emoji(item.get("urgency"))
            cat = item.get("category", "other")
            from_name = item.get("from_name", "")
            summary = item.get("summary") or item.get("subject", "")
            date = item.get("email_date", "")
            link = f"{_BASE_URL}/coo#action-{item['id']}"
            html += f"""
<div style="padding:12px 16px;margin-bottom:8px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;border-left:4px solid {_RED if item.get('urgency')=='high' else _AMBER if item.get('urgency')=='medium' else _GRAY};">
  <div style="font-size:13px;color:{_GRAY};margin-bottom:4px;">
    {emoji} <span style="background:#eff6ff;color:#1e40af;padding:1px 6px;border-radius:4px;font-size:11px;font-weight:600;text-transform:uppercase;">{cat}</span>
    &nbsp; {date} &nbsp; {from_name}
  </div>
  <div style="font-size:14px;line-height:1.5;">{summary}</div>
  <div style="margin-top:6px;"><a href="{link}" style="font-size:12px;color:#2563eb;text-decoration:none;">View in COO Dashboard &rarr;</a></div>
</div>"""
    html += _section_end()

    # ── Section 2: Financial Snapshot ──
    html += _section_header("\U0001f4b0 Financial Snapshot")
    accts = snapshot["accounts"]
    oblig = snapshot["obligations"]
    debts = snapshot["debts"]
    avail = oblig["available_to_spend"]
    avail_color = _GREEN if avail >= 0 else _RED

    html += f"""
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;">
<tr>
  <td style="padding:8px 12px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;width:33%;text-align:center;">
    <div style="font-size:11px;color:{_GRAY};text-transform:uppercase;">Checking 0341</div>
    <div style="font-size:18px;font-weight:700;margin-top:2px;">{_fmt(accts['tgf_checking_0341'])}</div>
  </td>
  <td style="width:8px;"></td>
  <td style="padding:8px 12px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;width:33%;text-align:center;">
    <div style="font-size:11px;color:{_GRAY};text-transform:uppercase;">Money Market 8045</div>
    <div style="font-size:18px;font-weight:700;margin-top:2px;">{_fmt(accts['tgf_money_market_8045'])}</div>
  </td>
  <td style="width:8px;"></td>
  <td style="padding:8px 12px;background:#fff;border:2px solid {_NAVY};border-radius:8px;width:33%;text-align:center;">
    <div style="font-size:11px;color:{_GRAY};text-transform:uppercase;">TGF Total</div>
    <div style="font-size:18px;font-weight:700;color:{_NAVY};margin-top:2px;">{_fmt(accts['tgf_total'])}</div>
  </td>
</tr>
</table>

<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;">
<tr>
  <td style="padding:8px 12px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;width:25%;text-align:center;">
    <div style="font-size:10px;color:{_GRAY};text-transform:uppercase;">Prize Pools</div>
    <div style="font-size:15px;font-weight:600;color:{_RED};">{_fmt(oblig['prize_pools_owed'])}</div>
  </td>
  <td style="width:6px;"></td>
  <td style="padding:8px 12px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;width:25%;text-align:center;">
    <div style="font-size:10px;color:{_GRAY};text-transform:uppercase;">Course Fees</div>
    <div style="font-size:15px;font-weight:600;color:{_RED};">{_fmt(oblig['course_fees_owed'])}</div>
  </td>
  <td style="width:6px;"></td>
  <td style="padding:8px 12px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;width:25%;text-align:center;">
    <div style="font-size:10px;color:{_GRAY};text-transform:uppercase;">Tax Reserve MTD</div>
    <div style="font-size:15px;font-weight:600;color:{_AMBER};">{_fmt(oblig['tax_reserve_mtd'])}</div>
  </td>
  <td style="width:6px;"></td>
  <td style="padding:8px 12px;background:#dcfce7;border:2px solid {_GREEN};border-radius:8px;width:25%;text-align:center;">
    <div style="font-size:10px;color:{_GRAY};text-transform:uppercase;">Available</div>
    <div style="font-size:18px;font-weight:700;color:{avail_color};">{_fmt(avail)}</div>
  </td>
</tr>
</table>

<div style="font-size:12px;color:{_GRAY};text-align:right;margin-bottom:4px;">
  {review['total']} items pending review
</div>"""
    html += _section_end()

    # ── Section 3: Upcoming Events ──
    html += _section_header("\U0001f4c5 Upcoming Events (Next 14 Days)")
    if not upcoming:
        html += _info_box("No events in the next 14 days")
    else:
        for ev in upcoming:
            regs = ev.get("registrations", 0)
            cc = ev.get("course_cost")
            course = ev.get("course", "")
            date = ev.get("event_date", "")
            breakeven_html = ""
            if cc and cc > 0 and regs > 0:
                cost_total = cc * regs
                breakeven_html = f' <span style="color:{_GRAY};font-size:11px;">(course cost: {_fmt(cost_total)})</span>'
            html += f"""
<div style="padding:10px 14px;margin-bottom:6px;background:#fff;border:1px solid #e5e7eb;border-radius:6px;">
  <div style="font-size:14px;font-weight:600;">{ev.get('item_name', '')}</div>
  <div style="font-size:12px;color:{_GRAY};margin-top:2px;">
    {date} &bull; {course} &bull; <strong>{regs}</strong> registered{breakeven_html}
  </div>
</div>"""
    html += _section_end()

    # ── Section 4: COO Observations ──
    observations = _get_ai_observations(action_items, snapshot, upcoming, review)
    html += _section_header("\U0001f4a1 COO Observations")
    if observations:
        for obs in observations:
            html += f"""<div style="padding:8px 14px;margin-bottom:6px;background:#fffbeb;border:1px solid #fde68a;border-radius:6px;font-size:13px;line-height:1.5;">{obs}</div>"""
    else:
        html += _info_box("No observations to report")
    html += _section_end()

    # ── Footer ──
    html += f"""
</td></tr>
</table>

<table width="100%" cellpadding="0" cellspacing="0" style="padding:16px 20px;text-align:center;border-top:1px solid #e5e7eb;">
<tr><td>
  <a href="{_BASE_URL}/coo" style="font-size:13px;color:#2563eb;text-decoration:none;font-weight:600;">View COO Dashboard &rarr;</a>
  <p style="margin:8px 0 0;font-size:11px;color:{_GRAY};">TGF Transaction Tracker v1.7.0</p>
</td></tr>
</table>

</body></html>"""

    return subject, html


def _section_header(title: str) -> str:
    return f"""
<div style="margin-top:20px;margin-bottom:10px;padding-bottom:6px;border-bottom:2px solid {_NAVY};">
  <h2 style="margin:0;font-size:16px;font-weight:700;color:{_NAVY};">{title}</h2>
</div>"""


def _section_end() -> str:
    return ""


def _info_box(text: str) -> str:
    return f"""<div style="padding:12px 16px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;font-size:13px;color:{_GREEN};">{text}</div>"""


def _get_ai_observations(action_items, snapshot, upcoming, review) -> list[str]:
    """Generate 2-3 short AI observations about current state."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return []

    context = {
        "open_action_items": len(action_items),
        "action_summaries": [a.get("summary", "")[:80] for a in action_items[:5]],
        "available_to_spend": snapshot["obligations"]["available_to_spend"],
        "tgf_total": snapshot["accounts"]["tgf_total"],
        "prize_pools_owed": snapshot["obligations"]["prize_pools_owed"],
        "course_fees_owed": snapshot["obligations"]["course_fees_owed"],
        "tax_reserve_mtd": snapshot["obligations"]["tax_reserve_mtd"],
        "total_debts": snapshot["debts"]["total_obligations"],
        "upcoming_events": len(upcoming),
        "upcoming_names": [e.get("item_name", "") for e in upcoming[:5]],
        "pending_review": review["total"],
    }

    prompt = f"""You are the TGF COO Agent. Based on the current state below, generate exactly 2-3 short observations.
Each observation should be 1-2 sentences max. Focus on patterns, risks, or opportunities.
Do NOT generate action items — only observations.

Current state:
{json.dumps(context, indent=2)}

Return a JSON array of strings: ["observation 1", "observation 2", "observation 3"]
Return ONLY the JSON array."""

    try:
        client = _anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        import re
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.warning("AI observations failed: %s", e)

    return []
