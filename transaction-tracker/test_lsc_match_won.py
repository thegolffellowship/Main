"""Lone Star Cup: play on after the match, the match-won moment, the
winner's shimmer and the Cup-clinched pop-up (Kerry 2026-10-09):

  "Players need to be able to continue playing holes even after a match is
   determined if there are holes that remain. They can still play for skins
   even though match is determined. Match should highlight shimmer in
   scoring when complete but should shimmer with chapter color for who won."
  "Oh when match ends scorecard needs to congratulate winner(s) and ask if
   you want to continue the round (for skins) or complete and confirm with
   scorecard"
  "When the cup is clinched a pop up congratulations message needs to pop
   up on the scorers site to say which chapter has clinched/retained the cup."

Pins:
- holes after a close-out are taken and the match result stays put;
- a card may be SUBMITTED with the holes after the match blank only when every
  Cup match on it is decided and the phone asks for it (finish_early); a
  player then signs that card as it is;
- the blank holes of a card finished early hold no skins hole open for the
  field (merge_entry_feed: finished -> compute_board treats them as withdrawn);
- the card's cup_standings carries the board's cup_status;
- the page contract: the won-modal words, the once-per-match key, scorer only,
  the shimmer keyed to the winner's side, reduced motion; the clinch words and
  the once-per-device key on both scorer pages.

Run: python3 test_lsc_match_won.py
"""
import contextlib
import io
import json
import logging
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)
from email_parser import score_entry as se  # noqa: E402
from email_parser import lsc_cup  # noqa: E402

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {str(detail)[:600]}"))
    if not cond:
        F.append(label)


NINE = [{"hole": h, "par": p, "stroke_index": si} for h, p, si in
        [(1, 4, 3), (2, 3, 9), (3, 5, 1), (4, 4, 5), (5, 4, 7), (6, 3, 8),
         (7, 4, 2), (8, 4, 6), (9, 5, 4)]]
PAR = {h["hole"]: h["par"] for h in NINE}
mk = lambda op_id, cid, hole, gross, **kw: {"op_id": op_id, "customer_id": cid, "hole": hole, "gross": gross, **kw}

print("Play on after the match; finish early only once every match is decided")
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date) VALUES (901, 'LSC TEST', '2026-10-10')")
    for cid, fn, ln in ((101, "Matthew", "Jenkins"), (102, "Rob", "Callaway"),
                        (103, "John", "Wade"), (104, "Chuck", "Fehlis")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
    conn.commit()
rid = se.create_round(901, 9, label="singles", course_holes=NINE)["round_id"]
gid = se.upsert_group(rid, 1, players=[{"customer_id": c, "display_name": n, "playing_handicap": 0, "seat": i + 1}
                                       for i, (c, n) in enumerate([(101, "Matthew Jenkins"), (102, "Rob Callaway"),
                                                                   (103, "John Wade"), (104, "Chuck Fehlis")])])["group_id"]
# a Sunday-style card: two singles matches on one card
db.set_app_setting("lsc_matches", json.dumps({"event_id": 901, "defending_champion": "sa", "sessions": [
    {"id": "sun", "format": "singles", "se_round": rid, "n_holes": 9,
     "matches": [{"id": "SUN-1", "austin": [101], "sa": [102]},
                 {"id": "SUN-2", "austin": [103], "sa": [104]}]}]}))
se.claim_group(gid, "dev", 101)
ops = []
for h in range(1, 6):          # SUN-1: Jenkins wins 1-5 -> 5&4 after hole 5
    ops += [mk(f"a{h}", 101, h, PAR[h] - 1), mk(f"b{h}", 102, h, PAR[h] + 1),
            mk(f"c{h}", 103, h, PAR[h]), mk(f"d{h}", 104, h, PAR[h])]   # SUN-2 all square
se.write_scores(gid, "dev", 101, ops)
ms = {m["match_id"]: m for m in se.get_group_card(gid, "dev")["match_status"]}
check("SUN-1 closes out 5&4 after hole 5; SUN-2 is still live",
      ms["SUN-1"]["final"] and ms["SUN-1"]["margin"] == "5&4" and not ms["SUN-2"]["final"], ms)
late = [mk(f"L{h}{c}", c, h, PAR[h]) for h in (6, 7) for c in (101, 102, 103, 104)]
res = se.write_scores(gid, "dev", 101, late)
check("holes after the close-out are still taken for every player (skins play on)",
      all(r["result"] == "ok" for r in res["results"]) and len(res["results"]) == 8, res)
ms = {m["match_id"]: m for m in se.get_group_card(gid, "dev")["match_status"]}
check("the decided match's result does not move", ms["SUN-1"]["margin"] == "5&4" and ms["SUN-1"]["closed_at"] == 5, ms["SUN-1"])

sub = dict(print_scorer_customer_id=102)
r = se.submit_card(gid, "dev", 101, finish_early=True, **sub)
check("finish early is refused while another match on the card is still live",
      r.get("error") == "the card isn't complete yet", r)
# SUN-2: Fehlis wins 8 and 9 for SA? make it Wade 2 up after 9 -> decided at the last hole
se.write_scores(gid, "dev", 101, [mk("W8", 103, 8, PAR[8] - 1), mk("X8", 104, 8, PAR[8]),
                                  mk("W9", 103, 9, PAR[9] - 1), mk("X9", 104, 9, PAR[9])])
ms = {m["match_id"]: m for m in se.get_group_card(gid, "dev")["match_status"]}
check("SUN-2 is decided over the last hole", ms["SUN-2"]["final"], ms["SUN-2"])
r = se.submit_card(gid, "dev", 101, **sub)
check("a plain submit of an incomplete card is still refused", r.get("error") == "the card isn't complete yet", r)
r = se.submit_card(gid, "dev", 101, finish_early=True, **sub)
check("finish early is taken once every Cup match on the card is decided",
      r.get("submitted") and r.get("finished_early") is True, r)
with db._connect(DB) as conn:
    note = conn.execute("SELECT note FROM se_signoffs WHERE group_id = ? AND kind = 'scorekeeper' "
                        "AND voided_at IS NULL", (gid,)).fetchone()[0]
check("the scorekeeper's attestation says the card was finished after the match",
      "finished after the match was decided" in note, note)
r = se.sign_card(gid, "p102", 102)
check("a player signs a card finished early as it is", "error" not in r, r)

# a plain (non-Cup) card never finishes early
rid2 = se.create_round(901, 9, label="plain", course_holes=NINE)["round_id"]
g2 = se.upsert_group(rid2, 1, players=[{"customer_id": 101, "display_name": "Matthew Jenkins", "playing_handicap": 0}])["group_id"]
se.claim_group(g2, "dev2", 101)
se.write_scores(g2, "dev2", 101, [mk("P1", 101, 1, 4)])
r = se.submit_card(g2, "dev2", 101, finish_early=True, print_scorer_name="Someone")
check("a card with no Cup match can't finish early", r.get("error") == "the card isn't complete yet", r)

print("Skins: a card finished early holds no hole open for the field")
feed = se.get_entered_scores(901, round_id=rid)
dial = json.loads(db.get_app_setting("lsc_matches"))
over = lsc_cup.merge_entry_feed(dial, feed)
check("merge_entry_feed names the players of the early-finished card who left holes blank (SUN-1's)",
      sorted(over["sun"].get("finished") or []) == [101, 102], over["sun"].get("finished"))
CTX = {"index": {101: 5.0, 102: 6.0, 103: 7.0, 104: 8.0}}
board = lsc_cup.compute_board(dial, over, None, CTX)
sk1 = board["sessions"][0]["skins"] or {}
h1 = [h for gr in sk1.get("groups", []) if gr.get("entrants") for h in gr.get("holes", [])]
check("with it every hole settles: holes 8-9 are decided by the players who posted them",
      h1 and all(h["status"] != "pending" for h in h1), h1)
dial2 = dict(dial)
held = lsc_cup.compute_board(dial2, {"sun": {k: v for k, v in over["sun"].items() if k != "finished"}}, None, CTX)
sk2 = held["sessions"][0]["skins"] or {}
h2 = [h for gr in sk2.get("groups", []) if gr.get("entrants") for h in gr.get("holes", [])]
check("without it the blank holes would hold the session's skins pending",
      any(h["status"] == "pending" for h in h2), h2)

print("The card carries the board's cup status")
orig = lsc_cup.lsc_board_payload
lsc_cup.lsc_board_payload = lambda db_path=None: {
    "configured": True, "event_id": 901, "teams": {"austin": {"points": 13.5}, "sa": {"points": 14.0}},
    "cup": {"status": "retained", "winner": "sa"}, "sessions": []}
try:
    cs = se._cup_standings(rid)
finally:
    lsc_cup.lsc_board_payload = orig
check("cup_standings.cup = the board's status, winner and event",
      (cs or {}).get("cup") == {"status": "retained", "winner": "sa", "event_id": 901, "preview": False}, cs)

print("The page contract")
T = open(os.path.join(HERE, "templates/score_entry.html")).read()
C = open(os.path.join(HERE, "templates/contests.html")).read()
J = open(os.path.join(HERE, "static/js/lsc-clinch.js")).read()
for s in ['? "win" : "wins"', 'for <span class="ch">${esc(w.chapter)}</span>', 'Match halved, \\u00BD point each',
          "Keep playing for skins", "Finish and confirm the card", "Keep scoring",
          'const wonKey = (m) => "se_mwon_" + tk + "_" + m.match_id;']:
    check(f"score_entry.html carries {s!r}", s in T)
wm = T[T.index("function wonModal()"):T.index("function clinchCheck()")]
check("the won modal is the scorekeeper's only (never a follower's read-only view)",
      "!keeping()" in wm.split("\n")[1], wm.split("\n")[1])
check("it is remembered when shown (a reload never repeats it)",
      wm.index("store.set(wonKey(m), true)") < wm.index("document.body.append"))
check("Finish sets the finish-early flag and opens Check the card",
      'store.set(K.fin, true)' in wm and 'hole = "review"' in wm)
check("the submit says finish_early when holes are blank", "finish_early: !allDone()" in T)
check("the screens follow roundOver(), not allDone()",
      "if (roundOver()) return checkScreen();" in T and "const done = roundOver();" in T)
check("the shimmer is keyed to the winner's side",
      ".se-mcard.won.lead-austin::after" in T and ".se-mcard.won.lead-sa::after" in T
      and 'm.cup && m.lead_team ? " lead-" + m.lead_team' in T and ".se-mcard.halved" in T)
check("reduced motion stops the shimmer",
      ".se-mcard.won::after, .se-mcard.halved::after { animation: none; display: none; }" in T)
check("score_entry.html loads the clinch pop-up and checks it on every render",
      '/static/js/lsc-clinch.js' in T and "clinchCheck();" in T)
check("the scorer's LEADERBOARD loads it in Cup mode and calls it from the board's cup",
      "{% if SOLO_CUP %}<script src=\"/static/js/lsc-clinch.js" in C
      and "window.lscClinchPopup({ status: cup.status" in C)
check("lsc-clinch.js: once per device, the logo, both words",
      '"lsc_clinch_seen_" + (c.event_id || "cup")' in J and "/static/lsc-logo-dark.png" in J
      and '" RETAINS" : " WINS") + " THE LONE STAR CUP"' in J and "prefers-reduced-motion" in J)
node = subprocess.run(["node", "-e", """
global.window = {}; global.document = {getElementById: () => null};
require(process.argv[1]);
const h = window.lscClinchHeadline;
console.log(JSON.stringify([h({status: 'won', winner: 'austin'}), h({status: 'retained', winner: 'sa'}),
  window.lscClinchPopup({status: 'open', winner: null})]));
""", os.path.join(HERE, "static/js/lsc-clinch.js")], capture_output=True, text=True)
check("the clinch words, run", node.stdout.strip() == json.dumps(
    ["AUSTIN WINS THE LONE STAR CUP", "SAN ANTONIO RETAINS THE LONE STAR CUP", False]).replace(" ", "")
    or json.loads(node.stdout or "null") == ["AUSTIN WINS THE LONE STAR CUP", "SAN ANTONIO RETAINS THE LONE STAR CUP", False],
    node.stdout + node.stderr)

print()
if F:
    print(f"FAILED: {len(F)}")
    for x in F:
        print("  -", x)
    sys.exit(1)
print("ALL PASS")
