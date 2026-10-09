"""THE LONE STAR CUP STARTER SHEET (design-claude #1481, Kerry-approved;
Kerry 10/8: "Check mail directive for LSC Starter Sheets from Claude Design
and incorporate now").

A theme on the production Starter Sheet for the Cup's rounds and its Friday
practice round: navy header band with the white-border Hideout logo, the
round's FORMAT, course and full date, first tee, a 50/50 team band, the
TEES key (only tees on the sheet), a TEE SHEET of 3-across cards, the
ALPHABETICAL list, a per-page key and a navy footer.

The data is the same the Cup's other reports read:
  * PRACTICE ROUND: the practice event's SAVED pairings (`get_event_print_pack`),
    each player's PH as the pack computes it;
  * FOURBALL / FOURSOMES / SINGLES: the round's matches from THE DRAW
    (`lsc_cup.cup_print_groups`), PH = the LOCKED course handicap.
Handicap math is the engine's (#1467 = #1481 §6/§7): Fourball HCP =
whs_round(PH x 0.9), OFF off the lowest of four; Foursomes (Chapman) A =
lower PH x 0.6, B = higher PH x 0.4, TEAM = whs_round(A + B), OFF off the
lower team; Singles OFF = PH - the lower PH in that match. Nothing here is
typed: design constants only.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from email_parser.handicap_calc import whs_round

NAVY = "#002855"
TEAM_COLOR = {"austin": "#BF5700", "sa": "#44596B"}
TEAL_OLD, TEAL_NEW = "#0f766e", "#0E8A9A"
FORMAT_TITLE = {"practice": "PRACTICE ROUND", "fourball": "FOURBALL",
                "chapman": "FOURSOMES", "singles": "SINGLES"}
COL_LABEL = {"fourball": "FOURBALL · 2 v 2 TEAMS", "chapman": "FOURSOMES · 2 v 2 TEAMS",
             "singles": "SINGLES · 1 v 1"}
SPLIT_OVER_PLAYERS = 20     # #1481 §5H sample: 15 fits one page, 28 splits


def _full_date(d) -> str:
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%A, %B %-d, %Y")
    except (ValueError, TypeError):
        return ""


def _clock(t: str) -> str:
    """'8:30' -> '8:30 AM', '1:30' -> '1:30 PM' (the Cup tees off 7-5);
    a label that already carries AM/PM is returned as is."""
    t = (t or "").strip()
    if not t or re.search(r"[AP]M$", t, re.I):
        return t.upper()
    m = re.match(r"^(\d{1,2}):(\d{2})$", t)
    if not m:
        return t
    h = int(m.group(1))
    return f"{h}:{m.group(2)} {'AM' if 7 <= h <= 11 else 'PM'}"


def _num(v, nd=0):
    if v is None:
        return ""
    if nd:
        return f"{float(v):.{nd}f}"
    return str(int(v))


def _names(conn, cids):
    out = {}
    if not cids:
        return out
    q = ",".join("?" * len(cids))
    for r in conn.execute(f"SELECT customer_id, first_name, last_name FROM customers "
                          f"WHERE customer_id IN ({q})", tuple(cids)):
        out[int(r[0])] = ((r[1] or "").strip(), (r[2] or "").strip())
    return out


def build(event_id: int, session_id: str | None = None, preview: bool = False,
          db_path=None) -> dict | None:
    """Everything the LSC starter sheet prints, or `gaps` saying why not."""
    from email_parser import database as db
    from email_parser import lsc_cup
    ctx = lsc_cup.lsc_report_context(int(event_id), db_path=db_path)
    if not ctx:
        return None
    base = db.get_event_print_pack(int(event_id), db_path=db_path)
    if not base:
        return None
    gaps, log = [], []
    try:
        lock = (json.loads(db.get_app_setting("lsc_handicap_lock", db_path=db_path) or "{}")
                .get(str(ctx["cup_event_id"])) or {}).get("players") or {}
    except Exception:
        lock = {}
    team_of = {int(c): (v or {}).get("team") for c, v in lock.items()}

    # ---- the round's groups --------------------------------------------
    if ctx["kind"] == "practice":
        fmt, date = "practice", base["event"].get("event_date")
        groups = []
        for g in base["groups"]:
            players = []
            for p in sorted(g["players"], key=lambda x: x.get("cart_pos") or 0):
                players.append({"customer_id": p.get("customer_id"), "name": p.get("name") or "",
                                "cart_pos": p.get("cart_pos"), "band": p.get("tee_choice") or "",
                                "idx": p.get("handicap_index_display"),
                                "ph": p.get("playing_handicap"),
                                "team": team_of.get(int(p["customer_id"])) if p.get("customer_id") else None,
                                "is_first_timer": bool(p.get("is_first_timer")),
                                "is_new": bool(p.get("is_new"))})
            groups.append({"time": re.sub(r"^HOLE\s+", "", g.get("slot_label") or "", flags=re.I),
                           "group_num": g["group_num"], "players": players, "match_ids": []})
        first_match = None
    else:
        cg = lsc_cup.cup_print_groups(int(event_id), session_id=session_id, preview=preview,
                                      db_path=db_path)
        gaps += cg["gaps"]
        log += cg["log"]
        if not cg["groups"] and not cg["gaps"]:
            gaps.append("This round isn't drawn yet. Its groups and tee times fill in from THE DRAW.")
        fmt = cg["groups"][0]["lsc_format"] if cg["groups"] else None
        date = cg["groups"][0].get("date") if cg["groups"] else None
        groups = [{"time": _clock(g["slot_label"]), "group_num": g["group_num"],
                   "players": [{**p, "band": p.get("tee_choice") or "",
                                "idx": p.get("handicap_index_display"),
                                "ph": p.get("playing_handicap"),
                                "is_first_timer": False, "is_new": False} for p in g["players"]],
                   "match_ids": g["match_ids"]} for g in cg["groups"]]
        # MATCH NUMBERS run through the weekend (#1481 §5G): each round
        # starts after every match of the rounds before it.
        try:
            dial = json.loads(db.get_app_setting("lsc_preview_matches" if preview else "lsc_matches",
                                                 db_path=db_path) or "{}")
        except Exception:
            dial = {}
        first_match, n = None, 1
        for s in dial.get("sessions") or []:
            if s.get("id") == session_id:
                first_match = n
                break
            n += int(s.get("n_matches") or len(s.get("matches") or []))
        order = {}
        for s in dial.get("sessions") or []:
            if s.get("id") == session_id:
                order = {m.get("id"): i for i, m in enumerate(s.get("matches") or [])}
        for g in groups:
            g["match_nums"] = [(first_match or 1) + order.get(mid, 0) for mid in g["match_ids"]]
        # 1T on a Cup round: the roster rule, against the Cup's own date
        rows = [p for g in groups for p in g["players"] if p.get("customer_id")]
        try:
            with db._connect(db_path) as conn:
                db._mark_first_timers(conn, int(event_id), rows)
        except Exception:
            log.append("1T badges unavailable.")
    if not fmt and not gaps:
        gaps.append("LSC round has no format.")

    # ---- names, member caps --------------------------------------------
    cids = sorted({int(p["customer_id"]) for g in groups for p in g["players"] if p.get("customer_id")})
    with db._connect(db_path) as conn:
        names = _names(conn, cids)
    from email_parser.lsc_cup import member_or_alumni
    caps_set = member_or_alumni(event_id, cids, db_path)
    for g in groups:
        for p in g["players"]:
            first, last = names.get(int(p["customer_id"]), ("", "")) if p.get("customer_id") else ("", "")
            if not (first or last):
                parts = (p.get("name") or "").split()
                first, last = (" ".join(parts[:-1]), parts[-1]) if len(parts) > 1 else ("", p.get("name") or "")
            # #1481 §5D: members and alumni get an uppercase LAST name
            # (+ Kerry's Cup roster ruling, lsc_cup.member_or_alumni)
            caps = int(p["customer_id"]) in caps_set if p.get("customer_id") else False
            p["first"], p["last"] = first, (last.upper() if caps else last)
            p["team_color"] = TEAM_COLOR.get(p.get("team") or "")
            if fmt and fmt != "practice" and not p["team_color"]:
                gaps.append(f"{p.get('name')}: no Cup team, so no team bar.")

    # ---- tees: only the ones on this sheet (#1481 §5A / §9) ---------------
    used = {str(p["band"]).lower() for g in groups for p in g["players"] if p.get("band")}
    legend = [t for t in base.get("tee_legend") or [] if str(t["band"]).lower() in used]
    share_65 = {}
    for t in legend:
        share_65[t["band"]] = (t.get("tee_key") or t.get("tee_name"))
    men65 = next((t for t in legend if str(t["band"]) == "65+"), None)
    tees = []
    for t in legend:
        color = t.get("color") or "#FFFFFF"
        ring = bool(t.get("ring"))
        if t.get("ladies"):
            shares = bool(men65 and (men65.get("color") or "").lower() == color.lower())
            ring = shares
            if color.lower() == TEAL_OLD:
                color = TEAL_NEW
        tees.append({"band": t["band"], "label": t.get("band_label") or t["band"],
                     "band_text": t["band"], "name": t.get("tee_name") or "",
                     "color": color, "ring": ring, "white": color.lower() in ("#fff", "#ffffff")})
    tee_by_band = {str(t["band"]).lower(): t for t in tees}
    for g in groups:
        for p in g["players"]:
            p["tee"] = tee_by_band.get(str(p.get("band") or "").lower())
            if not p["tee"]:
                gaps.append(f"{p.get('name')}: tee '{p.get('band') or 'none'}' is not one of the event's tees.")

    # ---- cards ------------------------------------------------------------
    cards = []
    for g in groups:
        ps = g["players"]
        card = {"time": g["time"], "group_num": g["group_num"], "fmt": fmt, "blocks": []}
        if fmt == "practice":
            card["cols"] = ["TEE", "IDX", "PH"]
            rows = []
            for i, p in enumerate(ps):
                rows.append({**p, "vals": [_num(p["idx"], 1), _num(p["ph"])],
                             "rider": (p.get("cart_pos") or 0) >= 3,
                             "rule": "cart" if i > 0 and (p.get("cart_pos") or 0) >= 3
                             and (ps[i - 1].get("cart_pos") or 0) < 3 else None})
            card["blocks"].append({"bar": None, "rows": rows})
        elif fmt in ("fourball", "singles"):
            card["cols"] = ["TEE", "IDX", "HCP" if fmt == "fourball" else "PH", "OFF"]
            card["col_label"] = COL_LABEL[fmt]
            chunks = [ps] if fmt == "fourball" else [ps[i:i + 2] for i in range(0, len(ps), 2)]
            for k, chunk in enumerate(chunks):
                math = lsc_cup.lsc_card_math(fmt, [{"cid": p["customer_id"], "ph": p["ph"],
                                                    "team": p["team"]} for p in chunk])
                rows = []
                for i, (p, m) in enumerate(zip(chunk, math)):
                    rows.append({**p, "vals": [_num(p["idx"], 1), _num(m["hcp"])],
                                 "off": _num(m["off"]),
                                 "rule": "team" if fmt == "fourball" and i == 2 else None})
                nums = g.get("match_nums") or []
                card["blocks"].append({"bar": f"MATCH {nums[k]}" if k < len(nums) else None,
                                       "rows": rows})
        elif fmt == "chapman":
            card["cols"] = ["TEE", "60/40", "TEAM", "OFF"]
            card["col_label"] = COL_LABEL[fmt]
            pairs = [[p for p in ps if p["team"] == t] for t in ("austin", "sa")]
            teams = []
            for pair in pairs:
                if len(pair) != 2 or any(p["ph"] is None for p in pair):
                    gaps.append(f"{card['time']}: a Foursomes pair needs two players with a PH.")
                    teams.append(None)
                    continue
                a, b = sorted(pair, key=lambda p: (float(p["ph"]), p["customer_id"]))
                sa, sb = round(float(a["ph"]) * 0.6, 1), round(float(b["ph"]) * 0.4, 1)
                exact = float(a["ph"]) * 0.6 + float(b["ph"]) * 0.4
                teams.append({"a": a, "b": b, "sa": sa, "sb": sb, "sum": round(exact, 1),
                              "team": lsc_cup.chapman_team_handicap([float(a["ph"]), float(b["ph"])])})
            low = min((t["team"] for t in teams if t), default=0)
            rows = []
            for k, t in enumerate(teams):
                if not t:
                    continue
                t["a"]["ab"], t["b"]["ab"] = "A", "B"
                t["a"]["share"], t["b"]["share"] = t["sa"], t["sb"]
                rows.append({**t["a"], "vals": [_num(t["sa"], 1)], "merge": {
                    "sum": f"{t['sum']:.1f}", "team": _num(t["team"]), "off": _num(t["team"] - low)},
                    "rule": "team" if k == 1 else None})
                rows.append({**t["b"], "vals": [_num(t["sb"], 1)], "merged_below": True, "rule": "dash"})
            nums = g.get("match_nums") or []
            card["blocks"].append({"bar": f"MATCH {nums[0]}" if nums else None, "rows": rows})
        cards.append(card)

    # ---- alphabetical -----------------------------------------------------
    alpha = []
    for g in groups:
        for p in g["players"]:
            row = {**p, "time": g["time"]}
            if fmt == "chapman":
                row["vals"] = [_num(p["idx"], 1), p.get("ab") or "", _num(p.get("share"), 1)]
            else:
                row["vals"] = [_num(p["idx"], 1), _num(p["ph"])]
            alpha.append(row)
    alpha.sort(key=lambda r: ((r["last"] or "").lower(), (r["first"] or "").lower()))
    alpha_cols = ["TEE", "IDX", "A/B", "PH"] if fmt == "chapman" else ["TEE", "IDX", "PH"]

    # ---- the key, per page (#1481 §5I / §6) -------------------------------
    always = ["Tee circle — matches the TEES key above.", "TEAMBAR",
              "IDX — TGF handicap index (18-hole)."]
    if fmt != "chapman":
        always.append("PH — playing handicap at 100%, from that index and the tee played"
                      + (" (the Cup's locked course handicap)." if fmt != "practice" else "."))
    tee_notes, alpha_notes = [], []
    if fmt == "practice":
        tee_notes = ["No games at this event, so there is no Cart/Team Net handicap."]
    elif fmt == "fourball":
        tee_notes = ["HCP — Fourball handicap, 90% of PH.",
                     "OFF — strokes off the lowest player in the match (all four on the card)."]
    elif fmt == "chapman":
        both = ["CHAPMAN — Foursomes is played as Chapman alternate shot, using the USGA 60/40 allowance.",
                "A — lower PH of the pair, 60% applied.", "B — higher PH of the pair, 40% applied."]
        tee_notes = both + ["60/40 — each player's applied share. A is listed first in each pair.",
                            "TEAM — the two shares added (small number), then rounded.",
                            "OFF — strokes off the lowest team in the match. One ball, one score per pair."]
        alpha_notes = both + ["PH — on this list, the applied share (A 60% / B 40%)."]
    elif fmt == "singles":
        lo = first_match or 15
        n_m = sum(len(g.get("match_ids") or []) for g in groups)
        tee_notes = [f"MATCH — two 1 v 1 matches per group (Matches {lo}–{lo + max(n_m, 1) - 1}), "
                     "Austin player listed first.",
                     "OFF — strokes off the lower player in that match (100% of PH)."]
    badge_notes = []
    ft = any(p.get("is_first_timer") for g in groups for p in g["players"])
    nw = any(p.get("is_new") for g in groups for p in g["players"])
    both_b = any(p.get("is_first_timer") and p.get("is_new") for g in groups for p in g["players"])
    if ft:
        badge_notes.append("1T — first TGF event ever.")
    if nw:
        badge_notes.append("NEW — new member, playing their first event as a member.")
    if both_b:
        badge_notes.append("A first-timer who is already a member wears both.")

    n_players = sum(len(g["players"]) for g in groups)
    split = n_players > SPLIT_OVER_PLAYERS
    ev = base["event"]
    holes_label = f"{(ev.get('format') or '18 Holes').upper()} · {(ev.get('start_type') or 'Tee Times').upper()}"
    if fmt != "practice":
        holes_label = "18 HOLES · TEE TIMES"
    course = ""
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT c.name FROM events e JOIN courses c ON c.course_id = e.course_id "
                         "WHERE e.id = ?", (int(event_id),)).fetchone()
        course = (r[0] if r else None) or (ev.get("course") or "")
    return {
        "event_id": int(event_id), "fmt": fmt, "title": FORMAT_TITLE.get(fmt or "", "LONE STAR CUP"),
        "course": course.upper(), "date": _full_date(date), "first_tee": cards[0]["time"] if cards else "",
        "holes_label": holes_label, "tees": tees, "cards": cards, "alpha": alpha,
        "alpha_cols": alpha_cols, "players": n_players, "split": split,
        "notes": {"always": always, "tee": tee_notes, "alpha": alpha_notes, "badges": badge_notes},
        "gaps": list(dict.fromkeys(gaps)), "log": log, "session": session_id, "preview": bool(preview),
        "file_stub": f"{ev.get('file_stub') or 'LSC'}{('-' + session_id) if session_id else ''}-StarterSheet",
        "team_colors": TEAM_COLOR,
    }
