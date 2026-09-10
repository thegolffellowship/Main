"""
Removed stays removed (Kerry 2026-09-09), and the contest-flags audit.

Three refunded 2026 City Match Play entries (Campos, Cheshire,
Lourigan) were re-created by the enrollment sync the moment their
purchase flags were restored from the order emails, because the sync
never read season_contest_removals. Run: python3 test_contest_removals.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402
from email_parser.contest_flags import contest_flags_audit  # noqa: E402

FAILS = 0


def check(label, cond, detail=""):
    global FAILS
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  -> {detail}"))
    if not cond:
        FAILS += 1


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    os.environ["DATABASE_PATH"] = p
    db.init_db(p)
    with db._connect(p) as conn:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter) "
                     "VALUES (901, 'Rolando', 'Campos', 'San Antonio')")
        conn.execute(
            "INSERT INTO items (id, email_uid, order_id, item_name, item_price, customer, "
            " customer_id, merchant, transaction_status, order_date, item_index, "
            " returning_or_new, city_match_play) VALUES (1597, 'uid-c', 'R745590832', "
            " 'TGF MEMBERSHIP', '$125.00', 'Rolando Campos', 901, 'The Golf Fellowship', "
            " 'active', '2026-05-13', 0, 'Returning', 'YES')")
        conn.execute(
            "INSERT INTO season_contest_removals (customer_name, customer_id, contest_type, "
            " chapter, season, source_item_id, enrolled_at, removed_at, reason, refund_amount, "
            " refund_method) VALUES ('Rolando Campos', 901, 'City Match Play', 'San Antonio', "
            " '2026', 1597, '2026-05-13', '2026-07-19 17:15:45', 'Withdrew — injury', 40.0, 'Venmo')")
        conn.commit()

    print("Removed stays removed")
    r = db.sync_season_contests_from_items(p)
    with db._connect(p) as conn:
        n = conn.execute("SELECT COUNT(*) FROM season_contests WHERE customer_id = 901 "
                         "AND contest_type = 'City Match Play'").fetchone()[0]
    check("a purchase flag covered by a later removal does not re-enroll", n == 0
          and r.get("skipped_removed", 0) >= 1, (n, r))
    with db._connect(p) as conn:      # an earlier sync re-created it
        conn.execute("INSERT INTO season_contests (customer_name, customer_id, contest_type, "
                     "chapter, season, source_item_id, enrolled_at) VALUES ('Rolando Campos', "
                     "901, 'City Match Play', 'San Antonio', '2026', 1597, '2026-05-13')")
        conn.commit()
    r = db.sync_season_contests_from_items(p)
    with db._connect(p) as conn:
        n = conn.execute("SELECT COUNT(*) FROM season_contests WHERE customer_id = 901 "
                         "AND contest_type = 'City Match Play'").fetchone()[0]
        flag = conn.execute("SELECT city_match_play FROM items WHERE id = 1597").fetchone()[0]
    check("a re-created enrollment is healed away", n == 0 and r.get("healed_removed") == 1, (n, r))
    check("the purchase flag survives — what was SOLD stays true", flag == "YES", flag)
    with db._connect(p) as conn:      # a NEW purchase after the removal enrolls
        conn.execute(
            "INSERT INTO items (id, email_uid, order_id, item_name, item_price, customer, "
            " customer_id, merchant, transaction_status, order_date, item_index, city_match_play) "
            "VALUES (1598, 'uid-d', 'R999', 'SEASON CONTESTS', '$50.00', 'Rolando Campos', 901, "
            " 'The Golf Fellowship', 'active', '2026-08-01', 0, 'YES')")
        conn.commit()
    db.sync_season_contests_from_items(p)
    with db._connect(p) as conn:
        n = conn.execute("SELECT COUNT(*) FROM season_contests WHERE customer_id = 901 "
                         "AND contest_type = 'City Match Play'").fetchone()[0]
    check("a purchase dated after the removal is a new decision and enrolls", n == 1, n)

    print("Removal keeps the purchase flag")
    with db._connect(p) as conn:
        eid = conn.execute("SELECT id FROM season_contests WHERE customer_id = 901 "
                           "AND contest_type = 'City Match Play'").fetchone()[0]
    db.remove_season_contest_enrollment(eid, reason="test", refund_amount=50.0,
                                        refund_method="Venmo", db_path=p)
    with db._connect(p) as conn:
        flag = conn.execute("SELECT city_match_play FROM items WHERE id = 1598").fetchone()[0]
        n = conn.execute("SELECT COUNT(*) FROM season_contests WHERE customer_id = 901").fetchone()[0]
    check("removing an enrollment records it and leaves the item flag", flag == "YES" and n == 0,
          (flag, n))

    print("Contest-flags audit against the order email")
    with db._connect(p) as conn:
        conn.execute(
            "INSERT INTO items (id, email_uid, order_id, item_name, item_price, customer, "
            " customer_id, merchant, transaction_status, order_date, item_index, returning_or_new, "
            " net_points_race) VALUES (2203, 'uid-m', 'R667402675', 'TGF MEMBERSHIP', '$125.00', "
            " 'Daniel Miller', NULL, 'The Golf Fellowship', 'active', '2026-07-02', 0, 'Returning', 'YES')")
        conn.execute(
            "INSERT INTO items (id, email_uid, order_id, item_name, item_price, customer, "
            " merchant, transaction_status, order_date, item_index, returning_or_new) "
            "VALUES (3000, 'uid-p', 'R100', 'TGF MEMBERSHIP', '$75.00', 'Plain Member', "
            " 'The Golf Fellowship', 'active', '2026-04-01', 0, 'Returning')")
        conn.commit()
    bodies = {
        "uid-c": {"text": "TGF MEMBERSHIP RETURNING or NEW?: RETURNING Add CITY Match Play?: YES SKU: MEM-R-S $125.00"},
        "uid-d": {"text": "SEASON CONTESTS Add CITY Match Play?: YES $50.00"},
        "uid-m": {"text": "TGF MEMBERSHIP RETURNING or NEW?: RETURNING Add FALL Points Race?: YES SKU: MEM-R-S $125.00"},
        "uid-p": {"text": "TGF MEMBERSHIP RETURNING or NEW?: RETURNING SKU: MEM-R-S $75.00"},
    }
    calls = []

    def fake_fetch(uid):
        calls.append(uid)
        return bodies.get(uid)
    rep = contest_flags_audit(db_path=p, fetch=fake_fetch)
    check("the $75 plain membership is not fetched (off-table only)", "uid-p" not in calls, calls)
    mm = {m["order_id"]: m["diffs"] for m in rep["mismatches"]}
    check("Miller: form says FALL yes / NET no, stored says NET yes → two diffs",
          set(mm.get("R667402675", {})) == {"net_points_race", "fall_net_points_race"}, mm)
    check("Campos and the season-contest row are clean", rep["clean"] == 2, rep)
    with db._connect(p) as conn:
        still = conn.execute("SELECT net_points_race FROM items WHERE id = 2203").fetchone()[0]
    check("dry run wrote nothing", still == "YES", still)
    rep2 = contest_flags_audit(db_path=p, apply=True, fetch=fake_fetch)
    with db._connect(p) as conn:
        row = conn.execute("SELECT net_points_race, fall_net_points_race FROM items "
                           "WHERE id = 2203").fetchone()
    check("apply writes the form's answers", tuple(row) == ("NO", "YES") and rep2["applied"] == 1,
          (tuple(row), rep2["applied"]))
    rep3 = contest_flags_audit(db_path=p, all_rows=True, fetch=fake_fetch)
    check("|all sweeps the $75 row too and finds it clean",
          "uid-p" in calls and rep3["mismatches"] == [], (calls, rep3["mismatches"]))

    print("A MEMBER box on an event order is not a membership (Kyle Compton)")
    with db._connect(p) as conn:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter) "
                     "VALUES (902, 'Kyle', 'Compton', 'Austin')")
        conn.execute(
            "INSERT INTO items (id, email_uid, order_id, item_name, item_price, customer, "
            " customer_id, customer_email, merchant, transaction_status, order_date, item_index, "
            " user_status) VALUES (4001, 'uid-k', 'R189036014', 'a18.5 FOREST CREEK', '$143.00', "
            " 'Kyle Compton', 902, 'kwcompton1969@gmail.com', 'The Golf Fellowship', 'active', "
            " '2026-09-09', 0, 'MEMBER')")
        conn.commit()
        kyle = conn.execute("SELECT * FROM items WHERE id = 4001").fetchone()
        st = db.resolve_player_status(dict(kyle), conn)
    check("the server resolver reads GUEST, not MEMBER", st == "GUEST", st)
    rep = db.member_rate_without_membership(db_path=p)
    check("and the member-rate check lists him", any(r["customer"] == "Kyle Compton" for r in rep["rows"])
          and rep["customers"] == 1, rep)
    with db._connect(p) as conn:      # once he buys a membership, MEMBER
        conn.execute(
            "INSERT INTO items (id, email_uid, order_id, item_name, item_price, customer, "
            " customer_id, customer_email, merchant, transaction_status, order_date, item_index) "
            "VALUES (4002, 'uid-k2', 'R189036015', 'TGF MEMBERSHIP', '$50.00', 'Kyle Compton', 902, "
            " 'kwcompton1969@gmail.com', 'The Golf Fellowship', 'active', '2026-09-10', 0)")
        conn.commit()
        st2 = db.resolve_player_status(dict(kyle), conn)
    check("a membership purchase flips the fallback to MEMBER", st2 == "MEMBER", st2)
    check("and clears him from the check", db.member_rate_without_membership(db_path=p)["customers"] == 0)
    # A Venmo / cash membership lives only as a customer_memberships term
    # (Kerry 2026-09-10: "Ferrara, Colasanto, Rivas and McKinley should all
    # have member transactions somewhere") — a term counts.
    with db._connect(p) as conn:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter) "
                     "VALUES (903, 'Adam', 'Colasanto', 'Austin')")
        conn.execute(
            "INSERT INTO items (id, email_uid, order_id, item_name, item_price, customer, "
            " customer_id, customer_email, merchant, transaction_status, order_date, item_index, "
            " user_status) VALUES (4003, 'uid-ac', 'R1', 'a9.1 STAR RANCH', '$91.00', "
            " 'Adam Colasanto', 903, 'awcolasanto@gmail.com', 'The Golf Fellowship', 'active', "
            " '2026-03-08', 0, 'MEMBER')")
        conn.commit()
    check("without a term he is on the list", db.member_rate_without_membership(db_path=p)["customers"] == 1)
    with db._connect(p) as conn:
        from email_parser.memberships import ensure_membership_tables
        ensure_membership_tables(conn)
        conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, source, notes) "
                     "VALUES (903, '2025-06-26', '2026-06-26', 'manual', 'Venmo')")
        conn.commit()
        ac = conn.execute("SELECT * FROM items WHERE id = 4003").fetchone()
        st3 = db.resolve_player_status(dict(ac), conn)
    check("a manual Venmo term is a membership: off the list, and the resolver keeps his own status",
          db.member_rate_without_membership(db_path=p)["customers"] == 0 and st3 == "MEMBER", st3)

    os.unlink(p)
    print()
    print("ALL PASS" if not FAILS else f"{FAILS} FAILED")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
