"""THE NO-SHOW SCORER SEQUENCE, items 1-3 (Kerry 2026-09-30, mailbox #1021,
ratified; Pairings Spec v1.4 12.2; built 10/26 for 10/27).

Kerry 9/30: "on the first hole there needs to be an obvious red player
missing button at the bottom. Then that opens up a prompt of who it is.
Then follows up with the three answers" ... "It should ask each hole until
after 4 holes and then the player is taken off card." Kerry 10/26, for
both N's: "Both should be at 3p" -> 3 holes.

1. The scorer's answers: only the phone keeping score, only its own
   players; late / unknown / absent / present ("+ Player"); se_audit rows;
   "Don't know yet" counts holes and turns absent after N (dial
   no_show_absent_after_holes, default 3), and also once his group has
   scored N holes while he has none.
2. An absent player never holds the night: the card's final time, the
   entered-scores feed (no individual / MVP / points / handicap round from
   him), and his blank holes are never filled with par.
3. The course notice: one email per event after 3 holes, all names, manager
   CC'd, logged, once; "Running late" never counts; the dial stops it.
Plus the wiring: route, job, bridge, the red button on the hole screen.

Run: python3 test_no_show.py
"""
import contextlib
import io
import logging
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)
from email_parser import score_entry as se  # noqa: E402
from email_parser import no_show_notice as nsn  # noqa: E402
from email_parser import print_pack as pp  # noqa: E402
from email_parser import after_lock as al  # noqa: E402
from email_parser import pairings_approval as pa  # noqa: E402

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


conn = sqlite3.connect(DB)
for cid, fn, ln in [(401, "Sam", "Keeper"), (402, "Mo", "Late"), (403, "Ned", "Noshow"),
                    (404, "Al", "Unsure"), (411, "Other", "Scorer"), (412, "Ollie", "Other")]:
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
EV = 940
conn.execute("INSERT INTO events (id, item_name, event_date, chapter, course, status) "
             "VALUES (?, 's10.27 No Show Links', '2099-10-27', 'San Antonio', 'No Show Links', 'active')", (EV,))
conn.commit()
conn.close()
NINE = [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 10)]
rid = se.create_round(EV, 9, round_date="2099-10-27", label="s10.27", course_holes=NINE, db_path=DB)["round_id"]
gid = se.upsert_group(rid, 1, players=[
    {"customer_id": 401, "display_name": "Sam Keeper", "playing_handicap": 5},
    {"customer_id": 402, "display_name": "Mo Late", "playing_handicap": 8},
    {"customer_id": 403, "display_name": "Ned Noshow", "playing_handicap": 10},
    {"customer_id": 404, "display_name": "Al Unsure", "playing_handicap": 12}], db_path=DB)["group_id"]
gid2 = se.upsert_group(rid, 2, players=[
    {"customer_id": 411, "display_name": "Other Scorer", "playing_handicap": 3},
    {"customer_id": 412, "display_name": "Ollie Other", "playing_handicap": 4}], db_path=DB)["group_id"]
se.claim_group(gid, "dev1", 401, db_path=DB)
se.claim_group(gid2, "dev2", 411, db_path=DB)
_n = [0]


def ops(cid, holes, gross=5):
    out = []
    for h in holes:
        _n[0] += 1
        out.append({"op_id": f"ns{_n[0]}", "hole": h, "gross": gross, "customer_id": cid})
    return out


print("1. The scorer's button and questions")
r = se.mark_player_missing(gid, "dev2", 403, "absent", hole=1, db_path=DB)
check("another phone can't answer for this card", "error" in r, r)
r = se.mark_player_missing(gid2, "dev2", 403, "absent", hole=1, db_path=DB)
check("a scorer can't take a player off another card", "error" in r and "isn't on this card" in r["error"], r)
r = se.mark_player_missing(gid, "dev1", 403, "maybe", hole=1, db_path=DB)
check("only the three answers (and present)", "error" in r, r)
r = se.mark_player_missing(gid, "dev1", 403, "absent", hole=1, entered_by=401, db_path=DB)
check("No, take him off this card: absent", r.get("ok") and r["effective"] == "absent", r)
r = se.mark_player_missing(gid, "dev1", 402, "late", hole=1, db_path=DB)
check("Running late: stays on the card", r.get("ok") and r["effective"] == "late", r)
r = se.mark_player_missing(gid, "dev1", 404, "unknown", hole=1, db_path=DB)
check("Don't know yet: asked once", r.get("ok") and r["effective"] == "unknown", r)
se.mark_player_missing(gid, "dev1", 404, "unknown", hole=1, db_path=DB)
c = sqlite3.connect(DB)
asked = c.execute("SELECT holes_asked FROM se_no_shows WHERE customer_id = 404").fetchone()[0]
n_audit = c.execute("SELECT COUNT(*) FROM se_audit WHERE kind = 'no_show'").fetchone()[0]
c.close()
check("asking again on the same hole doesn't count twice", asked == 1, asked)
check("every answer is in se_audit", n_audit == 4, n_audit)
card = se.get_group_card(gid, "dev1", db_path=DB)
ns = {n["customer_id"]: n for n in card["no_shows"]}
check("the card carries the no-shows and N", set(ns) == {402, 403, 404} and card["no_show_after_holes"] == 3, card["no_shows"])
for h in (2,):
    se.mark_player_missing(gid, "dev1", 404, "unknown", hole=h, db_path=DB)
check("2 holes of don't know yet: still unknown",
      {n["customer_id"]: n for n in se.get_group_card(gid, "dev1", db_path=DB)["no_shows"]}[404]["effective"] == "unknown")
se.mark_player_missing(gid, "dev1", 404, "unknown", hole=3, db_path=DB)
check("after 3 holes he is off the card (Kerry 10/26)",
      {n["customer_id"]: n for n in se.get_group_card(gid, "dev1", db_path=DB)["no_shows"]}[404]["effective"] == "absent")
db.set_app_setting(se.NO_SHOW_HOLES_SETTING, "5", DB)
check("the dial sets N", se.no_show_after_holes(DB) == 5)
db.set_app_setting(se.NO_SHOW_HOLES_SETTING, "", DB)
check("blank dial: 3 (Kerry 10/26: \"Both should be at 3p\")", se.no_show_after_holes(DB) == 3)
r = se.mark_player_missing(gid, "dev1", 404, "present", hole=5, db_path=DB)
check("+ Player puts him back", r.get("ok") and r["effective"] == "present"
      and 404 not in {n["customer_id"] for n in se.get_group_card(gid, "dev1", db_path=DB)["no_shows"]}, r)
se.mark_player_missing(gid, "dev1", 404, "absent", hole=5, db_path=DB)

print("2. Absent players don't hold the night")
se.write_scores(gid, "dev1", 401, ops(401, range(1, 10)) + ops(402, range(1, 10), 6), db_path=DB)
card = se.get_group_card(gid, "dev1", db_path=DB)
check("blank holes of absent players don't hold the card's final time", card["final_at"] is not None, card.get("final_at"))
c = sqlite3.connect(DB)
filled = c.execute("SELECT COUNT(*) FROM se_hole_scores WHERE subject_key IN ('c:403','c:404')").fetchone()[0]
c.close()
check("never filled with par", filled == 0, filled)
rnd = se.get_entered_scores(EV, db_path=DB)["rounds"][0]
fed = {p["customer_id"] for p in rnd["players"]}
check("absent players leave the entered-scores feed (no individual, MVP, points, handicap)",
      403 not in fed and 404 not in fed and {401, 402} <= fed, fed)
check("the feed names them as absent", {a["customer_id"] for a in rnd["absent"]} == {403, 404}, rnd.get("absent"))
g1 = next(g for g in rnd["groups"] if g.get("group_id") == gid) if rnd.get("groups") and "group_id" in rnd["groups"][0] else None
if g1 is not None:
    check("the group goes final in the feed", g1.get("final_at") is not None, g1)

# A "don't know yet" with no scores turns absent once his group has scored N holes.
c = sqlite3.connect(DB)
for cid, fn in [(421, "Zed"), (422, "Quinn")]:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,'Three')", (cid, fn))
c.commit()
c.close()
gid3 = se.upsert_group(rid, 3, players=[
    {"customer_id": 421, "display_name": "Zed Three", "playing_handicap": 1},
    {"customer_id": 422, "display_name": "Quinn Three", "playing_handicap": 2}], db_path=DB)["group_id"]
se.claim_group(gid3, "dev3", 421, db_path=DB)
se.mark_player_missing(gid3, "dev3", 422, "unknown", hole=1, db_path=DB)
se.write_scores(gid3, "dev3", 421, ops(421, range(1, 3)), db_path=DB)
check("2 group holes, none of his: still unknown",
      se.get_group_card(gid3, "dev3", db_path=DB)["no_shows"][0]["effective"] == "unknown")
se.write_scores(gid3, "dev3", 421, ops(421, [3]), db_path=DB)
check("3 group holes, none of his: off the card even if no one answered again",
      se.get_group_card(gid3, "dev3", db_path=DB)["no_shows"][0]["effective"] == "absent")

print("3. The course notice")
pp.course_recipients_for_event = lambda ev, db_path=None: {"ok": True, "to": "pro@course.test",
                                                           "cc": ["shop@course.test"], "course_id": 1}
al._manager_cc = lambda chapter, db_path=None: "manager@thegolffellowship.com"
pa.manager_for = lambda chapter, db_path=None: {"name": "Kerry", "email": "manager@thegolffellowship.com"}
SENT = []


def fake(to, s, h, cc):
    SENT.append({"to": to, "subject": s, "html": h, "cc": cc})
    return True


b = nsn.build(EV, DB)
check("names every no-show whose group has played 3 holes, never the late player",
      b["names"] == ["Al Unsure", "Ned Noshow", "Quinn Three"], b["names"])
check("TGF branded: the house frame (dark masthead, chapter label, title)",
      "background:#1B1B1B" in b["html"] and "SAN ANTONIO" in b["html"] and ">Player count<" in b["html"]
      and "The Golf Fellowship" in b["html"], b["html"][:400])
check("original count vs updated count: 8 to 5 (Kerry CoS #2375)",
      b["counts"] == {"registered": 8, "no_shows": 3, "left": 0, "added": 0, "playing": 5}
      and "Original count</td>" in b["html"] and ">8</td>" in b["html"]
      and "<strong>Updated count</strong>" in b["html"] and "<strong>5</strong>" in b["html"]
      and "Thanks,<br>Kerry" in b["html"], (b["counts"], b["html"]))
check("what happened, one line a person, and who dropped with the payment-count request",
      "<li>Ned Noshow: no-show</li>" in b["html"] and "<li>Al Unsure: no-show</li>" in b["html"]
      and "Please remove Al Unsure, Ned Noshow and Quinn Three from our final payment count." in b["html"],
      b["html"])
check("the subject carries both counts", b["subject"] == "TGF player count at No Show Links: 8 to 5", b["subject"])
check("To the course contact; CC the course's other contacts, the manager AND the admin",
      b["to"] == "pro@course.test" and b["cc"] == ["shop@course.test", "manager@thegolffellowship.com",
                                                   "kerry@thegolffellowship.com"], (b["to"], b["cc"]))
db.set_app_setting(nsn.ADMIN_CC_SETTING, "boss@gmail.com", DB)
check("the admin CC is staff only: a non-staff address holds the notice",
      any("staff address" in h for h in nsn.build(EV, DB)["held"]), nsn.build(EV, DB)["held"])
db.set_app_setting(nsn.ADMIN_CC_SETTING, "", DB)
check("the admin CC defaults to kerry@thegolffellowship.com", nsn.admin_cc(DB) == ["kerry@thegolffellowship.com"])
check("not UPDATED the first time", not b["updated"] and not b["subject"].startswith("UPDATED"), b["subject"])
d = nsn.run_event(EV, confirm=False, db_path=DB, sender=fake)
check("dry run sends nothing", d["status"] == "would send" and not SENT, d)
r = nsn.check(now=datetime(2099, 10, 27, 16, 0), db_path=DB, sender=fake)
check("the job sends one email to the course", len(SENT) == 1 and SENT[0]["to"] == "pro@course.test", (r, SENT))
check("manager CC'd with the course's other contacts",
      SENT and "manager@thegolffellowship.com" in SENT[0]["cc"] and "shop@course.test" in SENT[0]["cc"], SENT)
nsn.check(now=datetime(2099, 10, 27, 16, 5), db_path=DB, sender=fake)
check("never twice for the same set", len(SENT) == 1, SENT)
# A reported no-show ARRIVES on hole 4 (Quinn, group 3): the set changed -> UPDATED.
r = se.mark_player_missing(gid3, "dev3", 422, "present", hole=4, entered_by=421, db_path=DB)
check("+ Player on hole 4 after the group started: he joined on hole 4, holes 1-3 not played",
      r.get("ok") and r.get("joined_hole") == 4 and r.get("not_played") == [1, 2, 3], r)
nsn.check(now=datetime(2099, 10, 27, 16, 10), db_path=DB, sender=fake)
check("a changed set sends ONE UPDATED notice", len(SENT) == 2 and SENT[1]["subject"].startswith("UPDATED: ")
      and "<strong>UPDATED</strong>" in SENT[1]["html"], [s["subject"] for s in SENT])
check("...the same layout: original 8 vs updated 6, Quinn arrived late, the request without him",
      "<li>Quinn Three: arrived late (from hole 4), playing</li>" in SENT[1]["html"]
      and "<strong>6</strong>" in SENT[1]["html"] and "Original count" in SENT[1]["html"]
      and "Please remove Al Unsure and Ned Noshow from our final payment count." in SENT[1]["html"]
      and SENT[1]["subject"] == "UPDATED: TGF player count at No Show Links: 8 to 6", SENT[-1])
nsn.check(now=datetime(2099, 10, 27, 16, 15), db_path=DB, sender=fake)
check("...and never twice for the same set", len(SENT) == 2, len(SENT))
check("CC on the UPDATED one too: manager and admin",
      "manager@thegolffellowship.com" in SENT[1]["cc"] and "kerry@thegolffellowship.com" in SENT[1]["cc"])
c = sqlite3.connect(DB)
n_log = c.execute("SELECT COUNT(*) FROM message_log WHERE sent_by = 'no-show-notice'").fetchone()[0]
n_act = c.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type = 'no_show_notice'").fetchone()[0]
c.close()
check("every send logged (message_log + agent_action_log)", n_log == 2 and n_act == 2, (n_log, n_act))
db.set_app_setting(nsn.DIAL, "off", DB)
check("dial off stops it", nsn.check(now=datetime(2099, 10, 27, 16, 10), db_path=DB, sender=fake)["status"] == "off")
db.set_app_setting(nsn.DIAL, "", DB)
check("dial on by default, notice after 3 holes (Kerry 10/26)", nsn.dial_on(DB) and nsn.notice_holes(DB) == 3)

print("5. Blinds for missing players, late arrival, WD, make-up holes (Kerry 10/26)")
import json as _json  # noqa: E402
from email_parser import live_scoring as ls  # noqa: E402
from email_parser.timezone_utils import today_central_str  # noqa: E402
TODAY = today_central_str()
EV2, NAME2 = 950, "s10.28 Blind Links"
c = sqlite3.connect(DB)
course_id = c.execute("INSERT INTO courses (name, status) VALUES ('Blind Links', 'active') "
                      "RETURNING course_id").fetchone()[0]
tee = c.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, slope, tgf_bands, "
                "source) VALUES (?, 'White', 'M', 9, 'front', 34.0, 113, '50-64', 'admin') RETURNING tee_id",
                (course_id,)).fetchone()[0]
for h in range(1, 10):
    c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, stroke_index) VALUES (?,?,4,?)",
              (tee, h, h))
c.execute("INSERT INTO events (id, item_name, event_date, chapter, course, course_id, status, format) "
          "VALUES (?, ?, ?, 'San Antonio', 'Blind Links', ?, 'active', '9 Holes')", (EV2, NAME2, TODAY, course_id))
FIRST = {501: "Abe", 502: "Ben", 503: "Cal", 504: "Dan", 505: "Eli", 506: "Fox", 507: "Gus", 508: "Hal",
         509: "Ike", 510: "Jay", 511: "Ken", 512: "Lou", 513: "Max", 514: "Ned", 515: "Oz"}
for cid, fn in FIRST.items():
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status, "
              "current_player_status) VALUES (?, ?, 'Blind', 'San Antonio', 'active', 'active_member')", (cid, fn))
    c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, event_id, "
              "transaction_status, holes, order_date, user_status) VALUES (?,?, 'The Golf Fellowship', ?,?,?,?, "
              "'active', '9', ?, 'MEMBER')", (9000 + cid, f"u{9000 + cid}", f"{fn} Blind", cid, NAME2, EV2, TODAY))
    c.execute("INSERT INTO handicap_player_links (player_name, customer_id, customer_name) VALUES (?,?,?)",
              (f"{fn} Blind", cid, f"{fn} Blind"))
    for i in range(4):          # four events on file: an established index (Rule 15 eligibility)
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, differential, adjusted_score, rating, "
                  "slope, customer_id) VALUES (?,?,?,?,?,?,?)",
                  (f"{fn} Blind", "2026-0%d-01" % (i + 5), 0.0, 36, 36.0, 113, cid))
c.commit()
c.close()
GROUPS = {1: [501, 502, 503, 504], 2: [505, 506, 507, 508], 3: [509, 510, 511, 512], 4: [514, 515]}
SHEET = {"9": [{"group_num": g, "slot_label": str(g), "players": [
    {"name": f"{FIRST[cid]} Blind", "customer_id": cid, "cart_pos": i + 1, "tee_choice": "50-64",
     "handicap_index": 0.0} for i, cid in enumerate(cids)]} for g, cids in GROUPS.items()]}
db.save_event_pairings(EV2, SHEET, db_path=DB)
db.set_app_setting("score_entry_live", "1", db_path=DB)
db.set_app_setting("score_entry_events", _json.dumps([EV2]), db_path=DB)
NINE4 = [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 10)]
rid2 = se.create_round(EV2, 9, round_date=TODAY, label="s10.28", course_holes=NINE4, course_id=course_id,
                       db_path=DB)["round_id"]
G = {}
for g, cids in GROUPS.items():
    G[g] = se.upsert_group(rid2, g, players=[{"customer_id": cid, "display_name": f"{FIRST[cid]} Blind",
                                              "tee": "50-64", "playing_handicap": 0, "seat": i + 1}
                                             for i, cid in enumerate(cids)], db_path=DB)["group_id"]
    se.claim_group(G[g], f"d{g}", cids[0], db_path=DB)


def blinds():
    out = {}
    for _h, gs in db.get_event_blinds(EV2, db_path=DB).items():
        for gnum, seats in gs.items():
            for b in seats:
                out[(gnum, b["cart_pos"])] = b
    return out


def write(g, cid, holes, gross):
    return se.write_scores(G[g], f"d{g}", GROUPS[g][0], ops(cid, holes, gross), db_path=DB)


# -- one blind per absent player, drawn by itself (Cart Net: 15 < 16 players) --
r = se.mark_player_missing(G[1], "d1", 504, "absent", hole=1, db_path=DB)
b = blinds()
check("No, take him off: a blind is drawn at once, no manager tap (Kerry: 'Blinds would happen automatically')",
      (1, 4) in b and b[(1, 4)]["reason"] == "missed_hole" and r.get("blinds", {}).get("drawn"), (r, b))
check("Cart Net: the blind is from the OTHER cart of the same foursome (rule 15h)",
      b.get((1, 4), {}).get("customer_id") in (501, 502), b.get((1, 4)))
check("an absent player's blind covers every hole (none of his holes count)",
      b.get((1, 4), {}).get("missed_holes") == list(range(1, 10)), b.get((1, 4)))
se.mark_player_missing(G[1], "d1", 503, "absent", hole=1, db_path=DB)
b = blinds()
check("two absents in a group: two blinds", (1, 3) in b and (1, 4) in b, sorted(b))
check("one blind per person per event: the second is the other cart-A player",
      {b[(1, 3)]["customer_id"], b[(1, 4)]["customer_id"]} == {501, 502}, (b[(1, 3)], b[(1, 4)]))
c = sqlite3.connect(DB)
n_ev = c.execute("SELECT COUNT(*) FROM event_pairings WHERE event_id = ? AND lower(player_name) LIKE '%blind]%'",
                 (EV2,)).fetchone()[0]
n_log = c.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type = 'no_show_blind'").fetchone()[0]
c.close()
check("a blind is never written into event_pairings", n_ev == 0, n_ev)
check("every draw is logged", n_log >= 2, n_log)
# Team Net (the field outside the group) by the same per-seat rule
_unit = db._event_blind_unit
db._event_blind_unit = lambda *a, **k: "group"
se.mark_player_missing(G[2], "d2", 508, "absent", hole=1, db_path=DB)
db._event_blind_unit = _unit
b = blinds()
check("Team Net: the blind is from the field OUTSIDE the group, never someone already a blind",
      (2, 4) in b and b[(2, 4)]["customer_id"] not in GROUPS[2] + [501, 502], b.get((2, 4)))
_bl_2_4 = b[(2, 4)]["customer_id"]
r = se.mark_player_missing(G[2], "d2", 508, "present", hole=1, db_path=DB)
check("back before his group started: no hole missed, the blind is undone",
      (2, 4) not in blinds() and r.get("blinds", {}).get("removed"), r.get("blinds"))

# -- late arrival on hole 4 (Lou, group 3) --
se.mark_player_missing(G[3], "d3", 512, "absent", hole=1, db_path=DB)
b = blinds()
check("Lou off the card: a blind for his seat (other cart: Ike or Jay)",
      b.get((3, 4), {}).get("customer_id") in (509, 510), b.get((3, 4)))
lou_blind = b[(3, 4)]["customer_id"]
for cid in (509, 510):
    write(3, cid, [1, 2, 3], 4)
write(3, 511, [1, 2, 3], 6)
r = se.mark_player_missing(G[3], "d3", 512, "present", hole=4, entered_by=509, db_path=DB)
check("Lou shows up on hole 4: + Player puts him back from hole 4, holes 1-3 NOT PLAYED",
      r.get("joined_hole") == 4 and r.get("not_played") == [1, 2, 3] and not r.get("ask_makeup"), r)
b = blinds()
check("...the SAME blind now covers only the holes he missed (1-3)",
      b.get((3, 4), {}).get("customer_id") == lou_blind and b[(3, 4)]["missed_holes"] == [1, 2, 3], b.get((3, 4)))
card = se.get_group_card(G[3], "d3", db_path=DB)
lp = next(x for x in card["partials"] if x["customer_id"] == 512)
check("the scorer's phone carries the state (joined on hole 4, the blind's holes)",
      lp["joined_hole"] == 4 and lp["not_played"] == [1, 2, 3]
      and card["blinds"].get("512", {}).get("holes") == [1, 2, 3], (lp, card["blinds"]))
for cid in (509, 510):
    write(3, cid, range(4, 10), 6)
write(3, 511, range(4, 10), 6)
write(3, 512, range(4, 10), 3)
c = sqlite3.connect(DB)
pars = c.execute("SELECT COUNT(*) FROM se_hole_scores WHERE subject_key = 'c:512' AND hole_number <= 3").fetchone()[0]
c.close()
check("holes 1-3 are never filled with par", pars == 0, pars)
card = se.get_group_card(G[3], "d3", db_path=DB)
lp = next(x for x in card["partials"] if x["customer_id"] == 512)
check("the make-up question appears only once the rest of the group finished the regular holes",
      lp["ask_makeup"] is True and card["final_at"] is None, (lp, card["final_at"]))
r = se.mark_player_missing(G[3], "d3", 512, "makeup_no", hole=9, db_path=DB)
card = se.get_group_card(G[3], "d3", db_path=DB)
check("No: holes 1-3 are final as not played and the card can go final",
      card["final_at"] is not None, card.get("final_at"))
rnd = next(x for x in se.get_entered_scores(EV2, db_path=DB)["rounds"])
lou = next(p for p in rnd["players"] if p["customer_id"] == 512)
check("the feed: Lou in, an incomplete round, holes 1-3 not played",
      lou["incomplete_round"] and lou["not_played"] == [1, 2, 3] and sorted(lou["scores"]) == [str(h) for h in range(4, 10)],
      lou)

# -- make-up YES (Fox, group 2): the holes open, entered, the round complete, the blind undone --
for cid in (505, 507):
    write(2, cid, [1, 2, 3], 5)
se.mark_player_missing(G[2], "d2", 506, "late", hole=1, db_path=DB)
r = se.mark_player_missing(G[2], "d2", 506, "present", hole=4, db_path=DB)
check("Running late, then Here now on hole 4: joined on hole 4, a blind for 1-3",
      r.get("joined_hole") == 4 and blinds().get((2, 2), {}).get("missed_holes") == [1, 2, 3], (r, blinds().get((2, 2))))
for cid in (505, 507, 508):
    write(2, cid, range(4 if cid != 508 else 1, 10), 5)
write(2, 506, range(4, 10), 5)
r = se.mark_player_missing(G[2], "d2", 506, "makeup_yes", hole=9, db_path=DB)
card = se.get_group_card(G[2], "d2", db_path=DB)
check("Yes: holes 1-3 stay open and the card is not final until they're in",
      r.get("makeup_open") == [1, 2, 3] and card["final_at"] is None, (r, card.get("final_at")))
write(2, 506, [1, 2, 3], 5)
card = se.get_group_card(G[2], "d2", db_path=DB)
fox = next(p for p in next(x for x in se.get_entered_scores(EV2, db_path=DB)["rounds"])["players"] if p["customer_id"] == 506)
check("made up: his round is complete and counts for everything; the blind is undone",
      card["final_at"] is not None and not fox.get("incomplete_round") and (2, 2) not in blinds(),
      (card.get("final_at"), fox, blinds().get((2, 2))))

# -- WD (Eli, group 2 played; use group 1's Abe? he is a blind) -> Ken in group 3 is done; use group 4 --
write(4, 514, range(1, 6), 5)
write(4, 515, range(1, 6), 5)
r = se.mark_player_missing(G[4], "d4", 515, "wd", hole=6, db_path=DB)
check("Left the course (WD) on hole 6: holes 6-9 NOT PLAYED, his holes 1-5 stand",
      r.get("effective") == "wd" and r.get("not_played") == [6, 7, 8, 9], r)
check("...a blind covers his remaining holes, drawn by itself",
      blinds().get((4, 2), {}).get("missed_holes") == [6, 7, 8, 9], blinds().get((4, 2)))
write(4, 514, range(6, 10), 5)
card = se.get_group_card(G[4], "d4", db_path=DB)
check("...his remaining holes never hold the card, and no make-up question for a WD",
      card["final_at"] is not None and not any(x.get("ask_makeup") for x in card["partials"]), card.get("final_at"))
ns = se.event_no_shows(EV2, db_path=DB)
check("the course notice counts him as having left", [x["customer_id"] for x in ns["left"]] == [515], ns["left"])
_b2 = nsn.build(EV2, DB)
check("...and says what happened: left after hole 5, the late arrival playing, and asks to remove the WD",
      "<li>Oz Blind: left after hole 5</li>" in _b2["html"]
      and "<li>Lou Blind: arrived late (from hole 4), playing</li>" in _b2["html"]
      and "Please remove Oz Blind from our final payment count." in _b2["html"], _b2["html"])

# -- the games for an incomplete round (Kerry 10/26) --
db.get_event_leaderboard  # noqa: B018 (the real board, entry mode)


def est():
    """The engine state with everyone a buyer (no orders for games in this fixture)."""
    s_ = db.event_engine_state(NAME2, db_path=DB, live=True)
    for p_ in s_.get("players") or []:
        p_["buys_net"] = p_["buys_gross"] = True
    return s_


st = est()
check("the engine state carries the per-game settings and flags the short rounds",
      st.get("incomplete_round_games") == se.INCOMPLETE_ROUND_GAMES
      and {p["customer_id"] for p in st["players"] if p.get("incomplete_round")} == {512, 515},
      [(p["customer_id"], p.get("incomplete_round")) for p in st["players"]])
F_ = db.get_scoring_formulas(DB)
lb = ls.compute_leaderboard(st, F_)


def in_game(game, cid):
    g = lb["games"][game]
    if game in ("individual_net", "individual_gross"):
        return any(r_["customer_id"] == cid for f in g.get("flights") or [] for r_ in f["rows"])
    if game == "mvp":
        return any(r_["customer_id"] == cid for r_ in g.get("field") or [])
    return False


cards = {c_["customer_id"]: c_ for c_ in lb["cards"]}
check("Individual Net: OUT (ruled)", not in_game("individual_net", 512) and not in_game("individual_net", 515))
check("Individual Gross: OUT (ruled)", not in_game("individual_gross", 512))
_lh = {h_["hole"]: h_ for h_ in cards[512]["holes"]}
check("MVP: IN, net Stableford summed over the holes he played (1-3 score nothing), card complete",
      in_game("mvp", 512) and all(_lh[h]["strokes"] is None for h in (1, 2, 3))
      and cards[512]["stableford_net"] == sum((_lh[h]["stableford_net"] or 0) for h in range(4, 10)) > 0
      and cards[512]["complete"], (cards[512]["stableford_net"], lb["games"]["mvp"].get("status")))
sk_field = ls._eligible(lb["cards"], ls.SEED_LIVE_SCORING_CONFIG["games"]["skins"]["eligibility"])
check("Skins: IN on the holes he played, and his NOT PLAYED holes don't hold a skin open",
      any(c_["customer_id"] == 512 for c_ in [x for x in lb["cards"]]) and
      not any(not sk["settled"] for f in lb["games"]["skins"].get("flights") or [] for sk in f["skins"]
              if sk["hole"] <= 3), lb["games"]["skins"].get("flights"))
_save = dict(se.INCOMPLETE_ROUND_GAMES)
se.INCOMPLETE_ROUND_GAMES["individual_net"] = True
lb2 = ls.compute_leaderboard(est(), F_)
check("the per-game setting works: individual_net on puts him in",
      any(r_["customer_id"] == 512 for f in lb2["games"]["individual_net"]["flights"] for r_ in f["rows"]))
se.INCOMPLETE_ROUND_GAMES["mvp"] = False
lb3 = ls.compute_leaderboard(est(), F_)
check("...and mvp off takes him out", not any(r_["customer_id"] == 512 for r_ in lb3["games"]["mvp"].get("field") or []))
se.INCOMPLETE_ROUND_GAMES.clear()
se.INCOMPLETE_ROUND_GAMES.update(_save)
# ONLY WHAT HE PAID INTO (Kerry 10/26, CoS #2375: "Late arrivals of course is only eligible for what he's
# paid into or what's already included with his entry, in addition to the restrictions for not being
# eligible in the invidual net or gross due to incomplete scorecard"). The buyer lists decide, as for anyone.
_real = db.event_engine_state(NAME2, db_path=DB, live=True)       # nobody bought a game in this fixture
lb4 = ls.compute_leaderboard(_real, F_)
_sk = {c_["customer_id"] for c_ in ls._eligible(lb4["cards"], "gross_buyers")}
check("a short round who bought nothing: not in Skins, not in MVP (buyer lists decide)",
      512 not in _sk and not any(r_["customer_id"] == 512 for r_ in lb4["games"]["mvp"].get("field") or []), _sk)
check("...but in Team Net (comes with his entry)",
      any("Lou" in " ".join(t["members"]) for t in lb4["games"]["team_net"]["teams"]))
for p_ in _real["players"]:
    if p_["customer_id"] == 512:
        p_["buys_gross"], p_["buys_net"] = True, False
lb5 = ls.compute_leaderboard(_real, F_)
check("bought the gross bundle only: in Skins, still not in MVP (a net game) nor Individual Gross (short round)",
      512 in {c_["customer_id"] for c_ in ls._eligible(lb5["cards"], "gross_buyers")}
      and not any(r_["customer_id"] == 512 for r_ in lb5["games"]["mvp"].get("field") or [])
      and not any(r_["customer_id"] == 512 for f in lb5["games"]["individual_gross"].get("flights") or []
                  for r_ in f["rows"]))
check("points races: IN (ruled 'A short round should still count toward points races')",
      se.incomplete_round_plays("points"))
check("handicap round: OUT (ruled 'but not towards a handicap'): an incomplete round is never published",
      not se.incomplete_round_plays("handicap_round") and not se._publish_incomplete())
from email_parser import entry_publish as ep  # noqa: E402
pub = ep.publish_event(EV2, apply=False, db_path=DB, provisional=True)
inc = [x["customer_id"] for r_ in pub["rounds"] for x in r_.get("incomplete_round") or []]
held = [x["customer_id"] for r_ in pub["rounds"] for x in r_.get("held") or []]
check("the publisher: short rounds go to `incomplete_round`, never `held` (they don't stop the money)",
      sorted(inc) == [512, 515] and 512 not in held and 515 not in held, (inc, held))

# -- Team Net on the board: the blind on 1-3, his own ball 4-9 --
with db._connect(DB) as _cx:
    db._ensure_scoring_tables(_cx)
    db._ensure_gg_game_flights_tables(_cx)
    db._ensure_gg_game_results_tables(_cx)
lbd = db.get_event_leaderboard(NAME2, db_path=DB) or {}
team = next((t for t in lbd.get("teams") or []
             if any(m.get("customer_id") == 512 for m in t.get("players") or [])), None)
check("the board finds Lou's team with his blind on it",
      team is not None and any(m.get("blind") and m.get("blind_holes") == [1, 2, 3] for m in team["players"]),
      team and [(m.get("player_name"), m.get("blind_holes")) for m in team["players"]])
if team:
    balls = max((v.get("balls") or 1) for v in team["team_holes"].values()) if team["team_holes"] else 1
    # Ken 6 every hole; the blind 4 on 1-3; Lou 3 on 4-9 (par 4, no pops)
    exp = 0
    for h in range(1, 10):
        bl = sorted([6] + ([4] if h <= 3 else [3]))[:balls]
        exp += sum(bl)
    check(f"TEAM TOTAL: blind's 4 on holes 1-3, Lou's 3 on 4-9 ({balls}-ball) = {exp}, complete",
          team["total_net"] == exp and team["complete"] and team["thru"] == 9, (team["total_net"], exp, team["thru"]))
    check("Lou's NOT PLAYED holes never hold his team", all(str(h) in team["team_holes"] for h in (1, 2, 3)))
    # The other Team Net option, kept as one named setting: the blind plays his whole seat.
    se.TEAM_NET_INCOMPLETE_ROUND = "blind_whole_round"
    db.sync_no_show_blinds(EV2, db_path=DB)
    b_all = blinds().get((3, 4), {}).get("missed_holes")
    t2 = next(t for t in (db.get_event_leaderboard(NAME2, db_path=DB) or {}).get("teams") or []
              if any(m.get("customer_id") == 512 for m in t.get("players") or []))
    exp2 = sum(sum(sorted([6, 4 if h <= 3 else 6])[:balls]) for h in range(1, 10))
    check(f"TEAM_NET_INCOMPLETE_ROUND='blind_whole_round': the blind plays all 9, Lou's ball never counts = {exp2}",
          b_all == list(range(1, 10)) and t2["total_net"] == exp2, (b_all, t2["total_net"], exp2))
    se.TEAM_NET_INCOMPLETE_ROUND = "own_ball_and_blind"
    db.sync_no_show_blinds(EV2, db_path=DB)
    check("...and back to the ruled default: the same blind, holes 1-3 again",
          blinds().get((3, 4), {}).get("missed_holes") == [1, 2, 3]
          and blinds()[(3, 4)]["customer_id"] == lou_blind, blinds().get((3, 4)))
mv = {e_["customer_id"]: e_ for e_ in db._partial_round_mvp_entrants(NAME2, db_path=DB)}
check("the recorded City MVP sees a short round: engine points on the holes played, holes_played full (never waits)",
      512 in mv and mv[512]["holes_played"] == 9 and mv[512]["holes_actually_played"] == 6
      and mv[512]["points"] == cards[512]["stableford_net"], mv.get(512))
# a no-show (no card) and his blind share the slot: the blind takes it whole, in every mode
_w = db.team_slot_weights([{"player_name": "Dan Blind", "customer_id": None, "seat_customer_id": 504},
                           {"player_name": "Bl[Ben Blind]", "customer_id": 502, "blind": True}],
                          {504: {"customer_id": 502, "holes": list(range(1, 10)), "reason": "missed_hole"}}, 9)
check("a no-show's slot goes to his blind whole (he played nothing)",
      _w and _w[0]["weight"] == 0 and _w[1]["weight"] == 1 and _w[0]["slot"] == _w[1]["slot"], _w)
check("split_weighted_cents adds up to the cent", db.split_weighted_cents(2300, [6, 3]) == [1533, 767]
      and sum(db.split_weighted_cents(1001, [1, 1, 1])) == 1001)

# -- "+ Player": a last-second add and a switch --
c = sqlite3.connect(DB)
c.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
          "VALUES (516, 'Pat', 'Late', 'active_member')")
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, event_id, "
          "transaction_status, holes, order_date, user_status) VALUES (9516, 'u9516', 'The Golf Fellowship', "
          "'Pat Late', 516, ?, ?, 'active', '9', ?, 'MEMBER')", (NAME2, EV2, TODAY))
c.commit()
c.close()
ch = se.add_choices(G[4], db_path=DB)
check("+ Player offers a roster player on no card and players on other cards of the round",
      516 in [a["customer_id"] for a in ch["adds"]] and 502 in [s_["customer_id"] for s_ in ch["switches"]]
      and ch["open"], ch)
r = se.add_player_to_card(G[4], "someone-else", 516, hole=7, db_path=DB)
check("only the phone keeping score can add", "error" in r, r)
r = se.add_player_to_card(G[4], "d4", 516, hole=7, entered_by=514, db_path=DB)
c = sqlite3.connect(DB)
seat516 = c.execute("SELECT group_num, cart_pos FROM event_pairings WHERE event_id = ? AND customer_id = 516",
                    (EV2,)).fetchone()
c.close()
check("a last-second add: on the card, seated on the PAIRINGS (targeted write), plays from hole 7",
      r.get("ok") and r["mode"] == "add" and seat516 == (4, 3) and r.get("joined_hole") == 7, (r, seat516))
check("...his group already finished the regular holes, so the make-up question is up at once",
      r.get("ask_makeup") is True, r)
check("...and a blind covers the holes before he joined, drawn by itself",
      blinds().get((4, 3), {}).get("missed_holes") == [1, 2, 3, 4, 5, 6], blinds().get((4, 3)))
db.set_app_setting(se.CARD_LOCK_SETTING, "0", DB)
r = se.add_player_to_card(G[4], "d4", 511, hole=7, db_path=DB)
db.set_app_setting(se.CARD_LOCK_SETTING, "", DB)
check("a switch from a FINAL card is refused (the manager unlocks it first)", "final" in (r.get("error") or ""), r)
r = se.add_player_to_card(G[4], "d4", 502, hole=7, entered_by=514, db_path=DB)
c = sqlite3.connect(DB)
seat502 = c.execute("SELECT group_num FROM event_pairings WHERE event_id = ? AND customer_id = 502",
                    (EV2,)).fetchone()
c.close()
check("a switch: he moves, his old card loses him, his pairing seat follows",
      r.get("ok") and r["mode"] == "switch" and seat502 == (4,)
      and not any(p["customer_id"] == 502 for p in se.get_group_card(G[1], "d1", db_path=DB)["players"]), (r, seat502))
check("...the seat he left is an open seat and gets its Rule 15 blind at once",
      (r.get("pairing") or {}).get("vacated_blind", {}).get("seat") == "9:1:2"
      or blinds().get((1, 2), {}).get("reason") == "open_seat", (r.get("pairing"), blinds().get((1, 2))))

print("6. Paying a winning team's shared slot (Kerry 10/26: 'Split by holes is good')")
# The winning team: Ken, Ike, Jay, Lou (joined on hole 4) and Bl[Gus] who played Lou's holes 1-3.
ROW = {"teamTotal": 92, "team1st": 92, "team2nd": "NO_EVENT", "teamType": "Team Net",
       "ctp1": "NO_EVENT", "individualNet": "NO_EVENT", "skinsTotal": "NO_EVENT", "individualGross": "NO_EVENT"}
_saved_fns = {k: getattr(db, k) for k in ("_load_games_matrix", "_event_player_counts", "_event_looks_rained_out",
                                          "determine_tgf_mvp", "get_gg_game_results", "get_event_leaderboard",
                                          "engine_game_payouts", "no_show_blinds_by_player")}
db._load_games_matrix = lambda db_path=None: ({"16": ROW}, {})
db._event_player_counts = lambda conn, name: {"players": 16, "net": 0, "gross": 0}
db._event_looks_rained_out = lambda conn, name: None
db.determine_tgf_mvp = lambda name, db_path=None: {"error": "stub"}
db.get_gg_game_results = lambda name, db_path=None: {"results": []}
db.engine_game_payouts = lambda name, db_path=None: {"error": "stub"}
LBP = {"field_complete": True, "teams": [
    {"team_num": 3, "total_net": -12, "position": "1", "holes_total": 9, "players": [
        {"player_name": "Ken Blind", "customer_id": 511}, {"player_name": "Ike Blind", "customer_id": 509},
        {"player_name": "Jay Blind", "customer_id": 510}, {"player_name": "Lou Blind", "customer_id": 512},
        {"player_name": "Bl[Gus Blind]", "customer_id": 507, "blind": True, "blind_holes": [1, 2, 3]}]}]}
db.get_event_leaderboard = lambda name, db_path=None: LBP
db.no_show_blinds_by_player = lambda event_id, db_path=None: {
    512: {"name": "Gus Blind", "customer_id": 507, "holes": [1, 2, 3], "reason": "missed_hole"}}
_mode = se.TEAM_SLOT_PAYOUT
results = {}
for mode in ("pro_rata", "player", "blind"):
    se.TEAM_SLOT_PAYOUT = mode
    a = db.assemble_event_game_payouts(NAME2, db_path=DB)
    results[mode] = {r_["golferName"]: round(r_["amount"] * 100) for r_ in a["rows"] if r_["category"] == "team_net"}
se.TEAM_SLOT_PAYOUT = _mode
for k, v in _saved_fns.items():
    setattr(db, k, v)
pr = results["pro_rata"]
check("PRO RATA (ruled): 4 slots of $23.00; Lou 6/9 = $15.33, the blind 3/9 = $7.67",
      pr == {"Ken Blind": 2300, "Ike Blind": 2300, "Jay Blind": 2300, "Lou Blind": 1533, "Gus Blind": 767}, pr)
check("...to the cent: the shared slot adds up exactly to its share, the team to the purse",
      pr.get("Lou Blind", 0) + pr.get("Gus Blind", 0) == 2300 and sum(pr.values()) == 9200, pr)
check("PLAYER: the late player takes the whole slot, the blind nothing",
      results["player"].get("Lou Blind") == 2300 and "Gus Blind" not in results["player"]
      and sum(results["player"].values()) == 9200, results["player"])
check("BLIND: the blind takes the whole slot, the late player nothing",
      results["blind"].get("Gus Blind") == 2300 and "Lou Blind" not in results["blind"]
      and sum(results["blind"].values()) == 9200, results["blind"])
check("never one slot paid twice (4 slots, never 5 shares)",
      all(sum(r_.values()) == 9200 for r_ in results.values()), results)
print("    example (pro rata): " + ", ".join(f"{k} ${v / 100:.2f}" for k, v in pr.items()))


print("4. Wiring")
here = os.path.dirname(os.path.abspath(__file__))
_a = open(os.path.join(here, "app.py"), encoding="utf-8").read()
check("route /api/score-entry/missing", '"/api/score-entry/missing"' in _a and "mark_player_missing(" in _a)
check("the notice job is registered", 'id="no_show_notice"' in _a)
check("the read-only bridge", 'cmd == "scoring-no-show-notice"' in open(os.path.join(here, "mcp_server.py"), encoding="utf-8").read())
_t = open(os.path.join(here, "templates", "score_entry.html"), encoding="utf-8").read()
check("the red Player missing button sits in the hole screen's bottom bar",
      'data-act="missing">Player missing</button>' in _t and "se-missrow" in _t and "#B91C1C" in _t)
check("the three answers, word for word",
      "Running late, keep him on the card" in _t and "No, take him off this card" in _t and "Don't know yet" in _t)
check("Who's missing? and Is <Name> coming?", "Who's missing?" in _t and "Is ${esc(first(nm) || nm)} coming?" in _t)
check("+ Player on the absent chip", 'data-act="unmiss"' in _t and "+ Player" in _t)
check("Save leaves a late / not-here-yet player's hole blank, and a NOT PLAYED hole too",
      "&& !(s.cid != null && nsWaiting(s.cid))" in _t
      and "&& !(s.cid != null && (notPlayed(s.cid, hole) || (makeupOpen(s.cid, hole) && !regularDone()))))" in _t)
check("the phone shows the state: joined on hole N, left on hole N, the blind, Not played",
      '"Joined on hole "' in _t and '"Left on hole "' in _t and "Blind for Team Net" in _t
      and '"Not played"' in _t and 'data-act="unmiss" data-cid="${s.cid}">Here now' in _t)
check("the fourth answer: Left the course (WD)", 'data-a="wd">Left the course (WD)' in _t)
check("the make-up question and couldn't finish", "makeupScreen(" in _t and 'data-a="makeup_yes"' in _t
      and 'data-a="makeup_no"' in _t and "makeup_unfinished" in _t)
check("+ Player for someone else (add or switch)", 'data-act="addp"' in _t and "/api/score-entry/add-player" in _t
      and '"/api/score-entry/add-player"' in _a and '"/api/score-entry/add-choices"' in _a)
mig2 = open(os.path.join(here, "migrations", "0041_se_partial_rounds.sql"), encoding="utf-8").read()
check("migration 0041 (rule 3b): partial rounds keyed by customer_id, enums by CHECK, portable",
      re.search(r"customer_id\s+INTEGER NOT NULL REFERENCES customers\(customer_id\)", mig2)
      and "CHECK (kind IN ('joined', 'added', 'left'))" in mig2
      and "INSERT OR REPLACE" not in mig2 and "COLLATE NOCASE" not in mig2)
check("absent players leave the hole rows", "if (isAbsent(p.customer_id)) continue;" in _t)
mig = open(os.path.join(here, "migrations", "0040_se_no_shows.sql"), encoding="utf-8").read()
check("migration 0040: keyed by customer_id, portable", re.search(r"customer_id\s+INTEGER NOT NULL REFERENCES customers\(customer_id\)", mig)
      and "INSERT OR REPLACE" not in mig and "COLLATE NOCASE" not in mig)
check("the notice never queries se_* itself",
      "se_no_shows" not in open(os.path.join(here, "email_parser", "no_show_notice.py"), encoding="utf-8").read())

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
