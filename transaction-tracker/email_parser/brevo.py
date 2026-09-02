"""Tracker → Brevo contact sync (first Tracker→Brevo API brick).

Kerry-ratified via platform-claude (mailbox #381, 2026-09-02): the
public "TGF Insider" recap goes to everyone in Brevo EXCEPT active
members (they get the GG-roster recap), so Brevo needs to know who is
who. Nightly, every Tracker customer with an email is stamped onto its
Brevo contact:

    TGF_MEMBER_STATUS  active_member | former_member | prospect
    TGF_CHAPTER        the customer's chapter (when set)

Status comes from ``derive_member_financial_status_bulk`` (the same
member/alumni/guest derivation the boards use), mapped
member→active_member, alumni→former_member, guest→prospect. A Brevo
contact the Tracker doesn't know keeps a blank status, so a segment
built on ``TGF_MEMBER_STATUS != active_member`` still catches it.

Conservative by design: the sync UPDATES contacts already in Brevo and
never creates any unless the ``brevo_sync_create_missing`` dial is
"1" (then missing customers are imported into list 3 "TGF CONTACTS").
Safe no-op until ``BREVO_API_KEY`` lands on Railway.

Endpoints (Brevo API v3, header ``api-key``):
  GET  /v3/account                              — key check
  GET  /v3/contacts?limit=1000&offset=N         — inventory
  POST /v3/contacts/attributes/normal/<NAME>    — ensure attribute
  POST /v3/contacts/batch                       — update ≤100 / call
  PUT  /v3/contacts/<email>                     — per-contact fallback
  POST /v3/contacts/import                      — create (dial-gated)
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

BREVO_API = "https://api.brevo.com/v3"
STATUS_ATTR = "TGF_MEMBER_STATUS"
CHAPTER_ATTR = "TGF_CHAPTER"
STATUS_MAP = {"member": "active_member", "alumni": "former_member",
              "guest": "prospect"}
_STATUS_RANK = {"active_member": 3, "former_member": 2, "prospect": 1}
BATCH_SIZE = 100          # POST /v3/contacts/batch cap
IMPORT_BATCH = 500
DEFAULT_LIST_ID = 3       # "TGF CONTACTS"
_PAUSE = 0.12             # stay under Brevo's ~10 req/s


def _api_key() -> str | None:
    return (os.getenv("BREVO_API_KEY") or "").strip() or None


def _headers(key: str) -> dict:
    return {"api-key": key, "accept": "application/json",
            "content-type": "application/json"}


def brevo_status(db_path: str | Path | None = None) -> dict:
    """Key present? Account reachable? Last sync summary."""
    from . import database as db
    out = {"api_key_set": bool(_api_key()), "account": None,
           "last_sync": None,
           "create_missing": _create_scope(
               _dial(db, "brevo_sync_create_missing", db_path))}
    try:
        raw = db.get_app_setting("brevo_last_sync", db_path=db_path) \
            if db_path else db.get_app_setting("brevo_last_sync")
        out["last_sync"] = json.loads(raw) if raw else None
    except Exception:
        pass
    key = _api_key()
    if key:
        try:
            r = requests.get(f"{BREVO_API}/account", headers=_headers(key),
                             timeout=20)
            if r.ok:
                acct = r.json()
                out["account"] = {"email": acct.get("email"),
                                  "company": (acct.get("companyName")
                                              or acct.get("company"))}
            else:
                out["account_error"] = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            out["account_error"] = str(e)
    return out


def _dial(db, key: str, db_path) -> str | None:
    try:
        return (db.get_app_setting(key, db_path=db_path) if db_path
                else db.get_app_setting(key))
    except Exception:
        return None


# ── Tracker side ────────────────────────────────────────────────────

def tracker_contact_targets(db_path: str | Path | None = None) -> dict:
    """{email_lower: {"status": ..., "chapter": ...}} for every customer
    email the Tracker knows. A shared email across customers keeps the
    strongest status (active > former > prospect)."""
    from . import database as db
    conn = db.get_connection(db_path) if db_path else db.get_connection()
    try:
        conn.row_factory = __import__("sqlite3").Row
        rows = conn.execute(
            """SELECT ce.email, ce.customer_id, ce.is_primary, c.chapter,
                      c.first_name, c.last_name
               FROM customer_emails ce
               JOIN customers c ON c.customer_id = ce.customer_id
               WHERE ce.email IS NOT NULL AND ce.email <> ''
                 AND c.account_status <> 'banned'
               ORDER BY ce.customer_id, ce.is_primary DESC, ce.email_id""").fetchall()
        cids = sorted({r["customer_id"] for r in rows})
        derived = db.derive_member_financial_status_bulk(conn, cids)
    finally:
        conn.close()
    out: dict = {}
    seen_cust: set = set()
    for r in rows:
        email = (r["email"] or "").strip().lower()
        if "@" not in email:
            continue
        status = STATUS_MAP.get(derived.get(r["customer_id"], "guest"),
                                "prospect")
        chapter = (r["chapter"] or "").strip()
        if chapter.upper() == "TGF":
            chapter = ""
        # One import address per customer (primary first) so a person
        # with three known emails never becomes three Brevo contacts.
        importable = r["customer_id"] not in seen_cust
        seen_cust.add(r["customer_id"])
        cur = out.get(email)
        if cur is None or _STATUS_RANK[status] > _STATUS_RANK[cur["status"]]:
            out[email] = {"status": status, "chapter": chapter or (
                cur["chapter"] if cur else ""),
                "first_name": (r["first_name"] or "").strip(),
                "last_name": (r["last_name"] or "").strip(),
                "importable": importable or bool(cur and cur["importable"])}
        else:
            if not cur["chapter"] and chapter:
                cur["chapter"] = chapter
            cur["importable"] = cur["importable"] or importable
    return out


# ── Brevo side ──────────────────────────────────────────────────────

def _fetch_all_contacts(key: str) -> dict:
    """{email_lower: {"id": ..., "attributes": {...}}} for the whole
    account (1000/page)."""
    out: dict = {}
    offset = 0
    while True:
        r = requests.get(f"{BREVO_API}/contacts",
                         params={"limit": 1000, "offset": offset},
                         headers=_headers(key), timeout=60)
        r.raise_for_status()
        data = r.json()
        contacts = data.get("contacts") or []
        for c in contacts:
            email = (c.get("email") or "").strip().lower()
            if email:
                out[email] = {"id": c.get("id"),
                              "attributes": c.get("attributes") or {}}
        if len(contacts) < 1000:
            break
        offset += 1000
        time.sleep(_PAUSE)
    return out


def ensure_attributes(key: str) -> dict:
    """Create TGF_MEMBER_STATUS (text) if Brevo doesn't have it yet.
    TGF_CHAPTER already exists in the account; creating an existing
    attribute is a 400 we treat as fine."""
    out = {}
    for name in (STATUS_ATTR, CHAPTER_ATTR):
        try:
            r = requests.post(
                f"{BREVO_API}/contacts/attributes/normal/{name}",
                json={"type": "text"}, headers=_headers(key), timeout=20)
            if r.status_code in (200, 201, 204):
                out[name] = "created"
            elif r.status_code == 400 and ("exist" in r.text.lower()
                                            or "unique" in r.text.lower()):
                # Brevo says "Attribute name must be unique" for a
                # pre-existing attribute (seen on TGF_CHAPTER, first
                # live run 2026-09-02).
                out[name] = "exists"
            else:
                out[name] = f"HTTP {r.status_code}: {r.text[:120]}"
        except Exception as e:
            out[name] = str(e)
        time.sleep(_PAUSE)
    return out


def _needs_update(brevo_attrs: dict, target: dict) -> bool:
    if (brevo_attrs.get(STATUS_ATTR) or "") != target["status"]:
        return True
    return bool(target["chapter"]) and \
        (brevo_attrs.get(CHAPTER_ATTR) or "") != target["chapter"]


def _attrs_for(target: dict) -> dict:
    attrs = {STATUS_ATTR: target["status"]}
    if target["chapter"]:
        attrs[CHAPTER_ATTR] = target["chapter"]
    return attrs


def _import_attrs_for(target: dict) -> dict:
    """A NEW Brevo contact also gets the name (the recap greets by
    FIRSTNAME); updates never touch names Brevo already holds."""
    attrs = _attrs_for(target)
    if target.get("first_name"):
        attrs["FIRSTNAME"] = target["first_name"]
    if target.get("last_name"):
        attrs["LASTNAME"] = target["last_name"]
    return attrs


def _create_scope(dial_value: str | None) -> str:
    """brevo_sync_create_missing: '' / '0' → never create; 'active' →
    create missing ACTIVE MEMBERS only (Kerry 2026-09-02: 'adding those
    active members into Brevo that aren't in there currently'); '1' /
    'all' → every Tracker customer with an email."""
    v = (dial_value or "").strip().lower()
    if v in ("1", "all", "true", "yes"):
        return "all"
    if v in ("active", "members", "active_member"):
        return "active"
    return "none"


def _update_batch(key: str, batch: list[dict], errors: list) -> int:
    """POST /v3/contacts/batch; on a batch-level rejection fall back to
    per-contact PUTs so one odd address can't sink the other 99."""
    try:
        r = requests.post(f"{BREVO_API}/contacts/batch",
                          json={"contacts": batch}, headers=_headers(key),
                          timeout=60)
        if r.status_code in (200, 204):
            return len(batch)
        logger.warning("Brevo batch update HTTP %s: %s — falling back "
                       "to per-contact", r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("Brevo batch update failed: %s — falling back", e)
    done = 0
    for c in batch:
        try:
            r = requests.put(
                f"{BREVO_API}/contacts/{quote(c['email'], safe='')}",
                json={"attributes": c["attributes"]},
                headers=_headers(key), timeout=30)
            if r.status_code in (200, 204):
                done += 1
            else:
                errors.append({"email": c["email"],
                               "error": f"HTTP {r.status_code}: {r.text[:120]}"})
        except Exception as e:
            errors.append({"email": c["email"], "error": str(e)})
        time.sleep(_PAUSE)
    return done


def _import_missing(key: str, rows: list[dict], list_id: int,
                    errors: list) -> int:
    """POST /v3/contacts/import (jsonBody) — only when the dial allows
    creating contacts the Tracker knows but Brevo doesn't."""
    created = 0
    for i in range(0, len(rows), IMPORT_BATCH):
        chunk = rows[i:i + IMPORT_BATCH]
        try:
            r = requests.post(
                f"{BREVO_API}/contacts/import",
                json={"jsonBody": chunk, "listIds": [list_id],
                      "updateExistingContacts": True,
                      "emptyContactsAttributes": False},
                headers=_headers(key), timeout=60)
            if r.status_code in (200, 202):
                created += len(chunk)
            else:
                errors.append({"import": f"HTTP {r.status_code}: {r.text[:160]}"})
        except Exception as e:
            errors.append({"import": str(e)})
        time.sleep(_PAUSE)
    return created


def sync_member_status(db_path: str | Path | None = None,
                       dry_run: bool = False) -> dict:
    """Stamp TGF_MEMBER_STATUS / TGF_CHAPTER onto Brevo contacts.
    Returns a summary; persists it to the brevo_last_sync dial and the
    agent action log. Safe no-op (error noted) without BREVO_API_KEY."""
    from . import database as db
    from .timezone_utils import now_central
    started = time.time()
    result = {"ran_at": now_central().strftime("%Y-%m-%d %H:%M %Z"),
              "dry_run": dry_run, "tracker_emails": 0, "brevo_contacts": 0,
              "matched": 0, "to_update": 0, "updated": 0,
              "missing_in_brevo": 0, "created": 0,
              "by_status": {}, "errors": []}
    key = _api_key()
    if not key:
        result["error"] = "BREVO_API_KEY not set"
        return result

    targets = tracker_contact_targets(db_path)
    result["tracker_emails"] = len(targets)
    for t in targets.values():
        result["by_status"][t["status"]] = \
            result["by_status"].get(t["status"], 0) + 1

    if not dry_run:
        result["attributes"] = ensure_attributes(key)
    try:
        brevo = _fetch_all_contacts(key)
    except Exception as e:
        result["error"] = f"Brevo contact fetch failed: {e}"
        logger.warning(result["error"])
        return result
    result["brevo_contacts"] = len(brevo)

    scope = _create_scope(_dial(db, "brevo_sync_create_missing", db_path))
    result["create_scope"] = scope
    updates, missing = [], []
    for email, target in targets.items():
        bc = brevo.get(email)
        if bc is None:
            if target.get("importable", True):
                missing.append({"email": email,
                                "attributes": _import_attrs_for(target),
                                "_status": target["status"]})
            continue
        result["matched"] += 1
        if _needs_update(bc["attributes"], target):
            updates.append({"email": email, "attributes": _attrs_for(target)})
    result["to_update"] = len(updates)
    result["missing_in_brevo"] = len(missing)
    result["sample_updates"] = updates[:5]

    if not dry_run:
        for i in range(0, len(updates), BATCH_SIZE):
            result["updated"] += _update_batch(
                key, updates[i:i + BATCH_SIZE], result["errors"])
            time.sleep(_PAUSE)
        to_create = [m for m in missing
                     if scope == "all"
                     or (scope == "active" and m["_status"] == "active_member")]
        result["to_create"] = len(to_create)
        if to_create:
            list_id = int(_dial(db, "brevo_sync_list_id", db_path)
                          or DEFAULT_LIST_ID)
            rows = [{"email": m["email"], "attributes": m["attributes"]}
                    for m in to_create]
            result["created"] = _import_missing(key, rows, list_id,
                                                result["errors"])
            result["sample_created"] = rows[:5]
    result["seconds"] = round(time.time() - started, 1)
    result["errors"] = result["errors"][:25]

    if not dry_run:
        try:
            summary = {k: v for k, v in result.items()
                       if k not in ("sample_updates",)}
            if db_path:
                db.set_app_setting("brevo_last_sync", json.dumps(summary),
                                   db_path=db_path)
            else:
                db.set_app_setting("brevo_last_sync", json.dumps(summary))
            db.log_agent_action(
                "brevo-sync", "brevo-member-status-sync",
                f"Brevo sync: {result['updated']}/{result['to_update']} "
                f"updated, {result['matched']} matched of "
                f"{result['brevo_contacts']} Brevo contacts, "
                f"{result['missing_in_brevo']} Tracker emails not in Brevo"
                + (f", {result['created']} created" if result["created"] else ""),
                outcome="ok" if not result["errors"] else "partial")
        except Exception:
            logger.warning("Brevo sync bookkeeping failed", exc_info=True)
    return result


def nightly_brevo_sync() -> None:
    """Scheduler entry point."""
    if not _api_key():
        logger.info("Brevo nightly sync idle — BREVO_API_KEY not set")
        return
    try:
        res = sync_member_status()
        logger.info("Brevo nightly sync: %s", json.dumps(
            {k: res.get(k) for k in ("matched", "to_update", "updated",
                                     "missing_in_brevo", "created",
                                     "error")}))
    except Exception:
        logger.exception("Brevo nightly sync failed")
