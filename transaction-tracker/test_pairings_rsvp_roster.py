"""RSVP-only players are FIRST-CLASS on the pairings roster (Kerry
2026-09-15: "I need the ability to assign RSVP only's to groups and
requests. Need them to run in pairings").

Before this, a player who RSVP'd PLAYING in Golf Genius without buying
reached the pairings panel only through a client-side merge: a manager
could seat them by hand, but Generate never dealt them, a partner request
naming them could not resolve, and the manual-match validator refused
them. The roster is now built ONCE on the server (`_event_roster_rows`)
and every consumer reads it. This test pins:

  1. the derivation mirrors the Players tab rule for rule (matched-with-
     agreeing-email OUT, email-mismatch match IN, override OUT, email or
     resolved-name already registered OUT, first-name heuristic OUT only
     when no resolved name, NOT PLAYING out, cancelled event empty);
  2. the four consumers agree: roster rows, generator, request list,
     manual-match validator;
  3. $0 rsvp_only ORDER rows are on the roster too and badged.

Run: python3 test_pairings_rsvp_roster.py
"""
import os, sqlite3, sys, tempfile
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-rsvp-roster-"), "t.db")
# The full schema (the generator touches a dozen tables). init_db's data
# repairs chatter on an empty DB; that noise is not this test's output.
import contextlib, io  # noqa: E402
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
db._PARTNER_IDENTITY_CACHE.update({"at": 0.0, "map": {}})
conn = sqlite3.connect(tmp)
conn.row_factory = sqlite3.Row
EV = "s9.99 Test Quarry"
conn.execute("INSERT INTO events (id, item_name, event_date, course, chapter, format, status) "
             "VALUES (1, ?, '2026-09-22', 'The Quarry', 'San Antonio', '9 Holes', 'active')", (EV,))
conn.execute("INSERT INTO events (id, item_name, event_date, chapter, format, status) "
             "VALUES (2, 's9.98 Cancelled', '2026-09-23', 'San Antonio', '9 Holes', 'cancelled')")
conn.executemany(
    "INSERT INTO customers (customer_id, first_name, last_name, current_player_status) VALUES (?,?,?,?)",
    [(1, "Alan", "Paid", "active_member"), (2, "Bob", "Paid", "active_member"),
     (3, "Carl", "Rsvp", "active_member"), (4, "Dan", "South", "active_guest"),
     (5, "Ed", "Credited", "active_member"), (6, "Fay", "Zero", "active_guest")])
# Order rows: two paid, one credited (inactive), one $0 rsvp_only row.
rows = [
    ("u1", "Alan Paid", 1, "alan@x.com", "active", "Carl Rsvp"),
    ("u2", "Bob Paid", 2, "bob@x.com", "active", None),
    ("u5", "Ed Credited", 5, "ed@x.com", "credited", None),
    ("u6", "Fay Zero", 6, "fay@x.com", "rsvp_only", None),
]
for uid, name, cid, email, st, req in rows:
    conn.execute(
        "INSERT INTO items (email_uid, merchant, customer, customer_id, customer_email, item_name, "
        " holes, transaction_status, partner_request, order_date, created_at, event_id) "
        "VALUES (?,'GoDaddy',?,?,?,?,'9',?,?,'2026-09-10','2026-09-10 10:00:00',1)",
        (uid, name, cid, email, EV, st, req))
# RSVPs (latest per email wins):
rsvps = [
    # matched to Alan's active row with the SAME email -> OUT (circle on his row)
    ("r1", "Alan", "alan@x.com", "PLAYING", "2026-09-11 09:00:00", 1, 1),
    # matched_item_id points at Bob's row but the email disagrees -> IN
    ("r2", "Carl", "carl@x.com", "PLAYING", "2026-09-11 09:05:00", 2, 3),
    # unmatched, resolves through customers -> IN, as "Dan South"
    ("r3", "Dan", "dan@x.com", "PLAYING", "2026-09-11 09:10:00", None, 4),
    # unmatched, email overridden to not_playing -> OUT
    ("r4", "Gus", "gus@x.com", "PLAYING", "2026-09-11 09:15:00", None, None),
    # unmatched, NO card and NO customer: resolved_name falls back to the
    # RSVP's own name, so the Players tab lists "Bob" as a synthetic row
    # even though a registrant's name starts with it -> IN (mirrored)
    ("r5", "Bob", "bob2@x.com", "PLAYING", "2026-09-11 09:20:00", None, None),
    # NOT PLAYING -> OUT
    ("r6", "Hank", "hank@x.com", "NOT PLAYING", "2026-09-11 09:25:00", None, None),
    # unmatched, no card, no customer -> IN under the RSVP's own name
    ("r7", "Ivan", "ivan@x.com", "PLAYING", "2026-09-11 09:30:00", None, None),
    # an earlier PLAYING for Hank that the later NOT PLAYING supersedes
    ("r8", "Hank", "hank@x.com", "PLAYING", "2026-09-11 08:00:00", None, None),
    # a PLAYING RSVP on the CANCELLED event
    ("r9", "Zed", "zed@x.com", "PLAYING", "2026-09-11 09:40:00", None, None),
]
for uid, pname, email, resp, at, mid, cid in rsvps:
    conn.execute(
        "INSERT INTO rsvps (email_uid, player_name, player_email, matched_event, response, "
        " received_at, matched_item_id, customer_id) VALUES (?,?,?,?,?,?,?,?)",
        (uid, pname, email, EV if uid != "r9" else "s9.98 Cancelled", resp, at, mid, cid))
conn.execute("INSERT INTO rsvp_email_overrides (player_email, event_name, status) VALUES ('gus@x.com', ?, 'not_playing')", (EV,))
# A handicap history for Alan so the index rides on his roster row
# (v2.414.0: a player seated FROM Unassigned must keep his index).
conn.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES ('Alan Paid', 'Alan Paid', 1)")
# Three rounds, because the map is the TGF index (v2.460.0 — the same
# computation the ROSTER shows) and an index needs three.
ALAN_DIFFS = (4.0, 6.0, 5.0)
for i, d in enumerate(ALAN_DIFFS):
    conn.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) "
                 "VALUES ('Alan Paid', date('now', ?), 40, 34.5, 120, ?)", (f'-{i+1} days', d))
conn.commit()
ALAN_IDX = db.compute_handicap_index(list(ALAN_DIFFS), db.get_handicap_settings(tmp))

print("\n== derivation mirrors the Players tab ==")
extra = db._event_rsvp_only_players(conn, 1)
names = sorted(p["name"] for p in extra)
check("exactly the four unmatched PLAYING RSVPs are on the roster",
      names == ["Bob", "Carl Rsvp", "Dan South", "Ivan"], str(names))
check("a match whose email disagrees is treated as unmatched (Carl)", "Carl Rsvp" in names)
check("resolved through customers, not the RSVP first name (Dan South)", "Dan South" in names)
check("not_playing override drops the RSVP (Gus)", "Gus" not in names)
check("an RSVP with no card and no customer stays IN under its own name (Bob), as the Players tab shows it",
      "Bob" in names)
check("latest response wins (Hank's NOT PLAYING)", "Hank" not in names)
check("every RSVP row is flagged rsvp_only", all(p["rsvp_only"] for p in extra))
check("arrival time is the signup time for request priority",
      next(p for p in extra if p["name"] == "Carl Rsvp")["order_date"] == "2026-09-11")
check("a cancelled event has no RSVP roster", db._event_rsvp_only_players(conn, 2) == [])

print("\n== the roster is one list ==")
roster = db._event_roster_rows(conn, 1)
rn = sorted(r["name"] for r in roster)
check("orders + RSVPs, credited excluded",
      rn == ["Alan Paid", "Bob", "Bob Paid", "Carl Rsvp", "Dan South", "Fay Zero", "Ivan"], str(rn))
check("the $0 rsvp_only ORDER row is badged too",
      next(r for r in roster if r["name"] == "Fay Zero")["rsvp_only"] is True)
check("a paid row is not badged",
      next(r for r in roster if r["name"] == "Alan Paid")["rsvp_only"] is False)
ids = {r["name"]: r["customer_id"] for r in db._event_roster_players(conn, 1)}
check("_event_roster_players carries the RSVP player's customer_id", ids.get("Carl Rsvp") == 3, str(ids))

print("\n== 1Y = first-year member with NO handicap history before the event year ==")
conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, source) VALUES (1, '2026-03-01', '2027-03-01', 'backfill')")
conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, source) VALUES (2, '2026-05-01', '2027-05-01', 'renewal')")
conn.execute("INSERT INTO handicap_player_links (player_name, customer_name, customer_id) VALUES ('Bob Paid', 'Bob Paid', 2)")
conn.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) VALUES ('Bob Paid', '2025-06-01', 40, 34.5, 120, 5.0)")
conn.commit()
rows = {r["name"]: r for r in db._event_roster_rows(conn, 1)}
check("a 2026 membership with rounds only in 2026 is 1Y (Alan)", rows["Alan Paid"]["is_new"] is True, str(rows["Alan Paid"].get("first_round")))
check("a 2026 membership row but a 2025 handicap round is NOT 1Y (Bob)", rows["Bob Paid"]["is_new"] is False)
check("no membership at all is not 1Y (Fay, RSVP-only order)", rows["Fay Zero"]["is_new"] is False)

print("\n== one handicap-index lookup ==")
hmap = db._roster_handicap_index_map(conn)
check("the shared map reads the linked history (Alan: the TGF index of his three rounds)",
      hmap.get("alan paid") == ALAN_IDX, str(hmap))
check("unlinked players are simply absent", "bob paid" not in hmap)
conn.close()

print("\n== partner requests resolve to RSVP-only players ==")
reqs = db.get_event_partner_requests(1, db_path=tmp)["requests"]
alan = next((r for r in reqs if r["requester"] == "Alan Paid"), None)
check("Alan's request for Carl (RSVP-only) resolves", bool(alan and alan.get("matched")), str(alan))
check("…to the RSVP player's roster name", bool(alan and alan.get("partner") == "Carl Rsvp"), str(alan))

print("\n== the manual-match validator accepts RSVP-only players ==")
ok = True
try:
    res = db.set_partner_request_match(1, "Bob Paid", "Ivan", db_path=tmp)
    bob = next((r for r in res["requests"] if r["requester"] == "Bob Paid"), None)
    ok = bool(bob and bob.get("partner") == "Ivan")
except ValueError as e:
    ok = False; res = str(e)
check("Bob (paid) can be matched to Ivan (GG RSVP, no card)", ok, str(res)[:200])
ok2 = True
try:
    db.set_partner_request_match(1, "Dan South", "Fay Zero", db_path=tmp)
except ValueError as e:
    ok2 = False; err = str(e)
check("an RSVP-only player can be the REQUESTER", ok2, err if not ok2 else "")

print("\n== Generate deals RSVP-only players ==")
try:
    out = db.generate_event_pairings(1, mode="random", protect_partner_requests=True, db_path=tmp)
    seated = [p["name"] for g in out.get("9", []) for p in g["players"] if p.get("name")]
    check("every roster player is seated once",
          sorted(seated) == ["Alan Paid", "Bob", "Bob Paid", "Carl Rsvp", "Dan South", "Fay Zero", "Ivan"],
          str(seated))
    grp_of = {p["name"]: i for i, g in enumerate(out.get("9", [])) for p in g["players"] if p.get("name")}
    check("Alan's request for Carl is honored", grp_of.get("Alan Paid") == grp_of.get("Carl Rsvp"), str(grp_of))
    check("Bob's manual match to Ivan is honored", grp_of.get("Bob Paid") == grp_of.get("Ivan"), str(grp_of))
    alan = next(p for g in out.get("9", []) for p in g["players"] if p.get("name") == "Alan Paid")
    check("the generator seats Alan with the same index the map holds", alan.get("handicap_index") == ALAN_IDX, str(alan))
except Exception as e:  # noqa: BLE001
    import traceback; traceback.print_exc()
    check("generate_event_pairings ran on the fixture", False, repr(e))

print("\n" + ("FAILED: " + ", ".join(FAILURES) if FAILURES else "ALL PASSED"))
sys.exit(1 if FAILURES else 0)
