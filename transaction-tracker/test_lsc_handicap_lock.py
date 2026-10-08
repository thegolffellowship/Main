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


# --- The board reads for the Cup screens (CoS #1398, Track B) -------------

def _dial(se_round=None):
    return {"event_id": 3329, "defending_champion": "sa", "sessions": [
        {"id": "sun", "label": "SINGLES", "format": "singles", "date": "2026-10-11",
         "se_round": se_round, "matches": [
             {"id": "SUN-1", "tee_time": "8:30", "austin": [672], "sa": [306]},
             {"id": "SUN-2", "tee_time": "8:30", "austin": [13], "sa": [136]}]}]}


def test_session_titles_are_kerrys_words():
    assert lsc_cup.session_title("fourball") == "FOURBALL"
    assert lsc_cup.session_title("chapman") == "FOURSOMES"
    assert lsc_cup.session_title("foursomes") == "FOURSOMES"
    assert lsc_cup.session_title("singles") == "SINGLES"


def test_preview_board_reads_the_supplied_dial_and_the_locked_ch(cup_db):
    db.set_app_setting("lsc_handicap_lock", json.dumps({"3329": {"players": {
        "306": {"index": 12.4, "tee": "Red", "ch": 8},
        "672": {"index": 7.7, "tee": "Blue", "ch": 8}}}}), cup_db)
    # the LIVE dial says something else entirely; the preview never reads it
    db.set_app_setting("lsc_matches", json.dumps({"event_id": 3329, "sessions": []}), cup_db)
    b = lsc_cup.preview_board_payload(cup_db, dial=_dial())
    assert b["source"] == "preview"
    s = b["sessions"][0]
    assert s["title"] == "SINGLES"
    m1 = s["matches"][0]
    assert m1["state"] == "upcoming"
    assert [p["course_handicap"] for p in m1["players"]] == [8, 8]
    # no lock row = no CH, never a guess
    assert [p["course_handicap"] for p in s["matches"][1]["players"]] == [None, None]


def test_a_feed_ph_is_never_replaced_by_the_lock(cup_db):
    db.set_app_setting("lsc_handicap_lock", json.dumps({"3329": {"players": {
        "306": {"ch": 8}, "672": {"ch": 8}}}}), cup_db)
    with db._connect(cup_db) as conn:
        out = lsc_cup._apply_handicap_lock(conn, _dial(), {"sun": {"phs": {"306": 5}}})
    assert out["sun"]["phs"][306] == 5 and out["sun"]["phs"][672] == 8


def test_your_match_comes_first():
    board = {"sessions": [{"id": "sun", "matches": [
        {"match_id": "SUN-1", "players": [{"customer_ids": [672]}, {"customer_ids": [306]}]},
        {"match_id": "SUN-2", "players": [{"customer_ids": [13]}, {"customer_ids": [136]}]}]}]}
    v = lsc_cup.for_viewer(board, 136)
    assert [m["match_id"] for m in v["sessions"][0]["matches"]] == ["SUN-2", "SUN-1"]
    assert v["sessions"][0]["matches"][0]["yours"] is True
    assert v["your_matches"] == [{"session": "sun", "match_id": "SUN-2"}]
    # a spectator sees it unchanged, and the input is never mutated
    assert [m["match_id"] for m in lsc_cup.for_viewer(board, 999)["sessions"][0]["matches"]] == ["SUN-1", "SUN-2"]
    assert "yours" not in board["sessions"][0]["matches"][1]


def test_preview_dial_is_built_from_real_pairs_and_the_lock():
    pairs = {"austin": [{"id": f"A{i}", "cids": [i, i + 100], "pool": "low" if i < 4 else "high"}
                        for i in range(1, 8)],
             "sa": [{"id": f"S{i}", "cids": [i + 200, i + 300], "pool": "low" if i < 4 else "high"}
                    for i in range(1, 8)]}
    players = {}
    for i in range(1, 15):
        players[str(i)] = {"team": "austin", "ch": i, "index": float(i)}
        players[str(500 + i)] = {"team": "sa", "ch": 15 - i, "index": float(15 - i)}
    # Sunday ranks by raw INDEX, not CH (Kerry 10/7): 514 (CH 1, 0.5) then
    # 513 (CH 1, 1.4); and an Austin player with a low CH but higher index
    # ranks by his index
    players["513"] = {"team": "sa", "ch": 1, "index": 1.4}
    players["514"] = {"team": "sa", "ch": 1, "index": 0.5}
    players["2"] = {"team": "austin", "ch": 0, "index": 2.5}
    d = lsc_cup.build_preview_dial(
        {"event_id": 3329, "pairs": pairs, "board_live": True,
         "tee_sheet": {"sat-am": [f"8:{i}0" for i in range(3, 10)], "sun": ["8:30", "8:40"]},
         "sessions": [{"id": "sat-am", "format": "fourball", "date": "2026-10-10"},
                      {"id": "sat-pm", "format": "chapman"}, {"id": "sun", "format": "singles"}]},
        {"players": players})
    am, pm, sun = d["sessions"]
    assert d["board_live"] is False and "NOT the draw" in d["_note"]
    assert [am["label"], pm["label"], sun["label"]] == ["FOURBALL", "FOURSOMES", "SINGLES"]
    assert all(s["se_round"] is None for s in d["sessions"])
    assert am["matches"][0] == {"id": "SAT-AM-1", "tee_time": "8:30", "pool": "low",
                                "austin": [1, 101], "sa": [201, 301]}
    assert am["matches"][3]["pool"] == "high" and am["matches"][3]["austin"] == [4, 104]
    # Foursomes rotates SA one place inside each pool
    assert pm["matches"][0]["sa"] == [202, 302] and pm["matches"][2]["sa"] == [201, 301]
    assert len(sun["matches"]) == 14
    assert sun["matches"][0]["austin"] == [1] and sun["matches"][0]["sa"] == [514]
    assert sun["matches"][1]["sa"] == [513]
    assert sun["matches"][1]["austin"] == [2] and sun["matches"][2]["austin"] == [3]
    assert [m["tee_time"] for m in sun["matches"][:4]] == ["8:30", "8:30", "8:40", "8:40"]
    assert sun["matches"][6]["pool"] == "low" and sun["matches"][7]["pool"] == "high"


def test_a_partly_drawn_cup_still_counts_28_points_and_pairs_read_with_and():
    # Kerry 10/8 (CoS #1432/#1449): the draw lands matches one at a time into
    # the live dial, and a pair reads "A & B", never a slash.
    dial = {"event_id": 3329, "defending_champion": "sa", "sessions": [
        {"id": "sat-am", "format": "fourball", "n_matches": 7, "matches": [
            {"id": "SAT-AM-1", "austin": [1, 2], "sa": [3, 4]}]},
        {"id": "sat-pm", "format": "chapman", "n_matches": 7, "matches": []},
        {"id": "sun", "format": "singles", "n_matches": 14, "matches": []}]}
    names = {1: "Luke Youngs", 2: "Chris Cannon", 3: "Pat Youngs", 4: "Jeff Young"}
    b = lsc_cup.compute_board(dial, {}, names)
    assert b["cup"]["total"] == 28.0
    assert [p["name"] for p in b["sessions"][0]["matches"][0]["players"]] == [
        "Luke Youngs & Chris Cannon", "Pat Youngs & Jeff Young"]
