"""THE SAME-NIGHT ADMIN PAYOUT REPORT (Kerry 2026-10-26, CoS #2329 item 6,
#2331 item 7): "I like to pay same night as a standard. ... Needs an
automated Admin report once all events are completed that would carry a link
to PAYMENTS."

Once EVERY active event dated today (Central) is closed, one email goes to
Kerry: each event's name, players, the payouts recorded, what is still
unpaid, and a button to Payouts -> Unpaid (/tgf?view=unpaid).

"Closed" is the closeout's own test, never a new one:
closeout_checks.closeout_final_check(event)["final"] (cards in, parity,
payouts recorded; it blocks while no payouts exist). An event with nobody on
its roster is skipped, so a cancelled date never holds the report.

- Staff only: the recipient is app setting admin_payout_report_to (default
  kerry@thegolffellowship.com) and must be a @thegolffellowship.com address.
- Once per day: app setting admin_payout_report_sent:<YYYY-MM-DD>.
- Logged in message_log and agent_action_log.
- Dial admin_payout_report (on unless it reads off).
- Job admin_payout_report every 15 minutes, 5:00 PM to 11:45 PM Central.
- Read-only bridge scoring-admin-payout-report[:<YYYY-MM-DD>] (dry run).
"""
from __future__ import annotations

import html as _html
import logging
import os

logger = logging.getLogger(__name__)

DIAL = "admin_payout_report"
TO_KEY = "admin_payout_report_to"
TO_DEFAULT = "kerry@thegolffellowship.com"
SENT_KEY = "admin_payout_report_sent:{day}"
STAFF_DOMAIN = "@thegolffellowship.com"
PAYMENTS_PATH = "/tgf?view=unpaid"
FROM_HOUR = 17          # 5:00 PM Central


def _e(s) -> str:
    return _html.escape(str(s if s is not None else ""))


def _on(db_path=None) -> bool:
    from email_parser.database import get_app_setting
    return (get_app_setting(DIAL, db_path=db_path) or "").strip().lower() not in ("off", "0", "false", "no")


def recipient(db_path=None) -> str | None:
    """The staff address, or None when the setting names anyone else."""
    from email_parser.database import get_app_setting
    to = (get_app_setting(TO_KEY, db_path=db_path) or "").strip() or TO_DEFAULT
    return to if to.lower().endswith(STAFF_DOMAIN) else None


def payments_url() -> str:
    from email_parser.invitations import _base_url
    return f"{_base_url()}{PAYMENTS_PATH}"


def _money(x) -> str:
    return f"${float(x or 0):,.2f}"


def plan(day: str, db_path=None) -> dict:
    """What the report would say for one Central date. Nothing is sent."""
    from email_parser import database as db
    from email_parser.closeout_checks import closeout_final_check, _payout_rows
    with db._connect(db_path) as conn:
        evs = [dict(r) for r in conn.execute(
            "SELECT id, item_name, chapter, event_date FROM events WHERE substr(event_date, 1, 10) = ? "
            "AND COALESCE(status, 'active') = 'active' ORDER BY item_name", (day,)).fetchall()]
        rows = []
        for ev in evs:
            roster = db._event_roster_rows(conn, int(ev["id"]))
            if not roster:
                continue
            pays = _payout_rows(conn, int(ev["id"]))
            rows.append({"event_id": int(ev["id"]), "name": ev["item_name"], "chapter": ev.get("chapter") or "",
                         "players": len(roster), "payouts": len(pays),
                         "total": round(sum(float(p["amount"] or 0) for p in pays), 2),
                         "unpaid": round(sum(float(p["amount"] or 0) for p in pays if not p.get("paid_at")), 2),
                         "unpaid_count": sum(1 for p in pays if not p.get("paid_at"))})
    for r in rows:
        chk = closeout_final_check(r["event_id"], db_path=db_path)
        r["closed"] = bool(chk.get("final"))
        r["blocking"] = chk.get("blocking") or ([chk["error"]] if chk.get("error") else [])
        # VERIFY BEFORE PAY (Kerry 10/28 #2460-B): None unless the
        # payout_verify_gate dial is on and the check has not passed.
        from email_parser.payout_verify import lock_for
        r["pay_locked"] = lock_for(r["event_id"], db_path=db_path)
    return {"day": day, "events": rows, "all_closed": bool(rows) and all(r["closed"] for r in rows)}


def build(p: dict) -> dict:
    """{subject, html} for the plan."""
    from email_parser.event_day_email import frame
    from datetime import date
    try:
        d = date.fromisoformat(p["day"])
        day_long = f"{d.strftime('%A')}, {d.strftime('%B')} {d.day}"
    except ValueError:
        day_long = p["day"]
    unpaid = round(sum(r["unpaid"] for r in p["events"]), 2)
    trs = "".join(
        f'<tr><td style="padding:6px 8px;border-bottom:1px solid #E5E7EB;">{_e(r["name"])}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #E5E7EB;text-align:right;">{r["players"]}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #E5E7EB;text-align:right;">{r["payouts"]} &middot; {_money(r["total"])}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #E5E7EB;text-align:right;font-weight:700;">{_money(r["unpaid"])}</td></tr>'
        for r in p["events"])
    btn = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" '
           'style="margin:18px auto;"><tr><td bgcolor="#E87C3E" style="background:#E87C3E;border-radius:999px;">'
           f'<a href="{_e(payments_url())}" style="display:inline-block;background:#E87C3E;color:#ffffff;'
           'font-weight:700;font-size:16px;line-height:1;padding:14px 28px;border-radius:999px;'
           'text-decoration:none;font-family:Helvetica,Arial,sans-serif;">'
           '<span style="color:#ffffff;">Open PAYMENTS</span></a></td></tr></table>')
    locked = [r for r in p["events"] if r.get("pay_locked")]
    if locked:
        # The button stays locked while any event's check has not passed.
        btn = ('<p style="margin:18px 0;padding:12px 14px;background:#FEF2F2;border:1px solid #FECACA;'
               'border-radius:8px;color:#991B1B;"><strong>Pay is locked</strong> until the Tracker\'s '
               'check passes:<br>' + "<br>".join(f"{_e(r['name'])}: {_e(r['pay_locked'])}" for r in locked)
               + "</p>")
    inner = (f"<p>Every event for {_e(day_long)} is closed. "
             f"<strong>{_money(unpaid)}</strong> is waiting to be paid.</p>"
             '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
             'style="border-collapse:collapse;font-size:14px;">'
             '<tr style="color:#6B7280;"><td style="padding:6px 8px;">Event</td>'
             '<td style="padding:6px 8px;text-align:right;">Players</td>'
             '<td style="padding:6px 8px;text-align:right;">Payouts</td>'
             '<td style="padding:6px 8px;text-align:right;">Unpaid</td></tr>'
             f"{trs}</table>{btn}"
             '<p style="font-size:12px;color:#6B7280;">Sent by the Tracker once the night\'s closeout is done.</p>')
    return {"subject": f"Ready to pay: {day_long}, {_money(unpaid)} unpaid",
            "html": frame(inner, "ADMIN", "Same-night payouts")}


def run(day: str | None = None, confirm: bool = False, now=None, db_path=None) -> dict:
    """The job step. Dry run unless confirm."""
    from email_parser import database as db
    from email_parser.timezone_utils import now_central
    now = now or now_central()
    day = day or now.date().isoformat()
    if not _on(db_path):
        return {"status": "off"}
    key = SENT_KEY.format(day=day)
    if db.get_app_setting(key, db_path=db_path):
        return {"status": "already sent", "day": day}
    p = plan(day, db_path)
    if not p["events"]:
        return {"status": "no events today", "day": day}
    if not p["all_closed"]:
        return {"status": "waiting", "day": day,
                "open": [{"event": r["name"], "blocking": r["blocking"]} for r in p["events"] if not r["closed"]]}
    verifying = [r for r in p["events"] if (r.get("pay_locked") or "").startswith("Verifying")]
    if verifying:
        return {"status": "waiting", "day": day,
                "open": [{"event": r["name"], "blocking": [r["pay_locked"]]} for r in verifying]}
    to = recipient(db_path)
    if not to:
        return {"status": "held", "why": f"{TO_KEY} is not a staff address", "day": day}
    msg = build(p)
    if confirm is not True:
        return {"status": "would send", "to": to, "plan": p, "subject": msg["subject"], "dry_run": True}
    creds = [os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")]
    if not all(creds):
        return {"status": "error", "error": "Email credentials not configured"}
    from email_parser.fetcher import send_mail_graph
    ok = False
    try:
        ok = send_mail_graph(tenant_id=creds[0], client_id=creds[1], client_secret=creds[2],
                             from_address=creds[3], to_address=to,
                             subject=msg["subject"], html_body=msg["html"])
    except Exception:
        logger.exception("admin payout report: send failed")
    try:
        db.log_message({"event_name": "admin-payout-report", "template_id": None, "channel": "email",
                        "recipient_name": "Admin", "recipient_address": to, "subject": msg["subject"],
                        "body_preview": f"admin payout report {day}", "status": "sent" if ok else "failed",
                        "error_message": None if ok else "Send failed", "sent_by": "admin-payout-report"},
                       db_path=db_path)
        db.log_agent_action("admin-payout-report", "admin_payout_report",
                            f"{day}: {len(p['events'])} event(s), "
                            f"{_money(sum(r['unpaid'] for r in p['events']))} unpaid, "
                            f"{'sent' if ok else 'FAILED'} to {to}")
    except Exception:
        logger.exception("admin payout report: could not log")
    if ok:
        db.set_app_setting(key, now.strftime("%Y-%m-%d %H:%M"), db_path=db_path)
    return {"status": "sent" if ok else "failed", "to": to, "day": day, "events": len(p["events"])}


def tick(now=None, db_path=None) -> dict:
    """Every 15 minutes: from 5:00 PM Central until midnight."""
    from email_parser.timezone_utils import now_central
    now = now or now_central()
    if now.hour < FROM_HOUR:
        return {"status": "not yet"}
    return run(now=now, confirm=True, db_path=db_path)
