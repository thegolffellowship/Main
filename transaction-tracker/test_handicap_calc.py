"""Unit vectors for the WHS playing-handicap primitives (Task #16).

The allocation vector is REAL: John Wade, a9.18 Forest Creek, White tee,
GG playing handicap 5 — GG placed his 5 strokes on the holes with stroke
index 1,3,5,7,9 (holes 2,4,5,7,8). Our allocation must reproduce that.

Run: python3 test_handicap_calc.py
"""

from email_parser.handicap_calc import (
    whs_round, course_handicap, playing_handicap, allocate_strokes)

PASS = FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}: got {got!r}, want {want!r}")


def approx(label, got, want, tol=1e-6):
    global PASS, FAIL
    if abs(got - want) <= tol:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}: got {got!r}, want {want!r}")


def main():
    # whs_round — half up toward +inf
    check("round 6.5", whs_round(6.5), 7)
    check("round 6.49", whs_round(6.49), 6)
    check("round -0.5 (plus)", whs_round(-0.5), 0)
    check("round -2.5 (plus)", whs_round(-2.5), -2)

    # course_handicap — scratch-neutral tee (slope 113, rating == par)
    approx("CH neutral", course_handicap(10.0, 113, 36.0, 36), 10.0)
    # index 10 on slope 130, rating 35, par 36: 10*130/113 + (35-36)
    approx("CH sloped", course_handicap(10.0, 130, 35.0, 36),
           10.0 * 130 / 113 + (35 - 36))

    # playing_handicap — 100% base rounds the course handicap
    check("PH neutral", playing_handicap(10.0, 113, 36.0, 36), 10)
    check("PH rounds up", playing_handicap(9.6, 113, 36.0, 36), 10)
    # 85% allowance hook
    check("PH 85pct", playing_handicap(10.0, 113, 36.0, 36, allowance=0.85), 9)
    # max cap hook
    check("PH capped", playing_handicap(40.0, 113, 36.0, 36, max_hcp=18), 18)

    # allocate_strokes — Wade's REAL a9.18 card
    wade_si = {1: 15, 2: 1, 3: 13, 4: 3, 5: 5, 6: 17, 7: 9, 8: 7, 9: 11}
    dots = allocate_strokes(5, wade_si)
    got = {h for h, s in dots.items() if s == 1}
    check("Wade PH5 lands on holes 2,4,5,7,8", got, {2, 4, 5, 7, 8})
    check("Wade sum == 5", sum(dots.values()), 5)

    # wrap: PH 12 over 9 holes -> everyone 1, three hardest (SI 1,3,5) get 2
    dots12 = allocate_strokes(12, wade_si)
    check("PH12 hole2 (SI1) = 2", dots12[2], 2)
    check("PH12 hole4 (SI3) = 2", dots12[4], 2)
    check("PH12 hole5 (SI5) = 2", dots12[5], 2)
    check("PH12 hole8 (SI7) = 1", dots12[8], 1)
    check("PH12 sum == 12", sum(dots12.values()), 12)

    # max 2 pops cap: PH 20 over 9 -> nobody exceeds 2
    dots20 = allocate_strokes(20, wade_si)
    check("PH20 capped at 2/hole", max(dots20.values()), 2)

    # plus handicap: -2 gives back on the two EASIEST holes (SI 17, 15)
    dotsm = allocate_strokes(-2, wade_si)
    check("plus -2 gives back hole6 (SI17)", dotsm[6], -1)
    check("plus -2 gives back hole1 (SI15)", dotsm[1], -1)
    check("plus -2 sum == -2", sum(dotsm.values()), -2)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
