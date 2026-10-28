"""The Claude connector needs a person to approve it with the ADMIN PIN
(Kerry 10/23, security finding: authorize used to auto-approve anyone who
asked). Run: python3 test_mcp_auth_pin.py"""
import os, sys, urllib.parse
os.environ.update(MCP_CLIENT_ID="cid123", MCP_CLIENT_SECRET="sec456", ADMIN_PIN="9911")
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
import mcp_auth as ma

app = Starlette(routes=[Route("/oauth/authorize", ma.oauth_authorize, methods=["GET", "POST"]),
                        Route("/oauth/token", ma.oauth_token, methods=["POST", "OPTIONS"])])
c = TestClient(app, follow_redirects=False)
F = []
def check(l, ok, d=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {l}" + ("" if ok else f"  {d}"))
    if not ok: F.append(l)

q = {"client_id": "cid123", "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
     "response_type": "code", "state": "s1", "code_challenge": "x", "code_challenge_method": "S256"}
r = c.get("/oauth/authorize", params=q)
check("GET no longer issues a code: it shows the approve page",
      r.status_code == 200 and "Admin PIN" in r.text and "code=" not in r.headers.get("location", ""), r.status_code)
check("the page names the app asking", "claude.ai" in r.text)
r = c.post("/oauth/authorize", data={**q, "pin": "0000"})
check("a wrong PIN issues nothing", r.status_code == 200 and "not right" in r.text)
r = c.post("/oauth/authorize", data={**q, "pin": "9911"})
loc = r.headers.get("location", "")
check("the right PIN redirects with a code and the state",
      r.status_code == 302 and "code=" in loc and "state=s1" in loc and loc.startswith(q["redirect_uri"]), (r.status_code, loc))
r = c.post("/oauth/authorize", data={**q, "client_id": "nope", "pin": "9911"})
check("a wrong client id is refused even with the PIN", r.status_code == 401)
ma._PIN_FAILS[:] = []
for _ in range(ma._PIN_FAIL_MAX):
    c.post("/oauth/authorize", data={**q, "pin": "1"})
r = c.post("/oauth/authorize", data={**q, "pin": "9911"})
check("after too many wrong PINs even the right one waits", "Too many" in r.text and r.status_code == 200)
ma._PIN_FAILS[:] = []
os.environ["ADMIN_PIN"] = ""
r = c.post("/oauth/authorize", data={**q, "pin": ""})
check("no ADMIN_PIN configured means nobody is approved", r.status_code == 200 and "not right" in r.text)
src = open("asgi_app.py").read()
check("the route takes POST", 'Route("/oauth/authorize", oauth_authorize, methods=["GET", "POST"])' in src)
print("\n" + (f"{len(F)} FAILED: {F}" if F else "ALL PASS"))
sys.exit(1 if F else 0)
