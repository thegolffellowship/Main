"""THE POST-ROUND INTERVIEW BY EMAIL (Kerry 2026-10-29, Event Ops #2462).

- Who qualifies: City MVP / TGF MVP (recorded payouts), eagle or better,
  3+ birdies; two birdies do not.
- LOCKED: dial ai_interview_email off (default) or the wording unstamped ->
  the closeout hook sends nothing; on + stamped + payouts recorded -> one
  email per qualifier, once; a qualifier with no email is skipped.
- Signed links: tamper fails; a preview link saves nothing.
- Answers: stored per player; one follow-up per answer from the model (mocked;
  none without a key); only consented answers reach the recap.
- The recap waits for unfinished interviews only while the dial is on and
  inside the window; the recap writer adds quotes (and their dollar figures)
  only when there are some.
- Routes: GET saves nothing; the no-JS form and the JSON calls save.
Run: python3 test_ai_interview.py
"""
import contextlib, io, json, logging, os, sqlite3, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "ui-test")
os.environ.pop("ANTHROPIC_API_KEY", None)
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)
    import app as appmod
from email_parser import ai_interview as ai        # noqa: E402
from email_parser import results_email as rem      # noqa: E402
from email_parser import closeout_chain as cc      # noqa: E402
from email_parser import recap_writer as rw        # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

c = sqlite3.connect(DB)
c.execute("INSERT INTO events (id, item_name, event_date, chapter, course) VALUES (900, 's9.31 Test', '2026-10-31', 'San Antonio', 'Test GC')")
for cid, fn, ln in ((801, "Mvp", "Man"), (802, "Eagle", "Eye"), (803, "Bird", "Ie"), (804, "Two", "Birds"), (805, "No", "Mail")):
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
    if cid != 805:
        c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?,?,1)", (cid, f"p{cid}@example.com"))
c.commit()

PAR = {h: {"par": 4} for h in range(1, 10)}
def card(strokes):
    return {"round": {}, "meta": PAR, "holes": [{"hole_number": i + 1, "strokes": s} for i, s in enumerate(strokes)]}
FACTS = {"payouts": {801: [{"category": "mvp", "amount": 50, "description": ""}],
                     804: [{"category": "skins", "amount": 10, "description": ""}]},
         "cards": {801: card([4] * 9), 802: card([2, 4, 4, 4, 4, 4, 4, 4, 4]), 803: card([3, 3, 3, 4, 4, 4, 4, 4, 4]),
                   804: card([3, 3, 4, 4, 4, 4, 4, 4, 4]), 805: card([1, 4, 4, 4, 4, 4, 4, 4, 4])}}
rem.event_facts = lambda event_id, db_path=None: FACTS

print("== who qualifies ==")
q = {p["customer_id"]: p for p in ai.qualify(900)}
check("City MVP", [r["kind"] for r in q[801]["reasons"]] == ["mvp"], q.get(801))
check("eagle (2 on a par 4)", q[802]["reasons"][0]["kind"] == "eagle" and q[802]["reasons"][0]["holes"] == [1], q.get(802))
check("3 birdies", q[803]["reasons"][0] == {"kind": "birdies", "n": 3, "holes": [1, 2, 3], "streak": 3}, q.get(803))
check("two birdies do not qualify", 804 not in q)
check("a hole-in-one", q[805]["reasons"][0]["kind"] == "ace" and q[805]["email"] is None, q.get(805))
check("why reads plainly", q[802]["why"] == "Eagle on hole 1!" and q[803]["why"] == "3 birdies in a row!", (q[802]["why"], q[803]["why"]))

print("== the leading comment and the questions follow the achievement (Kerry 10/30) ==")
B = lambda holes: {"kind": "birdies", "n": len(holes), "holes": holes, "streak": ai._streak(holes)}  # noqa: E731
check("4 in a row", ai.reason_text([B([4, 5, 6, 7])]) == "4 birdies in a row!")
check("4, 3 in a row", ai.reason_text([B([2, 5, 6, 7])]) == "4 birdies, and 3 were in a row!")
check("3 apart", ai.reason_text([B([2, 5, 9])]) == "3 birdies!")
check("MVP + birdies: what got them there",
      ai.reason_text([{"kind": "mvp"}, B([2, 5, 9, 14])])
      == "You were the City MVP, and your 4 birdies helped get you there!",
      ai.reason_text([{"kind": "mvp"}, B([2, 5, 9, 14])]))
check("both MVPs + an eagle",
      ai.reason_text([{"kind": "tgf_mvp"}, {"kind": "mvp"}, {"kind": "eagle", "holes": [7]}])
      == "You were the City MVP and the TGF MVP, and the eagle on 7 helped get you there!")
check("eagle + birdies, no MVP", ai.reason_text([B([1, 2, 3]), {"kind": "eagle", "holes": [7]}])
      == "An eagle on hole 7, plus 3 birdies in a row!")
qs = ai.questions_for([{"kind": "eagle", "holes": [7]}])
check("eagle questions", qs == ["Walk us through the eagle on 7: the shots, the distances, the clubs, how it went in.",
                                "How did the rest of your round go?", "Is there anything else you'd like to add?"], qs)
qs = ai.questions_for([B([2, 5, 9, 14]), {"kind": "mvp"}])
check("MVP first, then one birdie question, then anything else",
      qs == ["Where did the round turn your way?", "What was working for you out there?",
             "Which of your 4 birdies was the best, and what happened?",
             "Is there anything else you'd like to add?"], qs)
qs = ai.questions_for([{"kind": "ace", "holes": [3]}, {"kind": "eagle", "holes": [7, 12]},
                       {"kind": "mvp"}, B([1, 2, 5])])
check("at most two extra questions", len(qs) == 5 and qs[2] == "Tell us about the eagle on 7 and 12: the shots and the clubs."
      and qs[3] == "Where did the round turn your way?", qs)

print("== locked: dial + wording stamp ==")
SENT = []
sender = lambda to, s, h: SENT.append((to, s, h)) or True       # noqa: E731
check("dial off by default: nothing", ai.closeout_hook(900, sender=sender) is None and not SENT)
db.set_app_setting("ai_interview_email", "on")
check("on but wording unstamped: nothing", ai.closeout_hook(900, sender=sender) is None and not SENT)
db.set_app_setting("ai_interview_approved", ai.template_hash())
db.set_app_setting("closeout_start:900", datetime.now().strftime("%Y-%m-%d %H:%M"))
# the MVP comes from the recorded payouts: hide it until the money is in
_payouts = FACTS["payouts"]; FACTS["payouts"] = {}
r = ai.closeout_hook(900, sender=sender)
check("CLOSEOUT START: the eagle and the birdies go at once (Kerry 10/30)",
      sorted(r["sent"]) == [802, 803] and len(SENT) == 2, r)
check("the recap waits for the MVP pass", "MVP" in (ai.recap_wait([900]) or ""), ai.recap_wait([900]))
check("nothing new before the money", ai.closeout_hook(900, sender=sender) is None and len(SENT) == 2)
FACTS["payouts"] = _payouts
db.set_app_setting("closeout_chain:900", json.dumps({"steps": {"payouts": {"ok": True}}}))
r = ai.closeout_hook(900, sender=sender)
check("payouts recorded: the MVP gets theirs", r["sent"] == [801] and len(SENT) == 3, r)
check("the recap now waits on the unfinished answers", "interview answers" in (ai.recap_wait([900]) or ""))
check("the wait is 90 minutes from closeout start", ai.DEFAULT_WAIT == 90
      and "up to 90 more minute" in (ai.recap_wait([900]) or ""), ai.recap_wait([900]))
check("after 90 minutes the recap goes anyway",
      ai.recap_wait([900], now=datetime.now() + timedelta(minutes=91)) is None)
# money recorded only after the wait: the recap has gone, so no late MVP ask
_old = (datetime.now() - timedelta(minutes=95)).strftime("%Y-%m-%d %H:%M")
db.set_app_setting("ai_interview:901", json.dumps({"sent_at": _old, "people": {}}))
db.set_app_setting("closeout_chain:901", json.dumps({"steps": {"payouts": {"ok": True}}}))
n = len(SENT)
r9 = ai.closeout_hook(901, sender=sender, now=datetime.now())
check("payouts after the wait: nobody new is asked", len(SENT) == n and "skipped" in (r9 or {}), r9)
check("no email on file is skipped, said so", r["skipped"] == [{"customer_id": 805, "why": "no email on file"}], r)
check("the email carries the signed link and the reason",
      all("/interview/" in h for _, _, h in SENT) and any("Eagle on hole 1!" in h for _, _, h in SENT))
check("never a second time", ai.closeout_hook(900, sender=sender) is None and len(SENT) == 3)
check("the hook never raises", ai.closeout_hook("x", sender=sender) in (None, {"error": "failed (logged)"}))

print("== links ==")
tok = ai.make_token(802, 900)
check("verifies", ai.verify_token(tok)["c"] == 802)
check("tamper fails", ai.verify_token(tok[:-1] + ("0" if tok[-1] != "0" else "1")) is None)
check("expired fails", ai.verify_token(ai.make_token(802, 900, now=datetime.utcnow() - timedelta(days=30))) is None)
check("another signer's token fails", ai.verify_token(__import__("email_parser.handicap_ask", fromlist=["x"]).make_token(802, 900)) is None)

print("== answers ==")
r = ai.record_answer(tok, 0, "Hit 7-iron to two feet on 1", ask=lambda s, u, m: "What did you see on the putt?")
check("stored, with one follow-up from the model", r == {"ok": True, "followup": "What did you see on the putt?"}, r)
r = ai.record_answer(tok, 0, "Straight in, $5 says it was luck", followup_q="What did you see on the putt?")
check("the follow-up answer asks nothing more", r == {"ok": True, "followup": None}, r)
check("no key, no follow-up (plain form)", ai.record_answer(tok, 1, "Driver", db_path=None)["followup"] is None)
check("NONE from the model means no follow-up", ai.followup("q", "a", ask=lambda s, u, m: "NONE") is None)
check("a model failure means no follow-up", ai.followup("q", "a", ask=lambda s, u, m: 1 / 0) is None)
check("bad question refused", not ai.record_answer(tok, 9, "x")["ok"])
pv = ai.make_token(803, 900, preview=True)
ai.record_answer(pv, 0, "preview words")
check("a preview link saves nothing", "803" not in ai._json(ai.ANSWERS_KEY.format(900)))
check("no consent yet -> no quotes", ai.consented_quotes(900) == [])

print("== the recap waits, only while the dial is on ==")
w = ai.recap_wait([900])
check("unfinished, inside the window: wait", w and "interview" in w, w)
db.set_app_setting("ai_interview_email", "off")
check("dial off: no wait", ai.recap_wait([900]) is None)
db.set_app_setting("ai_interview_email", "on")
db.set_app_setting("ai_interview_wait_minutes", "0")
check("window over: no wait", ai.recap_wait([900]) is None)
db.set_app_setting("ai_interview_wait_minutes", "30")
src = open(cc.__file__).read()
check("step_recap consults the wait, guarded", "_ai.recap_wait(ids" in src and "except Exception:\n        _w = None" in src)

ai.finish(tok, consent=True)
ai.finish(ai.make_token(801, 900), consent=False, answers={0: "never quote me"})
qs = ai.consented_quotes(900)
check("only the consenting player's words", {x["customer_id"] for x in qs} == {802} and len(qs) == 3, qs)
check("a finished player answers no more", not ai.record_answer(tok, 2, "late")["ok"])

print("== the recap writer ==")
facts = {"events": [{"quotes": [{"customer_id": 802, "answer": "Straight in, $5 says it was luck"}], "payouts": [],
                     "players": [], "points": {}}], "hio_pot": None}
check("a dollar figure a player said is allowed", 5.0 in rw._amounts(facts))
check("quote rules only when there are quotes", "quotes" in rw._extras_rules(facts)
      and rw._extras_rules({"events": [{}]}) == "")
src = open(rw.__file__).read()
check("night_facts adds quotes only when present", 'if qs:\n                e["quotes"] = qs' in src)

print("== routes ==")
with appmod.app.test_client() as tc:
    t3 = ai.make_token(803, 900)
    h = tc.get(f"/interview/{t3}")
    check("GET renders this player's questions (the birdie set)", h.status_code == 200
          and "Which birdie was the best, and what happened?" in h.get_data(as_text=True)
          and ai.LAST_QUESTION.replace("'", "&#39;") in h.get_data(as_text=True))
    page = h.get_data(as_text=True)
    check("permission is a Yes / No question, not a tick box (Kerry 10/30)",
          ai.CONSENT_LABEL in page and 'value="yes"' in page and 'value="no"' in page
          and 'type="checkbox"' not in page)
    check("GET saves nothing", "803" not in ai._json(ai.ANSWERS_KEY.format(900)))
    check("a bad link is 400", tc.get("/interview/nope").status_code == 400)
    r = tc.post(f"/interview/{t3}", data={"a0": "Chip-in on 9", "a1": "", "a2": "", "consent": "yes"})
    check("the no-JS form saves with consent", r.status_code == 200 and any(
        x["customer_id"] == 803 and x["answer"] == "Chip-in on 9" for x in ai.consented_quotes(900)))
    t5 = ai.make_token(805, 900)
    tc.post(f"/interview/{t5}", data={"a0": "Keep this private", "a1": "", "a2": "", "consent": "no"})
    check("the no-JS form: No -> not quoted", all(x["customer_id"] != 805 for x in ai.consented_quotes(900)))
    t1 = ai.make_token(804, 900)
    r = tc.post(f"/interview/{t1}/answer", json={"q": 0, "text": "Driver"})
    check("JSON answer 200", r.status_code == 200 and r.get_json()["ok"])
    r = tc.post(f"/interview/{t1}/finish", json={"consent": False})
    check("JSON finish, no consent -> not quoted", r.status_code == 200 and all(x["customer_id"] != 804 for x in ai.consented_quotes(900)))

print("== preview: staff only ==")
r = ai.send_preview(900, "someone@example.com")
check("a non-staff address is refused", "refused" in (r.get("error") or ""), r)
p = ai.plan(900)
check("the plan lists who and why, and the locks",
      {x["customer_id"] for x in p["qualifies"]} == {801, 802, 803, 805} and p["dial_on"] and p["approved"], p)
m = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")).read()
check("bridge exists", 'cmd == "scoring-ai-interview"' in m)
sw = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_parser", "scoring_window.py")).read()
check("wired at CLOSEOUT START, guarded", "_ai.closeout_hook(eid" in sw and 'interview hook failed' in sw)

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
