"""The Lone Star Cup WEEKEND EMAIL (Kerry 2026-10-09: "a full directive for the
weekend, everyone's individual times and pairings customized ... Add these
scorer notes in that email, also include on the event info in tracker").

Pins: one message per Cup player built from THE DRAW (match numbers through
the weekend, AM/PM times, partner and opponents, Sunday's group), the
scorer notes from the one copy, staff-only preview, and a member send that
refuses without confirm + the exact batch's approval code and never mails a
player twice.

Run: python3 test_lsc_weekend_email.py
"""
import os, sys, json, tempfile, contextlib, io, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-lscweek-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser import lsc_weekend_email as lwe                 # noqa: E402
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


EV = 3329
P = {7: ("Matt", "Jenkins"), 294: ("Mike", "Jenkins"), 136: ("Pat", "Youngs"), 88: ("Jeff", "Young"),
     87: ("Adam", "Baker"), 109: ("Neal", "Cloer"), 18: ("Kerry", "Niester"), 4: ("John", "Wade")}
with db._connect(tmp) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date) VALUES (?, 'LONE STAR CUP', '2026-10-10')", (EV,))
    for c, (f, l) in P.items():
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (c, f, l))
    conn.commit()
db.set_app_setting("lsc_matches", json.dumps({"event_id": EV, "sessions": [
    {"id": "sat-am", "label": "FOURBALL", "format": "fourball", "date": "2026-10-10",
     "matches": [{"id": "SAT-AM-1", "tee_time": "8:30", "austin": [7, 294], "sa": [136, 88]}]},
    {"id": "sat-pm", "label": "FOURSOMES", "format": "chapman", "date": "2026-10-10",
     "matches": [{"id": "SAT-PM-1", "tee_time": "1:30", "austin": [7, 294], "sa": [136, 88]}]},
    {"id": "sun", "label": "SINGLES", "format": "singles", "date": "2026-10-11",
     "matches": [{"id": "SUN-1", "tee_time": "8:30", "austin": [7], "sa": [87]},
                 {"id": "SUN-2", "tee_time": "8:30", "austin": [109], "sa": [136]}]}]}), tmp)
db.resolve_player_email = lambda c, conn=None, db_path=None: "" if int(c) == 88 else f"p{int(c)}@example.com"
sent = []
lwe._graph = lambda to, subject, html: sent.append((to, subject, html)) or True

print("one message per Cup player, from THE DRAW")
b = lwe.build(tmp)
by = {m["customer_id"]: m for m in b["messages"]}
check("every Cup player with an email gets one; no email is held, named",
      sorted(by) == [7, 87, 109, 136, 294] and [h["customer_id"] for h in b["held"]] == [88], (sorted(by), b["held"]))
mj = by[7]["html"]
check("Matt's three rounds: match numbers through the weekend, AM/PM times",
      "Fourball: Match 1, 8:30 AM off Hole 1" in mj and "Foursomes (Chapman): Match 2, 1:30 PM off Hole 1" in mj
      and "Singles: Match 3, 8:30 AM off Hole 1" in mj, mj)
check("partner and opponents by name", "You &amp; Mike Jenkins v Pat Youngs &amp; Jeff Young" in mj
      and "You v Adam Baker" in mj, mj)
check("Sunday names the other match in the group", "Playing in your group: Match 4, Neal Cloer v Pat Youngs." in mj, mj)
check("days headed in order", mj.index("Saturday, October 10") < mj.index("Sunday, October 11"))
check("his team named", "You play for <strong>Austin</strong>" in mj)
check("the formats and the points line", "Foursomes (Chapman):" in mj and "28 points in all" in mj)
check("every scorer note is in it", all(lwe._e(n) in mj for n in lwe.SCORER_NOTES))
check("links to the live board and Event Info", lwe.BOARD_URL in mj and lwe.INFO_URL in mj)
check("Adam (one round) gets Sunday only", "Match 3" in by[87]["html"] and "Fourball:" not in by[87]["html"].split("The formats")[0])

print("the send is gated on Kerry's word for this exact batch")
r = lwe.send(approval=b["hash"], confirm=False, db_path=tmp)
check("no confirm: nothing sent", r["sent"] == 0 and not sent, r)
r = lwe.send(approval="wrong", confirm=True, db_path=tmp)
check("wrong approval code: nothing sent", r["sent"] == 0 and not sent, r)
r = lwe.send(approval=b["hash"], confirm=True, db_path=tmp)
check("confirm + the code: each player once", r["sent"] == 5 and len(sent) == 5
      and {t for t, _, _ in sent} == {f"p{c}@example.com" for c in (7, 87, 109, 136, 294)}, r)
r = lwe.send(approval=b["hash"], confirm=True, db_path=tmp)
check("a second send mails nobody twice", r["sent"] == 0 and len(r["skipped_already_sent"]) == 5 and len(sent) == 5, r)

print("preview is staff only")
pv = lwe.send_preview(to="someone@example.com", db_path=tmp)
check("a non-staff address is refused", "error" in pv, pv)

print("the same notes on EVENT INFO")
body = open("templates/_lsc_info_body.html", encoding="utf-8").read()
app_src = open("app.py", encoding="utf-8").read()
js = open("static/js/lsc-info.js", encoding="utf-8").read()
check("Event Info carries a Scoring tab from the one copy",
      'data-s="scoring"' in body and 'data-sec="scoring"' in body and "scorer_notes=SCORER_NOTES" in app_src
      and 'scoring: "scoring"' in js)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
