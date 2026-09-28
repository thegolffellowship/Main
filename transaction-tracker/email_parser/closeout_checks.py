"""Closeout off Golf Genius (v2.511.0): pairing history from entered groups,
and the "results are final" test.

CA mailbox #829 item 3 (GO, rule 3b): "Closeout: PAIRING HISTORY from
entered groups, and the 'results are final' test rewrite." Needed for the
first events off GG (10/13). Closeout gap list #776 B2 and B5.

1. PAIRING HISTORY FROM ENTERED GROUPS -- `pairing_history_from_entry`.
   Today the ONLY record of who played together is the FINAL Golf Genius
   pairings ingest (closeout skill 1.2). Off GG, the score-entry groups are
   that record: the people who actually entered scores in one group played
   together. Rules, the same as the GG writers:
   - a player with NO entered hole played with nobody (a no-show or a
     withdrawal seeded from PAIRINGS) and is never paired;
   - BLIND DRAWS NEVER COUNT (Kerry 2026-09-08). Score entry has no blind
     seat -- a blind is not a person on the card -- so none can appear;
   - cart partners ("rode") are seats 1&2 and 3&4 of the group, the order
     score entry keeps players in (Kerry's cart ruling);
   - PREVIEW (test) rounds are never read;
   - each score-entry round is its own round_id ("se:<id>"), so a two-day
     event or the cup's three sessions keep every round's pairs.
   It follows the G-0 cutover (entry_publish): it WRITES only when the
   event has no Golf Genius pairing rows and falls on or after
   `entry_record_from`. Otherwise it runs in SHADOW and returns the pair
   diff against the GG rows -- the 9/29 and 10/6 parity check for pairings.

2. "RESULTS ARE FINAL" -- `closeout_final_check`. The 9 PM closeout acts on
   an event only when this says final; otherwise it names what is missing
   and the 5:30 AM catch-up finishes it. Two eras, decided per event:
   - GG era (the event has GG scorecards): cards equal the field, no card
     without a customer_id, no duplicate cards, every GG board posted WITH
     a purse, and payouts recorded.
   - ENTRY era (G-0 authoritative): every entered card closed and signed
     (an open disputed hole voids the player's signature, so disputes are
     covered), the round published into scorecards, no hole-in-one claim
     still pending, and payouts computed. Unanswered CTP holes are a
     warning until the matrix names the CTP holes (Track A, 10/13).

Entered scores are read ONLY through score_entry.get_entered_scores (the
score-entry tables belong to score_entry.py; test_score_entry.py guards it).
Both functions are read-only except `pairing_history_from_entry(apply=True)`
in authoritative mode. Portable SQL: explicit DELETE then INSERT, no DDL.
"""
from __future__ import annotations

from email_parser import database as db
from email_parser import entry_publish as ep
from email_parser import score_entry as se

ENTRY_ROUND_PREFIX = "se:"
GG_PAIR_SOURCES = ("gg_teamnet", "gg_teesheet")


def _resolve_event(conn, event: str | int) -> dict | None:
    s = str(event or "").strip()
    if not s:
        return None
    if s.isdigit():
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(s),)).fetchone()
        if r:
            return dict(r)
    r = conn.execute("SELECT * FROM events WHERE lower(item_name) = lower(?)", (s,)).fetchone()
    return dict(r) if r else None


def _names(conn, cids) -> dict:
    out = {}
    for cid in {c for c in cids if c}:
        r = conn.execute("SELECT TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) AS nm "
                         "FROM customers WHERE customer_id = ?", (cid,)).fetchone()
        out[cid] = (r["nm"] if r and (r["nm"] or "").strip() else f"customer {cid}")
    return out


def _entered_groups(read: dict) -> list[dict]:
    """[{round_id, group_id, players: [cid in seat order], no_shows: [cid]}]"""
    out = []
    for rnd in read.get("rounds") or []:
        if ep._is_preview(rnd):
            continue
        by_group: dict = {}
        for p in rnd.get("players") or []:
            g = by_group.setdefault(p.get("group_id"), {"players": [], "no_shows": []})
            played = any(v is not None for v in (p.get("scores") or {}).values())
            (g["players"] if played else g["no_shows"]).append(p.get("customer_id"))
        for gid, g in by_group.items():
            out.append({"round_id": rnd["round_id"], "group_id": gid, **g})
    return out


def _pairs(groups: list[dict]) -> list[dict]:
    out = []
    for g in groups:
        ps = [c for c in g["players"] if c]
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                out.append({"a": ps[i], "b": ps[j], "rode": 1 if i // 2 == j // 2 else 0,
                            "round_id": f"{ENTRY_ROUND_PREFIX}{g['round_id']}"})
    return out


def pairing_history_from_entry(event: str | int, apply: bool = False, db_path=None,
                               _read: dict | None = None) -> dict:
    with db._connect(db_path) as conn:
        db._ensure_pairing_tables(conn)
        ev = _resolve_event(conn, event)
        if not ev:
            return {"error": f"no event matches {event!r}"}
        read = _read if _read is not None else se.get_entered_scores(ev["id"], db_path=db_path)
        groups = _entered_groups(read)
        pairs = _pairs(groups)
        cids = [c for g in groups for c in g["players"] + g["no_shows"]]
        names = _names(conn, cids)
        gg_rows = [dict(r) for r in conn.execute(
            "SELECT customer_a_id, customer_b_id, player_a, player_b, rode, source "
            "FROM pairing_history WHERE event_id = ? AND lower(COALESCE(source,'app')) IN (?, ?)",
            (ev["id"],) + GG_PAIR_SOURCES).fetchall()]
        cut = ep.cutover_date(db_path)
        ev_date = str(ev.get("event_date") or "")[:10]
        if gg_rows:
            mode, why = "shadow", f"the event has {len(gg_rows)} Golf Genius pair row(s); entered pairs are diffed, not written"
        elif not ev_date:
            mode, why = "shadow", "the event has no date, so the cutover cannot be checked"
        elif ev_date < cut:
            mode, why = "shadow", f"event date {ev_date} is before the entry-record cutover {cut}"
        else:
            mode, why = "authoritative", f"no Golf Genius pair rows and event date {ev_date} >= cutover {cut}"
        out = {"event": {"id": ev["id"], "name": ev["item_name"], "date": ev_date},
               "mode": mode, "why": why, "rounds": sorted({g["round_id"] for g in groups}),
               "groups": len(groups), "pairs": len(pairs),
               "rode_pairs": sum(p["rode"] for p in pairs),
               "not_paired_no_score": sorted(names[c] for g in groups for c in g["no_shows"] if c),
               "applied": False}
        if not groups:
            out["note"] = "no entered groups on this event"
            return out
        key = lambda a, b: tuple(sorted((a, b)))
        entered = {key(p["a"], p["b"]) for p in pairs}
        if mode == "shadow":
            gg = {key(r["customer_a_id"], r["customer_b_id"]) for r in gg_rows
                  if r["customer_a_id"] and r["customer_b_id"]}
            if gg:
                fmt = lambda k: f"{names.get(k[0], k[0])} + {names.get(k[1], k[1])}"
                out["parity"] = {"entered_only": sorted(fmt(k) for k in entered - gg),
                                 "gg_only": sorted(fmt(k) for k in gg - entered),
                                 "match": entered == gg}
            return out
        if not apply:
            out["note"] = "dry run: nothing written (add |apply)"
            return out
        # One source owns an event: the entered rounds replace their own
        # earlier write and the app's PLANS for the event; GG rows cannot
        # exist here (authoritative mode requires none).
        conn.execute("DELETE FROM pairing_history WHERE event_id = ? AND "
                     "(lower(COALESCE(source,'app')) = 'app' OR "
                     " (lower(source) = 'entry' AND round_id LIKE ?))",
                     (ev["id"], ENTRY_ROUND_PREFIX + "%"))
        n = 0
        for p in pairs:
            a, b = sorted((p["a"], p["b"]), key=lambda c: names[c])
            conn.execute(
                "INSERT INTO pairing_history (player_a, player_b, event_id, event_date, "
                "customer_a_id, customer_b_id, rode, source, round_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'entry', ?)",
                (names[a], names[b], ev["id"], ev_date, a, b, p["rode"], p["round_id"]))
            n += 1
        conn.commit()
        out.update({"applied": True, "pairs_written": n})
        return out


def _payout_rows(conn, event_id: int) -> list[dict]:
    try:
        return [dict(r) for r in conn.execute(
            "SELECT p.id, p.customer_id, p.amount, p.description, p.paid_at "
            "FROM tgf_payouts p JOIN tgf_events t ON t.id = p.event_id "
            "WHERE t.events_id = ?", (event_id,)).fetchall()]
    except Exception:
        return []


def closeout_final_check(event: str | int, db_path=None, _read: dict | None = None) -> dict:
    with db._connect(db_path) as conn:
        ev = _resolve_event(conn, event)
        if not ev:
            return {"error": f"no event matches {event!r}"}
        eid = ev["id"]
        blocking: list = []
        warnings: list = []
        cards = [dict(r) for r in conn.execute(
            "SELECT id, customer_id, player_name, tee_id, lower(COALESCE(source,'gg')) AS src "
            "FROM scoring_rounds WHERE event_id = ?", (eid,)).fetchall()]
        gg_cards = [c for c in cards if c["src"] != ep.ENTRY_SOURCE]
        entry_cards = [c for c in cards if c["src"] == ep.ENTRY_SOURCE]
        payouts = _payout_rows(conn, eid)
        skip = db.hcp_skip_events(conn)
        read = _read if _read is not None else se.get_entered_scores(eid, db_path=db_path)
        rounds = [r for r in (read.get("rounds") or []) if not ep._is_preview(r)]
        mode, why = ep._mode(conn, ev, db_path) if rounds else ("gg", "no entered rounds")
        era = "entry" if (rounds and mode == "authoritative") else "gg"
        out = {"event": {"id": eid, "name": ev["item_name"], "date": str(ev.get("event_date") or "")[:10]},
               "era": era, "era_why": why}

        if era == "gg":
            roster = db._event_roster_rows(conn, eid)
            field_ids = {int(r["customer_id"]) for r in roster if r.get("customer_id")}
            field_unid = sorted({(r.get("name") or r.get("customer") or "").strip()
                                 for r in roster if not r.get("customer_id")} - {""})
            card_ids = [c["customer_id"] for c in gg_cards if c["customer_id"]]
            null_cards = [c["player_name"] for c in gg_cards if not c["customer_id"]]
            dup = sorted({c for c in card_ids if card_ids.count(c) > 1})
            names = _names(conn, list(field_ids) + card_ids)
            missing = sorted(names[c] for c in field_ids - set(card_ids))
            extra = sorted(names[c] for c in set(card_ids) - field_ids)
            boards = db.get_gg_game_results(ev["item_name"], db_path=db_path).get("results") or []
            # A game is unpaid only when NONE of its rows carries a purse
            # (money not entered on GG yet). A "_board" game is GG's full
            # standings (non-paying places at $0 by design) and never counts;
            # s9.24's Team Net board read as a false block before this.
            by_game: dict = {}
            for b in boards:
                if str(b.get("game") or "").endswith("_board"):
                    continue
                by_game.setdefault(f"{b['game']} {b.get('game_label') or ''}".strip(), []).append(b)
            zero = sorted(g for g, rows in by_game.items() if not any(r.get("purse") for r in rows))
            out["checks"] = {"field": len(field_ids) + len(field_unid), "cards": len(gg_cards),
                             "gg_board_rows": len(boards), "payout_rows": len(payouts)}
            if not gg_cards:
                blocking.append("no scorecards imported yet")
            if missing:
                blocking.append(f"no card for {len(missing)} registered player(s): {', '.join(missing)}")
            if field_unid:
                blocking.append(f"registered with no customer record: {', '.join(field_unid)}")
            if null_cards:
                blocking.append(f"card(s) with no customer_id (identity check, skill 1.1): {', '.join(sorted(null_cards))}")
            if dup:
                blocking.append(f"duplicate cards for {', '.join(names[c] for c in dup)} (run scoring-dedupe-rounds)")
            if extra:
                warnings.append(f"card(s) for players not on the roster: {', '.join(extra)}")
            if not boards:
                blocking.append("no Golf Genius results boards posted yet")
            elif zero:
                blocking.append(f"Golf Genius board(s) with no purse entered: {', '.join(zero)}")
            if not payouts:
                blocking.append("no payouts recorded for the event")
        else:
            held, eligible = [], []
            for rnd in rounds:
                for p in rnd.get("players") or []:
                    if not any(v is not None for v in (p.get("scores") or {}).values()):
                        continue  # a no-show seeded from PAIRINGS; nothing to finish
                    ok, reason = ep.publish_eligibility(rnd, p)
                    (eligible if ok else held).append((p, reason))
                for h in rnd.get("hio") or []:
                    if (h.get("status") or "") not in ("verified", "rejected", "withdrawn"):
                        blocking.append(f"hole-in-one claim on hole {h.get('hole')} is still {h.get('status')} (verify it)")
                unanswered = sorted(int(k) for k, v in (rnd.get("ctp") or {}).items() if v is None)
                if unanswered:
                    warnings.append(f"round {rnd['round_id']}: no CTP holder on par 3(s) {unanswered} "
                                    "(fine if nobody hit the green)")
            names = _names(conn, [p["customer_id"] for p, _ in held + eligible])
            published = {c["customer_id"] for c in entry_cards}
            unpublished = sorted(names[p["customer_id"]] for p, _ in eligible
                                 if p["customer_id"] not in published)
            out["checks"] = {"entered_players": len(held) + len(eligible), "signed_complete": len(eligible),
                             "published_cards": len(entry_cards), "payout_rows": len(payouts)}
            for p, reason in held:
                blocking.append(f"{names[p['customer_id']]}: {reason}")
            if unpublished:
                blocking.append(f"signed but not published into scorecards: {', '.join(unpublished)} "
                                f"(run scoring-entry-publish:{eid}|apply)")
            if not payouts:
                blocking.append("no payouts computed for the event")
        # A card with no tee has no rating/slope/par/stroke index: the handicap
        # post skips it and engine payouts refuse the event (v2.513.7). Found
        # on the 9/28 rehearsal copy, where all 33 entered cards were tee-less
        # and this check still said "final". Both eras, by name.
        own = entry_cards if era == "entry" else gg_cards
        teeless = sorted(c["player_name"] or f"customer {c['customer_id']}" for c in own if not c.get("tee_id"))
        if teeless:
            blocking.append(f"{len(teeless)} card(s) with no tee (handicaps can't post, engine payouts refuse): "
                            f"{', '.join(teeless)}")
        if eid in skip:
            warnings.append(f"no handicap post or card for this event: {skip[eid]}")
        out.update({"final": not blocking, "blocking": blocking, "warnings": warnings})
        return out
