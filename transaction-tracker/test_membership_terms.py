"""Membership terms — Kerry's two rulings of 2026-09-10 (v2.368.0).

  1. "When someone renews prior to the 365 date, their new membership
     should continue at the 365 date, not reset to the date of the
     renewal."  → continued_start(); the repair moves terms already
     recorded the old way.
  2. "Robert Straiton is a Manager. Until that changes he is automatically
     a member, without any dues. He is comped, yes, but ... we need to note
     what that comp amount is for tax purposes."  → ensure_manager_comp_terms()
     opens a manager_comp term (price 0, comp value in notes) for every
     manager in the chapter_managers dial, inside the status sync.

Run: python3 test_membership_terms.py
"""

import os
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
from email_parser import memberships as ms  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.executescript("""
            CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
                first_name TEXT, last_name TEXT, current_player_status TEXT,
                updated_at TEXT);
            CREATE TABLE items (id INTEGER PRIMARY KEY, customer_id INTEGER,
                order_date TEXT, item_name TEXT, item_price TEXT);
            CREATE TABLE statuses (status_id INTEGER PRIMARY KEY, status_name TEXT);
            CREATE TABLE customer_statuses (id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER, status_id INTEGER,
                set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, set_by INTEGER, notes TEXT);
            CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO statuses VALUES (1, 'member'), (2, 'former');
            INSERT INTO customers VALUES (31, 'Robert', 'Straiton', 'expired_member', NULL);
            INSERT INTO customers VALUES (82, 'Luke', 'Mazanec', 'active_member', NULL);
            INSERT INTO customers VALUES (7, 'Early', 'Bird', 'active_member', NULL);
        """)
        ms.ensure_membership_tables(conn)
        conn.commit()
    return p


# The dial lookup reads app_settings through database.get_app_setting; the
# fixture has the table, so the defaults apply (SA → 18, Austin → 31).
db.get_app_setting = lambda key, db_path=None: None

print("\n== 1. continued_start: early renewal continues, lapsed renewal restarts ==")
p = fresh_db()
with db._connect(p) as conn:
    conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, "
                 "source) VALUES (7, '2025-09-10', '2026-09-10', 'renewal')")
    conn.commit()
    check("renewing 2026-08-01 (early) starts 2026-09-10",
          ms.continued_start(conn, 7, "2026-08-01") == "2026-09-10")
    check("renewing 2026-09-10 (on the day) starts 2026-09-10",
          ms.continued_start(conn, 7, "2026-09-10") == "2026-09-10")
    check("renewing 2026-10-01 (lapsed) starts 2026-10-01",
          ms.continued_start(conn, 7, "2026-10-01") == "2026-10-01")
    check("no prior term → purchase date",
          ms.continued_start(conn, 82, "2026-09-10") == "2026-09-10")
    # Legacy calendar-year term: no continuation (would be zero-length).
    conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, "
                 "source) VALUES (82, '2024-03-01', '2024-12-31', 'backfill')")
    conn.commit()
    check("a 2024 calendar-year term does not continue",
          ms.continued_start(conn, 82, "2024-11-01") == "2024-11-01")

print("\n== 2. record_renewal_for_item uses the continuation ==")
with db._connect(p) as conn:
    conn.execute("INSERT INTO items VALUES (500, 7, '2026-08-01', 'TGF MEMBERSHIP', '$75.00')")
    conn.commit()
    term = ms.record_renewal_for_item(conn, 500, send_email=None)
check("new term starts at the old expiry", term and term["started_at"] == "2026-09-10",
      str(term))
check("and runs 365 days from there", term and term["expires_at"] == "2027-09-10",
      str(term))

print("\n== 3. repair_early_renewal_terms moves old-style early renewals ==")
p = fresh_db()
with db._connect(p) as conn:
    # Recorded the OLD way: renewed 2026-06-01 while the 2025-09-10 term ran.
    conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, "
                 "source) VALUES (7, '2025-09-10', '2026-09-10', 'backfill')")
    conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, "
                 "source) VALUES (7, '2026-06-01', '2027-06-01', 'renewal')")
    # A manual term overlapping — must be left alone.
    conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, "
                 "source) VALUES (82, '2025-01-01', '2026-01-01', 'backfill')")
    conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, "
                 "source, notes) VALUES (82, '2025-06-01', '2026-06-01', 'manual', 'admin')")
    conn.commit()
    dry = ms.repair_early_renewal_terms(conn, apply=False)
    check("dry run finds the one early renewal", dry["terms_to_move"] == 1
          and dry["changes"][0]["to"] == ["2026-09-10", "2027-09-10"], str(dry))
    check("manual terms are not touched",
          all(c["customer_id"] != 82 for c in dry["changes"]), str(dry))
    res = ms.repair_early_renewal_terms(conn, apply=True)
    row = conn.execute("SELECT started_at, expires_at FROM customer_memberships "
                       "WHERE customer_id = 7 AND source = 'renewal'").fetchone()
check("apply moves it", res["terms_moved"] == 1 and tuple(row) == ("2026-09-10", "2027-09-10"),
      f"{res} {tuple(row)}")
with db._connect(p) as conn:
    again = ms.repair_early_renewal_terms(conn, apply=True)
check("idempotent", again["terms_moved"] == 0, str(again))

print("\n== 4. manager comp terms ==")
p = fresh_db()
with db._connect(p) as conn:
    # Robert's real shape: one 2025 term that lapsed 2026-01-02.
    conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, "
                 "source, price_paid) VALUES (31, '2025-01-02', '2026-01-02', 'backfill', 75)")
    conn.commit()
    res = ms.ensure_manager_comp_terms(conn)
    terms = [dict(r) for r in conn.execute(
        "SELECT * FROM customer_memberships WHERE customer_id = 31 ORDER BY started_at")]
opened = [o for o in res["opened"] if o["customer_id"] == 31]
check("a comp term opened for Robert", len(opened) == 1, str(res))
check("it continues from the lapsed expiry, 365 days",
      terms[-1]["started_at"] == "2026-01-02" and terms[-1]["expires_at"] == "2027-01-02",
      str(terms[-1]))
check("price 0, a manual term marked Manager comp, comp value in notes",
      terms[-1]["price_paid"] == 0 and terms[-1]["source"] == "manual"
      and (terms[-1]["notes"] or "").startswith("Manager comp")
      and "$75.00" in (terms[-1]["notes"] or ""), str(terms[-1]))
kerry = [o for o in res["opened"] if o["customer_id"] == 18]
check("Kerry (SA manager, no terms in this fixture) gets one starting today",
      len(kerry) == 1 and kerry[0]["started_at"] == ms.today_central().strftime("%Y-%m-%d"),
      str(kerry))
with db._connect(p) as conn:
    sync = ms.sync_player_status_with_terms(conn)
    status = conn.execute("SELECT current_player_status FROM customers WHERE customer_id = 31"
                          ).fetchone()[0]
    again = ms.ensure_manager_comp_terms(conn)
check("the status sync upgrades him back to active_member", status == "active_member",
      f"{status} {sync}")
check("idempotent: no second comp term", again["opened"] == [], str(again))

print("\n== 5. backfill is idempotent per ITEM, and the dedupe cleans the v2.368.0 boot ==")
p = fresh_db()
with db._connect(p) as conn:
    conn.execute("INSERT INTO items VALUES (600, 7, '2025-09-10', 'TGF MEMBERSHIP', '$75.00')")
    conn.execute("INSERT INTO items VALUES (601, 7, '2026-06-01', 'TGF MEMBERSHIP', '$75.00')")
    conn.commit()
    r1 = ms.backfill_memberships_from_items(conn)
    r2 = ms.backfill_memberships_from_items(conn)
    terms = [tuple(r) for r in conn.execute(
        "SELECT started_at, expires_at, source_item_id FROM customer_memberships "
        "WHERE customer_id = 7 ORDER BY started_at")]
check("first backfill inserts 2 terms, the early renewal continued",
      r1["inserted"] == 2 and terms == [("2025-09-10", "2026-09-10", 600),
                                        ("2026-09-10", "2027-09-10", 601)], f"{r1} {terms}")
check("second backfill inserts nothing", r2["inserted"] == 0 and len(terms) == 2, str(r2))
with db._connect(p) as conn:
    # Simulate the v2.368.0 boot: a duplicate term for item 601 at a later start.
    conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, "
                 "source, source_item_id) VALUES (7, '2027-09-10', '2028-09-09', 'backfill', 601)")
    conn.commit()
    dry = ms.dedupe_terms_by_source_item(conn, apply=False)
    scoped = ms.dedupe_terms_by_source_item(conn, apply=False, created_since="2099-01-01")
    check("created_since scopes the deletion and lists the rest for review",
          scoped["duplicates_to_delete"] == 0
          and len(scoped["older_duplicates_left_for_review"]) == 1, str(scoped))
    res = ms.dedupe_terms_by_source_item(conn, apply=True)
    left = conn.execute("SELECT COUNT(*) FROM customer_memberships WHERE customer_id = 7").fetchone()[0]
    first = conn.execute("SELECT started_at FROM customer_memberships WHERE source_item_id = 601").fetchone()[0]
check("dedupe finds the later duplicate", dry["duplicates_to_delete"] == 1
      and dry["rows"][0]["started_at"] == "2027-09-10", str(dry))
check("apply deletes it and keeps the first term", res["duplicates_deleted"] == 1
      and left == 2 and first == "2026-09-10", f"{res} {left} {first}")

print("\n== 6. a manual term on the order date IS the purchase — no stacked year ==")
p = fresh_db()
with db._connect(p) as conn:
    # Don Vann's shape: Kerry entered the 2025-05-01 term by hand on 7/1; the
    # order item was linked to him later.
    conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, "
                 "source, notes) VALUES (82, '2025-05-01', '2026-05-01', 'manual', 'admin')")
    conn.execute("INSERT INTO items VALUES (700, 82, '2025-05-01', 'TGF MEMBERSHIP', '$50.00')")
    conn.commit()
    r = ms.backfill_memberships_from_items(conn)
    n = conn.execute("SELECT COUNT(*) FROM customer_memberships WHERE customer_id = 82").fetchone()[0]
check("backfill adds nothing on top of the manual term", r["inserted"] == 0 and n == 1, f"{r} {n}")

print("\n== 7. purge of one boot's backfill rows ==")
with db._connect(p) as conn:
    conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, source, "
                 "source_item_id, created_at) VALUES (82, '2026-05-01', '2027-05-01', 'backfill', 700, "
                 "'2026-09-10 16:17:10')")
    conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, source, "
                 "created_at) VALUES (7, '2026-01-01', '2027-01-01', 'backfill', '2026-06-23 16:35:20')")
    conn.commit()
    dry = ms.purge_backfill_terms_created_between(conn, "2026-09-10 16:17:00", "2026-09-10 16:18:00")
    res = ms.purge_backfill_terms_created_between(conn, "2026-09-10 16:17:00", "2026-09-10 16:18:00",
                                                  apply=True)
    left = [tuple(r) for r in conn.execute("SELECT customer_id, started_at FROM customer_memberships "
                                           "WHERE source = 'backfill'")]
check("only the row inside the window is targeted", dry["terms_to_delete"] == 1
      and res["terms_deleted"] == 1 and left == [(7, "2026-01-01")], f"{dry} {left}")

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL PASSED")
