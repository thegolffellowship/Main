"""THE RESULTS CARD ON FACEBOOK (Event Ops #2460-J, proposal; wording to
Kerry first).

Covers: the card reads the RECORDED results (first places, skins, closest to
the pin; no 2nd place, no dollars) with the date and the /member/results link;
a champion photo only when the photo's people are this event's winners and its
season is the event's year; post_to_facebook refuses without META_PAGE_TOKEN
and never raises (Meta refusal, network error); feed vs photos edge; Instagram
off by default; every gate in order (dial social_auto_post OFF by default,
wording stamp social_post_approved = template hash, once per event); the hook
after the players' results email and not after the 6 AM send; the read-only
bridge.

Run: python3 test_social_post.py
"""
import os, sys, io, contextlib, logging, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.pop("META_PAGE_TOKEN", None)
os.environ.pop("IG_BUSINESS_ACCOUNT_ID", None)
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import social_post as sp
    from email_parser import results_email as rem
    db.init_db(DB)

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


EV, EV2, EV4 = 9501, 9502, 9504
with db._connect(DB) as conn:
    for eid, nm, d in ((EV, "s9.80 Results Card", "2026-11-03"), (EV2, "2025 TGF Championship", "2025-06-03"),
                       (EV4, "2026 TGF Championship", "2026-11-14")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, course) "
                     "VALUES (?, ?, ?, 'San Antonio', 'active', 'Test GC')", (eid, nm, d))
    for cid, fn, ln in ((42, "Gus", "Vasquez"), (990301, "Ann", "Able"), (990302, "Bob", "Baker"),
                        (990303, "Cy", "Cole")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, ?)", (cid, fn, ln))
    for i, (eid, d) in enumerate(((EV, "2026-11-03"), (EV2, "2025-06-03"), (EV4, "2026-11-14"))):
        t = conn.execute("INSERT INTO tgf_events (code, name, event_date, events_id) VALUES (?, ?, ?, ?) "
                         "RETURNING id", (f"C{eid}", f"ev {eid}", d, eid)).fetchone()[0]
        for cid, desc, amt in ((42, "auto: Ind Net place 1", 40), (990301, "auto: Ind Net place 2", 25),
                               (990302, "auto: Skins ×1 hole 4", 18), (990303, "auto: Skins ×1 hole 7", 18),
                               (990301, "auto: CTP hole 3", 20)):
            conn.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, description) "
                         "VALUES (?, ?, 'game', ?, ?)", (t, cid, amt, desc))
    conn.commit()

print("1. The card")
c = sp.build_results_card(EV, db_path=DB)
t = c["text"]
check("event, date and link", "s9.80 Results Card" in t and "Tuesday, November 3, 2026" in t
      and f"/member/results/{EV}" in t, t)
check("first place, skins and CTP named", "Individual Net: Gus Vasquez" in t
      and "Skins: Bob Baker, Cy Cole" in t and "Closest to the Pin, hole 3: Ann Able" in t, t)
check("no 2nd place, no dollar amounts", "place 2" not in t and "2nd" not in t and "$" not in t, t)
check("not held", c["held"] == [], c["held"])
check("a regular night: no cup photo for a winner who once won a cup", c["image_url"] is None, c["image_url"])
c4 = sp.build_results_card(EV4, db_path=DB)
check("the 2026 championship: Gus Vasquez's 2026 Fellowship Cup photo",
      c4["image_url"] and c4["image_url"].endswith("/member/photo/c/fellowship_cup-2026.jpg"), c4["image_url"])
c2 = sp.build_results_card(EV2, db_path=DB)
check("a 2025 championship gets no 2026 photo", c2["image_url"] is None, c2["image_url"])
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status) "
                 "VALUES (9503, 'Empty', '2026-11-04', 'San Antonio', 'active')")
    conn.commit()
check("no recorded winners: held", sp.build_results_card(9503, db_path=DB)["held"])

print("2. post_to_facebook")
r = sp.post_to_facebook("hello")
check("no META_PAGE_TOKEN: refused with why, no raise",
      r == {"posted": False, "why": "META_PAGE_TOKEN is not set on Railway"}, r)
calls = []
real_gp = sp._graph_post
sp._graph_post = lambda path, data: (calls.append((path, dict(data))) or {"ok": True, "body": {"id": "P1"}})
try:
    r = sp.post_to_facebook("hi", link="L", token="tok")
    check("text post goes to the page feed with the link",
          r == {"posted": True, "id": "P1"} and calls[-1][0] == f"{sp.DEFAULT_PAGE_ID}/feed"
          and calls[-1][1]["link"] == "L", (r, calls))
    r = sp.post_to_facebook("hi", image_url="https://x/y.jpg", token="tok")
    check("with an image: the photos edge, the text as caption",
          calls[-1][0].endswith("/photos") and calls[-1][1]["caption"] == "hi", calls[-1])
finally:
    sp._graph_post = real_gp
import requests  # noqa: E402
real_post = requests.post
requests.post = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network down"))
try:
    r = sp.post_to_facebook("hi", token="tok")
    check("a network error is returned, never raised", r["posted"] is False and "network down" in r["why"], r)
finally:
    requests.post = real_post


class _R:
    status_code = 400
    text = ""
    def json(self):
        return {"error": {"message": "(#200) permission"}}


requests.post = lambda *a, **k: _R()
try:
    r = sp.post_to_facebook("hi", token="tok")
    check("a Meta refusal is returned with its message", not r["posted"] and "(#200) permission" in r["why"], r)
finally:
    requests.post = real_post
check("Instagram is off by default",
      sp.post_to_instagram("x", "https://x/y.jpg", ig_user_id="1", token="t", db_path=DB)["why"]
      == "dial social_instagram is off")

print("3. The gates, in order")
check("dial social_auto_post is OFF by default", "dial social_auto_post is off" in
      sp.post_event(EV, db_path=DB)["why"])
db.set_app_setting(sp.DIAL, "on", db_path=DB)
r = sp.post_event(EV, db_path=DB)
check("dial on, wording not approved: refused", "wording not approved" in r["why"]
      and sp.template_hash() in r["why"], r)
db.set_app_setting(sp.APPROVAL_KEY, "0000", db_path=DB)
check("a stale stamp is refused too", "wording not approved" in sp.post_event(EV, db_path=DB)["why"])
db.set_app_setting(sp.APPROVAL_KEY, sp.template_hash(), db_path=DB)
r = sp.post_event(EV, db_path=DB)
check("approved but no token: recorded as not posted, says why",
      r["posted"] is False and "META_PAGE_TOKEN" in r["facebook"]["why"], r)
fb = []
real_fb = sp.post_to_facebook
sp.post_to_facebook = lambda *a, **k: (fb.append((a, k)) or {"posted": True, "id": "PAGE_POST"})
try:
    r = sp.post_event(EV, db_path=DB)
    check("approved + posting works: posted once", r["posted"] and len(fb) == 1, r)
    r2 = sp.post_event(EV, db_path=DB)
    check("once per event", r2["why"] == "already posted" and len(fb) == 1, r2)
    stamp = json.loads(db.get_app_setting(sp.POSTED_KEY.format(EV), db_path=DB))
    check("stamped with the post id", stamp["facebook"]["id"] == "PAGE_POST", stamp)

    print("4. The hook: after the players' results email only")
    real_deliver = rem.deliver
    rem.deliver = lambda ids, recap, confirm=False, db_path=None, who=None: {"state": "sent", "sent": 2}
    try:
        from datetime import datetime
        db.set_app_setting(rem.SCHEDULE_KEY, json.dumps({
            f"{EV2}": {"at": "2026-11-03T21:00", "recap": "x.md", "authority": "t", "state": "scheduled"},
            f"{EV2}|played": {"at": "2026-11-03T21:00", "recap": None, "authority": "t", "state": "scheduled"},
        }), db_path=DB)
        n0 = len(fb)
        out = rem.auto_check(now=datetime(2026, 11, 3, 21, 5), db_path=DB)
        sch = json.loads(db.get_app_setting(rem.SCHEDULE_KEY, db_path=DB))
        check("the players' send calls the social hook", "social" in sch[f"{EV2}|played"]
              and len(fb) == n0 + 1, sch)
        check("the everyone-else send does not", "social" not in sch[f"{EV2}"], sch)
    finally:
        rem.deliver = real_deliver
finally:
    sp.post_to_facebook = real_fb

print("5. Bridge, read only")
_m = open("mcp_server.py", encoding="utf-8").read()
check("scoring-social-post registered and calls preview only",
      'cmd == "scoring-social-post"' in _m
      and "_spo.preview(" in _m.split('cmd == "scoring-social-post"')[1][:900]
      and "post_event" not in _m.split('cmd == "scoring-social-post"')[1][:900])
pv = sp.preview(EV, db_path=DB)
check("preview returns the text and the gates", pv["text"] and "approval" in pv and pv["token_set"] is False, pv)

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
