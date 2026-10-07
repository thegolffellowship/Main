"""The events-list PAID badge for a one-off team event counts the TEAM
from the money picture (Kerry 2026-10-04: "Can you mark the tracker
accordingly in the badge? It shouldn't only be shown as one paid.").

The Lone Star Cup roster is RSVP placeholders plus Venmo/Zelle money,
so `registrations` (active rows) reads 1. `oneoff_paid` counts roster
players whose balance is settled; money from someone OFF the team (a
declined player's unrefunded deposit, an unexplained payment) is not a
paid player. The phone card reads the same field as the desktop table.
"""

import contextlib
import io
import json
import logging
import sqlite3
from pathlib import Path

import pytest

from email_parser import database as db

EV = "LONE STAR CUP | The Hideout"


@pytest.fixture()
def cup_db(tmp_path):
    p = str(tmp_path / "cup.db")
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        db.init_db(p)
    logging.disable(logging.NOTSET)
    c = sqlite3.connect(p)
    # Production carries expense_transactions.event_id; a fresh init_db
    # creates the table after its event_id ALTER runs, so add it here.
    if "event_id" not in [r[1] for r in c.execute(
            "PRAGMA table_info(expense_transactions)")]:
        c.execute("ALTER TABLE expense_transactions ADD COLUMN event_id INTEGER")
    c.execute("INSERT INTO events (id, item_name, event_date) "
              "VALUES (3329, ?, '2026-10-10')", (EV,))
    for cid, nm in [(1, "Paid Full"), (2, "Deposit Only"), (3, "Nothing"),
                    (4, "Skins Paid"), (9, "Off Roster")]:
        c.execute("INSERT INTO customers (customer_id, first_name, last_name)"
                  " VALUES (?, ?, '')", (cid, nm))
    for cid in (1, 2, 3, 4):
        c.execute("INSERT INTO items (email_uid, item_index, customer, "
                  "item_name, order_date, transaction_status, merchant, "
                  "customer_id, event_id) VALUES (?, 0, ?, ?, '2026-09-01', "
                  "'rsvp_only', 'RSVP Only', ?, 3329)", (f"manual-rsvp-{cid}", f"c{cid}", EV, cid))
    for cid, amt in [(1, 250), (2, 150), (4, 150), (4, 175), (9, 325)]:
        c.execute("INSERT INTO expense_transactions (source_type, merchant, "
                  "amount, transaction_date, transaction_type, customer_id, "
                  "event_id, review_status) VALUES ('venmo', 'x', ?, "
                  "'2026-09-11', 'received', ?, 3329, 'approved')", (amt, cid))
    c.commit()
    c.close()
    roster = {"chapters": [
        {"chapter": "Austin", "seats": [{"customer_id": 1}, {"customer_id": 2}]},
        {"chapter": "San Antonio", "seats": [{"customer_id": 3}, {"customer_id": 4}]}]}
    db.set_app_setting("lsc_roster_final", json.dumps(roster), db_path=p)
    db.set_app_setting("oneoff_charges", json.dumps({"3329": {
        "default": 250, "team_dial": "lsc_roster_final",
        "addons": [{"key": "skins", "label": "SKINS", "amount": 75}]}}),
        db_path=p)
    db.set_app_setting("oneoff_addons", json.dumps({"3329": {"4": ["skins"]}}),
                       db_path=p)
    return p


def _cup(p):
    return next(e for e in db.get_all_events(db_path=p) if e["id"] == 3329)


def test_badge_counts_settled_team_players_not_active_rows(cup_db):
    ev = _cup(cup_db)
    assert ev["registrations"] == 0          # all placeholders
    assert ev["oneoff_paid"] == 2            # Paid Full + Skins Paid ($325)
    assert ev["oneoff_total"] == 4           # the team, not the off-roster payer


def test_off_roster_money_is_not_a_paid_player(cup_db):
    fin = db.get_oneoff_roster_finance(3329, db_path=cup_db,
                                       include_shirts=False)
    assert fin["players"]["9"]["balance"] <= 0   # still in the money view
    assert _cup(cup_db)["oneoff_paid"] == 2      # but not in the badge


def test_phone_card_reads_the_same_paid_field():
    html = (Path(__file__).parent / "templates" / "events.html").read_text()
    assert html.count("ev.oneoff_paid != null ? ev.oneoff_paid") >= 2


def _pay(p, cid, amt, ttype, notes="", category=None, matched=None):
    c = sqlite3.connect(p)
    c.execute("INSERT INTO expense_transactions (source_type, merchant, amount,"
              " transaction_date, transaction_type, customer_id, event_id,"
              " review_status, notes, category, matched_item_id) VALUES"
              " ('venmo', 'x', ?, '2026-10-06', ?, ?, 3329, 'approved', ?, ?, ?)",
              (amt, ttype, cid, notes, category, matched))
    c.commit()
    c.close()


def test_a_refunded_overpayment_leaves_the_balance(cup_db):
    """CoS #1339-3 (10/7): Jeff Young read CR $150 after Kerry paid his
    credit out by Venmo. A refund paid to a roster player on the event
    comes off his paid; winnings on the same event do not."""
    _pay(cup_db, 1, 150, "received")                    # overpaid: 400 vs 250
    fin = db.get_oneoff_roster_finance(3329, db_path=cup_db)["players"]["1"]
    assert fin["balance"] == -150                       # CR $150 before
    c = sqlite3.connect(cup_db)
    cr = c.execute("INSERT INTO items (email_uid, item_index, customer, item_name,"
                   " order_date, transaction_status, merchant, customer_id,"
                   " event_id, item_price) VALUES ('manual-refund-1', 0, 'c1', ?,"
                   " '2026-10-06', 'refunded', 'Partial Credit', 1, 3329, '$150.00')"
                   " RETURNING id", (EV,)).fetchone()[0]
    c.commit()
    c.close()
    _pay(cup_db, 1, 150, "payout", "Credit from LONE STAR CUP", matched=cr)
    fin = db.get_oneoff_roster_finance(3329, db_path=cup_db)["players"]["1"]
    assert fin["paid"] == 250 and fin["balance"] == 0 and fin["refunded"] == 150
    assert any(x["amount"] == -150 for x in fin["payments"])
    # Winnings paid on the Cup are not a refund of entry money.
    _pay(cup_db, 1, 40, "payout", "Paid Full - Winnings for LONE STAR CUP")
    assert db.get_oneoff_roster_finance(3329, db_path=cup_db)["players"]["1"]["balance"] == 0
    # A declined payer refunded in full nets to $0 paid.
    _pay(cup_db, 9, 325, "payout", "Refund for Lone Star Cup", category="refund")
    assert db.get_oneoff_roster_finance(3329, db_path=cup_db)["players"]["9"]["paid"] == 0
