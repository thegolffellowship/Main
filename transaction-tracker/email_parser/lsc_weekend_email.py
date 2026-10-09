"""THE LONE STAR CUP WEEKEND EMAIL (Kerry 2026-10-09: "It would be nice to be
able to send emails today with a full directive for the weekend, everyone's
individual times and pairings customized. Not just one round like today's
practice round but the full overview" ... "Add these scorer notes in that
email, also include on the event info in tracker").

One message per Cup player: their Friday practice tee time (when they play
it), each Cup session's match number, tee time, partner and opponents (and,
on Sunday, the other match in their group), their group's scorecard link
per round, how each format works, the scorer notes, and the links to the
live board and Event Info.

Where each fact comes from, never a second derivation:
- the matches, tee times and session dates: the `lsc_matches` dial (THE DRAW);
  the weekend match number counts through the dial's sessions, as the
  board and the starter sheets number them;
- the Friday practice group: the practice event's saved sheet
  (`get_event_print_pack`), found through the Cup's `friday` add-on;
- the scorecard links: `score_entry.cup_sign_sheets` (the cart signs' own);
- names and email: `customers` / `resolve_player_email`, by customer_id.

SENDS. `preview` mails staff only. `send` refuses unless `confirm` is set
AND `approval` equals the hash of exactly the batch the preview showed
(Kerry's word on THAT content), and records each customer in the app
setting `lsc_weekend_email_sent` before the Graph call, so nobody is mailed
twice. Nothing here sends on its own.
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import logging

logger = logging.getLogger(__name__)

SENT_KEY = "lsc_weekend_email_sent"
BOARD_URL = "https://tgf-tracker.up.railway.app/member/lonestarcup"
INFO_URL = "https://tgf-tracker.up.railway.app/member/lonestarcup/info"

# THE SCORER NOTES: one copy, read by this email and by the EVENT INFO page's
# Scoring section (templates/_lsc_info_body.html).
SCORER_NOTES = [
    "One phone per group keeps score. The scorer scans the QR code on the cart sign "
    "(or the scorecard) and taps SCORE THIS GROUP. Everyone else taps FOLLOW to watch "
    "the leaderboard; following claims nothing.",
    "Enter each player's GROSS score. The app applies everyone's strokes for the match.",
    "Picked up? Tap + past the triple to X. An X can't win the hole.",
    "Foursomes: one score per pair on each hole.",
    "No signal? Keep entering. Scores save on the phone and send on their own when the "
    "signal comes back. Don't clear the browser.",
    "Wrong score? Tap the hole and fix it. If a score is disputed, flag it with what it "
    "should be; Kerry or a manager approves or denies it.",
    "After 18: check the card, take a photo of the paper scorecard, then submit.",
    "Follow every match live on LEADERBOARD > LONE STAR CUP.",
]

SESSION_INFO = {
    "fourball": ("Fourball", "Each player plays his own ball; the pair's best net ball wins the "
                 "hole. 90% of course handicap, off the lowest player in the match."),
    "chapman": ("Foursomes (Chapman)", "Both partners tee off, each plays the other's ball for "
                "the second shot, then the pair picks one ball and alternates in. 60% of the "
                "low + 40% of the high handicap, off the lowest team in the match."),
    "singles": ("Singles", "One on one. 100% of course handicap, off the lower player."),
}
# THE EVENING DINNERS (Kerry 2026-10-09: "Need to add evening dinner venues and
# times and information/map"). One copy, read by this email (under each day)
# and by EVENT INFO's schedule (templates/_lsc_info_body.html).
DINNERS = [
    {"key": "fri", "date": "2026-10-09", "time": "7:30 PM", "venue": "Sectionhand Steakhouse",
     "where": "4412 Hwy 377 S, Brownwood", "note": "Shirts issued",
     "links": [("Website", "https://www.sectionhandsteakhouse.com"),
               ("Map", "https://www.google.com/maps/search/?api=1&query="
                       "Section+Hand+Steak+House+4412+Hwy+377+S+Brownwood+TX")]},
    {"key": "sat", "date": "2026-10-10", "time": "8:00 PM",
     "venue": "Pogue Farm Market Seafood & Steakhouse", "where": "", "note": "",
     "links": [("Map", "https://maps.app.goo.gl/uTGseEPBWC9uSKdH8")]},
]

POINTS_LINE = ("Every match is worth 1 point, ½ each for a match all square after 18 (no extra "
               "holes). 28 points in all; San Antonio, the holders, keep the Cup on a 14–14 tie.")


def _e(s) -> str:
    return _html.escape(str(s or ""), quote=True)


def _clock(t: str, session_id: str) -> str:
    """'8:30' -> '8:30 AM'; the Saturday afternoon session is PM."""
    t = str(t or "").strip()
    if not t or "M" in t.upper():
        return t
    try:
        h = int(t.split(":")[0])
    except ValueError:
        return t
    pm = session_id == "sat-pm" or 1 <= h <= 6
    return f"{t} {'PM' if pm else 'AM'}"


def _day(d: str) -> str:
    from datetime import date
    try:
        y, m, dd = (int(x) for x in str(d).split("-"))
        return date(y, m, dd).strftime("%A, %B %-d")
    except Exception:
        return str(d or "")


def _short(url):
    if not url:
        return url
    try:
        from email_parser.score_entry import short_score_url
        return short_score_url(url) or url
    except Exception:
        return url


def _dinner_html(d: dict) -> str:
    """'7:30 PM: Dinner at Sectionhand Steakhouse, 4412 Hwy 377 S, Brownwood.
    Shirts issued. Website · Map' as one paragraph under its day."""
    links = " &middot; ".join(f'<a href="{_e(u)}">{_e(t)}</a>' for t, u in d.get("links") or [])
    return (f'<p style="margin:8px 0 4px;"><strong>{_e(d["time"])}: Dinner at {_e(d["venue"])}</strong>'
            + (f', {_e(d["where"])}' if d.get("where") else "") + "."
            + (f' {_e(d["note"])}.' if d.get("note") else "")
            + (f"<br>{links}" if links else "") + "</p>")


def build(db_path=None) -> dict:
    """Every Cup player's message (nothing is sent).
    {event_id, messages: [{customer_id, name, email, subject, html}], held, hash}."""
    from email_parser import database as db
    from email_parser.score_entry import _json_setting, cup_sign_sheets
    dial = _json_setting("lsc_matches", db_path)
    eid = int(dial.get("event_id") or 0)
    if not eid:
        return {"error": "lsc_matches is not set"}
    sessions = [s for s in dial.get("sessions") or [] if s.get("matches")]

    # per (session, cid): the group's scorecard link (the cart sign's)
    links = {}
    try:
        for r in (cup_sign_sheets(eid, db_path=db_path).get("rounds") or []):
            for g in r.get("groups") or []:
                for p in g.get("players") or []:
                    links[(r.get("session"), int(p["customer_id"]))] = g.get("url")
    except Exception:
        logger.exception("lsc weekend email: scorecard links unavailable")

    # the Friday practice round: the Cup's 'friday' add-on event
    practice = {}
    try:
        cfg = json.loads(db.get_app_setting("oneoff_charges", db_path=db_path) or "{}").get(str(eid)) or {}
        peid = next((int(a["event_id"]) for a in cfg.get("addons") or []
                     if isinstance(a, dict) and a.get("key") == "friday" and a.get("event_id")), None)
        if peid:
            pk = db.get_event_print_pack(peid, db_path=db_path) or {}
            pdate = (pk.get("event") or {}).get("event_date")
            for g in pk.get("groups") or []:
                ps = [p for p in g.get("players") or [] if p.get("customer_id")]
                for p in ps:
                    practice[int(p["customer_id"])] = {
                        "date": pdate, "start": g.get("start_line") or g.get("slot_label") or "",
                        "mates": [int(q["customer_id"]) for q in ps if q is not p]}
    except Exception:
        logger.exception("lsc weekend email: practice round unavailable")

    cids = sorted({int(c) for s in sessions for m in s["matches"]
                   for c in (m.get("austin") or []) + (m.get("sa") or [])})
    conn = db.get_connection(db_path)
    try:
        names = {}
        for row in conn.execute(
                f"SELECT customer_id, first_name, last_name FROM customers WHERE customer_id IN "
                f"({','.join('?' * len(cids))})", cids):
            names[row[0]] = f"{(row[1] or '').strip()} {(row[2] or '').strip()}".strip()
        emails = {c: (db.resolve_player_email(c, conn=conn) or "").strip() for c in cids}
    finally:
        conn.close()
    nm = lambda c: names.get(int(c)) or f"#{c}"  # noqa: E731
    side_name = {"austin": "Austin", "sa": "San Antonio"}

    # weekend match numbers 1-28 through the dial's sessions
    numbered, n = [], 0
    for s in sessions:
        for m in s["matches"]:
            n += 1
            numbered.append((s, m, n))

    messages, held = [], []
    for c in cids:
        name, email = nm(c), emails.get(c) or ""
        if not email or "@" not in email:
            held.append({"customer_id": c, "name": name, "reason": "no email on file"})
            continue
        first = name.split()[0] if name else ""
        team = None
        rounds = []
        for s, m, no in numbered:
            for side, other in (("austin", "sa"), ("sa", "austin")):
                if c in [int(x) for x in m.get(side) or []]:
                    team = team or side
                    fmt = str(s.get("format") or "").lower()
                    title, how = SESSION_INFO.get(fmt, (s.get("label") or fmt, ""))
                    partner = [nm(x) for x in m.get(side) or [] if int(x) != c]
                    opp = [nm(x) for x in m.get(other) or []]
                    group_mates = ""
                    if fmt == "singles":
                        twin = next((mm for ss, mm, nn in numbered if ss is s and mm is not m
                                     and mm.get("tee_time") == m.get("tee_time")), None)
                        if twin:
                            tno = next(nn for ss, mm, nn in numbered if mm is twin)
                            group_mates = (f"Playing in your group: Match {tno}, "
                                           f"{nm((twin.get('austin') or [''])[0])} v "
                                           f"{nm((twin.get('sa') or [''])[0])}.")
                    rounds.append({"session": s.get("id"), "day": _day(s.get("date")), "date": str(s.get("date") or "")[:10], "title": title,
                                   "how": how, "no": no, "tee": _clock(m.get("tee_time"), s.get("id")),
                                   "partner": partner, "opp": opp, "group": group_mates,
                                   "link": _short(links.get((s.get("id"), c)))})
        pr = practice.get(c)
        subject = "Lone Star Cup: your weekend, tee times, matches and scoring"
        h = [f'<p>{_e(first)},</p>',
             '<p>Here is your whole Lone Star Cup weekend at The Hideout Golf Club &amp; Resort, '
             f'Brownwood. You play for <strong>{_e(side_name.get(team, ""))}</strong>.</p>']
        if pr:
            mates = ", ".join(nm(x) for x in pr["mates"])
            h.append(f'<h3 style="margin:18px 0 4px;">{_e(_day(pr["date"]))}: Practice round</h3>'
                     f'<p style="margin:0;"><strong>{_e(pr["start"])}</strong>'
                     + (f' with {_e(mates)}' if mates else "") + '.</p>')
        # Friday (no Cup round): the practice round when he plays it, then dinner
        fri = DINNERS[0]
        if not pr:
            h.append(f'<h3 style="margin:18px 0 4px;">{_e(_day(fri["date"]))}</h3>')
        h.append(_dinner_html(fri))
        # the other dinners: each after that day's last match, or under its
        # own day heading when he has no match that day
        left = list(DINNERS[1:])

        def _flush(before=None):
            while left and (before is None or left[0]["date"] < before):
                d = left.pop(0)
                h.append(f'<h3 style="margin:18px 0 4px;">{_e(_day(d["date"]))}</h3>')
                h.append(_dinner_html(d))
        last_day = None
        for i, r in enumerate(rounds):
            if r["day"] != last_day:
                _flush(r["date"])
                h.append(f'<h3 style="margin:18px 0 4px;">{_e(r["day"])}</h3>')
                last_day = r["day"]
            vs = (f'You &amp; {_e(" & ".join(r["partner"]))} v {_e(" & ".join(r["opp"]))}'
                  if r["partner"] else f'You v {_e(" & ".join(r["opp"]))}')
            h.append(f'<p style="margin:0 0 4px;"><strong>{_e(r["title"])}: Match {r["no"]}, '
                     f'{_e(r["tee"])} off Hole 1</strong><br>{vs}.'
                     + (f'<br>{_e(r["group"])}' if r["group"] else "")
                     + (f'<br><a href="{_e(r["link"])}">Your group\'s scorecard</a>' if r["link"] else "")
                     + '</p>')
            nxt = rounds[i + 1]["day"] if i + 1 < len(rounds) else None
            if left and left[0]["date"] == r["date"] and nxt != r["day"]:
                h.append(_dinner_html(left.pop(0)))
        _flush()
        h.append('<h3 style="margin:18px 0 4px;">The formats</h3><ul style="margin:0;">'
                 + "".join(f'<li><strong>{_e(t)}:</strong> {_e(w)}</li>'
                           for t, w in (SESSION_INFO[k] for k in ("fourball", "chapman", "singles")))
                 + f'</ul><p style="margin:6px 0 0;">{_e(POINTS_LINE)}</p>')
        h.append('<h3 style="margin:18px 0 4px;">Scoring on your phone</h3><ul style="margin:0;">'
                 + "".join(f"<li>{_e(x)}</li>" for x in SCORER_NOTES) + "</ul>")
        h.append(f'<p style="margin:14px 0 0;">Follow it live: <a href="{BOARD_URL}">Lone Star Cup leaderboard</a>'
                 f' &middot; <a href="{INFO_URL}">Event info</a></p>'
                 '<p>See you on the first tee.<br>Kerry</p>')
        html = "".join(h)
        try:
            from email_parser.fetcher import normalize_email_html
            html = normalize_email_html(html)
        except Exception:
            pass
        messages.append({"customer_id": c, "name": name, "email": email, "subject": subject,
                         "html": html, "rounds": len(rounds), "practice": bool(pr)})
    digest = hashlib.sha256(json.dumps([[m["customer_id"], m["email"], m["subject"], m["html"]]
                                        for m in messages]).encode()).hexdigest()[:12]
    return {"event_id": eid, "messages": messages, "held": held, "hash": digest}


def _graph(to, subject, html) -> bool:
    import os
    from email_parser.fetcher import send_mail_graph
    c = [os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")]
    if not all(c):
        return False
    return send_mail_graph(tenant_id=c[0], client_id=c[1], client_secret=c[2], from_address=c[3],
                           to_address=to, subject=subject, html_body=html)


def summary(built: dict) -> dict:
    return {"event_id": built.get("event_id"), "hash": built.get("hash"),
            "messages": len(built.get("messages") or []),
            "with_practice": sum(1 for m in built.get("messages") or [] if m["practice"]),
            "rounds_each": sorted({m["rounds"] for m in built.get("messages") or []}),
            "held": built.get("held"), "error": built.get("error")}


def send_preview(to: str = "kerry@thegolffellowship.com", sample_cids=(18,), db_path=None) -> dict:
    """STAFF ONLY: one email with the sample players' messages and the batch
    hash Kerry approves."""
    from email_parser.recap_mail import staff_only
    built = build(db_path)
    if built.get("error"):
        return built
    from email_parser import database as db
    if staff_only([to], get_setting=lambda k: db.get_app_setting(k, db_path=db_path)):
        return {"error": f"{to} is not a staff address"}
    picks = [m for m in built["messages"] if m["customer_id"] in set(sample_cids)] or built["messages"][:1]
    held = "".join(f"<li>{_e(h['name'])}: {_e(h['reason'])}</li>" for h in built["held"])
    head = (f'<p><strong>PREVIEW, staff only.</strong> {len(built["messages"])} players get their own '
            f'version of this email; {len(built["held"])} held.</p>'
            + (f"<ul>{held}</ul>" if held else "")
            + f'<p>Approval code: <strong>{built["hash"]}</strong>. Nothing goes to members until you say send.</p><hr>')
    body = head + "<hr>".join(f'<p style="color:#6B7280">To {_e(m["name"])} &lt;{_e(m["email"])}&gt;</p>'
                              + m["html"] for m in picks)
    ok = _graph(to, f"PREVIEW: {picks[0]['subject']}", body)
    return {**summary(built), "preview_sent": bool(ok), "to": to,
            "samples": [m["name"] for m in picks]}


def send(approval: str, confirm: bool = False, db_path=None) -> dict:
    """The member send. Refuses unless confirm and approval == the batch hash."""
    from email_parser import database as db
    built = build(db_path)
    if built.get("error"):
        return built
    if not confirm or approval != built["hash"]:
        return {**summary(built), "sent": 0,
                "refused": "needs confirm and the current approval code (the batch changed?)"}
    try:
        done = json.loads(db.get_app_setting(SENT_KEY, db_path=db_path) or "{}")
    except (TypeError, ValueError):
        done = {}
    from datetime import datetime, timezone
    sent, failed, skipped = [], [], []
    for m in built["messages"]:
        k = str(m["customer_id"])
        if k in done:
            skipped.append(m["name"])
            continue
        done[k] = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "email": m["email"], "hash": built["hash"], "status": "sending"}
        db.set_app_setting(SENT_KEY, json.dumps(done), db_path=db_path)
        ok = _graph(m["email"], m["subject"], m["html"])
        done[k]["status"] = "sent" if ok else "failed"
        db.set_app_setting(SENT_KEY, json.dumps(done), db_path=db_path)
        (sent if ok else failed).append(m["name"])
    return {**summary(built), "sent": len(sent), "failed": failed, "skipped_already_sent": skipped}
