"""GO 6 — capture Golf Genius's points ledger while GG still exists.

CA (#786, GO 6): "capture a complete GG per-player, per-event points ledger
NOW, while GG exists: every race, every enrolled player, every event date,
via effective_date. Store it as a read-only JSON BUNDLE in the repo or data
folder, not a DB table. Include Monthly." #790 adds: "The GG capture must
record, for each race, its exact event list."

WHY IT HAS TO BE NOW. We hold no GG standings history: `gg_points_standings`
is delete-then-insert per race and `gg_data_snapshots` keeps one row per key.
GG's per-player breakdown is the only per-event truth, and it goes away with
GG. The points-engine backtest (#770, go/no-go Fri 10/9) diffs against this
bundle at zero tolerance, so the bundle is the answer key.

READ-ONLY. No SQL, no writes, no GG mutation. It runs on the deployed app
(this sandbox's egress proxy blocks golfgenius.com) through the bridge
`scoring-points-ledger*`, and returns JSON that the caller assembles into the
bundle file. Resumable: each call does as many players as fit its time budget
and returns `next` until it is None.

FIDELITY OVER TIDINESS. Each player's breakdown is kept as GG's RAW parsed
tables — nothing is dropped or re-interpreted at capture. A normalised
per-round view is ALSO returned where the table shape is recognisable, but it
is derived, and the raw tables stay the record.
"""

from __future__ import annotations

import re
import time

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}


def list_ledger_races(year: int | None = None) -> list[dict]:
    """Every race to capture: the named season races plus every Monthly page.

    Named races come from `_GG_POINTS_RACES` (the same registry the live
    boards read). Monthly pages are discovered from each chapter portal's
    "<Month> Points" links — the same discovery `get_monthly_points` uses.
    Each entry carries a `ref` that `capture_race_ledger` accepts.
    """
    from .database import _GG_POINTS_RACES
    from golf_genius_sync import fetch_public_page, parse_page_structure
    from .timezone_utils import today_central
    yr = year or today_central().year

    out = []
    for key, cfg in _GG_POINTS_RACES.items():
        out.append({"ref": key, "kind": "season", "race_key": key,
                    "label": cfg.get("label"), "host": cfg["host"],
                    "league_id": cfg["league_id"], "page_id": cfg["page_id"],
                    "chapter": cfg.get("chapter"),
                    "enroll_season": cfg.get("enroll_season")})

    seen_hosts = {}
    for cfg in _GG_POINTS_RACES.values():
        seen_hosts.setdefault(cfg["host"], (cfg["league_id"], cfg.get("chapter")))
    for host, (league, chapter) in sorted(seen_hosts.items()):
        try:
            page = fetch_public_page(f"https://{host}/")
            struct = parse_page_structure(page["html"],
                                          page.get("final_url") or f"https://{host}/")
        except Exception as exc:
            out.append({"ref": None, "kind": "monthly_discovery_error",
                        "host": host, "error": repr(exc)})
            continue
        for link in struct.get("links") or []:
            m = re.match(r"^([A-Za-z]+)\s+Points$", (link.get("text") or "").strip())
            if not m or m.group(1).lower() not in _MONTHS:
                continue
            pid = re.search(r"/pages/(\d+)", link.get("href") or "")
            if not pid:
                continue
            month = f"{yr}-{_MONTHS[m.group(1).lower()]:02d}"
            out.append({"ref": f"page:{host}:{league}:{pid.group(1)}",
                        "kind": "monthly", "month": month,
                        "label": f"{chapter} {m.group(1)} Points",
                        "host": host, "league_id": league,
                        "page_id": pid.group(1), "chapter": chapter})
    return out


def _resolve(ref: str) -> dict:
    from .database import _GG_POINTS_RACES
    if ref in _GG_POINTS_RACES:
        cfg = _GG_POINTS_RACES[ref]
        return {"ref": ref, "host": cfg["host"], "league_id": cfg["league_id"],
                "page_id": cfg["page_id"], "label": cfg.get("label")}
    m = re.fullmatch(r"page:([a-z0-9.-]+\.golfgenius\.com):(\d+):(\d+)", ref)
    if not m:
        raise ValueError(f"unknown race ref {ref!r}")
    return {"ref": ref, "host": m.group(1), "league_id": m.group(2),
            "page_id": m.group(3), "label": None}


def _normalise_rounds(tables: list) -> list[dict]:
    """Best-effort per-round view of a GG breakdown. DERIVED — the raw
    tables remain the record. Recognises a header row containing a points
    column; every other column is kept under its header text."""
    rounds = []
    for t in tables or []:
        if not t or len(t) < 2:
            continue
        header = [str(c).strip() for c in t[0]]
        low = [h.lower() for h in header]
        if not any("point" in h for h in low):
            continue
        for r in t[1:]:
            row = {header[i] if i < len(header) else f"col{i}": str(c).strip()
                   for i, c in enumerate(r)}
            if any(v for v in row.values()):
                rounds.append(row)
    return rounds


def capture_race_ledger(ref: str, start: int = 0,
                        effective_date: str | None = None,
                        time_budget: float = 35.0) -> dict:
    """One chunk of one race's ledger. Call again with `start=next` until
    `next` is None. The standings table is returned on every chunk (cheap,
    and lets the assembler check the population did not move mid-capture).
    """
    from golf_genius_sync import (fetch_season_points_race,
                                  fetch_points_race_member_detail)
    from .timezone_utils import today_central
    spec = _resolve(ref)
    eff = effective_date or today_central().isoformat()
    t0 = time.monotonic()

    standings = fetch_season_points_race(spec["page_id"], spec["league_id"],
                                         spec["host"])
    players, i = [], start
    while i < len(standings):
        # Check the budget only AFTER at least one player: a chunk that does
        # nothing returns the same `next` and the caller loops forever (the
        # stubbed test hung exactly that way with budget 0 — and on the live
        # app a slow standings fetch alone could spend the budget).
        if players and time.monotonic() - t0 > time_budget:
            break
        row = standings[i]
        card = row.get("member_card_id")
        entry = {"index": i, "player_name": row.get("player_name"),
                 "member_card_id": card, "rank": row.get("rank"),
                 "total_points": row.get("total_points"),
                 "tournaments": row.get("tournaments")}
        if not card:
            entry["error"] = "no member_card_id on the standings row"
        else:
            try:
                d = fetch_points_race_member_detail(
                    spec["page_id"], card, league_id=spec["league_id"],
                    host=spec["host"], effective_date=eff)
                entry["raw_tables"] = d.get("tables")
                entry["headings"] = d.get("headings")
                entry["rounds"] = _normalise_rounds(d.get("tables"))
            except Exception as exc:
                entry["error"] = repr(exc)
        players.append(entry)
        i += 1

    return {"ref": ref, "spec": spec, "effective_date": eff,
            "captured_at": today_central().isoformat(),
            "standings": standings, "players": players,
            "start": start, "next": (i if i < len(standings) else None),
            "total_players": len(standings)}


def race_event_list(players: list[dict]) -> list[str]:
    """#790: a race's EXACT event list as GG counts it — the union of every
    round label in every player's breakdown. Caveat recorded with it: an
    event in which no captured player earned a row cannot appear."""
    events = set()
    for p in players:
        for r in p.get("rounds") or []:
            label = (r.get("Tournament") or r.get("Event") or r.get("Round")
                     or r.get("Date") or "")
            if label:
                events.add(label)
    return sorted(events)


# ── Persisted bundle on the data volume (CA #786: "repo or data folder") ──
# Pulling a race's full ledger back through a chat context is the wrong shape
# for several megabytes of tables, and the points-engine backtest runs on the
# deployed app anyway (it needs our scored rounds). So each captured chunk is
# MERGED into a JSON file beside the database, on the persistent volume, and
# the bridge returns only a short status. `read_bundle` pulls a file back out
# when someone wants a copy in the repo.

def _bundle_dir(effective_date: str, root=None):
    from pathlib import Path
    from .database import DB_PATH
    base = Path(root) if root else Path(DB_PATH).parent
    return base / "gg_points_ledger" / effective_date


def _safe(ref: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", ref)


def persist_chunk(chunk: dict, root=None) -> dict:
    """Merge one capture chunk into its race file; return a compact status.
    Players merge by index and a LATER chunk wins, so re-running a slice
    (e.g. after a transient GG 500) repairs it in place."""
    import json
    import os
    d = _bundle_dir(chunk["effective_date"], root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_safe(chunk['ref'])}.json"
    doc = {"ref": chunk["ref"], "spec": chunk["spec"],
           "effective_date": chunk["effective_date"], "players": {}}
    if path.exists():
        doc = json.loads(path.read_text())
        doc["players"] = {int(k): v for k, v in doc.get("players", {}).items()}
    doc["standings"] = chunk["standings"]
    doc["total_players"] = chunk["total_players"]
    doc["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    for p in chunk["players"]:
        doc["players"][int(p["index"])] = p
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({**doc, "players": {str(k): v for k, v
                                                  in sorted(doc["players"].items())}}))
    os.replace(tmp, path)
    return bundle_status_one(doc, str(path))


def bundle_status_one(doc: dict, path: str) -> dict:
    players = doc["players"]
    total = doc.get("total_players", 0)
    have = {int(k) for k in players}
    return {"ref": doc["ref"], "file": path, "total": total, "have": len(have),
            "missing": sorted(set(range(total)) - have)[:20],
            "errors": sorted(v.get("player_name") for v in players.values()
                             if v.get("error")),
            "complete": have >= set(range(total)) and not any(
                v.get("error") for v in players.values())}


def bundle_status(effective_date: str, root=None) -> list[dict]:
    import json
    d = _bundle_dir(effective_date, root)
    out = []
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        doc = json.loads(f.read_text())
        doc["players"] = {int(k): v for k, v in doc["players"].items()}
        out.append(bundle_status_one(doc, str(f)))
    return out


def read_bundle(effective_date: str, ref: str, root=None) -> dict:
    import json
    f = _bundle_dir(effective_date, root) / f"{_safe(ref)}.json"
    if not f.exists():
        return {"error": f"no bundle for {ref} on {effective_date}"}
    return json.loads(f.read_text())
