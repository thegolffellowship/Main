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
    # A lazy _ensure_* helper can be marked done for this path while its
    # ALTERs were rolled back (seen as a ~1-in-6 flake); run it for real.
    db._ensure_scoring_tables._ensure_inner(c)
    c.commit()
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


def test_nh_flag_moves_player_out_of_the_warning_and_back():
    from email_parser import nh_flags
    tmp = _fixture()
    r = nh_flags.set_nh(1, 4, True, set_by="manager:test", db_path=tmp)
    assert r["nh"] is True and r["before"] is False
    m = hw.missing_handicaps(1, db_path=tmp)
    assert [p["name"] for p in m["nh_players"]] == ["Dee Newbie"]
    assert "Dee Newbie" not in [p["name"] for p in m["players"]] and m["count"] == 2
    with db._connect(tmp) as c:
        assert nh_flags.event_nh_players(c, 1) == {4}
    nh_flags.set_nh(1, 4, False, set_by="manager:test", db_path=tmp)
    m = hw.missing_handicaps(1, db_path=tmp)
    assert m["count"] == 3 and m["nh_players"] == []
    with db._connect(tmp) as c:  # the row is kept, cleared, not deleted
        assert c.execute("SELECT nh FROM event_nh_flags WHERE event_id=1 AND customer_id=4").fetchone()[0] == 0


def test_nh_flag_refused_for_a_player_with_a_handicap_or_off_the_roster():
    from email_parser import nh_flags
    tmp = _fixture()
    assert "refused" in nh_flags.set_nh(1, 1, True, set_by="t", db_path=tmp)   # Ann has an index
    assert "refused" in nh_flags.set_nh(1, 999, True, set_by="t", db_path=tmp)


def test_vendor_rows_are_not_people():
    from email_parser.customer_query import query_customers, set_customer_field
    tmp = _fixture()
    with db._connect(tmp) as c:
        c.execute("INSERT INTO customers (customer_id, first_name, last_name, acquisition_source) "
                  "VALUES (394, 'Anthropic', '', 'vendor')")
        c.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES ('kerry', 'x', 'ok')")
        c.commit()
        post = c.execute("SELECT MAX(id) FROM platform_dialogue").fetchone()[0]
        assert 394 in db.vendor_customer_ids(c)
    ids = [x["customer_id"] for x in query_customers(db_path=tmp)["customers"]]
    assert 394 not in ids and 1 in ids
    assert 394 in [x["customer_id"] for x in query_customers(include_vendors=True, db_path=tmp)["customers"]]
    r = set_customer_field([394, 4], "gender", "M", "t", post, db_path=tmp)
    assert r["skipped_vendors"] == [394] and r["changes"] == 1
    # Clearing a vendor's gender to NULL is allowed (CFO #1083-2, #1134):
    # it puts back the vendor profiles set to M before the filter.
    with db._connect(tmp) as _c:
        _c.execute("UPDATE customers SET gender = 'M' WHERE customer_id = 394"); _c.commit()
    r = set_customer_field([394], "gender", None, "vendor: no gender", post, apply=True, db_path=tmp)
    assert r["skipped_vendors"] == [] and r["changes"] == 1 and r.get("applied"), r
    with db._connect(tmp) as _c:
        assert _c.execute("SELECT gender FROM customers WHERE customer_id = 394").fetchone()[0] is None


def test_date_of_birth_write():
    # Kerry 2026-10-06: "Date of Birth should be a field in customer database.
    # Which you should have a write tool for." Same guard as gender.
    from email_parser.customer_query import set_customer_field
    tmp = _fixture()
    with db._connect(tmp) as c:
        c.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES ('kerry', 'x', 'set it')")
        c.commit()
        post = c.execute("SELECT MAX(id) FROM platform_dialogue").fetchone()[0]
    # Production carries customers.date_of_birth (the GG roster enrich added
    # it); a bare fixture does not, and the write must say so, not crash.
    assert "no date_of_birth column" in set_customer_field([2], "date_of_birth", "1/25/1971", "x", post,
                                                           db_path=tmp).get("refused", "")
    with db._connect(tmp) as c:
        c.execute("ALTER TABLE customers ADD COLUMN date_of_birth TEXT"); c.commit()
    r = set_customer_field([2], "date_of_birth", "1/25/1971", "Bartz DOB", post, db_path=tmp)
    assert r["dry_run"] and r["changes"] == 1 and r["value"] == "1971-01-25", r
    with db._connect(tmp) as c:
        assert c.execute("SELECT date_of_birth FROM customers WHERE customer_id = 2").fetchone()[0] is None
    r = set_customer_field([2], "date_of_birth", "1971-01-25", "Bartz DOB", post, apply=True, db_path=tmp)
    assert r.get("applied") and r["changes"] == 1, r
    with db._connect(tmp) as c:
        assert c.execute("SELECT date_of_birth FROM customers WHERE customer_id = 2").fetchone()[0] == "1971-01-25"
    r = set_customer_field([2], "date_of_birth", "1971-01-25", "again", post, apply=True, db_path=tmp)
    assert r["changes"] == 0 and r["unchanged"] == 1, r
    assert "refused" in set_customer_field([2], "date_of_birth", "Jan 25 1971", "bad", post, db_path=tmp)
    assert "refused" in set_customer_field([2], "date_of_birth", "2099-01-01", "future", post, db_path=tmp)
    assert "refused" in set_customer_field([2], "shirt_size", "L", "nope", post, db_path=tmp)
    r = set_customer_field([2], "date_of_birth", None, "clear", post, apply=True, db_path=tmp)
    assert r["changes"] == 1
    with db._connect(tmp) as c:
        assert c.execute("SELECT date_of_birth FROM customers WHERE customer_id = 2").fetchone()[0] is None


def test_front_desk_relay_signed_in_the_header_carries_kerrys_word():
    # The Front Desk posts under author tracker-claude with "FROM: front-desk"
    # on its header line; its verbatim Kerry quotes must pass the guard
    # (v2.525.4). A lane's own post quoting Kerry still must not.
    from email_parser.customer_query import set_customer_field
    tmp = _fixture()
    with db._connect(tmp) as c:
        c.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES ('tracker-claude', 'front-desk', "
                  "'TO: platform-claude (CA), kerry\nFROM: front-desk, Tue 10/6 11:35 AM CDT\n\n"
                  "Kerry: \"Yes apply the correct hole data now.\"')")
        c.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES ('tracker-claude', 'scoring-tees', "
                  "'TO: kerry\nFROM: tracker-claude (Track A)\n\nKerry said \"go\" in my session.')")
        c.commit()
        relay, lane = [r[0] for r in c.execute("SELECT id FROM platform_dialogue ORDER BY id DESC LIMIT 2").fetchall()][::-1]
    r = set_customer_field([1], "gender", "M", "t", relay, db_path=tmp)
    assert "refused" not in r and "front-desk, quoting Kerry" in r["authority"], r
    r = set_customer_field([1], "gender", "M", "t", lane, db_path=tmp)
    assert "refused" in r, r
