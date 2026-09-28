"""Dress rehearsal (CA #800/#801): the scrubbed scratch copy and the PROOF that every outbound channel is off with
TGF_REHEARSAL=1.

Run:  python test_rehearsal.py
Point it at a restored copy too (the drill's check on the real data):
      REHEARSAL_DB=/path/tracker_rehearsal.db python test_rehearsal.py
"""
import os, sys, sqlite3, tempfile, json, subprocess, textwrap, logging, gzip, shutil
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
root = tempfile.mkdtemp(prefix="tgf-rehearsal-")
live = os.path.join(root, "live.db")
os.environ["DATABASE_PATH"] = live
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ["PERF_SAMPLES"] = "0"
logging.disable(logging.CRITICAL)

fails = []
def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"  {detail}"))
    if not cond:
        fails.append(label)

from email_parser import database as db
from email_parser import rehearsal as rh

db.init_db(live)
c = sqlite3.connect(live)
c.execute("INSERT INTO customers (customer_id, first_name, last_name, phone, venmo_username, payment_handle) "
          "VALUES (501, 'Pat', 'Golfer', '210-555-0101', '@Pat-Golfer-77', '@Pat-Golfer-77')")
c.execute("INSERT INTO customer_emails (customer_id, email) VALUES (501, 'pat.golfer@gmail.com')")
c.execute("INSERT INTO customer_emails (customer_id, email) VALUES (501, 'pat.alt@yahoo.com')")
c.execute("INSERT INTO items (email_uid, item_index, merchant, customer, customer_email, customer_phone, "
          "order_id, order_date, item_name, item_price, customer_id) VALUES "
          "('u1', 0, 'GoDaddy', 'Pat Golfer', 'pat.golfer@gmail.com', '210-555-0101', 'R1', "
          "'2026-09-01', 's9.1 THE QUARRY', '$86.00', 501)")
c.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('graph_refresh_token', 'SECRET-XYZ')")
c.execute("CREATE TABLE IF NOT EXISTS _t_unique_tok (id INTEGER PRIMARY KEY, merchant_token TEXT NOT NULL UNIQUE)")
c.executemany("INSERT INTO _t_unique_tok (merchant_token) VALUES (?)", [("netflix",), ("adobe",), ("zoom",)])
c.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('health_digest_time', '05:00')")
c.commit(); c.close()

print("== scrub(): contact details and secrets out, the replay's data in ==")
copy = os.path.join(root, "copy.db")
_src = sqlite3.connect(live); _src.execute("VACUUM INTO ?", (copy,)); _src.close()   # as the nightly backup makes it
try:
    rh.scrub(live)
    check("scrub() refuses the live database path", False, "it scrubbed the live file")
except ValueError:
    check("scrub() refuses the live database path", True)
done = rh.scrub(copy)
s = sqlite3.connect(copy)
cust = s.execute("SELECT first_name, last_name, phone, venmo_username, payment_handle FROM customers WHERE customer_id=501").fetchone()
check("customer name kept (the replay matches people by id and name)", cust[:2] == ("Pat", "Golfer"), cust)
check("customer phone and payment handles blanked", not cust[2] and not cust[3] and not cust[4], cust)
it = s.execute("SELECT customer_email, customer_phone, item_price, customer_id FROM items").fetchone()
check("order-row email/phone scrubbed, price and customer_id kept",
      it[0].endswith("@rehearsal.invalid") and not it[1] and it[2] == "$86.00" and it[3] == 501, it)
ce = s.execute("SELECT email FROM customer_emails").fetchall()
check("every customer_emails address is .invalid", all(r[0].endswith("@rehearsal.invalid") for r in ce), ce)
st = dict(s.execute("SELECT key, value FROM app_settings WHERE key IN ('graph_refresh_token','health_digest_time')").fetchall())
check("secret-looking settings emptied, ordinary dials kept",
      st.get("graph_refresh_token") == "" and st.get("health_digest_time") == "05:00", st)
check("a NOT NULL UNIQUE token column gets distinct placeholders (no collision)",
      sorted(r[0] for r in s.execute("SELECT merchant_token FROM _t_unique_tok")) == ["redacted-1", "redacted-2", "redacted-3"])
check("integrity ok after the scrub", s.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
check("no free pages left (rewritten with VACUUM INTO)", s.execute("PRAGMA freelist_count").fetchone()[0] == 0)
s.close()
raw = open(copy, "rb").read()
check("the original addresses are nowhere in the file's bytes",
      all(x not in raw for x in (b"pat.golfer@gmail.com", b"pat.alt@yahoo.com", b"210-555-0101",
                                  b"@Pat-Golfer-77", b"SECRET-XYZ")))
check("scrub() reports what it touched", len(done["columns"]) >= 4 and done["settings_blanked"] >= 1, done)
lc = sqlite3.connect(live)
check("...and the LIVE file was not touched",
      lc.execute("SELECT COUNT(*) FROM customer_emails WHERE email='pat.golfer@gmail.com'").fetchone()[0] == 1)
lc.close()

print("\n== install_scratch(): a leftover WAL never reaches the new copy ==")
fin = os.path.join(root, "scratch_final.db")
old = sqlite3.connect(fin); old.execute("PRAGMA journal_mode=WAL"); old.execute("PRAGMA wal_autocheckpoint=0")
old.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"); old.execute("CREATE UNIQUE INDEX t_v ON t(v)")
old.commit()
old.executemany("INSERT INTO t (v) VALUES (?)", [(f"old{i}",) for i in range(200)]); old.commit()
shutil.copy(fin + "-wal", fin + "-wal.keep")          # the WAL a killed job leaves behind
old.close()
shutil.move(fin + "-wal.keep", fin + "-wal")
new = os.path.join(root, "scratch_new.db")
n = sqlite3.connect(new); n.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
n.execute("CREATE UNIQUE INDEX t_v ON t(v)"); n.executemany("INSERT INTO t (v) VALUES (?)", [(f"new{i}",) for i in range(50)])
n.commit(); n.close()
check("a stale -wal sits beside the old copy (the 9/28 condition)", os.path.exists(fin + "-wal"))
rh.install_scratch(new, fin)
check("the stale -wal is gone before the new copy is opened", not os.path.exists(fin + "-wal"))
f = sqlite3.connect(fin)
check("the new copy opens intact: integrity ok, only its own 50 rows",
      f.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
      and f.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 50
      and f.execute("SELECT COUNT(*) FROM t WHERE v LIKE 'old%'").fetchone()[0] == 0)
f.close()

print("\n== status ==")
check("status() names the scratch path on the volume, beside the live file",
      rh.status(db_path=live)["scratch_path"].startswith(os.path.join(root, "rehearsal")))
import app as appmod
check("there is no download route for the scratch copy",
      not any("rehearsal" in str(r.rule) for r in appmod.app.url_map.iter_rules()))

print("\n== TGF_REHEARSAL=1: every outbound channel is off (child process) ==")
target = os.getenv("REHEARSAL_DB") or copy
child = textwrap.dedent(f'''
    import os, sys, json, socket, threading, logging
    logging.disable(logging.CRITICAL)
    os.environ["TGF_REHEARSAL"] = "1"
    os.environ["DATABASE_PATH"] = {target!r}
    os.environ["SECRET_KEY"] = "x"
    os.environ["HTTPS_PROXY"] = "http://127.0.0.1:59999"
    # Credentials present on purpose: the guard must hold even if a lane's
    # sandbox had them.
    for k in ("AZURE_TENANT_ID","AZURE_CLIENT_ID","AZURE_CLIENT_SECRET","EMAIL_ADDRESS",
              "BREVO_API_KEY","STRIPE_SECRET_KEY","TWILIO_AUTH_TOKEN","ANTHROPIC_API_KEY"):
        os.environ[k] = "set"
    sys.path.insert(0, {HERE!r})
    out = {{}}
    import email_parser
    from email_parser import rehearsal as rh
    out["guard"] = rh._GUARDED
    out["proxy_env_dropped"] = "HTTPS_PROXY" not in os.environ
    def attempt(name, fn):
        try:
            fn(); out[name] = "SENT"
        except rh.RehearsalOutboundBlocked:
            out[name] = "blocked"
        except Exception as e:
            out[name] = "blocked" if any("rehearsal.invalid" in str(x) or "TGF_REHEARSAL" in str(x) for x in (e, e.__cause__, e.__context__)) else type(e).__name__ + ": " + str(e)[:120]
    import requests
    attempt("graph_mail", lambda: requests.post("https://graph.microsoft.com/v1.0/users/x/sendMail", timeout=5))
    attempt("graph_token", lambda: requests.post("https://login.microsoftonline.com/t/oauth2/v2.0/token", timeout=5))
    attempt("brevo", lambda: requests.get("https://api.brevo.com/v3/account", timeout=5))
    attempt("stripe", lambda: requests.get("https://api.stripe.com/v1/charges", timeout=5))
    attempt("twilio_sms", lambda: requests.post("https://api.twilio.com/2010-04-01/Accounts/x/Messages.json", timeout=5))
    attempt("golf_genius", lambda: requests.get("https://tgf-sa.golfgenius.com/pages/1", timeout=5))
    attempt("anthropic", lambda: requests.post("https://api.anthropic.com/v1/messages", timeout=5))
    attempt("meta", lambda: requests.get("https://graph.facebook.com/v19.0/me", timeout=5))
    attempt("hubspot", lambda: requests.get("https://api.hubapi.com/crm/v3/objects/contacts", timeout=5))
    import smtplib
    attempt("smtp", lambda: smtplib.SMTP("smtp.office365.com", 587, timeout=5))
    attempt("raw_socket_ip", lambda: socket.create_connection(("8.8.8.8", 53), timeout=5))
    attempt("local_proxy", lambda: socket.create_connection(("127.0.0.1", 59999), timeout=5))
    # the app's own senders, end to end
    from email_parser.fetcher import send_mail_graph
    try:
        ok = send_mail_graph(tenant_id="t", client_id="c", client_secret="s", from_address="a@b.c",
                             to_address="r1@rehearsal.invalid", subject="x", html_body="x")
        out["send_mail_graph"] = "returned " + str(ok)
    except Exception as e:
        out["send_mail_graph"] = "raised " + type(e).__name__
    # loopback that is NOT the proxy still works (local tooling, test servers)
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
    port = srv.getsockname()[1]
    try:
        socket.create_connection(("127.0.0.1", port), timeout=2).close(); out["loopback_ok"] = True
    except Exception as e:
        out["loopback_ok"] = str(e)
    srv.close()
    import app as appmod
    out["scheduler_running"] = bool(getattr(appmod, "scheduler", None) and appmod.scheduler.running)
    import sqlite3
    c = sqlite3.connect(os.environ["DATABASE_PATH"])
    out["integrity"] = c.execute("PRAGMA integrity_check").fetchone()[0]
    try:
        out["real_emails_left"] = c.execute("SELECT COUNT(*) FROM customer_emails WHERE email LIKE '%@%' AND email NOT LIKE '%@rehearsal.invalid'").fetchone()[0]
    except sqlite3.Error:
        out["real_emails_left"] = None
    out["blocked_count"] = len(rh.BLOCKED)
    print("RESULT " + json.dumps(out))
''')
p = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, timeout=300,
                   env={k: v for k, v in os.environ.items() if k not in ("TGF_REHEARSAL",)})
line = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
res = json.loads(line[-1][7:]) if line else {}
if not res:
    print(p.stdout[-2000:], p.stderr[-3000:])
check("the guard is installed on import of email_parser", res.get("guard") is True, res)
check("the proxy settings are dropped so clients cannot route around it", res.get("proxy_env_dropped") is True, res)
for ch in ("graph_mail", "graph_token", "brevo", "stripe", "twilio_sms", "golf_genius",
           "anthropic", "meta", "hubspot", "smtp", "raw_socket_ip", "local_proxy"):
    check(f"outbound {ch} is BLOCKED", res.get(ch) == "blocked", res.get(ch))
check("the app's Graph sender cannot deliver (returns False or raises, nothing leaves)",
      str(res.get("send_mail_graph", "")).startswith(("returned False", "raised")), res.get("send_mail_graph"))
check("every attempt was refused by the guard itself (recorded)", (res.get("blocked_count") or 0) >= 12, res.get("blocked_count"))
check("plain loopback still works (local test servers)", res.get("loopback_ok") is True, res.get("loopback_ok"))
check("the scheduler does NOT start in a rehearsal, even with EMAIL_ADDRESS set", res.get("scheduler_running") is False, res)
check(f"the copy under test opens with integrity ok ({os.path.basename(target)})", res.get("integrity") == "ok", res.get("integrity"))
check("no real customer email in the copy under test", res.get("real_emails_left") == 0, res.get("real_emails_left"))

print("\n== without TGF_REHEARSAL nothing changes ==")
check("the guard is NOT active in this (normal) process", rh._GUARDED is False and not rh.active())

print()
print("ALL PASS" if not fails else f"FAILED ({len(fails)}): {fails}")
sys.exit(1 if fails else 0)
