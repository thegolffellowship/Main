"""The DAILY HEALTH DIGEST — the CTO agent (Kerry 2026-09-22: "I think we
would define your Agent Role as CTO") that reads the Tracker's own
measurements and reports back (Kerry 2026-09-22: *"an agent specifically
designed for this that will log things and report back to you and the
COO for you to pick up. Should be a standard once a day routine."*).

What it does, once a day at the dialled time (`health_digest_time`,
HH:MM Central, default 05:00 — Kerry's hour, #611: the Handicap Surfaces
lane's 5:15 pick-up reads it, and Kerry wakes to a brief):

  1. `build_health_report(days=1)` — p50 / p95 / max per route, job and
     bridge from `perf_samples`; the slow-open list with breakdowns and
     what else was running; job durations and failures; error counts
     from the agent action log; the database file's size and growth;
     the handicap cache's hit rate; a live probe of how long a bare
     connection takes RIGHT NOW; and FINDINGS — the rules below applied
     to those numbers, each with a severity.
  2. Posts the digest to the mailbox, topic `tracker-health`, addressed
     to tracker-claude (the lane that acts on it).
  3. Files every high/medium finding as a COO action item (category
     'other', from 'Tracker Health'), so it reaches the COO dashboard
     and the landing page's count. Subjects are stable per finding so
     the same problem on two mornings is ONE open item, not two.
  4. Prunes samples older than the retention window.

The same report backs `/admin/health` and the `scoring-health` bridge —
one builder, three readers, so the numbers cannot disagree.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from . import perf

logger = logging.getLogger(__name__)

# Kerry 2026-09-22 (#611): "5:00am for the central digest and subsequent
# response work so that anything is updated by the time I wake up." The
# Handicap Surfaces lane picks it up at 5:15, so it must be posted by 5:10.
DIGEST_TIME_DEFAULT = "05:00"
DIGEST_TOPIC = "tracker-health"
DIGEST_AUTHOR = "tracker-claude"
# Kerry 2026-09-22: "I think we would define your Agent Role as CTO."
ACTION_FROM = "CTO"
AGENT_NAME = "cto-agent"
# Findings rules (rules as data — the numbers a non-developer may tune)
RULES = {
    "route_p95_over_threshold": True,     # p95 above the path's SLOW line
    "job_error": True,                    # any failed job run
    "job_error_recent_hours": 3,          # errors all older than this + last run ok → RECOVERED (medium)
    "provider_alerts": True,              # an open hosting-provider alert (Railway) is a HIGH finding
    "provider_alert_days": 14,            # ...only this recent; older open ones are ONE stale-count line
    "job_slow": True,                     # a job over its SLOW line
    "db_growth_mb_per_day": 20,           # the file grew more than this
    "probe_connect_ms": 150,              # a bare connect slower than this
    "probe_read_ms": 150,
    "error_log_rows": 5,                  # agent-log error rows in the window
    "min_samples_expected": 1,            # fewer than this = nothing measured
    "free_pages_pct": 20,                 # freelist over this % of the file → VACUUM candidate
    "load_per_cpu": 4.0,                  # load1 / cpus over this → the box is saturated
    "volume_pct_warn": 80,                # the volume the DB sits on — medium finding
    "volume_pct_alarm": 90,               # ...high finding (9/22: 99% took the site down)
}


# ── the report ──────────────────────────────────────────────────────────
def _archive_status(db_path) -> dict:
    """The GG raw archive's own file (gg_archive.py) — mode, bytes, rows."""
    try:
        from .gg_archive import status
        return status(db_path)
    except Exception as e:      # the report never fails on its own extras
        return {"mode": "unknown", "error": str(e)[:120]}


def _table_counts(db_path) -> dict:
    out = {}
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        for t in ("items", "events", "customers", "handicap_rounds",
                  "scoring_rounds", "action_items", "agent_action_log", "perf_samples"):
            try:
                out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.Error:
                out[t] = None
    finally:
        conn.close()
    return out


def _log_errors(days: float, db_path) -> dict:
    """Error / slow rows in agent_action_log over the window, by type."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(
                """SELECT action_type, COUNT(*) AS n FROM agent_action_log
                    WHERE created_at >= ?
                      AND (action_type LIKE '%\\_error' ESCAPE '\\'
                           OR action_type LIKE '%\\_slow' ESCAPE '\\'
                           OR action_type LIKE '%fail%'
                           OR LOWER(COALESCE(outcome, '')) IN ('error', 'failed'))
                    GROUP BY action_type ORDER BY n DESC""", (since,)).fetchall()
        except sqlite3.Error:
            rows = []
    finally:
        conn.close()
    return {r["action_type"]: r["n"] for r in rows}


def _size_history(db_path, today: str, size_bytes: int) -> tuple[list, int | None]:
    """Record today's size; return the history and the growth since the
    previous recorded day (bytes), if any."""
    from .database import get_app_setting, set_app_setting
    try:
        hist = json.loads(get_app_setting("health_db_size_history", db_path=db_path) or "[]")
    except Exception:
        hist = []
    hist = [h for h in hist if h.get("date") != today]
    prev = hist[-1] if hist else None
    hist.append({"date": today, "bytes": size_bytes})
    hist = hist[-45:]
    try:
        set_app_setting("health_db_size_history", json.dumps(hist), db_path=db_path)
    except Exception:
        logger.debug("size history write failed (non-fatal)", exc_info=True)
    growth = (size_bytes - int(prev["bytes"])) if prev else None
    return hist, growth


def _hcp_cache_stats() -> dict:
    try:
        from .database import _HCP_CACHE_STATS
        h, m = _HCP_CACHE_STATS.get("hits", 0), _HCP_CACHE_STATS.get("misses", 0)
        return {"hits": h, "misses": m,
                "hit_rate": round(h / (h + m), 3) if (h + m) else None}
    except Exception:
        return {"hits": 0, "misses": 0, "hit_rate": None}


def _fmt_ms(ms) -> str:
    if ms is None:
        return "—"
    ms = int(ms)
    return f"{ms/1000:.1f} s" if ms >= 1000 else f"{ms} ms"


def _provider_alerts(db_path) -> list[dict]:
    """OPEN action items that are a hosting / infrastructure provider's own
    alert (Railway volume, billing, outage mail). The 9/22 outage was
    mailed by Railway three days earlier ("Main volume is 95% full") and
    sat in the queue at confidence 45, never surfaced (#621). The CTO
    digest names every open one until it is closed."""
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(
                """SELECT id, subject, from_email, email_date, created_at FROM action_items
                    WHERE status IN ('open', 'in_progress')
                      AND (LOWER(COALESCE(from_email, '')) LIKE '%railway%'
                           OR LOWER(COALESCE(from_email, '')) LIKE '%@render.com'
                           OR LOWER(COALESCE(from_email, '')) LIKE '%@fly.io'
                           OR LOWER(COALESCE(subject, '')) LIKE '%volume%full%'
                           OR LOWER(COALESCE(subject, '')) LIKE '%disk%full%')
                    ORDER BY created_at DESC LIMIT 10""").fetchall()
        except sqlite3.Error:
            rows = []
    finally:
        conn.close()
    return [dict(r) for r in rows]


def build_health_report(days: float = 1, db_path=None, record_size: bool = False) -> dict:
    """Everything the digest, the page and the bridge show."""
    from .timezone_utils import now_central, today_central_str
    db_path = perf._db_path(db_path)
    summary = perf.summary(days, db_path=db_path)
    slow = [s for s in perf.samples(days, db_path=db_path, limit=2000)
            if s["status"] in ("slow", "error")]
    slow.sort(key=lambda s: -s["total_ms"])
    jobs = {}
    for s in perf.samples(days, kind="job", db_path=db_path, limit=5000):
        j = jobs.setdefault(s["name"], {"name": s["name"], "runs": 0, "errors": 0,
                                        "max_ms": 0, "sum_ms": 0, "last_at": None,
                                        "last_status": None, "last_error": None,
                                        "last_error_at": None})
        j["runs"] += 1
        j["sum_ms"] += s["total_ms"]
        j["max_ms"] = max(j["max_ms"], s["total_ms"])
        if s["status"] == "error":
            j["errors"] += 1
            if j["last_error"] is None:
                j["last_error"] = ((s.get("detail") or {}).get("error") or "")[:200]
                j["last_error_at"] = s["at"]
        if j["last_at"] is None:          # samples come newest first
            j["last_at"], j["last_status"] = s["at"], s["status"]
    for j in jobs.values():
        j["avg_ms"] = int(round(j["sum_ms"] / j["runs"])) if j["runs"] else 0
    size = perf.db_size(db_path)
    today = today_central_str()
    growth = None
    hist = []
    if record_size:
        hist, growth = _size_history(db_path, today, size["bytes"])
    else:
        try:
            from .database import get_app_setting
            hist = json.loads(get_app_setting("health_db_size_history", db_path=db_path) or "[]")
            prev = [h for h in hist if h.get("date") != today]
            if prev:
                growth = size["bytes"] - int(prev[-1]["bytes"])
        except Exception:
            pass
    report = {
        "generated_at": now_central().strftime("%Y-%m-%d %H:%M"),
        "window_days": days,
        "summary": summary,
        "slow": slow[:40],
        "jobs": sorted(jobs.values(), key=lambda j: (-j["errors"], -j["max_ms"])),
        "log_errors": _log_errors(days, db_path),
        "db": {**size, "growth_bytes": growth, "history": hist[-14:],
               "counts": _table_counts(db_path), "layout": perf.db_layout(db_path),
               "disk": perf.disk_usage(db_path), "archive": _archive_status(db_path)},
        "probe": perf.probe_db_ms(db_path),
        # Inside a container os.getloadavg() is the HOST's number, so it is
        # read beside the cpu count; a ratio, not the raw figure, is the tell.
        "load1": perf._load1(),
        "cpus": os.cpu_count(),
        "hcp_cache": _hcp_cache_stats(),
        "provider_alerts": _provider_alerts(db_path),
        "sample_count": sum(r["count"] for k in summary for r in summary[k]),
    }
    report["findings"] = find(report)
    return report


def find(report: dict) -> list[dict]:
    """The rules applied to a report. Each finding: severity high | medium |
    info, a stable `key` (one open action item per key), a one-line text."""
    out = []
    S = report["summary"]
    if report["sample_count"] < RULES["min_samples_expected"]:
        out.append({"severity": "info", "key": "no_samples",
                    "text": "No perf samples in the window — nothing measured "
                            "(a fresh deploy, or the flusher is not running)."})
    if RULES["route_p95_over_threshold"]:
        for r in S["route"] + S["bridge"]:
            if r["p95"] > r["slow_ms"] and r["count"] >= 2:
                out.append({"severity": "high", "key": f"route_slow:{r['name']}",
                            "text": f"{r['name']}: p95 {_fmt_ms(r['p95'])} over its "
                                    f"{_fmt_ms(r['slow_ms'])} line (n={r['count']}, "
                                    f"p50 {_fmt_ms(r['p50'])}, max {_fmt_ms(r['max'])})"})
            elif r["max"] > r["slow_ms"]:
                out.append({"severity": "medium", "key": f"route_spike:{r['name']}",
                            "text": f"{r['name']}: {r['slow']} slow of {r['count']} "
                                    f"(max {_fmt_ms(r['max'])}, p95 {_fmt_ms(r['p95'])})"})
    for j in report["jobs"]:
        if RULES["job_error"] and j["errors"]:
            # Errors that stopped hours ago with the last run OK are a
            # RECOVERED incident, not a live one — reported, filed as
            # medium, and worded so nobody chases a fixed problem
            # (9/23: five HIGH items for a volume Kerry had already resized).
            recovered = False
            try:
                last_err = datetime.strptime(j["last_error_at"], "%Y-%m-%d %H:%M:%S") if j.get("last_error_at") else None
                age_h = ((datetime.now(timezone.utc).replace(tzinfo=None) - last_err).total_seconds() / 3600
                         if last_err else None)
                recovered = (j.get("last_status") == "ok" and age_h is not None
                             and age_h >= RULES["job_error_recent_hours"])
            except (TypeError, ValueError):
                recovered = False
            if recovered:
                out.append({"severity": "medium", "key": f"job_error:{j['name']}",
                            "text": f"job {j['name']} failed {j['errors']} of {j['runs']} run(s), "
                                    f"RECOVERED — last error {j['last_error_at']} UTC, every run since OK"
                                    + (f" — {j['last_error']}" if j.get("last_error") else "")})
            else:
                out.append({"severity": "high", "key": f"job_error:{j['name']}",
                            "text": f"job {j['name']} failed {j['errors']} of {j['runs']} run(s)"
                                    + (f" — {j['last_error']}" if j.get("last_error") else "")})
    if RULES["provider_alerts"]:
        # A provider alert IS an action item already — the finding names
        # it, it never files a second item about it (`file: False`; 9/24:
        # ten HEALTH items were filed pointing at ten Railway mails). Only
        # a recent one is a live finding; older open ones (May's "service
        # disruption — recovery complete") are one stale count, to close.
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RULES["provider_alert_days"])).strftime("%Y-%m-%d")
        stale = []
        for a in report.get("provider_alerts") or []:
            when = (a.get("email_date") or a.get("created_at") or "")[:10]
            if when and when < cutoff:
                stale.append(a)
                continue
            out.append({"severity": "high", "key": f"provider_alert:{a['id']}", "file": False,
                        "text": f"OPEN provider alert #{a['id']} since {when}: "
                                f"\"{a.get('subject')}\" ({a.get('from_email')}) — act on it or close it "
                                f"(the 9/22 outage was mailed three days ahead and sat in this queue)"})
        if stale:
            out.append({"severity": "info", "key": "provider_alerts_stale", "file": False,
                        "text": f"{len(stale)} older provider alert(s) still open (oldest {min((a.get('email_date') or a.get('created_at') or '')[:10] for a in stale)}): "
                                + ", ".join(f"#{a['id']}" for a in stale) + " — long resolved; close them"})
    if RULES["job_slow"]:
        for r in S["job"]:
            if r["slow"]:
                out.append({"severity": "medium", "key": f"job_slow:{r['name']}",
                            "text": f"job {r['name']}: {r['slow']} run(s) over "
                                    f"{_fmt_ms(r['slow_ms'])} (max {_fmt_ms(r['max'])})"})
    g = report["db"].get("growth_bytes")
    if g is not None and g > RULES["db_growth_mb_per_day"] * 1048576:
        out.append({"severity": "medium", "key": "db_growth",
                    "text": f"database grew {g/1048576:.1f} MB since the last digest "
                            f"(now {report['db']['bytes']/1048576:.1f} MB)"})
    pr = report.get("probe") or {}
    if pr.get("connect_ms", 0) > RULES["probe_connect_ms"] or pr.get("read_ms", 0) > RULES["probe_read_ms"]:
        out.append({"severity": "high", "key": "db_probe_slow",
                    "text": f"a bare database touch is slow right now: connect "
                            f"{pr.get('connect_ms')} ms, pragma {pr.get('pragma_ms')} ms, "
                            f"read {pr.get('read_ms')} ms — every section of every "
                            f"request pays this"})
    lay = (report["db"].get("layout") or {})
    if lay.get("page_count") and lay.get("freelist_pages") is not None:
        pct = 100.0 * lay["freelist_pages"] / max(1, lay["page_count"])
        if pct > RULES["free_pages_pct"]:
            out.append({"severity": "medium", "key": "db_free_pages",
                        "text": f"{pct:.0f}% of the database file is free pages "
                                f"({lay['free_bytes']/1048576:.0f} MB of {report['db']['bytes']/1048576:.0f} MB) — "
                                f"deleted rows' space never reclaimed; a VACUUM (off-hours, Kerry's call) "
                                f"would shrink the file every read pays for"})
    disk = report["db"].get("disk") or {}
    pct = disk.get("pct_used")
    if pct is not None and pct >= RULES["volume_pct_warn"]:
        sev = "high" if pct >= RULES["volume_pct_alarm"] else "medium"
        out.append({"severity": sev, "key": "volume_full",
                    "text": f"the volume the database sits on is {pct:.0f}% full "
                            f"({(disk.get('free_bytes') or 0)/1048576:.0f} MB free of "
                            f"{(disk.get('total_bytes') or 0)/1048576:.0f} MB) — at 100% SQLite "
                            f"cannot grow its WAL and every read fails (9/22 outage); resize the "
                            f"Railway volume (Volumes → Live resize) or move gg_raw_archive out"})
    big = [t for t in (lay.get("tables") or []) if t["type"] == "table"]
    if big and report["db"]["bytes"] and big[0]["bytes"] > 0.5 * report["db"]["bytes"] and big[0]["bytes"] > 50 * 1048576:
        out.append({"severity": "medium", "key": f"db_big_table:{big[0]['name']}",
                    "text": f"table {big[0]['name']} is {big[0]['bytes']/1048576:.0f} MB — over half the file"})
    if report.get("load1") is not None and report.get("cpus"):
        ratio = report["load1"] / max(1, report["cpus"])
        if ratio > RULES["load_per_cpu"]:
            out.append({"severity": "high", "key": "box_load",
                        "text": f"the box is saturated: load average {report['load1']} over "
                                f"{report['cpus']} cpu(s) (host figure inside the container) — "
                                f"every request waits for CPU before its first query"})
    n_err = sum(report["log_errors"].values())
    if n_err >= RULES["error_log_rows"]:
        top = ", ".join(f"{k} ×{v}" for k, v in list(report["log_errors"].items())[:4])
        out.append({"severity": "medium", "key": "log_errors",
                    "text": f"{n_err} error/slow rows in the agent action log: {top}"})
    sev = {"high": 0, "medium": 1, "info": 2}
    out.sort(key=lambda f: sev[f["severity"]])
    return out


# ── rendering ───────────────────────────────────────────────────────────
def render_markdown(report: dict) -> str:
    L = []
    L.append(f"TO: tracker-claude (Handicap Surfaces lane), kerry\n"
             f"FROM: CTO agent (Tracker Health & Performance) — DAILY DIGEST, last {report['window_days']:g} day(s), "
             f"generated {report['generated_at']} Central\n")
    f = report["findings"]
    if f:
        L.append("**FINDINGS**")
        for x in f:
            L.append(f"- [{x['severity'].upper()}] {x['text']}")
    else:
        L.append("**FINDINGS:** none — every measured path inside its line.")
    L.append("")
    for kind, title in (("route", "ROUTES"), ("job", "JOBS"), ("bridge", "BRIDGES")):
        rows = report["summary"].get(kind) or []
        if not rows:
            continue
        L.append(f"**{title}** (n · p50 · p95 · max · slow/err · line)")
        for r in rows[:25]:
            L.append(f"- {r['name']}: {r['count']} · {_fmt_ms(r['p50'])} · "
                     f"{_fmt_ms(r['p95'])} · {_fmt_ms(r['max'])} · "
                     f"{r['slow']}/{r['errors']} · {_fmt_ms(r['slow_ms'])}")
        L.append("")
    if report["slow"]:
        L.append("**SLOW / FAILED SAMPLES** (worst first)")
        for s in report["slow"][:12]:
            bd = s.get("breakdown") or {}
            worst = ", ".join(f"{k} {_fmt_ms(v)}" for k, v in
                              sorted(bd.items(), key=lambda kv: -kv[1])[:4])
            d = s.get("detail") or {}
            extra = ""
            if d.get("concurrent"):
                extra += f"; while {', '.join(d['concurrent'])}"
            if d.get("load1") is not None:
                extra += f"; load {d['load1']}"
            if d.get("error"):
                extra += f"; {d['error'][:120]}"
            ev = f" event {s['event_id']}" if s.get("event_id") else ""
            L.append(f"- {s['at']} {s['kind']} {s['name']}{ev}: {_fmt_ms(s['total_ms'])} "
                     f"[{s['status']}] — {worst}{extra}")
        L.append("")
    db = report["db"]
    g = db.get("growth_bytes")
    L.append(f"**DATABASE** {db['bytes']/1048576:.1f} MB"
             + (f" (+{g/1048576:.2f} MB since last digest)" if g is not None else "")
             + f", WAL {db['wal_bytes']/1048576:.1f} MB; rows: "
             + ", ".join(f"{k} {v}" for k, v in (db.get("counts") or {}).items() if v is not None))
    arc = db.get("archive") or {}
    if arc.get("mode") == "file":
        L.append(f"**GG ARCHIVE FILE** {arc.get('bytes', 0)/1048576:.1f} MB, {arc.get('rows') or 0} rows"
                 + (f"; last backup {arc['last_backup_at'][:10]}" if arc.get("last_backup_at") else "; never backed up on its own yet")
                 + ("" if arc.get("vacuum_at") else "; main file not yet vacuumed after the move"))
    elif arc.get("mode") == "main":
        L.append(f"**GG ARCHIVE** still in the main file ({arc.get('main_rows') or 0} rows); "
                 f"{arc.get('rows') or 0} copied to {arc.get('path')} so far")
    dk = db.get("disk") or {}
    if dk.get("pct_used") is not None:
        L.append(f"**VOLUME** {dk['pct_used']:.0f}% used — {dk['free_bytes']/1048576:.0f} MB free "
                 f"of {dk['total_bytes']/1048576:.0f} MB")
    lay = db.get("layout") or {}
    if lay.get("tables"):
        L.append("**WHERE THE BYTES ARE:** " + ", ".join(
            f"{t['name']} {t['bytes']/1048576:.0f} MB" for t in lay["tables"][:8])
            + (f"; free pages {lay['free_bytes']/1048576:.0f} MB" if lay.get("free_bytes") else ""))
    pr = report["probe"]
    L.append(f"**PROBE now:** connect {pr['connect_ms']} ms · pragma {pr['pragma_ms']} ms · "
             f"read {pr['read_ms']} ms · load1 {report.get('load1')} on {report.get('cpus')} cpu(s)")
    hc = report["hcp_cache"]
    L.append(f"**HANDICAP CACHE** since boot: {hc['hits']} hits / {hc['misses']} misses"
             + (f" ({hc['hit_rate']*100:.0f}%)" if hc.get("hit_rate") is not None else ""))
    if report.get("provider_alerts"):
        L.append("**PROVIDER ALERTS OPEN:** " + "; ".join(
            f"#{a['id']} {a.get('email_date') or ''} {a.get('subject')}" for a in report["provider_alerts"]))
    if report["log_errors"]:
        L.append("**LOG** error/slow rows: " + ", ".join(
            f"{k} ×{v}" for k, v in list(report["log_errors"].items())[:8]))
    L.append("")
    L.append("Read the same numbers at /admin/health or bridge `scoring-health[:<days>]`; "
             "raw rows in `perf_samples`.")
    return "\n".join(L)


# ── the once-a-day routine ──────────────────────────────────────────────
def digest_time(db_path=None) -> str:
    from .database import get_app_setting
    try:
        v = (get_app_setting("health_digest_time", db_path=db_path) or "").strip()
    except Exception:
        v = ""
    if len(v) == 5 and v[2] == ":" and v[:2].isdigit() and v[3:].isdigit():
        return v
    return DIGEST_TIME_DEFAULT


def file_action_items(findings: list[dict], db_path=None) -> list[dict]:
    """One COO action item per high/medium finding key. `save_action_item`
    de-dupes on subject + category while a matching item is open."""
    from .database import save_action_item
    from .timezone_utils import today_central_str
    filed = []
    for f in findings:
        if f["severity"] not in ("high", "medium") or f.get("file") is False:
            continue
        subject = f"HEALTH: {f['key']}"
        try:
            row = save_action_item({
                "subject": subject, "from_name": ACTION_FROM,
                "summary": f"{f['text']} — from the daily Tracker Health digest "
                           f"({today_central_str()}). Details: /admin/health.",
                "urgency": f["severity"], "category": "other",
                "email_date": today_central_str(), "confidence": 100,
            }, db_path=db_path)
            filed.append({"subject": subject, "id": row.get("id"),
                          "existing": row.get("summary", "").find(today_central_str()) < 0})
        except Exception:
            logger.warning("health: action item for %s not filed", f["key"], exc_info=True)
    return filed


def run_health_digest(post: bool = True, days: float = 1, db_path=None) -> dict:
    """Build, post, file, prune. `post=False` builds and returns the text
    without writing anything but the size history (the bridge's dry run)."""
    from .database import log_agent_action, post_platform_dialogue_entry, set_app_setting
    from .timezone_utils import today_central_str
    db_path = perf._db_path(db_path)
    try:
        perf.flush(db_path)
    except Exception:
        logger.debug("health: flush before digest failed", exc_info=True)
    report = build_health_report(days, db_path=db_path, record_size=post)
    body = render_markdown(report)
    out = {"posted": None, "action_items": [], "pruned": 0,
           "findings": report["findings"], "body": body}
    if not post:
        return out
    try:
        entry = post_platform_dialogue_entry(DIGEST_AUTHOR, body, DIGEST_TOPIC,
                                             db_path=db_path)
        out["posted"] = entry.get("id") if isinstance(entry, dict) else entry
    except TypeError:
        entry = post_platform_dialogue_entry(DIGEST_AUTHOR, body, DIGEST_TOPIC)
        out["posted"] = entry.get("id") if isinstance(entry, dict) else entry
    except Exception:
        logger.exception("health: mailbox post failed")
    out["action_items"] = file_action_items(report["findings"], db_path=db_path)
    try:
        out["pruned"] = perf.prune(db_path=db_path)
    except Exception:
        logger.debug("health: prune failed", exc_info=True)
    try:
        set_app_setting("health_digest_last", today_central_str(), db_path=db_path)
        n_hi = sum(1 for f in report["findings"] if f["severity"] == "high")
        log_agent_action(AGENT_NAME, "daily_digest",
                         f"{len(report['findings'])} finding(s), {n_hi} high; "
                         f"{report['sample_count']} samples; mailbox #{out['posted']}",
                         db_path=db_path)
    except Exception:
        logger.debug("health: bookkeeping failed", exc_info=True)
    return out


def digest_due(now=None, db_path=None) -> bool:
    """True when today's digest has not been posted and the dialled time
    has passed — the 15-minute check calls this, so changing the dial
    takes effect without a restart."""
    from .database import get_app_setting
    from .timezone_utils import now_central, today_central_str
    now = now or now_central()
    hh, mm = digest_time(db_path).split(":")
    if (now.hour, now.minute) < (int(hh), int(mm)):
        return False
    try:
        last = get_app_setting("health_digest_last", db_path=db_path)
    except Exception:
        last = None
    return last != today_central_str()


def health_digest_check(db_path=None) -> dict | None:
    """The scheduled entry point: runs the digest once per day, at or
    after the dialled time."""
    if not digest_due(db_path=db_path):
        return None
    return run_health_digest(post=True, db_path=db_path)


# ── closing what the digest filed ───────────────────────────────────────
def ack_findings(item_ids, note: str, by: str = AGENT_NAME, db_path=None) -> dict:
    """Close HEALTH action items the digest filed, with the reason on the
    row (never deleted; `resolution_notes` + `completed_by`). Only items
    whose subject starts with "HEALTH:" — other lanes' items are theirs.
    The scoring-health-ack bridge and the 5:10 AM CTO routine use this
    after a finding is fixed or explained (9/23: the disk-I/O errors
    resolved by the volume resize)."""
    from .database import _connect, update_action_item, log_agent_action
    from .timezone_utils import now_central
    closed, refused = [], []
    with _connect(db_path) as conn:
        for iid in item_ids:
            row = conn.execute("SELECT id, subject, status FROM action_items WHERE id = ?",
                               (int(iid),)).fetchone()
            if not row or not str(row["subject"] or "").startswith("HEALTH:"):
                refused.append({"id": int(iid), "why": "not a HEALTH item" if row else "no such item"})
                continue
            if row["status"] in ("completed", "dismissed"):
                refused.append({"id": int(iid), "why": f"already {row['status']}"})
                continue
            closed.append(int(iid))
    for iid in closed:
        update_action_item(iid, {"status": "completed",
                                 "completed_at": now_central().strftime("%Y-%m-%d %H:%M:%S"),
                                 "completed_by": by,
                                 "resolution_notes": (note or "")[:1000]}, db_path=db_path)
    if closed:
        try:
            log_agent_action(by, "health_ack", f"closed {closed}: {(note or '')[:200]}", db_path=db_path)
        except Exception:
            logger.debug("health ack log failed", exc_info=True)
    return {"closed": closed, "refused": refused}
