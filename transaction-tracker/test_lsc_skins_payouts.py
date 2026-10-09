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


def board(entry=("sat-am", "sat-pm", "sun"), sd=None, buyers=None, **kw):
    from email_parser.lsc_cup import compute_board
    b = compute_board(dial(), sd if sd is not None else session_data(**kw), NAMES,
                      {"buyers": set(BUYERS if buyers is None else buyers),
                       "index": dict(INDEX)})
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
    carryover_and_teams()
    auto_apply_and_visibility()
    print("\nFAILED: " + ", ".join(FAILURES) if FAILURES else "\nALL PASS")
    sys.exit(1 if FAILURES else 0)





def _tied_sd(am_tied=True, pm_tied=False, sun_f2_win=True):
    """session_data with chosen sessions all-tied (no skin won)."""
    sd = session_data(sun_complete=True)
    if am_tied:
        sd["sat-am"]["scores"] = flat(range(1, 9))
    if pm_tied:
        sd["sat-pm"]["scores"] = flat([1, 2, 5, 6])
    if not sun_f2_win:
        sd["sun"]["scores"][3][1] = 4          # Flight 2: every hole tied
    return sd


def carryover_and_teams():
    """Kerry 2026-10-09, ruling 5: "If no skins are awarded in a session the
    pot moves to the next session. If foursomes moves to singles then it is
    evenly distributed to the flights." And ruling 2 / CA #759: a buyer
    makes his team eligible to WIN, only buyers are PAID."""
    from email_parser.lsc_skins_payouts import plan_session_skins
    from email_parser.lsc_cup import strip_money
    print("\nCarryover between sessions:")
    POT = 7 * 2500

    # AM no skin -> PM pot doubles
    b = board(sd=_tied_sd(am_tied=True))
    plan = plan_session_skins(b)
    am, pm, sun = (sess(plan, s) for s in ("sat-am", "sat-pm", "sun"))
    check("AM no skin: final, nothing paid, its whole pot carried out (not unallocated)",
          am["final"] and am["rows"] == [] and am["carried_out_cents"] == POT
          and am["unallocated_cents"] == 0 and am["carries_to"] == "SAT PM", am)
    check("PM pot = its own $175 + $175 carried from SAT AM",
          pm["pot_cents"] == 2 * POT and pm["own_pot_cents"] == POT
          and pm["carry_in_cents"] == POT and pm["carried_from"] == ["SAT AM"], pm)
    a_pm = {r["customer_id"]: r["amount"] for r in pm["rows"]}
    check("PM: Al and Cy split the doubled pot ($175 each)", a_pm == {1: 175.0, 3: 175.0}, a_pm)
    check("Sunday keeps its own standalone pot", sun["pot_cents"] == POT and sun["carry_in_cents"] == 0, sun)
    skam = b["sessions"][0]["skins"]
    check("staff flag on AM: the pot carries to SAT PM",
          any("carries to SAT PM" in f for f in skam["flags"]), skam["flags"])
    m = strip_money(b)
    msk = m["sessions"][1]["skins"]
    check("member board: PM names SAT AM as carried in, and no dollar anywhere",
          msk.get("carried_from") == ["SAT AM"] and m["sessions"][0]["skins"]["carries_to"] == "SAT PM"
          and "$" not in json.dumps(m) and "cents" not in json.dumps(msk), msk)

    # AM and PM no skin -> Sunday flights each + half of the carried pots
    b = board(sd=_tied_sd(am_tied=True, pm_tied=True))
    plan = plan_session_skins(b)
    pm, sun = sess(plan, "sat-pm"), sess(plan, "sun")
    check("PM no skin: carries AM + PM ($350) to SUN", pm["carried_out_cents"] == 2 * POT
          and pm["carries_to"] == "SUN" and pm["rows"] == [], pm)
    check("SUN pot = own $175 + $350 carried from SAT AM + SAT PM",
          sun["pot_cents"] == 3 * POT and sun["carry_in_cents"] == 2 * POT
          and sun["carried_from"] == ["SAT AM", "SAT PM"], sun)
    g = b["sessions"][2]["skins"]["groups"]
    check("each flight: its own half ($87.50) + half the carry ($175) = $262.50",
          [x["pot_cents"] for x in g] == [26250, 26250], [x["pot_cents"] for x in g])
    a_sun = sorted((r["customer_id"], r["amount"]) for r in sun["rows"])
    check("Sunday winners: Fi (Flight 1) and Cy (Flight 2) $262.50 each",
          a_sun == [(3, 262.5), (6, 262.5)], a_sun)
    check("every dollar of the weekend is paid: 3 pots, $525",
          sum(sp["paid_cents"] for sp in plan["sessions"]) == 3 * POT, plan)

    # an odd carry splits to the cent: largest remainder, sums exactly
    from email_parser.lsc_cup import compute_skins_payout
    sun_sess = dial()["sessions"][2]
    sd = session_data(sun_complete=True)["sun"]
    r = compute_skins_payout(sun_sess, COURSE, sd["phs"], sd["scores"], names=NAMES,
                             buyers=set(BUYERS), index=dict(INDEX), carry_in_cents=12345)
    check("an odd carry splits to the cent and the flights sum to the pot",
          sorted(x["pot_cents"] for x in r["groups"]) == [8750 + 6172, 8750 + 6173]
          and sum(x["pot_cents"] for x in r["groups"]) == r["pot_cents"] == POT + 12345, r["groups"])

    # Sunday flight with no skin: unallocated, flagged for Kerry, not invented
    b = board(sd=_tied_sd(am_tied=False, sun_f2_win=False))
    sun = sess(plan_session_skins(b), "sun")
    flags = b["sessions"][2]["skins"]["flags"]
    check("a Sunday flight with no skin: its $87.50 unallocated, nothing carried",
          sun["final"] and sun["unallocated_cents"] == 8750 and sun["carried_out_cents"] == 0
          and [r["customer_id"] for r in sun["rows"]] == [6], sun)
    check("...and flagged for Kerry (no rule given)",
          any("Flight 2" in f and "Kerry decides" in f for f in flags), flags)

    # AM not final -> PM can't be paid (its carry-in isn't known)
    sd = _tied_sd(am_tied=True)
    del sd["sat-am"]["scores"][1][3]        # A1:austin hasn't posted hole 3
    del sd["sat-am"]["scores"][2][3]
    b = board(sd=sd)
    plan = plan_session_skins(b)
    pm = sess(plan, "sat-pm")
    check("AM cards out: PM is held, its carry-in not known yet",
          not pm["final"] and any("SAT AM isn't final yet" in x for x in pm["blockers"])
          and pm["carry_in_cents"] == 0, pm)
    check("...and so is Sunday (the chain waits on SAT AM)",
          any("SAT AM isn't final yet" in x for x in sess(plan, "sun")["blockers"]), sess(plan, "sun"))

    # a pot carried from a MOCK-scored session is never paid from
    b = board(sd=_tied_sd(am_tied=True), entry=("sat-pm", "sun"))
    pm = sess(plan_session_skins(b), "sat-pm")
    check("a carry from a mock-scored session holds the receiving session",
          not pm["final"] and any("carried from sat-am" in x for x in pm["blockers"]), pm)

    print("\nMixed teams (ruling 2, CA #759):")
    # Hal (8, NOT a buyer) is Gus's (7, buyer) partner on A2:sa. Hal's ball
    # wins hole 2 for the team; Gus is paid the FULL team skin, Hal nothing.
    sd = session_data()
    sd["sat-am"]["scores"][7][2] = 4
    sd["sat-am"]["scores"][8][2] = 3
    am = sess(plan_session_skins(board(sd=sd)), "sat-am")
    a_am = {r["customer_id"]: r["amount"] for r in am["rows"]}
    check("the NON-buyer's ball wins the hole for the mixed team; the buyer gets the full team skin",
          a_am == {1: 43.75, 2: 43.75, 7: 87.5} and 8 not in a_am, a_am)
    # a team with NO buyer (7 and 8 both out) is out entirely: its 3s can
    # neither win a hole nor tie one out
    sd = session_data(am_hole1_low=True)
    sd["sat-am"]["scores"][8][1] = 3        # ties A1:austin's 3 on hole 1
    sd["sat-am"]["scores"][7][2] = 3        # would win hole 2 alone
    b = board(sd=sd, buyers={1, 2, 3, 4, 5, 6})
    g = b["sessions"][0]["skins"]["groups"][0]
    hs = {h["hole"]: h for h in g["holes"]}
    check("no-buyer team: can't tie out hole 1 (A1:austin still wins it)",
          hs[1]["status"] == "won" and hs[1]["winner"] == "A1:austin", hs[1])
    check("no-buyer team: can't win hole 2 (nobody wins it)", hs[2]["status"] != "won", hs[2])
    check("no-buyer team is not an entry and is listed as excluded",
          "A2:sa" not in {t["key"] for t in g["totals"]}
          and any(x["team"] == "sa" and x["reason"] == "not bought in"
                  for x in b["sessions"][0]["skins"]["excluded"]), g["totals"])
    am = sess(plan_session_skins(b), "sat-am")
    check("only A1:austin is paid, the whole $150 pot (6 buyers)",
          {r["customer_id"]: r["amount"] for r in am["rows"]} == {1: 75.0, 2: 75.0}, am["rows"])

    print("\nSunday non-buyers, display only (Show All Players):")
    sd = session_data(sun_complete=True)
    sd["sun"]["scores"][8][2] = 3           # Hal (non-buyer, Flight 2 by index 20)
    b = board(sd=sd)
    g2 = b["sessions"][2]["skins"]["groups"][1]
    hal = [o for o in g2.get("others") or [] if o["customer_id"] == 8]
    check("Hal is listed in Flight 2's others with his gross card",
          hal and hal[0]["card"]["2"] == [3, 0] and hal[0]["index"] == 20.0, g2.get("others"))
    check("...but never an entry: his 3 doesn't win hole 2",
          8 not in {int(k.split(":")[-1]) for k in (t["key"] for t in g2["totals"])}
          and next(h for h in g2["holes"] if h["hole"] == 2)["status"] != "won", g2["holes"])
    m = strip_money(b)
    mo = m["sessions"][2]["skins"]["groups"][1]["others"]
    check("members get the others (names, index, gross) and still no money",
          mo and mo[0]["name"] == "Hal Sa" and "$" not in json.dumps(m), mo)


def auto_apply_and_visibility():
    """Kerry 10/9: "Ok to write payouts 15 minutes after all sessions are
    final" / "Yes when rounds complete" / "3. Yes definitely" (Winnings)."""
    from datetime import datetime, timedelta
    from email_parser import database as db
    from email_parser.lsc_skins_payouts import (lsc_skins_auto_check, auto_state,
                                                lsc_skins_payouts)
    print("\nAuto-apply:")
    p = _db()
    sat = datetime(2026, 10, 10, 12, 0, 0)
    b = board()                                   # AM + PM final, Sunday out
    r = lsc_skins_auto_check(db_path=p, now=sat, board=b)
    check("first sight of final: stamped, nothing written", r.get("status") == "waiting"
          and set(r["final_seen"]) == {"sat-am", "sat-pm"} and rows(p) == [], r)
    r = lsc_skins_auto_check(db_path=p, now=sat + timedelta(minutes=14), board=b)
    check("14 minutes: still nothing", r.get("status") == "waiting" and rows(p) == [], r)
    st = auto_state(db_path=p, board=b, now=sat + timedelta(minutes=14))
    am_st = next(x for x in st["sessions"] if x["session"] == "sat-am")
    check("auto_state reports the setting, final_seen and payable_at",
          st["enabled"] and st["in_window"] and am_st["final_seen"] == "2026-10-10 12:00:00"
          and am_st["payable_at"] == "2026-10-10 12:15:00" and not am_st["payable_now"], st)
    r = lsc_skins_auto_check(db_path=p, now=sat + timedelta(minutes=15), board=b)
    check("15 minutes: AM + PM applied (5 rows), Sunday not", r.get("status") == "applied"
          and r["writes"] == 5 and len(rows(p)) == 5
          and not any(x["description"].startswith("LSC SUN") for x in rows(p)), r)
    conn = sqlite3.connect(p)
    logs = conn.execute("SELECT agent_name, action_type FROM agent_action_log").fetchall()
    conn.close()
    check("the auto-apply is in the agent action log",
          ("scheduler", "lsc-skins-payouts-auto") in logs, logs)
    r = lsc_skins_auto_check(db_path=p, now=sat + timedelta(minutes=20), board=b)
    check("re-run: idempotent, writes nothing", r.get("status") == "up to date"
          and r["writes"] == 0 and len(rows(p)) == 5, r)

    # a corrected AM card after apply: the UNPAID rows it owns follow
    b2 = board(am_hole1_low=False)
    r = lsc_skins_auto_check(db_path=p, now=sat + timedelta(minutes=30), board=b2)
    by = {(x["customer_id"], x["description"].split(" — ")[0]): x["amount"] for x in rows(p)}
    check("a correction after apply updates the unpaid AM rows (Gus now $175)",
          r.get("status") == "applied" and by.get((7, "LSC SAT AM Skins")) == 175.0
          and (1, "LSC SAT AM Skins") not in by, by)
    # a session that stops being final restarts its clock
    r = lsc_skins_auto_check(db_path=p, now=sat + timedelta(minutes=35),
                             board=board(am_hole1_low=False, pm_complete=False))
    check("PM reopened: its final stamp is dropped (the 15 minutes restart)",
          "sat-pm" not in r["final_seen"] and "sat-am" in r["final_seen"], r)

    # Sunday pays 15 min after Sunday is final
    sun_t = datetime(2026, 10, 11, 15, 0, 0)
    b3 = board(am_hole1_low=False, sun_complete=True)
    lsc_skins_auto_check(db_path=p, now=sun_t, board=b3)
    r = lsc_skins_auto_check(db_path=p, now=sun_t + timedelta(minutes=10), board=b3)
    check("Sunday final 10 min: not yet", not any(x["description"].startswith("LSC SUN") for x in rows(p)), r)
    r = lsc_skins_auto_check(db_path=p, now=sun_t + timedelta(minutes=16), board=b3)
    check("Sunday final 16 min: Sunday rows written",
          sorted((x["customer_id"], x["amount"]) for x in rows(p) if x["description"].startswith("LSC SUN"))
          == [(3, 87.5), (6, 87.5)], r)

    # a PAID row is never touched by the auto job
    conn = sqlite3.connect(p)
    conn.execute("UPDATE tgf_payouts SET paid_at = '2026-10-11' WHERE customer_id = 6")
    conn.commit()
    conn.close()
    sd = session_data(am_hole1_low=False, sun_complete=True)
    sd["sun"]["scores"][6][3] = 4                 # Fi's skin corrected away
    sd["sun"]["scores"][5][3] = 3                 # Ed wins it instead
    r = lsc_skins_auto_check(db_path=p, now=sun_t + timedelta(minutes=40), board=board(sd=sd))
    fi = [x for x in rows(p) if x["customer_id"] == 6]
    check("auto never touches a PAID row (Fi's paid Sunday row stays)",
          len(fi) == 1 and fi[0]["paid_at"] == "2026-10-11" and fi[0]["amount"] == 87.5, fi)

    # setting off = nothing; outside the dates = nothing
    q = _db()
    db.set_app_setting("lsc_skins_auto", "0", db_path=q)
    r = lsc_skins_auto_check(db_path=q, now=sat + timedelta(hours=2), board=b)
    r2 = lsc_skins_auto_check(db_path=q, now=sat + timedelta(hours=3), board=b)
    check("lsc_skins_auto=0: nothing stamped, nothing written",
          "off" in (r.get("skipped") or "") and "off" in (r2.get("skipped") or "") and rows(q) == []
          and not db.get_app_setting("lsc_skins_final_seen", db_path=q), r)
    db.set_app_setting("lsc_skins_auto", "", db_path=q)
    for when in (datetime(2026, 10, 9, 23, 0), datetime(2026, 10, 13, 9, 0)):
        r = lsc_skins_auto_check(db_path=q, now=when, board=b)
        check(f"outside the Cup's dates ({when.date()}): nothing",
              "outside" in (r.get("skipped") or "") and rows(q) == [], r)

    print("\nMember visibility (Winnings / Spotlight):")
    w = db.get_customer_winnings("", db_path=p, customer_id=7)
    gus = [x for x in w["payouts"] if (x["description"] or "").startswith("LSC SAT AM Skins")]
    check("Winnings (get_customer_winnings, Spotlight's source) lists the Cup skins row",
          gus and gus[0]["category"] == "skins" and gus[0]["amount"] == 175.0
          and gus[0]["event_name"] == "2026 LONE STAR CUP"
          and str(gus[0]["event_date"]).startswith("2026-10-10"), w)
    wbg = db._winnings_by_game(w["payouts"], db.get_winnings_bundles(p), 2026)
    gross = next(x for x in wbg["by_year"]["2026"] if x["key"] == "gross")
    check("Spotlight Winnings by Game: in the 2026 season, Skins under GROSS Games",
          any(gm["category"] == "skins" and gm["total"] >= 175.0 for gm in gross["games"]), gross)
    # a found tgf_events row with no date is healed on apply (season scope)
    conn = sqlite3.connect(p)
    conn.execute("UPDATE tgf_events SET event_date = ''")
    conn.commit()
    conn.close()
    lsc_skins_payouts(apply=True, db_path=p, board=board(sd=sd))
    conn = sqlite3.connect(p)
    d = conn.execute("SELECT event_date FROM tgf_events").fetchone()[0]
    conn.close()
    check("apply heals a dateless tgf_events row so Winnings' season view keeps it",
          str(d).startswith("2026-10-10"), d)
    for f in (p, q):
        try:
            os.remove(f)
        except OSError:
            pass


if __name__ == "__main__":
    main()
