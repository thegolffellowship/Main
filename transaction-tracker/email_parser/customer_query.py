"""query_customers — a READ-ONLY field-level read of `customers` for the
lanes (Chief of Staff #1048: "Today I can't list the F/NULL gender set
without asking a crew"). Returns customer_id, name, chapter, membership
status, gender and the player's rounds this year, ordered active members
first, then this year's players, then name. Never writes."""
from __future__ import annotations

import re

_GENDER = {"F": "F", "M": "M", "NULL": None, "NONE": None, "UNKNOWN": None}
_STATUSES = ("active_member", "expired_member", "active_guest", "inactive", "first_timer")


def query_customers(gender: str = "", chapter: str = "", status: str = "",
                    played_since: str = "", limit: int = 500, include_vendors: bool = False,
                    db_path=None) -> dict:
    """Vendor profiles (role=vendor) are people-list noise and are left out
    unless include_vendors=True (#1075-3)."""
    from email_parser import database as db
    where, args = ["COALESCE(c.account_status, 'active') = 'active'"], []
    g = (gender or "").strip().upper()
    if g:
        if g not in _GENDER:
            return {"error": "gender must be F, M or NULL"}
        if _GENDER[g] is None:
            where.append("(c.gender IS NULL OR trim(c.gender) = '')")
        else:
            where.append("upper(c.gender) = ?")
            args.append(_GENDER[g])
    if chapter.strip():
        where.append("lower(c.chapter) = lower(?)")
        args.append(chapter.strip())
    st = (status or "").strip().lower()
    if st:
        if st not in _STATUSES:
            return {"error": f"status must be one of {', '.join(_STATUSES)}"}
        where.append("c.current_player_status = ?")
        args.append(st)
    year_from = (played_since or "").strip()[:10] or "2026-01-01"
    limit = max(1, min(int(limit or 500), 2000))
    with db._connect(db_path) as conn:
        rows = conn.execute(
            f"""SELECT c.customer_id, c.first_name, c.last_name, c.chapter,
                       c.current_player_status AS status, c.gender,
                       (SELECT COUNT(*) FROM scoring_rounds sr
                          JOIN events e ON e.id = sr.event_id
                         WHERE sr.customer_id = c.customer_id
                           AND substr(e.event_date, 1, 10) >= ?) AS rounds_since
                  FROM customers c
                 WHERE {' AND '.join(where)}""", [year_from] + args).fetchall()
        vendors = set() if include_vendors else db.vendor_customer_ids(conn)
    rows = [r for r in rows if r["customer_id"] not in vendors]
    out = [{"customer_id": r["customer_id"],
            "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "chapter": r["chapter"], "status": r["status"],
            "gender": r["gender"] or None, "rounds_since": r["rounds_since"]} for r in rows]
    out.sort(key=lambda x: (x["status"] != "active_member", -(x["rounds_since"] or 0),
                            (x["name"] or "").lower()))
    return {"count": len(out), "shown": min(len(out), limit), "rounds_since": year_from,
            "filters": {"gender": g or None, "chapter": chapter or None, "status": st or None,
                        "vendors": "included" if include_vendors else f"excluded ({len(vendors)})"},
            "customers": out[:limit]}


# ---------------------------------------------------------------------------
# set_customer_field — the ONE write the Chief of Staff gets (#1048/#1060):
# gender and the ambassador flag only, refused unless it cites a mailbox post
# that carries Kerry's OK (rule 3b), dry run by default, every change logged
# with its before and after.
# ---------------------------------------------------------------------------
SETTABLE = ("gender", "ambassador")


# Who may carry Kerry's word into a write (rule 3b). Kerry himself, or the
# Chief of Staff / Front Desk relaying him VERBATIM. A lane's own post that
# only mentions Kerry is not his OK (9/30: the first guard accepted #1057,
# a tracker-claude post, in a dry run; this is the fix).
RELAYS = ("platform-claude", "front-desk")
_KERRY_QUOTE = re.compile(r"\bkerry\b[^\n\"\u201c]{0,60}[\"\u201c]\s*\S", re.IGNORECASE)


def _kerry_ok(conn, post_id) -> tuple[bool, str]:
    try:
        r = conn.execute("SELECT id, author, body FROM platform_dialogue WHERE id = ?",
                         (int(post_id),)).fetchone()
    except (TypeError, ValueError):
        return False, "kerry_ok_post must be a mailbox post id"
    if not r:
        return False, f"mailbox post #{post_id} not found"
    author = (r["author"] or "").strip().lower()
    if author == "kerry":
        return True, f"#{r['id']} (kerry)"
    if author in RELAYS and _KERRY_QUOTE.search(r["body"] or ""):
        return True, f"#{r['id']} ({author}, quoting Kerry)"
    return False, (f"mailbox post #{post_id} ({author}) does not carry Kerry's word: it must be "
                   f"Kerry's own post, or {' / '.join(RELAYS)} quoting him verbatim")


def set_customer_field(customer_ids, field: str, value, reason: str, kerry_ok_post,
                       apply: bool = False, set_by: str = "mcp-claude", db_path=None) -> dict:
    from email_parser import database as db
    field = (field or "").strip().lower()
    if field not in SETTABLE:
        return {"refused": f"only {', '.join(SETTABLE)} can be set here"}
    if not (reason or "").strip():
        return {"refused": "a reason is required"}
    ids = customer_ids if isinstance(customer_ids, (list, tuple)) else [customer_ids]
    try:
        ids = sorted({int(i) for i in ids})
    except (TypeError, ValueError):
        return {"refused": "customer_ids must be integers"}
    if not ids:
        return {"refused": "no customer_ids"}
    if field == "gender":
        v = (str(value).strip().upper() if value not in (None, "") else "NULL")
        if v not in ("M", "F", "NULL"):
            return {"refused": "gender must be M, F or NULL"}
        value = None if v == "NULL" else v
    with db._connect(db_path) as conn:
        ok, why = _kerry_ok(conn, kerry_ok_post)
        if not ok:
            return {"refused": f"rule 3b: {why}"}
        if field == "ambassador":
            try:
                conn.execute("SELECT 1 FROM customer_ambassadors LIMIT 1")
            except Exception:
                return {"refused": "customer_ambassadors is not built yet (Side Games, #1060-5)"}
            return {"refused": "ambassador writes go through scoring-ambassador-set "
                               "(email_parser/ambassadors.py: per chapter, keeps rows)"}
        ph = ",".join("?" * len(ids))
        rows = {r["customer_id"]: r["gender"] for r in conn.execute(
            f"SELECT customer_id, gender FROM customers WHERE customer_id IN ({ph})", ids).fetchall()}
        missing = [i for i in ids if i not in rows]
        # A vendor profile is not a person: no gender (#1075-3).
        vendors = db.vendor_customer_ids(conn)
        skipped_vendors = [i for i in ids if i in rows and i in vendors]
        changes = [{"customer_id": i, "before": rows[i], "after": value}
                   for i in ids if i in rows and i not in vendors and (rows[i] or None) != value]
        out = {"field": field, "value": value, "authority": why, "reason": reason,
               "missing": missing, "skipped_vendors": skipped_vendors,
               "unchanged": len(rows) - len(changes) - len(skipped_vendors),
               "changes": len(changes), "sample": changes[:10], "dry_run": not apply}
        if not apply or not changes:
            return out
        for ch in changes:
            conn.execute("UPDATE customers SET gender = ? WHERE customer_id = ?",
                         (value, ch["customer_id"]))
        conn.commit()
    for ch in changes:
        db.log_agent_action(set_by, "set_customer_field",
                            f"customer {ch['customer_id']} gender {ch['before']!r} -> {ch['after']!r}; "
                            f"{reason}; authority {why}")
    out["applied"] = True
    return out
