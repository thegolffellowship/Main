"""Tests for the GG match-play detail parser against the REAL a9.16
REYES vs JENKINS fragment structure (Austin, tournament 4740049,
aggregate 2326119577). Known-correct GG result: match started on HOLE 2,
JENKINS won 5&4, REYES (8) received a stroke on all holes but #5."""
from email_parser.gg_match_play import parse_match_play_detail

# Real values read off GG's own detail fragment.
REYES = {1: 6, 2: 7, 3: 6, 4: 7, 5: 6, 6: 6, 7: 6, 8: 5, 9: 5}
REYES_DOTS = {1, 2, 3, 4, 6, 7, 8, 9}          # stroke on all but hole 5
JENKINS = {1: 4, 2: 5, 3: 4, 4: 5, 5: 3, 6: 2, 7: 4, 8: 4, 9: 5}
WINNER = {1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2, 8: 0, 9: 1}  # 2=JENKINS
START = 2


def _score_cell(hole, gross, dots, start):
    mark = " starting_hole_mark" if hole == start else ""
    dot_html = (" ●\n" * dots)
    return (f"<td class='hole{hole} score{mark}'>"
            f"<div class='handicap-dots'>\n{dot_html}</div>"
            f"<div class='single-score'><span class='score_box'>\n{gross}\n"
            f"</span></div></td>")


def _net_row(name, hcp, scores, dots, start):
    cells = "".join(_score_cell(h, scores[h], 1 if h in dots else 0, start)
                    for h in range(1, 10))
    return (f"<tr class='net-line' data-net-name='{name}'>"
            f"<td class='name left_aligned'>"
            f"<a class=\"expand-tee-details\" href=\"/x\">{name} ({hcp})</a></td>"
            f"{cells}</tr>")


def _build_fragment():
    hdr = "".join(
        (f"<td class='starting_hole_mark'>&nbsp;{h}</td>" if h == START
         else f"<td class=''>&nbsp;{h}</td>") for h in range(1, 10))
    lead = "".join(
        f"<td class='hole-lead{' starting_hole_mark' if h == START else ''}' "
        f"data-winner='{WINNER[h]}'>x up</td>" for h in range(1, 10))
    inner = (
        "<table class='detail_table' data-aggregate-id='2326119577'>"
        f"<tr class='header_row tee_header_row'><td></td>{hdr}</tr>"
        + _net_row("REYES, Isaac", 8, REYES, REYES_DOTS, START)
        + _net_row("JENKINS, Matt", 0, JENKINS, set(), START)
        + f"<tr class='match-lead' data-color-display='1'>"
          f"<td class='left_aligned match_text'>Match</td>{lead}</tr>"
        + "</table>")
    esc = inner.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'window.glg.tournaments2.toggleDetails("2326119577", "{esc}", "");'


def test_reyes_jenkins():
    r = parse_match_play_detail(_build_fragment())
    assert r is not None
    assert r["aggregate_id"] == "2326119577"
    assert r["start_hole"] == START, r["start_hole"]
    assert [p["name"] for p in r["players"]] == ["REYES, Isaac", "JENKINS, Matt"]
    assert r["players"][0]["handicap"] == 8
    assert r["players"][1]["handicap"] == 0
    # play order starts at hole 2 and wraps
    assert [h["hole"] for h in r["holes"]][:3] == [2, 3, 4]
    assert r["holes"][-1]["hole"] == 1
    # GG result reproduced
    assert r["gg_winner_name"] == "JENKINS, Matt", r["gg_winner_name"]
    assert r["gg_margin"] == "5&4", r["gg_margin"]
    assert r["closed_at_order"] == 5
    # NET dots: REYES stroked on all holes but #5
    dots = {h["hole"]: h["p1_strokes"] for h in r["holes"]}
    assert dots[5] == 0 and all(dots[h] == 1 for h in REYES_DOTS), dots
    # gross carried through
    g = {h["hole"]: (h["p1_gross"], h["p2_gross"]) for h in r["holes"]}
    assert g[6] == (6, 2) and g[2] == (7, 5)
    print("PASS reyes_jenkins: start=hole2, JENKINS 5&4, REYES dots 8/9")


# ── Youngs v Jenkins (a9.19 Teravista, Austin SF2): 9-hole match decided
# 2&1 ON hole 8 by a NET halve (Youngs strokes hole 8: gross 6 − 1 = 5 vs
# Jenkins 5); hole 9 never posted. The old flag-count walk closed this at
# hole 7 — "2 up with one POSTED flag left" — greying the hole that
# actually decided the match. 2 up with two MATCH holes to play is dormie.
YJ_JENKINS = {1: 3, 2: 4, 3: 3, 4: 5, 5: 3, 6: 6, 7: 4, 8: 5}
YJ_YOUNGS = {1: 3, 2: 4, 3: 4, 4: 4, 5: 3, 6: 4, 7: 3, 8: 6}
YJ_WINNER = {1: 0, 2: 0, 3: 1, 4: 2, 5: 0, 6: 2, 7: 2, 8: 0}  # 1=JENKINS


def _score_cell_opt(hole, gross, dots, start):
    """Like _score_cell but renders an EMPTY cell (no score_box) for an
    unposted hole — GG's card keeps the column, blank."""
    mark = " starting_hole_mark" if hole == start else ""
    dot_html = (" ●\n" * dots)
    inner = ("" if gross is None else
             f"<div class='single-score'><span class='score_box'>\n{gross}\n"
             f"</span></div>")
    return (f"<td class='hole{hole} score{mark}'>"
            f"<div class='handicap-dots'>\n{dot_html}</div>{inner}</td>")


def _build_yj_fragment():
    start = 1
    hdr = "".join(
        (f"<td class='starting_hole_mark'>&nbsp;{h}</td>" if h == start
         else f"<td class=''>&nbsp;{h}</td>") for h in range(1, 10))

    def net_row(name, hcp, scores, dots):
        cells = "".join(_score_cell_opt(h, scores.get(h),
                                        1 if h in dots else 0, start)
                        for h in range(1, 10))
        return (f"<tr class='net-line' data-net-name='{name}'>"
                f"<td class='name left_aligned'>"
                f"<a class=\"expand-tee-details\" href=\"/x\">{name} ({hcp})</a></td>"
                f"{cells}</tr>")

    lead = "".join(
        f"<td class='hole-lead'"
        + (f" data-winner='{YJ_WINNER[h]}'" if h in YJ_WINNER else "")
        + ">x up</td>" for h in range(1, 10))
    inner = (
        "<table class='detail_table' data-aggregate-id='999'>"
        f"<tr class='header_row tee_header_row'><td></td>{hdr}</tr>"
        + net_row("JENKINS, Matthew", 0, YJ_JENKINS, set())
        + net_row("YOUNGS, Luke", 1, YJ_YOUNGS, {8})
        + f"<tr class='match-lead' data-color-display='1'>"
          f"<td class='left_aligned match_text'>Match</td>{lead}</tr>"
        + "</table>")
    esc = inner.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'window.glg.tournaments2.toggleDetails("999", "{esc}", "");'


def test_youngs_jenkins_halve_clinch():
    r = parse_match_play_detail(_build_yj_fragment())
    assert r is not None
    assert r["n_holes"] == 9
    # the match was ALIVE through hole 7 (dormie) and closed ON hole 8
    assert r["closed_at_order"] == 8, r["closed_at_order"]
    assert r["thru"] == 8
    assert r["gg_margin"] == "2&1", r["gg_margin"]
    assert r["gg_winner_name"] == "YOUNGS, Luke", r["gg_winner_name"]
    # hole 8 carries the deciding NET halve flag + Youngs' stroke dot
    h8 = next(h for h in r["holes"] if h["hole"] == 8)
    assert h8["winner"] == 0 and h8["p2_strokes"] == 1
    # hole 9 unposted: no scores, no flag
    h9 = next(h for h in r["holes"] if h["hole"] == 9)
    assert h9["p1_gross"] is None and h9["winner"] is None
    print("PASS youngs_jenkins: alive thru 7, closed ON 8, YOUNGS 2&1")


def test_rederive_heals_frozen_snapshot():
    """A snapshot frozen with the old flag-count summary self-heals."""
    from email_parser.gg_match_play import rederive_close_out
    d = parse_match_play_detail(_build_yj_fragment())
    d.update({"closed_at_order": 7, "thru": 7})          # the old bad summary
    assert rederive_close_out(d) is True
    assert d["closed_at_order"] == 8 and d["thru"] == 8
    assert d["gg_margin"] == "2&1" and d["gg_winner_name"] == "YOUNGS, Luke"
    assert rederive_close_out(d) is False                # idempotent
    print("PASS rederive: frozen closed_at 7 healed to 8, idempotent")


if __name__ == "__main__":
    test_reyes_jenkins()
    test_youngs_jenkins_halve_clinch()
    test_rederive_heals_frozen_snapshot()
