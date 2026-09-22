"""Venmo never guesses an event (Kerry 2026-09-22, verbatim: "Venmo
should never automatically go to an event unless it's memo is
specifically something we created and matched. The only caveat is the
Lone Star cup. Any others should be earmarked for review somewhere
with options for tagging appropriately.")

The registration-based fallback (most recent event the payer is
registered on) put Franz's "Golf" on Avery Ranch and cup money on
Forest Creek. Now: explicit memo match, then the venmo_event_keywords
dial (the cup caveat as data), else NO event and the row stays pending
in the Accounting review queue.
"""

import json
import os
import sqlite3

import pytest

from email_parser.expense_parser import match_event_from_keywords


@pytest.fixture()
def kw_conn(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "kw.db"))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT);
""")
    conn.execute("INSERT INTO events VALUES (3329, "
                 "'LONE STAR CUP | The Hideout')")
    conn.execute("INSERT INTO app_settings VALUES "
                 "('venmo_event_keywords', ?)",
                 (json.dumps({"3329": ["lone star", "lonestar", "lsc",
                                       "hideout"]}),))
    yield conn
    conn.close()


def test_cup_keywords_match_case_insensitively(kw_conn):
    for memo in ("Hideout", "Golf hideout", "LoneStar Cup",
                 "100 balance for lone star cup"):
        assert match_event_from_keywords(memo, kw_conn) == \
            "LONE STAR CUP | The Hideout", memo


def test_plain_memo_matches_nothing(kw_conn):
    assert match_event_from_keywords("Golf", kw_conn) is None
    assert match_event_from_keywords("", kw_conn) is None


def test_no_dial_means_no_match(kw_conn):
    kw_conn.execute("DELETE FROM app_settings")
    assert match_event_from_keywords("Hideout", kw_conn) is None


def test_registration_fallback_is_gone_from_the_inbox():
    # The class guard: the inbox pipeline must not re-grow a
    # registration-based event guess for P2P money.
    src = open(os.path.join(os.path.dirname(__file__), "app.py")).read()
    assert "match_event_from_customer" not in src
