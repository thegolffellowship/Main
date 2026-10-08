"""A starting handicap reaches the BY-CUSTOMER index map even when the
player's name already sits in handicap_rounds with no handicap link.

David Wetz (672), 2026-10-07: his old DFW rounds (2022 to March 2025, all
outside the lookback) are in handicap_rounds under his name and nothing
links that name to his customer row. Kerry's temporary 7.7 (#1342) was
stored, the starting-handicap merge found him by NAME and put 7.7 on that
row, but left its customer_id empty; seen_cids then skipped the
placeholder append that would have carried it. Every reader keyed on
customer_id (`_handicap_index_18_by_customer`: score-entry playing
handicaps, the Cup seed, the Sunday skins flights) had no index for him.
"""

import contextlib
import io
import logging
import sqlite3

import pytest

from email_parser import database as db


@pytest.fixture()
def hdb(tmp_path):
    p = str(tmp_path / "h.db")
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        db.init_db(p)
    logging.disable(logging.NOTSET)
    c = sqlite3.connect(p)
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) "
              "VALUES (672, 'David', 'Wetz')")
    cols = {r[1] for r in c.execute("PRAGMA table_info(handicap_rounds)")}
    for i, (d, adj) in enumerate([(9.0, 44), (10.0, 45), (11.0, 46)]):
        row = {"player_name": "David Wetz", "round_date": f"2023-05-0{i + 1}",
               "differential": d, "adjusted_score": adj, "rating": 35.0,
               "slope": 120, "course_name": "Riverside", "tee_name": "Blue"}
        row = {k: v for k, v in row.items() if k in cols}
        c.execute(f"INSERT INTO handicap_rounds ({', '.join(row)}) "
                  f"VALUES ({', '.join('?' * len(row))})", list(row.values()))
    c.commit()
    c.close()
    db.set_starting_handicap(672, 7.7, set_by="test", db_path=p)
    return p


def test_unlinked_old_rounds_still_read_the_starting_index_by_customer(hdb):
    rows = [p for p in db.get_all_handicap_players(hdb)
            if p["player_name"] == "David Wetz"]
    assert len(rows) == 1, rows
    assert rows[0]["handicap_index_18"] == 7.7
    assert rows[0]["handicap_source"] == "starting"
    assert rows[0]["customer_id"] == 672
    # the roster's index map keys on customer_name (Kerry 10/8: "David Wetz
    # handicap still not showing")
    assert rows[0]["customer_name"] == "David Wetz"
    assert db._handicap_index_18_by_customer(hdb).get(672) == 7.7


def test_as_of_lock_reads_it_too(hdb):
    # The Cup reads the index as of its own date once it has teed off.
    assert db._handicap_index_18_by_customer(hdb, as_of="2026-10-10").get(672) == 7.7
