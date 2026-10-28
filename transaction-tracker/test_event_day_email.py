"""The EVENT-DAY EMAIL (CA #829): one pairing email per roster player,
built from the saved sheet, HELD at the boundary on any blank, staff-only
preview, member send locked behind Kerry's approval stamp + confirm,
never twice per event + customer. Graph is mocked — nothing leaves.

Run: python3 test_event_day_email.py
"""
import re, os, sys, io, contextlib, logging, tempfile
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

print("1. The dry build (design A2, Kerry 10/12)")
tpl = ede.load_template(DB)
check("the template is seeded as DATA with the A2 cards",
      bool(tpl) and all(t in tpl["html_body"] for t in ("{spot_card}", "{games_card}", "{scoring_button}")), tpl)
check("the A2 wording replaced the approved v1 hash", tpl["hash"] != "f76bf53aa8d5ee65", tpl["hash"])
b = ede.build_event_day_emails(EV, db_path=DB)
by = {m["customer_id"]: m for m in b.get("messages", [])}
held = {h["customer_id"]: h["reason"] for h in b.get("held", [])}
ann = by.get(880001, {})
at = ann.get("text", "")
check("Ann's message is ready, to her canonical email", ann.get("email") == "ann@example.test", b)
check("subject: day + course, start, shotgun; no internal code",
      ann.get("subject") == "Tuesday at TEST LINKS: Hole 1A, 8:00 AM shotgun", ann.get("subject"))
check("…the START card states the start as the Starter Sheet does",
      "YOUR START" in at and "Hole 1A \u00b7 8:00 AM" in at
      and "Shotgun \u00b7 Tuesday, October 13 \u00b7 Test Links GC" in at, at)
check("…the group lists all four with initials, herself marked",
      all(n in at for n in ("Ann Able", "you \u00b7 Cart A", "Bob Baker", "your cart \u00b7 Cart A",
                            "Cal Cole", "Dee Dunn", "Cart B"))
      and ">AA<" in ann.get("html", ""), at)
check("…format from the event and the games tab", "9 holes \u00b7 Team Net" in at, at)
check("…the chapter manager", "Text Kerry at" in at and "Kerry\nThe Golf Fellowship" in at, at)
check("the frame wraps it: masthead with chapter and title",
      "THE GOLF FELLOWSHIP \u00b7 SAN ANTONIO" in ann.get("html", "")
      and "Tuesday at TEST LINKS" in ann.get("html", ""))
print("1b. The Games card")
check("total in play and counts", "$367 in play" in at and "TUESDAY'S GAMES" in at, at)
check("one block per section with its pot", all(x in at for x in (
      "INCLUDED everyone \u00b7 $100", "NET GAMES 3 players \u00b7 $163", "GROSS GAMES 2 players \u00b7 $104")), at)
check("game names made plain, flight + skin notes, linked MVP", all(x in at for x in (
      "Closest to the Pin #1 $20", "2 flights, $58.50 to each flight winner",
      "one skin pays $52, two pay $26 each", "TGF MVP with Austin at Forest Creek $46")), at)
check("sub rows and a 'No Game' row never print",
      "Low Flight" not in at and "Ind" not in at.replace("Individual Net", "") and "Test Links GC $26" not in at, at)
check("Ann: INCLUDED + NET in, GROSS not bought",
      at.count("YOU'RE IN") == 2 and at.count("NOT BOUGHT") == 1, at)
check("Bob (BOTH) is in all three", by.get(880002, {}).get("text", "").count("YOU'RE IN") == 3)
check("Cal (none): included only", by.get(880003, {}).get("text", "").count("NOT BOUGHT") == 2)
check("a split bar sized by pot (cells add to 100%)",
      ann.get("html", "").count('height="12"') == 3, ann.get("html", "")[:200])
check("email-safe: no <style>, <img>, <svg>, flex or grid in the body",
      not any(x in ann.get("html", "").lower() for x in ("<style", "<img", "<svg", "display:flex", "display:grid")))
check("house paragraph spacing applied (normalize_email_html)", 'style="margin:0 0 1em;"' in ann.get("html", ""))
check("no brace survives in any ready message",
      not any("{" in m["html"] or "{" in m["subject"] for m in b["messages"]))
check("seated player with no email is HELD", "no email" in held.get(880005, ""), held)
check("roster player not on the sheet is HELD", "not in a group" in held.get(880006, ""), held)
check("Gus (group 2, two players) is ready with Eli on his card", "Eli Eno" in by.get(880007, {}).get("text", ""))
check("counts add up", b["counts"] == {"roster": 7, "ready": 5, "held": 2}, b["counts"])
check("no games note when the tab reads", b["games_note"] is None, b["games_note"])
check("unapproved by default", b["approved"] is False)
bad = ede.build_event_day_emails(EV, db_path=DB, games_tab={"error": "no Chromium on this deploy"})
check("an unreadable games tab drops the card, never the start",
      bad["counts"]["ready"] == 5 and "games card omitted" in (bad["games_note"] or "")
      and all("in play" not in m["text"] and "YOUR START" in m["text"] for m in bad["messages"]), bad["games_note"])
b2 = ede.build_event_day_emails(EV2, db_path=DB)
check("an unsaved sheet holds everybody", b2["counts"]["ready"] == 0
      and all("pairings not saved" in h["reason"] for h in b2["held"] if h.get("email")), b2["counts"])

print("1d. Kerry 10/13: HIO total, live scoring, tee sheet, pops")
check("the HIO line shows the RUNNING pot and what tonight adds",
      "Hole-in-One Pot: $" in at and "Tuesday's field adds $33" in at, at)
check("Live Scoring off: no Keep score button, and the build says so",
      "Keep score on your phone" not in at and "Live Scoring is not on" in (b.get("scoring_note") or ""),
      b.get("scoring_note"))
check("a tee sheet button that lands on the player's group",
      "See the full tee sheet" in at and "/member/teesheet/9101#g1" in ann.get("html", ""), ann.get("html", "")[-900:])
strip = ede.card_strip(
    {"ph": "6", "net": "5", "ph_dots": {11: 1, 13: 1, 18: 2}, "net_dots": {11: 1, 18: 1},
     "si_by_hole": {h: h - 9 for h in range(10, 19)}},
    {"holes": list(range(10, 19)), "par": {h: 4 for h in range(10, 19)}},
    {"name": "Team Net", "pct": 85, "unit": "group", "off_low": False, "par3_suppressed": True},
    {"index": 12.4}, "Gold Tees")
st = ede.html_to_text(strip)
check("YOUR CARD strip: holes, par, NET and TEAM pop rows",
      all(x in st for x in ("YOUR CARD", "HOLE 10 11 12", "PAR 4 4", "NET", "TEAM"))
      and strip.count("&#9679;") == 7, st)   # 6 pops + the legend dot
check("…and the handicap chain in words",
      "Index 12.4 on the Gold Tees gives you a Playing Handicap of 6 for Individual Net." in st
      and "Team Net uses 85% of your handicap: 5." in st and "No team pops on par 3s." in st, st)
check("no strip without stroke indexes (never guessed)",
      ede.card_strip({"ph": "6", "si_by_hole": {}}, {"holes": [10]}, {}, None, None) == "")
from email_parser import member_teesheet as mts
from email_parser import after_lock as _al
_pre_ei = mts.render_teesheet(mts.build_teesheet(EV, db_path=DB))
check("before the Event Info, a shotgun's member tee sheet hides the holes (Kerry 10/28)",
      "Group 1" in _pre_ei and "Hole 1A" not in _pre_ei and not re.search(r">\s*\d{1,2}[AB]\b", _pre_ei)
      and "Shotgun 8:00 AM" in _pre_ei, _pre_ei[:600])
_al._set(_al.STATE_KEY.format(int(EV)), {"seeded": True}, DB)
td = mts.build_teesheet(EV, db_path=DB)
page = mts.render_teesheet(td)
check("the member tee sheet lists every group with its anchor and players",
      'id="g1"' in page and 'id="g2"' in page and "Ann Able" in page and "Gus Gray" in page
      and "Hole 1A \u00b7 8:00 AM" in page, page[:300])
with db._connect(DB) as conn:  # back to "Event Info not sent" for the sections below
    conn.execute("DELETE FROM app_settings WHERE key = ?", (_al.STATE_KEY.format(int(EV)),))
    conn.commit()
check("each seated player shows his TGF index or No handicap (Kerry 10/20)",
      all(("HCP " in r or "No handicap" in r) for r in page.split('<div class="p"')[1:]), page[:600])
with db._connect(DB) as conn:
    db._ensure_pairing_tables(conn)
    _g1 = td["groups"][0]
    conn.execute("INSERT INTO blind_draws (event_id, holes, group_num, cart_pos, player_name, slot_key, reason) "
                 "VALUES (?, ?, ?, 4, 'Bob Blind', 'k', 'open_seat')",
                 (EV, str(next(g for g in db.get_event_print_pack(EV, db_path=DB)["groups"]
                               if g["group_num"] == _g1["group_num"])["holes"]), _g1["group_num"]))
    conn.commit()
_pb = mts.render_teesheet(mts.build_teesheet(EV, db_path=DB))
check("a drawn blind shows with the reason", "BLIND</span> Bob Blind" in _pb and "Blind for the open seat" in _pb,
      _pb[_pb.find('id="g1"'):][:900])
check("…and carries no email, phone or money",
      "@" not in page.replace("@media", "") and "$" not in page, page)
_pre = mts.render_teesheet(mts.build_teesheet(EV2, db_path=DB))
check("an event with no saved sheet says so", "not posted yet" in _pre)
check("...and still shows who is registered (Kerry 10/16), names only",
      "Registered so far" in _pre and "Ann Able" in _pre and "Gus Gray" in _pre and "7 registered" in _pre
      and "@" not in _pre.replace("@media", "") and "$" not in _pre, _pre[-1500:])
check("...a MEMBER's name links to their Spotlight", '/member/spotlight?player=880001' in _pre)
with db._connect(DB) as conn:
    conn.execute("UPDATE customers SET current_player_status = 'first_timer' WHERE customer_id = 880002")
    conn.commit()
_pre2 = mts.render_teesheet(mts.build_teesheet(EV2, db_path=DB))
check("...a non-member's name is plain text (the Spotlight is a member perk, Kerry 10/16)",
      '/member/spotlight?player=880002' not in _pre2 and "Bob Baker" in _pre2
      and "Members get their own" in _pre2)
with db._connect(DB) as conn:
    conn.execute("UPDATE customers SET current_player_status = 'active_member' WHERE customer_id = 880002")
    conn.commit()
db.set_starting_handicap(880003, 12.5, set_by="test", db_path=DB)
_pre3 = mts.render_teesheet(mts.build_teesheet(EV2, db_path=DB))
check("the registered list shows the 18-HOLE index (Kerry 10/16), as typed: 12.5 not 6.2",
      "HCP 12.5" in _pre3 and "HCP 6.2" not in _pre3 and "HCP 6.3" not in _pre3, _pre3[-1200:])
db.set_starting_handicap(880003, None, db_path=DB)
check("index shown with a plus for a plus handicap", mts._fmt_index(-1.46) == "+1.5"
      and mts._fmt_index(14.24) == "14.2" and mts._fmt_index(None) == "")

print("1c. A template still written the v1 way keeps working (Kerry may edit in the UI)")
V1 = ("<p>Hi {first_name},</p><p><strong>Your start:</strong> {start_line}</p>"
      "<p><strong>Your group:</strong></p>{group_block}{cart_block}{games_block}"
      "<p>Text {manager_name} at {manager_phone}.</p>")
with db._connect(DB) as conn:
    conn.execute("UPDATE message_templates SET html_body = ? WHERE id = ?", (V1, tpl["id"])); conn.commit()
v1 = ede.build_event_day_emails(EV, db_path=DB)
a1 = {m["customer_id"]: m for m in v1["messages"]}.get(880001, {})
check("v1 body: plain start, list, cart line, games list, no frame",
      "Your start: Hole 1A | 8:00 AM" in a1.get("text", "") and "- Bob Baker" in a1.get("text", "")
      and "Your cart partner: Bob Baker" in a1.get("text", "")
      and "NET games (Individual Net + MVP): you're in" in a1.get("text", "")
      and "THE GOLF FELLOWSHIP" not in a1.get("html", ""), a1.get("text"))
with db._connect(DB) as conn:
    conn.execute("UPDATE message_templates SET html_body = ? WHERE id = ?", (tpl["html_body"], tpl["id"])); conn.commit()

print("2. The boundary guard")
with db._connect(DB) as conn:
    conn.execute("UPDATE events SET chapter = 'Nowhere' WHERE id = ?", (EV,)); conn.commit()
b3 = ede.build_event_day_emails(EV, db_path=DB)
check("a blank {manager_name} holds every message", b3["counts"]["ready"] == 0
      and all("blank: {manager_name}" in h["reason"] for h in b3["held"]
              if h.get("email") and "not in a group" not in h["reason"]), b3["held"][:2])
with db._connect(DB) as conn:
    conn.execute("UPDATE events SET chapter = 'San Antonio' WHERE id = ?", (EV,)); conn.commit()
orig_body = tpl["html_body"]
def set_body(body):
    with db._connect(DB) as conn:
        conn.execute("UPDATE message_templates SET html_body = ? WHERE id = ?", (body, tpl["id"])); conn.commit()
set_body(orig_body + "<p>{x}</p>")
b4 = ede.build_event_day_emails(EV, db_path=DB)
check("a leftover {x} holds the message", b4["counts"]["ready"] == 0
      and any("{x}" in h["reason"] for h in b4["held"]), b4["held"][:2])
set_body(orig_body + "<p>Meet at [MEETING SPOT].</p>")
b5 = ede.build_event_day_emails(EV, db_path=DB)
check("a [BRACKETED BLANK] holds the message", b5["counts"]["ready"] == 0, b5["held"][:2])
set_body(orig_body)

print("3. The staff-only preview")
SENT.clear()
r = ede.send_event_day_preview(EV, to_address="pat@gmail.com", db_path=DB)
check("a non-staff address is refused", "error" in r and "staff only" in r["error"] and not SENT, r)
r = ede.send_event_day_preview(EV, to_address="kerry@thegolffellowship.com, pat@gmail.com", db_path=DB)
check("a mixed list is refused whole", "error" in r and not SENT, r)
r = ede.send_event_day_preview(EV, db_path=DB)
check("default preview goes to Kerry, ONE mail",
      r.get("status") == "sent" and len(SENT) == 1 and SENT[0]["to_address"] == "kerry@thegolffellowship.com", r)
check("…carries 3 samples, the held list and the counts",
      SENT and SENT[0]["html_body"].count("<strong>To:</strong>") == 3 and "HELD" in SENT[0]["html_body"]
      and "Eli Eno" in SENT[0]["html_body"] and "NOT approved" in SENT[0]["html_body"])

print("4. The member send")
SENT.clear()
r = ede.send_event_day_emails(EV, confirm=True, db_path=DB)
check("refused without the approval stamp", "refused" in r and not SENT, r)
db.set_app_setting(ede.APPROVAL_KEY, tpl["hash"], db_path=DB)
r = ede.send_event_day_emails(EV, confirm=False, db_path=DB)
check("refused without confirm, even when approved", "refused" in r and not SENT, r)
set_body(orig_body.replace("See you on the first tee", "See you soon"))
r = ede.send_event_day_emails(EV, confirm=True, db_path=DB)
check("an edited template voids the stamp", "refused" in r and not SENT, r)
set_body(orig_body)
r = ede.send_event_day_emails(EV, confirm=True, db_path=DB)
check("approved + confirm sends every ready message once",
      r.get("counts", {}).get("sent") == 5 and len(SENT) == 5, r.get("counts"))
check("…only to the fixture's own addresses",
      sorted(s["to_address"] for s in SENT) == sorted(["ann@example.test", "bob@example.test",
                                                         "cal@example.test", "dee@example.test",
                                                         "gus@example.test"]))
r2 = ede.send_event_day_emails(EV, confirm=True, db_path=DB)
check("a second run sends nothing (idempotent per event + customer)",
      len(SENT) == 5 and r2["counts"]["sent"] == 0 and r2["counts"]["skipped"] == 5, r2.get("counts"))
with db._connect(DB) as conn:
    rows = conn.execute("SELECT customer_id, status FROM event_day_email_sends WHERE event_id = ?", (EV,)).fetchall()
check("one 'sent' row per customer", len(rows) == 5 and all(x["status"] == "sent" for x in rows), [tuple(x) for x in rows])

print("4b. One player's actual message as a staff test")
SENT.clear()
r = ede.send_event_day_test(EV, 880001, "pat@gmail.com", db_path=DB)
check("a test to a non-staff address is refused", "error" in r and not SENT, r)
r = ede.send_event_day_test(EV, 880001, "kerry@thegolffellowship.com", db_path=DB)
check("the test is the player's exact message, unwrapped",
      r.get("status") == "sent" and len(SENT) == 1 and SENT[0]["subject"] == by[880001]["subject"]
      and "PREVIEW" not in SENT[0]["html_body"] and "YOUR START" in SENT[0]["html_body"], r)
with db._connect(DB) as conn:
    n = conn.execute("SELECT COUNT(*) FROM event_day_email_sends WHERE event_id = ?", (EV,)).fetchone()[0]
check("…and it is not counted as the player's send", n == 5, n)
check("a held player has no test", "held" in (ede.send_event_day_test(EV, 880005, "kerry@thegolffellowship.com", db_path=DB).get("error") or ""))

print("4c. Re-issue after a start change (Kerry 10/13, the Quarry)")
with db._connect(DB) as conn:
    ok_post = conn.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES "
                           "('kerry', 'front-desk', 'Send it - GO') RETURNING id").fetchone()[0]
    lane_post = conn.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES "
                             "('tracker-claude', 'front-desk', 'TO: x\nFROM: tracker-claude (lane)\nre-issue') "
                             "RETURNING id").fetchone()[0]
    conn.commit()
SENT.clear()
r = ede.send_event_day_reissue(EV, lane_post, confirm=True, db_path=DB)
check("a post without Kerry's word is refused", "refused" in r and not SENT, r)
r = ede.send_event_day_reissue(EV, ok_post, db_path=DB)
check("without confirm it is a dry run naming every ready player",
      r.get("dry_run") and r["counts"]["to_send"] == 5 and not SENT
      and r["sample_subject"].startswith("UPDATED START: "), r.get("counts"))
r = ede.send_event_day_reissue(EV, ok_post, confirm=True, db_path=DB)
check("confirm re-issues to every ready player although each was already sent",
      r.get("counts", {}).get("sent") == 5 and len(SENT) == 5, r.get("counts"))
check("…subject says UPDATED START and the notice sits inside the panel",
      all(s["subject"].startswith("UPDATED START: ") for s in SENT)
      and all("Your starting hole has changed" in s["html_body"] for s in SENT)
      and all(s["html_body"].find("UPDATED START") < s["html_body"].find("YOUR START") for s in SENT))
check("…to the fixture's own addresses only",
      sorted(s["to_address"] for s in SENT) == sorted(["ann@example.test", "bob@example.test",
                                                         "cal@example.test", "dee@example.test",
                                                         "gus@example.test"]))
r = ede.send_event_day_reissue(EV, ok_post, confirm=True, db_path=DB)
check("the same sheet state is never re-issued twice",
      len(SENT) == 5 and r["counts"]["sent"] == 0 and len(r["already_reissued"]) == 5, r.get("counts"))
with db._connect(DB) as conn:
    n = conn.execute("SELECT COUNT(*) FROM event_day_email_sends WHERE event_id = ?", (EV,)).fetchone()[0]
check("…and event_day_email_sends is untouched", n == 5, n)

print("4d. Late add: the new player plus their group only (Kerry 10/20)")
SENT.clear()
_b = ede.build_event_day_emails(EV, db_path=DB)
_late = _b["messages"][0]
_grp = [m for m in _b["messages"] if m.get("group") == _late.get("group")]
r = ede.send_event_day_late_adds(EV, [_late["customer_id"]], lane_post, confirm=True, db_path=DB)
check("a late-add send without Kerry's word is refused", "refused" in r and not SENT, r)
r = ede.send_event_day_late_adds(EV, [_late["customer_id"]], ok_post, db_path=DB)
check("dry run plans the late add and their group only",
      r.get("dry_run") and r["counts"]["to_send"] == len(_grp) and not SENT, r.get("counts"))
r = ede.send_event_day_late_adds(EV, [_late["customer_id"]], ok_post, confirm=True, db_path=DB)
_mine = [x for x in SENT if x["to_address"] == _late["email"]]
_mates = [x for x in SENT if x["to_address"] != _late["email"]]
check("the late add gets the plain approved message",
      len(_mine) == 1 and _mine[0]["subject"] == _late["subject"]
      and "UPDATED GROUP" not in _mine[0]["html_body"], [x["subject"] for x in _mine])
check("…groupmates get UPDATED GROUP naming who joined",
      len(_mates) == len(_grp) - 1
      and all(x["subject"].startswith("UPDATED GROUP: ") and _late["name"] in x["html_body"] for x in _mates))
n = len(SENT)
r = ede.send_event_day_late_adds(EV, [_late["customer_id"]], ok_post, confirm=True, db_path=DB)
check("the same group state is never sent twice", len(SENT) == n and r["counts"]["sent"] == 0, r.get("counts"))
r = ede.send_event_day_late_adds(EV, [99999999], ok_post, db_path=DB)
check("a cid with no sendable message is refused", "refused" in r, r)

print("4e. Newcomers (Kerry 10/20): welcome line, Rules of Play, card totals")
check("first timer gets Kerry's line, pronoun from gender",
      ede.welcome_line("Adam", "first", "M") == "This is Adam's first time playing with us! Welcome him in and help him understand our rules.")
check("…they/them when gender is unknown", "Welcome them in and help them" in ede.welcome_line("Adam", "first", None))
check("guest and new member wording", "as a guest" in ede.welcome_line("Al", "guest") and "new members" in ede.welcome_line("Al", "new"))
check("no line for a regular", ede.welcome_line("Al", None) == "")
check("kinds", ede.newcomer_kind({"is_first_timer": True}) == "first"
      and ede.newcomer_kind({"current_player_status": "active_guest"}) == "guest"
      and ede.newcomer_kind({"is_new": True}) == "new" and ede.newcomer_kind({}) is None)
_bn = ede.late_add_banner(["Adam Wilson"], [ede.welcome_line("Adam", "first", "M")])
check("the welcome line rides in the UPDATED GROUP notice", "first time playing with us" in _bn)
check("rules note links the Rules of Play PDF", ede.RULES_OF_PLAY_URL in ede.rules_note())
_cs = ede.card_strip({"si_by_hole": {1: 1}, "ph_dots": {1: 1, 2: 1}, "net_dots": {1: 1}},
                     {"holes": [1, 2], "par": {1: 4, 2: 5}}, {}, None, None)
check("YOUR CARD has a TOT column with par and pop totals", ">TOT<" in _cs and ">9<" in _cs, _cs[:200])

print("5. The bridge")
os.environ["DATABASE_PATH"] = DB
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import mcp_server
import json
SENT.clear()
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-event-day-email:{EV}"))
check("dry bridge reports counts and a sample, sends nothing",
      out.get("counts", {}).get("ready") == 5 and len(out.get("samples", [])) == 1 and not SENT, out.get("counts"))
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-event-day-email:{EV}|preview|pat@gmail.com"))
check("preview bridge refuses a non-staff address", "error" in out and not SENT, out)
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-event-day-email:{EV}|send"))
check("there is no member-send bridge", "error" in out and not SENT, out)

# EMAIL PLAYERS (Kerry 2026-10-08): the scoring link and the admin routes
check("the template carries each player's scoring button ({scoring_button})",
      "{scoring_button}" in (tpl or {}).get("html_body", ""))
check("no Live Scoring on the event: no scoring line, nothing held for it",
      all("Keep score on your phone" not in m["text"] for m in b["messages"]))
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PIN", "4242")
import app as _app
_cl = _app.app.test_client()
check("the Email Players preview is admin only", _cl.get("/api/events/1/event-day-email").status_code in (401, 302, 403))
check("the member tee sheet is public (no PIN) and 404s an unknown event",
      _cl.get(f"/member/teesheet/{EV}").status_code == 200 and _cl.get("/member/teesheet/999999").status_code == 404)
check("the Email Players send is admin only",
      _cl.post("/api/events/1/event-day-email/send", json={}).status_code in (401, 302, 403))

print("6. Your group: photos + Spotlight links (Kerry 10/19)")
_g = {"players": [{"name": "Ann Able", "customer_id": 11, "cart_pos": 1},
                  {"name": "Bob Baker", "customer_id": 12, "cart_pos": 2}]}
_h = ede.spot_card(_g, _g["players"][0], start_headline="4:00 PM", start_sub="x", tee=None,
                   format_line="", photos={"12": 1700000000}, base_url="https://t.example")
check("a player with a photo shows it", 'src="https://t.example/member/photo/h/12.jpg?v=1700000000"' in _h)
check("a player without a photo keeps the initials", ">AA</div>" in _h and "/member/photo/h/11.jpg" not in _h)
check("every name links to that player's Spotlight",
      "/member/spotlight?player=11" in _h and "/member/spotlight?player=12" in _h)

try: os.unlink(DB)
except OSError: pass
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
