"""Membership term tracking, renewal reminders, and roster opt-in/out.

One row in `customer_memberships` per term (year). The latest row per customer
is the "current" term; older rows are history. Term length is 365 days from
purchase for terms started 2025-01-01 or later, calendar-year (Dec 31) for
older ones (matches TGF's policy change last year).

The scheduler hits this from `app.py`:
- `daily_membership_job(send_email)` — sends notices, confirmations, and the
  no-response admin digest.
- `record_renewal_for_item(conn, item_id, send_email)` — called after a new
  membership purchase parses; opens a fresh term and triggers the confirmation
  email if the previous term had any reminders sent.

Roster opt-in/out is one-click via signed tokens:
- `make_roster_token(customer_id, term_id, action)` returns an HMAC-signed
  string. Verified by `verify_roster_token`.
- `apply_roster_choice(...)` flips the column and notifies admin.

All public DB functions accept either a `conn` or a `db_path`; pass a `conn`
when you're already inside a transaction.
"""
from __future__ import annotations

import base64
import hmac
import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, date
from typing import Callable, Optional

from .database import _connect, get_connection, _lookup_customer_id

logger = logging.getLogger(__name__)


# -- Constants --------------------------------------------------------------

MEMBERSHIP_PRICE = 75
# Override at runtime via MEMBERSHIP_RENEWAL_URL env var if the storefront URL
# ever moves. The default below matches the current TGF storefront product page.
RENEWAL_URL_DEFAULT = "https://thegolffellowship.com/shop/ols/products/tgf-membership"
ADMIN_NOTIFY_EMAIL = "admin@thegolffellowship.com"


def _renewal_url() -> str:
    """Read RENEWAL_URL from env at call time so the default can be overridden
    without a code deploy.  Falls back to the constant above."""
    return (os.getenv("MEMBERSHIP_RENEWAL_URL") or "").strip() or RENEWAL_URL_DEFAULT


# Backwards-compat shim: a few callers reference RENEWAL_URL as a module-level
# constant.  Resolved at import time, but the live value comes from
# `_renewal_url()` inside email rendering.
RENEWAL_URL = RENEWAL_URL_DEFAULT

# The policy switch year: terms started in 2025+ run 365 days from purchase.
# Anything earlier is calendar-year (expires Dec 31 of the start year).
POLICY_365_FROM_YEAR = 2025

# Notice windows (days before/after expiry):
NOTICE_WINDOWS = [
    ("notice_30d_sent_at",    -30, "30d"),
    ("notice_7d_sent_at",      -7, "7d"),
    ("notice_dayof_sent_at",    0, "dayof"),
    ("notice_lapsed_sent_at",  14, "lapsed"),
]

# Days after the lapsed notice with no response → admin digest.
NO_RESPONSE_DIGEST_DAYS = 7

# Signed-token expiry (days from issue).
ROSTER_TOKEN_TTL_DAYS = 30


# -- Schema -----------------------------------------------------------------

def ensure_membership_tables(conn: sqlite3.Connection) -> None:
    """Create customer_memberships if missing (handles live DB migration).

    Idempotent — safe to call from every read/write path.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_memberships (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id              INTEGER NOT NULL REFERENCES customers(customer_id),
            started_at               TEXT NOT NULL,
            expires_at               TEXT NOT NULL,
            source                   TEXT NOT NULL DEFAULT 'parsed'
                                       CHECK(source IN ('parsed', 'manual', 'renewal', 'backfill')),
            source_item_id           INTEGER REFERENCES items(id),
            price_paid               REAL,
            notes                    TEXT,
            notice_30d_sent_at       TEXT,
            notice_7d_sent_at        TEXT,
            notice_dayof_sent_at     TEXT,
            notice_lapsed_sent_at    TEXT,
            confirmation_sent_at     TEXT,
            roster_choice            TEXT
                                       CHECK(roster_choice IN ('keep', 'remove') OR roster_choice IS NULL),
            roster_choice_at         TEXT,
            roster_admin_notified_at TEXT,
            created_at               TEXT DEFAULT (datetime('now')),
            updated_at               TEXT DEFAULT (datetime('now')),
            UNIQUE(customer_id, started_at)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cust_memberships_customer ON customer_memberships(customer_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cust_memberships_expires ON customer_memberships(expires_at)"
    )
    conn.commit()


# -- Term helpers -----------------------------------------------------------

def compute_expires_at(started_at: str) -> str:
    """Return the expiration ISO date string for a term started on `started_at`.

    Terms started 2025+ run 365 days from purchase; older terms run to Dec 31
    of the start year.
    """
    try:
        d = datetime.strptime(started_at[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        # Fall back to today + 365 if the input is malformed.
        d = date.today()
    if d.year >= POLICY_365_FROM_YEAR:
        return (d + timedelta(days=365)).strftime("%Y-%m-%d")
    return f"{d.year}-12-31"


def _is_membership_item(item_name: str) -> bool:
    """Mirror of the frontend membership detector — match `deriveStatus`."""
    return "membership" in (item_name or "").lower()


# -- Backfill ---------------------------------------------------------------

def backfill_memberships_from_items(conn: sqlite3.Connection) -> dict:
    """Insert one row per parsed `membership` item into `customer_memberships`.

    Idempotent — `UNIQUE(customer_id, started_at)` skips rows that already exist.
    Skips items without `customer_id` (pre-identity rows that haven't been
    backfilled yet — they'll be picked up on a future boot).

    Returns counts: {scanned, inserted, skipped_no_customer}.
    """
    ensure_membership_tables(conn)

    rows = conn.execute(
        """
        SELECT id, customer_id, order_date, item_name, item_price
          FROM items
         WHERE LOWER(item_name) LIKE '%membership%'
           AND order_date IS NOT NULL
           AND order_date != ''
         ORDER BY order_date ASC
        """
    ).fetchall()

    scanned = len(rows)
    skipped_no_customer = 0
    inserted = 0

    for r in rows:
        if not r["customer_id"]:
            skipped_no_customer += 1
            continue
        started_at = (r["order_date"] or "")[:10]
        if not started_at:
            continue
        expires_at = compute_expires_at(started_at)
        # Strip any "$" / "(credit)" noise from price.
        price_paid = None
        try:
            raw = (r["item_price"] or "").replace("$", "").split("(")[0].replace(",", "").strip()
            if raw:
                price_paid = float(raw)
        except (ValueError, AttributeError):
            pass
        try:
            cur = conn.execute(
                """
                INSERT INTO customer_memberships
                    (customer_id, started_at, expires_at, source, source_item_id, price_paid)
                VALUES (?, ?, ?, 'backfill', ?, ?)
                """,
                (r["customer_id"], started_at, expires_at, r["id"], price_paid),
            )
            if cur.rowcount:
                inserted += 1
        except sqlite3.IntegrityError:
            # UNIQUE(customer_id, started_at) — already backfilled.
            pass

    if inserted:
        conn.commit()
        logger.info(
            "Membership backfill: scanned=%d inserted=%d skipped_no_customer=%d",
            scanned, inserted, skipped_no_customer,
        )
    return {
        "scanned": scanned,
        "inserted": inserted,
        "skipped_no_customer": skipped_no_customer,
    }


# -- CRUD -------------------------------------------------------------------

def get_memberships_for_customer(customer_id: int, db_path=None) -> list[dict]:
    """Return all membership terms for a customer, newest first."""
    with _connect(db_path) as conn:
        ensure_membership_tables(conn)
        rows = conn.execute(
            """
            SELECT *
              FROM customer_memberships
             WHERE customer_id = ?
             ORDER BY started_at DESC
            """,
            (customer_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_current_term_map(db_path=None) -> dict:
    """Return {customer_id: {started_at, expires_at, source, ...}} for all customers.

    Uses the latest term per customer (highest `started_at`). The Customers
    list page overlays this onto each row to render the Renewal column.
    """
    with _connect(db_path) as conn:
        ensure_membership_tables(conn)
        rows = conn.execute(
            """
            SELECT m.customer_id, m.id, m.started_at, m.expires_at, m.source,
                   m.notice_30d_sent_at, m.notice_7d_sent_at,
                   m.notice_dayof_sent_at, m.notice_lapsed_sent_at,
                   m.confirmation_sent_at, m.roster_choice
              FROM customer_memberships m
              JOIN (
                  SELECT customer_id, MAX(started_at) AS latest
                    FROM customer_memberships
                   GROUP BY customer_id
              ) latest_per
                ON latest_per.customer_id = m.customer_id
               AND latest_per.latest = m.started_at
            """
        ).fetchall()
    result = {}
    for r in rows:
        result[r["customer_id"]] = {
            "id": r["id"],
            "started_at": r["started_at"],
            "expires_at": r["expires_at"],
            "source": r["source"],
            "notice_30d_sent_at": r["notice_30d_sent_at"],
            "notice_7d_sent_at": r["notice_7d_sent_at"],
            "notice_dayof_sent_at": r["notice_dayof_sent_at"],
            "notice_lapsed_sent_at": r["notice_lapsed_sent_at"],
            "confirmation_sent_at": r["confirmation_sent_at"],
            "roster_choice": r["roster_choice"],
        }
    return result


def get_current_term(conn: sqlite3.Connection, customer_id: int) -> Optional[dict]:
    """Return the current (latest) term for this customer, or None."""
    ensure_membership_tables(conn)
    row = conn.execute(
        """
        SELECT * FROM customer_memberships
         WHERE customer_id = ?
         ORDER BY started_at DESC
         LIMIT 1
        """,
        (customer_id,),
    ).fetchone()
    return dict(row) if row else None


def add_manual_term(
    customer_id: int,
    started_at: str,
    expires_at: Optional[str] = None,
    notes: Optional[str] = None,
    db_path=None,
) -> dict:
    """Insert a manual membership term (e.g. for a member who renewed offline).

    `expires_at` defaults to `compute_expires_at(started_at)`. The 365-day rule
    is policy-based; an admin can override for legacy calendar-year edits.
    """
    if not started_at:
        raise ValueError("started_at is required")
    started_at = started_at[:10]
    if not expires_at:
        expires_at = compute_expires_at(started_at)
    expires_at = expires_at[:10]

    with _connect(db_path) as conn:
        ensure_membership_tables(conn)
        try:
            cur = conn.execute(
                """
                INSERT INTO customer_memberships
                    (customer_id, started_at, expires_at, source, notes)
                VALUES (?, ?, ?, 'manual', ?)
                """,
                (customer_id, started_at, expires_at, notes),
            )
        except sqlite3.IntegrityError as e:
            raise ValueError(
                f"Customer already has a term started on {started_at}"
            ) from e
        new_id = cur.lastrowid
        conn.commit()
    return {"id": new_id, "started_at": started_at, "expires_at": expires_at}


def update_term(term_id: int, fields: dict, db_path=None) -> int:
    """Update mutable columns on a term: started_at / expires_at / notes."""
    allowed = {"started_at", "expires_at", "notes"}
    safe = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not safe:
        return 0
    if "started_at" in safe:
        safe["started_at"] = safe["started_at"][:10]
    if "expires_at" in safe:
        safe["expires_at"] = safe["expires_at"][:10]

    set_clause = ", ".join(f"{k} = ?" for k in safe) + ", updated_at = datetime('now')"
    params = list(safe.values()) + [term_id]
    with _connect(db_path) as conn:
        ensure_membership_tables(conn)
        cur = conn.execute(
            f"UPDATE customer_memberships SET {set_clause} WHERE id = ?", params
        )
        conn.commit()
    return cur.rowcount


def delete_term(term_id: int, db_path=None) -> int:
    """Remove a term row (admin only — used to clean up mistaken manual entries)."""
    with _connect(db_path) as conn:
        ensure_membership_tables(conn)
        cur = conn.execute(
            "DELETE FROM customer_memberships WHERE id = ?", (term_id,)
        )
        conn.commit()
    return cur.rowcount


# -- Renewal detection ------------------------------------------------------

def record_renewal_for_item(
    conn: sqlite3.Connection,
    item_id: int,
    send_email: Optional[Callable] = None,
) -> Optional[dict]:
    """Open a new term for the customer who just bought a membership item.

    Called from `save_items` whenever a membership row lands. If the previous
    term had any reminders sent, fires the confirmation email.

    `send_email(to, subject, html)` is the caller's email-send hook (Microsoft
    Graph in production). Pass None during tests to skip the send.

    Returns the new term dict, or None if the item isn't a membership / has no
    customer / a duplicate term already exists.
    """
    ensure_membership_tables(conn)
    item = conn.execute(
        "SELECT id, customer_id, order_date, item_name, item_price FROM items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if not item or not _is_membership_item(item["item_name"] or ""):
        return None
    if not item["customer_id"]:
        logger.info("record_renewal_for_item: item %s has no customer_id, skipping", item_id)
        return None

    started_at = (item["order_date"] or "")[:10]
    if not started_at:
        return None
    expires_at = compute_expires_at(started_at)

    # Did the customer have a previous term that had any reminders sent?
    prev = conn.execute(
        """
        SELECT id, notice_30d_sent_at, notice_7d_sent_at,
               notice_dayof_sent_at, notice_lapsed_sent_at
          FROM customer_memberships
         WHERE customer_id = ?
         ORDER BY started_at DESC
         LIMIT 1
        """,
        (item["customer_id"],),
    ).fetchone()
    had_reminders = bool(prev and any(
        prev[col] for col in
        ("notice_30d_sent_at", "notice_7d_sent_at",
         "notice_dayof_sent_at", "notice_lapsed_sent_at")
    ))

    price_paid = None
    try:
        raw = (item["item_price"] or "").replace("$", "").split("(")[0].replace(",", "").strip()
        if raw:
            price_paid = float(raw)
    except (ValueError, AttributeError):
        pass

    try:
        cur = conn.execute(
            """
            INSERT INTO customer_memberships
                (customer_id, started_at, expires_at, source, source_item_id, price_paid)
            VALUES (?, ?, ?, 'renewal', ?, ?)
            """,
            (item["customer_id"], started_at, expires_at, item_id, price_paid),
        )
    except sqlite3.IntegrityError:
        # Duplicate term — already recorded for this date.
        return None
    new_id = cur.lastrowid
    conn.commit()

    new_term = dict(conn.execute(
        "SELECT * FROM customer_memberships WHERE id = ?", (new_id,)
    ).fetchone())

    # Send confirmation if there was a prior term with reminders.
    if had_reminders and send_email:
        try:
            sent = _send_confirmation(conn, new_term, send_email)
            if sent:
                conn.execute(
                    "UPDATE customer_memberships SET confirmation_sent_at = datetime('now') WHERE id = ?",
                    (new_id,),
                )
                conn.commit()
        except Exception:
            logger.exception("record_renewal_for_item: confirmation send failed for term %s", new_id)

    return new_term


# -- Email templates --------------------------------------------------------

def _email_shell(body_html: str) -> str:
    """Minimal HTML wrapper — keeps emails readable across clients."""
    url = _renewal_url()
    return f"""<!doctype html>
<html><body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#111827; max-width:600px; margin:0 auto; padding:1.5rem;">
{body_html}
<hr style="border:none; border-top:1px solid #e5e7eb; margin:1.5rem 0;">
<p style="font-size:0.78rem; color:#6b7280;">The Golf Fellowship · <a href="{url}" style="color:#2563eb;">thegolffellowship.com</a></p>
</body></html>"""


def _renew_button(label: str = "Renew Membership — $75") -> str:
    url = _renewal_url()
    return f"""<p style="margin:1.25rem 0;">
  <a href="{url}" style="display:inline-block; background:#16a34a; color:#fff; padding:0.7rem 1.4rem; border-radius:6px; text-decoration:none; font-weight:600;">{label}</a>
</p>
<p style="font-size:0.82rem; color:#6b7280; margin-top:-0.5rem;">Or paste this link into your browser: <a href="{url}" style="color:#2563eb;">{url}</a></p>"""


def _time_phrase(days_left: int) -> str:
    """Human-readable phrase for `days_left` between today and expires_at.

    Used to keep subject lines accurate when an admin fires Send Notice Now
    on a term that's not exactly 30 / 7 / 0 days from today (e.g. a manually
    backfilled term entered mid-cycle).
    """
    if days_left > 1:
        return f"in {days_left} days"
    if days_left == 1:
        return "tomorrow"
    if days_left == 0:
        return "today"
    if days_left == -1:
        return "yesterday"
    return f"{abs(days_left)} days ago"


def render_notice_email(window: str, term: dict, customer: dict) -> tuple[str, str]:
    """Return (subject, html_body) for a given notice window.

    `window` ∈ {"30d", "7d", "dayof", "lapsed"}.
    `term` has at minimum: expires_at.
    `customer` has at minimum: first_name.

    Subjects + body language are computed from the **actual** days remaining
    (today vs `expires_at`), not the window label, so a manually-fired
    Send Notice Now on a mid-cycle term reads correctly.  E.g. if Bryce's
    term expires in 14 days and the admin picks the "T-30" window, the
    subject says "expires in 14 days", not "in 30 days".
    """
    first_name = customer.get("first_name") or "there"
    expires_at = term["expires_at"]
    today = date.today()
    try:
        exp_d = datetime.strptime(expires_at[:10], "%Y-%m-%d").date()
    except ValueError:
        exp_d = today
    days_left = (exp_d - today).days
    days_lapsed = max(0, -days_left)
    expires_pretty = exp_d.strftime("%B %-d, %Y")
    phrase = _time_phrase(days_left)  # "in 14 days" / "tomorrow" / "today" / "2 days ago"

    if window == "30d":
        # Pre-expiry "heads up" — subject reflects the actual days remaining.
        if days_left > 0:
            subject = f"Your TGF membership expires {phrase}"
        elif days_left == 0:
            subject = "Your TGF membership expires today"
        else:
            subject = f"Your TGF membership lapsed {days_lapsed} days ago"
        body = f"""<p>Hi {first_name},</p>
<p>A heads-up that your membership in The Golf Fellowship expires on <strong>{expires_pretty}</strong>{f" ({phrase})" if days_left > 0 else ""}. Renewal is only <strong>$75 for the next 12 months</strong> and keeps your weekly event invitations and member pricing in place without a gap:</p>
{_renew_button()}
<p>Renewals run for 365 days from the date of purchase. If you've already renewed, no action needed — these reminders shut off automatically once the purchase lands in our system.</p>
<p>Thanks for being part of The Golf Fellowship.</p>
<p>— The Golf Fellowship</p>"""
        return subject, _email_shell(body)

    if window == "7d":
        # Tighter reminder — same dynamic subject treatment.
        if days_left > 0:
            subject = f"Your TGF membership expires {phrase}"
        elif days_left == 0:
            subject = "Your TGF membership expires today"
        else:
            subject = f"Your TGF membership lapsed {days_lapsed} days ago"
        body = f"""<p>Hi {first_name},</p>
<p>Quick reminder — your membership in The Golf Fellowship expires <strong>{expires_pretty}</strong>{f" ({phrase})" if days_left != 0 else " (today)"}. Renewal is only <strong>$75 for the next 12 months</strong>:</p>
{_renew_button()}
<p>Once your renewal comes through, these reminders stop on their own.</p>
<p>— The Golf Fellowship</p>"""
        return subject, _email_shell(body)

    if window == "dayof":
        subject = "Your TGF membership expires today"
        body = f"""<p>Hi {first_name},</p>
<p>Today is the last day of your current term with The Golf Fellowship. Renewal is only <strong>$75 for the next 12 months</strong>:</p>
{_renew_button()}
<p>Already renewed in the last 24 hours? Please ignore — your purchase will close out these notifications as soon as it parses.</p>
<p>— The Golf Fellowship</p>"""
        return subject, _email_shell(body)

    if window == "lapsed":
        keep_url, remove_url = _roster_action_urls(term)
        subject = "Final notice — your TGF membership has lapsed"
        body = f"""<p>Hi {first_name},</p>
<p>Your membership in The Golf Fellowship expired on <strong>{expires_pretty}</strong> ({days_lapsed} days ago) and we haven't seen a renewal come through yet. Renewal is still only <strong>$75 for the next 12 months</strong>:</p>
{_renew_button()}
<p><strong>About Golf Genius:</strong> unless we hear from you, we'll be removing you from the rosters that deliver our weekly event invitations. One click is enough — let us know which you'd prefer:</p>
<p style="margin:1.25rem 0;">
  <a href="{keep_url}" style="display:inline-block; background:#16a34a; color:#fff; padding:0.7rem 1.2rem; border-radius:6px; text-decoration:none; font-weight:600; margin-right:0.5rem;">✅ Keep me on the invite list</a>
  <a href="{remove_url}" style="display:inline-block; background:#dc2626; color:#fff; padding:0.7rem 1.2rem; border-radius:6px; text-decoration:none; font-weight:600;">❌ Remove me from the rosters</a>
</p>
<p style="font-size:0.82rem; color:#6b7280;">If the buttons don't work in your email client:<br>
  Keep on rosters: <a href="{keep_url}" style="color:#2563eb;">{keep_url}</a><br>
  Remove from rosters: <a href="{remove_url}" style="color:#2563eb;">{remove_url}</a>
</p>
<p>Either button notifies our admin team at <a href="mailto:{ADMIN_NOTIFY_EMAIL}" style="color:#2563eb;">{ADMIN_NOTIFY_EMAIL}</a>. If we don't hear back at all in the next {NO_RESPONSE_DIGEST_DAYS} days, we'll go ahead and remove you from the rosters — no hard feelings, you're always welcome back.</p>
<p>Thanks,<br>The Golf Fellowship</p>"""
        return subject, _email_shell(body)

    raise ValueError(f"Unknown notice window: {window}")


VALID_NOTICE_WINDOWS = {"30d", "7d", "dayof", "lapsed", "confirmation"}


def preview_notice(term_id: int, window: str, db_path=None) -> dict:
    """Render the notice email for an existing term WITHOUT sending it.

    Returns {to, subject, html, term, customer, can_send, reason}.  `can_send`
    is False when the recipient has no primary email on file (admin can still
    see what would have gone out, but the Send button is disabled).
    """
    if window not in VALID_NOTICE_WINDOWS:
        raise ValueError(f"Unknown notice window: {window}")
    with _connect(db_path) as conn:
        ensure_membership_tables(conn)
        term = conn.execute(
            "SELECT * FROM customer_memberships WHERE id = ?", (term_id,)
        ).fetchone()
        if not term:
            raise ValueError(f"Term {term_id} not found")
        term = dict(term)
        cust = conn.execute(
            """
            SELECT c.first_name, c.last_name,
                   COALESCE(NULLIF(TRIM(c.first_name||' '||c.last_name),''), '(unknown)') AS full_name,
                   ce.email
              FROM customers c
              LEFT JOIN customer_emails ce
                     ON ce.customer_id = c.customer_id AND ce.is_primary = 1
             WHERE c.customer_id = ?
            """,
            (term["customer_id"],),
        ).fetchone()
    if not cust:
        raise ValueError(f"Customer {term['customer_id']} not found")
    customer = {"first_name": cust["first_name"], "last_name": cust["last_name"]}
    if window == "confirmation":
        # Pull the originating order_id if the term came from a parsed item.
        order_id = None
        if term.get("source_item_id"):
            with _connect(db_path) as conn:
                row = conn.execute(
                    "SELECT order_id FROM items WHERE id = ?", (term["source_item_id"],)
                ).fetchone()
                if row:
                    order_id = row["order_id"]
        subject, html = render_confirmation_email(term, customer, order_id)
    else:
        subject, html = render_notice_email(window, term, customer)
    return {
        "to": cust["email"] or "",
        "subject": subject,
        "html": html,
        "term": term,
        "customer": {
            "first_name": cust["first_name"],
            "last_name": cust["last_name"],
            "full_name": cust["full_name"],
        },
        "can_send": bool(cust["email"]),
        "reason": "" if cust["email"] else "No primary email on file for this customer.",
    }


_WINDOW_TO_COLUMN = {
    "30d":          "notice_30d_sent_at",
    "7d":           "notice_7d_sent_at",
    "dayof":        "notice_dayof_sent_at",
    "lapsed":       "notice_lapsed_sent_at",
    "confirmation": "confirmation_sent_at",
}


def send_notice_now(
    term_id: int,
    window: str,
    send_email: Callable,
    db_path=None,
    subject_override: Optional[str] = None,
) -> dict:
    """Render + immediately send a notice for an existing term.

    Stamps the corresponding `*_sent_at` column on success so the daily
    scheduler doesn't re-fire the same window.

    `subject_override` (optional) replaces the rendered subject — used by
    the Send Notice Now modal so admins can hand-edit the subject before
    sending without leaving the preview page.

    Returns {ok, sent_to, subject, stamped_column} or {ok: False, error}.
    """
    if window not in VALID_NOTICE_WINDOWS:
        return {"ok": False, "error": f"Unknown window: {window}"}
    preview = preview_notice(term_id, window, db_path=db_path)
    if not preview["can_send"]:
        return {"ok": False, "error": preview["reason"]}
    subject = (subject_override or "").strip() or preview["subject"]
    sent = send_email(preview["to"], subject, preview["html"])
    if not sent:
        return {"ok": False, "error": "Email send failed (check server logs)"}
    col = _WINDOW_TO_COLUMN[window]
    with _connect(db_path) as conn:
        ensure_membership_tables(conn)
        conn.execute(
            f"UPDATE customer_memberships SET {col} = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (term_id,),
        )
        conn.commit()
    return {
        "ok": True,
        "sent_to": preview["to"],
        "subject": subject,
        "stamped_column": col,
    }


def render_confirmation_email(term: dict, customer: dict, order_id: Optional[str] = None) -> tuple[str, str]:
    """Return (subject, html_body) for the renewal confirmation email."""
    first_name = customer.get("first_name") or "there"
    try:
        exp_d = datetime.strptime(term["expires_at"][:10], "%Y-%m-%d").date()
        new_expires = exp_d.strftime("%B %-d, %Y")
    except (ValueError, KeyError):
        new_expires = term.get("expires_at", "(unknown)")
    try:
        ord_d = datetime.strptime(term["started_at"][:10], "%Y-%m-%d").date()
        order_date_pretty = ord_d.strftime("%B %-d, %Y")
    except (ValueError, KeyError):
        order_date_pretty = term.get("started_at", "")

    order_line = ""
    if order_id:
        order_line = f"<p>Order: <strong>{order_id}</strong> · {order_date_pretty}</p>"
    elif order_date_pretty:
        order_line = f"<p>Renewed: <strong>{order_date_pretty}</strong></p>"

    subject = "Thanks for renewing your TGF membership"
    body = f"""<p>Hi {first_name},</p>
<p>Thanks for renewing your membership in The Golf Fellowship. Your new term runs through <strong>{new_expires}</strong> — you'll stay on the Golf Genius rosters and continue to receive weekly event invitations without interruption.</p>
{order_line}
<p>If anything looks off — wrong date, wrong name, or you didn't actually renew — just reply to this email and we'll sort it.</p>
<p>See you out there,<br>The Golf Fellowship</p>"""
    return subject, _email_shell(body)


def _send_confirmation(conn: sqlite3.Connection, term: dict, send_email: Callable) -> bool:
    """Look up the customer + email and fire the confirmation. Returns True on send."""
    cust = conn.execute(
        """
        SELECT c.first_name, c.last_name, ce.email
          FROM customers c
          LEFT JOIN customer_emails ce
                 ON ce.customer_id = c.customer_id AND ce.is_primary = 1
         WHERE c.customer_id = ?
        """,
        (term["customer_id"],),
    ).fetchone()
    if not cust or not cust["email"]:
        logger.info("Membership confirmation: no email for customer %s", term["customer_id"])
        return False
    item_row = None
    if term.get("source_item_id"):
        item_row = conn.execute(
            "SELECT order_id FROM items WHERE id = ?", (term["source_item_id"],)
        ).fetchone()
    order_id = item_row["order_id"] if item_row else None
    subject, html = render_confirmation_email(term, dict(cust), order_id)
    return send_email(cust["email"], subject, html)


# -- Token signing for roster opt-in/out -----------------------------------

def _secret() -> bytes:
    """Use SECRET_KEY (Flask) for HMAC. Falls back to a stable dev string only if missing."""
    s = os.getenv("SECRET_KEY") or "tgf-roster-token-dev-fallback-do-not-use-in-prod"
    return s.encode("utf-8")


def make_roster_token(customer_id: int, term_id: int, action: str) -> str:
    """Return a URL-safe HMAC-signed token for a roster-keep / roster-remove link.

    Encodes customer_id, term_id, action, and an expiry timestamp. Verified by
    `verify_roster_token`. Tokens are single-purpose (one action) and expire
    after `ROSTER_TOKEN_TTL_DAYS`.
    """
    if action not in ("keep", "remove"):
        raise ValueError("action must be 'keep' or 'remove'")
    payload = {
        "c": customer_id,
        "t": term_id,
        "a": action,
        "e": int((datetime.utcnow() + timedelta(days=ROSTER_TOKEN_TTL_DAYS)).timestamp()),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    sig = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def verify_roster_token(token: str) -> Optional[dict]:
    """Return decoded payload dict or None if invalid/expired."""
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        pad = "=" * (-len(body) % 4)
        raw = base64.urlsafe_b64decode(body + pad)
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("e", 0) < int(datetime.utcnow().timestamp()):
        return None
    if payload.get("a") not in ("keep", "remove"):
        return None
    return payload


def _roster_action_urls(term: dict) -> tuple[str, str]:
    """Return (keep_url, remove_url) for the lapsed-notice email."""
    base = os.getenv("APP_BASE_URL", "https://tgf-tracker.up.railway.app").rstrip("/")
    keep = make_roster_token(term["customer_id"], term["id"], "keep")
    remove = make_roster_token(term["customer_id"], term["id"], "remove")
    return f"{base}/m/roster/{keep}", f"{base}/m/roster/{remove}"


def apply_roster_choice(token: str, send_email: Optional[Callable] = None) -> dict:
    """Decode the token, persist the choice, notify admin. Returns a dict for rendering.

    Result shape:
      {"ok": True, "action": "keep"|"remove", "customer_name": str, "term_id": int}
      or {"ok": False, "error": str}
    """
    payload = verify_roster_token(token)
    if not payload:
        return {"ok": False, "error": "This link is invalid or has expired."}

    customer_id = payload["c"]
    term_id = payload["t"]
    action = payload["a"]

    with _connect() as conn:
        ensure_membership_tables(conn)
        term = conn.execute(
            "SELECT * FROM customer_memberships WHERE id = ? AND customer_id = ?",
            (term_id, customer_id),
        ).fetchone()
        if not term:
            return {"ok": False, "error": "Membership term not found."}

        # Idempotent: a second click just re-renders the same confirmation.
        already = term["roster_choice"]
        if not already or already != action:
            conn.execute(
                """UPDATE customer_memberships
                      SET roster_choice = ?,
                          roster_choice_at = datetime('now'),
                          updated_at = datetime('now')
                    WHERE id = ?""",
                (action, term_id),
            )
            conn.commit()

        cust = conn.execute(
            """
            SELECT c.first_name, c.last_name,
                   COALESCE(NULLIF(TRIM(c.first_name||' '||c.last_name),''), '(unknown)') AS full_name,
                   ce.email
              FROM customers c
              LEFT JOIN customer_emails ce
                     ON ce.customer_id = c.customer_id AND ce.is_primary = 1
             WHERE c.customer_id = ?
            """,
            (customer_id,),
        ).fetchone()
        full_name = cust["full_name"] if cust else f"customer #{customer_id}"
        member_email = cust["email"] if cust else ""

        # Notify admin only on the first click (don't spam if member clicks twice).
        if not already and send_email:
            try:
                _notify_admin_of_roster_choice(
                    full_name, member_email, customer_id, action, send_email
                )
            except Exception:
                logger.exception("apply_roster_choice: admin notify failed")

    return {
        "ok": True,
        "action": action,
        "customer_name": full_name,
        "customer_id": customer_id,
        "term_id": term_id,
    }


def _notify_admin_of_roster_choice(
    full_name: str,
    member_email: str,
    customer_id: int,
    action: str,
    send_email: Callable,
) -> None:
    base = os.getenv("APP_BASE_URL", "https://tgf-tracker.up.railway.app").rstrip("/")
    cust_url = f"{base}/customers?customer_id={customer_id}"
    verb = "wants to STAY on" if action == "keep" else "asked to be REMOVED from"
    subject = f"[Roster] {full_name} {verb} the Golf Genius rosters"
    body = f"""<p><strong>{full_name}</strong> (<a href="mailto:{member_email}">{member_email or 'no email on file'}</a>) {verb} the Golf Genius rosters.</p>
<p><a href="{cust_url}">Open customer record</a></p>
<p style="font-size:0.82rem; color:#6b7280;">Customer ID {customer_id}. This notification is sent once per click.</p>"""
    send_email(ADMIN_NOTIFY_EMAIL, subject, _email_shell(body))


# -- Daily scheduler job ----------------------------------------------------

def daily_membership_job(send_email: Callable) -> dict:
    """Send notice emails, confirmations, and the no-response admin digest.

    Idempotent — each notice column gets stamped after a successful send so
    the next run won't re-fire.

    Returns a counts dict for logging.
    """
    counts = {
        "30d": 0, "7d": 0, "dayof": 0, "lapsed": 0,
        "confirmations": 0, "digest_sent": 0, "skipped_renewed": 0,
    }
    today = date.today()

    with _connect() as conn:
        ensure_membership_tables(conn)

        # 0. Renewal confirmations — for terms whose prior term had any
        # reminder sent and we haven't confirmed yet.
        pending_confirms = conn.execute(
            """
            SELECT m.id, m.customer_id, m.started_at, m.expires_at, m.source_item_id
              FROM customer_memberships m
             WHERE m.confirmation_sent_at IS NULL
               AND m.source IN ('renewal', 'parsed', 'manual')
               AND EXISTS (
                   SELECT 1 FROM customer_memberships prior
                    WHERE prior.customer_id = m.customer_id
                      AND prior.started_at < m.started_at
                      AND (prior.notice_30d_sent_at IS NOT NULL
                           OR prior.notice_7d_sent_at IS NOT NULL
                           OR prior.notice_dayof_sent_at IS NOT NULL
                           OR prior.notice_lapsed_sent_at IS NOT NULL)
               )
            """
        ).fetchall()
        for r in pending_confirms:
            try:
                term = dict(r)
                ok = _send_confirmation(conn, term, send_email)
                if ok:
                    conn.execute(
                        "UPDATE customer_memberships SET confirmation_sent_at = datetime('now') WHERE id = ?",
                        (r["id"],),
                    )
                    counts["confirmations"] += 1
            except Exception:
                logger.exception("Confirmation send failed for term %s", r["id"])
        conn.commit()

        # 1. Per-window notices.
        for col, offset, label in NOTICE_WINDOWS:
            target = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
            rows = conn.execute(
                f"""
                SELECT m.id, m.customer_id, m.started_at, m.expires_at,
                       c.first_name, c.last_name, ce.email
                  FROM customer_memberships m
                  JOIN customers c ON c.customer_id = m.customer_id
                  LEFT JOIN customer_emails ce
                         ON ce.customer_id = m.customer_id AND ce.is_primary = 1
                 WHERE m.expires_at = ?
                   AND m.{col} IS NULL
                """,
                (target,),
            ).fetchall()

            for r in rows:
                # Skip if a later term exists (already renewed) — stamp so we don't retry.
                later = conn.execute(
                    """SELECT 1 FROM customer_memberships
                        WHERE customer_id = ? AND started_at > ? LIMIT 1""",
                    (r["customer_id"], r["started_at"]),
                ).fetchone()
                if later:
                    conn.execute(
                        f"UPDATE customer_memberships SET {col} = datetime('now') WHERE id = ?",
                        (r["id"],),
                    )
                    counts["skipped_renewed"] += 1
                    continue

                if not r["email"]:
                    logger.info("Membership notice (%s): no email for customer %s", label, r["customer_id"])
                    continue

                term = dict(r)
                customer = {"first_name": r["first_name"], "last_name": r["last_name"]}
                try:
                    subject, html = render_notice_email(label, term, customer)
                    sent = send_email(r["email"], subject, html)
                    if sent:
                        conn.execute(
                            f"UPDATE customer_memberships SET {col} = datetime('now') WHERE id = ?",
                            (r["id"],),
                        )
                        counts[label] += 1
                except Exception:
                    logger.exception("Membership notice (%s) failed for term %s", label, r["id"])

            conn.commit()

        # 2. No-response admin digest.
        digest_target = (today - timedelta(days=NO_RESPONSE_DIGEST_DAYS)).strftime("%Y-%m-%d")
        no_responders = conn.execute(
            """
            SELECT m.id, m.customer_id, m.expires_at, m.notice_lapsed_sent_at,
                   COALESCE(NULLIF(TRIM(c.first_name||' '||c.last_name),''), '(unknown)') AS full_name,
                   ce.email AS member_email
              FROM customer_memberships m
              JOIN customers c ON c.customer_id = m.customer_id
              LEFT JOIN customer_emails ce
                     ON ce.customer_id = m.customer_id AND ce.is_primary = 1
             WHERE m.notice_lapsed_sent_at IS NOT NULL
               AND DATE(m.notice_lapsed_sent_at) <= ?
               AND m.roster_choice IS NULL
               AND m.roster_admin_notified_at IS NULL
               AND NOT EXISTS (
                   SELECT 1 FROM customer_memberships m2
                    WHERE m2.customer_id = m.customer_id
                      AND m2.started_at > m.started_at
               )
            """,
            (digest_target,),
        ).fetchall()

        if no_responders and send_email:
            base = os.getenv("APP_BASE_URL", "https://tgf-tracker.up.railway.app").rstrip("/")
            rows_html = "".join(
                f"""<tr>
  <td style="padding:0.4rem 0.6rem; border-bottom:1px solid #e5e7eb;">{r['full_name']}</td>
  <td style="padding:0.4rem 0.6rem; border-bottom:1px solid #e5e7eb;"><a href="mailto:{r['member_email'] or ''}">{r['member_email'] or '—'}</a></td>
  <td style="padding:0.4rem 0.6rem; border-bottom:1px solid #e5e7eb;">{r['expires_at']}</td>
  <td style="padding:0.4rem 0.6rem; border-bottom:1px solid #e5e7eb;"><a href="{base}/customers?customer_id={r['customer_id']}">Open</a></td>
</tr>"""
                for r in no_responders
            )
            subject = f"[Roster] {len(no_responders)} member(s) didn't respond — please remove from Golf Genius"
            body = f"""<p>The following {len(no_responders)} member(s) received the lapsed-membership final notice {NO_RESPONSE_DIGEST_DAYS}+ days ago and haven't clicked either roster button. Per the email instructions, they should now be removed from the Golf Genius rosters unless you've heard from them another way.</p>
<table style="border-collapse:collapse; width:100%; font-size:0.92rem;">
  <thead>
    <tr style="background:#f3f4f6;">
      <th style="padding:0.4rem 0.6rem; text-align:left; border-bottom:2px solid #e5e7eb;">Name</th>
      <th style="padding:0.4rem 0.6rem; text-align:left; border-bottom:2px solid #e5e7eb;">Email</th>
      <th style="padding:0.4rem 0.6rem; text-align:left; border-bottom:2px solid #e5e7eb;">Expired</th>
      <th style="padding:0.4rem 0.6rem; text-align:left; border-bottom:2px solid #e5e7eb;">&nbsp;</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
<p style="font-size:0.82rem; color:#6b7280;">A late response or renewal will still cancel the removal — this list reflects state as of when the digest ran.</p>"""
            try:
                ok = send_email(ADMIN_NOTIFY_EMAIL, subject, _email_shell(body))
                if ok:
                    ids = ",".join(str(r["id"]) for r in no_responders)
                    conn.execute(
                        f"UPDATE customer_memberships "
                        f"SET roster_admin_notified_at = datetime('now') "
                        f"WHERE id IN ({ids})"
                    )
                    conn.commit()
                    counts["digest_sent"] = len(no_responders)
            except Exception:
                logger.exception("No-response digest send failed")

    logger.info("daily_membership_job: %s", counts)
    return counts
