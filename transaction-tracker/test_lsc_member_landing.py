"""The Lone Star Cup is the member landing through Sunday evening (Kerry
2026-10-07, CoS #1351 D1). Dial lsc_member_landing_until (Central)."""
import os, sys, tempfile, logging, contextlib, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()):
    import app as appmod
    from email_parser import database as db
    db.init_db(os.environ["DATABASE_PATH"])
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)
c = appmod.app.test_client()
db.set_app_setting("lsc_member_landing_until", "2099-01-01 00:00")
r = c.get("/member")
check("during the Cup /member lands on the Lone Star Cup", r.status_code == 302 and r.headers["Location"].endswith("/member/lonestarcup"), r.headers.get("Location"))
check("/member/contests opens on the Cup tab", b"window.LSC_LANDING = true" in c.get("/member/contests").data)
db.set_app_setting("lsc_member_landing_until", "2020-01-01 00:00")
r = c.get("/member")
check("after Sunday evening /member is Spotlight again", r.headers["Location"].endswith("/member/spotlight"), r.headers.get("Location"))
check("/member/contests back to its default tab", b"window.LSC_LANDING = true" not in c.get("/member/contests").data)
print("ALL PASS" if not F else f"{len(F)} FAILED"); sys.exit(1 if F else 0)
