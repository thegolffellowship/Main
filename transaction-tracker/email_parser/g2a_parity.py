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

WHAT THIS HARNESS CANNOT GRADE, AND WILL NOT PRETEND TO:
  * RACES. `get_points_race_standings` and `get_monthly_points` both RENDER
    A SNAPSHOT FETCHED FROM GOLF GENIUS. There is no independent TGF points
    computation to diff against them, so "our race matches GG's race" would
    be comparing GG to itself — the same hollow-parity defect already found
    in `test_live_scoring_center.py` (CA Queue #10 note). The race tier
    therefore reports `status: "ungradeable"` with the reason, and a G2a run
    is never called a PASS while it does.
"""

from __future__ import annotations

# The two residual classes A2 allows. Anything else is a FAIL.
RESIDUAL_DERIVED_DOTS_PLUS1 = "derived_dots_ph_plus1_no_ndb_cap"
RESIDUAL_TIED_PAYOUT_ROUNDING = "tied_group_payout_1_2_cents_under_gg"
A2_CLASSES = (RESIDUAL_DERIVED_DOTS_PLUS1, RESIDUAL_TIED_PAYOUT_ROUNDING)

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

    # ── tier 4: RACES — ungradeable, and says so ──
    out["tiers"]["races"] = {
        "status": "ungradeable",
        "reason": (
            "Our race standings are a SNAPSHOT FETCHED FROM GOLF GENIUS "
            "(`get_points_race_standings` renders `gg_points_standings`; "
            "`get_monthly_points` fetches the GG portal). There is no "
            "independent TGF points computation, so diffing them against GG "
            "compares GG to itself and would report a hollow pass. G2a "
            "cannot claim the race leg until a TGF-side points engine "
            "exists — that is a build, not a test."),
        "what_would_unblock_it": (
            "A ratified TGF points schedule (position -> points, per race) "
            "computed from our own results, which does not exist today."),
    }
    out["blockers"].append(
        "races tier is UNGRADEABLE — we mirror GG's standings rather than "
        "computing them, so there is nothing to diff")

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
        "note": ("Category and game keys are not the same vocabulary, so "
                 "this reports both totals rather than asserting a per-row "
                 "match. Mapping them is the next step and must be ratified "
                 "before a purse row is graded — a wrong mapping would "
                 "manufacture agreement."),
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
