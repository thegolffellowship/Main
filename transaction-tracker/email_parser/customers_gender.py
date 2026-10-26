"""GENDER FROM TEES (Kerry 2026-10-14, rule 3b, via Front Desk: "Yes, approve
the rule and the column even though this should basically be temporary since
when we go to our own payment platform we'll be able to ask those questions
up front."; spec tracker-claude #1815, CoS #1799-2, migration 0019, db-claude
PASS #1855).

Kerry: "Should automatically know this if they select Forward tees … 95% of
the time or greater it's probably a woman."

Kerry 2026-10-20 widened it: "Gender should be assumed based on tee
selection for an event. 65+, 50-64, <50 are all men's tees." A registration
on a men's band with no rated rounds now sets M the same way.
THE RULE. A person with NO gender on file is set to F, marked
`gender_source = 'inferred_from_tees'`, when the signals say so:
  1. played tees: their scorecards are majority on F-rated tees
     (`scoring_rounds` → `course_tees.gender`);
  2. a registration whose tee band is Forward (`items.tee_choice`, or the
     band on a saved pairings seat).
A man playing Forward plays the M-rated Forward tee on courses rated both
ways, so his rounds say M: when the rounds say M and the band says Forward,
nothing is set (`conflict`) and the manager decides. A gender already on
file is NEVER overwritten, whatever its source.

The ONE writer is `infer(apply=True)`; the WHERE clause re-checks
`gender IS NULL` so a value stated in the meantime always wins. Dry run by
default; bridge `scoring-gender-infer[:apply][|<customer_id>,…]`. The job
`gender_infer_auto` runs only while app setting `gender_infer` reads "on"
(off until Kerry has seen the backfill list).

RETIREMENT (Kerry: temporary): once registration asks gender up front, turn
`gender_infer` off for good, remove this module and the chip, and drop
`gender_source` in its own migration when no row reads 'inferred_from_tees'.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

DIAL = "gender_infer"
SOURCE = "inferred_from_tees"
FORWARD = "forward"
# Kerry 2026-10-20: "65+, 50-64, <50 are all men's tees. Forward tees are for
# women generally."
MEN_BANDS = ("65+", "50-64", "<50")


def enabled(db_path=None) -> bool:
    from email_parser.database import get_app_setting
    return (get_app_setting(DIAL, db_path) or "off").strip().lower() == "on"


def _has_source_column(conn) -> bool:
    return any(r[1] == "gender_source" for r in conn.execute("PRAGMA table_info(customers)"))


def _signals(conn, cid: int) -> dict:
    rated = {"F": 0, "M": 0}
    try:
        for g, n in conn.execute(
                "SELECT ct.gender, COUNT(*) FROM scoring_rounds sr "
                "JOIN course_tees ct ON ct.tee_id = sr.tee_id "
                "WHERE sr.customer_id = ? AND ct.gender IN ('M', 'F') GROUP BY ct.gender",
                (cid,)).fetchall():
            rated[g] = int(n)
    except Exception:
        pass
    bands = set()
    for sql in ("SELECT DISTINCT lower(trim(tee_choice)) FROM items "
                "WHERE customer_id = ? AND tee_choice IS NOT NULL",
                "SELECT DISTINCT lower(trim(tee_choice)) FROM event_pairings "
                "WHERE customer_id = ? AND tee_choice IS NOT NULL"):
        try:
            bands |= {r[0] for r in conn.execute(sql, (cid,)).fetchall() if r[0]}
        except Exception:
            pass
    return {"rounds_f": rated["F"], "rounds_m": rated["M"], "forward": FORWARD in bands,
            "men_band": any(b in MEN_BANDS for b in bands)}


def decide(sig: dict) -> tuple[str | None, str]:
    """('F', why) to set, (None, why) to leave alone. Pure."""
    f, m, fwd = sig["rounds_f"], sig["rounds_m"], sig["forward"]
    men = sig.get("men_band", False)
    if f or m:
        if f > m:
            return "F", f"{f} of {f + m} rounds on F-rated tees"
        if fwd:
            return None, (f"conflict: Forward band but {m} of {f + m} rounds on "
                          "M-rated tees (a manager decides)")
        return None, "rounds say M (the boot step fills that one)"
    if fwd and men:
        return None, "conflict: registered on both Forward and a men's band (a manager decides)"
    if fwd:
        return "F", "registered on the Forward band; no rated rounds yet"
    if men:
        return "M", "registered on a men's band (65+ / 50-64 / <50); no rated rounds yet"
    return None, "no signal"


def infer(apply: bool = False, customer_ids=None, db_path=None) -> dict:
    """Every customer with NO gender who has a signal: what the rule would
    set. Writes only with apply=True, only where gender is still NULL."""
    from email_parser import database as db
    out = {"dry_run": not apply, "would_set": [], "conflicts": [], "set": 0}
    with db._connect(db_path) as conn:
        if not _has_source_column(conn):
            return {**out, "error": "migration 0019 (customers.gender_source) not applied"}
        q = ("SELECT customer_id, first_name, last_name FROM customers "
             "WHERE (gender IS NULL OR trim(gender) = '')")
        args: list = []
        if customer_ids:
            ids = [int(c) for c in customer_ids]
            q += f" AND customer_id IN ({','.join('?' * len(ids))})"
            args = ids
        try:
            vendors = set(db.vendor_customer_ids(conn))
        except Exception:
            vendors = set()
        for r in conn.execute(q, args).fetchall():
            cid = int(r["customer_id"])
            if cid in vendors:
                continue
            sig = _signals(conn, cid)
            g, why = decide(sig)
            row = {"customer_id": cid,
                   "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
                   "why": why, **sig}
            if g:
                row["gender"] = g
                out["would_set"].append(row)
            elif why.startswith("conflict"):
                out["conflicts"].append(row)
        if apply:
            for row in out["would_set"]:
                cur = conn.execute(
                    "UPDATE customers SET gender = ?, gender_source = ? "
                    "WHERE customer_id = ? AND (gender IS NULL OR trim(gender) = '')",
                    (row["gender"], SOURCE, row["customer_id"]))
                out["set"] += cur.rowcount or 0
            conn.commit()
    if apply and out["set"]:
        try:
            db.log_agent_action("gender-infer", "gender_inferred",
                                f"{out['set']} set from tees: "
                                + ", ".join(str(r["customer_id"]) for r in out["would_set"]),
                                outcome="ok", db_path=db_path)
        except Exception:
            logger.debug("gender-infer action log failed", exc_info=True)
    return out


def run_job(db_path=None) -> dict:
    """Scheduler entry: does nothing unless the dial is on."""
    if not enabled(db_path):
        return {"skipped": "gender_infer dial is off"}
    return infer(apply=True, db_path=db_path)
