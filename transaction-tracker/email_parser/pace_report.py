"""THE MANAGER PACE REPORT (Kerry 2026-10-19, #2092 §2 and #2096 §1).

Kerry: "I also want a pace report sent to the manager listing each group's
pace per hole average and total, along with a hole by hole average across all
groups to understand what the slowest holes were. I want the group pace
ordered from fastest to slowest." / "In that report, I need to quickly be able
to see who was in each group. Group numbers are meaningless to me."

One report per event round, STAFF ONLY, never to members:
  (a) groups fastest to slowest, each row led by the players' NAMES and the
      start hole or tee time (the group id never appears); average min/hole,
      total minutes over the measured holes (with the hole count), estimated
      round time, status with the reason;
  (b) hole by hole: average minutes across the counting groups, the slowest
      marked, n per hole, and a reason where a hole has no data;
  (c) one line on the method.
The numbers come from score_entry.compute_round_pace (the same measure that
fills se_group_pace / se_player_pace); this module reads no se_* table.

Recipients: the event's chapter manager with Kerry copied, staff addresses
only (recap_mail.staff_only). Sent the morning after by the job in app.py,
which does nothing unless app setting `pace_report_send` = on (default OFF,
Kerry turns it on). Once per round (message_log, sent_by='pace_report').
Bridge `scoring-pace-report:<event_id>[|preview|send]`.
"""
from __future__ import annotations

import html as _html
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

DIAL = "pace_report_send"
KERRY = "kerry@thegolffellowship.com"
SENT_BY = "pace_report"
FLAG_WORDS = {
    "few_holes": "too few holes timed",
    "long_gap": "a hole over the stoppage limit (weather or a break?)",
    "clock": "a phone clock far off the server (offline sync)",
    "entry_split": "players' saves far apart on several holes",
    "manager_entry": "card keyed by a manager afterwards",
}


def _e(s) -> str:
    return _html.escape("" if s is None else str(s))


def dial_on(db_path=None) -> bool:
    from email_parser.database import get_app_setting
    return (get_app_setting(DIAL, db_path=db_path) or "").strip().lower() in ("1", "on", "true", "yes")


def _names(customer_ids, db_path=None) -> dict:
    from email_parser import database as db
    ids = sorted({int(c) for c in customer_ids if c is not None})
    if not ids:
        return {}
    with db._connect(db_path) as conn:
        rows = conn.execute(
            "SELECT customer_id, TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) AS n "
            f"FROM customers WHERE customer_id IN ({','.join('?' * len(ids))})",
            ids).fetchall()
    return {r[0]: (r[1] or f"#{r[0]}") for r in rows}


def _mins(sec, places=1) -> str:
    return "" if sec is None else f"{sec / 60:.{places}f}"


def _hm(sec) -> str:
    if sec is None:
        return ""
    m = int(round(sec / 60))
    return f"{m // 60}:{m % 60:02d}"


def _rel(sec) -> str:
    if sec is None:
        return ""
    sign = "+" if sec > 0 else "−" if sec < 0 else "±"
    s = abs(int(sec))
    return f"{sign}{s // 60}:{s % 60:02d}/hole vs field"


def _status_text(g) -> str:
    if g["status"] == "flagged":
        return "flagged: " + "; ".join(FLAG_WORDS.get(f, f) for f in g["flags"]) + " (not counted)"
    if g["status"] == "adjusted":
        bits = []
        if g["start_moved"]:
            bits.append("first hole saved with the next")
        if g["end_moved"]:
            bits.append("second-to-last saved with the last")
        mid = g["batches"] - g["start_moved"] - g["end_moved"]
        if mid > 0:
            bits.append(f"{mid} catch-up{'s' if mid > 1 else ''} spread")
        return "adjusted: " + ("; ".join(bits) or "catch-up spread")
    return "clean"


def _start_text(g, first_hole) -> str:
    tee = (g.get("tee_time") or "").strip()
    if g.get("start_hole") not in (None, first_hole) or not tee:
        return f"Hole {g.get('start_hole')}" + (f" · {tee}" if tee else "")
    return f"Tee {tee}"


def round_report(round_id: int, db_path=None) -> dict:
    """(a), (b), (c) for one round, as data. Read-only."""
    from email_parser import score_entry as se
    rp = se.compute_round_pace(int(round_id), db_path=db_path)
    if rp.get("error"):
        return rp
    out = {"round_id": rp["round_id"], "event_id": rp["event_id"], "label": rp["label"],
           "round_date": rp["round_date"], "holes": rp["holes"], "excluded": rp["excluded"],
           "field_median_seconds": rp["field_median_seconds"], "method": se.PACE_METHOD_NOTE,
           "groups": [], "hole_table": []}
    if rp["excluded"]:
        return out
    names = _names([c for g in rp["groups"] for c in g["customer_ids"]], db_path)
    first = rp["hole_list"][0] if rp["hole_list"] else 1
    rows = []
    for g in rp["groups"]:
        spm = g["seconds_per_hole"]
        rows.append({
            "players": [names.get(c, f"#{c}") for c in g["customer_ids"]],
            "customer_ids": list(g["customer_ids"]),
            "start": _start_text(g, first),
            "min_per_hole": _mins(spm), "seconds_per_hole": spm,
            "total_minutes": int(round(g["span_seconds"] / 60)) if g["span_seconds"] is not None else None,
            "holes_timed": g["holes_timed"],
            "est_round": _hm(spm * rp["holes"]) if spm is not None else "",
            "vs_field": _rel(g["rel_seconds_per_hole"]),
            "status": g["status"], "status_text": _status_text(g),
        })
    rows.sort(key=lambda r: (r["seconds_per_hole"] is None, r["status"] == "flagged",
                             r["seconds_per_hole"] or 0))
    out["groups"] = rows
    counting = [g for g in rp["groups"] if g["status"] != "flagged"]
    avgs = {}
    for h in rp["hole_list"]:
        vals = [g["hole_seconds"][h] for g in counting if h in g["hole_seconds"]]
        avgs[h] = (sum(vals) / len(vals), len(vals)) if vals else (None, 0)
    ranked = sorted((v[0], h) for h, v in avgs.items() if v[0] is not None)
    slow = {h for _, h in ranked[-3:]} if len(ranked) > 3 else set()
    for h in rp["hole_list"]:
        a, n = avgs[h]
        why = None
        if a is None:
            ends = [g for g in counting if h in (g["first_hole"], g["last_hole"])]
            if counting and len(ends) == len(counting):
                why = "no data: every group started or finished on this hole"
            elif not counting:
                why = "no data: no group counted this round"
            else:
                why = "no data: no clean time from any counting group"
        out["hole_table"].append({"hole": h, "avg_minutes": _mins(a) if a is not None else None,
                                  "n": n, "slowest": h in slow, "why_none": why})
    out["slowest_holes"] = [h for _, h in reversed(ranked[-3:])] if ranked else []
    return out


def event_report(event_id: int, db_path=None) -> dict:
    from email_parser import database as db
    from email_parser import score_entry as se
    with db._connect(db_path) as conn:
        ev = conn.execute("SELECT id, item_name, event_date, chapter, course FROM events WHERE id = ?",
                          (int(event_id),)).fetchone()
    if not ev:
        return {"error": "no such event"}
    ev = dict(ev)
    rounds = [round_report(rid, db_path) for rid in se.event_round_ids(int(event_id), db_path=db_path)]
    return {"event": {"id": ev["id"], "name": ev["item_name"], "date": ev["event_date"],
                      "chapter": ev["chapter"], "course": ev["course"]},
            "rounds": rounds}


_TH = 'style="text-align:left;padding:6px 8px;border-bottom:2px solid #E87C3E;font-size:13px;"'
_TD = 'style="padding:6px 8px;border-bottom:1px solid #E5E7EB;font-size:13px;vertical-align:top;"'


def round_html(ev: dict, rr: dict) -> str:
    title = f"{ev.get('name') or ''}" + (f" — {rr['label']}" if rr.get("label") else "")
    where = (" · " + _e(ev.get("course"))) if ev.get("course") else ""
    head = (f'<h2 style="font-family:Georgia,serif;margin:16px 0 4px;">Pace report: {_e(title)}</h2>'
            f'<p style="color:#6B7280;margin:0 0 10px;">{_e(rr.get("round_date") or ev.get("date") or "")}'
            f'{where}. Staff only.</p>')
    if rr.get("excluded"):
        return head + f"<p>Not a timed round ({_e(rr['excluded'])}).</p>"
    if not rr["groups"]:
        return head + "<p>No saves from the phones on this round, so nothing to time.</p>"
    trs = []
    for g in rr["groups"]:
        trs.append(
            f"<tr><td {_TD}><b>{_e(', '.join(g['players']))}</b><br>"
            f'<span style="color:#6B7280;">{_e(g["start"])}</span></td>'
            f"<td {_TD}>{_e(g['min_per_hole'])}<br><span style=\"color:#6B7280;\">{_e(g['vs_field'])}</span></td>"
            f"<td {_TD}>{_e(g['total_minutes'])} min ({_e(g['holes_timed'])} holes)</td>"
            f"<td {_TD}>{_e(g['est_round'])}</td>"
            f"<td {_TD}>{_e(g['status_text'])}</td></tr>")
    groups = (f'<h3 style="margin:14px 0 6px;">Groups, fastest to slowest</h3>'
              f'<table style="border-collapse:collapse;width:100%;"><tr>'
              f"<th {_TH}>Players</th><th {_TH}>Min/hole</th><th {_TH}>Total</th>"
              f"<th {_TH}>Est. round</th><th {_TH}>Status</th></tr>{''.join(trs)}</table>")
    med = rr.get("field_median_seconds")
    hrs = []
    for h in rr["hole_table"]:
        if h["avg_minutes"] is None:
            val = f'<span style="color:#6B7280;">{_e(h["why_none"])}</span>'
        else:
            val = (f"<b>{_e(h['avg_minutes'])} — slowest</b>" if h["slowest"]
                   else _e(h["avg_minutes"]))
        hrs.append(f"<tr><td {_TD}>{_e(h['hole'])}</td><td {_TD}>{val}</td><td {_TD}>{_e(h['n'])}</td></tr>")
    holes = (f'<h3 style="margin:14px 0 6px;">Hole by hole (average minutes across counting groups)</h3>'
             f'<table style="border-collapse:collapse;"><tr><th {_TH}>Hole</th><th {_TH}>Avg min</th>'
             f"<th {_TH}>n</th></tr>{''.join(hrs)}</table>"
             + (f"<p>Slowest: {_e(', '.join(str(x) for x in rr['slowest_holes']))}.</p>"
                if rr.get("slowest_holes") else ""))
    field = (f"<p>Field median: {_e(_mins(med))} min/hole.</p>" if med is not None else "")
    return head + groups + field + holes + f'<p style="color:#6B7280;font-size:12px;">{_e(rr["method"])}</p>'


def build_email(event_id: int, round_id: int | None = None, db_path=None) -> dict:
    rep = event_report(event_id, db_path)
    if rep.get("error"):
        return rep
    rounds = [r for r in rep["rounds"] if round_id is None or r.get("round_id") == int(round_id)]
    body = "".join(round_html(rep["event"], r) for r in rounds if not r.get("error"))
    subject = f"Pace report: {rep['event']['name']}"
    return {"subject": subject, "html": body, "event": rep["event"], "rounds": rounds}


def recipients(chapter, db_path=None) -> tuple[list, list]:
    from email_parser.pairings_approval import manager_for
    mgr = manager_for(chapter, db_path) or {}
    to = [mgr["email"]] if mgr.get("email") else [KERRY]
    cc = [KERRY] if KERRY.lower() not in {a.lower() for a in to} else []
    return to, cc


def already_sent(round_id: int, db_path=None) -> bool:
    from email_parser import database as db
    with db._connect(db_path) as conn:
        return bool(conn.execute(
            "SELECT 1 FROM message_log WHERE sent_by = ? AND body_preview = ? AND status = 'sent' LIMIT 1",
            (SENT_BY, f"pace report round {int(round_id)}")).fetchone())


def send_round(event_id: int, round_id: int, db_path=None, force: bool = False) -> dict:
    """Send ONE round's report to the chapter manager(s), Kerry copied.
    Refused unless the dial is on; staff addresses only; once per round."""
    from email_parser import database as db
    from email_parser.recap_mail import staff_only
    if not dial_on(db_path):
        return {"status": "off", "why": f"app setting {DIAL} is off (Kerry turns it on)"}
    if already_sent(round_id, db_path) and not force:
        return {"status": "skipped", "why": "already sent for this round"}
    built = build_email(event_id, round_id, db_path)
    if built.get("error"):
        return built
    rr = next(iter(built["rounds"]), None)
    if not rr or rr.get("excluded") or not rr.get("groups"):
        return {"status": "skipped", "why": (rr or {}).get("excluded") or "nothing timed"}
    to, cc = recipients(built["event"].get("chapter"), db_path)

    def gs(k):
        try:
            return db.get_app_setting(k, db_path=db_path)
        except Exception:
            return None
    bad = staff_only(to + cc, gs)
    if bad:
        return {"status": "refused", "why": f"staff addresses only; refused {bad}"}
    from email_parser.event_day_email import _creds
    from email_parser import fetcher
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    ok = fetcher.send_mail_graph(tenant_id=creds[0], client_id=creds[1], client_secret=creds[2],
                                 from_address=creds[3], to_address=", ".join(to),
                                 subject=built["subject"], html_body=built["html"],
                                 cc_address=", ".join(cc) or None)
    try:
        db.log_message({"event_name": built["event"]["name"], "channel": "email",
                        "recipient_name": "chapter manager", "recipient_address": ", ".join(to + cc),
                        "subject": built["subject"], "body_preview": f"pace report round {int(round_id)}",
                        "status": "sent" if ok else "failed", "sent_by": SENT_BY}, db_path=db_path)
    except Exception:
        logger.exception("pace report: message log failed (non-fatal)")
    return {"status": "sent" if ok else "failed", "to": to, "cc": cc, "round_id": int(round_id)}


def morning_job(now=None, db_path=None) -> dict:
    """The scheduled job: rebuild the pace tables out of se_audit (always; they
    are derived), then -- only when the dial is on -- send yesterday's
    rounds' reports (Central date), once each."""
    from email_parser import score_entry as se
    from email_parser.timezone_utils import now_central
    out = {"rebuild": None, "sent": {}}
    try:
        out["rebuild"] = {"stored": se.rebuild_pace(apply=True, db_path=db_path)["stored"]}
    except Exception as exc:
        logger.exception("pace rebuild failed (non-fatal)")
        out["rebuild"] = {"error": str(exc)}
    if not dial_on(db_path):
        out["send"] = "off"
        return out
    day = ((now or now_central()) - timedelta(days=1)).strftime("%Y-%m-%d")
    for r in se.rounds_on_date(day, db_path=db_path):
        try:
            out["sent"][r["round_id"]] = send_round(r["event_id"], r["round_id"], db_path)
        except Exception as exc:
            logger.exception("pace report send failed (non-fatal)")
            out["sent"][r["round_id"]] = {"error": str(exc)}
    return out
