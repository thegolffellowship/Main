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
}


def _hubspot_token() -> str | None:
    return (os.getenv("HUBSPOT_TOKEN")
            or os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")) or None


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
_ANSWER_HIDE_PREFIXES = ("num_", "stripe_", "ad_campaign_id", "ad_set_id",
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


def check_new_leads(db_path: str | Path | None = None) -> dict:
    """Scheduled poll: pull new HubSpot contacts past the watermark,
    queue the ones that pass the source filter, ping the touch owners.
    Safe no-op when HUBSPOT_TOKEN is unset."""
    from . import database as db
    result = {"fetched": 0, "queued": 0, "notified": 0, "skipped_filter": 0}
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
            # Kerry-ruled priority (2026-08-28): (1) the AD SET they
            # clicked — chapter-targeted, primary; (2) the Event Invites
            # (stay-in-the-loop) answer; (3) the city map.
            got = None
            if isinstance(payload, dict):
                got = ad_set_chapters.get(str(payload.get("ad_set_id") or ""))
            got = got or route_chapter_from_payload(payload)
            return got or route_chapter(city, city_map)

        for c in passing:
            c["payload"] = enrich_payload(
                payloads.get(str(c["external_id"])), ad_set_names) or None
            c["chapter"] = _route(c["payload"], c.get("city"))
        new_ids = upsert_leads(conn, passing, city_map)
        result["queued"] = len(new_ids)
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
            enriched = enrich_payload(dict(p), ad_set_names)
            got = None if r["chapter"] else _route(enriched, r["city"])
            if enriched != p or got:
                conn.execute(
                    "UPDATE leads SET payload = ?, "
                    "chapter = COALESCE(chapter, ?) WHERE id = ?",
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
                "touched_at = COALESCE(touched_at, datetime('now')) "
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
            conn.execute(
                "UPDATE leads SET status = 'converted', "
                "tag = 'Registered event', "
                "touched_at = COALESCE(touched_at, datetime('now')) "
                "WHERE status != 'dismissed' "
                "AND COALESCE(tag, '') != 'Became member' "
                "AND (status != 'converted' "
                "     OR COALESCE(tag, '') != 'Registered event') "
                "AND customer_id IS NOT NULL "
                "AND EXISTS (SELECT 1 FROM items i "
                "            WHERE i.customer_id = leads.customer_id "
                "            AND i.transaction_status = 'active' "
                "            AND UPPER(i.item_name) NOT LIKE '%MEMBERSHIP%')")
        except sqlite3.Error as e:
            logger.warning("Lead conversion auto-detect failed: %s", e)
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

    # Advance the watermark to the newest createdate seen (dedup by
    # external_id makes the re-read of boundary contacts harmless).
    newest = max((c.get("arrived_at") or "" for c in contacts), default="")
    if newest:
        try:
            db.set_app_setting("leads_hubspot_watermark", newest)
        except Exception:
            logger.warning("Lead watermark update failed", exc_info=True)
    return result


def get_leads(status: str = "", limit: int = 200,
              db_path: str | Path | None = None) -> list[dict]:
    from . import database as db
    from .timezone_utils import now_central
    with db._connect(db_path) as conn:
        ensure_leads_table(conn)
        q = "SELECT * FROM leads"
        params: tuple = ()
        if status:
            q += " WHERE status = ?"
            params = (status,)
        q += " ORDER BY COALESCE(arrived_at, first_seen_at) DESC LIMIT ?"
        rows = [dict(r) for r in conn.execute(q, params + (limit,)).fetchall()]
    # "Existing customer" badge = the lead matches a customer with REAL
    # purchase history — NOT the prospect row the lead pass itself
    # created (Kerry 2026-08-28: "They are not members at all").
    cids = [r["customer_id"] for r in rows if r.get("customer_id")]
    with_history: set = set()
    if cids:
        ph = ",".join("?" * len(cids))
        with db._connect(db_path) as conn:
            with_history = {x[0] for x in conn.execute(
                f"SELECT DISTINCT customer_id FROM items "
                f"WHERE customer_id IN ({ph}) "
                f"AND transaction_status = 'active'", cids)}
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


# Kerry-editable via the lead_tag_options dial (JSON list of strings);
# these are the defaults. Tags are dispositions, orthogonal to the
# new/touched/converted/dismissed pipeline.
DEFAULT_TAG_OPTIONS = ["Left VM", "Texted", "No answer", "Call back",
                       "Interested", "Coming to event", "Too expensive",
                       "Not now", "Bad contact", "Registered event",
                       "Became member"]

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
                 db_path: str | Path | None = None) -> dict:
    """Set (or clear with '') a lead's disposition tag. Tagging a NEW
    lead marks it touched — a tag means somebody acted on it."""
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
                "touched_at = COALESCE(touched_at, datetime('now')) "
                "WHERE id = ?", (tag, lead_id))
        else:
            conn.execute("UPDATE leads SET tag = ? WHERE id = ?",
                         (tag or None, lead_id))
        conn.commit()
    return {"id": lead_id, "tag": tag or None, "ok": True}


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
        conn.commit()
    return {"lead_id": lead_id, "ok": True}


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
        else:
            conn.execute(
                "UPDATE leads SET status = ?, notes = COALESCE(NULLIF(?, ''), "
                "notes) WHERE id = ?", (status, notes, lead_id))
        conn.commit()
    return {"id": lead_id, "status": status, "ok": True}
