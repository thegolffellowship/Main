"""THE DRAW straight into the live Cup dial (Kerry 10/8, CoS #1432: "Can't
you set up the draw to automatically go to the matches for this weekend on
the tracker rather than copying here? Being able to push live immediately
would be much cooler.").

Track B owns the dial write and the partial-state rules (lsc_cup.draw_match,
clear_draw_session, draw_state); Tracker Build owns the page.
"""

import contextlib
import io
import json
import logging
import sqlite3

import pytest

from email_parser import database as db
from email_parser import lsc_cup

AUS = list(range(101, 115))      # 14 Austin players, index = cid - 100
SA = list(range(201, 215))       # 14 SA players, index = cid - 200 - 0.5


def _lock():
    p = {}
    for c in AUS:
        p[str(c)] = {"name": f"A{c}", "team": "austin", "index": float(c - 100), "ch": c - 100}
    for c in SA:
        p[str(c)] = {"name": f"S{c}", "team": "sa", "index": c - 200 - 0.5, "ch": c - 200}
    return {"3329": {"players": p}}


def _pairs(team, cids):
    out = []
    for i in range(7):
        a, b = cids[2 * i], cids[2 * i + 1]
        out.append({"id": f"{team}-P{i + 1}", "cids": [a, b], "names": f"{a} | {b}",
                    "combined_index": float(i), "pool": "low" if i < 3 else "high"})
    return out


def _dial():
    demo = [{"id": "X-1", "tee_time": "8:30", "austin": [101], "sa": [201]}]
    return {"event_id": 3329, "board_live": False, "defending_champion": "sa",
            "tee_sheet": {"sat-am": ["8:30", "8:40", "8:50", "9:00", "9:10", "9:20", "9:30"],
                          "sat-pm": ["1:30", "1:40", "1:50", "2:00", "2:10", "2:20", "2:30"],
                          "sun": ["8:30", "8:40", "8:50", "9:00", "9:10", "9:20", "9:30"]},
            "pairs": {"austin": _pairs("AUS", AUS), "sa": _pairs("SA", SA)},
            "sessions": [
                {"id": "sat-am", "label": "FOURBALL", "format": "fourball", "date": "2026-10-10",
                 "se_round": None, "matches": list(demo)},
                {"id": "sat-pm", "label": "FOURSOMES", "format": "chapman", "date": "2026-10-10",
                 "se_round": None, "matches": list(demo)},
                {"id": "sun", "label": "SINGLES", "format": "singles", "date": "2026-10-11",
                 "se_round": None, "matches": list(demo)}]}


@pytest.fixture()
def cup(tmp_path):
    p = str(tmp_path / "draw.db")
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        db.init_db(p)
    logging.disable(logging.NOTSET)
    c = sqlite3.connect(p)
    c.execute("INSERT INTO events (id, item_name, event_date) "
              "VALUES (3329, 'LONE STAR CUP | The Hideout', '2026-10-10')")
    for cid in AUS + SA:
        c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, 'P', ?)",
                  (cid, str(cid)))
    c.commit()
    c.close()
    db.set_app_setting("lsc_matches", json.dumps(_dial()), p)
    db.set_app_setting("lsc_handicap_lock", json.dumps(_lock()), p)
    db.set_app_setting("lsc_tees", json.dumps({"3329": {"players": {
        str(c): {"band": "<50", "tee": "Blue"} for c in AUS + SA}}}), p)
    db.set_app_setting("lsc_mock_scores", json.dumps({"sat-am": {"scores": {"101": {"1": 4}}}}), p)
    return p


def _live(p):
    return json.loads(db.get_app_setting("lsc_matches", p))


def _sess(p, sid):
    return next(s for s in _live(p)["sessions"] if s["id"] == sid)


def _pair(team, i):
    cids = AUS if team == "austin" else SA
    return [cids[2 * i], cids[2 * i + 1]]


def test_the_page_reads_raw_index_pools(cup):
    st = {s["id"]: s for s in lsc_cup.draw_state(cup)["sessions"]}
    am = st["sat-am"]["pools"]
    assert [len(am["low"]["austin"]), len(am["high"]["austin"])] == [3, 4]
    sun = st["sun"]["pools"]
    # Sunday Low 7 by locked raw index
    assert [e["cids"][0] for e in sun["low"]["sa"]] == SA[:7]
    assert st["sat-am"]["open"] and not st["sat-pm"]["open"]
    assert st["sat-am"]["drawn"] == 0      # the staged demo is not a draw


def test_first_draw_lands_live_clears_demo_and_mock(cup):
    r = lsc_cup.draw_match("sat-am", "low", _pair("austin", 0), _pair("sa", 2), cup)
    assert r["match"] == {"id": "SAT-AM-1", "tee_time": "8:30", "pool": "low",
                          "austin": _pair("austin", 0), "sa": _pair("sa", 2)}
    live = _live(cup)
    assert [len(s["matches"]) for s in live["sessions"]] == [1, 0, 0]
    assert [s["n_matches"] for s in live["sessions"]] == [7, 7, 14]
    assert not db.get_app_setting("lsc_mock_scores", cup)
    # the board already counts the whole Cup: 28 points, 14 to keep it
    b = lsc_cup.preview_board_payload(cup, dial=live)
    assert b["cup"]["total"] == 28.0
    assert len(b["sessions"][0]["matches"]) == 1


def test_numbers_and_tee_times_follow_the_pool(cup):
    r = lsc_cup.draw_match("sat-am", "high", _pair("austin", 5), _pair("sa", 3), cup)
    assert r["match"]["id"] == "SAT-AM-4" and r["match"]["tee_time"] == "9:00"
    r = lsc_cup.draw_match("sat-am", "low", _pair("austin", 1), _pair("sa", 1), cup)
    assert r["match"]["id"] == "SAT-AM-1" and r["match"]["tee_time"] == "8:30"
    assert [m["id"] for m in _sess(cup, "sat-am")["matches"]] == ["SAT-AM-1", "SAT-AM-4"]


def test_the_rules_refuse(cup):
    with pytest.raises(lsc_cup.DrawError, match="not in the low pool"):
        lsc_cup.draw_match("sat-am", "low", _pair("austin", 5), _pair("sa", 0), cup)
    lsc_cup.draw_match("sat-am", "low", _pair("austin", 0), _pair("sa", 0), cup)
    with pytest.raises(lsc_cup.DrawError, match="already drawn"):
        lsc_cup.draw_match("sat-am", "low", _pair("austin", 0), _pair("sa", 1), cup)
    with pytest.raises(lsc_cup.DrawError, match="FOURSOMES opens once FOURBALL"):
        lsc_cup.draw_match("sat-pm", "low", _pair("austin", 1), _pair("sa", 1), cup)
    # a refused draw writes nothing
    assert len(_sess(cup, "sat-am")["matches"]) == 1


def _draw_all_am(cup):
    for i in range(3):
        lsc_cup.draw_match("sat-am", "low", _pair("austin", i), _pair("sa", i), cup)
    for i in range(3, 7):
        r = lsc_cup.draw_match("sat-am", "high", _pair("austin", i), _pair("sa", i), cup)
    return r


def test_complete_session_seeds_and_binds(cup):
    r = _draw_all_am(cup)
    assert r["complete"] and r["seed"]["bound"], r
    assert isinstance(_sess(cup, "sat-am")["se_round"], int)
    st = {s["id"]: s for s in lsc_cup.draw_state(cup)["sessions"]}
    assert st["sat-pm"]["open"] and len(st["sat-pm"]["not_again"]) == 7


def test_foursomes_never_repeats_a_fourball_pairing(cup):
    _draw_all_am(cup)
    with pytest.raises(lsc_cup.DrawError, match="already meets in FOURBALL"):
        lsc_cup.draw_match("sat-pm", "low", _pair("austin", 0), _pair("sa", 0), cup)
    lsc_cup.draw_match("sat-pm", "low", _pair("austin", 0), _pair("sa", 1), cup)


def test_clear_rules(cup):
    _draw_all_am(cup)
    lsc_cup.draw_match("sat-pm", "low", _pair("austin", 0), _pair("sa", 1), cup)
    with pytest.raises(lsc_cup.DrawError, match="Clear FOURSOMES first"):
        lsc_cup.clear_draw_session("sat-am", cup)
    assert lsc_cup.clear_draw_session("sat-pm", cup) == {"session": "sat-pm", "cleared": 1}
    out = lsc_cup.clear_draw_session("sat-am", cup)
    assert out["cleared"] == 7
    am = _sess(cup, "sat-am")
    assert am["matches"] == [] and am["se_round"] is None and am["n_matches"] == 7
    # drawn again from scratch after a clear
    r = lsc_cup.draw_match("sat-am", "low", _pair("austin", 2), _pair("sa", 0), cup)
    assert r["match"]["id"] == "SAT-AM-1"


def test_sunday_two_matches_per_tee_time(cup):
    times = []
    for i in range(7):
        times.append(lsc_cup.draw_match("sun", "low", [AUS[i]], [SA[i]], cup)["match"])
    assert [m["id"] for m in times] == [f"SUN-{n}" for n in range(1, 8)]
    assert [m["tee_time"] for m in times] == ["8:30", "8:30", "8:40", "8:40", "8:50", "8:50", "9:00"]
    m8 = lsc_cup.draw_match("sun", "high", [AUS[7]], [SA[7]], cup)["match"]
    assert m8["id"] == "SUN-8" and m8["tee_time"] == "9:00"
    with pytest.raises(lsc_cup.DrawError, match="not in the low pool"):
        lsc_cup.draw_match("sun", "low", [AUS[8]], [SA[9]], cup)
