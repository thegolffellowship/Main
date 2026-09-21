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
    sg = "NET & GROSS" if i < 12 else ("GROSS" if i < 16 else "NET")
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
check("Individual Net: 13 buyers on a nine → 2 equal-size flights, low flight under 12.0",
      inn["selection"]["mode"] == "equal_size" and inn["selection"]["flight_count"] == 2
      and all(m["index"] < 12.0 for m in inn["selection"]["flights"][0]["members"]), str(inn["selection"]["flights"]))
check("...amounts from the matrix columns (netLow / netHigh)",
      inn["amounts"]["total_pot"] > 0 and inn["amounts"]["flights"][1]["matrix_column"] == "netHigh", str(inn["amounts"]))

print("\n== the printed Divisions & Flights page is a view of the same board ==")
rep = db.event_flights_report(EV, db_path=tmp)
rg = {x["game"]: x for x in rep["games"]}
check("same buyers", rg["individual_gross"]["buyers"] == 16 and rg["individual_net"]["buyers"] == 13)
check("same cut on Individual Gross (4/4/8)", [f["players"] for f in rg["individual_gross"]["flights"]] == [4, 4, 8])
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
import mcp_server as mcp  # noqa: E402
out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/", f"scoring-flights-board:{EV}"))
check("scoring-flights-board:<event_id> returns the same board", out.get("event_id") == EV and out.get("state") == "live", str(list(out.keys())[:8]))
out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/", "scoring-flights-board:abc"))
check("...and refuses a bad id with a usage line", "usage" in (out.get("error") or ""), str(out))

print()
if F:
    print(f"FAILED ({len(F)}):")
    for f in F:
        print("  -", f)
    sys.exit(1)
print("ALL PASSED")
