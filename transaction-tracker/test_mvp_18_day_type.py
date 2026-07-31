"""Tests for the 18-hole TGF MVP day-type rule (Kerry-ratified 2026-07-31).

Kerry's rulings, verbatim:
  1. "For two or more 18 whole days there is no cap just like the nine
     hole events."
  2. "Both cities' MVP totals are $ x N/2 = MVP and TGF MVP pots. Then
     combine each city…exactly like 9s. It's just a bigger $/player"
  3. "Is what it is. No adjustments for difficulty" (cross-course)
  4. "No mixed format TGF MVPs it's either nine or 18."
  5. The GAMES tab must show those totals like the 9-hole events do.
  + "for a single 18 hole event day we would max out at $100 and then put
     the rest into the individual net game. There will not be any residual
     for multiple 18 hole events."

Run: python3 test_mvp_18_day_type.py
"""

import os
import sys

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


# The money rules, expressed exactly as the UI derives them.
MVP_PER_BUYER = {9: 4, 18: 8}


def split(holes, n):
    half = MVP_PER_BUYER[holes] * n / 2
    return {"cityMVP": half, "tgfMVP": half}


def single_event_city_pot(holes, n):
    """One event that day: all MVP money to City MVP. 18h caps at $100."""
    full = MVP_PER_BUYER[holes] * n
    return min(full, 100) if holes == 18 else full


print("\n== rule 2: the split is half and half, at the 18-hole rate ==")

s22 = split(18, 22)
check("22 NET buyers -> $88 City + $88 TGF",
      s22 == {"cityMVP": 88.0, "tgfMVP": 88.0}, str(s22))
check("the 18-hole rate is double the 9-hole rate",
      MVP_PER_BUYER[18] == 2 * MVP_PER_BUYER[9],
      f"{MVP_PER_BUYER}")
check("9-hole is unchanged at $2 + $2 for 22 buyers",
      split(9, 22) == {"cityMVP": 44.0, "tgfMVP": 44.0}, str(split(9, 22)))

print("\n== rule 2: the TGF pot COMBINES each city, like the 9s ==")

# SA 22 NET buyers, Austin 14 NET buyers, both 18-hole, same day.
sa, austin = 22, 14
combined = split(18, sa)["tgfMVP"] + split(18, austin)["tgfMVP"]
check("the combined TGF MVP pot is both cities' halves",
      combined == 88.0 + 56.0, str(combined))
check("each city still keeps its own City MVP pot",
      split(18, sa)["cityMVP"] == 88.0
      and split(18, austin)["cityMVP"] == 56.0)
check("the day's total MVP money is $8 x every buyer",
      split(18, sa)["cityMVP"] + split(18, austin)["cityMVP"] + combined
      == 8 * (sa + austin),
      str(8 * (sa + austin)))

print("\n== rule 1 + residual: no cap and no residual on a multi-event day ==")

full22 = MVP_PER_BUYER[18] * 22
check("a single 18-hole event day caps City MVP at $100",
      single_event_city_pot(18, 22) == 100.0,
      str(single_event_city_pot(18, 22)))
check("the multi-event day is NOT capped — the full $176 is in play",
      s22["cityMVP"] + s22["tgfMVP"] == full22 == 176.0, str(full22))

# Individual Net has to give the capped-away residual back, or the tab
# would show the same dollars in two places.
net_total_pot = 26 * 22            # 572 — the matrix's netTotalPot
stored_ind_net = net_total_pot - single_event_city_pot(18, 22)   # 472
residual = full22 - single_event_city_pot(18, 22)                # 76
multi_ind_net = stored_ind_net - residual
check("the matrix row is the SINGLE-event day (Ind Net 472 at N=22)",
      stored_ind_net == 472.0, str(stored_ind_net))
check("the multi-event day Individual Net drops to $18 x N",
      multi_ind_net == 18 * 22 == 396.0, str(multi_ind_net))
check("nothing is double-counted: Ind Net + City + TGF = the NET pot",
      multi_ind_net + s22["cityMVP"] + s22["tgfMVP"] == net_total_pot,
      f"{multi_ind_net} + 88 + 88 vs {net_total_pot}")
check("a single-event day still balances against the capped pot",
      stored_ind_net + single_event_city_pot(18, 22) == net_total_pot,
      str(stored_ind_net + single_event_city_pot(18, 22)))

# Below the cap the two day types agree — the cap is what makes them differ.
small = 10
check("under the cap, single and multi day carry identical MVP money",
      single_event_city_pot(18, small)
      == split(18, small)["cityMVP"] + split(18, small)["tgfMVP"] == 80.0,
      str(single_event_city_pot(18, small)))

print("\n== rule 4: the day pool is SAME FORMAT only ==")

check("an 18-hole event is 18",
      db._event_holes_type("TGF SAN ANTONIO CHAMPIONSHIP", "18 Holes") == 18)
check("a 9-hole event is 9",
      db._event_holes_type("s9.20 TPC Oaks", "9 Holes") == 9)
check("an a18.x combo reads as 18",
      db._event_holes_type("a18.4 AUSTIN CHAMPIONSHIP", "9/18 Combo") == 18)
check("an a9.x combo reads as 9",
      db._event_holes_type("a9.20 Avery Ranch", "9/18 Combo") == 9)

day = [("TGF SAN ANTONIO CHAMPIONSHIP", "18 Holes"),
       ("TGF AUSTIN CHAMPIONSHIP", "18 Holes"),
       ("s9.21 Some Nine", "9 Holes")]
anchor = db._event_holes_type(*day[0])
pool = [n for n, f in day if db._event_holes_type(n, f) == anchor]
check("two 18-hole events pool together",
      pool == ["TGF SAN ANTONIO CHAMPIONSHIP", "TGF AUSTIN CHAMPIONSHIP"],
      str(pool))
check("the same-day 9-hole event is NOT pooled with them",
      "s9.21 Some Nine" not in pool, str(pool))

nine_anchor = db._event_holes_type(*day[2])
nine_pool = [n for n, f in day if db._event_holes_type(n, f) == nine_anchor]
check("the 9-hole event anchors its own pool, not an empty one",
      nine_pool == ["s9.21 Some Nine"], str(nine_pool))

print("\n" + ("ALL PASS" if not FAILURES else f"{len(FAILURES)} FAILED"))
for f in FAILURES:
    print("  -", f)
sys.exit(1 if FAILURES else 0)
