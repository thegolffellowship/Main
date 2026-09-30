"""Read-only views for the Chief of Staff and the Front Desk (#1048, #1051,
tool list #1057, approved #1060-3). Nothing here writes.

  score_entry_card(event_id, group, customer_id)  tool 7: one group's (or one
      player's) live card: hole-by-hole gross, marks, signatures, the card
      check, CTP and HIO claims. A filter over score_entry.get_entered_scores,
      so the se_* tables are still read only by score_entry.py.
  pairing_history_view(customer_id | event_id, year)  tool 8: who played with
      whom and who rode together, from pairing_history, counting only what
      the pairings engine counts (Golf Genius sources, played dates).
  get_standard(name, section)  tool 9: the standards the crews keep in the
      repo, by name, whole or one section.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ── tool 7 ─────────────────────────────────────────────────────────────────
def score_entry_card(event_id: int, group: int | None = None, customer_id: int | None = None,
                     db_path=None) -> dict:
    from email_parser import score_entry as se
    if not group and not customer_id:
        return {"error": "give group (the group number on the sheet) or customer_id"}
    read = se.get_entered_scores(int(event_id), db_path=db_path)
    out = {"event_id": read["event_id"], "official": False,
           "note": "live entered scores, not the money record; read-only",
           "version": read["version"], "as_of": read["as_of"], "rounds": []}
    for r in read["rounds"]:
        gids = set()
        if group:
            gids |= {g["group_id"] for g in r["groups"] if g["group_num"] == int(group)}
        if customer_id:
            gids |= {p["group_id"] for p in r["players"] if p["customer_id"] == int(customer_id)}
        if not gids:
            continue
        players = [p for p in r["players"] if p["group_id"] in gids]
        cids = {p["customer_id"] for p in players}
        out["rounds"].append({
            "round_id": r["round_id"], "date": r["date"], "label": r["label"],
            "holes": r["holes"], "status": r["status"], "course": r["course"],
            "groups": [g for g in r["groups"] if g["group_id"] in gids],
            "players": players,
            "teams": [t for t in r["teams"] if t["group_id"] in gids],
            "signoffs": [s for s in r["signoffs"] if s["customer_id"] in cids],
            "card_checks": [c for c in r["card_checks"] if c["group_id"] in gids],
            "ctp": {h: c for h, c in r["ctp"].items() if c and c.get("customer_id") in cids},
            "hio": [h for h in r["hio"] if h["customer_id"] in cids],
        })
    if not out["rounds"]:
        out["error"] = "no entered round has that group or player for this event"
    return out


# ── tool 8 ─────────────────────────────────────────────────────────────────
COUNTED_RULE = ("Counts Golf Genius rows only (source gg_teesheet / gg_teamnet; app-saved "
                "sheets are plans, Kerry 2026-09-08) on dates before today, Central. "
                "'rode' is the tee-sheet cart pairing (sequence 1&2 / 3&4). "
                "A solo cart is an event where the player has pair rows from the tee sheet "
                "but no rode partner; events with only gg_teamnet rows carry no cart data "
                "and are left out of the cart record.")


def _name_map(conn, cids) -> dict:
    cids = [c for c in set(cids) if c]
    if not cids:
        return {}
    q = ",".join("?" * len(cids))
    return {r["customer_id"]: f"{r['first_name']} {r['last_name']}".strip()
            for r in conn.execute(f"SELECT customer_id, first_name, last_name FROM customers "
                                  f"WHERE customer_id IN ({q})", cids)}


def pairing_history_view(customer_id: int = 0, event_id: int = 0, year: int = 0,
                         db_path=None) -> dict:
    from email_parser import database as db
    from email_parser.timezone_utils import today_central_str
    if not customer_id and not event_id:
        return {"error": "give customer_id or event_id"}
    today = today_central_str()
    where = ["lower(COALESCE(ph.source, 'app')) <> 'app'", "ph.event_date < ?"]
    args: list = [today]
    if year:
        where.append("substr(ph.event_date, 1, 4) = ?")
        args.append(str(int(year)))
    if customer_id:
        where.append("(ph.customer_a_id = ? OR ph.customer_b_id = ?)")
        args += [int(customer_id), int(customer_id)]
    if event_id:
        where.append("ph.event_id = ?")
        args.append(int(event_id))
    with db._connect(db_path) as conn:
        db._ensure_pairing_tables(conn)
        rows = [dict(r) for r in conn.execute(
            f"""SELECT ph.event_id, ph.event_date, ph.round_id, ph.customer_a_id, ph.customer_b_id,
                       ph.player_a, ph.player_b, COALESCE(ph.rode, 0) AS rode,
                       lower(COALESCE(ph.source, 'app')) AS source, e.item_name AS event_name
                FROM pairing_history ph LEFT JOIN events e ON e.id = ph.event_id
                WHERE {' AND '.join(where)} ORDER BY ph.event_date, ph.event_id""", args)]
        names = _name_map(conn, [r["customer_a_id"] for r in rows] + [r["customer_b_id"] for r in rows]
                          + [customer_id])
        unlinked = sum(1 for r in rows if not r["customer_a_id"] or not r["customer_b_id"])

    def nm(cid, fallback):
        return names.get(cid) or fallback

    if customer_id:
        cid = int(customer_id)
        mates: dict = {}
        events: dict = {}
        for r in rows:
            me_a = r["customer_a_id"] == cid
            other = r["customer_b_id"] if me_a else r["customer_a_id"]
            oname = nm(other, r["player_b"] if me_a else r["player_a"])
            key = other or f"name:{oname.lower()}"
            m = mates.setdefault(key, {"customer_id": other, "name": oname,
                                       "played_with": 0, "rode_with": 0, "events": []})
            m["played_with"] += 1
            m["rode_with"] += int(bool(r["rode"]))
            m["events"].append(r["event_name"] or r["event_id"])
            ek = (r["event_id"], r["round_id"] or "")
            e = events.setdefault(ek, {"event_id": r["event_id"], "event": r["event_name"],
                                       "date": r["event_date"], "round_id": r["round_id"],
                                       "sources": set(), "rode_with": None})
            e["sources"].add(r["source"])
            if r["rode"]:
                e["rode_with"] = oname
        cart = []
        for e in events.values():
            if "gg_teesheet" not in e["sources"]:
                continue
            cart.append({"event_id": e["event_id"], "event": e["event"], "date": e["date"],
                         "round_id": e["round_id"], "rode_with": e["rode_with"],
                         "solo_cart": e["rode_with"] is None})
        return {"customer_id": cid, "name": names.get(cid), "rule": COUNTED_RULE,
                "rounds_with_pairs": len(events),
                "partners": sorted(mates.values(), key=lambda m: (-m["played_with"], m["name"])),
                "cart_record": cart, "solo_carts": sum(1 for c in cart if c["solo_cart"]),
                "unlinked_rows": unlinked}
    pairs = [{"a": {"customer_id": r["customer_a_id"], "name": nm(r["customer_a_id"], r["player_a"])},
              "b": {"customer_id": r["customer_b_id"], "name": nm(r["customer_b_id"], r["player_b"])},
              "rode": bool(r["rode"]), "round_id": r["round_id"], "source": r["source"]}
             for r in rows]
    return {"event_id": int(event_id), "event": rows[0]["event_name"] if rows else None,
            "date": rows[0]["event_date"] if rows else None, "rule": COUNTED_RULE,
            "pairs": pairs, "rode_pairs": [p for p in pairs if p["rode"]],
            "unlinked_rows": unlinked}


# ── tool 9 ─────────────────────────────────────────────────────────────────
# The standards of record by short name. Anything a crew commits under
# docs/standards/<name>.md is served too, by its file stem.
STANDARDS = {
    "side-games": "docs/claude/side-games.md",
    "pairings": "docs/claude/pairings.md",
    "event-recaps": "docs/claude/event-recaps.md",
    "handicap": "docs/governance/TGF_Handicap_Standard_v1_0.md",
    "financial-model": "docs/claude/unified-financial-model.md",
    "score-entry": "docs/claude/score-entry.md",
    "facebook-events": "docs/claude/facebook-events.md",
    "insider-voice": "docs/claude/templates/insider-voice-examples.md",
}


def _catalogue() -> dict:
    cat = {k: ROOT / v for k, v in STANDARDS.items()}
    sd = ROOT / "docs" / "standards"
    if sd.is_dir():
        for f in sorted(sd.glob("*.md")):
            cat.setdefault(f.stem.lower(), f)
    return {k: v for k, v in cat.items() if v.is_file()}


def _section(text: str, want: str) -> str | None:
    want = want.strip().lower()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and want in m.group(2).lower():
            level = len(m.group(1))
            out = [line]
            for nxt in lines[i + 1:]:
                n = re.match(r"^(#{1,6})\s", nxt)
                if n and len(n.group(1)) <= level:
                    break
                out.append(nxt)
            return "\n".join(out)
    return None


def get_standard(name: str = "", section: str = "") -> dict:
    cat = _catalogue()
    if not name.strip():
        return {"standards": [{"name": k, "path": str(v.relative_to(ROOT)), "bytes": v.stat().st_size}
                              for k, v in cat.items()],
                "hint": "get_standard(name) for the whole text, or add section='<heading words>' for one section"}
    key = name.strip().lower().removesuffix(".md")
    f = cat.get(key)
    if not f:
        return {"error": f"no standard named {name!r}", "available": sorted(cat)}
    text = f.read_text(encoding="utf-8")
    if section.strip():
        part = _section(text, section)
        if part is None:
            heads = [l.lstrip("#").strip() for l in text.splitlines() if re.match(r"^#{1,6}\s", l)]
            return {"error": f"no heading in {key} contains {section!r}", "headings": heads[:200]}
        text = part
    return {"name": key, "path": str(f.relative_to(ROOT)), "chars": len(text), "text": text}
