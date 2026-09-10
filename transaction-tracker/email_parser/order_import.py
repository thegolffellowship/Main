"""
Date-range import of GoDaddy "New Order" emails (Kerry 2026-09-09):

  "Yes let's do August 1 thru December 28, 2025 for the shirt fund
   first. We also might have had different breakdowns for side games
   in 2025, so when parsing those, we might need to answer some gaps."

The live inbox check reads only the last 7 days. This reads a window
from the same mailbox (Graph's /messages lists every folder, so the
Outlook rules that file orders into dated folders do not hide them),
skips anything the Tracker already holds (by message id OR by the order
number in the subject — moved messages are re-keyed), and pushes the
rest through the SAME pipeline as the inbox check: parse_email →
save_items → save_parse_warnings → mark_email_processed, then the
event / contest / event-link syncs.

Two guards for a HISTORICAL import:
  * No member email. A 2025 membership term lands with its expiry in
    2026, and the daily membership job sends 30d / 7d / day-of / lapsed
    notices on exact dates and "thanks for renewing" confirmations to a
    later term whenever an earlier one carries a notice. Imported terms
    get all four notice columns stamped 'suppressed:historical-import'
    and any later term of the same customer with no confirmation yet is
    stamped the same, so nothing goes out to a member because of an
    import.
  * It runs in a background thread and reports through `status()`,
    because the MCP bridge times out at 60 s and a window of a few
    hundred orders takes minutes on the parser.

Dry-run (`preview`) never parses: it fetches, de-duplicates and counts.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_ORDER_RE = re.compile(r"#\s*(R\d{6,})")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SUPPRESSED = "suppressed:historical-import"

_JOB: dict = {"running": False}
_LOCK = threading.Lock()


def _creds():
    creds = [os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                    "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")]
    if not all(creds):
        raise RuntimeError("Azure AD / EMAIL_ADDRESS not configured")
    return creds


def _default_fetch(date_from: str, date_to: str) -> list[dict]:
    from .fetcher import fetch_transaction_emails
    since = datetime.strptime(date_from, "%Y-%m-%d")
    until = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
    return fetch_transaction_emails(*_creds(), since_date=since, until_date=until)


def _strip(html: str) -> str:
    from .parser import _strip_html
    return _strip_html(html)


def _order_id(email: dict) -> str | None:
    m = _ORDER_RE.search(email.get("subject") or "")
    return m.group(1) if m else None


def _is_membership(email: dict) -> bool:
    text = (email.get("text") or "") + " " + (email.get("html") or "")
    return "TGF MEMBERSHIP" in text.upper()


def _classify(emails: list[dict], db_path, membership_only: bool) -> dict:
    from . import database as db
    known_uids = db.get_known_email_uids(db_path)
    with db._connect(db_path) as conn:
        known_orders = {r[0] for r in conn.execute(
            "SELECT DISTINCT order_id FROM items WHERE order_id IS NOT NULL AND order_id != ''")}
    new, already, filtered = [], 0, 0
    for e in sorted(emails, key=lambda x: x.get("date") or ""):
        oid = _order_id(e)
        if e.get("uid") in known_uids or (oid and oid in known_orders):
            already += 1
            continue
        if membership_only and not _is_membership(e):
            filtered += 1
            continue
        new.append(e)
    by_month: dict = {}
    memberships = 0
    # A 2025 membership whose buyer has NO 2026 membership in the Tracker
    # becomes that customer's latest term, expired — the daily status
    # sync will read them as FORMER (and Brevo follows). True, but Kerry
    # should see the names before it happens.
    no_renewal: list = []
    with db._connect(db_path) as conn:
        for e in new:
            m = (e.get("date") or "")[:7]
            by_month[m] = by_month.get(m, 0) + 1
            if not _is_membership(e):
                continue
            memberships += 1
            addr = None
            mm = _EMAIL_RE.search(e.get("text") or _strip(e.get("html") or ""))
            if mm:
                addr = mm.group(0).lower()
            if not addr:
                continue
            renewed = conn.execute(
                """SELECT 1 FROM items
                   WHERE LOWER(COALESCE(customer_email,'')) = ?
                     AND UPPER(COALESCE(item_name,'')) LIKE '%MEMBERSHIP%'
                     AND substr(COALESCE(order_date,''),1,4) >= '2026'
                     AND COALESCE(transaction_status,'active') = 'active'
                   LIMIT 1""", (addr,)).fetchone()
            if not renewed:
                no_renewal.append(f"{(e.get('date') or '')[:10]} {addr}")
    return {"found": len(emails), "already_in_tracker": already,
            "filtered_out": filtered, "new": len(new),
            "new_memberships": memberships, "by_month": dict(sorted(by_month.items())),
            "memberships_without_2026_renewal": len(no_renewal),
            "memberships_without_2026_renewal_list": no_renewal[:80],
            "sample": [f"{(e.get('date') or '')[:10]} {e.get('subject')}" for e in new[:12]],
            "_new": new}


def preview(date_from: str, date_to: str, membership_only: bool = False,
            db_path: str | Path | None = None, fetch=None) -> dict:
    fetch = fetch or _default_fetch
    emails = fetch(date_from, date_to)
    c = _classify(emails, db_path, membership_only)
    c.pop("_new", None)
    c.update({"dry_run": True, "from": date_from, "to": date_to,
              "membership_only": membership_only,
              "note": ("Nothing parsed. Apply runs in the background; poll "
                       "scoring-import-status. Memberships route to the premium "
                       "model; events to the default. 2025 events have no event "
                       "rows yet, so their allocations wait in the gap list.")})
    return c


def _suppress_member_notices(conn, item_ids: list[int]) -> dict:
    """Stamp imported membership terms so the daily job never mails a
    member about a term the Tracker only just learned of."""
    if not item_ids:
        return {"terms": 0, "later_terms": 0}
    q = ",".join("?" * len(item_ids))
    try:
        terms = conn.execute(
            f"SELECT id, customer_id, started_at FROM customer_memberships "
            f"WHERE source_item_id IN ({q})", tuple(item_ids)).fetchall()
    except Exception:
        return {"terms": 0, "later_terms": 0, "error": "customer_memberships unavailable"}
    n_later = 0
    for t in terms:
        conn.execute(
            """UPDATE customer_memberships
               SET notice_30d_sent_at = COALESCE(notice_30d_sent_at, ?),
                   notice_7d_sent_at = COALESCE(notice_7d_sent_at, ?),
                   notice_dayof_sent_at = COALESCE(notice_dayof_sent_at, ?),
                   notice_lapsed_sent_at = COALESCE(notice_lapsed_sent_at, ?),
                   confirmation_sent_at = COALESCE(confirmation_sent_at, ?)
               WHERE id = ?""",
            (SUPPRESSED, SUPPRESSED, SUPPRESSED, SUPPRESSED, SUPPRESSED, t["id"]))
        n_later += conn.execute(
            """UPDATE customer_memberships SET confirmation_sent_at = ?
               WHERE customer_id = ? AND started_at > ? AND confirmation_sent_at IS NULL""",
            (SUPPRESSED, t["customer_id"], t["started_at"])).rowcount
    return {"terms": len(terms), "later_terms": n_later}


def _run(date_from, date_to, membership_only, db_path, fetch, parse):
    from . import database as db
    st = _JOB
    try:
        emails = fetch(date_from, date_to)
        c = _classify(emails, db_path, membership_only)
        new = c.pop("_new")
        st.update(c)
        st["to_parse"] = len(new)
        imported_ids: list[int] = []
        for i, email in enumerate(new, 1):
            st["current"] = f"{i}/{len(new)} {email.get('subject')}"
            try:
                rows = parse(email)
                st["parsed"] += 1
                if rows:
                    before = _max_item_id(db_path)
                    count = db.save_items(rows, db_path=db_path)
                    st["items_saved"] += count
                    imported_ids.extend(_new_item_ids(db_path, before))
                    try:
                        db.save_parse_warnings(rows, db_path=db_path)
                    except Exception:
                        logger.exception("import: parse warnings failed (non-fatal)")
                else:
                    st["no_items"] += 1
                db.mark_email_processed(email.get("uid", ""), len(rows or []), db_path=db_path)
            except Exception as e:  # noqa: BLE001
                logger.exception("import: failed on %s", email.get("subject"))
                st["errors"].append(f"{email.get('subject')}: {e}")
                if len(st["errors"]) >= 10 and st["parsed"] == 0:
                    st["message"] = "stopped: first ten emails all failed"
                    break
        st["current"] = None
        with db._connect(db_path) as conn:
            st["notices_suppressed"] = _suppress_member_notices(conn, imported_ids)
            conn.commit()
        if st["items_saved"]:
            for name, fn in (("events", db.sync_events_from_items),
                             ("contests", db.sync_season_contests_from_items),
                             ("event_links", db.backfill_event_links)):
                try:
                    st["sync"][name] = fn(db_path)
                except Exception as e:  # noqa: BLE001
                    logger.exception("import: %s sync failed (non-fatal)", name)
                    st["sync"][name] = f"failed: {e}"
        st["imported_item_ids"] = imported_ids
        st["message"] = st.get("message") or "done"
    except Exception as e:  # noqa: BLE001
        logger.exception("import: job failed")
        st["message"] = f"failed: {e}"
    finally:
        st["running"] = False
        st["finished_at"] = datetime.utcnow().isoformat(timespec="seconds")


def _max_item_id(db_path) -> int:
    from . import database as db
    with db._connect(db_path) as conn:
        return conn.execute("SELECT COALESCE(MAX(id), 0) FROM items").fetchone()[0]


def _new_item_ids(db_path, after: int) -> list[int]:
    from . import database as db
    with db._connect(db_path) as conn:
        return [r[0] for r in conn.execute("SELECT id FROM items WHERE id > ?", (after,))]


def start(date_from: str, date_to: str, membership_only: bool = False,
          db_path: str | Path | None = None, fetch=None, parse=None,
          background: bool = True) -> dict:
    from .parser import parse_email
    with _LOCK:
        if _JOB.get("running"):
            return {"error": "an import is already running", "status": status()}
        _JOB.clear()
        _JOB.update({"running": True, "from": date_from, "to": date_to,
                     "membership_only": membership_only,
                     "started_at": datetime.utcnow().isoformat(timespec="seconds"),
                     "parsed": 0, "items_saved": 0, "no_items": 0, "errors": [],
                     "sync": {}, "message": None, "current": None})
    args = (date_from, date_to, membership_only, db_path,
            fetch or _default_fetch, parse or parse_email)
    if background:
        threading.Thread(target=_run, args=args, name="order-import", daemon=True).start()
    else:
        _run(*args)
    return status()


def status() -> dict:
    out = {k: v for k, v in _JOB.items() if not k.startswith("_")}
    out["errors"] = list(out.get("errors") or [])[-10:]
    ids = out.pop("imported_item_ids", None)
    if ids is not None:
        out["imported_items"] = len(ids)
    return out
