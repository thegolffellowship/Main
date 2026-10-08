"""THE SAVED SHEET FOLLOWS THE EVENT (Kerry 2026-10-08, LSC practice round:
"I went and fixed the event with tee times from 1:30 to 2:00p, but when I
saved it, it deleted my pairings!" … "Needs to easily update if those
things changes without hiding them.")

The 3330 shape: a sheet saved under the 9-hole set with "Group N" labels
while the event had no start time; the edit made it an 18 with 1:30 tee
times. Pins: the edit moves the sheet to the 18 set and labels the groups
1:30..2:00; a later start-time change shifts them; a hand-typed label is
kept; a sheet stranded before this rule is SERVED as the event's set; and
the PAIRINGS tab never hides a non-empty set."""
import contextlib
import io
import logging
import os
import sqlite3

import pytest

from email_parser import database as db


@pytest.fixture()
def edb(tmp_path):
    p = str(tmp_path / "e.db")
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        db.init_db(p)
    logging.disable(logging.NOTSET)
    c = sqlite3.connect(p)
    c.execute("INSERT INTO events (id, item_name, event_date, format, start_type) "
              "VALUES (3330, 'LSC PRACTICE ROUND | The Hideout', '2026-10-09', '9 Holes', 'Tee Times')")
    for cid, (f, l) in {7: ("Matt", "Jenkins"), 672: ("David", "Wetz"), 18: ("Kerry", "Niester"),
                        703: ("Michael", "Mesa"), 4: ("John", "Wade")}.items():
        c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, f, l))
    c.commit()
    c.close()

    def P(cid, pos):
        return {"name": str(cid), "customer_id": cid, "cart_pos": pos}
    db.save_event_pairings(3330, {"9": [
        {"group_num": 1, "slot_label": "Group 1", "players": [P(7, 1), P(672, 2)]},
        {"group_num": 2, "slot_label": "Group 2", "players": [P(18, 1), P(703, 2)]},
        {"group_num": 3, "slot_label": "Group 3", "players": [P(4, 1)]}]}, db_path=p)
    return p


def _labels(p, holes):
    return [g["slot_label"] for g in db.get_event_pairings(3330, db_path=p).get(holes) or []]


def test_the_edit_moves_the_sheet_and_labels_the_tee_times(edb):
    db.update_event(3330, {"format": "18 Holes", "start_time": "13:30",
                           "tee_time_interval": 10}, db_path=edb)
    with db._connect(edb) as c:
        assert {r[0] for r in c.execute("SELECT DISTINCT holes FROM event_pairings "
                                        "WHERE event_id = 3330")} == {"18"}
    assert _labels(edb, "18") == ["1:30 PM", "1:40 PM", "1:50 PM"]
    assert sum(len(g["players"]) for g in db.get_event_pairings(3330, db_path=edb)["18"]) == 5


def test_a_later_start_time_change_shifts_the_labels(edb):
    db.update_event(3330, {"format": "18 Holes", "start_time": "13:30"}, db_path=edb)
    db.update_event(3330, {"start_time": "14:00"}, db_path=edb)
    assert _labels(edb, "18") == ["2:00 PM", "2:10 PM", "2:20 PM"]


def test_a_hand_typed_label_is_kept(edb):
    db.update_event(3330, {"format": "18 Holes", "start_time": "13:30"}, db_path=edb)
    with db._connect(edb) as c:
        c.execute("UPDATE event_pairings SET slot_label = '1:35 PM' WHERE event_id = 3330 AND group_num = 2")
        c.commit()
    db.update_event(3330, {"start_time": "14:00"}, db_path=edb)
    assert _labels(edb, "18") == ["2:00 PM", "1:35 PM", "2:20 PM"]


def test_a_sheet_stranded_before_this_rule_is_served_as_the_events_set(edb):
    # the edit happened on the old code: the event row changed, the sheet didn't
    with db._connect(edb) as c:
        c.execute("UPDATE events SET format = '18 Holes', start_time = '13:30' WHERE id = 3330")
        c.commit()
    pr = db.get_event_pairings(3330, db_path=edb)
    assert "9" not in pr and [g["slot_label"] for g in pr["18"]] == ["1:30 PM", "1:40 PM", "1:50 PM"]


def test_the_pairings_tab_never_hides_a_saved_set():
    src = open(os.path.join(os.path.dirname(__file__), "templates", "events.html")).read()
    assert "if (isCombo || !is18Only || state.groups_9.length)" in src
    assert "if (isCombo || is18Only || state.groups_18.length)" in src
