"""Facebook / HubSpot lead intake (mailbox #352/#353, Kerry-ratified
2026-08-27).

The Fall 2026 Meta lead campaign lands leads in HubSpot (native Meta Lead
Ads integration → contact with hs_analytics_source = PAID_SOCIAL, object
source FORM). The 48-hour personal touch is the conversion gate, so the
Tracker polls HubSpot on a timer, queues every new lead in the `leads`
table, and pings Kerry + the chapter manager by email the moment one
arrives. The admin queue at /admin/leads shows name / email / phone /
city / source / days-since-arrival and a touched state so the 48-hour
touch is auditable.

Why HubSpot (not Brevo, not Make.com): verified 2026-08-28 that Meta
leads land as HubSpot contacts (first campaign lead arrived 03:21 UTC,
PAID_SOCIAL/FORM), while Brevo holds the mailing lists. A scheduled pull
was Kerry's ratified default over webhooks. Needs one Railway env var:
HUBSPOT_TOKEN (private-app token with crm.objects.contacts.read).

Dials (rules-as-data, edited via scoring-setting-set):
  leads_hubspot_watermark   ISO UTC high-water mark for the poll window
                            (default 2026-08-27T00:00:00Z, campaign start)
  lead_source_filter        {"analytics_sources": [...], "object_source_labels":
                            [...]} — a contact QUEUES when its
                            hs_analytics_source is in the first list OR its
                            hs_object_source_label is in the second. Default
                            PAID_SOCIAL / SOCIAL_MEDIA + FORM / IMPORT — the
                            store-sync INTEGRATION contacts (existing
                            customers) deliberately do not match.
  lead_city_chapters        {"austin": "Austin", ...} — lowercase city
                            substring → chapter for touch routing.
  lead_notify_recipients    {"San Antonio": ["a@b"], "Austin": [...],
                            "default": [...]} — default falls back to
                            COO_EMAIL_TO / EMAIL_ADDRESS. Unrouted leads
                            notify every list.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

HUBSPOT_SEARCH_URL = "https://api.hubapi.com/crm/v3/objects/contacts/search"
DEFAULT_WATERMARK = "2026-08-27T00:00:00Z"   # Meta campaign activation
LEAD_PROPERTIES = ["firstname", "lastname", "email", "phone", "city",
                   "createdate", "hs_analytics_source",
                   "hs_object_source_label"]

DEFAULT_SOURCE_FILTER = {
    "analytics_sources": ["PAID_SOCIAL", "SOCIAL_MEDIA"],
    "object_source_labels": ["FORM", "IMPORT"],
}

# Lowercase city substring → chapter (touch owner routing). Extend via
# the lead_city_chapters dial; matching is substring, case-insensitive.
DEFAULT_CITY_CHAPTERS = {
    "austin": "Austin", "round rock": "Austin", "pflugerville": "Austin",
    "cedar park": "Austin", "leander": "Austin", "georgetown": "Austin",
    "hutto": "Austin", "manor": "Austin", "buda": "Austin", "kyle": "Austin",
    "lakeway": "Austin", "san antonio": "San Antonio",
    "new braunfels": "San Antonio", "schertz": "San Antonio",
    "seguin": "San Antonio", "boerne": "San Antonio",
    "converse": "San Antonio", "helotes": "San Antonio",
    "cibolo": "San Antonio", "universal city": "San Antonio",
    # Brevo CITY sweep additions (2026-09-02) — real chapter suburbs
    # seen on chapterless contacts. Longer/base-specific keys sit
    # BEFORE anything they could be confused with ("jbsa" / "ft. sam"
    # before a legacy "houston" key in the Brevo-only metro map).
    "jbsa": "San Antonio", "ft. sam": "San Antonio", "fort sam": "San Antonio",
    "lackland": "San Antonio", "randolph": "San Antonio",
    "bulverde": "San Antonio", "spring branch": "San Antonio",
    "garden ridge": "San Antonio", "selma": "San Antonio",
    "live oak": "San Antonio", "windcrest": "San Antonio",
    "alamo heights": "San Antonio", "castle hills": "San Antonio",
    "fair oaks": "San Antonio", "canyon lake": "San Antonio",
    "comfort": "San Antonio", "floresville": "San Antonio",
    "castroville": "San Antonio", "leon valley": "San Antonio",
    "lago vista": "Austin", "dripping springs": "Austin", "bee cave": "Austin",
    "wimberley": "Austin", "elgin": "Austin", "bastrop": "Austin",
    "taylor": "Austin", "liberty hill": "Austin", "jonestown": "Austin",
    "spicewood": "Austin", "marble falls": "Austin", "westlake": "Austin",
    "west lake hills": "Austin", "sunset valley": "Austin",
}


def _hubspot_token() -> str | None:
    return (os.getenv("HUBSPOT_TOKEN")
            or os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")) or None


# What counts as a HUMAN REPLY for the stats metric (mailbox #412).
# Narrower than the queue's response signal on purpose: `auto` is the
# app's own bookkeeping, `GG` is a Golf Genius RSVP and `HS` a HubSpot
# re-submission. All three mean the lead did SOMETHING — which is why
# they still disarm the 48-hour alarm — but none of them is the person
# writing back, so none of them belongs in "did our outreach work".
REPLY_EXCLUDED_NOTE_AUTHORS = ("auto", "gg", "hs")
# Tags Kerry only reaches for after hearing back. Nothing sets these
# automatically (the machine-written tags are 'Became member' and
# 'Registered event'), so one of these IS evidence of a reply.
REPLY_TAGS = ("Call back", "Interested", "Coming to event")

_REPLY_EXCLUDE_SQL = ", ".join(f"'{a}'" for a in REPLY_EXCLUDED_NOTE_AUTHORS)
_HOT_TAGS_SQL = ", ".join("'" + t.replace("'", "''") + "'" for t in REPLY_TAGS)


def ensure_leads_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            source        TEXT NOT NULL DEFAULT 'hubspot',
            external_id   TEXT,
            first_name    TEXT,
            last_name     TEXT,
            email         TEXT,
            phone         TEXT,
            city          TEXT,
            chapter       TEXT,
            source_label  TEXT,
            arrived_at    TEXT,
            first_seen_at TEXT DEFAULT (datetime('now')),
            notified_at   TEXT,
            touched_at    TEXT,
            touched_by    TEXT,
            status        TEXT NOT NULL DEFAULT 'new',
            notes         TEXT,
            payload       TEXT,
            customer_id   INTEGER REFERENCES customers(customer_id),
            UNIQUE (source, external_id)
        )
    """)
    try:
        # Flexible form-response capture (mailbox #355): questions change
        # between campaigns, so answers live as JSON, not columns.
        conn.execute("ALTER TABLE leads ADD COLUMN payload TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        # Disposition tag (Kerry 2026-08-28: "additional options for
        # tagging leads, not just touched and converted") — one current
        # tag per lead, options from the lead_tag_options dial.
        conn.execute("ALTER TABLE leads ADD COLUMN tag TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        # Follow-up / snooze date (mailbox #365, Kerry-ratified
        # 2026-08-31): leads self-schedule for future events (Truchan →
        # Silverhorn 9/8 etc.) — a future date snoozes the row out of
        # the active view; a due date resurfaces it at the top.
        conn.execute("ALTER TABLE leads ADD COLUMN follow_up_at TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        # Duplicate-lead merge (Kerry 2026-09-03): the loser points at
        # the keeper and drops out of every queue read. Never deleted —
        # its external_id must stay or the next poll re-creates it.
        conn.execute("ALTER TABLE leads ADD COLUMN merged_into INTEGER "
                     "REFERENCES leads(id)")
    except sqlite3.OperationalError:
        pass
    try:
        # 48-hour outreach alarm (Kerry 2026-09-03): when he tags an
        # outreach action (Texted / Sent email / Left VM) the wait for a
        # reply starts here, and follow_up_at is auto-set 2 days out.
        # A NON-NULL outreach_at is what marks a follow-up date as the
        # AUTO alarm — a date Kerry set by hand has outreach_at NULL and
        # is never cleared by a note or a status change.
        conn.execute("ALTER TABLE leads ADD COLUMN outreach_at TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        # Due-day ping dedup (mailbox #370, Kerry-ratified 2026-08-31):
        # stores the follow_up_at value that was pinged, so each due
        # date emails exactly once and a re-snoozed lead re-arms for
        # its new date automatically.
        conn.execute("ALTER TABLE leads ADD COLUMN follow_up_notified_for TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        # REPLIED evidence (mailbox #412, Kerry: "Responded definitely
        # needs to be resolved. We don't want to put that into those
        # statistics.").
        #
        # The stats metric is REPLIED and means a human wrote back. The
        # problem is that the evidence does not survive: the conversion
        # auto-detect OVERWRITES tag with 'Became member' / 'Registered
        # event', so a lead who texted back "Interested" and then
        # registered looks, afterwards, exactly like a lead who never
        # answered at all. Reading the reply off the CURRENT tag would
        # therefore undercount every campaign that actually worked.
        #
        # So stamp it when it happens instead of reconstructing it
        # later: first human reply wins, never cleared, no money and no
        # member-facing effect. Backfilled below from the evidence that
        # still exists today, which makes the metric no worse now and
        # correct from here on.
        conn.execute("ALTER TABLE leads ADD COLUMN replied_at TEXT")
        conn.execute(
            "UPDATE leads SET replied_at = COALESCE("
            "  (SELECT MIN(n.created_at) FROM lead_notes n "
            "   WHERE n.lead_id = leads.id "
            f"   AND COALESCE(LOWER(n.author), '') NOT IN ({_REPLY_EXCLUDE_SQL})),"
            "  touched_at, arrived_at) "
            "WHERE EXISTS (SELECT 1 FROM lead_notes n WHERE n.lead_id = leads.id "
            f"              AND COALESCE(LOWER(n.author), '') NOT IN ({_REPLY_EXCLUDE_SQL})) "
            f"   OR COALESCE(tag, '') IN ({_HOT_TAGS_SQL})")
    except sqlite3.OperationalError:
        pass
    # Per-lead notes log (mailbox #361 — first brick of Tracker-as-CRM):
    # timestamped, authored; newest previews on the card.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id    INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            author     TEXT,
            note       TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_status "
                 "ON leads(status, arrived_at)")
    # Campaign entity (mailbox #391): lead_campaigns + leads.campaign_id
    # + leads.converted_at, seeded with the current campaign.
    try:
        from .campaigns import ensure_campaigns_table
        ensure_campaigns_table(conn)
    except Exception:
        logger.warning("campaigns schema ensure failed", exc_info=True)
    # Heal (v2.261.1, Kerry: "Bad Contact is still persisting"): leads
    # carrying a deactivating tag from BEFORE the tag auto-dismissed —
    # or tagged during a deploy gap — flip to dismissed on every
    # read/write path. Idempotent; converted keeps its status. Commits
    # only when a row actually changed (ensure runs at the start of
    # operations, so nothing else is pending on this connection).
    try:
        cur = conn.execute(
            "UPDATE leads SET status = 'dismissed' "
            f"WHERE tag IN ({','.join('?' * len(DEACTIVATING_TAGS))}) "
            "AND status NOT IN ('dismissed', 'converted')",
            tuple(sorted(DEACTIVATING_TAGS)))
        if cur.rowcount:
            conn.commit()
    except sqlite3.OperationalError:
        pass


def _dial_json(key: str, default, db_path=None):
    from . import database as db
    try:
        raw = db.get_app_setting(key, db_path=db_path) if db_path \
            else db.get_app_setting(key)
        val = json.loads(raw) if raw else None
        return val if isinstance(val, type(default)) else default
    except Exception:
        return default


def route_chapter(city: str | None, city_map: dict | None = None) -> str | None:
    """Chapter for a lead's city — substring match, case-insensitive."""
    if not city:
        return None
    c = city.strip().lower()
    for frag, chapter in (city_map or DEFAULT_CITY_CHAPTERS).items():
        if frag in c:
            return chapter
    return None


def route_chapter_from_payload(payload: dict | None) -> str | None:
    """Chapter from the lead's OWN form answers. Kerry-ruled 2026-08-27:
    the STAY-IN-THE-LOOP answer ('yes_for_san_antonio') is the chapter
    signal — chapter_interest is form boilerplate that always says
    'austin_sa' and never decides. SA check FIRST because 'san_antonio'
    contains no 'austin' but combined values contain both tokens."""
    if not isinstance(payload, dict):
        return None

    def _chap(val: str) -> str | None:
        v = (val or "").lower()
        has_sa = "san_antonio" in v or "san antonio" in v
        has_atx = "austin" in v.replace("austin_sa", "") \
            or v.strip() in ("austin", "austin_only", "yes_for_austin")
        if v.strip() in ("austin_sa", "both", "either"):
            return None          # explicitly both → let the next signal decide
        if has_sa and not has_atx:
            return "San Antonio"
        if has_atx and not has_sa:
            return "Austin"
        return None

    for keys in (("stay_in_the_loop", "loop"),
                 ("chapter",)):
        for k, v in payload.items():
            if k == "chapter_interest":
                continue         # static boilerplate — never decides
            if any(t in k.lower() for t in keys) and isinstance(v, str):
                got = _chap(v)
                if got:
                    return got
    return None


# Facebook option values arrive as snake_case with the explanation glued
# on after '_-_' ("all_of_it!_-_enjoy_a_well-rounded_experience...").
# Show the short head, humanized (Kerry 2026-08-27: "reduce down to the
# initial part"). Special vocabulary for chapter tokens.
_PRETTY_MAP = {
    # Kerry-ruled decode vocabulary (2026-08-28)
    "austin_sa": "Austin + SA",
    "san_antonio": "San Antonio",
    "yes_for_san_antonio": "San Antonio",
    "yes_for_austin": "Austin",
    "yes_for_both": "Both",
    "no": "None",
    "yes_-_i_can_play_both_tuesdays_or_saturdays": "Both",
    "yes_-_i_can_play_saturdays": "Saturdays",
    "yes_-_i_can_play_tuesdays": "Tuesdays",
}


def extract_ad_ids(payload: dict | None) -> dict:
    """Meta attribution ids from the HubSpot first-URL (hsa_* params):
    hsa_cam → ad_campaign_id, hsa_grp → ad_set_id, hsa_ad → ad_id.
    The ad set is chapter-targeted (Kerry 2026-08-27: 'Austin - Fall
    2026 Leads' / 'SA - Fall 2026 Leads'), so it doubles as a routing
    signal and the per-ad-set stats dimension."""
    if not isinstance(payload, dict):
        return {}
    url = payload.get("hs_analytics_first_url") or ""
    if "hsa_" not in url:
        return {}
    try:
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(url).query)
        out = {}
        for param, key in (("hsa_cam", "ad_campaign_id"),
                           ("hsa_grp", "ad_set_id"),
                           ("hsa_ad", "ad_id")):
            v = (qs.get(param) or [None])[0]
            if v:
                out[key] = v
        return out
    except Exception:
        return {}


def enrich_payload(payload: dict | None, ad_set_names: dict | None = None,
                   ) -> dict | None:
    """Merge extracted ad ids + the human ad-set name (dial
    lead_ad_set_names: {id: name}) into the payload. Idempotent."""
    if not isinstance(payload, dict):
        return payload
    ids = extract_ad_ids(payload)
    for k, v in ids.items():
        payload.setdefault(k, v)
    asid = payload.get("ad_set_id")
    if asid and (ad_set_names or {}).get(str(asid)):
        payload["ad_set_name"] = ad_set_names[str(asid)]
    return payload


def prettify_answer(value) -> str:
    if not isinstance(value, str):
        return str(value)
    v = value.strip()
    if "://" in v or "@" in v or not any(c.isalpha() for c in v):
        return v                     # URLs, emails, ids, dates — leave alone
    mapped = _PRETTY_MAP.get(v.lower())
    if mapped:
        return mapped
    head, _, tail = v.partition("_-_")
    head = head.strip().rstrip("_")
    mapped = _PRETTY_MAP.get(head.lower())
    if mapped:
        return mapped

    def _human(s):
        t = s.replace("_", " ").strip()
        return (t[:1].upper() + t[1:]) if t else ""
    # A bare yes/no head loses the option's substance ("yes_-_i_can_play
    # _both_tuesdays_or_saturdays" is not just "Yes") — keep the tail.
    if head.lower() in ("yes", "no") and tail.strip():
        return f"{_human(head)} — {_human(tail).lower()}"
    return _human(head) or v


# Answers-panel display rules (email + queue; JS mirror in leads.html).
# Everything stays STORED — these only govern what renders. Form
# questions first, ad/campaign attribution second, plumbing hidden.
_ANSWER_HIDE_PREFIXES = ("_", "num_", "stripe_", "ad_campaign_id", "ad_set_id",
                         "ad_id")
_ANSWER_HIDE = {"lifecyclestage", "first_conversion_date",
                "recent_conversion_date", "first_conversion_event_name",
                "hs_object_source_label", "hs_analytics_first_url",
                "hs_analytics_source", "hs_analytics_source_data_1",
                # Kerry 2026-08-27: static boilerplate baked into the FB
                # lead form's hidden fields — always austin_sa /
                # city_newcomer on every submission of this form
                "chapter_interest", "ad_variation"}
_ANSWER_ATTR = {"ad_set_name": "Ad set",
                "hs_analytics_source_data_2": "Campaign",
                "recent_conversion_event_name": "Form"}


# Kerry-ruled short labels (2026-08-27) for the known form questions;
# an unrecognized question falls back to its humanized key.
_FORM_LABEL_PATTERNS = (
    ("play_tuesdays_or_saturdays", "Availability"),
    ("most_important", "Importance"),
    ("stay_in_the_loop", "Invitations"),
    ("loop", "Invitations"),
)


def _form_label(key: str) -> str:
    kl = key.lower()
    for frag, label in _FORM_LABEL_PATTERNS:
        if frag in kl:
            return label
    return key.replace("_", " ").capitalize()


def display_answers(payload: dict | None) -> list[tuple[str, str]]:
    """[(label, pretty_value)] — the lead's form answers first (that's
    what informs the touch), attribution after, plumbing hidden."""
    if not isinstance(payload, dict):
        return []
    hide = set(_ANSWER_HIDE) - set(_ANSWER_ATTR)
    form, attr = [], []
    for k in sorted(payload):
        if k in hide or k.startswith(_ANSWER_HIDE_PREFIXES):
            continue
        label = _ANSWER_ATTR.get(k)
        pretty = prettify_answer(payload[k])
        if label:
            attr.append((label, pretty))
        else:
            form.append((_form_label(k), pretty))
    return form + attr


def lead_passes_filter(analytics_source: str | None, source_label: str | None,
                       flt: dict | None = None) -> bool:
    flt = flt if isinstance(flt, dict) else DEFAULT_SOURCE_FILTER
    srcs = [s.upper() for s in flt.get("analytics_sources") or []]
    labels = [s.upper() for s in flt.get("object_source_labels") or []]
    return ((analytics_source or "").upper() in srcs
            or (source_label or "").upper() in labels)


def _match_customer_id(conn: sqlite3.Connection, email: str | None) -> int | None:
    if not email:
        return None
    row = conn.execute(
        "SELECT customer_id FROM customer_emails "
        "WHERE LOWER(email) = LOWER(?) LIMIT 1", (email.strip(),)).fetchone()
    return row["customer_id"] if row else None


def _link_or_create_customer(conn: sqlite3.Connection, lead: dict) -> int | None:
    """Real customer_id for a lead (Kerry 2026-08-28: 'I believe we need
    to'). Email match first; otherwise create a customers row through
    the SAME resolver save_items uses, so when the lead later buys, the
    order lands on the same identity. Requires a first AND last name —
    a half-named lead stays unlinked rather than minting a shell
    profile (fix the name, the next poll links it)."""
    from . import database as db
    cid = _match_customer_id(conn, lead.get("email"))
    if cid:
        return cid
    first = (lead.get("first_name") or "").strip()
    last = (lead.get("last_name") or "").strip()
    if not (first and last):
        return None
    try:
        cid = db._resolve_or_create_customer(
            conn, f"{first} {last}", lead.get("email"),
            phone=lead.get("phone"), chapter=lead.get("chapter"),
            first_name=first, last_name=last)
        if cid:
            # The resolver defaults acquisition_source to 'godaddy' —
            # a lead-created prospect came from the Facebook campaign.
            # Guarded to purchase-less rows so a matched real customer's
            # source is never rewritten (idempotent backfill included).
            conn.execute(
                "UPDATE customers SET acquisition_source = 'facebook_lead' "
                "WHERE customer_id = ? AND acquisition_source = 'godaddy' "
                "AND NOT EXISTS (SELECT 1 FROM items i "
                "                WHERE i.customer_id = customers.customer_id)",
                (cid,))
        return cid
    except Exception:
        logger.warning("Lead customer link failed for %s %s", first, last,
                       exc_info=True)
        return None


def upsert_leads(conn: sqlite3.Connection, rows: list[dict],
                 city_map: dict | None = None) -> list[int]:
    """Insert new lead rows (dedup on (source, external_id)); returns the
    ids of rows actually inserted this pass."""
    ensure_leads_table(conn)
    new_ids: list[int] = []
    for r in rows:
        dup = conn.execute(
            "SELECT id FROM leads WHERE source = ? AND external_id = ?",
            (r.get("source") or "hubspot", str(r.get("external_id")))).fetchone()
        if dup:
            continue
        chapter = r.get("chapter") or route_chapter(r.get("city"), city_map)
        cid = _match_customer_id(conn, r.get("email"))
        cur = conn.execute(
            """INSERT INTO leads (source, external_id, first_name, last_name,
                                  email, phone, city, chapter, source_label,
                                  arrived_at, customer_id, payload)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r.get("source") or "hubspot", str(r.get("external_id")),
             r.get("first_name"), r.get("last_name"), r.get("email"),
             r.get("phone"), r.get("city"), chapter, r.get("source_label"),
             r.get("arrived_at"), cid,
             json.dumps(r["payload"]) if r.get("payload") else None))
        new_ids.append(cur.lastrowid)
    conn.commit()
    return new_ids


def _fetch_hubspot_contacts(token: str, since_iso: str) -> list[dict]:
    """New HubSpot contacts created on/after the watermark, oldest first."""
    payload = {
        "filterGroups": [{"filters": [
            {"propertyName": "createdate", "operator": "GTE",
             "value": since_iso}]}],
        "properties": LEAD_PROPERTIES,
        "sorts": [{"propertyName": "createdate", "direction": "ASCENDING"}],
        "limit": 100,
    }
    resp = requests.post(
        HUBSPOT_SEARCH_URL, json=payload, timeout=30,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    resp.raise_for_status()
    out = []
    for c in resp.json().get("results", []):
        p = c.get("properties") or {}
        out.append({
            "source": "hubspot",
            "external_id": c.get("id"),
            "first_name": p.get("firstname"),
            "last_name": p.get("lastname"),
            "email": p.get("email"),
            "phone": p.get("phone"),
            "city": p.get("city"),
            "arrived_at": p.get("createdate"),
            "analytics_source": p.get("hs_analytics_source"),
            "source_label": p.get("hs_object_source_label"),
        })
    return out


# Identity-record placeholders (mirror of dashboard.js
# PLACEHOLDER_MERCHANTS): rows that put a PERSON in the system, not a
# purchase. They must never count as conversion evidence — the Oscar
# Gonzalez / Daniel Garza case (Kerry 2026-09-01): both carried one
# 'Roster Import' row from 3/3 and the auto-detect read it as
# "Registered event" even though neither has ever played or paid.
PLACEHOLDER_MERCHANTS = ("Roster Import", "Customer Entry", "RSVP Import",
                         "RSVP Email Link", "Handicap Import")

LOOP_QUESTION_KEY = ("would_you_like_to_stay_in_the_loop_with_tgf"
                     "_and_receive_event_invitations")

RECONV_WATERMARK_KEY = "leads_hubspot_reconv_watermark"
# Current fall campaign start — the first reconversion sweep back-collects
# this campaign's deduped re-submitters (Wilder, Hinojosa, O.Gonzalez,
# M.Hernandez, D.Garza as of 2026-09-01).
DEFAULT_RECONV_WATERMARK = "2026-08-27T00:00:00Z"




def _hist_ts(v):
    from datetime import datetime as _dt
    try:
        return _dt.fromisoformat(str(v).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _fetch_answer_history(token: str, contact_id: str, keys: list[str],
                          latest_conv: str = "") -> tuple[dict, dict]:
    """(dates, prev) via propertiesWithHistory, splitting a deduped
    re-submitter's answers by SURVEY (Kerry 2026-09-01: HubSpot merges
    submissions into one contact, so earlier-campaign answers persist
    beside the new ones and the card showed them mixed).

    dates = {key: LAST-set ISO timestamp}. Versions are sorted HERE —
    the v2.278.1 draft trusted the API's element order, read the wrong
    end, and stamped every answer with its FIRST-ever set date, tagging
    even current answers "earlier survey" (Kerry's Wilder card).

    prev = {key: {"v": value, "t": ts}} — for a key the CURRENT survey
    overwrote, the newest version set before the latest-conversion
    window, i.e. the EARLIER survey's answer. Lets the card show a
    changed answer in BOTH sections (new value on top, what it used to
    be below)."""
    if not keys:
        return {}, {}
    from datetime import timedelta as _td
    resp = requests.get(
        f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}",
        params={"propertiesWithHistory": ",".join(keys[:40])}, timeout=30,
        headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    cutoff = _hist_ts(latest_conv)
    if cutoff:
        cutoff = cutoff - _td(days=3)
    dates, prev = {}, {}
    for k, versions in (resp.json().get("propertiesWithHistory")
                        or {}).items():
        vs = [(_hist_ts(v.get("timestamp")), v) for v in (versions or [])]
        vs = sorted([x for x in vs if x[0]], key=lambda x: x[0],
                    reverse=True)
        if not vs:
            continue
        dates[k] = vs[0][1].get("timestamp")
        if cutoff and vs[0][0] >= cutoff:
            older = next((v for t, v in vs if t < cutoff
                          and v.get("value") not in (None, "")), None)
            if older is not None and older.get("value") != vs[0][1].get("value"):
                prev[k] = {"v": older["value"], "t": older.get("timestamp")}
    return dates, prev


def _answer_date_keys(payload: dict) -> list[str]:
    return [k for k in (payload or {})
            if not k.startswith(("hs_", "ad_", "_", "num_"))
            and k not in ("lifecyclestage", "chapter_interest",
                          "first_conversion_date",
                          "first_conversion_event_name",
                          "recent_conversion_date",
                          "recent_conversion_event_name")]

def _fetch_hubspot_reconversions(token: str, since_iso: str) -> list[dict]:
    """EXISTING HubSpot contacts who (re)submitted a Facebook Lead Ads
    form on/after the watermark (Kerry 2026-09-01: "add on this list
    people who filled out this Facebook Ad survey that were duplicates
    in HubSpot"). The createdate poll can never see them: HubSpot dedups
    the submission into the existing contact, so createdate stays old
    while recent_conversion_date moves. Filtered by the CONVERSION EVENT
    ('Facebook Lead Ads: …') rather than analytics source — a years-old
    contact's original source is whatever brought them in back then and
    would wrongly fail the ad-source filter. Contacts whose createdate
    equals the conversion are genuinely NEW and ride the normal poll."""
    payload = {
        "filterGroups": [{"filters": [
            {"propertyName": "recent_conversion_date", "operator": "GTE",
             "value": since_iso}]}],
        "properties": LEAD_PROPERTIES + ["recent_conversion_date",
                                         "recent_conversion_event_name"],
        "sorts": [{"propertyName": "recent_conversion_date",
                   "direction": "ASCENDING"}],
        "limit": 100,
    }
    resp = requests.post(
        HUBSPOT_SEARCH_URL, json=payload, timeout=30,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    resp.raise_for_status()
    out = []
    for c in resp.json().get("results", []):
        p = c.get("properties") or {}
        ev = (p.get("recent_conversion_event_name") or "")
        if not ev.startswith("Facebook Lead Ads:"):
            continue
        conv = (p.get("recent_conversion_date") or "").strip()
        created = (p.get("createdate") or "").strip()
        if created and conv and created[:16] == conv[:16]:
            continue        # new contact — the createdate poll owns it
        out.append({
            "source": "hubspot",
            "external_id": c.get("id"),
            "first_name": p.get("firstname"),
            "last_name": p.get("lastname"),
            "email": p.get("email"),
            "phone": p.get("phone"),
            "city": p.get("city"),
            "arrived_at": conv,
            "analytics_source": p.get("hs_analytics_source"),
            "source_label": p.get("hs_object_source_label"),
            "_reconversion": True,
            "_hs_created": created,
        })
    return out


# Identity fields already stored as columns — kept out of the payload.
_PAYLOAD_EXCLUDE = {"firstname", "lastname", "email", "phone", "city",
                    "createdate", "lastmodifieddate", "hs_object_id",
                    "hs_full_name_or_email"}
# hs_-prefixed properties are HubSpot internals and are dropped — except
# the attribution set the touch owner actually wants (mailbox #355).
_PAYLOAD_KEEP_HS = {"hs_analytics_source", "hs_analytics_source_data_1",
                    "hs_analytics_source_data_2", "hs_analytics_first_url",
                    "hs_object_source_label"}


def _fetch_property_names(token: str) -> list[str]:
    """Every contact property name in the portal — form questions arrive
    as custom properties, so pulling the full list (cached per pass) is
    what makes the capture survive campaign-to-campaign question
    changes (mailbox #355: flexible key/value over hardcoded columns)."""
    resp = requests.get(
        "https://api.hubapi.com/crm/v3/properties/contacts", timeout=30,
        headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    return [p["name"] for p in resp.json().get("results", []) if p.get("name")]


def _build_payload(props: dict) -> dict:
    out = {}
    for k, v in (props or {}).items():
        if v in (None, ""):
            continue
        if k in _PAYLOAD_EXCLUDE:
            continue
        if k.startswith("hs_") and k not in _PAYLOAD_KEEP_HS:
            continue
        out[k] = v
    return out


def _fetch_full_payloads(token: str, contact_ids: list[str]
                         ) -> tuple[dict[str, dict], dict[str, dict]]:
    """({contact_id: payload}, {contact_id: identity}) — batch-read
    contacts with every portal property. payload = form answers +
    attribution; identity = first/last/email/phone/city for the
    young-lead re-sync (#360: Privyr can win the creation race and the
    Meta native sync backfills attribution ~15 min later)."""
    if not contact_ids:
        return {}, {}
    try:
        names = _fetch_property_names(token)
    except Exception as e:
        logger.warning("HubSpot property list fetch failed (%s) — "
                       "capturing identity fields only", e)
        return {}, {}
    payloads: dict[str, dict] = {}
    identities: dict[str, dict] = {}
    for i in range(0, len(contact_ids), 100):
        chunk = contact_ids[i:i + 100]
        resp = requests.post(
            "https://api.hubapi.com/crm/v3/objects/contacts/batch/read",
            json={"inputs": [{"id": c} for c in chunk], "properties": names},
            timeout=30,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"})
        resp.raise_for_status()
        for c in resp.json().get("results", []):
            props = c.get("properties") or {}
            payloads[str(c.get("id"))] = _build_payload(props)
            identities[str(c.get("id"))] = {
                "first_name": props.get("firstname"),
                "last_name": props.get("lastname"),
                "email": props.get("email"),
                "phone": props.get("phone"),
                "city": props.get("city"),
            }
    return payloads, identities


def _notify_recipients(chapter: str | None, db_path=None) -> str:
    """Comma-separated recipient list for a lead's chapter. Unrouted
    leads go to every configured list (better a double ping than a
    missed 48-hour window)."""
    cfg = _dial_json("lead_notify_recipients", {}, db_path=db_path)
    default = cfg.get("default") or [a for a in [
        os.getenv("COO_EMAIL_TO") or os.getenv("EMAIL_ADDRESS")] if a]
    if chapter:
        # A routed chapter pings default + ITS OWN list only — a chapter
        # with no list of its own (San Antonio rides the default) must
        # not fan out to the other chapter's owner (Kerry 2026-08-28:
        # SA leads go to Kerry alone).
        addrs = list(default) + list(cfg.get(chapter) or [])
    else:
        # Unrouted → everyone: better a double ping than a missed 48h.
        addrs = list(default)
        for key, lst in cfg.items():
            if key != "default" and isinstance(lst, list):
                addrs += lst
    seen, out = set(), []
    for a in addrs:
        if a and a.lower() not in seen:
            seen.add(a.lower())
            out.append(a)
    return ",".join(out)


def _lead_email_html(lead: dict) -> str:
    def row(k, v):
        return (f"<tr><td style='padding:4px 12px 4px 0;color:#6B7280;"
                f"font-size:12px;text-transform:uppercase'>{k}</td>"
                f"<td style='padding:4px 0;font-size:14px'>{v or '—'}</td></tr>")
    name = " ".join(x for x in [lead.get("first_name"),
                                lead.get("last_name")] if x) or "(no name)"
    existing = (" — <b>matches an existing customer</b>"
                if lead.get("customer_id") else "")
    # Form answers so the 48-hour touch is informed, not cold (#355)
    payload = lead.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = None
    answers = ""
    shown = display_answers(payload)
    if shown:
        lines = "".join(row(label, val) for label, val in shown)
        answers = (f"<h3 style='margin:14px 0 4px;font-size:13px;"
                   f"color:#1B1B1B'>Form answers</h3>"
                   f"<table style='border-collapse:collapse'>{lines}</table>")
    return f"""
    <div style="font-family:Helvetica,Arial,sans-serif;max-width:520px">
      <h2 style="color:#E87C3E;margin:0 0 4px">New lead: {name}</h2>
      <p style="margin:0 0 12px;color:#4B5563">The 48-hour personal touch
      starts now{existing}.</p>
      <table style="border-collapse:collapse">
        {row("Email", lead.get("email"))}
        {row("Phone", lead.get("phone"))}
        {row("Chapter", lead.get("chapter") or "unrouted")}
        {row("Source", lead.get("source_label") or lead.get("source"))}
        {row("Arrived", lead.get("arrived_at"))}
      </table>
      {answers}
      <p style="margin:14px 0 0"><a
        href="https://tgf-tracker.up.railway.app/admin/leads"
        style="color:#2563eb">Open the New Leads queue</a> and mark it
        touched once you've reached out.</p>
    </div>"""


def _send_lead_ping(lead: dict, db_path=None) -> bool:
    from .fetcher import send_mail_graph
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_addr = os.getenv("EMAIL_ADDRESS")
    to = _notify_recipients(lead.get("chapter"), db_path=db_path)
    if not all([tenant_id, client_id, client_secret, from_addr, to]):
        logger.warning("Lead ping skipped — Graph creds or recipients missing")
        return False
    name = " ".join(x for x in [lead.get("first_name"),
                                lead.get("last_name")] if x) or lead.get("email")
    return send_mail_graph(
        tenant_id=tenant_id, client_id=client_id,
        client_secret=client_secret, from_address=from_addr, to_address=to,
        subject=f"🚨 New TGF lead: {name}"
                + (f" ({lead['chapter']})" if lead.get("chapter") else ""),
        html_body=_lead_email_html(lead))


def dismiss_no_loop_leads(conn: sqlite3.Connection) -> int:
    """Auto-dismiss leads who answered NO to the stay-in-the-loop
    question (Kerry 2026-09-01: no communication wanted → bottom
    DISMISSED). Same key/value test the CSV invite exports already use
    to exclude them. Never touches converted (a customer who opted out
    of invites is still a customer) or already-dismissed rows; an
    'auto' note records why. Returns rows dismissed."""
    n = 0
    for r in conn.execute(
            "SELECT id, payload FROM leads WHERE payload IS NOT NULL "
            "AND status NOT IN ('dismissed', 'converted')").fetchall():
        try:
            p = json.loads(r["payload"])
        except Exception:
            continue
        # CURRENT form's key first (Kerry 2026-09-01: a re-submitter's
        # payload carries BOTH surveys' properties — the fuzzy match can
        # land on a stale earlier-campaign answer). Same-key values are
        # per-property last-write in HubSpot, so the exact key is always
        # the latest submission's answer.
        val = p.get(LOOP_QUESTION_KEY)
        if not (isinstance(val, str) and val.strip()):
            val = next((v for k, v in p.items()
                        if ("stay_in_the_loop" in k.lower()
                            or "loop" in k.lower())
                        and isinstance(v, str) and v.strip()), "")
        optout = val.strip().lower().startswith("no")
        if not optout:
            continue
        conn.execute("UPDATE leads SET status = 'dismissed' WHERE id = ?",
                     (r["id"],))
        if not conn.execute(
                "SELECT 1 FROM lead_notes WHERE lead_id = ? "
                "AND note LIKE 'Opted out of invites%'",
                (r["id"],)).fetchone():
            conn.execute(
                "INSERT INTO lead_notes (lead_id, author, note) VALUES "
                "(?, 'auto', 'Opted out of invites on the survey "
                "(No loop) — auto-dismissed')", (r["id"],))
        n += 1
    return n


def lead_center_payload(status: str = "", campaigns: list | None = None,
                        db_path: str | Path | None = None) -> dict:
    """Everything the Lead Center page renders from, in one place.

    Lives here rather than inline in the route so it can be exercised by
    a test and read on production through `scoring-leads-payload`.
    v2.300.0 broke this payload on a single stale preset key and the
    page came up BLANK on mobile for a day, with every suite green,
    because nothing outside a browser could see what the route produced.

    NEVER index a preset by a slot key here. P1-P4 carried tue/sat/both
    until v2.300.0 and now carry one `text`; anything reading a preset
    body goes through .get() with fallbacks.
    """
    leads = get_leads(status=status, db_path=db_path)

    # Per-ad-set stats (Kerry 2026-08-27: "help us track stats for
    # each") — keyed on the human ad-set name when the dial knows it.
    by_ad_set: dict = {}
    for l in leads:
        p = l.get("payload") or {}
        key = (p.get("ad_set_name") or p.get("ad_set_id")
               or "(no ad attribution)")
        b = by_ad_set.setdefault(key, {"total": 0, "new": 0, "touched": 0,
                                       "converted": 0, "dismissed": 0})
        b["total"] += 1
        if l.get("status") in b:
            b[l["status"]] += 1

    # First-touch SMS presets (#383 → #388/#389, Kerry-ratified
    # 2026-09-02): picked server-side per lead (preset + slot + the #389
    # add-on) and filled client-side so the ▾ picker switches without a
    # refetch. Per-lead so ONE bad lead can never blank the queue.
    sms_presets = get_sms_presets(db_path)
    owners = get_touch_owners(db_path)
    nexts = next_event_labels(db_path)
    rows = next_event_rows(db_path)
    for l in leads:
        try:
            l["sms"] = select_sms_preset(l)
            l["sms"]["vars"] = sms_vars_for(l, owners, nexts, rows,
                                            l["sms"]["slot"])
        except Exception:
            logger.warning("Lead SMS preset pick failed for lead %s",
                           l.get("id"), exc_info=True)
            l["sms"] = None

    # Kept for older clients: the default template body + next-event map.
    _p4 = sms_presets.get("p4") or {}
    sms_template = (_p4.get("text") or _p4.get("tue")
                    or _p4.get("both") or "")
    return {"leads": leads, "by_ad_set": by_ad_set,
            "sms_template": sms_template,
            "next_events": dict(nexts.get("any") or {}),
            "sms_presets": sms_presets,
            "sms_order": sms_preset_order(sms_presets),
            "sms_p9_presets": sorted(SMS_P9_PRESETS),
            "campaigns": campaigns if campaigns is not None else [],
            "tag_options": get_tag_options(db_path),
            "answer_options": get_answer_options(),
            "manual_lead_sources": MANUAL_LEAD_SOURCES}


def followups_due(db_path: str | Path | None = None) -> list[dict]:
    """Every lead whose follow-up date has arrived or passed, most
    overdue first. Live state — nothing is marked or consumed by
    reading it, which is what lets the morning digest show the same
    lead every day until it is actually dealt with.
    """
    from . import database as db
    from .timezone_utils import now_central
    today = now_central().strftime("%Y-%m-%d")
    out: list[dict] = []
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM leads WHERE follow_up_at IS NOT NULL "
            "AND follow_up_at <= ? AND status != 'dismissed' "
            "AND merged_into IS NULL ORDER BY follow_up_at, id",
            (today,)).fetchall()]
        for lead in rows:
            nr = conn.execute(
                "SELECT note FROM lead_notes WHERE lead_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (lead["id"],)).fetchone()
            days = 0
            try:
                from datetime import date as _date
                y, m, d = (int(x) for x in str(lead["follow_up_at"])[:10].split("-"))
                ty, tm, td = (int(x) for x in today.split("-"))
                days = (_date(ty, tm, td) - _date(y, m, d)).days
            except Exception:
                pass
            out.append({
                "id": lead["id"],
                "name": " ".join(x for x in [lead.get("first_name"),
                                             lead.get("last_name")] if x)
                        or lead.get("email") or "(no name)",
                "chapter": lead.get("chapter"),
                "tag": lead.get("tag"),
                "email": lead.get("email"),
                "phone": lead.get("phone"),
                "due": lead.get("follow_up_at"),
                "days_over": days,
                "last_note": nr["note"] if nr else None,
                "customer_id": lead.get("customer_id"),
            })
    out.sort(key=lambda r: (-r["days_over"], r["name"]))
    return out


def _followup_digest_html(rows: list[dict], heading: str) -> str:
    """One list, not one email per lead."""
    def line(r):
        over = ("<span style='color:#dc2626;font-weight:600'>"
                f"{r['days_over']}d overdue</span>" if r["days_over"] > 0
                else "<span style='color:#059669;font-weight:600'>due today</span>")
        bits = " · ".join(x for x in [r.get("tag"), r.get("chapter"),
                                      r.get("phone")] if x)
        note = (f"<div style='font-size:12px;color:#6B7280;margin-top:2px'>"
                f"{r['last_note']}</div>" if r.get("last_note") else "")
        return (f"<div style='padding:8px 12px;margin-top:6px;background:#fff;"
                f"border:1px solid #e5e7eb;border-left:4px solid "
                f"{'#dc2626' if r['days_over'] > 0 else '#059669'};"
                f"border-radius:6px;font-size:13px'>"
                f"<strong>{r['name']}</strong> — {over}"
                f"<div style='font-size:12px;color:#6B7280'>{bits}</div>"
                f"{note}</div>")
    return f"""
    <div style="font-family:Helvetica,Arial,sans-serif;max-width:560px">
      <h2 style="color:#E87C3E;margin:0 0 4px">{heading}</h2>
      <p style="margin:0 0 12px;color:#4B5563">These are the people whose
      48-hour window is up. They are waiting on you, not the other way
      round.</p>
      {''.join(line(r) for r in rows)}
      <p style="margin:14px 0 0"><a
        href="https://tgf-tracker.up.railway.app/admin/leads"
        style="color:#2563eb">Open the Lead Center</a> — they are sitting
        under FOLLOW-UPS DUE at the top.</p>
    </div>"""


def send_followup_digests(db_path: str | Path | None = None) -> dict:
    """ONE morning digest per chapter owner, replacing the one-email-
    per-lead ping (Kerry 2026-09-03: "should be part of morning
    digest").

    Kerry's own copy rides the 7 AM COO Daily Briefing, which is his
    morning digest and already lands in his inbox. This sends only to
    recipients the briefing does NOT reach — a chapter's own list, like
    Robert on Austin — so a chapter manager keeps their notice without
    Kerry getting the same list twice.

    Dedup is PER DAY, not per lead: a lead that stays overdue appears
    again tomorrow, which is the point of a digest and the opposite of
    the old ping, which fired once and then went quiet forever.
    """
    from . import database as db
    from .timezone_utils import now_central
    now = now_central()
    result = {"due": 0, "digests": 0, "recipients": []}
    if now.hour < 7:
        # Morning delivery: the first sweep after 7 AM Central sends.
        return result
    today = now.strftime("%Y-%m-%d")
    rows = followups_due(db_path=db_path)
    result["due"] = len(rows)
    if not rows:
        return result

    cfg = _dial_json("lead_notify_recipients", {}, db_path=db_path)
    # The briefing covers the default list only when it actually runs.
    covered = set()
    if os.getenv("COO_EMAIL_TO"):
        for a in (cfg.get("default") or [os.getenv("COO_EMAIL_TO")]):
            if a:
                covered.add(a.strip().lower())

    sent_for = _dial_json("leads_followup_digest_sent", {}, db_path=db_path)
    for chapter, addrs in cfg.items():
        if chapter == "default" or not isinstance(addrs, list):
            continue
        to = [a for a in addrs if a and a.strip().lower() not in covered]
        if not to:
            continue
        mine = [r for r in rows if r.get("chapter") == chapter]
        if not mine:
            continue
        if sent_for.get(chapter) == today:
            continue
        if _send_digest_mail(", ".join(to), mine,
                             f"{chapter} follow-ups due"):
            sent_for[chapter] = today
            result["digests"] += 1
            result["recipients"].append(chapter)
    if result["digests"]:
        try:
            db.set_app_setting("leads_followup_digest_sent",
                               json.dumps(sent_for), db_path=db_path)
        except Exception:
            logger.warning("Could not record digest send state",
                           exc_info=True)
    return result


def _send_digest_mail(to: str, rows: list[dict], heading: str) -> bool:
    from .fetcher import send_mail_graph
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_addr = os.getenv("EMAIL_ADDRESS")
    if not all([tenant_id, client_id, client_secret, from_addr, to]):
        logger.warning("Follow-up digest skipped — Graph creds or "
                       "recipients missing")
        return False
    n = len(rows)
    return send_mail_graph(
        tenant_id=tenant_id, client_id=client_id,
        client_secret=client_secret, from_address=from_addr, to_address=to,
        subject=f"\u23f0 {n} follow-up{'s' if n != 1 else ''} due — {heading}",
        html_body=_followup_digest_html(rows, heading))


def check_new_leads(db_path: str | Path | None = None) -> dict:
    """Scheduled poll: pull new HubSpot contacts past the watermark,
    queue the ones that pass the source filter, ping the touch owners.
    Safe no-op when HUBSPOT_TOKEN is unset."""
    from . import database as db
    result = {"fetched": 0, "queued": 0, "notified": 0, "skipped_filter": 0}
    # Due-day follow-up sweep FIRST and independently, so a missing
    # HubSpot token or a failed fetch can never swallow a due digest.
    try:
        result["followups"] = send_followup_digests(db_path=db_path)
    except Exception:
        logger.warning("Follow-up due-ping sweep failed", exc_info=True)
    token = _hubspot_token()
    if not token:
        result["error"] = "HUBSPOT_TOKEN not set"
        return result

    watermark = None
    try:
        watermark = db.get_app_setting("leads_hubspot_watermark")
    except Exception:
        pass
    since = (watermark or DEFAULT_WATERMARK).strip()

    try:
        contacts = _fetch_hubspot_contacts(token, since)
    except Exception as e:
        logger.warning("HubSpot lead poll failed: %s", e)
        result["error"] = str(e)
        return result
    result["fetched"] = len(contacts)

    flt = _dial_json("lead_source_filter", DEFAULT_SOURCE_FILTER,
                     db_path=db_path)
    city_map = _dial_json("lead_city_chapters", DEFAULT_CITY_CHAPTERS,
                          db_path=db_path)
    passing = []
    for c in contacts:
        if lead_passes_filter(c.get("analytics_source"),
                              c.get("source_label"), flt):
            passing.append(c)
        else:
            result["skipped_filter"] += 1

    # Deduped re-submitters (Kerry 2026-09-01): existing HubSpot contacts
    # who filled the FB survey never cross the createdate watermark —
    # sweep them by recent_conversion_date instead. They bypass the
    # source filter (the conversion EVENT is the filter) and dedup in
    # upsert_leads by external_id like everyone else.
    reconv: list = []
    try:
        r_wm = None
        try:
            r_wm = db.get_app_setting(RECONV_WATERMARK_KEY)
        except Exception:
            pass
        reconv = _fetch_hubspot_reconversions(
            token, (r_wm or DEFAULT_RECONV_WATERMARK).strip())
    except Exception as e:
        logger.warning("HubSpot reconversion sweep failed: %s", e)
    result["reconversions"] = len(reconv)
    passing.extend(reconv)

    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        # Full form-response capture (mailbox #355) for the genuinely NEW
        # contacts only — one extra batch read per poll at most.
        known = {r["external_id"] for r in conn.execute(
            "SELECT external_id FROM leads WHERE source = 'hubspot'")}
        fresh_ids = [str(c["external_id"]) for c in passing
                     if str(c["external_id"]) not in known]
        # #360 (Kerry-ratified): dual pipelines write into HubSpot, and
        # when Privyr's bare-form push wins the creation race the first
        # snapshot has no ad attribution (Meta's native sync backfills
        # ~15 min later). Re-fetch every lead first seen < 48h and
        # update-if-changed, so attribution, names, and phones heal.
        resync_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM leads WHERE source = 'hubspot' "
            "AND first_seen_at >= datetime('now', '-48 hours')")]
        resync_ids = [str(r["external_id"]) for r in resync_rows
                      if str(r["external_id"]) not in fresh_ids]
        try:
            payloads, identities = _fetch_full_payloads(
                token, fresh_ids + resync_ids)
        except Exception as e:
            logger.warning("HubSpot full-payload fetch failed: %s", e)
            payloads, identities = {}, {}
        ad_set_names = _dial_json("lead_ad_set_names", {}, db_path=db_path)
        ad_set_chapters = _dial_json("lead_ad_set_chapters", {},
                                     db_path=db_path)

        def _route(payload, city):
            # Kerry-ruled priority (2026-08-31 amendment, supersedes
            # 2026-08-28: "If invites question overrides the Ad Set they
            # come from, their chapter needs to switch" — the Renick
            # case: SA ad set, Austin invites → Austin): (1) a
            # SINGLE-chapter Event Invites answer; (2) the AD SET they
            # clicked; (3) the city map. 'Both'/no answer carries no
            # override, so the ad set still decides those.
            got = route_chapter_from_payload(payload)
            if not got and isinstance(payload, dict):
                got = ad_set_chapters.get(str(payload.get("ad_set_id") or ""))
            return got or route_chapter(city, city_map)

        for c in passing:
            c["payload"] = enrich_payload(
                payloads.get(str(c["external_id"])), ad_set_names) or None
            c["chapter"] = _route(c["payload"], c.get("city"))
            # Re-submitters carry BOTH surveys' answers — stamp per-key
            # last-set timestamps so the card can tag which survey each
            # answer came from (Kerry 2026-09-01).
            if c.get("_reconversion") and c.get("payload"):
                try:
                    _d, _pv = _fetch_answer_history(
                        token, str(c["external_id"]),
                        _answer_date_keys(c["payload"]),
                        latest_conv=c["payload"].get(
                            "recent_conversion_date") or "")
                    c["payload"]["_answer_dates"] = _d
                    if _pv:
                        c["payload"]["_answers_prev"] = _pv
                    c["payload"]["_hist_v"] = 2
                except Exception as e:
                    logger.warning("Answer-history fetch failed for contact "
                                   "%s: %s", c.get("external_id"), e)
        new_ids = upsert_leads(conn, passing, city_map)
        result["queued"] = len(new_ids)
        # Backfill answer dates for re-submitters inserted before the
        # per-survey tagging existed (identified by their HS note);
        # bounded per poll.
        try:
            for r in conn.execute(
                    "SELECT l.id, l.external_id, l.payload FROM leads l "
                    "WHERE l.payload IS NOT NULL "
                    "AND l.payload NOT LIKE '%\"_hist_v\": 2%' "
                    "AND EXISTS (SELECT 1 FROM lead_notes n "
                    "            WHERE n.lead_id = l.id AND n.author = 'HS') "
                    "LIMIT 10").fetchall():
                try:
                    pl = json.loads(r["payload"])
                    _d, _pv = _fetch_answer_history(
                        token, str(r["external_id"]),
                        _answer_date_keys(pl),
                        latest_conv=pl.get("recent_conversion_date") or "")
                    pl["_answer_dates"] = _d
                    pl.pop("_answers_prev", None)
                    if _pv:
                        pl["_answers_prev"] = _pv
                    pl["_hist_v"] = 2
                    conn.execute("UPDATE leads SET payload = ? WHERE id = ?",
                                 (json.dumps(pl), r["id"]))
                except Exception:
                    logger.warning("Answer-history backfill failed for lead "
                                   "%s", r["id"], exc_info=True)
        except sqlite3.Error:
            pass
        # Badge the re-submitters with a note so the card says WHY they
        # appeared without a fresh HubSpot contact (existing since <date>).
        _reconv_ext = {str(c.get("external_id")): c for c in reconv}
        if _reconv_ext and new_ids:
            ph = ",".join("?" * len(new_ids))
            for r in conn.execute(
                    f"SELECT id, external_id FROM leads WHERE id IN ({ph})",
                    new_ids).fetchall():
                c = _reconv_ext.get(str(r["external_id"]))
                if c:
                    conn.execute(
                        "INSERT INTO lead_notes (lead_id, author, note) "
                        "VALUES (?, 'HS', ?)",
                        (r["id"],
                         "Re-submitted the FB survey — existing HubSpot "
                         f"contact since {str(c.get('_hs_created') or '')[:10]}"))
        # Apply the young-lead re-sync: replace the stored payload with
        # the fresh read (then re-enrich), fill EMPTY identity fields
        # only — a manual name fix (scoring-lead-edit) is never
        # clobbered. Chapter re-routes below via the standing self-heal.
        result["resynced"] = 0
        for r in resync_rows:
            ext = str(r["external_id"])
            if ext not in payloads:
                continue
            new_p = enrich_payload(dict(payloads[ext]), ad_set_names)
            try:
                old_p = json.loads(r["payload"]) if r.get("payload") else {}
            except Exception:
                old_p = {}
            # Manager-edited selections (Kerry 2026-09-02, the Mick
            # Hernandez card) ride across the fresh read — a re-sync
            # must never put HubSpot's stale answer back.
            new_p = apply_manual_answers(new_p, old_p)
            ident = identities.get(ext) or {}
            fills = {k: v for k, v in ident.items()
                     if v and not (r.get(k) or "").strip()}
            if new_p != old_p or fills:
                sets = ["payload = ?"]
                vals: list = [json.dumps(new_p)]
                for k, v in fills.items():
                    sets.append(f"{k} = ?")
                    vals.append(v)
                vals.append(r["id"])
                conn.execute(f"UPDATE leads SET {', '.join(sets)} "
                             f"WHERE id = ?", vals)
                result["resynced"] += 1
        # Self-heal: rows queued before payload routing / ad-id
        # extraction existed (or whose dials changed) get another look.
        for r in conn.execute(
                "SELECT id, city, chapter, payload FROM leads "
                "WHERE payload IS NOT NULL").fetchall():
            try:
                p = json.loads(r["payload"])
            except Exception:
                continue
            enriched = apply_manual_answers(
                enrich_payload(dict(p), ad_set_names), p)
            # Invites override re-route (Kerry 2026-08-31): a definitive
            # single-chapter invites answer wins even over an already-
            # routed chapter, so existing ad-set-routed leads (Renick)
            # flip on the next poll. Otherwise only NULL chapters route.
            inv = route_chapter_from_payload(enriched)
            if inv and inv != r["chapter"]:
                got = inv
            else:
                got = None if r["chapter"] else _route(enriched, r["city"])
            if enriched != p or got:
                conn.execute(
                    "UPDATE leads SET payload = ?, "
                    "chapter = COALESCE(?, chapter) WHERE id = ?",
                    (json.dumps(enriched), got, r["id"]))
        # Every lead gets a REAL customer_id (Kerry 2026-08-28) — link
        # by email or create through the save_items resolver. Runs each
        # poll so a name fix (or a later signup) links retroactively.
        for r in conn.execute(
                "SELECT * FROM leads WHERE customer_id IS NULL").fetchall():
            cid = _link_or_create_customer(conn, dict(r))
            if cid:
                conn.execute("UPDATE leads SET customer_id = ? WHERE id = ?",
                             (cid, r["id"]))
        # Prospect name sync: a lead-name correction (scoring-lead-edit)
        # must reach the purchase-less prospect the lead created — e.g.
        # Facebook handed over "Marcus | Real Estate" from a business
        # page name. Never touches a customer with purchase history.
        for r in conn.execute(
                "SELECT l.customer_id AS cid, l.first_name AS fn, "
                "       l.last_name AS ln "
                "FROM leads l JOIN customers c ON c.customer_id = l.customer_id "
                "WHERE l.first_name IS NOT NULL AND l.last_name IS NOT NULL "
                "AND (COALESCE(c.first_name, '') != l.first_name "
                "     OR COALESCE(c.last_name, '') != l.last_name) "
                "AND NOT EXISTS (SELECT 1 FROM items i "
                "                WHERE i.customer_id = c.customer_id)"
                ).fetchall():
            conn.execute(
                "UPDATE customers SET first_name = ?, last_name = ? "
                "WHERE customer_id = ?", (r["fn"], r["ln"], r["cid"]))
        # Conversion auto-detect (Kerry 2026-08-31: "if they become a
        # member or first play an event, there should be an auto update
        # to their lead card"). Two real-world outcomes, membership
        # outranking event: a membership purchase (or a
        # customer_memberships row — manual grants count) tags 'Became
        # member'; any other active purchase tags 'Registered event'.
        # Both flip status to converted and stop the 48h clock. Never
        # resurrects a dismissed lead; idempotent; a Registered-event
        # lead upgrades to Became member when the membership lands.
        try:
            conn.execute(
                "UPDATE leads SET status = 'converted', "
                "tag = 'Became member', "
                "touched_at = COALESCE(touched_at, datetime('now')), "
                "converted_at = COALESCE(converted_at, datetime('now')) "
                "WHERE status != 'dismissed' "
                "AND (status != 'converted' "
                "     OR COALESCE(tag, '') != 'Became member') "
                "AND customer_id IS NOT NULL "
                "AND (EXISTS (SELECT 1 FROM customer_memberships m "
                "             WHERE m.customer_id = leads.customer_id) "
                "     OR EXISTS (SELECT 1 FROM items i "
                "                WHERE i.customer_id = leads.customer_id "
                "                AND i.transaction_status = 'active' "
                "                AND UPPER(i.item_name) LIKE '%MEMBERSHIP%'))")
            _ph = ",".join("?" * len(PLACEHOLDER_MERCHANTS))
            conn.execute(
                "UPDATE leads SET status = 'converted', "
                "tag = 'Registered event', "
                "touched_at = COALESCE(touched_at, datetime('now')), "
                "converted_at = COALESCE(converted_at, datetime('now')) "
                "WHERE status != 'dismissed' "
                "AND COALESCE(tag, '') != 'Became member' "
                "AND (status != 'converted' "
                "     OR COALESCE(tag, '') != 'Registered event') "
                "AND customer_id IS NOT NULL "
                "AND EXISTS (SELECT 1 FROM items i "
                "            WHERE i.customer_id = leads.customer_id "
                "            AND i.transaction_status = 'active' "
                f"           AND i.merchant NOT IN ({_ph}) "
                "            AND UPPER(i.item_name) NOT LIKE '%MEMBERSHIP%')",
                PLACEHOLDER_MERCHANTS)
            # Heal (v2.277.1): leads the OLD rule auto-converted off a
            # placeholder row revert to the queue — auto-tagged rows only
            # ('Registered event'), with no REAL purchase and no
            # membership. touched fields stay as they are (a manual touch
            # that preceded the wrong flip must survive).
            conn.execute(
                "UPDATE leads SET status = 'new', tag = NULL "
                "WHERE status = 'converted' "
                "AND COALESCE(tag, '') = 'Registered event' "
                "AND customer_id IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM items i "
                "                WHERE i.customer_id = leads.customer_id "
                "                AND i.transaction_status = 'active' "
                f"               AND i.merchant NOT IN ({_ph})) "
                "AND NOT EXISTS (SELECT 1 FROM customer_memberships m "
                "                WHERE m.customer_id = leads.customer_id)",
                PLACEHOLDER_MERCHANTS)
        except sqlite3.Error as e:
            logger.warning("Lead conversion auto-detect failed: %s", e)
        # No-loop auto-dismiss (Kerry 2026-09-01: "If they're not wanting
        # communication (No Loop) then they should probably go to bottom
        # dismissed"). Runs every poll, idempotent.
        try:
            dismiss_no_loop_leads(conn)
        except Exception:
            logger.warning("No-loop auto-dismiss failed", exc_info=True)
        # Backfill: prospects created before the acquisition_source fix
        # carry the resolver's 'godaddy' default — purchase-less
        # lead-linked customers are Facebook acquisitions.
        conn.execute(
            "UPDATE customers SET acquisition_source = 'facebook_lead' "
            "WHERE acquisition_source = 'godaddy' "
            "AND customer_id IN (SELECT customer_id FROM leads "
            "                    WHERE customer_id IS NOT NULL) "
            "AND NOT EXISTS (SELECT 1 FROM items i "
            "                WHERE i.customer_id = customers.customer_id)")
        for lid in new_ids:
            lead = dict(conn.execute(
                "SELECT * FROM leads WHERE id = ?", (lid,)).fetchone())
            if _send_lead_ping(lead, db_path=db_path):
                conn.execute("UPDATE leads SET notified_at = datetime('now') "
                             "WHERE id = ?", (lid,))
                result["notified"] += 1
        conn.commit()

    # RSVP → lead-note bridge sweep (own connection, after the poll's
    # writes commit): backfills any RSVP the inbox-time bridge missed.
    try:
        sync_lead_rsvp_notes(db_path=db_path)
    except Exception:
        logger.warning("Lead RSVP-note sweep failed", exc_info=True)

    # Advance the watermark to the newest createdate seen (dedup by
    # external_id makes the re-read of boundary contacts harmless).
    newest = max((c.get("arrived_at") or "" for c in contacts), default="")
    if newest:
        try:
            db.set_app_setting("leads_hubspot_watermark", newest)
        except Exception:
            logger.warning("Lead watermark update failed", exc_info=True)
    newest_rc = max((c.get("arrived_at") or "" for c in reconv), default="")
    if newest_rc:
        try:
            db.set_app_setting(RECONV_WATERMARK_KEY, newest_rc)
        except Exception:
            logger.warning("Reconversion watermark update failed", exc_info=True)
    return result


def get_leads(status: str = "", limit: int = 200,
              db_path: str | Path | None = None) -> list[dict]:
    from . import database as db
    from .timezone_utils import now_central
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        try:
            from .campaigns import link_leads_to_campaigns
            if link_leads_to_campaigns(conn):
                conn.commit()
        except Exception:
            logger.warning("campaign auto-link failed", exc_info=True)
        # event_regs: REAL event registrations off the items table
        # (Kerry 2026-09-04). The tag can only say one thing and
        # membership outranks event, so a member who also plays was
        # invisible in the event count. Same predicate the conversion
        # auto-detect uses.
        _ph = ",".join("?" * len(PLACEHOLDER_MERCHANTS))
        q = ("SELECT l.*, c.name AS campaign_name, "
             "(SELECT COUNT(*) FROM items i "
             " WHERE i.customer_id = l.customer_id "
             " AND COALESCE(i.transaction_status, 'active') = 'active' "
             " AND i.parent_item_id IS NULL "
             f" AND i.merchant NOT IN ({_ph}) "
             " AND UPPER(COALESCE(i.item_name, '')) NOT LIKE '%MEMBERSHIP%'"
             ") AS event_regs "
             "FROM leads l "
             "LEFT JOIN lead_campaigns c ON c.id = l.campaign_id "
             "WHERE l.merged_into IS NULL")
        params: tuple = tuple(PLACEHOLDER_MERCHANTS)
        if status:
            q += " AND l.status = ?"
            params = params + (status,)
        q += " ORDER BY COALESCE(l.arrived_at, l.first_seen_at) DESC LIMIT ?"
        rows = [dict(r) for r in conn.execute(q, params + (limit,)).fetchall()]
    # "Existing customer" badge = the lead matches a customer with REAL
    # purchase history — NOT the prospect row the lead pass itself
    # created (Kerry 2026-08-28: "They are not members at all").
    cids = [r["customer_id"] for r in rows if r.get("customer_id")]
    with_history: set = set()
    if cids:
        ph = ",".join("?" * len(cids))
        with db._connect(db_path) as conn:
            # 'customer' badge = REAL purchase history only (Kerry
            # 2026-09-01, the Daniel Garza case: a roster-import identity
            # shell is not a customer) — placeholder rows excluded.
            _php = ",".join("?" * len(PLACEHOLDER_MERCHANTS))
            with_history = {x[0] for x in conn.execute(
                f"SELECT DISTINCT customer_id FROM items "
                f"WHERE customer_id IN ({ph}) "
                f"AND transaction_status = 'active' "
                f"AND merchant NOT IN ({_php})",
                cids + list(PLACEHOLDER_MERCHANTS))}
    # Notes log (#361): newest first, attached per lead
    notes_by_lead: dict = {}
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        for n in conn.execute(
                "SELECT lead_id, author, note, created_at FROM lead_notes "
                "ORDER BY id DESC"):
            notes_by_lead.setdefault(n["lead_id"], []).append(
                {"author": n["author"], "note": n["note"],
                 "created_at": n["created_at"]})
    now = now_central()
    for r in rows:
        r["notes_log"] = notes_by_lead.get(r["id"], [])
        r["has_history"] = r.get("customer_id") in with_history
        try:
            r["payload"] = json.loads(r["payload"]) if r.get("payload") else None
        except Exception:
            r["payload"] = None
        r["days_since_arrival"] = None
        stamp = (r.get("arrived_at") or r.get("first_seen_at") or "")[:10]
        try:
            from datetime import date
            y, m, d = (int(x) for x in stamp.split("-"))
            # arrived_at is UTC while `now` is Central — a lead arriving
            # after 7 PM CT carries tomorrow's UTC date, which made a
            # brand-new lead read "-1d". Clamp: never younger than today.
            r["days_since_arrival"] = max(0, (now.date() - date(y, m, d)).days)
        except Exception:
            pass
    return rows


def get_lead_export_rows(chapter: str,
                         db_path: str | Path | None = None) -> list[dict]:
    """First/Last/Email rows for one chapter's invite-list CSV (Kerry
    2026-08-28, handicap-export style). Membership criteria: the lead's
    INVITATIONS opt-in answer ('yes_for_<chapter>' or 'yes_for_both');
    a lead with no answer falls back to its routed chapter. Excluded:
    dismissed leads, 'Bad contact'/'Not now'/'Too expensive' tags,
    rows without email, and any explicit invitations opt-OUT (an
    answer starting with 'no' — Kerry 2026-08-31: those that don't
    want invites never go on the CSV)."""
    want_sa = chapter == "San Antonio"
    out = []
    for l in get_leads(limit=1000, db_path=db_path):
        if l.get("status") == "dismissed":
            continue
        if (l.get("tag") or "") in ("Bad contact", "Not now", "Too expensive"):
            continue
        email = (l.get("email") or "").strip()
        if not email:
            continue
        loop_val = ""
        for k, v in (l.get("payload") or {}).items():
            if ("stay_in_the_loop" in k.lower() or "loop" in k.lower()) \
                    and isinstance(v, str):
                loop_val = v.lower()
                break
        if loop_val:
            # Explicit opt-out ('no', or any future 'no_-_…' variant)
            # never rides the routed-chapter fallback — an answer that
            # isn't a clear yes stays off the invite list.
            if loop_val.startswith("no"):
                continue
            ok = (loop_val == "yes_for_both"
                  or (want_sa and "san_antonio" in loop_val)
                  or (not want_sa
                      and "austin" in loop_val.replace("austin_sa", "")))
        else:
            ok = l.get("chapter") == chapter
        if ok:
            out.append({"first_name": l.get("first_name") or "",
                        "last_name": l.get("last_name") or "",
                        "email": email})
    out.sort(key=lambda r: (r["last_name"].lower(), r["first_name"].lower()))
    return out


# ── 48-HOUR OUTREACH ALARM (Kerry 2026-09-03) ────────────────────────
# "Need a timestamp with alarm set when I click Texted or Emailed for
# someone for the first time. That should auto set a 48 hour alarm that
# resets when I change status or add a note, which probably signifies
# that there's been a response."
#
# Tagging an OUTREACH action stamps outreach_at and sets follow_up_at to
# +2 days, which rides the follow-up rails that already exist: the ⏰
# chip, the FOLLOW-UPS DUE section at the top of the queue, and the
# due-day email ping (#370). No second notification system.
#
# The alarm CLEARS on a response signal — any status change, any tag
# that is not itself outreach, or any note that is not system
# bookkeeping. A note from a person, a GG RSVP, or a HubSpot
# re-submission all mean the lead did something; only author 'auto'
# (campaign set, selections edited) is bookkeeping and leaves it armed.
#
# "For the first time" = the alarm only arms when no follow-up date is
# already pending, so re-tagging never pushes the date out, and a date
# Kerry set BY HAND (outreach_at NULL) is never touched by any of this.
DEFAULT_OUTREACH_TAGS = ["Texted", "Sent email", "Left VM"]
OUTREACH_FOLLOWUP_DAYS = 2                    # 48 hours
BOOKKEEPING_NOTE_AUTHORS = {"auto"}           # never counts as a response


def get_outreach_tags(db_path: str | Path | None = None) -> list[str]:
    """Tags that START the 48-hour clock; `lead_outreach_tags` dial over
    the defaults (Kerry named Texted and Sent email; Left VM is the same
    "reached out, now waiting" case, so it ships armed too)."""
    opts = _dial_json("lead_outreach_tags", [], db_path=db_path)
    return [str(o) for o in opts] if opts else list(DEFAULT_OUTREACH_TAGS)


def _stamp_replied(conn, lead_id: int, tag: str | None = None,
                   author: str | None = None) -> None:
    """Record the FIRST time a human wrote back (mailbox #412).

    Called from the two places a reply is actually observed — a note
    from a person, or one of the REPLY_TAGS. COALESCE keeps the first
    one: a later reply must not move the date, and nothing clears it.

    This exists because the conversion auto-detect overwrites `tag`, so
    by the time a lead converts there is no other trace left that they
    ever answered.
    """
    if author is not None:
        if (author or "").strip().lower() in REPLY_EXCLUDED_NOTE_AUTHORS:
            return
    elif (tag or "") not in REPLY_TAGS:
        return
    conn.execute(
        "UPDATE leads SET replied_at = COALESCE(replied_at, datetime('now')) "
        "WHERE id = ?", (lead_id,))


def _clear_outreach_alarm(conn, lead_id: int) -> bool:
    """Disarm the AUTO alarm (outreach_at NOT NULL). A hand-set
    follow-up date is left exactly as Kerry set it."""
    cur = conn.execute(
        "UPDATE leads SET follow_up_at = NULL, follow_up_notified_for = NULL, "
        "outreach_at = NULL WHERE id = ? AND outreach_at IS NOT NULL",
        (lead_id,))
    return bool(cur.rowcount)


# Tags that ALWAYS restart the 48-hour clock, even when one is already
# pending (Kerry 2026-09-03: "Need something like a Followed Up option
# that resets the timer"). The other outreach tags arm only on a FIRST
# touch, so re-tapping Texted on a lead whose alarm already fired did
# nothing at all — the chip just stayed red while Kerry kept working
# the person. This is the explicit "I reached out again" action, and
# being explicit is what makes overriding the pending date safe:
# a mis-tap on Texted must never push a lead out of sight, but choosing
# Followed up says exactly that.
DEFAULT_REARM_TAGS = ["Followed up"]


def get_rearm_tags(db_path: str | Path | None = None) -> list[str]:
    opts = _dial_json("lead_rearm_tags", [], db_path=db_path)
    return [str(o) for o in opts] if opts else list(DEFAULT_REARM_TAGS)


# Kerry-editable via the lead_tag_options dial (JSON list of strings);
# these are the defaults. Tags are dispositions, orthogonal to the
# new/touched/converted/dismissed pipeline.
DEFAULT_TAG_OPTIONS = ["Left VM", "Texted", "Sent email", "Followed up",
                       "No answer",
                       "Call back", "Interested", "Coming to event",
                       "Too expensive", "Days don't work", "Not now",
                       "Bad contact", "Registered event", "Became member"]

# Tags that deactivate the lead on selection (Kerry 2026-08-31, the
# Stetson Aaron case: "Too expensive right now" — don't delete, just
# deactivate; "Bad contact should also deactivate"). Selecting one flips
# status to dismissed: the row and its notes stay, it drops out of the
# active queue and the invite-list CSV, and Restore brings it back.
DEACTIVATING_TAGS = {"Too expensive", "Bad contact"}


def get_tag_options(db_path: str | Path | None = None) -> list[str]:
    opts = _dial_json("lead_tag_options", [], db_path=db_path)
    return [str(o) for o in opts] if opts else list(DEFAULT_TAG_OPTIONS)


def set_lead_tag(lead_id: int, tag: str,
                 db_path: str | Path | None = None,
                 author: str = "") -> dict:
    """Set (or clear with '') a lead's disposition tag. Tagging a NEW
    lead marks it touched — a tag means somebody acted on it.

    `author` records WHO (platform-claude #405): touched_by was NULL on
    every row because the Touched button prompts for a name but Kerry
    works the queue by tagging instead, and the tag path never captured
    one. That is the data the chapter-manager compensation model needs,
    so it is filled automatically from the session rather than by asking
    him for a name he already implied by being logged in."""
    from . import database as db
    tag = (tag or "").strip()
    if tag and tag not in get_tag_options(db_path):
        return {"error": f"unknown tag {tag!r} — options: "
                         f"{get_tag_options(db_path)} (edit the "
                         "lead_tag_options dial to add one)"}
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        row = conn.execute("SELECT id, status FROM leads WHERE id = ?",
                           (lead_id,)).fetchone()
        if not row:
            return {"error": f"lead {lead_id} not found"}
        if tag in DEACTIVATING_TAGS and row["status"] != "converted":
            # Deactivate, never delete: converted leads keep their status
            # (the tag still records the disposition).
            conn.execute(
                "UPDATE leads SET tag = ?, status = 'dismissed', "
                "touched_at = COALESCE(touched_at, datetime('now')) "
                "WHERE id = ?", (tag, lead_id))
        elif tag and row["status"] == "new":
            conn.execute(
                "UPDATE leads SET tag = ?, status = 'touched', "
                "touched_at = COALESCE(touched_at, datetime('now')), "
                "touched_by = COALESCE(NULLIF(touched_by, ''), NULLIF(?, '')) "
                "WHERE id = ?", (tag, (author or "").strip(), lead_id))
        else:
            conn.execute("UPDATE leads SET tag = ? WHERE id = ?",
                         (tag or None, lead_id))
        # 48-hour outreach alarm (Kerry 2026-09-03).
        from datetime import timedelta
        from .timezone_utils import now_central
        alarm = None
        rearm = bool(tag) and tag in get_rearm_tags(db_path)
        if tag and (rearm or tag in get_outreach_tags(db_path)):
            pending = conn.execute(
                "SELECT follow_up_at FROM leads WHERE id = ?",
                (lead_id,)).fetchone()["follow_up_at"]
            # "For the first time" for the ordinary outreach tags; a
            # RE-ARM tag restarts the clock whatever is pending.
            if rearm or not pending:
                now = now_central()
                due = (now + timedelta(days=OUTREACH_FOLLOWUP_DAYS)
                       ).strftime("%Y-%m-%d")
                # outreach_at is stored UTC like every other datetime
                # column (the UI's fmtNoteTime converts to Central); the
                # note text below is written in Central for the human.
                conn.execute(
                    "UPDATE leads SET outreach_at = datetime('now'), "
                    "follow_up_at = ?, follow_up_notified_for = NULL "
                    "WHERE id = ?", (due, lead_id))
                _md = (f"{due[5:7].lstrip('0')}/{due[8:10].lstrip('0')}")
                # A re-arm can replace a date Kerry set BY HAND, so the
                # note says what it replaced — nothing deliberate
                # disappears without a record of it.
                _was = ""
                if rearm and pending and pending != due:
                    _was = (f" (was {pending[5:7].lstrip('0')}"
                            f"/{pending[8:10].lstrip('0')})")
                _verb = "reset to" if (rearm and pending) else "set for"
                conn.execute(
                    "INSERT INTO lead_notes (lead_id, author, note) "
                    "VALUES (?, 'auto', ?)",
                    (lead_id, f"{tag} {now.strftime('%-m/%-d, %-I:%M %p')} "
                              f"— 48-hour follow-up {_verb} {_md}{_was}"))
                alarm = due
        elif tag:
            # Any non-outreach tag is a disposition he only reaches for
            # after hearing something (Interested, Call back, Not now...).
            _clear_outreach_alarm(conn, lead_id)
        _stamp_replied(conn, lead_id, tag=tag)
        conn.commit()
    return {"id": lead_id, "tag": tag or None, "follow_up_at": alarm,
            "ok": True}


def set_lead_followup(lead_id: int, date: str,
                      db_path: str | Path | None = None) -> dict:
    """Set (or clear with '') a lead's follow-up date (mailbox #365).
    A future date SNOOZES the lead (drops from the active view); on or
    before today it resurfaces under FOLLOW-UPS DUE at the top."""
    import re as _re
    from . import database as db
    date = (date or "").strip()
    if date and not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return {"error": f"bad date {date!r} — need YYYY-MM-DD or blank"}
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        if not conn.execute("SELECT 1 FROM leads WHERE id = ?",
                            (lead_id,)).fetchone():
            return {"error": f"lead {lead_id} not found"}
        conn.execute("UPDATE leads SET follow_up_at = ? WHERE id = ?",
                     (date or None, lead_id))
        conn.commit()
    return {"id": lead_id, "follow_up_at": date or None, "ok": True}


def sync_lead_rsvp_notes(db_path: str | Path | None = None) -> dict:
    """Bridge GG RSVPs onto lead cards (Kerry 2026-08-31, the Alex
    Porter case: a lead RSVPing — even Not Playing — is a response
    signal worth surfacing). Each RSVP matching a lead becomes ONE
    automatic note (author 'GG', stamped with the RSVP's received
    time), which promotes the lead to RESPONDED under the
    notes-count-as-response rule. Matches by customer_id first
    (rule 6), then by email. Idempotent: dedup on exact note text per
    lead, so re-runs and GG re-sends are no-ops; a changed answer
    (Not Playing → Playing) is new text and gets its own note."""
    from . import database as db
    added = 0
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        try:
            rows = conn.execute(
                """SELECT DISTINCT l.id AS lead_id, r.response,
                          COALESCE(r.matched_event, r.event_identifier,
                                   r.gg_event_name) AS ev,
                          COALESCE(r.received_at, r.created_at) AS at
                   FROM rsvps r JOIN leads l
                     ON (r.customer_id IS NOT NULL
                         AND r.customer_id = l.customer_id)
                     OR (COALESCE(r.player_email, '') != ''
                         AND LOWER(r.player_email)
                             = LOWER(COALESCE(l.email, '')))""").fetchall()
        except Exception:
            return {"rsvp_notes_added": 0}   # rsvps table absent (tests)
        for r in rows:
            resp = "Playing" if (r["response"] or "").upper() == "PLAYING" \
                else "Not Playing"
            note = f"RSVP'd {resp} — {r['ev'] or 'event'}"
            if conn.execute("SELECT 1 FROM lead_notes WHERE lead_id = ? "
                            "AND note = ?", (r["lead_id"], note)).fetchone():
                continue
            at = (r["at"] or "").replace("T", " ").replace("Z", "")[:19]
            conn.execute(
                "INSERT INTO lead_notes (lead_id, author, note, created_at) "
                "VALUES (?, 'GG', ?, COALESCE(?, datetime('now')))",
                (r["lead_id"], note, at or None))
            added += 1
        if added:
            conn.commit()
    return {"rsvp_notes_added": added}


def edit_lead_identity(lead_id: int, first_name: str | None = None,
                       last_name: str | None = None,
                       db_path: str | Path | None = None) -> dict:
    """Manager name fix from the Lead Center UI (Kerry 2026-08-31:
    "Need ability to edit names too" — FB forms often hand over a
    single name; the email local-part usually carries the surname).
    Updates the lead and immediately syncs the purchase-less prospect
    customer the lead created — mirroring the poll's prospect-name
    sync, and like it NEVER touching a customer with purchase
    history."""
    from . import database as db
    updates = {}
    if first_name is not None and first_name.strip():
        updates["first_name"] = first_name.strip()
    if last_name is not None:
        updates["last_name"] = last_name.strip() or None
    if not updates:
        return {"error": "nothing to update"}
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        row = conn.execute("SELECT * FROM leads WHERE id = ?",
                           (lead_id,)).fetchone()
        if not row:
            return {"error": f"lead {lead_id} not found"}
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE leads SET {sets} WHERE id = ?",
                     (*updates.values(), lead_id))
        fn = updates.get("first_name", row["first_name"])
        ln = updates.get("last_name", row["last_name"])
        synced = False
        cid = row["customer_id"]
        if cid and fn and ln:
            has_items = conn.execute(
                "SELECT 1 FROM items WHERE customer_id = ? LIMIT 1",
                (cid,)).fetchone()
            if not has_items:
                conn.execute(
                    "UPDATE customers SET first_name = ?, last_name = ? "
                    "WHERE customer_id = ?", (fn, ln, cid))
                synced = True
        conn.commit()
    return {"id": lead_id, "first_name": fn, "last_name": ln,
            "customer_synced": synced, "ok": True}


def add_lead_note(lead_id: int, note: str, author: str = "",
                  db_path: str | Path | None = None) -> dict:
    """Append to a lead's notes log (#361). Author is a short name or
    initial; timestamped server-side."""
    note = (note or "").strip()
    if not note:
        return {"error": "note text required"}
    from . import database as db
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        if not conn.execute("SELECT 1 FROM leads WHERE id = ?",
                            (lead_id,)).fetchone():
            return {"error": f"lead {lead_id} not found"}
        conn.execute(
            "INSERT INTO lead_notes (lead_id, author, note) VALUES (?,?,?)",
            (lead_id, (author or "").strip() or None, note))
        # A note means something happened (Kerry 2026-09-03: adding a note
        # "probably signifies that there's been a response") — disarm the
        # 48-hour alarm. Bookkeeping notes leave it armed.
        cleared = False
        if (author or "").strip().lower() not in BOOKKEEPING_NOTE_AUTHORS:
            cleared = _clear_outreach_alarm(conn, lead_id)
        _stamp_replied(conn, lead_id, author=author)
        conn.commit()
    return {"lead_id": lead_id, "alarm_cleared": cleared, "ok": True}


def mark_lead(lead_id: int, status: str, touched_by: str = "",
              notes: str = "", db_path: str | Path | None = None) -> dict:
    """Status moves + corrections (Kerry 2026-08-28: undo converted,
    change touched_by/notes after the fact).

      new        — full undo/restore: clears touched_at + touched_by
      touched    — mark touched; ALSO the undo of converted (keeps the
                   original touched stamp)
      converted / dismissed — as named
      edit       — no status change; just update touched_by and/or notes
    A non-empty touched_by/notes always overwrites the stored value."""
    if status not in ("new", "touched", "converted", "dismissed", "edit"):
        return {"error": f"invalid status {status!r}"}
    from . import database as db
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        row = conn.execute("SELECT id, status FROM leads WHERE id = ?",
                           (lead_id,)).fetchone()
        if not row:
            return {"error": f"lead {lead_id} not found"}
        if status == "edit":
            conn.execute(
                "UPDATE leads SET touched_by = COALESCE(NULLIF(?, ''), "
                "touched_by), notes = COALESCE(NULLIF(?, ''), notes) "
                "WHERE id = ?", (touched_by, notes, lead_id))
            status = row["status"]
        elif status == "new":
            conn.execute(
                "UPDATE leads SET status = 'new', touched_at = NULL, "
                "touched_by = NULL, notes = COALESCE(NULLIF(?, ''), notes) "
                "WHERE id = ?", (notes, lead_id))
        elif status in ("touched", "converted"):
            conn.execute(
                "UPDATE leads SET status = ?, touched_at = COALESCE(touched_at, "
                "datetime('now')), touched_by = COALESCE(NULLIF(?, ''), "
                "touched_by), notes = COALESCE(NULLIF(?, ''), notes) "
                "WHERE id = ?", (status, touched_by, notes, lead_id))
            if status == "converted":
                # Conversion date drives the 30-day trailing CPP/CPMem
                # (mailbox #391); first conversion stamp wins.
                conn.execute(
                    "UPDATE leads SET converted_at = COALESCE(converted_at, "
                    "datetime('now')) WHERE id = ?", (lead_id,))
        else:
            conn.execute(
                "UPDATE leads SET status = ?, notes = COALESCE(NULLIF(?, ''), "
                "notes) WHERE id = ?", (status, notes, lead_id))
        # A real status change disarms the 48-hour alarm (Kerry
        # 2026-09-03). Re-marking the status it already had changed
        # nothing, so it leaves the clock running.
        alarm_cleared = False
        if status != row["status"]:
            alarm_cleared = _clear_outreach_alarm(conn, lead_id)
        conn.commit()
    return {"id": lead_id, "status": status, "alarm_cleared": alarm_cleared,
            "ok": True}


# ── Manager-edited selections (Kerry 2026-09-02) ─────────────────────
# "I need to be able to edit Lead selections" — Mick Hernandez lives in
# SA, plays Austin occasionally, and asked off the Austin invite list;
# his FB answer still said "Both". The three survey answers (+ city and
# chapter) are editable from the card. Edits live in payload["_manual"]
# and are re-applied over every HubSpot re-sync / self-heal pass, so a
# young lead's 48-hour re-fetch can't put the stale answer back.
# Routing follows the edited Invitations answer exactly like a fresh
# submission would (single-chapter answer → that chapter).
MANUAL_ANSWER_KEYS = {
    "availability": "can_you_play_tuesdays_or_saturdays",
    "importance": "which_is_most_important_to_you",
    "invitations": LOOP_QUESTION_KEY,
}
# Raw Facebook option values (exact — every decoder/badge/CSV rule
# keys on these strings) with their card labels.
MANUAL_ANSWER_OPTIONS = {
    "availability": [
        ("yes_-_i_can_play_both_tuesdays_or_saturdays", "Both (Tue + Sat)"),
        ("yes_-_i_can_play_tuesdays", "Tuesdays only"),
        ("yes_-_i_can_play_saturdays", "Saturdays only"),
        ("neither_-_but_i'm_still_interested", "Neither, still interested"),
    ],
    "importance": [
        ("all_of_it!_-_enjoy_a_well-rounded_experience_with_top-notch_"
         "courses,_fair_competition,_and_meaningful_connections", "All of it"),
        ("golf_-_explore_a_variety_of_courses_and_play_as_much_as_possible",
         "Golf"),
        ("competition_-_test_yourself_in_individual_&_team_formats_with_"
         "fairness_for_all_skill_levels", "Competition"),
        ("community_-_connect_with_fellow_golfers,_forge_new_friendships,"
         "_and_foster_camaraderie", "Community"),
    ],
    "invitations": [
        ("yes_for_both", "Both chapters"),
        ("yes_for_san_antonio", "San Antonio only"),
        ("yes_for_austin", "Austin only"),
        ("no", "No invitations"),
    ],
}


def get_answer_options() -> dict:
    """{field: {question_key, options: [{value, label}]}} for the UI."""
    return {f: {"key": MANUAL_ANSWER_KEYS[f],
                "options": [{"value": v, "label": lbl}
                            for v, lbl in MANUAL_ANSWER_OPTIONS[f]]}
            for f in MANUAL_ANSWER_KEYS}


def apply_manual_answers(payload: dict | None,
                         previous: dict | None = None) -> dict | None:
    """Overlay payload['_manual'] (carried from `previous` when the new
    payload lacks it) onto the answer keys. Idempotent."""
    if not isinstance(payload, dict):
        return payload
    manual = payload.get("_manual")
    meta = payload.get("_manual_meta")
    if not isinstance(manual, dict) and isinstance(previous, dict):
        manual = previous.get("_manual")
        meta = previous.get("_manual_meta")
    if not isinstance(manual, dict) or not manual:
        return payload
    payload["_manual"] = dict(manual)
    if isinstance(meta, dict):
        payload["_manual_meta"] = dict(meta)
    for k, v in manual.items():
        payload[k] = v
    return payload


# Where a lead came from (#420 §6, Kerry: "Leads shouldn't only cover
# Facebook campaigns. Should also be able to add manual leads."). The
# Lead Center was a Facebook campaign screen; it is now a lead system.
# `meta` is the polled Facebook pipe, everything else is entered by hand.
# Referral leads cost $0, which is worth seeing next to the paid CPL.
MANUAL_LEAD_SOURCES = {
    "referral":  "Referral",
    "organic":   "Organic",
    "in_person": "Met in person",
    "partner":   "Partner",
    "manual":    "Manual",
}


def add_manual_lead(first_name: str, last_name: str = "", phone: str = "",
                    email: str = "", source: str = "manual",
                    chapter: str = "", city: str = "",
                    answers: dict | None = None, note: str = "",
                    referred_by: str = "", author: str = "",
                    db_path: str | Path | None = None) -> dict:
    """Add a lead nobody's ad campaign produced.

    Kannon Brown came off Robert's post, Kevin Ponder was met in person,
    Rick Billeaud and Joey Difrank came from Logan. These are TGF's
    cheapest acquisitions and the only channel with no instrumentation at
    all — before this they had no record anywhere.

    THE DESIGN WRINKLE (#420 §6): a manual lead has no survey answers,
    and Availability / Importance / Invitations are exactly what drive
    preset selection, event choice, cadence order, owner naming and the
    chapter callout. So they are OPTIONAL here and captured when known —
    Kerry usually learns half of it in the conversation that produced the
    lead. What he does not know stays genuinely blank, and the preset
    picker falls back the same way it does for a survey nobody finished,
    rather than being quietly defaulted to something that reads as fact.
    """
    import re

    from . import database as db
    from .timezone_utils import now_central

    first_name = (first_name or "").strip()
    if not first_name:
        return {"error": "a first name is required"}
    source = (source or "manual").strip().lower()
    if source not in MANUAL_LEAD_SOURCES:
        return {"error": f"source must be one of "
                         f"{sorted(MANUAL_LEAD_SOURCES)}, got {source!r}"}
    phone = (phone or "").strip()
    email = (email or "").strip()
    if not phone and not email:
        return {"error": "a phone or an email is required — a lead with "
                         "no way to reach them is not a lead"}
    chapter = (chapter or "").strip()
    if chapter and chapter not in ("San Antonio", "Austin"):
        return {"error": "chapter must be San Antonio, Austin, or blank"}

    answers = {k: v for k, v in (answers or {}).items() if v}
    for f, v in answers.items():
        if f not in MANUAL_ANSWER_KEYS:
            return {"error": f"unknown field {f!r}"}
        if v not in {o for o, _ in MANUAL_ANSWER_OPTIONS[f]}:
            return {"error": f"{f}: {v!r} is not a survey option"}

    now = now_central()
    payload = {MANUAL_ANSWER_KEYS[f]: v for f, v in answers.items()}
    payload["_manual_entry"] = {
        "by": (author or "manager").strip(),
        "at": now.strftime("%Y-%m-%d %H:%M"),
        "source": source,
    }
    if referred_by.strip():
        # The relationship, recorded as text until the referral model is
        # ratified (#413/#416). Deliberately NOT written to
        # customers.referred_by_customer_id, which today means "I paid
        # for this person's spot" — a different sentence.
        payload["_referred_by"] = referred_by.strip()

    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        # One person, one lead row. A manual add must not mint a second
        # record for somebody the Facebook pipe already delivered.
        dupe = None
        if phone:
            digits = re.sub(r"\D", "", phone)[-10:]
            if digits:
                for r in conn.execute(
                        "SELECT id, first_name, last_name, phone FROM leads "
                        "WHERE phone IS NOT NULL AND phone != '' "
                        "AND merged_into IS NULL"):
                    if re.sub(r"\D", "", r["phone"] or "")[-10:] == digits:
                        dupe = r
                        break
        if dupe is None and email:
            dupe = conn.execute(
                "SELECT id, first_name, last_name, phone FROM leads "
                "WHERE LOWER(TRIM(COALESCE(email,''))) = ? "
                "AND merged_into IS NULL", (email.lower(),)).fetchone()
        if dupe:
            return {"error": f"lead {dupe['id']} is already "
                             f"{(dupe['first_name'] or '').strip()} "
                             f"{(dupe['last_name'] or '').strip()}".strip()
                             + " with that contact — open that card instead",
                    "existing_lead_id": dupe["id"]}

        cur = conn.execute(
            "INSERT INTO leads (source, external_id, first_name, last_name, "
            " email, phone, city, chapter, source_label, arrived_at, "
            " status, payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?, 'new', ?)",
            (source, f"manual-{now.strftime('%Y%m%d%H%M%S')}-"
                     f"{first_name.lower()[:8]}",
             first_name, (last_name or "").strip() or None,
             email or None, phone or None, (city or "").strip() or None,
             chapter or None, MANUAL_LEAD_SOURCES[source],
             now.strftime("%Y-%m-%d %H:%M:%S"), json.dumps(payload)))
        lead_id = cur.lastrowid
        why = MANUAL_LEAD_SOURCES[source].lower()
        if referred_by.strip():
            why = f"referred by {referred_by.strip()}"
        conn.execute(
            "INSERT INTO lead_notes (lead_id, author, note) VALUES (?,?,?)",
            (lead_id, "auto",
             f"Added by hand ({why}) {now.strftime('%-m/%-d, %-I:%M %p')}"))
        if note.strip():
            conn.execute(
                "INSERT INTO lead_notes (lead_id, author, note) VALUES (?,?,?)",
                (lead_id, (author or "K").strip()[:12], note.strip()))
        conn.commit()
    return {"ok": True, "lead_id": lead_id, "source": source,
            "chapter": chapter or None,
            "answers_captured": sorted(answers),
            "answers_missing": sorted(set(MANUAL_ANSWER_KEYS) - set(answers))}


def set_lead_answers(lead_id: int, answers: dict | None = None,
                     city: str | None = None, chapter: str | None = None,
                     author: str = "", db_path: str | Path | None = None,
                     ) -> dict:
    """Edit a lead's survey selections / city / chapter from the card.
    answers: {availability|importance|invitations: raw option value}.
    chapter: 'San Antonio' | 'Austin' | '' (clear → re-route from the
    invites answer / city). Invitations 'no' leaves the lead to the
    standing no-loop auto-dismiss on the next poll. Audited via an
    auto note."""
    from . import database as db
    from .timezone_utils import now_central
    answers = {k: v for k, v in (answers or {}).items() if v is not None}
    for f, v in answers.items():
        if f not in MANUAL_ANSWER_KEYS:
            return {"error": f"unknown field {f!r}"}
        if v not in {o for o, _ in MANUAL_ANSWER_OPTIONS[f]}:
            return {"error": f"{f}: {v!r} is not a survey option"}
    if chapter is not None and chapter.strip() not in ("", "San Antonio",
                                                       "Austin"):
        return {"error": "chapter must be San Antonio, Austin, or blank"}
    if not answers and city is None and chapter is None:
        return {"error": "nothing to update"}
    changes: list[str] = []
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        row = conn.execute("SELECT * FROM leads WHERE id = ?",
                           (lead_id,)).fetchone()
        if not row:
            return {"error": f"lead {lead_id} not found"}
        try:
            payload = json.loads(row["payload"]) if row["payload"] else {}
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        stamp = now_central().strftime("%Y-%m-%d %H:%M")
        manual = dict(payload.get("_manual") or {})
        meta = dict(payload.get("_manual_meta") or {})
        for f, v in answers.items():
            key = MANUAL_ANSWER_KEYS[f]
            old = payload.get(key)
            if old == v:
                continue
            manual[key] = v
            meta[key] = {"by": (author or "manager").strip(), "at": stamp,
                         "was": old}
            payload[key] = v
            changes.append(f"{f.capitalize()}: {prettify_answer(old) if old else '—'}"
                           f" → {prettify_answer(v)}")
        payload["_manual"] = manual
        payload["_manual_meta"] = meta
        sets, vals = ["payload = ?"], [json.dumps(payload)]
        if city is not None and (city or "").strip() != (row["city"] or ""):
            sets.append("city = ?")
            vals.append(city.strip() or None)
            changes.append(f"City: {row['city'] or '—'} → {city.strip() or '—'}")
        new_chapter = row["chapter"]
        if chapter is not None:
            new_chapter = chapter.strip() or None
        elif "invitations" in answers:
            routed = route_chapter_from_payload(payload)
            if routed:
                new_chapter = routed
        if new_chapter != row["chapter"]:
            sets.append("chapter = ?")
            vals.append(new_chapter)
            changes.append(f"Chapter: {row['chapter'] or 'unrouted'} → "
                           f"{new_chapter or 'unrouted'}")
        vals.append(lead_id)
        conn.execute(f"UPDATE leads SET {', '.join(sets)} WHERE id = ?", vals)
        if changes:
            conn.execute(
                "INSERT INTO lead_notes (lead_id, author, note) VALUES (?, ?, ?)",
                (lead_id, "auto", f"Selections edited by "
                 f"{(author or 'manager').strip()}: " + "; ".join(changes)))
        conn.commit()
    try:
        db.log_agent_action("lead-center", "lead-answers-edit",
                            f"lead {lead_id}: " + ("; ".join(changes) or
                                                   "no change"))
    except Exception:
        pass
    return {"id": lead_id, "ok": True, "changes": changes,
            "chapter": new_chapter}


# ── FIRST-TOUCH SMS PRESETS (mailbox #383 → #388/#389, Kerry-ratified
#    2026-09-02 evening, reviewed one by one) ─────────────────────────
# One preset SET keyed on the survey answers the card already badges:
# Importance picks the OPENER (P1 Competition / P2 Golf / P3 Community /
# P4 All of it, P4 when blank); Availability picks the EVENT SLOT on
# P1–P4 (Tue → "Tuesday nights"/{next_tue}; Sat → "Saturday 18s"/
# {next_sat}; Both → "our events... Tuesday 9s and a Saturday 18 each
# month"/{next_event}); "No days" → P6 regardless; touched with no reply
# 2+ days → P7 (4+ days → P7b); a re-submitter / existing contact → P8.
# P9 is NOT a preset: it is an add-on line appended to whichever first
# touch fires (P1–P4, P8) when Invitations = Both cities (#389). The
# offer closer is an optional append, verbatim (#381 offer continuity).
# STANDING RULES: no em-dashes anywhere in text-voice copy (period or
# "..." instead); {owner} = the routed touch owner's first name (Robert
# speaks as Robert on Austin). Copy lives in the `lead_sms_presets`
# dial (JSON, merged over these defaults per key) so edits never need
# a deploy; `lead_touch_owners` maps chapter → first name.

DEFAULT_TOUCH_OWNERS = {"San Antonio": "Kerry", "Austin": "Robert",
                        "default": "Kerry"}

# ── PRESET COPY, REVISION WAVE 1 (platform-claude #406, Kerry-ratified
#    2026-09-03 evening). P1-P4 REPLACE the #388 versions.
#
# Kerry sent five real openers today and rewrote the ratified copy live
# every time: "it was too AI and not human enough." The core sentences
# survived; the scaffolding did not.
#
# {price_block} is OURS, not CA's: it holds the two price sentences
# exactly as ratified, and renders EMPTY when first-timer price cannot be
# computed (an uncontracted course like Forest Creek has no knowable cost
# until tee times are bought). Quoting "$ is our 1st Time rate" with a
# hole in it, to a stranger, is worse than not quoting a price. When the
# price IS available the output is byte-identical to the ratified copy.
#
# "Ambassadors" was replaced at Kerry's direction 2026-09-04. It named a
# role that does not exist, which would have made the text a promise
# somebody had to keep on a Tuesday night. His wording: "I'll pair you up
# with someone who will welcome you and show you the ropes."
DEFAULT_SMS_PRESETS: dict = {
    "p1": {
        "label": "Competition",
        "text": ("Hey {first_name}, {owner} with The Golf Fellowship. "
                 "Thanks for the interest! Good to see a fellow competitor.\n\n"
                 "Our events are fair, fun, and legit... gross and net games, "
                 "scratch players to high handicaps, and a crew you'll "
                 "actually want to play with.\n\n"
                 "Tuesday 9s and a Saturday 18 each month. Next one's {when} "
                 "at {course}{start_phrase}.{price_block} Want a spot?"),
    },
    "p2": {
        "label": "Golf",
        "text": ("Hey {first_name}, {owner} with The Golf Fellowship. "
                 "Thanks for your interest!\n\n"
                 "You said you're in it for the golf. We play a different "
                 "course every time, {cadence}, all set up for you so you "
                 "just sign up, show up, and play.\n\n"
                 "Next one{chapter} is {when} at {course}{start_phrase}."
                 "{price_block}\n\n"
                 "Would you like to try TGF out that day? We'd love to have "
                 "you play!"),
    },
    "p3": {
        "label": "Community",
        # Deliberately carries NO optional-gross-games line: skins is a
        # competitor's pitch and lands wrong on a community lead (#406).
        "text": ("Hey {first_name}, {owner} with The Golf Fellowship. "
                 "Thanks for the interest!\n\n"
                 "Saw community is what you're looking for. We're all about "
                 "connecting people thru the game. We mix you in with "
                 "different members each time so you play with as many "
                 "people as possible, and I'll pair you up with someone who "
                 "will welcome you and show you the ropes.\n\n"
                 "{cadence}, with fellowship after. Next one{chapter} is "
                 "{when} at {course}{start_phrase}.{price_block}\n\n"
                 "Want to come meet everybody?"),
    },
    "p4": {
        "label": "All of it",
        "text": ("Hey {first_name}, {owner} with The Golf Fellowship. "
                 "Thanks for the interest! Good to see someone who wants "
                 "the whole thing.\n\n"
                 "Good courses, fair competition, good people. We've been "
                 "chasing that mix for twenty seasons.\n\n"
                 "{cadence}, all set up for you. Next one{chapter} is {when} "
                 "at {course}{start_phrase}.{price_block}\n\n"
                 "Want to try it out?"),
    },
    # ── WAVE 2 (mailbox #417, Kerry-ratified 2026-09-04) ──────────
    # P6 / P7 / P7b / P8 REPLACE the #388 versions. The structural change
    # driving the wave: THE FOLLOW-UPS CARRY THE LINK, NOT A PRICE RECAP.
    # The prospect already saw price and inclusions on the first touch;
    # what they are missing two days later is one tap. Kerry raised the
    # objection himself — is it presumptuous to send a link to someone
    # who has not replied? — and answered it: requiring a reply first
    # makes HIM the gate, and some people do not text back because they
    # are busy, not because they are uninterested.
    #
    #   NEVER MAKE THE HUMAN THE BARRIER TO REGISTRATION.
    #
    # The {..._block} fragments are the #403/#406 valve: a sentence that
    # depends on a value we may not have renders as nothing rather than
    # sending a stranger a text with a hole in it.
    "p6": {
        "label": "No days",
        "text": ("Hey {first_name}, {owner} with The Golf Fellowship. "
                 "Thanks for the interest!\n\n"
                 "Sounds like Tuesdays and Saturdays don't work right now. "
                 "No pressure at all.\n\n"
                 "When does golf usually fit for you? Enough people asking "
                 "for a day is how we decide what to add."),
    },
    "p7": {
        "label": "Second touch",
        "text": ("Hey {first_name}, {owner} again. No reply, no problem.\n\n"
                 "Anything I can answer? Cost, timing, or whether there's "
                 "weird people...\n\n"
                 "{when} at {course} is up next based on your "
                 "availability.{deadline_block}{link_offer} Ready to give "
                 "it a shot?{link_line}"),
    },
    "p7b": {
        "label": "Second touch, 4+ days",
        "text": ("Hey {first_name}, {owner} again, and this is my last one "
                 "for now.\n\n"
                 "If the timing's just off, say \"later\" and I'll check "
                 "back when it fits. If it's first timer nerves, a net "
                 "Team Best Ball game is included, so your foursome is "
                 "actually rooting for you. Nobody's judging your swing, "
                 "they need it.\n\n"
                 "{when} at {course} if you want it.{link_below}"),
    },
    "p8": {
        "label": "Re-submitter",
        "text": ("Hey {first_name}, {owner} with The Golf Fellowship. Good "
                 "to see your name pop up again!\n\n"
                 "You keep circling back, so I figure you actually want to "
                 "do this. What's been getting in the way? Whatever it is, "
                 "we're here to welcome you whenever you're ready.\n\n"
                 "{when} at {course}{start_phrase} is next up if the "
                 "timing works{first_timer_tail}."),
    },
    "closer": {
        "label": "Offer line",
        "text": "$25 off your first event, plus a drink on us.",
    },
    # #406: P9 now also carries the OTHER chapter's event. This replaces
    # listing two events inside the opener — the close stays single.
    "p9": {
        "label": "Both cities add-on",
        "text": ("BTW, you marked both San Antonio and Austin. Do you "
                 "bounce between the two, or should I focus you on one?"
                 "{other_chapter_event}"),
    },
    # #417 fragments. Each one depends on a value that may be missing, so
    # each renders or vanishes as a unit — same valve as price_block.
    "deadline_block": {
        "label": "Sign-up deadline sentence",
        "text": " Sign ups close {deadline} so we can get the groups set.",
    },
    "link_offer": {
        "label": "Link offer sentence",
        "text": (" Here's the link if you want in, just click 1st Timer "
                 "for the discount."),
    },
    "link_line": {
        "label": "The link itself",
        "text": "\n\n{link}",
    },
    "link_below": {
        "label": "Link's below + the link (P7b)",
        "text": " Link's below.\n\n{link}",
    },
    "first_timer_tail": {
        "label": "1st Timer price tail (P8)",
        "text": ", {first_timer_price} as a 1st Timer",
    },
    # The two ratified price sentences, held together so they render or
    # vanish as one unit.
    "price_block": {
        "label": "Price sentences",
        "text": (" {first_timer_price} is our 1st Time rate ($25 off guest "
                 "rate), includes a free drink, cart{range_balls}, and "
                 "entry into Team Net game and Closest to Pins. Optional "
                 "gross games (skins and Individual Gross, preflighted by "
                 "handicaps) are {gross_bundle} more."),
        "no_games": (" {first_timer_price} is our 1st Time rate ($25 off "
                     "guest rate), includes a free drink, cart{range_balls}, "
                     "and entry into Team Net game and Closest to Pins."),
    },
}
SMS_PRESET_ORDER = ["p1", "p2", "p3", "p4", "p6", "p7", "p7b", "p8"]
SMS_SLOT_PRESETS: set = set()   # #406: cadence is a placeholder now, not variants
SMS_P9_PRESETS = {"p1", "p2", "p3", "p4", "p8"}   # #389 add-on rides here
SMS_SYSTEM_NOTE_AUTHORS = {"HS", "GG", "auto"}     # not a human reply
SMS_HOT_TAGS = {"Call back", "Interested", "Coming to event"}
SMS_SECOND_TOUCH_DAYS = 2
SMS_SECOND_TOUCH_ALT_DAYS = 4
SMS_SAT_BORROW_DAYS = 21


def backfill_outreach_alarms(dry_run: bool = False,
                             db_path: str | Path | None = None) -> dict:
    """MIGRATION GAP FIX (platform-claude #405, Kerry-approved 2026-09-03).

    The 48-hour alarm (v2.294.0) only arms on a NEW tagging, so every
    lead Kerry had already texted before the release got nothing — 27
    people personally contacted and sitting outside the very conversion
    gate the release exists to enforce. That is the exact failure mode
    the feature was built to prevent.

    Applies the SAME rule retroactively: outreach-tagged, touched, and no
    follow-up pending → outreach_at = touched_at, follow_up_at =
    touched_at + 2 days. A hand-set date is never overwritten (the
    `follow_up_at IS NULL` guard is what protects it).

    THE FORWARD LESSON, worth keeping: any feature that arms state on an
    event going forward needs a backfill for the rows that predate it,
    or it silently under-covers exactly the population it was built for.
    """
    from datetime import timedelta
    from . import database as db
    from .timezone_utils import to_central, today_central_str
    tags = get_outreach_tags(db_path)
    ph = ",".join("?" * len(tags))
    out: dict = {"dry_run": bool(dry_run), "outreach_tags": tags}
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        rows = [dict(r) for r in conn.execute(
            f"SELECT id, first_name, last_name, tag, touched_at, status "
            f"FROM leads WHERE status = 'touched' AND tag IN ({ph}) "
            f"AND follow_up_at IS NULL AND outreach_at IS NULL "
            f"AND touched_at IS NOT NULL AND merged_into IS NULL "
            f"ORDER BY touched_at", tuple(tags))]
        by_due: dict = {}
        for r in rows:
            # The due DAY is Central, exactly like the live arming path
            # (which stamps now_central() + 2). touched_at is stored UTC,
            # so an evening text — most of them — reads as the next day
            # in UTC and would land the alarm a day late.
            touched_ct = to_central(r["touched_at"])
            if touched_ct is None:
                continue
            due = (touched_ct + timedelta(days=OUTREACH_FOLLOWUP_DAYS)
                   ).strftime("%Y-%m-%d")
            r["due"] = due
            r["touched_day"] = touched_ct.strftime("%Y-%m-%d")
            by_due[due] = by_due.get(due, 0) + 1
        rows = [r for r in rows if r.get("due")]
        out["found"] = len(rows)
        out["by_due_date"] = dict(sorted(by_due.items()))
        _today = today_central_str()
        out["already_due"] = sum(1 for r in rows if r["due"] <= _today)
        out["leads"] = [{"id": r["id"],
                         "name": f"{r['first_name'] or ''} "
                                 f"{r['last_name'] or ''}".strip(),
                         "tag": r["tag"], "touched_at": r["touched_at"],
                         "due": r["due"]} for r in rows]
        if dry_run:
            return out
        # No ping-suppression guard here any more. It existed because
        # the old sweep sent ONE EMAIL PER LEAD, so a backfill reaching
        # back a week was a 39-email blast. The morning digest is one
        # email listing whatever is currently due, so a backfill of any
        # size costs exactly one line in tomorrow's list.
        for r in rows:
            conn.execute(
                "UPDATE leads SET outreach_at = touched_at, follow_up_at = ? "
                "WHERE id = ? AND follow_up_at IS NULL", (r["due"], r["id"]))
            conn.execute(
                "INSERT INTO lead_notes (lead_id, author, note) "
                "VALUES (?, 'auto', ?)",
                (r["id"], f"48-hour follow-up backfilled from the "
                          f"{r['tag']} tag ({r['touched_day']}) "
                          f"— due {r['due']}"))
        conn.commit()
        out["updated"] = len(rows)
    return out


# ── PLACEHOLDER RENDERING, revision wave 1 (#406) ────────────────────
# Every rule here is Kerry's, from comparing the ratified copy against
# what he actually typed to five real prospects.
GROSS_BUNDLE = {9: "$16", 18: "$30"}
FIRST_TIMER_DISCOUNT = 25          # 1st Timer = Guest - $25
GUEST_SURCHARGE = {9: 10, 18: 15, 27: 25}   # over Member; 27h has no 1st tier
_COURSE_SUFFIXES = (
    " golf club of texas", " golf club", " golf course", " golf links",
    " country club", " golf & country club", " cc", " gc",
)


def short_course_name(name: str) -> str:
    """Rule 1: main name only. Kerry: "Nobody says that." """
    n = (name or "").strip()
    low = n.lower()
    for suf in _COURSE_SUFFIXES:
        if low.endswith(suf):
            return n[: len(n) - len(suf)].strip()
    return n


def when_phrase(event_date: str, today=None) -> str:
    """Rule 2: inside 7 days -> day name. 8-10 days -> "next Saturday,
    Sep 12". Beyond -> "Sep 19". NEVER "9/19"."""
    from datetime import date as _d
    from .timezone_utils import now_central
    today = today or now_central().date()
    try:
        y, m, dd = (int(x) for x in str(event_date)[:10].split("-"))
        ev = _d(y, m, dd)
    except Exception:
        return ""
    days = (ev - today).days
    if 0 <= days <= 7:
        return ev.strftime("%A")
    if 8 <= days <= 10:
        return f"next {ev.strftime('%A')}, {ev.strftime('%b')} {ev.day}"
    return f"{ev.strftime('%b')} {ev.day}"


def _fmt_time(t: str) -> str:
    """'17:30' -> '5:30p'; '08:30' -> '8:30a'."""
    raw = (t or "").strip()
    if not raw:
        return ""
    try:
        hh, mm = (int(x) for x in raw.split(":")[:2])
    except Exception:
        return raw
    ap = "a" if hh < 12 else "p"
    h12 = hh % 12 or 12
    return f"{h12}:{mm:02d}{ap}" if mm else f"{h12}{ap}"


def start_phrase(event: dict) -> str:
    """Build ask B (#406): Kerry phrases by FORMAT, not clock.
    Shotgun -> ", 5:30p shotgun". Tee times -> " with tee times starting
    at 8:30a". Unknown -> empty, never a guess."""
    if not event:
        return ""
    t = _fmt_time(event.get("start_time") or "")
    kind = (event.get("start_type") or "").strip().lower()
    if not t:
        return ""
    if kind.startswith("shotgun"):
        return f", {t} shotgun"
    if kind.startswith("tee"):
        return f" with tee times starting at {t}"
    return ""


def cadence_phrase(slot: str) -> str:
    """Rule 4: order follows AVAILABILITY and NEVER drops the other
    option. Kerry: "I would always lead with weekly Tuesdays if they
    selected Tuesday's or both and wouldn't uninclude the other." The
    "whenever you can" softener rides on the NON-selected day only."""
    if slot == "sat":
        return ("a Saturday 18 each month and 9 after work on Tuesdays "
                "whenever you can")
    return "9 after work on Tuesdays weekly and a Saturday 18 each month"


def chapter_phrase(invitations: str, chapter: str) -> str:
    """Rule 5: the "here in SA" callout ONLY when Invitations = Both."""
    if (invitations or "").lower() != "yes_for_both":
        return ""
    if chapter == "San Antonio":
        return " here in SA"
    if chapter == "Austin":
        return " here in Austin"
    return ""


def owner_phrase(chapter: str, invitations: str, owners: dict) -> str:
    """Rule 3: BOTH names whenever the lead touches Austin (Austin-only
    OR both cities). Kerry: "I accidentally didn't include Robert on a
    couple. I like the inclusion." SA-only gets the sender alone."""
    owners = owners or DEFAULT_TOUCH_OWNERS
    inv = (invitations or "").lower()
    touches_austin = chapter == "Austin" or inv in ("yes_for_austin",
                                                    "yes_for_both")
    sa = owners.get("San Antonio") or owners.get("default") or "Kerry"
    atx = owners.get("Austin") or "Robert"
    if touches_austin and atx and atx != sa:
        return f"{sa} and {atx}"
    return owners.get(chapter) or sa


def event_holes(event: dict) -> int:
    """9 or 18 from the event code/format. TGF codes are s9.x / a18.x."""
    name = (event.get("item_name") or "").lower()
    fmt = (event.get("format") or "").lower()
    if "27" in fmt:
        return 27
    if name.startswith(("s18.", "a18.")) or "18" in fmt:
        return 18
    return 9


def signup_deadline_phrase(event: dict) -> str:
    """{deadline} — a SOCIAL deadline, derived, never stored (#417 ask E).

    Kerry's rule: Tuesday events and weekday evening 9s / 9-18 combos
    close two days before; standard weekend 18s close three. Rendered as
    that evening, so a Tuesday event reads "Sunday evening" and a
    Saturday event reads "Wednesday evening".

    CRITICAL, and easy to get wrong. Kerry, verbatim: "those aren't
    actual hard deadlines (see TGF Platform deadline, registration close
    time, rules), they're a preference for management and a little
    urgency." This function exists ONLY to render a sentence. It is
    deliberately not exported to, reconciled against, or consulted by any
    registration-close logic, and a late signup must never be blocked by
    it. If you find yourself importing this into a gate, stop.
    """
    from datetime import date as _date, timedelta as _td
    raw = (event or {}).get("event_date") or ""
    try:
        d = _date.fromisoformat(str(raw)[:10])
    except (ValueError, TypeError):
        return ""
    # Monday=0 … Saturday=5, Sunday=6. A "standard weekend 18" is the
    # only three-day case; everything else — Tuesday nights, weekday
    # evening 9s, 9-18 combos — is two.
    is_weekend = d.weekday() >= 5
    is_18 = str(event_holes(event)) == "18"
    days = 3 if (is_weekend and is_18) else 2
    return (d - _td(days=days)).strftime("%A") + " evening"


def first_timer_price(event: dict) -> float | None:
    """The 1st Timer player total, using the SAME arithmetic the Edit
    Event screen shows (course cost rounds UP first, then markup + game
    fee, then the whole charge rounds up, then the transaction fee).

    Guest = Member + $10 (9h/combo), +$15 (standalone 18h), +$25 (27h).
    1st Timer = Guest - $25, and 27-hole events have NO 1st Timer tier.

    Returns None when course_cost is unknown — an uncontracted course
    like Forest Creek has no knowable price until tee times are bought
    (#403/#404), and a blank in a text to a stranger is worse than no
    price at all."""
    if not event:
        return None
    holes = event_holes(event)
    if holes == 27:
        return None
    cc = event.get("course_cost")
    if cc is None and holes == 18:
        cc = event.get("course_cost_18")
    if cc is None and holes == 9:
        cc = event.get("course_cost_9")
    mu = event.get("tgf_markup")
    if mu is None:
        mu = event.get(f"tgf_markup_{holes}")
    if cc is None or mu is None:
        return None
    sg = event.get("side_game_fee")
    if sg is None:
        sg = event.get(f"side_game_fee_{holes}") or 0
    try:
        import math
        ft_markup = float(mu) + GUEST_SURCHARGE[holes] - FIRST_TIMER_DISCOUNT
        # The EVENT CHARGE, which is the number the Edit Event screen
        # shows and the number CA verified against it (Silverhorn 64/74/49,
        # Forest Creek 143/158/133). The card transaction fee is added at
        # checkout and is deliberately NOT quoted here — Kerry says "$49
        # is our 1st Time rate", not $50.72.
        return float(math.ceil(math.ceil(float(cc)) + ft_markup + float(sg)))
    except Exception:
        logger.warning("first_timer_price failed", exc_info=True)
        return None


def money(v) -> str:
    if v is None:
        return ""
    return f"${v:,.0f}" if float(v) == int(float(v)) else f"${v:,.2f}"


def get_touch_owners(db_path=None) -> dict:
    """chapter → first name for {owner}; dial `lead_touch_owners` over
    DEFAULT_TOUCH_OWNERS."""
    out = dict(DEFAULT_TOUCH_OWNERS)
    cfg = _dial_json("lead_touch_owners", {}, db_path=db_path)
    for k, v in cfg.items():
        if isinstance(v, str) and v.strip():
            out[k] = v.strip()
    return out


def get_sms_presets(db_path=None) -> dict:
    """The preset set: defaults merged per key with the `lead_sms_presets`
    dial (a dict of {key: {label/tue/sat/both/text}} or {key: "text"}).
    A legacy `lead_sms_template` dial, when set, rides along as the
    'custom' preset so nothing Kerry typed there is lost."""
    from . import database as db
    out = {k: dict(v) for k, v in DEFAULT_SMS_PRESETS.items()}
    cfg = _dial_json("lead_sms_presets", {}, db_path=db_path)
    for k, v in cfg.items():
        if isinstance(v, str):
            base = out.setdefault(k, {"label": k.upper()})
            if k in SMS_SLOT_PRESETS:
                base.update({"tue": v, "sat": v, "both": v})
            else:
                base["text"] = v
        elif isinstance(v, dict):
            base = out.setdefault(k, {"label": k.upper()})
            base.update({kk: vv for kk, vv in v.items()
                         if isinstance(vv, str)})
    try:
        legacy = (db.get_app_setting("lead_sms_template", db_path=db_path)
                  if db_path else db.get_app_setting("lead_sms_template"))
    except Exception:
        legacy = None
    if legacy and legacy.strip():
        out["custom"] = {"label": "Custom (lead_sms_template)",
                         "text": legacy.strip()}
    return out


# Not presets — fragments other presets embed. They must never appear in
# the ▾ picker as something Kerry can send on its own.
_SMS_FRAGMENTS = ("closer", "p9", "price_block", "deadline_block",
                  "link_offer", "link_line", "link_below",
                  "first_timer_tail")


def sms_preset_order(presets: dict) -> list[str]:
    order = [k for k in SMS_PRESET_ORDER if k in presets]
    order += sorted(k for k in presets
                    if k not in order and k not in _SMS_FRAGMENTS)
    return [k for k in order if k not in _SMS_FRAGMENTS]


def _event_label(row) -> str:
    """'Tuesday 9/8 at Silverhorn' from an events row."""
    from datetime import date
    name = (row["course"] or row["item_name"] or "").strip()
    try:
        y, m, d = (int(x) for x in str(row["event_date"])[:10].split("-"))
        dt = date(y, m, d)
        return f"{dt.strftime('%A')} {m}/{d} at {name}"
    except Exception:
        return f"{name} on {row['event_date']}"


def next_event_rows(db_path=None, today: str | None = None) -> dict:
    """{'any'|'tue'|'sat': {chapter: full event row}} — the presets need
    course, start time, format and pricing, not just a label."""
    from . import database as db
    from .timezone_utils import today_central_str
    from datetime import date
    today = today or today_central_str()
    out: dict = {"any": {}, "tue": {}, "sat": {}}
    try:
        with db._connect(db_path) as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM events WHERE event_date >= ? "
                "AND COALESCE(event_type, 'event') = 'event' "
                "ORDER BY event_date, item_name", (today,)).fetchall()]
    except Exception:
        logger.warning("next_event_rows failed", exc_info=True)
        return out
    for r in rows:
        name = (r.get("item_name") or "").lower()
        try:
            y, m, d = (int(x) for x in str(r["event_date"])[:10].split("-"))
            wd = date(y, m, d).weekday()
        except Exception:
            wd = None
        is_tue = (name.startswith(("s9.", "a9."))
                  or (wd == 1 and not name.startswith(("s18.", "a18."))))
        is_sat = (name.startswith(("s18.", "a18."))
                  or (wd == 5 and not name.startswith(("s9.", "a9."))))
        chapters = ([r.get("chapter")] if r.get("chapter")
                    and r["chapter"] != "TGF" else ["Austin", "San Antonio"])
        for ch in chapters:
            out["any"].setdefault(ch, r)
            if is_tue:
                out["tue"].setdefault(ch, r)
            if is_sat:
                out["sat"].setdefault(ch, r)
    return out


def next_event_labels(db_path=None, today: str | None = None) -> dict:
    """{'any': {chapter: label}, 'tue': {...}, 'sat': {...}} for the
    {next_event}/{next_tue}/{next_sat} placeholders. Tuesday 9s are the
    s9./a9. events, Saturday 18s the s18./a18. events (weekday-checked
    when the code prefix is missing); TGF-chapter events count for both.
    {next_sat} borrows the other chapter's Saturday when the lead's own
    chapter has none inside SMS_SAT_BORROW_DAYS (#383)."""
    from . import database as db
    from .timezone_utils import today_central_str
    from datetime import date, timedelta
    today = today or today_central_str()
    out: dict = {"any": {}, "tue": {}, "sat": {}}
    sat_dates: dict = {}
    try:
        with db._connect(db_path) as conn:
            rows = conn.execute(
                "SELECT item_name, event_date, chapter, course FROM events "
                "WHERE event_date >= ? AND COALESCE(event_type, 'event') "
                "= 'event' ORDER BY event_date, item_name",
                (today,)).fetchall()
    except Exception:
        logger.warning("Lead next-event lookup failed", exc_info=True)
        return out
    for r in rows:
        name = (r["item_name"] or "").lower()
        try:
            y, m, d = (int(x) for x in str(r["event_date"])[:10].split("-"))
            wd = date(y, m, d).weekday()
        except Exception:
            wd = None
        is_tue = (name.startswith("s9.") or name.startswith("a9.")
                  or (wd == 1 and not name.startswith(("s18.", "a18."))))
        is_sat = (name.startswith("s18.") or name.startswith("a18.")
                  or (wd == 5 and not name.startswith(("s9.", "a9."))))
        label = _event_label(r)
        chapters = ([r["chapter"]] if r["chapter"] and r["chapter"] != "TGF"
                    else ["Austin", "San Antonio"])
        for ch in chapters:
            out["any"].setdefault(ch, label)
            if is_tue:
                out["tue"].setdefault(ch, label)
            if is_sat and ch not in out["sat"]:
                out["sat"][ch] = label
                sat_dates[ch] = str(r["event_date"])[:10]
        out["any"].setdefault("default", label)
        if is_tue:
            out["tue"].setdefault("default", label)
        if is_sat:
            out["sat"].setdefault("default", label)
    # Saturday borrow: own chapter has no 18 inside the window → the
    # other chapter's next one, tagged with its chapter.
    try:
        limit = (date.fromisoformat(today)
                 + timedelta(days=SMS_SAT_BORROW_DAYS)).isoformat()
    except Exception:
        limit = None
    for ch in ("Austin", "San Antonio"):
        other = "San Antonio" if ch == "Austin" else "Austin"
        own = sat_dates.get(ch)
        if (own is None or (limit and own > limit)) and other in out["sat"]:
            if own is None or sat_dates[other] < own:
                out["sat"][ch] = f"{out['sat'][other]} ({other})"
    return out


def _lead_answer(lead: dict, field: str) -> str:
    """Lowercased raw answer for availability / importance / invitations,
    the CURRENT form's exact key first (the Garza rule), fuzzy after."""
    payload = lead.get("payload") or {}
    if not isinstance(payload, dict):
        return ""
    exact = MANUAL_ANSWER_KEYS[field]
    v = payload.get(exact)
    if isinstance(v, str) and v:
        return v.lower()
    frag = {"availability": "play_tuesdays_or_saturdays",
            "importance": "most_important",
            "invitations": "stay_in_the_loop"}[field]
    for k, val in payload.items():
        if frag in k and isinstance(val, str) and val:
            return val.lower()
    return ""


def sms_slot_for(lead: dict) -> str:
    """'tue' / 'sat' / 'both' / 'none' / '' from the Availability answer."""
    a = _lead_answer(lead, "availability")
    if not a:
        return ""
    if "both" in a:
        return "both"
    if "tuesdays" in a:
        return "tue"
    if "saturdays" in a:
        return "sat"
    return "none"


def _is_resubmitter(lead: dict) -> bool:
    if lead.get("has_history"):
        return True
    for n in lead.get("notes_log") or []:
        if (n.get("author") == "HS"
                and str(n.get("note") or "").startswith("Re-submitted")):
            return True
    return False


def _days_since(stamp: str | None, now) -> int | None:
    from datetime import date
    if not stamp:
        return None
    try:
        y, m, d = (int(x) for x in str(stamp)[:10].split("-"))
        return max(0, (now.date() - date(y, m, d)).days)
    except Exception:
        return None


def select_sms_preset(lead: dict, now=None) -> dict:
    """The ratified selection logic → {preset, slot, addons, why}.
    Second touch first (touched, no human reply, 2+ days; 4+ → P7b),
    then P8 for a re-submitter / existing contact, P6 for "No days",
    else Importance → P1–P4 (blank → P4) with the Availability slot
    (blank → tue, the ratified default shown). P9 rides on P1–P4 / P8
    when Invitations = Both cities."""
    from .timezone_utils import now_central
    now = now or now_central()
    slot = sms_slot_for(lead)
    invites = _lead_answer(lead, "invitations")
    addons: list = []

    def _pick(key, why, slot_used=""):
        if key in SMS_P9_PRESETS and invites == "yes_for_both":
            addons.append("p9")
        return {"preset": key, "slot": slot_used, "addons": addons,
                "why": why}

    if lead.get("status") == "touched":
        human_reply = ((lead.get("tag") or "") in SMS_HOT_TAGS
                       or any((n.get("author") or "") not in
                              SMS_SYSTEM_NOTE_AUTHORS
                              for n in lead.get("notes_log") or []))
        days = _days_since(lead.get("touched_at"), now)
        if not human_reply and days is not None:
            if days >= SMS_SECOND_TOUCH_ALT_DAYS:
                return _pick("p7b", f"touched {days}d ago, no reply")
            if days >= SMS_SECOND_TOUCH_DAYS:
                return _pick("p7", f"touched {days}d ago, no reply")
    if _is_resubmitter(lead):
        return _pick("p8", "re-submitted survey / existing contact")
    if slot == "none":
        return _pick("p6", "no days")
    imp = _lead_answer(lead, "importance")
    key = ("p2" if imp.startswith("golf")
           else "p1" if imp.startswith("competition")
           else "p3" if imp.startswith(("community", "connection",
                                        "fellowship"))
           else "p4")
    why = {"p1": "competition", "p2": "golf", "p3": "community",
           "p4": "all of it" if imp else "importance blank"}[key]
    slot_used = slot or "tue"
    return _pick(key, f"{why} · {slot_used}", slot_used)


def sms_vars_for(lead: dict, owners: dict | None = None,
                 nexts: dict | None = None, rows: dict | None = None,
                 slot: str = "") -> dict:
    """Every placeholder for one lead, per the #406 rules."""
    owners = owners or DEFAULT_TOUCH_OWNERS
    nexts = nexts or {"any": {}, "tue": {}, "sat": {}}
    rows = rows or {"any": {}, "tue": {}, "sat": {}}
    ch = lead.get("chapter") or ""
    invitations = _lead_answer(lead, "invitations")
    slot = slot or sms_slot_for(lead) or "tue"

    def _n(kind, fallback):
        m = nexts.get(kind) or {}
        return m.get(ch) or m.get("default") or fallback

    # The event this text is actually about: the one matching their day.
    kind = "sat" if slot == "sat" else ("tue" if slot in ("tue", "both") else "any")
    ev = (rows.get(kind) or {}).get(ch) or (rows.get("any") or {}).get(ch) or {}
    holes = event_holes(ev) if ev else 9
    price = first_timer_price(ev) if ev else None

    # P9 (#406) now names the OTHER chapter's next event.
    other = "San Antonio" if ch == "Austin" else "Austin"
    other_ev = (rows.get("any") or {}).get(other)
    other_phrase = ""
    if invitations == "yes_for_both" and other_ev:
        other_phrase = (f" Our {other} group is playing "
                        f"{short_course_name(other_ev.get('course') or '')} "
                        f"{when_phrase(other_ev.get('event_date'))}.")

    rb = ev.get("range_balls_included") if ev else None
    return {
        "first_name": (lead.get("first_name") or "").strip() or "there",
        "owner": owner_phrase(ch, invitations, owners),
        "cadence": cadence_phrase(slot),
        "chapter": chapter_phrase(invitations, ch),
        "when": when_phrase(ev.get("event_date")) if ev else "",
        "course": short_course_name(ev.get("course") or "") if ev else "",
        "start_phrase": start_phrase(ev),
        "first_timer_price": money(price),
        # #417: the follow-ups carry the link, not a price recap.
        "link": (ev.get("registration_url") or "").strip() if ev else "",
        "deadline": signup_deadline_phrase(ev) if ev else "",
        "range_balls": ", range balls" if rb else "",
        "gross_bundle": GROSS_BUNDLE.get(holes, GROSS_BUNDLE[9]),
        "other_chapter_event": other_phrase,
        # kept for P7 / P7b / P8, which still use the #388 text
        "next_tue": _n("tue", "Tuesday night"),
        "next_sat": _n("sat", "our next Saturday 18"),
        "next_event": _n("any", "one of our upcoming events"),
        "_price_known": price is not None,
    }


def render_sms(presets: dict, key: str, lead: dict, sms_vars: dict,
               slot: str = "", addons: list | None = None,
               closer: bool = False) -> str:
    """Fill a preset. {price_block} carries the two ratified price
    sentences and renders EMPTY when the first-timer price is unknown —
    an uncontracted course has no knowable cost until tee times are
    bought, and a text to a stranger with a hole where the price goes is
    worse than one that simply does not quote a price (#403/#406)."""
    import re
    p = presets.get(key) or {}
    text = p.get("text") or ""
    if not text and (key in SMS_SLOT_PRESETS or "tue" in p):
        text = p.get(slot or "tue") or p.get("tue") or ""
    lines = [text] if text else []
    for a in addons or []:
        t = (presets.get(a) or {}).get("text")
        if t:
            lines.append(t)
    if closer:
        t = (presets.get("closer") or {}).get("text")
        if t:
            lines.append(t)
    out = "\n".join(lines)

    # #417 fragments, assembled before the rest so a missing value takes
    # its whole sentence with it. A follow-up whose event has no
    # registration URL sends WITHOUT the link sentence rather than with a
    # dangling "Here's the link" and nothing after it.
    _frag_ok = {
        "deadline_block": bool(sms_vars.get("deadline")),
        "link_offer": bool(sms_vars.get("link")),
        "link_line": bool(sms_vars.get("link")),
        "link_below": bool(sms_vars.get("link")),
        "first_timer_tail": bool(sms_vars.get("_price_known")),
    }
    for _k, _ok in _frag_ok.items():
        tok = "{" + _k + "}"
        if tok in out:
            out = out.replace(
                tok, ((presets.get(_k) or {}).get("text") or "") if _ok else "")

    # Assemble the price block before substituting the rest.
    if "{price_block}" in out:
        block = ""
        if sms_vars.get("_price_known"):
            pb = presets.get("price_block") or {}
            # P3 deliberately omits the optional-gross-games sentence:
            # skins is a competitor's pitch and lands wrong on a
            # community lead (#406).
            block = (pb.get("no_games") if key == "p3" else pb.get("text")) or ""
        out = out.replace("{price_block}", block)

    for k, v in sms_vars.items():
        if k.startswith("_"):
            continue
        out = out.replace("{" + k + "}", str(v))
    # Tidy any double spaces a dropped block leaves behind.
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def lead_sms_text(lead_id: int, preset: str = "", closer: bool = False,
                  db_path: str | Path | None = None) -> dict:
    """Bridge helper: the picked (or requested) preset rendered for one
    lead, plus the selection reason and the full picker."""
    rows = [r for r in get_leads(limit=5000, db_path=db_path)
            if r["id"] == lead_id]
    if not rows:
        return {"error": f"lead {lead_id} not found"}
    lead = rows[0]
    presets = get_sms_presets(db_path)
    pick = select_sms_preset(lead)
    key = preset or pick["preset"]
    if key not in presets:
        return {"error": f"unknown preset '{key}'",
                "presets": sms_preset_order(presets)}
    vars_ = sms_vars_for(lead, get_touch_owners(db_path),
                         next_event_labels(db_path),
                         next_event_rows(db_path), pick["slot"])
    addons = pick["addons"] if key in SMS_P9_PRESETS else []
    return {"lead_id": lead_id, "name": f"{lead.get('first_name') or ''} "
            f"{lead.get('last_name') or ''}".strip(),
            "phone": lead.get("phone"), "chapter": lead.get("chapter"),
            "picked": pick, "preset": key,
            "label": presets[key].get("label"),
            "text": render_sms(presets, key, lead, vars_,
                               slot=pick["slot"], addons=addons,
                               closer=closer),
            "vars": vars_, "presets": sms_preset_order(presets)}


# ── DUPLICATE LEADS + MERGE (Kerry 2026-09-03) ───────────────────────
# "I see we have two Shane Winters. Those need to be merged. I thought
# we already merged them on HubSpot side."
#
# WHY IT HAPPENS: the Tracker dedups on (source, external_id) — the
# HubSpot contact id. When the SAME person submits the survey twice
# before HubSpot dedups them, or when Kerry merges two contacts in
# HubSpot AFTER the Tracker already polled both, the Tracker is left
# holding two rows with different external_ids. A HubSpot-side merge
# does not propagate back, so it will keep happening.
#
# THE MERGE never deletes the loser: its external_id has to stay in the
# table or the next poll re-inserts it as a brand-new lead. Instead the
# loser is marked merged_into + dismissed and filtered out of every
# queue read, so the row survives as the dedup key and as an audit
# trail.
STATUS_RANK = {"dismissed": 0, "new": 1, "touched": 2, "converted": 3}


def _norm_email(v) -> str:
    return (v or "").strip().lower()


def _norm_phone(v) -> str:
    d = "".join(c for c in str(v or "") if c.isdigit())
    return d[-10:] if len(d) >= 10 else ""


def _norm_name(first, last) -> str:
    return " ".join(f"{first or ''} {last or ''}".lower().split())


def find_duplicate_leads(db_path: str | Path | None = None) -> dict:
    """Groups of live lead rows that are the same person: same email,
    same last-10 phone digits, or same full name. Compact by design —
    enough to decide a merge without reading the whole queue."""
    from . import database as db
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        rows = [dict(r) for r in conn.execute(
            "SELECT id, first_name, last_name, email, phone, chapter, status, "
            "tag, external_id, customer_id, arrived_at, touched_at, "
            "follow_up_at, campaign_id, "
            "(SELECT COUNT(*) FROM lead_notes n WHERE n.lead_id = leads.id) "
            "AS notes FROM leads WHERE merged_into IS NULL "
            "ORDER BY id").fetchall()]
    buckets: dict = {}
    for r in rows:
        for kind, key in (("email", _norm_email(r["email"])),
                          ("phone", _norm_phone(r["phone"])),
                          ("name", _norm_name(r["first_name"], r["last_name"]))):
            if key:
                buckets.setdefault((kind, key), []).append(r["id"])
    by_id = {r["id"]: r for r in rows}
    seen: set = set()
    groups: list = []
    for (kind, key), ids in buckets.items():
        if len(ids) < 2:
            continue
        sig = tuple(sorted(ids))
        if sig in seen:
            continue
        seen.add(sig)
        matched = [k for (k, kk), vv in buckets.items()
                   if tuple(sorted(vv)) == sig]
        groups.append({
            "matched_on": sorted(matched), "lead_ids": list(sig),
            "suggested_keep": _suggest_keep([by_id[i] for i in sig]),
            "leads": [by_id[i] for i in sig],
        })
    groups.sort(key=lambda g: g["lead_ids"])
    return {"duplicate_groups": len(groups), "live_leads": len(rows),
            "groups": groups,
            "how_to_merge": "scoring-lead-merge:<keep_id>|<drop_id>[|dry]"}


def _suggest_keep(rows: list[dict]) -> int:
    """Keep the row carrying the most work: strongest status, then most
    notes, then a real customer link, then the earliest arrival."""
    return sorted(rows, key=lambda r: (
        -STATUS_RANK.get(r["status"], 0), -(r["notes"] or 0),
        0 if r["customer_id"] else 1,
        r["arrived_at"] or "9999"))[0]["id"]


def merge_leads(keep_id: int, drop_id: int, dry_run: bool = False,
                author: str = "", db_path: str | Path | None = None) -> dict:
    """Fold `drop_id` into `keep_id`. Notes move across, the strongest
    status and the earliest dates win, and any field blank on the keeper
    is filled from the loser (including payload answers, so an earlier
    survey is never lost). The loser is marked merged_into + dismissed,
    never deleted — its external_id has to stay put or the next HubSpot
    poll re-creates it."""
    from . import database as db
    if keep_id == drop_id:
        return {"error": "keep and drop are the same lead"}
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        keep = conn.execute("SELECT * FROM leads WHERE id = ?",
                            (keep_id,)).fetchone()
        drop = conn.execute("SELECT * FROM leads WHERE id = ?",
                            (drop_id,)).fetchone()
        if not keep:
            return {"error": f"lead {keep_id} not found"}
        if not drop:
            return {"error": f"lead {drop_id} not found"}
        keep, drop = dict(keep), dict(drop)
        if drop["merged_into"]:
            return {"error": f"lead {drop_id} is already merged into "
                             f"{drop['merged_into']}"}
        if keep["merged_into"]:
            return {"error": f"lead {keep_id} is itself merged into "
                             f"{keep['merged_into']} — merge into that one"}

        changes: dict = {}
        # Strongest status, and the tag that goes with it.
        if STATUS_RANK.get(drop["status"], 0) > STATUS_RANK.get(keep["status"], 0):
            changes["status"] = drop["status"]
            if drop["tag"]:
                changes["tag"] = drop["tag"]
        elif not keep["tag"] and drop["tag"]:
            changes["tag"] = drop["tag"]
        # Earliest real dates (the true first arrival / first touch).
        for col in ("arrived_at", "first_seen_at", "touched_at",
                    "converted_at", "outreach_at"):
            a, b = keep.get(col), drop.get(col)
            if b and (not a or str(b) < str(a)):
                changes[col] = b
        # Fill blanks from the loser.
        for col in ("first_name", "last_name", "email", "phone", "city",
                    "chapter", "customer_id", "campaign_id", "follow_up_at",
                    "touched_by", "notes", "source_label"):
            if not keep.get(col) and drop.get(col):
                changes[col] = drop[col]
        # Payload: keeper's answers win, loser's fill the gaps.
        try:
            kp = json.loads(keep["payload"] or "{}")
            dp = json.loads(drop["payload"] or "{}")
        except Exception:
            kp, dp = {}, {}
        added = [k for k in dp if k not in kp]
        if added:
            merged_payload = dict(dp)
            merged_payload.update(kp)
            changes["payload"] = json.dumps(merged_payload)

        note_count = conn.execute(
            "SELECT COUNT(*) FROM lead_notes WHERE lead_id = ?",
            (drop_id,)).fetchone()[0]
        summary = {
            "keep": keep_id, "drop": drop_id,
            "keep_name": _norm_name(keep["first_name"], keep["last_name"]),
            "drop_name": _norm_name(drop["first_name"], drop["last_name"]),
            "notes_moved": note_count,
            "payload_keys_recovered": sorted(added),
            "fields_changed": {k: v for k, v in changes.items()
                               if k != "payload"},
            "dry_run": bool(dry_run),
        }
        if dry_run:
            return summary

        if changes:
            cols = ", ".join(f"{c} = ?" for c in changes)
            conn.execute(f"UPDATE leads SET {cols} WHERE id = ?",
                         list(changes.values()) + [keep_id])
        conn.execute("UPDATE lead_notes SET lead_id = ? WHERE lead_id = ?",
                     (keep_id, drop_id))
        conn.execute(
            "UPDATE leads SET merged_into = ?, status = 'dismissed' "
            "WHERE id = ?", (keep_id, drop_id))
        conn.execute(
            "INSERT INTO lead_notes (lead_id, author, note) VALUES (?, 'auto', ?)",
            (keep_id, f"Merged duplicate lead #{drop_id} "
                      f"(HubSpot {drop['external_id']}) into this record by "
                      f"{(author or 'manager').strip()}"
                      + (f"; {note_count} note(s) moved" if note_count else "")))
        conn.commit()
    summary["ok"] = True
    return summary


def unmerge_lead(drop_id: int, db_path: str | Path | None = None) -> dict:
    """Undo the row-level half of a merge: the loser returns to the
    queue. Fields already folded into the keeper stay there — this is an
    escape hatch for a merge aimed at the wrong pair, not a full undo."""
    from . import database as db
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        row = conn.execute("SELECT merged_into FROM leads WHERE id = ?",
                           (drop_id,)).fetchone()
        if not row:
            return {"error": f"lead {drop_id} not found"}
        if not row["merged_into"]:
            return {"error": f"lead {drop_id} is not merged"}
        conn.execute("UPDATE leads SET merged_into = NULL, status = 'touched' "
                     "WHERE id = ?", (drop_id,))
        conn.commit()
    return {"id": drop_id, "restored": True, "ok": True,
            "note": "notes and folded fields stay on the keeper"}
