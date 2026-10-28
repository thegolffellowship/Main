"""MANAGER APPROVES THE PAIRINGS, THEN THE PLAYER EMAILS GO (Kerry
2026-10-13: "I'm thinking those emails go out ultimately right after the
pairings are generated. But for now they should t go out until the manager
approves the automated pairings. So the manager needs to receive a prompt to
review and approve the pairings which would then automatically send these
emails." / "Make the manager log in first.").

THE FLOW
1. The 5 PM auto-generate saves the sheet (database.auto_generate_pairings).
2. `prompt_check` (job `pairings_approval_prompt`, every 15 min from :05)
   finds events that are due (dated today, or tomorrow from 5 PM Central:
   the live-scoring window), switches Live Scoring on, and mails the
   chapter's manager ONE "Pairings ready: review and approve" email for the
   sheet as it stands. That email holds the groups, the pairings-audit flags,
   who would get no email and why, one sample player email, and a link to the
   review page.
3. The review page (/events/<id>/approve-pairings) requires a LOGIN: manager
   or admin, and a chapter manager only for his own chapter. Its one button,
   "Approve pairings & email N players", records who, when and the sheet's
   fingerprint, then runs the member send (event_day_email.
   send_event_day_emails): once per player, held players get nothing.
4. If the sheet changes after a prompt, the approval of the old one is
   refused (the page reloads to the new sheet), and a fresh prompt goes out
   (at most one an hour). Once the emails have gone, no more prompts.

The WORDING is still Kerry's to approve once (`event_day_email_approved`);
the manager's click approves that night's sheet and sends. State lives in
app setting `pairings_approval` ({event_id: {...}}); no new table.
Dial `pairings_approval_prompt`: 0/off stops the prompts.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

STATE_KEY = "pairings_approval"
DIAL = "pairings_approval_prompt"
# Kerry's TGF address for San Antonio and national events; other chapters
# use the dial's `email`, else the manager's own customer email.
# A manager's prompt goes to their TGF address, never a personal one (Kerry
# 10/19: "Robert's email for TGF is robert@thegolffellowship.com"). An email
# typed into the chapter_managers dial still wins; the customer row's own
# address is only the last resort.
DEFAULT_MANAGER_EMAIL = {"san antonio": "kerry@thegolffellowship.com",
                         "austin": "robert@thegolffellowship.com",
                         "tgf": "kerry@thegolffellowship.com"}


def _e(s) -> str:
    import html
    return html.escape(str(s or ""), quote=True)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def _load(db_path=None) -> dict:
    from email_parser.database import get_app_setting
    try:
        v = json.loads(get_app_setting(STATE_KEY, db_path=db_path) or "{}")
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}


def _save(state: dict, db_path=None) -> None:
    from email_parser.database import set_app_setting
    set_app_setting(STATE_KEY, json.dumps(state, sort_keys=True), db_path=db_path)


def event_state(event_id: int, db_path=None) -> dict:
    return dict(_load(db_path).get(str(int(event_id))) or {})


def _put(event_id: int, db_path=None, **kv) -> dict:
    st = _load(db_path)
    cur = dict(st.get(str(int(event_id))) or {})
    cur.update(kv)
    st[str(int(event_id))] = cur
    _save(st, db_path)
    return cur


def sheet_fingerprint(event_id: int, db_path=None) -> str | None:
    """A hash of the SAVED sheet (every hole set). None = nothing saved."""
    from email_parser.database import get_event_pairings
    saved = get_event_pairings(int(event_id), db_path=db_path) or {}
    norm = []
    for hk in sorted(k for k in saved if isinstance(saved.get(k), list)):
        for g in saved[hk]:
            players = [(p.get("customer_id"), p.get("name"), p.get("cart_pos"), p.get("tee_choice"))
                       for p in (g.get("players") or [])]
            if players:
                norm.append([hk, g.get("group_num"), g.get("slot_label"), players])
    if not norm:
        return None
    return hashlib.sha256(json.dumps(norm, default=str).encode()).hexdigest()[:16]


def emails_sent(event_id: int, db_path=None) -> int:
    from email_parser import database as db
    from email_parser.event_day_email import ensure_event_day_tables
    conn = db.get_connection(db_path)
    try:
        ensure_event_day_tables(conn)
        r = conn.execute("SELECT COUNT(*) FROM event_day_email_sends "
                         "WHERE event_id = ? AND status = 'sent'", (int(event_id),)).fetchone()
        return int(r[0] or 0)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Who approves
# ---------------------------------------------------------------------------

def manager_for(chapter: str | None, db_path=None) -> dict:
    """{'name', 'email', 'customer_id'} for the chapter's manager."""
    from email_parser import database as db
    cfg = db.get_chapter_managers(db_path)
    want = (chapter or "").strip().lower()
    entry = next((v for k, v in cfg.items() if k.strip().lower() == want), {}) or {}
    email = (entry.get("email") or "").strip() or DEFAULT_MANAGER_EMAIL.get(want, "")
    cid = entry.get("customer_id")
    if not email and cid:
        with db._connect(db_path) as conn:
            r = conn.execute("SELECT email FROM customer_emails WHERE customer_id = ? "
                             "ORDER BY is_primary DESC, email_id LIMIT 1", (int(cid),)).fetchone()
        email = (r[0] if r else "") or ""
    return {"name": entry.get("name") or {"austin": "Robert"}.get(want)
            or ("Kerry" if want in DEFAULT_MANAGER_EMAIL else ""),
            "email": email, "customer_id": cid}


def may_approve(role: str | None, session_chapter: str | None, event_chapter: str | None) -> str | None:
    """None when this login may approve; else the reason it may not."""
    if role == "admin":
        return None
    if role != "manager":
        return "Manager or admin login required."
    if session_chapter and (session_chapter or "").strip().lower() != (event_chapter or "").strip().lower():
        return f"This is a {event_chapter} event; your login is for {session_chapter}."
    return None


# ---------------------------------------------------------------------------
# The review: one read shared by the prompt email and the page
# ---------------------------------------------------------------------------

def review(event_id: int, db_path=None, light: bool = False) -> dict:
    """The review. light=True (the approve PAGE, CoS #2380-2 / #2393-6: it
    took 20 s on 10/26) skips the pairings audit and the Event Info build;
    the page fetches those afterwards from /approve-pairings/check."""
    from email_parser import database as db
    from email_parser.event_day_email import build_event_day_emails, approval_state, load_template
    from email_parser import perf
    # Where the page's time goes (10-12 s at host load 90 on 10/19): laps on
    # the route's own stopwatch, so the next digest names the slow section.
    _sw = perf.current()
    _lap = _sw.lap if _sw else (lambda label: 0)
    if _sw:
        _sw.mark()
    pack = db.get_event_print_pack(int(event_id), db_path=db_path)
    _lap("print_pack")
    if not pack:
        return {"error": f"event {event_id} not found"}
    ev = pack.get("event") or {}
    groups = []
    for g in pack.get("groups") or []:
        groups.append({"label": (g.get("start_line") or g.get("slot_label") or "").replace(" | ", " · "),
                       "players": [{"name": p.get("name"), "cart": ("A" if (p.get("cart_pos") or 0) in (1, 2)
                                                                     else "B" if (p.get("cart_pos") or 0) in (3, 4) else "")}
                                   for p in sorted(g.get("players") or [], key=lambda x: x.get("cart_pos") or 0)
                                   if (p.get("name") or "").strip()],
                       "blinds": [b.get("name") for b in g.get("blinds") or [] if b.get("name")]})
    flags = []
    if light:
        st = event_state(event_id, db_path)
        return {"event": {"id": int(event_id), "name": ev.get("item_name"), "date": ev.get("event_date"),
                          "course": ev.get("course"), "chapter": ev.get("chapter")},
                "fingerprint": sheet_fingerprint(event_id, db_path),
                "groups": groups, "hard_flags": [], "counts": {}, "held": [], "sample": None,
                "notes": [], "wording_approved": True, "light": True,
                "sent": emails_sent(event_id, db_path), "state": st}
    try:
        from email_parser.pairings_audit import event_pairing_audit
        # Only the hard flags are read here; the generator's own alternative (a whole
        # second pairings run, ~10 s at host load 90 on 10/26) is not shown.
        au = event_pairing_audit(int(event_id), db_path=db_path, with_alternative=False) or {}
        flags = [f for f in au.get("flags") or [] if f.get("kind") == "hard"]
    except Exception:
        logger.exception("pairings approval: audit failed (non-fatal)")
    _lap("audit")
    built = build_event_day_emails(int(event_id), db_path=db_path)
    _lap("build_emails")
    tpl = load_template(db_path)
    st = event_state(event_id, db_path)
    return {"event": {"id": int(event_id), "name": ev.get("item_name"), "date": ev.get("event_date"),
                      "course": ev.get("course"), "chapter": ev.get("chapter")},
            "fingerprint": sheet_fingerprint(event_id, db_path),
            "groups": groups, "hard_flags": flags,
            "counts": built.get("counts") or {}, "held": built.get("held") or [],
            "sample": (built.get("messages") or [None])[0],
            "notes": [n for n in (built.get("games_note"), built.get("scoring_note")) if n],
            "wording_approved": approval_state(tpl, db_path)["approved"],
            "sent": emails_sent(event_id, db_path), "state": st}


def _groups_html(groups: list) -> str:
    out = []
    for g in groups:
        names = "".join(f'<div style="padding:4px 0;border-top:1px solid #E5E7EB;">{_e(p["name"])}'
                        + (f' <span style="color:#6B7280;font-size:13px;">Cart {_e(p["cart"])}</span>' if p["cart"] else "")
                        + "</div>" for p in g["players"])
        bl = (f'<div style="color:#6B7280;font-size:13px;padding-top:4px;">Blind: {_e(", ".join(g["blinds"]))}</div>'
              if g["blinds"] else "")
        out.append(f'<div style="border:1px solid #E5E7EB;border-radius:8px;margin:0 0 10px;overflow:hidden;">'
                   f'<div style="background:#E87C3E;color:#fff;font-weight:bold;padding:6px 10px;">{_e(g["label"])}</div>'
                   f'<div style="padding:4px 10px 8px;">{names}{bl}</div></div>')
    return "".join(out)


def _flags_html(rv: dict) -> str:
    parts = []
    if rv["hard_flags"]:
        parts.append('<p><b>Pairings rules flagged:</b></p><ul>' + "".join(
            f'<li>{_e(f.get("group"))}: {_e(f.get("rule"))}. {_e(f.get("detail"))}</li>'
            for f in rv["hard_flags"]) + "</ul>")
    if rv["held"]:
        parts.append('<p><b>These players would get no email:</b></p><ul>' + "".join(
            f'<li>{_e(h.get("name"))}: {_e(h.get("reason"))}</li>' for h in rv["held"]) + "</ul>")
    for n in rv["notes"]:
        parts.append(f"<p><em>{_e(n)}</em></p>")
    if not rv["wording_approved"]:
        parts.append("<p><b>The email wording has changed and Kerry has not approved it yet, "
                     "so approving will not send until he does.</b></p>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------

def send_prompt(event_id: int, db_path=None, base_url: str | None = None, now=None) -> dict:
    from email_parser.event_day_email import _creds, _graph_send
    from email_parser import database as db
    rv = review(event_id, db_path)
    if rv.get("error"):
        return rv
    if not rv["fingerprint"]:
        return {"skipped": "no saved pairings"}
    # Never ask twice for a sheet already approved (Kerry 10/19: "Robert had
    # already approved his I believe. You didn't need to send his.").
    if (rv.get("state") or {}).get("approved_fp") == rv["fingerprint"]:
        return {"skipped": "this sheet is already approved"}
    mgr = manager_for(rv["event"]["chapter"], db_path)
    if not mgr["email"]:
        return {"skipped": f"no manager email for {rv['event']['chapter']}"}
    from email_parser.score_entry import _base_url
    url = f"{_base_url(base_url)}/events/{int(event_id)}/approve-pairings"
    c = rv["counts"]
    ev = rv["event"]
    sample = rv["sample"]
    # The real times for THIS event (Kerry 10/28: "Don't know what your
    # manager's approval email means"): a Saturday morning event's tee times
    # go tonight at the lock, its Event Info at noon Friday.
    from email_parser.timezone_utils import now_central as _nc
    with db._connect(db_path) as _c:
        _evrow = _c.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    _evd = dict(_evrow) if _evrow else {"event_date": ev.get("date")}
    _now = now or _nc()
    _lock_eve = lock_evening_word(_evd, _now, db_path)
    _ia = info_at(_evd, db_path)
    _info_t = "noon" if is_morning_event(_evd) else info_time(db_path)
    _info_words = (f"{_info_t} {day_word(_ia, _now)}" if _ia else f"{info_time()} on event day")
    if is_morning_event(_evd) and _ia:
        _info_words += ", with the Course Files"
    html_body = (
        f"<p>Hi {_e(mgr['name'] or 'there')},</p>"
        f"<p>The pairings for <b>{_e(ev['name'])}</b> ({_e(ev['date'])}, {_e(ev['course'])}) are ready. "
        f"Please review and approve them. When you approve, the tee-times email goes to the players, "
        f"the course and you (at 7:00 PM {_lock_eve} if nobody approves); "
        f"their full Event Info email goes at {_info_words}: "
        f"<b>{c.get('ready', 0)} players</b>"
        + (f", {c.get('held')} held" if c.get("held") else "") + ".</p>"
        # One tap approves (Kerry 10/19: "This should show two buttons:
        # APPROVE Pairings / EDIT Pairings ... Why go to a review page that
        # shows the same thing."). The link carries this sheet's
        # fingerprint, so a changed sheet is never approved by an old email.
        f'<p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="display:inline-table;">'
        f'<tr><td bgcolor="#E87C3E" style="background:#E87C3E;border-radius:999px;">'
        f'<a href="{_e(url)}?approve={_e(rv["fingerprint"])}" style="display:inline-block;background:#E87C3E;color:#fff;'
        f'text-decoration:none;font-weight:bold;padding:12px 20px;border-radius:999px;">'
        f"Approve pairings</a></td></tr></table>"
        f' &nbsp; <a href="{_e(_base_url(base_url))}/events?event={int(event_id)}&amp;view=pairings" style="display:inline-block;'
        f'border:2px solid #1B1B1B;color:#1B1B1B;text-decoration:none;font-weight:bold;padding:10px 18px;border-radius:999px;">'
        f"Edit pairings</a></p>"
        f"<p style=\"color:#6B7280;font-size:13px;\">You'll be asked to log in to the Tracker.</p>"
        + _flags_html(rv)
        + "<p><b>The groups:</b></p>" + _groups_html(rv["groups"])
        + (f'<hr style="border:0;border-top:2px solid #E87C3E"><p><b>Sample: the {_info_t} Event Info email</b> ({_info_words.split(", with")[0]}; not the tee-times email) '
           f"(to {_e(sample['name'])}):</p>" + sample["html"] if sample else ""))
    subject = f"Pairings ready to approve: {ev['name']}"
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    ok = _graph_send(creds, mgr["email"], subject, html_body)
    try:
        db.log_message({"event_name": ev["name"], "channel": "email", "recipient_name": mgr["name"],
                        "recipient_address": mgr["email"], "subject": subject,
                        "body_preview": f"approval prompt, sheet {rv['fingerprint']}",
                        "status": "sent" if ok else "failed", "sent_by": "pairings_approval"},
                       db_path=db_path)
    except Exception:
        pass
    if ok:
        _put(event_id, db_path, prompted_fp=rv["fingerprint"],
             prompted_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), prompted_to=mgr["email"])
    return {"status": "sent" if ok else "failed", "to": mgr["email"], "fingerprint": rv["fingerprint"],
            "counts": c, "hard_flags": len(rv["hard_flags"])}


def prompt_check(now=None, db_path=None) -> dict:
    """The job: prompt each due event's manager ONCE, right after the 5:00 PM
    pairings run. Kerry 10/26 (CoS #2329 item 1): "Just once right after 5:00p
    pairings generation is fine." A sheet changed after the prompt does not
    prompt again; the old email's Approve link refuses a stale sheet and opens
    the review page on the current one."""
    from email_parser.database import get_app_setting
    from email_parser.live_scoring_default import due_event_ids, ensure_live_scoring, _skip_reason
    from email_parser import database as db
    if (get_app_setting(DIAL, db_path=db_path) or "").strip().lower() in ("0", "off", "false"):
        return {"status": "off"}
    # Due = its lock has passed (database.event_lock_at: Kerry 10/26, a
    # weekend event locks three days before, so its prompt comes then, not
    # the evening before play), plus the old "tomorrow from 5:00 PM" set.
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    from datetime import timedelta as _td
    near = set(due_event_ids(now, db_path))
    due = list(near)
    with db._connect(db_path) as conn:
        _rows = [dict(r) for r in conn.execute(
            "SELECT * FROM events WHERE COALESCE(status, 'active') = 'active' "
            "AND substr(event_date, 1, 10) >= ? AND substr(event_date, 1, 10) <= ?",
            (now.date().isoformat(), (now.date() + _td(days=7)).isoformat()))]
    for _ev in _rows:
        _lock = db.event_lock_at(_ev, db_path)
        if _lock is not None and _lock <= now and int(_ev["id"]) not in near:
            due.append(int(_ev["id"]))
    out = {}
    for eid in due:
        try:
            with db._connect(db_path) as conn:
                ev = dict(conn.execute("SELECT id, item_name, event_date, status FROM events WHERE id = ?",
                                       (eid,)).fetchone())
            why = _skip_reason(ev, db_path)
            if why:
                out[eid] = {"skipped": why}
                continue
            if emails_sent(eid, db_path):
                out[eid] = {"skipped": "player emails already sent"}
                continue
            fp = sheet_fingerprint(eid, db_path)
            if not fp:
                out[eid] = {"skipped": "no saved pairings"}
                continue
            st = event_state(eid, db_path)
            if st.get("prompted_at") or st.get("prompted_fp"):
                out[eid] = {"skipped": "already prompted once for this event"}
                continue
            if eid in near:
                ensure_live_scoring(eid, db_path=db_path)
            out[eid] = send_prompt(eid, db_path, now=now)
        except Exception as exc:
            logger.exception("pairings approval prompt failed for %s", eid)
            out[eid] = {"error": str(exc)}
    return {"status": "ran", "events": out}


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------

EVENT_INFO_HOUR = 6       # default; the personal Event Info email, morning of
INFO_HOUR_DIAL = "event_info_hour"


def info_hour(db_path=None) -> int:
    """The hour (Central) the Event Info email goes on event day. Kerry 10/26
    (CoS #2307 item 3, #2331 B): "Move event info email to 6:00am." Dial
    event_info_hour (5-11), default 6. It was 7 (Kerry 10/19)."""
    from email_parser.database import get_app_setting
    try:
        h = int((get_app_setting(INFO_HOUR_DIAL, db_path=db_path) or "").strip())
        return h if 5 <= h <= 11 else EVENT_INFO_HOUR
    except (ValueError, TypeError):
        return EVENT_INFO_HOUR
    except Exception:
        return EVENT_INFO_HOUR


def info_time(db_path=None) -> str:
    """"6:00 AM": the Event Info time as people read it (12-hour, #2325)."""
    return f"{info_hour(db_path)}:00 AM"



# ---------------------------------------------------------------------------
# Who approved, when, and what approval sends (Kerry 10/26 via CoS #2378-#2380,
# #2393: "Ok, I'm good with that plan now.")
# ---------------------------------------------------------------------------

APPROVED_GREEN = "#2f7d4a"


def approver_name(role: str | None, session_chapter: str | None, db_path=None) -> str:
    """The person's name for "APPROVED · Kerry · 5:14 PM Mon"."""
    if (role or "").lower() == "admin":
        return "Kerry"
    m = manager_for(session_chapter, db_path) if session_chapter else {}
    n = (m.get("name") or "").strip()
    return n.split()[0] if n else (role or "Manager").title()


def _at12(utc_stamp) -> str:
    """'2026-10-26 22:14:39' (UTC) -> '5:14 PM Mon' (Central)."""
    from email_parser.timezone_utils import to_central, clock12
    dt = to_central(utc_stamp)
    return f"{clock12(dt)} {dt.strftime('%a')}" if dt else ""


def approval_status(event_id: int, db_path=None, fingerprint: str | None = None) -> dict:
    """{approval: none | approved | changed, approved_name, approved_at12, label}.
    changed = approved, then the sheet was edited (CoS #2393-5)."""
    st = event_state(event_id, db_path)
    cur = fingerprint if fingerprint is not None else sheet_fingerprint(event_id, db_path)
    fp = st.get("approved_fp")
    name = st.get("approved_name") or ("Kerry" if (st.get("approved_by") or "").startswith("admin")
                                       else "auto 7 PM" if (st.get("approved_by") or "").startswith("auto")
                                       else (st.get("approved_by") or "").split(" (")[0].title())
    at = _at12(st.get("approved_at")) if st.get("approved_at") else ""
    state = "none" if not fp else ("approved" if fp == cur else "changed")
    return {"approval": state, "approved_name": name if fp else None, "approved_at12": at if fp else None,
            "label": (f"APPROVED · {name} · {at}" if state == "approved"
                      else "Changed since approval · Approve again" if state == "changed" else "Approve")}


_COURSE_SUFFIX = re.compile(r"\s+(golf club|golf course|country club|golf & country club|gc)\b.*$", re.I)


def _course_short(course: str) -> str:
    return _COURSE_SUFFIX.sub("", (course or "").strip()) or (course or "").strip()


def _day_name(d) -> str:
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%A")
    except ValueError:
        return ""


def send_plan(event_id: int, db_path=None, after: bool = False) -> dict:
    """What approval sends, as the manager reads it under the button and in
    the confirm pop-up (wording stamped by Kerry, CoS #2393). Live counts:
    players, the course contact by name, open spots and invitees. after=True
    is the wording once approved ("are going out now")."""
    from email_parser import database as db
    from email_parser import teetimes_email as tt
    from email_parser.print_pack import course_recipients_for_event
    from email_parser.course_files_noon import send_day
    from datetime import timedelta as _td
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    if not r:
        return {"error": f"no event {event_id}"}
    ev = dict(r)
    c = tt.plan_counts(int(event_id), db_path)
    n, spots, inv = c["players"], c["open_spots"], c["invitees"]
    course = (ev.get("course") or "").strip()
    short = _course_short(course)
    rec = course_recipients_for_event(ev, db_path)
    has_contact = bool(rec.get("ok"))
    if has_contact:
        staff = rec.get("staff") or []
        prim = next((x.get("name") for x in staff if x.get("is_primary")), None) or rec.get("to_name") or ""
        others = [x.get("name") for x in staff if not x.get("is_primary") and x.get("name")]
        who = prim + (f", CC {', '.join(others)}" if others else "")
        course_clause = f", to {course} ({who})" if who else f", to {course}"
    else:
        course_clause = ""
    # The tee-times email only goes the evening before play (teetimes_email.
    # send_window_ok): approving a sheet days ahead (a weekend event locks on
    # Wednesday) sends it at 5:00 PM that evening, not now.
    from email_parser.timezone_utils import today_central
    try:
        _evd = datetime.strptime(str(ev["event_date"])[:10], "%Y-%m-%d").date()
    except ValueError:
        _evd = None
    # The tee-times email goes on the LOCK evening (Kerry 10/28: "moved to
    # the night of the lock and pairings generation...same as Tuesday
    # events"): a Saturday event's lock is Wednesday 5:00 PM.
    _lk = db.event_lock_at(ev, db_path)
    eve = _lk.date() if _lk is not None else (_evd - _td(days=1) if _evd else None)
    now_ok = eve is None or today_central() >= eve
    eve_name = eve.strftime("%A") if eve else ""
    from email_parser.timezone_utils import clock12 as _c12
    lock_clock = _c12(_lk) if _lk is not None else "5:00 PM"
    # Tee times go once per person per event (teetimes_email._sent). A sheet
    # re-approved after they went sends nothing new, so the line says so
    # (Kerry 10/26, Silverhorn re-approved 9:59 PM, nothing went); the
    # 6:00 AM Event Info carries the updated groups.
    _went = sorted(v for k, v in tt._sent(int(event_id), db_path).items() if str(k).startswith("player:"))
    already = _at12(_went[0]) if _went else ""
    if already:
        s1 = (f"Tee times already went at {already}." + (" They are not sent again." if after
              else " Approving again does not send them again."))
    elif now_ok:
        verb = "Tee times are going out now" if after else "Approving sends tee times now"
        s1 = f"{verb} to all {n} players{course_clause} and to you."
    else:
        verb = "Tee times go" if after else "Approving sends tee times"
        s1 = f"{verb} to all {n} players{course_clause} and to you at {lock_clock} {eve_name}."
    s_open = (f"Invitees who haven't registered get the open-spots email ({spots} spot{'s' if spots != 1 else ''} open)."
              if inv > 0 and spots > 0 and not already else "")
    morning = is_morning_event(ev)
    if morning:
        try:
            dname = (datetime.strptime(str(ev["event_date"])[:10], "%Y-%m-%d") - _td(days=1)).strftime("%A")
        except ValueError:
            dname = ""
        s_info = (f"Players get their full Event Info at noon {dname}"
                  + (f", and {short} gets the Course Files at the same time." if has_contact else "."))
        s_files = ""
    else:
        s_info = (f"Players get their full Event Info{' with the updated groups' if already else ''}"
                  f" at {info_time(db_path)} {_day_name(ev.get('event_date'))}.")
        s_files = f"{short} gets the Course Files at noon {_day_name(send_day(ev))}." if has_contact else ""
    s_nocontact = "" if has_contact else "No course contact on file: the course gets nothing until one is added."
    line = " ".join(x for x in (s1, s_nocontact, s_open, s_info, s_files) if x)
    if already:
        confirm = (f"Approve these pairings? Tee times already went at {already} and are not sent again. "
                   + s_info)
    else:
        confirm = (f"Approve these pairings? Tee times go {'now' if now_ok else 'at ' + lock_clock + ' ' + eve_name} to {n} players"
                   + (f", {course} and you" if has_contact else " and you")
                   + (f", and the open-spots email to {inv} invitee{'s' if inv != 1 else ''}." if inv > 0 and spots > 0 else "."))
    auto_line = ("If you don't approve, this all goes automatically at 7:00 PM."
                 if now_ok else f"If you don't approve, this all goes automatically at 7:00 PM {eve_name}.")
    if morning:
        # A morning event's Event Info and Course Files keep their own time
        # (noon the day before); only the tee times go at 7:00 PM.
        auto_line = ("If you don't approve, the tee times go automatically at 7:00 PM"
                     + ("" if now_ok else f" {eve_name}") + f"; the Event Info still goes at noon {dname}.")
    if already:
        auto_line = "Nothing else goes tonight."
    return {"line": line, "auto_line": auto_line,
            "confirm": confirm, "players": n, "open_spots": spots, "invitees": inv,
            "course": course, "course_contact": has_contact, "morning": morning,
            "teetimes_sent_at12": already}

def approve_and_send(event_id: int, fingerprint: str, *, role: str | None,
                     session_chapter: str | None, approved_by: str, db_path=None,
                     send_now: bool = False, background: bool = False) -> dict:
    from email_parser import database as db
    from email_parser.event_day_email import send_event_day_emails
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT chapter, item_name FROM events WHERE id = ?", (int(event_id),)).fetchone()
    if not r:
        return {"error": "event not found", "code": 404}
    why = may_approve(role, session_chapter, r["chapter"])
    if why:
        return {"error": why, "code": 403}
    cur = sheet_fingerprint(event_id, db_path)
    if not cur:
        return {"error": "No pairings are saved for this event.", "code": 409}
    if (fingerprint or "") != cur:
        return {"error": "The pairings changed since this page was opened. Reload to review the new sheet.",
                "code": 409, "fingerprint": cur}
    # A second tap on an approved sheet does nothing (CoS #2393-4).
    if event_state(event_id, db_path).get("approved_fp") == cur and not send_now:
        return {"status": "already approved", "fingerprint": cur, **approval_status(event_id, db_path, cur)}
    _put(event_id, db_path, approved_fp=cur, approved_by=approved_by,
         approved_name=approver_name(role, session_chapter, db_path),
         approved_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    if not send_now:
        # Kerry 10/19: "I thought we're just sending tee times tonight and
        # then the full event info email at 7:00am". Approval signs off the
        # sheet; the personal Event Info email goes on event day.
        try:
            db.log_agent_action("pairings-approval", "approve_pairings",
                                f"{r['item_name']}: sheet {cur} approved by {approved_by}; "
                                f"Event Info emails go at {info_time()}",
                                db_path=db_path)
        except Exception:
            pass
        # The tee-times email goes on approval (Kerry 10/19), IN THE
        # BACKGROUND (CoS #2380-1 / #2393-4: the page sat on "Approving..."
        # while it built and sent): the answer comes back at once. The
        # per-message claim (teetimes_email._claim) keeps this and the job
        # from ever both sending.
        def _bg():
            try:
                from email_parser.teetimes_email import _deliver
                _deliver(int(event_id), db_path)
            except Exception:
                logger.exception("tee-times send on approval failed for %s", event_id)
        if background:
            import threading
            threading.Thread(target=_bg, name=f"teetimes-approve-{event_id}", daemon=True).start()
            tt = {"status": "sending in the background"}
        else:
            _bg()
            tt = {"status": "sent in the foreground"}
        return {"status": "approved", "fingerprint": cur, "teetimes": tt,
                "sends_at": (lambda _t: _t if _t.startswith("noon") else f"{_t} on the event day")(info_time_for_id(event_id, db_path)),
                **approval_status(event_id, db_path, cur),
                "plan": send_plan(event_id, db_path, after=True)}
    try:
        db.log_agent_action("pairings-approval", "approve_pairings",
                            f"{r['item_name']}: sheet {cur} approved by {approved_by}; emailing players",
                            db_path=db_path)
    except Exception:
        pass
    res = send_event_day_emails(int(event_id), confirm=True, db_path=db_path)
    if res.get("counts"):
        _put(event_id, db_path, sent_counts=res["counts"])
    return res


# ---------------------------------------------------------------------------
# The page (manager login required by the route)
# ---------------------------------------------------------------------------

SAMPLE_HEAD = ('<h3>Sample: the 7:00 AM Event Info email each player gets on event day</h3>'
               '<p style="color:#6B7280;font-size:13px;">Not tonight\'s tee-times email; this is the '
               'full email that follows in the morning.</p>')


def render_page(rv: dict, db_path=None) -> str:
    """The approve page (CoS #2393, Kerry: "Ok, I'm good with that plan now."):
    the line under the button says what goes where and when, the confirm
    names the live counts, approval answers at once (the sending runs in the
    background) and turns into a green APPROVED · who · time bar. The audit
    and the Event Info sample load after the page (/approve-pairings/check)."""
    ev = rv["event"]
    eid = int(ev["id"])
    stt = approval_status(eid, db_path, rv["fingerprint"]) if rv["fingerprint"] else {"approval": "none"}
    approved = stt["approval"] == "approved"
    plan = send_plan(eid, db_path, after=approved) if rv["fingerprint"] else {}
    if not rv["fingerprint"]:
        action = '<div class="warn">No pairings are saved for this event yet.</div>'
    else:
        bar = (f'<div id="bar" class="ok">{_e(stt["label"])}</div>' if approved else
               (f'<div class="amber">Changed since approval: {_e(stt["approved_name"] or "")} approved an earlier '
                f'sheet at {_e(stt["approved_at12"] or "")}.</div>' if stt["approval"] == "changed" else ""))
        btn = ("" if approved else
               f'<button id="go" data-fp="{_e(rv["fingerprint"])}" data-confirm="{_e(plan.get("confirm", ""))}">'
               f'{"Approve again" if stt["approval"] == "changed" else "Approve pairings"}</button>')
        action = (bar + btn
                  + f'<div id="line" class="line">{_e(plan.get("line", ""))}</div>'
                  + ("" if approved else f'<div class="line sub">{_e(plan.get("auto_line", ""))}</div>')
                  + '<div id="msg"></div>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Approve Pairings · {_e(ev['name'])}</title>
<style>
body {{ margin:0; background:#F8F8F8; color:#1B1B1B; font:16px/1.45 "Helvetica Neue",Helvetica,Arial,sans-serif; }}
header {{ background:#1B1B1B; color:#fff; padding:16px; }}
header .e {{ font:bold 12px Georgia,serif; letter-spacing:2px; color:#E87C3E; }}
header h1 {{ font:bold 22px Georgia,serif; margin:4px 0 0; }}
main {{ max-width:640px; margin:0 auto; padding:16px; }}
button {{ width:100%; background:#E87C3E; color:#fff; border:0; border-radius:999px; padding:14px;
          font:bold 16px Georgia,serif; cursor:pointer; }}
button[disabled] {{ opacity:.6; }}
.ok {{ background:{APPROVED_GREEN}; color:#fff; border-radius:999px; padding:14px; text-align:center;
       font:bold 16px Georgia,serif; letter-spacing:.5px; }}
.amber {{ background:#FEF3C7; color:#92400E; border-radius:8px; padding:10px 12px; margin-bottom:10px; }}
.line {{ color:#374151; font-size:14px; margin-top:8px; }}
.line.sub {{ color:#6B7280; font-size:13px; margin-top:4px; }}
.warn {{ background:#FEF3C7; border-radius:8px; padding:12px; }}
#msg {{ margin-top:10px; color:#B91C1C; }}
.sample {{ border:1px solid #E5E7EB; border-radius:8px; background:#fff; overflow:hidden; margin-top:8px; }}
</style></head><body>
<header><div class="e">APPROVE PAIRINGS</div><h1>{_e(ev['name'])}</h1>
<div style="color:#D1D5DB;font-size:14px;">{_e(_day_name(ev['date']))}, {_e(_date_short(ev['date']))} · {_e(ev['course'])}</div></header>
<main>
{action}
<p style="margin-top:12px;"><a href="/events?event={eid}&amp;view=pairings" style="display:inline-block;width:100%;box-sizing:border-box;text-align:center;border:2px solid #1B1B1B;color:#1B1B1B;text-decoration:none;font-weight:bold;padding:12px;border-radius:999px;font-family:Georgia,serif;">Edit pairings</a></p>
<div id="checks" style="color:#6B7280;font-size:13px;">Checking the rules and the emails…</div>
<h3>The groups</h3>
{_groups_html(rv["groups"])}
<div id="sample"></div>
</main>
<script>
(function () {{
  fetch("/events/{eid}/approve-pairings/check").then(function (r) {{ return r.json(); }}).then(function (d) {{
    document.getElementById("checks").innerHTML = d.flags_html || "";
    if (d.sample_html) document.getElementById("sample").innerHTML = d.sample_html;
  }}).catch(function () {{ document.getElementById("checks").textContent = ""; }});
  var b = document.getElementById("go"); if (!b) return;
  b.addEventListener("click", function () {{
    if (b.disabled) return;
    if (!confirm(b.getAttribute("data-confirm"))) return;
    b.disabled = true; b.textContent = "Approving\u2026";
    fetch("/api/events/{eid}/approve-pairings", {{method: "POST", headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{fingerprint: b.getAttribute("data-fp")}})}})
      .then(function (r) {{ return r.json().then(function (d) {{ return [r, d]; }}); }})
      .then(function (x) {{
        var r = x[0], d = x[1], m = document.getElementById("msg");
        if (r.status === 409 && d.fingerprint) {{ m.textContent = d.error; setTimeout(function () {{ location.reload(); }}, 1500); return; }}
        if (!r.ok || d.error || d.refused) {{ m.textContent = "Not approved: " + (d.error || d.refused); b.disabled = false; b.textContent = "Try again"; return; }}
        var bar = document.createElement("div"); bar.id = "bar"; bar.className = "ok"; bar.textContent = d.label || "APPROVED";
        b.parentNode.replaceChild(bar, b);
        var ln = document.getElementById("line"); if (ln && d.plan && d.plan.line) ln.textContent = d.plan.line;
        var sub = document.querySelector(".line.sub"); if (sub) sub.remove();
      }}).catch(function (e) {{ b.disabled = false; b.textContent = "Try again"; document.getElementById("msg").textContent = "No answer from the Tracker. Try again."; }});
  }});
}})();
</script>
</body></html>"""


def _date_short(d) -> str:
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%B %-d")
    except ValueError:
        return str(d or "")


def check_parts(event_id: int, db_path=None) -> dict:
    """The slow half of the page, fetched after it loads: rule flags, who
    gets no Event Info email, and the sample."""
    rv = review(event_id, db_path)
    if rv.get("error"):
        return rv
    sample = rv.get("sample")
    head = SAMPLE_HEAD.replace('7:00 AM', info_time(db_path))
    try:
        from email_parser import database as db
        with db._connect(db_path) as conn:
            _r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
        if _r and is_morning_event(dict(_r)):
            # a morning event's Event Info goes at noon the day before (Kerry 10/26)
            head = (SAMPLE_HEAD.replace("the 7:00 AM Event Info email each player gets on event day",
                                        "the Event Info email each player gets at noon the day before")
                    .replace("the full email that follows in the morning",
                             "the full email that follows at noon the day before"))
    except Exception:
        pass
    return {"flags_html": _flags_html(rv),
            "sample_html": ((head + '<div class="sample">' + sample["html"] + '</div>') if sample else "")}


# ---------------------------------------------------------------------------
# 7 PM lock / 7 AM Event Info send (Kerry 2026-10-19)
# ---------------------------------------------------------------------------
# Kerry 10/19: "I thought we're just sending tee times tonight and then the
# full event info email at 7:00am". Approval (or the 7 PM auto-approval) only
# signs off the sheet; the 7 PM tee-times email (teetimes_email) is the only
# player email the night before; the personal Event Info email goes at 7 AM.
AUTO_DIAL = "pairings_auto_send"
AUTO_HOUR = 19


MORNING_BEFORE_HOUR = 13


def is_morning_event(ev: dict) -> bool:
    """First tee before 1:00 PM: Event Info and Course Files go at noon the
    day before (course_files_noon.send_day is the same test)."""
    from email_parser.after_lock import _first_tee
    ft = _first_tee(ev)
    return ft is not None and ft.hour < MORNING_BEFORE_HOUR


def info_time_for(ev: dict, db_path=None) -> str:
    """When this event's Event Info goes, as people read it."""
    return "noon the day before" if is_morning_event(ev) else info_time(db_path)


def info_time_for_id(event_id, db_path=None) -> str:
    from email_parser import database as db
    try:
        with db._connect(db_path) as conn:
            r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
        return info_time_for(dict(r), db_path) if r else info_time(db_path)
    except Exception:
        return info_time(db_path)


def info_at(ev: dict, db_path=None):
    """When this event's Event Info goes, as a naive Central datetime: noon
    the day before for a morning event, else the event_info_hour on event day.
    None without a readable date."""
    try:
        d = datetime.strptime(str(ev.get("event_date") or "")[:10], "%Y-%m-%d")
    except ValueError:
        return None
    if is_morning_event(ev):
        return (d - timedelta(days=1)).replace(hour=12)
    return d.replace(hour=info_hour(db_path))


def day_word(d, ref) -> str:
    """'today' / 'tomorrow' / the day name ('Friday'), seen from `ref` (a
    date or datetime): how a date reads in an email sent on `ref`'s day."""
    d = d.date() if isinstance(d, datetime) else d
    ref = ref.date() if isinstance(ref, datetime) else ref
    n = (d - ref).days
    if n == 0:
        return "today"
    if n == 1:
        return "tomorrow"
    if 1 < n < 7:
        return d.strftime("%A")
    return d.strftime("%A, %B %-d")


def lock_evening_word(ev: dict, ref, db_path=None) -> str:
    """'tonight' when the lock is on `ref`'s day, else 'Wednesday evening'."""
    from email_parser import database as db
    lk = db.event_lock_at(ev, db_path)
    if lk is None:
        return "the evening of the lock"
    w = day_word(lk, ref)
    return "tonight" if w == "today" else ("tomorrow evening" if w == "tomorrow" else f"{w} evening")


def auto_send_check(now=None, db_path=None) -> dict:
    """Two moments (Kerry 10/19: "just sending tee times tonight and then the
    full event info email at 7:00am"):
      * 7 PM the day before: a sheet no manager approved is approved as it
        stands ("auto 7 PM"). NO player email goes.
      * 7:00 AM on event day (until noon): every event with saved pairings
        whose players have had no Event Info email gets it now, approved or
        not. A failure emails Kerry and retries hourly."""
    from email_parser.database import get_app_setting
    from email_parser.live_scoring_default import _skip_reason
    from email_parser.event_day_email import send_event_day_emails
    from email_parser import database as db
    if (get_app_setting(AUTO_DIAL, db_path=db_path) or "").strip().lower() in ("0", "off", "false"):
        return {"status": "off"}
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    today = now.date()
    lock_day = now.hour >= AUTO_HOUR
    send_day = today.isoformat() if info_hour(db_path) <= now.hour < 12 else None
    # A MORNING event (first tee before 1:00 PM: the noon Course Files job's
    # own test, course_files_noon.send_day) gets its Event Info at NOON THE
    # DAY BEFORE, with the Course Files (Kerry 10/26, CoS #2355: "18 hole
    # event info like Fall Champ needs to go out one day prior at noon, same
    # time as course files."). It has no separate 7 PM auto-approve: the noon
    # send approves the sheet as it stands.
    # THE 7 PM AUTO-APPROVE IS ON THE LOCK NIGHT for every event (Kerry
    # 10/28: the tee-times email goes "the night of the lock and pairings
    # generation...same as Tuesday events"): a Saturday event locks Wednesday
    # 5 PM, so its sheet is signed off Wednesday 7 PM with its tee times.
    from email_parser.course_files_noon import send_day as _cf_day
    from email_parser.after_lock import _first_tee
    with db._connect(db_path) as conn:
        cand = [dict(r) for r in conn.execute(
            "SELECT * FROM events WHERE substr(event_date, 1, 10) >= ? AND substr(event_date, 1, 10) <= ? "
            "AND COALESCE(status, 'active') = 'active'",
            (today.isoformat(), (today + timedelta(days=7)).isoformat())).fetchall()]
    rows = []
    for r in cand:
        d = str(r["event_date"])[:10]
        if is_morning_event(r):
            ft = _first_tee(r)
            if _cf_day(r) == today.isoformat() and now.hour >= 12:
                rows.append({**r, "_mode": "send"})
                continue
            if d == today.isoformat() and (ft is None or now < ft):
                rows.append({**r, "_mode": "send"})        # a failed noon send keeps retrying
                continue
        elif d == send_day:
            rows.append({**r, "_mode": "send"})
            continue
        _lk = db.event_lock_at(r, db_path)
        if lock_day and _lk is not None and _lk.date() == today and d > today.isoformat():
            rows.append({**r, "_mode": "lock"})
    if not rows:
        return {"status": "not yet"}
    out = {}
    for r in rows:
        eid = int(r["id"])
        try:
            why = _skip_reason(dict(r), db_path)
            if why:
                out[eid] = {"skipped": why}
                continue
            if emails_sent(eid, db_path):
                out[eid] = {"skipped": "Event Info emails already sent"}
                continue
            fp = sheet_fingerprint(eid, db_path)
            if not fp:
                out[eid] = {"skipped": "no saved pairings"}
                continue
            st = event_state(eid, db_path)
            if r["_mode"] == "lock":
                if st.get("approved_fp") == fp:
                    out[eid] = {"skipped": "a manager approved this sheet"}
                else:
                    _put(eid, db_path, approved_fp=fp, approved_by="auto 7 PM (no manager approval)",
                         approved_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                    out[eid] = {"status": "auto-approved", "sends_at": info_time_for(r, db_path)}
                continue
            # event day, 7 AM to noon: the Event Info send
            last_fail = st.get("auto_failed_at")
            if last_fail:
                try:
                    if datetime.utcnow() - datetime.strptime(last_fail, "%Y-%m-%d %H:%M:%S") < timedelta(minutes=60):
                        out[eid] = {"skipped": "last try failed; retrying hourly"}
                        continue
                except ValueError:
                    pass
            if st.get("approved_fp") != fp:
                _put(eid, db_path, approved_fp=fp,
                     approved_by=(st.get("approved_by") or f"auto {info_time(db_path)}") + f" (sheet as of {info_time(db_path)})",
                     approved_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            res = send_event_day_emails(eid, confirm=True, db_path=db_path)
            if res.get("counts"):
                _put(eid, db_path, sent_counts=res["counts"])
            if res.get("counts") and not res.get("error") and not res.get("refused") and emails_sent(eid, db_path):
                _put(eid, db_path, auto_sent_fp=fp, auto_failed_at=None,
                     auto_sent_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            else:
                raise RuntimeError(res.get("error") or res.get("refused") or "no player email was sent")
            out[eid] = res
        except Exception as exc:
            logger.exception("Event Info send failed for %s", eid)
            out[eid] = {"error": str(exc)}
            _put(eid, db_path, auto_failed_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            _alert_failure(eid, str(exc), db_path)
    return {"status": "ran", "events": out}


def _alert_failure(event_id: int, why: str, db_path=None) -> None:
    """Email Kerry that the 7 PM send failed; it retries hourly."""
    try:
        from email_parser.event_day_email import _creds, _graph_send
        from email_parser import database as db
        with db._connect(db_path) as conn:
            r = conn.execute("SELECT item_name FROM events WHERE id = ?", (int(event_id),)).fetchone()
        name = r["item_name"] if r else f"event {event_id}"
        creds = _creds()
        if creds:
            _graph_send(creds, DEFAULT_MANAGER_EMAIL["tgf"],
                        f"{info_time(db_path)} Event Info send FAILED: {name}",
                        f"<p>The {info_time(db_path)} Event Info email for <b>{_e(name)}</b> did not go out.</p>"
                                  f"<p>Reason: {_e(why)}</p><p>The Tracker tries again every hour. "
                                  f"Reply here if you want it sent by hand.</p>")
        db.log_agent_action("pairings-approval", "auto_send_failed", f"{name}: {why}", db_path=db_path)
    except Exception:
        logger.exception("pairings auto-send: failure alert could not be sent")
