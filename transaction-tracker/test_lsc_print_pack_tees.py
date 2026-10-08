"""The Cup's tee table fills a blank tee on the LSC print pack (Kerry
2026-09-28, `lsc_tees`: "Each player plays the tee of his usual 2026
band"). 10/8: David Wetz (DFW, no usual band here) printed "tee 'none'"
on the practice round's cards and Starter Sheet. Only LSC events, only a
BLANK tee; a regular event and a player's own tee are untouched."""
import contextlib
import io
import json
import logging
import sqlite3

import pytest

from email_parser import database as db


@pytest.fixture()
def pdb(tmp_path):
    p = str(tmp_path / "p.db")
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        db.init_db(p)
    logging.disable(logging.NOTSET)
    c = sqlite3.connect(p)
    course = c.execute("INSERT INTO courses (name, status) VALUES ('The Hideout Golf Club','active') "
                       "RETURNING course_id").fetchone()[0]
    for name, band in (("Blue", "<50"), ("White", "50-64")):
        tid = c.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, rating, slope, "
                        "tgf_bands, source) VALUES (?,?,'M',18,71.7,129,?,'admin') RETURNING tee_id",
                        (course, name, band)).fetchone()[0]
        for h in range(1, 19):
            c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) "
                      "VALUES (?,?,4,350,?)", (tid, h, h))
    for eid, nm in ((3329, "LONE STAR CUP | The Hideout"), (3330, "LSC PRACTICE ROUND | The Hideout"),
                    (3304, "s9.25 X")):
        c.execute("INSERT INTO events (id, item_name, event_date, course_id, chapter, format) "
                  "VALUES (?,?,'2026-10-09',?,'TGF','18 Holes')", (eid, nm, course))
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (672,'David','Wetz')")
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (7,'Matt','Jenkins')")
    c.commit()
    c.close()
    db.set_app_setting("lsc_matches", json.dumps({"event_id": 3329, "sessions": []}), db_path=p)
    db.set_app_setting("oneoff_charges", json.dumps(
        {"3329": {"addons": [{"key": "friday", "event_id": 3330}]}}), db_path=p)
    db.set_app_setting("lsc_tees", json.dumps({"3329": {"players": {
        "672": {"band": "<50"}, "7": {"band": "<50"}}}}), db_path=p)
    for eid in (3330, 3304):
        db.save_event_pairings(eid, {"18": [{"group_num": 1, "slot_label": "1:30 PM", "players": [
            {"name": "Matt Jenkins", "cart_pos": 1, "customer_id": 7, "tee_choice": "50-64"},
            {"name": "David Wetz", "cart_pos": 2, "customer_id": 672, "tee_choice": None}]}]},
            db_path=p)
    return p


def _tees(pack):
    return {pl["customer_id"]: pl.get("tee_choice") for g in pack["groups"] for pl in g["players"]}


def test_the_practice_round_fills_a_blank_tee_from_the_cup_table(pdb):
    t = _tees(db.get_event_print_pack(3330, db_path=pdb))
    assert t[672] == "<50"
    assert t[7] == "50-64"          # his own tee is never replaced


def test_a_regular_event_is_untouched(pdb):
    assert not _tees(db.get_event_print_pack(3304, db_path=pdb))[672]
