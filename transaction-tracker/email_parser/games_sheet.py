"""GAMES & PAYOUTS sheet (CD #967, Kerry-approved 2026-09-29).

One Letter page for the players: what each game pays, the write-in lines
for the winners, the Stableford values the MVP is scored on and the
Hole-in-One pot. EVERY FIGURE IS THE GAMES TAB'S (the #897 rule): the
pots, places, flights, entrant counts, MWP and totals come from the Events
page's own `renderGamesPanel` run headless (`page_probe.event_games_tab`,
the same reader as the `get_event_games` tool), so the sheet and the tab
cannot disagree. Nothing here recomputes a pot. The only other sources
are the ones the tab itself leans on:

- CTP hole numbers: the Proximity report (`event_proximity_report`), which
  picks the course's shortest par-3s per the ratified CTP rule;
- the Stableford values: `get_scoring_formulas()` (championship table on
  championship events);
- the Hole-in-One pot and today's adds: the HIO ledger (`get_hio_pot`);
- the Individual Gross minimum: the live matrix (first entrant count with
  a funded Individual Gross).

The rule text lives in `GAME_RULES` below, in Kerry's words (9/29): one
place, never typed into the template.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Kerry 2026-09-29, verbatim where quoted: "Add 'Winners split pot' on the
# other games"; "Ties on Event MVP should say Tiebreakers:".
GAME_RULES = {
    "team": ("{unit} vs the field. Best net score per hole. {pct}% handicaps"
             "{off_low}{par3}. Ties: winners split pot."),
    "ctp": "Ball must be on the green. Ties: winners split pot.",
    "ind_net": ("{flights}. Check the Divisions/Flights report to confirm "
                "yours. Ties: winners split pot."),
    "skins": "{flights}. Straight gross, flighted at 8+ players. Winners split pot by skins won.",
    "skins_half": ("Under 8 gross entrants, skins play ½ net: half your "
                   "strokes. Winners split pot by skins won."),
    "ind_gross": "{flights}. Straight gross, no handicaps. Ties: winners split pot.",
    "ind_gross_off": "Needs {min} gross entrants on {holes}-hole events.",
    "mvp": ("Most net Stableford points. Tiebreakers: 1st = Total Net | "
            "2nd = Total Gross | 3rd = Split winnings."),
    "tgf_mvp": ("Shared with {others}: {parts}. Best Event MVP across TGF "
                "wins; ties split."),
}

_CHAPTER_SHORT = {"san antonio": "SA", "austin": "Austin"}


def _money(s) -> float | None:
    if s is None:
        return None
    m = re.search(r"-?\$?\s*([\d,]+(?:\.\d+)?)", str(s))
    if not m or "—" == str(s).strip():
        return None
    return float(m.group(1).replace(",", ""))


def fmt_money(v, cents: str = "auto") -> str:
    if v is None:
        return "—"
    v = round(float(v) + 0.0, 2)
    if cents == "auto" and abs(v - round(v)) < 0.005:
        return f"${round(v):,}"
    return f"${v:,.2f}"


def _chap(ch) -> str:
    return _CHAPTER_SHORT.get((ch or "").strip().lower(), (ch or "").strip() or "?")


def _plural_flights(n: int) -> str:
    return "1 flight" if n == 1 else f"{n} flights"


def parse_games_tab(g: dict) -> dict:
    """The tab's rendered rows -> numbers. Raises ValueError when the tab
    has no regular games (a bucket event, or no matrix row)."""
    if g.get("buckets"):
        raise ValueError("bucket-account event: the regular games matrix does not apply")
    if g.get("empty"):
        raise ValueError(g["empty"])
    out = {"team": None, "ctps": [], "included_total": None,
           "ind_net": None, "mvp": None, "tgf_mvp": None, "net_total": None,
           "skins": None, "ind_gross": None, "gross_total": None,
           "total": _money((g.get("total") or {}).get("pot")),
           "mwp": _money((g.get("total") or {}).get("mwp")),
           "notes": []}
    for sec in g.get("sections") or []:
        name = (sec.get("section") or "").upper()
        rows = sec.get("rows") or []
        sub = _money((sec.get("subtotal") or {}).get("pot"))
        if name.startswith("INCLUDED"):
            out["included_total"] = sub
            for r in rows:
                game = (r.get("game") or "").strip()
                if r.get("disabled"):
                    continue
                if re.match(r"^(team|cart) net", game, re.I):
                    places = [v for v in (_money(r.get("1st")), _money(r.get("2nd"))) if v]
                    out["team"] = {"label": game, "pot": _money(r.get("pot")), "places": places,
                                   "cart": game.lower().startswith("cart")}
                elif game.upper().startswith("CTP"):
                    out["ctps"].append(_money(r.get("pot")))
        elif name.startswith("NET"):
            out["net_total"] = sub
            cur = None
            for r in rows:
                game = (r.get("game") or "").strip()
                if r.get("disabled"):
                    continue
                if game.startswith("Individual Net"):
                    out["ind_net"] = {"pot": _money(r.get("pot")),
                                      "flights": int(r.get("flights") or 1), "flight_rows": []}
                    cur = "ind_net"
                elif r.get("sub") and cur == "ind_net" and game.endswith("Flight"):
                    out["ind_net"]["flight_rows"].append(
                        {"name": game, "places": [v for v in (_money(r.get(k)) for k in
                                                               ("1st", "2nd", "3rd", "4th")) if v]})
                elif game.startswith("City MVP"):
                    out["mvp"] = {"pot": _money(r.get("pot"))}
                    cur = None
                elif game.startswith("TGF MVP"):
                    out["tgf_mvp"] = {"pot": _money(r.get("pot")), "lines": []}
                    cur = "tgf"
                elif r.get("sub") and cur == "tgf" and _money(r.get("pot")) is not None:
                    out["tgf_mvp"]["lines"].append({"course": game.replace("✖", "").strip(),
                                                    "pot": _money(r.get("pot"))})
        elif name.startswith("GROSS"):
            out["gross_total"] = sub
            for r in rows:
                game = (r.get("game") or "").strip()
                if game.startswith("Skins"):
                    if r.get("disabled"):
                        continue
                    out["skins"] = {"label": game, "pot": _money(r.get("pot")),
                                    "flights": int(r.get("flights") or 1),
                                    "half_net": "1/2" in game}
                elif game.startswith("Ind. Gross"):
                    if r.get("disabled"):
                        out["ind_gross"] = {"off": True}
                    else:
                        det = r.get("1st") or ""
                        places = [_money(x) for x in re.findall(r"\$[\d,.]+", det)]
                        out["ind_gross"] = {"off": False, "pot": _money(r.get("pot")),
                                            "flights": int(r.get("flights") or 1),
                                            "places": [p for p in places if p]}
    return out


def _ind_gross_minimum(holes: int, db_path=None) -> int | None:
    from email_parser import database as db
    m9, m18 = db._load_games_matrix(db_path)
    m = m9 if holes == 9 else m18
    ns = sorted(int(k) for k, row in m.items()
                if str(k).isdigit() and db._matrix_num((row or {}).get("individualGross")) > 0)
    return ns[0] if ns else None


def _stableford(ev: dict, db_path=None) -> dict:
    from email_parser import database as db
    f = db.get_scoring_formulas(db_path)
    champ = "CHAMPIONSHIP" in (ev.get("item_name") or "").upper()
    if champ:
        f = db.get_championship_formulas(f, db_path=db_path)
    t = {str(k): v for k, v in (f.get("stableford_net_table") or {}).items()}
    rows = [("Double eagle or better", t.get("-3")), ("Eagle", t.get("-2")),
            ("Birdie", t.get("-1")), ("Par", t.get("0")), ("Bogey", t.get("1")),
            ("Double bogey or worse", t.get("2"))]
    return {"rows": [{"label": a, "pts": b} for a, b in rows if b is not None],
            "hio": f.get("stableford_net_hio"), "championship": champ}


def _hio_band(ev: dict, db_path=None) -> dict | None:
    from email_parser import database as db
    try:
        d = db.get_hio_pot(db_path=db_path) if db_path else db.get_hio_pot()
    except Exception:
        logger.exception("games sheet: HIO pot unavailable")
        return None
    day = (ev.get("event_date") or "")[:10]
    rows = [r for r in (d.get("events") or []) if str(r.get("date") or "")[:10] == day
            and r.get("running") is not None]
    if not rows:
        return {"pot": d.get("pot"), "today": None, "parts": []}
    names = [r["event"] for r in rows]
    chap = {}
    with db._connect(db_path) as conn:
        for n in names:
            c = conn.execute("SELECT chapter FROM events WHERE item_name = ?", (n,)).fetchone()
            ch = c[0] if c else None
            if not ch:   # the event code says it: s9.25 -> San Antonio, a9.25 -> Austin
                ch = {"s": "San Antonio", "a": "Austin"}.get((n or " ")[0].lower())
            chap[n] = _chap(ch)
    return {"pot": max(float(r["running"]) for r in rows),
            "today": sum(float(r.get("hio") or 0) for r in rows),
            "parts": [{"chapter": chap[r["event"]], "amount": float(r.get("hio") or 0)}
                      for r in rows]}


def _team_rule(ev_id: int, cart: bool, db_path=None) -> str:
    """The Team/Cart Net line the scorecards' legend prints, from the same
    engine dial (allowance %, off the field's low, par-3 rule)."""
    from email_parser import database as db
    pct, off_low, par3 = None, False, False
    try:
        from email_parser.scorecards import _team_no_par3_pops
        pack = db.get_event_print_pack(int(ev_id), db_path=db_path) or {}
        pct = round((pack.get("team_allowance") or 0) * 100)
        off_low = bool((pack.get("team_off_lowest") or {}).get("applied"))
        par3 = bool(_team_no_par3_pops())
    except Exception:
        logger.exception("games sheet: team dial unavailable for %s", ev_id)
    return GAME_RULES["team"].format(
        unit="Your cart" if cart else "Your foursome",
        pct=pct if pct is not None else "—",
        off_low=" off the field's low" if off_low else "",
        par3=f"; no {'Cart' if cart else 'Team'} Net strokes on par 3s" if par3 else "")


def build_games_sheet(event_id: int, games: dict | None = None, db_path=None) -> dict | None:
    """Everything the template prints. `games` is the probe's output (the
    GAMES tab); omitted, the probe runs. None for an unknown event; a dict
    with "error" when the tab has no regular games to print."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    if not r:
        return None
    ev = dict(r)
    if games is None:
        from email_parser.page_probe import event_games_tab
        games = event_games_tab(int(event_id))
    if games.get("error"):
        return {"error": games["error"], "event": ev}
    try:
        t = parse_games_tab(games)
    except ValueError as exc:
        return {"error": str(exc), "event": ev}
    holes = int(games.get("holes") or 9)
    counts = games.get("counts") or {}
    warnings: list[str] = []

    prox = db.event_proximity_report(int(event_id), db_path=db_path) or {}
    pack = db.get_event_print_pack(int(event_id), db_path=db_path) or {}
    pev = pack.get("event") or {}
    start_type = (ev.get("start_type") or "").strip().lower()
    nine = "18 Holes" if holes == 18 else f"{(prox.get('nine') or ev.get('nine_side') or 'Front').title()} 9"
    from email_parser.scorecards import _fmt_date
    header = {
        "chapter": (ev.get("chapter") or "").upper(),
        "course": prox.get("course_name") or ev.get("course") or "",
        "meta": " · ".join(x for x in (_fmt_date(ev.get("event_date")),
                                        (ev.get("item_name") or "").split(" ")[0], nine) if x),
        "start_type": "SHOTGUN" if start_type.startswith("shotgun") else "TEE TIMES",
        "start_time": pev.get("start_clock") or ev.get("start_time") or "",
        "file_stub": pev.get("file_stub") or db.print_file_stub(ev),
    }

    # ── INCLUDED ──
    included = []
    team = t["team"]
    if team:
        size = 2 if team["cart"] else 4
        lines = [{"label": ("1st", "2nd")[i], "amount": f"{fmt_money(p / size)}/plyr"}
                 for i, p in enumerate(team["places"])]
        included.append({"name": f"{'Cart' if team['cart'] else 'Team'} Net · Best Ball",
                         "pot": fmt_money(team["pot"]),
                         "rule": _team_rule(event_id, team["cart"], db_path), "lines": lines})
    ctp_total = sum(v or 0 for v in t["ctps"])
    if t["ctps"]:
        contests = prox.get("contests") or []
        lines = []
        for i, v in enumerate(t["ctps"]):
            c = contests[i] if i < len(contests) else None
            if c and c.get("kind") == "ctp":
                label = f"Hole {c['hole']}"
            elif c and c.get("kind") == "longest_putt":
                label = f"Putt · {c['hole']}"
            else:
                label = "Hole ___"
                warnings.append(f"CTP #{i + 1}: no hole from the course card (Proximity report); "
                                "the line prints a blank hole number.")
            lines.append({"label": label, "amount": fmt_money(v)})
        included.append({"name": "Proxies · Closest to Pin", "pot": fmt_money(ctp_total),
                         "rule": GAME_RULES["ctp"], "lines": lines, "two_up": len(lines) >= 3})

    # ── NET ──
    net_games = []
    link = games.get("mvp_link")
    net_count = int(counts.get("net") or 0)
    gross_count = int(counts.get("gross") or 0)
    linked_extra = 0.0
    if t["tgf_mvp"] and link:
        linked_extra = float(link.get("combined_pot") or 0) - float(link.get("this_event_tgf_mvp") or 0)
    if t["ind_net"]:
        n = t["ind_net"]
        lines = []
        for fi, fr in enumerate(n["flight_rows"]):
            for pi, amt in enumerate(fr["places"]):
                lines.append({"label": f"F{fi + 1} · {('1st', '2nd', '3rd', '4th')[pi]}",
                              "amount": fmt_money(amt), "new_flight": fi > 0 and pi == 0})
        net_games.append({"name": "Individual Net", "pot": fmt_money(n["pot"]),
                          "rule": GAME_RULES["ind_net"].format(flights=_plural_flights(n["flights"])),
                          "lines": lines})
    if t["mvp"]:
        net_games.append({"name": "Event MVP", "pot": fmt_money(t["mvp"]["pot"]),
                          "rule": GAME_RULES["mvp"],
                          "lines": [{"label": "MVP", "amount": fmt_money(t["mvp"]["pot"])}]})
    if t["tgf_mvp"]:
        tm = t["tgf_mvp"]
        if link and link.get("linked"):
            others = ", ".join(f"{_chap(l.get('chapter'))} ({(l.get('event_name') or '').strip()})"
                               for l in link["linked"])
            parts = " + ".join([f"{_chap(link.get('this_chapter'))} "
                                f"{fmt_money(link.get('this_event_tgf_mvp'))}"]
                               + [f"{_chap(l.get('chapter'))} {fmt_money(l.get('tgf_mvp'))}"
                                  for l in link["linked"]])
            rule = GAME_RULES["tgf_mvp"].format(others=others, parts=parts)
        else:
            rule = "Best Event MVP across TGF wins; ties split."
        net_games.append({"name": "TGF MVP", "pot": fmt_money(tm["pot"]), "rule": rule,
                          "lines": [{"label": "TGF MVP", "amount": fmt_money(tm["pot"])}]})

    # ── GROSS ──
    gross_games = []
    if t["skins"]:
        s = t["skins"]
        per = (s["pot"] or 0) / max(1, s["flights"])
        rule = (GAME_RULES["skins_half"] if s["half_net"]
                else GAME_RULES["skins"].format(flights=_plural_flights(s["flights"])))
        gross_games.append({"name": "Skins · ½ Net" if s["half_net"] else "Skins · Gross",
                            "pot": fmt_money(per), "per_flight": s["flights"] > 1, "rule": rule,
                            "lines": [{"label": f"Flight {i + 1}" if s["flights"] > 1 else "Skins",
                                       "hint": "skins ÷ pot", "amount": fmt_money(per)}
                                      for i in range(s["flights"])]})
    ig = t["ind_gross"]
    if ig and ig["off"]:
        mn = _ind_gross_minimum(holes, db_path)
        gross_games.append({"name": "Individual Gross", "off": True,
                            "rule": GAME_RULES["ind_gross_off"].format(min=mn or "more", holes=holes)})
    elif ig:
        lines = []
        for fi in range(ig["flights"]):
            for pi, amt in enumerate(ig["places"]):
                lines.append({"label": f"F{fi + 1} · {('1st', '2nd')[pi]}" if ig["flights"] > 1
                              else ("1st", "2nd")[pi],
                              "amount": fmt_money(amt), "new_flight": fi > 0 and pi == 0})
        gross_games.append({"name": "Individual Gross", "pot": fmt_money(ig["pot"]),
                            "rule": GAME_RULES["ind_gross"].format(flights=_plural_flights(ig["flights"])),
                            "lines": lines})

    # ── the money in four buckets, and the pot check ──
    team_pot = (team or {}).get("pot") or 0
    buckets = [("Team Net" if not (team or {}).get("cart") else "Cart Net", team_pot, "team"),
               ("CTP", ctp_total, "ctp"),
               ("Net Games", t["net_total"] or 0, "net"),
               ("Gross Games", t["gross_total"] or 0, "gross")]
    fund = t["total"] or 0
    check = round(sum(b[1] for b in buckets), 2)
    if abs(check - fund) > 0.01:
        warnings.append(f"POT CHECK MISMATCH: sections add to {fmt_money(check)} but the GAMES tab "
                        f"total is {fmt_money(fund)}.")
    if t["included_total"] is not None and abs((team_pot + ctp_total) - t["included_total"]) > 0.01:
        warnings.append(f"Included Games: Team {fmt_money(team_pot)} + CTP {fmt_money(ctp_total)} "
                        f"≠ subtotal {fmt_money(t['included_total'])}.")
    bar = [{"label": f"{name} {fmt_money(v)}", "pct": round(100.0 * v / fund, 3), "key": key}
           for name, v, key in buckets if v and fund]

    def _fee(total, n, extra=0.0):
        if not total or not n:
            return None
        return fmt_money((float(total) - extra) / n)

    sections = {
        "included": {"title": "Included Games", "total": fmt_money(t["included_total"]),
                     "strip": "Everyone in the field is entered automatically.",
                     "games": included} if included else None,
        "gross": {"title": "Gross Games", "total": fmt_money(t["gross_total"]),
                  "strip": f"Straight up, no handicaps · {gross_count} entrants @ "
                           f"{_fee(t['gross_total'], gross_count) or '—'}",
                  "games": gross_games} if gross_games else None,
        "net": {"title": "Net Games", "total": fmt_money(t["net_total"]),
                "strip": f"Members only · {net_count} entrants @ "
                         f"{_fee(t['net_total'], net_count, linked_extra) or '—'}",
                "games": net_games} if net_games else None,
    }
    return {
        "event": {"id": int(event_id), "item_name": ev.get("item_name"), **header},
        "fund": fmt_money(fund), "mwp": fmt_money(t["mwp"]),
        "field": {"players": int(counts.get("players") or 0), "net": net_count, "gross": gross_count},
        "bar": bar, "sections": sections,
        "pot_check": {"parts": [(b[0].split()[0] if b[2] != "ctp" else "CTP", fmt_money(b[1]))
                                for b in buckets], "total": fmt_money(check),
                      "ok": abs(check - fund) <= 0.01},
        "stableford": _stableford(ev, db_path),
        "hio": _hio_band(ev, db_path),
        "warnings": warnings,
        "source": games.get("source"),
    }
