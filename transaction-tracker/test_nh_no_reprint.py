"""Kerry 2026-10-20: "Send them now with Adam blank. And make this standard.
If a handicap comes in later, just update it on the tracker and remove the
blind. That's not reason to resend the print pack or even just his affected
printouts." Guards print_pack._handicap_only_change / seat_signature."""
import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
from email_parser import database as db
from email_parser import print_pack as pp

F = []
def check(name, ok, extra=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f"  {extra}"))
    if not ok:
        F.append(name)

DB = os.environ["DATABASE_PATH"]
db.init_db(DB)

def built(players, parts, blinds=None):
    return {"pack": {"groups": [{"holes": "9", "group_num": 2, "slot_label": "3:50 PM",
                                 "players": players, "blinds": blinds or []}]},
            "part_shas": parts}

seats = [{"cart_pos": 1, "customer_id": 42, "tee_choice": "50-64"},
         {"cart_pos": 4, "customer_id": 846, "tee_choice": "50-64"}]
base = {"starter-sheet": "a", "cart-signs": "b", "scorecards": "c", "games-payouts": "d"}
db.set_app_setting("print_pack_sent_seats:9", json.dumps({"seats": pp.seat_signature(built(seats, base)),
                                                          "parts": base}), db_path=DB)
check("a handicap arriving (starter sheet + scorecards + cart signs change, same seats) is not resent",
      pp._handicap_only_change(9, built(seats, {**base, "starter-sheet": "x", "scorecards": "y", "cart-signs": "z"},
                                        blinds=[]), db_path=DB))
check("blinds are not part of the seat signature",
      pp.seat_signature(built(seats, base, blinds=[{"name": "Jeff Young"}])) == pp.seat_signature(built(seats, base)))
check("a moved player still resends",
      not pp._handicap_only_change(9, built([seats[0], {**seats[1], "cart_pos": 3}], {**base, "starter-sheet": "x"}), db_path=DB))
check("a games change still resends",
      not pp._handicap_only_change(9, built(seats, {**base, "games-payouts": "q"}), db_path=DB))
check("nothing on record: send as before", not pp._handicap_only_change(10, built(seats, base), db_path=DB))

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILED: {F}"))
sys.exit(1 if F else 0)
