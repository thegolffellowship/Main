"""EVENT PHOTOS (Kerry 2026-10-29, Event Ops #2460-J: "photos of champions
this Saturday, and possibly photos on regular event nights too ... super
simple").

- Add photo is manager/admin only (an anonymous or scorer upload is refused);
  the button renders on the scorer's page for a staff session only.
- A photo is a file beside the DB (event_photos/<event>/<id>.jpg + index.json),
  re-encoded to <= 1600 px; a bad image, an unknown event or customer is refused.
- The public list is PII-free (no uploader); the file route refuses traversal.
- Emails: nothing unless dial event_photos_in_email = on (default off).
- Spotlight: only on the explicit manager action, only for a tagged photo; it
  writes a 400 px square headshot through player_photos and keeps the old one.
- The nightly files backup carries event_photos/.
Run: python3 test_event_photos.py
"""
import contextlib, io, logging, os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "ui-test")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)
    import app as appmod
from email_parser import event_photos as ep        # noqa: E402
from email_parser import player_photos as pp       # noqa: E402
from email_parser import score_entry as se         # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

try:
    from PIL import Image
except Exception:
    Image = None


def jpeg(w=3000, h=2000):
    if Image is None:
        return b"\xff\xd8\xff" + b"0" * 1000
    b = io.BytesIO()
    Image.new("RGB", (w, h), (200, 120, 60)).save(b, "JPEG", quality=90)
    return b.getvalue()


c = sqlite3.connect(DB)
c.execute("INSERT INTO events (id, item_name, event_date, chapter) VALUES (900, 's9.31 Test', '2026-10-31', 'San Antonio')")
c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (42, 'Gus', 'Vasquez')")
c.commit()

print("== the store ==")
r = ep.save_photo(900, jpeg(), caption="Fall Champion", customer_id=42, by="admin")
check("saved", r.get("ok"), r)
pid = r["photo"]["id"]
f = ep.photo_file(900, pid)
check("a file beside the DB under event_photos/900/", f is not None and f.parent == ep.store_dir() / "900", f)
if Image is not None:
    im = Image.open(f)
    check("re-encoded to <= 1600 px", max(im.size) <= 1600, im.size)
check("a non-image is refused", ep.save_photo(900, b"hello").get("error"))
check("an unknown event is refused", ep.save_photo(999, jpeg(10, 10)).get("error"))
check("an unknown customer is refused", ep.save_photo(900, jpeg(10, 10), customer_id=7777).get("error"))
r2 = ep.save_photo(900, jpeg(800, 600), caption="The field")
rows = ep.event_photos(900)
check("the reader lists both, oldest first", [x["id"] for x in rows] == [pid, r2["photo"]["id"]], rows)
check("public rows carry no uploader", all("by" not in x for x in rows))
check("traversal refused", ep.photo_file(900, "../../t") is None and ep.photo_file("9/../1", pid) is None)

print("== emails: dial off by default ==")
check("email card empty while off", ep.email_card_html(900, "https://x") == "")
check("recap facts empty while off", ep.recap_facts(900) == [])
db.set_app_setting("event_photos_in_email", "on")
html = ep.email_card_html(900, "https://x")
check("on: the PHOTOS card with absolute image URLs", "PHOTOS" in html and f"https://x/member/event-photo/900/{pid}.jpg" in html)
check("on: recap facts are captions + tags", ep.recap_facts(900)[0] == {"caption": "Fall Champion", "customer_id": 42})
from email_parser import results_email as rem      # noqa: E402
check("results email wires the card", "PHOTOS" in rem._photos({"event": {"id": 900}, "db_path": None}))
db.set_app_setting("event_photos_in_email", "off")
check("results email: nothing when off", rem._photos({"event": {"id": 900}, "db_path": None}) == "")

print("== Spotlight: explicit, tagged only ==")
check("an untagged photo is refused", ep.promote_to_spotlight(900, r2["photo"]["id"]).get("error"))
old = pp.photo_dir() / "h-42.jpg"
old.parent.mkdir(parents=True, exist_ok=True)
old.write_bytes(jpeg(400, 400))
res = ep.promote_to_spotlight(900, pid, by="admin")
if Image is not None:
    check("promoted", res.get("ok") and res.get("customer_id") == 42, res)
    check("the earlier headshot is kept", res.get("previous_kept") and (pp.photo_dir() / "replaced" / res["previous_kept"]).is_file())
    check("a 400 px square headshot", Image.open(pp.photo_dir() / "h-42.jpg").size == (400, 400))
    check("marked promoted", any(x["promoted"] for x in ep.event_photos(900)))
check("save_photo never promotes by itself",
      "promote_to_spotlight" not in open(ep.__file__).read().split("def save_photo")[1].split("def public_row")[0])

print("== routes ==")
with appmod.app.test_client() as tc:
    r = tc.post("/api/event-photos/upload", data={"event_id": "900", "photo": (io.BytesIO(jpeg(50, 50)), "p.jpg")},
                content_type="multipart/form-data")
    check("anonymous upload refused", r.status_code == 401, r.status_code)
    r = tc.post(f"/api/event-photos/900/{pid}/spotlight")
    check("anonymous Spotlight refused", r.status_code == 401, r.status_code)
    j = tc.get("/api/event-photos/900").get_json()
    check("public list 200, no uploader", len(j["photos"]) == 2 and all("by" not in x for x in j["photos"]))
    check("the file is public", tc.get(f"/member/event-photo/900/{pid}.jpg").status_code == 200)
    check("a missing photo is 404", tc.get("/member/event-photo/900/p20260101000000-abcdef.jpg").status_code == 404)
    with tc.session_transaction() as s:
        s["role"] = "manager"
        s["chapter"] = "San Antonio"
    r = tc.post("/api/event-photos/upload", data={"event_id": "900", "caption": "x", "customer_id": "42",
                                                  "photo": (io.BytesIO(jpeg(50, 50)), "p.jpg")},
                content_type="multipart/form-data")
    check("manager upload works", r.status_code == 200 and r.get_json().get("ok"), r.get_data()[:200])
    j = tc.get("/api/event-photos/900?staff=1").get_json()
    check("staff list names the tagged player and uploader",
          any(x.get("player") == "Gus Vasquez" and x.get("by") == "manager:San Antonio" for x in j["photos"]), j)
    db.set_app_setting("event_photos_capture", "off")
    r = tc.post("/api/event-photos/upload", data={"event_id": "900", "photo": (io.BytesIO(jpeg(50, 50)), "p.jpg")},
                content_type="multipart/form-data")
    check("dial off: upload refused", r.status_code == 403, r.status_code)
    db.set_app_setting("event_photos_capture", "on")

print("== the button on the scorer's page: staff only ==")
rid = se.create_round(900, 9, label="t", course_holes=[{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 10)])["round_id"]
gid = se.upsert_group(rid, 1, players=[{"customer_id": 42, "display_name": "Gus", "seat": 1}])["group_id"]
db.set_app_setting("score_entry_live", "1")
db.set_app_setting("score_entry_events", "[900]")
TOK = se.make_group_token(gid)
with appmod.app.test_client() as tc:
    check("a player: no Add photo", 'id="se-evp"' not in tc.get(f"/member/score?t={TOK}").get_data(as_text=True))
    with tc.session_transaction() as s:
        s["role"] = "admin"
    check("admin: Add photo", 'id="se-evp"' in tc.get(f"/member/score?t={TOK}").get_data(as_text=True))
    h = tc.get("/events/900/live-scoring").get_data(as_text=True)
    check("manager Live Scoring page: Photos panel", 'id="evp"' in h and "manage: true" in h)

from email_parser.backups import FILE_STORES       # noqa: E402
check("files backup carries event_photos/", "event_photos" in FILE_STORES)

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
