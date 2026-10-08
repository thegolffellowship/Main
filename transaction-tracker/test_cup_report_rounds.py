"""ROUNDS UNDER ONE EVENT (Kerry 2026-10-08: "If we can streamline it into
ROUNDS under one expanded event, that would be nice. Obviously ROSTER is
overarching, but then other things are per round like the reports.").
The Cup's sessions ride on its events-list row; REPORTS prints per round."""
import contextlib
import io
import json
import logging
import os
import sqlite3

from email_parser import database as db


def test_the_cup_row_carries_its_rounds(tmp_path):
    p = str(tmp_path / "r.db")
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        db.init_db(p)
    logging.disable(logging.NOTSET)
    c = sqlite3.connect(p)
    c.execute("INSERT INTO events (id, item_name, event_date) VALUES (3329, 'LONE STAR CUP | The Hideout', '2026-10-10')")
    c.execute("INSERT INTO events (id, item_name, event_date) VALUES (3304, 's9.25 X', '2026-09-29')")
    c.commit()
    c.close()
    db.set_app_setting("lsc_matches", json.dumps({"event_id": 3329, "sessions": [
        {"id": "sat-am", "format": "fourball", "date": "2026-10-10", "n_matches": 7,
         "matches": [{"id": "SAT-AM-1"}]},
        {"id": "sat-pm", "format": "chapman", "date": "2026-10-10", "n_matches": 7, "matches": []},
        {"id": "sun", "format": "singles", "date": "2026-10-11", "n_matches": 14, "matches": []}]}),
        db_path=p)
    db.set_app_setting("oneoff_charges", json.dumps({"3329": {"addons": [
        {"key": "friday", "event_id": 3330}]}}), db_path=p)
    evs = {e["id"]: e for e in db.get_all_events(db_path=p)}
    assert [(r["id"], r["title"], r["drawn"], r["of"]) for r in evs[3329]["report_rounds"]] == [
        ("practice", "PRACTICE ROUND", None, None),
        ("sat-am", "FOURBALL", 1, 7), ("sat-pm", "FOURSOMES", 0, 7), ("sun", "SINGLES", 0, 14)]
    assert evs[3329]["report_rounds"][0]["event_id"] == 3330
    assert "report_rounds" not in evs[3304]


def test_reports_prints_each_round():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "events.html")).read()
    assert "ev.report_rounds && ev.report_rounds.length" in src
    assert "const q = `session=${encodeURIComponent(r.id)}`" in src
    assert "cup-cart-signs?${q}" in src and "starter-sheet?${q}" in src
