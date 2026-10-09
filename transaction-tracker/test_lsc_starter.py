"""THE LONE STAR CUP STARTER SHEET (design-claude #1481, Kerry-approved;
Kerry 10/8: "Check mail directive for LSC Starter Sheets from Claude Design
and incorporate now"). Pins CD's §7 math spot-checks, the match numbering
through the weekend, the A-first Chapman pairs, only-used tees, the solid
new teal, pagination, and the render of all four formats."""
import contextlib
import io
import json
import logging
import os
import sqlite3

import pytest

from email_parser import database as db
from email_parser import lsc_starter

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture()
def sdb(tmp_path):
    p = str(tmp_path / "s.db")
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        db.init_db(p)
    logging.disable(logging.NOTSET)
    c = sqlite3.connect(p)
    course = c.execute("INSERT INTO courses (name, status) VALUES ('The Hideout Golf Club & Resort','active') "
                       "RETURNING course_id").fetchone()[0]
    for nm, band, g in (("Blue", "<50", "M"), ("White", "50-64", "M"), ("Red", "65+", "M"), ("Teal", "Forward", "F")):
        tid = c.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, rating, slope, tgf_bands, "
                        "source) VALUES (?,?,?,18,71.7,129,?,'admin') RETURNING tee_id", (course, nm, g, band)).fetchone()[0]
        for h in range(1, 19):
            c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) "
                      "VALUES (?,?,4,350,?)", (tid, h, h))
    for cid, f, l in ((7, "Matt", "Jenkins"), (13, "Kerry", "Niester"), (88, "Jeff", "Young"), (438, "Chris", "Cannon")):
        c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, f, l))
    c.execute("INSERT INTO events (id, item_name, event_date, course_id, format, start_type, side_game_fee) "
              "VALUES (3329, 'LONE STAR CUP | The Hideout', '2026-10-10', ?, '18 Holes', 'Tee Times', 0)", (course,))
    c.commit()
    c.close()
    # CD #1481 §7's sample: Jenkins 3, Niester 1 (Austin) v Young 2, Cannon 8 (SA)
    lock = {"7": ("austin", 3), "13": ("austin", 1), "88": ("sa", 2), "438": ("sa", 8)}
    db.set_app_setting("lsc_handicap_lock", json.dumps({"3329": {"players": {
        k: {"name": k, "team": t, "ch": ch, "index": float(ch), "tee": "Blue"} for k, (t, ch) in lock.items()}}}), db_path=p)
    db.set_app_setting("lsc_tees", json.dumps({"3329": {"bands": {"<50": "Blue"}, "players": {
        k: {"band": "<50"} for k in lock}}}), db_path=p)
    db.set_app_setting("lsc_matches", json.dumps({"event_id": 3329, "sessions": [
        {"id": "sat-am", "format": "fourball", "date": "2026-10-10", "n_matches": 7,
         "matches": [{"id": "SAT-AM-1", "tee_time": "1:30", "austin": [7, 13], "sa": [88, 438]}]},
        {"id": "sat-pm", "format": "chapman", "date": "2026-10-10", "n_matches": 7,
         "matches": [{"id": "SAT-PM-1", "tee_time": "1:30", "austin": [7, 13], "sa": [438, 88]}]},
        {"id": "sun", "format": "singles", "date": "2026-10-11", "n_matches": 14,
         "matches": [{"id": "SUN-1", "tee_time": "1:30", "austin": [7], "sa": [438]},
                     {"id": "SUN-2", "tee_time": "1:30", "austin": [13], "sa": [88]}]}]}), db_path=p)
    return p


def _rows(s):
    return [r for b in s["cards"][0]["blocks"] for r in b["rows"]]


def test_fourball_spot_check(sdb):
    s = lsc_starter.build(3329, "sat-am", db_path=sdb)
    assert s["gaps"] == [] and s["title"] == "FOURBALL" and s["date"] == "Saturday, October 10, 2026"
    got = {r["first"]: (r["vals"][1], r["off"]) for r in _rows(s)}
    assert got == {"Matt": ("3", "2"), "Kerry": ("1", "0"), "Jeff": ("2", "1"), "Chris": ("7", "6")}
    assert s["cards"][0]["blocks"][0]["bar"] == "MATCH 1"
    assert s["cards"][0]["cols"] == ["TEE", "IDX", "HCP", "OFF"] and s["first_tee"] == "1:30 PM"


def test_foursomes_spot_check_a_first(sdb):
    s = lsc_starter.build(3329, "sat-pm", db_path=sdb)
    rows = _rows(s)
    # A = the lower PH, listed first in each pair
    assert [(r["first"], r["ab"], r["vals"][0]) for r in rows] == [
        ("Kerry", "A", "0.6"), ("Matt", "B", "1.2"), ("Jeff", "A", "1.2"), ("Chris", "B", "3.2")]
    assert (rows[0]["merge"]["sum"], rows[0]["merge"]["team"], rows[0]["merge"]["off"]) == ("1.8", "2", "0")
    assert (rows[2]["merge"]["sum"], rows[2]["merge"]["team"], rows[2]["merge"]["off"]) == ("4.4", "4", "2")
    assert s["cards"][0]["blocks"][0]["bar"] == "MATCH 8"            # numbering runs through the weekend
    assert s["alpha_cols"] == ["TEE", "IDX", "A/B", "PH"]


def test_singles_spot_check_two_matches(sdb):
    s = lsc_starter.build(3329, "sun", db_path=sdb)
    blocks = s["cards"][0]["blocks"]
    assert [b["bar"] for b in blocks] == ["MATCH 15", "MATCH 16"]
    assert [(r["first"], r["off"]) for r in blocks[0]["rows"]] == [("Matt", "0"), ("Chris", "5")]
    assert [(r["first"], r["off"]) for r in blocks[1]["rows"]] == [("Kerry", "0"), ("Jeff", "1")]


def test_only_the_tees_on_the_sheet_and_one_page_for_a_small_field(sdb):
    s = lsc_starter.build(3329, "sat-am", db_path=sdb)
    assert [t["band"] for t in s["tees"]] == ["<50"]
    assert s["split"] is False and s["players"] == 4


def test_the_sheet_renders_every_format(sdb):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(os.path.join(HERE, "templates")))
    for sid, title in (("sat-am", "FOURBALL"), ("sat-pm", "FOURSOMES"), ("sun", "SINGLES")):
        html = env.get_template("lsc_starter_sheet.html").render(s=lsc_starter.build(3329, sid, db_path=sdb))
        assert f'<div class="fmt">{title}</div>' in html and "lsc-logo-dark.png" in html
        assert "thegolffellowship.com" in html and "TEE SHEET" in html and "ALPHABETICAL" in html


def test_new_teal_is_solid_when_women_have_their_own_tee():
    out = db._sheet_tee_key(
        [{"band": "65+", "color": "#C0392B", "ring": False},
         {"band": "Forward", "color": "#0F766E", "ladies": True, "ring": True}],
        [{"players": [{"tee_choice": "Forward"}]}])
    assert [t["band"] for t in out["tee_legend_sheet"]] == ["Forward"]       # only the tee in use
    assert out["tee_swatches_sheet"]["Forward"] == "#0E8A9A" and out["tee_ring_sheet"]["Forward"] is False
