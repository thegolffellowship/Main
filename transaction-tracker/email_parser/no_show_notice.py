"""THE COURSE NO-SHOW NOTICE (Kerry 2026-09-30, mailbox #1021, ratified;
Pairings Spec v1.4 12.2; Event Ops NO-SHOW SCORER SEQUENCE item 3; built
10/26 for 10/27; rebuilt 10/26 on branch tb5-no-show-2).

Kerry 10/26, verbatim: "Message to course needs to update player count
totals. That message should be a TGF branded email that CCs manager and
admin." Earlier (#2370): "Yes absent mark and course notice should both
happen at 3 holes."

- A TGF-branded email in the house frame (event_day_email.frame, like
  course_update.py). Kerry 10/26 (CoS #2375): "No-show sequence with email to
  course should show original count vs updated count and the what happened
  and who dropped with a request to have them removed from our final payment
  count." So: ORIGINAL count (the players on the event's cards, the sheet the
  course got) vs UPDATED count (playing now); WHAT HAPPENED, one line a
  person (no-show / left after hole N / arrived late (from hole N), playing /
  added at the course, playing); and "Please remove <who dropped> from our
  final payment count." The same layout on every UPDATED version.
- To the course's primary TGF contact; CC its other TGF contacts
  (print_pack.course_recipients_for_event, the one reader), the chapter
  manager (after_lock._manager_cc) AND the admin (app setting
  no_show_notice_admin_cc, default kerry@thegolffellowship.com, TGF staff
  addresses only).
- When it goes: once a no-show's group has played the notice's holes (dial
  no_show_course_notice_holes, default 3; "Running late" never counts) or a
  player LEFT the course. After that, each time the SET changes (a new
  no-show, a reported no-show who arrives, a WD, a last-second add) an
  UPDATED notice goes; never twice for the same set (compared with the last
  one sent). State: app setting no_show_notice_sent:<event_id>.
- Holds on a blank (no course contact, no manager name, no course name, a
  non-staff admin CC). Every send in message_log and agent_action_log.
- Dial no_show_course_notice (on unless off). Job every 5 minutes on event
  day; the same job re-syncs the Rule 15 blinds for missing players
  (database.sync_no_show_blinds) whether or not the dial is on. Read-only
  bridge scoring-no-show-notice:<event_id>[|preview[|<staff>]].
This module never reads se_* tables; score_entry.event_no_shows is its source.
"""
from __future__ import annotations

import html as _html
import json
import logging

logger = logging.getLogger(__name__)

DIAL = "no_show_course_notice"
HOLES_DIAL = "no_show_course_notice_holes"
HOLES_DEFAULT = 3
SENT_KEY = "no_show_notice_sent:{}"
ADMIN_CC_SETTING = "no_show_notice_admin_cc"
ADMIN_CC_DEFAULT = "kerry@thegolffellowship.com"

SUBJECT = "TGF player count at {course}: {original} to {playing}"
UPDATED_PREFIX = "UPDATED: "


def _setting(key, db_path=None):
    from email_parser.database import get_app_setting
    try:
        return get_app_setting(key, db_path=db_path)
    except Exception:
        return None


def dial_on(db_path=None) -> bool:
    return (_setting(DIAL, db_path) or "").strip().lower() not in ("0", "off", "false", "no")


def notice_holes(db_path=None) -> int:
    try:
        return max(1, int(_setting(HOLES_DIAL, db_path) or HOLES_DEFAULT))
    except (TypeError, ValueError):
        return HOLES_DEFAULT


def admin_cc(db_path=None) -> list:
    from email_parser.recap_mail import _addrs
    raw = _setting(ADMIN_CC_SETTING, db_path)
    return _addrs(raw if raw not in (None, "") else ADMIN_CC_DEFAULT)


def _join(names: list) -> str:
    names = [n for n in names if n]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _sent(event_id, db_path=None) -> dict:
    raw = _setting(SENT_KEY.format(int(event_id)), db_path)
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except (TypeError, ValueError):
        return {}


def _signature(due, left, added) -> dict:
    return {"no_shows": sorted({int(x["customer_id"]) for x in due}),
            "left": sorted({int(x["customer_id"]) for x in left}),
            "added": sorted({int(x["customer_id"]) for x in added})}


def _same_as_sent(sig: dict, names: list, sent: dict) -> bool:
    if not sent:
        return False
    if "sig" in sent:
        return sent["sig"] == sig
    # a notice sent before the UPDATED rule stored names only (v2.600.0)
    return (sorted(sent.get("names") or []) == sorted(names)
            and not sig["left"] and not sig["added"])


def build(event_id: int, db_path=None) -> dict:
    """{to, cc, subject, html, names, counts, held[], due, updated} for one
    event. Sends nothing."""
    from email_parser import database as db
    from email_parser.score_entry import event_no_shows
    from email_parser.print_pack import course_recipients_for_event
    from email_parser.after_lock import _manager_cc
    from email_parser.pairings_approval import manager_for
    from email_parser.event_day_email import frame
    from email_parser.recap_mail import staff_only
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    if not r:
        return {"error": f"no event {event_id}"}
    ev = dict(r)
    n = notice_holes(db_path)
    ns = event_no_shows(int(event_id), db_path)
    rows = ns.get("no_shows") or []
    due = [x for x in rows if (x.get("group_holes_played") or 0) >= n and x.get("name")]
    left = [x for x in ns.get("left") or [] if x.get("name")]
    added = [x for x in ns.get("added") or [] if x.get("name")]
    sent = _sent(event_id, db_path)
    sig = _signature(due, left, added)
    names = sorted({x["name"] for x in due})
    reported = set((sent.get("sig") or {}).get("no_shows") or [])
    arrived = [x for x in ns.get("arrived") or [] if int(x["customer_id"]) in reported]
    on_cards = int(ns.get("registered") or 0)
    registered = on_cards - len(added)
    playing = on_cards - len(due) - len(left)
    counts = {"registered": registered, "no_shows": len(due), "left": len(left),
              "added": len(added), "playing": playing}
    rec = course_recipients_for_event(ev, db_path)
    mgr = manager_for(ev.get("chapter"), db_path) or {}
    held = []
    if not rec.get("ok"):
        held.append(rec.get("why") or "no course contact on file")
    if not (mgr.get("name") or "").strip():
        held.append("no manager name for this chapter")
    course = (ev.get("course") or "").strip()
    if not course:
        held.append("this event has no course name")
    adm = admin_cc(db_path)
    bad = staff_only(adm, lambda k: _setting(k, db_path))
    if bad:
        held.append(f"the admin CC must be a TGF staff address; refused {', '.join(bad)}")
    cc = list(rec.get("cc") or [])
    for m in [_manager_cc(ev.get("chapter"), db_path)] + adm:
        if m and m not in cc and m != rec.get("to"):
            cc.append(m)
    updated = bool(sent)
    e = _html.escape
    first = ((rec.get("to_name") or "").split(" ") or [""])[0].strip() or "there"

    # THE LAYOUT (Kerry 10/26, CoS #2375: "No-show sequence with email to
    # course should show original count vs updated count and the what
    # happened and who dropped with a request to have them removed from our
    # final payment count"). The same layout every time; UPDATED says so.
    td = 'style="padding:6px 0;border-bottom:1px solid #E5E7EB;"'
    tdr = 'align="right" style="padding:6px 0;border-bottom:1px solid #E5E7EB;"'
    table = ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
             'style="border-collapse:collapse;margin:8px 0 14px;">'
             f'<tr><td {td}>Original count</td><td {tdr}>{registered}</td></tr>'
             f'<tr><td {td}><strong>Updated count</strong></td><td {tdr}><strong>{playing}</strong></td></tr>'
             '</table>')
    what = []          # (name, what happened)
    for x in sorted(due, key=lambda x: x["name"]):
        what.append((x["name"], "no-show"))
    for x in sorted(left, key=lambda x: x["name"]):
        what.append((x["name"], f"left after hole {x['after_hole']}" if x.get("after_hole")
                     else "left before his first hole"))
    all_arrived = [x for x in ns.get("arrived") or [] if x.get("name")]
    for x in sorted(all_arrived, key=lambda x: x["name"]):
        what.append((x["name"], f"arrived late (from hole {x['joined_hole']}), playing"))
    for x in sorted(added, key=lambda x: x["name"]):
        what.append((x["name"], "added at the course, playing"))
    dropped = [x["name"] for x in sorted(due, key=lambda x: x["name"])] + \
              [x["name"] for x in sorted(left, key=lambda x: x["name"])]
    what_html = ("<p><strong>What happened</strong></p><ul>"
                 + "".join(f"<li>{e(nm)}: {e(w)}</li>" for nm, w in what) + "</ul>") if what else ""
    ask = (f"<p>Please remove {e(_join(dropped))} from our final payment count.</p>" if dropped
           else "<p>Nobody has dropped. Please keep our final payment count at the updated count.</p>")
    inner = (f"<p>Hi {e(first)},</p>"
             + (f"<p><strong>UPDATED</strong> player count for today's TGF event at {e(course)}.</p>"
                if updated else f"<p>Player count for today's TGF event at {e(course)}.</p>")
             + table + what_html + ask
             + f"<p>Thanks,<br>{e((mgr.get('name') or '').strip())}<br>The Golf Fellowship</p>")
    subject = (UPDATED_PREFIX if updated else "") + SUBJECT.format(course=course, original=registered, playing=playing)
    chapter = (ev.get("chapter") or "").upper()
    return {"event_id": int(event_id), "event": ev.get("item_name"), "event_date": ev.get("event_date"),
            "to": rec.get("to"), "cc": cc, "names": names, "left": [x["name"] for x in left],
            "added": [x["name"] for x in added], "arrived": [x["name"] for x in arrived],
            "counts": counts, "pending": [x for x in rows if x not in due],
            "holes": n, "held": held, "subject": subject, "updated": updated,
            "signature": sig, "same_as_sent": _same_as_sent(sig, names, sent),
            "has_news": bool(due or left or (sent and not _same_as_sent(sig, names, sent))),
            "html": frame(inner, chapter or "THE GOLF FELLOWSHIP",
                          ("UPDATED " if updated else "") + "Player count"),
            "sent": sent or None}


def run_event(event_id: int, confirm: bool = False, db_path=None, sender=None) -> dict:
    """Send (confirm=True) or preview one event's notice."""
    from email_parser import database as db
    b = build(event_id, db_path)
    if b.get("error"):
        return b
    out = {k: v for k, v in b.items() if k != "html"}
    if b["same_as_sent"]:
        return {**out, "status": "already sent"}
    if not b["has_news"]:
        return {**out, "status": "nothing to send",
                "why": f"no no-show whose group has played {b['holes']} holes and nobody left"}
    if b["held"]:
        return {**out, "status": "held"}
    if confirm is not True:
        return {**out, "status": "would send", "dry_run": True}
    if sender is None:
        from email_parser.event_day_email import _creds, _graph_send
        creds = _creds()
        if not creds:
            return {**out, "status": "error", "why": "Email credentials not configured on server"}
        sender = lambda to, s, h, cc: _graph_send(creds, to, s, h, cc=",".join(cc) or None)  # noqa: E731
    ok = False
    try:
        ok = bool(sender(b["to"], b["subject"], b["html"], b["cc"]))
    except Exception:
        logger.exception("no-show notice send failed for %s", event_id)
    c = b["counts"]
    summary = (f"registered {c['registered']}, no-shows {c['no_shows']}"
               f"{' (' + ', '.join(b['names']) + ')' if b['names'] else ''}, left {c['left']}, "
               f"added {c['added']}, playing {c['playing']}")
    try:
        db.log_message({"event_name": b["event"], "channel": "email", "recipient_name": "course contact",
                        "recipient_address": b["to"], "subject": b["subject"],
                        "body_preview": summary,
                        "status": "sent" if ok else "failed", "sent_by": "no-show-notice",
                        "event_id": int(event_id)}, db_path=db_path)
        db.log_agent_action("no-show-notice", "no_show_notice",
                            f"event {event_id}: {'UPDATED ' if b['updated'] else ''}"
                            f"{'sent' if ok else 'FAILED'} to {b['to']} cc {b['cc']}: {summary}",
                            db_path=db_path)
    except Exception:
        pass
    if ok:
        prev = b.get("sent") or {}
        db.set_app_setting(SENT_KEY.format(int(event_id)),
                           json.dumps({"sig": b["signature"], "names": b["names"], "to": b["to"],
                                       "counts": c,
                                       "sends": int(prev.get("sends") or (1 if prev else 0)) + 1}),
                           db_path=db_path)
    return {**out, "status": "sent" if ok else "failed"}


def check(now=None, db_path=None, sender=None) -> dict:
    """The job: every active event dated today. Re-syncs the Rule 15 blinds
    for missing players first (no manager tap), whatever the dial says."""
    from email_parser import database as db
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    with db._connect(db_path) as conn:
        ids = [int(x[0]) for x in conn.execute(
            "SELECT id FROM events WHERE substr(event_date, 1, 10) = ? "
            "AND COALESCE(status, 'active') = 'active'", (now.date().isoformat(),)).fetchall()]
    blinds = {}
    for eid in ids:
        try:
            r = db.sync_no_show_blinds(eid, db_path=db_path)
            if r.get("drawn") or r.get("removed") or r.get("updated"):
                blinds[eid] = {k: len(r.get(k) or []) for k in ("drawn", "updated", "removed")}
        except Exception:
            logger.exception("no-show blind sync failed for %s", eid)
    if not dial_on(db_path):
        return {"status": "off", "blinds": blinds}
    out = {}
    for eid in ids:
        try:
            r = run_event(eid, confirm=True, db_path=db_path, sender=sender)
            if r.get("status") not in ("nothing to send", "already sent"):
                out[eid] = r.get("status")
        except Exception as exc:
            logger.exception("no-show notice failed for %s", eid)
            out[eid] = f"error: {exc}"
    return {"status": "ran", "events": out, "blinds": blinds}


def send_preview(event_id: int, to_address: str | None = None, db_path=None) -> dict:
    """ONE sample to staff only. Nothing goes to the course."""
    from email_parser.event_day_email import _creds, _graph_send
    from email_parser.recap_mail import staff_only, _addrs
    to = _addrs(to_address) or ["kerry@thegolffellowship.com"]
    bad = staff_only(to, lambda k: _setting(k, db_path))
    if bad:
        return {"error": f"a no-show notice preview goes to TGF staff only; refused {bad}"}
    b = build(event_id, db_path)
    if b.get("error"):
        return b
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    head = (f"<p><strong>No-show notice PREVIEW</strong>. Nothing went to the course. Would go To "
            f"{_html.escape(str(b['to']))}, CC {_html.escape(', '.join(b['cc']) or 'nobody')}. "
            f"Held now: {_html.escape('; '.join(b['held']) or 'nothing')}.</p><hr>")
    ok = _graph_send(creds, ",".join(to), "PREVIEW: " + b["subject"], head + b["html"])
    return {"status": "sent" if ok else "failed", "to": to}
