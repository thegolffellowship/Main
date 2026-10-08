"""The Lone Star Cup HANDICAP LOCK (Kerry 2026-10-07, CoS #1389: "Handicaps
should lock now. They won't change.").

`lsc_handicap_lock` = {"<event_id>": {"players": {"<cid>": {index, tee, ch}}}}
holds each player's index and course handicap of record. The Sunday skins
flights read the locked INDEX over the computed one (James Wilson Jr: locked
12.4 = Flight 2; his live index had drifted to 10.8 = Flight 1). The cup seed
reads the locked CH as the playing handicap (test_score_entry.py).
"""

import contextlib
import io
import json
import logging
import sqlite3

import pytest

from email_parser import database as db
from email_parser import lsc_cup


@pytest.fixture()
def cup_db(tmp_path):
    p = str(tmp_path / "lock.db")
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        db.init_db(p)
    logging.disable(logging.NOTSET)
    c = sqlite3.connect(p)
    c.execute("INSERT INTO events (id, item_name, event_date) "
              "VALUES (3329, 'LONE STAR CUP | The Hideout', '2026-10-10')")
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) "
              "VALUES (306, 'James', 'Wilson')")
    c.commit()
    c.close()
    db.set_starting_handicap(306, 10.8, set_by="test", db_path=p)
    return p


def _ctx(p):
    with db._connect(p) as conn:
        return lsc_cup._skins_ctx(conn, {"event_id": 3329}, p)


def test_without_a_lock_the_computed_index_flights(cup_db):
    assert _ctx(cup_db)["index"].get(306) == 10.8


def test_the_locked_index_wins_for_the_sunday_flights(cup_db):
    db.set_app_setting("lsc_handicap_lock", json.dumps({"3329": {"players": {
        "306": {"index": 12.4, "tee": "Red", "ch": 8}}}}), cup_db)
    assert _ctx(cup_db)["index"].get(306) == 12.4


def test_a_bad_lock_never_breaks_the_read(cup_db):
    db.set_app_setting("lsc_handicap_lock", "{not json", cup_db)
    assert _ctx(cup_db)["index"].get(306) == 10.8
