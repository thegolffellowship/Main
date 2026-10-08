"""AUTO-APPLY (Kerry 2026-10-07, CoS #1377-1: "Ok. Build it."): a Venmo /
Cash App receipt matched >= 85 to a player on an open one-off roster, for
exactly his open balance (or balance + one unmarked add-on), links to the
event and the roster reads PAID; flagged "auto · CFO to confirm". Anything
else stays pending. Also: promoting a receipt sets its event_id (Track B
#1380). Run: python3 -m pytest -q test_receipt_autoapply.py
"""
import contextlib, io, json, logging, sqlite3
import pytest
from email_parser import database as db
from email_parser.receipt_autoapply import auto_apply_receipt, plan_auto_apply

EV = "LONE STAR CUP | The Hideout"


@pytest.fixture()
def cup(tmp_path):
    p = str(tmp_path / "cup.db")
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        db.init_db(p)
    logging.disable(logging.NOTSET)
    c = sqlite3.connect(p)
    if "event_id" not in [r[1] for r in c.execute("PRAGMA table_info(expense_transactions)")]:
        c.execute("ALTER TABLE expense_transactions ADD COLUMN event_id INTEGER")
    c.execute("INSERT INTO events (id, item_name, event_date) VALUES (3329, ?, '2099-10-10')", (EV,))
    for cid, nm in [(1, "Owes Entry"), (2, "Owes Skins Too"), (3, "Paid Up")]:
        c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, '')", (cid, nm))
        c.execute("INSERT INTO items (email_uid, item_index, customer, item_name, order_date, "
                  "transaction_status, merchant, customer_id, event_id) VALUES (?, 0, ?, ?, "
                  "'2026-09-01', 'rsvp_only', 'RSVP Only', ?, 3329)", (f"m-{cid}", nm, EV, cid))
    c.execute("INSERT INTO expense_transactions (source_type, merchant, amount, transaction_date, "
              "transaction_type, customer_id, event_id, review_status) VALUES ('venmo', 'x', 250, "
              "'2026-09-11', 'received', 3, 3329, 'approved')")
    c.commit()
    c.close()
    db.set_app_setting("oneoff_charges", json.dumps({"3329": {"default": 250, "addons": [
        {"key": "friday", "label": "FRI", "amount": 110}, {"key": "skins", "label": "SKINS", "amount": 75}]}}),
        db_path=p)
    return p


def _receipt(p, cid, amt, conf=95, source="venmo", status="pending"):
    c = sqlite3.connect(p)
    rid = c.execute("INSERT INTO expense_transactions (source_type, merchant, amount, transaction_date, "
                    "transaction_type, customer_id, confidence, review_status, notes) VALUES "
                    "(?, 'x', ?, '2026-10-07', 'received', ?, ?, ?, 'lone star') RETURNING id",
                    (source, amt, cid, conf, status)).fetchone()[0]
    c.commit()
    c.close()
    return rid


def _row(p, rid):
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    try:
        return dict(c.execute("SELECT * FROM expense_transactions WHERE id = ?", (rid,)).fetchone())
    finally:
        c.close()


def _bal(p, cid):
    return db.get_oneoff_roster_finance(3329, db_path=p)["players"][str(cid)]["balance"]


def test_exact_balance_links_and_reads_paid(cup):
    assert _bal(cup, 1) == 250
    rid = _receipt(cup, 1, 250)
    res = auto_apply_receipt(rid, db_path=cup)
    assert res["applied"], res
    r = _row(cup, rid)
    assert r["event_id"] == 3329 and r["review_status"] == "pending"
    assert "auto · CFO to confirm" in r["notes"]
    assert _bal(cup, 1) == 0


def test_balance_plus_an_unmarked_addon_marks_it(cup):
    rid = _receipt(cup, 2, 325)
    res = auto_apply_receipt(rid, db_path=cup)
    assert res["applied"] and res["addon"] == "skins", res
    assert _bal(cup, 2) == 0


@pytest.mark.parametrize("kw,why", [
    ({"amt": 200}, "no open roster balance"),
    ({"conf": 70}, "confidence"),
    ({"source": "zelle"}, "not Venmo or Cash App"),
    ({"status": "approved"}, "not pending"),
])
def test_anything_else_stays_pending(cup, kw, why):
    rid = _receipt(cup, 1, kw.get("amt", 250), conf=kw.get("conf", 95),
                   source=kw.get("source", "venmo"), status=kw.get("status", "pending"))
    res = auto_apply_receipt(rid, db_path=cup)
    assert not res["applied"] and why in res["why"], res
    assert _row(cup, rid)["event_id"] is None


def test_paid_up_player_and_unknown_player_are_left(cup):
    assert not auto_apply_receipt(_receipt(cup, 3, 250), db_path=cup)["applied"]
    assert not auto_apply_receipt(_receipt(cup, 99, 250), db_path=cup)["applied"]


def test_past_event_is_not_open(cup):
    c = sqlite3.connect(cup)
    c.execute("UPDATE events SET event_date = '2020-01-01' WHERE id = 3329")
    c.commit()
    c.close()
    assert not plan_auto_apply(_receipt(cup, 1, 250), db_path=cup)["apply"]


def test_promote_sets_the_receipts_event_id(cup):
    rid = _receipt(cup, 1, 100)
    c = sqlite3.connect(cup)
    c.execute("UPDATE expense_transactions SET event_name = ? WHERE id = ?", (EV, rid))
    c.commit()
    c.close()
    db.promote_expense_to_ledger(rid, None, "TGF", db_path=cup)
    assert _row(cup, rid)["event_id"] == 3329
