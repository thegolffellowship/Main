"""Brevo campaign audience split (Kerry 2026-09-17): the async recipient
export → emails → TGF status groups. requests is mocked; no network.

Run: python3 test_brevo_campaign_split.py
"""
import os
import sys

os.environ.setdefault("DATABASE_PATH", ":memory:")
sys.path.insert(0, os.path.dirname(__file__))
from email_parser import brevo  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


class R:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text or (str(payload) if payload is not None else "")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


CSV = {
    "all": "EMAIL,FIRSTNAME\nA@x.com,A\nb@x.com,B\nc@x.com,C\nd@x.com,D\ne@x.com,E\n",
    "openers": "EMAIL\na@x.com\nc@x.com\ne@x.com\n",
    "clickers": "EMAIL\nc@x.com\n",
    "unsubscribed": "EMAIL\nd@x.com\n",
}
calls = []
polls = {"n": 0}


def fake_post(url, headers=None, json=None, timeout=None):
    calls.append(("POST", url, json))
    t = json["recipientsType"]
    return R(202, {"processId": {"all": 1, "openers": 2, "clickers": 3, "unsubscribed": 4}[t]})


def fake_get(url, headers=None, params=None, timeout=None):
    calls.append(("GET", url, None))
    if "/processes/" in url:
        pid = int(url.rsplit("/", 1)[1])
        polls["n"] += 1
        if polls["n"] % 2 == 1:           # first poll: still running
            return R(200, {"id": pid, "status": "in_process"})
        return R(200, {"id": pid, "status": "completed", "export_url": f"https://files.example/{pid}.csv"})
    if url.endswith(".csv"):
        pid = int(url.rsplit("/", 1)[1].split(".")[0])
        return R(200, None, CSV[{1: "all", 2: "openers", 3: "clickers", 4: "unsubscribed"}[pid]])
    raise AssertionError(url)


brevo.requests.post = fake_post
brevo.requests.get = fake_get
brevo.time.sleep = lambda s: None
brevo.tracker_contact_targets = lambda db_path=None: {
    "a@x.com": {"status": "active_member"}, "b@x.com": {"status": "former_member"},
    "c@x.com": {"status": "prospect"}, "d@x.com": {"status": "former_member"}}
os.environ["BREVO_API_KEY"] = "k"

res = brevo.campaign_split(19)
check("four exports requested, one per type", [c[2]["recipientsType"] for c in calls if c[0] == "POST"]
      == ["all", "openers", "clickers", "unsubscribed"])
check("emails parsed case-insensitively, header row skipped", res["totals"] == {"all": 5, "openers": 3, "clickers": 1, "unsubscribed": 1}, str(res["totals"]))
g = res["groups"]
check("groups by Tracker status; unknown = not in Tracker",
      g["active_member"]["all"] == 1 and g["former_member"]["all"] == 2 and g["prospect"]["all"] == 1 and g["unknown"]["all"] == 1, str(g))
check("rates inside each group", g["prospect"]["clickers_pct"] == 100.0 and g["former_member"]["unsubscribed_pct"] == 50.0
      and g["unknown"]["openers_pct"] == 100.0 and g["active_member"]["clickers_pct"] == 0.0, str(g))
check("no errors", res["errors"] == [], str(res["errors"]))
brevo.requests.post = lambda *a, **k: R(400, {"message": "nope"}, "nope")
res2 = brevo.campaign_split(19, types=("clickers",))
check("export failure is reported, not raised", res2["errors"] and "clickers" in res2["errors"][0], str(res2))
del os.environ["BREVO_API_KEY"]
check("no key → error", brevo.campaign_split(19).get("error"))

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}"); sys.exit(1)
print("ALL PASSED")
