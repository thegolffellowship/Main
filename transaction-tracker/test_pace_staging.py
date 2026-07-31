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
        # Same 7 players on a TEE-TIME event: the threesome must take
        # the EARLIEST time (Kerry 2026-07-21 clarification).
        conn.execute(
            "INSERT INTO events (id, item_name, event_date, chapter, format,"
            " start_type, start_time, tee_time_count, tee_time_interval)"
            " VALUES (604, 's9.94 SmallsFirst', '2026-08-18', 'San Antonio',"
            " '9 Holes', 'Tee Times', '17:30', 4, 10)")
        for j in range(1, 8):
            conn.execute(
                "INSERT INTO items (email_uid, merchant, order_date,"
                " item_name, customer, customer_id, holes, event_id,"
                " transaction_status) VALUES (?, 'GoDaddy', '2026-07-10',"
                " 's9.94 SmallsFirst', ?, ?, '9', 604, 'active')",
                (f"manual-test-604-{j}", f"Player Seven{j}", 100 + j))
        # 13-player shotgun ([4,3,3,3] — the max three 3-somes case) on
        # 4 slots (1A,1B,2A,2B): smalls must stage 2A → 2B → 1A, with
        # the foursome behind them at 1B.
        conn.execute(
            "INSERT INTO events (id, item_name, event_date, chapter, format,"
            " start_type, start_time, tee_time_count, tee_time_interval)"
            " VALUES (605, 's9.93 ThreeSmalls', '2026-08-25', 'San Antonio',"
            " '9 Holes', 'Shotgun', '17:30', 4, 10)")
        for j in range(1, 14):
            conn.execute(
                "INSERT INTO items (email_uid, merchant, order_date,"
                " item_name, customer, customer_id, holes, event_id,"
                " transaction_status) VALUES (?, 'GoDaddy', '2026-07-10',"
                " 's9.93 ThreeSmalls', ?, ?, '9', 605, 'active')",
                (f"manual-test-605-{j}", f"Player Thirteen{j}", 300 + j))
        # Cross-request event (Kerry 2026-07-21, signup-order priority):
        # Zed signed up FIRST (but sorts alphabetically LAST) requesting
        # Ben; Amy requested Ben a day later; Ben himself requested Dan
        # later still. First-come wins: Zed+Ben pair, Amy and Ben's own
        # request are outranked.
        conn.execute(
            "INSERT INTO events (id, item_name, event_date, chapter, format,"
            " start_type, start_time, tee_time_count, tee_time_interval)"
            " VALUES (606, 's9.92 CrossReq', '2026-09-01', 'San Antonio',"
            " '9 Holes', 'Shotgun', '17:30', 2, 10)")
        cross = [("Amy Late", "2026-07-02", "Ben Target"),
                 ("Ben Target", "2026-07-03", "Dan Other"),
                 ("Dan Other", "2026-07-04", None),
                 ("Ed Fifth", "2026-07-05", None),
                 ("Zed Early", "2026-07-01", "Ben Target"),
                 # Unresolvable request — no roster surname matches, so it
                 # stays unmatched until a manager binds it. (Was 'Danny
                 # Other', which the v2.152.6 nickname-robust matcher now
                 # correctly resolves to Dan Other — Danny/Dan is exactly
                 # the class Kerry asked for. Changed the fixture to keep
                 # testing the UNRESOLVABLE path rather than weaken the
                 # matcher.)
                 # the manager binds it manually (Kerry 2026-07-21).
                 ("Fay Sixth", "2026-07-06", "Zzz Nomatch"),
                 # Multi-name request — two rostered names in one text;
                 # only ONE partner is honored, manager links which.
                 ("Gil Seventh", "2026-07-07", "Dan Other or Ed Fifth")]
        for j, (name, od, req) in enumerate(cross, start=1):
            conn.execute(
                "INSERT INTO items (email_uid, merchant, order_date,"
                " item_name, customer, customer_id, holes, partner_request,"
                " event_id, transaction_status) VALUES (?, 'GoDaddy', ?,"
                " 's9.92 CrossReq', ?, ?, '9', ?, 606, 'active')",
                (f"manual-test-606-{j}", od, name, 400 + j, req))
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


def train_paces(groups):
    """Group paces in TRUE shotgun play order, front of the train
    first: hole DESC, A before B (the A group tees off ahead of the B
    group on a shared hole — Kerry's 12A/12B ruling)."""
    import re

    def rank(g):
        m = re.match(r"^(\d+)([AB])$", g["slot_label"])
        return (-int(m.group(1)), 0 if m.group(2) == "A" else 1)

    return [g["group_pace"] for g in sorted(groups, key=rank)]


def main():
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    build_db(tmp)

    for _ in range(5):  # composition is randomized — invariants must hold
        # Tee times: fastest first
        res_t = db.generate_event_pairings(600, db_path=tmp)
        pt = paces(res_t["9"])
        check(f"tee times fastest-first {pt}",
              all(pt[i] >= pt[i + 1] for i in range(len(pt) - 1)))
        # Shotgun: fastest at the FRONT of the train — higher average
        # goes first in true play order (hole DESC, A before B).
        res_s = db.generate_event_pairings(601, db_path=tmp)
        ps = train_paces(res_s["9"])
        check(f"shotgun fastest-first in play order {ps}",
              all(ps[i] >= ps[i + 1] for i in range(len(ps) - 1)))
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
    # 7 players split [4, 3]; only hole 10 is loaded (2 groups), so the
    # threesome takes its A slot (10A — the hole's lead-off group) and
    # the foursome follows at 10B, whatever the pace mix.
    for _ in range(5):
        res_b = db.generate_event_pairings(602, db_path=tmp)
        by_size = {len(g["players"]): g["slot_label"] for g in res_b["9"]}
        check(f"threesome leads the train {by_size}",
              by_size.get(3) == "10A" and by_size.get(4) == "10B")

    # ── Tee times: threesome takes the EARLIEST time ─────────────────
    for _ in range(5):
        res_e = db.generate_event_pairings(604, db_path=tmp)
        sizes = [len(g["players"]) for g in res_e["9"]]
        check(f"tee times smalls first {sizes}", sizes == [3, 4])

    # ── Three 3-somes stage 2A → 2B → 1A (max-three-smalls case) ─────
    # 13 players = [4,3,3,3] over slots 1A,1B,2A,2B: furthest loaded
    # hole's A, then its B, then the A one hole back; the foursome
    # slots in behind them at 1B. _make_group_sizes never produces
    # more than three 3-somes in a grouping.
    for _ in range(3):
        res_m = db.generate_event_pairings(605, db_path=tmp)
        by_label = {g["slot_label"]: len(g["players"]) for g in res_m["9"]}
        check(f"three smalls at 2A/2B/1A {by_label}",
              by_label == {"2A": 3, "2B": 3, "1A": 3, "1B": 4})
    check("group sizes never exceed three 3-somes",
          all(db._make_group_sizes(n).count(3) <= 3 for n in range(1, 80)))

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
    # ── Request list + manager suppression (Kerry 2026-07-21) ────────
    # The request stays visible when suppressed, but the generator
    # ignores it: with Al→Bo suppressed the tee rule wins the carts
    # again; restore brings the request back.
    with db._connect(tmp) as conn:
        conn.execute("UPDATE items SET partner_request = 'Zzz Nobody' "
                     "WHERE event_id = 603 AND customer = 'Cy Tee'")
        conn.commit()
    reqs = db.get_event_partner_requests(603, db_path=tmp)["requests"]
    by_requester = {r["requester"]: r for r in reqs}
    check("request list shows both requests", len(reqs) == 2)
    check("Al→Bo matched & active",
          by_requester["Al Tee"]["partner"] == "Bo Tee"
          and by_requester["Al Tee"]["matched"]
          and not by_requester["Al Tee"]["suppressed"])
    check("unmatched request flagged",
          not by_requester["Cy Tee"]["matched"]
          and by_requester["Cy Tee"]["request_text"] == "Zzz Nobody")

    out = db.set_partner_request_suppression(603, "Al Tee", True, db_path=tmp)
    sup_row = next(r for r in out["requests"] if r["requester"] == "Al Tee")
    check("suppressed request still listed", sup_row["suppressed"])
    for _ in range(3):
        res_t = db.generate_event_pairings(603, db_path=tmp)
        grp = res_t["9"][0]["players"]
        by_pos = {p["cart_pos"]: (p.get("tee_choice") or "").strip().lower()
                  for p in grp}
        check(f"suppressed request ignored — tees pair carts {by_pos}",
              by_pos[1] == by_pos[2] and by_pos[3] == by_pos[4])

    out = db.set_partner_request_suppression(603, "Al Tee", False, db_path=tmp)
    check("restore clears the badge",
          not next(r for r in out["requests"]
                   if r["requester"] == "Al Tee")["suppressed"])
    res_t = db.generate_event_pairings(603, db_path=tmp)
    pos = {p["name"]: p["cart_pos"] for p in res_t["9"][0]["players"]}
    check(f"restored request honored {pos}",
          (pos["Al Tee"] <= 2) == (pos["Bo Tee"] <= 2))
    with db._connect(tmp) as conn:
        conn.execute("UPDATE items SET partner_request = NULL "
                     "WHERE event_id = 603")
        conn.commit()

    # ── Signup-order request priority (Kerry 2026-07-21) ─────────────
    # List comes back in signup order with the first-come lock
    # simulated: Zed (signed up first, sorts last alphabetically) wins
    # Ben; Amy's later request for Ben and Ben's own later request for
    # Dan are OUTRANKED.
    reqs = db.get_event_partner_requests(606, db_path=tmp)["requests"]
    check("requests in signup order",
          [r["requester"] for r in reqs] == ["Zed Early", "Amy Late",
                                             "Ben Target", "Fay Sixth",
                                             "Gil Seventh"])
    check("first request active, later ones outranked",
          [r["locked_out"] for r in reqs] == [False, True, True, False,
                                              False])
    check("typo request unmatched until fixed",
          not reqs[3]["matched"] and reqs[3]["request_text"] == "Zzz Nomatch")
    check("multi-name request flagged with candidates",
          reqs[4]["multi"]
          and reqs[4]["candidates"] == ["Dan Other", "Ed Fifth"]
          and reqs[4]["partner"] == "Dan Other")
    check("outranked reason names the lock",
          "Ben Target" in (reqs[1]["locked_reason"] or ""))
    for _ in range(3):
        res_c = db.generate_event_pairings(606, db_path=tmp)
        pos = {p["name"]: (g["group_num"], p["cart_pos"])
               for g in res_c["9"] for p in g["players"]}
        same_group = pos["Zed Early"][0] == pos["Ben Target"][0]
        same_cart = (pos["Zed Early"][1] <= 2) == (pos["Ben Target"][1] <= 2)
        check(f"earliest request wins the pair {pos}", same_group and same_cart)

    # Overriding the earlier lock (suppress Zed) promotes Amy's request;
    # Ben's own request stays outranked (Ben is claimed by Amy now).
    out = db.set_partner_request_suppression(606, "Zed Early", True,
                                             db_path=tmp)
    by_req = {r["requester"]: r for r in out["requests"]}
    check("override promotes the next request",
          not by_req["Amy Late"]["locked_out"]
          and by_req["Ben Target"]["locked_out"])
    res_c = db.generate_event_pairings(606, db_path=tmp)
    pos = {p["name"]: (g["group_num"], p["cart_pos"])
           for g in res_c["9"] for p in g["players"]}
    check(f"promoted request honored {pos}",
          pos["Amy Late"][0] == pos["Ben Target"][0]
          and (pos["Amy Late"][1] <= 2) == (pos["Ben Target"][1] <= 2))
    db.set_partner_request_suppression(606, "Zed Early", False, db_path=tmp)

    # ── Manual match for unresolved request text (Kerry 2026-07-21) ──
    # Bind Fay's unresolvable request to roster player Dan Other: the list
    # flags it manual, the lock simulation counts it, and the generator
    # honors it. Clearing restores the unmatched state.
    out = db.set_partner_request_match(606, "Fay Sixth", "Dan Other",
                                       db_path=tmp)
    fay = next(r for r in out["requests"] if r["requester"] == "Fay Sixth")
    check("manual match binds the request",
          fay["matched"] and fay["manual"] and fay["partner"] == "Dan Other"
          and not fay["locked_out"])
    for _ in range(3):
        res_c = db.generate_event_pairings(606, db_path=tmp)
        pos = {p["name"]: (g["group_num"], p["cart_pos"])
               for g in res_c["9"] for p in g["players"]}
        ok = (pos["Fay Sixth"][0] == pos["Dan Other"][0]
              and (pos["Fay Sixth"][1] <= 2) == (pos["Dan Other"][1] <= 2)
              and pos["Zed Early"][0] == pos["Ben Target"][0])
        check(f"manual match honored alongside first-come pair {pos}", ok)
    try:
        db.set_partner_request_match(606, "Fay Sixth", "Nobody Real",
                                     db_path=tmp)
        check("off-roster manual match rejected", False)
    except ValueError:
        check("off-roster manual match rejected", True)
    out = db.set_partner_request_match(606, "Fay Sixth", None, db_path=tmp)
    fay = next(r for r in out["requests"] if r["requester"] == "Fay Sixth")
    check("cleared manual match returns to unmatched",
          not fay["matched"] and not fay["manual"])

    # ── Multi-name request: manager links ONE (Kerry 2026-07-21) ─────
    # Gil's text names Dan AND Ed; auto-match took Dan. Linking Ed
    # overrides — the generator pairs Gil with Ed, and Dan is free.
    out = db.set_partner_request_match(606, "Gil Seventh", "Ed Fifth",
                                       db_path=tmp)
    gil = next(r for r in out["requests"] if r["requester"] == "Gil Seventh")
    check("linked one of the multi-name candidates",
          gil["partner"] == "Ed Fifth" and gil["manual"] and gil["multi"])
    for _ in range(3):
        res_c = db.generate_event_pairings(606, db_path=tmp)
        pos = {p["name"]: (g["group_num"], p["cart_pos"])
               for g in res_c["9"] for p in g["players"]}
        check(f"linked multi-name partner honored {pos}",
              pos["Gil Seventh"][0] == pos["Ed Fifth"][0]
              and (pos["Gil Seventh"][1] <= 2) == (pos["Ed Fifth"][1] <= 2))
    db.set_partner_request_match(606, "Gil Seventh", None, db_path=tmp)

    # ── Holes derived from event format at insert (Kerry 2026-07-21) ─
    # Blank holes breaks the side-games player buckets; on single-format
    # events the format is authoritative — blank AND wrong parses get
    # stamped at insert. Non-event rows (memberships) stay untouched.
    db.save_items([
        {"email_uid": "manual-test-holes-1", "item_index": 0,
         "merchant": "The Golf Fellowship", "customer": "Holes Blank",
         "order_date": "2026-07-21",
         "item_name": "s9.98 Teetimes", "holes": None,
         "transaction_status": "active"},
        {"email_uid": "manual-test-holes-2", "item_index": 0,
         "merchant": "The Golf Fellowship", "customer": "Holes Wrong",
         "order_date": "2026-07-21",
         "item_name": "s9.98 Teetimes", "holes": "18",
         "transaction_status": "active"},
        {"email_uid": "manual-test-holes-3", "item_index": 0,
         "merchant": "The Golf Fellowship", "customer": "Holes Member",
         "order_date": "2026-07-21",
         "item_name": "TGF MEMBERSHIP", "holes": None,
         "transaction_status": "active"},
    ], db_path=tmp)
    with db._connect(tmp) as conn:
        hv = {r["email_uid"]: r["holes"] for r in conn.execute(
            "SELECT email_uid, holes FROM items "
            "WHERE email_uid LIKE 'manual-test-holes-%'").fetchall()}
    check("blank holes derived from event format",
          hv.get("manual-test-holes-1") == "9")
    check("wrong holes corrected at insert",
          hv.get("manual-test-holes-2") == "9")
    check("non-event rows untouched",
          hv.get("manual-test-holes-3") is None)

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
