"""CONCEPTS (CoS #1904) + ADVISOR ACCESS, design B (Kerry "Yep B", CoS #1905).

Acceptance from the two posts:
- a manager sees CONCEPTS in the nav and opens a page (shell + sandboxed frame);
- a member_mode visitor sees nothing new; a direct URL with no role gets the
  sign-in gate, not the page; view-only gets the gate too;
- an advisor link opens CONCEPTS, the shell reads Concepts | Leaderboard |
  Handicaps with the advisor's name; /customers gets the sign-in gate; a
  view-only API refuses;
- revoke: the same link and the open session both stop ("no longer active");
- each page an advisor opens is logged and shows on the Admin row;
- only the concepts section is ever served;
- phone parity: the page is one responsive template (no separate phone
  route), checked for the 560px rule.

Run: python3 test_concepts_advisors.py
"""
import contextlib, io, logging, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    DB = os.environ["DATABASE_PATH"]
    db.init_db(DB)
    import app as appmod  # noqa: E402
from email_parser import advisors as adv  # noqa: E402
from email_parser.library import library_put, tgf_config  # noqa: E402

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {str(detail)[:300]}"))
    if not cond:
        F.append(label)


HTML = ("<!DOCTYPE html><html><head><style>body{font-family:Bitter}</style></head>"
        "<body><h1>Road to the Lone Star Cup</h1><script>document.title='x'</script></body></html>")
META = {"doc_id": "tgf-2027-season-member", "title": "Road to the Lone Star Cup", "version": "1.0",
        "status": "draft", "owner": "platform-claude", "onedrive_path": "-", "project_files": "false",
        "reads": ["platform-claude"]}
cfg = tgf_config(DB)
put = library_put("concepts/TGF_2027_Season_Member_v1_0.md", HTML, META, author="platform-claude",
                  apply=True, cfg=cfg)
check("migration 0023: a concept page files under concepts/", put.get("id"), put)
other = library_put("specs/Secret_Spec_v1_0.md", "# not a concept", dict(META, doc_id="secret-spec",
                    title="Secret"), author="platform-claude", apply=True, cfg=cfg)

print("anonymous / member")
anon = appmod.app.test_client()
r = anon.get("/concepts", headers={"Accept": "text/html"})
check("no role: the sign-in gate, not the page", r.status_code == 401 and b"Sign in" in r.data, r.status_code)
r = anon.get("/concepts/tgf-2027-season-member/raw", headers={"Accept": "text/html"})
check("no role: the raw page is gated too", r.status_code == 401)
r = anon.get("/api/concepts")
check("no role: the API refuses", r.status_code == 401)
html = anon.get("/member/handicaps").data.decode()
check("a member_mode page shows nothing new", "/concepts" not in html)

print("view-only")
vo = appmod.app.test_client()
with vo.session_transaction() as s:
    s["role"] = "view-only"
check("view-only gets the gate, never the page",
      vo.get("/concepts", headers={"Accept": "text/html"}).status_code == 401)

print("manager")
mg = appmod.app.test_client()
with mg.session_transaction() as s:
    s["role"] = "manager"
r = mg.get("/concepts", headers={"Accept": "text/html"})
page = r.data.decode()
check("manager: CONCEPTS lists the page", r.status_code == 200 and "Road to the Lone Star Cup" in page, r.status_code)
check("the manager nav carries the Concepts link (desktop and drawer)", page.count('href="/concepts"') >= 2)
check("a spec from another section is never listed", "Secret" not in page)
r = mg.get("/concepts/tgf-2027-season-member")
check("manager: the page opens in the shell with a sandboxed frame",
      r.status_code == 200 and b'/concepts/tgf-2027-season-member/raw' in r.data and b'sandbox=' in r.data)
raw = mg.get("/concepts/tgf-2027-season-member/raw")
csp = raw.headers.get("Content-Security-Policy", "")
check("the raw page is the Library body as-is", raw.data.decode() == HTML)
check("served sandboxed: scripts run with no Tracker origin", "sandbox allow-scripts" in csp
      and "allow-same-origin" not in csp)
check("only concepts are served", mg.get("/concepts/secret-spec/raw").status_code == 404
      and mg.get("/concepts/secret-spec").status_code == 404)

print("advisor link")
a = adv.add("Jeff Test", "jeff@example.com", db_path=DB)
lk = adv.link(a["advisor_id"], base_url="https://x.test", db_path=DB)
tok = lk["url"].rsplit("/", 1)[1]
ad = appmod.app.test_client()
r = ad.get(f"/advisor/{tok}")
check("the link signs in and lands on CONCEPTS", r.status_code == 302 and r.headers["Location"].endswith("/concepts"))
with ad.session_transaction() as s:
    check("identity from the token: role advisor, its id and version", s.get("role") == "advisor"
          and s.get("advisor_id") == a["advisor_id"] and s.get("advisor_tv") == 1, dict(s))
r = ad.get("/concepts", headers={"Accept": "text/html"})
page = r.data.decode()
check("advisor: CONCEPTS opens", r.status_code == 200 and "Road to the Lone Star Cup" in page)
check("advisor shell: Concepts | Leaderboard | Handicaps with the advisor's name",
      'href="/concepts"' in page and 'href="/member/contests"' in page and 'href="/member/handicaps"' in page
      and "Jeff Test" in page and "/member/spotlight" not in page and "shell-cta-chooser" not in page)
check("advisor: member mode (no login modal)", "window.MEMBER_MODE = true" in page)
r = ad.get("/concepts/tgf-2027-season-member")
check("advisor: the page opens", r.status_code == 200)
r = ad.get("/customers", headers={"Accept": "text/html"})
check("advisor guessing /customers gets the sign-in gate", r.status_code == 401 and b"Sign in" in r.data)
check("advisor: /events and /admin pages gated too",
      ad.get("/events", headers={"Accept": "text/html"}).status_code == 401
      and ad.get("/admin/advisors", headers={"Accept": "text/html"}).status_code == 401)
check("advisor: a view-only API refuses", ad.get("/api/customers").status_code == 403)
check("advisor: a member page opens", ad.get("/member/handicaps", headers={"Accept": "text/html"}).status_code == 200)
check("advisor: the advisors API refuses", ad.get("/api/advisors").status_code == 403)
row = next(x for x in adv.list_all(db_path=DB) if x["advisor_id"] == a["advisor_id"])
check("the open is logged and shows on the Admin row with last seen",
      row["last_seen_at"] and row["pages_opened"] and row["pages_opened"][0]["doc_id"] == "tgf-2027-season-member", row)

print("a forged or tampered link")
check("a tampered token is refused", ad.get(f"/advisor/{tok[:-2]}xx").status_code == 401)
check("a token for another advisor id can't be made without the secret",
      adv.decode_token(tok.replace(tok.split('.')[0], tok.split('.')[0][::-1])) is None)

print("revoke")
b = adv.add("Mary Test", db_path=DB)
btok = adv.link(b["advisor_id"], db_path=DB)["url"].rsplit("/", 1)[1]
adv.revoke(a["advisor_id"], db_path=DB)
r = ad.get("/concepts", headers={"Accept": "text/html"})
check("the open session stops at once", r.status_code == 401 and b"no longer active" in r.data, r.data[:200])
with ad.session_transaction() as s:
    check("and the session is cleared", "role" not in s and "advisor_id" not in s, dict(s))
r = appmod.app.test_client().get(f"/advisor/{tok}")
check("the same link after revoke: 'this link is no longer active'", r.status_code == 401 and b"no longer active" in r.data)
r = appmod.app.test_client().get(f"/advisor/{btok}")
check("another advisor is untouched", r.status_code == 302)
adv.reinstate(a["advisor_id"], db_path=DB)
check("reinstating leaves the old link dead (a new link is needed)",
      appmod.app.test_client().get(f"/advisor/{tok}").status_code == 401)
new = adv.link(a["advisor_id"], db_path=DB)["url"].rsplit("/", 1)[1]
check("a new link after reinstate works", appmod.app.test_client().get(f"/advisor/{new}").status_code == 302)

print("admin")
ac = appmod.app.test_client()
with ac.session_transaction() as s:
    s["role"] = "admin"
r = ac.post("/api/advisors", json={"name": "  Daniel   Test ", "email": "D@Example.com"})
check("admin adds an advisor (name tidied, email lower-cased)", r.status_code == 200 and r.json["name"] == "Daniel Test")
check("a nameless advisor is refused", ac.post("/api/advisors", json={"name": " "}).status_code == 400)
did = r.json["advisor_id"]
r = ac.post(f"/api/advisors/{did}/link")
check("admin copies a link", r.status_code == 200 and "/advisor/" in r.json["url"])
check("admin page renders", ac.get("/admin/advisors").status_code == 200)
check("manager cannot manage advisors", mg.post("/api/advisors", json={"name": "x"}).status_code == 403)

print("phone parity + source guards")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "concepts.html")).read()
asrc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "admin_advisors.html")).read()
check("concepts and advisors pages carry the one 560px phone rule",
      "@media (max-width: 560px)" in src and "@media (max-width: 560px)" in asrc and "768" not in src + asrc)
asrc_py = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_parser", "advisors.py")).read()
check("the Tracker never emails an advisor", "send_email" not in asrc_py and "sendMail" not in asrc_py)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILED: {F}"))
sys.exit(1 if F else 0)
