"""Daily unsubscribes (Kerry 2026-10-23): Tracker invitation opt-outs from the
action log, Brevo unsubscribes by diffing a daily snapshot, and the digest
section. Run: python3 test_unsubscribes.py"""
import os, sys, tempfile, contextlib, io, logging, sqlite3, json
from datetime import datetime, timedelta
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-unsub-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ.setdefault("ADMIN_PIN", "1234"); os.environ.setdefault("SECRET_KEY", "x")
os.environ["SCHEDULER_DISABLED"] = "1"
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as A  # noqa: F401
from email_parser import database as db
from email_parser import unsubscribes as us
from email_parser import report

F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

c = sqlite3.connect(tmp)
c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (318, 'Warren', 'Kamealoha')")
c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (500, 'Ann', 'Brevo')")
c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (500, 'Ann@Example.com', 1)")
c.commit(); c.close()
now = datetime.utcnow()
db.log_agent_action("rsvp-link", "event_invite_unsubscribe", "customer 318", db_path=tmp)

print("== invitations ==")
r = us.recent(24, db_path=tmp)
check("an invitation opt-out in the last day is listed by name",
      [(x["source"], x["name"]) for x in r] == [("invitations", "Warren Kamealoha")], r)
check("outside the window it is not", us.recent(24, db_path=tmp, now=now + timedelta(days=2)) == [])

print("== Brevo snapshot diff ==")
out = us.refresh(db_path=tmp, now=now, fetch=lambda: ["old@x.com"])
check("first run stores a baseline and logs nothing", out["brevo"] == "baseline" and us._log(tmp) == [], out)
out = us.refresh(db_path=tmp, now=now, fetch=lambda: ["old@x.com", "ann@example.com"])
check("a new Brevo unsubscribe is logged once", out["new"] == 1 and len(us._log(tmp)) == 1, out)
row = us._log(tmp)[0]
check("...matched to the customer by email", row["customer_id"] == 500 and row["name"] == "Ann Brevo", row)
us.refresh(db_path=tmp, now=now, fetch=lambda: ["old@x.com", "ann@example.com"])
check("no change, no new row", len(us._log(tmp)) == 1)
us.refresh(db_path=tmp, now=now, fetch=lambda: ["ann@example.com"])
check("someone leaving the blacklist is logged as resubscribed",
      us._log(tmp)[-1]["kind"] == "resubscribed" and us._log(tmp)[-1]["email"] == "old@x.com")
check("a Brevo read failure never raises", us.refresh(db_path=tmp, fetch=lambda: 1 / 0)["brevo"].startswith("read failed"))

print("== digest section ==")
rows = us.recent(24, db_path=tmp)
h = report.build_digest_html([], [], [], [], [], None, rows)
check("the digest has the section with names and sources",
      "Unsubscribes (Last 24 Hours)" in h and "Warren Kamealoha" in h and "TGF Insider (Brevo)" in h
      and "Resubscribed" in h)
check("an empty day says so", "Nobody unsubscribed." in report.build_digest_html([], [], [], [], [], None, []))
check("no data, no section", "Unsubscribes" not in report.build_digest_html([], [], [], [], [], None, None))
src = open("mcp_server.py").read()
check("bridge scoring-unsubscribes exists", 'cmd == "scoring-unsubscribes"' in src)

print("\n" + (f"{len(F)} FAILED: {F}" if F else "ALL PASS"))
sys.exit(1 if F else 0)
