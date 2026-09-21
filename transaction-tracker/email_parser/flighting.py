"""Flighting & payout rules — the RATIFIED rule set, as data, in two layers.

Source of every number here: Tracker mailbox #571–#575 (Kerry, Fri 9/18 –
Sat 9/19 2026) as revised by #581/#582 (Mon 9/21). Nothing in this module is
a proposal; where a reading of the rulings was needed it is named as an
ASSUMPTION in the docstring of the function that makes it and reported on
the result, so the board can say so.

Pure — no DB, no Flask — like `live_scoring.py`, `match_play.py` and
`season_payouts.py`, so it unit-tests in isolation (`test_flighting.py`) and
ports to the Platform unchanged.

THE TWO LAYERS (B5, #571/#572; "the matrix must read as two layers", #582):

  SELECTION  — which games run (incl. every matrix game-selection
               threshold: Cart vs Team Net, gross Skins vs ½ Net, Ind Gross
               activation), the flight count, the band edges, each player's
               flight. FROZEN at the freeze action.
  AMOUNTS    — pots, places and dollars. RECOMPUTED at settlement from the
               ACTUAL buyers (wd_credits decides who is a buyer, upstream).

`build()` produces both from one field (a LIVE board). `settle()` takes a
frozen board and the field as it stands now, keeps the SELECTION, recomputes
the AMOUNTS, and reports the delta — who added, who dropped, pot then vs now,
places then vs now — so a published-vs-paid question answers itself.

THE RULES (verbatim intent, #582):
  POT (Individual Gross): 10% of the total gross pot off the top = OVERALL
      LOW GROSS bonus, whole field. Remaining 90% split by headcount:
      share = 0.9 × rate ($7.20 on an 18, $3.60 on a nine). Flight pot =
      share × flight headcount. A solo flight's player receives his share; if
      he is also overall low gross he receives share + bonus.
  NO MINIMUM FLIGHT SIZE. NO MERGING, ever (B2 superseded). Flights are what
      the ladder produces.
  LADDERS: 3-flight <6.0 / 6.0–11.9 / 12.0+; 4-flight adds 12.0–17.9 / 18.0+.
      Cut lines never move. (Exclusive upper bounds — 12.0 goes UP — the
      representation `live_scoring.SEED_FLIGHT_CONFIG` already uses.)
  PLACES by FLIGHT size, same for 9 and 18: 1–9 → 1 place; 10–19 → 2 places
      (2/3, 1/3); 20+ → 3 places (50/30/20). Ties: combine the tied places'
      money and split evenly; sums to the pot.
  LABELS (P2-6): a flight's label is derived from its ACTUAL membership.
  SKINS IS UNAFFECTED (#572): separate buy-in, flight split at 12.0, ½ Net
      under 8 buyers on a nine; its pot stays the matrix rule (skins pot ÷
      flights, paid per skin).
  INDIVIDUAL NET: the SAME fixed ladder as Skins (<12.0 / 12.0+ for two
      flights) — Kerry 2026-09-21: "Flights for Individual Net is supposed
      to be same as Skins at <12.0 and 12.0+, not 12.4" (supersedes the
      #571 equal-size reading; equal_size remains a dial on FLIGHT_RULES);
      AMOUNTS from the live matrix columns.

Nothing here pays anyone. Golf Genius stays the payer of record until Kerry
flips it per event.
"""
from __future__ import annotations

import copy
from typing import Callable

# ---------------------------------------------------------------------------
# The rules, as data (Guiding Principle 2)
# ---------------------------------------------------------------------------

FLIGHT_RULES: dict = {
    "version": 1,
    "source": ("mailbox #571-#575 (Kerry 2026-09-18/19) as revised by "
               "#581/#582 (2026-09-21)"),
    # Flight on the raw 18-hole TGF index (= 2 x the nine-hole index),
    # RULED 2026-07-30 (#253) and unchanged.
    "index_scale": "18",
    # Exclusive upper bounds per flight count. 12.0 goes UP; 11.9 tops the
    # flight below. "Cut lines never move" — the 3- and 4-flight ladders
    # share 6.0 and 12.0 by construction.
    "ladders": {
        "1": [],
        "2": [12.0],
        "3": [6.0, 12.0],
        "4": [6.0, 12.0, 18.0],
    },
    # #572: "THERE IS NO MINIMUM FLIGHT SIZE. No merging, ever."
    "min_flight_size": 0,
    "merge": False,
    # #573: places paid by FLIGHT size, not field size; same on 9 and 18.
    "places_by_flight_size": [
        {"min": 1, "max": 9, "split": [1.0]},
        {"min": 10, "max": 19, "split": [2 / 3, 1 / 3]},
        {"min": 20, "max": None, "split": [0.50, 0.30, 0.20]},
    ],
    # #572 B4 revised: the 10% is an OVERALL LOW GROSS bonus, whole field.
    "gross": {
        "bonus_pct": 0.10,
        "bonus_label": "Overall Low Gross",
        # The Individual Gross share of the GROSS bundle (side-games.md
        # buy-in pricing: 9h $16 = Skins $9 + Ind Gross $4 + markup $3;
        # 18h $30 = Skins $18 + Ind Gross $8 + markup $4).
        "rate": {"9": 4.0, "18": 8.0},
    },
    "net": {
        # KERRY 2026-09-21 (Brackenridge board printed "Flight 1 (HCP
        # <12.4)"): "Flights for Individual Net is supposed to be same as
        # Skins at <12.0 and 12.0+, not 12.4." Individual Net cuts on the
        # SAME fixed ladder as Skins; equal_size stays available as a dial.
        "mode": "fixed_bands",
        "low_flight_ceiling": 12.0,      # exclusive: 12.0 is pushed up (equal_size mode only)
        "amounts": "matrix",
    },
    "skins": {"amounts": "matrix_equal_per_flight"},
    "ties": "combine the tied places' money and split evenly; sums to the pot",
}

# The games this board covers, in the order the sheet prints them.
BOARD_GAMES = (
    # (game key, label, buyer kind)
    ("individual_net", "Individual Net", "NET"),
    ("skins", "Skins", "GROSS"),
    ("individual_gross", "Individual Gross", "GROSS"),
)

# How the live matrix names a NET flight's place columns, by flight order
# (flight 1 = the LOW flight). This is the convention the recorded-payouts
# path already uses (`assemble_event_game_payouts`); it is data here so the
# board and the payouts cannot drift apart.
NET_MATRIX_FLIGHT_PREFIXES = ("netLow", "netHigh", "netMid", "net4th")
NET_MATRIX_PLACE_SUFFIXES = ("1st", "2nd", "3rd", "4th")


# ---------------------------------------------------------------------------
# Small exact-money helpers — MONEY OUT = MONEY IN (side-games.md)
# ---------------------------------------------------------------------------

def _cents(x: float) -> int:
    return int(round(float(x) * 100))


def split_exact(total: float, weights: list[float]) -> list[float]:
    """Split `total` by `weights` into cents that SUM EXACTLY to the total
    (largest-remainder). The last cent never drifts."""
    if not weights:
        return []
    tc = _cents(total)
    wsum = float(sum(weights)) or 1.0
    raw = [tc * float(w) / wsum for w in weights]
    floors = [int(r) for r in raw]
    short = tc - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - floors[i]), i))
    for i in order[:max(0, short)]:
        floors[i] += 1
    return [c / 100.0 for c in floors]


def tie_split(place_amounts: list[float], first_place: int, n_tied: int) -> list[float]:
    """The ratified tie rule: the `n_tied` players sharing `first_place`
    combine the money of places first_place .. first_place+n_tied-1 and split
    it evenly, exact cents, summing to what those places carried. A tie that
    runs past the paid places simply pools what is paid."""
    lo = max(0, first_place - 1)
    pool = sum(place_amounts[lo:lo + n_tied])
    return split_exact(pool, [1.0] * n_tied)


# ---------------------------------------------------------------------------
# Ladder cuts and labels
# ---------------------------------------------------------------------------

def _idx(p: dict) -> float:
    v = p.get("index")
    return 99.0 if v is None else float(v)


def index_text(idx) -> str:
    """Golf's own notation: a plus handicap prints +1.4 for -1.4."""
    if idx is None:
        return "—"
    return f"+{abs(idx):.1f}" if idx < 0 else f"{idx:.1f}"


def band_text(i: int, edges: list[float]) -> str:
    """The RULE a band states: '<6.0', '6.0–11.9', '12.0+'. Edges are
    exclusive upper bounds, so the printed top of a middle band is the
    edge less one tenth — the boundary Kerry ratified (12.0 goes UP)."""
    if not edges:
        return "All handicaps"
    if i == 0:
        return f"<{edges[0]:.1f}"
    if i >= len(edges):
        return f"{edges[-1]:.1f}+"
    return f"{edges[i - 1]:.1f}–{edges[i] - 0.1:.1f}"


def derived_label(members: list[dict]) -> str:
    """P2-6: the label is the flight's ACTUAL membership ('8.1–14.3'),
    never a typed band. A solo flight prints its one index; an empty band
    prints nothing rather than a range it does not hold."""
    if not members:
        return "—"
    lo, hi = _idx(members[0]), _idx(members[-1])
    if lo == hi:
        return index_text(lo)
    return f"{index_text(lo)}–{index_text(hi)}"


def cut_by_edges(players: list[dict], edges: list[float]) -> list[list[dict]]:
    """Place every indexed player into the band whose exclusive upper bound
    is the first one above his index. Every band is returned, EMPTY OR NOT
    — a band with nobody in it is still a numbered flight on the board (no
    merging, ever), and a late add after the freeze may land in it."""
    bands: list[list[dict]] = [[] for _ in range(len(edges) + 1)]
    for p in sorted(players, key=lambda p: (_idx(p), p.get("name") or "")):
        slot = len(edges)
        for i, hi in enumerate(edges):
            if _idx(p) < hi:
                slot = i
                break
        bands[slot].append(p)
    return bands


def ladder_for(count: int, rules: dict | None = None) -> list[float]:
    """The ratified ladder for a flight count. A count with no ladder on
    file (5+) is a gap in the rules, not a rule — reported by the caller."""
    r = rules or FLIGHT_RULES
    return list((r.get("ladders") or {}).get(str(int(count))) or []) if count > 1 else []


def places_for(flight_size: int, rules: dict | None = None) -> list[float]:
    """#573: 1–9 → [1.0]; 10–19 → [2/3, 1/3]; 20+ → [.5, .3, .2]. Zero
    players → no places (nothing to pay)."""
    r = rules or FLIGHT_RULES
    n = int(flight_size or 0)
    if n <= 0:
        return []
    for row in r.get("places_by_flight_size") or []:
        lo, hi = row.get("min", 1), row.get("max")
        if n >= lo and (hi is None or n <= hi):
            return list(row["split"])
    return [1.0]


# ---------------------------------------------------------------------------
# AMOUNTS per game
# ---------------------------------------------------------------------------

def gross_amounts(holes_key: str, flight_sizes: list[int],
                  rules: dict | None = None) -> dict:
    """The B4-revised Individual Gross pot (#572) with #573 places.

    total = rate × buyers; bonus = 10% of total (Overall Low Gross, whole
    field); share = 0.9 × rate; flight pot = share × headcount; places by
    flight size; every flight's places sum exactly to its pot and the
    flights plus the bonus sum exactly to the total. Worked (#572, field A,
    14 buyers on an 18): bonus $11.20, share $7.20, F1(2) $14.40, F2(6)
    $43.20, F3(6) $43.20 → $100.80 + $11.20 = $112."""
    r = rules or FLIGHT_RULES
    g = r["gross"]
    rate = float(g["rate"][str(holes_key)])
    n = int(sum(int(s) for s in flight_sizes))
    total = round(rate * n, 2)
    bonus = round(total * float(g["bonus_pct"]), 2)
    share = round(rate * (1.0 - float(g["bonus_pct"])), 2)
    flights = []
    for i, size in enumerate(flight_sizes):
        size = int(size)
        pot = round(share * size, 2)
        split = places_for(size, r)
        amts = split_exact(pot, split) if split else []
        flights.append({
            "flight_no": i + 1, "players": size, "pot": pot,
            "places": [{"place": k + 1, "pct": round(split[k], 6), "amount": amts[k]}
                       for k in range(len(split))],
        })
    paid = round(sum(f["pot"] for f in flights) + bonus, 2)
    return {
        "rule": "B4-revised (#572) + places (#573)",
        "rate": rate, "buyers": n, "total_pot": total,
        "bonus": bonus, "bonus_label": g["bonus_label"],
        "bonus_pct": float(g["bonus_pct"]), "share": share,
        "flights": flights,
        "sum_check": abs(paid - total) < 0.005,
    }


def _num(v) -> float:
    if v in (None, "", "NO_GAME", "NO_EVENT"):
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def net_amounts(matrix_row: dict | None, flight_sizes: list[int],
                is18: bool) -> dict:
    """Individual Net AMOUNTS: the live matrix row for the CURRENT buyer
    count, its place columns read per flight in the recorded-payouts
    convention (Low, High, Mid, 4th). The matrix already encodes the
    2/3–1/3 and 3rd/4th-place ladders per count; this board does not
    re-derive them (#571: net flights are equal-size cuts and unaffected).
    A flight with nobody in it carries its column money as $0 paid — the
    matrix does not know the field is thin, and this says so."""
    row = matrix_row or {}
    pot = round(_num(row.get("individualNet")), 2)
    flights = []
    n_pl = 4 if is18 else 3
    for i, size in enumerate(flight_sizes):
        prefix = (NET_MATRIX_FLIGHT_PREFIXES[i]
                  if i < len(NET_MATRIX_FLIGHT_PREFIXES) else None)
        places = []
        if prefix:
            for k in range(n_pl):
                amt = round(_num(row.get(f"{prefix}{NET_MATRIX_PLACE_SUFFIXES[k]}")), 2)
                if amt > 0:
                    places.append({"place": k + 1, "pct": None, "amount": amt})
        fpot = round(sum(p["amount"] for p in places), 2)
        flights.append({"flight_no": i + 1, "players": int(size),
                        "pot": fpot, "places": places,
                        "matrix_column": prefix})
    return {"rule": "live matrix (netLow/netHigh…) at the current buyer count",
            "buyers": int(sum(int(s) for s in flight_sizes)),
            "total_pot": pot, "flights": flights,
            "sum_check": abs(round(sum(f["pot"] for f in flights), 2) - pot) < 0.005
            if flights else True}


def skins_amounts(matrix_row: dict | None, flight_sizes: list[int]) -> dict:
    """Skins AMOUNTS: the matrix skins pot at the current buyer count,
    split EQUALLY per flight (the existing ratified rule — flight pot =
    pot ÷ flights), paid per skin at settlement. Skins is unaffected by
    B4 (#572)."""
    row = matrix_row or {}
    pot = round(_num(row.get("skinsTotal")), 2)
    k = len(flight_sizes) or 1
    per = split_exact(pot, [1.0] * k) if pot > 0 else [0.0] * k
    flights = [{"flight_no": i + 1, "players": int(size), "pot": per[i],
                "places": [], "paid": "per skin won, at settlement"}
               for i, size in enumerate(flight_sizes)]
    return {"rule": "live matrix skinsTotal ÷ flights (equal per flight); per skin",
            "buyers": int(sum(int(s) for s in flight_sizes)),
            "total_pot": pot, "flights": flights, "sum_check": True}


# ---------------------------------------------------------------------------
# SELECTION per game
# ---------------------------------------------------------------------------

def _select_variant(game_cfg: dict, holes_key: str, buyers: int) -> dict:
    """Reported variant selection (the a9.23 layer). Imported lazily so this
    module stays importable with no other module present."""
    try:
        from .live_scoring import select_variant
    except ImportError:                                   # pragma: no cover
        from live_scoring import select_variant           # type: ignore
    return select_variant(game_cfg, holes_key, buyers)


def _bands_lookup(bands, n: int, default=None):
    for lo, hi, val in (bands or []):
        if n >= lo and (hi is None or n <= hi):
            return val
    return default


def _flight_count(game: str, matrix_row: dict | None, game_cfg: dict,
                  holes_key: str, n: int) -> tuple[int, str]:
    """The flight COUNT: the LIVE matrix column first (it is the governing
    layer), the seed game config's bands as the fallback for a count the
    matrix does not carry."""
    col = {"individual_net": "netFlights", "skins": "skinsFlights",
           "individual_gross": "grossFlights"}.get(game)
    row = matrix_row or {}
    if col and _num(row.get(col)) > 0:
        return int(_num(row.get(col))), f"live matrix {col} at {n} buyers"
    bands = (game_cfg.get("flight_bands") or {}).get(str(holes_key))
    return int(_bands_lookup(bands, n, 1) or 1), "seed game config flight_bands"


def _net_plan(field: list[dict], count: int, rules: dict) -> tuple[list[list[dict]], list[float], list[str]]:
    """Individual Net: equal-size cuts, tie-safe, low flight under the
    ceiling — `live_scoring.flight_plan` with NO merging. Returns the
    groups, the edges the cut implies (each flight's exclusive upper bound
    = the next flight's lowest index, for placing a late add after the
    freeze), and the plan's own notes."""
    try:
        from .live_scoring import flight_plan, SEED_FLIGHT_CONFIG
    except ImportError:                                   # pragma: no cover
        from live_scoring import flight_plan, SEED_FLIGHT_CONFIG  # type: ignore
    cfg = copy.deepcopy(SEED_FLIGHT_CONFIG)
    cfg["min_flight_size"] = 0                       # #572: no merging
    cfg["low_flight_ceiling"] = {"individual_net": rules["net"]["low_flight_ceiling"]}
    # flight_plan keys its players and hands back only key/name/index, so
    # the original dicts (customer_id, ph) are restored by key afterwards.
    by_key = {}
    keyed = []
    for i, p in enumerate(field):
        k = str(p.get("customer_id") if p.get("customer_id") is not None else f"n{i}")
        by_key[k] = p
        keyed.append({"key": k, "name": p.get("name"), "index": p.get("index")})
    plan = flight_plan(keyed, count, game="individual_net", config=cfg,
                       mode=rules["net"]["mode"])
    groups = [[dict(by_key[m["key"]]) for m in f["members"]] for f in plan["flights"]]
    while len(groups) < count:
        groups.append([])
    edges = [float(g[0]["index"]) for g in groups[1:] if g]
    return groups, edges, list(plan.get("notes") or [])


def select_game(game: str, label: str, kind: str, field: list[dict],
                holes_key: str, matrix_row: dict | None, game_cfg: dict,
                rules: dict | None = None) -> dict:
    """The SELECTION layer for one game from the field as it stands.

    `field` is that game's buyers: [{customer_id, name, index, ph?}]. The
    index is the raw 18-hole TGF index of record (locked as-of for a
    started event, upstream)."""
    r = rules or FLIGHT_RULES
    n = len(field)
    sel: dict = {
        "game": game, "label": label, "kind": kind,
        "buyers_at_selection": n, "active": True, "inactive_reason": None,
        "variant": None, "flight_count": 0, "count_source": None,
        "mode": None, "edges": [], "edges_source": None,
        "flights": [], "unflighted": [], "notes": [],
    }
    if n == 0:
        sel["active"] = False
        sel["inactive_reason"] = f"Nobody bought into {kind} games."
        return sel
    # Activation: the LIVE matrix says whether the game runs at this count
    # (Ind Gross has a column that reads NO_GAME below its threshold); the
    # seed config's min_buyers is the fallback when the matrix is silent.
    row = matrix_row or {}
    if game == "individual_gross":
        min_buyers = (game_cfg.get("min_buyers") or {}).get(str(holes_key))
        runs = (_num(row.get("individualGross")) > 0) if row else (
            min_buyers is None or n >= min_buyers)
        if not runs:
            sel["active"] = False
            sel["inactive_reason"] = (
                f"{label} activates at {min_buyers} buyers on "
                f"{'an 18' if str(holes_key) == '18' else 'a 9'}-hole event; "
                f"{n} bought in.")
            return sel
    sel["variant"] = _select_variant(game_cfg, str(holes_key), n)
    count, src = _flight_count(game, matrix_row, game_cfg, holes_key, n)
    sel["flight_count"], sel["count_source"] = count, src
    known = [p for p in field if p.get("index") is not None]
    unknown = [p for p in field if p.get("index") is None]
    if unknown:
        sel["notes"].append(
            f"{len(unknown)} player(s) have no handicap index and cannot be "
            f"flighted: {', '.join(sorted(p.get('name') or '' for p in unknown))}.")
    if game == "individual_net" and r["net"]["mode"] == "equal_size":
        sel["mode"] = r["net"]["mode"]
        groups, edges, notes = _net_plan(known, count, r)
        sel["edges"], sel["edges_source"] = edges, "equal-size cut (next flight's lowest index)"
        sel["notes"].extend(notes)
    else:
        sel["mode"] = "fixed_bands"
        edges = ladder_for(count, r)
        if count > 1 and not edges:
            sel["notes"].append(
                f"No ratified ladder for {count} flights — the board cut "
                f"as ONE flight and says so. This is a gap in the rules.")
            count = 1
            sel["flight_count"] = 1
        sel["edges"], sel["edges_source"] = edges, "ratified ladder (cut lines never move)"
        groups = cut_by_edges(known, edges)
    for i, g in enumerate(groups):
        g = sorted(g, key=lambda p: (_idx(p), p.get("name") or ""))
        sel["flights"].append({
            "flight_no": i + 1,
            "band": band_text(i, sel["edges"]) if sel["mode"] == "fixed_bands"
                    else (band_text(i, sel["edges"]) if sel["edges"] else "All handicaps"),
            "label": derived_label(g),
            "players": len(g),
            "members": [_member(p) for p in g],
        })
    sel["unflighted"] = [_member(p) for p in sorted(unknown, key=lambda p: p.get("name") or "")]
    return sel


def _member(p: dict) -> dict:
    return {"customer_id": p.get("customer_id"), "name": p.get("name"),
            "index": p.get("index"), "index_text": index_text(p.get("index")),
            "ph": p.get("ph")}


# ---------------------------------------------------------------------------
# AMOUNTS from a SELECTION + the buyers now
# ---------------------------------------------------------------------------

def amounts_for(sel: dict, holes_key: str, matrix_row_now: dict | None,
                rules: dict | None = None) -> dict | None:
    """The AMOUNTS layer for one game, from its (possibly frozen) SELECTION
    and the matrix row at the CURRENT buyer count. Headcounts are read off
    the selection's flights, which `settle()` has already re-populated."""
    r = rules or FLIGHT_RULES
    if not sel.get("active"):
        return None
    sizes = [f["players"] for f in sel["flights"]]
    game = sel["game"]
    if game == "individual_gross":
        return gross_amounts(str(holes_key), sizes, r)
    if game == "individual_net":
        return net_amounts(matrix_row_now, sizes, str(holes_key) == "18")
    if game == "skins":
        return skins_amounts(matrix_row_now, sizes)
    return None


# ---------------------------------------------------------------------------
# The board: build (LIVE) and settle (FROZEN → SETTLED)
# ---------------------------------------------------------------------------

def _games_cfg():
    try:
        from .live_scoring import SEED_LIVE_SCORING_CONFIG
    except ImportError:                                   # pragma: no cover
        from live_scoring import SEED_LIVE_SCORING_CONFIG  # type: ignore
    return SEED_LIVE_SCORING_CONFIG["games"]


def build(field_by_kind: dict, holes_key: str,
          matrix_row_for: Callable[[int], dict | None],
          games_cfg: dict | None = None, rules: dict | None = None) -> dict:
    """A LIVE board: SELECTION and AMOUNTS from the same field.

    field_by_kind: {"NET": [players], "GROSS": [players]} — the bundle
    buyers per kind, each {customer_id, name, index, ph?}.
    matrix_row_for(n): the LIVE matrix row for n buyers on this hole count.
    """
    r = rules or FLIGHT_RULES
    cfg = games_cfg or _games_cfg()
    games = []
    for game, label, kind in BOARD_GAMES:
        field = list(field_by_kind.get(kind) or [])
        row = matrix_row_for(len(field)) if field else None
        sel = select_game(game, label, kind, field, holes_key, row,
                          cfg.get(game) or {}, r)
        games.append({"game": game, "label": label, "kind": kind,
                      "active": sel["active"],
                      "inactive_reason": sel["inactive_reason"],
                      "selection": sel,
                      "amounts": amounts_for(sel, holes_key, row, r),
                      "delta": None})
    return {"state": "live", "rules_version": r["version"],
            "rules_source": r["source"], "holes_key": str(holes_key),
            "index_scale": r["index_scale"], "games": games}


def _place_by_edges(p: dict, edges: list[float]) -> int:
    for i, hi in enumerate(edges):
        if _idx(p) < hi:
            return i
    return len(edges)


def settle(frozen: dict, field_by_kind: dict,
           matrix_row_for: Callable[[int], dict | None],
           rules: dict | None = None, state: str = "settled") -> dict:
    """FROZEN → SETTLED (or a FROZEN board re-read against the field now).

    Keeps every SELECTION fact (games, variant, flight count, edges, each
    frozen player's flight); places a buyer who was not there at the freeze
    by the FROZEN edges (his flight is decided by the same cut lines); drops
    a frozen member who is no longer a buyer (credited WD) from the
    headcount; recomputes the AMOUNTS from the headcounts now; and reports
    the DELTA per game and per flight. Structure never changes here (#572:
    "settlement recomputes amounts only — never structure")."""
    r = rules or FLIGHT_RULES
    out = copy.deepcopy(frozen)
    out["state"] = state
    for entry in out["games"]:
        sel = entry["selection"]
        kind = entry["kind"]
        now = {int(p["customer_id"]): p for p in (field_by_kind.get(kind) or [])
               if p.get("customer_id") is not None}
        before_flights = copy.deepcopy(sel["flights"])
        before_amounts = copy.deepcopy(entry.get("amounts"))
        added, dropped = [], []
        if not sel.get("active"):
            # A game that was NOT running at the freeze does not start
            # running at settlement (its activation threshold froze too);
            # a game that WAS running keeps running even if buyers fall.
            entry["delta"] = {"added": [], "dropped": [],
                              "buyers_before": sel["buyers_at_selection"],
                              "buyers_after": len(now), "flights": [],
                              "note": "game selection frozen: not running"}
            continue
        frozen_ids: set = set()
        for f in sel["flights"]:
            kept = []
            for m in f["members"]:
                cid = m.get("customer_id")
                if cid is not None and int(cid) in now:
                    frozen_ids.add(int(cid))
                    p = now[int(cid)]
                    kept.append({**m, "ph": p.get("ph", m.get("ph"))})
                else:
                    dropped.append({**m, "flight_no": f["flight_no"]})
            f["members"] = kept
        for u in sel.get("unflighted") or []:
            if u.get("customer_id") is not None:
                frozen_ids.add(int(u["customer_id"]))
        for cid, p in now.items():
            if cid in frozen_ids:
                continue
            if p.get("index") is None:
                sel["unflighted"].append(_member(p))
                added.append({**_member(p), "flight_no": None})
                continue
            slot = _place_by_edges(p, sel.get("edges") or [])
            slot = min(slot, len(sel["flights"]) - 1) if sel["flights"] else 0
            m = _member(p)
            sel["flights"][slot]["members"].append(m)
            added.append({**m, "flight_no": sel["flights"][slot]["flight_no"]})
        for f in sel["flights"]:
            f["members"].sort(key=lambda m: (_idx(m), m.get("name") or ""))
            f["players"] = len(f["members"])
            f["label"] = derived_label(f["members"])
        row_now = matrix_row_for(len(now)) if now else None
        entry["amounts"] = amounts_for(sel, out["holes_key"], row_now, r)
        entry["delta"] = _delta(before_flights, sel["flights"],
                                before_amounts, entry["amounts"],
                                added, dropped, sel["buyers_at_selection"], len(now))
    return out


def _delta(before_fl, after_fl, before_am, after_am, added, dropped,
           buyers_before, buyers_after) -> dict:
    bf = {f["flight_no"]: f for f in (before_fl or [])}
    ba = {f["flight_no"]: f for f in ((before_am or {}).get("flights") or [])}
    aa = {f["flight_no"]: f for f in ((after_am or {}).get("flights") or [])}
    flights = []
    for f in after_fl:
        no = f["flight_no"]
        pb, pa = ba.get(no) or {}, aa.get(no) or {}
        flights.append({
            "flight_no": no,
            "players_before": (bf.get(no) or {}).get("players", 0),
            "players_after": f["players"],
            "pot_before": pb.get("pot", 0.0), "pot_after": pa.get("pot", 0.0),
            "places_before": [p["amount"] for p in pb.get("places") or []],
            "places_after": [p["amount"] for p in pa.get("places") or []],
            "changed": ((bf.get(no) or {}).get("players", 0) != f["players"]
                        or abs(pb.get("pot", 0.0) - pa.get("pot", 0.0)) >= 0.005),
        })
    return {
        "added": added, "dropped": dropped,
        "buyers_before": buyers_before, "buyers_after": buyers_after,
        "total_pot_before": (before_am or {}).get("total_pot", 0.0),
        "total_pot_after": (after_am or {}).get("total_pot", 0.0),
        "bonus_before": (before_am or {}).get("bonus"),
        "bonus_after": (after_am or {}).get("bonus"),
        "flights": flights,
        "changed": bool(added or dropped or any(f["changed"] for f in flights)),
    }
