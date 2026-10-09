"""Lone Star Cup DAILY skins winners -> PAYOUTS (Kerry 10/9: "Daily Winner
Amounts should go to PAYOUTS so I can easily pay them per normal").

A real staff board from the Cup engine (compute_board, the ratified skins
rules) on a three-hole fixture: Saturday AM Fourball + PM Foursomes (team
net), Sunday singles (gross, two flights). Checks: the per-day plan, the dry
run writes nothing, apply writes one tgf_payouts row per winner per FINAL
day in the shape the PAYOUTS page reads, a re-run is a no-op, a changed
result updates / removes only UNPAID rows and never a PAID one, a held day
and a mock-scored session write nothing, and members still get no money.

Run: python3 test_lsc_skins_payouts.py
"""

import json
import os
import sqlite3
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else "  " + str(detail)[:900]))
    if not cond:
        FAILURES.append(label)


COURSE = [{"hole": h, "par": 4, "stroke_index": h} for h in (1, 2, 3)]
NAMES = {1: "Al Austin", 2: "Bo Austin", 3: "Cy Austin", 4: "Di Austin",
         5: "Ed Sa", 6: "Fi Sa", 7: "Gus Sa", 8: "Hal Sa"}
BUYERS = {1, 2, 3, 4, 5, 6, 7}           # 8 did not buy in
INDEX = {1: 5.0, 2: 6.0, 3: 15.0, 4: 16.0, 5: 7.0, 6: 8.0, 7: 18.0, 8: 20.0}


def dial():
    return {"event_id": 3329, "sessions": [
        {"id": "sat-am", "date": "2026-10-10", "format": "fourball", "n_holes": 3,
         "se_round": 1,
         "matches": [{"id": "A1", "austin": [1, 2], "sa": [5, 6]},
                     {"id": "A2", "austin": [3, 4], "sa": [7, 8]}]},
        {"id": "sat-pm", "date": "2026-10-10", "format": "chapman", "n_holes": 3,
         "se_round": 2,
         "matches": [{"id": "P1", "austin": [1, 3], "sa": [5, 7]},
                     {"id": "P2", "austin": [2, 4], "sa": [6, 8]}]},
        {"id": "sun", "date": "2026-10-11", "format": "singles", "n_holes": 3,
         "se_round": 3,
         "matches": [{"id": "S1", "austin": [1], "sa": [5]},
                     {"id": "S2", "austin": [2], "sa": [6]},
                     {"id": "S3", "austin": [3], "sa": [7]},
                     {"id": "S4", "austin": [4], "sa": [8]}]}]}


def flat(cids, g=4):
    return {c: {1: g, 2: g, 3: g} for c in cids}


def session_data(am_hole1_low=True, sun_complete=False):
    am = flat(range(1, 9))
    if am_hole1_low:
        am[1][1] = 3                     # A1:austin (1 & 2) wins hole 1
    am[7][2] = 3                         # A2:sa wins hole 2: 7 bought, 8 didn't
    pm = flat([1, 2, 5, 6])              # Chapman: the ball sits on partner one
    pm[1][2] = 3                         # P1:austin (1 & 3) wins hole 2
    sun = flat(range(1, 9))
    sun[6][3] = 3                        # Flight 1: Fi wins hole 3
    sun[3][1] = 3                        # Flight 2: Cy wins hole 1
    if not sun_complete:
        del sun[4][3]                    # Di's card is still out on 3
    zero = {c: 0 for c in range(1, 9)}
    return {"sat-am": {"course": COURSE, "phs": zero, "scores": am},
            "sat-pm": {"course": COURSE, "phs": zero, "scores": pm},
            "sun": {"course": COURSE, "phs": zero, "scores": sun}}


def board(entry=("sat-am", "sat-pm", "sun"), **kw):
    from email_parser.lsc_cup import compute_board
    b = compute_board(dial(), session_data(**kw), NAMES,
                      {"buyers": set(BUYERS), "index": dict(INDEX)})
    b.update({"configured": True, "source": "entry", "entry_sessions": list(entry)})
    return b


def _db():
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    from email_parser import database as db
    db.init_db(p)
    conn = sqlite3.connect(p)
    conn.execute("INSERT INTO events (id, item_name, event_date, course, chapter) "
                 "VALUES (3329, '2026 LONE STAR CUP', '2026-10-10', 'The Hideout', 'TGF')")
    for c, nm in NAMES.items():
        f, l = nm.split()
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) "
                     "VALUES (?, ?, ?)", (c, f, l))
    conn.commit()
    conn.close()
    return p


def rows(p):
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    out = [dict(r) for r in conn.execute(
        "SELECT p.*, t.source AS t_source, t.amount AS t_amount FROM tgf_payouts p "
        "LEFT JOIN acct_transactions t ON t.id = p.acct_transaction_id ORDER BY p.id")]
    conn.close()
    return out


def acts(res, day):
    d = next(x for x in res["days"] if x["day"] == day)
    return {(a.get("customer_id"), a["action"]) for a in d["actions"]}


def main():
    from email_parser.lsc_skins_payouts import plan_daily_skins, lsc_skins_payouts
    from email_parser.lsc_cup import strip_money

    # ── the plan: Saturday final (AM + PM added up per winner), Sunday held
    plan = plan_daily_skins(board())
    sat = next(d for d in plan["days"] if d["day"] == "SAT")
    sun = next(d for d in plan["days"] if d["day"] == "SUN")
    amt = {r["customer_id"]: r["amount"] for r in sat["rows"]}
    print("\nSaturday dry-run rows:")
    for r in sat["rows"]:
        print(f"    cid {r['customer_id']} {NAMES[r['customer_id']]:<10} ${r['amount']:>7.2f}  {r['description']}")
    check("Saturday is final, Sunday is not", sat["final"] and not sun["final"], plan)
    check("Sunday says why: a card is still out", any("cards still out" in b for b in sun["blockers"]), sun)
    check("Saturday: Al = AM half-skin + PM half-skin ($43.75 + $87.50)", amt.get(1) == 131.25, amt)
    check("Saturday: Bo = AM half-skin only", amt.get(2) == 43.75, amt)
    check("Saturday: Cy = PM half-skin only", amt.get(3) == 87.50, amt)
    check("Saturday: Gus takes the FULL mixed-team skin (CA #759)", amt.get(7) == 87.50 and 8 not in amt, amt)
    check("Saturday pays both pots exactly", sat["paid_cents"] == 2 * 7 * 2500 == sat["pot_cents"], sat)
    d1 = next(r for r in sat["rows"] if r["customer_id"] == 1)["description"]
    check("description: LSC SAT Skins, each session's skins, holes and amount",
          d1.startswith("LSC SAT Skins — ") and "Fourball ×1 (hole 1) $43.75" in d1
          and "Foursomes ×1 (hole 2) $87.50" in d1, d1)

    p = _db()
    # ── dry run writes nothing
    res = lsc_skins_payouts(board=board(), db_path=p)
    check("dry run: four creates on Saturday, Sunday held",
          acts(res, "SAT") == {(1, "create"), (2, "create"), (3, "create"), (7, "create")}
          and acts(res, "SUN") == {(None, "held")}, res)
    check("dry run: the tgf_events row would be created", res["tgf_event"]["state"] == "would create", res["tgf_event"])
    check("dry run wrote nothing", rows(p) == [], rows(p))

    # ── apply: one row per winner per final day, the normal shape
    res = lsc_skins_payouts(apply=True, board=board(), db_path=p)
    rs = rows(p)
    check("apply wrote 4 rows", res["writes"] == 4 and len(rs) == 4, res)
    check("category skins, LSC SAT Skins description, customer_id set",
          all(r["category"] == "skins" and r["description"].startswith("LSC SAT Skins")
              and r["customer_id"] in (1, 2, 3, 7) for r in rs), rs)
    check("each row has its PENDING ledger placeholder (Pay link)",
          all(r["t_source"] == "pending" and abs(r["t_amount"] + r["amount"]) < 0.005 for r in rs), rs)
    conn = sqlite3.connect(p)
    ev = conn.execute("SELECT id, events_id, total_purse, winners_count FROM tgf_events").fetchall()
    conn.close()
    check("the cup's tgf_events row carries events_id 3329 and the purse",
          len(ev) == 1 and ev[0][1] == 3329 and abs(ev[0][2] - 350.0) < 0.005 and ev[0][3] == 4, ev)

    # ── re-run: nothing changes
    res = lsc_skins_payouts(apply=True, board=board(), db_path=p)
    check("re-run is a no-op", res["writes"] == 0
          and all(a == "unchanged" for _, a in acts(res, "SAT")) and len(rows(p)) == 4, res)

    # ── Bo's row is PAID; then a corrected card ties AM hole 1
    conn = sqlite3.connect(p)
    conn.execute("UPDATE tgf_payouts SET paid_at = '2026-10-10' WHERE customer_id = 2")
    conn.commit()
    conn.close()
    b2 = board(am_hole1_low=False)
    res = lsc_skins_payouts(board=b2, db_path=p)
    check("changed result (dry run): Al + Gus update, Cy unchanged, Bo's PAID row reported not touched",
          acts(res, "SAT") == {(1, "update"), (3, "unchanged"), (7, "update"),
                               (2, "paid_no_longer_wins")}, res)
    res = lsc_skins_payouts(apply=True, board=b2, db_path=p)
    by = {r["customer_id"]: r for r in rows(p)}
    check("Al's unpaid row now $87.50, its placeholder follows",
          by[1]["amount"] == 87.5 and by[1]["t_amount"] == -87.5, by[1])
    check("Gus now has the whole AM pot", by[7]["amount"] == 175.0, by[7])
    check("Bo's PAID row is untouched", by[2]["amount"] == 43.75 and by[2]["paid_at"] == "2026-10-10", by[2])

    # ── a winner who drops out with an UNPAID row loses it
    conn = sqlite3.connect(p)
    conn.execute("UPDATE tgf_payouts SET paid_at = NULL WHERE customer_id = 2")
    conn.commit()
    conn.close()
    res = lsc_skins_payouts(apply=True, board=b2, db_path=p)
    check("an unpaid row the result no longer pays is removed (and its placeholder)",
          (2, "delete") in acts(res, "SAT") and 2 not in {r["customer_id"] for r in rows(p)}, res)
    conn = sqlite3.connect(p)
    left = conn.execute("SELECT COUNT(*) FROM acct_transactions WHERE source = 'pending' "
                        "AND category = 'prize_payout'").fetchone()[0]
    conn.close()
    check("pending placeholders = live unpaid rows", left == len(rows(p)), (left, rows(p)))

    # ── Sunday final: its own rows, Saturday's left alone
    b3 = board(am_hole1_low=False, sun_complete=True)
    res = lsc_skins_payouts(apply=True, board=b3, db_path=p)
    sun_rows = [r for r in rows(p) if r["description"].startswith("LSC SUN Skins")]
    check("Sunday: one row per flight winner, half the pot each",
          sorted((r["customer_id"], r["amount"]) for r in sun_rows) == [(3, 87.5), (6, 87.5)], sun_rows)
    check("Saturday untouched by the Sunday run", all(a == "unchanged" for _, a in acts(res, "SAT")), res)

    # ── a session scored from the staging MOCK dial is never paid from
    p2 = _db()
    res = lsc_skins_payouts(apply=True, board=board(entry=("sat-am", "sun")), db_path=p2)
    sat2 = next(d for d in res["days"] if d["day"] == "SAT")
    check("mock-scored session holds its whole day", not sat2["final"]
          and any("not scored from entered cards" in b for b in sat2["blockers"])
          and rows(p2) == [], sat2)

    # ── members: no money anywhere on the board, hole scores kept
    m = strip_money(board())
    sk = m["sessions"][0]["skins"]
    g = sk["groups"][0]
    check("member board: no pot, payouts or amounts",
          "pot_cents" not in sk and "payouts" not in g and "pot_cents" not in g
          and "$" not in json.dumps(m) and "cents" not in json.dumps(sk), sk)
    check("member board keeps the Skins board's hole scores", g.get("cards") and g.get("par"), g)

    for f in (p, p2):
        try:
            os.remove(f)
        except OSError:
            pass
    print("\nFAILED: " + ", ".join(FAILURES) if FAILURES else "\nALL PASS")
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
