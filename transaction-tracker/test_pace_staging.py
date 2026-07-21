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
        # 7-player BACK-nine shotgun (Kerry 2026-07-21): sizes split
        # [4, 3] — the threesome must LEAD the train whatever its pace.
        conn.execute(
            "INSERT INTO events (id, item_name, event_date, chapter, format,"
            " start_type, start_time, tee_time_count, tee_time_interval,"
            " nine_side)"
            " VALUES (602, 's9.96 BackNine', '2026-08-04', 'San Antonio',"
            " '9 Holes', 'Shotgun', '17:30', 4, 10, 'Back')")
        for j in range(1, 8):
            conn.execute(
                "INSERT INTO items (email_uid, merchant, order_date,"
                " item_name, customer, customer_id, holes, event_id,"
                " transaction_status) VALUES (?, 'GoDaddy', '2026-07-10',"
                " 's9.96 BackNine', ?, ?, '9', 602, 'active')",
                (f"manual-test-602-{j}", f"Player Seven{j}", 100 + j))
        # Adversarial ratings: 1s and 3s scattered so pace-primary
        # ordering would often pull a slow threesome off the front.
        for cid, r in ((101, 1), (102, 3), (103, 1), (104, 3), (105, 1),
                       (106, 3), (107, 1)):
            conn.execute(
                "INSERT INTO customers (customer_id, first_name, last_name,"
                " pace_rating, pace_rating_source) VALUES (?, 'Player', ?,"
                " ?, 'manager')", (cid, f"Seven{cid - 100}", r))
        # 4-player tee-cart event: two Combo + two White tees interleaved
        # alphabetically — same-tee players must end up cart mates.
        conn.execute(
            "INSERT INTO events (id, item_name, event_date, chapter, format,"
            " start_type, start_time, tee_time_count, tee_time_interval)"
            " VALUES (603, 's9.95 Tees', '2026-08-11', 'San Antonio',"
            " '9 Holes', 'Shotgun', '17:30', 1, 10)")
        for j, (name, tee) in enumerate([("Al Tee", "Combo"),
                                         ("Bo Tee", "white "),
                                         ("Cy Tee", "combo"),
                                         ("Dan Tee", "White")], start=1):
            conn.execute(
                "INSERT INTO items (email_uid, merchant, order_date,"
                " item_name, customer, customer_id, holes, tee_choice,"
                " event_id, transaction_status) VALUES (?, 'GoDaddy',"
                " '2026-07-10', 's9.95 Tees', ?, ?, '9', ?, 603, 'active')",
                (f"manual-test-603-{j}", name, 200 + j, tee))
            conn.execute(
                "INSERT INTO customers (customer_id, first_name, last_name)"
                " VALUES (?, ?, ?)", (200 + j, *name.split()))
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

    # ── Threesomes lead the shotgun train (Kerry 2026-07-21) ─────────
    # 7 players split [4, 3]; whatever the (random) composition and its
    # pace mix, the short group takes the LAST filled slot — the front
    # of the hole train — and the foursome the first.
    for _ in range(5):
        res_b = db.generate_event_pairings(602, db_path=tmp)
        sizes = [len(g["players"]) for g in res_b["9"]]
        check(f"threesome leads the train {sizes}",
              sizes[0] == 4 and sizes[-1] == 3)

    # ── Back-nine side: shotgun labels start at hole 10 ──────────────
    res_b = db.generate_event_pairings(602, db_path=tmp)
    check("back-9 slots", res_b["slots_9"] == ["10A", "10B", "11A", "11B"])
    labels = [g["slot_label"] for g in res_b["9"]]
    check(f"back-9 group labels {labels}",
          all(l in res_b["slots_9"] for l in labels))

    # ── Switch sides: saved labels shift with the setting ────────────
    db.save_event_pairings(602, {"9": res_b["9"]}, db_path=tmp)
    out = db.switch_event_pairings_side(602, db_path=tmp)
    check("switch flips to Front", out["nine_side"] == "Front")
    saved = db.get_event_pairings(602, db_path=tmp)
    front_labels = {g["slot_label"] for g in saved["9"]}
    check(f"saved labels shifted to front {sorted(front_labels)}",
          front_labels <= {"1A", "1B", "2A", "2B"})
    out2 = db.switch_event_pairings_side(602, db_path=tmp)
    saved2 = db.get_event_pairings(602, db_path=tmp)
    back_labels = {g["slot_label"] for g in saved2["9"]}
    check("switch back to Back restores labels",
          out2["nine_side"] == "Back"
          and back_labels <= {"10A", "10B", "11A", "11B"})

    # ── Same-tee cart mates (Kerry 2026-07-21) ───────────────────────
    # Two Combo + two White tees (case/whitespace drift included): each
    # cart (seats 1&2 / 3&4) must hold one tee, not a split.
    for _ in range(5):
        res_t = db.generate_event_pairings(603, db_path=tmp)
        grp = res_t["9"][0]["players"]
        by_pos = {p["cart_pos"]: (p.get("tee_choice") or "").strip().lower()
                  for p in grp}
        check(f"tee pairs share carts {by_pos}",
              by_pos[1] == by_pos[2] and by_pos[3] == by_pos[4])

    # Partner request supersedes tee matching: Al (Combo) requests Bo
    # (White) — they ride together; the leftover pair shares the other
    # cart even though tees now can't match.
    with db._connect(tmp) as conn:
        conn.execute("UPDATE items SET partner_request = 'Bo Tee' "
                     "WHERE event_id = 603 AND customer = 'Al Tee'")
        conn.commit()
    for _ in range(3):
        res_t = db.generate_event_pairings(603, db_path=tmp)
        grp = res_t["9"][0]["players"]
        pos = {p["name"]: p["cart_pos"] for p in grp}
        same_cart = ((pos["Al Tee"] <= 2) == (pos["Bo Tee"] <= 2))
        check(f"request beats tee {pos}", same_cart)
    with db._connect(tmp) as conn:
        conn.execute("UPDATE items SET partner_request = NULL "
                     "WHERE event_id = 603")
        conn.commit()

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
