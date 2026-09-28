"""Fall NET payout ladder = the City Net family (Kerry, CA #788 item 4)."""
import io, sys
from email_parser.database import _GG_POINTS_RACES
from email_parser import season_payouts as sp
FAIL = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    cond or FAIL.append(label)

fall = {k: v for k, v in _GG_POINTS_RACES.items() if v.get("enroll_season") == "fall"}
check("both Fall NET races are registered", sorted(fall) == ["austin_fall_net", "san_antonio_fall_net"])
check("neither is flighted, so the board resolves to the CITY NET family",
      not any(v.get("flights") for v in fall.values()))
src = io.open("email_parser/database.py", encoding="utf-8").read()
check("the 'fall ladder not ratified' hold is gone",
      "Fall payout ladder isn't ratified yet" not in src)
# Worked: $40 of every entry to the purse (Payouts v1.1 §11), same basis as City Net.
p = sp.city_net_payouts(10)
check("N=10: pot $400, 3 places (30% paid, min 2)",
      p["pot_cents"] == 40000 and len(p["amounts_cents"]) == 3, p)
check("  ...45/30/25", p["amounts_cents"] == [18000, 12000, 10000], p)
p = sp.city_net_payouts(41)
check("N=41 (illustrative field): pot $1,640, paid in full to the cent",
      p["pot_cents"] == 164000 and sum(p["amounts_cents"]) == 164000, p)
print("\n" + "=" * 50)
if FAIL: print(f"{len(FAIL)} FAILED: {FAIL}"); sys.exit(1)
print("ALL FALL-PAYOUT TESTS PASSED")
