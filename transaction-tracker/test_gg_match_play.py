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


if __name__ == "__main__":
    test_reyes_jenkins()
