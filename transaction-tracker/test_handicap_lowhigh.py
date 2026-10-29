"""THE HANDICAP LINK, NO-INDEX ANSWER: LOW / HIGH, LOCKED (Kerry 2026-10-28,
Event Ops #2474-B, #2475-1).

Kerry: "We should thank them and tell them what their quick calculated
starting TGF Handicap Index would be based on a low score entry. Don't allow
them to go back to change it to avoid tampering." / "We should be asking them
to give an 18 hole total, but you could put a minimum of 60 in the low one" /
"They should only be able to enter a number. A low number and a high number.
It shouldn't accept non-numbers." / "No cap on high."

Run: python3 test_handicap_lowhigh.py
"""
import contextlib, io, logging, os, sqlite3, sys, tempfile
from datetime import timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="tgf-hlh-"), "t.db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    DB = os.environ["DATABASE_PATH"]
    db.init_db(DB)
    import app as appmod  # noqa: E402
from email_parser import handicap_ask as ha  # noqa: E402
from email_parser.timezone_utils import today_central  # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {str(detail)[:400]}"))
    if not cond:
        F.append(label)

V = lambda lo, hi: ha.validate({"kind": "none", "score_low": lo, "score_high": hi})  # noqa: E731
print("the server refuses")
check("both numbers are required", V("90", "").get("error") and V("", "100").get("error") and V("", "").get("error"))
check("digits only: letters, decimals, signs, spaces inside are refused",
      all(V(lo, hi).get("error") for lo, hi in (("9O", "100"), ("90.5", "100"), ("-90", "100"),
                                                ("90", "1 00"), ("ninety", "100"), ("90", "１００"))))
check("LOW at least 60 (an 18-hole total, never a nine)", V("59", "70").get("error") and not V("60", "70").get("error"))
check("HIGH at least LOW (not swapped)", V("100", "95").get("error") and not V("95", "95").get("error"))
check("no cap on HIGH", V("110", "160").get("score_high") == 160 and V("110", "999").get("score_high") == 999)
check("free text is gone: the answer is LOW and HIGH only",
      V("90", "100") == {"kind": "none", "score_low": 90, "score_high": 100})
check("starting handicap = LOW - 72", ha.starting_from_scores(V("90", "100")) == 18.0)
check("the new lines stay OUTSIDE the stamped wording (the live ask is not re-locked)",
      ha.DONE_RULE_TGF not in ha.template_hash() and "DONE_RULE_TGF" not in
      open("email_parser/handicap_ask.py").read().split("def template_hash")[1].split("return")[0])

c = sqlite3.connect(DB)
db._ensure_scoring_tables._ensure_inner(c)
ev_date = (today_central() + timedelta(days=4)).isoformat()
c.execute("INSERT INTO events (id, item_name, event_date, course, chapter, status) "
          "VALUES (9101, 's9.99 Lock Test', ?, 'TPC', 'San Antonio', 'active')", (ev_date,))
c.execute("INSERT INTO customers (customer_id, first_name, last_name, venmo_username) VALUES (701, 'Lou', 'Low', 'Lou-Low-1')")
c.commit(); c.close()
cl = appmod.app.test_client()
tok = ha.make_token(701, 9101)

print("the page")
pg = cl.get(f"/handicap/{tok}").data.decode()
check("two number boxes, numeric keypad, digits pattern",
      'name="score_low"' in pg and 'name="score_high"' in pg and pg.count('pattern="[0-9]*"') >= 2
      and pg.count('inputmode="numeric"') >= 2)
check("the page strips non-digits as typed and checks LOW >= 60 / HIGH >= LOW before submit",
      "replace(/[^0-9]/g" in pg and "L < 60" in pg and "H < L" in pg)
check("no free-text box (rounds a year) any more", "rounds_year" not in pg)
r = cl.post(f"/handicap/{tok}", data={"kind": "none", "score_low": "45", "score_high": "50"})
check("a 9-hole total is refused with the reason", r.status_code == 400 and b"at least 60" in r.data)
r = cl.post(f"/handicap/{tok}", data={"kind": "none", "score_low": "88", "score_high": "97"})
check("thank-you names it: starting TGF Handicap Index 16.0 from the low score of 88 minus 72",
      r.status_code == 200
      and b"Your starting TGF Handicap Index is 16.0, from your low score of 88 minus 72." in r.data, r.data[-800:])
check("...and says the link is locked", ha.DONE_LOCKED.encode().replace(b"'", b"&#39;") in r.data
      or b"can&#39;t be changed from this link" in r.data)
with db._connect(DB) as cc:
    v = cc.execute("SELECT starting_handicap_18, starting_handicap_set_by FROM customers WHERE customer_id = 701").fetchone()
check("set 16.0 by the rule", v[0] == 16.0 and v[1] == ha.RULE_SET_BY, tuple(v))

print("locked after the answer")
pg2 = cl.get(f"/handicap/{tok}").data.decode()
check("back on the link: no form, the locked page", "I have a GHIN number" not in pg2
      and 'name="score_low"' not in pg2 and ha.LOCKED_HEAD in pg2, pg2[-600:])
r = cl.post(f"/handicap/{tok}", data={"kind": "none", "score_low": "70", "score_high": "80"})
check("a second POST is refused (409) and changes nothing", r.status_code == 409)
with db._connect(DB) as cc:
    v2 = cc.execute("SELECT starting_handicap_18 FROM customers WHERE customer_id = 701").fetchone()[0]
check("...still 16.0", v2 == 16.0)
check("record() itself refuses (not just the page)", ha.record(tok, {"kind": "ghin", "ghin": "1234567",
                                                                    "index": "2.0"}, db_path=DB).get("locked"))
pv = ha.make_token(701, 9101, preview=True)
check("a staff preview link is never locked (it saves nothing)",
      cl.post(f"/handicap/{pv}", data={"kind": "none", "score_low": "70", "score_high": "80"}).status_code == 200)
check("GHIN / other-service paths unchanged (75%)",
      ha.validate({"kind": "ghin", "ghin": "1234567", "index": "14.2"}).get("index") == 14.2
      and ha.starting_from_index(14.2) == 10.7)
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
