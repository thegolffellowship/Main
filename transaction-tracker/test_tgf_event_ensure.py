"""Every Tracker event gets its tgf_events row from the Tracker event itself
(CA #786 GO 2), with events_id stamped at birth, and the payout recorder
finds the same row rather than making a second one.

Run: python3 test_tgf_event_ensure.py
"""

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


def main():
    from email_parser import database as db
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.init_db(p)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(events)")}
    vals = {"item_name": "s10.13 The Quarry", "event_date": "2026-10-13",
            "course": "The Quarry", "chapter": "San Antonio"}
    use = {k: v for k, v in vals.items() if k in cols}
    eid = conn.execute(
        f"INSERT INTO events ({', '.join(use)}) VALUES ({', '.join('?' * len(use))}) RETURNING id",
        tuple(use.values())).fetchone()[0]
    conn.commit()
    conn.close()

    dry = db.ensure_tgf_events([eid, 999999], db_path=p)
    st = {e["event_id"]: e for e in dry["events"]}
    check("dry run says it would create", st[eid]["status"] == "would create", dry)
    check("an unknown event is reported, not guessed", "error" in st[999999], dry)
    conn = sqlite3.connect(p)
    n = conn.execute("SELECT COUNT(*) FROM tgf_events").fetchone()[0]
    conn.close()
    check("dry run writes nothing", n == 0, n)

    app = db.ensure_tgf_events([eid], apply=True, db_path=p)
    check("apply creates the row", app["events"][0]["status"] == "created", app)
    tid = app["events"][0]["tgf_event_id"]
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM tgf_events WHERE id = ?", (tid,)).fetchone())
    conn.close()
    check("events_id stamped at birth", row["events_id"] == eid, row)
    check("code is the full event name", row["code"] == "s10.13 The Quarry", row)

    again = db.ensure_tgf_events([eid], apply=True, db_path=p)
    check("second apply finds it, creates nothing",
          again["events"][0]["status"] == "exists"
          and again["events"][0]["tgf_event_id"] == tid, again)

    # A legacy row keyed by the bare code with no events_id is adopted and stamped.
    conn = sqlite3.connect(p)
    conn.execute("DELETE FROM tgf_events")
    conn.execute("INSERT INTO tgf_events (code, name, event_date) VALUES ('s10.13', 's10.13', '2026-10-13')")
    conn.commit()
    conn.close()
    adopt = db.ensure_tgf_events([eid], apply=True, db_path=p)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM tgf_events")]
    conn.close()
    check("legacy bare-code row adopted, not duplicated", len(rows) == 1, rows)
    check("adopted row renamed and stamped",
          rows and rows[0]["code"] == "s10.13 The Quarry" and rows[0]["events_id"] == eid,
          rows)
    check("adoption reported as exists", adopt["events"][0]["status"] == "exists", adopt)

    # Recording payouts returns a result instead of raising (v2.505.2 left a
    # stale `full` reference that raised AFTER the insert, skipping the
    # Venmo auto-match; found on a9.25 Star Ranch 2026-09-29).
    rows_in = [{"golferName": "SCHNEIDER, Lou", "category": "skins",
                "amount": 10.0, "description": "Skins Par on 2"}]
    try:
        rec = db.record_event_game_payouts("s10.13 The Quarry", rows_in, db_path=p)
    except Exception as e:  # noqa: BLE001
        rec = {"raised": repr(e)}
    check("recording payouts does not raise", "raised" not in rec, rec)
    check("result names the event code",
          rec.get("tgf_event_code") == "s10.13 The Quarry", rec)
    try:
        again = db.record_event_game_payouts("s10.13 The Quarry", rows_in,
                                             force=True, db_path=p)
    except Exception as e:  # noqa: BLE001
        again = {"raised": repr(e)}
    check("forced re-record does not raise", "raised" not in again, again)
    os.remove(p)

    print(f"\n{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
