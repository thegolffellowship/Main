"""Missing-handicap warning (Kerry 2026-09-30, CoS #1064-1 / #1067-3): a
roster row with no TGF index and no starting handicap is named, with the
case that applies and its fix. Read-only; one computation shared by the
events page, the MCP tool and the Front Desk brief."""
import contextlib, io, os, sqlite3, tempfile
from email_parser import database as db, handicap_warnings as hw


def _fixture():
    tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-nohcp-"), "t.db")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        db.init_db(tmp)
    c = sqlite3.connect(tmp)
    c.row_factory = sqlite3.Row
    EV = "s9.99 Future Quarry"
    c.execute("INSERT INTO events (id, item_name, event_date, course, chapter, format, status) "
              "VALUES (1, ?, '2099-01-06', 'The Quarry', 'San Antonio', '9 Holes', 'active')", (EV,))
    c.execute("INSERT INTO events (id, item_name, event_date, chapter, format, status) "
              "VALUES (2, 's9.1 Past', '2020-01-07', 'San Antonio', '9 Holes', 'active')")
    c.executemany("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) VALUES (?,?,?,?)",
                  [(1, "Ann", "Indexed", "active_member"), (2, "Bea", "Starting", "first_timer"),
                   (3, "Cal", "Oneround", "active_guest"), (4, "Dee", "Newbie", "first_timer")])
    for uid, name, cid in (("u1", "Ann Indexed", 1), ("u2", "Bea Starting", 2),
                           ("u3", "Cal Oneround", 3), ("u4", "Dee Newbie", 4)):
        c.execute("INSERT INTO items (email_uid, merchant, customer, customer_id, customer_email, item_name, holes, "
                  "transaction_status, order_date, created_at, event_id) "
                  "VALUES (?,'GoDaddy',?,?,?,?,'9','active','2026-09-10','2026-09-10 10:00:00',1)",
                  (uid, name, cid, f"{uid}@x.com", EV))
        c.execute("INSERT INTO items (email_uid, merchant, customer, customer_id, customer_email, item_name, holes, "
                  "transaction_status, order_date, created_at, event_id) "
                  "VALUES (?,'GoDaddy',?,?,?,'s9.1 Past','9','active','2020-01-01','2020-01-01 10:00:00',2)",
                  (uid + "p", name, cid, f"{uid}@x.com"))
    # An unmatched PLAYING RSVP with no customer at all.
    c.execute("INSERT INTO rsvps (email_uid, player_name, player_email, matched_event, response, received_at) "
              "VALUES ('r1', 'Ed Stranger', 'ed@x.com', ?, 'PLAYING', '2026-09-11 09:00:00')", (EV,))
    for nm, cid in (("Ann Indexed", 1), ("Cal Oneround", 3)):
        c.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES (?,?,?)", (nm, nm, cid))
    for i, d in enumerate((4.0, 6.0, 5.0)):
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) "
                  "VALUES ('Ann Indexed', date('2026-09-01', ?), 40, 34.5, 120, ?)", (f"-{i} days", d))
    c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) "
              "VALUES ('Cal Oneround', '2026-08-01', 45, 34.5, 120, 9.0)")
    c.commit(); c.close()
    db.set_starting_handicap(2, 18.0, set_by="test", db_path=tmp)
    return tmp


def test_names_only_the_players_with_no_handicap_and_the_case():
    tmp = _fixture()
    r = hw.missing_handicaps(1, db_path=tmp)
    got = {p["name"]: p["case"] for p in r["players"]}
    assert got == {"Cal Oneround": "few_rounds", "Dee Newbie": "new", "Ed Stranger": "no_identity"}, got
    assert r["count"] == 3 and r["upcoming"] is True
    assert r["message"] == "3 players have no handicap: Cal Oneround, Dee Newbie, Ed Stranger"
    assert all("75%" in p["fix"] for p in r["players"])
    assert r["nh_note"]


def test_past_event_is_flagged_not_upcoming_and_brief_skips_it():
    tmp = _fixture()
    assert hw.missing_handicaps(2, db_path=tmp)["upcoming"] is False
    b = hw.upcoming_missing_handicaps(days=40000, db_path=tmp)
    assert [e["event_id"] for e in b["events"]] == [1] and b["players_missing"] == 3


def test_setting_a_starting_handicap_clears_the_player():
    tmp = _fixture()
    db.set_starting_handicap(4, 24.0, set_by="test", db_path=tmp)
    names = [p["name"] for p in hw.missing_handicaps(1, db_path=tmp)["players"]]
    assert "Dee Newbie" not in names and len(names) == 2
