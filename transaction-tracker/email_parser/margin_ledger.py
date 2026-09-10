"""
Margin ledger reads — the questions Kerry asked on 2026-09-09 after the
fee work, in his words:

  "Our bookkeeping needs to be above reproach and account for every
   penny and I need to know what needs to be in our liability buckets
   too."

  "ultimately I want you to tell me where the gaps are in the past
   event costs ... so I can give you that information for our
   bookkeeping and reporting/allocations to be correct."

  "All memberships fund shirts but here's how it needs to be allocated.
   August 2025 thru July 2026 goes to 2026 Lone Star Cup shirt fund,
   while August 2026 to July 2027 goes to 2027 shirt fund."

Three reads, all read-only:

  * `lsc_fund_year(date)` — which Lone Star Cup a membership funds.
  * `margin_gaps()` — every event/item class dated before the
    margin-model cutover, with what the books say (rate card) beside
    what the residual model would book today, and WHY they differ.
    This is the list Kerry fills in. It never writes.
  * `liability_buckets()` — what TGF is holding for someone else or has
    earmarked: prize payouts owed, credits held, shirt fund by Cup
    year, the HIO pot, sales-tax reserve by month (filed / open).
  * `membership_gap()` — the first gap group: every membership sold,
    grouped by what was sold, booked vs today's decomposition, and the
    prices the table does not know. `apply=True` rebooks membership
    rows only.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Sales tax is filed monthly by the 20th of the following month.
TAX_FILING_DAY = 20


def lsc_fund_year(date_str: str | None) -> int | None:
    """The Lone Star Cup year a membership sold on `date_str` funds.
    Memberships sold August through July fund the Cup played that
    OCTOBER: Aug 2025–Jul 2026 → the 2026 Cup, Aug 2026–Jul 2027 → the
    2027 Cup. Kerry 2026-09-09: "The Cup is typically in October ...
    That's the point. To allow time to order shirts with what was
    collected prior to City & TGF Championships as the funding
    source." """
    d = (str(date_str or "").strip())[:10]
    if len(d) < 7:
        return None
    try:
        y, m = int(d[:4]), int(d[5:7])
    except ValueError:
        return None
    return y + 1 if m >= 8 else y


def _cutover(conn) -> str:
    from . import database as db
    return (db._setting_via(conn, "margin_model_cutover")
            or db.MARGIN_MODEL_CUTOVER)[:10]


def margin_gaps(db_path: str | Path | None = None, limit: int = 60) -> dict:
    """For every allocation dated BEFORE the cutover: what the books say
    versus what the residual model would book from today's event
    configuration, grouped by event, with a reason. Measure-only.

    A row's "would book" is computed through the ordinary allocator
    under the thread-local cutover override, so nothing is written and
    live allocations are unaffected. The reasons are heuristics from the
    shapes — what is missing, not what to enter — so Kerry can supply
    the missing facts (course cost per package, the membership tier
    prices of the day, prize structures) event by event."""
    from . import database as db
    from .fee_splits import rebook_spread_since
    with db._connect(db_path) as conn:
        cutover = _cutover(conn)
        events = {r["item_name"].upper(): dict(r) for r in conn.execute(
            "SELECT item_name, event_date, course, chapter, course_cost, "
            "course_cost_9, course_cost_18, event_type FROM events "
            "WHERE item_name IS NOT NULL")}
        first_date = conn.execute(
            "SELECT MIN(substr(order_date,1,10)) AS d FROM items "
            "WHERE merchant = 'The Golf Fellowship' AND order_date IS NOT NULL"
        ).fetchone()["d"] or "2025-12-01"
    # Everything before the real cutover, evaluated as if the residual
    # model had always applied.
    m = rebook_spread_since(first_date, dry_run=True, db_path=db_path,
                            cutover_override=first_date)
    groups: dict = defaultdict(lambda: {
        "event": None, "rows": 0, "booked": 0.0, "would_book": 0.0,
        "delta": 0.0, "negative_rows": 0, "negative_sum": 0.0, "new_rows": 0,
        "sample_order": None, "event_date": None, "course_cost": None,
        "event_type": None})
    # By ORDER month: the credit the signed-tax ruling would have given
    # each filed month had the residual model applied then. Kerry
    # 2026-09-09: "your (or CA's) calculations for my past month's sales
    # tax numbers ... probably overshot them because we weren't recording
    # any negative sales tax impact." Memberships are excluded from the
    # negative figures (their gap is decomposition, not a loss).
    by_month: dict = defaultdict(lambda: {
        "rows": 0, "booked": 0.0, "would_book": 0.0,
        "negative_rows": 0, "negative_sum": 0.0, "negative_tax_credit": 0.0})
    for c in m["changes"]:
        # Only rows before the real cutover are "gaps"; later rows are
        # already residual and moved only by their spread.
        name = (c.get("event_name") or "(unnamed)")
        g = groups[name.upper()]
        g["event"] = name
        g["rows"] += 1
        b, a = c["tgf_operating"]
        g["booked"] = round(g["booked"] + b, 2)
        g["would_book"] = round(g["would_book"] + a, 2)
        g["delta"] = round(g["delta"] + (a - b), 2)
        if a < 0:
            g["negative_rows"] += 1
            g["negative_sum"] = round(g["negative_sum"] + a, 2)
        if c.get("new_row"):
            g["new_rows"] += 1
        g["sample_order"] = g["sample_order"] or c["order_id"]
        _mo = (c.get("allocation_date") or "")[:7]
        if _mo and "MEMBERSHIP" not in name.upper():
            bm = by_month[_mo]
            bm["rows"] += 1
            bm["booked"] = round(bm["booked"] + b, 2)
            bm["would_book"] = round(bm["would_book"] + a, 2)
            if a < 0:
                bm["negative_rows"] += 1
                bm["negative_sum"] = round(bm["negative_sum"] + a, 2)
                bm["negative_tax_credit"] = round(bm["negative_sum"] * 0.0825, 2)
    out_rows = []
    for key, g in groups.items():
        ev = events.get(key)
        if ev:
            g["event_date"] = ev.get("event_date")
            g["course_cost"] = ev.get("course_cost")
            g["event_type"] = ev.get("event_type")
        name_u = key
        reasons = []
        if "MEMBERSHIP" in name_u:
            reasons.append("membership tier/contest pricing of the day differs from "
                           "today's model (44/69/244 + $10/contest − $10 shirts)")
        elif ev is None:
            reasons.append("no events row for this item name — nothing to cost against")
        else:
            if ev.get("course_cost") in (None, "", 0, 0.0) and \
               ev.get("course_cost_9") in (None, "", 0, 0.0) and \
               ev.get("course_cost_18") in (None, "", 0, 0.0):
                reasons.append("course cost is blank on the event")
            if any(k in name_u for k in ("CHAMPIONSHIP", "MATCHES", "CUP", "TOUR", "KICKOFF")):
                reasons.append("package/marquee event — per-package course cost and "
                               "prize structure not in the event row")
        if g["negative_rows"]:
            reasons.append(f"{g['negative_rows']} row(s) would book NEGATIVE margin "
                           f"(discount deeper than markup, or costs above price)")
        if abs(g["delta"]) > 25 * max(g["rows"], 1):
            reasons.append("per-row swing over $25 — configuration, not rounding")
        if not reasons:
            reasons.append("1st-Timer / discounted rounds booked at rate card; "
                           "residual would show the discount")
        g["reasons"] = reasons
        out_rows.append(g)
    out_rows.sort(key=lambda g: -abs(g["delta"]))
    return {
        "cutover": cutover,
        "history_from": first_date,
        "events": len(out_rows),
        "rows": sum(g["rows"] for g in out_rows),
        "booked_total": round(sum(g["booked"] for g in out_rows), 2),
        "would_book_total": round(sum(g["would_book"] for g in out_rows), 2),
        "delta_total": round(sum(g["delta"] for g in out_rows), 2),
        "note": ("Measure-only. 'would_book' is today's residual model applied to "
                 "history through the ordinary allocator; where it is absurd, the "
                 "event's cost/prize configuration is the gap, not the model."),
        "by_month": {k: by_month[k] for k in sorted(by_month)},
        "gaps": out_rows[:limit],
    }


def membership_gap(db_path: str | Path | None = None,
                   apply: bool = False) -> dict:
    """The MEMBERSHIP gap group (Kerry 2026-09-09: "Let's go with the
    membership gap recommendation first").

    Every active membership item in the Tracker's history, grouped by
    what was sold (price, New/Returning/Plus, contests bundled), with
    what the books hold beside what today's membership decomposition
    books: base (44 / 69 / 244 taxable) + $6 Monthly Points pool +
    $10 markup per contest + the contest pools + the $10 shirt
    set-aside. A group FITS when those parts sum to the price paid to
    the cent; a group that does not fit is a price the table does not
    know (a tier or bundle of the day) and is the question for Kerry.

    The membership decomposition never depended on the margin-model
    cutover, so "would book" here is exactly what an apply writes; the
    only cutover-gated part, the fee spread, stays off pre-cutover rows.
    `apply=True` rebooks ONLY membership rows (event rows in the same
    orders are untouched) and is audited by the caller."""
    from . import database as db
    from .fee_splits import rebook_spread_since
    with db._connect(db_path) as conn:
        cutover = _cutover(conn)
        first_date = conn.execute(
            "SELECT MIN(substr(order_date,1,10)) AS d FROM items "
            "WHERE merchant = 'The Golf Fellowship' AND order_date IS NOT NULL"
        ).fetchone()["d"] or "2025-12-01"
        lsc = db._membership_setaside("lsc_shirt", 10.0, conn)
        rows = [dict(r) for r in conn.execute(
            """SELECT i.id, i.order_id, i.order_date, i.item_price, i.customer,
                      i.returning_or_new, i.net_points_race, i.gross_points_race,
                      i.city_match_play, i.fall_net_points_race, i.item_name,
                      a.tgf_operating AS booked_tgf, a.prize_pool AS booked_pool,
                      a.lsc_shirt_fund AS booked_shirt, a.tax_reserve AS booked_tax
               FROM items i
               LEFT JOIN acct_allocations a ON a.item_id = i.id
               WHERE i.merchant = 'The Golf Fellowship'
                 AND UPPER(COALESCE(i.item_name,'')) LIKE '%MEMBERSHIP%'
                 AND COALESCE(i.transaction_status,'active') = 'active'
                 AND i.parent_item_id IS NULL
               ORDER BY i.order_date, i.id""")]
        groups: dict = {}
        for r in rows:
            price = db._parse_dollar(r.get("item_price"))
            if price <= 0:
                continue
            would = db._calc_membership_allocation(r, conn)
            flags = []
            for f, tag in (("net_points_race", "NET"), ("gross_points_race", "GROSS"),
                           ("city_match_play", "MATCH"), ("fall_net_points_race", "FALL")):
                v = (r.get(f) or "").strip().upper()
                if v and v not in ("NO", "NONE", "N/A"):
                    flags.append(tag)
            ron = (r.get("returning_or_new") or "").strip().upper()
            kind = ("Plus" if "PLUS" in ron or "PLUS" in (r.get("item_name") or "").upper()
                    else "New" if ("NEW" in ron or "1ST" in ron or "FIRST" in ron)
                    else "Returning" if ron else "(blank)")
            w_tgf = float(would.get("tgf_operating") or 0)
            w_pool = float(would.get("prize_pool") or 0)
            w_shirt = float(would.get("lsc_shirt_fund") or 0)
            fits = abs((w_tgf + w_shirt + w_pool) - price) < 0.01
            key = (round(price, 2), kind, "+".join(flags) or "none")
            g = groups.setdefault(key, {
                "price": key[0], "type": kind, "contests": key[2],
                "rows": 0, "unallocated": 0, "fits_table": fits,
                "booked_margin": 0.0, "would_margin": 0.0,
                "booked_pool": 0.0, "would_pool": 0.0,
                "booked_shirt": 0.0, "would_shirt": 0.0,
                "booked_tax": 0.0, "would_tax": 0.0,
                "first": r.get("order_date"), "last": r.get("order_date"),
                "fund_years": defaultdict(int), "samples": []})
            g["rows"] += 1
            if r.get("booked_tgf") is None:
                g["unallocated"] += 1
            g["booked_margin"] = round(g["booked_margin"] + float(r.get("booked_tgf") or 0), 2)
            g["would_margin"] = round(g["would_margin"] + w_tgf, 2)
            g["booked_pool"] = round(g["booked_pool"] + float(r.get("booked_pool") or 0), 2)
            g["would_pool"] = round(g["would_pool"] + w_pool, 2)
            g["booked_shirt"] = round(g["booked_shirt"] + float(r.get("booked_shirt") or 0), 2)
            g["would_shirt"] = round(g["would_shirt"] + w_shirt, 2)
            g["booked_tax"] = round(g["booked_tax"] + float(r.get("booked_tax") or 0), 2)
            g["would_tax"] = round(g["would_tax"] + w_tgf * 0.0825, 2)
            g["last"] = r.get("order_date")
            fy = lsc_fund_year(r.get("order_date"))
            if fy:
                g["fund_years"][str(fy)] += 1
            if len(g["samples"]) < 2:
                g["samples"].append(f"{r.get('order_id')} {r.get('customer')}")
    out_groups = []
    for g in groups.values():
        g["fund_years"] = dict(g["fund_years"])
        g["delta_margin"] = round(g["would_margin"] - g["booked_margin"], 2)
        g["delta_tax"] = round(g["would_tax"] - g["booked_tax"], 2)
        out_groups.append(g)
    out_groups.sort(key=lambda g: (-g["rows"], g["price"]))
    result = {
        "cutover": cutover, "history_from": first_date,
        "shirt_setaside_per_membership": lsc,
        "table": ("base New 44 / Returning 69 / Plus 244 taxable + $6 Monthly Points "
                  "pool + $10 markup per contest (Plus waived) + contest pools "
                  "(NET 80, Gross 40, Match Play 40, FALL Net 40) + $10 shirt "
                  "set-aside out of TGF's side"),
        "rows": sum(g["rows"] for g in out_groups),
        "groups": len(out_groups),
        "fits": sum(1 for g in out_groups if g["fits_table"]),
        "misfits": [g for g in out_groups if not g["fits_table"]],
        "booked_margin": round(sum(g["booked_margin"] for g in out_groups), 2),
        "would_margin": round(sum(g["would_margin"] for g in out_groups), 2),
        "booked_pool": round(sum(g["booked_pool"] for g in out_groups), 2),
        "would_pool": round(sum(g["would_pool"] for g in out_groups), 2),
        "booked_shirt": round(sum(g["booked_shirt"] for g in out_groups), 2),
        "would_shirt": round(sum(g["would_shirt"] for g in out_groups), 2),
        "booked_tax": round(sum(g["booked_tax"] for g in out_groups), 2),
        "would_tax": round(sum(g["would_tax"] for g in out_groups), 2),
        "by_group": out_groups,
    }
    result["delta_margin"] = round(result["would_margin"] - result["booked_margin"], 2)
    result["delta_tax"] = round(result["would_tax"] - result["booked_tax"], 2)
    if apply:
        result["applied"] = rebook_spread_since(
            first_date, dry_run=False, db_path=db_path, item_class="membership")
        result["applied"].pop("changes", None)
    return result


def liability_buckets(db_path: str | Path | None = None,
                      today: str | None = None) -> dict:
    """What TGF is holding for someone else or has earmarked. Read-only.

      prize_payouts_owed  — tgf_payouts rows not yet paid (owed to winners)
      credits_held        — customer credit balances (refunds console
                            'outstanding')
      lsc_shirt_fund      — $10 per membership SOLD, by Cup year
                            (Aug–Jul), from the membership items
                            themselves so pre-cutover memberships count
                            (Kerry: 'All memberships fund shirts')
      sales_tax_reserve   — tax_reserve by month, split filed / open by
                            the 20th-of-next-month rule
    """
    from . import database as db
    from .timezone_utils import today_central_str
    today = (today or today_central_str())[:10]
    out: dict = {"as_of": today}
    with db._connect(db_path) as conn:
        # Prize payouts owed
        try:
            r = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS amt "
                "FROM tgf_payouts WHERE paid_at IS NULL").fetchone()
            out["prize_payouts_owed"] = {"rows": r["n"], "amount": round(r["amt"], 2)}
        except Exception:
            logger.warning("payouts owed read failed", exc_info=True)
            out["prize_payouts_owed"] = {"error": "unavailable"}
        # Credits held (refunds console)
        try:
            ro = db.get_refunds_overview(db_path)
            outstanding = ro.get("outstanding") or []
            amt = 0.0
            for x in outstanding:
                amt += float(x.get("amount") or x.get("credit_amount") or 0)
            out["credits_held"] = {"rows": len(outstanding), "amount": round(amt, 2)}
        except Exception:
            logger.warning("credits held read failed", exc_info=True)
            out["credits_held"] = {"error": "unavailable"}
        # Shirt fund by Cup year, from membership items sold
        per = db._membership_setaside("lsc_shirt", 10.0, conn)
        # The Tracker's order history starts where the email parsing
        # started; memberships sold before that are not in it, so an
        # early fund year is a FLOOR until the older sales are loaded.
        records_from = conn.execute(
            "SELECT MIN(substr(order_date,1,10)) AS d FROM items "
            "WHERE merchant = 'The Golf Fellowship'").fetchone()["d"]
        fund: dict = defaultdict(lambda: {"memberships": 0, "funded": 0.0})
        for r in conn.execute(
                """SELECT order_date FROM items
                   WHERE UPPER(COALESCE(item_name,'')) LIKE '%MEMBERSHIP%'
                     AND COALESCE(transaction_status,'active') = 'active'
                     AND parent_item_id IS NULL
                     AND COALESCE(item_price,'') NOT IN ('', '$0.00', '0', '0.0')"""):
            y = lsc_fund_year(r["order_date"])
            # Memberships before Aug 2025 funded no shirts (Kerry
            # 2026-09-10: that year's shirts came from season-contest and
            # LSC markups, already spent) — not a fund to track.
            if y is None or (r["order_date"] or "")[:10] < db.LSC_SHIRT_SETASIDE_FROM:
                continue
            fund[y]["memberships"] += 1
            fund[y]["funded"] = round(fund[y]["funded"] + per, 2)
        out["lsc_shirt_fund"] = {
            "per_membership": per,
            "rule": "Aug–Jul membership sales fund the Cup played that October "
                    "(Aug 2025–Jul 2026 → 2026 Cup); memberships before Aug 2025 "
                    "funded no shirts (Kerry 2026-09-10)",
            "records_from": records_from,
            "by_cup_year": {str(k): v for k, v in sorted(fund.items())},
            "spend_recorded": "not tracked yet — shirt purchases are not tagged to the fund",
        }
        # Hole-in-One pot (rolling, carried across seasons). Kerry
        # 2026-09-09: "I also need to put the full HIO pot amount in
        # there [the HYSA] right away so I don't have it in my TGF
        # Checking account to spend."
        try:
            hio = db.get_hio_pot(db_path)
            _ev = hio.get("events") or []
            out["hio_pot"] = {"pot": round(float(hio.get("pot") or 0), 2),
                              "carry_in": round(float(hio.get("carry_in") or 0), 2),
                              "contributed": round(float(hio.get("total_contributed") or 0), 2),
                              "paid_out": round(float(hio.get("paid_out") or 0), 2),
                              "events_counted": hio.get("events_counted"),
                              "through": _ev[-1].get("date") if _ev else None}
        except Exception:
            logger.warning("HIO pot read failed", exc_info=True)
            out["hio_pot"] = {"error": "unavailable"}
        # Sales tax reserve by month
        months = {}
        for r in conn.execute(
                """SELECT substr(allocation_date,1,7) AS m,
                          COALESCE(SUM(tax_reserve),0) AS tax,
                          COALESCE(SUM(tgf_operating),0) AS margin,
                          COUNT(*) AS rows
                   FROM acct_allocations
                   WHERE allocation_date IS NOT NULL
                   GROUP BY m ORDER BY m"""):
            m = r["m"]
            if not m or len(m) < 7:
                continue
            y, mo = int(m[:4]), int(m[5:7])
            ny, nm = (y + 1, 1) if mo == 12 else (y, mo + 1)
            due = f"{ny:04d}-{nm:02d}-{TAX_FILING_DAY:02d}"
            # Rows are SIGNED (a loss-leader round is a credit); the
            # MONTH floors at zero — Kerry 2026-09-09.
            months[m] = {"tax_reserve": round(max(r["tax"], 0.0), 2),
                         "tax_reserve_signed_sum": round(r["tax"], 2),
                         "margin": round(r["margin"], 2), "rows": r["rows"],
                         "due": due, "status": "filed" if due < today else "open"}
        out["sales_tax_reserve"] = {
            "rate": ("8.25% of TGF margin per row, signed; a negative row is a "
                     "credit against its month; the month floors at zero"),
            "by_month": months,
            "open_total": round(sum(v["tax_reserve"] for v in months.values()
                                    if v["status"] == "open"), 2),
        }
    return out
