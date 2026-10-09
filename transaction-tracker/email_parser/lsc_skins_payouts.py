"""Lone Star Cup DAILY SKINS winners -> the PAYOUTS page (Kerry 10/9:
"Daily Winner Amounts should go to PAYOUTS so I can easily pay them per
normal").

The rule of record is lsc_cup.compute_skins_payout (CA #725/#726): each 18
is its own pot ($25 x the players in that round who bought the weekend
skins), Saturday team NET skins in two sessions (AM Fourball, PM
Foursomes), Sunday individual GROSS skins in two flights, no carryover,
money held until every entry posts every hole. This module does not
re-decide any of that. It reads the staff board the Cup tab already
computes and adds a winner's amounts up PER DAY: Saturday = AM + PM,
Sunday = both flights.

What it writes, and only on apply (Kerry ratifies before any money row is
written, rule 3b):
  - one `tgf_payouts` row per winner per day on event 3329's
    `tgf_events` row (found or created from the Tracker event,
    `_ensure_tgf_event_row`), category 'skins', the shape every normal
    event's skins winner has, so the PAYOUTS page lists it with its Pay
    link, the Venmo matcher can mark it PAID, and `lsc_skins_pot` drains;
  - description "LSC SAT Skins — Fourball x2 (holes 3, 7) $41.67 · ..."
    The "LSC <DAY> Skins" prefix is how a re-run finds its own rows. It
    is not "auto:", so the GG auto-recorder's force path and
    scoring-payouts-clear-auto never delete these.

A day is written only when it is FINAL: every skins group with entrants
in every session that day is complete (every card posted), and every
session that day is scored from REAL entered cards (never the staging
mock dial). Idempotent: re-running changes nothing. A changed result
updates or removes UNPAID rows only; a PAID row is never touched, and a
paid row that no longer matches is reported for Kerry instead.
"""
from __future__ import annotations

import logging
from datetime import date as _date

logger = logging.getLogger(__name__)

CATEGORY = "skins"
DAY_TAGS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_TITLE = {"fourball": "Fourball", "chapman": "Foursomes",
          "foursomes": "Foursomes", "alternate_shot": "Foursomes",
          "singles": "Singles"}


def _day_tag(iso: str | None) -> str | None:
    try:
        return DAY_TAGS[_date.fromisoformat(str(iso)[:10]).weekday()]
    except (TypeError, ValueError):
        return None


def prefix_for(tag: str) -> str:
    return f"LSC {tag} Skins"


def _holes_txt(holes: list) -> str:
    if not holes:
        return ""
    return ("hole " if len(holes) == 1 else "holes ") + ", ".join(str(h) for h in holes)


def plan_daily_skins(board: dict) -> dict:
    """Pure: the STAFF board (lsc_cup board payload, money not stripped)
    -> per day, is it final, why not, and the winner rows it would pay.
    Writes nothing, reads nothing."""
    entry = set(board.get("entry_sessions") or [])
    by_date: dict = {}
    order: list = []
    for s in board.get("sessions") or []:
        d = s.get("date")
        if d not in by_date:
            by_date[d] = []
            order.append(d)
        by_date[d].append(s)
    days = []
    for d in sorted(order, key=lambda x: str(x or "")):
        ss = by_date[d]
        tag = _day_tag(d)
        blockers: list = []
        if not tag:
            blockers.append(f"session(s) {', '.join(str(s.get('id')) for s in ss)} "
                            "carry no date in the lsc_matches dial")
        per: dict = {}
        unallocated = 0
        pot = 0
        for s in ss:
            sid = s.get("id")
            sk = s.get("skins") or {}
            title = _TITLE.get(str(s.get("format") or "").lower(),
                               str(s.get("title") or sid))
            if sk.get("pot_cents") is None:
                blockers.append(f"{sid}: no staff skins payout on the board")
                continue
            pot += int(sk.get("pot_cents") or 0)
            if sid not in entry:
                blockers.append(f"{sid}: not scored from entered cards "
                                "(mock or no scores), never paid from")
            for g in sk.get("groups") or []:
                if not g.get("entrants"):
                    continue
                if not g.get("complete"):
                    blockers.append(f"{sid} {g.get('label')}: skins held, "
                                    "cards still out")
                    continue
                unallocated += int(g.get("unpaid_cents") or 0)
                part = title + (f" Flight {g['flight']}" if g.get("flight") else "")
                for p in g.get("payouts") or []:
                    holes = [h.get("hole") for h in g.get("holes") or []
                             if h.get("winner") == p.get("key")]
                    for pp in p.get("per_player") or []:
                        cid = int(pp["customer_id"])
                        acc = per.setdefault(cid, {"cents": 0, "skins": 0, "parts": []})
                        acc["cents"] += int(pp.get("cents") or 0)
                        acc["skins"] += int(p.get("skins") or 0)
                        acc["parts"].append({"session": sid, "game": part,
                                             "label": p.get("label"),
                                             "skins": p.get("skins"),
                                             "holes": holes,
                                             "cents": int(pp.get("cents") or 0)})
        rows = []
        if tag:
            for cid, acc in sorted(per.items(), key=lambda kv: (-kv[1]["cents"], kv[0])):
                bits = [f"{x['game']} ×{x['skins']} ({_holes_txt(x['holes'])}) "
                        f"${x['cents'] / 100:.2f}" for x in acc["parts"]]
                rows.append({"customer_id": cid, "category": CATEGORY,
                             "amount": round(acc["cents"] / 100.0, 2),
                             "cents": acc["cents"], "skins": acc["skins"],
                             "description": f"{prefix_for(tag)} — " + " · ".join(bits),
                             "parts": acc["parts"]})
        days.append({"date": d, "day": tag,
                     "sessions": [s.get("id") for s in ss],
                     "final": not blockers, "blockers": blockers,
                     "pot_cents": pot, "unallocated_cents": unallocated,
                     "paid_cents": sum(r["cents"] for r in rows),
                     "rows": rows})
    return {"event_id": board.get("event_id"), "source": board.get("source"),
            "days": days}


def _is_paid(conn, row) -> bool:
    if row["paid_at"]:
        return True
    if not row["acct_transaction_id"]:
        return False
    t = conn.execute("SELECT source, COALESCE(status, 'active') AS st "
                     "FROM acct_transactions WHERE id = ?",
                     (row["acct_transaction_id"],)).fetchone()
    return bool(t and t["source"] != "pending" and t["st"] in ("active", "reconciled"))


def lsc_skins_payouts(apply: bool = False, db_path=None, board: dict | None = None) -> dict:
    """Dry run by default: what the PAYOUTS page would get for each final
    day of Cup skins, against what is already there. apply=True writes
    (creates / updates unpaid / removes unpaid rows a changed result no
    longer pays). Never touches a paid row. `board` lets a test hand in a
    staff board; normally it is the live (or frozen) Cup board."""
    from email_parser import database as db
    from email_parser import lsc_cup
    if board is None:
        board = lsc_cup._board_payload(db_path, use_frozen=True)
    if not board.get("configured"):
        return {"error": "no lsc_matches dial"}
    eid = board.get("event_id")
    if not eid:
        return {"error": "the lsc_matches dial has no event_id"}
    plan = plan_daily_skins(board)
    out = {"applied": bool(apply), "event_id": eid, "source": plan["source"],
           "days": [], "writes": 0}
    with db._connect(db_path) as conn:
        ev = conn.execute("SELECT * FROM events WHERE id = ?", (int(eid),)).fetchone()
        if not ev:
            return {"error": f"event {eid} not found"}
        ev = dict(ev)
        trow, full, _bare = db._tgf_event_lookup(conn, ev)
        tgf_id = trow["id"] if trow else None
        out["tgf_event"] = {"id": tgf_id, "code": full,
                            "state": "exists" if tgf_id else "would create"}
        existing = []
        if tgf_id:
            existing = [dict(r, paid=_is_paid(conn, r)) for r in conn.execute(
                "SELECT id, customer_id, category, amount, description, "
                "acct_transaction_id, paid_at FROM tgf_payouts "
                "WHERE event_id = ? AND lower(category) = ?",
                (tgf_id, CATEGORY)).fetchall()]

        def _name(cid):
            r = conn.execute("SELECT first_name, last_name FROM customers "
                             "WHERE customer_id = ?", (cid,)).fetchone()
            return " ".join(x for x in (r["first_name"], r["last_name"]) if x) if r else f"#{cid}"

        todo = []          # (kind, payload)
        for day in plan["days"]:
            d_out = {k: day[k] for k in ("date", "day", "sessions", "final",
                                         "blockers", "pot_cents",
                                         "unallocated_cents", "paid_cents")}
            d_out["actions"] = []
            if not day["final"] or not day["day"]:
                d_out["actions"].append({"action": "held",
                                         "why": "day not final; nothing written, "
                                                "existing rows left as they are"})
                out["days"].append(d_out)
                continue
            pre = prefix_for(day["day"]).lower()
            mine = [e for e in existing
                    if (e["description"] or "").lower().startswith(pre)]
            have: dict = {}
            for e in mine:
                have.setdefault(int(e["customer_id"]), []).append(e)
            for r in day["rows"]:
                cid = r["customer_id"]
                base = {"customer_id": cid, "name": _name(cid),
                        "amount": r["amount"], "description": r["description"]}
                rows = have.pop(cid, [])
                paid = [x for x in rows if x["paid"]]
                unpaid = [x for x in rows if not x["paid"]]
                if paid:
                    psum = round(sum(float(x["amount"]) for x in paid), 2)
                    if abs(psum - r["amount"]) < 0.005:
                        d_out["actions"].append({**base, "action": "paid_ok",
                                                 "payout_ids": [x["id"] for x in paid]})
                    else:
                        d_out["actions"].append({**base, "action": "paid_differs",
                                                 "paid": psum,
                                                 "delta": round(r["amount"] - psum, 2),
                                                 "payout_ids": [x["id"] for x in paid],
                                                 "why": "a PAID row is never changed; "
                                                        "Kerry decides the difference"})
                    for x in unpaid:      # a paid row already covers this winner
                        d_out["actions"].append({**base, "action": "delete_duplicate",
                                                 "payout_id": x["id"]})
                        todo.append(("delete", x))
                    continue
                if not unpaid:
                    d_out["actions"].append({**base, "action": "create"})
                    todo.append(("create", {**r, "date": day["date"]}))
                    continue
                first, extra = unpaid[0], unpaid[1:]
                same = (abs(float(first["amount"]) - r["amount"]) < 0.005
                        and (first["description"] or "") == r["description"])
                if same:
                    d_out["actions"].append({**base, "action": "unchanged",
                                             "payout_id": first["id"]})
                else:
                    d_out["actions"].append({**base, "action": "update",
                                             "payout_id": first["id"],
                                             "was": float(first["amount"])})
                    todo.append(("update", (first, r)))
                for x in extra:
                    d_out["actions"].append({**base, "action": "delete_duplicate",
                                             "payout_id": x["id"]})
                    todo.append(("delete", x))
            # rows of this day for someone the result no longer pays
            for cid, rows in have.items():
                for x in rows:
                    base = {"customer_id": cid, "name": _name(cid),
                            "amount": float(x["amount"]),
                            "description": x["description"], "payout_id": x["id"]}
                    if x["paid"]:
                        d_out["actions"].append({**base, "action": "paid_no_longer_wins",
                                                 "why": "a PAID row is never changed; "
                                                        "Kerry decides"})
                    else:
                        d_out["actions"].append({**base, "action": "delete"})
                        todo.append(("delete", x))
            out["days"].append(d_out)
        out["writes"] = len(todo)
        if not apply or not todo:
            return out

        if not tgf_id:
            tgf_id, _created = db._ensure_tgf_event_row(conn, ev)
            out["tgf_event"].update({"id": tgf_id, "state": "created"})
        new_ids = []
        for kind, p in todo:
            if kind == "create":
                nid = conn.execute(
                    "INSERT INTO tgf_payouts (event_id, customer_id, category, "
                    "amount, description) VALUES (?, ?, ?, ?, ?) RETURNING id",
                    (tgf_id, p["customer_id"], CATEGORY, p["amount"],
                     p["description"])).fetchone()[0]
                new_ids.append(nid)
            elif kind == "update":
                row, want = p
                conn.execute("UPDATE tgf_payouts SET amount = ?, description = ? "
                             "WHERE id = ? AND paid_at IS NULL",
                             (want["amount"], want["description"], row["id"]))
                if row["acct_transaction_id"]:
                    conn.execute(
                        "UPDATE acct_transactions SET total_amount = ?, amount = ? "
                        "WHERE id = ? AND source = 'pending'",
                        (want["amount"], -want["amount"], row["acct_transaction_id"]))
            elif kind == "delete":
                if p["acct_transaction_id"]:
                    conn.execute("DELETE FROM acct_transactions "
                                 "WHERE id = ? AND source = 'pending'",
                                 (p["acct_transaction_id"],))
                conn.execute("DELETE FROM tgf_payouts WHERE id = ? AND paid_at IS NULL",
                             (p["id"],))
        if new_ids:
            ph = ",".join("?" * len(new_ids))
            fresh = conn.execute(
                f"""SELECT p.id, p.event_id, p.customer_id, p.amount, p.category,
                           p.description, e.event_date, e.name AS event_name
                      FROM tgf_payouts p JOIN tgf_events e ON e.id = p.event_id
                     WHERE p.id IN ({ph})""", new_ids).fetchall()
            out["venmo_matched"] = db._reconcile_payouts_with_venmo(conn, fresh)
        st = conn.execute(
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS total, "
            "COUNT(DISTINCT customer_id) AS winners FROM tgf_payouts "
            "WHERE event_id = ?", (tgf_id,)).fetchone()
        conn.execute("UPDATE tgf_events SET total_purse = ?, winners_count = ?, "
                     "payouts_count = ? WHERE id = ?",
                     (st["total"], st["winners"], st["cnt"], tgf_id))
        conn.commit()
    try:
        db.log_agent_action("mcp-claude", "scoring-lsc-skins-payouts",
                            f"event {eid}: {out['writes']} write(s) on tgf_event {tgf_id}",
                            db_path=db_path)
    except Exception:
        logger.exception("lsc skins payouts: action log failed")
    return out
