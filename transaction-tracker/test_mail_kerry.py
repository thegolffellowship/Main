"""Mail to Kerry through the Tracker mailer (Kerry 2026-09-30, #1050).
Run: python3 test_mail_kerry.py"""
import os, sys, json, tempfile, contextlib, io, logging
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-mk-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "x")
logging.disable(logging.CRITICAL)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)
    import mcp_server
from email_parser import mail_kerry as MK, fetcher

d = json.loads(mcp_server._scoring_dispatch("", "scoring-mail-kerry:Sales tax: August|<p>Pay $229.75 by 10/20.</p>"))
check("dry run renders, sends nothing, recipient is Kerry", d["status"] == "dry_run" and d["to"] == MK.KERRY
      and "229.75" in d["html"], d)
h = MK.mail_kerry("Hi", "<p>Dear {first_name}, [AMOUNT]</p>", send=True, db_path=DB)
check("a leftover {tag} or [BLANK] holds the message", h["status"] == "held" and len(h["problems"]) == 1, h)
check("empty subject / body held", MK.mail_kerry("", "", send=True, db_path=DB)["status"] == "held")
sent = []
fetcher.send_mail_graph = lambda **kw: sent.append(kw) or True
for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS"):
    os.environ[k] = "x"
r = json.loads(mcp_server._scoring_dispatch("", "scoring-mail-kerry-send:Report|<p>September snapshot</p>"))
check("send goes to Kerry and only Kerry", r["status"] == "sent" and len(sent) == 1
      and sent[0]["to_address"] == MK.KERRY and not sent[0].get("cc_address"), (r, sent))
import inspect
check("no parameter can change the recipient", "to" not in inspect.signature(MK.mail_kerry).parameters)
with db._connect(DB) as c:
    n = c.execute("SELECT COUNT(*) FROM message_log WHERE event_name = 'mail-kerry' AND status = 'sent'").fetchone()[0]
    a = c.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type = 'mail_kerry'").fetchone()[0]
check("logged in message_log and agent_action_log", n == 1 and a == 1, (n, a))
print(f"\n{len(F)} FAILURE(S): {F}" if F else "\nALL PASS")
sys.exit(1 if F else 0)
