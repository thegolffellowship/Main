"""One pair can be recorded once PER ROUND, and blind draws never count.

Kerry 2026-09-08, on the two-day TGF Championship: "Yes of course both
rounds count as pairings. Apply both." and "Blind draws should never
count in pairings."

pairing_history carried UNIQUE(player_a, player_b, event_id), so a pair
drawn together on Friday AND Saturday could only be stored once — the
second day vanished into an INSERT OR IGNORE and the pair read as having
played together half as often as they did.

Run: python3 test_pairing_rounds.py
"""

import os
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILURES.append(label)


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name

    # Build the OLD shape first, with rows in it, so the migration is
    # exercised the way production met it.
    with db._connect(p) as conn:
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, "
                     "item_name TEXT, event_date TEXT, format TEXT)")
        conn.execute("INSERT INTO events VALUES "
                     "(3291, '2026 TGF CHAMPIONSHIP', '2026-08-15', '18 Holes')")
        conn.execute("""
            CREATE TABLE pairing_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                player_a    TEXT NOT NULL,
                player_b    TEXT NOT NULL,
                event_id    INTEGER NOT NULL REFERENCES events(id),
                event_date  TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(player_a, player_b, event_id)
            )""")
        conn.execute("INSERT INTO pairing_history "
                     "(player_a, player_b, event_id, event_date) "
                     "VALUES ('Adam Baker','Jay Hogue',3291,'2026-08-15')")
        conn.commit()

    with db._connect(p) as conn:
        before = conn.execute(
            "SELECT COUNT(*) FROM pairing_history").fetchone()[0]
        db._ensure_pairing_tables(conn)
        after = conn.execute(
            "SELECT COUNT(*) FROM pairing_history").fetchone()[0]
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='pairing_history'"
        ).fetchone()["sql"]
        idx = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='pairing_history'")]

    check("the existing rows survive the rebuild", after == before == 1,
          (before, after))
    check("the table-level UNIQUE is gone", "UNIQUE" not in sql.upper(), sql)
    check("uniqueness moved to an index", "idx_pairing_history_uq" in idx, idx)
    check("the lookup indexes are recreated",
          "idx_pairing_history_ab" in idx and
          "idx_pairing_history_date" in idx, idx)

    # The point of it: same pair, same event, two rounds.
    with db._connect(p) as conn:
        for rid in ("1692724", "1692725"):
            conn.execute(
                "INSERT OR IGNORE INTO pairing_history "
                "(player_a, player_b, event_id, event_date, source, round_id) "
                "VALUES ('Adam Baker','Mary Wade',3291,'2026-08-15',"
                "'gg_teamnet',?)", (rid,))
        # ... and the same round twice is still once.
        conn.execute(
            "INSERT OR IGNORE INTO pairing_history "
            "(player_a, player_b, event_id, event_date, source, round_id) "
            "VALUES ('Adam Baker','Mary Wade',3291,'2026-08-15',"
            "'gg_teamnet','1692724')")
        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) FROM pairing_history WHERE player_b = 'Mary Wade'"
        ).fetchone()[0]
    check("a pair drawn together in BOTH rounds counts twice", n == 2, n)

    # A single-round event still behaves exactly as before.
    with db._connect(p) as conn:
        conn.execute("INSERT INTO events VALUES "
                     "(3289, 'SA CHAMP', '2026-08-01', '18 Holes')")
        for _ in range(2):
            conn.execute(
                "INSERT OR IGNORE INTO pairing_history "
                "(player_a, player_b, event_id, event_date, source) "
                "VALUES ('Ann One','Bob Two',3289,'2026-08-01','gg_teesheet')")
        conn.commit()
        n2 = conn.execute(
            "SELECT COUNT(*) FROM pairing_history WHERE event_id = 3289"
        ).fetchone()[0]
    check("a single-round event still records a pair once", n2 == 1, n2)

    # Re-running the migration must be a no-op.
    with db._connect(p) as conn:
        again = db._migrate_pairing_history_rounds(conn)
        n3 = conn.execute("SELECT COUNT(*) FROM pairing_history").fetchone()[0]
    check("the migration is idempotent", again is False and n3 == 4,
          (again, n3))

    # BLIND DRAWS: the seat parser must yield None for a blind fill, and
    # None seats must never become a pairing.
    groups = db._parse_teamnet_groups([[
        ["SOUTH, Daniel + MORENO, Robert + WADE, Mary + "
         "Bl[HAMILTON, Doug] TGF San Antonio"]]])
    check("a blind fill parses as an empty seat, not a player",
          bool(groups) and groups[0].count(None) == 1, groups)
    check("the three real players keep their seats",
          bool(groups) and sum(1 for s in groups[0] if s) == 3, groups)
    real = [s for s in (groups[0] if groups else []) if s]
    check("the blind player's name is not among them",
          all("HAMILTON" not in str(s).upper() for s in real), real)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: " + ", ".join(FAILURES))
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
