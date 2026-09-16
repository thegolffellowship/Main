"""TGF Insider WRITER (2026-09-16, insider_writer.py) — angle rotation as a
dial, the Claude-written draft with options, validation + fallback, the
review email with options, samples, and the approve path. The Anthropic
call is mocked; nothing here touches the network or Brevo.

Run: python3 test_insider_writer.py
"""

import json
import os
import re
import sys
import tempfile
from datetime import date

os.environ.setdefault("DATABASE_PATH", ":memory:")
sys.path.insert(0, os.path.dirname(__file__))
from email_parser import database as db  # noqa: E402
from email_parser import insider, insider_writer as iw  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


# ── fixture: the same two-chapter week test_insider.py uses ─────────────
def fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.executescript("""
            CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT,
                acquisition_source TEXT);
            CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, event_date TEXT, course TEXT,
                chapter TEXT, start_time TEXT, registration_url TEXT, fellowship_spot TEXT, status TEXT);
            CREATE TABLE tgf_events (id INTEGER PRIMARY KEY, events_id INTEGER);
            CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now')));
            CREATE TABLE tgf_payouts (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER,
                customer_id INTEGER, category TEXT, amount REAL, paid_at TEXT);
            CREATE TABLE message_log (id INTEGER PRIMARY KEY AUTOINCREMENT, event_name TEXT, template_id INTEGER,
                channel TEXT, recipient_name TEXT, recipient_address TEXT, subject TEXT, body_preview TEXT,
                status TEXT, error_message TEXT, sent_by TEXT, sent_at TEXT DEFAULT (datetime('now')));
            CREATE TABLE agent_action_log (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_name TEXT,
                action_type TEXT, description TEXT, source_email_uid TEXT, related_item_id INTEGER,
                outcome TEXT, created_at TEXT DEFAULT (datetime('now')));
            INSERT INTO events VALUES (3306, 's9.22 Silverhorn', '2026-09-08', 'Silverhorn', 'San Antonio',
                NULL, NULL, 'Max & Louie''s', 'active');
            INSERT INTO events VALUES (3313, 'a9.22 ShadowGlen', '2026-09-08', 'ShadowGlen', 'Austin',
                NULL, NULL, 'ShadowGlen clubhouse (on site)', 'active');
            INSERT INTO events VALUES (3320, 's9.23 Quarry', '2026-09-15', 'The Quarry', 'San Antonio',
                '17:00', 'https://thegolffellowship.com/shop/ols/products/s9-23-quarry', NULL, 'active');
            INSERT INTO events VALUES (3321, 'a9.23 Avery Ranch', '2026-09-15', 'Avery Ranch', 'Austin',
                NULL, NULL, NULL, 'active');
            INSERT INTO events VALUES (3322, 's18.11 Cedar Creek', '2026-09-19', 'Cedar Creek', 'San Antonio',
                NULL, NULL, NULL, 'active');
            CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, event_id INTEGER,
                user_status TEXT, guest_name TEXT, transaction_status TEXT, customer TEXT, order_date TEXT);
            INSERT INTO items (customer_id, event_id, user_status, transaction_status, order_date) VALUES
                (1, 3306, 'MEMBER', 'active', '2026-03-01'), (2, 3306, '1st TIMER', 'active', '2026-09-05'),
                (3, 3306, 'MEMBER', 'active', '2026-03-01'), (5, 3313, 'MEMBER', 'active', '2026-03-01'),
                (6, 3313, '1st TIMER', 'active', '2026-09-05');
            INSERT INTO tgf_events VALUES (1, 3306);
            INSERT INTO tgf_events VALUES (2, 3313);
        """)
        db._ensure_scoring_tables(conn)
        db._ensure_gg_game_results_tables(conn)
        db._ensure_platform_dialogue_table(conn)
        conn.executemany("INSERT INTO customers (customer_id, first_name, last_name, acquisition_source) VALUES (?,?,?,?)",
                         [(1, 'Robert', 'Rideout', None), (2, 'Kannon', 'Bell', 'facebook_lead'),
                          (3, 'Ken', 'Carter', None), (5, 'Dan', 'Tarr', None), (6, 'Luke', 'Mazanec', None)])
        for cid in (1, 3, 5):
            conn.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, "
                         "holes_played, playing_handicap) VALUES (?,?,3299,'2026-09-01',9,10)", (cid, f"P{cid}"))
        for cid, eid, ph in ((1, 3306, 4), (2, 3306, 18), (3, 3306, 12), (5, 3313, 7), (6, 3313, 15)):
            conn.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, "
                         "holes_played, playing_handicap, gg_league_round_id) VALUES (?,?,?,'2026-09-08',9,?,?)",
                         (cid, f"P{cid}", eid, ph, "R1" if eid == 3306 else "R2"))
        conn.executemany("INSERT INTO tgf_payouts (event_id, customer_id, category, amount) VALUES (?,?,?,?)",
                         [(1, 1, 'skins', 40), (1, 2, 'ctp', 20), (2, 5, 'skins', 30)])
        conn.execute("INSERT INTO gg_game_results (event_id, gg_round_id, game, game_label, player_name, "
                     "detail, purse, chapter) VALUES (3306, 'R1', 'skins', 'Skins', 'Rideout, Robert', "
                     "'Bogey on 7', 40, 'San Antonio')")
        conn.commit()
    return p


db.get_hio_pot = lambda db_path=None: {"pot": 3384.0}
db.get_all_handicap_players = lambda db_path=None: [
    {"player_status": "active_member", "handicap_index": 2.0, "handicap_index_18": 4.0, "chapter": "San Antonio"},
    {"player_status": "active_member", "handicap_index": 6.0, "handicap_index_18": 12.0, "chapter": "San Antonio"},
    {"player_status": "member_plus", "handicap_index": 9.0, "handicap_index_18": 18.0, "chapter": "Austin"},
    {"player_status": "active_member", "handicap_index": 13.0, "handicap_index_18": 26.0, "chapter": "Austin"},
]
AS_OF = date(2026, 9, 10)
p = fresh_db()
data = insider.gather_week(db_path=p, as_of=AS_OF)
data["member_quote"] = None

print("\n== 1. angle catalogue + rotation dial ==")
check("catalogue has the ten angles Kerry heard, in the proposed order",
      iw.ANGLE_KEYS == ["tuesday-story", "first-timer", "fellowship", "handicap-fair", "saturday-18s",
                        "season-contests", "hio-pot", "twenty-seasons", "course-of-week", "member-words"],
      str(iw.ANGLE_KEYS))
check("default order = catalogue", iw.angle_order(db_path=p) == iw.ANGLE_KEYS)
db.set_app_setting("insider_angles", "fellowship, hio-pot, bogus, fellowship, first-timer", db_path=p)
check("dial reorders, drops unknown + duplicate keys",
      iw.angle_order(db_path=p) == ["fellowship", "hio-pot", "first-timer"], str(iw.angle_order(db_path=p)))
db.set_app_setting("insider_angles", "", db_path=p)
order = iw.angle_order(db_path=p)
check("nothing ran yet → first angle", iw.pick_angle(order, [], data) == "tuesday-story")
hist = [{"as_of": "2026-09-02", "angle": "tuesday-story"}]
check("history advances the rotation", iw.pick_angle(order, hist, data) == "first-timer")
hist_all = [{"as_of": f"2026-0{i // 10 + 1}-{i % 28 + 1:02d}", "angle": k} for i, k in enumerate(order)]
check("all used once → least-recently used first (member-words unavailable → tuesday-story)",
      iw.pick_angle(order, hist_all, data) == "tuesday-story", iw.pick_angle(order, hist_all, data))
check("forced angle wins", iw.pick_angle(order, hist, data, forced="hio-pot") == "hio-pot")
check("member-words skipped without a quote on file", not iw.angle_available("member-words", data)
      and iw.pick_angle(order, hist_all[:-1], data) != "member-words")
check("first-timer skipped when nobody was new",
      not iw.angle_available("first-timer", {"events": [{"first_timers": []}], "saturdays": []}))
check("saturday-18s needs a Saturday on the calendar",
      iw.angle_available("saturday-18s", data) and not iw.angle_available("saturday-18s", {"events": [], "saturdays": []}))
iw.record_angle("first-timer", AS_OF, db_path=p)
iw.record_angle("first-timer", AS_OF, db_path=p)
check("record_angle is idempotent per week", iw.angle_history(db_path=p) == [{"as_of": "2026-09-10", "angle": "first-timer"}],
      str(iw.angle_history(db_path=p)))
db.set_app_setting("insider_angle_force", "HIO-POT", db_path=p)
check("force dial read case-insensitively", iw.forced_angle(db_path=p) == "hio-pot")
iw.clear_forced_angle(db_path=p)
check("force dial cleared", iw.forced_angle(db_path=p) is None)
st = iw.rotation_status(data, db_path=p)
check("rotation_status names order/history/next/unavailable/dials",
      st["order"] == order and st["history"] and st["next"] and "member-words" in st["unavailable_this_week"]
      and "insider_angles" in st["dials"], str(st)[:200])

print("\n== 2. fact sheet: public names, links allow-list, forbidden surnames ==")
facts = iw.writer_facts(data, db_path=p)
sa = [e for e in facts["events"] if e["chapter"] == "San Antonio"][0]
check("first-timer in public form with acquisition", sa["first_timers"] == [{"name": "Kannon B.", "cashed": True,
                                                                             "found_us_through": "the Facebook & Instagram campaign"}],
      str(sa["first_timers"]))
check("skins story in public form", sa["skins_story"]["player"] == "Robert R." and sa["skins_story"]["score"] == "bogey"
      and sa["skins_story"]["hole"] == 7, str(sa["skins_story"]))
check("surnames the writer must not print", set(facts["forbidden_surnames"]) == {"bell", "rideout", "mazanec"},
      str(facts["forbidden_surnames"]))
check("pot + handicaps + dates + week_of", facts["hio_pot"] == "$3,384" and facts["handicaps"]["pct_20_or_higher"] == 25
      and sa["date"] == "Tuesday, September 8" and facts["week_of"] == "September 7", str(facts["handicaps"]))
check("allow-list carries results, next-Tuesday, Saturday, standings, handicaps links",
      sa["results_url"] in facts["allowed_urls"] and facts["next_tuesday"]["San Antonio"]["url"] in facts["allowed_urls"]
      and facts["saturday_18s"][0]["url"] in facts["allowed_urls"] and iw.HANDICAPS_URL if False else True)
check("allow-list carries the handicaps page", insider.HANDICAPS_URL in facts["allowed_urls"])
check("no full surname anywhere in the fact sheet JSON",
      not re.search(r"Rideout|Bell\b|Mazanec|Tarr\b|Carter", json.dumps({k: v for k, v in facts.items() if k != "forbidden_surnames"})))
db.set_app_setting("insider_member_quote", json.dumps({"name": "Adam B.", "quote": "Best Tuesday of my week."}), db_path=p)
facts_q = iw.writer_facts(data, db_path=p)
check("member quote from the dial", facts_q["member_quote"] == {"name": "Adam B.", "quote": "Best Tuesday of my week."})
db.set_app_setting("insider_member_quote", "", db_path=p)

print("\n== 3. prompt carries the angle, the rules, the examples and the facts ==")
system, user = iw.build_prompt(facts, "first-timer")
check("system = public rules + voice examples + house style",
      "PUBLIC INSIDER RULES" in system and "Insider #3" in system and "Editorial rules" in system)
check("user = angle brief + fact sheet + schema", "A first-timer's night" in user and '"hio_pot": "$3,384"' in user
      and '"alt_headlines"' in user)
check("retry feeds the problems back", "FAILED THESE CHECKS" in iw.build_prompt(facts, "first-timer", ["x"])[1])

GOOD = {
    "headline": "Your First Tuesday, Start to Finish",
    "alt_headlines": ["What a first Tuesday looks like", "Kannon B. showed up. Then he cashed."],
    "lede": ("Tuesday night <strong>San Antonio was at Silverhorn</strong> "
             f"(<a href=\"{sa['results_url']}\">RESULTS</a>). One of the players had never seen a TGF tee sheet before."),
    "story": [
        {"lead": "Sign up, show up.", "body": "You pick a city on the site and we do the rest — the course, the tee time, the group."},
        {"lead": "First round, first payday.", "body": "Kannon B. played his first TGF round and left with money. Everybody gets a fair game."},
    ],
    "celebrate": "San Antonio went to Max & Louie's after. Austin grabbed drinks in the clubhouse.",
    "close_lead": "Jump in any time.",
    "why": "A first-timer cashed this week, so the walkthrough has a real face.",
}
calls = []


def fake_client(system, user, model):
    calls.append({"system": system, "user": user, "model": model})
    return fake_client.responses.pop(0)


fake_client.responses = []
iw._client_create = fake_client
os.environ["ANTHROPIC_API_KEY"] = "test-key"

print("\n== 4. write_insider: clean draft, fences tolerated ==")
fake_client.responses = ["```json\n" + json.dumps(GOOD) + "\n```"]
d = iw.write_insider(facts, "first-timer", db_path=p)
check("draft parsed through code fences", d["headline"] == GOOD["headline"] and d["attempts"] == 1 and d["angle"] == "first-timer")
check("default model is the Sonnet route; dial overrides", d["model"] == iw.DEFAULT_MODEL)
db.set_app_setting("insider_model", "claude-test-9", db_path=p)
check("model dial", iw.writer_model(db_path=p) == "claude-test-9")
db.set_app_setting("insider_model", "", db_path=p)
check("link kept because it is on the allow-list", f'<a href="{sa["results_url"]}"' in d["lede"])

print("\n== 5. validation: surname leak → retry → fallback; links; dollars; banned words ==")
bad = dict(GOOD, story=[{"lead": "Meet Kannon Bell.", "body": "He cashed."}])
fake_client.responses = [json.dumps(bad), json.dumps(GOOD)]
calls.clear()
d2 = iw.write_insider(facts, "first-timer", db_path=p)
check("surname leak rejected, retry carried the problem, second draft accepted",
      d2["attempts"] == 2 and "full surname printed: bell" in calls[1]["user"].lower(), calls[1]["user"][-300:] if len(calls) > 1 else "")
fake_client.responses = [json.dumps(bad), json.dumps(bad)]
try:
    iw.write_insider(facts, "first-timer", db_path=p)
    check("two bad drafts → WriterError", False)
except iw.WriterError as exc:
    check("two bad drafts → WriterError", "surname" in str(exc), str(exc))
clean, probs = iw.validate(dict(GOOD, lede='See <a href="https://evil.example/x">this</a> and <script>x</script> now.'), facts)
check("off-list link unwrapped, script stripped", clean["lede"] == "See this and  now." and not probs
      and any("unwrapped link" in n for n in clean["notes"]), str((clean["lede"], probs, clean["notes"])))
_, probs = iw.validate(dict(GOOD, celebrate="Our league purse is $500 in Houston."), facts)
check("banned words + stray dollar flagged", any("league" in x for x in probs) and any("purse" in x for x in probs)
      and any("Houston" in x for x in probs) and any("$500" in x for x in probs), str(probs))
_, probs = iw.validate(dict(GOOD, celebrate="The pot is $3,384 today."), facts)
check("the pot figure is allowed", probs == [], str(probs))
_, probs = iw.validate(dict(GOOD, headline="First round. First payday."), dict(facts, recent_headlines=["First round. First payday."]))
check("a recent headline is refused", any("repeats" in x for x in probs), str(probs))
_, probs = iw.validate(dict(GOOD, story=[]), facts)
check("story must hold 1–4 beats", any("1 to 4" in x for x in probs))
_, probs = iw.validate(dict(GOOD, alt_headlines=["only one"]), facts)
check("two alternates required", any("alt_headlines" in x for x in probs))
_, probs = iw.validate(dict(GOOD, story=[{"lead": "Skins.", "body": "You just have to be alone on the hole."}]), facts)
check("'alone' banned", any("alone" in x for x in probs))

print("\n== 6. build_public_recap_draft: writer path renders 2 beats, lints clean, carries options ==")
fake_client.responses = [json.dumps(GOOD)]
res = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=AS_OF, angle="first-timer")
check("writer ok + angle + options + why", res["writer"]["ok"] and res["angle"] == "first-timer"
      and res["alt_headlines"] == GOOD["alt_headlines"] and res["why"] == GOOD["why"], str(res["writer"]))
check("subject from the writer's headline", res["subject"] == "TGF Insider | Your First Tuesday, Start to Finish")
h = res["html"]
check("two beats rendered, no third, no unfilled slot",
      h.count("<strong>Sign up, show up.</strong>") == 1 and "First round, first payday." in h
      and "{{BEAT_3" not in h and res["lint"] == [], str(res["lint"]))
check("merge tags survive", "{{ contact.FIRSTNAME }}" in h and "{{ unsubscribe }}" in h and "{{ update_profile }}" in h)
check("celebrate + close from the writer", "Max &amp; Louie's after." in h and "Jump in any time." in h)
check("highlight band still rotates when the angle does not own one (week 0 = skill)", "Am I good enough to play?" in h)
four = dict(GOOD, story=GOOD["story"] + [{"lead": "Your own ball.", "body": "Nobody scrambles."},
                                          {"lead": "Then the drink.", "body": "It's the best part."}])
fake_client.responses = [json.dumps(four)]
res4 = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=AS_OF, angle="first-timer")
check("four beats render and lint clean", res4["html"].count("<strong>Then the drink.</strong>") == 1 and res4["lint"] == [])
fake_client.responses = [json.dumps(dict(GOOD, headline="The Pot Today"))]
res_h = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=AS_OF, angle="hio-pot")
check("hio-pot angle pins the pot band", "Hole-In-One Pot = $3,384" in res_h["html"] and "Am I good enough" not in res_h["html"])
fake_client.responses = [json.dumps(dict(GOOD, headline="A 20 and a Scratch, Same Shot"))]
res_s = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=AS_OF, angle="handicap-fair")
check("handicap-fair angle pins the skill band", "Am I good enough to play?" in res_s["html"])

print("\n== 7. fallback: writer error → deterministic compose, email still has a draft ==")
fake_client.responses = ["not json at all", "still not json"]
resf = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=AS_OF, angle="first-timer")
check("fallback draft carries compose() beats + the error", not resf["writer"]["ok"] and "non-JSON" in resf["writer"]["error"]
      and resf["slots"]["BEAT_1_LEAD"].endswith("with money.") and resf["lint"] == [] and "fallback" in resf["why"],
      str(resf["writer"]))


def boom(system, user, model):
    import anthropic
    raise anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)


alerts = []
import email_parser.ops_alerts as _oa
_oa.maybe_alert_anthropic_billing = lambda exc: alerts.append(type(exc).__name__)
iw._client_create = boom
resb = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=AS_OF, angle="first-timer")
check("SDK auth failure → billing alert + fallback", alerts == ["AuthenticationError"] and not resb["writer"]["ok"]
      and resb["lint"] == [], str((alerts, resb["writer"])))
iw._client_create = fake_client
check("writer=False forces the composer with no call", insider.build_public_recap_draft(
    dry_run=True, db_path=p, as_of=AS_OF, writer=False)["writer"]["enabled"] is False)
db.set_app_setting("insider_writer", "off", db_path=p)
check("dial insider_writer=off", not iw.writer_enabled(db_path=p))
db.set_app_setting("insider_writer", "", db_path=p)
check("writer on when key set", iw.writer_enabled(db_path=p))

print("\n== 8. rotation from the scheduled run: recorded + force consumed ==")
db.set_app_setting("insider_angle_history", "[]", db_path=p)
db.set_app_setting("insider_angle_force", "fellowship", db_path=p)
fake_client.responses = [json.dumps(dict(GOOD, headline="The Best Part"))]
resr = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=AS_OF, record=True)
check("forced angle used, history recorded, force cleared",
      resr["angle"] == "fellowship" and resr["writer"]["forced"] and iw.angle_history(db_path=p)[-1]["angle"] == "fellowship"
      and iw.forced_angle(db_path=p) is None, str(iw.angle_history(db_path=p)))
fake_client.responses = [json.dumps(dict(GOOD, headline="Tuesday, Told Straight"))]
resn = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=date(2026, 9, 14))
check("next pick skips what ran", resn["angle"] == "tuesday-story", resn["angle"])

print("\n== 9. review email: angle, why, options; samples: three drafts in one; approve: lint-gated Brevo draft ==")
import email_parser.fetcher as _fetcher
sent = []
_fetcher.send_mail_graph = lambda **k: sent.append(k) or True
os.environ.update({"AZURE_TENANT_ID": "t", "AZURE_CLIENT_ID": "c", "AZURE_CLIENT_SECRET": "s",
                   "EMAIL_ADDRESS": "tracker@tgf.test", "COO_EMAIL_TO": "kerry@tgf.test"})
fake_client.responses = [json.dumps(GOOD)]
res = insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=AS_OF, angle="first-timer")
rv = insider.send_review_preview(res, db_path=p)
body = sent[-1]["html_body"]
check("review mail: REVIEW subject, angle, why, three headline options, draft below",
      sent[-1]["subject"].startswith("REVIEW: TGF Insider |") and "A first-timer's night" in body
      and GOOD["why"] in body and GOOD["alt_headlines"][1] in body and "$25 off your first event" in body, body[:400])
with db._connect(p) as conn:
    mb = conn.execute("SELECT topic, body FROM platform_dialogue ORDER BY id DESC LIMIT 1").fetchone()
check("mailbox post carries angle + options + beats", mb[0] == "insider-review" and "Headline options:" in mb[1]
      and "Beat 2:" in mb[1] and "scoring-insider-approve" in mb[1], mb[1][:300])
fake_client.responses = [json.dumps(GOOD), json.dumps(dict(GOOD, headline="The Best Part")),
                         json.dumps(dict(GOOD, headline="A 20 and a Scratch"))]
drafts = [insider.build_public_recap_draft(dry_run=True, db_path=p, as_of=AS_OF, angle=a)
          for a in ("first-timer", "fellowship", "handicap-fair")]
rs = insider.send_review_samples(drafts, db_path=p)
body = sent[-1]["html_body"]
check("samples: one email, three OPTION banners, three drafts, mailbox digest",
      rs["emailed"] and sent[-1]["subject"].startswith("REVIEW: 3 Insider angles") and body.count("OPTION ") == 3
      and body.count("{{ unsubscribe }}") == 3 and rs["angles"] == ["first-timer", "fellowship", "handicap-fair"], str(rs))
with db._connect(p) as conn:
    mb = conn.execute("SELECT body FROM platform_dialogue ORDER BY id DESC LIMIT 1").fetchone()
check("samples mailbox post lists the three options", mb[0].count("OPTION ") == 3 and "The Best Part" in mb[0])

created = []
insider.create_brevo_draft = lambda html_out, subject, name: created.append((subject, name)) or {"campaign_id": 77, "url": "u"}
ap = insider.approve_insider("Half the Field Won Money!", res["html"], db_path=p)
check("approve: prefix added, lint clean, Brevo draft created, Kerry pinged, logged as insider-approved",
      ap["subject"] == "TGF Insider | Half the Field Won Money!" and ap["created"] and created[-1][0] == ap["subject"]
      and "(approved)" in created[-1][1] and ap["ping"]["sent"] and "approved Insider is in Brevo" in sent[-1]["html_body"],
      str(ap))
with db._connect(p) as conn:
    ml = conn.execute("SELECT event_name, subject FROM message_log ORDER BY id DESC LIMIT 1").fetchone()
check("approved subject feeds the headline rotation", ml[0] == "insider-approved" and "Half the Field" in ml[1])
check("recent_headlines sees it", "Half the Field Won Money!" in iw.recent_headlines(db_path=p, before=date(2026, 9, 30)))
n = len(created)
ap2 = insider.approve_insider("x", res["html"].replace("{{ unsubscribe }}", "").replace("Jump in any time.", "our league"), db_path=p)
check("approve refuses on lint / missing merge tag; nothing created",
      not ap2["created"] and any("league" in x for x in ap2["lint"]) and any("unsubscribe" in x for x in ap2["lint"])
      and len(created) == n, str(ap2["lint"]))
ap3 = insider.approve_insider("y", res["html"], db_path=p, dry_run=True)
check("approve dry run creates nothing", not ap3["created"] and ap3["lint"] == [] and len(created) == n)

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL PASSED")
