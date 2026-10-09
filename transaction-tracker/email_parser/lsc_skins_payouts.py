"""Lone Star Cup SKINS winners -> the PAYOUTS page, one row per winner per
SESSION (Kerry 10/9: "Daily Winner Amounts should go to PAYOUTS so I can
easily pay them per normal", then the same day: "So $575 available for each
skins session. Session pots standalone.").

The rule of record is lsc_cup.compute_skins_payout (CA #725/#726): each
session is its own pot ($25 x the players in that session who bought the
weekend skins), Saturday team NET skins in two sessions (AM Fourball, PM
Foursomes) at the full session allowance off zero, Sunday individual GROSS
skins in two flights split 50/50, no carryover, money held until every
entry posts every hole. This module does not re-decide any of that. It
reads the staff board the Cup tab already computes and writes each
SESSION's winners on their own, never added up across a day.

What it writes, and only on apply (Kerry ratifies before any money row is
written, rule 3b):
  - one `tgf_payouts` row per winner per session on event 3329's
    `tgf_events` row (found or created from the Tracker event,
    `_ensure_tgf_event_row`), category 'skins', the shape every normal
    event's skins winner has, so the PAYOUTS page lists it with its Pay
    link, the Venmo matcher can mark it PAID, and `lsc_skins_pot` drains;
  - description "LSC SAT AM Skins — Fourball ×2 (holes 3, 7) $41.67",
    "LSC SAT PM Skins — Foursomes ×1 (hole 5) $57.50",
    "LSC SUN Skins — Flight 1 ×1 (hole 3) $28.75 · Flight 2 ...".
    The "LSC <SESSION> Skins" prefix is how a re-run finds its own rows. It
    is not "auto:", so the GG auto-recorder's force path and
    scoring-payouts-clear-auto never delete these.

A session is written as soon as IT is final: every skins group with
entrants in it is complete (every card posted) and it is scored from REAL
entered cards (never the staging mock dial). It does not wait for the other
session that day. Idempotent: re-running changes nothing. A changed result
updates or removes UNPAID rows only; a PAID row is never touched, and a
paid row that no longer matches is reported for Kerry instead.

Before 10/9 PM this module wrote one row per winner per DAY ("LSC SAT
Skins — ..."). No such row was ever written in production (the dry run
showed 0 writes), but if one exists: an UNPAID per-day row is removed when
a session of that day is written (the session rows replace it); a PAID
per-day row holds that whole day for Kerry, so nobody is paid twice.
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


def session_tag(sess: dict, n_that_day: int = 1) -> str | None:
    """'SAT AM', 'SAT PM', 'SUN': the day from the session's date, and the
    half of the day from its id (sat-am / sat-pm). A day with one session
    is just the day; a day with several whose ids name no AM/PM uses the id."""
    day = _day_tag(sess.get("date"))
    if not day:
        return None
    sid = str(sess.get("id") or "")
    half = next((t.upper() for t in sid.lower().replace("_", "-").split("-")
                 if t in ("am", "pm")), None)
    if half:
        return f"{day} {half}"
    if n_that_day > 1:
        return f"{day} {sid.upper()}"
    return day


def prefix_for(tag: str) -> str:
    return f"LSC {tag} Skins"


def _holes_txt(holes: list) -> str:
    if not holes:
        return ""
    return ("hole " if len(holes) == 1 else "holes ") + ", ".join(str(h) for h in holes)


def plan_session_skins(board: dict) -> dict:
    """Pure: the STAFF board (lsc_cup board payload, money not stripped)
    -> per SESSION, is it final, why not, and the winner rows it would pay.
    Writes nothing, reads nothing."""
    entry = set(board.get("entry_sessions") or [])
    sessions = board.get("sessions") or []
    per_day: dict = {}
    for s in sessions:
        per_day[s.get("date")] = per_day.get(s.get("date"), 0) + 1
    out = []
    for s in sessions:
        sid = s.get("id")
        tag = session_tag(s, per_day.get(s.get("date"), 1))
        sk = s.get("skins") or {}
        title = _TITLE.get(str(s.get("format") or "").lower(),
                           str(s.get("title") or sid))
        blockers: list = []
        if not tag:
            blockers.append(f"{sid}: no date in the lsc_matches dial")
        per: dict = {}
        unallocated = 0
        pot = 0
        if sk.get("pot_cents") is None:
            blockers.append(f"{sid}: no staff skins payout on the board")
        else:
            pot = int(sk.get("pot_cents") or 0)
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
                part = f"Flight {g['flight']}" if g.get("flight") else title
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
        out.append({"session": sid, "date": s.get("date"), "tag": tag,
                    "day": _day_tag(s.get("date")), "format": s.get("format"),
                    "final": not blockers, "blockers": blockers,
                    "pot_cents": pot, "unallocated_cents": unallocated,
                    "paid_cents": sum(r["cents"] for r in rows),
                    "rows": rows})
    return {"event_id": board.get("event_id"), "source": board.get("source"),
            "sessions": out}


def _is_paid(conn, row) -> bool:
    if row["paid_at"]:
        return True
    if not row["acct_transaction_id"]:
        return False
    t = conn.execute("SELECT source, COALESCE(status, 'active') AS st "
                     "FROM acct_transactions WHERE id = ?",
                     (row["acct_transaction_id"],)).fetchone()
    return bool(t and t["source"] != "pending" and t["st"] in ("active", "reconciled"))


def _starts(desc, prefix: str) -> bool:
    """Does a description belong to this prefix? "LSC SAT Skins" must not
    claim "LSC SAT AM Skins" (it doesn't: the next character differs)."""
    return (desc or "").lower().startswith(prefix.lower() + " ")


def lsc_skins_payouts(apply: bool = False, db_path=None, board: dict | None = None) -> dict:
    """Dry run by default: what the PAYOUTS page would get for each final
    SESSION of Cup skins, against what is already there. apply=True writes
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
    plan = plan_session_skins(board)
    out = {"applied": bool(apply), "event_id": eid, "source": plan["source"],
           "sessions": [], "writes": 0}
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

        # The OLD per-day rows ("LSC SAT Skins — ..."), for a day that now
        # pays per session under a different prefix. A PAID one holds the
        # day for Kerry; an UNPAID one is removed once (the sessions replace it).
        legacy_done: set = set()
        todo = []          # (kind, payload)
        for sp in plan["sessions"]:
            s_out = {k: sp[k] for k in ("session", "date", "tag", "final",
                                        "blockers", "pot_cents",
                                        "unallocated_cents", "paid_cents")}
            s_out["blockers"] = list(s_out["blockers"])
            s_out["actions"] = []
            legacy = []
            day = sp.get("day")
            if sp["tag"] and day and sp["tag"] != day:
                legacy = [e for e in existing if _starts(e["description"], prefix_for(day))]
            legacy_paid = [e for e in legacy if e["paid"]]
            if legacy_paid:
                s_out["final"] = False
                s_out["blockers"].append(
                    f"a PAID per-day '{prefix_for(day)}' row exists (payout id(s) "
                    f"{', '.join(str(e['id']) for e in legacy_paid)}); the "
                    "per-session rows would pay twice, Kerry decides")
            if not s_out["final"] or not sp["tag"]:
                s_out["actions"].append({"action": "held",
                                         "why": "session not final; nothing written, "
                                                "existing rows left as they are"})
                out["sessions"].append(s_out)
                continue
            if day not in legacy_done:
                legacy_done.add(day)
                for x in legacy:
                    s_out["actions"].append({"customer_id": x["customer_id"],
                                             "name": _name(x["customer_id"]),
                                             "amount": float(x["amount"]),
                                             "description": x["description"],
                                             "payout_id": x["id"],
                                             "action": "delete_legacy_day_row"})
                    todo.append(("delete", x))
            mine = [e for e in existing if _starts(e["description"], prefix_for(sp["tag"]))]
            have: dict = {}
            for e in mine:
                have.setdefault(int(e["customer_id"]), []).append(e)
            for r in sp["rows"]:
                cid = r["customer_id"]
                base = {"customer_id": cid, "name": _name(cid),
                        "amount": r["amount"], "description": r["description"]}
                rows = have.pop(cid, [])
                paid = [x for x in rows if x["paid"]]
                unpaid = [x for x in rows if not x["paid"]]
                if paid:
                    psum = round(sum(float(x["amount"]) for x in paid), 2)
                    if abs(psum - r["amount"]) < 0.005:
                        s_out["actions"].append({**base, "action": "paid_ok",
                                                 "payout_ids": [x["id"] for x in paid]})
                    else:
                        s_out["actions"].append({**base, "action": "paid_differs",
                                                 "paid": psum,
                                                 "delta": round(r["amount"] - psum, 2),
                                                 "payout_ids": [x["id"] for x in paid],
                                                 "why": "a PAID row is never changed; "
                                                        "Kerry decides the difference"})
                    for x in unpaid:      # a paid row already covers this winner
                        s_out["actions"].append({**base, "action": "delete_duplicate",
                                                 "payout_id": x["id"]})
                        todo.append(("delete", x))
                    continue
                if not unpaid:
                    s_out["actions"].append({**base, "action": "create"})
                    todo.append(("create", {**r, "date": sp["date"]}))
                    continue
                first, extra = unpaid[0], unpaid[1:]
                same = (abs(float(first["amount"]) - r["amount"]) < 0.005
                        and (first["description"] or "") == r["description"])
                if same:
                    s_out["actions"].append({**base, "action": "unchanged",
                                             "payout_id": first["id"]})
                else:
                    s_out["actions"].append({**base, "action": "update",
                                             "payout_id": first["id"],
                                             "was": float(first["amount"])})
                    todo.append(("update", (first, r)))
                for x in extra:
                    s_out["actions"].append({**base, "action": "delete_duplicate",
                                             "payout_id": x["id"]})
                    todo.append(("delete", x))
            # rows of this session for someone the result no longer pays
            for cid, rows in have.items():
                for x in rows:
                    base = {"customer_id": cid, "name": _name(cid),
                            "amount": float(x["amount"]),
                            "description": x["description"], "payout_id": x["id"]}
                    if x["paid"]:
                        s_out["actions"].append({**base, "action": "paid_no_longer_wins",
                                                 "why": "a PAID row is never changed; "
                                                        "Kerry decides"})
                    else:
                        s_out["actions"].append({**base, "action": "delete"})
                        todo.append(("delete", x))
            out["sessions"].append(s_out)
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
