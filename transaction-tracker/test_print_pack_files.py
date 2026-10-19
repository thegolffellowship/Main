"""Print files: the bound pack cut into one PDF per report (Kerry 2026-10-09:
"Can you have the practice round reports sent to me in separate PDF files
right now? I need to send to course for printing").

Run: python3 test_print_pack_files.py
"""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pypdf import PdfWriter, PdfReader                       # noqa: E402
from email_parser import print_pack as pp                    # noqa: E402
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


w = PdfWriter()
sizes = [(200, 300), (300, 200), (300, 200), (300, 200), (300, 200), (400, 400), (400, 400)]
for wd, ht in sizes:
    w.add_blank_page(width=wd, height=ht)
buf = io.BytesIO(); w.write(buf)
built = {"pdf": buf.getvalue(),
         "parts": [{"slug": "starter-sheet", "pages": 1}, {"slug": "cart-signs", "pages": 4},
                   {"slug": "scorecards", "pages": 2}],
         "event": {"id": 3330, "item_name": "LSC PRACTICE ROUND | The Hideout", "event_date": "2026-10-09"}}
files = pp.split_print_pack(built)
names = [f for f, _ in files]
check("one file per report, in print order",
      len(files) == 3 and names[0].endswith("-StarterSheet.pdf") and names[1].endswith("-CartSigns.pdf")
      and names[2].endswith("-Scorecards.pdf"), names)
pages = [len(PdfReader(io.BytesIO(b)).pages) for _, b in files]
check("each file holds exactly its report's pages", pages == [1, 4, 2], pages)
first = PdfReader(io.BytesIO(files[2][1])).pages[0]
check("the pages are the report's own (scorecards are the 400x400 pages)",
      round(float(first.mediabox.width)) == 400, first.mediabox)
built["parts"][1]["pages"] = 3
try:
    pp.split_print_pack(built); check("a page-count mismatch is refused", False)
except ValueError:
    check("a page-count mismatch is refused", True)
print("course files and the rules sheet (Kerry 10/13)")
w = PdfWriter()
for _ in range(9):
    w.add_blank_page(width=300, height=300)
buf = io.BytesIO(); w.write(buf)
full = {"pdf": buf.getvalue(), "event": built["event"],
        "parts": [{"slug": s_, "pages": 1} for s_ in
                  ("starter-sheet", "cart-signs", "scorecards", "games-payouts",
                   "divisions-flights", "proximity-markers")] + [{"slug": "rules-of-play", "pages": 3}]}
cf = [f for f, _ in pp.split_print_pack(full, only=pp.COURSE_FILE_PARTS)]
check("the course gets Starter Sheet, Cart Signs, Scorecards, Proximity, Rules of Play only",
      [f.rsplit("-", 1)[1] for f in cf] == ["StarterSheet.pdf", "CartSigns.pdf", "Scorecards.pdf",
                                            "Proximity.pdf", "RulesOfPlay.pdf"], cf)
rp = [b for f, b in pp.split_print_pack(full, only=pp.COURSE_FILE_PARTS) if f.endswith("RulesOfPlay.pdf")][0]
check("skipped reports still advance the page count (rules = its own 3 pages)",
      len(PdfReader(io.BytesIO(rp)).pages) == 3)
check("the full split still has all seven reports", len(pp.split_print_pack(full)) == 7)
HERE = os.path.dirname(os.path.abspath(__file__))
rules = pp._rules_sheet_bytes(os.path.join(HERE, "static"))
check("the Rules of Play sheet ships in static/print", rules and rules[:4] == b"%PDF")
pdf2, parts2 = pp._append_rules_sheet(files[0][1], [{"slug": "starter-sheet", "pages": 1}], rules)
check("the rules sheet binds onto the end of the pack",
      parts2[-1] == {"slug": "rules-of-play", "pages": len(PdfReader(io.BytesIO(rules)).pages)}
      and len(PdfReader(io.BytesIO(pdf2)).pages) == 1 + parts2[-1]["pages"], parts2)
check("no rules file: the pack is unchanged", pp._append_rules_sheet(b"x", [], None) == (b"x", []))
pk = open(os.path.join(HERE, "email_parser", "print_pack.py"), encoding="utf-8").read()
check("the course email defaults to the course's reports",
      "split_print_pack(built, only=COURSE_FILE_PARTS)" in pk)
ev_src = open(os.path.join(HERE, "templates", "events.html"), encoding="utf-8").read()
check("Course Files button + route", "sendCourseFiles(" in ev_src and
      '"/api/events/<int:event_id>/course-files/send"' in open(os.path.join(HERE, "app.py"), encoding="utf-8").read())

print("straight to the course contact (Kerry 10/13)")
import tempfile                                               # noqa: E402
from email_parser import database as db                       # noqa: E402
TMP = tempfile.mkdtemp(); DB = os.path.join(TMP, "t.db")
db.init_db(DB)
with db._connect(DB) as c:
    c.execute("INSERT INTO courses (name) VALUES ('The Quarry Golf Club')")
    qid = c.execute("SELECT course_id FROM courses WHERE name='The Quarry Golf Club'").fetchone()[0]
    c.commit()
check("no contact: nothing to send to", pp.course_contact_for_event({"id": 1, "course_id": qid}, db_path=DB) is None)
from email_parser import course_staff as cs                   # noqa: E402
cs.save_staff(qid, name="Pro Shop", email="proshop@quarry.com", role="tgf_contact", is_primary=True, apply=True, db_path=DB)
cs.save_staff(qid, name="Event Desk", email="events@quarry.com", role="tgf_contact", apply=True, db_path=DB)
check("the event resolves its course's primary TGF contact (course_staff, v2.561.0)",
      pp.course_contact_for_event({"id": 1, "course_id": qid}, db_path=DB) == "proshop@quarry.com")
_sent = {}
_orig = pp.send_print_pack_files
pp.send_print_pack_files = lambda b, **k: _sent.update(k) or {"sent": True, "to": k.get("to_address")}
os.environ.setdefault("PRINT_PACK_EMAIL_TO", "kerry@thegolffellowship.com")
res = pp.send_course_files({"event": {"id": 1, "course_id": qid, "chapter": "San Antonio"}}, db_path=DB)
check("To the primary, the other TGF contact and Kerry on CC, course wording",
      _sent.get("to_address") == "proshop@quarry.com"
      and "events@quarry.com" in (_sent.get("cc_address") or "")
      and "kerry@thegolffellowship.com" in (_sent.get("cc_address") or "") and _sent.get("for_course") is True, _sent)
_sent.clear()
res = pp.send_course_files({"event": {"id": 2, "course_id": None, "course": "Nowhere"}}, db_path=DB)
# Kerry 10/19: "If there is not a course contact - send to manager."
check("no contact: the files go to the manager (our pack recipients) instead",
      res.get("no_contact") and res.get("to_manager")
      and _sent.get("to_address") == "kerry@thegolffellowship.com", (res, _sent))
_sent.clear()
_env = os.environ.pop("PRINT_PACK_EMAIL_TO", None)
_env2 = {k: os.environ.pop(k, None) for k in ("DAILY_REPORT_TO", "EMAIL_ADDRESS")}
res = pp.send_course_files({"event": {"id": 3, "course_id": None, "course": "Nowhere"}}, db_path=DB)
check("no contact and no manager address: refused, nothing sent", res.get("no_contact") and not _sent, res)
if _env:
    os.environ["PRINT_PACK_EMAIL_TO"] = _env
for k, v in _env2.items():
    if v:
        os.environ[k] = v
pp.send_print_pack_files = _orig
check("the interim course_print_contacts setting is retired", "course_print_contacts(" not in pk
      and "def set_course_print_contact" not in pk)

print("scorecards one card per GROUP unless directed (Kerry 10/13)")
check("default: per group", pp.scorecard_grouping(3318, db_path=DB) == "team")
db.set_app_setting("print_pack_scorecard_grouping", "3318", db_path=DB)
check("per cart only for a named event", pp.scorecard_grouping(3318, db_path=DB) == "cart"
      and pp.scorecard_grouping(3307, db_path=DB) == "team")
db.set_app_setting("print_pack_scorecard_grouping", "", db_path=DB)
check("the pack no longer reads the net game's unit for the grouping",
      '"cart" if unit == "cart" else "team"' not in pk and "scorecard_grouping(int(event_id)" in pk)

src = open("mcp_server.py", encoding="utf-8").read()
check("the bridge takes |files and builds with the scorecards forced in",
      'parts[1].lower() == "files"' in src and "force_scorecards=True" in src)

app_src = open("app.py", encoding="utf-8").read()
check("the Cup prints its own per-session files (starter sheet, 3e cart signs, QR scorecards)",
      'parts[1].lower().split("=")[0] == "cup-files"' in src and "def build_cup_print_files(" in app_src
      and '"lsc_starter_sheet.html"' in app_src and 'cup_cart_signs_data(int(event_id), session_id=sid)' in app_src
      and 'build_scorecards(int(event_id), "3up", "team", qr="on", session=sid)' in app_src)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
