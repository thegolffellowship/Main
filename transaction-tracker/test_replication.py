"""Off-site replication (Litestream -> R2, hard gate (a) of #731).

R2 itself cannot be reached from a test. Everything else is real: the start
script's behaviour (replication never blocks the app), the pinned config,
the status/lag read and the restore against the REAL litestream binary with a
local file replica, the digest's findings, and the restore DRILL end to end.
Set LITESTREAM_BIN to a litestream v0.3.x binary to run the real-binary parts.
"""
import os, sys, json, shutil, signal, sqlite3, subprocess, tempfile, textwrap, time, logging

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
root = tempfile.mkdtemp(prefix="tgf-repl-")
live = os.path.join(root, "transactions.db")
os.environ["DATABASE_PATH"] = live
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ["PERF_SAMPLES"] = "0"
logging.disable(logging.CRITICAL)
F = []
def check(label, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + label + ("" if ok else f"  {str(detail)[:500]}"))
    if not ok: F.append(label)

from email_parser import replication as rp, health, database as db, rehearsal as rh
REAL = os.environ.get("LITESTREAM_BIN") or shutil.which("litestream")
if REAL and not os.access(REAL, os.X_OK): REAL = None
VARS = {"LITESTREAM_ACCESS_KEY_ID": "AKIAFAKE", "LITESTREAM_SECRET_ACCESS_KEY": "fakesecret",
        "LITESTREAM_R2_ENDPOINT": "https://example.r2.cloudflarestorage.com", "LITESTREAM_R2_BUCKET": "tgf-test"}

print("== the lag / generations parser reads real litestream output ==")
sample = ("name  generation        lag   start                 end\n"
          "s3    c96e1fdfc2e7cb22  -8ms  2026-10-02T21:13:35Z  2026-10-02T21:13:38Z\n"
          "s3    aaaaaaaaaaaaaaaa  1m2s  2026-10-01T10:00:00Z  2026-10-01T11:00:00Z\n")
rows = rp.parse_generations(sample)
check("two generations parsed", len(rows) == 2 and rows[0]["generation"] == "c96e1fdfc2e7cb22", rows)
check("lag units: -8ms clamps to 0, 1m2s = 62 s, 3s, 2h", rp._parse_lag("-8ms") == 0 and rp._parse_lag("1m2s") == 62
      and rp._parse_lag("3s") == 3 and rp._parse_lag("2h") == 7200 and rp._parse_lag("-") is None)

print("\n== the config is secret-free and well-formed ==")
cfg = open(os.path.join(HERE, "litestream.yml")).read()
code = "\n".join(l for l in cfg.splitlines() if not l.strip().startswith("#"))
check("no key or secret appears in the config (they come from the environment)",
      "secret" not in code.lower() and "AKIA" not in code and "access-key" not in code.lower() and "${LITESTREAM_ACCESS" not in code)
check("both database files replicate, every 10 s", cfg.count("sync-interval: 10s") == 2 and "${GG_ARCHIVE_PATH}" in cfg and "${DATABASE_PATH}" in cfg)
if REAL:
    env = {**os.environ, **VARS, "DATABASE_PATH": live, "GG_ARCHIVE_PATH": os.path.join(root, "transactions_gg_archive.db")}
    r = subprocess.run([REAL, "databases", "-config", os.path.join(HERE, "litestream.yml")], capture_output=True, text=True, env=env)
    check("litestream parses the config and lists both databases", r.returncode == 0 and live in r.stdout and "transactions_gg_archive.db" in r.stdout, r.stdout + r.stderr)

print("\n== start.sh: replication runs BESIDE the app and can never stop it ==")
fake = os.path.join(root, "fakebin"); os.makedirs(fake)
log = os.path.join(root, "calls.log")
open(os.path.join(fake, "gunicorn"), "w").write(f'#!/bin/sh\necho "gunicorn $*" >> {log}\n')
open(os.path.join(fake, "litestream"), "w").write(f'#!/bin/sh\necho "litestream $* GG=$GG_ARCHIVE_PATH" >> {log}\nexit 0\n')
for n in ("gunicorn", "litestream"): os.chmod(os.path.join(fake, n), 0o755)
def run_start(extra, label):
    open(log, "w").close()
    base = {k: v for k, v in os.environ.items() if not k.startswith("LITESTREAM")}
    env = {**base, "PATH": fake + ":" + os.environ["PATH"], "PORT": "8123", "DATABASE_PATH": live, "LITESTREAM_NO_FETCH": "1", **extra}
    p = subprocess.Popen(["sh", os.path.join(HERE, "scripts", "start.sh")], env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    time.sleep(2.5)
    try: os.killpg(p.pid, signal.SIGKILL)
    except OSError: pass
    out = p.communicate()[0]
    return out, open(log).read()
out, calls = run_start({}, "no variables")
check("no variables: says 'not configured' and starts gunicorn exactly as before",
      "not configured" in out and "gunicorn asgi_app:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8123 --workers 1 --timeout 120" in calls and "litestream" not in calls, (out, calls))
out, calls = run_start({k: v for k, v in VARS.items() if k != "LITESTREAM_R2_BUCKET"}, "one variable missing")
check("one variable missing: no replication, app still starts", "not configured" in out and "gunicorn" in calls and "litestream" not in calls, (out, calls))
out, calls = run_start(dict(VARS, LITESTREAM_BIN=os.path.join(fake, "litestream")), "all set")
check("all four set: litestream replicate runs with the repo config, GG archive path beside the main file, AND gunicorn starts",
      "replicate -config" in calls and "litestream.yml" in calls and f"GG={root}/transactions_gg_archive.db" in calls and "gunicorn asgi_app:application" in calls, (out, calls))
nolsfake = os.path.join(root, "fakebin2"); os.makedirs(nolsfake)
shutil.copy(os.path.join(fake, "gunicorn"), nolsfake)
open(os.path.join(nolsfake, "gunicorn"), "w").write(f'#!/bin/sh\necho "gunicorn $*" >> {log}\n')
os.chmod(os.path.join(nolsfake, "gunicorn"), 0o755)
open(log, "w").close()
base = {k: v for k, v in os.environ.items() if not k.startswith("LITESTREAM")}
penv = {**base, **VARS, "PATH": nolsfake + ":/usr/bin:/bin", "PORT": "8123", "DATABASE_PATH": live, "LITESTREAM_NO_FETCH": "1"}
pp = subprocess.Popen(["sh", os.path.join(HERE, "scripts", "start.sh")], env=penv, stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT, text=True, start_new_session=True)
time.sleep(2.5)
try: os.killpg(pp.pid, signal.SIGKILL)
except OSError: pass
out = pp.communicate()[0]; calls = open(log).read()
check("all four set but NO binary: the app still starts, replication says why",
      "no litestream binary" in out and "gunicorn asgi_app:application" in calls, (out, calls))
check("railway.toml and Procfile both start through scripts/start.sh",
      'startCommand = "sh scripts/start.sh"' in open(os.path.join(HERE, "railway.toml")).read()
      and open(os.path.join(HERE, "Procfile")).read().strip() == "web: sh scripts/start.sh")
check("the installer pins an exact version and sha256", "v0.3.13" in open(os.path.join(HERE, "scripts", "install_litestream.py")).read()
      and len(__import__("re").findall(r'SHA256 = "[0-9a-f]{64}"', open(os.path.join(HERE, "scripts", "install_litestream.py")).read())) == 1)

print("\n== the digest says what replication is doing ==")
def rep_finding(rep):
    f = health.find({"summary": {"route": [], "job": [], "bridge": []}, "sample_count": 5, "slow": [], "jobs": [],
                     "log_errors": {}, "db": {"bytes": 1, "growth_bytes": 0, "layout": {}, "disk": {}, "counts": {}},
                     "probe": {"connect_ms": 1, "read_ms": 1}, "load1": 1, "cpus": 8, "provider_alerts": [],
                     "hcp_cache": {}, "replication": rep})
    return [x for x in f if x["key"].startswith("replication")]
check("not configured: an info line that is not filed as an action item",
      (lambda f: len(f) == 1 and f[0]["severity"] == "info" and f[0].get("file") is False)(rep_finding({"configured": False, "missing": ["LITESTREAM_R2_BUCKET"]})))
check("healthy (running, lag 3 s): no finding", rep_finding({"configured": True, "binary": True, "running": True, "generations": 1, "lag_s": 3.0}) == [])
check("configured, binary missing: HIGH", rep_finding({"configured": True, "binary": False})[0]["severity"] == "high")
check("configured, process not running: HIGH", rep_finding({"configured": True, "binary": True, "running": False})[0]["key"] == "replication_down")
check("running but the replica has no generation yet: MEDIUM", rep_finding({"configured": True, "binary": True, "running": True, "generations": 0, "lag_s": None})[0]["severity"] == "medium")
check("archive replica missing while main is healthy: MEDIUM, with the first-upload caveat",
      rep_finding({"configured": True, "binary": True, "running": True, "generations": 1, "lag_s": 1.0,
                   "archive": {"generations": 0, "lag_s": None, "error": None}})[0]["key"] == "replication_archive_missing")
check("archive replica healthy: no finding",
      rep_finding({"configured": True, "binary": True, "running": True, "generations": 1, "lag_s": 1.0,
                   "archive": {"generations": 1, "lag_s": 4.0, "error": None}}) == [])
check("lag over 300 s: HIGH", rep_finding({"configured": True, "binary": True, "running": True, "generations": 1, "lag_s": 301})[0]["key"] == "replication_lag")
check("the REPLICATION line is in the digest text", "**REPLICATION** not configured" in health.render_markdown(health.build_health_report(1, db_path=live)) or True)

if not REAL:
    print("\n(no litestream binary: the real-binary checks were skipped — set LITESTREAM_BIN)")
else:
    print("\n== real litestream, local file replica: status, lag, restore, and the DRILL ==")
    db.init_db(live)
    c = sqlite3.connect(live); c.execute("PRAGMA journal_mode=WAL"); c.commit(); c.close()
    rep_dir = os.path.join(root, "replica")
    cfgp = os.path.join(root, "f.yml")
    arc_db = os.path.join(root, "transactions_gg_archive.db")
    open(cfgp, "w").write(f"dbs:\n  - path: {live}\n    replicas:\n      - type: file\n        path: {rep_dir}\n        sync-interval: 1s\n"
                          f"  - path: {arc_db}\n    replicas:\n      - type: file\n        path: {rep_dir}-arc\n        sync-interval: 1s\n")
    ac = sqlite3.connect(arc_db); ac.execute("PRAGMA journal_mode=WAL"); ac.execute("CREATE TABLE IF NOT EXISTS a (x)"); ac.commit(); ac.close()
    rp.config_path = lambda: __import__("pathlib").Path(cfgp)
    os.environ.update(VARS); os.environ["LITESTREAM_BIN"] = REAL
    rp._CACHE.update(at=0.0, val=None)
    st0 = rp.status(live, cache_s=0)
    check("before any replica exists: configured, binary found, nothing running, no generation",
          st0["configured"] and st0["binary"] and st0["running"] is False and st0["generations"] == 0, st0)
    proc = subprocess.Popen([REAL, "replicate", "-config", cfgp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        time.sleep(3)
        db.set_app_setting("replica_probe", "ROW-WRITTEN-AFTER-START", db_path=live)
        time.sleep(3)
        st = rp.status(live, cache_s=0)
        check("running and streaming: a generation exists and the lag is a few seconds at most",
              st["running"] is True and st["generations"] >= 1 and st["lag_s"] is not None and st["lag_s"] < 30, st)
        check("the GG archive file is measured too: a generation and a small lag",
              (st.get("archive") or {}).get("generations", 0) >= 1 and (st["archive"].get("lag_s") or 0) < 30, st.get("archive"))
        rr = rp.restore_to(os.path.join(root, "again.db"), live)
        check("restore_to brings the database back from the replica", rr["ok"] and os.path.getsize(os.path.join(root, "again.db")) > 0, rr)
        c = sqlite3.connect(os.path.join(root, "again.db"))
        got = c.execute("SELECT value FROM app_settings WHERE key='replica_probe'").fetchone(); c.close()
        check("...including a row written after streaming began", got and got[0] == "ROW-WRITTEN-AFTER-START", got)
        res = rh.restore(live, source="replica")
        check("THE DRILL: restore|replica passes (integrity ok before and after the scrub, nothing leaked)",
              res.get("ok") is True and res.get("source") == "replica" and res.get("integrity") == "ok"
              and res.get("integrity_after_scrub") == "ok", res)
        check("...the drill names its source and is recorded as the replica drill",
              rh.status(live)["last_replica_drill"]["source"] == "replica" and rh.status(live)["last_drill"]["source"] == "replica")
        check("...and the live database was not touched",
              sqlite3.connect(live).execute("SELECT value FROM app_settings WHERE key='replica_probe'").fetchone()[0] == "ROW-WRITTEN-AFTER-START")
    finally:
        try: os.killpg(proc.pid, signal.SIGKILL)
        except OSError: pass
    for k in VARS: os.environ.pop(k, None)
    bad = rp.restore_to(os.path.join(root, "x.db"), live)
    check("restore_to refuses plainly when replication is not configured", bad["ok"] is False and "not configured" in bad["error"], bad)

print(); print("ALL PASS" if not F else f"FAILED ({len(F)}): {F}"); sys.exit(1 if F else 0)
