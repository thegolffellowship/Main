"""LSC synthetic weekend (CA #800 item 5 / #801 step 3) — Track B.

Runs a made-up cup weekend THROUGH SCORE ENTRY (the se_* write path a
phone uses) on a SCRATCH database, then reads the board exactly as the
member endpoint does (lsc_cup.lsc_board_payload) and grades it against
answers computed BY HAND (the literals below; the reasoning is in the
comments). Never point it at production.

usage: TGF_REHEARSAL is set by the script itself
  python3 tools/lsc_synthetic_weekend.py <scratch_db_path> [--synthetic-index] [--out <report.json>]
"""
import json
import os
import sys

DB = os.path.abspath(sys.argv[1])
if DB.startswith("/data") or "transactions.db" == os.path.basename(DB) and "scratch" not in DB:
    sys.exit(f"refusing: {DB} does not look like a scratch copy")
if any(k.startswith("RAILWAY_") for k in os.environ) and "--i-am-scratch" not in sys.argv:
    sys.exit("refusing: this looks like Railway; pass --i-am-scratch only for the scratch file")
os.environ["DATABASE_PATH"] = DB
os.environ["TGF_REHEARSAL"] = "1"      # Health #813: outbound guard on import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SYNTH_INDEX = "--synthetic-index" in sys.argv   # option C: no real indexes

from email_parser import score_entry as se          # noqa: E402
from email_parser import lsc_cup                     # noqa: E402
from email_parser.database import _connect           # noqa: E402
from email_parser import database as _db             # noqa: E402

# Prove outbound is off before writing anything (Health #813).
import socket                                        # noqa: E402
try:
    socket.create_connection(("graph.microsoft.com", 443), timeout=3)
    sys.exit("OUTBOUND NOT BLOCKED - refusing to run")
except Exception as _e:
    OUTBOUND_PROOF = type(_e).__name__
    if OUTBOUND_PROOF != "RehearsalOutboundBlocked":
        sys.exit(f"outbound guard not proven ({OUTBOUND_PROOF}) - refusing to run")

# Option C: synthetic TGF 18-hole indexes (the index READ path is not
# exercised; 13 sits exactly on the 12.0 break -> Flight 2).
SYNTH = {7: 9.8, 35: 6.1, 37: 4.0, 6: 5.5, 130: 14.2, 315: 13.0, 13: 12.0}
if SYNTH_INDEX:
    _db._handicap_index_18_by_customer = lambda db_path=None, as_of=None: dict(SYNTH)

EVENT = 3329
PAR = 4
COURSE = [{"hole": h, "par": PAR, "stroke_index": h} for h in range(1, 19)]

# ---- the made-up field (real cup-roster customer_ids; names from the roster)
# Austin: 7, 4, 37, 315, 13 (5 players)   SA: 35, 130, 6, 87 (4 players)
# 14 v 13 in miniature: Austin is the bigger side, one Austin player sits
# each session and no Austin player sits twice (#757 draft).
BUYERS = {7, 37, 315, 13, 35, 130, 6}          # 4 and 87 did NOT buy skins
SITS = {"am": 13, "pm": 315, "sun": 4}           # 13, 315 buyers -> $25 credit; 4 not

SESSIONS = {
    "am": {"label": "Saturday AM — Four-Ball", "format": "fourball",
           "matches": [("M1", [7, 4], [35, 130]), ("M2", [37, 315], [6, 87])],
           "ph": {7: 10, 4: 14, 35: 8, 130: 12, 37: 6, 315: 6, 6: 6, 87: 6}},
    "pm": {"label": "Saturday PM — Chapman", "format": "chapman",
           "matches": [("M1", [7, 37], [35, 6]), ("M2", [4, 13], [130, 87])],
           "ph": {7: 10, 37: 6, 35: 8, 6: 6, 4: 14, 13: 12, 130: 12, 87: 16}},
    "sun": {"label": "Sunday — Singles", "format": "singles",
            "matches": [("S1", [7], [35]), ("S2", [37], [130]),
                        ("S3", [315], [6]), ("S4", [13], [87])],
            "ph": {7: 10, 35: 8, 37: 6, 130: 12, 315: 10, 6: 6, 13: 12, 87: 16}},
}

# gross: default par everywhere, then the designed deviations
def grid(players):
    return {c: {h: PAR for h in range(1, 19)} for c in players}

AM = grid([7, 4, 35, 130, 37, 315, 6, 87])
AM[6][3] = 3            # M2 SA birdie on 3
AM[37][9] = 3           # M2 Austin birdie on 9
AM[130][12] = 7         # X PICKUP (130 picks up on 12; partner 35 halves it)
AM_MARKS = {130: {12: "picked_up"}}

PM_TEAM = {             # Chapman: ONE ball per team (se_teams row)
    (7, 37): {h: PAR for h in range(1, 19)},
    (6, 35): {**{h: PAR for h in range(1, 19)}, 2: 3, 4: 3},
    (4, 13): {**{h: PAR for h in range(1, 19)}, 7: 3, 8: 3},
    (87, 130): {**{h: PAR for h in range(1, 19)}, 1: 5},
}

SUN = grid([7, 35, 37, 130, 315, 6, 13, 87])
SUN[7][2] = 7; SUN[35][2] = 7      # X PICKUP: 7 picks up on 2 (net 6 < 35's net 7)
SUN_MARKS = {7: {2: "picked_up"}}
for h in (1, 2, 3, 4, 10):
    SUN[6][h] = 3
for h in (1, 2, 3, 4, 5):
    SUN[13][h] = 3

# ---- HAND-COMPUTED ANSWERS -------------------------------------------------
# AM four-ball, 90% off the low (whs half-up): M1 7:9 4:12.6->13 35:7.2->7
#   130:10.8->11; low 7 -> strokes 7:2 (SI1-2) 4:6 (SI1-6) 130:4 (SI1-4).
#   Holes 1-4 best net 3 v 3 halved; 5-6 Austin (4 nets 3 v 4); rest par
#   -> Austin 2 up with 1 to play after 17 -> AUSTIN 2&1.
#   130's pickup on 12 changes nothing (35 posts a 4) -> still 2&1.
#   M2 all PH 6 -> 5.4->5 each, no strokes; SA wins 3, Austin wins 9 -> HALVED.
# PM Chapman 60/40: M1 Austin .6*6+.4*10=7.6->8, SA .6*6+.4*8=6.8->7,
#   Austin +1 on SI1: wins 1 (net 3); SA wins 2 and 4 -> SA 1 UP.
#   M2 Austin .6*12+.4*14=12.8->13, SA .6*12+.4*16=13.6->14, SA +1 on SI1:
#   hole 1 SA 5-1=4 v 4 halved; Austin wins 7, 8 -> 2 up, 1 to play -> AUSTIN 2&1.
# Sunday singles 100%: S1 7 +2 (SI1-2): wins 1 (net 3); hole 2 7 net 6 but
#   PICKED UP -> cannot win -> 35 wins 2; rest halved -> HALVED.
#   (If the pickup rule failed: Austin 2 UP.)
#   S2 130 +6: wins 1-6 -> 6 up with 5 to play after 13 -> SA 6&5.
#   S3 315 +4: 6's birdies 1-4 halve (net 3 v 3); 6 birdie 10 -> SA 1 UP.
#   S4 87 +4: 13's birdies 1-4 halve; 13 birdie 5 -> AUSTIN 1 UP.
EXPECT_MATCHES = {
    ("am", "M1"): ("austin", "2&1"), ("am", "M2"): ("halved", None),
    ("pm", "M1"): ("sa", "1 UP"),    ("pm", "M2"): ("austin", "2&1"),
    ("sun", "S1"): ("halved", None), ("sun", "S2"): ("sa", "6&5"),
    ("sun", "S3"): ("sa", "1 UP"),   ("sun", "S4"): ("austin", "1 UP"),
}
# Points: Austin 1+.5 +0+1 +.5+0+0+1 = 4.0 ; SA .5 +1+0 +.5+1+1+0 = 4.0
# 8 points on the board, 4-4, SA is the defending champion -> SA RETAINS.
EXPECT_POINTS = {"austin": 4.0, "sa": 4.0}
EXPECT_CUP = {"status": "retained", "winner": "sa", "total": 8.0}
# Skins pots = $25 x buyers who PLAY the round (#787 item 4):
#   AM buyers playing 7,35,130,37,315,6 = 6 -> $150 (13 sits: $25 credit)
#   PM buyers playing 7,37,35,6,13,130  = 6 -> $150 (315 sits: $25 credit)
#   SUN buyers playing 7,37,315,13,35,130,6 = 7 -> $175 (4 sits, no buy: nothing)
EXPECT_POTS = {"am": 15000, "pm": 15000, "sun": 17500}
# AM team skins (gross best ball), ALL four teams play (#759):
#   hole 3 M2-SA (6/87 MIXED) 3 unique; hole 9 M2-Austin 3 unique. 2 skins,
#   $75 each: 6 gets the WHOLE $75 (87 didn't buy); 37 $37.50, 315 $37.50.
# PM: hole 1 SA-M2 5 (4,4,4 tie) none; 2,4 M1-SA; 7,8 M2-Austin (4/13 MIXED).
#   4 skins $37.50: 35 $37.50, 6 $37.50, 13 the whole $75.00.
EXPECT_TEAM_PAY = {"am": {6: 7500, 37: 3750, 315: 3750},
                   "pm": {35: 3750, 6: 3750, 13: 7500}}
EXPECT_CREDITS = {13: 2500, 315: 2500}          # sit-out wallet credits owed


def write_session(key, sess, rid):
    """Groups = one per match; claim, write (with a duplicated op_id to
    stand in for a weak-signal retry), and pickup marks."""
    ph = sess["ph"]
    gids = {}
    for n, (mid, a, s) in enumerate(sess["matches"], start=1):
        players = [{"customer_id": c, "display_name": f"#{c}",
                    "playing_handicap": ph[c]} for c in a + s]
        gids[mid] = se.upsert_group(rid, n, label=mid, players=players,
                                    db_path=DB)["group_id"]
    for mid, a, s in sess["matches"]:
        gid = gids[mid]
        dev = f"synthetic-{key}-{mid}"
        assert se.claim_group(gid, dev, a[0], db_path=DB).get("granted")
        ops = []
        if sess["format"] == "chapman":
            for pair in (a, s):
                team = se.add_team(rid, gid, pair[0], pair[1], db_path=DB)["team_id"]
                sc = PM_TEAM[tuple(sorted(pair))]
                for h in range(1, 19):
                    ops.append({"op_id": f"{key}-{mid}-t{team}-{h}", "hole": h,
                                "gross": sc[h], "team_id": team})
        else:
            grid_ = AM if key == "am" else SUN
            marks = AM_MARKS if key == "am" else SUN_MARKS
            for c in a + s:
                for h in range(1, 19):
                    op = {"op_id": f"{key}-{mid}-c{c}-{h}", "hole": h,
                          "gross": grid_[c][h], "customer_id": c}
                    if marks.get(c, {}).get(h):
                        op["mark"] = marks[c][h]
                    ops.append(op)
        for i in range(0, len(ops), 40):
            r = se.write_scores(gid, dev, a[0], ops[i:i + 40], db_path=DB)
            bad = [x for x in r.get("results", []) if x["result"] not in ("ok", "dup")]
            assert not bad and "error" not in r, (key, mid, bad or r)
        retry = se.write_scores(gid, dev, a[0], ops[:3], db_path=DB)   # retry
        assert all(x["result"] == "dup" for x in retry["results"]), retry


def main():
    rounds = {}
    for key, sess in SESSIONS.items():
        rounds[key] = se.create_round(EVENT, 18, label=f"SYNTHETIC {sess['label']}",
                                      course_holes=COURSE, db_path=DB)["round_id"]
        write_session(key, sess, rounds[key])

    with _connect(DB) as conn:
        dial = lsc_cup._setting_json(conn, "lsc_matches") or {}
        dial.update({"event_id": EVENT, "board_live": False,
                     "defending_champion": "sa", "_note": "SYNTHETIC WEEKEND (scratch)"})
        dial["sessions"] = [
            {"id": k, "label": s["label"], "format": s["format"], "n_holes": 18,
             "se_round": rounds[k],
             "matches": [{"id": m, "austin": a, "sa": b} for m, a, b in s["matches"]]}
            for k, s in SESSIONS.items()]
        addons = lsc_cup._setting_json(conn, "oneoff_addons") or {}
        addons[str(EVENT)] = {str(c): ["skins"] for c in sorted(BUYERS)}
        for k, v in (("lsc_matches", dial), ("oneoff_addons", addons)):
            conn.execute("DELETE FROM app_settings WHERE key = ?", (k,))
            conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?)",
                         (k, json.dumps(v)))
        conn.commit()

    board = lsc_cup.lsc_board_payload(db_path=DB)
    rows = []

    def check(name, got, want):
        rows.append((name, "PASS" if got == want else "FAIL", want, got))

    check("board source is entered scores", board.get("source"), "entry")
    check("member gate: board_live false", board.get("board_live"), False)
    by = {s["id"]: s for s in board["sessions"]}
    for (sid, mid), (w, res) in EXPECT_MATCHES.items():
        m = next(x for x in by[sid]["matches"] if x.get("match_id") == mid)
        idx = m.get("gg_winner_idx")
        got_w = {1: "austin", 2: "sa"}.get(idx, "halved") if m.get("state") == "final" else m.get("state")
        check(f"{sid} {mid} result (final)", (got_w, m.get("gg_margin") if got_w != "halved" else None), (w, res))
    pts = {"austin": 0.0, "sa": 0.0}
    for s_ in board["sessions"]:
        for m in s_["matches"]:
            for k in pts:
                pts[k] += float((m.get("points") or {}).get(k) or 0)
    check("points (sum of match points)", pts, EXPECT_POINTS)
    check("teams header points", {t: float((board.get("teams") or {}).get(t, {}).get("points", -1))
                                  if isinstance((board.get("teams") or {}).get(t), dict) else None
                                  for t in pts}, EXPECT_POINTS)
    cup = board.get("cup") or {}
    check("cup status (4-4, SA defending)",
          {"status": cup.get("status"), "winner": cup.get("winner"), "total": cup.get("total")},
          EXPECT_CUP)
    for sid, want in EXPECT_POTS.items():
        check(f"{sid} skins pot = $25 x buyers who play", (by[sid].get("skins") or {}).get("pot_cents"), want)
    for sid, want in EXPECT_TEAM_PAY.items():
        got = {}
        for g in (by[sid].get("skins") or {}).get("groups") or []:
            for p in g.get("payouts") or []:
                for pp in p.get("per_player") or []:
                    got[pp["customer_id"]] = got.get(pp["customer_id"], 0) + pp["cents"]
        check(f"{sid} team skins payout (mixed teams play, buyer gets full skin)", got, want)
    # Sunday flighted gross skins: an independent oracle written from the
    # ruling (index < 12.0 = Flight 1, else Flight 2; half the pot each; a
    # unique low gross wins; a picked-up ball never wins; no carryover;
    # a buyer with no index can't be flighted). The INPUT (each player's
    # frozen index on this database) is read, the answer is not.
    with _connect(DB) as conn:
        idx = lsc_cup._skins_ctx(conn, dial, DB).get("index") or {}
    sun_players = [c for _, a, b in SESSIONS["sun"]["matches"] for c in a + b if c in BUYERS]
    ix = {c: idx.get(c, idx.get(str(c))) for c in sun_players}
    flights = {1: [c for c in sun_players if ix[c] is not None and float(ix[c]) < 12.0],
               2: [c for c in sun_players if ix[c] is not None and float(ix[c]) >= 12.0]}
    want_sun, half = {}, EXPECT_POTS["sun"] // 2
    for f, members in flights.items():
        won = {}
        for h in range(1, 19):
            live = {c: SUN[c][h] for c in members if not SUN_MARKS.get(c, {}).get(h)}
            if not live:
                continue
            lo = min(live.values())
            at = [c for c, v in live.items() if v == lo]
            if len(at) == 1:
                won[at[0]] = won.get(at[0], 0) + 1
        tot = sum(won.values())
        if tot:
            per = half / tot          # these designs divide evenly (checked below)
            for c, n in won.items():
                want_sun[c] = want_sun.get(c, 0) + round(per * n)
    got_sun = {}
    for g in (by["sun"].get("skins") or {}).get("groups") or []:
        for p in g.get("payouts") or []:
            for pp in p.get("per_player") or []:
                got_sun[pp["customer_id"]] = got_sun.get(pp["customer_id"], 0) + pp["cents"]
    check(f"sun flighted skins payout, oracle (index {ix})", got_sun, want_sun)
    if SYNTH_INDEX:
        # BY HAND: Flight 1 (<12.0) = 7, 35, 37, 6; Flight 2 = 130, 315, 13.
        # Pot $175 -> $87.50 a flight. F1: 6 alone at 3 on 1,2,3,4,10 (7's
        # picked-up 7 on 2 can't win anyway) -> 5 skins, $87.50 to 6.
        # F2: 13 alone at 3 on 1-5 -> 5 skins, $87.50 to 13.
        check("sun flighted skins payout, by hand (12.0 break -> Flight 2)",
              got_sun, {6: 8750, 13: 8750})
    check("outbound blocked before any write", OUTBOUND_PROOF, "RehearsalOutboundBlocked")
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    if out:
        json.dump({"db": os.path.basename(DB), "synthetic_index": SYNTH_INDEX,
                   "rounds": rounds,
                   "rows": [{"check": r[0], "result": r[1], "want": r[2], "got": r[3]}
                            for r in rows]},
                  open(out, "w"), indent=1, default=str)
    for r in rows:
        print(f"{r[1]:4}  {r[0]}\n      want {r[2]}\n      got  {r[3]}")


if __name__ == "__main__":
    main()
