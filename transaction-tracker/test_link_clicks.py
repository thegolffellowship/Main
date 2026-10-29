"""THE CLICK LOG (Kerry 10/29: "Let's do the click log next"; #2480-2/#2481):
every visit to a link we sent a person is logged with customer_id, event,
time, user agent and IP; a likely mail scanner is flagged and never counts as
the person; the handicap-ask banner line and the payout-ask chips say whether
it was opened.

Run: python3 test_link_clicks.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-clk-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import database as db       # noqa: E402
from email_parser import link_clicks as lc    # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

db.init_db(DB)
with db._connect(DB) as c:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (851, 'Eric', 'Carstens')")
    eid = c.execute("INSERT INTO events (item_name, event_date) VALUES ('s18.12 T', '2099-10-31') RETURNING id").fetchone()[0]
    c.commit()
PHONE = {"ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari", "lang": "en-US", "ip": "1.2.3.4"}
SCANNER = {"ua": "", "lang": "", "ip": "40.1.1.1"}

check("nothing logged: not opened yet", lc.opened_line("handicap", 851, db_path=DB) == "not opened yet")
lc.record("handicap", 851, eid, SCANNER, DB)
check("a mail scanner is flagged, not counted as Eric",
      "mail scanner only" in lc.opened_line("handicap", 851, db_path=DB))
lc.record("handicap", 851, eid, PHONE, DB)
o = lc.opened("handicap", 851, db_path=DB)
check("Eric's own visit counts", o and o["count"] == 1 and o["scanner_hits"] == 1, o)
check("the line says opened", lc.opened_line("handicap", 851, db_path=DB).startswith("opened "))
with db._connect(DB) as c:
    d = c.execute("SELECT description FROM agent_action_log WHERE agent_name = 'link-click' ORDER BY id DESC").fetchone()[0]
check("logged with customer, event, user agent and IP",
      f"customer 851 event {eid}" in d and "iPhone" in d and "1.2.3.4" in d, d)

u = lc.tag_url(f"https://x/member/teesheet/{eid}#g3", 851, eid, "teesheet")
check("the tee-sheet link carries a signed tag and keeps its #group", "?w=" in u and u.endswith("#g3"), u)
tag = u.split("w=")[1].split("#")[0]
check("the tag reads back as Eric, this event", lc.read_tag(tag) == {"c": 851, "v": eid, "k": "teesheet"})
check("a forged tag is refused", lc.read_tag(tag[:-2] + "00") is None)

import app as _app
cl = _app.app.test_client()
cl.get(f"/member/teesheet/{eid}?w={tag}", headers={"User-Agent": PHONE["ua"], "Accept-Language": "en"})
check("opening the tee sheet with the tag logs Eric",
      (lc.opened("teesheet", 851, db_path=DB) or {}).get("count") == 1)
cl.get(f"/member/teesheet/{eid}", headers={"User-Agent": PHONE["ua"], "Accept-Language": "en"})
check("without the tag the page is just public, nothing logged",
      (lc.opened("teesheet", 851, db_path=DB) or {}).get("count") == 1)

from email_parser import handicap_ask as ha
tok = ha.make_token(851, eid)
cl.get(f"/handicap/{tok}", headers={"User-Agent": PHONE["ua"], "Accept-Language": "en"})
check("opening the handicap ask logs it", (lc.opened("handicap", 851, db_path=DB) or {}).get("count") == 2)
src = open("email_parser/event_day_email.py").read() + open("email_parser/results_email.py").read()
check("the event-day and results emails tag their links", "tag_url" in src and "_tag_results" in src)

print("== the open pixel (Kerry 10/29) ==")
with db._connect(DB) as c:
    c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (851, 'eric@x.com', 1)")
    c.commit()
px = lc.pixel_for("Eric@x.com", subject="Your handicap", db_path=DB)
check("one known person: a 1x1 pixel", px.startswith("<img") and "/o/" in px, px)
check("a CC means no pixel (Kerry's copy would count as Eric)",
      lc.pixel_for("eric@x.com", cc="kerry@thegolffellowship.com", subject="x", db_path=DB) == "")
check("staff and unknown addresses get none",
      lc.pixel_for("kerry@thegolffellowship.com", db_path=DB) == "" and lc.pixel_for("who@x.com", db_path=DB) == "")
check("two recipients get none", lc.pixel_for("eric@x.com, b@x.com", db_path=DB) == "")
tag = px.split("/o/")[1].split(".gif")[0]
r = cl.get(f"/o/{tag}.gif", headers={"User-Agent": "Mozilla/5.0 (via ggpht.com GoogleImageProxy)"},
           environ_base={"REMOTE_ADDR": "66.1.1.1"})
check("the pixel route answers a gif, never cached",
      r.status_code == 200 and r.mimetype == "image/gif" and "no-store" in r.headers.get("Cache-Control", ""))
e = lc.engagement(db_path=DB)["by_customer"][851]
check("a Gmail open counts as Eric opening it", e["sent"] == 1 and e["opened"] == 1, e)
cl.get(f"/o/{tag}.gif", headers={"User-Agent": "Mozilla/5.0"}, environ_base={"REMOTE_ADDR": "17.58.1.1"})
e = lc.engagement(db_path=DB)["by_customer"][851]
check("an Apple privacy preload is 'unknown', not an open", e["opened"] == 1 and e["unknown"] == 1, e)
check("a forged pixel logs nothing",
      cl.get("/o/abc.def.gif").status_code == 200 and lc.engagement(db_path=DB)["by_customer"][851]["opened"] == 1)
with db._connect(DB) as c:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (900, 'Never', 'Opens')")
    c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (900, 'never@x.com', 1)")
    c.commit()
for i in range(3):
    lc.pixel_for("never@x.com", subject=f"m{i}", db_path=DB)
nv = lc.engagement(db_path=DB)["never_engaged"]
check("three emails, no open, no click: listed as never engaged (nobody removed)",
      [900, "Never Opens", 3] in nv and not any(x[0] == 851 for x in nv), nv)
check("the send path adds the pixel", "pixel_for" in open("email_parser/fetcher.py").read())
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
