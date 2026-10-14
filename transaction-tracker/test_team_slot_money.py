"""TEAM money per SLOT from the GAMES money (Kerry 2026-10-13): "In the case
where a blind helps their team win and they are on another team that wins the
person takes the higher total and doesn't get any of the lower. The lower is
divided equally amongst the rest of the team. In Stu's case he wins the full
amount of $26. While Robert and Luke split the $52 for first."

Run: python3 test_team_slot_money.py
"""
import logging
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
logging.disable(logging.CRITICAL)
from email_parser import database as db  # noqa: E402

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


def tn(c):
    return [{"category": "team_net", "cents": c}]


print("Austin a9.27: Straiton on the 1st-place cart and blind on the 2nd")
teams = [{"players": [{"player_name": "Robert Straiton", "customer_id": 31},
                      {"player_name": "Luke Youngs", "customer_id": 13}]},
         {"players": [{"player_name": "Stu Kirksey", "customer_id": 48},
                      {"player_name": "Bl[Robert Straiton]", "customer_id": 31, "blind": True}]}]
db.team_slot_money(teams, {31: tn(2600), 13: tn(2600), 48: tn(2600)})
check("1st cart purse $52, Straiton and Youngs $26 each",
      teams[0]["purse"] == 52.0 and [m["team_won"] for m in teams[0]["players"]] == [26.0, 26.0], teams[0])
check("2nd cart purse $26, all to Kirksey; the blind slot earns nothing",
      teams[1]["purse"] == 26.0 and [m["team_won"] for m in teams[1]["players"]] == [26.0, None], teams[1])

print("San Antonio s9.27: McCormick blind on a winning team, own team out of the money")
teams = [{"players": [{"player_name": "Jeff Young", "customer_id": 88},
                      {"player_name": "Ale Dimas", "customer_id": 835},
                      {"player_name": "Pat Youngs", "customer_id": 136},
                      {"player_name": "Bl[Michele McCormick]", "customer_id": 765, "blind": True}]},
         {"players": [{"player_name": "Adam Baker", "customer_id": 87},
                      {"player_name": "Michele McCormick", "customer_id": 765}]}]
db.team_slot_money(teams, {88: tn(1150), 835: tn(1150),
                           136: tn(1150) + [{"category": "ctp", "cents": 2300}], 765: tn(1150)})
check("the blind's team: $46, the blind slot paid $11.50",
      teams[0]["purse"] == 46.0 and teams[0]["players"][3]["team_won"] == 11.5, teams[0])
check("her own team shows nothing (her money came from the blind slot)",
      teams[1]["purse"] is None and teams[1]["players"][1]["team_won"] is None, teams[1])
check("other categories (CTP) never count as team money", teams[0]["players"][2]["team_won"] == 11.5)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
