"""Functional proof of the rule 8 AMENDMENT (Kerry 2026-07-14, Task #25):
"Match Play is king" — the Match Play season state dictates pairings.

Covers:
1. Pool-phase detection: pool-mates on the roster with no PLAYED match
   (scheduled-but-unplayed row OR no row at all) are potential matches;
   played pairs are not.
2. Knockout-phase detection: pending current-round bracket matchups
   (both players placed, no winner) between rostered players; decided
   matchups and half-filled next-round slots are not.
3. Generator constraint: confirmed opponents land in the SAME foursome
   in OPPOSITE carts (seats 1/2 vs 3/4), above partner requests; a
   partner request still fits AROUND the match when there's room; the
   response tags mp_opponent for the PAIRINGS-tab denotation.
4. Declined matches (not passed as mp_pairs) constrain nothing.

Run: python3 test_mp_pairings.py
"""

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
        conn.execute(
            "INSERT INTO events (id, item_name, event_date, chapter, format,"
            " start_type, start_time, tee_time_count, tee_time_interval)"
            " VALUES (500, 's9.99 Testrack', '2026-07-21', 'San Antonio',"
            " '9 Holes', 'Tee Times', '17:30', 4, 10)")
        players = ["Alice Alpha", "Bob Bravo", "Carl Charlie", "Dana Delta",
                   "Evan Echo", "Fay Foxtrot", "Gil Golf", "Hana Hotel"]
        for i, name in enumerate(players, start=1):
            first, last = name.split()
            conn.execute(
                "INSERT INTO customers (customer_id, first_name, last_name)"
                " VALUES (?, ?, ?)", (i, first, last))
            conn.execute(
                "INSERT INTO items (email_uid, merchant, order_date,"
                " item_name, customer, customer_id, holes, event_id,"
                " transaction_status) VALUES"
                " (?, 'GoDaddy', '2026-07-10', 's9.99 Testrack', ?, ?, '9',"
                " 500, 'active')",
                (f"manual-test-{i}", name, i))
        # Partner request: Carl requests Dana (both free of matches at first)
        conn.execute("UPDATE items SET partner_request = 'Dana Delta'"
                     " WHERE customer = 'Carl Charlie'")
        # Pools: Pool A = Alice, Bob, Evan + one non-rostered member.
        conn.execute("INSERT INTO cmp_pools (id, season, chapter, pool_name)"
                     " VALUES (10, '2026', 'San Antonio', 'Pool A')")
        for nm, cid in [("Alice Alpha", 1), ("Bob Bravo", 2),
                        ("Evan Echo", 5), ("Zed Zulu", None)]:
            conn.execute("INSERT INTO cmp_pool_members (pool_id,"
                         " customer_name, customer_id) VALUES (10, ?, ?)",
                         (nm, cid))
        # Alice vs Evan already PLAYED; Alice vs Bob and Bob vs Evan pending.
        conn.execute(
            "INSERT INTO cmp_matches (pool_id, player1_name, player2_name,"
            " winner_name, played_at) VALUES"
            " (10, 'Alice Alpha', 'Evan Echo', 'Alice Alpha', datetime('now'))")
        conn.commit()


def main():
    tmpdir = tempfile.mkdtemp()
    tmp = Path(tmpdir) / "test.db"
    build_db(tmp)

    # ── 1. Pool-phase detection ─────────────────────────────────────
    det = db.detect_match_play_pairings(500, db_path=tmp)
    pairs = {frozenset((m["player1"], m["player2"])) for m in det["matches"]}
    print(f"pool phase: {det['phase']}, matches: {sorted(tuple(sorted(p)) for p in pairs)}")
    check("phase is pool", det["phase"] == "pool")
    check("Alice-Bob pending (no row)",
          frozenset(("Alice Alpha", "Bob Bravo")) in pairs)
    check("Bob-Evan pending (no row)",
          frozenset(("Bob Bravo", "Evan Echo")) in pairs)
    check("Alice-Evan NOT pending (played)",
          frozenset(("Alice Alpha", "Evan Echo")) not in pairs)
    check("Zed (not rostered) excluded",
          not any("Zed Zulu" in p for p in pairs))
    check("exactly 2 matches", len(pairs) == 2)

    # ── 2. Generator: confirmed matches constrain composition/seats ──
    mp = [["Alice Alpha", "Bob Bravo"]]
    res = db.generate_event_pairings(500, mp_pairs=mp, db_path=tmp)
    groups = res["9"]
    by_name = {}
    for g in groups:
        for p in g["players"]:
            by_name[p["name"]] = (g["group_num"], p["cart_pos"], p)
    ga, gb = by_name["Alice Alpha"], by_name["Bob Bravo"]
    check("MP opponents share a foursome", ga[0] == gb[0])
    check("MP opponents in OPPOSITE carts",
          (ga[1] <= 2) != (gb[1] <= 2))
    check("mp_opponent tagged on Alice", ga[2].get("mp_opponent") == "Bob Bravo")
    check("mp_opponent tagged on Bob", gb[2].get("mp_opponent") == "Alice Alpha")
    gc, gd = by_name["Carl Charlie"], by_name["Dana Delta"]
    check("partner request still honored (same group)", gc[0] == gd[0])
    check("partner pair same cart", (gc[1] <= 2) == (gd[1] <= 2))

    # ── 3. Declined match constrains nothing (run many times) ───────
    # (composition is randomized; a decline must never TAG opponents)
    res2 = db.generate_event_pairings(500, mp_pairs=[], db_path=tmp)
    tagged = [p for g in res2["9"] for p in g["players"] if p.get("mp_opponent")]
    check("no mp tags without confirmed pairs", not tagged)

    # ── 4. Partner request attaches AROUND a match ───────────────────
    with db._connect(tmp) as conn:
        conn.execute("UPDATE items SET partner_request = 'Alice Alpha'"
                     " WHERE customer = 'Fay Foxtrot'")
        conn.commit()
    res3 = db.generate_event_pairings(500, mp_pairs=mp, db_path=tmp)
    by3 = {}
    for g in res3["9"]:
        for p in g["players"]:
            by3[p["name"]] = (g["group_num"], p["cart_pos"])
    check("match survives alongside the request",
          by3["Alice Alpha"][0] == by3["Bob Bravo"][0]
          and (by3["Alice Alpha"][1] <= 2) != (by3["Bob Bravo"][1] <= 2))
    check("Fay joins Alice's match foursome",
          by3["Fay Foxtrot"][0] == by3["Alice Alpha"][0])
    check("Fay rides with Alice (same cart)",
          (by3["Fay Foxtrot"][1] <= 2) == (by3["Alice Alpha"][1] <= 2))

    # ── 5. Knockout-phase detection ──────────────────────────────────
    with db._connect(tmp) as conn:
        # SF: Alice vs Bob pending (both rostered); Carl vs Zed pending
        # (Zed not rostered); final has a lone advanced player.
        rows = [
            ("sf", 0, "Alice Alpha", 1, None),
            ("sf", 1, "Bob Bravo", 2, None),
            ("sf", 2, "Carl Charlie", 3, None),
            ("sf", 3, "Zed Zulu", None, None),
            ("final", 0, "Hana Hotel", 8, None),
        ]
        for rnd, slot, nm, cid, win in rows:
            conn.execute(
                "INSERT INTO cmp_bracket (season, chapter, round, slot,"
                " player_name, player_id, winner_name) VALUES"
                " ('2026', 'San Antonio', ?, ?, ?, ?, ?)",
                (rnd, slot, nm, cid, win))
        conn.commit()
    det2 = db.detect_match_play_pairings(500, db_path=tmp)
    pairs2 = {frozenset((m["player1"], m["player2"])) for m in det2["matches"]}
    print(f"knockout phase: {det2['phase']}, matches: {sorted(tuple(sorted(p)) for p in pairs2)}")
    check("phase flips to knockout once bracket exists",
          det2["phase"] == "knockout")
    check("pending SF matchup detected",
          frozenset(("Alice Alpha", "Bob Bravo")) in pairs2)
    check("matchup vs non-rostered player excluded",
          not any("Carl Charlie" in p for p in pairs2))
    check("half-filled final not a matchup", len(pairs2) == 1)
    check("label is Semifinal",
          det2["matches"][0]["label"] == "Semifinal")

    # Decided matchup disappears
    with db._connect(tmp) as conn:
        conn.execute("UPDATE cmp_bracket SET winner_name = 'Alice Alpha'"
                     " WHERE round = 'sf' AND slot IN (0, 1)")
        conn.commit()
    det3 = db.detect_match_play_pairings(500, db_path=tmp)
    check("decided matchup no longer detected", not det3["matches"])

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
