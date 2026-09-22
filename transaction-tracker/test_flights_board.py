"""The DIVISIONS / FLIGHTS board (mailbox #582 / #584, Kerry 2026-09-21):
the ratified flighting + payout rules computed from TRACKER DATA — roster
buy-ins (wd_credits decides), the index of record by customer_id, each
player's PH as the starter sheet computes it, the LIVE matrix's variant and
flight count — in the two layers, beside what Golf Genius recorded, served
by the manager route and the scoring bridge. Dry run: pays nobody.

The rule arithmetic itself is pinned in test_flighting.py; what is pinned
here is that the board feeds the rules the RIGHT field and that the printed
Divisions & Flights page is a view of the same board.

Run: python3 test_flights_board.py
"""
import os, sqlite3, sys, tempfile, contextlib, io, logging, json
# The app binds DB_PATH at import, so the temp file is named BEFORE anything
# imports (the print-pack test's pattern).
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-fb-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PIN", "0000")
from email_parser import database as db  # noqa: E402
logging.getLogger("email_parser.database").setLevel(logging.ERROR)
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
EV, COURSE = 4200, 9200
# A COMPLETED nine (dated yesterday) so the index locks as-of and the board
# reads as "recomputed now"; one designated <50 tee so a PH can be computed.
c.execute("INSERT INTO courses (course_id, name, short_name, status) VALUES (?, 'Brackenridge Park Golf Course', 'Brackenridge', 'active')", (COURSE,))
c.execute("INSERT INTO events (id, item_name, event_date, chapter, course, course_id, status, format, nine_side) "
          "VALUES (?, 's9.24 Brackenridge', date('now', '-1 day'), 'San Antonio', 'Brackenridge Park Golf Course', ?, 'active', '9 Holes', 'Front')", (EV, COURSE))
PAR = {1: 4, 2: 5, 3: 3, 4: 4, 5: 3, 6: 4, 7: 4, 8: 3, 9: 5}          # 35
c.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope, rating, tgf_bands) VALUES (11, ?, 'White', 120, 34.5, '<50')", (COURSE,))
for h in PAR:
    c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) VALUES (11, ?, ?, 350, ?)", (h, PAR[h], h))

# 18-hole indexes the fixture MEANS (best-1-of-3 x 1.0, adjustment -2.0,
# doubled) — 16 GROSS buyers so Individual Gross runs at its 9-hole
# threshold, 14 NET buyers so Ind Net cuts two flights.
players = [
    (301, "Pat", "Youngs", -1.0), (302, "Kerry", "Niester", 1.6), (303, "Nic", "Skinner", 5.8),
    (304, "Luke", "Mazanec", 5.6), (305, "Bear", "Clarkson", 6.0), (306, "Gus", "Vasquez", 11.0),
    (307, "Doug", "Hamilton", 11.2), (308, "Chris", "Espinosa", 11.8), (309, "Rob", "Callaway", 12.0),
    (310, "Chuck", "Fehlis", 13.8), (311, "Mary", "Wade", 14.6), (312, "Larry", "Anthis", 15.8),
    (313, "Richard", "Palacios", 16.4), (314, "Will", "Peterson", 16.6), (315, "Don", "Sharitz", 18.0),
    (316, "Craig", "Bourquin", 24.0), (317, "Jeff", "Rideout", 27.2), (318, "Michael", "Murphy", 34.0),
]
for i, (cid, f, l, idx18) in enumerate(players):
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) VALUES (?, ?, ?, 'San Antonio', 'active')", (cid, f, l))
    c.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES (?, ?, ?)", (f"{l}, {f}", f"{f} {l}", cid))
    diff = idx18 / 2.0 + 2.0
    for _d in (10, 20, 30):
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) "
                  "VALUES (?, date('now', ?), 45, 34.5, 120, ?)", (f"{l}, {f}", f"-{_d} days", diff))
    sg = "BOTH" if i < 12 else ("GROSS" if i < 16 else "NET")
    c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, side_games, user_status, tee_choice) "
              "VALUES (?, ?, 'The Golf Fellowship', ?, ?, 's9.24 Brackenridge', '2026-09-10', 'active', ?, ?, 'MEMBER', '<50')",
              (800 + i, f"u{800+i}", f"{f} {l}", cid, EV, sg))
# A credited WD (Murphy, NET) is NOT a buyer; an uncredited WD (Rideout, NET) still is.
c.execute("UPDATE items SET transaction_status = 'wd', wd_credits = ? WHERE customer_id = 318", (json.dumps({"net_games": 9}),))
c.execute("UPDATE items SET transaction_status = 'wd' WHERE customer_id = 317")
# What Golf Genius recorded for Skins on this event (a published-vs-paid line).
db._ensure_gg_game_results_tables(c)
c.execute("INSERT INTO gg_game_results (event_id, game, game_label, customer_id, player_name, position, detail, purse) VALUES (?, 'skins', 'SKINS Gross 9 $', 302, 'NIESTER, Kerry', '', 'Birdie on 3', 65.0)", (EV,))
c.execute("INSERT INTO gg_game_results (event_id, game, game_label, customer_id, player_name, position, detail, purse) VALUES (?, 'skins', 'SKINS Gross 9 $', 313, 'PALACIOS, Richard', '', 'Par on 7', 65.0)", (EV,))
c.execute("INSERT INTO gg_game_results (event_id, game, game_label, customer_id, player_name, position, detail, purse) VALUES (?, 'ctp', 'Closest to Pin #3', 302, 'NIESTER, Kerry', 'None', NULL, 32.0)", (EV,))
c.commit()

print("\n== the board reads the roster, the index of record and the matrix ==")
board = db.event_flights_board(EV, db_path=tmp)
check("a board comes back for the event", bool(board) and board["event_id"] == EV)
check("state is LIVE and it is a dry run naming GG as payer of record",
      board["state"] == "live" and board["dry_run"] is True and board["payer_of_record"] == "Golf Genius")
check("NET buyers: 13 = 12 both + Rideout's uncredited WD (Murphy's credited WD is out)",
      board["buyers"]["NET"] == 13, str(board["buyers"]))
check("GROSS buyers: 16", board["buyers"]["GROSS"] == 16, str(board["buyers"]))
check("the event has started, so the index is locked as-of its date",
      board["event_started"] and board["handicap_as_of"] and "locked as of" in board["index_basis"], str(board.get("index_basis")))
check("the board says a completed event's LIVE figures are recomputed now", board["event_completed"] is True)
g = {x["game"]: x for x in board["games"]}
check("three games in print order", [x["game"] for x in board["games"]] == ["individual_net", "skins", "individual_gross"])

ig = g["individual_gross"]
check("Individual Gross RUNS at 16 buyers on a nine (the live matrix / seed threshold)", ig["active"] is True, str(ig["inactive_reason"]))
check("...3 flights on the ratified ladder", ig["selection"]["flight_count"] == 3 and ig["selection"]["edges"] == [6.0, 12.0], str(ig["selection"]))
sizes = [f["players"] for f in ig["selection"]["flights"]]
check("...cut 4 / 4 / 8: 6.0 goes up (Clarkson), 12.0 goes up (Callaway)", sizes == [4, 4, 8], str(sizes))
check("...flight labels derive from membership", ig["selection"]["flights"][0]["label"] == "+1.0–5.8", ig["selection"]["flights"][0]["label"])
am = ig["amounts"]
check("...pot $64 = 16 × $4; bonus $6.40; share $3.60; pots 14.40 / 14.40 / 28.80",
      am["total_pot"] == 64.0 and am["bonus"] == 6.4 and am["share"] == 3.6
      and [f["pot"] for f in am["flights"]] == [14.4, 14.4, 28.8], str(am))
check("...every flight under 10 pays one place", all(len(f["places"]) == 1 for f in am["flights"]))
m0 = ig["selection"]["flights"][0]["members"][0]
check("members carry customer_id, name, sort_name, index and PH",
      m0["customer_id"] == 301 and m0["sort_name"] == "YOUNGS, Pat" and m0["index_text"] == "+1.0" and m0["ph"] is not None, str(m0))
# The PH is the starter sheet's number: nine-hole index on the nine-hole
# card, playing_handicap(idx/2, slope 120, rating 34.5, par 35).
from email_parser.handicap_calc import playing_handicap as _ph
check("...and the PH is the starter sheet's chain (index/2 on the nine-hole card)",
      m0["ph"] == _ph(-0.5, 120, 34.5, 35), f"{m0['ph']} vs {_ph(-0.5, 120, 34.5, 35)}")

sk = g["skins"]
check("Skins: 16 gross buyers on a nine → gross skins, 2 flights at 12.0, cut 8/8",
      sk["selection"]["variant"]["name"] == "gross" and [f["players"] for f in sk["selection"]["flights"]] == [8, 8], str(sk["selection"]["flights"]))
check("...the skins pot is the matrix's, split equally per flight ($144 → $72 / $72)",
      sk["amounts"]["total_pot"] == 144.0 and [f["pot"] for f in sk["amounts"]["flights"]] == [72.0, 72.0], str(sk["amounts"]))
check("...beside what Golf Genius recorded for Skins ($130 across 2 rows; the CTP row is not this game's)",
      sk["gg_recorded"]["total"] == 130.0 and len(sk["gg_recorded"]["rows"]) == 2, str(sk["gg_recorded"]))

inn = g["individual_net"]
check("Individual Net: 13 buyers on a nine → 2 flights split down the middle by default, the SMALLER half in Flight 1: 6/7 (Kerry 2026-09-22: 'the lower number should go to the Flight 1')",
      inn["selection"]["mode"] == "equal_size" and inn["selection"]["flight_count"] == 2
      and [f["players"] for f in inn["selection"]["flights"]] == [6, 7], str([f["players"] for f in inn["selection"]["flights"]]))
_mres = db.set_event_flight_mode(EV, "individual_net", "fixed_bands", db_path=tmp)
_inn2 = next(x for x in _mres["games"] if x["game"] == "individual_net")
check("...the HCP BANDS toggle (set_event_flight_mode) cuts it at 12.0 like Skins, low flight under 12.0, and says it is the event's choice",
      _mres.get("ok") and _inn2["selection"]["mode"] == "fixed_bands" and _inn2["selection"]["mode_source"] == "event toggle"
      and all(m["index"] < 12.0 for m in _inn2["selection"]["flights"][0]["members"])
      and all(m["index"] >= 12.0 for m in _inn2["selection"]["flights"][1]["members"]), str(_inn2["selection"]["flights"]))
check("...the board reports the event's toggles", _mres.get("flight_modes") == {"individual_net": "fixed_bands"}, str(_mres.get("flight_modes")))
check("...and 'default' clears it", db.set_event_flight_mode(EV, "individual_net", None, db_path=tmp)["flight_modes"] == {})
check("an unknown game is refused", db.set_event_flight_mode(EV, "bingo", "equal_size", db_path=tmp).get("ok") is False)

print("\n== CUSTOM flights by drag (Kerry 2026-09-22 #599) ==")
_sk0 = next(x for x in db.event_flights_board(EV, db_path=tmp)["games"] if x["game"] == "skins")["selection"]
_low = _sk0["flights"][1]["members"][0]          # the lowest index in Flight 2
_mv = db.move_event_flight_player(EV, "skins", _low["customer_id"], 1, by="test", db_path=tmp)
_sk1 = next(x for x in _mv["games"] if x["game"] == "skins")["selection"]
check("moving Flight 2's lowest index to Flight 1 makes Skins CUSTOM on its HCP base: 8/8 → 9/7, the move on the record",
      _mv.get("ok") and _sk1["mode"] == "custom" and _sk1["base_mode"] == "fixed_bands"
      and [f["players"] for f in _sk1["flights"]] == [9, 7] and _sk1["moves"][0]["customer_id"] == _low["customer_id"],
      str((_mv.get("error"), _sk1.get("mode"), [f["players"] for f in _sk1["flights"]])))
check("...the response says who moved where, and the setting is stored customer_id-keyed",
      _mv["moved"]["to_flight"] == 1 and "CUSTOM" in _mv["moved"]["text"]
      and _mv["flight_modes"]["skins"] == {"mode": "custom", "base": "fixed_bands", "moves": {str(_low["customer_id"]): 1}},
      str((_mv.get("moved"), _mv.get("flight_modes"))))
check("...the custom note names him", _low["name"] in _sk1["custom_note"], _sk1["custom_note"])
check("...the audit log has the move", any(a["action_type"] == "flights_move" for a in db.get_agent_action_log(db_path=tmp, limit=5)))
_rep = {x["game"]: x for x in db.event_flights_report(EV, db_path=tmp)["games"]}
check("...the printed Divisions & Flights page follows the board (Flight 1 band says custom, 9 players)",
      "custom" in _rep["skins"]["flights"][0]["name"] and _rep["skins"]["flights"][0]["players"] == 9,
      str(_rep["skins"]["flights"][0]))
_back = db.move_event_flight_player(EV, "skins", _low["customer_id"], 2, by="test", db_path=tmp)
check("dropping him back on his rule flight clears the move; the game is plainly HCP again (the base stays explicit)",
      _back["moved"]["cleared"] and _back["flight_modes"] == {"skins": "fixed_bands"}
      and next(x for x in _back["games"] if x["game"] == "skins")["selection"]["mode"] == "fixed_bands", str(_back.get("flight_modes")))
db.move_event_flight_player(EV, "skins", _low["customer_id"], 1, by="test", db_path=tmp)
_ev = db.set_event_flight_mode(EV, "skins", "equal_size", by="test", db_path=tmp)
check("clicking EVEN re-cuts from scratch and clears the moves (moves_cleared reported)",
      _ev["moves_cleared"] is True and _ev["flight_modes"] == {"skins": "equal_size"}
      and next(x for x in _ev["games"] if x["game"] == "skins")["selection"]["mode"] == "equal_size", str(_ev.get("flight_modes")))
db.set_event_flight_mode(EV, "skins", None, by="test", db_path=tmp)
check("a move to a flight not on the board is refused", db.move_event_flight_player(EV, "skins", _low["customer_id"], 5, db_path=tmp).get("ok") is False)
check("a player not flighted in that game is refused", "not flighted" in db.move_event_flight_player(EV, "skins", 999999, 1, db_path=tmp).get("error", ""))
check("the moves left nothing behind: every game is back on its default cut", db.event_flight_modes(EV, db_path=tmp) == {}, str(db.event_flight_modes(EV, db_path=tmp)))
db.set_event_flight_mode(EV, "skins", None, db_path=tmp)
check("...amounts from the matrix columns (netLow / netHigh)",
      inn["amounts"]["total_pot"] > 0 and inn["amounts"]["flights"][1]["matrix_column"] == "netHigh", str(inn["amounts"]))

print("\n== a nine on a course that holds only 18-hole sets with per-nine ratings (Brackenridge 2026-09-21) ==")
EV2, COURSE2 = 4201, 9201
c.execute("INSERT INTO courses (course_id, name, short_name, status) VALUES (?, 'Brackenridge CRDB', 'Brack', 'active')", (COURSE2,))
c.execute("INSERT INTO events (id, item_name, event_date, chapter, course, course_id, status, format, nine_side) "
          "VALUES (?, 's9.30 Brackenridge', date('now', '+30 day'), 'San Antonio', 'Brackenridge CRDB', ?, 'active', '9 Holes', 'Front')", (EV2, COURSE2))
c.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, gender, holes, slope, rating, tgf_bands) VALUES (12, ?, 'Blue', 'M', 18, 129, 69.8, '<50')", (COURSE2,))
c.execute("INSERT INTO tee_set_ratings (tee_id, rating_type, course_rating, slope, source) VALUES (12, 'total', 69.8, 129, 'usga_crdb'), (12, 'front', 35.6, 131, 'usga_crdb'), (12, 'back', 34.2, 127, 'usga_crdb')")
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, side_games, user_status, tee_choice) "
          "VALUES (900, 'u900', 'The Golf Fellowship', 'Kerry Niester', 302, 's9.30 Brackenridge', '2026-09-10', 'active', ?, 'NET', 'MEMBER', '<50')", (EV2,))
c.commit()
b2 = db.event_flights_board(EV2, db_path=tmp)
m2 = b2["games"][0]["selection"]["flights"][0]["members"][0]
check("the PH comes off the FRONT rating row of the 18-hole set (35.6 / 131), par 36 with no card",
      m2["ph"] == _ph(0.8, 131, 35.6, 36) and b2["ph_basis"] == "front nine card", f"{m2} {b2['ph_basis']} {b2['ph_note']}")
check("the gross places ladder reports its source (seed until the dial is set)",
      b2["places_source"].startswith("seed") and b2["places_by_flight_size"][1]["min"] == 10, b2.get("places_source"))
db.set_app_setting("gross_places_by_flight_size", json.dumps([{"min": 1, "max": 5, "split": [1.0]}, {"min": 6, "max": None, "split": [0.6, 0.4]}]), db_path=tmp)
b3 = db.event_flights_board(EV, db_path=tmp)
ig3 = next(g for g in b3["games"] if g["game"] == "individual_gross")
check("...and the app_settings dial overrides it: a flight of 8 now pays two places 60/40",
      b3["places_source"].startswith("app_settings") and [p["amount"] for p in ig3["amounts"]["flights"][2]["places"]] == [17.28, 11.52],
      str(ig3["amounts"]["flights"][2]))
db.set_app_setting("gross_places_by_flight_size", "", db_path=tmp)

print("\n== FREEZE / SETTLE / UNFREEZE (Kerry 2026-09-21: 'Yes, build the freeze tables and the button.') ==")
r = db.freeze_event_flights(EV, by="test", db_path=tmp)
check("freeze returns the board FROZEN with its stamp",
      r.get("ok") and r["state"] == "frozen" and r["freeze"]["taken_by"] == "test" and r["freeze"]["trigger"] == "freeze_button", str({k: r.get(k) for k in ("ok", "state", "freeze", "error")}))
n_fro = c.execute("SELECT COUNT(*) FROM event_flight_snapshots WHERE event_id = ? AND state = 'frozen' AND voided_at IS NULL", (EV,)).fetchone()[0]
check("one frozen snapshot row", n_fro == 1, str(n_fro))
mem = c.execute("SELECT COUNT(*), SUM(customer_id IS NULL) FROM event_flight_snapshot_members m JOIN event_flight_snapshots s ON s.id = m.snapshot_id WHERE s.event_id = ? AND s.state = 'frozen'", (EV,)).fetchone()
check("member rows carry customer_id, one per player per game (13 net + 16 skins + 16 gross = 45)", mem[0] == 45 and (mem[1] or 0) == 0, str(tuple(mem)))
r2 = db.freeze_event_flights(EV, by="test", db_path=tmp)
check("a second press refuses rather than re-freezing", not r2.get("ok") and "already" in (r2.get("error") or ""), str(r2.get("error")))
# A late GROSS signup at index 3.0 after the freeze: lands in flight 1 by the
# FROZEN edges, the pot recomputes, the selection does not move.
c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) VALUES (319, 'Late', 'Low', 'San Antonio', 'active')")
c.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES ('Low, Late', 'Late Low', 319)")
for _d in (10, 20, 30):
    c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) VALUES ('Low, Late', date('now', ?), 45, 34.5, 120, 3.5)", (f"-{_d} days",))
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, side_games, user_status, tee_choice) "
          "VALUES (901, 'u901', 'The Golf Fellowship', 'Late Low', 319, 's9.24 Brackenridge', '2026-09-11', 'active', ?, 'GROSS', 'MEMBER', '<50')", (EV,))
c.commit()
fb = db.event_flights_board(EV, db_path=tmp)
igf = next(g for g in fb["games"] if g["game"] == "individual_gross")
check("the FROZEN board keeps the selection (3 flights, edges 6/12) and places the late add in flight 1: 5/4/8",
      fb["state"] == "frozen" and igf["selection"]["edges"] == [6.0, 12.0] and [f["players"] for f in igf["selection"]["flights"]] == [5, 4, 8], str([f["players"] for f in igf["selection"]["flights"]]))
check("...the pot recomputes from 17 buyers: flight 1 $18.00, bonus $6.80",
      igf["amounts"]["flights"][0]["pot"] == 18.0 and igf["amounts"]["bonus"] == 6.8, str(igf["amounts"]))
check("...and the delta names him", [a["name"] for a in igf["delta"]["added"]] == ["Late Low"] and igf["delta"]["added"][0]["flight_no"] == 1 and igf["delta"]["changed"], str(igf["delta"]))
sk_f = next(g for g in fb["games"] if g["game"] == "skins")
check("Skins on the frozen board: still 2 flights, the late add in flight 1 (9/8), pot at 17 buyers", [f["players"] for f in sk_f["selection"]["flights"]] == [9, 8] and sk_f["amounts"]["buyers"] == 17, str(sk_f["amounts"]))
st = db.settle_event_flights(EV, by="test", db_path=tmp)
check("settle returns SETTLED with both stamps", st.get("ok") and st["state"] == "settled" and st["settled"]["taken_by"] == "test" and st["freeze"], str({k: st.get(k) for k in ("ok", "state", "error")}))
c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) VALUES (320, 'Even', 'Later', 'San Antonio', 'active')")
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, side_games, user_status, tee_choice) "
          "VALUES (902, 'u902', 'The Golf Fellowship', 'Even Later', 320, 's9.24 Brackenridge', '2026-09-11', 'active', ?, 'GROSS', 'MEMBER', '<50')", (EV,))
c.commit()
sb = db.event_flights_board(EV, db_path=tmp)
check("a SETTLED board is served from storage — a later signup does not move it (17 gross, not 18)",
      sb["state"] == "settled" and sb["buyers"]["GROSS"] == 17, str(sb["buyers"]))
check("...and cannot be settled twice", not db.settle_event_flights(EV, db_path=tmp).get("ok"))
u = db.unfreeze_event_flights(EV, by="test", db_path=tmp)
check("unfreeze voids both rows and the board reads LIVE with 18 gross buyers",
      u.get("ok") and u["state"] == "live" and len(u["voided"]) == 2 and u["buyers"]["GROSS"] == 18, str({k: u.get(k) for k in ("ok", "state", "voided", "buyers")}))
kept = c.execute("SELECT COUNT(*) FROM event_flight_snapshots WHERE event_id = ? AND voided_at IS NOT NULL", (EV,)).fetchone()[0]
check("...the voided rows are kept for the audit", kept == 2, str(kept))
check("settle without a freeze refuses", not db.settle_event_flights(EV, db_path=tmp).get("ok"))
check("unfreeze on a LIVE board refuses", not db.unfreeze_event_flights(EV, db_path=tmp).get("ok"))
au = c.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type IN ('flights_freeze', 'flights_settle', 'flights_unfreeze')").fetchone()[0]
check("every action is audited", au == 3, str(au))

print("\n== the printed Divisions & Flights page is a view of the same board ==")
rep = db.event_flights_report(EV, db_path=tmp)
rg = {x["game"]: x for x in rep["games"]}
check("same buyers (18 gross after the two late signups above, 13 net)", rg["individual_gross"]["buyers"] == 18 and rg["individual_net"]["buyers"] == 13, str((rg["individual_gross"]["buyers"], rg["individual_net"]["buyers"])))
check("same cut on Individual Gross (5/4/8; the index-less signup is listed apart)", [f["players"] for f in rg["individual_gross"]["flights"]] == [5, 4, 8] and len(rg["individual_gross"]["unflighted"]) == 1, str([f["players"] for f in rg["individual_gross"]["flights"]]))
check("the printed name states the band the flight holds",
      rg["individual_gross"]["flights"][1]["name"] == "Flight 2 (HCP 6.0–11.9)", rg["individual_gross"]["flights"][1]["name"])
check("...and the derived range rides along", rg["individual_gross"]["flights"][1]["label"] == "6.0–11.8")

print("\n== the route (manager) and the bridge serve it ==")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as appmod
client = appmod.app.test_client()
r = client.get(f"/api/events/{EV}/flights-board")
check("anonymous is refused", r.status_code in (401, 403, 302), str(r.status_code))
with client.session_transaction() as s:
    s["role"] = "manager"; s["authenticated"] = True
r = client.get(f"/api/events/{EV}/flights-board")
check("a manager gets the board", r.status_code == 200, str(r.status_code))
payload = r.get_json() or {}
check("...with both layers per game and no event pricing row",
      payload.get("games") and "selection" in payload["games"][0] and "amounts" in payload["games"][0] and "event" not in payload,
      str(list(payload.keys())))
r = client.get("/api/events/999999/flights-board")
check("an unknown event is a 404", r.status_code == 404, str(r.status_code))
_gm = next((x for x in payload["games"] if x["active"] and x["selection"]["flight_count"] >= 2 and x["selection"]["flights"][1]["members"]), None)
_mcid = _gm["selection"]["flights"][1]["members"][0]["customer_id"] if _gm else None
r = client.post(f"/api/events/{EV}/flights/move", json={"game": _gm["game"] if _gm else "skins", "customer_id": _mcid, "flight_no": 1})
check("POST flights/move as a manager on a LIVE board: 200 and the board comes back CUSTOM with the move",
      _gm is not None and r.status_code == 200 and (r.get_json() or {}).get("moved", {}).get("to_flight") == 1
      and next(x for x in r.get_json()["games"] if x["game"] == _gm["game"])["selection"]["mode"] == "custom",
      str((r.status_code, (r.get_json() or {}).get("error"), _gm and _gm["game"])))
r = client.post(f"/api/events/{EV}/flights/move", json={"game": _gm["game"] if _gm else "skins", "customer_id": _mcid, "flight_no": 2})
check("...dropping him back on his rule flight clears it (200, cleared)", r.status_code == 200 and (r.get_json() or {}).get("moved", {}).get("cleared") is True, str(r.get_json() and r.get_json().get("moved")))
db.set_event_flight_mode(EV, _gm["game"] if _gm else "skins", None, db_path=tmp)
r = client.post(f"/api/events/{EV}/flights/freeze", json={"note": "route"})
check("POST flights/freeze as a manager freezes (200, state frozen, note kept)",
      r.status_code == 200 and (r.get_json() or {}).get("state") == "frozen" and (r.get_json() or {})["freeze"]["note"] == "route", str((r.status_code, (r.get_json() or {}).get("error"))))
r = client.post(f"/api/events/{EV}/flights/freeze", json={})
check("...a second POST is a 409, not a re-freeze", r.status_code == 409, str(r.status_code))
r = client.post(f"/api/events/{EV}/flights/bogus", json={})
check("...an unknown action is a 404", r.status_code == 404, str(r.status_code))
r = client.post(f"/api/events/{EV}/flights/move", json={"game": "skins", "customer_id": 301, "flight_no": 1})
check("POST flights/move on a FROZEN board is a 409 that says unfreeze first", r.status_code == 409 and "frozen" in (r.get_json() or {}).get("error", ""), str((r.status_code, r.get_json())))
r = client.post(f"/api/events/{EV}/flights/mode", json={"game": "skins", "mode": "equal_size"})
check("...and so is the toggle", r.status_code == 409, str(r.status_code))
import mcp_server as mcp  # noqa: E402
out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/", f"scoring-flights-board:{EV}"))
check("scoring-flights-board:<event_id> returns the same board (FROZEN by the route above)", out.get("event_id") == EV and out.get("state") == "frozen", str((out.get("event_id"), out.get("state"))))
out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/", "scoring-flights-board:abc"))
check("...and refuses a bad id with a usage line", "usage" in (out.get("error") or ""), str(out))
out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/", f"scoring-flights-unfreeze:{EV}"))
check("scoring-flights-unfreeze dry run says what it would void", out.get("dry_run") and out.get("would") == "void" and out["snapshots"], str(out))
out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/", f"scoring-flights-unfreeze:{EV}|apply"))
check("...|apply voids and the board reads LIVE", out.get("ok") and out.get("state") == "live", str({k: out.get(k) for k in ("ok", "state", "error")}))
out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/", f"scoring-flights-freeze:{EV}"))
check("scoring-flights-freeze dry run reports the flights it would freeze", out.get("dry_run") and out.get("would") == "freeze" and out["games"], str(out)[:200])
_gm = next((x for x in db.event_flights_board(EV, db_path=tmp)["games"]
            if x["active"] and x["selection"]["flight_count"] >= 2 and x["selection"]["flights"][1]["members"]), None)
_bcid = _gm["selection"]["flights"][1]["members"][0]["customer_id"] if _gm else 0
out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/", f"scoring-flights-move:{EV}|{_gm['game'] if _gm else 'skins'}|{_bcid}|1"))
check("bridge scoring-flights-move:<id>|<game>|<cid>|1 moves him (LIVE) and reports the custom cut",
      _gm is not None and out.get("ok") and out["moved"]["customer_id"] == _bcid and next(g for g in out["games"] if g["game"] == _gm["game"])["mode"] == "custom", str(out)[:300])
out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/", "scoring-flights-move:abc"))
check("...and refuses a bad call with a usage line", "usage" in (out.get("error") or ""), str(out))

print()
if F:
    print(f"FAILED ({len(F)}):")
    for f in F:
        print("  -", f)
    sys.exit(1)
print("ALL PASSED")
