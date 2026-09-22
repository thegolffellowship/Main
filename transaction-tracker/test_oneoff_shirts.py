"""Shirt sizes are CUSTOMER data, not event data (Kerry 2026-09-22:
"When I add their shirt sizes will that be added to their customer_id?
If not we need to.").

A pick on a one-off roster saves the event's selection to the
oneoff_shirts dial AND writes the canonical customers.shirt_size —
the profile is the durable record. Clearing the event pick leaves the
profile alone, and the roster prefill prefers the canonical size over
digging through order history.
"""

import json
import sqlite3

import pytest

from email_parser import database as db


@pytest.fixture()
def shirt_db(tmp_path):
    p = str(tmp_path / "shirts.db")
    conn = sqlite3.connect(p)
    conn.executescript("""
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT,
                        last_name TEXT, chapter TEXT, shirt_size TEXT);
CREATE TABLE items (id INTEGER PRIMARY KEY, customer_id INT, event_id INT,
                    transaction_status TEXT, shirt_size TEXT, order_date TEXT);
CREATE TABLE expense_transactions (id INTEGER PRIMARY KEY, customer_id INT,
    event_id INT, amount REAL, transaction_type TEXT, transaction_date TEXT,
    notes TEXT, merchant TEXT, review_status TEXT);
CREATE TABLE scoring_rounds (id INTEGER PRIMARY KEY, customer_id INT,
                             event_id INT, tee_id INT, source TEXT);
CREATE TABLE course_tees (tee_id INTEGER PRIMARY KEY, tee_name TEXT,
                          gender TEXT);
""")
    conn.execute("INSERT INTO app_settings VALUES ('oneoff_charges', ?, '')",
                 (json.dumps({"9": {"default": 250, "shirts": True}}),))
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", [
        (1, "Pick", "Me", "Austin", None),
        (2, "Canon", "Ical", "Austin", "XL"),
        (3, "Order", "Only", "Austin", None),
    ])
    conn.executemany(
        "INSERT INTO items (customer_id, event_id, transaction_status,"
        " shirt_size, order_date) VALUES (?,?,?,?,?)",
        [(1, 9, "rsvp_only", None, "2026-09-01"),
         (2, 9, "rsvp_only", None, "2026-09-01"),
         (3, 9, "rsvp_only", None, "2026-09-01"),
         # order history: cid 2 has an OLD differing size, cid 3's only
         # source is order history
         (2, 5, "active", "M", "2026-05-01"),
         (3, 5, "active", "2XL", "2026-06-01")])
    conn.commit()
    conn.close()
    return p


def test_pick_writes_canonical_customer_size(shirt_db):
    out = db.set_oneoff_shirt(9, 1, "L", db_path=shirt_db)
    assert out["canonical_updated"] is True
    with sqlite3.connect(shirt_db) as c:
        assert c.execute("SELECT shirt_size FROM customers WHERE "
                         "customer_id = 1").fetchone()[0] == "L"


def test_clear_keeps_canonical(shirt_db):
    db.set_oneoff_shirt(9, 1, "L", db_path=shirt_db)
    db.set_oneoff_shirt(9, 1, "", db_path=shirt_db)
    with sqlite3.connect(shirt_db) as c:
        assert c.execute("SELECT shirt_size FROM customers WHERE "
                         "customer_id = 1").fetchone()[0] == "L"
    fin = db.get_oneoff_roster_finance(9, db_path=shirt_db)
    sh = fin["players"]["1"]["shirt"]
    assert sh["selected"] is None and sh["known"] == "L"


def test_prefill_prefers_canonical_over_order_history(shirt_db):
    fin = db.get_oneoff_roster_finance(9, db_path=shirt_db)
    # cid 2: canonical XL beats the old "M" on the order
    assert fin["players"]["2"]["shirt"]["known"] == "XL"
    # cid 3: no canonical yet -> order history serves
    assert fin["players"]["3"]["shirt"]["known"] == "2XL"
