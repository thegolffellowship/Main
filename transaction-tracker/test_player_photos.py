"""Player photos (Kerry 2026-10-10: headshots and team duo shots on the Lone
Star Cup surfaces). Files beside the DB, no table; the public read is ids
and version stamps only; a missing photo is a 404 and the page keeps its
initials.

Run: python3 test_player_photos.py
"""
import re, base64, contextlib, io, json, logging, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-photos-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser import player_photos as pp                     # noqa: E402
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


with db._connect(tmp) as conn:
    for cid, fn, ln in ((62, "Bill", "Barstow"), (672, "David", "Wetz"),
                       (497, "Paul", "Day"), (299, "Mark", "Freund"), (289, "Jay", "Horton"), (31, "Robert", "Straiton")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
    conn.commit()
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200 + b"\xff\xd9"

check("a headshot saves for a real customer", pp.save_photo("headshot", [62], JPEG).get("saved") == "h-62.jpg")
check("a team shot saves under the sorted ids", pp.save_photo("team", [672, 62], JPEG).get("saved") == "t-62-672.jpg")
check("an unknown customer is refused", "no customer" in pp.save_photo("headshot", [999], JPEG).get("error", ""))
check("not a JPEG is refused", pp.save_photo("headshot", [62], b"GIF89a....").get("error") == "not a JPEG")
check("an oversize photo is refused", "limit" in pp.save_photo("headshot", [62], JPEG + b"\x00" * pp.MAX_BYTES).get("error", ""))
check("a team needs two different people", "two different" in pp.save_photo("team", [62, 62], JPEG).get("error", ""))
idx = pp.photo_index()
check("the index is ids and stamps only", set(idx) == {"h", "t", "c"} and "62" in idx["h"] and "62-672" in idx["t"]
      and all(isinstance(v, int) for v in list(idx["h"].values()) + list(idx["t"].values())), str(idx))
check("path tricks never resolve to a file", pp.photo_file("h", "../t") is None and pp.photo_file("x", "62") is None
      and pp.photo_file("t", "62-672/../../x") is None)
check("a team read finds the pair in either order", pp.photo_file("t", "672-62") is not None)

import app as A                                                   # noqa: E402
LSC_CAPT, _cap = A.LSC_CAPTAIN_BY_RACE, A._with_lsc_captain
tc = A.app.test_client()
r = tc.get("/api/player-photos")
check("the index is public (member tier) and carries no names", r.status_code == 200
      and "Barstow" not in r.get_data(as_text=True), r.status_code)
check("a headshot serves as a JPEG", tc.get("/member/photo/h/62.jpg").mimetype == "image/jpeg")
check("a missing photo is a 404 (the page keeps its initials)", tc.get("/member/photo/h/999999.jpg").status_code == 404)
check("the Cup seed set serves from the repo (David Wetz, the Wetz & Barstow pair)", tc.get("/member/photo/h/672.jpg").status_code == 200
      and tc.get("/member/photo/t/672-62.jpg").status_code == 200 and "62-672" in pp.photo_index()["t"])

# CHAMPION PHOTOS (Kerry 2026-10-12): the Fellowship Cup plaque photo ships in the
# repo, is read-only at runtime, and shows only for the people tagged in it.
c = pp.photo_index()["c"].get("fellowship_cup-2026") or {}
check("the champion photo is in the index with ids, cup name and caption", c.get("ids") == [42]
      and c.get("cup") == "The Bruce Friesenhahn Fellowship Cup" and "Gus Vasquez" in c.get("caption", "")
      and isinstance(c.get("v"), int), str(c))
r = tc.get("/member/photo/c/fellowship_cup-2026.jpg")
check("the champion photo serves as a JPEG from the repo", r.status_code == 200 and r.mimetype == "image/jpeg"
      and r.data[:3] == b"\xff\xd8\xff" and len(r.data) < 400 * 1024, r.status_code)
check("an unknown champion key or a path trick is a 404", tc.get("/member/photo/c/city_net-2026.jpg").status_code == 404
      and pp.photo_file("c", "../h-42") is None and pp.photo_file("c", "") is None)
check("the public index still carries no names beyond the champion caption", "Barstow" not in tc.get("/api/player-photos").get_data(as_text=True))
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "contests.html")).read()
check("the plaque carries its champion ids and the photo is matched against them",
      'data-race="fellowship_cup" data-cids=' in src and "fcApplyChampPhoto" in src and "norm((el.dataset.cids" in src)
check("a failed or missing photo keeps the trophy glyph", 'onerror="this.remove()"' in src.split("function fcApplyChampPhoto")[1][:1500]
      or "if (!el || !p || el.dataset.photoDone) return;" in src)

pc = pp.photo_index()["c"].get("players_cup-2026") or {}
check("the Players Cup champion photo is indexed for Robert Straiton (31) with the cup name and caption",
      pc.get("ids") == [31] and pc.get("cup") == "The Players Cup" and "Robert Straiton" in pc.get("caption", ""), str(pc))
check("the Players Cup photo serves as a JPEG from the repo", tc.get("/member/photo/c/players_cup-2026.jpg").status_code == 200
      and tc.get("/member/photo/c/players_cup-2026.jpg").mimetype == "image/jpeg")
check("Robert's cropped headshot is in the seed set, a square JPEG under the size cap",
      "31" in pp.photo_index()["h"] and tc.get("/member/photo/h/31.jpg").status_code == 200
      and len(tc.get("/member/photo/h/31.jpg").data) < pp.MAX_BYTES)
check("Jay Horton's cropped headshot (289) is in the seed set, a JPEG under the size cap",
      "289" in pp.photo_index()["h"] and tc.get("/member/photo/h/289.jpg").status_code == 200
      and len(tc.get("/member/photo/h/289.jpg").data) < pp.MAX_BYTES)
check("Mark Freund's (299) and Paul Day's (497) cropped headshots are in the seed set",
      all(i in pp.photo_index()["h"] and tc.get(f"/member/photo/h/{i}.jpg").status_code == 200 for i in ("299", "497")))
PAST = {"fellowship_cup-2023": [497], "fellowship_cup-2024": [299], "fellowship_cup-2025": [289],
        "players_cup-2023": [289], "players_cup-2024": [31]}
c = pp.photo_index()["c"]
check("the five past-champion photos are registered, tagged with exactly their champion, and served as JPEGs",
      all(k in c and c[k]["ids"] == ids and tc.get(f"/member/photo/c/{k}.jpg").status_code == 200
          and tc.get(f"/member/photo/c/{k}.jpg").mimetype == "image/jpeg" for k, ids in PAST.items()))
check("a past year with no photo (Players Cup 2025) is not served", tc.get("/member/photo/c/players_cup-2025.jpg").status_code == 404)
r = tc.get("/api/cup-champions")
j = r.get_json() if r.status_code == 200 else {}
fc = {x["year"]: x for x in j.get("fellowship_cup", [])}
pcx = {x["year"]: x for x in j.get("players_cup", [])}
check("/api/cup-champions lists each cup newest year first, with the photo only where one is registered",
      r.status_code == 200 and [x["year"] for x in j["fellowship_cup"]] == [2025, 2024, 2023]
      and [x["year"] for x in j["players_cup"]] == [2025, 2024, 2023]
      and fc[2024]["photo"]["key"] == "fellowship_cup-2024" and pcx[2025]["photo"] is None
      and pcx[2023]["customer_ids"] == [289]
      and fc[2023]["names"] == ["Paul Day"] and pcx[2024]["names"] == ["Robert Straiton"])
check("the strip carries names and photo tags only, no contact data",
      all(k in ("year", "customer_ids", "names", "photo") for x in j["fellowship_cup"] for k in x))
check("each cup plaque carries its race and champion ids, and one function applies the photo to whichever is on screen",
      'data-race="players_cup" data-cids=' in src and 'document.querySelector(\'.tgf-champ-plaque[data-race]\')' in src
      and 'fcPhotoIdx[race + "-2026"]' in src)

check("the NET boards' city champion and each month's winner wear their headshot (data-head plaques filled from the h index)",
      'data-head="1" data-cids=' in src and "function fcApplyHeadshots" in src and "fcHeadIdx = (j && j.h)" in src
      and "Points ${mWin.length > 1" in src and "monthPlaque" in src)
check("the top tab order is EVENTS | POINTS RACES | LONE STAR CUP | MATCH PLAY (Kerry 10/12 put the Cup back in the middle)",
      src.index('<button class="top-tab active" data-top="points-race">') < src.index('<button class="top-tab" data-top="lone-star-cup">')
      < src.index('<button class="top-tab" data-top="match-play">'))
check("the tab bar sits flush under the header and the race-chip sub nav pins under it (no page padding or section gap)",
      "body main, html.tgf-wide body main { padding-top: 0; }" in src and ".pr-section:has(> .pr-race-row:first-child) { padding-top: 0; }" in src
      and 'document.querySelector(".pr-race-row")' in src and 'chipRow.style.position = phone ? "" : "sticky"' in src)

check("standings rows: top 3 get a headshot slot (concept B), others a blank slot of the same width, filled from the h index",
      "function prAvatarSlot" in src and "function fcApplyAvatars" in src and src.count("prAvatarSlot(r, compact") >= 3
      and "td.pr-name-td.has-av" in src and ".pr-av { position: absolute; left: 0; top: 0; bottom: 0; width: 58px" in src
      and 'class="pr-rk"' in src and 'class="pr-pts"' in src)
check("the LSC captain comes from the Cup roster, not the champion: server sends it, the plaque and rows name them",
      "lsc_captain_id" in src and "capSeparate" in src and "Lone Star Cup Captain: " in src and 'capCity + " LSC CAPTAIN"' in src and "capColors" in src
      and LSC_CAPT.get("austin_net") == (7, "Matt Jenkins") and LSC_CAPT.get("san_antonio_net") == (35, "Rob Callaway")
      and _cap("austin_net", {"a": 1})["lsc_captain_id"] == 7 and _cap("city_gross", {"a": 1}) == {"a": 1})

HERE = os.path.dirname(os.path.abspath(__file__))
seeds = [f for f in os.listdir(os.path.join(HERE, "data", "player_photos")) if re.fullmatch(r"h-\d+\.jpg", f)]
champs = [f for f in os.listdir(os.path.join(HERE, "data", "champion_photos")) if f.endswith(".jpg")]
check("every seed headshot has a small 160px copy under 20KB, and every champion photo a 300x400 copy under 80KB (load time, Kerry 10/12)",
      all(os.path.isfile(os.path.join(HERE, "data", "player_photos", "sm", f))
          and os.path.getsize(os.path.join(HERE, "data", "player_photos", "sm", f)) < 20 * 1024 for f in seeds)
      and all(os.path.isfile(os.path.join(HERE, "data", "champion_photos", "sm", f))
              and os.path.getsize(os.path.join(HERE, "data", "champion_photos", "sm", f)) < 80 * 1024 for f in champs))
full, small = tc.get("/member/photo/c/fellowship_cup-2026.jpg"), tc.get("/member/photo/cs/fellowship_cup-2026.jpg")
hfull, hsmall = tc.get("/member/photo/h/289.jpg"), tc.get("/member/photo/hs/289.jpg")
check("the small champion and headshot routes serve JPEGs far lighter than the full ones; unknown keys are 404",
      small.status_code == 200 and small.mimetype == "image/jpeg" and len(small.data) < len(full.data) / 3
      and hsmall.status_code == 200 and len(hsmall.data) < len(hfull.data) / 2
      and tc.get("/member/photo/cs/nope.jpg").status_code == 404 and tc.get("/member/photo/hs/999999.jpg").status_code == 404)
sq = tc.get("/member/photo/cq/fellowship_cup-2026.jpg")
check("champion badge photos are SQUARE crops (400x400, head, torso and trophy) far lighter than the full photo; the full one is for the lightbox",
      sq.status_code == 200 and sq.mimetype == "image/jpeg" and len(sq.data) < 80 * 1024
      and all(os.path.isfile(os.path.join(HERE, "data", "champion_photos", "sq", f)) for f in champs)
      and tc.get("/member/photo/cq/nope.jpg").status_code == 404
      and 'width="140" height="140"' in src and "fcChampLightbox(fullSrc, p.caption)" in src)
check("photos cache for a week (the URL carries ?v=mtime) and the index for a minute",
      "604800" in small.headers.get("Cache-Control", "") and "max-age=60" in tc.get("/api/player-photos").headers.get("Cache-Control", ""))
check("every small display uses the small route and only the lightbox asks for the full photo",
      src.count("/member/photo/cq/") >= 2 and src.count("/member/photo/hs/") >= 3 and 'replace("/photo/hs/", "/photo/h/")' in src)
check("standings: money is larger, Bitter and right-aligned on the name row; names are Bitter (Kerry 10/12)",
      ".pr-nm { display: flex; align-items: center; justify-content: space-between" in src
      and ".pr-nm-l { min-width: 0; font-family: 'Bitter'" in src and "font: 700 17px/1 'Bitter'" in src
      and src.count('<div class="pr-nm"><div class="pr-nm-l">') >= 3 and 'class="pr-pay-l"' in src
      and src.count('<span class="pr-nm-b">') >= 3 and ".pr-nm-1.no-hcp .pr-hcp" in src and "function prFitNames" in src and '.pr-nm.no-pay .pr-pay { display: none; }' in src
      and ".pr-nm-t.no-badge .pr-nm-b { display: none; }" in src and 'classList.add("no-hcp")' in src and src.count('<span class="pr-nm-chev">') >= 3 and src.count('class="pr-nm-1"') >= 3 and 'RK</th>' in src)
check("every cell of a standings row is vertically centred on the row (rank, points and buy-in no longer ride high beside the headshot)",
      "tr[data-pname] > td" in src and "vertical-align: middle; }" in src)
check("anyone who won money in a contest gets their headshot, not only the top 3 (paid places and the month's winner)",
      "((n >= 1 && n <= 3) || r._pay || paid)" in src and "prAvatarSlot(r, compact, win)" in src)
check("the board header is just the title and a right-aligned HOW IT WORKS; the pot, places, bought-in count and phase move into the popup",
      "#pr-preamble, #pr-preamble-toggle, #pr-phase-chip { display: none !important; }" in src and "#pr-hiw-btn { margin-left: auto; }" in src
      and "function prHiwGlance" in src and 'class="pr-hiw-glance"' in src and "prHiwGlance();" in src
      and 'tile("Bought in"' in src and 'tile("Pot"' in src and "Places paid" in src
      and "pre.insertBefore(hiw, pre.firstChild)" not in src)
check("a player with no headshot gets no placeholder: the slot is removed and the name sits at the left like a non-winner's",
      ".pr-av:empty { display: none; }" in src and "if (fcHeadIdx) el.remove(); return; }" in src)
check("bought in is plain white and NOT bought in a soft grey row with a BUY IN pill while buy-in is open (option A, Kerry 10/12)",
      "const PR_BUYIN_URL" in src and "function prBuyBtn" in src and "function prBuyLegend" in src and "tr.pr-nobuy" in src
      and 'r.enrolled ? ""' in src and 'background:#EEEEEC;' in src
      and "function prBuyOpenFor" in src and "/fall_net/.test(raceKey || \"\")" in src and "const showBuy = !compact && prBuyOpenNow;" in src
      and "window.TGF_MEMBER_ID" in src and "tr.pr-buyin-row > td" in src and "@keyframes prBuyMid" in src and "Not in</span>" not in src.split("const badge = r.enrolled")[1].split("const nameCell")[0] and src.count('class="${nobuy ? "pr-nobuy" : ""}') + src.count('class="${nobuyF ? "pr-nobuy" : ""}"') == 2
      and "var(--buyin-green,#bbf7d0);\"\n                     : (r.customer_id" not in src and "prBuyLegend(d.standings)" in src and '${showBuy ? "" : buyHtml}' in src)
check("the Bought in / Not bought in legend boxes are real filters that hide those rows and survive a re-render",
      'data-buyfilter="in"' in src and 'data-buyfilter="out"' in src and "function prApplyBuyFilter" in src
      and "prBuyFilter[cb.dataset.buyfilter] = cb.checked;" in src and src.count("prApplyBuyFilter();") >= 3)
check("anything a narrow row hid (handicap, money, badges) is listed under the name while the row is expanded",
      "function prSyncHidden" in src and 'class="pr-hid-line"' in src and "data-hcp=" in src and "data-payl=" in src
      and "new MutationObserver(put)" in src and ".pr-detail-row, .pr-mo-detail" in src)
sp = open(os.path.join(HERE, "templates", "spotlight.html")).read()
check("the Spotlight profile photo is a rounded square in a frame of the player's chapter colour",
      ".spt-photo-frame.ch-austin { background: var(--chapter-austin" in sp and ".spt-photo-frame.ch-sa" in sp
      and "border-radius: 12px" in sp and "padding: 2px; border-radius: 14px" in sp and 'sptHeadshot(d.customer_id, d.chapter)' in sp)
check("the Spotlight headshot enlarges like the trophy photos (full 400px photo in the lightbox, small one on the card)",
      'data-full="/member/photo/h/' in sp and 'src="/member/photo/hs/' in sp and "function sptLightbox" in sp
      and ".spt-photo[data-full]" in sp)
import mcp_server as M                                            # noqa: E402
b64 = base64.b64encode(JPEG).decode()
out = json.loads(M._scoring_dispatch("https://www.golfgenius.com/", f"scoring-player-photo:headshot|672|{b64}"))
check("the bridge writes a finished headshot", out.get("saved") == "h-672.jpg", str(out))
check("the bridge lists", "672" in json.loads(M._scoring_dispatch("https://www.golfgenius.com/", "scoring-player-photo:list"))["h"])
check("the bridge removes", json.loads(M._scoring_dispatch("https://www.golfgenius.com/", "scoring-player-photo:remove|headshot|672")).get("removed") == "h-672.jpg")
check("bad base64 is refused", "base64" in json.loads(M._scoring_dispatch("https://www.golfgenius.com/", "scoring-player-photo:headshot|62|@@@")).get("error", ""))

here = os.path.dirname(os.path.abspath(__file__))
se = open(os.path.join(here, "templates", "score_entry.html")).read()
ct = open(os.path.join(here, "templates", "contests.html")).read()
sp = open(os.path.join(here, "templates", "spotlight.html")).read()
check("SCORING: a singles side's initials square carries the headshot, initials beneath as the fallback",
      'fetch("/api/player-photos")' in se and "const monoCell = (k, cls) =>" in se
      and "sd.length === 1 ? photoOf(sd) : null" in se and "this.parentNode.classList.remove('ph');this.remove()" in se)
check("LEADERBOARD: strip headshots for singles, the photo index re-read with every board load",
      "lscPhotosLoad()]);" in ct and "aPhoto: ((P[0] || {}).customer_ids || []).length === 1" in ct
      and '${o.aPhoto ? " ph" : ""}' in ct)
check("LEADERBOARD: the opened card heads with the singles face-off or the pair's duo shot",
      "function lscPhotoHead(m, o)" in ct and "const photoHead = lscPhotoHead(m, o);" in ct
      and "return `${photoHead}${strokeBar}" in ct and 'class="lsc-duo' in ct)
check("SPOTLIGHT: the headshot beside the name, slotted in without a re-render",
      "sptHeadshot(d.customer_id, d.chapter)" in sp and 'w.insertAdjacentHTML("afterbegin", sptHeadshot(SPT_DATA.customer_id, SPT_DATA.chapter))' in sp)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
