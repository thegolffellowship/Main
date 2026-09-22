"""The Dashboard feed — what needs Kerry today, as counts and links.

Kerry, 2026-09-21: *"maybe I should be landing on a DASHBOARD page that
summarizes anything current that I can go to with a click"* and then
*"Dashboard replaces COO as landing, absorb the action items — I don't
use the current what needs me today stuff at all right now, so let's
ditch those for the new comprehensive dashboard."*

TWO RULES, ratified in the same breath as the page:

1. **It is a ROUTER, never a workspace.** Every card is a count and a
   link to the surface that owns the work. Nothing is worked here. The
   moment a card can be acted on it starts competing with the page it
   points at, and the two drift.
2. **A card with nothing in it does not render.** A page that always
   shows every card becomes wallpaper by the second week; one that shows
   three things today and six tomorrow keeps being read. `build()`
   returns only the cards with something in them — the caller renders
   what it is given and nothing else.

Why the COO surface is being retired rather than the `action_items`
TABLE: nine code paths write that table (discrepancy sweeps, parse
warnings, the GG history ingest), so it is the mechanism by which the
system reports the problems it found. Kerry does not read the page. The
fix is to surface the COUNT where he will see it and link to the page
that works them — not to stop detecting.

Every feed is independently wrapped: a broken query costs its own card,
never the page. A dashboard that 500s is worse than one missing a row.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# How far out "this week" looks, and how far back an event stays
# "awaiting closeout" before it stops being this week's problem.
WEEK_AHEAD_DAYS = 7
CLOSEOUT_LOOKBACK_DAYS = 21
# A first timer stays on the attribution card this long. Past that,
# nobody remembers who brought them and asking is noise.
ATTRIBUTION_WINDOW_DAYS = 60
# Email triage looks back this far. The table holds ~3,100 open rows
# going back to the feature's first day; an unscoped count is an archive,
# not a to-do list, and an archive on a landing page trains you to look
# past it.
TRIAGE_WINDOW_DAYS = 14

_TONES = {"do", "watch", "info"}


def _card(key, title, count, href, detail="", tone="do", items=None):
    return {"key": key, "title": title, "count": count, "href": href,
            "detail": detail, "tone": tone if tone in _TONES else "info",
            "items": items or []}


def _days(a: str, b: str) -> int | None:
    from datetime import date
    try:
        y1, m1, d1 = (int(x) for x in str(a)[:10].split("-"))
        y2, m2, d2 = (int(x) for x in str(b)[:10].split("-"))
        return (date(y1, m1, d1) - date(y2, m2, d2)).days
    except Exception:
        return None


def _when(days: int | None) -> str:
    if days is None:
        return ""
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days < 0:
        return f"{abs(days)}d ago"
    return f"in {days}d"


# ── feeds ───────────────────────────────────────────────────────────
# Each takes (conn, today) and returns a card or None. None means
# "nothing to show", which is how a card stays off the page.

def _events_this_week(conn, today):
    from datetime import date, timedelta
    end = (date.fromisoformat(today) + timedelta(days=WEEK_AHEAD_DAYS)).isoformat()
    rows = conn.execute(
        "SELECT e.id, e.item_name, e.event_date, e.chapter, "
        "  (SELECT COUNT(*) FROM items i WHERE i.event_id = e.id "
        "     AND COALESCE(i.transaction_status,'active') = 'active') AS regs "
        "FROM events e "
        "WHERE e.event_date >= ? AND e.event_date <= ? "
        "  AND COALESCE(e.event_type,'event') = 'event' "
        "ORDER BY e.event_date, e.item_name", (today, end)).fetchall()
    if not rows:
        return None
    items = [{"label": r["item_name"],
              "meta": f"{_when(_days(r['event_date'], today))} · "
                      f"{r['regs']} in" + (f" · {r['chapter']}" if r["chapter"] else ""),
              "href": f"/events?event={r['id']}"} for r in rows]
    return _card("events_week", "Events this week", len(rows), "/events",
                 "tee sheets to work", "do", items)


def _events_awaiting_closeout(conn, today):
    """Played, and the money is not finished: payouts recorded but not
    all paid, or a field with scorecards and no payouts at all."""
    from datetime import date, timedelta
    start = (date.fromisoformat(today)
             - timedelta(days=CLOSEOUT_LOOKBACK_DAYS)).isoformat()
    rows = conn.execute(
        "SELECT e.id, e.item_name, e.event_date, "
        "  (SELECT COUNT(*) FROM tgf_payouts p JOIN tgf_events te ON te.id = p.event_id "
        "     WHERE te.events_id = e.id AND p.paid_at IS NULL) AS unpaid "
        "FROM events e "
        "WHERE e.event_date >= ? AND e.event_date < ? "
        "  AND COALESCE(e.event_type,'event') = 'event' "
        "ORDER BY e.event_date DESC", (start, today)).fetchall()
    open_rows = [r for r in rows if (r["unpaid"] or 0) > 0]
    if not open_rows:
        return None
    items = [{"label": r["item_name"],
              "meta": f"{r['unpaid']} payout{'' if r['unpaid'] == 1 else 's'} unpaid "
                      f"· {_when(_days(r['event_date'], today))}",
              "href": f"/events?event={r['id']}"} for r in open_rows]
    return _card("closeout", "Events to close out", len(open_rows), "/tgf",
                 "played, money not settled", "do", items)


def _new_leads(conn, today):
    n = conn.execute(
        "SELECT COUNT(*) c FROM leads WHERE status = 'new' "
        "AND merged_into IS NULL").fetchone()["c"]
    if not n:
        return None
    return _card("leads_new", "New leads", n, "/admin/leads?f=new",
                 "nobody has touched them", "do")


def _followups_due(conn, today):
    n = conn.execute(
        "SELECT COUNT(*) c FROM leads WHERE merged_into IS NULL "
        "AND status NOT IN ('dismissed','converted') "
        "AND follow_up_at IS NOT NULL AND follow_up_at <= ?",
        (today,)).fetchone()["c"]
    if not n:
        return None
    return _card("leads_due", "Follow-ups due", n, "/admin/leads?f=due",
                 "the 48-hour gate", "do")


def _first_timers_to_attribute(conn, today):
    """WHO BROUGHT THEM — the Ty Bubela card (Kerry 2026-09-21).

    A recent first-timer registration whose customer has nobody recorded
    as having brought them. The CONFIRMATION lives on the Leads page
    band; this only says how many are waiting. Deliberately quiet about
    the mechanism because the referral schema is not ratified yet
    (docs/claude/referral-attribution.md) — the count is true either way.
    """
    from datetime import date, timedelta
    start = (date.fromisoformat(today)
             - timedelta(days=ATTRIBUTION_WINDOW_DAYS)).isoformat()
    # Someone whose lead row carries a campaign id is already answered:
    # the ad brought them, and asking Kerry "who brought them?" about a
    # person Facebook is invoicing him for is the card asking a question
    # the Tracker can answer itself (Kerry 2026-09-21: "if they're
    # already tied to a lead campaign, then they shouldn't be on the
    # first timers list to attribute"). A leads table is not guaranteed
    # (a bare transactions DB has none), so the clause is conditional
    # rather than letting the whole card fall over rule 2.
    has_leads = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='leads'"
    ).fetchone()
    # ONE predicate, written once and used both ways below: true when a
    # campaign already accounts for this person.
    #
    # A lead row is not the only proof. Kerry, seeing Hector Hinojosa on
    # this card: "Isn't Hector Hinojosa a campaign lead?" He is — his
    # customers.acquisition_source reads 'facebook_lead' — and that stamp
    # is only ever written to a customer who was linked to a lead
    # (leads.py, both write sites), so it holds even when the lead row's
    # campaign_id does not. Anything else, 'godaddy' included, is a store
    # channel and says nothing about who brought them.
    parts = ["COALESCE(c.acquisition_source,'') = 'facebook_lead'"]
    if has_leads:
        parts.append("EXISTS (SELECT 1 FROM leads l "
                     "WHERE l.customer_id = c.customer_id "
                     "AND l.campaign_id IS NOT NULL)")
    CAMPAIGN_KNOWN = "(" + " OR ".join(parts) + ")"

    BASE = (
        "SELECT DISTINCT c.customer_id, "
        "  TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')) AS name, "
        "  MIN(i.order_date) AS first_order "
        "FROM items i JOIN customers c ON c.customer_id = i.customer_id "
        "WHERE UPPER(COALESCE(i.user_status,'')) LIKE '%1ST TIMER%' "
        "  AND COALESCE(i.transaction_status,'active') = 'active' "
        "  AND i.order_date >= ? "
        "  AND c.referred_by_customer_id IS NULL "
        "  AND {campaign} "
        "GROUP BY c.customer_id ORDER BY first_order DESC")

    # The blank question: nobody has said, and no campaign accounts for
    # them either (Kerry: "if they're already tied to a lead campaign,
    # then they shouldn't be on the first timers list to attribute").
    rows = conn.execute(BASE.format(campaign="NOT " + CAMPAIGN_KNOWN),
                        (start,)).fetchall()
    # ...but a campaign lead can STILL have a referrer worth paying.
    # Kerry 2026-09-22, on Justin Angelone: "The campaign connection is
    # still real, because he filled out the form and that's how I
    # responded to him, but we also need to honor the referral and pay
    # out to Isaac." So campaign-tied people are excluded from the BLANK
    # question only. Where their own order names somebody, they come back
    # as a CONFIRMATION — which is what Kerry asked for: "He should only
    # show up on a 1st Timer attribution list to confirm it was Jeff,
    # with an option to switch in worst case."
    suggested = conn.execute(BASE.format(campaign=CAMPAIGN_KNOWN),
                             (start,)).fetchall()

    from .attribution import suggest_referrer
    seen = {r["customer_id"] for r in rows}
    merged = list(rows) + [r for r in suggested if r["customer_id"] not in seen]

    items = []
    for r in merged:
        try:
            hint = suggest_referrer(r["customer_id"], conn)
        except Exception:
            hint = None
        if r["customer_id"] not in seen and not hint:
            continue        # campaign-tied AND nothing to confirm: stay out
        row = {"label": r["name"] or f"customer {r['customer_id']}",
               "meta": (f"{hint['referrer_name']}?" if hint
                        else f"first played {_when(_days(r['first_order'], today))}"),
               "href": f"/customers?cid={r['customer_id']}",
               "attribute_cid": r["customer_id"]}
        if hint:
            row["suggest"] = hint
        items.append(row)
    if not items:
        return None
    n_confirm = sum(1 for i in items if i.get("suggest"))
    return _card("attribute", "First timers to attribute", len(items),
                 "/admin/leads",
                 (f"{n_confirm} just need confirming" if n_confirm
                  else "who referred them?"), "watch", items)


def _renewals(conn, today):
    from datetime import date, timedelta
    soon = (date.fromisoformat(today) + timedelta(days=30)).isoformat()
    row = conn.execute(
        "SELECT SUM(CASE WHEN expires_at < ? THEN 1 ELSE 0 END) AS lapsed, "
        "       SUM(CASE WHEN expires_at >= ? AND expires_at <= ? THEN 1 ELSE 0 END) AS soon "
        "FROM (SELECT customer_id, MAX(expires_at) AS expires_at "
        "        FROM customer_memberships GROUP BY customer_id)",
        (today, today, soon)).fetchone()
    lapsed, due = (row["lapsed"] or 0), (row["soon"] or 0)
    if not due and not lapsed:
        return None
    detail = " · ".join(filter(None, [
        f"{due} expiring in 30d" if due else "",
        f"{lapsed} already lapsed" if lapsed else ""]))
    return _card("renewals", "Memberships", due + lapsed, "/customers",
                 detail, "watch")


def _expense_queue(conn, today):
    n = conn.execute("SELECT COUNT(*) c FROM expense_transactions "
                     "WHERE review_status = 'pending'").fetchone()["c"]
    if not n:
        return None
    return _card("expenses", "Expenses to review", n, "/accounting",
                 "nothing books until they are", "watch")


def _action_items(conn, today):
    """ABSORBED from the COO page (Kerry: 'absorb the action items').

    This is the AI email triage — mail that wants a reply: a course
    asking about a reservation, a member inquiry, a partner pitch. The
    table stays (nine code paths write it); only the front door moves.

    SCOPED, and the scope is the whole point. There are ~3,100 rows open,
    a backlog going back to the feature's first day, and a card reading
    3,151 teaches Kerry to ignore the page — which is exactly why he
    stopped opening the COO dashboard. HIGH urgency inside the window is
    the cut that makes it a today list instead of an archive.
    """
    from datetime import date, timedelta
    start = (date.fromisoformat(today) - timedelta(days=TRIAGE_WINDOW_DAYS)).isoformat()
    rows = conn.execute(
        "SELECT id, subject, from_name, email_date FROM action_items "
        "WHERE status = 'open' AND urgency = 'high' AND email_date >= ? "
        "ORDER BY email_date DESC, id DESC", (start,)).fetchall()
    if not rows:
        return None
    items = [{"label": (r["subject"] or "(no subject)")[:70],
              "meta": " · ".join(filter(None, [
                  (r["from_name"] or "").strip(),
                  _when(_days(r["email_date"], today))])),
              "href": "/coo"} for r in rows]
    return _card("action_items", "Email needing a reply", len(rows), "/coo",
                 f"high priority, last {TRIAGE_WINDOW_DAYS} days", "do", items)


def _ca_queue(conn, today):
    n = conn.execute("SELECT COUNT(*) c FROM ca_queue "
                     "WHERE status = 'open'").fetchone()["c"]
    if not n:
        return None
    return _card("ca_queue", "Open decisions", n, "/admin/ca-queue",
                 "waiting on you", "info")


FEEDS = (
    _events_this_week,
    _events_awaiting_closeout,
    _followups_due,
    _new_leads,
    _first_timers_to_attribute,
    _renewals,
    _expense_queue,
    _action_items,
    _ca_queue,
)


def build(db_path: str | Path | None = None, today: str | None = None) -> dict:
    """{cards: [...], skipped: [...], as_of: 'YYYY-MM-DD'}.

    Only cards with something in them are returned (rule 2). A feed that
    raises is named in `skipped` and costs nothing else — the page still
    renders.
    """
    from . import database as db
    from .timezone_utils import today_central_str
    today = today or today_central_str()
    cards, skipped = [], []
    with db._connect(db_path) as conn:
        for feed in FEEDS:
            name = feed.__name__.lstrip("_")
            try:
                c = feed(conn, today)
            except Exception as e:
                logger.warning("dashboard feed %s failed", name, exc_info=True)
                skipped.append({"feed": name, "error": str(e)[:200]})
                continue
            if c and c.get("count"):
                cards.append(c)
    return {"as_of": today, "cards": cards, "skipped": skipped,
            "total": sum(c["count"] for c in cards)}
