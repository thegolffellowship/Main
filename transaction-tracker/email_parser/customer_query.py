"""query_customers — a READ-ONLY field-level read of `customers` for the
lanes (Chief of Staff #1048: "Today I can't list the F/NULL gender set
without asking a crew"). Returns customer_id, name, chapter, membership
status, gender and the player's rounds this year, ordered active members
first, then this year's players, then name. Never writes."""
from __future__ import annotations

_GENDER = {"F": "F", "M": "M", "NULL": None, "NONE": None, "UNKNOWN": None}
_STATUSES = ("active_member", "expired_member", "active_guest", "inactive", "first_timer")


def query_customers(gender: str = "", chapter: str = "", status: str = "",
                    played_since: str = "", limit: int = 500, db_path=None) -> dict:
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
    out = [{"customer_id": r["customer_id"],
            "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "chapter": r["chapter"], "status": r["status"],
            "gender": r["gender"] or None, "rounds_since": r["rounds_since"]} for r in rows]
    out.sort(key=lambda x: (x["status"] != "active_member", -(x["rounds_since"] or 0),
                            (x["name"] or "").lower()))
    return {"count": len(out), "shown": min(len(out), limit), "rounds_since": year_from,
            "filters": {"gender": g or None, "chapter": chapter or None, "status": st or None},
            "customers": out[:limit]}
