"""The 10/19 leaderboard rulings, server side (handoff 12.7 / 13):
B1 the `evlb_overall_tab` dial, B2 CTPs / PROXIES from the proxy slots,
B3 First LAST member casing (display only), B4 the board state + its line,
B7 each player's THRU and tee start. The board renderer is covered by
test_evlb_rulings_b1_b7.js.

Run: python3 test_evlb_rulings_b1_b7.py
"""
import contextlib
import io
import json
import logging
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    from email_parser import score_entry as se  # noqa: E402
    db.init_db(DB)

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


print("== B3: member_caps_first_last ==")
cf = db.member_caps_first_last
for args, want in [(("Michelle DelCarmen",), "Michelle DelCARMEN"),
                   (("Adam Baker",), "Adam BAKER"),
                   (("Sean MacBride",), "Sean MacBRIDE"),
                   (("Tom Delgado",), "Tom DELGADO"),
                   (("Jim O'Brien",), "Jim O'BRIEN"),
                   (("Mary Ann Van Dyke", "Van Dyke"), "Mary Ann VAN DYKE"),
                   (("Bob Smith Jr.",), "Bob SMITH Jr."),
                   (("Ed Smith-Jones",), "Ed SMITH-JONES"),
                   (("BAKER, Adam",), "Adam BAKER"),
                   (("Cher",), "Cher"),
                   (("Adam BAKER", "Baker"), "Adam BAKER")]:
    check(f"{args} -> {want}", cf(*args) == want, cf(*args))
check("the Last, First form is unchanged", db.member_caps_name("DelCarmen, Michelle") == "DelCARMEN, Michelle")

EV, NAME = 971, "s9.30 Rulings Links"
c = sqlite3.connect(DB)
course_id = c.execute("INSERT INTO courses (name, status) VALUES ('Rulings Links', 'active') "
                      "RETURNING course_id").fetchone()[0]
tee = c.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, "
                "slope, tgf_bands, source) VALUES (?, 'White', 'M', 9, 'front', 34.0, 120, "
                "'50-64', 'admin') RETURNING tee_id", (course_id,)).fetchone()[0]
PARS = {1: 4, 2: 4, 3: 3, 4: 4, 5: 5, 6: 4, 7: 3, 8: 4, 9: 5}      # two par 3s: two CTPs
for h in range(1, 10):
    c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, stroke_index, yardage) "
              "VALUES (?,?,?,?,?)", (tee, h, PARS[h], h, 150 if PARS[h] == 3 else 380))
c.execute("INSERT INTO events (id, item_name, event_date, course_id, course, chapter, format, "
          "start_type, start_time) VALUES (?,?,?,?,?,?,?,?,?)",
          (EV, NAME, "2026-10-20", course_id, "Rulings Links", "San Antonio", "9 Holes",
           "Shotgun", "15:40"))
db._ensure_scoring_tables(c); db._ensure_pairing_tables(c)
db._ensure_gg_game_flights_tables(c); db._ensure_gg_game_results_tables(c)
# cid, first, last, member?, holes posted so far
PLAYERS = [(801, "Michelle", "DelCarmen", True, 9),
           (802, "Adam", "Baker", True, 5),
           (803, "Sean", "MacBride", False, 0),
           (804, "Tom", "Delgado", True, 9)]
RID = {}
for cid, fn, ln, mem, n in PLAYERS:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
              "VALUES (?,?,?,?)", (cid, fn, ln, "active_member" if mem else None))
    RID[cid] = c.execute(
        "INSERT INTO scoring_rounds (customer_id, player_name, event_id, gg_aggregate_id, round_date, "
        "course_id, tee_id, holes_played, playing_handicap, gross, net, source, imported_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
        (cid, f"{fn} {ln}", EV, f"entry:{cid}", "2026-10-20", course_id, tee, n, 5,
         sum(PARS[h] for h in range(1, n + 1)) or None, None, "entry",
         "2026-10-18 23:09:14")).fetchone()[0]
    for h in range(1, n + 1):
        c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, strokes_received) "
                  "VALUES (?,?,?,?)", (RID[cid], h, PARS[h], 0))
# the saved sheet: MacBride's group starts on 7 (slot "7A") at the shotgun
c.execute("INSERT INTO event_pairings (event_id, holes, group_num, slot_label, player_name, cart_pos, "
          "customer_id) VALUES (?,?,?,?,?,?,?)", (EV, "9", 2, "7A", "Sean MacBride", 1, 803))
c.commit(); c.close()


def board():
    se._CTP_CACHE.clear()
    return db.get_event_leaderboard(NAME, db_path=DB) or {}


print("== B7: THRU per player ==")
lb = board()
by = {r["customer_id"]: r for r in lb.get("overall_board") or []}
check("thru counts the holes posted", [by[c_]["thru"] for c_ in (801, 802, 803, 804)] == [9, 5, 0, 9],
      [by[c_].get("thru") for c_ in by])
check("finished only when every hole is in", by[801]["finished"] and not by[802]["finished"])
check("no hole yet: tee time and starting hole from the saved sheet",
      by[803].get("tee_start") == {"tee_time": "3:40 PM", "start_hole": "7"}, by[803].get("tee_start"))
check("a player already going carries no tee start", "tee_start" not in by[802])
check("points per net par for the MVP pace (the table's par rung)", lb.get("pts_par_hole") == 1, lb.get("pts_par_hole"))

print("== B1: OVERALL behind its dial ==")
check("evlb_overall_tab is off by default", lb.get("overall_tab") is False, lb.get("overall_tab"))

print("== B2: CTPs or PROXIES ==")
check("two par 3s for two slots: CTPs", lb.get("proxy_tab_label") == "CTPs", lb.get("proxy_tab_label"))

print("== B3: member casing on the board, never in the database ==")
check("member, prefix kept: Michelle DelCARMEN", by[801]["player_name"] == "Michelle DelCARMEN", by[801]["player_name"])
check("member: Adam BAKER", by[802]["player_name"] == "Adam BAKER", by[802]["player_name"])
check("member, no prefix (Delgado is not Del+Gado): Tom DELGADO", by[804]["player_name"] == "Tom DELGADO")
check("non-member keeps his case: Sean MacBride", by[803]["player_name"] == "Sean MacBride")
check("the game boards read the same casing",
      all(r["player_name"] == by[r["customer_id"]]["player_name"]
          for s in lb.get("net_board") or [] for r in s.get("rows") or []))
c = sqlite3.connect(DB)
check("customers rows are untouched", c.execute(
    "SELECT last_name FROM customers WHERE customer_id = 801").fetchone()[0] == "DelCarmen")
check("scoring_rounds names are untouched", c.execute(
    "SELECT player_name FROM scoring_rounds WHERE id = ?", (RID[801],)).fetchone()[0] == "Michelle DelCarmen")
c.close()

print("== B4: the board state ==")
check("cards still out: LIVE", lb.get("board_state") == "live" and lb.get("board_state_word") == "LIVE",
      (lb.get("board_state"), lb.get("board_state_word")))
words = [w["word"] for w in lb.get("board_state_guide") or []]
check("the guide carries the four words", words == ["UPCOMING", "LIVE", "IN REVIEW", "FINAL"], words)
lock = se.card_lock_minutes(DB)
check("the IN REVIEW line takes its minutes from the dial",
      f"{lock} minutes" in lb["board_state_guide"][2]["text"], lb["board_state_guide"][2]["text"])
db.set_app_setting("se_card_lock_minutes", "22", DB)
check("...and follows it when the dial moves", "22 minutes" in board()["board_state_guide"][2]["text"])

# nobody has a hole yet -> UPCOMING
c = sqlite3.connect(DB)
c.execute("DELETE FROM scoring_holes")
c.commit(); c.close()
lb = board()
check("no hole posted: UPCOMING", lb.get("board_state") == "upcoming", lb.get("board_state"))

# every hole in -> IN REVIEW until results close
c = sqlite3.connect(DB)
for cid, *_ in PLAYERS:
    c.execute("UPDATE scoring_rounds SET holes_played = 9, gross = 36 WHERE id = ?", (RID[cid],))
    for h in range(1, 10):
        c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, strokes_received) "
                  "VALUES (?,?,?,?)", (RID[cid], h, PARS[h], 0))
c.commit(); c.close()
lb = board()
check("every score in, nothing recorded: IN REVIEW", lb.get("board_state") == "in_review", lb.get("board_state"))
check("every player reads F", all(r["finished"] for r in lb["overall_board"]))
db.set_app_setting("auto_payouts_fp", json.dumps({str(EV): {"fp": "x", "final": True, "recorded": True}}), DB)
lb = board()
check("closeout recorded the payouts: FINAL", lb.get("board_state") == "final"
      and lb.get("board_state_text") == "Results are closed and prizes are set.", (lb.get("board_state"), lb.get("board_state_text")))
db.set_app_setting("auto_payouts_hold", json.dumps({str(EV): {"reason": "check hole 7", "by": "kerry"}}), DB)
lb = board()
check("a hold keeps it IN REVIEW: \"Results are being checked.\"",
      lb.get("board_state") == "in_review" and lb.get("board_state_held") is True
      and lb.get("board_state_text") == "Results are being checked.", (lb.get("board_state"), lb.get("board_state_text")))
db.set_app_setting("auto_payouts_hold", "{}", DB)
db.set_app_setting("auto_payouts_fp", json.dumps({str(EV): {"fp": "x", "final": True, "display_only": True}}), DB)
check("shown but not recorded (auto record off): still IN REVIEW", board().get("board_state") == "in_review")

print("== B4: the rule itself ==")
bs = db._evlb_board_state
check("no games and every score in: FINAL with nothing to record",
      bs({"field_complete": True, "money_visible": True, "money_final": True}, no_games=True,
         recorded=False, fp=None, hold=None) == ("final", False))
check("the money still settling (the 10-minute hold) is IN REVIEW",
      bs({"field_complete": True, "money_visible": False}, no_games=False, recorded=True,
         fp=None, hold=None)[0] == "in_review")
check("an unconfirmed closest-to-the-pin takeover is a hold",
      bs({"field_complete": True, "money_visible": True, "money_final": True,
          "proxies": [{"pending": True}]}, no_games=False, recorded=True, fp=None, hold=None) == ("in_review", True))

print("== B1 / B2: the dial, a Longest Putt ==")
db.set_app_setting("evlb_overall_tab", "on", DB)
check("evlb_overall_tab on brings OVERALL back", board().get("overall_tab") is True)
c = sqlite3.connect(DB)
c.execute("UPDATE course_tee_holes SET par = 4 WHERE hole_number = 7")      # one par 3 for two slots
c.commit(); c.close()
check("one par 3 for two slots (the other is a Longest Putt): PROXIES",
      board().get("proxy_tab_label") == "PROXIES", board().get("proxy_tab_label"))

os.unlink(DB)
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
