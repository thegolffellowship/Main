"""One person, one LSC seat (Kerry 2026-09-07: "Jay Hogue twice? Did we
cover someone over?").

Golf Genius opened a SECOND Austin NET line for Jay Hogue and for Matt
Sharp when they played the San Antonio 6/27 Kissing Tree event: same
member card, no affiliation tag, the 8 points on their own row. The
Fellowship Cup board inherited both rows, and the Lone Star Cup seat
allocator — which deduped the CHOICE of contest but rebuilt the holders
from the raw stream — seated Hogue twice. Austin's team read 14 seats
and 13 people; the top Austin alternate lost a place and nothing said so.

These tests pin the collapse itself, which is the mechanism every later
pass reads from.

Run: python3 test_lsc_duplicate_seats.py
"""

import os
import sys

os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser.database import _dedupe_stream_by_cid  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILURES.append(label)


def main():
    # The live Austin shape: Hogue T7 and 30th, Sharp T12 and 24th.
    cands = [
        {"name": "WADE, John", "cid": 4, "place": 5},
        {"name": "HOGUE, Jay", "cid": 37, "place": 7},
        {"name": "SHARP, Matt", "cid": 30, "place": 12},
        {"name": "REED, Paul", "cid": 15, "place": 14},
        {"name": "SHARP, Matt", "cid": 30, "place": 24},
        {"name": "HOGUE, Jay", "cid": 37, "place": 30},
    ]
    report = []
    out = _dedupe_stream_by_cid(cands, "Austin", report)

    cids = [c["cid"] for c in out]
    check("one entry per person", len(cids) == len(set(cids)), cids)
    check("four people survive, not six", len(out) == 4, out)
    check("the BEST place is the one kept",
          [(c["cid"], c["place"]) for c in out]
          == [(4, 5), (37, 7), (30, 12), (15, 14)], out)
    check("the collapse is reported, not silent", len(report) == 2, report)
    check("the report names who and what was dropped",
          sorted((r["customer_id"], r["kept_place"], r["dropped_place"])
                 for r in report) == [(30, 12, 24), (37, 7, 30)], report)

    # Order independence: the same board delivered worst-first must give
    # the same answer. The live board arrives ranked; nothing guarantees
    # the next one will, and a seat must not depend on that.
    rev_report = []
    rev = _dedupe_stream_by_cid(list(reversed(cands)), "Austin", rev_report)
    check("arrival order cannot change who is kept",
          [(c["cid"], c["place"]) for c in rev]
          == [(4, 5), (37, 7), (30, 12), (15, 14)], rev)

    # A clean board must pass through untouched — the guard has to be
    # free when there is nothing to collapse.
    clean = [{"name": "A", "cid": 1, "place": 1},
             {"name": "B", "cid": 2, "place": 2}]
    creport = []
    check("a clean stream is unchanged",
          _dedupe_stream_by_cid(clean, "Austin", creport)
          == clean and creport == [], creport)

    # Three rows for one person collapse to one.
    triple = [{"name": "X", "cid": 9, "place": 3},
              {"name": "X", "cid": 9, "place": 11},
              {"name": "X", "cid": 9, "place": 40}]
    treport = []
    out3 = _dedupe_stream_by_cid(triple, "Austin", treport)
    check("three rows for one person collapse to one",
          out3 == [{"name": "X", "cid": 9, "place": 3}]
          and len(treport) == 2, (out3, treport))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: " + ", ".join(FAILURES))
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
