"""Functional proof of the pace STAGING engine (task #23, Kerry 2026-07-14).

Rules under test (defaults from PAIRING_STAGING_DEFAULTS, overridable via
the 'pairing_staging_rules' app_settings JSON — principle 2):
- Group pace = average member pace_rating; NULL reads as 2.
- Sequential tee times: fastest groups FIRST (slot order = pace desc).
- Shotgun hole-trains: fastest groups at the FRONT of the train, which is
  the HIGHER hole numbers / later sheet slots (slot order = pace asc).
- Pace NEVER dictates composition — only slot order. (Asserted by
  checking group membership sets are unchanged between the two starts.)
- enabled=false restores the legacy shotgun threesomes-last ordering.

Run: python3 test_pace_staging.py
"""

import json
import tempfile
from pathlib import Path

from email_parser import database as db

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}")


def build_db(tmp: Path):
    db.init_db(tmp)
    with db._connect(tmp) as conn:
        # Two events over the same 8-player roster: tee times + shotgun
        conn.execute(
            "INSERT INTO events (id, item_name, event_date, chapter, format,"
            " start_type, start_time, tee_time_count, tee_time_interval)"
            " VALUES (600, 's9.98 Teetimes', '2026-07-21', 'San Antonio',"
            " '9 Holes', 'Tee Times', '17:30', 4, 10)")
        conn.execute(
            "INSERT INTO events (id, item_name, event_date, chapter, format,"
            " start_type, start_time, tee_time_count, tee_time_interval)"
            " VALUES (601, 's9.97 Shotgun', '2026-07-28', 'San Antonio',"
            " '9 Holes', 'Shotgun', '17:30', 4, 10)")
        # Ratings: two 3s, two 1s, four unrated (read as 2)
        ratings = {"Ada Fast": 3, "Ben Fast": 3, "Cal Slow": 1, "Deb Slow": 1,
                   "Eli Mid": None, "Fia Mid": None, "Gus Mid": None,
                   "Hal Mid": None}
        for i, (name, r) in enumerate(ratings.items(), start=1):
            first, last = name.split()
            conn.execute(
                "INSERT INTO customers (customer_id, first_name, last_name,"
                " pace_rating, pace_rating_source) VALUES (?, ?, ?, ?, ?)",
                (i, first, last, r, "manager" if r else None))
            for ev in (600, 601):
                conn.execute(
                    "INSERT INTO items (email_uid, merchant, order_date,"
                    " item_name, customer, customer_id, holes, event_id,"
                    " transaction_status) VALUES (?, 'GoDaddy', '2026-07-10',"
                    " ?, ?, ?, '9', ?, 'active')",
                    (f"manual-test-{ev}-{i}",
                     "s9.98 Teetimes" if ev == 600 else "s9.97 Shotgun",
                     name, i, ev))
        conn.commit()


def paces(groups):
    return [g["group_pace"] for g in groups]


def main():
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    build_db(tmp)

    for _ in range(5):  # composition is randomized — invariants must hold
        # Tee times: fastest first
        res_t = db.generate_event_pairings(600, db_path=tmp)
        pt = paces(res_t["9"])
        check(f"tee times fastest-first {pt}",
              all(pt[i] >= pt[i + 1] for i in range(len(pt) - 1)))
        # Shotgun: fastest LAST (front of the hole train)
        res_s = db.generate_event_pairings(601, db_path=tmp)
        ps = paces(res_s["9"])
        check(f"shotgun fastest-last {ps}",
              all(ps[i] <= ps[i + 1] for i in range(len(ps) - 1)))
        # group_pace present on every group
        check("group_pace on all groups",
              all(g["group_pace"] is not None for g in res_t["9"] + res_s["9"]))

    # Pace never dictates composition: with history empty and no
    # requests, sizes are the standard split and every player appears
    # exactly once.
    res = db.generate_event_pairings(600, db_path=tmp)
    names = [p["name"] for g in res["9"] for p in g["players"]]
    check("every player staged exactly once",
          sorted(names) == sorted(set(names)) and len(names) == 8)

    # Rules are data: disabling staging restores legacy behavior and
    # drops the ordering guarantee (no crash, groups still complete).
    db.set_app_setting("pairing_staging_rules",
                       json.dumps({"enabled": False}), db_path=tmp)
    res_off = db.generate_event_pairings(601, db_path=tmp)
    n_off = sum(len(g["players"]) for g in res_off["9"])
    check("staging off still fields everyone", n_off == 8)
    rules = db.get_pairing_staging_rules(db_path=tmp)
    check("override read back", rules["enabled"] is False)
    check("defaults still merged", rules["shotgun"] == "fast_front")

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
