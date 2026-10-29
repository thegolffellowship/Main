"""HANDICAP LINK IDENTITY (Kerry 2026-10-29, after "Paul Cleary").

A guest, "Cleary, Paul", played Hill Country Matches on 5/16. A link row
named "Paul Cleary" was written on 5/19 pointing at Adam Baker's customer_id,
and the scorecard import then resolved Cleary's card to Baker through that
link. The index readers take "the first linked name with an index", so the
Fall Championship starter sheet showed Baker at Cleary's 9.0 instead of his
own 6.4. The pairing seat was fixed in July (the `!Name` literal); the link
and the scorecard were not. Kerry: "Fix it now and run an audit on all other
handicaps... What do we need to do to make sure it doesn't happen again?"

This module is the one answer to "does this Golf Genius name belong to this
customer?":
  name_matches(conn, player_name, customer_id) -> "match" | "likely" | "mismatch"
  audit(conn)            every link, scorecard and handicap round whose name
                         does not belong to the customer it points at
  unlink(...)            take a wrong link off a customer (link, scorecards,
                         handicap rounds), dry run by default, logged
  link_cid_ok(...)       the guard every automatic link writer calls
  ordered_link_names(...) a customer's linked names, own name first

A MISMATCH is a name whose last name differs from the customer's (canonical
or any name alias) or whose first name is not the customer's, a prefix of it
(Matt / Matthew) or one of their one-word aliases. Family members share a
last name, so "Pat Youngs" never passes for Luke Youngs.
"""
from __future__ import annotations

import json
import re

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
BLOCK_SETTING = "hcp_link_blocked"   # [{"player_name", "customer_id"}] never re-link


def _tokens(name: str) -> list[str]:
    """'CLEARY, Paul' / 'Paul Cleary' / 'Victor III Arias' -> ['paul', 'cleary']."""
    s = " ".join(str(name or "").split())
    if "," in s:
        last, first = [p.strip() for p in s.split(",", 1)]
        s = f"{first} {last}"
    s = s.lower()
    s = re.sub(r"[^a-z\s'-]", " ", s)          # drops digits (GG 'Paul1') and dots
    s = s.replace("'", "")
    words = [w.strip("-") for w in s.split()]
    return [w for w in words if w and w not in _SUFFIXES]


def _first_last(name: str):
    t = _tokens(name)
    if len(t) < 2:
        return None
    return t[0], t[-1]


def _customer_names(conn, customer_id: int) -> tuple[list, set]:
    """([(first, last), ...] full names, {one-word aliases}) for a customer."""
    full, singles = [], set()
    c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                     (int(customer_id),)).fetchone()
    if c:
        fl = _first_last(f"{c[0] or ''} {c[1] or ''}")
        if fl:
            full.append(fl)
    try:
        rows = conn.execute(
            "SELECT alias_value FROM customer_aliases WHERE customer_id = ? AND alias_type = 'name'",
            (int(customer_id),)).fetchall()
    except Exception:
        rows = []
    for r in rows:
        t = _tokens(r[0])
        if len(t) >= 2:
            full.append((t[0], t[-1]))
        elif len(t) == 1:
            singles.add(t[0])
    return full, singles


def _first_ok(a: str, b: str) -> bool:
    """Same first name, or one a 3+ letter prefix of the other (Matt/Matthew)."""
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return len(short) >= 3 and long_.startswith(short)


def name_matches(conn, player_name: str, customer_id: int) -> str:
    fl = _first_last(player_name)
    if not fl or not customer_id:
        return "likely"            # nothing to judge on: a one-word name never blocks
    full, singles = _customer_names(conn, customer_id)
    if not full:
        return "likely"
    first, last = fl
    if (first, last) in full:
        return "match"
    for f, l in full:
        if l == last and (_first_ok(first, f) or first in singles):
            return "likely"
    return "mismatch"


def _canonical(conn, cid):
    c = conn.execute("SELECT TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) "
                     "FROM customers WHERE customer_id = ?", (cid,)).fetchone()
    return (c[0] if c else None) or None


def _blocked(conn) -> list:
    try:
        r = conn.execute("SELECT value FROM app_settings WHERE key = ?", (BLOCK_SETTING,)).fetchone()
        return json.loads(r[0]) if r and r[0] else []
    except Exception:
        return []


def is_blocked(conn, player_name: str, customer_id) -> bool:
    key = _tokens(player_name)
    for b in _blocked(conn):
        if int(b.get("customer_id") or 0) == int(customer_id or 0) and _tokens(b.get("player_name")) == key:
            return True
    return False


def link_cid_ok(conn, player_name: str, customer_id) -> bool:
    """The guard for AUTOMATIC link writers (imports, backfills, relink, the
    handicap post): a customer_id is written onto a link only when the name
    belongs to that customer and was never unlinked from them. A manual,
    Kerry-ordered link (`link_handicap_history`) does not call this."""
    if not customer_id:
        return True
    if is_blocked(conn, player_name, customer_id):
        return False
    return name_matches(conn, player_name, customer_id) != "mismatch"


def ordered_link_names(conn, customer_id: int) -> list[str]:
    """A customer's linked GG names, own name first: exact matches, then
    likely ones, then any mismatch last (never trusted ahead of the real
    one). Inside a tier, the name with the most rounds wins."""
    rows = conn.execute(
        """SELECT l.player_name,
                  (SELECT COUNT(*) FROM handicap_rounds hr WHERE hr.player_name = l.player_name) AS n
           FROM handicap_player_links l WHERE l.customer_id = ?""", (int(customer_id),)).fetchall()
    rank = {"match": 0, "likely": 1, "mismatch": 2}
    out = sorted(rows, key=lambda r: (rank[name_matches(conn, r[0], customer_id)], -(r[1] or 0), r[0]))
    return [r[0] for r in out]


def audit(conn) -> dict:
    """READ-ONLY. Every link, scorecard and handicap round carrying a
    customer_id whose name does not belong to that customer."""
    out = {"links": [], "scorecards": [], "handicap_rounds": [], "likely": []}
    for r in conn.execute(
            """SELECT l.player_name, l.customer_name, l.customer_id, l.linked_at,
                      (SELECT COUNT(*) FROM handicap_rounds hr WHERE hr.player_name = l.player_name) AS n,
                      (SELECT MAX(round_date) FROM handicap_rounds hr WHERE hr.player_name = l.player_name) AS last
               FROM handicap_player_links l WHERE l.customer_id IS NOT NULL
               ORDER BY l.player_name""").fetchall():
        v = name_matches(conn, r[0], r[2])
        row = {"player_name": r[0], "customer_id": r[2], "customer": _canonical(conn, r[2]),
               "link_label": r[1], "linked_at": r[3], "rounds": r[4], "last_round": r[5]}
        if v == "mismatch":
            out["links"].append(row)
        elif v == "likely":
            out["likely"].append(row)
    for r in conn.execute(
            """SELECT player_name, customer_id, COUNT(*) AS n, MIN(round_date) AS first,
                      MAX(round_date) AS last, GROUP_CONCAT(id) AS ids
               FROM scoring_rounds WHERE customer_id IS NOT NULL
               GROUP BY player_name, customer_id""").fetchall():
        if name_matches(conn, r[0], r[1]) == "mismatch":
            out["scorecards"].append({"player_name": r[0], "customer_id": r[1],
                                      "customer": _canonical(conn, r[1]), "cards": r[2],
                                      "first": r[3], "last": r[4],
                                      "ids": [int(x) for x in (r[5] or "").split(",") if x][:20]})
    try:
        hr = conn.execute(
            """SELECT player_name, customer_id, COUNT(*) AS n, MAX(round_date) AS last
               FROM handicap_rounds WHERE customer_id IS NOT NULL
               GROUP BY player_name, customer_id""").fetchall()
    except Exception:
        hr = []
    for r in hr:
        if name_matches(conn, r[0], r[1]) == "mismatch":
            out["handicap_rounds"].append({"player_name": r[0], "customer_id": r[1],
                                           "customer": _canonical(conn, r[1]),
                                           "rounds": r[2], "last": r[3]})
    out["counts"] = {k: len(out[k]) for k in ("links", "scorecards", "handicap_rounds", "likely")}
    out["clean"] = not (out["links"] or out["scorecards"] or out["handicap_rounds"])
    return out


def unlink(conn, player_name: str, customer_id: int, apply: bool = False, note: str = "") -> dict:
    """Take a wrong GG name off a customer. The link keeps its row (and the
    player's rounds stay under their own name) with no customer; every
    scorecard and handicap round of that name on that customer loses the id;
    the pair goes on the block list so no automatic writer links it back.
    Dry run by default. The caller commits."""
    cid = int(customer_id)
    key = _tokens(player_name)
    links = [r[0] for r in conn.execute(
        "SELECT player_name FROM handicap_player_links WHERE customer_id = ?", (cid,)).fetchall()
        if _tokens(r[0]) == key]
    cards = [(r[0], r[1]) for r in conn.execute(
        "SELECT id, player_name FROM scoring_rounds WHERE customer_id = ?", (cid,)).fetchall()
        if _tokens(r[1]) == key]
    try:
        hrs = [r[0] for r in conn.execute(
            "SELECT id, player_name FROM handicap_rounds WHERE customer_id = ?", (cid,)).fetchall()
            if _tokens(r[1]) == key]
    except Exception:
        hrs = []
    out = {"player_name": player_name, "customer_id": cid, "customer": _canonical(conn, cid),
           "verdict": name_matches(conn, player_name, cid),
           "links": links, "scorecards": [c[0] for c in cards], "handicap_rounds": len(hrs),
           "applied": bool(apply)}
    if not (links or cards or hrs):
        out["error"] = f"nothing named {player_name!r} is on customer {cid}"
        return out
    if not apply:
        return out
    for pn in links:
        conn.execute("UPDATE handicap_player_links SET customer_id = NULL, customer_name = NULL "
                     "WHERE player_name = ? AND customer_id = ?", (pn, cid))
    for sid, _ in cards:
        conn.execute("UPDATE scoring_rounds SET customer_id = NULL WHERE id = ?", (sid,))
    for hid in hrs:
        conn.execute("UPDATE handicap_rounds SET customer_id = NULL WHERE id = ?", (hid,))
    blocked = _blocked(conn)
    if not is_blocked(conn, player_name, cid):
        blocked.append({"player_name": player_name, "customer_id": cid, "note": note})
        conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (BLOCK_SETTING, json.dumps(blocked)))
    return out
