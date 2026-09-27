"""LSC skins pot liability bucket (Kerry via CA #753 item 5, 2026-09-27,
CA Queue #23): held = $75 x players marked SKINS on the cup roster (the
oneoff_addons 'skins' key the payout reads), paid_out = skins payouts
recorded PAID for the cup, balance = held - paid_out. Read-only.

Run: python3 test_lsc_skins_pot.py
"""

import json
import os
import sqlite3
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILURES.append(label)


def _db():
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    from email_parser import database as db
    db.init_db(p)
    conn = sqlite3.connect(p)
    # Minimal payouts tables: the bucket reads only these columns, and the
    # real ones carry NOT NULL columns this test has no use for.
    conn.executescript("""
        DROP TABLE IF EXISTS tgf_payouts;
        DROP TABLE IF EXISTS tgf_events;
        CREATE TABLE tgf_events (id INTEGER PRIMARY KEY, events_id INTEGER);
        CREATE TABLE tgf_payouts (id INTEGER PRIMARY KEY, event_id INTEGER,
            customer_id INTEGER, category TEXT, amount REAL, paid_at TEXT);
    """)
    conn.commit()
    conn.close()
    return p


def _set(p, key, val):
    conn = sqlite3.connect(p)
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                 (key, json.dumps(val)))
    conn.commit()
    conn.close()


def main():
    from email_parser.database import _connect
    from email_parser.margin_ledger import lsc_skins_pot

    p = _db()
    with _connect(p) as conn:
        out = lsc_skins_pot(conn)
    check("no dial -> says so, no number invented", "error" in out, out)

    _set(p, "lsc_matches", {"event_id": 3329,
                            "sessions": [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}]})
    _set(p, "oneoff_addons", {"3329": {"10": ["skins"], "11": ["skins", "friday"],
                                       "12": ["friday"], "13": []},
                              "999": {"20": ["skins"]}})
    with _connect(p) as conn:
        out = lsc_skins_pot(conn)
    check("$75 per player over 3 rounds", out.get("per_player") == 75.0, out)
    check("only marked skins buyers on THIS cup count", out.get("buyers_marked") == 2, out)
    check("held = 2 x $75", out.get("held") == 150.0, out)
    check("nothing paid yet", out.get("paid_out") == 0.0 and out.get("balance") == 150.0, out)

    conn = sqlite3.connect(p)
    conn.executescript("""
        INSERT INTO tgf_events (id, events_id) VALUES (7, 3329), (8, 999);
        INSERT INTO tgf_payouts (event_id, customer_id, category, amount, paid_at)
        VALUES (7, 10, 'Skins', 40, '2026-10-10'),
               (7, 11, 'skins', 25, NULL),
               (7, 11, 'team_net', 90, '2026-10-10'),
               (8, 20, 'skins', 500, '2026-10-10');
    """)
    conn.commit()
    conn.close()
    with _connect(p) as conn:
        out = lsc_skins_pot(conn)
    check("paid_out counts PAID skins rows for this cup only", out.get("paid_out") == 40.0, out)
    check("balance = held - paid", out.get("balance") == 110.0, out)

    from email_parser.margin_ledger import liability_buckets
    liab = liability_buckets(db_path=p, today="2026-10-01")
    check("liability_buckets carries lsc_skins_pot",
          (liab.get("lsc_skins_pot") or {}).get("held") == 150.0, liab.get("lsc_skins_pot"))
    os.remove(p)

    print(f"\n{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
