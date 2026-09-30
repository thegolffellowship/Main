"""CoS tools 7-9 (#1057): score-entry card filter, pairing history view,
standards by name. All read-only."""
import tempfile
from email_parser import database as db, cos_reads as cr, score_entry as se


def _db():
    tmp = tempfile.mktemp(suffix=".db")
    db.init_db(tmp)
    with db._connect(tmp) as c:
        db._ensure_pairing_tables(c)
        for cid, f, l in ((1, "Ann", "A"), (2, "Bob", "B"), (3, "Cy", "C"), (4, "Di", "D")):
            c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, f, l))
        c.execute("INSERT INTO events (id, item_name, event_date) VALUES (10, 's9.1 X', '2026-09-01')")
        c.execute("INSERT INTO events (id, item_name, event_date) VALUES (11, 's9.2 Y', '2026-09-08')")
        c.execute("INSERT INTO events (id, item_name, event_date) VALUES (12, 's9.3 Z', '2099-01-01')")
        rows = [  # event, a, b, rode, source
            (10, 1, 2, 1, "gg_teesheet"), (10, 1, 3, 0, "gg_teesheet"), (10, 2, 3, 0, "gg_teesheet"),
            (11, 1, 3, 0, "gg_teesheet"), (11, 1, 4, 0, "gg_teesheet"),   # Ann solo cart on 11
            (11, 2, 4, 1, "app"),                                         # app row: a plan, never counted
            (12, 1, 2, 1, "gg_teesheet"),                                 # not played yet
        ]
        dates = {10: "2026-09-01", 11: "2026-09-08", 12: "2099-01-01"}
        names = {1: "Ann A", 2: "Bob B", 3: "Cy C", 4: "Di D"}
        for e, a, b, rode, src in rows:
            c.execute("INSERT INTO pairing_history (player_a, player_b, event_id, event_date, customer_a_id, "
                      "customer_b_id, rode, source) VALUES (?,?,?,?,?,?,?,?)",
                      (names[a], names[b], e, dates[e], a, b, rode, src))
        c.commit()
    return tmp


def test_customer_view_partners_and_solo_cart():
    r = cr.pairing_history_view(customer_id=1, db_path=_db())
    by = {p["customer_id"]: p for p in r["partners"]}
    assert by[3]["played_with"] == 2 and by[2]["played_with"] == 1 and by[2]["rode_with"] == 1
    assert r["rounds_with_pairs"] == 2
    cart = {c["event_id"]: c for c in r["cart_record"]}
    assert cart[10]["rode_with"] == "Bob B" and not cart[10]["solo_cart"]
    assert cart[11]["solo_cart"] and r["solo_carts"] == 1


def test_app_rows_and_future_dates_not_counted():
    tmp = _db()
    r = cr.pairing_history_view(customer_id=4, db_path=tmp)
    assert [p["customer_id"] for p in r["partners"]] == [1]
    assert cr.pairing_history_view(event_id=12, db_path=tmp)["pairs"] == []


def test_event_view():
    r = cr.pairing_history_view(event_id=10, db_path=_db())
    assert len(r["pairs"]) == 3 and len(r["rode_pairs"]) == 1


def test_score_entry_card_filters_one_group(monkeypatch):
    fake = {"event_id": 5, "version": 3, "as_of": "t", "rounds": [{
        "round_id": 1, "date": "d", "label": "L", "holes": 9, "status": "open", "course": [],
        "groups": [{"group_id": 7, "group_num": 1}, {"group_id": 8, "group_num": 2}],
        "players": [{"customer_id": 1, "group_id": 7, "scores": {"1": 4}},
                    {"customer_id": 2, "group_id": 8, "scores": {}}],
        "teams": [], "signoffs": [{"customer_id": 1}, {"customer_id": 2}],
        "card_checks": [{"group_id": 8}], "ctp": {"3": {"customer_id": 2}, "7": None},
        "hio": []}]}
    monkeypatch.setattr(se, "get_entered_scores", lambda *a, **k: fake)
    r = cr.score_entry_card(5, group=1)
    rd = r["rounds"][0]
    assert [p["customer_id"] for p in rd["players"]] == [1]
    assert rd["signoffs"] == [{"customer_id": 1}] and rd["card_checks"] == [] and rd["ctp"] == {}
    r = cr.score_entry_card(5, customer_id=2)
    assert r["rounds"][0]["ctp"] == {"3": {"customer_id": 2}} and len(r["rounds"][0]["card_checks"]) == 1
    assert "error" in cr.score_entry_card(5, group=9)
    assert "error" in cr.score_entry_card(5)


def test_standard_by_name_and_section():
    lst = cr.get_standard()
    assert any(s["name"] == "side-games" for s in lst["standards"])
    whole = cr.get_standard("side-games")
    assert whole["chars"] > 1000
    heads = [l for l in whole["text"].splitlines() if l.startswith("## ")]
    part = cr.get_standard("side-games", heads[0][3:])
    assert part["text"].startswith(heads[0]) and part["chars"] < whole["chars"]
    assert "error" in cr.get_standard("nope") and "error" in cr.get_standard("side-games", "zzqq no such")
