"""Winnings wait for EVERY hole of EVERY player, then for the settle.

Kerry 2026-09-15, mid-round, looking at $63 beside a name with three
holes posted: "Winnings should not be showing. Not all scores are in.
Every hole must be accounted for every player."

The first version of the hold trusted the clock alone — ten minutes since
the last score was written. A quiet ten minutes is not the end of a
round: it is a group between nines, a phone in a pocket, a scorer who
stopped to eat. The clock cannot tell those apart. The CARD can.

Run: python3 test_money_hold.py
"""
import os, sqlite3, sys, tempfile, contextlib, io, logging
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
logging.getLogger("email_parser.database").setLevel(logging.ERROR)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-hold-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)

EV = 9001
with db._connect(tmp) as c:
    db._ensure_scoring_tables(c)
    c.execute("INSERT INTO events (id, item_name, event_date, format) "
              "VALUES (?, 's9.99 Test', '2026-09-15', '9 Holes')", (EV,))
    # three players; one is only four holes in
    for i, (nm, holes) in enumerate([("A One", 9), ("B Two", 4), ("C Three", 9)], 1):
        c.execute("INSERT INTO scoring_rounds (id, player_name, event_id, gross) "
                  "VALUES (?,?,?,40)", (i, nm, EV))
        for h in range(1, holes + 1):
            c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, "
                      "strokes) VALUES (?,?,4)", (i, h))
    c.commit()

    print("\n== a field with cards still out is not complete ==")
    r = db._event_field_complete(c, EV, 9)
    check("the round is not complete", r["complete"] is False)
    check("and the player who is short is NAMED, not counted",
          [p["player"] for p in r["pending"]] == ["B Two"], str(r["pending"]))
    check("with how far along they are", r["pending"][0]["holes"] == 4)
    check("the hole tally is reported for the banner",
          (r["holes_posted"], r["holes_needed"]) == (22, 27), str(r))

    print("\n== a blank hole counts as missing, not as posted ==")
    c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes) "
              "VALUES (2,5,NULL)")
    c.commit()
    check("a row with no strokes on it does not close the gap",
          db._event_field_complete(c, EV, 9)["complete"] is False)

    print("\n== every hole in ⇒ complete ==")
    c.execute("UPDATE scoring_holes SET strokes = 4 WHERE scoring_round_id = 2 "
              "AND hole_number = 5")
    for h in (6, 7, 8, 9):
        c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, "
                  "strokes) VALUES (2,?,4)", (h,))
    c.commit()
    r = db._event_field_complete(c, EV, 9)
    check("the round is complete once nobody is short", r["complete"] is True, str(r))
    check("…and nobody is pending", r["pending"] == [])

    print("\n== a player's holes are the union of their rounds ==")
    # GG writes one scoring_rounds row per board; the ALL Gross row carries
    # no net. Holes hang off whichever row the import wrote them to.
    c.execute("INSERT INTO scoring_rounds (id, player_name, event_id, net) "
              "VALUES (4, 'A One', ?, 33)", (EV,))
    c.commit()
    check("a second board for a player already complete does not un-complete "
          "them", db._event_field_complete(c, EV, 9)["complete"] is True,
          str(db._event_field_complete(c, EV, 9)["pending"]))

    print("\n== an 18-hole event wants 18 ==")
    check("nine holes posted is half a card on an eighteen",
          db._event_field_complete(c, EV, 18)["complete"] is False)

    print("\n== an event with no scores at all ==")
    c.execute("INSERT INTO events (id, item_name, event_date, format) "
              "VALUES (9002, 's9.98 Empty', '2026-09-15', '9 Holes')")
    c.commit()
    check("an empty field is never 'complete' — that would post money on "
          "nothing", db._event_field_complete(c, 9002, 9)["complete"] is False)

import inspect
print("\n== 'when scores were last posted' must mean that ==")
# Kerry's hold measures its settle from imported_at. A re-import used to
# leave it alone, so the clock ran from whenever the card FIRST appeared
# — by the time the last hole landed the ten minutes had long since
# elapsed and the pot would post instantly.
_imp = inspect.getsource(db.import_gg_scorecards) if hasattr(
    db, "import_gg_scorecards") else ""
check("a CHANGED card restamps imported_at",
      "SET imported_at = " in _imp and "_changed" in _imp)
check("…and an unchanged re-import does NOT, or the money never posts",
      "if _changed:" in _imp)

print("\n== the live poll asks for TGF's day, not the container's ==")
# Kerry 2026-09-16: "Leaderboard isn't updating again." Railway runs in
# UTC, so from 7pm Central the poller asked for events dated TOMORROW and
# reported a clean sweep of zero events while a round was being played.
_src = inspect.getsource(db.poll_live_events)
check("the poller's today is Central", "today_central_str()" in _src
      and "datetime.now().strftime" not in _src, _src[:200])
check("a round that runs past midnight is still polled",
      "-6 hours" in _src and "event_date = ?" in _src)
check("has-it-started reads the Central clock too",
      "now_central()" in inspect.getsource(db._event_started))

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
