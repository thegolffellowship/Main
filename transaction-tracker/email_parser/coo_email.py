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

from email_parser.timezone_utils import now_central
import anthropic as _anthropic

from email_parser.database import (
    get_action_items,
    get_app_setting,
    get_coo_financial_snapshot,
    get_pending_review_count,
    get_all_events,
    _connect,
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
    today = now_central()
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

    # Parse warnings
    try:
        with _connect() as conn:
            new_warnings = conn.execute(
                "SELECT COUNT(*) as cnt FROM parse_warnings WHERE status = 'open' AND created_at >= datetime('now', '-24 hours')"
            ).fetchone()["cnt"]
            total_warnings = conn.execute(
                "SELECT COUNT(*) as cnt FROM parse_warnings WHERE status = 'open'"
            ).fetchone()["cnt"]
    except Exception:
        new_warnings, total_warnings = 0, 0

    # Split the open items into NEW (last 24h) vs standing backlog \u2014 the
    # briefing leads with what changed, not the whole pile (Kerry
    # 2026-07-20: "honestly overwhelming... produce a summary of
    # everything from last 24 hours to start out, with an allowance to
    # see each of these in detail").
    cutoff = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    new_items = [a for a in action_items if (a.get("created_at") or "") >= cutoff]
    backlog = [a for a in action_items if (a.get("created_at") or "") < cutoff]
    high_backlog = [a for a in backlog if a.get("urgency") == "high"]
    try:
        detail_cap = int(get_app_setting("daily_briefing_detail_cap") or 10)
    except Exception:
        detail_cap = 10

    try:
        from email_parser.leads import followups_due
        fups = followups_due()
    except Exception:
        logger.warning("Follow-ups section failed (non-fatal)", exc_info=True)
        fups = []
    _fups_over = [f for f in fups if f["days_over"] > 0]

    # Subject
    action_count = len(action_items)
    subject = (f"TGF Daily Briefing \u2014 {day_str} | "
               f"{len(new_items)} new \u00b7 {action_count} open")
    # The 48-hour touch is the conversion gate, so overdue follow-ups
    # belong where Kerry sees them without opening anything.
    if _fups_over:
        subject += f" \u00b7 {len(_fups_over)} follow-up{'s' if len(_fups_over) != 1 else ''} overdue"
    if new_warnings > 0:
        subject = f"\u26a0\ufe0f {subject} ({new_warnings} new parse warning{'s' if new_warnings != 1 else ''})"

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

    # ── Section 0: Administrative Overview (last 24 hours) ──
    html += _section_header("\U0001f4cb Administrative Overview — Last 24 Hours")
    _high_total = len(high_backlog) + sum(
        1 for a in new_items if a.get("urgency") == "high")
    mem = _get_membership_summary()
    money = _get_outstanding_money()
    html += f"""
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;">
<tr>
  <td style="padding:8px 10px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;text-align:center;">
    <div style="font-size:10px;color:{_GRAY};text-transform:uppercase;">New (24h)</div>
    <div style="font-size:18px;font-weight:700;color:{_RED if new_items else _GREEN};">{len(new_items)}</div>
  </td>
  <td style="width:6px;"></td>
  <td style="padding:8px 10px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;text-align:center;">
    <div style="font-size:10px;color:{_GRAY};text-transform:uppercase;">Open backlog</div>
    <div style="font-size:18px;font-weight:700;">{len(backlog)}</div>
  </td>
  <td style="width:6px;"></td>
  <td style="padding:8px 10px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;text-align:center;">
    <div style="font-size:10px;color:{_GRAY};text-transform:uppercase;">High urgency</div>
    <div style="font-size:18px;font-weight:700;color:{_RED if _high_total else _GRAY};">{_high_total}</div>
  </td>
  <td style="width:6px;"></td>
  <td style="padding:8px 10px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;text-align:center;">
    <div style="font-size:10px;color:{_GRAY};text-transform:uppercase;">Expiring mbrs</div>
    <div style="font-size:18px;font-weight:700;color:{_AMBER if mem["expiring"] else _GREEN};">{len(mem["expiring"])}</div>
  </td>
</tr>
</table>
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;">
<tr>
  <td style="padding:8px 10px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;text-align:center;">
    <div style="font-size:10px;color:{_GRAY};text-transform:uppercase;"><a href="{_BASE_URL}/tgf" style="color:{_GRAY};text-decoration:none;">Outstanding payouts &rarr;</a></div>
    <div style="font-size:16px;font-weight:700;color:{_RED if money["payout_total"] else _GREEN};">{_fmt(money["payout_total"])}</div>
    <div style="font-size:10px;color:{_GRAY};">{money["payout_groups"]} golfer{"s" if money["payout_groups"] != 1 else ""}</div>
  </td>
  <td style="width:6px;"></td>
  <td style="padding:8px 10px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;text-align:center;">
    <div style="font-size:10px;color:{_GRAY};text-transform:uppercase;"><a href="{_BASE_URL}/tgf" style="color:{_GRAY};text-decoration:none;">Outstanding refunds &rarr;</a></div>
    <div style="font-size:16px;font-weight:700;color:{_RED if money["refund_total"] else _GREEN};">{_fmt(money["refund_total"])}</div>
    <div style="font-size:10px;color:{_GRAY};">{money["refund_count"]} item{"s" if money["refund_count"] != 1 else ""}</div>
  </td>
  <td style="width:6px;"></td>
  <td style="padding:8px 10px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;text-align:center;">
    <div style="font-size:10px;color:{_GRAY};text-transform:uppercase;"><a href="{_BASE_URL}/transactions" style="color:{_GRAY};text-decoration:none;">Open credits &rarr;</a></div>
    <div style="font-size:16px;font-weight:700;color:{_AMBER if money["credit_total"] else _GREEN};">{_fmt(money["credit_total"])}</div>
    <div style="font-size:10px;color:{_GRAY};">{money["credit_count"]} item{"s" if money["credit_count"] != 1 else ""}</div>
  </td>
</tr>
</table>"""
    ai = _get_admin_overview(new_items, backlog, snapshot, upcoming, mem, money)
    for line in ai.get("summary", []):
        html += f"""<div style="padding:8px 14px;margin-bottom:6px;background:#fff;border:1px solid #e5e7eb;border-left:4px solid {_NAVY};border-radius:6px;font-size:13px;line-height:1.5;">{line}</div>"""
    html += _section_end()

    # ── Section 0b: Quick Wins ── overdue payouts render
    # deterministically (money SLA is not left to the AI's judgement:
    # Kerry 2026-07-20 "payouts should go out within 24 hours of event"),
    # then the AI's sub-5-minute suggestions.
    qw_payouts = money.get("overdue", [])[:4]
    if qw_payouts or ai.get("quick_wins"):
        html += _section_header("\u26a1 Quick Wins")
        for o in qw_payouts:
            html += f"""<div style="padding:8px 14px;margin-bottom:6px;background:#fef2f2;border:1px solid #fecaca;border-radius:6px;font-size:13px;line-height:1.5;"><strong>Pay {o["name"]} {_fmt(o["amount"])}</strong> — {o["event"]}, {o["days"]}d past the 24h payout standard &nbsp;<a href="{_BASE_URL}/tgf" style="font-size:12px;color:#2563eb;text-decoration:none;">Open Unpaid queue &rarr;</a></div>"""
        if len(money.get("overdue", [])) > 4:
            html += f"""<div style="font-size:12px;color:{_GRAY};margin-bottom:6px;">+{len(money["overdue"]) - 4} more overdue payout groups in the Unpaid queue</div>"""
        for line in ai.get("quick_wins", []):
            html += f"""<div style="padding:8px 14px;margin-bottom:6px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;font-size:13px;line-height:1.5;">{line}</div>"""
        html += _section_end()

    # ── Section 0b2: Follow-ups due (Kerry 2026-09-03: "should be part
    # of morning digest"). This replaced one email per lead, which was
    # fine at organic pace and a 39-email blast the moment a backfill
    # ran. It sits above Memberships because the 48-hour touch is the
    # conversion gate: these are people who reached out and are waiting.
    # Unlike the old ping, a lead that stays overdue is listed again
    # tomorrow — the whole point of a digest.
    if fups:
        _over = _fups_over
        html += _section_header(
            f"\u23f0 Follow-ups Due ({len(fups)}"
            + (f", {len(_over)} overdue" if _over else "") + ")")
        for f in fups[:detail_cap]:
            _when = (f"<span style=\"color:{_RED};font-weight:600;\">"
                     f"{f['days_over']}d overdue</span>" if f["days_over"] > 0
                     else f"<span style=\"color:{_GREEN};font-weight:600;\">"
                          f"due today</span>")
            _bits = " \u00b7 ".join(x for x in [f.get("tag"), f.get("chapter"),
                                               f.get("phone")] if x)
            html += f"""<div style="padding:8px 12px;margin-bottom:6px;background:#fff;border:1px solid #e5e7eb;border-left:4px solid {_RED if f["days_over"] > 0 else _GREEN};border-radius:6px;font-size:13px;line-height:1.5;"><strong>{f["name"]}</strong> — {_when} &nbsp;<a href="{_BASE_URL}/admin/leads" style="font-size:12px;color:#2563eb;text-decoration:none;">Open &rarr;</a><div style="font-size:12px;color:{_GRAY};">{_bits}</div></div>"""
        if len(fups) > detail_cap:
            html += f"""<div style="font-size:12px;color:{_GRAY};margin-bottom:6px;">+{len(fups) - detail_cap} more under FOLLOW-UPS DUE in the <a href="{_BASE_URL}/admin/leads" style="color:#2563eb;text-decoration:none;">Lead Center</a></div>"""
        html += _section_end()

    # ── Section 0c: Memberships ──
    html += _section_header("\U0001f465 Memberships")
    def _mem_rows(rows, color, label):
        out = ""
        if rows:
            out += f"""<div style="margin-top:6px;font-size:12px;color:{_GRAY};font-weight:600;text-transform:uppercase;">{label} ({len(rows)})</div>"""
            for r in rows[:12]:
                _lnk = ((' &nbsp;<a href="' + _BASE_URL
                         + '/customers?cid=' + str(r["cid"])
                         + '" style="font-size:12px;color:#2563eb;text-decoration:none;">Open &rarr;</a>')
                        if r.get("cid") else "")
                out += f"""<div style="padding:6px 12px;margin-top:4px;background:#fff;border:1px solid #e5e7eb;border-left:4px solid {color};border-radius:6px;font-size:13px;">{r["name"]} <span style="color:{_GRAY};font-size:12px;">— {r["detail"]}</span>{_lnk}</div>"""
            if len(rows) > 12:
                out += f"""<div style="font-size:12px;color:{_GRAY};margin-top:4px;">+{len(rows) - 12} more</div>"""
        return out
    mem_html = (_mem_rows(mem["expiring"], _AMBER, "Expiring soon — personal outreach")
                + _mem_rows(mem["lapsed"], _RED, "Just lapsed — personal outreach")
                + _mem_rows(mem["renewed"], _GREEN, "Renewed (last 7 days)")
                + _mem_rows(mem["new"], _NAVY, "New members (last 7 days)"))
    html += mem_html if mem_html else _info_box("\u2705 No membership movement — nothing expiring within the window")
    html += _section_end()

    # ── Section 1: Action Required — NEW + high urgency in full,
    # standing backlog rolled up by category (detail is one click away).
    detail_items = sorted(
        new_items + high_backlog,
        key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("urgency", "low"), 2))
    overflow = max(0, len(detail_items) - detail_cap)
    detail_items = detail_items[:detail_cap]
    html += _section_header("\U0001f534 Action Required (new + high urgency)")
    if not action_items:
        html += _info_box("\u2705 No open action items")
    elif not detail_items:
        html += _info_box(f"Nothing new in the last 24 hours — {len(backlog)} standing items rolled up below.")
    else:
        for item in detail_items:
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
        if overflow:
            html += _info_box(f"+{overflow} more new/high-urgency items — see the COO Dashboard.")
    plain_backlog = [a for a in backlog if a.get("urgency") != "high"]
    if plain_backlog:
        by_cat = {}
        for a in plain_backlog:
            c = (a.get("category") or "other").upper()
            by_cat.setdefault(c, []).append(a)
        html += f"""<div style="margin-top:10px;font-size:12px;color:{_GRAY};font-weight:600;text-transform:uppercase;">Standing backlog ({len(plain_backlog)})</div>"""
        for c, rows in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
            oldest = min((r.get("email_date") or r.get("created_at") or "")[:10] for r in rows)
            html += f"""
<div style="padding:8px 14px;margin-top:6px;background:#fff;border:1px solid #e5e7eb;border-radius:6px;font-size:13px;">
  <span style="background:#eff6ff;color:#1e40af;padding:1px 6px;border-radius:4px;font-size:11px;font-weight:600;">{c}</span>
  &nbsp;<strong>{len(rows)}</strong> open <span style="color:{_GRAY};">(oldest {oldest})</span>
  &nbsp;<a href="{_BASE_URL}/coo" style="font-size:12px;color:#2563eb;text-decoration:none;">Review &rarr;</a>
</div>"""
    html += _section_end()

    # ── Section 1b: Parse Warnings ──
    html += _section_header("\U0001f50d Parse Warnings")
    if total_warnings == 0:
        html += _info_box("\u2705 No open warnings")
    else:
        warn_border = _RED if new_warnings > 0 else _AMBER
        html += f"""
<div style="padding:12px 16px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;border-left:4px solid {warn_border};">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="font-size:13px;color:{_GRAY};">New (last 24h)</td>
    <td style="font-size:16px;font-weight:700;text-align:right;color:{_RED if new_warnings > 0 else _GRAY};">{new_warnings}</td>
  </tr>
  <tr>
    <td style="font-size:13px;color:{_GRAY};padding-top:4px;">Total open</td>
    <td style="font-size:16px;font-weight:700;text-align:right;padding-top:4px;">{total_warnings}</td>
  </tr>
  </table>
  <div style="margin-top:8px;"><a href="{_BASE_URL}/admin" style="font-size:12px;color:#2563eb;text-decoration:none;">View Audit Log &rarr;</a></div>
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


def _get_outstanding_money() -> dict:
    """Outstanding payouts / refunds / credits for the briefing chips +
    Quick Wins (Kerry 2026-07-20: payouts should go out within 24 hours
    of the event — SLA dial app_settings payout_sla_hours, default 24)."""
    out = {"payout_total": 0.0, "payout_groups": 0, "overdue": [],
           "refund_total": 0.0, "refund_count": 0,
           "credit_total": 0.0, "credit_count": 0}
    try:
        sla_h = int(get_app_setting("payout_sla_hours") or 24)
    except Exception:
        sla_h = 24
    today = now_central()
    try:
        from email_parser.database import get_unpaid_payout_groups
        groups = (get_unpaid_payout_groups() or {}).get("groups", [])
        out["payout_groups"] = len(groups)
        out["payout_total"] = round(sum(float(g.get("total") or 0) for g in groups), 2)
        for g in groups:
            ev_date = (g.get("event_date") or "")[:10]
            try:
                age_h = (today - datetime.strptime(ev_date, "%Y-%m-%d")).total_seconds() / 3600
            except Exception:
                continue
            if age_h > sla_h:
                out["overdue"].append({
                    "name": g.get("name"), "amount": float(g.get("total") or 0),
                    "event": g.get("code"), "days": int(age_h // 24)})
        out["overdue"].sort(key=lambda x: -x["amount"])
    except Exception:
        logger.exception("briefing: unpaid payouts fetch failed")
    try:
        from email_parser.database import get_refunds_overview
        ro = get_refunds_overview() or {}
        outstanding = ro.get("outstanding") or []
        out["refund_count"] = len(outstanding)
        out["refund_total"] = round(sum(float(r.get("amount") or 0) for r in outstanding), 2)
    except Exception:
        logger.exception("briefing: refunds overview fetch failed")
    try:
        from email_parser.database import _parse_dollar
        with _connect() as conn:
            rows = conn.execute("""
                SELECT item_price, transaction_fees, credit_amount,
                       transaction_status
                  FROM items
                 WHERE transaction_status = 'credited'
                    OR (transaction_status = 'wd'
                        AND COALESCE(credit_amount, '') != '')""").fetchall()
        total = 0.0
        for r in rows:
            if r["transaction_status"] == "wd":
                total += _parse_dollar(r["credit_amount"] or "0")
            else:
                total += (_parse_dollar(r["item_price"])
                          + _parse_dollar(r["transaction_fees"] or "0"))
        out["credit_count"] = len(rows)
        out["credit_total"] = round(total, 2)
    except Exception:
        logger.exception("briefing: credits fetch failed")
    return out


def _get_membership_summary() -> dict:
    """Membership movement for the briefing (Kerry 2026-07-20: "Who's
    about to expire, vs who's renewed or new. Need to know who I can
    reach out to personally"). Windows are dials:
    app_settings daily_briefing_expiry_window (days ahead, default 30)
    and daily_briefing_recent_window (days back, default 7)."""
    try:
        ahead = int(get_app_setting("daily_briefing_expiry_window") or 30)
    except Exception:
        ahead = 30
    try:
        back = int(get_app_setting("daily_briefing_recent_window") or 7)
    except Exception:
        back = 7
    today = now_central().strftime("%Y-%m-%d")
    ahead_str = (now_central() + timedelta(days=ahead)).strftime("%Y-%m-%d")
    back_str = (now_central() - timedelta(days=back)).strftime("%Y-%m-%d")
    out = {"expiring": [], "lapsed": [], "renewed": [], "new": []}
    try:
        with _connect() as conn:
            # Latest term per customer
            latest = conn.execute("""
                SELECT m.customer_id,
                       TRIM(c.first_name || ' ' || c.last_name) AS name,
                       MAX(m.expires_at) AS expires_at
                  FROM customer_memberships m
                  JOIN customers c ON c.customer_id = m.customer_id
                 GROUP BY m.customer_id""").fetchall()
            for r in latest:
                exp = (r["expires_at"] or "")[:10]
                if today <= exp <= ahead_str:
                    out["expiring"].append(
                        {"name": r["name"], "detail": f"expires {exp}",
                         "cid": r["customer_id"]})
                elif back_str <= exp < today:
                    out["lapsed"].append(
                        {"name": r["name"], "detail": f"expired {exp}",
                         "cid": r["customer_id"]})
            out["expiring"].sort(key=lambda x: x["detail"])
            out["lapsed"].sort(key=lambda x: x["detail"])
            # Renewals + first-time members in the recent window
            recent = conn.execute("""
                SELECT m.customer_id, m.started_at, m.source,
                       TRIM(c.first_name || ' ' || c.last_name) AS name,
                       (SELECT COUNT(*) FROM customer_memberships m2
                         WHERE m2.customer_id = m.customer_id) AS terms
                  FROM customer_memberships m
                  JOIN customers c ON c.customer_id = m.customer_id
                 WHERE m.created_at >= ?""", (back_str,)).fetchall()
            for r in recent:
                row = {"name": r["name"], "cid": r["customer_id"],
                       "detail": f"term started {(r['started_at'] or '')[:10]}"}
                (out["new"] if r["terms"] <= 1 else out["renewed"]).append(row)
    except Exception:
        logger.exception("briefing membership summary failed")
    return out


def _get_admin_overview(new_items, backlog, snapshot, upcoming, mem, money) -> dict:
    """One Claude call producing the prioritized 24h summary + quick
    wins for the top of the briefing. Returns {"summary": [...],
    "quick_wins": [...]} — empty lists on any failure so the email
    still sends."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"summary": [], "quick_wins": []}
    context = {
        "new_action_items_24h": [
            {"category": a.get("category"), "urgency": a.get("urgency"),
             "from": a.get("from_name"),
             "summary": (a.get("summary") or "")[:200]}
            for a in new_items[:25]],
        "backlog_count": len(backlog),
        "backlog_categories": {},
        "memberships": {
            "expiring_soon": [m["name"] for m in mem["expiring"][:15]],
            "just_lapsed": [m["name"] for m in mem["lapsed"][:15]],
            "renewed_recent": len(mem["renewed"]),
            "new_recent": len(mem["new"])},
        "available_to_spend": snapshot["obligations"]["available_to_spend"],
        "upcoming_events": [e.get("item_name") for e in upcoming[:6]],
        "outstanding_money": {
            "unpaid_payout_total": money["payout_total"],
            "overdue_payout_groups": len(money["overdue"]),
            "outstanding_refund_total": money["refund_total"],
            "open_credit_total": money["credit_total"]},
    }
    for a in backlog:
        c = (a.get("category") or "other")
        context["backlog_categories"][c] = context["backlog_categories"].get(c, 0) + 1

    prompt = f"""You are the TGF COO Agent writing the morning administrative overview.
From the state below, produce:
- "summary": 3-6 bullets organizing the LAST 24 HOURS by priority — what happened, what needs Kerry today, grouped logically (events/courses first, then money, then members). Plain sentences, no headers.
- "quick_wins": 0-4 bullets, each a single small action Kerry could clear in under 5 minutes right now (a reply, a tap, a confirmation). Only include genuinely quick items; omit if none.

State:
{json.dumps(context, indent=1)}

Return ONLY JSON: {{"summary": ["..."], "quick_wins": ["..."]}}"""
    try:
        client = _anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}])
        text = resp.content[0].text.strip()
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return {"summary": list(data.get("summary") or []),
                    "quick_wins": list(data.get("quick_wins") or [])}
    except Exception as e:
        logger.warning("admin overview AI failed: %s", e)
    return {"summary": [], "quick_wins": []}


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
