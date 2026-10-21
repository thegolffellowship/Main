"""AFTER-LOCK CHANGES (Kerry 2026-10-20 #2139; #2168 "No manager approval
needed but cc the manager on all changes"). Graph is mocked: nothing leaves.
- the Event Info send saves the sheet it carried;
- a MOVED player: he and both groups get UPDATED GROUP, manager CC'd;
- an ADDED player gets his Event Info (and the send is recorded);
- a TEE change / GAMES change: a notice to that player only, manager CC'd;
- every change sends once; the course gets only the changed sheets.
Run: python3 test_after_lock.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import event_day_email as ede
    from email_parser import fetcher
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

# Graph is mocked for the whole file: no real mail can leave.
SENT = []
def fake_send(**kw):
    SENT.append(kw); return True
fetcher.send_mail_graph = fake_send
for k, v in (("AZURE_TENANT_ID", "t"), ("AZURE_CLIENT_ID", "c"), ("AZURE_CLIENT_SECRET", "s"),
             ("EMAIL_ADDRESS", "tracker@example.test")):
    os.environ[k] = v

EV, EV2 = 9101, 9102
PEOPLE = [  # cid, first, last, email, side_games
    (880001, "Ann", "Able", "ann@example.test", "NET"),
    (880002, "Bob", "Baker", "bob@example.test", "BOTH"),
    (880003, "Cal", "Cole", "cal@example.test", "NONE"),
    (880004, "Dee", "Dunn", "dee@example.test", "GROSS"),
    (880005, "Eli", "Eno", None, "NET"),                   # seated, no email
    (880006, "Fay", "Fox", "fay@example.test", "NET"),     # on roster, not seated
    (880007, "Gus", "Gray", "gus@example.test", "NONE"),
]
with db._connect(DB) as conn:
    for eid, name in ((EV, "s9.99 TEST LINKS"), (EV2, "s9.98 UNSAVED LINKS")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, "
                     "start_type, start_time, course) VALUES (?, ?, '2026-10-13', 'San Antonio', "
                     "'active', '9-hole', 'Shotgun', '08:00', 'Test Links GC')", (eid, name))
    for cid, fn, ln, em, sg in PEOPLE:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                     "VALUES (?,?,?,'active_member')", (cid, fn, ln))
        if em:
            conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?,?,1)", (cid, em))
        for eid, name in ((EV, "s9.99 TEST LINKS"), (EV2, "s9.98 UNSAVED LINKS")):
            conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, tee_choice, "
                         "side_games, transaction_status, order_date, order_id, email_uid, merchant) "
                         "VALUES (?, ?, ?, ?, '9', '50-64', ?, 'active', '2026-10-01', ?, ?, 'GoDaddy')",
                         (f"{fn} {ln}", cid, name, eid, sg, f"R{cid}{eid}", f"manual-{cid}-{eid}"))
    conn.commit()
db.set_event_bundle_offers(EV, ["NET", "GROSS"], db_path=DB)
db.save_event_pairings(EV, {"9": [
    {"group_num": 1, "slot_label": "1A", "players": [
        {"name": "Ann Able", "cart_pos": 1, "customer_id": 880001},
        {"name": "Bob Baker", "cart_pos": 2, "customer_id": 880002},
        {"name": "Cal Cole", "cart_pos": 3, "customer_id": 880003},
        {"name": "Dee Dunn", "cart_pos": 4, "customer_id": 880004}]},
    {"group_num": 2, "slot_label": "1B", "players": [
        {"name": "Eli Eno", "cart_pos": 1, "customer_id": 880005},
        {"name": "Gus Gray", "cart_pos": 2, "customer_id": 880007}]}]}, db_path=DB)

# The GAMES tab as page_probe returns it (trimmed from s9.27 The Quarry,
# 10/12): the card is built from this, never recomputed.
GAMES_TAB = {
    "counts": {"players": 7, "net": 3, "gross": 2},
    "sections": [
        {"section": "INCLUDED GAMES (7 players)", "rows": [
            {"game": "TEAM Net", "pot": "$80", "1st": "$80"},
            {"game": "CTP #1", "pot": "$20"}],
         "subtotal": {"pot": "$100"}},
        {"section": "NET GAMES (3 players)", "rows": [
            {"game": "Individual Net", "pot": "$117", "flights": "2"},
            {"game": "Low Flight", "1st": "$58.50", "2nd": "\u2014", "sub": True},
            {"game": "High Flight", "1st": "$58.50", "2nd": "\u2014", "sub": True},
            {"game": "TGF MVP \U0001F517", "pot": "$46"},
            {"game": "Test Links GC", "pot": "$26", "sub": True}],
         "subtotal": {"pot": "$163"}},
        {"section": "GROSS GAMES (2 players)", "rows": [
            {"game": "Skins Gross", "pot": "$104", "flights": "2"},
            {"game": "Per skin: 1=$52, 2=$26, 3=$17.33", "sub": True},
            {"game": "Ind. Gross", "note": "No Game", "disabled": True}],
         "subtotal": {"pot": "$104"}}],
    "total": {"pot": "$367"},
    "hole_in_one": ["Hole-in-One Pot: $33 (a9.27 $13 + s9.27 $20)", ""],
    "buyers": {"players": [{"customer_id": c} for c in (880001, 880002, 880003, 880004, 880005, 880006, 880007)],
               "net": [{"customer_id": c} for c in (880001, 880002, 880005)],
               "gross": [{"customer_id": c} for c in (880002, 880004)]},
    "mvp_link": {"linked": [{"event_name": "a9.27 Forest Creek", "course": "Forest Creek Golf Club",
                             "chapter": "Austin"}]},
    "team_type": "TEAM Net",
}
ede._read_games_tab = lambda eid: GAMES_TAB   # no Chromium in a test


from email_parser import after_lock as al
from email_parser import print_pack as pp
tpl = ede.load_template(DB)
db.set_app_setting(ede.APPROVAL_KEY, tpl["hash"], db_path=DB)
MGR = "kerry@thegolffellowship.com"   # San Antonio's manager (pairings_approval default)

print("1. The Event Info send saves the sheet it carried")
check("no baseline before the send: nothing to compare", al.plan(EV, DB).get("skipped"))
r = ede.send_event_day_emails(EV, confirm=True, db_path=DB)
base = al._get(al.STATE_KEY.format(EV), DB)
check("the send recorded the sheet", base and set(base["players"]) >= {"880001", "880004", "880007"}, base)
check("…with group, start, tee and games", base["players"]["880001"]["games"] == ["NET"]
      and base["players"]["880002"]["games"] == ["GROSS", "NET"] and base["players"]["880001"]["tee"], base["players"]["880001"])
check("no change: nothing to send", al.run_event(EV, confirm=True, db_path=DB).get("status") == "no change")

def save(groups):
    db.save_event_pairings(EV, {"9": groups}, db_path=DB)
G1 = [{"name": "Ann Able", "cart_pos": 1, "customer_id": 880001},
      {"name": "Bob Baker", "cart_pos": 2, "customer_id": 880002},
      {"name": "Cal Cole", "cart_pos": 3, "customer_id": 880003}]
G2 = [{"name": "Eli Eno", "cart_pos": 1, "customer_id": 880005},
      {"name": "Gus Gray", "cart_pos": 2, "customer_id": 880007},
      {"name": "Dee Dunn", "cart_pos": 3, "customer_id": 880004}]

print("2. A moved player (Dee 1A -> 1B)")
save([{"group_num": 1, "slot_label": "1A", "players": G1}, {"group_num": 2, "slot_label": "1B", "players": G2}])
SENT.clear()
dry = al.run_event(EV, confirm=False, db_path=DB)
check("dry run: Dee is the one moved", dry["diff"]["moved"] == ["880004"] and dry.get("dry_run") and not SENT, dry.get("diff"))
r = al.run_event(EV, confirm=True, db_path=DB)
to = {s["to_address"]: s for s in SENT}
check("Dee and both groups are mailed (Eli has no email)",
      sorted(to) == sorted(["dee@example.test", "ann@example.test", "bob@example.test", "cal@example.test", "gus@example.test"]),
      sorted(to))
check("every email says UPDATED GROUP and CCs the manager",
      all(s["subject"].startswith("UPDATED GROUP: ") and s["cc_address"] == MGR for s in SENT))
check("Dee is told her new start", "Your group has changed" in to["dee@example.test"]["html_body"]
      and "1B" in to["dee@example.test"]["html_body"])
check("her old group hears she left, her new group that she joined",
      "Dee Dunn</strong> is no longer in your group" in to["ann@example.test"]["html_body"]
      and "Dee Dunn</strong> joins your group" in to["gus@example.test"]["html_body"])
check("no course send before the Course Files went", "not sent yet" in r["course"]["status"], r["course"])
n = len(SENT)
r = al.run_event(EV, confirm=True, db_path=DB)
check("the same change never sends twice", len(SENT) == n and r.get("status") == "no change", r)

print("3. A tee change (Ann) and a games change (Cal)")
with db._connect(DB) as conn:
    conn.execute("UPDATE items SET tee_choice = '65+' WHERE customer_id = 880001 AND event_id = ?", (EV,))
    conn.execute("UPDATE items SET side_games = 'NET' WHERE customer_id = 880003 AND event_id = ?", (EV,))
    conn.commit()
SENT.clear()
r = al.run_event(EV, confirm=True, db_path=DB)
to = {s["to_address"]: s for s in SENT}
check("only Ann and Cal are mailed", sorted(to) == ["ann@example.test", "cal@example.test"], sorted(to))
check("Ann: UPDATED TEES, manager CC'd", to["ann@example.test"]["subject"].startswith("UPDATED TEES: ")
      and to["ann@example.test"]["cc_address"] == MGR and "tees" in to["ann@example.test"]["html_body"])
check("Cal: UPDATED GAMES names the NET games", to["cal@example.test"]["subject"].startswith("UPDATED GAMES: ")
      and "NET</strong> games" in to["cal@example.test"]["html_body"])
check("a tee or games change never goes to the course", r["course"]["status"] == "no seat change", r["course"])

print("4. An added player (Fay, on the roster, now seated)")
save([{"group_num": 1, "slot_label": "1A", "players": G1 + [{"name": "Fay Fox", "cart_pos": 4, "customer_id": 880006}]},
      {"group_num": 2, "slot_label": "1B", "players": G2}])
SENT.clear()
r = al.run_event(EV, confirm=True, db_path=DB)
to = {s["to_address"]: s for s in SENT}
check("Fay and her new group are mailed", sorted(to) == ["ann@example.test", "bob@example.test", "cal@example.test", "fay@example.test"], sorted(to))
check("Fay is welcomed in, the group hears she joins", "You're in!" in to["fay@example.test"]["html_body"]
      and "Fay Fox</strong> joins your group" in to["bob@example.test"]["html_body"])
with db._connect(DB) as conn:
    row = conn.execute("SELECT status FROM event_day_email_sends WHERE event_id = ? AND customer_id = 880006", (EV,)).fetchone()
check("Fay's Event Info is recorded, so nothing else sends it", row and row[0] == "sent", row)

print("5. The course gets only the sheets that changed")
calls = []
pp.build_event_print_pack = lambda render, eid, sd, db_path=None: {
    "event": {"id": eid}, "part_shas": {"starter-sheet": "new", "cart-signs": "new", "scorecards": "same",
                                        "proximity-markers": "same", "rules-of-play": "same"}}
def fake_cf(built, db_path=None, only=None, updated=False):
    calls.append((only, updated)); return {"sent": True}
pp.send_course_files = fake_cf
prev = {"parts": {"starter-sheet": "old", "cart-signs": "old", "scorecards": "same",
                  "proximity-markers": "same", "rules-of-play": "same"}}
c = al._course_resend(EV, object(), "", prev, True, DB)
check("only the Starter Sheet and Cart Signs, marked updated",
      calls == [(("starter-sheet", "cart-signs"), True)] and c["status"] == "sent", (calls, c))
check("nothing changed: nothing goes", al._course_resend(EV, object(), "", {"parts": {
      "starter-sheet": "new", "cart-signs": "new", "scorecards": "same", "proximity-markers": "same",
      "rules-of-play": "same"}}, True, DB)["status"] == "no course sheet changed")

print("6. The job: today's events until the first tee; the dial")
from datetime import datetime
check("before the 8:00 AM shotgun it runs", al.check(now=datetime(2026, 10, 13, 7, 30), db_path=DB)["events"].get(EV, {}).get("status") == "no change",
      al.check(now=datetime(2026, 10, 13, 7, 30), db_path=DB))
check("after the first tee it stops", al.check(now=datetime(2026, 10, 13, 8, 5), db_path=DB)["events"][EV]["status"] == "first tee passed")
db.set_app_setting(al.DIAL, "off", db_path=DB)
check("dial off: nothing runs", al.check(now=datetime(2026, 10, 13, 7, 30), db_path=DB)["status"] == "off")
db.set_app_setting(al.DIAL, "", db_path=DB)

print("7. Wiring")
_a = open("app.py", encoding="utf-8").read()
check("the 15-minute job is registered", 'id="after_lock_changes"' in _a and "after_lock import check" in _a)
_pp = open("email_parser/print_pack.py", encoding="utf-8").read()
check("a Course Files send records the sheets it sent", "after_lock.record_course_files" in _pp)

print("\n" + (f"{len(F)} FAILED: {F}" if F else "ALL PASS"))
sys.exit(1 if F else 0)
