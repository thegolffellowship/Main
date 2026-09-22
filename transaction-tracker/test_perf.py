"""The Tracker measures itself (email_parser/perf.py, Tracker Health lane
2026-09-22): the shared stopwatch, the perf_samples table, the flusher,
the slow line, the route / job / bridge wrappers — and the PAIRINGS open
fixes that came out of the first profile (the roster read once, the
handicap cache actually hitting, no Golf Genius wait on a read, the
roster builder's indexes).

Run: python3 test_perf.py
"""
import os, sys, sqlite3, tempfile, contextlib, io, logging, json, time
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-perf-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PIN", "0000")
os.environ.pop("EMAIL_ADDRESS", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402
from email_parser import perf  # noqa: E402
logging.getLogger("email_parser.database").setLevel(logging.ERROR)
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
perf._DB_PATH_OVERRIDE = tmp
perf.DISABLED = False


def rows(name=None):
    c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
    q = "SELECT * FROM perf_samples" + (" WHERE name = ?" if name else "") + " ORDER BY id"
    out = [dict(r) for r in c.execute(q, (name,) if name else ())]
    c.close()
    return out


print("\n== the stopwatch and the table ==")
c = sqlite3.connect(tmp)
check("init_db created perf_samples with its two indexes",
      c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name IN ('perf_samples','idx_perf_samples_at','idx_perf_samples_name_at')").fetchone()[0] == 3)
c.close()
sw = perf.Stopwatch("route", "unit_a", slow_ms=10_000, event_id=42, role="admin")
time.sleep(0.01); sw.lap("one"); time.sleep(0.005); sw.lap("two")
snap = sw.snapshot()
check("snapshot carries the laps and their sum", set(snap) == {"one", "two", "total"} and snap["total"] == snap["one"] + snap["two"], str(snap))
sw.note(http=200)
out = sw.finish()
check("finish returns the true total (>= the laps)", out["total"] >= snap["total"], str(out))
check("nothing is on disk until a flush — the request thread never writes", rows("unit_a") == [])
n = perf.flush(tmp)
r = rows("unit_a")
check("flush writes the queued sample", n == 1 and len(r) == 1, str((n, r)))
r = r[0]
check("...kind, name, event_id, role, status ok", (r["kind"], r["name"], r["event_id"], r["role"], r["status"]) == ("route", "unit_a", 42, "admin", "ok"), str(r))
bd = json.loads(r["breakdown"])
check("...breakdown JSON has the laps (and the tail as _rest if any)", bd["one"] >= 9 and "two" in bd, str(bd))
d = json.loads(r["detail"])
check("...detail carries the note and the load average", d.get("http") == 200 and "load1" in d, str(d))

print("\n== SLOW: status + the agent_action_log row Kerry reads ==")
sw = perf.Stopwatch("route", "unit_slow", slow_ms=1, event_id=7)
time.sleep(0.01); sw.lap("busy"); sw.finish()
perf.flush(tmp)
r = rows("unit_slow")[0]
check("over the line → status slow", r["status"] == "slow", r["status"])
logrow = db.get_agent_action_log(agent_name="app", limit=5, db_path=tmp)
check("...and a `unit_slow_slow` row in agent_action_log naming the event and the worst section",
      any(x["action_type"] == "unit_slow_slow" and "event 7" in x["description"] and "busy" in x["description"] for x in logrow), str(logrow))

print("\n== errors, concurrency, discard ==")
try:
    with perf.Stopwatch("job", "unit_job_err", slow_ms=10_000) as sw:
        raise RuntimeError("boom")
except RuntimeError:
    pass
perf.flush(tmp)
r = rows("unit_job_err")[0]
check("an exception inside the context → status error, message in detail, exception re-raised",
      r["status"] == "error" and "boom" in json.loads(r["detail"])["error"] and r["role"] == "scheduler", str(r))
outer = perf.Stopwatch("job", "unit_outer", slow_ms=10_000)
inner = perf.Stopwatch("route", "unit_inner", slow_ms=10_000)
inner.finish(); outer.finish(); perf.flush(tmp)
r = rows("unit_inner")[0]
check("a sample records what else was running when it started (job:unit_outer)",
      json.loads(r["detail"]).get("concurrent") == ["job:unit_outer"], r["detail"])
sw = perf.Stopwatch("bridge", "unit_discard"); sw.discard(); perf.flush(tmp)
check("discard leaves no row and no in-flight entry", rows("unit_discard") == [] and id(sw) not in perf._INFLIGHT)

print("\n== thresholds: rules as data ==")
check("a named path has its own line (pairings_get 4 s)", perf.slow_threshold("route", "pairings_get", tmp) == 4000)
check("an unknown route takes the kind default", perf.slow_threshold("route", "nope", tmp) == perf.SLOW_MS_DEFAULT["route"])
db.set_app_setting("perf_slow_ms", json.dumps({"pairings_get": 999}), db_path=tmp)
perf._SLOW_DIAL["at"] = 0
check("the perf_slow_ms dial overrides it without a deploy", perf.slow_threshold("route", "pairings_get", tmp) == 999)
db.set_app_setting("perf_slow_ms", "", db_path=tmp); perf._SLOW_DIAL["at"] = 0

print("\n== summary / prune ==")
for v in (10, 20, 30, 40, 1000):
    perf.record("route", "unit_pct", v, db_path=tmp)
perf.flush(tmp)
s = perf.summary(1, db_path=tmp)
row = next(x for x in s["route"] if x["name"] == "unit_pct")
check("p50 / p95 / max / count over the window", (row["count"], row["p50"], row["max"]) == (5, 30, 1000) and 900 < row["p95"] <= 1000, str(row))
c = sqlite3.connect(tmp)
c.execute("INSERT INTO perf_samples (at, kind, name, total_ms) VALUES ('2020-01-01 00:00:00', 'route', 'old', 1)"); c.commit(); c.close()
check("prune removes samples past the retention window and nothing newer", perf.prune(db_path=tmp) == 1 and rows("old") == [] and rows("unit_pct"))

print("\n== the wrappers ==")
from flask import Flask, jsonify  # noqa: E402
tapp = Flask("t")


@tapp.route("/ok")
@perf.timed_route("unit_view", slow_ms=10_000)
def _ok():
    perf.current().lap("a")
    return jsonify({"timings_ms": perf.current().snapshot()})


@tapp.route("/boom")
@perf.timed_route("unit_view_boom", slow_ms=10_000)
def _boom():
    raise ValueError("nope")


tc = tapp.test_client()
r = tc.get("/ok"); perf.flush(tmp)
check("timed_route: the view sees its stopwatch via perf.current() and the sample lands",
      r.status_code == 200 and "a" in r.get_json()["timings_ms"] and rows("unit_view")[0]["status"] == "ok")
check("...and current() is cleared after the view", perf.current() is None)
r = tc.get("/boom"); perf.flush(tmp)
check("timed_route: an exception → status error, and Flask still answers 500",
      r.status_code == 500 and rows("unit_view_boom")[0]["status"] == "error")


def job_fn():
    return 5


w = perf.timed_job(job_fn, "unit_job")
check("timed_job returns the value and is idempotent", w() == 5 and perf.timed_job(w) is w)
perf.flush(tmp)
check("...one job sample per run, role scheduler", rows("unit_job")[0]["role"] == "scheduler")

print("\n== the app: pairings GET, scheduler, bridges ==")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as appmod
    import mcp_server as mcp
perf._DB_PATH_OVERRIDE = tmp
c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
EV, COURSE = 4200, 9200
c.execute("INSERT INTO courses (course_id, name, short_name, status) VALUES (?, 'Brackenridge Park Golf Course', 'Brackenridge', 'active')", (COURSE,))
c.execute("INSERT INTO events (id, item_name, event_date, chapter, course, course_id, status, format, nine_side) "
          "VALUES (?, 's9.24 Brackenridge', date('now'), 'San Antonio', 'Brackenridge Park Golf Course', ?, 'active', '9 Holes', 'Front')", (EV, COURSE))
players = [(301, "Pat", "Youngs", 4.0), (302, "Kerry", "Niester", 6.0), (303, "Nic", "Skinner", 8.0), (304, "Luke", "Mazanec", 10.0),
           (305, "Bear", "Clarkson", 12.0), (306, "Gus", "Vasquez", 14.0)]
for i, (cid, f, l, idx) in enumerate(players):
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status, current_player_status) VALUES (?, ?, ?, 'San Antonio', 'active', 'active_member')", (cid, f, l))
    c.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES (?, ?, ?)", (f"{l}, {f}", f"{f} {l}", cid))
    for _d in (10, 20, 30):
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) VALUES (?, date('now', ?), 45, 34.5, 120, ?)", (f"{l}, {f}", f"-{_d} days", idx / 2))
    c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, side_games, user_status, tee_choice) "
              "VALUES (?, ?, 'The Golf Fellowship', ?, ?, 's9.24 Brackenridge', '2026-09-10', 'active', ?, 'BOTH', 'MEMBER', '<50')", (800 + i, f"u{800+i}", f"{f} {l}", cid, EV))
db._ensure_pairing_tables(c)
for pos, (cid, f, l, _) in enumerate(players[:4]):
    c.execute("INSERT INTO event_pairings (event_id, holes, group_num, slot_label, player_name, cart_pos, customer_id) VALUES (?, '9', 1, '1A', ?, ?, ?)", (EV, f"{f} {l}", pos + 1, cid))
c.commit()

sig1, sig2 = db._hcp_players_signature(tmp), db._hcp_players_signature(tmp)
check("the handicap cache signature is STABLE between two reads (v2.484.3's never was — hcp_exclude is on scoring_rounds)",
      sig1 == sig2 and sig1[0] != "nosig", str(sig1))
db._HCP_PLAYERS_CACHE.clear(); db._HCP_CACHE_STATS.update(hits=0, misses=0)
db.get_all_handicap_players(tmp); db.get_all_handicap_players(tmp)
check("...so the second read is a cache HIT", db._HCP_CACHE_STATS == {"hits": 1, "misses": 1}, str(db._HCP_CACHE_STATS))
p1 = db.get_all_handicap_players(tmp); p1[0]["handicap_index"] = -99
check("...and callers still get their own copy", db.get_all_handicap_players(tmp)[0]["handicap_index"] != -99)
c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) VALUES ('Youngs, Pat', date('now'), 45, 34.5, 120, 1.0)"); c.commit()
check("a posted round changes the signature (the next read recomputes)", db._hcp_players_signature(tmp) != sig1)

conn = db.get_connection(tmp)
roster = db._event_roster_rows(conn, EV)
a = db.get_event_pairings(EV, db_path=tmp)
b = db.get_event_pairings(EV, db_path=tmp, roster_rows=roster, hcp_map=db._roster_handicap_index_map(conn, db_path=tmp))
check("get_event_pairings with the roster + index map passed in answers exactly as without", a == b, str((a, b)))
pa = db.event_blind_pool(conn, EV, db_path=tmp)
pb = db.event_blind_pool(conn, EV, db_path=tmp, roster_rows=roster)
check("event_blind_pool with the roster passed in answers exactly as without", pa == pb)
check("detect_match_play_pairings / get_event_partner_requests accept the roster too",
      db.detect_match_play_pairings(EV, db_path=tmp, roster_rows=roster)["event_id"] == EV
      and db.get_event_partner_requests(EV, db_path=tmp, roster_rows=roster) is not None)
for ix in ("idx_items_customer_id", "idx_items_item_name_nocase", "idx_handicap_player_links_customer"):
    check(f"index {ix} exists", conn.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (ix,)).fetchone() is not None)
ph = ",".join("?" * len(db.PAIRING_INACTIVE_STATUSES))
plan = " | ".join(r[3] for r in conn.execute(f"""EXPLAIN QUERY PLAN SELECT i.id, (SELECT COUNT(*) FROM items i3 WHERE i3.customer_id = i.customer_id) FROM events e
    LEFT JOIN event_aliases ea ON ea.canonical_event_name = e.item_name
    JOIN items i ON (i.item_name = e.item_name COLLATE NOCASE OR i.item_name = ea.alias_name COLLATE NOCASE OR i.event_id = e.id)
    WHERE e.id = ? AND COALESCE(i.transaction_status, 'active') NOT IN ({ph})""", (EV, *db.PAIRING_INACTIVE_STATUSES)))
check("the roster join's three arms and the orders count all use an index (no SCAN of items)",
      "SCAN i" not in plan and "idx_items_item_name_nocase" in plan and "idx_items_customer_id" in plan, plan)
conn.close()

# no_network never waits — even with no snapshot at all
called = {"sync": 0, "queued": 0}
_orig_refresh, _orig_queue = db.refresh_points_race_standings, db._queue_points_refresh
db.refresh_points_race_standings = lambda *a, **k: called.__setitem__("sync", called["sync"] + 1)
db._queue_points_refresh = lambda *a, **k: (called.__setitem__("queued", called["queued"] + 1), True)[1]
try:
    race = next(iter(db._GG_POINTS_RACES))
    res = db.get_points_race_standings(race, db_path=tmp, no_network=True)
finally:
    db.refresh_points_race_standings, db._queue_points_refresh = _orig_refresh, _orig_queue
check("get_points_race_standings(no_network=True) with NO snapshot queues the refresh and does not fetch inline",
      called == {"sync": 0, "queued": 1} and res.get("refresh_queued") is True, str((called, res.get("refresh_queued"))))

client = appmod.app.test_client()
with client.session_transaction() as s:
    s["role"] = "manager"; s["authenticated"] = True
r = client.get(f"/api/events/{EV}/pairings")
tm = (r.get_json() or {}).get("timings_ms") or {}
check("the pairings GET answers with timings_ms on the shared stopwatch (connect, index_map, roster_rows, saved_sheet … blind_pool)",
      r.status_code == 200 and {"connect", "index_map", "roster_rows", "saved_sheet", "standings", "blind_pool", "total"} <= set(tm), str(tm))
perf.flush(tmp)
pr = rows("pairings_get")
check("...and one perf_samples row per open, kind route, the event id on it, the role on it",
      len(pr) == 1 and pr[0]["kind"] == "route" and pr[0]["event_id"] == EV and pr[0]["role"] == "manager", str(pr))
for url, name in (("/api/events", "events_list"), ("/api/items", "items_list"), (f"/api/items?event_id={EV}", "items_event"),
                  (f"/api/events/{EV}", "event_one"), ("/api/handicaps/index-map", "hcp_index_map"), ("/api/rsvps/bulk", "rsvps_bulk"),
                  (f"/api/events/{EV}/flights-board", "flights_board")):
    client.get(url)
perf.flush(tmp)
have = {r["name"] for r in rows()}
check("the EVENTS landing loads + roster reads + flights board are sampled under their names",
      {"events_list", "items_list", "items_event", "event_one", "hcp_index_map", "rsvps_bulk", "flights_board"} <= have, str(sorted(have)))
check("timed_route keeps Flask endpoint names (functools.wraps)", "api_get_pairings" in appmod.app.view_functions)

j = appmod.scheduler.add_job(job_fn, "date", id="unit_sched_job", replace_existing=True)
check("every scheduler.add_job wraps the callable in timed_job", getattr(j.func, "_perf_job", False) is True)
appmod.scheduler.remove_job("unit_sched_job")

with client.session_transaction() as s:
    s["role"] = "admin"
r = client.get("/api/admin/health?days=1")
check("/api/admin/health (admin) serves the report", r.status_code == 200 and "summary" in r.get_json() and r.get_json()["sample_count"] > 0)
r = client.get("/admin/health")
check("/admin/health renders for an admin", r.status_code == 200 and b"Tracker Health" in r.data)
with client.session_transaction() as s:
    s["role"] = "manager"
check("...and redirects a manager (never a JSON 403 on a page)", client.get("/admin/health").status_code == 302)
check("/health is still the unauthenticated Railway probe", client.get("/health").status_code == 200)

out = mcp._scoring_dispatch("", "scoring-health:1")
rep = json.loads(out)
check("bridge scoring-health[:<days>] returns the report", "findings" in rep and rep["window_days"] == 1)
perf.flush(tmp)
check("...and the bridge call itself is a sample (kind bridge, name scoring-health)", any(r["kind"] == "bridge" and r["name"] == "scoring-health" for r in rows()))
check("a non-bridge extract leaves no sample", mcp._scoring_dispatch("https://x.golfgenius.com/p", "summary") is None and not any(r["name"] == "summary" for r in rows()))
c.close()

print()
if F:
    print(f"{len(F)} FAILED: " + "; ".join(F))
    sys.exit(1)
print("ALL PASS")
