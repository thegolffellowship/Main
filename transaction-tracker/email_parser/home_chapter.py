"""HOME CHAPTER — the audit Kerry asked for, and the ruling-gated setter.

CA #784 (Kerry, rule 3b): points standings ALWAYS follow the player's HOME
chapter = `customers.chapter`. "Most events" and "most recent" derivations
are REJECTED as a way of SETTING it. The lane lists the flagged players
(Barna, Moore, Sharp, Franz, Williams, plus any other home chapter that looks
wrong) with their current home chapter "so Kerry can confirm or correct the
DATA". Never overwrite customers.chapter from items.chapter.

So there are two halves and they are deliberately different:

  audit_home_chapters()   READ-ONLY. Uses where a player actually plays only
                          as EVIDENCE for a human to look at. It never
                          decides anything.
  set_home_chapter()      WRITES, but only for a customer + chapter pair a
                          named ruling covers (a mailbox id), only to a
                          chapter that exists in `chapters`, and logs the
                          before/after. The existing chapter-guess confirm
                          path refuses non-blank profiles on purpose; this is
                          the narrow door for a ruled correction.

Portable-SQL rule (CA #682): lower() on both sides, no NOCASE, no LIKE on
case, no INSERT OR REPLACE.
"""
from __future__ import annotations

NAMED = ("barna", "moore", "sharp", "franz", "williams")
NEUTRAL_EVENT_CHAPTERS = ("TGF", "(none)")


def audit_home_chapters(year: str = "2026", db_path=None) -> dict:
    from .database import get_connection
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT c.customer_id, c.first_name, c.last_name,
                      c.chapter AS home, e.chapter AS event_chapter,
                      COUNT(DISTINCT sr.event_id) AS n
                 FROM customers c
                 JOIN scoring_rounds sr ON sr.customer_id = c.customer_id
                 JOIN events e ON e.id = sr.event_id
                WHERE substr(sr.round_date, 1, 4) = ?
                GROUP BY c.customer_id, e.chapter""", (year,)).fetchall()
    finally:
        conn.close()

    people: dict = {}
    for r in rows:
        p = people.setdefault(r["customer_id"], {
            "customer_id": r["customer_id"],
            "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "home_chapter": r["home"], "events_by_chapter": {}})
        p["events_by_chapter"][r["event_chapter"] or "(none)"] = r["n"]

    flagged = []
    for p in people.values():
        # TGF-wide events (championships, the cup) belong to no chapter, so
        # they are shown but never count as "playing away from home" — the
        # first live run flagged players whose only 2026 event was a TGF one.
        by = {k: v for k, v in p["events_by_chapter"].items()
              if k not in NEUTRAL_EVENT_CHAPTERS}
        total = sum(p["events_by_chapter"].values())
        home = (p["home_chapter"] or "").strip()
        most = max(by, key=by.get) if by else None
        reasons = []
        if not home:
            reasons.append("blank home chapter")
        elif by and by.get(home, 0) == 0:
            reasons.append(f"has played {total} event(s) in {year}, none in "
                           f"his home chapter")
        elif most and most != home and by[most] > by.get(home, 0):
            reasons.append(f"plays more in {most} ({by[most]}) than at home "
                           f"({by.get(home, 0)})")
        last = p["name"].split()[-1].lower() if p["name"] else ""
        if last in NAMED:
            reasons.append("named in CA #784")
        if reasons:
            flagged.append(dict(p, reasons=reasons, events_total=total))
    flagged.sort(key=lambda p: ("named in CA #784" not in p["reasons"],
                                p["name"]))
    return {
        "year": year, "players_with_rounds": len(people),
        "flagged": flagged,
        "note": ("EVIDENCE ONLY. Where a player plays is shown so Kerry can "
                 "confirm or correct the DATA; it is never used to set a home "
                 "chapter (CA #784 rejects 'most events' and 'most recent')."),
    }


def _first_played(conn, customer_id: int, fallback: str | None) -> str:
    r = conn.execute(
        """SELECT MIN(substr(e.event_date, 1, 10)) FROM scoring_rounds sr
             JOIN events e ON e.id = sr.event_id WHERE sr.customer_id = ?""",
        (customer_id,)).fetchone()
    return (r[0] if r and r[0] else None) or (str(fallback or "")[:10] or "2007-01-01")


def backfill_home_chapters(apply: bool = False, db_path=None) -> dict:
    """The reported backfill of the approved migration (#1084): for every
    customer with no home_chapter_id, copy the id from customers.chapter
    (resolved against `chapters` by name or short code, lower() both sides)
    and open ONE history row (from_date = first event played, else
    created_at; set_by 'backfill'). Never derived from play. Blanks stay
    NULL and are listed for Kerry/Robert to set. Vendor profiles are
    skipped. Dry run unless apply."""
    from .database import get_connection, vendor_customer_ids
    conn = get_connection(db_path)
    try:
        cmap = {}
        for r in conn.execute("SELECT chapter_id, name, short_code FROM chapters"):
            cmap[(r["name"] or "").strip().lower()] = (r["chapter_id"], r["name"])
            if r["short_code"]:
                cmap.setdefault(r["short_code"].strip().lower(), (r["chapter_id"], r["name"]))
        vendors = vendor_customer_ids(conn)
        rows = [dict(r) for r in conn.execute(
            """SELECT customer_id, first_name, last_name, chapter, current_player_status,
                      created_at, home_chapter_id
                 FROM customers WHERE COALESCE(account_status, 'active') = 'active'
                ORDER BY customer_id""")]
        will, blank, unresolved, by_chapter = [], [], [], {}
        for r in rows:
            if r["customer_id"] in vendors or r["home_chapter_id"] is not None:
                continue
            raw = (r["chapter"] or "").strip()
            name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
            if not raw:
                blank.append({"customer_id": r["customer_id"], "name": name,
                              "status": r["current_player_status"]})
                continue
            hit = cmap.get(raw.lower())
            if not hit:
                unresolved.append({"customer_id": r["customer_id"], "name": name, "chapter": raw})
                continue
            will.append((r["customer_id"], hit[0], _first_played(conn, r["customer_id"], r["created_at"])))
            by_chapter[hit[1]] = by_chapter.get(hit[1], 0) + 1
        if apply:
            for cid, chid, frm in will:
                conn.execute("UPDATE customers SET home_chapter_id = ? WHERE customer_id = ? "
                             "AND home_chapter_id IS NULL", (chid, cid))
                conn.execute(
                    """INSERT INTO customer_chapter_history
                           (customer_id, chapter_id, from_date, set_by, reason)
                       VALUES (?, ?, ?, 'backfill', 'from customers.chapter (CA #784; migration #1084)')""",
                    (cid, chid, frm))
            conn.commit()
        drift = conn.execute(
            """SELECT COUNT(*) FROM customers c JOIN chapters ch ON ch.chapter_id = c.home_chapter_id
                WHERE lower(COALESCE(c.chapter, '')) <> lower(ch.name)""").fetchone()[0]
    finally:
        conn.close()
    blank.sort(key=lambda b: ((b["status"] or "") != "active_member", b["name"].lower()))
    return {"dry_run": not apply, "would_set" if not apply else "set": len(will),
            "by_chapter": by_chapter, "blank": len(blank), "blank_list": blank,
            "unresolved": unresolved, "vendors_skipped": len(vendors),
            "text_vs_id_drift": drift}


def home_chapter_id_of(conn, customer_id: int):
    """THE reader for a member's home chapter id (readers move here from
    customers.chapter, one at a time)."""
    r = conn.execute("SELECT home_chapter_id FROM customers WHERE customer_id = ?",
                     (customer_id,)).fetchone()
    return r[0] if r else None


def set_home_chapter(customer_id: int, chapter: str, ruling: str,
                     db_path=None) -> dict:
    """Set ONE customer's home chapter under a NAMED ruling. Refuses without
    a ruling reference, and refuses a chapter not in `chapters`.

    The ONLY writer of a home chapter (#1084). It sets home_chapter_id,
    closes the open history row and opens a new one (a move is never an
    overwrite), and mirrors the name into the read-only customers.chapter
    so its remaining readers stay right until they move."""
    from .database import get_connection, log_agent_action
    from .timezone_utils import today_central_str
    if not (ruling or "").strip():
        return {"error": "a ruling reference (e.g. 'CA #784') is required"}
    conn = get_connection(db_path)
    try:
        ok = conn.execute("SELECT chapter_id, name FROM chapters WHERE lower(name) = lower(?)",
                          (chapter,)).fetchone()
        if not ok:
            return {"error": f"unknown chapter {chapter!r}"}
        cur = conn.execute("SELECT chapter, first_name, last_name FROM customers "
                           "WHERE customer_id = ?", (customer_id,)).fetchone()
        if not cur:
            return {"error": f"customer {customer_id} not found"}
        before = cur["chapter"]
        try:
            before_id = conn.execute("SELECT home_chapter_id FROM customers WHERE customer_id = ?",
                                     (customer_id,)).fetchone()[0]
        except Exception:
            before_id = ok["chapter_id"]  # migration 0004 not applied yet: text only
        if (before or "") == ok["name"] and before_id == ok["chapter_id"]:
            return {"customer_id": customer_id, "unchanged": True,
                    "home_chapter": before}
        today = today_central_str()
        conn.execute("UPDATE customers SET chapter = ? WHERE customer_id = ?",
                     (ok["name"], customer_id))
        try:
            conn.execute("UPDATE customers SET home_chapter_id = ? WHERE customer_id = ?",
                         (ok["chapter_id"], customer_id))
            conn.execute("UPDATE customer_chapter_history SET to_date = ? "
                         "WHERE customer_id = ? AND to_date IS NULL", (today, customer_id))
            conn.execute("""INSERT INTO customer_chapter_history
                                (customer_id, chapter_id, from_date, set_by, reason)
                            VALUES (?, ?, ?, 'mcp-claude', ?)""",
                         (customer_id, ok["chapter_id"], today, ruling))
        except Exception:
            pass  # pre-migration database: the text column is still the record
        conn.commit()
    finally:
        conn.close()
    log_agent_action("mcp-claude", "home-chapter-set",
                     f"customer {customer_id}: {before!r} -> {ok['name']!r} "
                     f"under {ruling}")
    return {"customer_id": customer_id,
            "name": f"{cur['first_name']} {cur['last_name']}",
            "before": before, "after": ok["name"], "chapter_id": ok["chapter_id"],
            "ruling": ruling}
