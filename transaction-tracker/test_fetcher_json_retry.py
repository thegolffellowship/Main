"""A Graph GET whose body arrives cut off is asked for once more (Health 10/19:
inbox_check JSONDecodeError on 10/18 and 10/19, both under host load)."""
import sys
from email_parser import fetcher

fails = []


def check(name, ok):
    print(("  PASS  " if ok else "  FAIL  ") + name)
    if not ok:
        fails.append(name)


class Resp:
    status_code = 200
    url = "https://graph.microsoft.com/v1.0/x?$top=1"
    headers = {}

    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        import json
        return json.loads(self.body)


calls = []


def fake_request(method, url, **kw):
    calls.append((method, url))
    return Resp('{"value": [1, 2]}')


fetcher.requests.request = fake_request

good = Resp('{"value": [3]}')
check("a clean body is returned without a second request",
      fetcher._json_or_retry(good) == {"value": [3]} and not calls)

cut = Resp('{"value": [1, 2, 3, 4')
out = fetcher._json_or_retry(cut, headers={}, timeout=30)
check("a cut-off body is requested once more and the new body is used",
      out == {"value": [1, 2]} and len(calls) == 1 and calls[0] == ("get", cut.url))


class AlwaysBad(Resp):
    pass


def bad_request(method, url, **kw):
    return Resp('{"value": [')


fetcher.requests.request = bad_request
try:
    fetcher._json_or_retry(Resp('{'), headers={}, timeout=30)
    check("a body that is bad twice still raises (the job's own error path)", False)
except ValueError:
    check("a body that is bad twice still raises (the job's own error path)", True)

print("\nALL PASS" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
