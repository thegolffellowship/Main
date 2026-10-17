"""THE PAYOUT ASK (Kerry 2026-10-17, CoS #1977; mockups MM2hscPx8cHQ56NCaxVjkp;
"I can pay all of them ... Send to Mark and Michele"). Someone we owe
winnings to with no way to pay them on file is emailed a signed link: Venmo
first (shown back before it saves), then "get Venmo", then credit / Zelle /
PayPal / Cash App / Apple Cash. Nothing is paid by the Tracker; nothing is
sent unless the wording carries Kerry's stamp (and, for the job, the dial).

Run: python3 test_payout_ask.py
"""
import contextlib, io, logging, os, sqlite3, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    DB = os.environ["DATABASE_PATH"]
    db.init_db(DB)
    import app as appmod  # noqa: E402
from email_parser import payout_ask as pa  # noqa: E402

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {str(detail)[:400]}"))
    if not cond:
        F.append(label)


TODAY = datetime.utcnow().date()
c = sqlite3.connect(DB)
for _t in ("tgf_payouts", "tgf_events", "acct_transactions", "customer_emails", "customers",
           "action_items"):
    c.execute(f"DELETE FROM {_t}")
c.execute("INSERT INTO tgf_events (id, code, name, event_date) VALUES (1, 'a9.26', 'a9.26 Avery Ranch', ?)",
          ((TODAY - timedelta(days=11)).isoformat(),))
c.execute("INSERT INTO tgf_events (id, code, name, event_date) VALUES (2, 's9.27', 's9.27 The Quarry', ?)",
          ((TODAY - timedelta(days=4)).isoformat(),))
people = [(833, "Mark", "Parker", None, None), (765, "Michele", "McCormick", None, None),
          (10, "Vic", "Venmo", "vic-venmo", None), (11, "Zed", "Zelle", None, "zelle"),
          (12, "Paid", "Already", None, None), (13, "Nomail", "Person", None, None)]
for cid, fn, ln, ven, meth in people:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, venmo_username, payment_method) "
              "VALUES (?,?,?,?,?)", (cid, fn, ln, ven, meth))
    if cid != 13:
        c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?,?,1)",
                  (cid, f"p{cid}@example.com"))
tid = 100
for cid, ev, amt, src in ((833, 1, 16.25, "pending"), (765, 2, 11.50, "pending"), (10, 2, 5.0, "pending"),
                          (11, 2, 7.0, "pending"), (12, 2, 9.0, "venmo"), (13, 2, 4.0, "pending"),
                          (765, 1, 2.00, "pending")):
    tid += 1
    c.execute("INSERT INTO acct_transactions (id, date, description, total_amount, type, source) "
              "VALUES (?,?,?,?, 'expense', ?)", (tid, TODAY.isoformat(), "payout", amt, src))
    c.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, description, "
              "acct_transaction_id) VALUES (?,?,?,?,?,?)", (ev, cid, "team_net", amt, "Team Net 2nd", tid))
c.commit(); c.close()

print("who is asked")
cands = {o["customer_id"]: o for o in pa.candidates(db_path=DB)}
check("Mark and Michele are asked", 833 in cands and 765 in cands, cands.keys())
check("someone with Venmo, a method, or nothing owed is not", not ({10, 11, 12} & set(cands)), cands.keys())
check("Michele's two open payouts add up", abs(cands[765]["amount"] - 13.50) < 0.001
      and len(cands[765]["events"]) == 2, cands[765])
pl = pa.plan(db_path=DB)
check("no email goes to the manager list, not the send", [o["customer_id"] for o in pl["no_email"]] == [13], pl)

print("parsing handles")
check("Venmo: a leading @ is stripped", pa.parse_venmo("@Mark-Parker-7") == "Mark-Parker-7")
check("Zelle takes a phone", pa.parse_handle("zelle", "512.923.9719") == "(512) 923-9719")
check("Zelle takes an email", pa.parse_handle("zelle", "Me@Example.com") == "me@example.com")
check("PayPal takes a PayPal.Me link", pa.parse_handle("paypal", "https://paypal.me/MarkP") == "MarkP")
check("Cash App gets its $", pa.parse_handle("cashapp", "markp") == "$markp")
check("Apple Cash needs a phone", pa.parse_handle("applepay", "+1 210 269 4230") == "(210) 269-4230")
for m, bad in (("zelle", "nope"), ("cashapp", "$1bad"), ("applepay", "x@y.com"), ("paypal", "a b")):
    try:
        pa.parse_handle(m, bad)
        ok = False
    except ValueError:
        ok = True
    check(f"{m} refuses {bad!r}", ok)

print("the email")
msg = pa.build_message(cands[833])
check("one event: the subject names the amount and the event",
      msg["subject"] == "You won $16.25 at a9.26 Avery Ranch: where should we send it?", msg["subject"])
check("the email carries the signed link and no leftover tag",
      "/payout/" in msg["html"] and not msg["held"], msg["held"])
m2 = pa.build_message(cands[765], "reminder")
check("two events: a total and the reminder subject", m2["subject"] == "Reminder: your $13.50 in TGF winnings"
      and "$13.50" in m2["html"], m2["subject"])

print("locks")
check("send_now refuses until the wording is stamped", pa.send_now([833], db_path=DB).get("error"))
check("the job does nothing with the dial off", "skipped" in pa.auto_check(db_path=DB))
db.set_app_setting(pa.APPROVAL_KEY, pa.template_hash(), db_path=DB)
check("...and still nothing with only the stamp", "skipped" in pa.auto_check(db_path=DB))

print("the named send")
out = []
res = pa.send_now([833, 765, 10, 13], db_path=DB, sender=lambda to, s, h: out.append((to, s)) or True)
check("Mark and Michele are sent, nobody else", sorted(x["customer_id"] for x in res["sent"]) == [765, 833]
      and len(out) == 2, res)
check("the others are refused with a reason", {r["customer_id"] for r in res["refused"]} == {10, 13}, res)
again = pa.send_now([833], db_path=DB, sender=lambda *a: True)
check("never a second ask", not again["sent"] and again["refused"][0]["why"].startswith("already"), again)

print("reminder timing")
st = pa.load_state(DB)
st["833"]["sent_at"] = (datetime.utcnow() - timedelta(days=3)).isoformat() + "Z"
pa._save_state(st, DB)
pl = pa.plan(db_path=DB)
check("2 days later Mark is due one reminder", [o["customer_id"] for o in pl["reminders"]] == [833], pl["reminders"])
check("Michele, asked just now, waits", [o["customer_id"] for o in pl["waiting"]] == [765], pl["waiting"])

print("the page")
cl = appmod.app.test_client()
tok = pa.make_token(833)
r = cl.get(f"/payout/{tok}")
check("the page opens and asks for Venmo with the amount", r.status_code == 200
      and b"$16.25" in r.data and b"Venmo username" in r.data, r.status_code)
check("a GET saves nothing", not (pa.load_state(DB).get("833") or {}).get("answered_at"))
r = cl.post(f"/payout/{tok}", data={"action": "venmo_check", "venmo": "@Mark-Parker-7"})
check("Continue shows the username back, not saved yet", b"Is this right?" in r.data
      and b"@Mark-Parker-7" in r.data and not (pa.load_state(DB).get("833") or {}).get("answered_at"))
r = cl.post(f"/payout/{tok}", data={"action": "venmo_check", "venmo": "x"})
check("a bad username is refused on the page", r.status_code == 400 and b"doesn" in r.data)
r = cl.post(f"/payout/{tok}", data={"action": "venmo_save", "venmo": "Mark-Parker-7"})
with sqlite3.connect(DB) as cx:
    v = cx.execute("SELECT venmo_username FROM customers WHERE customer_id = 833").fetchone()[0]
check("Yes saves Venmo on the profile", r.status_code == 200 and v == "Mark-Parker-7" and b"Got it" in r.data, v)
check("answered: no reminder after that", 833 not in [o["customer_id"] for o in pa.plan(db_path=DB)["reminders"]])
check("the get-Venmo step offers only app links", b"apps.apple.com" in cl.get(f"/payout/{tok}?step=get").data)

tok2 = pa.make_token(765)
r = cl.post(f"/payout/{tok2}", data={"action": "other", "method": "zelle", "reason": "blocked",
                                       "handle_zelle": "210-269-4230"})
with sqlite3.connect(DB) as cx:
    m, h = cx.execute("SELECT payment_method, payment_handle FROM customers WHERE customer_id = 765").fetchone()
check("Zelle saves method + handle where Payouts reads them", (m, h) == ("zelle", "(210) 269-4230")
      and b"Zelle" in r.data, (m, h))
check("the reason is kept (blocked: no more Venmo nudges)",
      pa.load_state(DB)["765"]["answer"]["reason"] == "blocked")

tok3 = pa.make_token(13)
r = cl.post(f"/payout/{tok3}", data={"action": "other", "method": "credit"})
with sqlite3.connect(DB) as cx:
    ai = cx.execute("SELECT subject FROM action_items WHERE subject LIKE 'PAYOUT AS CREDIT%'").fetchall()
    paid = cx.execute("SELECT count(*) FROM acct_transactions WHERE source != 'pending' AND id > 100 "
                      "AND description = 'payout' AND total_amount = 4.0").fetchone()[0]
check("credit raises one action item and moves no money", len(ai) == 1 and paid == 0, ai)

pv = pa.make_token(10, preview=True)
r = cl.post(f"/payout/{pv}", data={"action": "venmo_save", "venmo": "someone-else"})
with sqlite3.connect(DB) as cx:
    v10 = cx.execute("SELECT venmo_username FROM customers WHERE customer_id = 10").fetchone()[0]
check("a preview link saves nothing", v10 == "vic-venmo")
check("a forged link is refused", cl.get("/payout/abc.def").status_code == 400)
from email_parser import handicap_ask as ha  # noqa: E402
check("a handicap link cannot open the payout page",
      cl.get(f"/payout/{ha.make_token(833, 1)}").status_code == 400)

print("status chips")
sr = pa.status_rows(DB)
check("chips: Mark in (venmo), Michele in (zelle)", sr["833"]["kind"] == "venmo" and sr["765"]["kind"] == "zelle", sr)

print()
if F:
    print(f"{len(F)} FAILED")
    sys.exit(1)
print("ALL PASS")
