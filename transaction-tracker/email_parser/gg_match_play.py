"""Golf Genius Match Play detail parser (pure, no DB/Flask).

GG's match-play game is a v2tournaments tournament whose per-match rows expand
(XHR) to `/tournaments2/details/<aggregate_id>`, returning a JS-wrapped HTML
fragment: `window.glg.tournaments2.toggleDetails("<agg>", "<html>", ...)`.

That fragment is the AUTHORITATIVE source for a NET match:
  * `starting_hole_mark` class marks the hole the match STARTED on (shotgun).
  * two `net-line` rows (`data-net-name`) carry each player's per-hole GROSS
    (`.score_box`) and per-hole handicap strokes (the `●` count inside
    `.handicap-dots`) — these are the NET dots.
  * a `match-lead` row carries GG's own per-hole winner flag
    (`data-winner` 1 = first net-line player, 2 = second, 0 = halved) and the
    running "X up" text.

Reading the winner flags IN PLAY ORDER (starting at `starting_hole_mark`, then
wrapping) reproduces GG's recorded winner + margin exactly — including the
close-out hole — because it IS GG's computation. This module never decides a
winner from raw gross; it reads GG's per-hole verdict and only sequences it.

`parse_match_play_detail(fragment)` returns a dict; the caller (database.py)
aligns the two GG players to our cmp_matches row and snapshots the result.
"""
from __future__ import annotations
import re
import html as _html

_DOT = "●"  # ● filled circle used for a handicap stroke


def _unwrap_toggle_details(fragment: str) -> str:
    """Pull the inner HTML out of
    window.glg.tournaments2.toggleDetails("<agg>", "<html>", ...).
    The HTML is a JS double-quoted string with \\n / \\" / \\' escapes."""
    if "toggleDetails" not in fragment:
        return fragment
    # The first arg is the aggregate id; the second is the HTML string.
    m = re.search(r'toggleDetails\(\s*"[^"]*"\s*,\s*"', fragment)
    if not m:
        return fragment
    i = m.end()  # just past the opening quote of the HTML arg
    out, n = [], len(fragment)
    while i < n:
        c = fragment[i]
        if c == "\\" and i + 1 < n:
            nxt = fragment[i + 1]
            out.append({"n": "\n", "t": "\t", '"': '"', "'": "'",
                        "\\": "\\", "/": "/"}.get(nxt, nxt))
            i += 2
            continue
        if c == '"':
            break
        out.append(c)
        i += 1
    return "".join(out)


def _cells(row_html: str):
    """Yield (class_attr, inner_html) for each <td> in a row."""
    for m in re.finditer(r"<td\b([^>]*)>(.*?)</td>", row_html, re.S):
        attrs = m.group(1)
        cls = ""
        cm = re.search(r"class=['\"]([^'\"]*)['\"]", attrs)
        if cm:
            cls = cm.group(1)
        yield attrs, cls, m.group(2)


def _hole_no(cls: str):
    m = re.search(r"\bhole(\d+)\b", cls)
    return int(m.group(1)) if m else None


def parse_match_play_detail(fragment: str) -> dict | None:
    """Parse one GG match-play detail fragment. Returns:
      {
        aggregate_id, players:[{name, handicap}], start_hole,
        holes:[{hole, order, p1_gross, p2_gross, p1_strokes, p2_strokes,
                winner}],           # winner: 1|2|0 (p1/p2/halved); None if unplayed
        gg_winner_idx: 1|2|None, gg_winner_name, gg_margin ('5&4'|'2 UP'|'AS'),
        closed_at_order, thru
      }
    winner/gross/strokes are aligned to players[0]=p1, players[1]=p2 in the
    order the two net-line rows appear in GG. None if the fragment isn't a
    parseable match."""
    doc = _unwrap_toggle_details(fragment)
    agg = None
    am = re.search(r"data-aggregate-id=['\"](\d+)['\"]", doc)
    if am:
        agg = am.group(1)

    # start hole — from the tee header row's starting_hole_mark cell
    start_hole = None
    for attrs, cls, inner in _cells(doc):
        if "starting_hole_mark" in cls and "hole-lead" not in cls \
                and "score" not in cls:
            txt = re.sub(r"<[^>]+>", "", inner)
            txt = _html.unescape(txt).strip()
            if txt.isdigit():
                start_hole = int(txt)
                break

    # two net-line rows
    net_rows = re.findall(
        r"<tr\b[^>]*class=['\"][^'\"]*net-line[^'\"]*['\"][^>]*"
        r"data-net-name=['\"]([^'\"]*)['\"][^>]*>(.*?)</tr>", doc, re.S)
    if len(net_rows) < 2:
        return None
    net_rows = net_rows[:2]

    players, per_player_holes = [], []
    col_holes = None                      # column order of holes (from net row)
    for name, row_html in net_rows:
        name = _html.unescape(name).strip()
        # handicap from the name link "NAME (H)"
        hcp = None
        hm = re.search(re.escape(name) + r"\s*\((\+?\d+)\)", doc)
        if hm:
            v = hm.group(1)
            hcp = -int(v[1:]) if v.startswith("+") else int(v)
        holes, order_cols = {}, []
        for attrs, cls, inner in _cells(row_html):
            hn = _hole_no(cls)
            if hn is None or "score" not in cls:
                continue
            order_cols.append(hn)
            sb = re.search(r"score_box['\"]?\s*>\s*(\d+)", inner)
            gross = int(sb.group(1)) if sb else None
            dots = 0
            dm = re.search(r"handicap-dots['\"]?\s*>(.*?)</div>", inner, re.S)
            if dm:
                dots = dm.group(1).count(_DOT)
            holes[hn] = {"gross": gross, "strokes": dots}
        if col_holes is None:
            col_holes = order_cols
        players.append({"name": name, "handicap": hcp})
        per_player_holes.append(holes)

    # match-lead row → per-hole winner flag. The lead cells carry class
    # 'hole-lead' with NO hole number (positional); they align 1:1, in order,
    # with the net rows' score columns (col_holes). Summary cells
    # (out/in/total_match_result) are NOT 'hole-lead', so filtering to
    # 'hole-lead' keeps only the per-hole columns, preserving alignment.
    lead_holes = {}
    for m in re.finditer(r"<tr\b[^>]*class=['\"][^'\"]*match-lead[^'\"]*['\"]"
                         r"[^>]*>(.*?)</tr>", doc, re.S):
        row = m.group(1)
        lead_cells = []
        for attrs, cls, inner in _cells(row):
            if "hole-lead" not in cls:
                continue
            wm = re.search(r"data-winner=['\"](\d+)['\"]", attrs)
            lead_cells.append(int(wm.group(1)) if wm else None)
        if any(v is not None for v in lead_cells) and col_holes:
            for i, hn in enumerate(col_holes):
                if i < len(lead_cells):
                    lead_holes[hn] = lead_cells[i]
            break

    p1h, p2h = per_player_holes
    all_holes = sorted(set(p1h) | set(p2h))
    if not all_holes:
        return None
    if start_hole is None or start_hole not in all_holes:
        start_hole = all_holes[0]

    # play order: start_hole, then ascending wrap
    idx = all_holes.index(start_hole)
    play_order = all_holes[idx:] + all_holes[:idx]

    holes_out, order = [], 0
    for hn in play_order:
        order += 1
        w = lead_holes.get(hn)
        holes_out.append({
            "hole": hn, "order": order,
            "p1_gross": p1h.get(hn, {}).get("gross"),
            "p2_gross": p2h.get(hn, {}).get("gross"),
            "p1_strokes": p1h.get(hn, {}).get("strokes", 0),
            "p2_strokes": p2h.get(hn, {}).get("strokes", 0),
            "winner": w,
        })

    # derive GG winner + margin by walking the winner flags in play order
    lead = 0            # + => p1 ahead, - => p2 ahead
    closed_at = None
    played = [h for h in holes_out if h["winner"] is not None]
    n_played = len(played)
    for i, h in enumerate(played):
        if h["winner"] == 1:
            lead += 1
        elif h["winner"] == 2:
            lead -= 1
        remaining = n_played - (i + 1)
        if closed_at is None and abs(lead) > remaining:
            closed_at = i + 1
            break
    if closed_at is not None:
        to_play = n_played - closed_at
        margin = f"{abs(lead)}&{to_play}" if to_play > 0 else f"{abs(lead)} UP"
        thru = closed_at
    else:
        margin = "AS" if lead == 0 else f"{abs(lead)} UP"
        thru = n_played
    gg_winner_idx = 1 if lead > 0 else (2 if lead < 0 else None)
    gg_winner_name = (players[0]["name"] if gg_winner_idx == 1
                      else players[1]["name"] if gg_winner_idx == 2 else None)

    return {
        "aggregate_id": agg,
        "players": players,
        "start_hole": start_hole,
        "holes": holes_out,
        "gg_winner_idx": gg_winner_idx,
        "gg_winner_name": gg_winner_name,
        "gg_margin": margin,
        "closed_at_order": closed_at,
        "thru": thru,
        "n_holes": len(all_holes),
    }
