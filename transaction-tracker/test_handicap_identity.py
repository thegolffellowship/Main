"""Handicap card identity: `customer_id`, never a name string.

Kerry 2026-09-15, on the handicap-card event filter: "What's the bug? We
need to fix it."

The send matched event registrants to handicap links by comparing two
NAME STRINGS — `items.customer` (a per-order historical snapshot) against
`handicap_player_links.customer_name`. So "Mike Murphy" on the order and
"Michael Murphy" on the link were the same man and resolved to nothing,
and he was classified "no TGF handicap on record" and silently got no
card. Three compounding defects, all tested here:

  (a) name-string identity on both sides of the match;
  (b) `WHERE customer_name IS NOT NULL` dropped any link that had a
      `customer_id` but no name label;
  (c) the route built its OWN roster from get_all_items() + aliases
      instead of `_event_roster_rows` — the ONE builder (v2.410.0) — so a
      Golf Genius RSVP with no order row was invisible and was not even
      counted in `registered`.

CLAUDE.md guiding principle 6: "when checking whether 'Stuart Kirksey'
and 'Stu Kirksey' are the same person, join through `customer_id` — never
compare name strings."

Run: python3 test_handicap_identity.py
"""
import os, sys, tempfile, logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)

logging.disable(logging.WARNING)
# app is imported with NO email credentials on purpose: that is what keeps
# the background scheduler from starting and fighting this test for the
# SQLite file. The route's own credential check reads os.environ at call
# time, so they are set immediately after the import instead.
import app as appmod                                            # noqa: E402
from email_parser import database as db                          # noqa: E402
for _k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
           "EMAIL_ADDRESS"):
    os.environ[_k] = "test"

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


# ---------------------------------------------------------------------
# Fixture. One event with four registrants, each one a different way a
# player can fail to be recognised:
#
#   Michael Murphy  — NAME DRIFT. The order says "Mike Murphy", the
#                     handicap link says "Michael Murphy". One person,
#                     one customer_id. Must be SENT.
#   Stuart Kirksey  — the link has a customer_id and NO customer_name at
#                     all. Must not vanish.
#   Gus Vasquez     — GG RSVP only, no order row. Must be counted in
#                     `registered`.
#   Nolan Index     — on the roster, genuinely no handicap. Must be
#                     skipped AND named.
# ---------------------------------------------------------------------
conn = db.get_connection()
cur = conn.cursor()


def customer(cid, first, last, status="active_member", chapter="San Antonio"):
    cur.execute(
        """INSERT INTO customers (customer_id, first_name, last_name, chapter,
                                  current_player_status)
           VALUES (?, ?, ?, ?, ?)""", (cid, first, last, chapter, status))
    cur.execute(
        """INSERT INTO customer_emails (customer_id, email, is_primary)
           VALUES (?, ?, 1)""",
        (cid, f"{first}.{last}@example.com".lower()))


EVENT = "s9.99 Identity Test"
cur.execute(
    """INSERT INTO events (id, item_name, event_date, chapter, status)
       VALUES (9901, ?, '2026-09-15', 'San Antonio', 'active')""", (EVENT,))

customer(9001, "Michael", "Murphy")
customer(9002, "Stuart", "Kirksey")
customer(9003, "Gus", "Vasquez")
customer(9004, "Nolan", "Index")

# Order rows. NOTE the `customer` column deliberately disagrees with the
# canonical name for Murphy — that is the whole bug.
for cid, cname in ((9001, "Mike Murphy"),      # <- drifted snapshot
                   (9002, "Stuart Kirksey"),
                   (9004, "Nolan Index")):
    cur.execute(
        """INSERT INTO items (customer, customer_id, item_name, event_id,
                              transaction_status, parent_item_id, chapter,
                              customer_email, order_date, email_uid, merchant)
           VALUES (?, ?, ?, 9901, 'active', NULL, 'San Antonio', ?,
                   '2026-09-10', ?, 'GoDaddy')""",
        (cname, cid, EVENT, f"order.{cid}@example.com", f"uid-{cid}"))

# Gus is a PLAYING Golf Genius RSVP with no order row at all.
cur.execute(
    """INSERT INTO rsvps (email_uid, matched_event, player_name, player_email,
                          response, customer_id, received_at)
       VALUES ('rsvp-9003', ?, 'Gus', 'gus.vasquez@example.com', 'PLAYING',
               9003, '2026-09-11 08:00:00')""", (EVENT,))

# Handicap links. Murphy's LABEL is the canonical name, not the order's.
# Kirksey's label is NULL — a link with an id and no name.
cur.execute("""INSERT INTO handicap_player_links (player_name, customer_name, customer_id)
               VALUES ('MURPHY, Michael', 'Michael Murphy', 9001)""")
cur.execute("""INSERT INTO handicap_player_links (player_name, customer_name, customer_id)
               VALUES ('KIRKSEY, Stu', NULL, 9002)""")
cur.execute("""INSERT INTO handicap_player_links (player_name, customer_name, customer_id)
               VALUES ('VASQUEZ, Gus', 'Gus Vasquez', 9003)""")

# Enough posted rounds to establish an index for the first three.
for pname, diffs in (("MURPHY, Michael", [16.0, 17.0, 18.0]),
                     ("KIRKSEY, Stu", [8.0, 9.0, 10.0]),
                     ("VASQUEZ, Gus", [5.0, 6.0, 7.0])):
    for i, d in enumerate(diffs):
        cur.execute(
            """INSERT INTO handicap_rounds (player_name, round_date, tee_name,
                                            adjusted_score, rating, slope,
                                            differential)
               VALUES (?, ?, 'Blue', 40, 34.0, 113, ?)""",
            (pname, f"2026-0{i + 6}-01", d))
conn.commit()
conn.close()


print("\n== get_handicap_export_data publishes the identity key ==")
export = db.get_handicap_export_data(db_path=DB)
rows = {r["player_name"]: r for r in export["rows"]}
check("every exported row carries a customer_id",
      all(r.get("customer_id") is not None for r in export["rows"]),
      str([r["player_name"] for r in export["rows"]
           if r.get("customer_id") is None]))
check("a link with a NULL customer_name does not vanish",
      "KIRKSEY, Stu" in rows,
      f"got {sorted(rows)}")
check("…and it resolves to the right person through its customer_id",
      rows.get("KIRKSEY, Stu", {}).get("customer_id") == 9002)
check("…and its email came off the customer profile, not a name join",
      rows.get("KIRKSEY, Stu", {}).get("email") == "stuart.kirksey@example.com",
      str(rows.get("KIRKSEY, Stu", {}).get("email")))
check("the drifted name still resolves to its customer",
      rows.get("MURPHY, Michael", {}).get("customer_id") == 9001)
check("first/last come from the CANONICAL profile, not the order snapshot",
      (rows.get("MURPHY, Michael", {}).get("first_name"),
       rows.get("MURPHY, Michael", {}).get("last_name")) == ("Michael", "Murphy"),
      str(rows.get("MURPHY, Michael")))
check("nothing needed the name fallback, and the report says so",
      export.get("name_fallbacks") == [], str(export.get("name_fallbacks")))


print("\n== an unlinked link is REPORTED, never silently resolved ==")
conn = db.get_connection()
conn.execute("""INSERT INTO handicap_player_links (player_name, customer_name, customer_id)
                VALUES ('ORPHAN, Nobody', 'Nobody Orphan', NULL)""")
conn.execute("""INSERT INTO handicap_rounds (player_name, round_date, tee_name,
                                             adjusted_score, rating, slope, differential)
                VALUES ('ORPHAN, Nobody', '2026-06-01', 'Blue', 40, 34.0, 113, 12.0)""")
conn.commit()
conn.close()
export2 = db.get_handicap_export_data(db_path=DB)
fb = {f["player_name"] for f in export2.get("name_fallbacks") or []}
check("the id-less link is named in name_fallbacks",
      "ORPHAN, Nobody" in fb, str(fb))
check("…and the count rides along for the caller",
      export2["_debug"]["name_fallback_count"] == 1,
      str(export2["_debug"].get("name_fallback_count")))


print("\n== the read-only audit measures the same gap ==")
audit = db.audit_handicap_link_identity(db_path=DB)
check("the audit writes nothing and says so", audit["read_only"] is True)
check("it counts the one link with no customer_id",
      audit["links"]["no_customer_id"] == 1, str(audit["links"]))
check("it names the row rather than only tallying it",
      [r["player_name"] for r in audit["links"]["no_customer_id_rows"]]
      == ["ORPHAN, Nobody"])
check("it reports NAME DRIFT on the link label separately from coverage",
      audit["links"]["name_drift"] == 0, str(audit["links"]["name_drift_rows"]))
check("it flags a link that carries an id but no name label",
      audit["links"]["customer_id_but_no_name_label"] == 1)
check("it reports handicap_rounds that reach no customer_id",
      audit["rounds"]["player_names_not_resolvable"] == 1,
      str(audit["rounds"]["worst"]))


print("\n== the roster is THE roster (v2.410.0), and the send reads it ==")
conn = db.get_connection()
roster = db._event_roster_rows(conn, 9901)
conn.close()
names = sorted((r.get("name") or "") for r in roster)
check("the GG-RSVP-only player is on the roster with no order row",
      any((r.get("name") or "").lower() == "gus vasquez" for r in roster),
      str(names))
check("…carrying his customer_id, so he can be matched at all",
      any(r.get("customer_id") == 9003 for r in roster))
check("all four registrants are on it", len(roster) == 4, str(names))


print("\n== the send classifies every registrant, by customer_id ==")
sent_to = []
appmod.send_mail_graph = lambda **kw: (sent_to.append(kw.get("to_address")) or True)
client = appmod.app.test_client()
with client.session_transaction() as sess:
    sess["role"] = "manager"
resp = client.post("/api/handicaps/send-bulk-email",
                   json={"event_name": EVENT})
out = resp.get_json()
check("the send ran", resp.status_code == 200, str(out)[:300])
out = out or {}
check("all four registrants were counted, GG RSVP included",
      out.get("registered") == 4, f"registered={out.get('registered')}")
check("three cards went out", out.get("sent") == 3,
      f"sent={out.get('sent')} skipped={out.get('skipped_players')}")
skipped = {s["player"]: s["why"] for s in out.get("skipped_players") or []}
check("the drifted-name player was SENT, not called 'no handicap on record'",
      "michael.murphy@example.com" in sent_to and "Mike Murphy" not in skipped
      and "Michael Murphy" not in skipped,
      f"sent_to={sent_to} skipped={skipped}")
check("the null-label link was SENT too",
      "stuart.kirksey@example.com" in sent_to, str(sent_to))
check("the GG-RSVP-only player was SENT",
      "gus.vasquez@example.com" in sent_to, str(sent_to))
check("the one genuine no-index player is skipped AND named",
      "Nolan Index" in skipped, str(skipped))
check("…for the right reason",
      skipped.get("Nolan Index") == "no TGF handicap on record",
      str(skipped))
check("the buckets reconcile — nothing unaccounted",
      out.get("unaccounted") == 0,
      f"registered={out.get('registered')} accounted={out.get('accounted')}")
check("the unlinked handicap population is surfaced on the send",
      out.get("unlinked_handicap_count") == 1,
      str(out.get("unlinked_handicap_count")))


print("\n== MEMBERS-only filters by customer_id, not by a name string ==")
conn = db.get_connection()
# Nobody's profile name matches their link label now — under the old
# `first_name || ' ' || last_name = customer_name` join this would empty
# the send.
conn.execute("UPDATE customers SET first_name = 'Mikey' WHERE customer_id = 9001")
conn.execute("UPDATE customers SET current_player_status = 'inactive' "
             "WHERE customer_id = 9003")
conn.commit()
conn.close()
sent_to.clear()
resp = client.post("/api/handicaps/send-bulk-email",
                   json={"event_name": EVENT, "members_only": True})
out = resp.get_json() or {}
check("the renamed member still receives his card",
      "michael.murphy@example.com" in sent_to, str(sent_to))
check("the non-member is filtered out",
      "gus.vasquez@example.com" not in sent_to, str(sent_to))
check("…and counted as such rather than dropped",
      out.get("skipped_not_member", 0) >= 1, str(out))


print("\n== an unrecognised audience is REFUSED, never sent to ==")
sent_to.clear()
resp = client.post("/api/handicaps/send-bulk-email",
                   json={"event_name": "s9.99 No Such Event"})
check("an unknown event is a 400, not a silent full-roster blast",
      resp.status_code == 400, str(resp.get_json()))
check("…and nothing was sent", sent_to == [], str(sent_to))


print("\n== the class: no name-string join survives on the send path ==")
src = open("app.py", encoding="utf-8").read()
fn = src[src.index("def api_handicap_send_bulk_email"):]
fn = fn[:fn.index("# Routes — Participation Analysis")]
# Comments are stripped first: the fix is DOCUMENTED by quoting the query
# it replaced, and a naive substring search finds the explanation and
# calls it the defect.
fn = "\n".join(ln.split("#", 1)[0] if ln.lstrip().startswith("#") else ln
               for ln in fn.splitlines())
check("the route no longer builds its own roster from get_all_items",
      "get_all_items()" not in fn, "a fifth roster query is back")
check("the route reads _event_roster_rows",
      "_event_roster_rows" in fn)
check("no player_name→customer_name map survives",
      "player_to_customer" not in fn)
check("members-only no longer joins on first_name || ' ' || last_name",
      "first_name || ' ' || c.last_name" not in fn
      and "c.first_name || ' ' || c.last_name" not in fn)

try:
    os.unlink(DB)
except OSError:
    pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
