"""Tests for the live-scoring engine (email_parser/live_scoring.py).

The engine's job is to reproduce every event game from raw gross hole
scores alone. These tests pin the ratified rules from
`docs/claude/side-games.md` and the derivation contract from
`docs/claude/scoring.md`, so a formula-layer change that would break the
Stage-1 parity gate fails here first.

Run: python3 test_live_scoring.py
"""

import random
import sys

from email_parser.database import (get_scoring_formulas,
                                   compute_hole_derivations,
                                   _SCORING_FORMULA_DEFAULTS)
from email_parser import live_scoring as ls

FORMULAS = dict(_SCORING_FORMULA_DEFAULTS)

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


# A real-shaped nine: two par 3s, one par 5, stroke indexes 1-9.
NINE = [
    {"hole": 1, "par": 4, "stroke_index": 3, "yardage": 380},
    {"hole": 2, "par": 3, "stroke_index": 9, "yardage": 155},
    {"hole": 3, "par": 5, "stroke_index": 1, "yardage": 520},
    {"hole": 4, "par": 4, "stroke_index": 5, "yardage": 400},
    {"hole": 5, "par": 4, "stroke_index": 7, "yardage": 365},
    {"hole": 6, "par": 3, "stroke_index": 8, "yardage": 190},
    {"hole": 7, "par": 4, "stroke_index": 2, "yardage": 430},
    {"hole": 8, "par": 4, "stroke_index": 6, "yardage": 375},
    {"hole": 9, "par": 5, "stroke_index": 4, "yardage": 505},
]
PAR_TOTAL = sum(h["par"] for h in NINE)  # 36


def player(key, name, ph, scores, **kw):
    p = {"key": key, "name": name, "playing_handicap": ph, "scores": scores,
         "buys_net": True, "buys_gross": True, "is_member": True,
         "customer_id": None}
    p.update(kw)
    return p


def even_par(offset=0):
    return {h["hole"]: h["par"] + offset for h in NINE}


# ---------------------------------------------------------------------------
print("\n== build_cards: derivation + allocation ==")

state = {"holes": NINE, "players": [
    player("a", "Scratch Sam", 0, even_par()),
    player("b", "Bogey Bob", 9, even_par(1)),
]}
cards = ls.build_cards(state, FORMULAS)
sam, bob = cards[0], cards[1]

check("even-par gross totals to par", sam["gross"] == PAR_TOTAL,
      f"got {sam['gross']} want {PAR_TOTAL}")
check("scratch player receives no strokes",
      all(h["strokes_received"] == 0 for h in sam["holes"]))
check("9 handicap over 9 holes = one stroke per hole",
      all(h["strokes_received"] == 1 for h in bob["holes"]))
check("dots are DERIVED when GG supplies none",
      sam["allocation_source"] == "derived")
# Net table: par = 1 point. Even par on 9 holes = 9 net points.
check("even par scores 9 net Stableford points", sam["stableford_net"] == 9,
      f"got {sam['stableford_net']}")
# Bogey Bob is +1 gross everywhere but gets a stroke everywhere -> net par.
check("bogey-with-a-stroke nets par all the way round",
      bob["stableford_net"] == 9, f"got {bob['stableford_net']}")
check("net total = gross minus playing handicap",
      bob["net"] == bob["gross"] - 9, f"{bob['net']} vs {bob['gross']}-9")
check("thru counts holes with a score", sam["thru"] == 9)
check("complete flag set on a full card", sam["complete"] is True)

# GIVEN dots must be used verbatim — that is how a GG-seeded card keeps
# GG's own allocation so a parity diff isolates the scoring math.
given = {"holes": NINE, "players": [
    player("a", "Odd Allocation", 9, even_par(),
           strokes_received={h["hole"]: (2 if h["hole"] == 1 else 0)
                             for h in NINE})]}
gc = ls.build_cards(given, FORMULAS)[0]
check("GIVEN dots override derived allocation",
      gc["allocation_source"] == "given"
      and gc["holes"][0]["strokes_received"] == 2
      and gc["holes"][1]["strokes_received"] == 0)

# Plus handicap: a stroke goes BACK on the easiest hole (highest index = 9).
plus = {"holes": NINE, "players": [player("p", "Texas Terry", -1, even_par())]}
pc = ls.build_cards(plus, FORMULAS)[0]
give_back = {h["hole"]: h["strokes_received"] for h in pc["holes"]}
check("plus handicap gives a stroke back on the easiest hole",
      give_back[2] == -1 and sum(give_back.values()) == -1, str(give_back))
check("plus-handicap net = gross + 1", pc["net"] == pc["gross"] + 1)

# Partial card
partial = {"holes": NINE, "players": [
    player("x", "Mid Round", 0, {1: 4, 2: 3, 3: 5})]}
px = ls.build_cards(partial, FORMULAS)[0]
check("partial card reports thru correctly", px["thru"] == 3)
check("partial card is not complete", px["complete"] is False)
check("partial card only totals played holes", px["gross"] == 12)


# ---------------------------------------------------------------------------
print("\n== Individual Net / Gross: flighting + activation ==")

# 12 net buyers on a nine -> 2 flights, split at HCP 12.0 per side-games.md.
field12 = [player(f"n{i}", f"Net {i}", hcp, even_par())
           for i, hcp in enumerate([0, 3, 5, 8, 10, 11, 12, 14, 16, 18, 20, 24])]
res = ls.game_individual(ls.build_cards({"holes": NINE, "players": field12},
                                        FORMULAS),
                         ls.SEED_LIVE_SCORING_CONFIG, "9", "net")
check("12 net buyers on a nine -> 2 flights", len(res["flights"]) == 2,
      f"got {len(res['flights'])}")
f1 = next(f for f in res["flights"] if f["flight"] == "1")
f2 = next(f for f in res["flights"] if f["flight"] == "2")
check("flight 1 is everyone below HCP 12.0", f1["players"] == 6,
      f"got {f1['players']}")
check("flight 2 is HCP 12.0 and up", f2["players"] == 6,
      f"got {f2['players']}")

# 11 buyers -> single flight (the ratified band boundary).
field11 = field12[:11]
res11 = ls.game_individual(ls.build_cards({"holes": NINE, "players": field11},
                                          FORMULAS),
                           ls.SEED_LIVE_SCORING_CONFIG, "9", "net")
check("11 net buyers on a nine -> 1 flight", len(res11["flights"]) == 1)

# Individual Gross activates at 16 buyers on a nine (LIVE matrix value).
res_g15 = ls.game_individual(
    ls.build_cards({"holes": NINE,
                    "players": [player(f"g{i}", f"G{i}", 5, even_par())
                                for i in range(15)]}, FORMULAS),
    ls.SEED_LIVE_SCORING_CONFIG, "9", "gross")
check("Individual Gross is inactive at 15 buyers on a nine",
      res_g15["active"] is False and res_g15["warnings"])
res_g16 = ls.game_individual(
    ls.build_cards({"holes": NINE,
                    "players": [player(f"g{i}", f"G{i}", i, even_par())
                                for i in range(16)]}, FORMULAS),
    ls.SEED_LIVE_SCORING_CONFIG, "9", "gross")
check("Individual Gross activates at 16 buyers with 3 flights",
      res_g16["active"] is True and len(res_g16["flights"]) == 3,
      f"active={res_g16['active']} flights={len(res_g16['flights'])}")

# Non-buyers are excluded from a buyers-only game.
mixed = ls.build_cards({"holes": NINE, "players": [
    player("buy", "Buyer", 5, even_par()),
    player("no", "Non Buyer", 5, even_par(), buys_net=False),
]}, FORMULAS)
res_mix = ls.game_individual(mixed, ls.SEED_LIVE_SCORING_CONFIG, "9", "net")
check("non-buyers excluded from Individual Net", res_mix["buyers"] == 1)

# Ranking: most points wins, stroke score breaks the tie.
tie_field = ls.build_cards({"holes": NINE, "players": [
    player("hi", "Higher Net", 4, even_par()),
    player("lo", "Lower Net", 0, even_par()),
]}, FORMULAS)
res_tie = ls.game_individual(tie_field, ls.SEED_LIVE_SCORING_CONFIG, "9", "net")
rows = res_tie["flights"][0]["rows"]
check("equal points tie broken by the stroke score",
      rows[0]["name"] == "Higher Net" and rows[0]["place"] == 1,
      f"got {[ (r['name'], r['points'], r['score']) for r in rows ]}")


# ---------------------------------------------------------------------------
print("\n== Team Net: one best NET ball per hole vs par ==")

team_state = {"holes": NINE, "players": [
    # Team 1: A is even par; B birdies hole 1 gross.
    player("a", "A", 0, even_par(), team=1),
    player("b", "B", 0, {**even_par(), 1: 3}, team=1),
    # Team 2: both bogey everything, no strokes.
    player("c", "C", 0, even_par(1), team=2),
    player("d", "D", 0, even_par(1), team=2),
]}
tn = ls.game_team_net(ls.build_cards(team_state, FORMULAS),
                      ls.SEED_LIVE_SCORING_CONFIG)
t1 = next(t for t in tn["teams"] if t["team"] == 1)
t2 = next(t for t in tn["teams"] if t["team"] == 2)
check("best ball takes the birdie on hole 1", t1["vs_par"] == -1,
      f"got {t1['vs_par']}")
check("bogey-everywhere team is +9", t2["vs_par"] == 9, f"got {t2['vs_par']}")
check("lower vs-par team ranks first", t1["place"] == 1 and t2["place"] == 2)
check("best-ball credit names the player", t1["holes"][0]["by"] == "B")
check("short team is flagged, not silently scored",
      any("blind draw" in w for w in tn["warnings"]), str(tn["warnings"]))

# A handicap stroke can win the hole for the team.
strokes_state = {"holes": NINE, "players": [
    player("e", "E", 9, even_par(1), team=1),
    player("f", "F", 9, even_par(1), team=1),
]}
tn2 = ls.game_team_net(ls.build_cards(strokes_state, FORMULAS),
                       ls.SEED_LIVE_SCORING_CONFIG)
check("team net uses NET balls (bogeys with strokes = even)",
      tn2["teams"][0]["vs_par"] == 0, f"got {tn2['teams'][0]['vs_par']}")

no_team = ls.game_team_net(ls.build_cards(
    {"holes": NINE, "players": [player("z", "Z", 0, even_par())]}, FORMULAS),
    ls.SEED_LIVE_SCORING_CONFIG)
check("no pairings -> Team Net warns instead of inventing teams",
      not no_team["teams"] and no_team["warnings"])


# ---------------------------------------------------------------------------
print("\n== Skins: outright low GROSS within flight ==")

skins_state = {"holes": NINE, "players": [
    player(f"s{i}", f"S{i}", 5, even_par()) for i in range(8)
]}
# S0 alone birdies hole 1; S1 and S2 both birdie hole 3 (tie -> no skin).
skins_state["players"][0]["scores"][1] = 3
skins_state["players"][1]["scores"][3] = 4
skins_state["players"][2]["scores"][3] = 4
sk = ls.game_skins(ls.build_cards(skins_state, FORMULAS),
                   ls.SEED_LIVE_SCORING_CONFIG, "9")
check("8 gross buyers on a nine -> 2 flights", len(sk["flights"]) == 2,
      f"got {len(sk['flights'])}")
check("skins is active at 8 buyers", sk["active"] is True)
all_skins = [s for f in sk["flights"] for s in f["skins"]]
check("outright low gross wins a skin",
      any(s["hole"] == 1 and s["winner"] == "S0" for s in all_skins),
      str(all_skins))
check("a tied hole yields no skin",
      not any(s["hole"] == 3 for s in all_skins), str(all_skins))
check("tied holes are counted",
      sum(f["tied_holes"] for f in sk["flights"]) >= 1)

sk_small = ls.game_skins(ls.build_cards(
    {"holes": NINE, "players": [player(f"s{i}", f"S{i}", 5, even_par())
                                for i in range(6)]}, FORMULAS),
    ls.SEED_LIVE_SCORING_CONFIG, "9")
check("below 8 buyers Skins 1/2 Net is flagged as NOT implemented",
      sk_small["active"] is False
      and any("1/2 Net" in w for w in sk_small["warnings"]),
      str(sk_small["warnings"]))


# ---------------------------------------------------------------------------
print("\n== MVP: highest net Stableford + incomplete-card guard ==")

mvp_state = {"holes": NINE, "players": [
    player("w", "Winner", 0, {**even_par(), 1: 3}),   # birdie -> 10 pts
    player("r", "Runner", 0, even_par()),             # 9 pts
]}
mv = ls.game_mvp(ls.build_cards(mvp_state, FORMULAS),
                 ls.SEED_LIVE_SCORING_CONFIG, 9)
check("MVP determined on a complete field", mv["status"] == "determined",
      mv["status"])
check("MVP is the highest net Stableford",
      mv["winners"][0]["name"] == "Winner")

# Kerry's s9.20 catch: a card short of a full round leaves it provisional
# while its player could still catch the leader.
mvp_partial = {"holes": NINE, "players": [
    player("w", "Winner", 0, {**even_par(), 1: 3}),
    player("p", "Still Playing", 0, {h: NINE[h - 1]["par"] for h in range(1, 9)}),
]}
mvp2 = ls.game_mvp(ls.build_cards(mvp_partial, FORMULAS),
                   ls.SEED_LIVE_SCORING_CONFIG, 9)
check("an unfinished card that could still catch the leader blocks the MVP",
      mvp2["status"] == "incomplete_cards" and mvp2["incomplete"],
      mvp2["status"])

# Mathematically eliminated: the leader is further ahead than the hole can pay.
mvp_elim = {"holes": NINE, "players": [
    player("w", "Winner", 0, {h: NINE[h - 1]["par"] - 1 for h in range(1, 10)}),
    player("d", "Done", 0, {h: NINE[h - 1]["par"] + 3 for h in range(1, 9)}),
]}
mvp3 = ls.game_mvp(ls.build_cards(mvp_elim, FORMULAS),
                   ls.SEED_LIVE_SCORING_CONFIG, 9)
check("an eliminated unfinished card does not block the MVP",
      mvp3["status"] == "determined", mvp3["status"])

mvp_none = ls.game_mvp(ls.build_cards(
    {"holes": NINE, "players": [player("n", "N", 0, even_par(),
                                       buys_net=False)]}, FORMULAS),
    ls.SEED_LIVE_SCORING_CONFIG, 9)
check("no NET buyers -> no MVP", mvp_none["status"] == "no_net_buyers")


# ---------------------------------------------------------------------------
print("\n== CTP slots + Hole-in-One ==")

ctp = ls.ctp_slots({"holes": NINE}, ls.SEED_LIVE_SCORING_CONFIG)
check("two par-3s on the nine fill both CTP slots", len(ctp["slots"]) == 2,
      str(ctp["slots"]))
check("no spillover when the par-3s cover the slots", not ctp["spillover"])

# Three par 3s, two slots -> the two SHORTEST are selected.
three_par3 = [dict(h) for h in NINE]
three_par3[3] = {"hole": 4, "par": 3, "stroke_index": 5, "yardage": 120}
ctp3 = ls.ctp_slots({"holes": three_par3}, ls.SEED_LIVE_SCORING_CONFIG)
picked = sorted(s["hole"] for s in ctp3["slots"])
check("more par-3s than slots -> the SHORTEST are selected",
      picked == [2, 4], f"got {picked} (yardages 155/190/120)")

one_par3 = [dict(h) for h in NINE]
one_par3[5] = {"hole": 6, "par": 4, "stroke_index": 8, "yardage": 190}
ctp1 = ls.ctp_slots({"holes": one_par3}, ls.SEED_LIVE_SCORING_CONFIG)
check("fewer par-3s than slots -> Longest Putt on the last hole",
      len(ctp1["slots"]) == 1 and len(ctp1["spillover"]) == 1
      and ctp1["spillover"][0]["hole"] == 9, str(ctp1))

hio_state = {"holes": NINE, "players": [
    player("m", "Member Ace", 0, {**even_par(), 2: 1}),
    player("g", "Guest Ace", 0, {**even_par(), 6: 1}, is_member=False),
]}
hio = ls.game_hio(ls.build_cards(hio_state, FORMULAS),
                  ls.SEED_LIVE_SCORING_CONFIG)
check("both aces detected", len(hio["aces"]) == 2)
check("member ace is eligible",
      next(a for a in hio["aces"] if a["name"] == "Member Ace")["eligible"])
check("guest ace pays in but cannot win",
      not next(a for a in hio["aces"] if a["name"] == "Guest Ace")["eligible"])

# A par-3 ace takes the HIGHER of the HIO bonus and the vs-par value (=8),
# never both — the ratified rule in _SCORING_FORMULA_DEFAULTS.
ace_card = ls.build_cards(hio_state, FORMULAS)[0]
ace_hole = next(h for h in ace_card["holes"] if h["hole"] == 2)
check("par-3 ace scores 8 gross points (eagle == HIO bonus, not stacked)",
      ace_hole["stableford_gross"] == 8, f"got {ace_hole['stableford_gross']}")


# ---------------------------------------------------------------------------
print("\n== compute_leaderboard: the whole surface ==")

full = {"holes": NINE, "players": [
    player("a", "A", 0, even_par(), team=1),
    player("b", "B", 9, even_par(1), team=1),
    player("c", "C", 4, even_par(), team=2),
    player("d", "D", 18, even_par(2), team=2),
]}
lb = ls.compute_leaderboard(full, FORMULAS)
check("leaderboard reports the hole count", lb["holes"] == 9)
check("nine-hole round resolves to the 9-hole rule set", lb["holes_key"] == "9")
check("every game is present",
      set(lb["games"]) == {"individual_net", "individual_gross", "team_net",
                           "skins", "mvp", "ctp", "hio"})
check("overall board is ranked by net points then net score",
      lb["overall"][0]["place"] == 1)
check("overall board covers the whole field", len(lb["overall"]) == 4)

# 18 holes must route to the 18-hole rule set.
EIGHTEEN = NINE + [{**h, "hole": h["hole"] + 9} for h in NINE]
lb18 = ls.compute_leaderboard(
    {"holes": EIGHTEEN,
     "players": [player("a", "A", 0, {h["hole"]: h["par"] for h in EIGHTEEN})]},
    FORMULAS)
check("eighteen-hole round resolves to the 18-hole rule set",
      lb18["holes_key"] == "18" and lb18["holes"] == 18)
check("18-hole CTP gets two slots per nine",
      len(lb18["games"]["ctp"]["slots"]) == 4,
      str(lb18["games"]["ctp"]["slots"]))


# ---------------------------------------------------------------------------
print("\n== parity_diff: the Stage-1 confidence gate ==")

pcards = ls.build_cards({"holes": NINE, "players": [
    player("a", "A", 0, even_par()),
    player("b", "B", 9, even_par(1)),
]}, FORMULAS)
gg_ok = {"a": {"gross": PAR_TOTAL, "net": PAR_TOTAL, "playing_handicap": 0},
         "b": {"gross": PAR_TOTAL + 9, "net": PAR_TOTAL,
               "playing_handicap": 9}}
pd = ls.parity_diff(pcards, gg_ok)
check("agreeing numbers report parity", pd["parity"] is True, str(pd))
check("clean players counted", pd["players_clean"] == 2)

gg_bad = dict(gg_ok)
gg_bad["b"] = {**gg_ok["b"], "net": PAR_TOTAL + 1}
pd_bad = ls.parity_diff(pcards, gg_bad)
check("a disagreeing field breaks parity", pd_bad["parity"] is False)
check("the mismatched field is named",
      pd_bad["rows"][1]["deltas"][0]["field"] == "net",
      str(pd_bad["rows"][1]["deltas"]))
check("mismatched player counted", pd_bad["players_mismatched"] == 1)

pd_missing = ls.parity_diff(pcards, {"a": gg_ok["a"]})
check("a player GG never carded is reported, not scored",
      pd_missing["players_without_gg"] == 1)

# A GG row of all-Nones must never manufacture a clean parity report.
pd_empty = ls.parity_diff(pcards, {"a": {"gross": None, "net": None},
                                   "b": {"gross": None, "net": None}})
check("an empty GG row checks nothing and claims no parity",
      pd_empty["checked"] == 0 and pd_empty["parity"] is False, str(pd_empty))

# Allocation parity: our DERIVED dots vs GG's own dots.
pd_dots = ls.parity_diff(pcards, {
    "b": {"strokes_received": {h["hole"]: (2 if h["hole"] == 1 else 0)
                               for h in NINE}}})
check("derived dots that disagree with GG's are surfaced per hole",
      any(d["field"].startswith("dots@")
          for d in pd_dots["rows"][1]["deltas"]),
      str(pd_dots["rows"][1]["deltas"][:3]))


# ---------------------------------------------------------------------------
print("\n== simulate_strokes ==")

rng = random.Random(7)
sims = [ls.simulate_strokes(4, 9, rng) for _ in range(400)]
check("simulated scores are always at least 1", min(sims) >= 1)
check("a 9-handicap averages over par on a par 4",
      4.0 < sum(sims) / len(sims) < 7.0, f"mean {sum(sims)/len(sims):.2f}")
scratch = [ls.simulate_strokes(4, 0, rng) for _ in range(400)]
check("a scratch player averages lower than a 9",
      sum(scratch) / len(scratch) < sum(sims) / len(sims))
check("simulation is deterministic for a given seed",
      [ls.simulate_strokes(4, 9, random.Random(1)) for _ in range(3)]
      == [ls.simulate_strokes(4, 9, random.Random(1)) for _ in range(3)])


# ---------------------------------------------------------------------------
print("\n== formula-layer wiring ==")

check("engine defaults to the live formula layer",
      ls._default_derive_hole(4, 4, 0, get_scoring_formulas())["stableford_net"]
      == compute_hole_derivations(4, 4, 0, get_scoring_formulas())["stableford_net"])

# Championship schedule (+1 per net category) must flow straight through.
champ = dict(FORMULAS)
champ["stableford_net_table"] = {k: v + 1 for k, v in
                                 FORMULAS["stableford_net_table"].items()}
champ_card = ls.build_cards({"holes": NINE,
                             "players": [player("a", "A", 0, even_par())]},
                            champ)[0]
check("championship formulas raise every net category",
      champ_card["stableford_net"] == 18, f"got {champ_card['stableford_net']}")


print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL LIVE-SCORING TESTS PASSED")
