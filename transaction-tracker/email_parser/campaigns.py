"""Lead campaigns + campaign stats (mailbox #391, Kerry-ratified
2026-09-03 AM).

The CAMPAIGN ENTITY: a `lead_campaigns` row per ad campaign (Meta),
organic bucket, or manual/historical import. Leads link through
`leads.campaign_id`, auto-filled from the Meta attribution already in
the payload (hsa_cam → ad_campaign_id) and assignable by hand for
organic/unattributed leads. Designed so the deferred 2024–2025 backfill
(item 4) and the "Historical" reactivation campaign (item 5) are plain
rows with source='historical' + manual lead assignment — no schema
change needed later.

METRIC DEFINITIONS (Kerry's, verbatim):
  CPL   = ad spend / leads
  CPP   = Cost Per Player = ad spend / unique leads who became a PLAYER
          (registered any event OR became a member; both counts once)
  CPMem = Cost Per Member = ad spend / leads who became members
          (never "CPM" — that is cost-per-mille in the Meta panel)
Each reported CURRENT (to date) and 30-DAY TRAILING: conversions keep
arriving after spend stops, so the honest read counts conversions
through 30 days after the last dollar (campaign end date). While that
window is still open the trailing figure equals current and the panel
says when the window closes.

META PANEL: spend, impressions, reach, frequency, link clicks, CTR,
CPM, leads, CPL from the Marketing API insights edge
(act_2353186181735308) once META_ACCESS_TOKEN lands on Railway;
fallback = the campaign row's manual spend (spend_manual) so CPL / CPP /
CPMem work from day one.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# The same rows the lead pipeline treats as "puts a PERSON in the
# system, not a purchase" — never an event registration.
from .leads import PLACEHOLDER_MERCHANTS  # noqa: E402

META_AD_ACCOUNT_ID = "2353186181735308"
META_GRAPH_VERSION = "v21.0"
META_INSIGHT_FIELDS = ("spend,impressions,reach,frequency,"
                       "inline_link_clicks,ctr,cpm,actions")
TRAILING_DAYS = 30
INSIGHTS_STALE_MINUTES = 60

# The current campaign (Kerry 2026-09-03) — seeded once, then Kerry's
# rows rule. Dates from Meta (start 2026-08-27, stop 2026-09-06 CT).
DEFAULT_CAMPAIGNS = [
    {"name": "Fall 2026 Leads", "source": "meta",
     "meta_campaign_id": "120253511733060195",
     "start_date": "2026-08-27", "end_date": "2026-09-06",
     "spend_manual": None,
     "notes": "Meta 'TGF Leads Campaign - Fall 2026 Season'"},
]
CAMPAIGN_SOURCES = ("meta", "organic", "manual", "historical")
HOT_TAGS = {"Call back", "Interested", "Coming to event"}
INTERESTED_TAGS = {"Interested", "Coming to event"}


def _meta_token() -> str | None:
    return (os.getenv("META_ACCESS_TOKEN") or "").strip() or None


# ── schema ───────────────────────────────────────────────────────────

def ensure_campaigns_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_campaigns (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT NOT NULL UNIQUE,
            source           TEXT NOT NULL DEFAULT 'meta',
            meta_campaign_id TEXT,
            start_date       TEXT,
            end_date         TEXT,
            spend_manual     REAL,
            notes            TEXT,
            created_at       TEXT DEFAULT (datetime('now')),
            updated_at       TEXT DEFAULT (datetime('now'))
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_campaign_insights (
            campaign_id  INTEGER PRIMARY KEY
                         REFERENCES lead_campaigns(id) ON DELETE CASCADE,
            fetched_at   TEXT,
            payload      TEXT,
            error        TEXT
        )""")
    for col in ("campaign_id INTEGER REFERENCES lead_campaigns(id)",
                "converted_at TEXT"):
        try:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    # Seed the current campaign once (by meta id — a rename survives).
    for c in DEFAULT_CAMPAIGNS:
        if not conn.execute(
                "SELECT 1 FROM lead_campaigns WHERE meta_campaign_id = ? "
                "OR name = ?", (c["meta_campaign_id"], c["name"])).fetchone():
            conn.execute(
                "INSERT INTO lead_campaigns (name, source, meta_campaign_id, "
                "start_date, end_date, spend_manual, notes) "
                "VALUES (?,?,?,?,?,?,?)",
                (c["name"], c["source"], c["meta_campaign_id"],
                 c["start_date"], c["end_date"], c["spend_manual"],
                 c["notes"]))
    # converted_at backfill for rows converted before the column
    # existed (touched_at is the closest honest stamp we hold).
    try:
        conn.execute(
            "UPDATE leads SET converted_at = COALESCE(touched_at, "
            "arrived_at, first_seen_at) WHERE status = 'converted' "
            "AND converted_at IS NULL")
    except sqlite3.OperationalError:
        pass


def link_leads_to_campaigns(conn: sqlite3.Connection) -> int:
    """Auto-link unassigned leads whose payload carries a Meta campaign
    id matching a campaign row. Manual assignments are never touched
    (campaign_id already set). Returns rows linked."""
    ids = {r["meta_campaign_id"]: r["id"] for r in conn.execute(
        "SELECT id, meta_campaign_id FROM lead_campaigns "
        "WHERE meta_campaign_id IS NOT NULL AND meta_campaign_id != ''")}
    if not ids:
        return 0
    n = 0
    for r in conn.execute("SELECT id, payload FROM leads "
                          "WHERE campaign_id IS NULL AND payload IS NOT NULL "
                          "AND merged_into IS NULL"
                          ).fetchall():
        try:
            p = json.loads(r["payload"] or "{}")
        except Exception:
            continue
        cid = ids.get(str(p.get("ad_campaign_id") or ""))
        if cid:
            conn.execute("UPDATE leads SET campaign_id = ? WHERE id = ?",
                         (cid, r["id"]))
            n += 1
    return n


# ── campaign CRUD ────────────────────────────────────────────────────

def list_campaigns(db_path: str | Path | None = None) -> list[dict]:
    from . import database as db
    with db._connect(db_path) as conn:
        ensure_campaigns_table(conn)
        rows = [dict(r) for r in conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM leads l "
            "             WHERE l.campaign_id = c.id "
            "             AND l.merged_into IS NULL) AS lead_count, "
            "i.fetched_at AS insights_fetched_at, i.payload AS insights, "
            "i.error AS insights_error "
            "FROM lead_campaigns c "
            "LEFT JOIN lead_campaign_insights i ON i.campaign_id = c.id "
            "ORDER BY COALESCE(c.start_date, c.created_at) DESC, c.id DESC")]
        conn.commit()
    for r in rows:
        try:
            r["insights"] = json.loads(r["insights"]) if r.get("insights") else None
        except Exception:
            r["insights"] = None
    return rows


def set_campaign(campaign_id: int | None = None, name: str | None = None,
                 source: str | None = None, meta_campaign_id: str | None = None,
                 start_date: str | None = None, end_date: str | None = None,
                 spend_manual: float | None = None, notes: str | None = None,
                 db_path: str | Path | None = None) -> dict:
    """Create (no id, name required) or update (id) a campaign row.
    Only the fields passed change. spend_manual is the fallback spend
    while META_ACCESS_TOKEN is not set (or for organic/manual rows)."""
    from . import database as db
    if source is not None and source not in CAMPAIGN_SOURCES:
        return {"error": f"source must be one of {CAMPAIGN_SOURCES}"}
    with db._connect(db_path) as conn:
        ensure_campaigns_table(conn)
        if campaign_id is None:
            if not (name or "").strip():
                return {"error": "name required"}
            if conn.execute("SELECT 1 FROM lead_campaigns WHERE name = ?",
                            (name.strip(),)).fetchone():
                return {"error": f"campaign '{name.strip()}' exists"}
            conn.execute(
                "INSERT INTO lead_campaigns (name, source, meta_campaign_id, "
                "start_date, end_date, spend_manual, notes) VALUES (?,?,?,?,?,?,?)",
                (name.strip(), source or "manual", meta_campaign_id or None,
                 start_date or None, end_date or None, spend_manual,
                 notes or None))
            campaign_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            if not conn.execute("SELECT 1 FROM lead_campaigns WHERE id = ?",
                                (campaign_id,)).fetchone():
                return {"error": f"campaign {campaign_id} not found"}
            sets, vals = [], []
            for col, v in (("name", name), ("source", source),
                           ("meta_campaign_id", meta_campaign_id),
                           ("start_date", start_date), ("end_date", end_date),
                           ("spend_manual", spend_manual), ("notes", notes)):
                if v is not None:
                    sets.append(f"{col} = ?")
                    vals.append(v.strip() if isinstance(v, str) else v)
            if sets:
                sets.append("updated_at = datetime('now')")
                conn.execute(f"UPDATE lead_campaigns SET {', '.join(sets)} "
                             "WHERE id = ?", vals + [campaign_id])
        linked = link_leads_to_campaigns(conn)
        conn.commit()
        row = dict(conn.execute("SELECT * FROM lead_campaigns WHERE id = ?",
                                (campaign_id,)).fetchone())
    row["linked"] = linked
    row["ok"] = True
    return row


def set_lead_campaign(lead_id: int, campaign_id: int | None,
                      author: str = "", db_path: str | Path | None = None,
                      ) -> dict:
    """Assign (or clear, campaign_id None) a lead's campaign by hand —
    organic / unattributed leads, or a historical import. Audited via
    an auto note."""
    from . import database as db
    with db._connect(db_path) as conn:
        ensure_campaigns_table(conn)
        row = conn.execute("SELECT id, campaign_id FROM leads WHERE id = ?",
                           (lead_id,)).fetchone()
        if not row:
            return {"error": f"lead {lead_id} not found"}
        new_name = None
        if campaign_id is not None:
            c = conn.execute("SELECT name FROM lead_campaigns WHERE id = ?",
                             (campaign_id,)).fetchone()
            if not c:
                return {"error": f"campaign {campaign_id} not found"}
            new_name = c["name"]
        old = row["campaign_id"]
        old_name = None
        if old:
            o = conn.execute("SELECT name FROM lead_campaigns WHERE id = ?",
                             (old,)).fetchone()
            old_name = o["name"] if o else str(old)
        conn.execute("UPDATE leads SET campaign_id = ? WHERE id = ?",
                     (campaign_id, lead_id))
        if old != campaign_id:
            conn.execute(
                "INSERT INTO lead_notes (lead_id, author, note) VALUES (?,?,?)",
                (lead_id, "auto",
                 f"Campaign set to {new_name or 'none'} by "
                 f"{(author or 'manager').strip()}"
                 + (f" (was {old_name})" if old_name else "")))
        conn.commit()
    return {"id": lead_id, "campaign_id": campaign_id,
            "campaign_name": new_name, "ok": True}


# ── Meta insights ────────────────────────────────────────────────────

def _parse_money(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _normalize_insights(raw: dict) -> dict:
    """Marketing API insights row → the panel's fields."""
    out = {
        "spend": _parse_money(raw.get("spend")),
        "impressions": int(raw.get("impressions") or 0) or None,
        "reach": int(raw.get("reach") or 0) or None,
        "frequency": _parse_money(raw.get("frequency")),
        "link_clicks": int(raw.get("inline_link_clicks") or 0) or None,
        "ctr": _parse_money(raw.get("ctr")),
        "cpm": _parse_money(raw.get("cpm")),
        "meta_leads": None,
        "date_start": raw.get("date_start"),
        "date_stop": raw.get("date_stop"),
    }
    for a in raw.get("actions") or []:
        if a.get("action_type") in ("lead", "onsite_conversion.lead_grouped",
                                    "leadgen_grouped"):
            try:
                out["meta_leads"] = int(float(a.get("value") or 0))
            except (TypeError, ValueError):
                pass
            if a.get("action_type") == "lead":
                break
    return out


def fetch_meta_insights(meta_campaign_id: str, token: str | None = None,
                        timeout: int = 20) -> dict:
    """One campaign's lifetime insights from the Marketing API. Raises
    on transport / API error (the caller records the error text)."""
    token = token or _meta_token()
    if not token:
        raise RuntimeError("META_ACCESS_TOKEN not set")
    url = (f"https://graph.facebook.com/{META_GRAPH_VERSION}/"
           f"{meta_campaign_id}/insights")
    r = requests.get(url, params={"fields": META_INSIGHT_FIELDS,
                                  "date_preset": "maximum",
                                  "access_token": token}, timeout=timeout)
    body = r.json() if r.content else {}
    if r.status_code != 200 or "error" in body:
        msg = (body.get("error") or {}).get("message") or r.text[:200]
        raise RuntimeError(f"Meta insights {r.status_code}: {msg}")
    rows = body.get("data") or []
    return _normalize_insights(rows[0] if rows else {})


def refresh_meta_insights(db_path: str | Path | None = None,
                          force: bool = False) -> dict:
    """Pull insights for every campaign with a meta id; cached per
    campaign, refreshed when older than INSIGHTS_STALE_MINUTES. Safe
    no-op until META_ACCESS_TOKEN is set (fallback = manual spend)."""
    from . import database as db
    res = {"token": bool(_meta_token()), "refreshed": 0, "skipped": 0,
           "errors": []}
    if not _meta_token():
        res["note"] = "META_ACCESS_TOKEN not set — manual spend in use"
        return res
    with db._connect(db_path) as conn:
        ensure_campaigns_table(conn)
        rows = conn.execute(
            "SELECT c.id, c.meta_campaign_id, i.fetched_at "
            "FROM lead_campaigns c "
            "LEFT JOIN lead_campaign_insights i ON i.campaign_id = c.id "
            "WHERE c.meta_campaign_id IS NOT NULL AND c.meta_campaign_id != ''"
            ).fetchall()
        for r in rows:
            if not force and r["fetched_at"]:
                try:
                    age = datetime.utcnow() - datetime.fromisoformat(
                        r["fetched_at"][:19])
                    if age < timedelta(minutes=INSIGHTS_STALE_MINUTES):
                        res["skipped"] += 1
                        continue
                except Exception:
                    pass
            try:
                data = fetch_meta_insights(r["meta_campaign_id"])
                conn.execute(
                    "INSERT INTO lead_campaign_insights (campaign_id, "
                    "fetched_at, payload, error) VALUES (?, datetime('now'), "
                    "?, NULL) ON CONFLICT(campaign_id) DO UPDATE SET "
                    "fetched_at = excluded.fetched_at, payload = "
                    "excluded.payload, error = NULL",
                    (r["id"], json.dumps(data)))
                res["refreshed"] += 1
            except Exception as e:
                logger.warning("Meta insights failed for campaign %s: %s",
                               r["id"], e)
                res["errors"].append({"campaign_id": r["id"], "error": str(e)})
                conn.execute(
                    "INSERT INTO lead_campaign_insights (campaign_id, "
                    "fetched_at, payload, error) VALUES (?, NULL, NULL, ?) "
                    "ON CONFLICT(campaign_id) DO UPDATE SET error = "
                    "excluded.error", (r["id"], str(e)[:300]))
        conn.commit()
    return res


# ── stats ────────────────────────────────────────────────────────────

def _ratio(spend, n):
    if spend is None or not n:
        return None
    return round(spend / n, 2)


# ALL CAMPAIGNS carried spend but no Meta metrics — every other tile
# read "—" (Kerry 2026-09-04: "Looks like META data is not
# updating"). The insights were live and fresh the whole time; the
# roll-up bucket simply never got any. Sum what is additive and
# DERIVE the ratios, rather than averaging rates, which would be
# wrong the moment two campaigns differ in size.
def _roll_up_insights(rows: list[dict]) -> dict | None:
    ins = [c["insights"] for c in rows
           if c.get("insights") and c["insights"].get("spend") is not None]
    if not ins:
        return None
    if len(ins) == 1:
        return dict(ins[0])
    agg: dict = {"campaigns": len(ins)}
    for k in ("spend", "impressions", "reach", "link_clicks",
              "meta_leads"):
        vals = [i.get(k) for i in ins if i.get(k) is not None]
        agg[k] = sum(vals) if vals else None
    starts = [i.get("date_start") for i in ins if i.get("date_start")]
    stops = [i.get("date_stop") for i in ins if i.get("date_stop")]
    agg["date_start"] = min(starts) if starts else None
    agg["date_stop"] = max(stops) if stops else None
    imp, reach = agg.get("impressions"), agg.get("reach")
    # REACH IS PEOPLE, and the same person can be reached by two
    # campaigns, so a summed reach double-counts and the frequency
    # derived from it reads low. Flagged rather than hidden — the
    # number is still the best available.
    agg["frequency"] = (imp / reach) if imp and reach else None
    agg["reach_approx"] = True
    agg["ctr"] = (100.0 * agg["link_clicks"] / imp) \
        if imp and agg.get("link_clicks") is not None else None
    agg["cpm"] = (1000.0 * agg["spend"] / imp) \
        if imp and agg.get("spend") is not None else None
    return agg


def campaign_value(lead_rows: list[dict], conn,
                   db_path: str | Path | None = None,
                   gap_fill_seconds: float = 8.0) -> dict:
    """What a set of campaign leads has actually been worth to TGF.

    TWO different numbers, and the difference is the whole point:

      collected  — every dollar these customers have paid TGF, ever.
      margin     — what TGF KEPT of it (tgf_operating, the same bucket
                   the Monthly Money Flow waterfall calls TGF gross
                   margin), after course fees go to the course and prize
                   pools go to the winners.

    BOTH come from `acct_allocations`, deliberately. Summing
    `items.item_price` for the gross looked simpler and gave $0 against
    a real $245 of margin on production — SQLite is dynamically typed
    and that column is not reliably numeric. Reading both figures off
    the same rows also means ONE coverage number applies to both,
    instead of a gross that looks complete sitting next to a margin
    that is not.

    Most of an entry fee is pass-through. ROI computed on `collected`
    would read roughly six times better than the business actually did,
    which is exactly the number nobody should base an ad budget on. ROI
    here is margin-based; `collected` is reported alongside so the two
    are never confused.

    `acct_allocations` rows are written LAZILY, so margin is only known
    for orders that have been allocated. Rather than quietly under-report,
    this gap-fills the missing orders through the same allocator the
    money-flow report uses (idempotent), under a time budget, and returns
    `coverage_pct` so a partial answer is visible as partial.
    """
    from . import database as db
    import time as _t
    # WHY THE PEOPLE COUNT IS LOWER THAN THE LEAD COUNT (Kerry
    # 2026-09-04: "Why not all 103 people from campaign? Why only 97?").
    # Value is per PERSON and a lead is not a person: some leads have no
    # customer record yet, and one person can submit the form twice. The
    # panel has to say which, or the gap looks like lost money.
    ids = [r["customer_id"] for r in lead_rows if r.get("customer_id")]
    customer_ids = sorted(set(ids))
    out = {"leads": len(lead_rows), "customers": len(customer_ids),
           "leads_without_customer": sum(1 for r in lead_rows
                                         if not r.get("customer_id")),
           "duplicate_leads": len(ids) - len(customer_ids),
           "collected": 0.0, "margin": 0.0,
           "items": 0, "orders": 0, "allocated_orders": 0,
           "coverage_pct": None, "allocated_now": 0, "coverage_pending": 0}
    if not customer_ids:
        return out
    ph = ",".join("?" * len(customer_ids))
    rows = conn.execute(
        # items answers WHICH orders are theirs; the money comes from the
        # allocations layer below.
        f"SELECT i.id, i.order_id "
        f"FROM items i WHERE i.customer_id IN ({ph}) "
        f"AND COALESCE(i.transaction_status, 'active') = 'active' "
        f"AND i.parent_item_id IS NULL "
        f"AND i.merchant NOT IN ({','.join(repr(m) for m in PLACEHOLDER_MERCHANTS)})",
        tuple(customer_ids)).fetchall()
    out["items"] = len(rows)
    orders = sorted({r["order_id"] for r in rows if r["order_id"]})
    out["orders"] = len(orders)
    out["rows"] = []
    out["margin_actual"] = 0.0
    out["overstated"] = 0.0
    out["rows_reconcile"] = True
    if not orders:
        return out

    oph = ",".join("?" * len(orders))
    have = {r["order_id"] for r in conn.execute(
        f"SELECT DISTINCT order_id FROM acct_allocations "
        f"WHERE order_id IN ({oph})", tuple(orders)).fetchall()}
    # gap_fill_seconds <= 0 reads what is already allocated and writes
    # nothing — the escape hatch if the allocator ever misbehaves on a
    # big campaign, and what the tests use.
    missing = [o for o in orders if o not in have] if gap_fill_seconds > 0 else []
    deadline = _t.monotonic() + gap_fill_seconds
    for n, oid in enumerate(missing):
        if _t.monotonic() > deadline:
            out["coverage_pending"] = len(missing) - n
            break
        try:
            # db_path MUST ride along — without it the allocator writes
            # to the default database, which is silently wrong anywhere
            # but production.
            if db.calculate_order_allocation(oid, db_path=db_path):
                out["allocated_now"] += 1
        except Exception:
            logger.warning("campaign value: allocation failed for %s", oid,
                           exc_info=True)

    agg = conn.execute(
        f"SELECT COUNT(DISTINCT a.order_id) AS n, "
        f"       COALESCE(SUM(CAST(a.tgf_operating AS REAL)), 0) AS margin, "
        f"       COALESCE(SUM(CAST(a.total_collected AS REAL)), 0) AS collected "
        f"FROM acct_allocations a WHERE a.order_id IN ({oph})",
        tuple(orders)).fetchone()
    out["allocated_orders"] = agg["n"] or 0
    out["margin"] = round(agg["margin"] or 0.0, 2)
    out["collected"] = round(agg["collected"] or 0.0, 2)

    # The audit trail (Kerry 2026-09-04: "I want to make sure your math
    # is correct"). It earned its keep immediately: the headline margin
    # OVERSTATES what TGF kept.
    #
    # `tgf_operating` is the event's STANDARD markup
    # (_calc_event_allocation = tgf_markup + side_markup). It does not
    # look at what the player actually paid, so a 1st Timer who came in
    # $25 under the guest rate still books the full markup and the
    # shortfall is invisible. Memberships are exact; discounted rounds
    # are not.
    #
    # Hence two figures per row:
    #   margin_booked  — tgf_operating, what the books say.
    #   margin_actual  — money_in - course - surcharge - prizes, what
    #                    was genuinely left over.
    #
    # Getting `money_in` right took three tries and two corrections from
    # Kerry, so the wrong turns are recorded here rather than repeated:
    #   1. collected MINUS the processor fee — wrong; would have called
    #      every membership broken.
    #   2. collected, fee dropped entirely — also wrong: the customer
    #      PAYS the 3.5% on top and GoDaddy takes its own cut, and those
    #      are two different numbers.
    #   3. collected + transaction_fee - merchant_fee — right in shape,
    #      wrong in data, because transaction_fee is duplicated across
    #      the items of a multi-item order (see below).
    #   4. this one: the order's actual DEPOSIT, apportioned per item.
    # fee_in / fee_out are still reported per row so the processor spread
    # stays visible, but they no longer feed the margin.
    #
    # CORRECTION, Kerry 2026-09-04: "Logan isn't $60 in. It's $62.10 in
    # minus GoDaddy transaction fees. Whatever that is, that's the actual
    # money in."
    #
    # That sentence is the formula, and following it exposed a real bug.
    # `godaddy_order_splits.transaction_fee` is written from the PARSER's
    # per-item `transaction_fees` field, and on a MULTI-ITEM order the
    # parser stamps the ORDER's whole fee onto every item row. Summing it
    # per item therefore counts one fee two, three, four times. Michele
    # McCormick's order (Silverhorn $64 + membership $50) carries $3.99 on
    # BOTH rows; the order fee is $3.99, not $7.98. `merchant_fee` does not
    # have the problem — the writer pro-rates it at insert time.
    #
    # So stop reconstructing money-in from fee legs and read what actually
    # landed: `acct_transactions.net_deposit` is the deposit GoDaddy made
    # for the order, i.e. exactly "charged minus what GoDaddy took". Split
    # it across the order's items in proportion to what each item charged.
    #
    # Read-side on purpose. The root cause is at WRITE time and the stored
    # split rows are money records that other reports read; rewriting them
    # is a migration, not a bug fix, and needs its own ratification.
    money_in: dict = {}
    fees: dict = {}
    try:
        for fr in conn.execute(
                "SELECT s.item_id, t.net_deposit, "
                "  SUM(CASE WHEN s.split_type = 'registration' "
                "           THEN s.amount ELSE 0 END) AS reg, "
                "  SUM(CASE WHEN s.split_type = 'transaction_fee' "
                "           THEN ABS(s.amount) ELSE 0 END) AS fee_in, "
                "  SUM(CASE WHEN s.split_type = 'merchant_fee' "
                "           THEN ABS(s.amount) ELSE 0 END) AS fee_out, "
                "  (SELECT SUM(s2.amount) FROM godaddy_order_splits s2 "
                "   WHERE s2.transaction_id = s.transaction_id "
                "   AND s2.split_type = 'registration') AS order_reg "
                "FROM godaddy_order_splits s "
                "LEFT JOIN acct_transactions t ON t.id = s.transaction_id "
                "WHERE s.item_id IS NOT NULL "
                "GROUP BY s.item_id").fetchall():
            _reg = float(fr["reg"] or 0)
            _order_reg = float(fr["order_reg"] or 0)
            _net = fr["net_deposit"]
            fees[fr["item_id"]] = (float(fr["fee_in"] or 0),
                                   float(fr["fee_out"] or 0))
            if _net is not None and _order_reg > 0:
                money_in[fr["item_id"]] = round(
                    float(_net) * (_reg / _order_reg), 2)
    except Exception:
        logger.warning("fee splits unavailable — margin_actual falls back "
                       "to the collected amount", exc_info=True)

    out["rows"] = []
    for r in conn.execute(
            f"SELECT a.order_id, a.event_name, a.allocation_date, "
            f"       a.allocation_status, a.notes, "
            f"       CAST(COALESCE(a.total_collected,0) AS REAL) AS collected, "
            f"       CAST(COALESCE(a.course_payable,0) AS REAL) AS course, "
            f"       CAST(COALESCE(a.course_surcharge,0) AS REAL) AS surcharge, "
            f"       CAST(COALESCE(a.prize_pool,0) AS REAL) AS prizes, "
            f"       CAST(COALESCE(a.godaddy_fee,0) AS REAL) AS fee, "
            f"       CAST(COALESCE(a.tax_reserve,0) AS REAL) AS tax, "
            f"       CAST(COALESCE(a.tgf_operating,0) AS REAL) AS margin, "
            f"       a.item_id, i.item_name, "
            f"       TRIM(COALESCE(c.first_name,'')||' '||"
            f"            COALESCE(c.last_name,'')) AS player "
            f"FROM acct_allocations a "
            f"LEFT JOIN items i ON i.id = a.item_id "
            f"LEFT JOIN customers c ON c.customer_id = i.customer_id "
            f"WHERE a.order_id IN ({oph}) "
            f"ORDER BY a.allocation_date, a.order_id",
            tuple(orders)).fetchall():
        d = dict(r)
        d["player"] = (d.get("player") or "").strip() or "(unknown)"
        d["margin_booked"] = d["margin"]
        d["fee_in"] = round(fees.get(d.get("item_id"), (0.0, 0.0))[0], 2)
        d["fee_out"] = round(fees.get(d.get("item_id"), (0.0, 0.0))[1], 2)
        d["fee_net"] = round(d["fee_in"] - d["fee_out"], 2)
        # MONEY IN = this item's share of what GoDaddy actually deposited
        # for the order (Kerry's rule, above). `collected` is the sticker
        # price and is kept for display, but it is not what arrived.
        _mi = money_in.get(d.get("item_id"))
        d["money_in"] = _mi if _mi is not None else d["collected"]
        d["money_in_source"] = "deposit" if _mi is not None else "collected"
        d["margin_actual"] = round(d["money_in"] - d["course"]
                                   - d["surcharge"] - d["prizes"], 2)
        # Positive = the books claim more than was actually left over.
        d["overstated"] = round(d["margin_booked"] - d["margin_actual"], 2)
        for k in ("collected", "course", "surcharge", "prizes", "fee",
                  "tax", "margin", "margin_booked", "margin_actual",
                  "overstated", "fee_in", "fee_out", "fee_net", "money_in"):
            d[k] = round(d[k], 2)
        out["rows"].append(d)
    out["margin_actual"] = round(sum(r["margin_actual"] for r in out["rows"]), 2)
    out["overstated"] = round(out["margin"] - out["margin_actual"], 2)
    out["coverage_pct"] = (round(100.0 * out["allocated_orders"]
                                 / out["orders"], 1) if out["orders"] else None)
    out["rows_reconcile"] = abs(out["overstated"]) < 0.05
    return out


def _funnel(leads: list[dict], today: date, cutoff: date | None) -> dict:
    """Counts for one bucket. cutoff = the trailing-window end (campaign
    end + 30d); None = no window (organic / undated)."""
    f = {"leads": len(leads), "touched": 0, "replied": 0, "interested": 0,
         "players": 0, "members": 0, "registered": 0, "dismissed": 0,
         "new": 0, "players_trailing": 0, "members_trailing": 0}
    for l in leads:
        st = l.get("status")
        tag = l.get("tag") or ""
        if st == "new":
            f["new"] += 1
        if st in ("touched", "converted"):
            f["touched"] += 1
            # REPLIED is the STATS metric and it means one thing only:
            # a human wrote back to our outreach. Kerry ruled it in
            # mailbox #412 — "Responded definitely needs to be resolved.
            # We don't want to put that into those statistics."
            #
            # So this excludes, deliberately:
            #   * `auto` notes (bookkeeping the app wrote to itself),
            #   * GG RSVPs and HubSpot re-submissions (the note query
            #     that feeds note_count drops authors HS / GG / auto),
            #   * bare `status == converted` — somebody can register on
            #     Golf Genius without ever answering a text, and that is
            #     a conversion, not a reply.
            # HOT_TAGS stay in: nothing sets them automatically (the
            # only machine-written tags are `Became member` and
            # `Registered event`), so a hot tag means Kerry heard back.
            #
            # The QUEUE's broader RESPONDED is a different word for a
            # different job and is unchanged — it answers "who still
            # needs me", this answers "did our outreach work".
            # replied_at is the durable record, stamped the moment a
            # reply is seen; the tag and note checks stay as a fallback
            # for anything that predates it or is stamped elsewhere.
            if (l.get("replied_at") or tag in HOT_TAGS
                    or (l.get("note_count") or 0) > 0):
                f["replied"] += 1
        # UNIQUE leads who have registered for an event, members
        # included — a member who also plays belongs in both counts, so
        # this deliberately overlaps `members` rather than partitioning.
        if (l.get("event_regs") or 0) > 0:
            f["registered"] += 1
        if tag in INTERESTED_TAGS:
            f["interested"] += 1
        if st == "dismissed":
            f["dismissed"] += 1
        if st == "converted":
            f["players"] += 1
            is_mem = tag == "Became member"
            if is_mem:
                f["members"] += 1
            conv = (l.get("converted_at") or "")[:10]
            inside = True
            if cutoff and conv:
                try:
                    inside = date.fromisoformat(conv) <= cutoff
                except ValueError:
                    inside = True
            if inside:
                f["players_trailing"] += 1
                if is_mem:
                    f["members_trailing"] += 1
    f["reply_pct"] = (round(100.0 * f["replied"] / f["touched"], 1)
                      if f["touched"] else None)
    return f


def campaign_stats(db_path: str | Path | None = None,
                   today: str | None = None,
                   gap_fill_seconds: float = 8.0) -> dict:
    """Per-campaign + all-time stats for the Lead Center stats view:
    META panel (insights or manual spend), FUNNEL panel with CPL / CPP /
    CPMem current + 30-day trailing, per-chapter split."""
    from . import database as db
    from .leads import _REPLY_EXCLUDE_SQL, ensure_leads_table
    from .timezone_utils import today_central_str
    today_d = date.fromisoformat(today or today_central_str())
    campaigns = list_campaigns(db_path)
    with db._connect(db_path) as conn:
        # Stats reads lead columns, so the lead MIGRATIONS have to have
        # run — this entry point cannot assume some other page got there
        # first. Skipping it is how `no such column: l.replied_at` took
        # the stats view down the moment v2.317.0 deployed.
        ensure_leads_table(conn)
        ensure_campaigns_table(conn)
        link_leads_to_campaigns(conn)
        conn.commit()
        leads = [dict(r) for r in conn.execute(
            "SELECT l.id, l.status, l.tag, l.chapter, l.campaign_id, "
            "l.customer_id, l.converted_at, l.arrived_at, l.replied_at, "
            # Only notes a PERSON wrote count toward REPLIED — see
            # leads.REPLY_EXCLUDED_NOTE_AUTHORS for why GG and HS are out
            # here but still disarm the alarm in the queue. Matched
            # case-insensitively so an author stored as 'gg' can't slip
            # in as a reply.
            "(SELECT COUNT(*) FROM lead_notes n WHERE n.lead_id = l.id "
            f" AND COALESCE(LOWER(n.author), '') NOT IN ({_REPLY_EXCLUDE_SQL})) "
            "AS note_count, "
            # Kerry 2026-09-04: "Registered event guests should show
            # total unique leads from this campaign who have registered
            # for events, INCLUDING those who have become members." The
            # tag can only say one thing and membership outranks event,
            # so a member who also plays was invisible in the event
            # count. This asks the items table instead of the tag. Same
            # predicate the conversion auto-detect uses.
            "(SELECT COUNT(*) FROM items i WHERE i.customer_id = "
            " l.customer_id AND COALESCE(i.transaction_status,'active') "
            " = 'active' AND i.parent_item_id IS NULL "
            f"AND i.merchant NOT IN ({','.join(repr(m) for m in PLACEHOLDER_MERCHANTS)}) "
            " AND UPPER(COALESCE(i.item_name,'')) NOT LIKE '%MEMBERSHIP%') "
            "AS event_regs "
            "FROM leads l "
            # A merged duplicate keeps its campaign link (and its
            # external_id) but is NOT a second lead — counting it would
            # inflate leads and deflate CPL (v2.295.1, the Shane Winter
            # merge).
            "WHERE l.merged_into IS NULL").fetchall()]
    by_campaign: dict = {}
    for l in leads:
        by_campaign.setdefault(l.get("campaign_id"), []).append(l)

    def _bucket(name, rows, spend, spend_source, end_date, insights=None,
                cid=None, value=None):
        cutoff = None
        window_open = None
        if end_date:
            try:
                cutoff = date.fromisoformat(end_date) + timedelta(days=TRAILING_DAYS)
                window_open = today_d <= cutoff
            except ValueError:
                cutoff = None
        f = _funnel(rows, today_d, cutoff)
        chapters = {}
        for ch in ("San Antonio", "Austin", None):
            sub = [r for r in rows if (r.get("chapter") or None) == ch]
            if sub:
                chapters[ch or "unrouted"] = _funnel(sub, today_d, cutoff)
        cost = {
            "cpl": _ratio(spend, f["leads"]),
            "cpp": _ratio(spend, f["players"]),
            "cpmem": _ratio(spend, f["members"]),
            "cpp_trailing": _ratio(spend, f["players_trailing"]),
            "cpmem_trailing": _ratio(spend, f["members_trailing"]),
        }
        # ROI on MARGIN, never on gross collected (Kerry 2026-09-04:
        # "a calculated ROI on the stats, that includes the lifetime
        # value of the campaign"). Most of an entry fee passes straight
        # through to the course and the prize pool, so ROI on collected
        # would flatter the number by roughly 6x.
        roi = None
        if value and spend:
            roi = {
                "spend": round(spend, 2),
                "collected": value.get("collected"),
                "margin": value.get("margin"),
                "net": round((value.get("margin") or 0) - spend, 2),
                # 1.0 = broke even. 2.4 = every ad dollar came back as
                # $2.40 of TGF margin.
                "roas_margin": (round((value.get("margin") or 0) / spend, 2)
                                if spend else None),
                "roas_collected": (round((value.get("collected") or 0) / spend, 2)
                                   if spend else None),
                "pct": (round(100.0 * ((value.get("margin") or 0) - spend)
                              / spend, 1) if spend else None),
                "value_per_lead": (round((value.get("margin") or 0)
                                         / f["leads"], 2) if f["leads"] else None),
                # The audit's honest figure, and what ROI looks like on
                # it. The headline still quotes the booked margin, but
                # nobody should have to open a table to learn the two
                # differ.
                "margin_actual": value.get("margin_actual"),
                "overstated": value.get("overstated"),
                "reconciles": value.get("rows_reconcile"),
                "roas_actual": (round((value.get("margin_actual") or 0) / spend, 2)
                                if spend else None),
                "coverage_pct": value.get("coverage_pct"),
                "coverage_pending": value.get("coverage_pending"),
            }
        return {"id": cid, "name": name, "spend": spend,
                "spend_source": spend_source, "end_date": end_date,
                "trailing_cutoff": cutoff.isoformat() if cutoff else None,
                "trailing_window_open": window_open,
                "meta": insights, "funnel": f, "cost": cost,
                "value": value, "roi": roi,
                "chapters": chapters}

    out_campaigns = []
    total_spend = 0.0
    any_spend = False
    latest_end = None
    for c in campaigns:
        ins = c.get("insights")
        spend = ins.get("spend") if ins and ins.get("spend") is not None \
            else c.get("spend_manual")
        spend_source = ("meta" if ins and ins.get("spend") is not None
                        else "manual" if c.get("spend_manual") is not None
                        else "none")
        if spend is not None:
            total_spend += spend
            any_spend = True
        if c.get("end_date") and (latest_end is None
                                  or c["end_date"] > latest_end):
            latest_end = c["end_date"]
        _rows = by_campaign.get(c["id"], [])
        with db._connect(db_path) as _vc:
            _val = campaign_value(_rows, _vc, db_path, gap_fill_seconds)
        b = _bucket(c["name"], _rows, spend,
                    spend_source, c.get("end_date"), ins, c["id"], _val)
        b.update({"source": c.get("source"),
                  "meta_campaign_id": c.get("meta_campaign_id"),
                  "start_date": c.get("start_date"),
                  "spend_manual": c.get("spend_manual"),
                  "insights_fetched_at": c.get("insights_fetched_at"),
                  "insights_error": c.get("insights_error"),
                  "notes": c.get("notes")})
        out_campaigns.append(b)
    organic = by_campaign.get(None, [])
    unattributed = _bucket("Unattributed / organic", organic, None, "none",
                           None)
    all_ins = _roll_up_insights(campaigns)
    with db._connect(db_path) as _vc:
        _all_val = campaign_value(leads, _vc, db_path, gap_fill_seconds)
    all_bucket = _bucket("All campaigns", leads,
                         total_spend if any_spend else None,
                         "meta" if all_ins else ("sum" if any_spend
                                                else "none"),
                         latest_end, all_ins, None, _all_val)
    if all_ins:
        # so the panel can date-stamp the roll-up like a single campaign
        all_bucket["insights_fetched_at"] = max(
            (c.get("insights_fetched_at") or "" for c in campaigns),
            default="") or None
    return {"today": today_d.isoformat(), "meta_token": bool(_meta_token()),
            "trailing_days": TRAILING_DAYS,
            "definitions": {
                "CPL": "ad spend / leads",
                "CPP": "ad spend / unique leads who became a player "
                       "(registered any event or became a member)",
                "CPMem": "ad spend / leads who became members",
                "trailing": f"conversions counted through {TRAILING_DAYS} "
                            "days after the campaign's last spend day",
            },
            "campaigns": out_campaigns, "unattributed": unattributed,
            "all": all_bucket}
