"""Lone Star Cup QR signs (v2.525.19, Kerry 2026-10-07 #1357-6 / #1358-2):
one sign per group per session, from the Cup's own score-entry rounds
(pairings_holes 'lsc:<session>'), each with the group's scorer QR and the
match it carries. Read-only: never seeds a round.

Run: python3 test_cup_signs.py
"""
import os, sys, json, tempfile, contextlib, io, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-cupsigns-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
os.environ["ADMIN_PIN"] = "4242"
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser import score_entry as se                        # noqa: E402
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


EV = 3329
PAR = [4, 4, 3, 4, 5, 4, 4, 3, 4] * 2
with db._connect(tmp) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, format, course) VALUES "
                 "(?, 'LONE STAR CUP 2026', '2026-10-10', 'San Antonio', '18 Holes', 'The Hideout')", (EV,))
    for cid, fn, ln in ((7, "Matthew", "Jenkins"), (4, "John", "Wade"), (35, "Rob", "Callaway"),
                        (130, "Chuck", "Fehlis"), (13, "Luke", "Youngs"), (18, "Kerry", "Niester")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
    conn.commit()
course = [{"hole": h, "par": PAR[h - 1], "stroke_index": h, "yardage": 380} for h in range(1, 19)]
rid = se.create_round(EV, 18, round_date="2026-10-10", label="Lone Star Cup · Saturday AM — Four-Ball",
                      course_holes=course, pairings_holes="lsc:sat-am", created_by="test", db_path=tmp)["round_id"]
g1 = se.upsert_group(rid, 1, tee_time="8:30", players=[
    {"customer_id": 7, "display_name": "Matthew Jenkins", "seat": 1},
    {"customer_id": 4, "display_name": "John Wade", "seat": 2},
    {"customer_id": 35, "display_name": "Rob Callaway", "seat": 3},
    {"customer_id": 130, "display_name": "Chuck Fehlis", "seat": 4}], db_path=tmp)["group_id"]
g2 = se.upsert_group(rid, 2, tee_time="8:40", players=[
    {"customer_id": 13, "display_name": "Luke Youngs", "seat": 1},
    {"customer_id": 18, "display_name": "Kerry Niester", "seat": 2}], db_path=tmp)["group_id"]
# a plain (non-cup) round on the same event must NOT appear on the signs
se.create_round(EV, 18, label="practice", course_holes=course, pairings_holes="18", db_path=tmp)
db.set_app_setting("lsc_matches", json.dumps({
    "event_id": EV, "defending_champion": "sa",
    "sessions": [{"id": "sat-am", "label": "Saturday AM — Four-Ball", "date": "2026-10-10",
                  "format": "fourball", "se_round": rid, "n_holes": 18,
                  "matches": [{"id": "SAT-AM-1", "tee_time": "8:30", "austin": [7, 4], "sa": [35, 130]},
                              {"id": "SAT-AM-2", "tee_time": "8:40", "austin": [13], "sa": [18]}]}]}), tmp)

sh = se.cup_sign_sheets(EV, base_url="https://tgf-tracker.up.railway.app", db_path=tmp)
check("the event is named", sh.get("event", {}).get("name") == "LONE STAR CUP 2026", str(sh.get("event")))
check("only the Cup's session rounds are listed (the practice round is not)",
      [r["session"] for r in sh.get("rounds", [])] == ["sat-am"], str([r.get("session") for r in sh.get("rounds", [])]))
r0 = (sh.get("rounds") or [{}])[0]
gs = r0.get("groups") or []
check("two groups, in order, with their tee times", [(g["group_num"], g["tee_time"]) for g in gs] == [(1, "8:30"), (2, "8:40")],
      str([(g.get("group_num"), g.get("tee_time")) for g in gs]))
check("each group carries its match id from the dial", [g["matches"] for g in gs] == [["SAT-AM-1"], ["SAT-AM-2"]],
      str([g.get("matches") for g in gs]))
check("the players are listed in seat order", [p["name"] for p in gs[0]["players"]][:2] == ["Matthew Jenkins", "John Wade"] if gs else False)
check("the QR is the group's signed scoring link", bool(gs) and gs[0]["url"].startswith("https://tgf-tracker.up.railway.app/member/score?t=")
      and se.verify_group_token(gs[0]["url"].split("t=", 1)[1]) == g1, str(gs and gs[0].get("url")))
check("the QR renders as SVG", bool(gs) and (gs[0].get("qr_svg") or "").lstrip().startswith("<svg"))
check("an unknown event says so, never raises", "error" in se.cup_sign_sheets(424242, db_path=tmp))

# the PREVIEW dial (Track B #1405): a demo round bound in lsc_preview_matches
# gets its matches flagged preview; the live dial is untouched
rid_demo = se.create_round(EV, 18, round_date="2026-10-10", label="FOURBALL · PREVIEW", course_holes=course,
                           pairings_holes="preview:sat-am", db_path=tmp)["round_id"]
gd = se.upsert_group(rid_demo, 1, tee_time="8:30", players=[
    {"customer_id": 7, "display_name": "Matthew Jenkins", "seat": 1},
    {"customer_id": 35, "display_name": "Rob Callaway", "seat": 2}], db_path=tmp)["group_id"]
db.set_app_setting("lsc_preview_matches", json.dumps({
    "event_id": EV, "sessions": [{"id": "sat-am", "label": "FOURBALL", "format": "fourball", "se_round": rid_demo,
                                  "n_holes": 18, "matches": [{"id": "DEMO-1", "austin": [7], "sa": [35]}]}]}), tmp)
rmd = se.round_matches(rid_demo, db_path=tmp)
check("a demo round bound in lsc_preview_matches carries its matches, flagged preview",
      rmd.get(7, {}).get("match_id") == "DEMO-1" and rmd[7].get("preview") is True and rmd[7]["session"] == "sat-am", str(rmd))
check("the live round's matches are not flagged preview", se.round_matches(rid, db_path=tmp)[7].get("preview") is False)
check("round_is_preview tells the two apart", se.round_is_preview(rid_demo, db_path=tmp) and not se.round_is_preview(rid, db_path=tmp))
check("the demo round's signs are not on the Cup sign page (only lsc:* rounds)",
      [r["session"] for r in se.cup_sign_sheets(EV, db_path=tmp)["rounds"]] == ["sat-am"])

# the staff print page
import app as A                                                   # noqa: E402
tc = A.app.test_client()
with tc.session_transaction() as s_:
    s_.clear(); s_["role"] = "manager"; s_["authenticated"] = True; s_["logged_in"] = True
page = tc.get(f"/events/{EV}/cup-signs")
body = page.get_data(as_text=True)
check("the sign page renders for a manager", page.status_code == 200, page.status_code)
check("it carries the session, the match, the tee time and the QR",
      "Saturday AM" in body and "SAT-AM-1" in body and "8:30" in body and "<svg" in body)
check("SCORE THIS GROUP / FOLLOW THE CUP is what the sign promises", "score this group or follow the Cup" in body)
check("?round_id= narrows to one session", tc.get(f"/events/{EV}/cup-signs?round_id=999999").get_data(as_text=True).count("<svg") == 0)
# the phone page: a Cup link carries the splash markup, a plain event's link does not
g_plain = se.upsert_group(se.create_round(4242, 18, label="plain", course_holes=course, pairings_holes="18", db_path=tmp)["round_id"],
                          1, players=[{"customer_id": 7, "display_name": "Matthew Jenkins", "seat": 1}], db_path=tmp)["group_id"]
pc = A.app.test_client()
check("a Cup scoring link opens on the SPLASH markup (route reads the round, not the card)",
      'id="se-splash"' in pc.get(f"/member/score?t={se.make_group_token(g1)}").get_data(as_text=True))
# the Cup's Friday practice round opens on the splash too (Kerry 10/8)
db.set_app_setting("oneoff_charges", json.dumps({str(EV): {"addons": [{"key": "friday", "event_id": 3330}]}}), db_path=tmp)
g_prac = se.upsert_group(se.create_round(3330, 18, label="practice", course_holes=course, pairings_holes="18", db_path=tmp)["round_id"],
                         1, players=[{"customer_id": 7, "display_name": "Matthew Jenkins", "seat": 1}], db_path=tmp)["group_id"]
check("the practice round's link opens on the SPLASH (Kerry 10/8)",
      'id="se-splash"' in pc.get(f"/member/score?t={se.make_group_token(g_prac)}").get_data(as_text=True))
check("a plain event's link carries no Cup splash", 'id="se-splash"' not in pc.get(f"/member/score?t={se.make_group_token(g_plain)}").get_data(as_text=True))
check("a bad link carries no splash and still renders", 'id="se-splash"' not in pc.get("/member/score?t=nope").get_data(as_text=True))
check("group_is_cup never raises", se.group_is_cup(999999, db_path=tmp) is False and se.group_is_cup(g1, db_path=tmp) is True)
anon = A.app.test_client().get(f"/events/{EV}/cup-signs")
check("the page is staff-only", anon.status_code in (302, 401, 403), anon.status_code)

# the phone's landing: SCORE THIS GROUP / FOLLOW THE CUP (template contract)
tpl = open("templates/score_entry.html", encoding="utf-8").read()
check("the phone page lands on the two buttons before Who are you?",
      'data-act="gate-score"' in tpl and 'data-act="gate-follow"' in tpl
      and tpl.index("function gateScreen()") < tpl.index("function joinScreen()")
      and 'if (!who && !store.get(K.gate, false)) body = gateScreen();' in tpl)
# Kerry 10/9: "Make sure no links take you outside the scorer's interface of
# the SCORING and LEADERBOARD": FOLLOW THE CUP opens the scorer's LEADERBOARD
# with the match open, never the public Cup page
check("FOLLOW opens the scorer's LEADERBOARD (the Cup with the match expanded), never the public Cup page",
      'const follow = "/member/score/board?t=" + encodeURIComponent(T)' in tpl
      and '"&match=" + encodeURIComponent(cupIds[0])' in tpl and '"/member/lonestarcup?"' not in tpl)
check("the scorer's opened Fourball card stays one line per team (Kerry 10/10: \"Only showing one line per "
      "team for fourball is fine in scorers view\")", 'const fb = m.format === "fourball"' not in tpl)
check("+ reads X at the triple in a Cup match and rests on an X (Kerry 10/10: option 1)",
      "const toX = cupOf(s.cids) && !xx && cur.v != null && cur.v === hiOf(hole);" in tpl
      and 'class="se-plus tox"' in tpl and 'class="se-plus rest"' in tpl and ".se-plus.tox {" in tpl)
check("the hole screen carries the HOW IT WORKS pill (#1398-C2) and NO Team score box (Kerry 10/10: "
      "\"I don't think that team score is necessary\")",
      "${teamScoreBox(hole)}" not in tpl and "pr-hiw-link" in tpl
      and 'data-act="hiw"' in tpl and "Team PH " in tpl)
# Kerry 10/9: "For how it works buttons they should only pop up a modal that
# can easily be closed" -- the scoring page's HOW IT WORKS is a popup with a
# close, never a link out; the info body's PDF/share links are hidden in it
check("HOW IT WORKS on the scoring page opens a closable popup, not a page",
      "function openHiw(k)" in tpl and "function closeHiw()" in tpl and 'if (act === "hiw") { openHiw(b.dataset.k); return; }' in tpl
      and "/member/lonestarcup/info#" not in tpl and '<script src="/static/js/lsc-info.js"></script>' in tpl
      and ".se-hiwm [data-lsc-info-pdf], .se-hiwm [data-lsc-info-share] { display: none !important; }" in tpl)
import re as _re
_links = [m for m in _re.findall(r'href="(/[^"$]*)', tpl) if not m.startswith("/static/")]
check("the scoring page carries no link to another page", not _links, _links)
_cts = open("templates/contests.html", encoding="utf-8").read()
check("the scorer's LEADERBOARD hides the EVENT INFO links that open outside it",
      "body.evlb-solo [data-lsc-info-pdf], body.evlb-solo [data-lsc-info-share] { display: none !important; }" in _cts)
# Kerry 10/9: "remove all that hidden team management stuff from the leaderboard
# page altogether? Put it on its own separate admin only page"
_teams = open("templates/lsc_teams.html", encoding="utf-8").read()
check("the Cup rosters / deposits / lodging panel is gone from LEADERBOARD and lives on /admin/lsc-teams",
      'id="lsc-rosters"' not in _cts and "depBadge" not in _cts and "lodgeIc" not in _cts
      and 'id="lsc-rosters"' in _teams and "depBadge" in _teams and "Lodging" in _teams)
_app = open("app.py", encoding="utf-8").read()
check("/admin/lsc-teams is admin only",
      '@app.route("/admin/lsc-teams")' in _app
      and 'if session.get("role") != "admin":\n        return redirect("/events")\n    return render_template("lsc_teams.html")' in _app)
check("player rows carry name + tee + PH only: no 'vs' and no 'Team · one ball' on the hole screen",
      'replace(/^Match vs/, "vs")' not in tpl and "s.team ? s.meta : null" not in tpl)
check("the landing carries THIS GROUP by side, Who are you? carries Back, Held carries SAVED SO FAR (mockups QRLanding / WhoAreYou / Held)",
      'class="se-box se-this"' in tpl and 'data-act="gate-back"' in tpl and "Saved so far" in tpl
      and "There's no timeout and nothing happens by itself." in tpl
      and "Tap your name to keep the card." in tpl)
check("an event not yet opted in (404 'not open for this event') shows the admin sign-in, like scoring-off does",
      '/not open (yet|for this event)/' in tpl)
check("the Cup SPLASH (Kerry 10/8, FD #1442): inline markup, the logo's navy, a shimmer, reduced-motion fallback, tap to skip, words if the logo fails",
      'id="se-splash"' in tpl and "--lsc-navy: #002855" in tpl and "background: var(--lsc-navy)" in tpl and "@keyframes se-shimmer" in tpl and "prefers-reduced-motion" in tpl
      and 'el.addEventListener("click", done)' in tpl and "LONE STAR CUP<span>2026</span>" in tpl
      and '"se_splash_" + tk' in tpl and "!who && !store.get(K.gate, false) && !following" in tpl)
check("session titles are FOURBALL / FOURSOMES / SINGLES (#1397-1)",
      '"FOURBALL"' in tpl and '"FOURSOMES"' in tpl and '"SINGLES"' in tpl)
cts = open("templates/contests.html", encoding="utf-8").read()
check("the Cup board opens ?match=<id> and keeps open cards open across its refresh",
      'data-lsc-match=' in cts and 'get("match")' in cts and "lscMatchOpened" in cts)

# Kerry 10/9: "Leaderboard view on Lone Star Cup weekend should not be showing
# standard leaderboards. It be showing the list of matches just like the member view"
check("a Cup round's group knows its session; the practice round and a plain event do not",
      se.cup_session_of_group(g1, db_path=tmp) == "sat-am" and se.cup_session_of_group(g_prac, db_path=tmp) is None
      and se.cup_session_of_group(g_plain, db_path=tmp) is None and se.cup_session_of_group(999999, db_path=tmp) is None)
check("the scorer's board page wires a Cup session to the Cup tab, on his session",
      'window.SOLO_CUP = {{ SOLO_CUP|tojson }}; window.lscSel = window.SOLO_CUP;' in cts
      and 'hash = window.SOLO_CUP ? "#tab=lsc" : "#tab=events"' in cts)

# Kerry 10/9: "For team games ... each team have a border around the players
# that are on the same team" (Cup sides in their colours; Cart Net carts)
sep = open("templates/score_entry.html", encoding="utf-8").read()
check("the scoring screen boxes each team's players",
      '<div class="se-stack">${teamWrap(rowsByKey)}</div>' in sep and "function teamGroups()" in sep
      and '["AUSTIN", "#BF5700"], ["SAN ANTONIO", "#4B6274"]' in sep and 'tg.unit === "cart"' in sep
      and ".se-teambox {" in sep)

# Kerry 10/9: "Reduce that text to the MATCH # | FORMAT" -- the weekend's numbers
rmx = se.round_matches(rid, db_path=tmp)
check("each Cup match carries its weekend number (1-28, as the board and sheets)",
      rmx.get(7, {}).get("match_no") == 1 and rmx.get(13, {}).get("match_no") == 2, rmx.get(7))
check("a Cup card's heading is MATCH # | FORMAT on every screen",
      "const cupEyebrow = () =>" in sep and '" | " + sx.title' in sep
      and "const eyebrow = () => cupEyebrow() ||" in sep and "const eyebrowGroup = () => cupEyebrow() ||" in sep)

# Kerry 10/9: the Cup's team score pinned under the header ABOVE the toggles,
# full width; the hole's Par / yds / SI inline with its number
check("the Cup team bar sits first in the pinned bar, above SCORING | LEADERBOARD",
      'nav.insertBefore(slot, nav.firstChild)' in sep and "#se-cupbar { margin: -8px -16px 8px;" in sep)
check("the hole details sit on the hole number's line",
      '<div class="se-hl"><h1 class="se-h1 big">Hole ${hole}</h1><div class="se-sub">' in sep
      and ".se-hole .se-hl { display: flex; align-items: baseline;" in sep)

# Kerry 10/9: the scorer's LEADERBOARD top matches SCORING: team score above
# the toggles, no second Cup banner, HOW IT WORKS at the right of the logo
check("the scorer's Cup board pins the team score in the toggle bar, above the toggles",
      "function lscSoloPinHead(box)" in cts and "lscSoloPinHead(box);" in cts
      and 'tgl.insertBefore(slot, tgl.firstChild)' in cts)
check("the second Cup banner is hidden and HOW IT WORKS sits in the logo header",
      "body.lsc-solo #section-lone-star-cup .lsc-event { display: none; }" in cts
      and 'b.id = "lsc-hdr-hiw"' in cts and "hdr.appendChild(b)" in cts)

# Kerry 10/9: "Simply colored names works. Do it" -- a Cup player's name in
# his team's colour on the scoring rows and the card tables
check("Cup player names carry the team colour (Austin orange, San Antonio slate)",
      'const TEAM_INK = {austin: "#BF5700", sa: "#4B6274"};' in sep
      and '<span class="nm"${inkStyle(s.cids)}>' in sep and "const c = teamInk(s.cids);" in sep)

# Kerry 10/9: "For team matches on SCORING just show stacked names as first
# initial and last names"
check("a pair on the scoring match strip stacks first initial + last, one partner per line",
      'class="se-mc-name pair' in sep and '(w[0][0] || "") + ". "' in sep)

# Kerry 10/9: "Make sure all scorecards are cleared and they all land on the
# starting holes"
check("an empty card opens on its starting hole; a cleared card drops holes queued before the clear",
      "const saved = empty ? null : store.get(K.hole, null);" in sep
      and "Date.parse(o.client_ts) <= cut" in sep and "(card.cleared_at || null) !== prevClr" in sep)

# Kerry 10/9: "The orange text up top should just have PRACTICE ROUND | DATE"
check("the Cup's practice-round card heads PRACTICE ROUND (| date on the landing)",
      'const practiceEyebrow = () => document.body.classList.contains("lsc") && !cupSession() ? "Practice Round" : null;' in sep
      and 'cupEyebrow() || practiceEyebrow() ||' in sep and '"Practice Round" + (card.round_date ? " | " + dt(card.round_date) : "")' in sep)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
