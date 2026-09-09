"""
Contest add-on flags audited against the ORDER EMAIL (Kerry 2026-09-09):

  "For the oversight on the Match Play flag, we need to run thru the
   other Membership transactions and make sure that anything that
   doesn't show as $50 (New) or $75 (Returning) gets checked for Season
   Contest add-ons and associated markups."

For every membership (price not $50 / $75 unless `all_rows`) and every
SEASON CONTESTS item that came from a real order email, fetch the email
from Microsoft Graph (no AI), read the printed option lines with
`parser.contest_flags_from_body`, and compare with the four stored
flags. Dry-run reports; `apply=True` writes the flags the form printed.
The sync honors removals, so restoring a flag on a refunded entry does
not re-enroll anyone; it restores what was SOLD so the money decomposes.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

FLAGS = ("net_points_race", "gross_points_race", "city_match_play",
         "fall_net_points_race")


def _default_fetch(uid: str) -> dict | None:
    from .fetcher import fetch_email_by_id
    creds = [os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                    "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")]
    if not all(creds):
        raise RuntimeError("Azure AD / EMAIL_ADDRESS not configured")
    return fetch_email_by_id(*creds, uid)


def _body_text(email_data: dict) -> str:
    from .parser import _strip_html
    body = email_data.get("text") or ""
    if not body and email_data.get("html"):
        body = _strip_html(email_data["html"])
    return body or ""


def contest_flags_audit(db_path: str | Path | None = None, apply: bool = False,
                        all_rows: bool = False, limit: int | None = None,
                        fetch=None) -> dict:
    from . import database as db
    from .parser import contest_flags_from_body
    fetch = fetch or _default_fetch
    out = {"apply": apply, "all_rows": all_rows, "rows": 0, "fetched": 0,
           "unfetchable": [], "mismatches": [], "applied": 0, "clean": 0}
    with db._connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(
            """SELECT id, order_id, order_date, customer, item_name, item_price,
                      email_uid, net_points_race, gross_points_race,
                      city_match_play, fall_net_points_race
               FROM items
               WHERE merchant = 'The Golf Fellowship'
                 AND COALESCE(transaction_status, 'active') = 'active'
                 AND parent_item_id IS NULL
                 AND email_uid IS NOT NULL AND email_uid NOT LIKE 'manual-%'
                 AND (UPPER(COALESCE(item_name,'')) LIKE '%MEMBERSHIP%'
                      OR UPPER(COALESCE(item_name,'')) LIKE '%SEASON CONTEST%')
               ORDER BY order_date, id""")]
        if not all_rows:
            rows = [r for r in rows
                    if "MEMBERSHIP" not in (r["item_name"] or "").upper()
                    or db._parse_dollar(r.get("item_price")) not in (50.0, 75.0)]
        if limit:
            rows = rows[:limit]
        cache: dict = {}
        for r in rows:
            out["rows"] += 1
            uid = r["email_uid"]
            if uid not in cache:
                try:
                    cache[uid] = fetch(uid)
                except Exception as e:  # noqa: BLE001
                    logger.warning("contest flags audit: fetch failed for %s: %s", uid, e)
                    cache[uid] = None
            email = cache[uid]
            if not email:
                out["unfetchable"].append({"item_id": r["id"], "order_id": r["order_id"],
                                           "customer": r["customer"]})
                continue
            out["fetched"] += 1
            form = contest_flags_from_body(_body_text(email).upper())
            diffs = {}
            for f in FLAGS:
                if f not in form:
                    continue
                stored = (r.get(f) or "").strip().upper()
                stored_yes = stored.startswith("YES")
                want_yes = form[f] == "YES"
                if stored_yes != want_yes:
                    diffs[f] = {"stored": r.get(f), "form": form[f]}
            if not diffs:
                out["clean"] += 1
                continue
            rec = {"item_id": r["id"], "order_id": r["order_id"],
                   "order_date": r["order_date"], "customer": r["customer"],
                   "item": r["item_name"], "price": r["item_price"], "diffs": diffs}
            out["mismatches"].append(rec)
            if apply:
                sets = ", ".join(f"{f} = ?" for f in diffs)
                conn.execute(f"UPDATE items SET {sets} WHERE id = ?",
                             tuple(diffs[f]["form"] for f in diffs) + (r["id"],))
                out["applied"] += 1
        if apply:
            conn.commit()
    return out
