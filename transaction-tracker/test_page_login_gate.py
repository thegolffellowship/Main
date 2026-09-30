"""A signed-out visit to a PAGE asks for the PIN and comes back; the API
still answers JSON (Kerry 2026-09-28: the scorecards link opened in Safari,
outside the Tracker app, showed raw JSON).

Run: python3 test_page_login_gate.py
"""
import contextlib, io, logging, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["ADMIN_PIN"] = "4242"
os.environ.setdefault("SECRET_KEY", "test")
os.environ["DISABLE_SCHEDULER"] = "1"
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as appmod
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

c = appmod.app.test_client()
H = {"Accept": "text/html,application/xhtml+xml"}
for path in ("/events/1/scorecards", "/events/1/scorecards.pdf", "/events/1/starter-sheet",
             "/events/1/cart-signs"):
    r = c.get(path, headers=H)
    body = r.get_data(as_text=True)
    check(f"signed out, {path}: a sign-in page, not JSON",
          r.status_code == 401 and "Sign in" in body and "Not authenticated" not in body,
          (r.status_code, body[:80]))
r = c.get("/api/events/1/group-codes", headers=H)
check("the API still answers JSON 401", r.status_code == 401 and r.is_json, r.status_code)
r = c.get("/events/1/scorecards")
check("a non-browser GET (no HTML accept) still gets JSON", r.status_code == 401 and r.is_json)
r = c.post("/api/auth/login", json={"pin": "4242"})
check("PIN signs in", r.status_code == 200, r.get_data(as_text=True)[:80])
r = c.get("/events/1/scorecards", headers=H)
check("signed in, the page answers (404 for a missing event, not 401)", r.status_code in (200, 404),
      r.status_code)
print(f"\n{len(F)} failure(s)")
sys.exit(1 if F else 0)
