"""Store registration links: derived from the event name, saved only when
the store answers, expired (never deleted) once the event is played.

Kerry 2026-09-09: "Are you able to grab other current event URLs and add
them to the Event pages for email or text presets? ... After the events
they become obsolete and should be removed or something."

Run: python3 test_event_links.py
"""

import os
import sqlite3
import sys
import tempfile
from datetime import date

os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import event_links as el  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILURES.append(label)


TODAY = date(2026, 9, 9)


def fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    with sqlite3.connect(tmp.name) as c:
        c.executescript("""
            CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT,
                event_date TEXT, registration_url TEXT,
                registration_url_status TEXT, registration_url_checked_at TEXT);
            INSERT INTO events VALUES (3314, 'a9.23 Avery Ranch', '2026-09-15', NULL, NULL, NULL);
            INSERT INTO events VALUES (3310, 's18.11 CEDAR CREEK', '2026-09-19', NULL, NULL, NULL);
            INSERT INTO events VALUES (3302, 's9.23 The Quarry', '2026-09-15',
                'https://thegolffellowship.com/shop/ols/products/quarry-tuesday', NULL, NULL);
            INSERT INTO events VALUES (3306, 's9.22 Silverhorn', '2026-09-08',
                'https://thegolffellowship.com/shop/ols/products/s9-22-silverhorn', 'ok', '2026-09-01 12:00:00');
            INSERT INTO events VALUES (3237, 'SEASON CONTESTS', NULL, NULL, NULL, NULL);
        """)
    return tmp.name


def rows(p):
    with sqlite3.connect(p) as c:
        c.row_factory = sqlite3.Row
        return {r["id"]: dict(r) for r in c.execute("SELECT * FROM events")}


def main():
    # ── the slug rule, against URLs Kerry has actually pasted ──────────
    check("a9.23 Avery Ranch -> a9-23-avery-ranch",
          el.derive_store_slug("a9.23 Avery Ranch") == "a9-23-avery-ranch")
    check("s18.11 CEDAR CREEK -> s18-11-cedar-creek",
          el.derive_store_slug("s18.11 CEDAR CREEK") == "s18-11-cedar-creek")
    check("2026 TGF CHAMPIONSHIP -> 2026-tgf-championship",
          el.derive_store_slug("2026 TGF CHAMPIONSHIP") == "2026-tgf-championship")
    check("a pipe and doubled spaces collapse to one hyphen",
          el.derive_store_slug("s9.16 TPC San Antonio | Oaks") == "s9-16-tpc-san-antonio-oaks",
          el.derive_store_slug("s9.16 TPC San Antonio | Oaks"))
    check("an empty name derives no URL", el.derive_store_url("") == "")
    check("the full URL sits under the store base",
          el.derive_store_url("a9.23 Avery Ranch")
          == "https://thegolffellowship.com/shop/ols/products/a9-23-avery-ranch")

    # ── the checker, with the network replaced ─────────────────────────
    good = "https://thegolffellowship.com/shop/ols/products/a9-23-avery-ranch"
    check("200 on the product URL is ok",
          el.check_store_url(good, fetch=lambda u, t: (200, u))["status"] == "ok")
    check("200 after a redirect to the shop index is MISSING (GoDaddy soft-404)",
          el.check_store_url(good, fetch=lambda u, t: (200, "https://thegolffellowship.com/shop"))["status"] == "missing")
    check("404 is missing",
          el.check_store_url(good, fetch=lambda u, t: (404, u))["status"] == "missing")
    check("a 5xx is error, not missing",
          el.check_store_url(good, fetch=lambda u, t: (503, u))["status"] == "error")

    def boom(u, t):
        raise TimeoutError("slow")
    check("a network failure is error", el.check_store_url(good, fetch=boom)["status"] == "error")
    check("a non-store host is refused before any fetch",
          el.check_store_url("https://evil.example/x", fetch=lambda u, t: (200, u))["status"] == "error")
    check("http:// is refused", not el.is_store_url("http://thegolffellowship.com/shop/ols/products/x"))

    # ── link state as the modal reads it ───────────────────────────────
    up = {"item_name": "a9.23 Avery Ranch", "event_date": "2026-09-15", "registration_url": None}
    st = el.link_state(up, TODAY)
    check("upcoming with no URL: missing + a suggestion",
          st["state"] == "missing" and st["suggested_url"].endswith("/a9-23-avery-ranch"), st)
    past = {"item_name": "s9.22 Silverhorn", "event_date": "2026-09-08",
            "registration_url": good, "registration_url_status": "ok"}
    check("a played event's link reads expired even when it verified",
          el.link_state(past, TODAY)["state"] == "expired")
    check("today's event is NOT expired",
          el.link_state({"event_date": "2026-09-09", "registration_url": good}, TODAY)["state"] == "unverified")

    # ── the composer variable ──────────────────────────────────────────
    url, why = el.event_url_for_message(past, TODAY)
    check("expired link is refused for {event_url}", url == "" and "played" in why, (url, why))
    url, why = el.event_url_for_message(up, TODAY)
    check("no link on file is refused", url == "" and "no registration link" in why, (url, why))
    ok_ev = dict(up, registration_url=good, registration_url_status="ok")
    check("verified upcoming link renders", el.event_url_for_message(ok_ev, TODAY) == (good, ""))
    typed_ev = dict(up, registration_url=good, registration_url_status=None)
    check("a hand-typed, not-yet-verified link still renders",
          el.event_url_for_message(typed_ev, TODAY)[0] == good)
    dead_ev = dict(up, registration_url=good, registration_url_status="missing")
    check("a link the store rejected is refused",
          el.event_url_for_message(dead_ev, TODAY)[0] == "")

    # ── the sweep ──────────────────────────────────────────────────────
    store = {  # what the store "knows"
        "https://thegolffellowship.com/shop/ols/products/a9-23-avery-ranch": (200, None),
        "https://thegolffellowship.com/shop/ols/products/quarry-tuesday": (200, None),
        # Cedar Creek not listed yet -> soft-404 redirect to the shop index
    }

    def fake_checker(url):
        code, final = store.get(url, (200, "https://thegolffellowship.com/shop"))
        return el.check_store_url(url, fetch=lambda u, t: (code, final or u))

    p = fresh_db()
    dry = el.sweep_event_links(p, apply=False, today=TODAY, checker=fake_checker)
    r = rows(p)
    check("dry run writes nothing",
          r[3314]["registration_url"] is None and r[3306]["registration_url_status"] == "ok", r)
    check("dry run reports the derived Avery Ranch link as ok",
          any(x["id"] == 3314 and x["derived"] and x["status"] == "ok" for x in dry["rows"]), dry["rows"])
    check("dry run reports Cedar Creek as missing (store has no page yet)",
          any(x["id"] == 3310 and x["status"] == "missing" for x in dry["rows"]), dry["rows"])
    check("events with no date are skipped",
          not any(x["id"] == 3237 for x in dry["rows"]))

    res = el.sweep_event_links(p, apply=True, today=TODAY, checker=fake_checker)
    r = rows(p)
    check("apply fills a verified derived link",
          r[3314]["registration_url"] == "https://thegolffellowship.com/shop/ols/products/a9-23-avery-ranch"
          and r[3314]["registration_url_status"] == "ok" and r[3314]["registration_url_checked_at"], r[3314])
    check("apply does NOT save a derived link the store rejected",
          r[3310]["registration_url"] is None and r[3310]["registration_url_status"] is None, r[3310])
    check("a hand-typed URL is verified in place, never replaced",
          r[3302]["registration_url"].endswith("/quarry-tuesday") and r[3302]["registration_url_status"] == "ok", r[3302])
    check("a played event's link is marked expired, URL kept",
          r[3306]["registration_url"].endswith("/s9-22-silverhorn") and r[3306]["registration_url_status"] == "expired", r[3306])
    check("counts: 2 verified, 1 filled, 1 missing, 1 expired",
          (res["verified"], res["filled"], res["missing"], res["expired"]) == (2, 1, 1, 1),
          {k: res[k] for k in ("verified", "filled", "missing", "expired", "errors")})

    res2 = el.sweep_event_links(p, apply=True, today=TODAY, checker=fake_checker)
    check("second sweep is idempotent (nothing newly filled or expired)",
          res2["filled"] == 0 and res2["expired"] == 0, res2)

    one = el.sweep_event_links(p, apply=True, today=TODAY, checker=fake_checker, only_event_id=3310)
    check("only_event_id scopes the sweep", [x["id"] for x in one["rows"]] == [3310], one["rows"])

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
