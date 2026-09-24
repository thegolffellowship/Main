"""
A second FALL Points Race purchase opens a DUPLICATE_CONTEST_ENTRY warning
(Jeff Rideout, s9.25 Canyon Springs, 2026-09-23, mailbox #641).
Run: python3 test_fall_duplicate_entry.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402

FAILS = 0


def check(label, cond, detail=""):
    global FAILS
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  -> {detail}"))
    if not cond:
        FAILS += 1


def _item(conn, iid, order, name, date, fall, cid=701, status="active"):
    conn.execute(
        "INSERT INTO items (id, email_uid, order_id, item_name, item_price, customer, "
        " customer_id, merchant, transaction_status, order_date, item_index, "
        " fall_net_points_race) VALUES (?, ?, ?, ?, '$136.00', 'Jeff Rideout', ?, "
        " 'The Golf Fellowship', ?, ?, 0, ?)",
        (iid, f"uid-{iid}", order, name, cid, status, date, fall))


def warnings(p):
    with db._connect(p) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM parse_warnings WHERE warning_code = 'DUPLICATE_CONTEST_ENTRY'")]


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    os.environ["DATABASE_PATH"] = p
    db.init_db(p)
    with db._connect(p) as conn:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter) "
                     "VALUES (701, 'Jeff', 'Rideout', 'San Antonio')")
        _item(conn, 2542, 'R108266473', 'FALL KICKOFF | Landa Park', '2026-08-20',
              'YES, SAN ANTONIO')
        conn.commit()

    print("One FALL entry")
    r = db.sync_season_contests_from_items(p)
    check("a single purchase enrolls and warns nothing",
          r.get("enrolled") == 1 and r.get("duplicate_entries") == 0 and not warnings(p), r)

    print("A second FALL purchase on another order")
    with db._connect(p) as conn:
        _item(conn, 2957, 'R395621042', 's9.25 CANYON SPRINGS', '2026-09-20',
              'YES, SAN ANTONIO')
        conn.commit()
    r = db.sync_season_contests_from_items(p)
    w = warnings(p)
    with db._connect(p) as conn:
        n = conn.execute("SELECT COUNT(*), MIN(source_item_id) FROM season_contests "
                         "WHERE customer_id = 701 AND season = '2026 Fall'").fetchone()
    check("still exactly one enrollment, backed by the first order",
          n[0] == 1 and n[1] == 2542, tuple(n))
    check("one DUPLICATE_CONTEST_ENTRY warning, on the second item",
          len(w) == 1 and w[0]["order_id"] == 'R395621042' and w[0]["customer_id"] == 701
          and w[0]["status"] == 'open' and 'R108266473' in w[0]["message"], w)
    check("the sync reports it", r.get("duplicate_entries") == 1, r)

    print("Idempotent + respects a dismissal")
    r = db.sync_season_contests_from_items(p)
    check("a re-run adds no second warning", len(warnings(p)) == 1
          and r.get("duplicate_entries") == 0, r)
    with db._connect(p) as conn:
        conn.execute("UPDATE parse_warnings SET status = 'dismissed' "
                     "WHERE warning_code = 'DUPLICATE_CONTEST_ENTRY'")
        conn.commit()
    db.sync_season_contests_from_items(p)
    w = warnings(p)
    check("a dismissed warning is not reopened", len(w) == 1 and w[0]["status"] == 'dismissed', w)

    print("Resolved by flipping the flag, and other cases stay quiet")
    with db._connect(p) as conn:
        conn.execute("DELETE FROM parse_warnings")
        conn.execute("UPDATE items SET fall_net_points_race = 'NO' WHERE id = 2957")
        # same order, two rows (e.g. a quantity split) is not a duplicate purchase
        _item(conn, 2543, 'R108266473', 'FALL KICKOFF | Landa Park', '2026-08-20',
              'YES, SAN ANTONIO')
        # a credited second purchase is already handled
        _item(conn, 2999, 'R777', 's9.26 SOMEWHERE', '2026-09-27', 'YES, SAN ANTONIO',
              status='credited')
        conn.commit()
    r = db.sync_season_contests_from_items(p)
    check("no warning once the flag is NO, same-order rows or credited rows",
          not warnings(p) and r.get("duplicate_entries") == 0, (warnings(p), r))

    print(f"\n{'ALL PASS' if not FAILS else f'{FAILS} FAILURE(S)'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
