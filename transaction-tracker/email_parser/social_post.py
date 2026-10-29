"""THE RESULTS CARD ON FACEBOOK (and, later, Instagram). Event Ops #2460-J,
a PROPOSAL: the wording goes to Kerry first.

Event Ops: "auto-post a results card to the TGF Facebook page and Instagram
after the participant email. META_PAGE_TOKEN is already a planned Railway
variable."

- `build_results_card(event_id)`: a short text post read from the RECORDED
  results only: the event, its date, the winners (first places, skins, closest
  to the pin, from `tgf_payouts`, no dollar amounts), the Fall race champions
  once race close declared them, and the link to `/member/results/<event_id>`.
  A champion photo is attached when one in `player_photos.CHAMPION_PHOTOS`
  shows exactly people this event names (its season = the event's year).
- `post_to_facebook(...)`: the Graph API page feed (or the page's photos
  edge when there is an image). Never raises: it returns {"posted": False,
  "why": ...} when META_PAGE_TOKEN is missing or Meta refuses.
- `post_to_instagram(...)`: built, OFF. Instagram needs an Instagram
  business account id (IG_BUSINESS_ACCOUNT_ID) and a public image URL; it
  runs only with dial `social_instagram` on.
- `after_results_email(event_ids)`: the hook. `results_email.auto_check`
  calls it once the players' same-day results email has SENT. It posts only
  with dial `social_auto_post` = on AND app setting `social_post_approved`
  equal to the current `template_hash()` (the event_day_email approval
  pattern: change a word of TEMPLATE and the stamp no longer matches). Once
  per event (`social_post:<event_id>`).

Read-only bridge `scoring-social-post:<event_id>[|preview]`. Guard
test_social_post.py.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re

logger = logging.getLogger(__name__)

BASE = "https://tgf-tracker.up.railway.app"
GRAPH = "https://graph.facebook.com/v21.0"
DEFAULT_PAGE_ID = "119648338214501"     # the TGF Facebook Page (railway-api-setup.md)
DIAL = "social_auto_post"
IG_DIAL = "social_instagram"
APPROVAL_KEY = "social_post_approved"
POSTED_KEY = "social_post:{}"
MAX_WINNER_LINES = 8

# THE WORDING (a proposal until Kerry approves it; its hash is the stamp).
TEMPLATE = (
    "{event} | {date}\n"
    "\n"
    "Congratulations to the night's winners:\n"
    "{winners}\n"
    "{champions}"
    "\n"
    "Full results: {link}\n"
    "\n"
    "#TheGolfFellowship"
)
CHAMPIONS_LINE = "{title}: {who}\n"


def template_hash() -> str:
    return hashlib.sha256(TEMPLATE.encode("utf-8")).hexdigest()[:16]


def _setting(key, db_path=None) -> str:
    from email_parser.database import get_app_setting
    try:
        return (get_app_setting(key, db_path=db_path) or "").strip()
    except Exception:
        return ""


def _on(key, db_path=None) -> bool:
    return _setting(key, db_path).lower() in ("1", "on", "true", "yes")


def approval_state(db_path=None) -> dict:
    stamp = _setting(APPROVAL_KEY, db_path)
    cur = template_hash()
    return {"template_hash": cur, "approved_hash": stamp or None, "approved": stamp == cur}


def _date_label(d: str) -> str:
    from datetime import date
    try:
        x = date.fromisoformat(str(d)[:10])
    except ValueError:
        return str(d or "")[:10]
    return f"{x.strftime('%A')}, {x.strftime('%B')} {x.day}, {x.year}"


def _names(conn, ids) -> dict:
    ids = sorted({int(i) for i in ids if i})
    if not ids:
        return {}
    out = {}
    for r in conn.execute(
            "SELECT customer_id, first_name, last_name FROM customers "
            "WHERE customer_id IN (%s)" % ",".join("?" * len(ids)), ids):
        n = " ".join(x for x in ((r["first_name"] or "").strip(), (r["last_name"] or "").strip()) if x)
        if n:
            out[int(r["customer_id"])] = n
    return out


def _winner_lines(conn, event_id: int) -> tuple[list, set]:
    """[(label, [names])] from the recorded payouts: first places, every
    skin, closest to the pin. Never a dollar amount."""
    from email_parser.results_email import _payout_label
    tgf = conn.execute("SELECT id FROM tgf_events WHERE events_id = ? ORDER BY id DESC LIMIT 1",
                       (int(event_id),)).fetchone()
    if not tgf:
        return [], set()
    rows = [dict(r) for r in conn.execute(
        "SELECT customer_id, category, description FROM tgf_payouts "
        "WHERE event_id = ? AND customer_id IS NOT NULL ORDER BY id", (tgf[0],))]
    names = _names(conn, [r["customer_id"] for r in rows])
    groups: dict = {}
    ids: set = set()
    for r in rows:
        lab = re.sub(r"<[^>]+>", "", _payout_label(r.get("category") or "", r.get("description") or ""))
        lab = lab.replace("&amp;", "&")
        first = re.search(r"·\s*(1st|T1)$", lab)
        if lab.startswith("Skins"):
            key = "Skins"
        elif lab.startswith("Closest to the Pin"):
            key = lab.replace(" · ", ", ")
        elif first:
            key = re.sub(r"\s*·\s*(1st|T1)$", "", lab).replace(" · ", ", ")
        else:
            continue
        nm = names.get(int(r["customer_id"]))
        if not nm:
            continue
        lst = groups.setdefault(key, [])
        if nm not in lst:
            lst.append(nm)
        ids.add(int(r["customer_id"]))
    order = sorted(groups, key=lambda k: (0 if k.startswith("Individual") else
                                          1 if "Net" in k else 2 if k == "Skins" else 3, k))
    return [(k, groups[k]) for k in order][:MAX_WINNER_LINES], ids


def _champion_lines(ev: dict, db_path=None) -> tuple[list, set]:
    """The Fall race champions this event made final (race close), as the
    results email's THE CHAMPIONS block reads them."""
    from email_parser import database as db
    from email_parser.results_email import FALL_RACE, _chapter_key
    ch = _chapter_key(ev)
    keys = [ch] if ch in FALL_RACE else (list(FALL_RACE) if ch == "tgf" else [])
    out, ids = [], set()
    for key in keys:
        try:
            data = db.get_points_race_standings(FALL_RACE[key][0], db_path=db_path, no_network=True)
        except Exception:
            logger.exception("social post: race %s unreadable", key)
            continue
        champs = data.get("champions") or []
        if not data.get("race_final") or not champs:
            continue
        names = []
        for c in champs:
            n = c.get("player_name") or ""
            names.append((n.split(", ", 1)[1] + " " + n.split(", ", 1)[0].title()) if ", " in n else n)
            if c.get("customer_id"):
                ids.add(int(c["customer_id"]))
        title = f"{FALL_RACE[key][2]} Fall Net " + ("Co-Champions" if len(names) > 1 else "Champion")
        out.append((title, " and ".join(names)))
    return out, ids


def _photo(ev: dict, ids: set) -> str | None:
    from email_parser.player_photos import CHAMPION_PHOTOS, photo_file
    year = str(ev.get("event_date") or "")[:4]
    for key, c in CHAMPION_PHOTOS.items():
        if key.endswith(f"-{year}") and set(c["customer_ids"]) and set(c["customer_ids"]) <= ids \
                and photo_file("c", key):
            return f"{BASE}/member/photo/c/{key}.jpg"
    return None


def build_results_card(event_id: int, db_path=None) -> dict:
    """The post for one event. `held` lists why it must not go (no event,
    no recorded winners, a leftover {tag})."""
    from email_parser import database as db
    eid = int(event_id)
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone()
        if not r:
            return {"event_id": eid, "held": [f"no event {eid}"], "text": ""}
        ev = dict(r)
        winners, w_ids = _winner_lines(conn, eid)
    champs, c_ids = _champion_lines(ev, db_path)
    # A champion photo shows a CUP champion: only for a race champion this
    # card names, or a winner of a championship / cup event itself. A
    # Tuesday-night winner who once won a cup gets no cup photo.
    photo_ids = set(c_ids)
    if re.search(r"champ|cup", str(ev.get("item_name") or ""), re.I):
        photo_ids |= w_ids
    link = f"{BASE}/member/results/{eid}"
    text = TEMPLATE.format(
        event=(ev.get("item_name") or "").strip(),
        date=_date_label(ev.get("event_date")),
        winners="\n".join(f"{k}: {', '.join(v)}" for k, v in winners),
        champions="".join(CHAMPIONS_LINE.format(title=t, who=w) for t, w in champs),
        link=link)
    held = []
    if not winners and not champs:
        held.append("no recorded winners for this event yet (tgf_payouts)")
    if re.search(r"\{[a-z_]+\}|\[BLANK\]", text):
        held.append("a blank or leftover {tag} in the text")
    return {"event_id": eid, "event": ev.get("item_name"), "date": str(ev.get("event_date") or "")[:10],
            "text": text, "link": link, "image_url": _photo(ev, photo_ids),
            "winners": winners, "champions": champs, "template_hash": template_hash(), "held": held}


def _graph_post(path: str, data: dict) -> dict:
    """One POST to the Graph API. Never raises."""
    try:
        import requests
        r = requests.post(f"{GRAPH}/{path}", data=data, timeout=20)
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text[:300]}
        if r.status_code >= 400 or "error" in body:
            err = body.get("error") or {}
            return {"ok": False, "why": f"Meta refused ({r.status_code}): "
                                        f"{err.get('message') or body.get('raw') or 'no message'}"}
        return {"ok": True, "body": body}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "why": f"Graph call failed: {exc}"}


def post_to_facebook(message: str, link: str | None = None, image_url: str | None = None,
                     page_id: str | None = None, token: str | None = None) -> dict:
    """Post to the TGF Facebook Page. With an image: the page's photos edge
    (the caption carries the text); else the feed with the link. Returns
    {"posted": bool, "id"?, "why"?}; never raises."""
    token = token if token is not None else os.environ.get("META_PAGE_TOKEN", "")
    if not (token or "").strip():
        return {"posted": False, "why": "META_PAGE_TOKEN is not set on Railway"}
    if not (message or "").strip():
        return {"posted": False, "why": "empty message"}
    page = page_id or os.environ.get("META_PAGE_ID") or DEFAULT_PAGE_ID
    if image_url:
        res = _graph_post(f"{page}/photos", {"url": image_url, "caption": message,
                                             "access_token": token})
    else:
        data = {"message": message, "access_token": token}
        if link:
            data["link"] = link
        res = _graph_post(f"{page}/feed", data)
    if not res["ok"]:
        return {"posted": False, "why": res["why"]}
    b = res["body"]
    return {"posted": True, "id": b.get("post_id") or b.get("id")}


def post_to_instagram(caption: str, image_url: str | None, ig_user_id: str | None = None,
                      token: str | None = None, db_path=None) -> dict:
    """Instagram, BUILT AND OFF: needs dial `social_instagram`, an Instagram
    business account id (IG_BUSINESS_ACCOUNT_ID) and a public image URL (an
    Instagram post is always an image). Two calls: create the media
    container, then publish it. Never raises."""
    if not _on(IG_DIAL, db_path):
        return {"posted": False, "why": f"dial {IG_DIAL} is off"}
    token = token if token is not None else os.environ.get("META_PAGE_TOKEN", "")
    ig = ig_user_id or os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
    if not (token or "").strip():
        return {"posted": False, "why": "META_PAGE_TOKEN is not set on Railway"}
    if not ig:
        return {"posted": False, "why": "IG_BUSINESS_ACCOUNT_ID is not set"}
    if not image_url:
        return {"posted": False, "why": "Instagram needs an image; this card has none"}
    c = _graph_post(f"{ig}/media", {"image_url": image_url, "caption": caption, "access_token": token})
    if not c["ok"]:
        return {"posted": False, "why": c["why"]}
    p = _graph_post(f"{ig}/media_publish", {"creation_id": c["body"].get("id"), "access_token": token})
    if not p["ok"]:
        return {"posted": False, "why": p["why"]}
    return {"posted": True, "id": p["body"].get("id")}


def post_event(event_id: int, db_path=None) -> dict:
    """Every gate, then the post, once per event. Never raises."""
    from email_parser import database as db
    eid = int(event_id)
    try:
        if not _on(DIAL, db_path):
            return {"event_id": eid, "posted": False, "why": f"dial {DIAL} is off"}
        appr = approval_state(db_path)
        if not appr["approved"]:
            return {"event_id": eid, "posted": False,
                    "why": f"wording not approved: app setting {APPROVAL_KEY} must equal "
                           f"{appr['template_hash']}"}
        prev = _setting(POSTED_KEY.format(eid), db_path)
        if prev and json.loads(prev).get("posted"):
            return {"event_id": eid, "posted": False, "why": "already posted", "prev": json.loads(prev)}
        card = build_results_card(eid, db_path=db_path)
        if card["held"]:
            return {"event_id": eid, "posted": False, "why": "; ".join(card["held"])}
        fb = post_to_facebook(card["text"], link=card["link"], image_url=card["image_url"])
        ig = post_to_instagram(card["text"], card["image_url"], db_path=db_path)
        rec = {"posted": fb["posted"], "facebook": fb, "instagram": ig,
               "template_hash": card["template_hash"]}
        db.set_app_setting(POSTED_KEY.format(eid), json.dumps(rec), db_path=db_path)
        db.log_agent_action("social-post", "social_post",
                            f"event {eid} ({card['event']}): Facebook "
                            + (f"posted {fb.get('id')}" if fb["posted"] else f"not posted: {fb.get('why')}"),
                            db_path=db_path)
        return {"event_id": eid, **rec}
    except Exception as exc:  # noqa: BLE001
        logger.exception("social post failed for %s", eid)
        return {"event_id": eid, "posted": False, "why": f"error: {exc}"}


def after_results_email(event_ids, db_path=None) -> dict:
    """The hook after the players' results email has sent. Never raises."""
    out = {}
    for e in event_ids or []:
        out[int(e)] = post_event(int(e), db_path=db_path)
    return out


def preview(event_id: int, db_path=None) -> dict:
    """The read-only bridge: the post text and every gate's state."""
    card = build_results_card(int(event_id), db_path=db_path)
    return {**card, "approval": approval_state(db_path), "dial": DIAL, "dial_on": _on(DIAL, db_path),
            "instagram_dial_on": _on(IG_DIAL, db_path),
            "token_set": bool(os.environ.get("META_PAGE_TOKEN", "").strip()),
            "already": _setting(POSTED_KEY.format(int(event_id)), db_path) or None,
            "note": "read only; posts only after the players' results email, with the dial on "
                    "and the wording stamp equal to template_hash"}
