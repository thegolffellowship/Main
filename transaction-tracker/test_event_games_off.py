"""NO GAMES AT THIS EVENT (Kerry 2026-10-08, LSC practice round 3330: "No
games this event, so anything related to them like Cart Net should hide or
turn off"). The event's own price is the switch: an INCLUDED GAMES fee that
is SET and $0 means no Team/Cart Net, no CTP, no Hole-in-One slice. Unset
(NULL) is not off. The 36-hole championship keeps its own HIO rule."""
import contextlib
import io
import logging
import os
import sqlite3

import pytest

from email_parser import database as db


def test_the_switch_reads_the_price():
    off = db.event_games_off
    assert off({"side_game_fee": 0.0})
    assert off({"side_game_fee": 0, "side_game_fee_9": 0, "side_game_fee_18": None})
    assert not off({"side_game_fee": 14.0})
    assert not off({"side_game_fee": None})                       # unset is not off
    assert not off({"side_game_fee": 0, "side_game_fee_18": 14})  # a combo with an 18 fee
    assert not off(None)


@pytest.fixture()
def gdb(tmp_path):
    p = str(tmp_path / "g.db")
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        db.init_db(p)
    logging.disable(logging.NOTSET)
    c = sqlite3.connect(p)
    c.execute("INSERT INTO events (id, item_name, event_date, side_game_fee, format) VALUES "
              "(3330, 'LSC PRACTICE ROUND | The Hideout', '2026-10-01', 0.0, '18 Holes')")
    c.execute("INSERT INTO events (id, item_name, event_date, side_game_fee, format) VALUES "
              "(3304, 's18.9 GAMES ON', '2026-10-01', 14.0, '18 Holes')")
    for eid, name in ((3330, "LSC PRACTICE ROUND | The Hideout"), (3304, "s18.9 GAMES ON")):
        for i in range(15):
            c.execute("INSERT INTO items (customer, item_name, event_id, transaction_status, order_date, "
                      "order_id, email_uid, merchant, holes) VALUES (?,?,?,'active','2026-09-20',?,?,"
                      "'GoDaddy','18')", (f"P{eid}x{i} Last", name, eid, f"R{eid}{i}", f"m-{eid}-{i}"))
    c.commit()
    c.close()
    return p


def test_the_hio_pot_takes_nothing_from_a_no_games_event(gdb):
    pot = db.get_hio_pot(db_path=gdb)
    names = [e["event"] for e in pot["events"]]
    assert "LSC PRACTICE ROUND | The Hideout" not in names
    assert "s18.9 GAMES ON" in names            # the same field with games still contributes


def test_no_ctp_at_a_no_games_event(gdb):
    rep = db.event_proximity_report(3330, db_path=gdb)
    assert rep["contests"] == [] and "No games at this event" in rep["notes"][0]


def test_the_games_sheet_says_no_games(gdb):
    from email_parser.games_sheet import build_games_sheet
    gs = build_games_sheet(3330, games={}, db_path=gdb)
    assert "No games at this event" in gs["error"]


def test_the_page_and_reports_follow_the_same_switch():
    here = os.path.dirname(os.path.abspath(__file__))
    ev = open(os.path.join(here, "templates", "events.html")).read()
    assert "function eventGamesOff(ev)" in ev and "if (eventGamesOff(ev)) {" in ev
    assert "if (!eventGamesOff(ev)) {" in ev          # REPORTS hides the game reports
    ss = open(os.path.join(here, "templates", "starter_sheet.html")).read()
    assert ss.count("pack.get('games_off')") >= 3
