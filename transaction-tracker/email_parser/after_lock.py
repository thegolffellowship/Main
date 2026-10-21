"""AFTER-LOCK CHANGES (Kerry 2026-10-20, mailbox #2139; #2168).

Kerry, verbatim (#2139): "A moved player should trigger a resend to affected
players and should send only the affected sheets to the course for reprint
with a CC to manager and me. A tee change and a games change is NOT a reason
to send new print packs to course. That can happen within the tracker, with
email notices going only to either the player (tee change) or to the affected
players (games change) with CC's to the manager."

Kerry (#2168): "No manager approval needed but cc the manager on all
changes. Push notifications to manager when we have that capability" (push
is not built; the manager is CC'd on every email instead).

How it works:
- When the Event Info emails go out (event_day_email.send_event_day_emails),
  the sheet as sent is saved: who sits in which group, on which tee, with
  which games (`after_lock_state:<event_id>`). When the Course Files go, the
  sheets as sent are saved too (`course_files_sent:<event_id>`).
- Job `after_lock_changes` (every 15 min) compares each of today's events
  against that copy until its first tee. Each change is sent once, then the
  saved copy moves to the new sheet, so nothing is ever sent twice:
    * MOVED / ADDED / REMOVED player: the moved or added player gets the
      Event Info email again ("UPDATED GROUP: " + a notice); everyone in the
      group they left and the group they joined gets it with a notice naming
      who joined or left. The course gets ONLY the sheets whose contents
      changed (never Proximity or Rules when they did not), To the course,
      CC its other contacts + the manager + Kerry.
    * TEE change: a short notice to that player.
    * GAMES change: a short notice to that player.
  The chapter manager is CC'd on every email. Dial `after_lock_auto`
  (default on; "off" stops it). The approved Event Info template is
  required, as for every event-day send.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

STATE_KEY = "after_lock_state:{}"
COURSE_KEY = "course_files_sent:{}"
DIAL = "after_lock_auto"
GROUP_PREFIX = "UPDATED GROUP: "
TEE_PREFIX = "UPDATED TEES: "
GAMES_PREFIX = "UPDATED GAMES: "


def _get(key, db_path=None):
    from email_parser import database as db
    try:
        return json.loads(db.get_app_setting(key, db_path=db_path) or "null")
    except (TypeError, ValueError):
        return None


def _set(key, val, db_path=None):
    from email_parser import database as db
    db.set_app_setting(key, json.dumps(val, sort_keys=True), db_path=db_path)


def _gkey(g: dict) -> str:
    return f"{g.get('holes')}|{g.get('group_num')}"


def sheet_state(event_id: int, db_path=None) -> dict:
    """{players: {cid: {name, group, start, cart, tee, games}}, groups:
    {gkey: {label, start}}} from the saved sheet (get_event_print_pack, the
    Starter Sheet's own source) and the games each player bought."""
    from email_parser import database as db
    from email_parser.event_day_email import _games_context
    pack = db.get_event_print_pack(int(event_id), db_path=db_path) or {}
    ev = pack.get("event") or {}
    players, groups = {}, {}
    with db._connect(db_path) as conn:
        try:
            gctx = _games_context(conn, {"id": int(event_id), "item_name": ev.get("item_name")}, db_path)
        except Exception:
            logger.exception("after-lock: games unreadable for %s", event_id)
            gctx = {"ok": False}
    for g in pack.get("groups") or []:
        gk = _gkey(g)
        groups[gk] = {"label": g.get("slot_label"), "start": g.get("start_line")}
        for p in g.get("players") or []:
            cid = p.get("customer_id")
            if not cid or p.get("blind"):
                continue
            games = sorted(k for k in (gctx.get("offered") or [])
                           if int(cid) in (gctx.get("buyers") or {}).get(k, set())) if gctx.get("ok") else None
            players[str(int(cid))] = {"name": (p.get("name") or "").strip(), "group": gk,
                                      "start": g.get("start_line"), "cart": p.get("cart_pos"),
                                      "tee": p.get("tee_choice"), "games": games}
    return {"players": players, "groups": groups,
            "tee_names": {str(t.get("band")): t.get("tee_name")
                          for t in pack.get("tee_legend") or [] if t.get("band") is not None}}


def record_sent(event_id: int, db_path=None) -> None:
    """Save the sheet as the Event Info emails carried it (the baseline)."""
    try:
        _set(STATE_KEY.format(int(event_id)), sheet_state(event_id, db_path), db_path)
    except Exception:
        logger.exception("after-lock: could not record the sent sheet for %s", event_id)


def record_course_files(event_id: int, part_shas: dict, db_path=None) -> None:
    try:
        _set(COURSE_KEY.format(int(event_id)), {"parts": part_shas or {}}, db_path)
    except Exception:
        logger.exception("after-lock: could not record the course files for %s", event_id)


def diff(before: dict, now: dict) -> dict:
    """{moved: [cid], added: [cid], removed: [cid], tee: [cid], games: [cid],
    groups: {gkey}} between two sheet states. A moved player changed group,
    start or cart; a tee change or a games change is the player's own."""
    b, n = (before or {}).get("players") or {}, (now or {}).get("players") or {}
    out = {"moved": [], "added": [], "removed": [], "tee": [], "games": [], "groups": set()}
    for cid, p in n.items():
        q = b.get(cid)
        if q is None:
            out["added"].append(cid); out["groups"].add(p["group"])
            continue
        if (q.get("group"), q.get("start"), q.get("cart")) != (p.get("group"), p.get("start"), p.get("cart")):
            out["moved"].append(cid); out["groups"].update({q.get("group"), p.get("group")})
        if (q.get("tee") or "") != (p.get("tee") or ""):
            out["tee"].append(cid)
        if q.get("games") is not None and p.get("games") is not None and q["games"] != p["games"]:
            out["games"].append(cid)
    for cid, q in b.items():
        if cid not in n:
            out["removed"].append(cid); out["groups"].add(q.get("group"))
    out["groups"].discard(None)
    return out


def _banner(title: str, body_html: str) -> str:
    from email_parser.event_day_email import _T, ORANGE, INK
    return (f'<table {_T} style="margin:0 0 14px;"><tr><td bgcolor="#FFF7ED" '
            f'style="background:#FFF7ED;border:2px solid {ORANGE};border-radius:8px;padding:12px 14px;">'
            f'<div style="font:bold 13px Georgia,serif;letter-spacing:1px;color:{ORANGE};">{title}</div>'
            f'<div style="padding-top:4px;color:{INK};">{body_html}</div></td></tr></table>')


def _e(s) -> str:
    import html
    return html.escape("" if s is None else str(s), quote=True)


def _and(names: list) -> str:
    names = [n for n in names if n]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1] if names else ""


def plan(event_id: int, db_path=None) -> dict:
    """What would go now (nothing is sent): the changes since the saved
    sheet and every email they call for."""
    before = _get(STATE_KEY.format(int(event_id)), db_path)
    if not before:
        return {"event_id": int(event_id), "skipped": "Event Info not sent yet: nothing to compare"}
    now = sheet_state(event_id, db_path)
    d = diff(before, now)
    any_change = any(d[k] for k in ("moved", "added", "removed", "tee", "games"))
    return {"event_id": int(event_id), "before": before, "now": now, "diff": d,
            "changed": any_change}


def _manager_cc(chapter, db_path=None) -> str | None:
    from email_parser.pairings_approval import manager_for
    try:
        return (manager_for(chapter, db_path) or {}).get("email") or None
    except Exception:
        return None


def run_event(event_id: int, render=None, static_dir=None, confirm: bool = False,
              db_path=None) -> dict:
    """Send what one event's changes call for. confirm=False is a dry run."""
    from email_parser import database as db
    from email_parser import event_day_email as ede
    p = plan(event_id, db_path)
    if p.get("skipped") or not p.get("changed"):
        return {**{k: v for k, v in p.items() if k not in ("before", "now")},
                "status": p.get("skipped") or "no change"}
    d, before, now = p["diff"], p["before"], p["now"]
    tpl = ede.load_template(db_path)
    appr = ede.approval_state(tpl, db_path)
    if not appr["approved"]:
        return {"event_id": int(event_id), "refused": "Event Info template not approved"}
    built = ede.build_event_day_emails(event_id, db_path=db_path)
    if built.get("error"):
        return {"event_id": int(event_id), "error": built["error"]}
    msgs = {str(m["customer_id"]): m for m in built["messages"]}
    cc = _manager_cc((built.get("event") or {}).get("chapter"), db_path)
    name = lambda cid: ((now["players"].get(cid) or before["players"].get(cid) or {}).get("name") or "")
    first = lambda cid: (name(cid).split() or [""])[0]
    sends = []   # (cid, subject, html, tag)

    # 1. MOVED / ADDED / REMOVED: the mover and both groups
    movers = set(d["moved"]) | set(d["added"])
    for gk in sorted(d["groups"]):
        joined = [c for c in movers if (now["players"].get(c) or {}).get("group") == gk]
        left = [c for c in set(d["moved"]) | set(d["removed"])
                if (before["players"].get(c) or {}).get("group") == gk
                and (now["players"].get(c) or {}).get("group") != gk]
        for cid, pl in now["players"].items():
            if pl.get("group") != gk or cid in movers or cid not in msgs:
                continue
            bits = []
            if joined:
                bits.append(f"<strong>{_e(_and([name(c) for c in joined]))}</strong> "
                            f"{'join' if len(joined) > 1 else 'joins'} your group.")
            if left:
                bits.append(f"<strong>{_e(_and([name(c) for c in left]))}</strong> "
                            f"{'are' if len(left) > 1 else 'is'} no longer in your group.")
            if not bits:
                continue
            m = msgs[cid]
            sends.append((cid, GROUP_PREFIX + m["subject"],
                          ede.with_banner(m["html"], _banner("UPDATED GROUP", " ".join(bits)
                                          + " Your start is the same. This replaces the earlier email.")),
                          "AFTER-LOCK GROUP "))
    for cid in sorted(movers):
        m = msgs.get(cid)
        if not m:
            continue
        st = (now["players"][cid].get("start") or "").replace(" | ", " · ")
        was = before["players"].get(cid) or {}
        if cid not in d["moved"]:
            body = "You're in! Your group and cart are below."
        elif was.get("group") != now["players"][cid].get("group"):
            body = (f"Your group has changed. You now start on <strong>{_e(st)}</strong>. "
                    f"This replaces the earlier email; your group and cart are below.")
        elif was.get("start") != now["players"][cid].get("start"):
            body = (f"Your start has changed. You now start on <strong>{_e(st)}</strong>. "
                    f"Your group is the same. This replaces the earlier email.")
        else:
            body = "Your cart has changed; your group and start are the same. Your cart is below."
        sends.append((cid, GROUP_PREFIX + m["subject"],
                      ede.with_banner(m["html"], _banner("UPDATED GROUP", body)), "AFTER-LOCK MOVED "))

    # 2. TEE change: that player only
    for cid in d["tee"]:
        if cid in movers or not msgs.get(cid):
            continue
        tn = now["tee_names"].get(str(now["players"][cid].get("tee"))) or now["players"][cid].get("tee")
        m = msgs[cid]
        sends.append((cid, TEE_PREFIX + m["subject"],
                      ede.with_banner(m["html"], _banner("UPDATED TEES",
                          f"You now play the <strong>{_e(tn)}</strong> tees. Your group and start are the same.")),
                      "AFTER-LOCK TEE "))

    # 3. GAMES change: that player only
    for cid in d["games"]:
        if cid in movers or not msgs.get(cid):
            continue
        g = now["players"][cid].get("games") or []
        txt = (f"You're now in the <strong>{_e(' and '.join(g))}</strong> games." if g
               else "You're no longer in the NET or GROSS games.")
        m = msgs[cid]
        sends.append((cid, GAMES_PREFIX + m["subject"],
                      ede.with_banner(m["html"], _banner("UPDATED GAMES",
                          txt + " Your group and start are the same.")), "AFTER-LOCK GAMES "))

    # one email per person: a later kind folds into the first
    seen, todo = set(), []
    for s in sends:
        if s[0] in seen:
            continue
        seen.add(s[0]); todo.append(s)

    # 4. the course: only the sheets that changed, only for a seat change
    course = {"status": "no seat change"}
    if d["moved"] or d["added"] or d["removed"]:
        prev = _get(COURSE_KEY.format(int(event_id)), db_path)
        if not prev:
            course = {"status": "Course Files not sent yet: the next send carries the new sheet"}
        elif render is None:
            course = {"status": "no renderer (dry run outside the app)"}
        else:
            course = _course_resend(event_id, render, static_dir, prev, confirm, db_path)

    out = {"event_id": int(event_id), "event": built.get("event"), "cc": cc,
           "diff": {k: (sorted(v) if isinstance(v, (set, list)) else v) for k, v in d.items()},
           "emails": [{"customer_id": int(c), "name": name(c), "subject": s} for c, s, _h, _t in todo],
           "course": course}
    if confirm is not True:
        return {**out, "dry_run": True}
    creds = ede._creds()
    if not creds:
        return {**out, "error": "Email credentials not configured on server"}
    sent, failed = [], []
    for cid, subject, html, tag in todo:
        m = msgs[cid]
        ok = False
        try:
            ok = ede._graph_send(creds, m["email"], subject, html, cc=cc)
        except Exception:
            logger.exception("after-lock send failed for %s", cid)
        (sent if ok else failed).append({"customer_id": int(cid), "name": m["name"]})
        if ok and cid in d["added"]:
            # an added player has now had his Event Info: nothing else sends it
            try:
                with db._connect(db_path) as conn:
                    ede.ensure_event_day_tables(conn)
                    conn.execute(
                        "INSERT INTO event_day_email_sends (event_id, customer_id, email, template_hash, "
                        "status, sent_at) VALUES (?, ?, ?, ?, 'sent', datetime('now')) "
                        "ON CONFLICT(event_id, customer_id) DO NOTHING",
                        (int(event_id), int(cid), m["email"], built["template_hash"]))
                    conn.commit()
            except Exception:
                logger.exception("after-lock: could not record the Event Info for %s", cid)
        try:
            db.log_message({"event_name": (built.get("event") or {}).get("name"), "channel": "email",
                            "recipient_name": m["name"], "recipient_address": m["email"],
                            "subject": subject, "body_preview": tag + m["text"][:180],
                            "status": "sent" if ok else "failed", "sent_by": "after_lock"},
                           db_path=db_path)
        except Exception:
            pass
    # the saved sheet moves to the new one once every email went; a failed
    # email keeps the old copy so the next run tries again
    if not failed:
        _set(STATE_KEY.format(int(event_id)), now, db_path)
    return {**out, "sent": sent, "failed": failed}


def _course_resend(event_id, render, static_dir, prev, confirm, db_path=None) -> dict:
    from email_parser import print_pack as pp
    built = pp.build_event_print_pack(render, int(event_id), static_dir, db_path=db_path)
    if not built or built.get("error"):
        return {"status": "error", "why": (built or {}).get("error") or "nothing to print"}
    nowp, was = built.get("part_shas") or {}, prev.get("parts") or {}
    changed = [sl for sl in pp.COURSE_FILE_PARTS if nowp.get(sl) != was.get(sl)]
    if not changed:
        return {"status": "no course sheet changed"}
    if confirm is not True:
        return {"status": "would send", "parts": changed}
    res = pp.send_course_files(built, db_path=db_path, only=tuple(changed), updated=True)
    if res.get("sent"):
        record_course_files(event_id, nowp, db_path)
    return {"status": "sent" if res.get("sent") else "failed", "parts": changed, **res}


def _first_tee_passed(ev: dict, now) -> bool:
    from email_parser import database as db
    try:
        ft = db._evlb_first_tee(ev, {}, None)
    except Exception:
        ft = None
    if not ft:
        return False
    try:
        t = datetime.strptime(f"{str(ev.get('event_date'))[:10]} {ft}", "%Y-%m-%d %I:%M %p")
    except ValueError:
        return False
    return now >= t


def check(render=None, static_dir=None, now=None, db_path=None) -> dict:
    """The job: today's events, from the Event Info send to the first tee."""
    from email_parser import database as db
    if (db.get_app_setting(DIAL, db_path=db_path) or "").strip().lower() in ("0", "off", "false"):
        return {"status": "off"}
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    with db._connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM events WHERE substr(event_date, 1, 10) = ? "
            "AND COALESCE(status, 'active') = 'active'", (now.date().isoformat(),))]
    out = {}
    for ev in rows:
        if not _get(STATE_KEY.format(int(ev["id"])), db_path):
            continue
        if _first_tee_passed(ev, now):
            out[ev["id"]] = {"status": "first tee passed"}
            continue
        try:
            out[ev["id"]] = run_event(ev["id"], render, static_dir, confirm=True, db_path=db_path)
        except Exception as exc:
            logger.exception("after-lock check failed for %s", ev["id"])
            out[ev["id"]] = {"error": str(exc)}
    return {"status": "ran", "events": out}
