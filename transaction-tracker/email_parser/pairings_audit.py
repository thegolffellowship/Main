"""PAIRINGS AUDIT, read-only (Kerry 2026-10-06 via Front Desk: "you
mentioned some things you couldn't see. Create tools for you to see them").

One read of an event's SAVED pairing sheet with everything a reviewer needs
to check it against the Pairings Engine Spec v1.2 ladder (CoS #1036) and the
Pairing Standards: per-player flags, per-group and per-cart rule results,
a repeat-depth table with the lower-count alternatives, blinds, sheet
provenance, and the generator's own alternative with its score. It writes
nothing and never changes a saved sheet.

Kerry's rulings encoded here, verbatim:
- "I don't play with X twice (unless other pairings rules dictate) until
  I've played with all others once."
- "Repeats should be in sequence whenever possible." So a repeat pair is a
  violation while either player has a lower-count partner in the field.
- "Pairings Requests definitely dictate in most cases so Bourquin and
  Saldana would ride together." and "2nd requests go to opposite carts but
  that's not true when it comes to Pairings Requests. It's only true with
  repeat pairings (that don't have requests)." So a REQUESTED partner rides
  in the SAME cart; the opposite-cart rule (R-G) applies only to repeat,
  non-request pairs.

Rules whose exact Spec v1.2 wording this lane does not hold (R-B, R-C, R-E)
are evaluated as read by the Front Desk on 10/6 (#1249) and marked
`reading` so the CoS can confirm them against the spec text.
"""
from __future__ import annotations

BACK_BAND = "<50"


def _band(tee) -> str:
    return str(tee or "").strip()


def _carts(players: list) -> list[list]:
    """Seat order 1&2 / 3&4 (a fifth rides with 3&4)."""
    ps = sorted(players, key=lambda p: p.get("cart_pos") or 0)
    return [c for c in (ps[0:2], ps[2:]) if c]


def event_pairing_audit(event_id: int, db_path=None) -> dict:
    from email_parser import database as db
    from email_parser.ambassadors import chapter_ambassadors
    from email_parser.cos_reads import pairing_history_view
    event_id = int(event_id)
    K = db._pair_key_name
    with db._connect(db_path) as conn:
        ev = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not ev:
            return {"error": f"no event {event_id}"}
        ev = dict(ev)
        ev_date = str(ev.get("event_date") or "")[:10]
        roster = db._event_roster_rows(conn, event_id)
        by_cid, by_key = {}, {}
        for r in roster:
            if r.get("customer_id"):
                by_cid.setdefault(int(r["customer_id"]), r)
            by_key.setdefault(K(r.get("customer") or ""), r)
        rode = db._rode_counts_from_conn(conn, event_id)
        hcp = db._roster_handicap_index_map(conn, as_of=db._event_index_as_of(ev), db_path=db_path)
        all_names = [r.get("customer") for r in roster if r.get("customer")]
        host_of = db._host_of_map(roster, all_names,
                                  roster_ids={r["customer"]: r["customer_id"] for r in roster
                                              if r.get("customer_id") and r.get("customer")})
        prov = conn.execute(
            "SELECT MIN(created_at) AS first, MAX(created_at) AS last, COUNT(*) AS n "
            "FROM event_pairings WHERE event_id = ?", (event_id,)).fetchone()
        log_rows = []
        try:
            log_rows = [dict(r) for r in conn.execute(
                """SELECT created_at, agent_name, action_type, description FROM agent_action_log
                   WHERE (instr(lower(action_type), 'pairing') > 0 OR instr(lower(description), 'pairing') > 0)
                     AND instr(description, ?) > 0
                   ORDER BY id DESC LIMIT 10""", (str(event_id),))]
        except Exception:
            pass
        blinds = []
        try:
            blinds = [dict(r) for r in conn.execute(
                "SELECT * FROM blind_draws WHERE event_id = ? ORDER BY group_num, cart_pos", (event_id,))]
        except Exception:
            pass
        here_ambs = chapter_ambassadors(conn, ev["chapter_id"]) if ev.get("chapter_id") else set()
        cids = sorted(by_cid)
        cust, played, amb_rows, gates = {}, {}, {}, {}
        if cids:
            ph = ",".join("?" * len(cids))
            for r in conn.execute(
                    f"""SELECT customer_id, gender, starting_handicap_18, ambassador, group_captain,
                               solo_back_ok, current_player_status
                        FROM customers WHERE customer_id IN ({ph})""", cids):
                cust[int(r["customer_id"])] = dict(r)
            # rounds played before tonight, every chapter ("regardless of location")
            for r in conn.execute(
                    f"""SELECT customer_id, COUNT(DISTINCT substr(round_date, 1, 10)) AS n
                        FROM scoring_rounds WHERE customer_id IN ({ph})
                          AND substr(COALESCE(round_date, ''), 1, 10) < ?
                        GROUP BY customer_id""", (*cids, ev_date)):
                played[int(r["customer_id"])] = int(r["n"])
            from email_parser.ambassadors import ambassador_rows
            amb_rows.update(ambassador_rows(conn, cids))
            for c in cids:
                try:
                    gates[c] = db.customer_blind_gate(conn, c, db_path=db_path)
                except Exception as e:  # noqa: BLE001
                    gates[c] = f"unread: {e}"
    year = int(ev_date[:4]) if ev_date[:4].isdigit() else None
    counts = db.get_pairing_history_counts(year=year, db_path=db_path, exclude_event_id=event_id)
    sheet = db.get_event_pairings(event_id, db_path=db_path, roster_rows=roster, hcp_map=hcp)
    requests = db.get_event_partner_requests(event_id, db_path=db_path,
                                             roster_rows=roster).get("requests", [])
    try:
        mp = db.detect_match_play_pairings(event_id, db_path=db_path, roster_rows=roster)
    except Exception as e:  # noqa: BLE001 — rule 8 read must not sink the audit
        mp = {"error": str(e)}
    try:
        unit = db._event_blind_unit(sheet, db_path=db_path) if sheet else None
    except Exception:  # noqa: BLE001
        unit = None
    game = {"cart": "Cart Net", "group": "Team Net"}.get(unit, unit)

    def prior(a, b):
        ka, kb = K(a), K(b)
        return int(counts.get((min(ka, kb), max(ka, kb)), 0))

    def rode_n(a, b):
        ka, kb = K(a), K(b)
        return int(rode.get((min(ka, kb), max(ka, kb)), 0))

    # solo-cart history per player (R-C), played rounds before tonight, newest first
    solo_hist = {}
    for cid in cids:
        try:
            v = pairing_history_view(customer_id=cid, db_path=db_path)
            rec = [e for e in (v.get("cart_record") or []) if str(e.get("date") or "") < ev_date]
            rec.sort(key=lambda e: str(e.get("date") or ""), reverse=True)
            streak = 0
            for e in rec:
                if not e.get("solo_cart"):
                    break
                streak += 1
            solo_hist[cid] = {"rounds_on_record": len(rec),
                              "solo_carts": sum(1 for e in rec if e.get("solo_cart")),
                              "solo_streak_before_tonight": streak,
                              "last_solo": next((e.get("date") for e in rec if e.get("solo_cart")), None)}
        except Exception as e:  # noqa: BLE001
            solo_hist[cid] = {"error": str(e)}

    # requests: requester -> resolved partner (suppressed and unmatched skipped)
    req_pairs = [(rq["requester"], rq["partner"]) for rq in requests
                 if rq.get("requester") and rq.get("partner") and not rq.get("suppressed")]
    req_keys = {frozenset((K(a), K(b))) for a, b in req_pairs}
    host_name = {K(n): n for n in all_names}

    field_names = []
    for grps in sheet.values():
        for g in grps:
            field_names += [p["name"] for p in g.get("players", []) if p.get("name")]

    players_out, groups_out, flags = [], [], []

    def pflags(p):
        cid = int(p["customer_id"]) if p.get("customer_id") else None
        r = (by_cid.get(cid) if cid else None) or by_key.get(K(p["name"])) or {}
        c = cust.get(cid) or {}
        idx = hcp.get(("c", cid)) if cid and ("c", cid) in hcp else hcp.get(K(p["name"]))
        start = c.get("starting_handicap_18")
        n_played = played.get(cid, 0) if cid else None
        return {
            "name": p["name"], "customer_id": cid, "cart_pos": p.get("cart_pos"),
            "tee": _band(p.get("tee_choice") or r.get("tee_choice")),
            "gender": c.get("gender"),
            "ambassador": bool(cid in here_ambs) if here_ambs else bool(c.get("ambassador")),
            "ambassador_chip": bool(c.get("ambassador")),
            "ambassador_chapters": amb_rows.get(cid, []),
            "group_captain": bool(c.get("group_captain") or r.get("group_captain")),
            "solo_back_ok": bool(c.get("solo_back_ok") or r.get("solo_back_ok")),
            "is_new": bool(r.get("is_new")), "is_first_timer": bool(r.get("is_first_timer")),
            "events_played_before": n_played,
            "first_three": (n_played is not None and n_played < 3),
            "status": c.get("current_player_status") or r.get("user_status"),
            "index": idx,
            "index_source": ("posted" if idx is not None else
                             "starting/intro" if start is not None else "none"),
            "starting_handicap_18": start,
            "blind_gate": (gates.get(cid) or "eligible") if cid else "no customer_id",
            "partner_request": r.get("partner_request"),
            "invited_by": host_name.get(host_of.get(K(p["name"]))),
            "rsvp_only": bool(r.get("rsvp_only")),
            "solo_history": solo_hist.get(cid) if cid else None,
        }

    for holes in sorted(sheet, key=str):
        for g in sorted(sheet[holes], key=lambda x: x.get("group_num") or 0):
            ps = [pflags(p) for p in sorted(g.get("players", []), key=lambda x: x.get("cart_pos") or 0)]
            players_out += ps
            names = [p["name"] for p in ps]
            carts = _carts(ps)
            res = []

            def hit(rule, kind, ok, detail):
                res.append({"rule": rule, "kind": kind, "ok": ok, "detail": detail})
                if not ok:
                    flags.append({"group": g.get("slot_label"), "rule": rule, "kind": kind, "detail": detail})

            # rule 5 + Kerry 10/6: requested partners in the SAME group and SAME cart
            seen_req = set()
            for a, b in req_pairs:
                if a in names and frozenset((K(a), K(b))) not in seen_req:
                    seen_req.add(frozenset((K(a), K(b))))
                    same_g = a in names and b in names
                    same_c = any(a in [x["name"] for x in c] and b in [x["name"] for x in c] for c in carts)
                    hit("rule 5 request", "hard", same_g and same_c,
                        f"{a} + {b}: " + ("same cart" if same_c else "same group, different carts" if same_g else "not in the same group"))
            # rule 4: guest rides with inviter (same cart)
            for p in ps:
                inv = p.get("invited_by")
                if inv and K(inv) in {K(n) for n in field_names}:
                    n_guests = sum(1 for h in host_of.values() if h == K(inv))
                    same_g = K(inv) in {K(n) for n in names}
                    same_c = any(p["name"] in [x["name"] for x in c] and K(inv) in [K(x["name"]) for x in c] for c in carts)
                    # one cart holds the host and ONE guest; with more guests the group is the test
                    ok = same_c if n_guests == 1 else same_g
                    hit("rule 4 guest/inviter", "hard", ok,
                        f"{p['name']} invited by {inv}: " + ("same cart" if same_c else "same group" if same_g else "not in the same group")
                        + (f" ({n_guests} guests)" if n_guests > 1 else ""))
            # R-A: a 1st Timer's group has an Ambassador
            ambs = [p for p in ps if p["ambassador"]]
            for p in ps:
                if p["is_first_timer"]:
                    hit("R-A 1st Timer + Ambassador", "hard", bool(ambs),
                        f"{p['name']}: " + (", ".join(a["name"] for a in ambs) or "no Ambassador in the group"))
                    # R-F soft: same-gender Ambassador
                    if p.get("gender"):
                        same = [a for a in ambs if a.get("gender") == p["gender"]]
                        hit("R-F same-gender Ambassador", "soft", bool(same),
                            f"{p['name']} ({p['gender']}): " + (", ".join(a["name"] for a in same) or "none"))
            # R-D (back tees only): a lone <50 player in a group. Same test as
            # the generator (rule 12, `_lone_back_offender`): a player on the
            # solo_back_ok list is exempt (Kerry 2026-10-06, Mazanec).
            backs = [p for p in ps if p["tee"] == BACK_BAND]
            if len(backs) == 1 and len(ps) > 1:
                b = backs[0]
                hit("R-D lone back-tee", "hard", bool(b["solo_back_ok"]),
                    f"{b['name']} is the only {BACK_BAND} in the group" +
                    (" (solo_back_ok: allowed)" if b["solo_back_ok"] else ""))
            # R-C: solo cart tonight
            for c in carts:
                if len(c) == 1 and len(ps) > 1:
                    p = c[0]
                    sh = p.get("solo_history") or {}
                    streak = sh.get("solo_streak_before_tonight") or 0
                    # Hard from the 3rd solo cart in a row, the generator's rule
                    # (Kerry 2026-10-06); a first-three player alone is soft.
                    hard = streak >= 2
                    hit("R-C solo cart (reading)", "hard" if hard else "soft", not hard and not sh.get("solo_carts"),
                        f"{p['name']} rides alone; prior solo carts on record {sh.get('solo_carts')}, "
                        f"{streak} in a row before tonight" + ("; in first three events" if p.get("first_three") else ""))
            # R-E soft: cart partners on the same tee band
            for c in carts:
                if len(c) == 2 and c[0]["tee"] and c[1]["tee"] and c[0]["tee"] != c[1]["tee"]:
                    hit("R-E cart tee band (reading)", "soft", False,
                        f"{c[0]['name']} {c[0]['tee']} / {c[1]['name']} {c[1]['tee']}")
            # R-B soft (reading): a player in his first three events has an established member in the group
            for p in ps:
                if p.get("first_three"):
                    est = [q["name"] for q in ps if q is not p and not q.get("first_three")]
                    hit("R-B first three events (reading)", "soft", bool(est),
                        f"{p['name']} ({p.get('events_played_before')} prior): with {', '.join(est) or 'no established member'}")
            # R-G: repeat cart partners split, unless they requested each other
            for c in carts:
                if len(c) == 2:
                    a, b = c[0]["name"], c[1]["name"]
                    if rode_n(a, b) and frozenset((K(a), K(b))) not in req_keys:
                        hit("R-G cart variety", "soft", False, f"{a} + {b} have shared a cart {rode_n(a, b)}x before")
            pairs = []
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    pairs.append({"a": names[i], "b": names[j], "prior": prior(names[i], names[j]),
                                  "rode_prior": rode_n(names[i], names[j]),
                                  "requested": frozenset((K(names[i]), K(names[j]))) in req_keys})
            groups_out.append({"holes": str(holes), "group_num": g.get("group_num"),
                               "slot_label": g.get("slot_label"),
                               "carts": [[x["name"] for x in c] for c in carts],
                               "players": names, "pairs": pairs,
                               "pair_score": sum(p["prior"] for p in pairs),
                               "rules": res})

    # repeat depth: every repeat pair, and the lowest-count partners each player had available
    repeats = []
    for g in groups_out:
        for p in g["pairs"]:
            if p["prior"] < 1 or p["requested"]:
                continue
            alts = {}
            for who in (p["a"], p["b"]):
                cand = sorted(((prior(who, o), o) for o in field_names if o != who), key=lambda t: t[0])
                lo = cand[0][0] if cand else 0
                alts[who] = {"lowest_available": lo,
                             "partners_at_lowest": [o for n, o in cand if n == lo][:8]}
            viol = any(a["lowest_available"] < p["prior"] for a in alts.values())
            # a 3rd meeting while either has never played someone here, etc.
            skips = any(a["lowest_available"] + 2 <= p["prior"] for a in alts.values())
            repeats.append({"group": g["slot_label"], "a": p["a"], "b": p["b"],
                            "season_count": p["prior"], "tonight_makes": p["prior"] + 1,
                            "out_of_sequence": viol, "skips_a_level": skips, "alternatives": alts})
            if viol:
                flags.append({"group": g["slot_label"], "rule": "new pairings / repeats in sequence",
                              "kind": "soft", "detail": f"{p['a']} + {p['b']} at {p['prior']} while lower-count partners exist"})
    repeats.sort(key=lambda r: -r["season_count"])

    # the generator's alternative (read-only: generate_event_pairings never saves)
    alt = {}
    try:
        gen = db.generate_event_pairings(event_id, db_path=db_path)
        for holes in ("9", "18"):
            if holes not in gen:
                continue
            gg = []
            for g in gen[holes]:
                ns = [p["name"] for p in g.get("players", []) if p.get("name")]
                sc = sum(prior(ns[i], ns[j]) for i in range(len(ns)) for j in range(i + 1, len(ns)))
                gg.append({"slot_label": g.get("slot_label"), "players": ns, "pair_score": sc})
            alt[holes] = {"groups": gg, "total_pair_score": sum(x["pair_score"] for x in gg)}
    except Exception as e:
        alt = {"error": str(e)}

    blinds_out = []
    for b in blinds:
        cid = b.get("customer_id")
        home = next((g["slot_label"] for g in groups_out if b.get("player_name") in g["players"]), None)
        blinds_out.append({"holes": b.get("holes"), "group_num": b.get("group_num"),
                           "slot_label": b.get("slot_label"), "cart_pos": b.get("cart_pos"),
                           "player": b.get("player_name"), "customer_id": cid,
                           "reason": b.get("reason"), "source": b.get("source"),
                           "plays_in_group": home,
                           "from_other_group": bool(home and home != b.get("slot_label")),
                           "blind_gate": ((gates.get(int(cid)) or "eligible") if cid and int(cid) in gates
                                          else None)})
    sheet_score = sum(g["pair_score"] for g in groups_out)
    return {
        "event_id": event_id, "event": ev.get("item_name"), "event_date": ev_date,
        "chapter": ev.get("chapter"), "format": ev.get("format"),
        "net_game": game,
        "blind_rule": ("Cart Net: a blind fills a CART, drawn from the other cart of the same group (rule 15h)"
                       if unit == "cart" else
                       "Team Net: the whole group is the team, so a blind comes from another group"
                       if unit == "group" else None),
        "rulings": [
            "I don't play with X twice (unless other pairings rules dictate) until I've played with all others once.",
            "Repeats should be in sequence whenever possible.",
            "Pairings Requests definitely dictate in most cases so Bourquin and Saldana would ride together.",
            "2nd requests go to opposite carts but that's not true when it comes to Pairings Requests. "
            "It's only true with repeat pairings (that don't have requests).",
        ],
        "provenance": {"rows": prov["n"], "first_saved": prov["first"], "last_saved": prov["last"],
                       "log": log_rows,
                       "note": "event_pairings does not record generator-vs-manual; the log rows are the trail"},
        "players": players_out,
        "groups": groups_out,
        "requests": requests,
        "match_play": mp,
        "blinds": blinds_out,
        "repeats": repeats,
        "flags": flags,
        "summary": {"groups": len(groups_out), "players": len(players_out),
                    "sheet_pair_score": sheet_score,
                    "generator_pair_score": {h: v.get("total_pair_score") for h, v in alt.items()} if "error" not in alt else alt,
                    "hard_flags": sum(1 for f in flags if f["kind"] == "hard"),
                    "soft_flags": sum(1 for f in flags if f["kind"] == "soft"),
                    "repeat_pairs": len(repeats),
                    "out_of_sequence": sum(1 for r in repeats if r["out_of_sequence"]),
                    "skips_a_level": sum(1 for r in repeats if r["skips_a_level"]),
                    "deepest_repeat": max((r["season_count"] for r in repeats), default=0)},
        "generator_alternative": alt,
        "reading_note": ("R-B, R-C and R-E are evaluated as read by the Front Desk (#1249); the exact Spec v1.2 "
                         "wording is not in this lane. Rule 4 reads the guest's 'Purchased by' order note."),
    }
