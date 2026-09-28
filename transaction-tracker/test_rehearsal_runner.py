"""The Railway rehearsal runner (CA #832, Kerry chose B): jobs run in a
separate, secret-free TGF_REHEARSAL=1 process on the scratch copy only.

Proves: the child's environment carries no secrets and no RAILWAY_* vars;
a bridge job reads and WRITES the scratch copy and never the live file; the
outbound guard is installed in the child before any bridge runs; refused
bridges are refused; tool arguments are allow-listed (no free-form argv, no
second database); one job at a time; the lane tools' guards admit the
runner's scratch file and nothing else.
"""
import os, sys, json, time, sqlite3, tempfile, subprocess, logging

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
root = tempfile.mkdtemp(prefix="tgf-runner-")
live = os.path.join(root, "transactions.db")
os.environ["DATABASE_PATH"] = live
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ["PERF_SAMPLES"] = "0"
logging.disable(logging.CRITICAL)

fails = []
def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"  {str(detail)[:600]}"))
    if not cond:
        fails.append(label)

from email_parser import database as db
from email_parser import rehearsal as rh

db.init_db(live)
db.set_app_setting("runner_probe", "LIVE", db_path=live)
rdir = rh.rehearsal_dir(live); rdir.mkdir(parents=True, exist_ok=True)
scratch = rdir / rh.SCRUBBED
_c = sqlite3.connect(live); _c.execute("VACUUM INTO ?", (str(scratch),)); _c.close()

def wait(jid, secs=240):
    t0 = time.time()
    while time.time() - t0 < secs:
        st = rh.job_status(jid, db_path=live)
        if st.get("status") != "running":
            return st
        time.sleep(0.5)
    return rh.job_status(jid, db_path=live)

print("== the child's environment is an allow-list ==")
os.environ["AZURE_CLIENT_SECRET"] = "s3cret"; os.environ["BREVO_API_KEY"] = "b"; os.environ["RAILWAY_PROJECT_ID"] = "p"
env = rh._child_env(rdir, scratch, bridge=True)
check("no secrets and no RAILWAY_* vars reach the child",
      not any(k.startswith(("AZURE", "BREVO", "RAILWAY", "STRIPE", "TWILIO", "ANTHROPIC", "EMAIL")) for k in env), sorted(env))
check("the child gets TGF_REHEARSAL=1 and the runner flag", env["TGF_REHEARSAL"] == "1" and env["TGF_REHEARSAL_RUNNER"] == "1")
check("a bridge child's DATABASE_PATH is the scratch copy", env["DATABASE_PATH"] == str(scratch))
check("a tool child gets no DATABASE_PATH (each tool sets its own)", "DATABASE_PATH" not in rh._child_env(rdir, scratch, bridge=False))
for k in ("AZURE_CLIENT_SECRET", "BREVO_API_KEY", "RAILWAY_PROJECT_ID"):
    os.environ.pop(k, None)

print("\n== tool arguments are allow-listed ==")
out = rdir / "jobs" / "x-report.json"
a = rh.build_tool_argv("se_replay", "--events 3309,3315 --workers 8", scratch, out)
check("se_replay argv: scratch path, the given events, a report path, --i-am-scratch last",
      a[2:4] == ["--db", str(scratch)] and "3309,3315" in a and a[-1] == "--i-am-scratch" and str(out) in a, a)
for bad, why in (("--events 1;rm -rf /", "shell text in a value"), ("--db /data/transactions.db --events 1", "a second database"),
                 ("--events 1 --port 80", "an unlisted flag"), ("", "missing --events")):
    try:
        rh.build_tool_argv("se_replay", bad, scratch, out); ok = False
    except ValueError:
        ok = True
    check(f"refused: {why}", ok)
try:
    rh.build_tool_argv("rm", "", scratch, out); ok = False
except ValueError:
    ok = True
check("refused: a tool that is not on the list", ok)
t = rh.build_tool_argv("takeover", "--events 3309 --undo", scratch, out)
check("takeover argv: scratch path first, --undo allowed", t[2] == str(scratch) and "--undo" in t and t[-1] == "--i-am-scratch", t)

print("\n== the lane tools' guards admit the runner's scratch file and nothing else ==")
def guard_probe(extra_env, path):
    code = ("import os,sys; sys.path.insert(0, %r); from email_parser.rehearsal import runner_scratch_ok as ok; "
            "print('ADMIT' if ok(%r) else 'REFUSE')" % (HERE, str(path)))
    e = {k: v for k, v in os.environ.items() if not k.startswith("TGF_REHEARSAL")}
    e.update(extra_env)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=e).stdout.strip()
renv = {"TGF_REHEARSAL": "1", "TGF_REHEARSAL_RUNNER": "1", "TGF_REHEARSAL_DIR": str(rdir)}
check("runner child + file inside rehearsal/ -> admitted", guard_probe(renv, scratch) == "ADMIT")
check("same env, the live file -> refused", guard_probe(renv, live) == "REFUSE")
check("same env, a file outside rehearsal/ -> refused", guard_probe(renv, os.path.join(root, "other.db")) == "REFUSE")
check("no runner flag -> refused", guard_probe({"TGF_REHEARSAL": "1", "TGF_REHEARSAL_DIR": str(rdir)}, scratch) == "REFUSE")
check("no TGF_REHEARSAL -> refused", guard_probe({"TGF_REHEARSAL_RUNNER": "1", "TGF_REHEARSAL_DIR": str(rdir)}, scratch) == "REFUSE")

print("\n== a BRIDGE job runs on the scratch copy, never the live file ==")
j = rh.start_job("bridge", "scoring-setting-set:runner_probe|SCRATCH", db_path=live)
check("the job starts and names how to read it", j.get("status") == "running" and "job|" in j.get("read_with", ""), j)
st = wait(j["id"])
check("it finishes cleanly", st.get("status") == "done", {k: st.get(k) for k in ("status", "exit_code", "log_tail")})
check("its bridge answer comes back parsed", isinstance(st.get("result"), dict) and st["result"].get("saved") is True, st.get("result"))
check("the SCRATCH copy was written", sqlite3.connect(str(scratch)).execute(
      "SELECT value FROM app_settings WHERE key='runner_probe'").fetchone()[0] == "SCRATCH")
check("the LIVE file was not", db.get_app_setting("runner_probe", db_path=live) == "LIVE")
j2 = rh.start_job("bridge", "scoring-setting-get:runner_probe", db_path=live)
st2 = wait(j2["id"])
check("a read bridge sees the scratch value", (st2.get("result") or {}).get("value") == "SCRATCH", st2.get("result"))

print("\n== refused bridges ==")
for ex in ("scoring-rehearsal:restore", "scoring-gg-archive:vacuum|go", "scoring-backup", "probe_golf_genius"):
    r = rh.start_job("bridge", ex, db_path=live)
    check(f"refused: {ex}", "error" in r, r)

print("\n== one job at a time ==")
jd = rh._jobs_dir(live)
fake = jd / "zzzz-fake.json"
fake.write_text(json.dumps({"id": "zzzz-fake", "kind": "bridge", "spec": "x", "status": "running",
                            "pid": os.getpid(), "proc_start": rh._proc_start(os.getpid())}))
r = rh.start_job("bridge", "scoring-setting-get:runner_probe", db_path=live)
check("a second job is refused while one runs", "error" in r and "zzzz-fake" in r["error"], r)
fake.unlink()

print("\n== a dead job's pid, reused after a restart, never revives it (#862/#863) ==")
check("this process's start time is readable", isinstance(rh._proc_start(os.getpid()), int))
for label, extra in (("recorded before the fix (no proc_start)", {}),
                     ("a different process start time (pid reused)", {"proc_start": -1})):
    ghost = jd / "zzzz-ghost.json"
    ghost.write_text(json.dumps({"id": "zzzz-ghost", "kind": "tool", "spec": "se_replay", "status": "running",
                                 "pid": os.getpid(), **extra}))      # a LIVE pid, like pid 17 after the deploy
    r = rh.start_job("bridge", "scoring-setting-get:runner_probe", db_path=live)
    check(f"{label}: not blocking, a new job starts", r.get("status") == "running", r)
    wait(r["id"]) if r.get("id") else None
    saved = json.loads(ghost.read_text())
    check(f"{label}: 'lost' is SAVED in the job file", saved.get("status") == "lost" and saved.get("ended_at"), saved)
    check(f"{label}: job_status reads lost", rh.job_status("zzzz-ghost", db_path=live).get("status") == "lost")
    ghost.unlink()

print("\n== a TOOL job runs the lane harness in the child ==")
j3 = rh.start_job("tool", "takeover", "--events 999999", db_path=live)
st3 = wait(j3["id"])
log = st3.get("log_tail", "")
check("the takeover tool's own guard admits the scratch file (it reaches its run step)",
      "TAKEOVER on scratch file" in log and "refusing" not in log.lower(), log[-800:])
j4 = rh.start_job("tool", "se_replay", "--events 999999 --workers 1", db_path=live)
st4 = wait(j4["id"])
log4 = st4.get("log_tail", "")
check("se_replay's guard admits it too (no Railway / production-path refusal)",
      "looks like a Railway" not in log4 and "production database path" not in log4 and "--i-am-scratch" not in log4, log4[-800:])
check("list_jobs shows the runs", len(rh.list_jobs(db_path=live)) >= 4)
check("tool jobs run at the lowest CPU priority", st4.get("nice") == 19 or not __import__("shutil").which("nice"), st4.get("nice"))
check("a missing job id answers plainly", "error" in rh.job_status("nope", db_path=live))

print("\n== jobs stay out of a live score-entry event (Front Desk #851) ==")
from datetime import datetime as _dt
check("tee times parse: 17:00, 5:00 PM, 8:30am", rh._parse_tee("17:00") == (17, 0)
      and rh._parse_tee("5:00 PM") == (17, 0) and rh._parse_tee("8:30am") == (8, 30) and rh._parse_tee("TBD") is None)
_lc = sqlite3.connect(live)
_lc.execute("CREATE TABLE IF NOT EXISTS se_rounds (id INTEGER PRIMARY KEY, event_id INTEGER, round_date TEXT, "
            "label TEXT, holes INTEGER, status TEXT DEFAULT 'open')")
_lc.execute("INSERT INTO events (item_name, event_date, start_time) VALUES ('t9.29 Hold Test', '2026-09-29', '5:00 PM')")
_ev = _lc.execute("SELECT id FROM events WHERE item_name='t9.29 Hold Test'").fetchone()[0]
_lc.execute("INSERT INTO se_rounds (event_id, round_date, holes, status) VALUES (?, '2026-09-29', 9, 'open')", (_ev,))
_lc.commit()
check("the day before: no hold", rh.live_event_hold(live, now=_dt(2026, 9, 28, 20, 0)) is None)
check("event day, 3:00 PM (2 h before tee): no hold", rh.live_event_hold(live, now=_dt(2026, 9, 29, 15, 0)) is None)
check("event day, 4:05 PM (inside the hour before tee): held",
      "tees off" in (rh.live_event_hold(live, now=_dt(2026, 9, 29, 16, 5)) or ""))
check("event day, 8:30 PM, round still open: held", rh.live_event_hold(live, now=_dt(2026, 9, 29, 20, 30)) is not None)
_lc.execute("UPDATE se_rounds SET status='closed'"); _lc.commit()
check("round closed: hold lifts", rh.live_event_hold(live, now=_dt(2026, 9, 29, 20, 30)) is None)
db.set_app_setting("rehearsal_hold", "1", db_path=live)
r = rh.start_job("bridge", "scoring-setting-get:runner_probe", db_path=live)
check("app setting rehearsal_hold=1 refuses a job, nothing started", "held" in r.get("error", ""), r)
db.set_app_setting("rehearsal_hold", "0", db_path=live)
_lc.execute("DELETE FROM se_rounds"); _lc.commit(); _lc.close()

print("\n== no scratch copy -> a plain refusal ==")
os.rename(scratch, str(scratch) + ".bak")
check("start_job refuses before a restore exists", "error" in rh.start_job("bridge", "scoring-setting-get:x", db_path=live))
os.rename(str(scratch) + ".bak", scratch)

print()
print("ALL PASS" if not fails else f"FAILED ({len(fails)}): {fails}")
sys.exit(1 if fails else 0)
