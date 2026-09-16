"""half-Net Skins, and the a9.23 Avery Ranch finding that forced it.

THE THESIS THIS FILE PINS. On 2026-09-15 four players bought the gross
bundle at a9.23 Avery Ranch on a nine. Below eight buyers the side-games
matrix switches Skins to "SKINS 1/2 Net $" — a NET game — so that is the
game Golf Genius ran and paid. Our engine computed GROSS skins regardless,
found three skins all to Luke Youngs, and reported that GG was
contradicting itself about Carlos Zapata's hole 7.

GOLF GENIUS WAS RIGHT AND WE WERE WRONG. Zapata made gross 4 on a par 4,
received a stroke there under the 50% allowance, and netted 3 — an outright
net birdie, which is exactly what GG's own detail line says ("Birdie on 7").
The buyer count had silently changed WHICH GAME WAS PLAYED, and the rules of
that game lived only in a Golf Genius settings screen.

WHAT IS PROVEN AND WHAT IS NOT. GG's detail strings are relative to par and
therefore pin the allocation from the outside:

    YOUNGS, Luke    "Par on 2, Birdie on 3, Eagle on 5"   $39
    ZAPATA, Carlos  "Birdie on 7"                         $13   (pot $52)

Luke's hole 5 is a par 5 he made in 3. GG calls that an EAGLE, so Luke
received ZERO strokes — with a stroke it would have been an Albatross. His
playing handicap is 1.0, so 50% = 0.5 rounded DOWN. That eliminates
round-half-up and is the only rounding fact this event establishes.

It does NOT establish what 2.5 (Zapata) and 3.5 (Melchor) do. Every naive
independent rounding hands Eduardo Melchor a fifth skin that GG did not pay.
That gap is CA Queue #7 and is asserted below so nobody closes it by
guessing.

Run: python3 test_half_net_skins.py
"""

import sys

from email_parser.database import _SCORING_FORMULA_DEFAULTS
from email_parser import live_scoring as ls

FORMULAS = dict(_SCORING_FORMULA_DEFAULTS)
FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


# --------------------------------------------------------------------------
# a9.23 Avery Ranch, front nine, as imported. Par and stroke index are
# identical on the Blue and White tees, which is why one hole list serves.
# --------------------------------------------------------------------------
PAR = {1: 4, 2: 4, 3: 5, 4: 4, 5: 5, 6: 3, 7: 4, 8: 3, 9: 4}
SI = {1: 15, 2: 13, 3: 9, 4: 5, 5: 1, 6: 11, 7: 3, 8: 17, 9: 7}
HOLES = [{"hole": h, "par": PAR[h], "stroke_index": SI[h], "yardage": 350}
         for h in range(1, 10)]

# The four GROSS-bundle buyers and their gross cards.
GROSS = {
    "YOUNGS, Luke":    {1: 4, 2: 4, 3: 4, 4: 5, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5},
    "ZAPATA, Carlos":  {1: 4, 2: 5, 3: 7, 4: 5, 5: 7, 6: 4, 7: 4, 8: 3, 9: 5},
    "MELCHOR, Eduardo": {1: 5, 2: 5, 3: 5, 4: 5, 5: 6, 6: 6, 7: 7, 8: 4, 9: 5},
    "STRAITON, Robert": {1: 5, 2: 5, 3: 6, 4: 7, 5: 6, 6: 3, 7: 5, 8: 3, 9: 5},
}
PH = {"YOUNGS, Luke": 1.0, "ZAPATA, Carlos": 5.0,
      "MELCHOR, Eduardo": 7.0, "STRAITON, Robert": 0.0}
CUSTOMER_ID = {"YOUNGS, Luke": 13, "ZAPATA, Carlos": 439,
               "MELCHOR, Eduardo": 61, "STRAITON, Robert": 31}

POT = 52.0
# What Golf Genius actually paid, and what this file exists to reproduce.
GG_SKINS = {(2, "YOUNGS, Luke", "Par"), (3, "YOUNGS, Luke", "Birdie"),
            (5, "YOUNGS, Luke", "Eagle"), (7, "ZAPATA, Carlos", "Birdie")}
GG_MONEY = {"YOUNGS, Luke": 39.0, "ZAPATA, Carlos": 13.0}


def a923_state():
    return {"holes": HOLES, "players": [
        {"key": name, "customer_id": CUSTOMER_ID[name], "name": name,
         "playing_handicap": PH[name], "flight": None, "team": None,
         "buys_net": True, "buys_gross": True, "is_member": True,
         "scores": GROSS[name]} for name in GROSS]}


def label_vs_par(score, par):
    return {-3: "Albatross", -2: "Eagle", -1: "Birdie",
            0: "Par", 1: "Bogey", 2: "Double"}.get(score - par, f"{score - par:+d}")


def skins_set(result):
    out = set()
    for f in result["flights"]:
        for s in f["skins"]:
            out.add((s["hole"], s["winner"], label_vs_par(s["score"], s["par"])))
    return out


def money(result, pot=POT):
    tally = {}
    for f in result["flights"]:
        for s in f["skins"]:
            tally[s["winner"]] = tally.get(s["winner"], 0) + 1
    total = sum(tally.values())
    if not total:
        return {}
    return {w: round(n * pot / total, 2) for w, n in tally.items()}


cards = ls.build_cards(a923_state(), FORMULAS)

print("== the matrix is the governing layer ==")

res = ls.game_skins(cards, ls.SEED_LIVE_SCORING_CONFIG, "9")
check("4 gross buyers on a nine selects the half-Net variant",
      res["variant"] == "half_net", res["variant"])
check("the selected game is NET, not gross", res["basis"] == "net")
check("it carries Golf Genius's own name for the game",
      res["gg_name"] == "SKINS 1/2 Net $", str(res.get("gg_name")))
check("the selection is REPORTED with its reason, not inferred",
      "matrix runs" in (res["selection"] or {}).get("reason", ""),
      str(res.get("selection")))
check("the 50% allowance is carried as data",
      res["handicaps"]["dials"]["allowance_pct"] == 50)
check("'off the lowest' is a SEPARATE dial from the percentage",
      res["handicaps"]["dials"]["off_lowest"] is True
      and "off_lowest" not in str(res["handicaps"]["dials"]["allowance_pct"]))
check("skins declares itself a pops-per-hole game",
      res["pops_per_hole"] is True)

print("\n== the bug this replaced: the gross question on a net game ==")

gross_only = ls.game_skins(
    cards,
    {**ls.SEED_LIVE_SCORING_CONFIG,
     "games": {**ls.SEED_LIVE_SCORING_CONFIG["games"],
               "skins": {**ls.SEED_LIVE_SCORING_CONFIG["games"]["skins"],
                         "variants": [
                             {"name": "gross", "label": "Skins",
                              "when_buyers": {"9": [0, None]},
                              "basis": "gross", "handicap": None}]}}},
    "9")
gross_skins = skins_set(gross_only)
check("computing GROSS gives 3 skins, all to Youngs — the wrong answer",
      len(gross_skins) == 3
      and {w for _, w, _ in gross_skins} == {"YOUNGS, Luke"},
      str(sorted(gross_skins)))
check("the gross answer pays Zapata nothing, contradicting GG",
      "ZAPATA, Carlos" not in money(gross_only), str(money(gross_only)))

print("\n== the NET game reproduces Golf Genius exactly ==")

# GG's own detail lines pin Youngs at ZERO strokes ("Eagle on 5", not
# Albatross). Both surviving allocations put Zapata and Melchor level; each
# reproduces GG's board, hole for hole and dollar for dollar.
for tag, strokes in (("Zapata 2 / Melchor 2", {"ZAPATA, Carlos": 2,
                                               "MELCHOR, Eduardo": 2}),
                     ("Zapata 3 / Melchor 3", {"ZAPATA, Carlos": 3,
                                               "MELCHOR, Eduardo": 3})):
    override = {}
    for name in GROSS:
        n = strokes.get(name, 0)
        override[name] = {h: 0 for h in SI}
        for hole in sorted(SI, key=lambda x: SI[x])[:n]:
            override[name][hole] = 1
    r = ls.game_skins(cards, ls.SEED_LIVE_SCORING_CONFIG, "9",
                      strokes_override=override)
    check(f"[{tag}] reproduces GG's four skins exactly",
          skins_set(r) == GG_SKINS, str(sorted(skins_set(r))))
    check(f"[{tag}] reproduces GG's money exactly ($39 / $13 of $52)",
          money(r) == GG_MONEY, str(money(r)))
    check(f"[{tag}] Zapata's hole 7 is an outright NET birdie",
          any(s["hole"] == 7 and s["winner"] == "ZAPATA, Carlos"
              and s["gross"] == 4 and s["score"] == 3 and s["pops"] == 1
              for f in r["flights"] for s in f["skins"]),
          str(sorted(skins_set(r))))
    check(f"[{tag}] Youngs' hole 5 is an EAGLE, so he took no stroke",
          any(s["hole"] == 5 and s["winner"] == "YOUNGS, Luke"
              and s["pops"] == 0 and s["score"] == 3
              for f in r["flights"] for s in f["skins"]))

print("\n== the rounding dial is NOT ratified — CA Queue #7 ==")

check("the board declares its handicap dial unratified",
      res.get("handicap_ratified") is False)
check("and says so in a warning a reader will see",
      any("NOT ratified" in w for w in res["warnings"]), str(res["warnings"]))

# The guard: no naive independent rounding of 0.5 / 2.5 / 3.5 reproduces
# GG. If a future change makes one of these pass, the dial has been GUESSED
# rather than ruled on, and this test is the thing that should stop it.
for mode in ("half_up", "half_even", "floor", "half_down"):
    cfg = {**ls.SEED_LIVE_SCORING_CONFIG,
           "games": {**ls.SEED_LIVE_SCORING_CONFIG["games"],
                     "skins": {**ls.SEED_LIVE_SCORING_CONFIG["games"]["skins"],
                               "variants": [
                                   {**ls.SEED_LIVE_SCORING_CONFIG["games"]
                                    ["skins"]["variants"][0],
                                    "handicap": {
                                        **ls.SEED_LIVE_SCORING_CONFIG["games"]
                                        ["skins"]["variants"][0]["handicap"],
                                        "rounding": mode}}]}}}
    r = ls.game_skins(cards, cfg, "9")
    check(f"'{mode}' does NOT reproduce GG (the dial is still open)",
          skins_set(r) != GG_SKINS,
          f"{mode} unexpectedly matched — has the dial been ruled on?")

# Kerry ratified a TGF rounding convention the same day (CA Queue #5, mailbox
# #530): the PLUS-handicap round deduction rounds half away from zero. The
# tempting shortcut is to apply it to this allowance too and call the dial
# closed. It does not reproduce GG, and this asserts so, because the shortcut
# will occur to the next reader as well.
_half_away = {"YOUNGS, Luke": 1, "ZAPATA, Carlos": 3,
              "MELCHOR, Eduardo": 4, "STRAITON, Robert": 0}
_ov = {}
for _name in GROSS:
    _ov[_name] = {h: 0 for h in SI}
    for _hole in sorted(SI, key=lambda x: SI[x])[:_half_away[_name]]:
        _ov[_name][_hole] = 1
_ha = ls.game_skins(cards, ls.SEED_LIVE_SCORING_CONFIG, "9", strokes_override=_ov)
check("TGF's ratified 'half away from zero' does NOT reproduce GG either",
      skins_set(_ha) != GG_SKINS, str(sorted(skins_set(_ha))))
check("  ...it makes Youngs' hole 5 an Albatross, where GG says Eagle",
      any(s["hole"] == 5 and s["winner"] == "YOUNGS, Luke"
          and label_vs_par(s["score"], s["par"]) == "Albatross"
          for f in _ha["flights"] for s in f["skins"]),
      str(sorted(skins_set(_ha))))
check("  ...and it pays a fifth skin GG did not pay",
      len(skins_set(_ha)) == 5, str(sorted(skins_set(_ha))))

check("half-up is refuted by GG's own words, not merely by the payout",
      ls._round_allowance(0.5, "half_up") == 1
      and ls._round_allowance(0.5, "half_down") == 0,
      "GG calls Youngs' hole 5 an Eagle, so 0.5 must round DOWN")

print("\n== the USGA allowance table, with its verification state ==")

check("the four-player ladder matches Kerry's ratified Team Net figures",
      [ls._USGA_ALLOWANCES[k]["allowance_pct"]
       for k in ("best_1_of_4", "best_2_of_4", "best_3_of_4", "best_4_of_4")]
      == [75, 85, 100, 100])
check("the confirmed ladder is marked confirmed",
      all(ls._USGA_ALLOWANCES[k]["confirmed"]
          for k in ("best_1_of_4", "best_2_of_4", "best_3_of_4",
                    "best_4_of_4")))
check("Team Net's allowance follows the BALL COUNT, as data",
      ls.SEED_LIVE_SCORING_CONFIG["games"]["team_net"]
      ["allowance_pct_by_balls"] == {"1": 75, "2": 85, "3": 100, "4": 100})
check("the UNVERIFIED Cart Net two-ball row carries no number to fall back on",
      ls._USGA_ALLOWANCES["best_2_of_2"]["allowance_pct"] is None
      and ls._USGA_ALLOWANCES["best_2_of_2"]["confirmed"] is False)
check("and the one-ball Cart Net row is flagged unconfirmed too",
      ls._USGA_ALLOWANCES["best_1_of_2"]["confirmed"] is False)

print("\n== pops are a property of the GAME, not of the card ==")

G = ls.SEED_LIVE_SCORING_CONFIG["games"]
check("Individual Net is ROUND-level (gross total - playing handicap)",
      G["individual_net"]["pops_per_hole"] is False)
check("Individual Gross is ROUND-level and sees no handicap at all",
      G["individual_gross"]["pops_per_hole"] is False)
check("Team Net best-ball is HOLE-level", G["team_net"]["pops_per_hole"] is True)
check("Net Points / MVP Stableford is HOLE-level",
      G["mvp"]["pops_per_hole"] is True)
check("every game DECLARES the flag rather than leaving it to be assumed",
      all("pops_per_hole" in G[g] for g in G), str(sorted(G)))


# ---------------------------------------------------------------------------
print("\n== the scoring-skins-audit bridge asks the game's ACTUAL question ==")
# The bridge is what Kerry runs. Drive the real `skins_audit` over a9.23's
# real numbers, with the two DB reads it makes served from an in-memory
# database, so the whole path is exercised and not just the engine under it.

import sqlite3
from email_parser import database as db

_TEE = {"YOUNGS, Luke": 885, "ZAPATA, Carlos": 886,
        "MELCHOR, Eduardo": 885, "STRAITON, Robert": 885}
_RID = {"YOUNGS, Luke": 3519, "ZAPATA, Carlos": 3521,
        "MELCHOR, Eduardo": 3520, "STRAITON, Robert": 3527}

_mem = sqlite3.connect(":memory:", check_same_thread=False)
_mem.execute("CREATE TABLE scoring_rounds (id INTEGER, playing_handicap REAL, "
             "tee_id INTEGER)")
_mem.execute("CREATE TABLE course_tee_holes (tee_id INTEGER, "
             "hole_number INTEGER, stroke_index INTEGER)")
for _n in GROSS:
    _mem.execute("INSERT INTO scoring_rounds VALUES (?,?,?)",
                 (_RID[_n], PH[_n], _TEE[_n]))
for _t in (885, 886):                      # Blue and White share the index
    for _h, _s in SI.items():
        _mem.execute("INSERT INTO course_tee_holes VALUES (?,?,?)", (_t, _h, _s))
_mem.commit()


class _KeepOpen:
    """skins_audit closes the connection it is handed; this one outlives it."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, *a, **k):
        return self._conn.execute(*a, **k)

    def close(self):
        pass


_handle = _KeepOpen(_mem)

_fake_board = {
    "event_name": "a9.23 Avery Ranch",
    "hole_cols": list(range(1, 10)),
    "n_gross_buyers": 4,
    "cards": {str(_RID[n]): [[h, GROSS[n][h]] for h in range(1, 10)]
              for n in GROSS},
    "skins_board": [{"label": None, "rows": [
        {"scoring_round_id": _RID[n], "player_name": n, "buyer": True,
         "win_skins": False, "won": []} for n in GROSS]}],
    "skin_cells": {},
}

_real_lb, _real_conn = db.get_event_leaderboard, db.get_connection
db.get_event_leaderboard = lambda *a, **k: _fake_board
db.get_connection = lambda *a, **k: _handle
try:
    audit = db.skins_audit("a9.23 Avery Ranch")
finally:
    db.get_event_leaderboard, db.get_connection = _real_lb, _real_conn

check("the audit names the game the matrix selected",
      audit["game"]["variant"] == "half_net"
      and audit["game"]["gg_name"] == "SKINS 1/2 Net $",
      str(audit["game"].get("variant")))
check("the audit computes on a NET basis, not gross",
      audit["game"]["basis"] == "net")
check("the audit reports the buyer count that made the decision",
      audit["game"]["gross_buyers"] == 4)
check("the audit declares the unratified dial rather than paying off it",
      audit["game"]["handicap_ratified"] is False
      and any("NOT ratified" in w for w in audit["warnings"]),
      str(audit["warnings"]))
_f = audit["flights"][0]
check("the audit prints each buyer's playing handicap AND game strokes",
      _f["playing_handicaps"]["ZAPATA, Carlos"]["playing_handicap"] == 5.0
      and "game_strokes" in _f["playing_handicaps"]["ZAPATA, Carlos"],
      str(_f["playing_handicaps"]))
_scored = [h for h in _f["holes"] if h.get("verdict") != "no scores posted"]
check("every hole shows BOTH the gross and the pops, so the two questions "
      "can never be confused again",
      all("gross" in h for h in _scored) and any(h.get("pops") for h in _scored),
      str(_scored[6]))
check("hole 7 is no longer read as a tie — Zapata holds it on net",
      any(h["hole"] == 7 and h.get("winner") == "ZAPATA, Carlos"
          for h in _scored),
      str([h for h in _scored if h["hole"] == 7]))
check("the old note claiming 'outright low gross' is gone",
      "the game the matrix selected" in audit["note"].lower(), audit["note"])

print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL half-NET SKINS TESTS PASSED")
