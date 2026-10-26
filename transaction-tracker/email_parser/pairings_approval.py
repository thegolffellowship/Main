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
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

STATE_KEY = "pairings_approval"
DIAL = "pairings_approval_prompt"
REPROMPT_MINUTES = 60
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

def review(event_id: int, db_path=None) -> dict:
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
    try:
        from email_parser.pairings_audit import event_pairing_audit
        au = event_pairing_audit(int(event_id), db_path=db_path) or {}
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

def send_prompt(event_id: int, db_path=None, base_url: str | None = None) -> dict:
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
    html_body = (
        f"<p>Hi {_e(mgr['name'] or 'there')},</p>"
        f"<p>The pairings for <b>{_e(ev['name'])}</b> ({_e(ev['date'])}, {_e(ev['course'])}) are ready. "
        f"Please review and approve them. When you approve, the tee-times email goes to the players, "
        f"the course and you (at 7:00 PM if nobody approves); "
        f"their full Event Info email goes at {EVENT_INFO_HOUR}:00 AM on event day: "
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
        + (f'<hr style="border:0;border-top:2px solid #E87C3E"><p><b>Sample: the 7:00 AM Event Info email</b> (not tonight\'s tee-times email) '
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
    """The job: prompt each due event's manager once per sheet."""
    from email_parser.database import get_app_setting
    from email_parser.live_scoring_default import due_event_ids, ensure_live_scoring, _skip_reason
    from email_parser import database as db
    if (get_app_setting(DIAL, db_path=db_path) or "").strip().lower() in ("0", "off", "false"):
        return {"status": "off"}
    out = {}
    for eid in due_event_ids(now, db_path):
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
            if st.get("prompted_fp") == fp:
                out[eid] = {"skipped": "already prompted for this sheet"}
                continue
            last = st.get("prompted_at")
            if last:
                try:
                    if datetime.utcnow() - datetime.strptime(last, "%Y-%m-%d %H:%M:%S") < timedelta(minutes=REPROMPT_MINUTES):
                        out[eid] = {"skipped": "sheet changed; re-prompt waits an hour"}
                        continue
                except ValueError:
                    pass
            ensure_live_scoring(eid, db_path=db_path)
            out[eid] = send_prompt(eid, db_path)
        except Exception as exc:
            logger.exception("pairings approval prompt failed for %s", eid)
            out[eid] = {"error": str(exc)}
    return {"status": "ran", "events": out}


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------

EVENT_INFO_HOUR = 7       # the personal Event Info email, morning of (Kerry 10/19)


def approve_and_send(event_id: int, fingerprint: str, *, role: str | None,
                     session_chapter: str | None, approved_by: str, db_path=None,
                     send_now: bool = False) -> dict:
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
    _put(event_id, db_path, approved_fp=cur, approved_by=approved_by,
         approved_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    if not send_now:
        # Kerry 10/19: "I thought we're just sending tee times tonight and
        # then the full event info email at 7:00am". Approval signs off the
        # sheet; the personal Event Info email goes at 7:00 AM on event day
        # (event_info_morning_check).
        try:
            db.log_agent_action("pairings-approval", "approve_pairings",
                                f"{r['item_name']}: sheet {cur} approved by {approved_by}; "
                                f"Event Info emails go at {EVENT_INFO_HOUR}:00 AM",
                                db_path=db_path)
        except Exception:
            pass
        rv = review(event_id, db_path)
        # The tee-times email goes on approval (Kerry 10/19), each version
        # only with its stamp and the dial on.
        tt = None
        try:
            from email_parser.teetimes_email import _deliver
            tt = _deliver(int(event_id), db_path)
        except Exception as exc:
            logger.exception("tee-times send on approval failed for %s", event_id)
            tt = {"error": str(exc)}
        return {"status": "approved", "fingerprint": cur, "teetimes": tt,
                "sends_at": f"{EVENT_INFO_HOUR}:00 AM on the event day",
                "counts": {"approved": 1, "ready": (rv.get("counts") or {}).get("ready", 0),
                           "held": (rv.get("counts") or {}).get("held", 0)}}
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


def render_page(rv: dict) -> str:
    ev = rv["event"]
    c = rv["counts"]
    st = rv["state"]
    if rv["sent"]:
        action = (f'<div class="done">Player emails sent: <b>{rv["sent"]}</b>'
                  + (f' (approved by {_e(st.get("approved_by"))}, {_e(st.get("approved_at"))} UTC)'
                     if st.get("approved_by") else "") + ".</div>")
    elif not rv["fingerprint"]:
        action = '<div class="warn">No pairings are saved for this event yet.</div>'
    else:
        appr = (f'<div class="done">Approved by {_e(st.get("approved_by"))}. Event Info emails go to '
                f'{c.get("ready", 0)} players at {EVENT_INFO_HOUR}:00 AM.</div>'
                if st.get("approved_fp") == rv["fingerprint"] else "")
        action = appr or (f'<button id="go" data-fp="{_e(rv["fingerprint"])}">Approve pairings</button>'
                          f'<div style="color:#6B7280;font-size:13px;margin-top:6px;">Players get their full Event Info '
                          f'email at {EVENT_INFO_HOUR}:00 AM on event day ({c.get("ready", 0)} ready).</div>'
                          '<div id="msg"></div>')
    sample = rv["sample"]
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
          font:bold 16px Arial,sans-serif; cursor:pointer; }}
button[disabled] {{ opacity:.6; }}
.done {{ background:#bbf7d0; color:#15803D; border-radius:8px; padding:12px; }}
.warn {{ background:#FEF3C7; border-radius:8px; padding:12px; }}
#msg {{ margin-top:10px; }}
.sample {{ border:1px solid #E5E7EB; border-radius:8px; background:#fff; overflow:hidden; margin-top:8px; }}
</style></head><body>
<header><div class="e">APPROVE PAIRINGS</div><h1>{_e(ev['name'])}</h1>
<div style="color:#D1D5DB;font-size:14px;">{_e(ev['date'])} · {_e(ev['course'])} · {c.get('ready', 0)} ready{f", {c.get('held')} held" if c.get('held') else ""}</div></header>
<main>
{action}
<p style="margin-top:12px;"><a href="/events?event={int(ev['id'])}&amp;view=pairings" style="display:inline-block;width:100%;box-sizing:border-box;text-align:center;border:2px solid #1B1B1B;color:#1B1B1B;text-decoration:none;font-weight:bold;padding:12px;border-radius:999px;">Edit pairings</a></p>
{_flags_html(rv)}
<h3>The groups</h3>
{_groups_html(rv["groups"])}
{(SAMPLE_HEAD + '<div class="sample">' + sample["html"] + '</div>') if sample else ""}
</main>
<script>
(function () {{
  var b = document.getElementById("go"); if (!b) return;
  b.addEventListener("click", function () {{
    if (!confirm("Approve these pairings? Players get their Event Info email at 7:00 AM.")) return;
    b.disabled = true; b.textContent = "Approving\\u2026";
    fetch("/api/events/{int(ev['id'])}/approve-pairings", {{method: "POST", headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{fingerprint: b.getAttribute("data-fp")}})}})
      .then(function (r) {{ return r.json().then(function (d) {{ return [r, d]; }}); }})
      .then(function (x) {{
        var r = x[0], d = x[1], m = document.getElementById("msg");
        if (r.status === 409 && d.fingerprint) {{ m.textContent = d.error; setTimeout(function () {{ location.reload(); }}, 1500); return; }}
        if (!r.ok || d.error || d.refused) {{ m.textContent = "Not sent: " + (d.error || d.refused); b.disabled = false; b.textContent = "Try again"; return; }}
        var k = d.counts || {{}};
        m.innerHTML = d.status === "approved"
          ? '<div class="done">Approved. Event Info emails go to ' + (k.ready || 0) + ' players at ' + (d.sends_at || "7:00 AM") + '.</div>'
          : '<div class="done">Approved. Sent ' + (k.sent || 0) + ", already sent before " + (k.skipped || 0) + ", failed " + (k.failed || 0) + ".</div>";
        b.style.display = "none";
      }}).catch(function (e) {{ b.disabled = false; b.textContent = "Try again"; document.getElementById("msg").textContent = String(e); }});
  }});
}})();
</script>
</body></html>"""


# ---------------------------------------------------------------------------
# 7 PM lock / 7 AM Event Info send (Kerry 2026-10-19)
# ---------------------------------------------------------------------------
# Kerry 10/19: "I thought we're just sending tee times tonight and then the
# full event info email at 7:00am". Approval (or the 7 PM auto-approval) only
# signs off the sheet; the 7 PM tee-times email (teetimes_email) is the only
# player email the night before; the personal Event Info email goes at 7 AM.
AUTO_DIAL = "pairings_auto_send"
AUTO_HOUR = 19


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
    lock_day = (today + timedelta(days=1)).isoformat() if now.hour >= AUTO_HOUR else None
    send_day = today.isoformat() if EVENT_INFO_HOUR <= now.hour < 12 else None
    days = [d for d in (lock_day, send_day) if d]
    if not days:
        return {"status": "not yet"}
    with db._connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, item_name, event_date, status FROM events WHERE substr(event_date, 1, 10) IN ({}) "
            "AND COALESCE(status, 'active') = 'active'".format(",".join("?" * len(days))),
            days).fetchall()
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
            if str(r["event_date"])[:10] == lock_day:
                if st.get("approved_fp") == fp:
                    out[eid] = {"skipped": "a manager approved this sheet"}
                else:
                    _put(eid, db_path, approved_fp=fp, approved_by="auto 7 PM (no manager approval)",
                         approved_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                    out[eid] = {"status": "auto-approved", "sends_at": f"{EVENT_INFO_HOUR}:00 AM"}
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
                     approved_by=(st.get("approved_by") or "auto 7 AM") + " (sheet as of 7 AM)",
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
                        f"7 AM Event Info send FAILED: {name}",
                        f"<p>The 7 AM Event Info email for <b>{_e(name)}</b> did not go out.</p>"
                                  f"<p>Reason: {_e(why)}</p><p>The Tracker tries again every hour. "
                                  f"Reply here if you want it sent by hand.</p>")
        db.log_agent_action("pairings-approval", "auto_send_failed", f"{name}: {why}", db_path=db_path)
    except Exception:
        logger.exception("pairings auto-send: failure alert could not be sent")
