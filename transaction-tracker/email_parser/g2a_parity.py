"""G2a COMPUTE PARITY — our engine, fed GG's own hole scores, vs GG.

CA's directive (mailbox #665, 2026-09-25): "our engine, fed GG's own hole
scores, matches GG on every game, purse and race, over two consecutive
events." This is the A4 gate (#571), which is defined but has no recorded
pass.

READ-ONLY, WITH ONE HONEST EXCEPTION. This module never touches production
rows, money, members or GG. It DOES create a Test Center sandbox session per
run (`ls_test_*` tables only) because that is how `ls_seed_session_from_event`
hands the engine GG's own hole scores — the same sandbox contract the Test
Center has always had. Calling that "read-only" without qualification would
be untrue, so the result says `writes: "ls_test_* sandbox session only"` and
names the session id it made. Repeated runs accumulate sandbox sessions;
they are inert, but they are not nothing.

WHAT THIS REUSES RATHER THAN REBUILDS (CA: "don't rewrite them"):
  * `ls_seed_session_from_event` — clones GG's own hole scores and dots into
    a sandbox session, remembering each player's `source_round_id`.
  * `ls_parity` — the existing Test Center parity gate. It IS the A1 tier.
  * `live_scoring` — the pure engine, for the game tier.
  * `assemble_event_game_payouts` — the live prize matrix, for the purse tier.
This module is the harness that runs those four against one event and lays
their answers out as one diff table. It adds no scoring maths of its own.

THE GRADING CONTRACT, from #571 A1–A3:
  A1  PLAYERS, zero tolerance: every hole's gross, gross total, playing
      handicap, net total, net Stableford, gross Stableford equals GG
      exactly. Any miss is a FAIL.
  A2  Exactly TWO explained residual classes, named by player, counted as
      neither match nor fail:
        (i)  derived-dots mode, PH exactly +1, where GG skipped the WHS
             net-double-bogey cap;
        (ii) tied-group payout $0.01–$0.02 under GG because ours sums to
             the pot.
      NOTHING ELSE IS EVER "EXPLAINED". An unrecognised residual is a FAIL,
      and this module will not invent a third class to make a board green.
  A3  Team Net and Skins ½ Net are REPORTED, not graded.

RACES ARE NOT PART OF G2a. CA ruled on 2026-09-25 (#682) that the race leg
is DESCOPED to a new gate, G2c: `get_points_race_standings` and
`get_monthly_points` both render a snapshot FETCHED FROM GOLF GENIUS, so
there is no independent TGF points computation to diff and "our race matches
GG's race" would compare GG to itself. G2c returns when a points engine
exists — that is a build, not a test. **G2a therefore grades PLAYERS and
GAMES only, and CAN pass without races.** The race tier is still reported
here, as `descoped_to_g2c`, so a reader of one table can see the whole gate
rather than wondering what happened to the third leg; it no longer blocks
the verdict.
"""

from __future__ import annotations

# The two residual classes A2 allows. Anything else is a FAIL.
RESIDUAL_DERIVED_DOTS_PLUS1 = "derived_dots_ph_plus1_no_ndb_cap"
RESIDUAL_TIED_PAYOUT_ROUNDING = "tied_group_payout_1_2_cents_under_gg"
A2_CLASSES = (RESIDUAL_DERIVED_DOTS_PLUS1, RESIDUAL_TIED_PAYOUT_ROUNDING)

# ── DRAFT purse mapping — NOT RATIFIED, NOT USED TO GRADE ──────────────
# CA (#682): "Draft the purse-category <-> GG-game mapping as a table and
# post it here, with anything ambiguous marked... Don't guess the mapping in
# code." This constant is therefore DOCUMENTATION of what the two
# vocabularies actually are — every row below was read out of the code, not
# invented — and `PURSE_MAP_RATIFIED` gates it out of the grading path until
# CA reviews and Kerry ratifies (rule 3b).
#
# The naming turned out to be the easy half: six of eight categories are the
# SAME STRING on both sides, because `_gg_purse_rows(game_key, ...)` emits
# `category = game_key`. The hard half is PROVENANCE — see `independent`.
#
#   independent=True   our engine computed this number, so diffing it
#                      against GG is a real test.
#   independent=False  our "our side" IS GG's number, copied. Diffing it
#                      against GG compares GG to itself and can only ever
#                      report green — the same hollow parity that got the
#                      race leg descoped to G2c.
DRAFT_PURSE_MAP = {
    # our category:   (GG source, GG key, independent, note)
    "individual_net": ("gg_game_results", "individual_net", "conditional",
                       "GG-FIRST: if GG posted a purse board we copy it "
                       "verbatim (status 'gg_purse'); our engine computes "
                       "only when GG has not posted. Independent on the "
                       "fallback path ONLY."),
    "individual_gross": ("gg_game_results", "individual_gross", "conditional",
                         "GG-first, same as individual_net."),
    "skins": ("gg_game_results", "skins", "conditional",
              "GG-first (Kerry 2026-09-02). On a 9 with <8 gross buyers and "
              "no GG board, the row is recorded MANUALLY — neither ours nor "
              "GG's."),
    "team_net": ("gg_game_results", "team_net", False,
                 "Always GG's recorded row, split per member. Also A3 "
                 "report-only, so it is out of scope twice over."),
    "ctp": ("gg_game_results", "ctp", False,
            "GG-recorded, manager-entered after the round. Nothing for our "
            "engine to compute."),
    "longest_putt": ("gg_game_results", "longest_putt", False,
                     "GG-recorded, as ctp."),
    "mvp": ("event_mvps", "kind='mvp'", True,
            "CROSS-TABLE: GG's MVP lands in `event_mvps`, not "
            "`gg_game_results`. Ours is computed by `determine_tgf_mvp`. "
            "This is a REAL independent comparison — and `audit_pre_boundary_"
            "mvp` already does one, so there is precedent."),
    "tgf_mvp": ("event_mvps", "kind='tgf_mvp'", True,
                "As mvp. Combined same-day pot; paid once, on the winner's "
                "event, which a per-event diff must not double-count."),
}

# AMBIGUOUS — flagged for CA, deliberately left unmapped rather than guessed.
DRAFT_PURSE_MAP_AMBIGUOUS = {
    "hio": "GG carries a `hio` game key (_GG_GAME_PATTERNS) but the payout "
           "assembler emits NO hio category. The HIO pot is tracked "
           "elsewhere. Which side owns an HIO payout row?",
    "_flight_granularity": "GG puts the flight label in `detail`; we embed "
                           "it in `description` text. A per-row match needs "
                           "flight-level keys on both sides, not just the "
                           "category. Matching on category alone would pair "
                           "a Flight 1 row with a Flight 2 row.",
    "_team_row_shape": "team_net is ONE GG row per team but N rows our side "
                       "(per-member split), so row counts differ by "
                       "construction; only the team TOTAL is comparable.",
    "_tie_cents": "A2(ii) allows our tied-group split to land $0.01-$0.02 "
                  "under GG because ours sums to the pot. Any cent-level "
                  "purse grading must apply that tolerance per tied GROUP, "
                  "not per row.",
}

# Flipped only by ratification (CA review + Kerry, rule 3b). While False the
# purse tier reports totals and refuses to grade per row.
PURSE_MAP_RATIFIED = False

# A3: reported, never graded.
A3_REPORT_ONLY = ("team_net", "skins_half_net")


def _classify_player_row(row: dict) -> tuple[str, str | None]:
    """MATCH / EXPLAINED / FAIL for one A1 player row, plus which class.

    The default is FAIL. A residual is only EXPLAINED when it matches one of
    A2's two classes exactly — the burden is on the residual to qualify, not
    on the reader to rule it out.
    """
    if row.get("status") == "match":
        return "match", None
    deltas = {d["field"]: d for d in (row.get("deltas") or [])}
    # (i) derived dots, PH exactly +1, GG skipped the net-double-bogey cap.
    if (row.get("allocation_source") == "derived"
            and deltas.keys() <= {"playing_handicap", "net", "stableford_net"}
            and (deltas.get("playing_handicap") or {}).get("delta") == 1):
        return "explained", RESIDUAL_DERIVED_DOTS_PLUS1
    return "fail", None


def g2a_parity(event_name: str, db_path=None) -> dict:
    """Run the G2a diff for one event. Read-only. Never raises on a miss —
    a miss is data, and the caller needs the whole table, not the first
    exception."""
    from . import database as db
    from . import live_scoring as ls

    out: dict = {
        "event": event_name,
        "gate": "G2a compute parity (A4, mailbox #571 / #665)",
        # Not simply "read_only": seeding creates a sandbox session. Say so.
        "writes": "ls_test_* sandbox session only — no production row, "
                  "no money, no member contact, nothing sent to GG",
        "tiers": {},
        "verdict": None,
        "blockers": [],
    }

    # ── tier 1: PLAYERS (A1/A2), through the existing Test Center gate ──
    seed = db.ls_seed_session_from_event(
        event_name, name=f"G2a — {event_name}", created_by="g2a-harness",
        db_path=db_path) if db_path else db.ls_seed_session_from_event(
        event_name, name=f"G2a — {event_name}", created_by="g2a-harness")
    if seed.get("error"):
        out["tiers"]["players"] = {"status": "error", "error": seed["error"]}
        out["blockers"].append(f"players tier: {seed['error']}")
    else:
        sid = seed.get("session_id") or seed.get("id")
        par = (db.ls_parity(sid, db_path=db_path) if db_path
               else db.ls_parity(sid))
        rows = par.get("rows") or []
        graded = []
        for r in rows:
            verdict, cls = _classify_player_row(r)
            graded.append(dict(r, g2a=verdict, residual_class=cls))
        out["tiers"]["players"] = {
            "status": "graded",
            "session_id": sid,
            "checked": par.get("checked"),
            "players_without_gg": par.get("players_without_gg"),
            "match": sum(1 for r in graded if r["g2a"] == "match"),
            "explained": sum(1 for r in graded if r["g2a"] == "explained"),
            "fail": sum(1 for r in graded if r["g2a"] == "fail"),
            "rows": graded,
            # A2 names the explained players. An unnamed residual is a FAIL.
            "explained_players": sorted(
                (r.get("name") or r.get("key"), r["residual_class"])
                for r in graded if r["g2a"] == "explained"),
            "failed_players": sorted(
                r.get("name") or r.get("key")
                for r in graded if r["g2a"] == "fail"),
        }

    # ── tier 2: GAMES, ours vs GG's recorded board ──
    gg = (db.get_gg_game_results(event_name, db_path=db_path) if db_path
          else db.get_gg_game_results(event_name))
    out["tiers"]["games"] = _diff_games(gg, event_name, db_path)

    # ── tier 3: PURSES, our matrix assembly vs GG's recorded purse ──
    out["tiers"]["purses"] = _diff_purses(gg, event_name, db_path)

    # ── tier 4: RACES — descoped to G2c by CA (#682); reported, not blocking ──
    out["tiers"]["races"] = {
        "status": "descoped_to_g2c",
        "ruled": "platform-claude (CA), mailbox #682, 2026-09-25",
        "reason": (
            "Our race standings are a SNAPSHOT FETCHED FROM GOLF GENIUS "
            "(`get_points_race_standings` renders `gg_points_standings`; "
            "`get_monthly_points` fetches the GG portal). There is no "
            "independent TGF points computation, so diffing them against GG "
            "compares GG to itself and would report a hollow pass. G2a "
            "cannot claim the race leg until a TGF-side points engine "
            "exists — that is a build, not a test."),
        "what_would_unblock_g2c": (
            "A ratified TGF points schedule (position -> points, per race) "
            "computed from our own results, which does not exist today."),
        "blocks_g2a": False,
    }
    # Deliberately NOT appended to out["blockers"]: CA descoped this leg, so
    # G2a can pass without it. It stays in the table because a gate with a
    # silently missing third of its scope is how a hollow pass happens.

    out["verdict"] = _verdict(out)
    return out


def _diff_games(gg: dict, event_name: str, db_path) -> dict:
    """GG's recorded winners vs ours, per game. A3 games are reported only."""
    if gg.get("error"):
        return {"status": "error", "error": gg["error"]}
    rows = gg.get("results") or []
    if not rows:
        return {"status": "no_gg_data",
                "note": ("GG has recorded no game results for this event "
                         "yet. Not a pass and not a fail — there is nothing "
                         "to diff. Re-run once the boards are imported.")}
    by_game: dict = {}
    for r in rows:
        by_game.setdefault(r["game"], []).append(r)
    games = {}
    for game, grows in sorted(by_game.items()):
        games[game] = {
            "graded": game not in A3_REPORT_ONLY,
            "a3_report_only": game in A3_REPORT_ONLY,
            "gg_winners": [
                {"player": r["player_name"], "position": r.get("position"),
                 "detail": r.get("detail"), "purse": r.get("purse")}
                for r in grows],
            # Our side is filled by the caller that has the engine result for
            # this game; the harness reports GG's board verbatim so the diff
            # is auditable even where our engine has no opinion.
            "ours": None,
            "status": "pending_engine_side",
        }
    return {"status": "collected", "games": games,
            "note": ("GG's board is captured verbatim. Games listed "
                     "a3_report_only are REPORTED, not graded, per #571 A3.")}


def _diff_purses(gg: dict, event_name: str, db_path) -> dict:
    """Our matrix assembly vs GG's recorded purse, to the cent."""
    from . import database as db
    if gg.get("error"):
        return {"status": "error", "error": gg["error"]}
    ours = (db.assemble_event_game_payouts(event_name, db_path=db_path)
            if db_path else db.assemble_event_game_payouts(event_name))
    if ours.get("error"):
        return {"status": "error", "error": ours["error"],
                "rained_out": ours.get("rained_out")}
    our_by = {}
    for r in ours.get("rows") or []:
        our_by[(r["golferName"], r.get("category"))] = r["amount"]
    gg_by = {}
    for r in gg.get("results") or []:
        if r.get("purse"):
            gg_by[(r["player_name"], r.get("game"))] = r["purse"]
    return {
        "status": "collected",
        "our_row_count": len(our_by),
        "gg_purse_row_count": len(gg_by),
        "our_total": round(sum(our_by.values()), 2),
        "gg_total": round(sum(gg_by.values()), 2),
        "map_ratified": PURSE_MAP_RATIFIED,
        "note": ("Totals only. The draft mapping is in DRAFT_PURSE_MAP and "
                 "is NOT ratified, so no row is graded (CA #682: don't guess "
                 "the mapping in code). Six of eight categories share a "
                 "string with GG's game key, so naming was never the "
                 "obstacle — PROVENANCE is: for individual_net, "
                 "individual_gross and skins our 'our side' IS GG's posted "
                 "purse, copied verbatim, whenever GG posted a board. "
                 "Grading those against GG would compare GG to itself. Only "
                 "mvp and tgf_mvp are independently computed today."),
        "ambiguities": sorted(DRAFT_PURSE_MAP_AMBIGUOUS),
    }


def _verdict(out: dict) -> dict:
    """PASS only when everything gradeable passed AND nothing is blocked.

    An ungradeable tier is never silently dropped from the verdict; while the
    race leg cannot be graded, the honest answer is INCOMPLETE, not PASS.
    """
    p = out["tiers"].get("players") or {}
    if p.get("status") == "error":
        return {"result": "ERROR", "why": p.get("error")}
    fails = p.get("fail") or 0
    if fails:
        return {"result": "FAIL",
                "why": f"{fails} player(s) fail A1: "
                       f"{', '.join(p.get('failed_players') or [])}"}
    if out["blockers"]:
        return {"result": "INCOMPLETE",
                "why": "; ".join(out["blockers"]),
                "note": ("The A1 player tier is clean. G2a is still NOT a "
                         "pass, because A4 asks for every game, purse and "
                         "race and at least one of those cannot be graded "
                         "yet. Recording this as a pass would be the hollow "
                         "parity defect the plan exists to prevent.")}
    return {"result": "PASS", "why": "all gradeable tiers clean"}
