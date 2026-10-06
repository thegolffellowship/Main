"""THE PRINTED SCORECARD (Convergence #15, CA #885-5; design-claude
#890-#897, CA rulings #898/#900; Kerry 2026-09-28: "Build the scorecards").

Pure assembly over readers the Tracker already has. NOTHING on a card is
typed, hard-coded or computed here if the Tracker holds it (#897):

  * groups, order, slot, cart seats, index, PH, the net-game value, its
    allowance and off-the-lowest  -> `get_event_print_pack` (the Starter
    Sheet's reader, so the sheet and the card cannot disagree)
  * which tees print                -> `event_tee_legend` (designated sets)
  * par / stroke index / yardage    -> `course_tee_holes` (`_ls_tee_holes`)
  * dots                            -> `handicap_calc.ruled_dots`, the one
    allocator the G-0 publish stores pops with (D24 / CA #771)
  * par-3 suppression of net dots   -> the engine's own game rule
    (`live_scoring` team_net `no_pops_on_par3`), never a print choice
  * the scorer QR                   -> `score_entry.event_group_links`

A missing required value never prints as a blank or a guess (#897-G):
`build_scorecards` returns `gaps`, and the page shows them instead of
cards. The only values that live here are design constants (#897-F):
colours, sizes, labels.
"""
from __future__ import annotations

import re
from datetime import datetime

# Layouts (#891-A / #895 §1): (cards per sheet, orientation, base font px)
LAYOUTS = {
    "3up": {"per_sheet": 3, "orient": "portrait", "font": 11.0,
            "label": "3 per sheet · Portrait"},
    "2up": {"per_sheet": 2, "orient": "portrait", "font": 14.5,
            "label": "2 per sheet · Portrait"},
    "2land": {"per_sheet": 2, "orient": "landscape", "font": 13.5,
              "label": "2 per sheet · Landscape"},
}
GROUPINGS = ("team", "cart")

# Scorecard tee-row colours by MASTER tee name (#890 §4; CA #898-6: a token
# map, no colour column). Unknown names print black-on-white and are logged.
TEE_TOKENS = {
    "gold": ("#FFCF40", "#1B1B1B"),
    "blue": ("#2F5FA6", "#FFFFFF"),
    "red": ("#C0392B", "#FFFFFF"),
    "white": ("#FFFFFF", "#1B1B1B"),
    "black": ("#111111", "#FFFFFF"),
    "green": ("#2E7D32", "#FFFFFF"),
    "silver": ("#C0C4CA", "#1B1B1B"),
}

# Band text as stored -> as printed (#897-B; CA #898-7: "Forward", not Women)
BAND_TEXT = {"<50": "< 50", "50-64": "50–64", "65+": "65+", "forward": "Forward"}


def _band_text(band: str) -> str:
    parts = [b.strip() for b in str(band or "").split(",") if b.strip()]
    return " · ".join(BAND_TEXT.get(b.lower(), BAND_TEXT.get(b, b)) for b in parts)


def _master(name: str) -> str:
    from email_parser.database import _gg_tee_parts
    return _gg_tee_parts(name or "")["master"]


def merge_shared_tees(tees: list, grids: dict) -> list:
    """ONE LINE PER TEE (Kerry 2026-10-06, Avery Ranch card: "In the case
    where two tee groups share a tee, just have one and put 65+ & Forward
    so that we don't take up two lines"). Two designated bands SHARE a tee
    when they print the same tee name and the same yardage on every hole
    played; the later band folds into the earlier row and the age cell
    reads both ("65+ & Forward"). A tee with a rating of its own for the
    folded band (a women's rating on the same markers) prints both
    ratings. The input rows are untouched: the yardage grid, chips and
    per-player lookups keep reading every band."""
    out = []
    for t in tees:
        host = next((o for o in out if (o["master"] or "").lower() == (t["master"] or "").lower()
                     and all(grids[hk]["yards"].get(o["band"], {}) == grids[hk]["yards"].get(t["band"], {})
                             for hk in grids)), None)
        if host is None:
            out.append({**t, "bands": [t["band"]], "merged_bands": [], "rating_extra": None})
            continue
        host["bands"].append(t["band"])
        host["merged_bands"].append(t["band"])
        host["band_text"] = " & ".join(_band_text(b) for b in host["bands"])
        if t.get("rating") and (t.get("rating"), t.get("slope")) != (host.get("rating"), host.get("slope")):
            host["rating_extra"] = f"{t['rating']}/{t['slope']}"
    return out


def _tee_colour(master: str):
    m = (master or "").strip().lower()
    m = re.sub(r"\s*\((?:l|lady|ladies)\)\s*", "", m).strip()
    m = re.sub(r"\s+tees?$", "", m)
    return TEE_TOKENS.get(m)


def _row_colour(tee_id, master: str, overrides: dict):
    """(bg, fg) for a tee row from THE resolver (database.resolve_tee_color:
    explicit colour, else the colour word anywhere in the name — Kerry
    2026-09-28, Star Ranch's "Champ - Blue"). A word with a design token
    (#890 §4) prints the design's shade; anything else prints the
    resolver's hex with ink picked for contrast. None = unresolved."""
    from email_parser.database import resolve_tee_color
    res = resolve_tee_color(tee_id, master, overrides)
    if res["word"] and res["word"] in TEE_TOKENS:
        return TEE_TOKENS[res["word"]]
    hx = res["hex"]
    if not hx:
        return None
    r, g, b = (int(hx[i:i + 2], 16) for i in (1, 3, 5))
    ink = "#1B1B1B" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#FFFFFF"
    return (hx, ink)


def chip_styles(tees: list) -> tuple[dict, dict]:
    """Name-circle colour and outline per band, from the card's own tee rows.

    Kerry 2026-09-29: the circle beside a name must be the SAME colour as
    that tee's row ("are all of the tee dots by names matching the colors
    of the tee rows?"), so it is read from the row, never a second palette.
    A women's tee prints as an OUTLINE only when it shares its colour with
    another row on the card (women on Gold beside 65+ Gold); with a colour
    of its own it is solid ("it doesn't need to differentiate")."""
    bg = {t["band"]: t["bg"] for t in tees}
    outline = {t["band"]: bool(t.get("ladies")) and any(
        o is not t and (o["bg"] or "").lower() == (t["bg"] or "").lower() for o in tees)
        for t in tees}
    return bg, outline


def _short_code(master: str, ladies: bool) -> str:
    base = re.sub(r"\s*\((?:l|lady|ladies)\)\s*", "", master or "", flags=re.I).strip()
    base = re.sub(r"\s+tees?$", "", base, flags=re.I)
    code = base[:1].upper() if base else "?"
    return code + ("-L" if ladies else "")


def _fmt_date(d: str | None) -> str | None:
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%a, %B %-d, %Y")
    except (ValueError, TypeError):
        return None


def _name_parts(conn, cid, fallback: str):
    if cid:
        r = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                         (int(cid),)).fetchone()
        if r and (r[0] or r[1]):
            return (r[0] or "").strip(), (r[1] or "").strip()
    parts = (fallback or "").split()
    return (" ".join(parts[:-1]), parts[-1]) if len(parts) > 1 else ("", fallback or "")


def _hcp_text(v):
    if v is None:
        return None
    v = int(v)
    return f"+{-v}" if v < 0 else str(v)


def _start_hole(slot_short: str, shotgun: bool, first_tee: str) -> str:
    return slot_short if shotgun else first_tee


def _team_no_par3_pops() -> bool:
    try:
        from email_parser.live_scoring import SEED_LIVE_SCORING_CONFIG as _LSC
        return bool((_LSC["games"].get("team_net") or {}).get("no_pops_on_par3"))
    except Exception:
        return False


def build_scorecards(event_id: int, layout: str = "3up", grouping: str = "team",
                     qr: str = "on", holes_override: str | None = None,
                     allow_gaps: bool = False, db_path=None) -> dict | None:
    """Everything the scorecard template prints, or `gaps` saying why not.

    layout: 3up | 2up | 2land.  grouping: team (one card per group) | cart
    (one card per cart). qr: on (the default: every group's scorer link when
    live scoring is on for the event — Kerry 2026-10-06, "There needs to be
    [a button]. It should now be checked by default.") | off | auto (only the
    groups the `score_entry_qr` dial names) | preview (every group's real
    link for a look, even with live scoring off).

    allow_gaps (CA #915): a player-level gap — one player with no PH — no
    longer blocks the other cards; that card prints with PH and net BLANK,
    no dots, and the print log names him. Every event-level gap (course,
    tees, pairings, par/SI) still stops the print."""
    from email_parser import database as db
    layout = layout if layout in LAYOUTS else "3up"
    grouping = grouping if grouping in GROUPINGS else "team"
    pack = db.get_event_print_pack(int(event_id), db_path=db_path)
    if not pack:
        return None
    gaps: list[str] = []
    log: list[str] = []
    flagged: list[str] = []
    with db._connect(db_path) as conn:
        ev = dict(conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone())
        course_name = None
        if ev.get("course_id"):
            r = conn.execute("SELECT name FROM courses WHERE course_id = ?",
                             (ev["course_id"],)).fetchone()
            course_name = r[0] if r else None
        legend = pack.get("tee_legend") or []
        tee_rows, _basis, _note = db._event_tee_rows(conn, ev, legend)
        holes_by_tee = {}
        for t in legend:
            if t.get("tee_id"):
                holes_by_tee[t["tee_id"]] = {int(h["hole_number"]): h
                                             for h in db._ls_tee_holes(conn, t["tee_id"])}
        players_by_cid = {}
        for g in pack["groups"]:
            for p in g["players"]:
                p["_first"], p["_last"] = _name_parts(conn, p.get("customer_id"), p.get("name"))
        pairings_saved = None
        try:
            r = conn.execute("SELECT MAX(created_at) FROM event_pairings WHERE event_id = ?",
                             (int(event_id),)).fetchone()
            pairings_saved = r[0] if r else None
        except Exception:
            pairings_saved = None
    del players_by_cid

    if not course_name:
        gaps.append("No course on this event — set the course before printing cards.")
    if not pack["groups"]:
        gaps.append("No saved pairings — save PAIRINGS before printing cards.")
    if not legend:
        gaps.append(f"No designated tees for {course_name or 'this course'} — designate the "
                    "course's tee sets before printing cards.")

    is18_event = pack.get("holes_key") == "18"
    nine = (ev.get("nine_side") or "Front").strip().lower()
    shotgun = (ev.get("start_type") or "").strip().lower().startswith("shotgun")
    first_tee = "10" if nine == "back" else "1"

    def _played(hkey: str) -> list[int]:
        if hkey == "18":
            return list(range(1, 19))
        return list(range(10, 19)) if nine == "back" else list(range(1, 10))

    # ---- tees in play: one row each, in legend order (max four) --------
    _overrides = db.tee_color_overrides(db_path=db_path)
    tees = []
    for t in legend[:4]:
        master = _master(t.get("tee_name") or "")
        row = tee_rows.get(t["band"])
        col = _row_colour(t.get("tee_id"), master, _overrides)
        if not col:
            log.append(f"Tee '{master}' has no colour (none set, no colour word in its name); "
                       "printed black on white. Name its colour (scoring-tee-colors).")
            col = ("#FFFFFF", "#1B1B1B")
        tees.append({
            "band": t["band"], "master": master, "ladies": bool(t.get("ladies")),
            "tee_id": t.get("tee_id"), "bg": col[0], "fg": col[1],
            "code": _short_code(master, bool(t.get("ladies"))),
            "band_text": _band_text(t["band"]),
            "rating": (row or {}).get("rating"), "slope": (row or {}).get("slope"),
            "holes": holes_by_tee.get(t.get("tee_id"), {}),
        })
        if not row:
            gaps.append(f"Tee '{master}' ({_band_text(t['band'])}) has no rating/slope for "
                        "this event's holes — fix the course card before printing.")
    _chip_bg, _chip_outline = chip_styles(tees)
    if len(legend) > 4:
        log.append(f"{len(legend)} designated tees; the first four print.")
    by_band = {t["band"]: t for t in tees}
    # Par + stroke index come from the <50 set (#897-B), else the first.
    par_tee = by_band.get("<50") or (tees[0] if tees else None)

    hole_keys = sorted({g["holes"] for g in pack["groups"]} or {"18" if is18_event else "9"})
    if holes_override in ("9", "18"):
        hole_keys = [holes_override]
    grids = {}
    for hk in hole_keys:
        played = _played(hk)
        grid = {"holes": played, "par": {}, "si": {}, "yards": {}}
        if par_tee:
            for h in played:
                hh = par_tee["holes"].get(h) or {}
                if hh.get("par") is None or hh.get("stroke_index") is None:
                    gaps.append(f"No par/stroke index for hole {h} on the {par_tee['master']} "
                                "card — load the course card before printing.")
                    continue
                grid["par"][h] = int(hh["par"])
                grid["si"][h] = int(hh["stroke_index"])
            for t in tees:
                for h in played:
                    oh = t["holes"].get(h) or {}
                    if oh.get("par") not in (None, grid["par"].get(h)) or \
                            oh.get("stroke_index") not in (None, grid["si"].get(h)):
                        log.append(f"{t['master']} hole {h} par/SI differ from the "
                                   f"{par_tee['master']} set; printed the {par_tee['master']} values.")
                    grid["yards"].setdefault(t["band"], {})[h] = oh.get("yardage")
        grid["par_out"] = sum(v for h, v in grid["par"].items() if h <= 9)
        grid["par_in"] = sum(v for h, v in grid["par"].items() if h >= 10)
        grid["par_total"] = sum(grid["par"].values())
        for t in tees:
            y = grid["yards"].get(t["band"], {})
            vals = [v for v in y.values() if v is not None]
            t.setdefault("totals", {})[hk] = {
                "out": sum(v for h, v in y.items() if v and h <= 9),
                "in": sum(v for h, v in y.items() if v and h >= 10),
                "total": sum(vals)}
        grids[hk] = grid

    # ---- the net game: label and allowance from the engine ------------
    unit = pack.get("team_unit") or "group"
    net_word = "CART" if unit == "cart" else "TEAM"
    net_short = "C" if unit == "cart" else "T"
    net_name = "Cart Net" if unit == "cart" else "Team Net"
    allow_pct = round((pack.get("team_allowance") or 0) * 100)
    off_low = pack.get("team_off_lowest") or {}
    suppress_par3 = _team_no_par3_pops()
    if not suppress_par3:
        log.append("Net-game dots include par 3s: the engine's Team Net rule has "
                   "no_pops_on_par3 off (CA #898-1 / Tracker Build #902-A open).")

    # ---- QR -----------------------------------------------------------
    links: dict = {}
    qr_on = False
    if qr in ("on", "auto", "preview"):
        try:
            from email_parser import score_entry as se
            enabled = se.event_enabled(int(event_id), db_path)
            if qr == "on" and not enabled:
                log.append("QR codes: live scoring is off for this event, so the cards carry no code.")
            if qr == "preview" or (enabled and (qr == "on" or se._qr_dial(int(event_id), db_path))):
                qr_on = True
                for hk in hole_keys:
                    if qr == "on":
                        # A code needs a round: seed it from the SAVED pairings
                        # (idempotent; the cart signs do the same on print).
                        se.seed_round_from_pairings(int(event_id), hk, db_path=db_path)
                    links[hk] = se.event_group_links(int(event_id), hk, db_path=db_path)
                if qr == "auto":
                    want = se._qr_dial(int(event_id), db_path)
                    if want != "all":
                        for hk in links:
                            links[hk] = {k: v for k, v in links[hk].items() if k in (want or [])}
        except Exception as e:  # noqa: BLE001
            log.append(f"QR unavailable: {str(e)[:120]}")
            qr_on = False

    # ---- cards --------------------------------------------------------
    cards = []
    dump = []
    for g in pack["groups"]:
        hk = g["holes"] if not holes_override else holes_override
        grid = grids.get(hk)
        slot_short = re.sub(r"^HOLE\s+", "", g["slot_label"] or "", flags=re.I)
        if shotgun:
            start_time = pack["event"].get("start_clock")
        else:
            start_time = slot_short
        start_hole = _start_hole(slot_short, shotgun, first_tee)
        m = re.match(r"(\d+)", str(start_hole))
        hl_hole = int(m.group(1)) if m else None
        if not start_time:
            gaps.append(f"Group {g['group_num']}: no start time on the event.")
        rows = []
        for p in sorted(g["players"], key=lambda x: x.get("cart_pos") or 0):
            band = (p.get("tee_choice") or "").strip()
            tee = by_band.get(band)
            nm = f"{p['_last'].upper()}, {p['_first']}".strip().strip(",")
            if not tee:
                gaps.append(f"{p.get('name')} (group {g['group_num']}): tee '{band or 'none'}' "
                            "is not one of the event's designated tees.")
            ph = p.get("playing_handicap")
            net = p.get("team_handicap")
            if ph is None:
                (flagged if allow_gaps else gaps).append(
                    f"{p.get('name')} (group {g['group_num']}): no playing handicap — "
                    + ("no TGF index yet; set a starting handicap on his profile and reprint."
                       if p.get("handicap_index_display") is None and tee else
                       "his tee has no rating/slope for this event — fix the course card.")
                    + " The Starter Sheet shows the same gap.")
            if net is None and ph is not None:
                gaps.append(f"{p.get('name')} (group {g['group_num']}): no {net_name} handicap.")
            si_own = {}
            if tee and grid:
                for h in grid["holes"]:
                    oh = tee["holes"].get(h) or {}
                    if oh.get("stroke_index") is not None:
                        si_own[h] = int(oh["stroke_index"])
                if len(si_own) != len(grid["holes"]):
                    gaps.append(f"{p.get('name')}: the {tee['master']} card has no stroke index "
                                "for every hole played.")
                    si_own = {}
            from email_parser.handicap_calc import ruled_dots
            ph_dots = ruled_dots(ph, si_own) if (ph is not None and ph > 0 and si_own) else {}
            net_dots = ruled_dots(net, si_own) if (net is not None and net > 0 and si_own) else {}
            # Kerry 9/29: on a par 3 the team pop the rule takes away still
            # prints, as an OUTLINE ("would-be" pop), so the card shows what
            # the rule removed. Scoring reads net_dots only.
            net_ghost = {}
            if suppress_par3 and grid:
                net_ghost = {h: v for h, v in net_dots.items()
                             if grid["par"].get(h) == 3 and (v or 0) > 0}
                net_dots = {h: (0 if grid["par"].get(h) == 3 else v) for h, v in net_dots.items()}
            row = {
                "name": nm, "initials": ((p["_first"][:1] + p["_last"][:1]).upper()),
                "tee_code": tee["code"] if tee else "?",
                # The Starter Sheet's own swatch for this band (Kerry: "same
                # as the Starter Sheet").
                # ONE source (Kerry 9/29: "are all of the tee dots by names
                # matching the colors of the tee rows? We need to make that
                # happen"): the circle is the band's own tee-row colour.
                "chip": _chip_bg.get(band),
                # Outline only when a women's tee SHARES its colour with
                # another row on this card (Kerry 9/29); its own colour → solid.
                "chip_ladies": bool(_chip_outline.get(band)),
                "cart_pos": p.get("cart_pos"), "customer_id": p.get("customer_id"),
                "ph": _hcp_text(ph) or "", "net": _hcp_text(net) or "",
                "ph_dots": {h: max(0, int(v or 0)) for h, v in ph_dots.items()},
                "net_dots": {h: max(0, int(v or 0)) for h, v in net_dots.items()},
                "net_ghost": {h: int(v) for h, v in net_ghost.items()},
                "rider": (p.get("cart_pos") or 0) >= 3,
            }
            rows.append(row)
            dump.append({"group_num": g["group_num"], "slot_label": g["slot_label"],
                         "cart_pos": p.get("cart_pos"), "customer_id": p.get("customer_id"),
                         "name": row["name"], "band": band,
                         "tee_id": tee["tee_id"] if tee else None,
                         "index": p.get("handicap_index_display"),
                         "course_handicap_raw": p.get("course_handicap_raw"),
                         "ph": ph, "net_allowed": p.get("team_allowed"), "net": net,
                         "si_by_hole": si_own, "ph_dots": row["ph_dots"],
                         "net_dots": row["net_dots"]})
        base = {"group_num": g["group_num"], "holes": hk, "slot_label": g["slot_label"],
                "start_time": start_time, "start_hole": start_hole, "hl_hole": hl_hole,
                "qr": None, "ggid": g.get("ggid")}
        url = (links.get(g["holes"]) or {}).get(g["group_num"]) if qr_on else None
        if url:
            from email_parser.score_entry import qr_svg
            base["qr"] = {"url": url, "svg": qr_svg(url)}
        elif qr in ("preview", "on") and qr_on:
            log.append(f"Group {g['group_num']}: no scorer link (no open round) — QR slot empty.")
        if grouping == "cart":
            a = [r for r in rows if (r["cart_pos"] or 0) <= 2]
            b = [r for r in rows if (r["cart_pos"] or 0) >= 3]
            for part, label in ((a, "A"), (b, "B")):
                if part:
                    cards.append({**base, "cart": label,
                                  "rows": [{**r, "rider": False} for r in part], "split_after": None})
        else:
            split = next((i for i, r in enumerate(rows) if r["rider"]), None)
            cards.append({**base, "cart": None, "rows": rows,
                          "split_after": split if split not in (None, 0) else None})

    lay = LAYOUTS[layout]
    # NAME SIZE (Kerry 2026-09-29: bigger "to maximize legibility"): each
    # name as large as its cell allows — up to 1.35x the card font — and
    # only the long ones shrink, so nothing wraps. Cell width follows the
    # locked column widths (#895: 9-hole lead 24%; 18-hole left lead 35.1%
    # of half the card); ~0.62 em per Bitter-bold character is the estimate.
    _w = 1008 if lay["orient"] == "landscape" else 768
    _base = lay["font"]
    def _name_em(name: str, lead_px: float) -> float:
        avail = lead_px - 1.75 * _base
        return round(max(0.7, min(1.35, avail / (0.62 * _base * max(len(name), 1)))), 2)
    for c in cards:
        for r in c["rows"]:
            r["name_em"] = _name_em(r["name"], 0.24 * _w)
            r["name_em_18"] = _name_em(r["name"], 0.372 * (_w - 6) / 2)
    if layout == "3up" and len(tees) >= 5:
        gaps.append("This event has 5+ tees; the 3-per-sheet card cannot hold them. "
                    "Use a 2-per-sheet layout.")
    sheets = [cards[i:i + lay["per_sheet"]] for i in range(0, len(cards), lay["per_sheet"])]
    pct_note = (f"{allow_pct}%" + (", off the field's low" if off_low.get("applied") else "")
                + ("; no pops on par 3s" if suppress_par3 else ""))
    for f in flagged:
        log.append("PRINTED ANYWAY (flagged): " + f + " His PH and net print blank, no dots.")
    return {
        "event": {"id": int(event_id), "item_name": ev.get("item_name"),
                  "chapter": (ev.get("chapter") or "").upper(),
                  "course": course_name, "date": _fmt_date(ev.get("event_date")),
                  "event_date": ev.get("event_date"), "shotgun": shotgun,
                  "file_stub": pack["event"].get("file_stub")},
        "layout": layout, "layout_meta": lay, "grouping": grouping, "qr": qr,
        "tees": merge_shared_tees(tees, grids), "grids": grids, "cards": cards, "sheets": sheets,
        "net": {"word": net_word, "short": net_short, "name": net_name,
                "pct": allow_pct, "pct_note": pct_note, "unit": unit,
                "basis": pack.get("team_basis"), "low": off_low.get("low"),
                "off_low": bool(off_low.get("applied")),
                "par3_suppressed": suppress_par3},
        "gaps": list(dict.fromkeys(gaps)), "log": list(dict.fromkeys(log)),
        "flagged": list(dict.fromkeys(flagged)), "allow_gaps": bool(allow_gaps),
        "player_gaps": any("no playing handicap" in x for x in gaps),
        "groups": [{"holes": g["holes"], "group_num": g["group_num"],
                    "slot": re.sub(r"^HOLE\s+", "", g["slot_label"] or "", flags=re.I),
                    "players": ", ".join((p.get("_last") or p.get("name") or "")
                                         for p in sorted(g["players"],
                                                         key=lambda x: x.get("cart_pos") or 0)),
                    "ggid": g.get("ggid") or ""} for g in pack["groups"]],
        "pairings_saved": pairings_saved,
        "handicap_as_of": ev.get("event_date") if db._event_index_as_of(ev) else "today",
        "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
        "dump": dump,
    }


# ---------------------------------------------------------------------------
# PDF + the staff-only send ("approve a template")
# ---------------------------------------------------------------------------

ALL_COMBOS = [(lay, grp) for lay in ("3up", "2up", "2land") for grp in GROUPINGS]


def build_scorecards_pdf(render, event_id: int, static_dir: str, sets: list[dict],
                         db_path=None) -> dict:
    """Render each requested set ({layout, grouping, qr, holes}) and bind
    them into one PDF through the print pack's Chromium path. A set with
    gaps is NOT rendered; the gaps come back instead (#897-G). Returns
    {pdf, parts:[{slug, pages, sheets, ok}], gaps, filename}."""
    from email_parser.print_pack import _render_pdf_chromium
    htmls, meta, gaps = [], [], {}
    ev_name = None
    stub = None
    for s in sets:
        sc = build_scorecards(event_id, s.get("layout", "3up"), s.get("grouping", "team"),
                              qr=s.get("qr", "on"), holes_override=s.get("holes"),
                              allow_gaps=bool(s.get("allow_gaps")), db_path=db_path)
        if not sc:
            return {"error": "event not found"}
        ev_name = sc["event"]["item_name"]
        stub = sc["event"].get("file_stub") or stub
        slug = f"{sc['layout']}-{sc['grouping']}-{s.get('holes') or 'event'}-qr{sc['qr']}"
        if sc["gaps"]:
            gaps[slug] = sc["gaps"]
            continue
        htmls.append((slug, render("scorecards.html", sc=sc)))
        meta.append({"slug": slug, "sheets": len(sc["sheets"]), "cards": len(sc["cards"])})
    if not htmls:
        return {"error": "nothing to print", "gaps": gaps}
    pdf, parts, engine = _render_pdf_chromium(htmls, static_dir)
    by = {p["slug"]: p["pages"] for p in parts}
    for m in meta:
        m["pages"] = by.get(m["slug"])
        m["one_page_per_sheet"] = m["pages"] == m["sheets"]
    code = (ev_name or f"event-{event_id}").replace("/", "-")
    return {"pdf": pdf, "parts": meta, "gaps": gaps, "engine": engine,
            # <stub>-Scorecards.pdf, the convention every report uses (Kerry
            # 9/29: "the file naming convention is different … and incorrect").
            "filename": f"{stub or code}-Scorecards.pdf", "event_name": ev_name}


def send_scorecards_pdf(built: dict, to_address: str | None = None, note: str = "") -> dict:
    """Mail the scorecard PDF to KERRY ONLY (staff), subject "approve a
    template". Refuses any non-staff address: these are drafts for
    approval, never a member send."""
    import os
    from email_parser.fetcher import send_mail_graph
    base = (os.getenv("PRINT_PACK_EMAIL_TO") or os.getenv("DAILY_REPORT_TO")
            or os.getenv("EMAIL_ADDRESS") or "")
    to_address = (to_address or base).strip()
    addrs = [a.strip() for a in to_address.split(",") if a.strip()]
    allowed = {a.strip().lower() for a in base.split(",") if a.strip()}
    bad = [a for a in addrs if not (a.lower().endswith("@thegolffellowship.com")
                                    or a.lower() in allowed)]
    if not addrs or bad:
        return {"sent": False, "why": f"staff addresses only; refused {bad or 'empty'}"}
    creds = {k: os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                       "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")}
    if not all(creds.values()):
        return {"sent": False, "why": "mail credentials not set"}
    rows = "".join(f"<li>{p['slug']}: {p['cards']} cards, {p['sheets']} sheets, "
                   f"{p['pages']} pages</li>" for p in built.get("parts") or [])
    html = (f"<p>Scorecard test set for <b>{built.get('event_name')}</b>, for your approval "
            f"before it replaces Golf Genius's card.</p><ul>{rows}</ul>"
            + (f"<p>{note}</p>" if note else "")
            + "<p>Nothing was sent to members.</p>")
    ok = send_mail_graph(tenant_id=creds["AZURE_TENANT_ID"], client_id=creds["AZURE_CLIENT_ID"],
                         client_secret=creds["AZURE_CLIENT_SECRET"],
                         from_address=creds["EMAIL_ADDRESS"], to_address=", ".join(addrs),
                         subject=f"approve a template — Scorecards — {built.get('event_name')}",
                         html_body=html,
                         attachments=[(built["filename"], built["pdf"], "application/pdf")])
    return {"sent": bool(ok), "to": addrs, "bytes": len(built.get("pdf") or b"")}
