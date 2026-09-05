#!/usr/bin/env python3
"""The money model ratified in mailbox #418 / #420 / #422.

Three rules, each of which someone will be tempted to "fix" later:

  1. TGF margin is the RESIDUAL, not the rate-card markup, and it is
     allowed to go negative. The 9-hole 1st Timer loss is a LOSS LEADER
     Kerry accepted deliberately.
  2. A membership sets aside $6 for the monthly points race AND $10 for
     Lone Star Cup shirts. A set-aside that exists in policy but not in
     code is margin that reads high forever.
  3. PAST EVENTS ARE FROZEN. An allocation dated before the cutover keeps
     the model it was booked under, because those months are already
     filed with the Comptroller.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


SHADOW = {
    "item_name": "a9.22 SHADOWGLEN", "event_date": "2026-09-08",
    "course": "ShadowGlen Golf Club", "chapter": "Austin",
    "course_cost": 43.30, "tgf_markup": 8.0, "side_game_fee": 7.0,
    "format": "9 Hole", "course_surcharge": 0.0,
}


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    os.environ["DATABASE_PATH"] = p
    with db._connect(p) as conn:
        conn.execute("""CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT,
            event_date TEXT, course TEXT, chapter TEXT, format TEXT,
            course_cost REAL, course_cost_9 REAL, course_cost_18 REAL,
            course_cost_breakdown TEXT, course_cost_breakdown_9 TEXT,
            course_cost_breakdown_18 TEXT, tgf_markup REAL,
            tgf_markup_9 REAL, tgf_markup_18 REAL, side_game_fee REAL,
            course_surcharge REAL)""")
        conn.execute("CREATE TABLE event_aliases (alias_name TEXT, "
                     "canonical_event_name TEXT)")
        conn.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, "
                     "value TEXT)")
        conn.execute(
            "INSERT INTO events (item_name, event_date, course, chapter, "
            " format, course_cost, tgf_markup, side_game_fee, course_surcharge) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (SHADOW["item_name"], SHADOW["event_date"], SHADOW["course"],
             SHADOW["chapter"], SHADOW["format"], SHADOW["course_cost"],
             SHADOW["tgf_markup"], SHADOW["side_game_fee"], 0.0))
        conn.commit()

    # ── 1. THE LOSS LEADER ───────────────────────────────────────
    # Logan Billeaud's real order: 1st Timer $44 + GROSS side game $16.
    # Rate card says $11 of markup ($8 base + $3 side). What was actually
    # left after ShadowGlen and the winners is -$3.30.
    print("The 9-hole 1st Timer is booked as the loss it actually is")
    with db._connect(p) as conn:
        a = db._calc_event_allocation(
            {"item_name": "a9.22 SHADOWGLEN", "holes": "9",
             "side_games": "GROSS", "item_price": 60.0,
             "order_date": "2026-09-10"}, conn)
    check("course is paid in full, no discount to the course",
          a["course_payable"] == 43.30, a)
    check("winners are paid in full, no discount to the pool",
          a["prize_pool"] == 20.0, a)
    check("TGF margin is the residual and it is NEGATIVE",
          a["tgf_operating"] == -3.30, a)
    check("the discount is booked as its own visible number",
          a["discount_given"] == 14.30, a)
    check("rate card + discount reconciles back to the residual",
          round(a["discount_given"] + a["tgf_operating"], 2) == 11.00, a)

    # An 18-hole clears, because $15 + $15 of markup outruns the $25
    # discount where $8 + $10 cannot. That asymmetry is the whole reason
    # 9-hole 1st Timers lose money.
    print("An 18-hole 1st Timer clears, which is why the 9s are the ones that lose")
    with db._connect(p) as conn:
        conn.execute(
            "INSERT INTO events (item_name, event_date, course, chapter, "
            " format, course_cost, tgf_markup, side_game_fee, course_surcharge) "
            "VALUES ('s18.11 CEDAR CREEK','2026-09-19','Cedar Creek', "
            " 'San Antonio','18 Hole',90.65,15.0,14.0,0.0)")
        conn.commit()
        b = db._calc_event_allocation(
            {"item_name": "s18.11 CEDAR CREEK", "holes": "18",
             "side_games": "NONE", "item_price": 110.0,
             "order_date": "2026-09-10"}, conn)
    check("the 18-hole keeps a positive margin", b["tgf_operating"] == 5.35, b)

    # A MEMBER paying full freight must be unaffected by any of this.
    print("A member paying rate card is untouched")
    with db._connect(p) as conn:
        m = db._calc_event_allocation(
            {"item_name": "a9.22 SHADOWGLEN", "holes": "9",
             "side_games": "NONE", "item_price": 59.0,
             "order_date": "2026-09-10"}, conn)
    check("full-price margin is the rounding TGF keeps, not a loss",
          m["tgf_operating"] == 8.70, m)
    check("and no discount is recorded",
          m["discount_given"] == -0.70, m)

    # ── 2. PAST EVENTS ARE FROZEN ────────────────────────────────
    print("An allocation from a filed month keeps its old numbers")
    with db._connect(p) as conn:
        old = db._calc_event_allocation(
            {"item_name": "a9.22 SHADOWGLEN", "holes": "9",
             "side_games": "GROSS", "item_price": 60.0,
             "order_date": "2026-09-04"}, conn)
    check("a pre-cutover row still books the rate-card markup",
          old["tgf_operating"] == 11.00, old)
    check("and records no discount, because that model had none",
          "discount_given" not in old, old)
    check("the SAME order after the cutover books the residual",
          a["tgf_operating"] == -3.30)

    # ── 3. THE MEMBERSHIP SET-ASIDES ─────────────────────────────
    print("A membership sets aside the points race AND the LSC shirts")
    with db._connect(p) as conn:
        mem = db._calc_membership_allocation(
            {"item_name": "TGF MEMBERSHIP", "returning_or_new": "New",
             "item_price": 50.0}, conn)
    check("$6 still goes to the monthly points race",
          mem["prize_pool"] == 6.0, mem)
    check("$10 goes to the LSC shirt fund, in its OWN bucket",
          mem["lsc_shirt_fund"] == 10.0, mem)
    check("and it comes OUT of TGF's margin: $44 becomes $34",
          mem["tgf_operating"] == 34.0, mem)
    check("the shirt fund is NOT in the prize pool — prize money is owed "
          "to winners, this is a TGF earmark",
          mem["prize_pool"] == 6.0 and mem["lsc_shirt_fund"] == 10.0, mem)

    print("The shirt set-aside is a dial, not a constant")
    with db._connect(p) as conn:
        conn.execute("INSERT OR REPLACE INTO app_settings VALUES "
                     "('membership_setaside_lsc_shirt', '12.5')")
        conn.commit()
    with db._connect(p) as conn:
        mem2 = db._calc_membership_allocation(
            {"item_name": "TGF MEMBERSHIP", "returning_or_new": "New",
             "item_price": 50.0}, conn)
    check("the dial moves it", mem2["lsc_shirt_fund"] == 12.5, mem2)
    check("and margin follows", mem2["tgf_operating"] == 31.5, mem2)
    with db._connect(p) as conn:
        conn.execute("INSERT OR REPLACE INTO app_settings VALUES "
                     "('membership_setaside_lsc_shirt', 'not a number')")
        conn.commit()
    with db._connect(p) as conn:
        mem3 = db._calc_membership_allocation(
            {"item_name": "TGF MEMBERSHIP", "returning_or_new": "New",
             "item_price": 50.0}, conn)
    check("a garbage dial falls back to $10 rather than booking zero",
          mem3["lsc_shirt_fund"] == 10.0, mem3)

    os.unlink(p)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
