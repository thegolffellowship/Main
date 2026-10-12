"""Player photos (Kerry 2026-10-10: headshots and team duo shots on the Lone
Star Cup surfaces). Files beside the DB, no table; the public read is ids
and version stamps only; a missing photo is a 404 and the page keeps its
initials.

Run: python3 test_player_photos.py
"""
import base64, contextlib, io, json, logging, os, sys, tempfile
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
    for cid, fn, ln in ((62, "Bill", "Barstow"), (672, "David", "Wetz")):
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
check("each cup plaque carries its race and champion ids, and one function applies the photo to whichever is on screen",
      'data-race="players_cup" data-cids=' in src and 'document.querySelector(\'.tgf-champ-plaque[data-race]\')' in src
      and 'fcPhotoIdx[race + "-2026"]' in src)

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
      "sptHeadshot(d.customer_id)" in sp and 'w.insertAdjacentHTML("afterbegin", sptHeadshot(SPT_DATA.customer_id))' in sp)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
