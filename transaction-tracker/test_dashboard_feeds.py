"""dashboard.build(): the contract the page depends on.

Kerry's two rules, 2026-09-21: a card with nothing in it does not render,
and the page never dies because one feed did. Isolated from the DB layer
on purpose — the FEEDS tuple is the seam.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import dashboard as D

FAIL = []
def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + str(detail) if not cond else ""))
    if not cond: FAIL.append(label)

class _Conn:
    def __enter__(self): return self
    def __exit__(self, *a): return False

import email_parser.database as _db
_db._connect = lambda db_path=None: _Conn()

def _run(feeds):
    D.FEEDS = tuple(feeds)
    return D.build(today="2026-09-21")

print("build()")
full = lambda c, t: D._card("full", "Full", 3, "/x", "d", "do")
empty = lambda c, t: D._card("empty", "Empty", 0, "/y")
none_ = lambda c, t: None
def boom(c, t): raise RuntimeError("no such table: renewals")

r = _run([full, empty, none_])
check("a card with a count survives", [c["key"] for c in r["cards"]] == ["full"], r["cards"])
check("a ZERO-count card never reaches the page — Kerry's rule 2",
      all(c["key"] != "empty" for c in r["cards"]), r["cards"])
check("a feed returning None is simply absent", len(r["cards"]) == 1, r)
check("the total is the sum of what is shown", r["total"] == 3, r)
check("nothing skipped when every feed is healthy", r["skipped"] == [], r)

r = _run([full, boom])
check("a raising feed costs ITS OWN CARD, never the page",
      [c["key"] for c in r["cards"]] == ["full"], r["cards"])
check("...and is named in skipped so the page can say so",
      r["skipped"] and r["skipped"][0]["feed"] == "boom"
      and "no such table" in r["skipped"][0]["error"], r["skipped"])

r = _run([none_])
check("every queue clear returns an empty list, not an error",
      r["cards"] == [] and r["total"] == 0 and r["skipped"] == [], r)
check("as_of is carried for the page header", r["as_of"] == "2026-09-21", r)

print("card shape")
c = D._card("k", "T", 1, "/h")
check("tone defaults to 'do' — most cards are work", c["tone"] == "do", c)
check("an unknown tone falls back to info rather than emitting a bad class",
      D._card("k", "T", 1, "/h", tone="chartreuse")["tone"] == "info")
check("items defaults to a list, never None (the page maps over it)",
      c["items"] == [], c)

print("date helpers")
check("today reads as today", D._when(0) == "today")
check("tomorrow reads as tomorrow", D._when(1) == "tomorrow")
check("the past reads as ago", D._when(-3) == "3d ago")
check("the future reads as in Nd", D._when(4) == "in 4d")
check("an unparseable date is blank, never a crash or a wrong number",
      D._when(D._days("not-a-date", "2026-09-21")) == "")

print(("\nALL PASS" if not FAIL else f"\n{len(FAIL)} FAILURE(S): {FAIL}"))
sys.exit(1 if FAIL else 0)
