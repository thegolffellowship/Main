"""The daily health digest (email_parser/health.py): the report, the
findings rules, the markdown, the mailbox post, the COO action items
(one open item per finding, never a duplicate), the dialled time, the
once-a-day gate and the prune.

Run: python3 test_health_digest.py
"""
import os, sys, sqlite3, tempfile, contextlib, io, logging, json
from datetime import datetime
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-health-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ.setdefault("SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402
from email_parser import perf, health  # noqa: E402
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
c = sqlite3.connect(tmp)
c.execute("INSERT INTO items (id, email_uid, merchant, customer, item_name, order_date, transaction_status) VALUES (1, 'u1', 'The Golf Fellowship', 'Pat Youngs', 's9.24 Brackenridge', '2026-09-10', 'active')")
c.commit(); c.close()

print("\n== the report and its findings ==")
for v in (300, 400, 500, 6000, 9000):           # p95 over the 4 s line
    perf.record("route", "pairings_get", v, breakdown={"saved_sheet": v // 2, "standings": v // 4}, event_id=3309,
                status="slow" if v > 4000 else "ok", detail={"concurrent": ["job:auto_live_poll"], "load1": 1.2} if v > 4000 else None, db_path=tmp)
for v in (50, 60, 70):                           # fine
    perf.record("route", "events_list", v, db_path=tmp)
perf.record("route", "customers_list", 3000, status="slow", db_path=tmp)     # one spike, p95 under? n=1 → spike rule
perf.record("job", "auto_live_poll", 1200, db_path=tmp)
perf.record("job", "db_backup", 800, status="error", detail={"error": "RuntimeError('no creds')"}, db_path=tmp)
perf.record("bridge", "scoring-flights-close", 900, db_path=tmp)
perf.flush(tmp)
rep = health.build_health_report(1, db_path=tmp)
check("routes / jobs / bridges summarised", {r["name"] for r in rep["summary"]["route"]} == {"pairings_get", "events_list", "customers_list"}
      and {r["name"] for r in rep["summary"]["job"]} == {"auto_live_poll", "db_backup"} and rep["summary"]["bridge"][0]["name"] == "scoring-flights-close")
keys = {f["key"]: f for f in rep["findings"]}
check("FINDING high: a route whose p95 is over its line (pairings_get)", keys.get("route_slow:pairings_get", {}).get("severity") == "high", str(keys))
check("FINDING high: a failed job run (db_backup) with its error", keys.get("job_error:db_backup", {}).get("severity") == "high" and "no creds" in keys["job_error:db_backup"]["text"], str(keys))
check("FINDING medium: one spike on customers_list, p95 not over", keys.get("route_spike:customers_list", {}).get("severity") == "medium", str(keys))
check("a healthy route raises nothing", not any(k.endswith("events_list") for k in keys))
check("findings are ordered high → medium → info", [f["severity"] for f in rep["findings"]] == sorted([f["severity"] for f in rep["findings"]], key={"high": 0, "medium": 1, "info": 2}.get))
check("the slow list carries breakdown + what else ran + load", rep["slow"][0]["name"] == "pairings_get" and rep["slow"][0]["breakdown"]["saved_sheet"] == 4500 and rep["slow"][0]["detail"]["concurrent"] == ["job:auto_live_poll"])
check("jobs: runs / errors / last status", next(j for j in rep["jobs"] if j["name"] == "db_backup")["errors"] == 1 and next(j for j in rep["jobs"] if j["name"] == "auto_live_poll")["last_status"] == "ok")
check("db size, counts and the live probe are on the report", rep["db"]["bytes"] > 0 and rep["db"]["counts"]["items"] == 1 and "connect_ms" in rep["probe"])
lay = rep["db"]["layout"]
check("the layout says where the bytes are (page count, free pages, biggest tables via dbstat)",
      lay["page_count"] > 0 and lay["freelist_pages"] is not None and (lay["dbstat"] is False or lay["tables"]), str(lay)[:200])
fake = dict(rep); fake["db"] = dict(rep["db"], bytes=400 * 1048576, layout={"page_count": 100, "freelist_pages": 40, "free_bytes": 160 * 1048576, "tables": [{"name": "big", "bytes": 300 * 1048576, "type": "table"}]}); fake["load1"] = 87.4; fake["cpus"] = 8
fk = {f["key"]: f for f in health.find(fake)}
check("FINDING medium: free pages over 20% of the file → VACUUM candidate (Kerry's call, never run by the agent)", "db_free_pages" in fk and "VACUUM" in fk["db_free_pages"]["text"], str(fk))
check("FINDING medium: one table over half the file", fk.get("db_big_table:big", {}).get("severity") == "medium")
check("FINDING high: the box saturated (load per cpu over the rule)", fk.get("box_load", {}).get("severity") == "high")

md = health.render_markdown(rep)
check("markdown is addressed to tracker-claude + kerry and leads with the findings",
      md.startswith("TO: tracker-claude") and "**FINDINGS**" in md and "[HIGH] pairings_get" in md, md[:300])
check("...names the slow open's sections and what ran beside it", "saved_sheet 4.5 s" in md and "while job:auto_live_poll" in md)
check("...and the database line", "**DATABASE**" in md and "items 1" in md)

print("\n== the routine: mailbox post, action items, once a day ==")
db.set_app_setting("health_digest_time", "05:45", db_path=tmp)
check("digest_due honours the dial: not due at 05:30", health.digest_due(now=datetime(2026, 9, 23, 5, 30), db_path=tmp) is False)
check("...due at 05:45", health.digest_due(now=datetime(2026, 9, 23, 5, 45), db_path=tmp) is True)
db.set_app_setting("health_digest_time", "garbage", db_path=tmp)
check("a bad dial value falls back to the default 05:00 (Kerry #611)", health.digest_time(tmp) == "05:00")
db.set_app_setting("health_digest_time", "06:00", db_path=tmp)
check("the dial can move the hour (06:00)", health.digest_time(tmp) == "06:00" and health.digest_due(now=datetime(2026, 9, 23, 5, 50), db_path=tmp) is False)

res = health.run_health_digest(post=False, db_path=tmp)
check("post=False builds the text and writes nothing", res["posted"] is None and res["action_items"] == [] and "TO: tracker-claude" in res["body"]
      and db.read_platform_dialogue_entries(5, "tracker-health", 0, db_path=tmp) == [])

res = health.run_health_digest(post=True, db_path=tmp)
posts = db.read_platform_dialogue_entries(5, "tracker-health", 0, db_path=tmp)
check("post=True posts ONE mailbox entry, topic tracker-health, author tracker-claude", len(posts) == 1 and posts[0]["author"] == "tracker-claude" and posts[0]["id"] == res["posted"], str(posts))
items = db.get_action_items(status="open", db_path=tmp)
subj = sorted(i["subject"] for i in items)
check("every high/medium finding is a COO action item (HEALTH: <key>), from the CTO, category other",
      subj == sorted(f"HEALTH: {f['key']}" for f in rep["findings"] if f["severity"] in ("high", "medium"))
      and all(i["from_name"] == "CTO" and i["category"] == "other" for i in items), str(subj))
check("urgency follows severity", next(i for i in items if i["subject"] == "HEALTH: job_error:db_backup")["urgency"] == "high")
check("the once-a-day mark is set and the digest is no longer due today",
      db.get_app_setting("health_digest_last", db_path=tmp) == __import__("email_parser.timezone_utils", fromlist=["x"]).today_central_str()
      and health.digest_due(now=datetime.now().replace(hour=23, minute=59), db_path=tmp) is False)
check("...and health_digest_check() therefore does nothing", health.health_digest_check(db_path=tmp) is None)
check("the routine is logged as cto-agent / daily_digest", any(r["action_type"] == "daily_digest" for r in db.get_agent_action_log(agent_name="cto-agent", db_path=tmp)))

n_before = len(items)
health.run_health_digest(post=True, db_path=tmp)
check("a second run the same morning files NO duplicate action items (dedupe on subject while open)",
      len(db.get_action_items(status="open", db_path=tmp)) == n_before)
db.update_action_item(items[0]["id"], {"status": "completed"}, db_path=tmp)
health.run_health_digest(post=True, db_path=tmp)
check("...but a finding closed and found again is filed again", len(db.get_action_items(status="open", db_path=tmp)) == n_before)

c = sqlite3.connect(tmp)
c.execute("INSERT INTO perf_samples (at, kind, name, total_ms) VALUES ('2020-01-01 00:00:00', 'route', 'old', 1)"); c.commit()
res = health.run_health_digest(post=True, db_path=tmp)
check("the routine prunes samples past retention", res["pruned"] == 1 and c.execute("SELECT COUNT(*) FROM perf_samples WHERE name='old'").fetchone()[0] == 0)
hist = json.loads(db.get_app_setting("health_db_size_history", db_path=tmp))
check("the database size is recorded once per day for the growth line", len(hist) == 1 and hist[0]["bytes"] > 0)
c.close()

print()
if F:
    print(f"{len(F)} FAILED: " + "; ".join(F))
    sys.exit(1)
print("ALL PASS")
