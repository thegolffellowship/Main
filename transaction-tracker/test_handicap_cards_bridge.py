"""The closeout can send the handicap cards (v2.487.0).

Kerry 2026-09-23: "For the closeout automatically send the handicap card
updates to those who played in that event. To remove one more manual
operation from me." The Handicaps page's By-Event send became ONE
function, `send_handicap_cards`, with a DRY RUN that names who would get
a card and touches nothing; the bridge `scoring-hcp-cards:<event>[|apply]`
and the route both call it.

Run: python test_handicap_cards_bridge.py
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


tmp = tempfile.mktemp(suffix=".db")
db.init_db(tmp)
c = sqlite3.connect(tmp)
c.row_factory = sqlite3.Row
c.execute("INSERT INTO courses (course_id, name, status) VALUES (900, 'Test Links', 'active')")
c.execute("INSERT INTO events (id, item_name, event_date, chapter, course, course_id, status, format, nine_side) "
          "VALUES (990, 's9.99 Test Links', '2026-09-22', 'San Antonio', 'Test Links', 900, 'active', '9 Holes', 'Front')")
# Three registrants: one with a full handicap history and an email, one
# with a history but NO email, one with no handicap link at all.
for cid, first, last, email in ((301, "Pat", "Youngs", "pat@example.com"),
                                 (302, "Larry", "Anthis", None),
                                 (303, "Gus", "Vasquez", "gus@example.com")):
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) "
              "VALUES (?, ?, ?, 'San Antonio', 'active')", (cid, first, last))
    if email:
        c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?, ?, 1)", (cid, email))
    c.execute("INSERT INTO items (email_uid, item_index, merchant, customer, customer_id, item_name, event_id, "
              "transaction_status, chapter, first_name, last_name, customer_email, order_date, item_price) "
              "VALUES (?, 0, 'Manual Entry', ?, ?, 's9.99 Test Links', 990, 'active', 'San Antonio', ?, ?, ?, "
              "'2026-09-20', '$50.00')",
              (f"manual-test-{cid}", f"{first} {last}", cid, first, last, email))
for cid, first, last in ((301, "Pat", "Youngs"), (302, "Larry", "Anthis")):
    c.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES (?, ?, ?)",
              (f"{last}, {first}", f"{first} {last}", cid))
    for d in (10, 20, 30, 40):
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) "
                  "VALUES (?, date('now', ?), 45, 34.5, 120, 9.4)", (f"{last}, {first}", f"-{d} days"))
c.commit()
c.close()

print("A dry run names who would get a card and touches nothing")
res = db.send_handicap_cards(event_name="s9.99 Test Links", dry_run=True, sent_by="closeout", db_path=tmp)
check("the dry run answers with status dry_run and no error", res.get("status") == "dry_run" and not res.get("error"), res)
names = [w["player"] for w in (res.get("would_send") or [])]
check("the player with an index and an email is the one who would get a card", names == ["Pat Youngs"], res)
check("the player with no email is counted and NAMED, not dropped",
      res.get("skipped_no_email") == 1 and any(p["player"] == "Larry Anthis" and "email" in p["why"]
                                              for p in res.get("skipped_players", [])), res.get("skipped_players"))
check("the player with no handicap is counted and NAMED",
      any("no TGF handicap" in p["why"] for p in res.get("skipped_players", [])), res.get("skipped_players"))
check("the arithmetic closes: 3 registered, 0 unaccounted",
      res.get("registered") == 3 and res.get("unaccounted") == 0, {k: res.get(k) for k in ("registered", "accounted", "unaccounted")})
check("nothing was sent", res.get("sent") == 0 and res.get("failed") == 0, res)
c = sqlite3.connect(tmp)
n_log = c.execute("SELECT COUNT(*) FROM message_log WHERE event_name = 'handicap-card'").fetchone()[0]
c.close()
check("no message_log row was written by the dry run", n_log == 0, n_log)

print()
print("An unknown event refuses rather than falling through to a send")
bad = db.send_handicap_cards(event_name="s9.98 Nowhere", dry_run=False, db_path=tmp)
check("unknown event → error 400, nothing sent", bad.get("http") == 400 and "nothing sent" in bad.get("error", ""), bad)

print()
print("The bridge and the route both call the one function")
src = open(os.path.join(os.path.dirname(__file__), "mcp_server.py"), encoding="utf-8").read()
check("scoring-hcp-cards bridge exists and defaults to a dry run",
      'cmd == "scoring-hcp-cards"' in src and "dry_run=not _apply" in src)
app_src = open(os.path.join(os.path.dirname(__file__), "app.py"), encoding="utf-8").read()
check("the page route delegates to send_handicap_cards with dry_run=False",
      "send_handicap_cards(" in app_src and "dry_run=False" in app_src.split("send_handicap_cards(")[1][:400])

print()
print("ALL PASS" if not F else f"FAILED: {F}")
sys.exit(1 if F else 0)
