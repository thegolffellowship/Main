"""The Ambassador flag (Pairings Spec v1.2 #1036-4, approved CoS #1046,
shape Tracker Build #1055).

Kerry: "I will currently determine the Ambassador role. Definitely not
something to be derived right now." So the flag is SET, never computed
(and only on an active member with an established TGF handicap, #1080-1): by
Kerry, or by Robert for Austin on Kerry's say-so. Every write cites a
mailbox post carrying Kerry's word (the same rule-3b guard as
`set_customer_field`), is a dry run unless applied, and is action-logged
with its before and after.

Table `customer_ambassadors` (migrations/0002): one row per customer per
chapter. Removing an ambassador sets ambassador = 0 with who/when/why; a
row is never deleted, so "was an ambassador on 10/6" stays answerable.

The pairings engine reads ONLY `chapter_ambassadors(conn, chapter_id)`
(#1055-2); test_ambassadors.py fails if any other module names the table.
"""
from __future__ import annotations


def chapter_ambassadors(conn, chapter_id) -> set[int]:
    """customer_ids flagged ambassador = 1 in this chapter. The one reader
    the pairings rules (R-A, R-F) use. An empty set when the table does not
    exist yet (a fresh or test database)."""
    try:
        rows = conn.execute(
            "SELECT customer_id FROM customer_ambassadors "
            "WHERE chapter_id = ? AND ambassador = 1", (int(chapter_id),)).fetchall()
    except Exception:  # noqa: BLE001 — no table yet
        return set()
    return {int(r[0]) for r in rows}


def _resolve_chapter(conn, chapter) -> tuple[int | None, str | None]:
    """chapter_id from an id, a name ("San Antonio") or a short code ("SA")."""
    s = str(chapter or "").strip()
    if not s:
        return None, None
    if s.isdigit():
        r = conn.execute("SELECT chapter_id, name FROM chapters WHERE chapter_id = ?",
                         (int(s),)).fetchone()
    else:
        r = conn.execute(
            "SELECT chapter_id, name FROM chapters "
            "WHERE lower(name) = lower(?) OR lower(COALESCE(short_code, '')) = lower(?)",
            (s, s)).fetchone()
    return (int(r[0]), r[1]) if r else (None, None)


def list_ambassadors(chapter=None, include_removed: bool = False, db_path=None) -> dict:
    """Read: every flag row (current ambassadors, or all with history)."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        where, args = [], []
        if chapter not in (None, ""):
            cid, _ = _resolve_chapter(conn, chapter)
            if cid is None:
                return {"error": f"unknown chapter {chapter!r}"}
            where.append("a.chapter_id = ?")
            args.append(cid)
        if not include_removed:
            where.append("a.ambassador = 1")
        try:
            rows = conn.execute(
                f"""SELECT a.customer_id, a.chapter_id, ch.name AS chapter,
                           c.first_name, c.last_name, c.gender, a.ambassador,
                           a.set_by, a.set_at, a.note
                      FROM customer_ambassadors a
                      JOIN customers c ON c.customer_id = a.customer_id
                      LEFT JOIN chapters ch ON ch.chapter_id = a.chapter_id
                     {('WHERE ' + ' AND '.join(where)) if where else ''}
                     ORDER BY ch.name, lower(c.last_name), lower(c.first_name)""",
                args).fetchall()
        except Exception as e:  # noqa: BLE001
            return {"error": f"customer_ambassadors not available: {e}"}
    out = [{"customer_id": r["customer_id"], "chapter_id": r["chapter_id"],
            "chapter": r["chapter"],
            "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "gender": r["gender"] or None, "ambassador": bool(r["ambassador"]),
            "set_by": r["set_by"], "set_at": r["set_at"], "note": r["note"]} for r in rows]
    return {"count": len(out), "ambassadors": out}


def set_ambassador(customer_id, chapter, on: bool, kerry_ok_post, note: str = "",
                   apply: bool = False, set_by: str = "mcp-claude", db_path=None) -> dict:
    """Flag (on=True) or unflag (on=False) one customer as an Ambassador in
    one chapter. Refused unless `kerry_ok_post` carries Kerry's word. Dry
    run unless apply. Unflagging keeps the row (ambassador = 0)."""
    from email_parser import database as db
    from email_parser.customer_query import _kerry_ok
    try:
        cust = int(customer_id)
    except (TypeError, ValueError):
        return {"refused": "customer_id must be an integer"}
    on = bool(on)
    with db._connect(db_path) as conn:
        ok, why = _kerry_ok(conn, kerry_ok_post)
        if not ok:
            return {"refused": f"rule 3b: {why}"}
        chap_id, chap_name = _resolve_chapter(conn, chapter)
        if chap_id is None:
            return {"refused": f"unknown chapter {chapter!r}"}
        c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                         (cust,)).fetchone()
        if not c:
            return {"refused": f"customer {cust} not found"}
        name = f"{c['first_name'] or ''} {c['last_name'] or ''}".strip()
        # AN AMBASSADOR IS ALWAYS BLIND-ELIGIBLE (Kerry, CoS #1080-1): an
        # active member with an established TGF handicap, so every
        # Ambassador is a valid 1st-Timer host and a valid blind. The same
        # gate as the blind draw (`database.blind_gate`), same words.
        if on:
            why_not = db.customer_blind_gate(conn, cust, db_path=db_path)
            if why_not:
                return {"refused": f"{name} cannot be an Ambassador: {why_not} "
                                   f"(an Ambassador must be an active member with an "
                                   f"established TGF handicap, #1080-1)",
                        "customer_id": cust, "name": name}
        prev = conn.execute(
            "SELECT ambassador FROM customer_ambassadors WHERE customer_id = ? AND chapter_id = ?",
            (cust, chap_id)).fetchone()
        before = None if prev is None else bool(prev[0])
        out = {"customer_id": cust, "name": name, "chapter_id": chap_id, "chapter": chap_name,
               "before": before, "after": on, "authority": why, "note": note or None,
               "dry_run": not apply, "changed": before != on}
        if before == on:
            out["changed"] = False
            return out
        if before is None and not on:
            out["changed"] = False
            out["why"] = "not an ambassador; nothing to remove"
            return out
        if not apply:
            return out
        if prev is None:
            conn.execute(
                "INSERT INTO customer_ambassadors (customer_id, chapter_id, ambassador, set_by, note) "
                "VALUES (?, ?, ?, ?, ?)", (cust, chap_id, 1 if on else 0, set_by, note or None))
        else:
            conn.execute(
                "UPDATE customer_ambassadors SET ambassador = ?, set_by = ?, "
                "set_at = datetime('now'), note = ? WHERE customer_id = ? AND chapter_id = ?",
                (1 if on else 0, set_by, note or None, cust, chap_id))
        conn.commit()
    db.log_agent_action(set_by, "set_ambassador",
                        f"customer {cust} ({name}) {chap_name}: ambassador {before!r} -> {on!r}; "
                        f"{note or 'no note'}; authority {why}", db_path=db_path)
    out["applied"] = True
    return out
