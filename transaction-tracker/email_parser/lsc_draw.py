"""LONE STAR CUP DRAW, live into the dial (Kerry 10/8 via CoS #1432: "Can't
you set up the draw to automatically go to the matches for this weekend on
the tracker rather than copying here? Being able to push live immediately
would be much cooler.").

The staff-only page /events/<id>/cup-draw is the Chief of Staff's draw board
(cup_draw.template.html) ported as is. This module is its data and its one
write path:

- ``pools(event_id)``: the entrants. Saturday = the fixed pairs in
  ``lsc_matches.pairs`` (low/high pool by COMBINED RAW INDEX, #1415), names
  from the handicap lock; Sunday = each team's 14 players from
  ``lsc_handicap_lock`` sorted by locked raw index, Low 7 / High 7.
- ``state(event_id)``: what has been drawn, read back from the dial (a drawn
  match carries ``draw: {pool, a, s, n}``).
- ``land(...)``: write one drawn match into its session of the live dial.
  The server re-checks every rule the page enforces: entrant in the pool
  and not yet drawn, a Saturday PM pool only after its AM pool is complete,
  no PM pairing that repeats an AM pairing, and the rest of the pool still
  completable (the page's canComplete look-ahead). The first drawn match in
  a session drops that session's STAGED (undrawn) matches.
- ``clear(...)``: remove a session's drawn matches; clearing FOURBALL also
  clears FOURSOMES (its no-repeat rule depends on FOURBALL).

Match number = tee order: Saturday 1-3 low pool, 4-7 high; Sunday 1-7 low,
8-14 high. Tee time = session start + 10 min per match, two matches per tee
time on Sunday. se_round and board_live are left as they are. Every write
is logged in agent_action_log.
"""
from __future__ import annotations

import json

DIAL = "lsc_matches"
LOCK = "lsc_handicap_lock"

# page key -> (dial session id, start hh, start mm, matches per tee time, id prefix)
SESSIONS = {
    "fb": ("sat-am", 8, 30, 1, "SAT-AM-"),
    "fs": ("sat-pm", 13, 30, 1, "SAT-PM-"),
    "sg": ("sun", 8, 30, 2, "SUN-"),
}
POOLS = ("low", "high")


def _get(key, db_path=None) -> dict:
    from email_parser.database import get_app_setting
    try:
        raw = get_app_setting(key, db_path=db_path) or ""
        return json.loads(raw) if raw.strip() else {}
    except (ValueError, TypeError):
        return {}


def _lock_players(event_id, db_path=None) -> dict:
    return ((_get(LOCK, db_path).get(str(event_id)) or {}).get("players") or {})


def pools(event_id: int, db_path=None) -> dict:
    """{"fb"|"fs"|"sg": {"low"|"high": {"austin": [...], "sa": [...]}}}; an
    entrant is {key, label, idx, cids}. Saturday AM and PM draw from the same
    pairs. Raises nothing; empty lists when the dial or lock is not set."""
    dial = _get(DIAL, db_path)
    lock = _lock_players(event_id, db_path)

    def nm(c):
        return (lock.get(str(c)) or {}).get("name") or f"#{c}"

    raw = dial.get("pairs") or {}
    sat = {p: {"austin": [], "sa": []} for p in POOLS}
    for team in ("austin", "sa"):
        for pr in [p for p in raw.get(team) or [] if isinstance(p, dict)]:
            pool = pr.get("pool")
            if pool not in POOLS:
                continue
            cids = [int(c) for c in pr.get("cids") or []]
            idx = pr.get("combined_index")
            if idx is None:
                idx = round(sum(float((lock.get(str(c)) or {}).get("index") or 0) for c in cids), 1)
            sat[pool][team].append({"key": str(pr.get("id")), "label": " / ".join(nm(c) for c in cids),
                                    "idx": float(idx), "cids": cids})
        for pool in POOLS:
            sat[pool][team].sort(key=lambda e: (e["idx"], e["key"]))
    sun = {p: {"austin": [], "sa": []} for p in POOLS}
    for team in ("austin", "sa"):
        players = sorted(((int(c), v) for c, v in lock.items() if (v or {}).get("team") == team),
                         key=lambda t: (float(t[1].get("index") if t[1].get("index") is not None else 99), t[0]))
        half = (len(players) + 1) // 2
        for i, (c, v) in enumerate(players):
            sun["low" if i < half else "high"][team].append(
                {"key": str(c), "label": v.get("name") or f"#{c}",
                 "idx": float(v.get("index") if v.get("index") is not None else 0), "cids": [c]})
    return {"fb": sat, "fs": sat, "sg": sun}


def _session(dial: dict, sid: str) -> dict | None:
    return next((s for s in dial.get("sessions") or [] if s.get("id") == sid), None)


def state(event_id: int, db_path=None) -> dict:
    """{"fb": {"low": [[a_key, s_key], ...], "high": [...]}, ...} in draw
    order, read from the drawn matches in the live dial."""
    dial = _get(DIAL, db_path)
    out = {k: {p: [] for p in POOLS} for k in SESSIONS}
    for k, (sid, *_r) in SESSIONS.items():
        sess = _session(dial, sid) or {}
        drawn = [m for m in sess.get("matches") or [] if isinstance(m.get("draw"), dict)]
        for m in sorted(drawn, key=lambda m: int(m["draw"].get("n") or 0)):
            d = m["draw"]
            if d.get("pool") in POOLS:
                out[k][d["pool"]].append([str(d.get("a")), str(d.get("s"))])
    return out


def _can_complete(a_keys, s_keys, forbid) -> bool:
    """The page's canComplete: can the remaining Austin entrants each still
    get an SA opponent with no forbidden (AM-repeat) pairing?"""
    if not a_keys:
        return True
    a = a_keys[0]
    for s in s_keys:
        if f"{a}|{s}" in forbid:
            continue
        if _can_complete(a_keys[1:], [x for x in s_keys if x != s], forbid):
            return True
    return False


def tee_time(sess_key: str, n: int) -> str:
    """Tee time for 0-based match index n, as the dial writes it ("8:30")."""
    _sid, hh, mm, per, _p = SESSIONS[sess_key]
    total = hh * 60 + mm + 10 * (n // per)
    h, m = divmod(total, 60)
    return f"{(h % 12) or 12}:{m:02d}"


def land(event_id: int, sess_key: str, pool: str, a_key: str, s_key: str,
         *, actor: str = "cup-draw", db_path=None) -> dict:
    """Write one drawn match into the live dial. Returns {ok, match} or
    {error}."""
    from email_parser.database import set_app_setting, log_agent_action
    if sess_key not in SESSIONS or pool not in POOLS:
        return {"error": "unknown session or pool"}
    dial = _get(DIAL, db_path)
    if int(dial.get("event_id") or 0) != int(event_id):
        return {"error": "the Cup dial is not set for this event"}
    sid, _hh, _mm, _per, prefix = SESSIONS[sess_key]
    sess = _session(dial, sid)
    if sess is None:
        return {"error": f"session {sid} is not on the dial"}
    pl = pools(event_id, db_path)[sess_key][pool]
    st = state(event_id, db_path)
    done = st[sess_key][pool]
    a_ent = next((e for e in pl["austin"] if e["key"] == str(a_key)), None)
    s_ent = next((e for e in pl["sa"] if e["key"] == str(s_key)), None)
    if not a_ent or not s_ent:
        return {"error": "that entrant is not in this pool"}
    if any(m[0] == a_ent["key"] for m in done) or any(m[1] == s_ent["key"] for m in done):
        return {"error": "that entrant is already drawn"}
    forbid = set()
    if sess_key == "fs":
        if len(st["fb"][pool]) < len(pools(event_id, db_path)["fb"][pool]["austin"]):
            return {"error": "Draw Saturday AM first"}
        forbid = {f"{a}|{s}" for a, s in st["fb"][pool]}
    if f"{a_ent['key']}|{s_ent['key']}" in forbid:
        return {"error": "that pairing already met on Saturday AM"}
    rem_a = [e["key"] for e in pl["austin"] if e["key"] != a_ent["key"] and not any(m[0] == e["key"] for m in done)]
    rem_s = [e["key"] for e in pl["sa"] if e["key"] != s_ent["key"] and not any(m[1] == e["key"] for m in done)]
    if not _can_complete(rem_a, rem_s, forbid):
        return {"error": "that pairing would force a repeat later in the pool"}
    offset = len(pools(event_id, db_path)[sess_key]["low"]["austin"]) if pool == "high" else 0
    n = offset + len(done)                        # 0-based tee order
    match = {"id": f"{prefix}{n + 1}", "tee_time": tee_time(sess_key, n),
             "austin": a_ent["cids"], "sa": s_ent["cids"],
             "draw": {"pool": pool, "a": a_ent["key"], "s": s_ent["key"], "n": n + 1}}
    kept = [m for m in sess.get("matches") or [] if isinstance(m.get("draw"), dict)]
    dropped = len(sess.get("matches") or []) - len(kept)   # STAGED matches go on the first draw
    kept.append(match)
    sess["matches"] = sorted(kept, key=lambda m: int(m["draw"]["n"]))
    set_app_setting(DIAL, json.dumps(dial), db_path=db_path)
    log_agent_action(actor, "lsc-draw-land",
                     f"event {event_id} {sid} {pool} match {n + 1} {match['tee_time']}: "
                     f"{a_ent['label']} v {s_ent['label']}"
                     + (f" (dropped {dropped} staged)" if dropped else ""), db_path=db_path)
    return {"ok": True, "match": match, "dropped_staged": dropped,
            "label": {"a": a_ent["label"], "s": s_ent["label"]}}


def clear(event_id: int, sess_key: str, *, actor: str = "cup-draw", db_path=None) -> dict:
    """Remove a session's drawn matches (FOURBALL takes FOURSOMES with it)."""
    from email_parser.database import set_app_setting, log_agent_action
    if sess_key not in SESSIONS:
        return {"error": "unknown session"}
    dial = _get(DIAL, db_path)
    if int(dial.get("event_id") or 0) != int(event_id):
        return {"error": "the Cup dial is not set for this event"}
    keys = [sess_key] + (["fs"] if sess_key == "fb" else [])
    removed = {}
    for k in keys:
        sess = _session(dial, SESSIONS[k][0])
        if sess is None:
            continue
        before = len(sess.get("matches") or [])
        sess["matches"] = [m for m in sess.get("matches") or [] if not isinstance(m.get("draw"), dict)]
        removed[SESSIONS[k][0]] = before - len(sess["matches"])
    set_app_setting(DIAL, json.dumps(dial), db_path=db_path)
    log_agent_action(actor, "lsc-draw-clear", f"event {event_id} cleared {removed}", db_path=db_path)
    return {"ok": True, "removed": removed}
