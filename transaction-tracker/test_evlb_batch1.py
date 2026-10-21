"""EVENTS LEADERBOARD BATCH 1, server side (design-claude #2147-#2150,
Kerry-approved 2026-10-20).
- R2: ONE state value. `evlb_state` is the rule; the board, the list chip
  and board_summary.attach() all carry the same word (pain point 1).
- §2: the strip's lines; the lock time comes from the event, never a literal.
- §1: the list is paged by month and every card carries board_state.
Run: python3 test_evlb_batch1.py"""
import os, sys, tempfile, contextlib, io, logging, sqlite3
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-evlb-b1-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ.setdefault("ADMIN_PIN", "1234"); os.environ.setdefault("SECRET_KEY", "x")
os.environ["SCHEDULER_DISABLED"] = "1"
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as A  # noqa: F401
from email_parser import database as db
from email_parser import board_summary as bs

F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

print("== R2: one state rule ==")
S = db.evlb_state
check("no hole posted: UPCOMING", S(field_complete=False, holes_posted=0, held=False, closed=False) == "upcoming")
check("holes posted, field out: LIVE", S(field_complete=False, holes_posted=5, held=False, closed=True) == "live")
check("field in, not closed: IN REVIEW", S(field_complete=True, holes_posted=9, held=False, closed=False) == "in_review")
check("field in, held: IN REVIEW even if closed", S(field_complete=True, holes_posted=9, held=True, closed=True) == "in_review")
check("field in, money not final: IN REVIEW", S(field_complete=True, holes_posted=9, held=False, money_final=False, closed=True) == "in_review")
check("field in, closed: FINAL", S(field_complete=True, holes_posted=9, held=False, closed=True) == "final")

out = {"field_complete": True, "holes_posted": 9, "money_visible": True, "money_final": True, "proxies": []}
st, held = db._evlb_board_state(out, no_games=False, recorded=False, fp={"final": True, "held": True}, hold=None)
check("a held preview keeps the board IN REVIEW and says held", st == "in_review" and held is True, (st, held))
st, held = db._evlb_board_state(out, no_games=False, recorded=True, fp=None, hold=None)
check("recorded payouts: FINAL", st == "final" and not held)
st, held = db._evlb_board_state(dict(out, field_complete=False, holes_posted=3), no_games=False, recorded=True,
                                fp={"held": True}, hold={"reason": "x"})
check("a hold never shows on a LIVE board", st == "live" and held is False, (st, held))

# attach() keeps the board's value: a board the rule calls IN REVIEW (held)
# must not turn FINAL because the preview says final
lb = {"event": {}, "board_state": "in_review", "field": 4, "field_complete": True}
bs.attach(lb, db_path=tmp)
check("board_summary.attach keeps the one state (no second calculator)", lb["board_state"] == "in_review", lb["board_state"])
check("a payload without a state still gets one", bs.attach({"event": {}, "field": 0}, db_path=tmp)["board_state"] == "upcoming")

print("== §2: strip lines ==")
T = db.EVLB_STRIP_TEXT
check("UPCOMING names the first tee", T["upcoming"].format(first_tee="3:40 PM") == "Pairings are set. First tee 3:40 PM.")
check("LIVE: the one money line", T["live"] == "Money is projected until every card is in.")
check("IN REVIEW names the lock time", T["in_review"].format(lock_at="7:34 PM") == "Every score is in. Cards lock at 7:34 PM.")
check("held / FINAL", T["held"] == "Results are being checked." and T["final"] == "Results are closed and prizes are set.")
check("no strip line carries a typed minute count", not any("minute" in v for v in T.values()))
check("the lock time reads in Central", db._evlb_clock("2026-10-21T00:34:00Z") == "7:34 PM", db._evlb_clock("2026-10-21T00:34:00Z"))
check("an unreadable time is None", db._evlb_clock("nope") is None)
check("the guide no longer says 'no money shows yet' while LIVE",
      "no money shows yet" not in db.evlb_state_guide(15, 10)[1]["text"])

print("== §1: the list, paged by month ==")
c = sqlite3.connect(tmp)
for i, (name, date, ch) in enumerate([("s9.28 TPC Canyons", "2026-10-20", "San Antonio"),
                                      ("a9.28 Avery Ranch", "2026-10-20", "Austin"),
                                      ("s9.24 Brackenridge", "2026-09-22", "San Antonio"),
                                      ("s8.1 Old One", "2025-08-01", "San Antonio")], start=9101):
    c.execute("INSERT INTO events (id, item_name, event_date, chapter, format) VALUES (?,?,?,?,'9 Holes')", (i, name, date, ch))
    c.execute("INSERT INTO scoring_rounds (event_id, player_name, source) VALUES (?, 'Pat Youngs', 'gg')", (i,))
c.commit(); c.close()
d = db.get_events_leaderboard(year="2026", month="2026-10", db_path=tmp)
check("one month's cards", sorted(e["item_name"] for e in d["events"]) == ["a9.28 Avery Ranch", "s9.28 TPC Canyons"],
      [e["item_name"] for e in d["events"]])
check("every month of the season is a row with its count",
      [(m["ym"], m["count"]) for m in d["months"]] == [("2026-10", 2), ("2026-09", 1)], d["months"])
check("month labels read OCTOBER 2026", d["months"][0]["label"] == "OCTOBER 2026")
check("the seasons with events", d["years"] == ["2026", "2025"], d["years"])
check("each card carries a board_state from the one rule",
      all(e.get("board_state") in ("upcoming", "live", "in_review", "final") for e in d["events"]))
check("chapter bars: AUS orange, SA slate",
      {e["chapter"]: e["chapter_color"] for e in d["events"]} == {"Austin": "#BF5700", "San Antonio": "#44596B"})
d2 = db.get_events_leaderboard(event="s9.24 Brackenridge", db_path=tmp)
check("an event's own link opens on its month", d2["month"] == "2026-09"
      and [e["item_name"] for e in d2["events"]] == ["s9.24 Brackenridge"], d2["month"])
d3 = db.get_events_leaderboard(year="2025", db_path=tmp)
check("the season picker moves to that season's months", d3["year"] == "2025" and d3["month"] == "2025-08")

print("\n" + (f"{len(F)} FAILED: {F}" if F else "ALL PASS"))
sys.exit(1 if F else 0)
