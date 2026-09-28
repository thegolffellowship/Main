"""SCORE-ENTRY REPLAY + LOAD (CA #800/#801, Track A).

Feeds the Golf Genius hole scores of completed events through the REAL
score-entry path (the phone's HTTP routes: claim, take-over, queued writes,
sign), group by group, several groups at once, then closes the round and
checks every entered hole against the source card.

    python tools/se_replay.py --db /path/to/SCRATCH.db --events 3309,3315 \
        --workers 8 --i-am-scratch [--out report.json]

SCRATCH COPIES ONLY. It refuses to run inside Railway, refuses a database
whose path looks like production, and needs --i-am-scratch. It turns
score_entry_live on IN THE SCRATCH FILE so the link routes answer; nothing
here sends mail, SMS or anything else (the app is started with every
outbound credential removed from the environment).

Per group (one thread each, --workers at once):
  * phone A claims the card with the group's first player as scorer;
  * holes 1..6 are written hole by hole; hole 3's batch is sent twice
    (a lost ack: the resend must come back "dup"), hole 5 is sent in two
    halves with the first half resent (a dropped connection mid-batch);
  * phone B TAKES OVER after hole 6; phone A then tries hole 7 and must be
    refused ("refused_lock", its value kept in the audit, never lost);
  * phone B writes holes 7..9, the scorekeeper attests, every player signs.
Then the round is closed and every se_* hole is diffed against the card.

GG holes above triple bogey can't be entered (Kerry: "GG is max triple;
pickups enter triple"): they are entered at triple and reported as the
named class above_max_triple, never as a lost hole.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

OUTBOUND_ENV = ("SMTP", "MAIL", "BREVO", "TWILIO", "STRIPE", "SENDGRID", "GMAIL",
                "HUBSPOT", "GG_", "GOLF_GENIUS", "META", "FACEBOOK", "SLACK", "WEBHOOK")


def _guard(db: str, ok: bool) -> None:
    if not ok:
        sys.exit("refusing: pass --i-am-scratch (this writes score-entry rows)")
    # The ONE exception: Health's Railway rehearsal runner (CA #832, Kerry's
    # B) runs this in a separate, secret-free child with TGF_REHEARSAL=1 on
    # a file inside <volume>/rehearsal/. Nothing else passes.
    from email_parser.rehearsal import runner_scratch_ok
    runner = runner_scratch_ok(db)
    if (os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID")) and not runner:
        sys.exit("refusing: this looks like a Railway (production) process")
    p = os.path.abspath(db)
    if not os.path.exists(p):
        sys.exit(f"no such database: {p}")
    if not runner and (p.startswith("/data/") or os.path.basename(p) == "transactions.db" and "scratch" not in p):
        sys.exit(f"refusing: {p} looks like a production database path; copy it to a scratch name")


def _strip_outbound() -> list[str]:
    gone = [k for k in list(os.environ) if any(t in k.upper() for t in OUTBOUND_ENV)]
    for k in gone:
        os.environ.pop(k, None)
    return gone


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--events", required=True, help="comma-separated event ids")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--port", type=int, default=5191)
    ap.add_argument("--out")
    ap.add_argument("--i-am-scratch", action="store_true")
    a = ap.parse_args()
    _guard(a.db, a.i_am_scratch)
    stripped = _strip_outbound()
    os.environ["DATABASE_PATH"] = os.path.abspath(a.db)
    os.environ.setdefault("SECRET_KEY", "se-replay-scratch")
    os.environ["SE_REPLAY"] = "1"

    import contextlib
    import io
    import logging
    import sqlite3
    import urllib.request
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from email_parser import database as db
        from email_parser import score_entry as se
        import app as appmod
    db.set_app_setting("score_entry_live", "1")

    from werkzeug.serving import make_server
    srv = make_server("127.0.0.1", a.port, appmod.app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{a.port}"
    lat: list[float] = []
    lat_lock = threading.Lock()

    def post(path, body):
        t0 = time.perf_counter()
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                out = json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            out = {"http_error": e.code, "body": e.read().decode()[:300]}
        with lat_lock:
            lat.append(time.perf_counter() - t0)
        return out

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    report = {"db": os.path.abspath(a.db), "outbound_env_removed": stripped, "events": []}

    jobs = []           # (event state, group number) across ALL events: one shared pool
    states = []
    for ev_id in [int(x) for x in a.events.split(",") if x.strip()]:
        ev = conn.execute("SELECT * FROM events WHERE id = ?", (ev_id,)).fetchone()
        cards = [dict(r) for r in conn.execute(
            "SELECT r.id, r.customer_id, r.player_name, r.playing_handicap, r.holes_played, "
            "r.course_id, r.tee_id, t.tee_name FROM scoring_rounds r "
            "LEFT JOIN course_tees t ON t.tee_id = r.tee_id "
            "WHERE r.event_id = ? AND COALESCE(r.source,'gg') = 'gg' ORDER BY r.id",
            (ev_id,))]
        er = {"event_id": ev_id, "event": ev["item_name"] if ev else None, "cards": len(cards)}
        if not cards:
            er["result"] = "FAIL: no GG cards in this database"
            report["events"].append(er)
            continue
        holes_by = {}
        par_si = {}
        for c in cards:
            hs = {}
            for h in conn.execute("SELECT hole_number, strokes FROM scoring_holes "
                                  "WHERE scoring_round_id = ? AND strokes IS NOT NULL", (c["id"],)):
                hs[int(h[0])] = int(h[1])
            holes_by[c["id"]] = hs
        # The course card for the holes played (par / SI), from the same
        # tables the GG import writes; a hole with no par can't be checked
        # against max triple and is reported.
        tee_ids = sorted({c["tee_id"] for c in cards if c["tee_id"]})
        for tid in tee_ids:
            for h in db._ls_tee_holes(conn, tid):
                par_si.setdefault(int(h["hole_number"]), (h["par"], h["stroke_index"], h.get("yardage")))
        played = sorted({n for hs in holes_by.values() for n in hs})
        n_holes = 18 if len(played) > 9 else 9
        course = [{"hole": n, "par": par_si.get(n, (None,))[0], "stroke_index": par_si.get(n, (None, None))[1],
                   "yardage": par_si.get(n, (None, None, None))[2]} for n in played]
        er["holes"] = played
        rid = se.create_round(ev_id, n_holes, round_date=(ev["event_date"] if ev else None),
                              label=f"REPLAY #801 {ev['item_name'] if ev else ev_id}",
                              course_holes=course, created_by="se_replay",
                              # the cards' own course, so G-0 resolves each tee on it
                              course_id=next((c["course_id"] for c in cards if c["course_id"]), None)
                              )["round_id"]
        er["round_id"] = rid
        # Real foursomes where the saved pairings still hold them; else by 4.
        grp_of = {}
        try:
            for r in conn.execute("SELECT customer_id, group_num FROM event_pairings WHERE event_id = ? "
                                  "AND customer_id IS NOT NULL", (ev_id,)):
                grp_of[int(r[0])] = int(r[1])
        except sqlite3.Error:
            pass
        groups: dict[int, list] = {}
        spill = 100
        for i, c in enumerate(cards):
            g = grp_of.get(c["customer_id"])
            if g is None:
                g = spill + i // 4
            groups.setdefault(g, []).append(c)
        er["groups_from_pairings"] = bool(grp_of)
        gids = {}
        for gnum, cs in sorted(groups.items()):
            res = se.upsert_group(rid, gnum, players=[{
                "customer_id": c["customer_id"], "display_name": c["player_name"],
                "playing_handicap": c["playing_handicap"],
                # the GG card's tee, as the tee name (#849/#850): G-0 resolves a
                # name through the same legend as a band, and never guesses one
                "tee": c.get("tee_name")} for c in cs])
            gids[gnum] = res["group_id"]
        par = {h["hole"]: h["par"] for h in course}

        def entered_value(n, strokes, par=par):
            p = par.get(n)
            if p and strokes > p + 3:
                return p + 3, "above_max_triple"
            return strokes, None

        def run_group(gnum, gids=gids, groups=groups, holes_by=holes_by, played=played,
                      entered_value=entered_value):
            gid = gids[gnum]
            cs = groups[gnum]
            tok = se.make_group_token(gid)
            out = {"group": gnum, "players": len(cs), "results": {}, "classes": [], "errors": []}
            A, B = f"replayA-{gid}", f"replayB-{gid}"
            keeper = cs[0]["customer_id"]
            c1 = post("/api/score-entry/claim", {"t": tok, "device_id": A, "customer_id": keeper})
            if not c1.get("granted"):
                out["errors"].append(f"claim A: {c1}")
            seq = [0]

            def ops_for(n, device_tag):
                ops = []
                for c in cs:
                    s = holes_by[c["id"]].get(n)
                    if s is None:
                        continue
                    v, cls = entered_value(n, s)
                    if cls and device_tag != "Astale":
                        out["classes"].append({"class": cls, "customer_id": c["customer_id"],
                                               "hole": n, "gg": s, "entered": v})
                    seq[0] += 1
                    ops.append({"op_id": f"rp-{gid}-{device_tag}-{n}-{c['customer_id']}",
                                "customer_id": c["customer_id"], "hole": n, "gross": v})
                return ops

            def send(device, ops):
                r = post("/api/score-entry/write", {"t": tok, "device_id": device,
                                                    "entered_by": keeper, "ops": ops})
                for x in r.get("results", []):
                    out["results"][x.get("result")] = out["results"].get(x.get("result"), 0) + 1
                if "results" not in r:
                    out["errors"].append(f"write: {r}")
                return r

            first = [n for n in played][:6]
            for n in first:
                ops = ops_for(n, "A")
                if n == played[2]:
                    send(A, ops)
                    r2 = send(A, ops)               # lost ack: the resend
                    if any(x.get("result") != "dup" for x in r2.get("results", [])):
                        out["errors"].append("resend was not all dup")
                elif n == played[4]:
                    half = len(ops) // 2 or 1
                    send(A, ops[:half])
                    send(A, ops)                    # dropped mid-batch: resend all
                else:
                    send(A, ops)
            cb = post("/api/score-entry/claim", {"t": tok, "device_id": B, "customer_id": keeper,
                                                 "takeover": True})
            if not cb.get("granted"):
                out["errors"].append(f"takeover B: {cb}")
            rest = played[6:]
            if rest:
                stale = ops_for(rest[0], "Astale")
                rr = post("/api/score-entry/write", {"t": tok, "device_id": A, "entered_by": keeper,
                                                     "ops": stale})
                refused = [x for x in rr.get("results", []) if x.get("result") == "refused_lock"]
                out["stale_phone_refused"] = len(refused) == len(stale)
            for n in rest:
                send(B, ops_for(n, "B"))
            s = post("/api/score-entry/sign", {"t": tok, "device_id": B, "customer_id": keeper,
                                               "kind": "scorekeeper"})
            if s.get("error"):
                out["errors"].append(f"attest: {s}")
            for c in cs:
                s = post("/api/score-entry/sign", {"t": tok, "device_id": f"player-{c['customer_id']}",
                                                   "customer_id": c["customer_id"]})
                if s.get("error"):
                    out["errors"].append(f"sign {c['customer_id']}: {s.get('error')}")
            return out

        st = {"er": er, "rid": rid, "cards": cards, "holes_by": holes_by, "groups": groups,
              "entered_value": entered_value, "run_group": run_group, "gres": {}}
        states.append(st)
        jobs += [(st, g) for g in sorted(groups)]

    # Every event's groups enter AT ONCE (8 at a time by default), the way a
    # Tuesday with both chapters would hit the server.
    t0 = time.perf_counter()
    active = [0]
    peak = [0]
    alock = threading.Lock()

    def one(job):
        st, g = job
        with alock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        try:
            st["gres"][g] = st["run_group"](g)
        finally:
            with alock:
                active[0] -= 1
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(one, jobs))
    report["load"] = {"groups_total": len(jobs), "workers": a.workers,
                      "peak_concurrent_groups": peak[0],
                      "elapsed_s": round(time.perf_counter() - t0, 2)}

    for st in states:
        er, rid, cards, holes_by, groups = st["er"], st["rid"], st["cards"], st["holes_by"], st["groups"]
        entered_value, ev_id = st["entered_value"], er["event_id"]
        gres = [st["gres"][g] for g in sorted(groups)]
        se.close_round(rid)

        # THE CHECK: every se_* hole against the card.
        read = se.get_entered_scores(ev_id, rid)["rounds"][0]
        got = {p["customer_id"]: {int(k): v for k, v in (p.get("scores") or {}).items()}
               for p in read["players"]}
        expected = matched = lost = wrong = named = 0
        diffs = []
        classes = [c for g in gres for c in g["classes"]]
        named_keys = {(c["customer_id"], c["hole"]) for c in classes}
        for c in cards:
            for n, s in holes_by[c["id"]].items():
                expected += 1
                v = got.get(c["customer_id"], {}).get(n)
                want, _cls = entered_value(n, s)
                if v is None:
                    lost += 1
                    diffs.append({"customer_id": c["customer_id"], "hole": n, "gg": s, "entry": None})
                elif v != want:
                    wrong += 1
                    diffs.append({"customer_id": c["customer_id"], "hole": n, "gg": s, "entry": v})
                elif (c["customer_id"], n) in named_keys:
                    named += 1
                else:
                    matched += 1
        signed = {(x["customer_id"], x["kind"]) for x in read.get("signoffs", [])}
        er.update({
            "groups": len(groups), "holes_expected": expected, "holes_exact": matched,
            "holes_named_class": named, "holes_lost": lost, "holes_wrong": wrong,
            "diffs": diffs[:50], "named_classes": classes,
            "players_signed": sum(1 for c in cards if (c["customer_id"], "player") in signed),
            "groups_attested": sum(1 for g in read["groups"]
                                   if any((p["customer_id"], "scorekeeper") in signed
                                          for p in read["players"] if p["group_id"] == g["group_id"])),
            "stale_phone_refused_all": all(g.get("stale_phone_refused", True) for g in gres),
            "write_results": {k: sum(g["results"].get(k, 0) for g in gres)
                              for k in {k for g in gres for k in g["results"]}},
            "errors": [e for g in gres for e in g["errors"]][:30],
            "round_status": se.get_entered_scores(ev_id, rid)["rounds"][0]["status"],
            # a refused write is never lost: its value sits in se_audit.detail
            "refused_kept_in_audit": se.refused_writes_kept(rid),
            # every card that had a tee carries it onto the entered round (#849/#850)
            "tee_expected": sum(1 for c in cards if c.get("tee_name")),
            "tee_carried": sum(1 for p in read["players"]
                               if p.get("tee") and any(c["customer_id"] == p["customer_id"]
                                                       and c.get("tee_name") for c in cards)),
        })
        er["result"] = "PASS" if (lost == 0 and wrong == 0 and not er["errors"]
                                  and er["players_signed"] == len(cards)
                                  and er["groups_attested"] == len(groups)
                                  and er["stale_phone_refused_all"]
                                  and er["round_status"] == "closed"
                                  and er["refused_kept_in_audit"] == len(cards)
                                  and er["tee_carried"] == er["tee_expected"]) else "FAIL"
        report["events"].append(er)

    srv.shutdown()
    if lat:
        s = sorted(lat)
        report["requests"] = {"n": len(s), "p50_ms": round(statistics.median(s) * 1000, 1),
                              "p95_ms": round(s[int(len(s) * 0.95) - 1] * 1000, 1),
                              "max_ms": round(s[-1] * 1000, 1)}
    report["workers"] = a.workers
    txt = json.dumps(report, indent=2, default=str)
    if a.out:
        open(a.out, "w").write(txt)
    print(txt)
    return 0 if all(e.get("result") == "PASS" for e in report["events"]) else 1


if __name__ == "__main__":
    sys.exit(main())
