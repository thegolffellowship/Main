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

import re

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
A3_REPORT_ONLY = ("team_net", "team_net_board", "skins_half_net")


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
    board = None
    if (out["tiers"].get("players") or {}).get("status") == "graded":
        sid = out["tiers"]["players"]["session_id"]
        board = (db.ls_leaderboard(sid, db_path=db_path, pin_flights=True)
                 if db_path else db.ls_leaderboard(sid, pin_flights=True))
        if board.get("error"):
            board = None
    gg_mvp = _gg_recorded_mvp(event_name, db_path)
    out["tiers"]["games"] = _diff_games(gg, event_name, db_path,
                                        board=board, gg_mvp=gg_mvp)
    for game, g in (out["tiers"]["games"].get("games") or {}).items():
        if g.get("graded") and g.get("status") in ("pending_engine_side",
                                                     "no_engine_equivalent"):
            out["blockers"].append(
                f"games tier: {game} has no engine-side result to grade "
                f"({g['status']})")

    # ── tier 3: PURSES, our matrix assembly vs GG's recorded purse ──
    out["tiers"]["purses"] = _diff_purses(gg, event_name, db_path)
    if board is not None:
        st = (db.ls_build_state(sid, db_path=db_path) if db_path
              else db.ls_build_state(sid))
        eng = (db.engine_game_payouts(event_name, db_path=db_path, state=st)
               if db_path else db.engine_game_payouts(event_name, state=st))
        out["tiers"]["purses"]["engine"] = _grade_engine_purses(gg, eng)

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


def _norm_name(name) -> str:
    """'MURPHY, Mike' / 'Mike Murphy' / 'Bl[PALACIOS, Richard]' -> 'mike murphy'.

    Used only when a row carries no customer_id. The blind marker is
    stripped so a blind resolves to the member whose score it borrowed.
    """
    s = (name or "").strip()
    m = re.match(r"^bl\[(.*)\]", s, re.I)
    if m:
        s = m.group(1)
    if "," in s:
        last, first = s.split(",", 1)
        s = f"{first.strip()} {last.strip()}"
    return " ".join(s.lower().split())


def _card_index(board: dict):
    """(by customer_id, by normalised name) -> our card key."""
    by_cid, by_name = {}, {}
    for c in board.get("cards") or []:
        if c.get("customer_id") is not None:
            by_cid[c["customer_id"]] = c["key"]
        by_name.setdefault(_norm_name(c.get("name")), c["key"])
    return by_cid, by_name


def _resolve(row_cid, row_name, idx):
    by_cid, by_name = idx
    if row_cid is not None and row_cid in by_cid:
        return by_cid[row_cid]
    return by_name.get(_norm_name(row_name))


def _pos_int(pos):
    m = re.search(r"\d+", str(pos or ""))
    return int(m.group(0)) if m else None


def _grade_individual(grows, ours: dict, idx, names) -> dict:
    """GG's paid places vs our flight places, player by player.

    Each GG winner must hold the same place in our engine. Any player our
    engine places at or above the last paid place of that flight who is NOT
    on GG's board is an extra. Competition ranking on both sides, so a tie
    is 'T1' on GG and place 1 twice on ours.
    """
    if not ours or not ours.get("active"):
        return {"status": "mismatch", "diffs": [
            "our engine did not run this game "
            + "; ".join((ours or {}).get("warnings") or [])]}
    place_of, flight_of = {}, {}
    for f in ours.get("flights") or []:
        for r in f["rows"]:
            place_of[r["key"]] = r["place"]
            flight_of[r["key"]] = f["flight"]
    diffs, gg_keys, worst = [], set(), {}
    for r in grows:
        k = _resolve(r.get("customer_id"), r.get("player_name"), idx)
        pos = _pos_int(r.get("position"))
        if k is None:
            diffs.append(f"{r['player_name']}: on GG's board, not on our card")
            continue
        gg_keys.add(k)
        fl = flight_of.get(k)
        worst[fl] = max(worst.get(fl, 0), pos or 0)
        if place_of.get(k) != pos:
            diffs.append(f"{names.get(k, k)}: GG {r.get('position')}, ours "
                         f"{place_of.get(k)} ({fl})")
    for f in ours.get("flights") or []:
        cut = worst.get(f["flight"])
        if cut is None:
            diffs.append(f"our flight {f['flight']} has no GG winner at all")
            continue
        for r in f["rows"]:
            if r["place"] <= cut and r["key"] not in gg_keys:
                diffs.append(f"{r['name']}: ours place {r['place']} in "
                             f"{f['flight']}, not on GG's board")
    ours_list = [{"player": r["name"], "flight": f["flight"],
                  "place": r["place"], "points": r["points"]}
                 for f in ours.get("flights") or [] for r in f["rows"]
                 if r["place"] <= (worst.get(f["flight"]) or 0)]
    return {"status": "mismatch" if diffs else "match", "diffs": diffs,
            "ours": ours_list}


_SKIN_RE = re.compile(r"on\s+(\d+)", re.I)


def _grade_skins(grows, ours: dict, idx, names) -> dict:
    """GG's (player, hole) skins vs ours — the set must be identical."""
    gg_set, diffs = set(), []
    for r in grows:
        k = _resolve(r.get("customer_id"), r.get("player_name"), idx)
        holes = [int(h) for h in _SKIN_RE.findall(r.get("detail") or "")]
        if k is None:
            diffs.append(f"{r['player_name']}: on GG's board, not on our card")
            continue
        if not holes:
            diffs.append(f"{r['player_name']}: GG detail "
                         f"{r.get('detail')!r} names no hole")
        gg_set |= {(k, h) for h in holes}
    our_set = {(sk["key"], sk["hole"])
               for f in (ours or {}).get("flights") or []
               for sk in f["skins"]}
    for k, h in sorted(gg_set - our_set, key=lambda x: x[1]):
        diffs.append(f"hole {h}: GG skin to {names.get(k, k)}, ours not")
    for k, h in sorted(our_set - gg_set, key=lambda x: x[1]):
        diffs.append(f"hole {h}: our skin to {names.get(k, k)}, GG not")
    return {"status": "mismatch" if diffs else "match", "diffs": diffs,
            "variant": (ours or {}).get("gg_name") or (ours or {}).get("label"),
            "selection": ((ours or {}).get("selection") or {}).get("reason"),
            "ours": sorted(f"{names.get(k, k)} #{h}" for k, h in our_set)}


def _grade_mvp(gg_names: list, ours: dict, idx, names) -> dict:
    gg_keys = {_resolve(None, n, idx) for n in gg_names}
    our_keys = {w["key"] for w in (ours or {}).get("winners") or []}
    diffs = []
    if None in gg_keys:
        diffs.append("a GG MVP is not on our card: " + ", ".join(gg_names))
    if gg_keys - {None} != our_keys:
        diffs.append(
            "GG " + ", ".join(sorted(gg_names)) + " / ours "
            + (", ".join(sorted(names.get(k, k) for k in our_keys))
               or "none"))
    return {"status": "mismatch" if diffs else "match", "diffs": diffs,
            "ours": sorted(names.get(k, k) for k in our_keys)}


# Games whose GG row is a MEASURED fact entered by the manager (a tape
# measure, a witness), not something computable from hole scores. Reported
# with GG's row; there is no engine side to grade.
INPUT_NOT_COMPUTED = ("ctp", "longest_putt", "hio")


def _diff_games(gg: dict, event_name: str, db_path, board=None,
                gg_mvp=None) -> dict:
    """GG's recorded winners vs our engine's, per game.

    Graded games (A1): individual_net, individual_gross, skins, mvp —
    zero tolerance, player by player. A3 games (team_net and its board,
    skins_half_net) are reported with our side beside GG's, not graded.
    CTP / longest putt / HIO are manager-entered facts, reported only.
    A graded GG game with no engine equivalent is a BLOCKER, never a pass.
    """
    if gg.get("error"):
        return {"status": "error", "error": gg["error"]}
    rows = gg.get("results") or []
    if not rows and not gg_mvp:
        return {"status": "no_gg_data",
                "note": ("GG has recorded no game results for this event "
                         "yet. Not a pass and not a fail — there is nothing "
                         "to diff. Re-run once the boards are imported.")}
    by_game: dict = {}
    for r in rows:
        by_game.setdefault(r["game"], []).append(r)
    ours_games = (board or {}).get("games") or {}
    idx = _card_index(board or {})
    names = {c["key"]: c["name"] for c in (board or {}).get("cards") or []}
    games = {}
    for game, grows in sorted(by_game.items()):
        entry = {
            "graded": game not in A3_REPORT_ONLY
                      and game not in INPUT_NOT_COMPUTED,
            "a3_report_only": game in A3_REPORT_ONLY,
            "gg_winners": [
                {"player": r["player_name"], "position": r.get("position"),
                 "detail": r.get("detail"), "purse": r.get("purse")}
                for r in grows],
        }
        if board is None:
            entry.update(ours=None, status="pending_engine_side")
        elif game in INPUT_NOT_COMPUTED:
            entry.update(ours=None, status="input_not_computed")
        elif game in ("individual_net", "individual_gross"):
            entry.update(_grade_individual(grows, ours_games.get(game),
                                           idx, names))
        elif game == "skins":
            entry.update(_grade_skins(grows, ours_games.get("skins"),
                                      idx, names))
        elif game in ("team_net", "team_net_board"):
            tn = ours_games.get("team_net") or {}
            entry.update(status="reported", ours=[
                {"team": t["team"], "place": t["place"],
                 "vs_par": t["vs_par"], "members": t["members"]}
                for t in tn.get("teams") or []][:6],
                warnings=tn.get("warnings") or [])
        else:
            entry.update(ours=None, status="no_engine_equivalent")
        games[game] = entry
    # MVP lives in event_mvps, not gg_game_results.
    if board is not None and gg_mvp:
        games["mvp"] = dict(
            graded=True, a3_report_only=False,
            gg_winners=[{"player": n} for n in gg_mvp],
            **_grade_mvp(gg_mvp, ours_games.get("mvp"), idx, names))
    # A graded game our engine paid that GG has no board for is a diff too.
    if board is not None:
        for game in ("individual_net", "individual_gross", "skins"):
            g = ours_games.get(game) or {}
            paid = (any(f.get("skins") for f in g.get("flights") or [])
                    if game == "skins" else g.get("active"))
            if paid and game not in games:
                games[game] = {"graded": True, "a3_report_only": False,
                               "gg_winners": [], "status": "mismatch",
                               "diffs": [f"our engine ran {game}; GG "
                                         f"recorded no board for it"]}
    return {"status": "graded" if board is not None else "collected",
            "games": games,
            "note": ("GG's board is captured verbatim beside ours. Games "
                     "listed a3_report_only are REPORTED, not graded, per "
                     "#571 A3; ctp / longest_putt / hio are manager-entered "
                     "facts with no engine side.")}


def _gg_recorded_mvp(event_name: str, db_path) -> list:
    from . import database as db
    try:
        conn = (db.get_connection(db_path) if db_path
                else db.get_connection())
        try:
            return [r["player_name"] for r in conn.execute(
                "SELECT m.player_name FROM event_mvps m "
                "JOIN events e ON e.id = m.event_id "
                "WHERE lower(e.item_name) = lower(?) AND m.kind = 'mvp'",
                (event_name,)).fetchall()]
        finally:
            conn.close()
    except Exception:
        return []


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


ENGINE_PURSE_GAMES = ("individual_net", "individual_gross", "skins")


def _grade_engine_purses(gg: dict, eng: dict) -> dict:
    """Our ENGINE's payouts (flight board AMOUNTS x engine results, flights
    pinned from the frozen selection) vs GG's posted purses, per player per
    game, to the cent. Unlike the matrix-assembly totals above this is an
    independent computation — nothing on our side is copied from GG — so a
    match here is a real result. A2(ii) applies: a TIED row may land
    $0.01-$0.02 under GG because ours sums to the pot; that is EXPLAINED,
    anything else is a mismatch."""
    if eng.get("error"):
        return {"status": "error", "error": eng["error"]}
    games = {}
    gg_rows = gg.get("results") or []
    for game in ENGINE_PURSE_GAMES:
        ours = (eng.get("games") or {}).get(game)
        theirs = [r for r in gg_rows if r.get("game") == game
                  and (r.get("purse") or 0) > 0]
        if not ours or ours.get("status") in ("not_running",):
            if theirs:
                games[game] = {"status": "mismatch", "diffs": [
                    f"GG paid {game}; our flight board has it not running"]}
            continue
        gg_by, gg_name = {}, {}
        for r in theirs:
            k = r.get("customer_id") or _norm_name(r.get("player_name"))
            gg_by[k] = round(gg_by.get(k, 0.0) + float(r["purse"]), 2)
            gg_name[k] = r.get("player_name")
        our_by, our_name, tied = {}, {}, set()
        for r in ours.get("rows") or []:
            k = r.get("customer_id") or _norm_name(r.get("name"))
            our_by[k] = round(our_by.get(k, 0.0) + float(r["amount"]), 2)
            our_name[k] = r.get("name")
            if "(T)" in (r.get("detail") or ""):
                tied.add(k)
        diffs, explained = [], []
        for k in sorted(set(gg_by) | set(our_by), key=str):
            a, b = our_by.get(k, 0.0), gg_by.get(k, 0.0)
            if abs(a - b) < 0.005:
                continue
            who = our_name.get(k) or gg_name.get(k) or k
            if k in tied and 0 < round(b - a, 2) <= 0.02:
                explained.append(f"{who}: ours ${a:.2f}, GG ${b:.2f} "
                                 f"({RESIDUAL_TIED_PAYOUT_ROUNDING})")
            else:
                diffs.append(f"{who}: ours ${a:.2f}, GG ${b:.2f}")
        games[game] = {
            "status": "mismatch" if diffs else "match",
            "engine_status": ours.get("status"),
            "flight_source": ours.get("flight_source"),
            "variant": ours.get("variant"),
            "ours_total": ours.get("total"), "gg_total": round(sum(gg_by.values()), 2),
            "unallocated": ours.get("unallocated") or [],
            "diffs": diffs, "explained": explained}
    return {"status": "graded", "games": games,
            "board_state": eng.get("board_state"),
            "note": ("Engine payouts: the flight board's AMOUNTS applied to "
                     "our engine's results with the frozen flights pinned. "
                     "Independent of GG, so this grades.")}


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
    g = out["tiers"].get("games") or {}
    bad = sorted(k for k, v in (g.get("games") or {}).items()
                 if v.get("graded") and v.get("status") == "mismatch")
    ep = ((out["tiers"].get("purses") or {}).get("engine") or {}).get("games") or {}
    bad += sorted(f"purse:{k}" for k, v in ep.items()
                  if v.get("status") == "mismatch")
    if bad:
        def _why(k):
            if k.startswith("purse:"):
                return f"{k}: " + " | ".join(ep[k[6:]].get("diffs") or [])
            return f"{k}: " + " | ".join(g["games"][k].get("diffs") or [])
        return {"result": "FAIL",
                "why": "differ from GG: " + "; ".join(_why(k) for k in bad)}
    if out["blockers"]:
        return {"result": "INCOMPLETE",
                "why": "; ".join(out["blockers"]),
                "note": ("The A1 player tier is clean. G2a is still NOT a "
                         "pass, because A4 asks for every game, purse and "
                         "race and at least one of those cannot be graded "
                         "yet. Recording this as a pass would be the hollow "
                         "parity defect the plan exists to prevent.")}
    return {"result": "PASS", "why": "all gradeable tiers clean"}
