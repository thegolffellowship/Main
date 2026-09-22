"""Who referred this player — guessed from what the order already says.

Kerry 2026-09-22, on Shahyan Javed: "Shahyan Javed should have
automatically been attributed to Jeff Young because Jeff purchased him.
He should only show up on a 1st Timer attribution list to confirm it was
Jeff, with an option to switch in worst case."

His order carried Jeff's name THREE times — `notes` read "Purchased by
Jeff Young", `coupon_code` was `tgf-jeff`, and there was a partner
request. Asking a question the data already answers is the thing this
module exists to stop.

DERIVE, THEN CONFIRM. Nothing here writes an attribution. A suggestion
is evidence plus a name; a person still says yes, because the cost of a
wrong guess is now a $25 referral fee to the wrong member.
"""
from __future__ import annotations

import re
import sqlite3

# Strongest first. The order matters: the first signal that resolves to a
# real customer wins, and its `source` is what gets recorded — so a spot
# somebody paid for reads bought_spot, not "told us".
#
# confidence is for the UI's wording, never for skipping the human:
#   high — the order states it outright
#   med  — the order implies it and the name resolves
_PURCHASED_BY = re.compile(r"purchased\s+by\s+(.+?)\s*$", re.I)
_REFERRAL_COUPON = re.compile(r"^tgf-referral-(.+)$", re.I)
_NAMED_COUPON = re.compile(r"^tgf-([a-z]{3,})$", re.I)


def _resolve(conn, name: str | None, exclude_id: int) -> tuple[int, str] | None:
    """A name to a customer_id, or nothing. Never a guess between two."""
    from .database import _lookup_customer_id
    name = (name or "").strip()
    if not name:
        return None
    try:
        cid = _lookup_customer_id(conn, name, None)
    except sqlite3.OperationalError:
        # The shared resolver reaches across several tables. A suggestion
        # is a nicety — it must never be the thing that breaks a card, so
        # fall back to the one match that needs nothing but `customers`.
        cid = None
    if not cid:
        hits = conn.execute(
            "SELECT customer_id FROM customers "
            "WHERE LOWER(TRIM(COALESCE(first_name,'') || ' ' || "
            "  COALESCE(last_name,''))) = ?", (name.lower(),)).fetchall()
        cid = hits[0]["customer_id"] if len(hits) == 1 else None
    if not cid or cid == exclude_id:
        return None
    row = conn.execute(
        "SELECT TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) "
        "AS n FROM customers WHERE customer_id = ?", (cid,)).fetchone()
    return (cid, (row["n"] or "").strip() or name) if row else None


def _by_first_name(conn, token: str, exclude_id: int) -> tuple[int, str] | None:
    """`tgf-jeff` → Jeff Young, but ONLY if exactly one member is a Jeff.

    A coupon token is a nickname, not an identity. Two Jeffs means the
    Tracker does not know which one and must not pretend it does.
    """
    rows = conn.execute(
        "SELECT customer_id, TRIM(COALESCE(first_name,'') || ' ' || "
        "  COALESCE(last_name,'')) AS n FROM customers "
        "WHERE LOWER(TRIM(COALESCE(first_name,''))) = ? AND customer_id <> ?",
        (token.strip().lower(), exclude_id)).fetchall()
    if len(rows) != 1:
        return None
    return (rows[0]["customer_id"], (rows[0]["n"] or "").strip())


def suggest_referrer(customer_id: int, conn) -> dict | None:
    """{referrer_customer_id, referrer_name, source, evidence, confidence}.

    Reads only this customer's own orders. Returns None when the orders
    say nothing — silence is a real answer and is better than a guess.
    """
    try:
        items = conn.execute(
            "SELECT id, order_date, notes, coupon_code, referred_by, referral "
            "FROM items WHERE customer_id = ? "
            "  AND COALESCE(transaction_status,'active') = 'active' "
            "ORDER BY order_date, id", (customer_id,)).fetchall()
    except sqlite3.OperationalError:
        return None

    for it in items:
        keys = it.keys()

        # 1. The new-member form asked outright.
        for col, label in (("referred_by", "referred by"),
                           ("referral", "referral")):
            if col in keys and (it[col] or "").strip():
                hit = _resolve(conn, it[col], customer_id)
                if hit:
                    return {"referrer_customer_id": hit[0],
                            "referrer_name": hit[1], "source": "lead_form",
                            "evidence": f"the order form's {label} field said "
                                        f"\"{(it[col] or '').strip()}\"",
                            "confidence": "high"}

        # 2. Somebody paid for their spot. The Tracker watched it happen.
        if "notes" in keys and (it["notes"] or "").strip():
            m = _PURCHASED_BY.search(it["notes"])
            if m:
                hit = _resolve(conn, m.group(1), customer_id)
                if hit:
                    return {"referrer_customer_id": hit[0],
                            "referrer_name": hit[1], "source": "bought_spot",
                            "evidence": f"the order reads \"{it['notes'].strip()}\"",
                            "confidence": "high"}

        # 3. A referral coupon names its owner.
        code = (it["coupon_code"] or "").strip() if "coupon_code" in keys else ""
        if code:
            m = _REFERRAL_COUPON.match(code)
            if m:
                hit = (_resolve(conn, m.group(1), customer_id)
                       or _by_first_name(conn, m.group(1), customer_id))
                if hit:
                    return {"referrer_customer_id": hit[0],
                            "referrer_name": hit[1], "source": "coupon",
                            "evidence": f"they redeemed {code}",
                            "confidence": "high"}
            m = _NAMED_COUPON.match(code)
            if m:
                hit = _by_first_name(conn, m.group(1), customer_id)
                if hit:
                    return {"referrer_customer_id": hit[0],
                            "referrer_name": hit[1], "source": "coupon",
                            "evidence": f"they redeemed {code}",
                            "confidence": "med"}
    return None
