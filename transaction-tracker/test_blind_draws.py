"""A credited player leaves the sheet, and a BLIND fills the seat.

Kerry 2026-09-15, having credited Will Wallace after the shotgun had gone
off and then found him still seated:

  "He should automatically be removed from the pairings when that happens
   unless you strongly suggest otherwise. I could understand if it was
   before the event started. In this case the group would not be
   're-seated' because the event starts. However ... for any open spots
   like this, BLIND's from the field of Members with established handicaps
   only, should be added into those slots ... Blind's should be auto
   generated based off of a history of who's been blinds too, so there's
   even distribution of who gets the benefit of being a blind for Team Net
   over the course of a year."

Three rules under test: the removal happens by itself wherever the money
action is taken, the clock decides whether the group re-seats, and the
draw spreads the benefit instead of landing on the same people.

Run: python3 test_blind_draws.py
"""
import os, sqlite3, sys, tempfile, contextlib, io, logging
from datetime import datetime, timedelta
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
logging.getLogger("email_parser.database").setLevel(logging.ERROR)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-blind-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
TODAY = datetime.now().strftime("%Y-%m-%d")
EV = 3302
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status, "
          "start_type, start_time) VALUES (?, 's9.23 The Quarry', ?, "
          "'San Antonio', 'active', 'Shotgun', '17:00')", (EV, TODAY))

# The field: eight members with indexes, one guest, one member with no rounds.
FIELD = [(1, "Jeff", "Rideout", "active_member"), (2, "Mary", "Wade", "active_member"),
         (3, "Will", "Wallace", "active_member"), (4, "Daniel", "South", "active_member"),
         (5, "Larry", "Anthis", "member_plus"), (6, "Gus", "Vasquez", "active_member"),
         (7, "Adam", "Baker", "active_member"), (8, "Pat", "Youngs", "active_member"),
         (9, "Randy", "Guest", "active_guest"), (10, "Newt", "Newman", "active_member")]
for cid, fn, ln, st in FIELD:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, "
              "account_status, current_player_status) VALUES (?,?,?, 'San Antonio', 'active', ?)",
              (cid, fn, ln, st))
    c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, "
              "item_name, event_id, transaction_status, holes, order_date, user_status) "
              "VALUES (?,?, 'The Golf Fellowship', ?,?, 's9.23 The Quarry', ?, "
              "'active', '9', ?, 'MEMBER')",
              (700 + cid, f"u{700+cid}", f"{fn} {ln}", cid, EV, TODAY))
    if ln == "Newman":       # a member with no posted rounds — no index
        continue
    c.execute("INSERT INTO handicap_player_links (player_name, customer_id, customer_name) "
              "VALUES (?,?,?)", (f"{fn} {ln}", cid, f"{fn} {ln}"))
    for i in range(4):       # four rounds each ⇒ an established index
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, differential, "
                  "adjusted_score, rating, slope, customer_id) VALUES (?,?,?,?,?,?,?)",
                  (f"{fn} {ln}", "2026-0%d-01" % (i + 2), 10.0 + cid, 45, 35.0, 120, cid))
c.commit()

SHEET = {"9": [
    {"group_num": 1, "slot_label": "1", "players": [
        {"name": "Daniel South", "cart_pos": 1, "tee_choice": "50-64", "handicap_index": 6.0},
        {"name": "Larry Anthis", "cart_pos": 2, "tee_choice": "50-64", "handicap_index": 7.0},
        {"name": "Gus Vasquez", "cart_pos": 3, "tee_choice": "50-64", "handicap_index": 8.0},
        {"name": "Adam Baker", "cart_pos": 4, "tee_choice": "<50", "handicap_index": 6.6}]},
    {"group_num": 2, "slot_label": "4", "players": [
        {"name": "Jeff Rideout", "cart_pos": 1, "tee_choice": "50-64", "handicap_index": 9.0},
        {"name": "Will Wallace", "cart_pos": 2, "tee_choice": "50-64", "handicap_index": 5.0},
        {"name": "Mary Wade", "cart_pos": 3, "tee_choice": "Forward", "handicap_index": 12.0}]},
]}
db.save_event_pairings(EV, SHEET, db_path=tmp)

print("\n== has the event started? ==")
check("a past date has started", db._event_started({"event_date": "2026-01-01"}))
check("a future date has not", not db._event_started({"event_date": "2099-01-01"}))
_noon = datetime.strptime(TODAY + " 12:00", "%Y-%m-%d %H:%M")
check("today, five hours before the shotgun, has not started",
      not db._event_started({"event_date": TODAY, "start_time": "17:00"},
                            now=_noon))
check("today, an hour after the shotgun, has started",
      db._event_started({"event_date": TODAY, "start_time": "17:00"},
                        now=_noon.replace(hour=18)))
check("today with NO time recorded counts as started — a sheet already out "
      "is never reshuffled on a guess",
      db._event_started({"event_date": TODAY}, now=_noon))

print("\n== crediting a player removes him from the sheet, by itself ==")
# The shotgun has GONE OFF: dated yesterday, so the assertion does not
# depend on what time of day the suite happens to run.
c.execute("UPDATE events SET event_date = date(?, '-1 day') WHERE id = ?",
          (TODAY, EV)); c.commit()
will = c.execute("SELECT id FROM items WHERE customer = 'Will Wallace'").fetchone()["id"]
db.credit_item(will, note="Could not make it", db_path=tmp)
got = db.get_event_pairings(EV, db_path=tmp)
g2 = next(g for g in got["9"] if g["group_num"] == 2)
names = [p["name"] for p in g2["players"]]
check("no yes/no popup needed — the status change did it", "Will Wallace" not in names, str(names))
check("his group-mates are still there", set(names) == {"Jeff Rideout", "Mary Wade"}, str(names))
check("the event has started, so nobody was re-seated: Mary keeps seat 3",
      [p["cart_pos"] for p in g2["players"] if p["name"] == "Mary Wade"] == [3],
      str([(p["name"], p["cart_pos"]) for p in g2["players"]]))
check("seat 2 is now OPEN", 2 not in {p["cart_pos"] for p in g2["players"]})

c.execute("UPDATE events SET event_date = ? WHERE id = ?", (TODAY, EV)); c.commit()

print("\n== a player with a second row on the event is NOT unseated ==")
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, "
          "item_name, event_id, transaction_status, holes, order_date, user_status) "
          "VALUES (760, 'u760', 'The Golf Fellowship', 'Adam Baker', 7, "
          "'s9.23 The Quarry', ?, 'active', '9', ?, 'MEMBER')", (EV, TODAY)); c.commit()
extra = c.execute("SELECT id FROM items WHERE customer = 'Adam Baker' "
                  "ORDER BY id DESC LIMIT 1").fetchone()["id"]
db.credit_item(extra, note="Side games only", db_path=tmp)
g1 = next(g for g in db.get_event_pairings(EV, db_path=tmp)["9"] if g["group_num"] == 1)
check("crediting ONE of his rows leaves him playing",
      "Adam Baker" in [p["name"] for p in g1["players"]])

print("\n== before the start, the group DOES re-seat ==")
c.execute("UPDATE events SET event_date = '2099-01-01' WHERE id = ?", (EV,)); c.commit()
db.save_event_pairings(EV, SHEET, db_path=tmp)
db.remove_player_from_pairings(EV, "Will Wallace", db_path=tmp)
g2 = next(g for g in db.get_event_pairings(EV, db_path=tmp)["9"] if g["group_num"] == 2)
check("seats close up when the sheet has not gone out",
      sorted(p["cart_pos"] for p in g2["players"]) == [1, 2], str(
          [(p["name"], p["cart_pos"]) for p in g2["players"]]))
c.execute("UPDATE events SET event_date = ? WHERE id = ?", (TODAY, EV)); c.commit()

print("\n== who may be drawn ==")
with db._connect(tmp) as conn:
    pool = db.event_blind_pool(conn, EV)
elig = {e["name"] for e in pool["eligible"]}
why = {e["name"]: e["why"] for e in pool["excluded"]}
check("members in the field with an ESTABLISHED index are eligible",
      "Daniel South" in elig, str(elig))
check("a GUEST is not", "Randy Guest" not in elig, str(elig))
check("…and the reason is recorded, not swallowed",
      "not a member" in why.get("Randy Guest", ""), str(why))
check("a member with no established index is not", "Newt Newman" not in elig, str(elig))
check("…for that reason", "established" in why.get("Newt Newman", ""), str(why))
check("the credited player is off the roster, so out of the pool",
      "Will Wallace" not in elig, str(elig))

print("\n== the draw fills the open seats ==")
db.save_event_pairings(EV, SHEET, db_path=tmp)          # restore the 3-man group
db.remove_player_from_pairings(EV, "Will Wallace", reseat=False, db_path=tmp)
res = db.draw_event_blinds(EV, dry_run=False, redraw=True, db_path=tmp, team_unit="group")
seats = {(d["group_num"], d["cart_pos"]): d["name"] for d in res["drawn"]}
check("group 2 is short two seats of a foursome and both are drawn",
      sorted(p for (g, p) in seats if g == 2) == [2, 4], str(sorted(seats)))
check("nobody in the group fills its own team",
      not ({seats.get((2, 2)), seats.get((2, 4))} &
           {"Jeff Rideout", "Mary Wade"}), str(seats))
check("one blind per person per event", len(set(seats.values())) == len(seats), str(seats))
check("a guest is never drawn", "Randy Guest" not in seats.values(), str(seats))

print("\n== a blind is not a seat ==")
rows = [r["player_name"] for r in c.execute(
    "SELECT player_name FROM event_pairings WHERE event_id = ? AND group_num = 2",
    (EV,))]
drawn_names = set(seats.values())
check("no blind is written into event_pairings — it would invent a pair "
      "that never rode",
      sorted(rows) == ["Jeff Rideout", "Mary Wade"], str(rows))
check("…and no Bl[] wrapper leaks into the sheet either",
      not any("Bl[" in r for r in rows), str(rows))
g2 = next(g for g in db.get_event_pairings(EV, db_path=tmp)["9"] if g["group_num"] == 2)
check("the sheet still shows two players in the group", len(g2["players"]) == 2)
check("…and carries the blinds alongside", len(g2.get("blinds") or []) == 2,
      str(g2.get("blinds")))
check("the drawn card is offered in GG's own notation",
      all(d["gg_text"].startswith("Bl[") and ", " in d["gg_text"]
          for d in res["drawn"]), str([d["gg_text"] for d in res["drawn"]]))

print("\n== the benefit spreads over the year ==")
with db._connect(tmp) as conn:
    hist = db.blind_draw_history(conn, year=datetime.now().year)
check("tonight's draw is recorded as history", len(hist) == 2, str(hist))
# Everyone who has NOT been a blind must come ahead of everyone who has.
db.save_event_pairings(EV, SHEET, db_path=tmp)
db.remove_player_from_pairings(EV, "Will Wallace", reseat=False, db_path=tmp)
EV2 = 3303
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status, "
          "start_type, start_time) VALUES (?, 's9.24 Olympia Hills', ?, "
          "'San Antonio', 'active', 'Shotgun', '17:00')", (EV2, TODAY))
for cid, fn, ln, st in FIELD:
    c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, "
              "item_name, event_id, transaction_status, holes, order_date, user_status) "
              "VALUES (?,?, 'The Golf Fellowship', ?,?, 's9.24 Olympia Hills', ?, "
              "'active', '9', ?, 'MEMBER')",
              (800 + cid, f"v{800+cid}", f"{fn} {ln}", cid, EV2, TODAY))
c.commit()
db.save_event_pairings(EV2, {"9": [{"group_num": 1, "slot_label": "1", "players": [
    {"name": "Daniel South", "cart_pos": 1, "tee_choice": "50-64", "handicap_index": 6.0},
    {"name": "Larry Anthis", "cart_pos": 2, "tee_choice": "50-64", "handicap_index": 7.0},
    {"name": "Gus Vasquez", "cart_pos": 3, "tee_choice": "50-64", "handicap_index": 8.0}]}]},
    db_path=tmp)
res2 = db.draw_event_blinds(EV2, dry_run=True, db_path=tmp, team_unit="group")
pick2 = {d["name"] for d in res2["drawn"]}
check("the next event's blind is NOT someone who has already been one",
      not (pick2 & drawn_names), f"{pick2} vs already {drawn_names}")
check("…and the draw says what it counted",
      all(d["blinds_ytd"] == 0 for d in res2["drawn"]), str(res2["drawn"]))

print("\n== a blind already entered in Golf Genius covers a seat ==")
c.execute("INSERT INTO blind_draws (event_id, event_date, player_name, "
          "customer_id, slot_key, source) VALUES (?, ?, 'YOUNGS, Pat', 8, "
          "'gg:youngs|p', 'gg')", (EV2, TODAY)); c.commit()
res3 = db.draw_event_blinds(EV2, dry_run=True, db_path=tmp, team_unit="group")
check("the seat Kerry already filled in GG is not drawn again",
      len(res3["drawn"]) == 0 and len(res3["covered_by_existing"]) == 1,
      str(res3["drawn"]) + str(res3["covered_by_existing"]))
check("…and it says who covers it",
      res3["covered_by_existing"][0]["name"] == "Pat Youngs",
      str(res3["covered_by_existing"]))
c.execute("DELETE FROM blind_draws WHERE event_id = ? AND source = 'gg'", (EV2,))
c.commit()

print("\n== the draw is a DRAW ==")
# Kerry 2026-09-15: "RANDOM would choose players randomly who've been
# blinds the least." Fewest-first is the fairness rule; the randomness is
# what stops the same person inside that tier being picked every week.
_names = set()
for _ in range(25):
    _r = db.draw_event_blinds(EV2, dry_run=True, db_path=tmp, team_unit="group")
    for d in _r["drawn"]:
        _names.add(d["name"])
        if d["blinds_ytd"] != 0:
            F.append("a player with blinds was drawn over one with none")
check("every pick comes from the fewest-blinds tier", not F, str(_names))
check("…and it is not the same name every time", len(_names) > 1, str(_names))
check("a dry run writes nothing", c.execute(
    "SELECT COUNT(*) n FROM blind_draws WHERE event_id = ?", (EV2,)).fetchone()["n"] == 0)


print("\n== rule 15h: on a CART Net night the blind is the other cart of the same foursome ==")
# Kerry 2026-09-18: "On Cart Net, when there are OPEN slots in need of a
# Blind, the blind is from the other cart in the foursome (the one that
# meets the requirements of the random selection for Team Net). In Team
# Net, it is randomly from the field outside of their group."
db.save_event_pairings(EV, SHEET, db_path=tmp)      # group 2: Rideout 1, Wallace 2, Wade 3 — seat 4 open
with db._connect(tmp) as _c:
    _c.execute("DELETE FROM blind_draws WHERE event_id = ?", (EV,)); _c.commit()
_cart = db.draw_event_blinds(EV, dry_run=True, redraw=True, db_path=tmp)      # matrix: 7 seated -> cart
check("the field below 16 is a cart night", _cart["team_unit"] == "cart", _cart.get("team_unit"))
_seat4 = next((d for d in _cart["drawn"] if d["group_num"] == 2 and d["cart_pos"] == 4), None)
check("the open seat in cart B is filled from cart A of the SAME group",
      _seat4 is not None and _seat4["name"] in ("Jeff Rideout", "Will Wallace")
      and _seat4["drawn_from"] == "other cart", _seat4)
_team = db.draw_event_blinds(EV, dry_run=True, redraw=True, db_path=tmp, team_unit="group")
_seat4t = next((d for d in _team["drawn"] if d["group_num"] == 2 and d["cart_pos"] == 4), None)
check("on a Team Net night the same seat draws from the field outside the group",
      _seat4t is not None and _seat4t["name"] not in ("Jeff Rideout", "Will Wallace", "Mary Wade")
      and _seat4t["drawn_from"] == "field", _seat4t)

print("\n== the single-seat RANDOM is the same rule as the button (Kerry 2026-09-22) ==")
db.save_event_pairings(EV, SHEET, db_path=tmp)
db.remove_player_from_pairings(EV, "Will Wallace", reseat=False, db_path=tmp)
db.clear_event_blinds(EV, db_path=tmp)
# Six seated on the sheet: the matrix runs CART Net below 16, so rule 15h
# applies — the other cart of the same foursome first. Group 2 holds
# Jeff Rideout (seat 1) and Mary Wade (seat 3).
one = db.draw_one_blind(EV, "9", 2, 2, db_path=tmp)
check("seat 2 (cart 1) draws from the OTHER cart — Mary Wade, not the field",
      one.get("name") == "Mary Wade" and one.get("drawn_from") == "other cart"
      and one.get("team_unit") == "cart", str(one))
two = db.draw_one_blind(EV, "9", 2, 4, db_path=tmp)
check("seat 4 (cart 2) draws Jeff Rideout from cart 1 the same way",
      two.get("name") == "Jeff Rideout" and two.get("drawn_from") == "other cart", str(two))
db.clear_event_blinds(EV, db_path=tmp)
whole = db.draw_event_blinds(EV, dry_run=True, db_path=tmp)
check("…and the BLINDS button reads the same unit and the same sources for those seats",
      whole.get("team_unit") == "cart"
      and {(d["group_num"], d["cart_pos"]): d["drawn_from"] for d in whole["drawn"]}
      == {(2, 2): "other cart", (2, 4): "other cart"}, str(whole.get("drawn")))

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
