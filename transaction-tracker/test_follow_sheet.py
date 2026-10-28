"""THE LIVE ROUND FOLLOWS THE SHEET, the manager's tee change, and the
handicap-link answers (Kerry 10/27, CoS #2425/#2426/#2429).

A. Every saved change to the sheet re-derives the live round until first tee;
   a group the sheet no longer has is dropped whatever its number (Silverhorn
   10/27: the consolidation left an empty "Hole 3B", group 6 of 1-5 and 7).
B. A manager changes one player's tee for one event; the sheet, the playing
   handicap and the live card follow; it is logged with who.
C. No index: starting handicap = low usual score - 72 (a 9-hole score doubled),
   and the manager gets an email for every answer, Kerry CC'd.

Run: python3 test_follow_sheet.py
"""
import os, sys, io, contextlib, logging, tempfile, time, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import score_entry as se
    from email_parser import live_scoring_default as lsd
    from email_parser import handicap_ask as ha
    from email_parser import fetcher
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

fetcher.send_mail_graph = lambda **kw: True
EV, NAME = 9301, "s9.60 FOLLOW"
PEOPLE = [(990101 + i, f"P{i} Player") for i in range(12)]
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                 "start_time, course) VALUES (?, ?, '2030-10-22', 'San Antonio', 'active', '9-hole', "
                 "'Shotgun', '16:30', 'Test GC')", (EV, NAME))
    for cid, nm in PEOPLE:
        fn, ln = nm.split()
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, ?)", (cid, fn, ln))
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, side_games, "
                     "tee_choice, transaction_status, order_date, order_id, email_uid, merchant) VALUES "
                     "(?, ?, ?, ?, '9', 'NONE', '65+', 'active', '2026-10-01', ?, ?, 'GoDaddy')",
                     (nm, cid, NAME, EV, f"R{cid}", f"m-{cid}"))
    conn.commit()


def sheet(groups):
    db.save_event_pairings(EV, {"9": [
        {"group_num": n, "slot_label": lab, "players": [
            {"name": PEOPLE[i][1], "cart_pos": k + 1, "customer_id": PEOPLE[i][0]} for k, i in enumerate(idx)]}
        for n, lab, idx in groups]}, db_path=DB)


def round_groups():
    rid = lsd.se_round_id(EV, "9", DB)
    with db._connect(DB) as conn:
        return {r[0]: sorted(x[0] for x in conn.execute(
            "SELECT customer_id FROM se_players WHERE group_id = ?", (r[1],)))
            for r in conn.execute("SELECT group_num, id FROM se_groups WHERE round_id = ?", (rid,))}


BEFORE = datetime(2030, 10, 21, 17, 30)        # Monday evening, before the 4:30 PM shotgun
AFTER = datetime(2030, 10, 22, 16, 45)         # Tuesday, on the course

print("A. The live round follows the sheet until first tee")
sheet([(1, "1A", [0, 1, 2, 3]), (2, "1B", [4, 5, 6, 7]), (3, "2A", [8, 9, 10, 11])])
lsd.live_scoring_auto_check(BEFORE, DB)
check("seeded: three groups", sorted(round_groups()) == [1, 2, 3], round_groups())
# Monday 9:59 PM: 12 -> 8, consolidated; the sheet keeps groups 1 and 3.
with db._connect(DB) as conn:
    for i in (4, 5, 6, 7):
        conn.execute("UPDATE items SET transaction_status = 'credited' WHERE customer_id = ?", (PEOPLE[i][0],))
    conn.commit()
sheet([(1, "1A", [0, 1, 2, 3]), (3, "2A", [8, 9, 10, 11])])
res = lsd.follow_sheet(EV, DB, now=BEFORE)
g = round_groups()
check("the group the sheet no longer has is DROPPED, even in the middle of the numbers (Hole 3B)",
      sorted(g) == [1, 3], (g, res))
check("…and the kept groups hold exactly the sheet's players",
      g[1] == sorted(PEOPLE[i][0] for i in (0, 1, 2, 3)) and g[3] == sorted(PEOPLE[i][0] for i in (8, 9, 10, 11)), g)
check("the re-seed reports it", any(v for k, v in (res.get("rounds") or {}).items()) and res.get("enabled"), res)
sheet([(1, "1A", [0, 1, 8, 9]), (3, "2A", [2, 3, 10, 11])])
lsd.follow_sheet(EV, DB, now=BEFORE)
g = round_groups()
check("a swap on the sheet reaches the cards", PEOPLE[8][0] in g[1] and PEOPLE[2][0] in g[3], g)
sheet([(1, "1A", [0, 1, 2, 3]), (3, "2A", [8, 9, 10, 11])])
held = lsd.follow_sheet(EV, DB, now=AFTER)
g = round_groups()
check("after first tee the round is NOT re-derived (a group never relinks mid-round)",
      PEOPLE[8][0] in g[1] and held.get("held", {}).get("9") == "first tee passed", (g, held))
check("follow_sheet never creates a round", lsd.follow_sheet(424242, DB, now=BEFORE).get("skipped"))
sheet([(1, "1A", [0, 1, 2, 3]), (3, "2A", [8, 9, 10, 11])])
lsd.follow_sheet(EV, DB, now=BEFORE)

print("B. The manager's tee change")
P0 = PEOPLE[0][0]
check("a band that is not one of the four is refused", db.set_event_tee(EV, P0, "Blue", set_by="t", db_path=DB).get("error"))
check("someone not on the roster is refused", db.set_event_tee(EV, 1, "<50", set_by="t", db_path=DB).get("error"))
r = db.set_event_tee(EV, P0, "<50", set_by="manager (San Antonio)", db_path=DB)
check("the change saves: before 65+, now <50, the order row too", r.get("before") == "65+"
      and r.get("tee") == "<50" and r.get("items_updated") == 1, r)
with db._connect(DB) as conn:
    row = next(d for d in db._event_roster_rows(conn, EV) if d["customer_id"] == P0)
    log = conn.execute("SELECT description FROM agent_action_log WHERE action_type = 'set_event_tee' "
                       "ORDER BY id DESC LIMIT 1").fetchone()
check("the roster reads the manager's tee", row["tee_choice"] == "<50" and row.get("tee_source") == "manager", row)
check("it is logged with who", log and "manager (San Antonio)" in log[0] and "65+ -> <50" in log[0], log)
pack = db.get_event_print_pack(EV, db_path=DB)
pp = next(p for gg in pack["groups"] for p in gg["players"] if p["customer_id"] == P0)
check("the sheet prints the new tee", pp.get("tee_choice") == "<50", pp)
lsd.follow_sheet(EV, DB, now=BEFORE)
with db._connect(DB) as conn:
    t = conn.execute("SELECT tee FROM se_players WHERE customer_id = ?", (P0,)).fetchone()
check("the live card follows", t and t[0] == "<50", t)

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as _app
cl = _app.app.test_client()
check("the tee route needs a login", cl.post(f"/api/events/{EV}/tee", json={}).status_code == 401)
with cl.session_transaction() as s:
    s["role"] = "manager"; s["chapter"] = "Austin"; s["authenticated"] = True
check("an Austin manager cannot change a San Antonio player's tee",
      cl.post(f"/api/events/{EV}/tee", json={"customer_id": P0, "tee": "50-64"}).status_code == 403)
with cl.session_transaction() as s:
    s["chapter"] = "San Antonio"
rr = cl.post(f"/api/events/{EV}/tee", json={"customer_id": P0, "tee": "50-64"})
check("the San Antonio manager can, and the answer names the player", rr.status_code == 200
      and rr.get_json().get("tee") == "50-64" and rr.get_json().get("name"), rr.get_json())
ok = False
for _ in range(50):          # the after-request hook runs in a thread
    with db._connect(DB) as conn:
        t = conn.execute("SELECT tee FROM se_players WHERE customer_id = ?", (P0,)).fetchone()
    if t and t[0] == "50-64":
        ok = True
        break
    time.sleep(0.1)
check("the save itself re-derives the live card (no job needed)", ok, t)
html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "events.html")).read()
check("ROSTER (desktop + phone) and PAIRINGS render the tee through the one picker",
      html.count("teePickHtml(") >= 5 and "/api/events/${evId}/tee" in html)

print("C. Handicap-link answers")
check("low score minus 72: 90-100 for 18 -> 18.0",
      ha.starting_from_scores(ha.validate({"kind": "none", "score_low": "90", "score_high": "100"})) == 18.0)
check("a single score is the low end: 95 -> 23.0",
      ha.starting_from_scores(ha.validate({"kind": "none", "score_low": "95"})) == 23.0)
check("a 9-hole score is doubled first: 45-50 for 9 -> 18.0",
      ha.starting_from_scores(ha.validate({"kind": "none", "score_low": "45", "score_high": "50"})) == 18.0)
nothing = ha.validate({"kind": "none"})
check("no number: nothing to set", nothing.get("error") is None and ha.starting_from_scores(nothing) is None, nothing)
ev = {"id": EV, "item_name": NAME}
m = ha.manager_message("Alex Porter", ev, nothing, None, False, base_url="https://x.test")
check("no number: the manager's email says NOTHING SET, with a one-tap link",
      "NOTHING SET" in m["subject"] and f"/events?event={EV}" in m["html"] and "Change it on the roster" in m["html"], m)
a = ha.validate({"kind": "none", "score_low": "90", "score_high": "100"})
m = ha.manager_message("Alex Porter", ev, a, 18.0, True, base_url="https://x.test")
check("the rule: the email quotes the player's words and the number",
      "18.0" in m["subject"] and "usually shoots 90-100 for 18" in m["subject"], m["subject"])
sent = []
res = ha.notify_manager(P0, EV, a, 18.0, applied=True, db_path=DB,
                        sender=lambda to, s, h, cc: sent.append((to, s, cc)) or True)
check("every answer emails the chapter manager, Kerry CC'd (or Kerry alone when he is the manager)",
      res.get("sent") and sent and (sent[0][2] == "kerry@thegolffellowship.com"
                                    or sent[0][0] == "kerry@thegolffellowship.com"), (res, sent))
with db._connect(DB) as conn:
    conn.execute("UPDATE customers SET starting_handicap_18 = 18.0, starting_handicap_set_by = 'admin' "
                 "WHERE customer_id = ?", (P0,))
    conn.commit()
st = ha.load_state(DB)
st[str(P0)] = {"status": "need", "answer": {"kind": "none", "score_low": None, "score_high": None},
               "answered_at": "2026-10-26T22:30:00Z"}
ha._save_state(st, DB)
rows = ha.status_rows([P0], missing_ids=[], db_path=DB)
check("a number the manager typed replaces Needs a number (Alex Porter, 10/27)",
      rows and rows[0]["status"] == "manager_set" and "set by manager: 18.0" in rows[0]["line"], rows)

print("D. Closest to the pin on the hole (Kerry 10/27)")
se_html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "score_entry.html")).read()
box = se_html[se_html.index("function ctpBox("):se_html.index("function holeScreen(")]
check("the hole screen shows the box, on contest holes only",
      "${ctpBox(hole)}" in se_html and 'c.kind !== "ctp"' in box and "card.ctp" in box)
check("label and name only: no LIVE, no group, no time, no takeover, no distance (Kerry 10/27)",
      "Closest to the pin" in box and "No one on the green yet" in box
      and not any(w in box for w in ("LIVE", "Live", "group_num", "Group", "since", "Taken over", " ft ")), box)

print()
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
