"""Lone Star Cup skins winners -> PAYOUTS, one row per winner per SESSION
(Kerry 10/9: "Daily Winner Amounts should go to PAYOUTS so I can easily pay
them per normal", then "Session pots standalone").

A real staff board from the Cup engine (compute_board, the ratified skins
rules) on a three-hole fixture: Saturday AM Fourball + PM Foursomes (team
net), Sunday singles (gross, two flights). Checks: the per-session plan, a
session pays as soon as IT is final (the AM while PM cards are out), the dry
run writes nothing, apply writes one tgf_payouts row per winner per FINAL
session in the shape the PAYOUTS page reads, a re-run is a no-op, a changed
result updates / removes only UNPAID rows and never a PAID one, a held
session and a mock-scored session write nothing, an old per-day row is
replaced when unpaid and holds its day when paid, and members still get no
money.

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


def session_data(am_hole1_low=True, sun_complete=False, pm_complete=True):
    am = flat(range(1, 9))
    if am_hole1_low:
        am[1][1] = 3                     # A1:austin (1 & 2) wins hole 1
    am[7][2] = 3                         # A2:sa wins hole 2: 7 bought, 8 didn't
    pm = flat([1, 2, 5, 6])              # Chapman: the ball sits on partner one
    pm[1][2] = 3                         # P1:austin (1 & 3) wins hole 2
    if not pm_complete:
        del pm[6][3]                     # P2:sa's card is still out on 3
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


def sess(res, sid):
    return next(x for x in res["sessions"] if x["session"] == sid)


def acts(res, sid):
    return {(a.get("customer_id"), a["action"]) for a in sess(res, sid)["actions"]}


def main():
    from email_parser.lsc_skins_payouts import plan_session_skins, lsc_skins_payouts
    from email_parser.lsc_cup import strip_money

    # ── the plan: one entry per SESSION, each pot standalone
    plan = plan_session_skins(board())
    am, pm, sun = (sess(plan, s) for s in ("sat-am", "sat-pm", "sun"))
    print("\nSession dry-run rows:")
    for sp in (am, pm):
        for r in sp["rows"]:
            print(f"    {sp['tag']:<7} cid {r['customer_id']} {NAMES[r['customer_id']]:<10} ${r['amount']:>7.2f}  {r['description']}")
    check("tags: SAT AM, SAT PM, SUN", (am["tag"], pm["tag"], sun["tag"]) == ("SAT AM", "SAT PM", "SUN"), plan)
    check("Saturday AM and PM are final, Sunday is not", am["final"] and pm["final"] and not sun["final"], plan)
    check("Sunday says why: a card is still out", any("cards still out" in b for b in sun["blockers"]), sun)
    a_am = {r["customer_id"]: r["amount"] for r in am["rows"]}
    a_pm = {r["customer_id"]: r["amount"] for r in pm["rows"]}
    check("AM: Al and Bo split the hole-1 skin ($43.75 each), Gus takes the FULL mixed-team skin (CA #759)",
          a_am == {1: 43.75, 2: 43.75, 7: 87.50}, a_am)
    check("PM: Al and Cy split the one Foursomes skin ($87.50 each)", a_pm == {1: 87.50, 3: 87.50}, a_pm)
    check("each session pays its OWN pot exactly ($25 x its 7 buyers)",
          am["paid_cents"] == am["pot_cents"] == 7 * 2500 and pm["paid_cents"] == pm["pot_cents"] == 7 * 2500,
          (am["pot_cents"], pm["pot_cents"]))
    d_am = next(r for r in am["rows"] if r["customer_id"] == 1)["description"]
    d_pm = next(r for r in pm["rows"] if r["customer_id"] == 1)["description"]
    check("descriptions name the session: LSC SAT AM Skins / LSC SAT PM Skins",
          d_am == "LSC SAT AM Skins — Fourball ×1 (hole 1) $43.75"
          and d_pm == "LSC SAT PM Skins — Foursomes ×1 (hole 2) $87.50", (d_am, d_pm))

    # ── a session is payable as soon as IT is final: AM pays while PM cards are out
    plan2 = plan_session_skins(board(pm_complete=False))
    check("AM final while PM is held (cards still out)",
          sess(plan2, "sat-am")["final"] and not sess(plan2, "sat-pm")["final"]
          and any("cards still out" in b for b in sess(plan2, "sat-pm")["blockers"]), plan2)

    p = _db()
    # ── dry run writes nothing
    res = lsc_skins_payouts(board=board(), db_path=p)
    check("dry run: AM 3 creates, PM 2 creates, Sunday held",
          acts(res, "sat-am") == {(1, "create"), (2, "create"), (7, "create")}
          and acts(res, "sat-pm") == {(1, "create"), (3, "create")}
          and acts(res, "sun") == {(None, "held")}, res)
    check("dry run: the tgf_events row would be created", res["tgf_event"]["state"] == "would create", res["tgf_event"])
    check("dry run wrote nothing", rows(p) == [], rows(p))

    # ── apply with PM still out: only the AM rows
    res = lsc_skins_payouts(apply=True, board=board(pm_complete=False), db_path=p)
    rs = rows(p)
    check("apply (PM out): 3 AM rows, PM held", res["writes"] == 3 and len(rs) == 3
          and all(r["description"].startswith("LSC SAT AM Skins — ") for r in rs)
          and acts(res, "sat-pm") == {(None, "held")}, res)

    # ── apply once PM is in: the PM rows join, AM untouched
    res = lsc_skins_payouts(apply=True, board=board(), db_path=p)
    rs = rows(p)
    check("apply: PM's 2 rows added, AM unchanged", res["writes"] == 2 and len(rs) == 5
          and all(a == "unchanged" for _, a in acts(res, "sat-am")), res)
    check("Al has TWO rows, one per session, never added up",
          sorted((r["description"].split(" — ")[0], r["amount"]) for r in rs if r["customer_id"] == 1)
          == [("LSC SAT AM Skins", 43.75), ("LSC SAT PM Skins", 87.5)], rs)
    check("category skins, customer_id set",
          all(r["category"] == "skins" and r["customer_id"] in (1, 2, 3, 7) for r in rs), rs)
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
          and all(a == "unchanged" for _, a in acts(res, "sat-am") | acts(res, "sat-pm"))
          and len(rows(p)) == 5, res)

    # ── Bo's AM row is PAID; then a corrected card ties AM hole 1
    conn = sqlite3.connect(p)
    conn.execute("UPDATE tgf_payouts SET paid_at = '2026-10-10' WHERE customer_id = 2")
    conn.commit()
    conn.close()
    b2 = board(am_hole1_low=False)
    res = lsc_skins_payouts(board=b2, db_path=p)
    check("changed AM result (dry run): Al's AM row deleted, Gus updated, Bo's PAID row reported not touched; PM unchanged",
          acts(res, "sat-am") == {(1, "delete"), (7, "update"), (2, "paid_no_longer_wins")}
          and acts(res, "sat-pm") == {(1, "unchanged"), (3, "unchanged")}, res)
    res = lsc_skins_payouts(apply=True, board=b2, db_path=p)
    by = {(r["customer_id"], r["description"].split(" — ")[0]): r for r in rows(p)}
    check("Gus now has the whole AM pot", by[(7, "LSC SAT AM Skins")]["amount"] == 175.0
          and by[(7, "LSC SAT AM Skins")]["t_amount"] == -175.0, by)
    check("Al keeps only his PM row", (1, "LSC SAT AM Skins") not in by
          and by[(1, "LSC SAT PM Skins")]["amount"] == 87.5, by)
    check("Bo's PAID row is untouched", by[(2, "LSC SAT AM Skins")]["amount"] == 43.75
          and by[(2, "LSC SAT AM Skins")]["paid_at"] == "2026-10-10", by)

    # ── a winner who drops out with an UNPAID row loses it
    conn = sqlite3.connect(p)
    conn.execute("UPDATE tgf_payouts SET paid_at = NULL WHERE customer_id = 2")
    conn.commit()
    conn.close()
    res = lsc_skins_payouts(apply=True, board=b2, db_path=p)
    check("an unpaid row the result no longer pays is removed (and its placeholder)",
          (2, "delete") in acts(res, "sat-am") and 2 not in {r["customer_id"] for r in rows(p)}, res)
    conn = sqlite3.connect(p)
    left = conn.execute("SELECT COUNT(*) FROM acct_transactions WHERE source = 'pending' "
                        "AND category = 'prize_payout'").fetchone()[0]
    conn.close()
    check("pending placeholders = live unpaid rows", left == len(rows(p)), (left, rows(p)))

    # ── Sunday final: its own rows, a flight each, Saturday's left alone
    b3 = board(am_hole1_low=False, sun_complete=True)
    res = lsc_skins_payouts(apply=True, board=b3, db_path=p)
    sun_rows = [r for r in rows(p) if r["description"].startswith("LSC SUN Skins")]
    check("Sunday: one row per flight winner, half the pot each",
          sorted((r["customer_id"], r["amount"]) for r in sun_rows) == [(3, 87.5), (6, 87.5)], sun_rows)
    check("Sunday description names the flight",
          sorted(r["description"] for r in sun_rows) == ["LSC SUN Skins — Flight 1 ×1 (hole 3) $87.50",
                                                        "LSC SUN Skins — Flight 2 ×1 (hole 1) $87.50"], sun_rows)
    check("Saturday untouched by the Sunday run",
          all(a == "unchanged" for _, a in acts(res, "sat-am") | acts(res, "sat-pm")), res)

    # ── a session scored from the staging MOCK dial is never paid from;
    #    the other sessions that day still pay (pots standalone)
    p2 = _db()
    res = lsc_skins_payouts(apply=True, board=board(entry=("sat-am", "sun")), db_path=p2)
    pm2 = sess(res, "sat-pm")
    check("mock-scored PM is held, the AM still pays", not pm2["final"]
          and any("not scored from entered cards" in b for b in pm2["blockers"])
          and {r["description"].split(" — ")[0] for r in rows(p2)} == {"LSC SAT AM Skins"}, res)

    # ── an OLD per-day row ("LSC SAT Skins — ..."): unpaid -> replaced by the session rows
    def _legacy_db(paid):
        q = _db()
        lsc_skins_payouts(apply=True, board=board(), db_path=q)   # creates the tgf_events row
        conn = sqlite3.connect(q)
        conn.execute("DELETE FROM tgf_payouts")
        conn.execute("DELETE FROM acct_transactions")
        tid = conn.execute("SELECT id FROM tgf_events").fetchone()[0]
        conn.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, "
                     "description, paid_at) VALUES (?, 1, 'skins', 131.25, "
                     "'LSC SAT Skins — Fourball ×1 (hole 1) $43.75 · Foursomes ×1 (hole 2) $87.50', ?)",
                     (tid, "2026-10-10" if paid else None))
        conn.commit()
        conn.close()
        return q
    p3 = _legacy_db(paid=False)
    res = lsc_skins_payouts(board=board(), db_path=p3)
    check("dry run: the unpaid per-day row is listed for removal once, beside the session creates",
          (1, "delete_legacy_day_row") in acts(res, "sat-am")
          and not any(a == "delete_legacy_day_row" for _, a in acts(res, "sat-pm")), res)
    lsc_skins_payouts(apply=True, board=board(), db_path=p3)
    descs = sorted(r["description"].split(" — ")[0] for r in rows(p3))
    check("apply: per-day row gone, 5 session rows in its place",
          "LSC SAT Skins" not in descs and len(descs) == 5, descs)

    # ...and a PAID per-day row holds the whole day for Kerry (nobody paid twice)
    p4 = _legacy_db(paid=True)
    res = lsc_skins_payouts(apply=True, board=board(), db_path=p4)
    check("a PAID per-day row holds both Saturday sessions, writes nothing for them",
          not sess(res, "sat-am")["final"] and not sess(res, "sat-pm")["final"]
          and any("PAID per-day" in b for b in sess(res, "sat-am")["blockers"])
          and len(rows(p4)) == 1 and rows(p4)[0]["paid_at"] == "2026-10-10", res)

    # ── members: no money anywhere on the board, hole scores kept
    m = strip_money(board())
    sk = m["sessions"][0]["skins"]
    g = sk["groups"][0]
    check("member board: no pot, payouts or amounts",
          "pot_cents" not in sk and "payouts" not in g and "pot_cents" not in g
          and "$" not in json.dumps(m) and "cents" not in json.dumps(sk), sk)
    check("member board keeps the Skins board's hole scores", g.get("cards") and g.get("par"), g)
    check("member board carries the partners' names for the stacked team cell",
          g["entries"]["A1:austin"]["names"] == ["Al Austin", "Bo Austin"], g.get("entries"))

    for f in (p, p2, p3, p4):
        try:
            os.remove(f)
        except OSError:
            pass
    print("\nFAILED: " + ", ".join(FAILURES) if FAILURES else "\nALL PASS")
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()


