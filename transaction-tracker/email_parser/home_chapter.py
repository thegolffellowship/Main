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


def set_home_chapter(customer_id: int, chapter: str, ruling: str,
                     db_path=None) -> dict:
    """Set ONE customer's home chapter under a NAMED ruling. Refuses without
    a ruling reference, and refuses a chapter not in `chapters`."""
    from .database import get_connection, log_agent_action
    if not (ruling or "").strip():
        return {"error": "a ruling reference (e.g. 'CA #784') is required"}
    conn = get_connection(db_path)
    try:
        ok = conn.execute("SELECT name FROM chapters WHERE lower(name) = lower(?)",
                          (chapter,)).fetchone()
        if not ok:
            return {"error": f"unknown chapter {chapter!r}"}
        cur = conn.execute("SELECT chapter, first_name, last_name FROM customers "
                           "WHERE customer_id = ?", (customer_id,)).fetchone()
        if not cur:
            return {"error": f"customer {customer_id} not found"}
        before = cur["chapter"]
        if (before or "") == ok["name"]:
            return {"customer_id": customer_id, "unchanged": True,
                    "home_chapter": before}
        conn.execute("UPDATE customers SET chapter = ? WHERE customer_id = ?",
                     (ok["name"], customer_id))
        conn.commit()
    finally:
        conn.close()
    log_agent_action("mcp-claude", "home-chapter-set",
                     f"customer {customer_id}: {before!r} -> {ok['name']!r} "
                     f"under {ruling}")
    return {"customer_id": customer_id,
            "name": f"{cur['first_name']} {cur['last_name']}",
            "before": before, "after": ok["name"], "ruling": ruling}
