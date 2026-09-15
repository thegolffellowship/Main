"""First timer = FIRST EVENT, and the pairings count report.

Kerry 2026-09-15, looking at the s9.23 sheet: "any 1st Timer, even if
they've become a member already and didn't select 1st timer should be
highlighted as a first timer. So Morris Allen should be highlighted even
though he joined already, because it's his first event." Plus: "produce
a pairings count report ... how many times has each player played with
the others in their groups this year including tonight."

Run: python3 test_pairing_counts.py
"""
import os, sqlite3, sys, tempfile, contextlib, io, logging
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
logging.getLogger("email_parser.database").setLevel(logging.ERROR)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-pc-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
EV, PRIOR = 3302, 3100
TONIGHT, EARLIER = "2026-09-15", "2026-06-10"
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (?, 's9.23 The Quarry', ?, 'San Antonio', 'active')", (EV, TONIGHT))
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (?, 's6.10 Silverhorn', ?, 'San Antonio', 'active')", (PRIOR, EARLIER))

# 1 Morris: joined as a MEMBER this year, never played an event.
# 2 Daniel: a member who played in June.
# 3 Larry: no order history at all, but handicap rounds from GG in May.
# 4 Jose: the order says 1ST TIMER.
PEOPLE = [(1, "Morris", "Allen"), (2, "Daniel", "South"),
          (3, "Larry", "Anthis"), (4, "Jose", "Mejia")]
for cid, f, l in PEOPLE:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) VALUES (?, ?, ?, 'San Antonio', 'active')", (cid, f, l))
def item(iid, cid, name, ev, evdate, status="MEMBER", tx="active", item_name="s9.23 The Quarry"):
    c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, user_status, tee_choice) "
              "VALUES (?, ?, 'The Golf Fellowship', ?, ?, ?, ?, ?, ?, ?, '50-64')",
              (iid, f"u{iid}", name, cid, item_name, evdate, tx, ev, status))
# tonight's roster
item(1, 1, "Morris Allen", EV, TONIGHT)
item(2, 2, "Daniel South", EV, TONIGHT)
item(3, 3, "Larry Anthis", EV, TONIGHT)
item(4, 4, "Jose Mejia",   EV, TONIGHT, status="1ST TIMER")
# Morris's MEMBERSHIP purchase — a buy-in, not an event
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status) "
          "VALUES (90, 'u90', 'The Golf Fellowship', 'Morris Allen', 1, 'TGF MEMBERSHIP', '2026-08-02', 'active')")
# Daniel played in June
item(91, 2, "Daniel South", PRIOR, EARLIER, item_name="s6.10 Silverhorn")
# Larry has GG rounds and no orders before tonight
c.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES ('Larry Anthis', 'Larry Anthis', 3)")
c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) VALUES ('Larry Anthis', '2026-05-04', 92, 71.2, 128, 18.4)")
c.commit()

print("\n== 1st timer = first EVENT, not the checkout label ==")
roster = {r["name"]: r for r in db._event_roster_rows(c, EV)}
check("a member who joined this year and never played reads 1ST TIMER (Morris Allen)",
      roster["Morris Allen"]["is_first_timer"] is True, str(sorted(roster)))
check("…a membership purchase is not an event", roster["Morris Allen"]["experience"] >= 2)
check("a member who played an earlier event does NOT (Daniel South)",
      roster["Daniel South"]["is_first_timer"] is False)
check("handicap rounds before the event are proof of play, with no order (Larry Anthis)",
      roster["Larry Anthis"]["is_first_timer"] is False)
check("the explicit 1ST TIMER label still stands on its own (Jose Mejia)",
      roster["Jose Mejia"]["is_first_timer"] is True)
_rows = [{"name": "Ghost", "customer_id": None, "is_first_timer": False}]
db._mark_first_timers(c, EV, _rows)
check("a roster row with no customer_id is never invented into a 1st timer",
      _rows[0]["is_first_timer"] is False)

print("\n== the count report: history + tonight ==")
db._ensure_pairing_tables(c)   # the pairing tables are lazy, as in the app
for grp, names in ((1, ["Daniel South", "Morris Allen", "Larry Anthis", "Jose Mejia"]),):
    for pos, nm in enumerate(names, start=1):
        c.execute("INSERT INTO event_pairings (event_id, holes, group_num, slot_label, player_name, cart_pos, tee_choice) "
                  "VALUES (?, '9', ?, '1A', ?, ?, '50-64')", (EV, grp, nm, pos))
def hist(a, b, ev, d, source="gg"):
    c.execute("INSERT INTO pairing_history (player_a, player_b, event_id, event_date, source) VALUES (?, ?, ?, ?, ?)",
              (min(a, b), max(a, b), ev, d, source))
hist("Daniel South", "Larry Anthis", PRIOR, EARLIER)                 # played once
hist("Daniel South", "Larry Anthis", 3101, "2026-04-02")             # and again
hist("Daniel South", "Morris Allen", 3102, "2026-07-01", source="app")  # a PLAN, not played
hist("Larry Anthis", "Morris Allen", EV, TONIGHT)                    # tonight's own row
c.commit()
rep = db.pairing_counts_report(EV, db_path=tmp)
pair = {frozenset((p["a"], p["b"])): p for p in rep["groups"][0]["pairs"]}
check("every pair in the group is scored", len(pair) == 6, str(len(pair)))
check("two played rounds + tonight = 3", pair[frozenset(("Daniel South", "Larry Anthis"))]["total"] == 3)
check("a pair that has never met reads 1 (tonight)", pair[frozenset(("Morris Allen", "Jose Mejia"))]["total"] == 1)
check("an app-saved sheet is a plan, not history", pair[frozenset(("Daniel South", "Morris Allen"))]["total"] == 1)
check("the event never counts against itself", pair[frozenset(("Larry Anthis", "Morris Allen"))]["total"] == 1)
check("seats 1&2 are marked as riding together", pair[frozenset(("Daniel South", "Morris Allen"))]["rode"] is True)
check("seats 2&3 are not", pair[frozenset(("Morris Allen", "Larry Anthis"))]["rode"] is False)
check("repeats are pulled out for the manager", rep["n_repeat_pairs"] == 1 and rep["highest_pair_count"] == 3, str(rep["repeats"]))
_pp = {p["name"]: p for p in rep["groups"][0]["per_player"]}
check("each player gets a line naming his three mates", all(len(v["mates"]) == 3 for v in _pp.values()))
check("…carrying the roster's own marks", _pp["Morris Allen"]["is_first_timer"] is True and _pp["Daniel South"]["is_first_timer"] is False)
check("the text rendering names the event and the year", "s9.23 The Quarry" in rep["text"] and "2026" in rep["text"])
check("a second run is stable (read-only)", db.pairing_counts_report(EV, db_path=tmp)["n_repeat_pairs"] == 1)

print("\n== the roster's counts, as the cards get them ==")
rc = db.roster_pair_counts(c, EV, ["Daniel South", "Larry Anthis", "Morris Allen", "Jose Mejia"])
check("keyed 'a|b' on normalized names, PRIOR counts only (tonight is the page's +1)",
      rc.get("daniel south|larry anthis") == 2, str(rc))
check("pairs with no history are left out, not sent as 0",
      "jose mejia|morris allen" not in rc and "morris allen|jose mejia" not in rc, str(rc))
check("a player off this roster is never shipped",
      all("richard palacios" not in k for k in rc), str(rc))
check("the app-saved plan and this event's own rows stay out",
      "daniel south|morris allen" not in rc and "larry anthis|morris allen" not in rc, str(rc))
_rc2 = db.roster_pair_counts(c, EV, [])
check("an empty roster asks nothing of the database", _rc2 == {})

print("\nALL PASSED" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
