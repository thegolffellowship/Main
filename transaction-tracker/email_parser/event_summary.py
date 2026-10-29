"""THE EVENT SUMMARY (Event Ops #2460-E, Kerry 2026-10-29).

Kerry: "there should be a Summary page created on the Tracker, probably for
each event, and a direct link is sent to Managers & Admin to go see the full
report ... Handicap changes, Payout stuff, Financial report, Pace of Play
report. It could probably take place of the FINANCIAL tab ... PAYOUTS tab can
move under this SUMMARY tab. RECAP could also go in there with the ability to
edit it before it goes to players if manager/admin beats the time window to
make adjustments." And: "Admin payout report should include more
information. This should be a manager's full report".

ONE payload (`build_summary`) feeds all three surfaces: the SUMMARY tab on
the event (templates/events.html), the standalone phone page
/events/<id>/summary (`render_page`), and the manager email
(`send_summary_email`). Every figure is read from the record:
  players    the pairings roster (database._event_roster_rows)
  financial  database.get_event_financial_summary (admin only unless app
             setting event_summary_financial_managers is on)
  payouts    tgf_payouts for the event (count, total, unpaid, per golfer)
  handicaps  the rounds POSTED for the event, rebuilt the way the handicap
             recap email rebuilds them (index before -> after)
  pace       pace_report.event_report (groups fastest first, est round)
  recap      the night's stored recap (recap_store), editable until the
             results email that carries it has sent

The email goes to STAFF ONLY: the chapter manager (pairings_approval.
manager_for) and the admin (admin_payout_report.recipient), each address
checked with recap_mail.staff_only. It is meant to replace both the
same-night admin payout report and the handicap recap email. Dial
`event_summary_email` (default OFF): when on, the admin payout report job
sends this email once per event (stamp event_summary_sent:<id>) at the
moment it would have sent its own, and the admin payout report and the
handicap recap email skip. Nothing here pays, deletes, or mails a member.
Bridge scoring-event-summary:<event_id>[|preview[|<staff email>]].
Guard test_event_summary.py.
"""
from __future__ import annotations

import html as _html
import logging

logger = logging.getLogger(__name__)

DIAL = "event_summary_email"
FIN_DIAL = "event_summary_financial_managers"
SENT_KEY = "event_summary_sent:{}"
SENT_BY = "event-summary"
RECAP_MAX = 60000


def _e(s) -> str:
    return _html.escape("" if s is None else str(s))


def _money(x) -> str:
    return f"${float(x or 0):,.2f}"


def _flag(key, db_path=None) -> bool:
    from email_parser.database import get_app_setting
    return (get_app_setting(key, db_path=db_path) or "").strip().lower() in ("1", "on", "true", "yes")


def dial_on(db_path=None) -> bool:
    """The summary email replaces the admin payout report and the handicap
    recap email. Default OFF."""
    return _flag(DIAL, db_path)


def may_see_financial(role: str | None, db_path=None) -> bool:
    """FINANCIAL is admin-only (Kerry 2026-08-05); managers see it in the
    summary only when app setting event_summary_financial_managers is on."""
    return role == "admin" or (role == "manager" and _flag(FIN_DIAL, db_path))


def summary_url(event_id: int) -> str:
    from email_parser.score_entry import _base_url
    return f"{_base_url()}/events/{int(event_id)}/summary"


def event_row(event_id: int, db_path=None) -> dict | None:
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT id, item_name, event_date, chapter, course, "
                         "COALESCE(status, 'active') AS status FROM events WHERE id = ?",
                         (int(event_id),)).fetchone()
    return dict(r) if r else None


# ---------------------------------------------------------------------------
# The sections
# ---------------------------------------------------------------------------

def _payouts(conn, event_id: int) -> dict:
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT p.id, p.customer_id, p.category, p.amount, p.description, p.paid_at, "
            "TRIM(COALESCE(c.first_name, '') || ' ' || COALESCE(c.last_name, '')) AS name "
            "FROM tgf_payouts p JOIN tgf_events t ON t.id = p.event_id "
            "LEFT JOIN customers c ON c.customer_id = p.customer_id "
            "WHERE t.events_id = ? ORDER BY p.id", (int(event_id),)).fetchall()]
    except Exception:
        rows = []
    golfers: dict = {}
    for p in rows:
        g = golfers.setdefault(p["customer_id"], {"customer_id": p["customer_id"],
                                                  "name": (p["name"] or "").strip() or f"#{p['customer_id']}",
                                                  "total": 0.0, "unpaid": 0.0, "items": []})
        amt = float(p["amount"] or 0)
        g["total"] = round(g["total"] + amt, 2)
        if not p["paid_at"]:
            g["unpaid"] = round(g["unpaid"] + amt, 2)
        g["items"].append({"category": p["category"], "description": p["description"],
                           "amount": round(amt, 2), "paid": bool(p["paid_at"])})
    total = round(sum(float(p["amount"] or 0) for p in rows), 2)
    unpaid = [p for p in rows if not p["paid_at"]]
    return {"count": len(rows), "total": total,
            "unpaid": round(sum(float(p["amount"] or 0) for p in unpaid), 2),
            "unpaid_count": len(unpaid),
            "winners": sorted(golfers.values(), key=lambda g: (-g["total"], g["name"]))}


def _financial(name: str, db_path=None) -> dict:
    from email_parser import database as db
    try:
        f = db.get_event_financial_summary(name, db_path=db_path)
    except Exception as exc:
        logger.exception("event summary: financial summary failed")
        return {"error": f"{type(exc).__name__}: {exc}"}
    rev, exp, con = f.get("revenue") or {}, f.get("expenses") or {}, f.get("contra_revenue") or {}
    return {"revenue": rev.get("total"), "credits_and_refunds": con.get("total"),
            "net_revenue": f.get("net_revenue"), "course_fees": exp.get("course_fees"),
            "prize_fund": exp.get("prize_fund"), "processing_fees": exp.get("processing_fees"),
            "expenses": exp.get("total"), "projected_profit": f.get("projected_profit"),
            "player_counts": f.get("player_counts"),
            "accounting_verified": bool(f.get("accounting_verified")),
            "revenue_discrepancy": f.get("revenue_discrepancy")}


def _handicaps(name: str, db_path=None) -> dict:
    """The handicap changes POSTED for the event, rebuilt the way
    send_handicap_recap_for_event rebuilds them (the pre-posting pool
    excludes the event's own rounds, so before -> after stays right after
    posting). One row per player; a two-nine posting carries both
    differentials."""
    from email_parser import database as db
    rows = []
    try:
        pv = db.get_scoring_handicap_preview(name, db_path=db_path) if db_path \
            else db.get_scoring_handicap_preview(name)
        if pv.get("error") and not pv.get("skipped_by_ruling"):
            pv = {"rounds": []}
        if pv.get("skipped_by_ruling"):
            return {"posted": 0, "moved": 0, "rows": [], "note": pv.get("error")}
        rows = [{"player_name": r["player_name"], "customer_id": r["customer_id"],
                 "differential": r["differential_ndb"], "index_now": r["index_now"],
                 "index_after": r["index_after_ndb"]}
                for r in pv.get("rounds") or [] if r.get("already_imported")]
        if not rows:
            rows = [{k: r.get(k) for k in ("player_name", "customer_id", "differential",
                                            "index_now", "index_after")}
                    for r in db._two_nine_recap_rows(name, db_path=db_path)]
    except Exception as exc:
        logger.exception("event summary: handicap rows failed")
        return {"posted": 0, "moved": 0, "rows": [], "error": f"{type(exc).__name__}: {exc}"}
    players: dict = {}
    for r in rows:
        key = r["customer_id"] or r["player_name"]
        p = players.setdefault(key, {"player_name": r["player_name"], "customer_id": r["customer_id"],
                                     "differentials": [], "index_before": r["index_now"],
                                     "index_after": r["index_after"]})
        if r["differential"] is not None:
            p["differentials"].append(r["differential"])
    out = []
    for p in players.values():
        b, a = p["index_before"], p["index_after"]
        p["change"] = round(a - b, 1) if a is not None and b is not None else None
        p["new"] = b is None
        out.append(p)
    out.sort(key=lambda p: (p["change"] if p["change"] is not None else 99.0, p["player_name"] or ""))
    moved = sum(1 for p in out if p["new"] or (p["change"] or 0) != 0)
    return {"posted": len(out), "moved": moved, "rows": out}


def _pace(event_id: int, db_path=None) -> dict:
    from email_parser import pace_report as pr
    try:
        rep = pr.event_report(int(event_id), db_path=db_path)
    except Exception as exc:
        logger.exception("event summary: pace report failed")
        return {"rounds": [], "error": f"{type(exc).__name__}: {exc}"}
    rounds = [r for r in rep.get("rounds") or [] if not r.get("error")]
    timed = [(g, r) for r in rounds for g in r.get("groups") or []
             if g.get("seconds_per_hole") is not None and g.get("status") != "flagged"]
    timed.sort(key=lambda gr: gr[0]["seconds_per_hole"])

    def _pick(gr):
        if not gr:
            return None
        g, r = gr
        return {"players": g["players"], "min_per_hole": g["min_per_hole"], "est_round": g["est_round"],
                "start": g["start"], "round": r.get("label")}
    return {"rounds": rounds, "fastest": _pick(timed[0] if timed else None),
            "slowest": _pick(timed[-1] if len(timed) > 1 else None)}


def recap_info(ev: dict, db_path=None) -> dict:
    """The night's recap and whether it can still be edited. The recap is
    found the way the closeout chain stores it (closeout_recap_night:<date>),
    else on the results email schedule. It locks once a results email that
    carries it has sent (state 'sent', or a run that sent any message)."""
    from email_parser import database as db
    from email_parser import recap_store
    from email_parser import results_email as re_
    from email_parser.closeout_chain import NIGHT_KEY
    eid = int(ev["id"])
    name = db.get_app_setting(NIGHT_KEY.format(str(ev.get("event_date") or "")[:10]), db_path=db_path)
    entries = []
    for key, s in re_._json_setting(re_.SCHEDULE_KEY, db_path).items():
        try:
            ids = [int(x) for x in key.partition("|")[0].split(",") if x.strip()]
        except ValueError:
            continue
        if eid in ids and isinstance(s, dict) and s.get("recap"):
            entries.append(s)
    if not name and entries:
        name = entries[-1]["recap"]
    if not name:
        return {"name": None, "md": None, "editable": False,
                "why": "No recap is written for this night yet. It is written at the end of the closeout."}
    mine = [s for s in entries if s.get("recap") == name]
    sent = [s for s in mine if s.get("state") == "sent" or (s.get("last_run") or {}).get("sent")]
    pending = [s for s in mine if s.get("state") in ("scheduled", "held")]
    out = {"name": name, "md": None, "editable": False, "sent_at": None, "send_at": None,
           "edited": False, "edited_by": None, "edited_at": None, "why": None}
    try:
        out["md"] = recap_store.read_text(name, db_path=db_path)
    except Exception as exc:
        out["why"] = f"The recap {name} could not be read ({exc})."
        return out
    if recap_store.is_db(name):
        meta = (recap_store.load(name, db_path=db_path) or {}).get("meta") or {}
        out.update(edited=bool(meta.get("edited")), edited_by=meta.get("edited_by"),
                   edited_at=meta.get("edited_at"))
    if sent:
        out["sent_at"] = sent[0].get("sent_at") or sent[0].get("at")
        out["why"] = "Locked: the results email carrying this recap has gone to the players."
    elif not recap_store.is_db(name):
        out["why"] = "This recap is a file in the repo; edit it there."
    else:
        out["editable"] = True
    if pending:
        out["send_at"] = min(s["at"] for s in pending)
    return out


def save_recap(event_id: int, md: str, who: str, db_path=None) -> dict:
    """A manager's or admin's edit before the recap goes to the players.
    Writes through recap_store.update_text and is logged."""
    from email_parser import database as db
    from email_parser import recap_store
    ev = event_row(event_id, db_path)
    if not ev:
        return {"error": "no such event", "code": 404}
    text = (md or "").replace("\r\n", "\n").strip()
    if not text:
        return {"error": "the recap cannot be empty", "code": 400}
    if len(text) > RECAP_MAX:
        return {"error": f"the recap is over {RECAP_MAX} characters", "code": 400}
    info = recap_info(ev, db_path)
    if not info["editable"]:
        return {"error": info.get("why") or "this recap cannot be edited", "code": 409}
    before = info.get("md") or ""
    if before.strip() == text:
        return {"ok": True, "name": info["name"], "changed": False}
    recap_store.update_text(info["name"], text + "\n", db_path=db_path, who=who)
    try:
        db.log_agent_action(SENT_BY, "recap_edit",
                            f"{info['name']} edited from event {int(event_id)} ({ev['item_name']}) by {who}: "
                            f"{len(before)} -> {len(text)} chars", db_path=db_path)
    except Exception:
        logger.exception("event summary: could not log the recap edit")
    return {"ok": True, "name": info["name"], "changed": True}


# ---------------------------------------------------------------------------
# The payload
# ---------------------------------------------------------------------------

def build_summary(event_id: int, include_financial: bool = True, db_path=None) -> dict:
    """The one payload the SUMMARY tab, the page and the email read."""
    from email_parser import database as db
    ev = event_row(event_id, db_path)
    if not ev:
        return {"error": f"no event {event_id}"}
    with db._connect(db_path) as conn:
        try:
            players = len(db._event_roster_rows(conn, int(event_id)))
        except Exception:
            logger.exception("event summary: roster read failed")
            players = None
        pays = _payouts(conn, int(event_id))
    fin = _financial(ev["item_name"], db_path)
    hc = _handicaps(ev["item_name"], db_path)
    pace = _pace(int(event_id), db_path)
    recap = recap_info(ev, db_path)
    games_total = fin.get("prize_fund") if not fin.get("error") else None
    out = {
        "event": {"id": int(ev["id"]), "name": ev["item_name"], "date": str(ev["event_date"] or "")[:10],
                  "chapter": ev["chapter"] or "", "course": ev["course"] or "", "status": ev["status"]},
        "headline": {"players": players, "games_total": games_total,
                     "payouts_count": pays["count"], "payouts_total": pays["total"],
                     "unpaid": pays["unpaid"], "unpaid_count": pays["unpaid_count"],
                     "handicaps_posted": hc["posted"], "handicap_changes": hc["moved"],
                     "fastest": pace["fastest"], "slowest": pace["slowest"]},
        "financial": fin if include_financial else {"hidden": True,
                                                    "why": "The financial report is admin only."},
        "payouts": pays, "handicaps": hc, "pace": pace, "recap": recap,
        "links": {"summary": summary_url(int(ev["id"])),
                  "tracker": f"/events?event={int(ev['id'])}&view=summary"},
    }
    return out


# ---------------------------------------------------------------------------
# The email (staff only)
# ---------------------------------------------------------------------------

def _gs(db_path):
    from email_parser import database as db

    def gs(k):
        try:
            return db.get_app_setting(k, db_path=db_path)
        except Exception:
            return None
    return gs


def recipients(chapter: str | None, db_path=None) -> tuple[list, list]:
    """(staff addresses, refused addresses): the chapter manager and the
    admin, de-duplicated. A non-staff address is refused, never mailed."""
    from email_parser.pairings_approval import manager_for
    from email_parser.admin_payout_report import recipient as admin_to
    from email_parser.recap_mail import staff_only, _addrs
    want = _addrs((manager_for(chapter, db_path) or {}).get("email")) + _addrs(admin_to(db_path))
    seen, out = set(), []
    for a in want:
        if a.lower() not in seen:
            seen.add(a.lower())
            out.append(a)
    bad = staff_only(out, _gs(db_path))
    return [a for a in out if a not in bad], bad


def _pace_line(p) -> str:
    if not p:
        return "&mdash;"
    return (f"{_e(', '.join(p['players']))}<br><span style=\"color:#6B7280;\">"
            f"{_e(p['min_per_hole'])} min/hole &middot; est. {_e(p['est_round'])}</span>")


def build_email(s: dict) -> dict:
    """{subject, html}: the headline numbers and a button to the page."""
    from email_parser.event_day_email import frame
    from email_parser.admin_payout_report import payments_url
    ev, h = s["event"], s["headline"]
    td = 'style="padding:6px 8px;border-bottom:1px solid #E5E7EB;vertical-align:top;"'
    tdr = 'style="padding:6px 8px;border-bottom:1px solid #E5E7EB;text-align:right;vertical-align:top;font-weight:700;"'
    rows = [("Players", _e(h["players"] if h["players"] is not None else "?")),
            ("Games (prize fund)", _money(h["games_total"]) if h["games_total"] is not None else "&mdash;"),
            ("Payouts recorded", f"{h['payouts_count']} &middot; {_money(h['payouts_total'])}"),
            ("Unpaid", f"{h['unpaid_count']} &middot; {_money(h['unpaid'])}"),
            ("Handicap changes", f"{h['handicap_changes']} of {h['handicaps_posted']} posted"),
            ("Fastest group", _pace_line(h["fastest"])),
            ("Slowest group", _pace_line(h["slowest"]))]
    trs = "".join(f"<tr><td {td}>{k}</td><td {tdr}>{v}</td></tr>" for k, v in rows)
    rc = s.get("recap") or {}
    if rc.get("editable"):
        rline = ("The recap can still be edited on the summary page"
                 + (f" before it goes to the players ({_e(rc['send_at'].replace('T', ' '))})." if rc.get("send_at")
                    else " before it goes to the players."))
    elif rc.get("name"):
        rline = _e(rc.get("why") or "")
    else:
        rline = "No recap is written yet."
    btn = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" '
           'style="margin:18px auto;"><tr><td bgcolor="#E87C3E" style="background:#E87C3E;border-radius:999px;">'
           f'<a href="{_e(s["links"]["summary"])}" style="display:inline-block;background:#E87C3E;color:#ffffff;'
           'font-weight:700;font-size:16px;line-height:1;padding:14px 28px;border-radius:999px;'
           'text-decoration:none;font-family:Helvetica,Arial,sans-serif;">'
           '<span style="color:#ffffff;">Open the full summary</span></a></td></tr></table>')
    inner = (f"<p>{_e(ev['name'])} is closed out. The full report (financial, payouts, handicap changes, "
             f"pace of play and the recap) is on the summary page.</p>"
             '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
             f'style="border-collapse:collapse;font-size:14px;">{trs}</table>'
             f'<p style="font-size:14px;">{rline}</p>{btn}'
             f'<p style="font-size:12px;color:#6B7280;">Pay from <a href="{_e(payments_url())}">PAYMENTS</a> '
             "(admin). Staff only; sent by the Tracker once the night's closeout is done.</p>")
    subject = (f"Event summary: {ev['name']}, {h['players'] if h['players'] is not None else '?'} players, "
               f"{_money(h['unpaid'])} unpaid")
    return {"subject": subject, "html": frame(inner, (ev.get("chapter") or "TGF").upper(), "Event summary")}


def send_summary_email(event_id: int, to=None, dry_run: bool = False, force: bool = False,
                       now=None, db_path=None) -> dict:
    """ONE email to the chapter manager + admin (staff only), once per event
    (event_summary_sent:<id>). `to` sends a preview to the staff address(es)
    named instead and stamps nothing. dry_run returns the payload."""
    from email_parser import database as db
    from email_parser.recap_mail import staff_only, _addrs
    from email_parser.timezone_utils import now_central
    s = build_summary(event_id, include_financial=False, db_path=db_path)
    if s.get("error"):
        return s
    key = SENT_KEY.format(int(event_id))
    preview = bool(to)
    refused: list = []
    if preview:
        rc = _addrs(to)
        bad = staff_only(rc, _gs(db_path))
        if bad:
            return {"error": f"the event summary goes to TGF staff only; refused {bad}"}
    else:
        stamp = db.get_app_setting(key, db_path=db_path)
        if stamp and not force:
            return {"status": "already sent", "event_id": int(event_id), "at": stamp}
        rc, refused = recipients(s["event"]["chapter"], db_path)
    msg = build_email(s)
    if not rc:
        return {"status": "held", "why": "no staff recipient", "refused": refused}
    if dry_run:
        return {"status": "would send", "to": rc, "refused": refused, "preview": preview,
                "subject": msg["subject"], "payload": s, "dry_run": True}
    from email_parser.event_day_email import _creds
    creds = _creds()
    if not creds:
        return {"status": "error", "error": "Email credentials not configured"}
    from email_parser import fetcher
    ok = False
    try:
        ok = fetcher.send_mail_graph(tenant_id=creds[0], client_id=creds[1], client_secret=creds[2],
                                     from_address=creds[3], to_address=", ".join(rc),
                                     subject=msg["subject"], html_body=msg["html"])
    except Exception:
        logger.exception("event summary: send failed")
    now = now or now_central()
    try:
        db.log_message({"event_name": s["event"]["name"], "template_id": None, "channel": "email",
                        "recipient_name": "Manager + Admin", "recipient_address": ", ".join(rc),
                        "subject": msg["subject"],
                        "body_preview": f"event summary {int(event_id)}{' (preview)' if preview else ''}",
                        "status": "sent" if ok else "failed",
                        "error_message": None if ok else "Send failed", "sent_by": SENT_BY}, db_path=db_path)
        db.log_agent_action(SENT_BY, "event_summary_email",
                            f"event {int(event_id)} {s['event']['name']}: "
                            f"{'preview ' if preview else ''}{'sent' if ok else 'FAILED'} to {', '.join(rc)}"
                            + (f"; refused {refused}" if refused else ""), db_path=db_path)
    except Exception:
        logger.exception("event summary: could not log")
    if ok and not preview:
        db.set_app_setting(key, now.strftime("%Y-%m-%d %H:%M"), db_path=db_path)
    return {"status": "sent" if ok else "failed", "to": rc, "refused": refused,
            "preview": preview, "event_id": int(event_id)}


def run_for_plan(p: dict, confirm: bool = False, now=None, db_path=None) -> dict:
    """Called by admin_payout_report.run once every event of the day is
    closed, when the dial is on: the summary email per event replaces the
    admin payout report. When every event's summary has gone, the admin
    report's own day stamp is set so it never sends that day."""
    from email_parser import database as db
    from email_parser.admin_payout_report import SENT_KEY as APR_KEY
    results = []
    for r in p["events"]:
        results.append({"event": r["name"], "event_id": r["event_id"],
                        **{k: v for k, v in send_summary_email(r["event_id"], dry_run=not confirm, now=now,
                                                               db_path=db_path).items() if k != "payload"}})
    if not confirm:
        return {"status": "would send", "replaced_by": DIAL, "day": p["day"], "events": results,
                "dry_run": True}
    done = all(x.get("status") in ("sent", "already sent") for x in results)
    if done:
        from email_parser.timezone_utils import now_central
        db.set_app_setting(APR_KEY.format(day=p["day"]), (now or now_central()).strftime("%Y-%m-%d %H:%M"),
                           db_path=db_path)
    return {"status": "sent" if done else "failed", "replaced_by": DIAL, "day": p["day"], "events": results}


# ---------------------------------------------------------------------------
# The standalone page (phone first)
# ---------------------------------------------------------------------------

def _h(title: str, body: str, sid: str) -> str:
    return f'<section id="{sid}"><h2>{_e(title)}</h2>{body}</section>'


def _fin_html(f: dict) -> str:
    if f.get("hidden"):
        return f'<p class="muted">{_e(f.get("why"))}</p>'
    if f.get("error"):
        return f'<p class="muted">The financial summary could not be built: {_e(f["error"])}</p>'
    lines = [("Revenue", f.get("revenue")), ("Credits and refunds", f.get("credits_and_refunds")),
             ("Net revenue", f.get("net_revenue")), ("Course fees", f.get("course_fees")),
             ("Prize fund (games)", f.get("prize_fund")), ("Processing fees", f.get("processing_fees")),
             ("Expenses", f.get("expenses"))]
    trs = "".join(f"<tr><td>{_e(k)}</td><td class=\"n\">{_money(v)}</td></tr>" for k, v in lines)
    pc = f.get("player_counts") or {}
    profit = f.get("projected_profit") or 0
    return (f'<table class="kv">{trs}<tr class="tot"><td>Projected bottom line</td>'
            f'<td class="n {"pos" if profit >= 0 else "neg"}">{_money(profit)}</td></tr></table>'
            f'<p class="muted">Paid {_e(pc.get("paid", 0))} &middot; comp {_e(pc.get("comp", 0))} &middot; '
            f'WD {_e(pc.get("wd", 0))}. {"Verified from the ledger." if f.get("accounting_verified") else "Estimated from allocations."}</p>')


def _pay_html(p: dict) -> str:
    if not p["count"]:
        return '<p class="muted">No payouts recorded yet.</p>'
    trs = []
    for g in p["winners"]:
        what = ", ".join((i["description"] or i["category"] or "") for i in g["items"])
        state = (f'<div class="neg">unpaid {_money(g["unpaid"])}</div>' if g["unpaid"]
                 else '<div class="muted">paid</div>')
        trs.append(f'<tr><td>{_e(g["name"])}<div class="muted">{_e(what)}</div></td>'
                   f'<td class="n">{_money(g["total"])}{state}</td></tr>')
    trs = "".join(trs)
    return (f'<p>{p["count"]} payouts, {_money(p["total"])}. <b>{_money(p["unpaid"])}</b> unpaid '
            f'({p["unpaid_count"]}).</p><table class="kv">{trs}</table>')


def _hc_html(hc: dict) -> str:
    if hc.get("error"):
        return f'<p class="muted">{_e(hc["error"])}</p>'
    if not hc["rows"]:
        return f'<p class="muted">{_e(hc.get("note") or "No handicap rounds posted for this event yet.")}</p>'

    def _ix(v):
        return f"{v:.1f}N" if v is not None else "&mdash;"
    trs = []
    for r in hc["rows"]:
        c = r["change"]
        arrow = ('<span class="muted">new</span>' if r["new"] else
                 f'<span class="pos">&#9660; {abs(c):.1f}</span>' if (c or 0) < 0 else
                 f'<span class="neg">&#9650; {c:.1f}</span>' if (c or 0) > 0 else '<span class="muted">&mdash;</span>')
        diffs = ", ".join(f"{d:.1f}" for d in r["differentials"])
        trs.append(f'<tr><td>{_e(r["player_name"])}<div class="muted">diff {_e(diffs)}</div></td>'
                   f'<td class="n">{_ix(r["index_before"])} &rarr; <b>{_ix(r["index_after"])}</b><div>{arrow}</div></td></tr>')
    return (f'<p>{hc["moved"]} of {hc["posted"]} players changed.</p>'
            f'<table class="kv">{"".join(trs)}</table>')


def _pace_html(pc: dict) -> str:
    if pc.get("error"):
        return f'<p class="muted">{_e(pc["error"])}</p>'
    if not pc["rounds"]:
        return '<p class="muted">No live-scoring round for this event, so nothing was timed.</p>'
    out = []
    for r in pc["rounds"]:
        lab = f'<h3>{_e(r.get("label") or "Round")}</h3>' if len(pc["rounds"]) > 1 else ""
        if r.get("excluded"):
            out.append(lab + f'<p class="muted">Not a timed round ({_e(r["excluded"])}).</p>')
            continue
        if not r.get("groups"):
            out.append(lab + '<p class="muted">No saves from the phones on this round.</p>')
            continue
        trs = "".join(
            f'<tr><td>{_e(", ".join(g["players"]))}<div class="muted">{_e(g["start"])} &middot; '
            f'{_e(g["status_text"])}</div></td><td class="n">{_e(g["min_per_hole"])} min/hole'
            f'<div class="muted">est. {_e(g["est_round"])}</div></td></tr>' for g in r["groups"])
        slow = (f'<p class="muted">Slowest holes: {_e(", ".join(str(x) for x in r["slowest_holes"]))}.</p>'
                if r.get("slowest_holes") else "")
        out.append(lab + f'<p class="muted">Groups, fastest first.</p><table class="kv">{trs}</table>{slow}')
    return "".join(out)


def _recap_html(rc: dict, eid: int) -> str:
    if not rc.get("name"):
        return f'<p class="muted">{_e(rc.get("why"))}</p>'
    meta = []
    if rc.get("send_at"):
        meta.append(f"Goes to the players {_e(str(rc['send_at']).replace('T', ' '))}.")
    if rc.get("edited"):
        meta.append(f"Last edited{(' by ' + _e(rc['edited_by'])) if rc.get('edited_by') else ''}"
                    f"{(' at ' + _e(rc['edited_at'])) if rc.get('edited_at') else ''}.")
    meta.append("One recap covers the whole night (every event that date).")
    head = f'<p class="muted">{" ".join(meta)}</p>'
    if not rc.get("editable"):
        return head + f'<p class="muted">{_e(rc.get("why"))}</p><pre class="recap">{_e(rc.get("md"))}</pre>'
    return (head + f'<textarea id="recap-md" rows="18">{_e(rc.get("md"))}</textarea>'
            f'<button id="recap-save" data-eid="{int(eid)}">Save recap</button><div id="recap-msg"></div>')


def render_page(s: dict) -> str:
    ev, h = s["event"], s["headline"]
    eid = ev["id"]

    def _tile(k, v):
        return f'<div class="tile"><div class="k">{_e(k)}</div><div class="v">{v}</div></div>'
    tiles = (_tile("Players", _e(h["players"] if h["players"] is not None else "?"))
             + _tile("Games", _money(h["games_total"]) if h["games_total"] is not None else "&mdash;")
             + _tile("Payouts", _money(h["payouts_total"]))
             + _tile("Unpaid", _money(h["unpaid"]))
             + _tile("HCP changes", f'{h["handicap_changes"]}/{h["handicaps_posted"]}'))
    nav = "".join(f'<a href="#{k}">{lab}</a>' for k, lab in (
        ("financial", "Financial"), ("payouts", "Payouts"), ("handicaps", "Handicaps"),
        ("pace", "Pace"), ("recap", "Recap")))
    body = (_h("Financial", _fin_html(s["financial"]), "financial")
            + _h("Payouts", _pay_html(s["payouts"]), "payouts")
            + _h("Handicaps", _hc_html(s["handicaps"]), "handicaps")
            + _h("Pace of play", _pace_html(s["pace"]), "pace")
            + _h("Recap", _recap_html(s["recap"], eid), "recap"))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Event Summary · {_e(ev['name'])}</title>
<style>
body {{ margin:0; background:#F8F8F8; color:#1B1B1B; font:16px/1.45 "Helvetica Neue",Helvetica,Arial,sans-serif; }}
header {{ background:#1B1B1B; color:#fff; padding:16px; }}
header .e {{ font:bold 12px Georgia,serif; letter-spacing:2px; color:#E87C3E; }}
header h1 {{ font:bold 22px Georgia,serif; margin:4px 0 0; }}
main {{ max-width:720px; margin:0 auto; padding:16px; }}
nav.jump {{ display:flex; flex-wrap:wrap; gap:6px; margin:0 0 12px; }}
nav.jump a {{ font:bold 13px Georgia,serif; color:#1B1B1B; border:2px solid #1B1B1B; border-radius:999px;
             padding:4px 12px; text-decoration:none; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(110px,1fr)); gap:8px; margin-bottom:12px; }}
.tile {{ background:#fff; border:1px solid #E5E7EB; border-radius:8px; padding:8px 10px; }}
.tile .k {{ font-size:11px; letter-spacing:1px; text-transform:uppercase; color:#6B7280; }}
.tile .v {{ font:bold 20px Georgia,serif; }}
section {{ background:#fff; border:1px solid #E5E7EB; border-radius:10px; padding:12px 14px; margin-bottom:12px; }}
section h2 {{ font:bold 18px Georgia,serif; margin:0 0 8px; border-bottom:2px solid #E87C3E; padding-bottom:4px; }}
section h3 {{ font:bold 15px Georgia,serif; margin:10px 0 4px; }}
table.kv {{ width:100%; border-collapse:collapse; font-size:14px; }}
table.kv td {{ padding:6px 4px; border-bottom:1px solid #F3F4F6; vertical-align:top; white-space:normal; }}
table.kv td.n {{ text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }}
table.kv tr.tot td {{ font-weight:700; border-top:2px solid #1B1B1B; }}
.muted {{ color:#6B7280; font-size:13px; }}
.pos {{ color:#15803D; }} .neg {{ color:#B91C1C; }}
pre.recap {{ white-space:pre-wrap; font:13px/1.45 ui-monospace,Menlo,monospace; background:#F9FAFB;
            border-radius:6px; padding:10px; max-height:420px; overflow:auto; }}
textarea {{ width:100%; box-sizing:border-box; font:13px/1.45 ui-monospace,Menlo,monospace; border:1px solid #D1D5DB;
           border-radius:8px; padding:10px; }}
button {{ margin-top:8px; width:100%; background:#E87C3E; color:#fff; border:0; border-radius:999px; padding:12px;
         font:bold 16px Georgia,serif; cursor:pointer; }}
button[disabled] {{ opacity:.6; }}
#recap-msg {{ margin-top:8px; font-size:14px; }}
.back {{ display:block; text-align:center; border:2px solid #1B1B1B; color:#1B1B1B; text-decoration:none;
        font:bold 15px Georgia,serif; padding:10px; border-radius:999px; }}
</style></head><body>
<header><div class="e">EVENT SUMMARY</div><h1>{_e(ev['name'])}</h1>
<div style="color:#D1D5DB;font-size:14px;">{_e(ev['date'])} · {_e(ev['course'])} · {_e(ev['chapter'])}</div></header>
<main>
<div class="tiles">{tiles}</div>
<nav class="jump">{nav}</nav>
{body}
<a class="back" href="{_e(s['links']['tracker'])}">Open the event in the Tracker</a>
</main>
<script>
(function () {{
  var b = document.getElementById("recap-save");
  if (!b) return;
  b.addEventListener("click", function () {{
    var msg = document.getElementById("recap-msg");
    b.disabled = true; msg.textContent = "Saving…"; msg.style.color = "#374151";
    fetch("/api/events/" + b.dataset.eid + "/summary/recap", {{
      method: "POST", headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{md: document.getElementById("recap-md").value}})
    }}).then(function (r) {{ return r.json().then(function (d) {{ return [r.ok, d]; }}); }})
      .then(function (x) {{
        b.disabled = false;
        if (x[0] && x[1].ok) {{ msg.style.color = "#15803D"; msg.textContent = x[1].changed ? "Saved." : "No change."; }}
        else {{ msg.style.color = "#B91C1C"; msg.textContent = (x[1] && x[1].error) || "Save failed."; }}
      }}).catch(function () {{ b.disabled = false; msg.style.color = "#B91C1C"; msg.textContent = "Save failed."; }});
  }});
}})();
</script>
</body></html>"""
