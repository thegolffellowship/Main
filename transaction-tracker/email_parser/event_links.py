"""Store registration links for events — derived, verified, expiring.

Kerry 2026-09-09, pasting the Avery Ranch product URL: *"Are you able to
grab other current event URLs and add them to the Event pages for email
or text presets? You could just add a box in each of the Event
Creator/Edit modals to show these. After the events they become obsolete
and should be removed or something."*

The box already existed — `events.registration_url`, added for the Lead
Center follow-up texts (#417 D) — but it was typed by hand or left blank.
This module makes it DERIVED (principle 1: compute, don't collect):

  * the store slug is the event name lower-cased with every run of
    non-alphanumerics collapsed to one hyphen — verified against the URLs
    Kerry has pasted: "a9.23 Avery Ranch" → a9-23-avery-ranch,
    "s18.11 CEDAR CREEK" → s18-11-cedar-creek, "2026 TGF CHAMPIONSHIP" →
    2026-tgf-championship;
  * a derived URL is only SAVED once the store answers for it (the store
    is GoDaddy Online Store; unknown products redirect to the shop index
    rather than 404, so "answers" means HTTP 200 AND the final URL still
    carries the slug);
  * a link is never deleted — past events are frozen (principle 4). Once
    the event date has passed the link's STATE reads `expired`, the
    composer variable {event_url} refuses to render it, and the modal
    says so. That is the "removed or something".

Consumers: the Lead Center follow-up texts (`leads.py`, which already
drop the link sentence when the field is blank) and the Message Players
composer through the `{event_url}` variable (`app.py` send + preview).

Host allowlist on the checker for the same reason `fetch_public_page`
has one: anything reachable through a bridge command must not be an
open proxy out of the Railway network.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

STORE_BASE = "https://thegolffellowship.com/shop/ols/products/"
STORE_HOSTS = {"thegolffellowship.com", "www.thegolffellowship.com"}

_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Link states, as the modal badge and the composer guard read them.
STATE_OK = "ok"                  # verified against the store
STATE_UNVERIFIED = "unverified"  # a URL is on file; the store has not been asked
STATE_MISSING = "missing"        # nothing on file, or the store does not know the slug
STATE_EXPIRED = "expired"        # the event date has passed
STATE_ERROR = "error"            # the store could not be reached when last asked


def derive_store_slug(item_name: str | None) -> str:
    return _SLUG_RE.sub("-", (item_name or "").lower()).strip("-")


def derive_store_url(item_name: str | None) -> str:
    slug = derive_store_slug(item_name)
    return STORE_BASE + slug if slug else ""


def is_store_url(url: str | None) -> bool:
    try:
        p = urlparse((url or "").strip())
    except ValueError:
        return False
    return p.scheme == "https" and p.netloc.lower() in STORE_HOSTS


def _default_fetch(url: str, timeout: int) -> tuple[int, str]:
    import requests
    r = requests.get(url, timeout=timeout, allow_redirects=True,
                     headers={"User-Agent": "TGF-Tracker link check"})
    return r.status_code, r.url or url


def check_store_url(url: str, timeout: int = 12,
                    fetch: Callable[[str, int], tuple[int, str]] | None = None) -> dict:
    """Ask the store whether a product URL is live.

    Returns {"status": ok|missing|error, "http": int|None, "final_url": str,
    "detail": str}. `fetch(url, timeout) -> (status_code, final_url)` is
    injectable so the rule can be tested without the network.
    """
    url = (url or "").strip()
    if not is_store_url(url):
        return {"status": STATE_ERROR, "http": None, "final_url": url,
                "detail": "not a thegolffellowship.com store URL"}
    try:
        code, final = (fetch or _default_fetch)(url, timeout)
    except Exception as exc:  # network, DNS, timeout — all "could not ask"
        return {"status": STATE_ERROR, "http": None, "final_url": url,
                "detail": str(exc)[:200]}
    slug = url.rstrip("/").rsplit("/", 1)[-1].lower()
    final_l = (final or "").lower()
    if code == 200 and slug and slug in final_l:
        return {"status": STATE_OK, "http": code, "final_url": final, "detail": ""}
    if code == 404 or (code == 200 and slug not in final_l):
        return {"status": STATE_MISSING, "http": code, "final_url": final,
                "detail": "the store has no product at this address"}
    return {"status": STATE_ERROR, "http": code, "final_url": final,
            "detail": f"HTTP {code}"}


def _is_past(event_date: str | None, today: date) -> bool:
    return bool(event_date) and str(event_date)[:10] < today.isoformat()


def link_state(ev: dict, today: date | None = None) -> dict:
    """The link as the UI should show it: url, state, suggested_url."""
    today = today or date.today()
    url = (ev.get("registration_url") or "").strip()
    if _is_past(ev.get("event_date"), today):
        state = STATE_EXPIRED
    elif url:
        state = ev.get("registration_url_status") or STATE_UNVERIFIED
        if state == STATE_MISSING and url:
            # A URL is on file but the store said no — keep it visible,
            # keep the badge honest.
            state = STATE_MISSING
    else:
        state = STATE_MISSING
    suggested = ""
    if not url and state != STATE_EXPIRED:
        suggested = derive_store_url(ev.get("item_name"))
    return {"url": url, "state": state, "suggested_url": suggested,
            "checked_at": ev.get("registration_url_checked_at")}


def event_url_for_message(ev: dict | None, today: date | None = None) -> tuple[str, str]:
    """(url, problem) for the {event_url} variable. url is "" whenever the
    link must not go out; problem says why, for the send guard."""
    if not ev:
        return "", "no event on file"
    st = link_state(ev, today)
    if st["state"] == STATE_EXPIRED:
        return "", "the event has already been played, so its registration link is expired"
    if not st["url"]:
        return "", "no registration link on file for this event"
    if st["state"] == STATE_MISSING:
        return "", "the registration link on file did not verify against the store"
    return st["url"], ""


def sweep_event_links(db_path: str | Path | None = None, apply: bool = False,
                      today: date | None = None,
                      checker: Callable[[str], dict] | None = None,
                      only_event_id: int | None = None) -> dict:
    """Derive, verify and (with apply) save store links for upcoming events;
    mark past events' links expired. Never deletes a URL.

    Runs from the daily scheduler job, the modal's Verify button
    (only_event_id) and the `scoring-event-links` bridge.
    """
    from . import database as db  # lazy: database imports nothing from here

    today = today or date.today()
    checker = checker or check_store_url
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    out: dict = {"apply": apply, "today": today.isoformat(), "rows": [],
                 "verified": 0, "filled": 0, "missing": 0, "expired": 0, "errors": 0}
    with db._connect(db_path) as conn:
        q = ("SELECT id, item_name, event_date, registration_url, "
             "registration_url_status FROM events WHERE event_date IS NOT NULL")
        args: tuple = ()
        if only_event_id:
            q += " AND id = ?"
            args = (only_event_id,)
        rows = conn.execute(q + " ORDER BY event_date, id", args).fetchall()
        for r in rows:
            ev = dict(r)
            url = (ev.get("registration_url") or "").strip()
            rep = {"id": ev["id"], "item_name": ev["item_name"],
                   "event_date": ev["event_date"], "url": url,
                   "derived": False, "saved": False}
            if _is_past(ev["event_date"], today):
                # Frozen: keep the URL, flip the state once.
                if url and ev.get("registration_url_status") != STATE_EXPIRED:
                    rep["status"] = STATE_EXPIRED
                    out["expired"] += 1
                    if apply:
                        conn.execute(
                            "UPDATE events SET registration_url_status = ? "
                            "WHERE id = ?", (STATE_EXPIRED, ev["id"]))
                        rep["saved"] = True
                    out["rows"].append(rep)
                continue
            if not url:
                url = derive_store_url(ev["item_name"])
                rep["url"] = url
                rep["derived"] = True
            if not url:
                continue
            res = checker(url)
            rep["status"] = res["status"]
            rep["http"] = res.get("http")
            if res["status"] == STATE_OK:
                out["verified"] += 1
            elif res["status"] == STATE_MISSING:
                out["missing"] += 1
            else:
                out["errors"] += 1
            if apply:
                if rep["derived"] and res["status"] == STATE_OK:
                    conn.execute(
                        "UPDATE events SET registration_url = ?, "
                        "registration_url_status = ?, registration_url_checked_at = ? "
                        "WHERE id = ?", (url, STATE_OK, now, ev["id"]))
                    out["filled"] += 1
                    rep["saved"] = True
                elif not rep["derived"]:
                    # A URL on file (typed or previously derived): record
                    # what the store said, leave the URL alone.
                    conn.execute(
                        "UPDATE events SET registration_url_status = ?, "
                        "registration_url_checked_at = ? WHERE id = ?",
                        (res["status"], now, ev["id"]))
                    rep["saved"] = True
                # derived + not ok: nothing saved — the modal shows the
                # suggestion and the badge stays MISSING.
            out["rows"].append(rep)
        if apply:
            conn.commit()
    return out
