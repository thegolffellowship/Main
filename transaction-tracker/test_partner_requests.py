"""Partner-request rules (Kerry 2026-07-30 / 07-31), on the SA Championship.

First-come (rule 11) is the default: once a player is claimed in either
direction, later requests touching them are OUTRANKED. Five things beat it:

 1. A RECIPROCAL request is not a loser. "Chuck Fehlis -> Gus Vasquez" after
    "Gus Vasquez -> Chuck Fehlis" is the same pairing restated -> CONFIRMED.
 2. If someone PAID for another player, assume they should be paired.
 3. "A member can bring as many guests as they want and play with up to 3",
    so a host and three guests are one approved foursome, not three
    competing requests where the last two lose.
 4. GUESTS may join a group that is already claimed — "a system to give all
    guests the ability to feel the group out and play with who they want,
    but require the members to branch out, beyond a single player request."
    Membership is decided by the ROSTER, never by the order label.
 5. A manager can APPROVE any outranked request (rule 5 override).

In every case the request JOINS the existing group rather than displacing
anyone, and a FOURSOME is the hard ceiling.

Run: python3 test_partner_requests.py
"""
import os, sqlite3, sys, tempfile
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


def _refused(fn):
    try:
        fn()
        return False
    except ValueError:
        return True


# Force the name -> customer_id index to rebuild off THIS fixture DB.
db._PARTNER_IDENTITY_CACHE.update({"at": 0.0, "map": {}})
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-pr-"), "t.db")
conn = sqlite3.connect(tmp)
conn.executescript("""
 CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, chapter TEXT);
 CREATE TABLE event_aliases (alias_name TEXT, canonical_event_name TEXT);
 CREATE TABLE items (id INTEGER PRIMARY KEY, customer TEXT, customer_id INTEGER,
   item_name TEXT, holes TEXT, partner_request TEXT, order_date TEXT,
   created_at TEXT, notes TEXT, transaction_status TEXT, parent_item_id INTEGER,
   event_id INTEGER, order_id TEXT, customer_email TEXT, user_status TEXT);
 CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT,
   last_name TEXT, company_name TEXT, account_status TEXT,
   current_player_status TEXT);
 CREATE TABLE customer_aliases (id INTEGER PRIMARY KEY, customer_id INTEGER,
   customer_name TEXT, alias_type TEXT, alias_value TEXT);
""")
conn.execute("INSERT INTO events (id, item_name, chapter) VALUES "
             "(1,'TGF SAN ANTONIO CHAMPIONSHIP','San Antonio')")
# (customer, request, order_date, purchased-by note, order_id, email, member?)
#
# The real SA Championship shape, both halves of it:
#   * Jacob Williams is on DANIEL'S order — Daniel paid for his spot, and
#     only Jacob's row carries a "Purchased by" note. His host has to be
#     found from the shared order_id (Kerry 2026-07-31).
#   * Mark Villa and Orlando Kypuros bought their OWN 1st-Timer spots on
#     separate orders and both requested Dan South. Nobody paid for them,
#     so no host link exists — they are honored because they are GUESTS
#     ("give all guests the ability to feel the group out and play with
#     who they want, but require the members to branch out").
# Everyone else is a member, so first-come binds them.
ORD = "R900000001"
FIELD = [
    ("Gus Vasquez",     "Chuck Fehlis",   "2026-07-15", None, "R1", "gus@x.com", True),
    ("Pat Youngs",      "John White",     "2026-07-24", None, "R2", "pat@x.com", True),
    ("Chuck Fehlis",    "Gus Vasquez",    "2026-07-27", None, "R3", "chuck@x.com", True),
    ("Richard Palacios","Larry Anthis",   "2026-07-28", None, "R4", "rich@x.com", True),
    ("Larry Anthis",    "Michael Murphy", "2026-07-29", None, "R5", "larry@x.com", True),
    ("Michael Murphy",  None,             "2026-07-29", None, "R6", "mike@x.com", True),
    ("Daniel South",    None,             "2026-07-19", None, ORD, "dan@x.com", True),
    ("Mark Villa",      "Dan South",      "2026-07-31", None, "R7", "villa@x.com", False),
    ("Orlando Kypuros", "Dan South",      "2026-07-31", None, "R8", "ok@x.com", False),
    ("Jacob Williams",  None,             "2026-07-31", "Purchased by Daniel South",
     ORD, None, False),
]
for i, (nm, req, od, note, oid, mail, member) in enumerate(FIELD, start=1):
    # Both a member and a guest can be labelled "1ST TIMER" on the order —
    # the roster is what decides (Kerry 2026-07-30), so the label is
    # deliberately identical for Villa (guest) and Murphy (member).
    conn.execute("INSERT INTO items (id, customer, customer_id, item_name, holes,"
                 " partner_request, order_date, created_at, notes,"
                 " transaction_status, order_id, customer_email, user_status)"
                 " VALUES (?,?,?,?,'18',?,?,?,?, 'active',?,?, '1ST TIMER')",
                 (i, nm, i, 'TGF SAN ANTONIO CHAMPIONSHIP', req, od, od, note,
                  oid, mail))
    parts = nm.split()
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name,"
                 " account_status, current_player_status) VALUES (?,?,?, 'active', ?)",
                 (i, parts[0], parts[-1],
                  "active_member" if member else "active_guest"))
# "Dan South" is a real alias on Daniel South's PROFILE (customer_id 7), so
# the guests' requests resolve id-to-id rather than by string resemblance
# (Kerry 2026-07-30: "reference actual aliases in customer_id profiles").
conn.execute("INSERT INTO customer_aliases (customer_id, customer_name,"
             " alias_type, alias_value) VALUES (7,'Daniel South','name','Dan South')")
conn.commit(); conn.close()

out = db.get_event_partner_requests(1, db_path=tmp)["requests"]
by = {r["requester"]: r for r in out}
print("\n== reciprocal requests are CONFIRMED, not outranked ==")
check("Gus -> Chuck is the first claim and stays active",
      by["Gus Vasquez"]["status"] == "active", str(by["Gus Vasquez"]))
check("Chuck -> Gus is CONFIRMED, not OUTRANKED",
      by["Chuck Fehlis"]["status"] == "confirmed", str(by["Chuck Fehlis"]))
check("...and is not flagged locked_out", not by["Chuck Fehlis"]["locked_out"])
check("...with a reason that reads as agreement",
      "confirms it" in (by["Chuck Fehlis"]["locked_reason"] or ""),
      str(by["Chuck Fehlis"]["locked_reason"]))

print("\n== a genuine conflict is still outranked ==")
check("Palacios -> Anthis claims first", by["Richard Palacios"]["status"] == "active")
check("Anthis -> Murphy is genuinely outranked (different partner)",
      by["Larry Anthis"]["status"] == "outranked", str(by["Larry Anthis"]))

print("\n== paying for someone implies a pairing ==")
check("Jacob Williams gets an IMPLIED request despite writing none",
      "Jacob Williams" in by and by["Jacob Williams"]["implied"],
      str(by.get("Jacob Williams")))
check("...resolved to the person who paid",
      by["Jacob Williams"]["partner"] == "Daniel South",
      str(by.get("Jacob Williams", {}).get("partner")))

print("\n== the host's guest, and the guests who bought their own spots ==")
GUESTS = ("Mark Villa", "Orlando Kypuros", "Jacob Williams")
for g in GUESTS:
    check(f"{g} is NOT outranked against Daniel South",
          not by[g]["locked_out"] and by[g]["status"] != "outranked",
          f"{by[g]['status']} / {by[g]['locked_reason']}")
    check(f"...and {g} resolves 'Dan South' to Daniel South",
          by[g]["partner"] == "Daniel South", str(by[g]["partner"]))

# Jacob is on Daniel's ORDER — that is the host link, and his row is the
# only one with a "Purchased by" note.
check("the bought-for guest is flagged as a host group",
      by["Jacob Williams"]["host_group"], str(by["Jacob Williams"]))
check("...and the self-paying guests are NOT — nobody bought their spot",
      not by["Mark Villa"]["host_group"] and not by["Orlando Kypuros"]["host_group"],
      "self-paying guests were wrongly linked to a host")

# Villa and Kypuros are honored purely because they are GUESTS (Kerry
# 2026-07-31). Villa claims Daniel first, so his is an ordinary win;
# Kypuros arrives after Daniel is claimed and is honored anyway.
check("the first guest to claim Daniel is plain ACTIVE",
      by["Mark Villa"]["status"] == "active", str(by["Mark Villa"]["status"]))
check("a guest arriving after the claim is GUEST OK, not outranked",
      by["Orlando Kypuros"]["status"] == "guest",
      f"{by['Orlando Kypuros']['status']} / {by['Orlando Kypuros']['locked_reason']}")
check("...with a reason that names the guest rule",
      "Guest request" in (by["Orlando Kypuros"]["locked_reason"] or ""),
      str(by["Orlando Kypuros"]["locked_reason"]))
check("the bought-for guest is CONFIRMED via the host group",
      by["Jacob Williams"]["status"] == "confirmed",
      str(by["Jacob Williams"]["status"]))

# The order LABEL is "1ST TIMER" for everyone in this fixture — only the
# roster distinguishes them (Kerry 2026-07-30).
check("membership comes from the roster, not the 1ST TIMER label",
      by["Larry Anthis"]["requester_is_member"]
      and not by["Mark Villa"]["requester_is_member"],
      f"{by['Larry Anthis']['requester_is_member']} / "
      f"{by['Mark Villa']['requester_is_member']}")

print("\n== MEMBERS are held to first-come and must branch out ==")
check("a member's request onto a claimed player is OUTRANKED",
      by["Larry Anthis"]["status"] == "outranked", str(by["Larry Anthis"]))
check("...with a reason that says members branch out",
      "branch out" in (by["Larry Anthis"]["locked_reason"] or ""),
      str(by["Larry Anthis"]["locked_reason"]))

print("\n== a manager can APPROVE an outranked request ==")
appr = db.set_partner_request_approval(1, "Larry Anthis", True,
                                       approved_by="admin", db_path=tmp)["requests"]
byA = {r["requester"]: r for r in appr}
check("the approved request is honored", byA["Larry Anthis"]["status"] == "approved",
      str(byA["Larry Anthis"]))
check("...and is no longer flagged locked_out",
      not byA["Larry Anthis"]["locked_out"])
check("...with a reason naming the manager override",
      "Approved by a manager" in (byA["Larry Anthis"]["locked_reason"] or ""),
      str(byA["Larry Anthis"]["locked_reason"]))
check("...and the earlier request it lost to is UNTOUCHED — nobody is displaced",
      byA["Richard Palacios"]["status"] == "active"
      and not byA["Richard Palacios"]["locked_out"],
      str(byA["Richard Palacios"]))
check("approving a player who isn't on the roster is refused",
      _refused(lambda: db.set_partner_request_approval(
          1, "Ghost Player", True, db_path=tmp)))
rev = {r["requester"]: r for r in db.set_partner_request_approval(
    1, "Larry Anthis", False, db_path=tmp)["requests"]}
check("revoking the approval puts it back to OUTRANKED",
      rev["Larry Anthis"]["status"] == "outranked", str(rev["Larry Anthis"]))

print("\n== a foursome is still the ceiling, approval or not ==")
conn = sqlite3.connect(tmp)
conn.execute("INSERT INTO items (id, customer, customer_id, item_name, holes,"
             " partner_request, order_date, created_at, notes,"
             " transaction_status, order_id, user_status)"
             " VALUES (99,'Fourth Guest',99,'TGF SAN ANTONIO CHAMPIONSHIP','18',"
             "'Dan South','2026-08-01','2026-08-01',NULL,'active','R99','GUEST')")
conn.execute("INSERT INTO customers (customer_id, first_name, last_name,"
             " account_status, current_player_status)"
             " VALUES (99,'Fourth','Guest','active','active_guest')")
conn.commit(); conn.close()
by2 = {r["requester"]: r for r in db.get_event_partner_requests(1, db_path=tmp)["requests"]}
check("a FIFTH player on Daniel's group is outranked even though he's a guest",
      by2["Fourth Guest"]["status"] == "outranked", str(by2["Fourth Guest"]))
check("...with a reason naming the foursome limit",
      "foursome" in (by2["Fourth Guest"]["locked_reason"] or ""),
      str(by2["Fourth Guest"]["locked_reason"]))
check("approving him STILL cannot make five",
      {r["requester"]: r for r in db.set_partner_request_approval(
          1, "Fourth Guest", True, db_path=tmp)["requests"]
       }["Fourth Guest"]["status"] == "outranked")
db.set_partner_request_approval(1, "Fourth Guest", False, db_path=tmp)
check("the first three are unaffected",
      all(by2[g]["status"] in ("active", "guest", "confirmed")
          and not by2[g]["locked_out"] for g in GUESTS),
      str([(g, by2[g]["status"]) for g in GUESTS]))

print("\n== unmatched text still surfaces for the manager ==")
check("Pat Youngs -> John White stays unmatched (not on roster)",
      not by["Pat Youngs"]["matched"], str(by["Pat Youngs"]))

print("\n== a manager can ADD a request that never came in ==")
# Kerry 2026-07-30: "I also need the ability to add a Playing Partner
# Request in the requests drop down."
check("Michael Murphy has no request to begin with",
      "Michael Murphy" not in by)
added = db.set_partner_request_match(1, "Michael Murphy", "Pat Youngs",
                                     db_path=tmp)["requests"]
by3 = {r["requester"]: r for r in added}
check("...and now he has one", "Michael Murphy" in by3, str(list(by3)))
check("...pointed at the player the manager picked",
      by3.get("Michael Murphy", {}).get("partner") == "Pat Youngs",
      str(by3.get("Michael Murphy")))
check("...badged as manager-added, not as a signup request",
      by3["Michael Murphy"]["added"] and by3["Michael Murphy"]["manual"],
      str(by3["Michael Murphy"]))
check("...and it does NOT jump the queue — it sits at his signup position",
      list(by3).index("Michael Murphy") < list(by3).index("Mark Villa"),
      f"{list(by3)}")
check("adding one for a player who isn't on the roster is refused",
      _refused(lambda: db.set_partner_request_match(
          1, "Ghost Player", "Pat Youngs", db_path=tmp)))
check("clearing it removes the request again",
      "Michael Murphy" not in {
          r["requester"] for r in db.set_partner_request_match(
              1, "Michael Murphy", None, db_path=tmp)["requests"]})

print("\n== the GENERATOR builds the same groups the panel promises ==")
# A panel that badges the guests GUEST OK / CONFIRMED while the generator
# splits them off is worse than no badge at all.
rows = [dict(customer=nm, notes=note, order_id=oid, customer_email=mail)
        for nm, req, od, note, oid, mail, member in FIELD]
roster_names = [f[0] for f in FIELD]
host_of = db._host_of_map(rows, roster_names)
check("only the bought-for guest has a host",
      host_of == {"jacob williams": "daniel south"}, str(host_of))

pmap = {nm: req for nm, req, od, note, oid, mail, member in FIELD}
members = {nm: member for nm, req, od, note, oid, mail, member in FIELD}
# What the generator does: host units first, then guest/approved pairs.
units = db._host_units(host_of, roster_names)
guest_pairs = [(nm, db._find_partner_name(pmap[nm], roster_names, nm))
               for nm in roster_names
               if pmap.get(nm) and not members[nm]]
units = db._merge_name_units(units, [(a, b) for a, b in guest_pairs if b])
check("one bound unit is built, capped at a foursome",
      len(units) == 1 and len(units[0]) == 4, str(units))

groups = db._random_groups(roster_names, pmap, {}, True, host_units=units)
grp = next((g for g in groups if "Daniel South" in g), [])
check("the generator puts Daniel South and all three guests in ONE group",
      all(g in grp for g in GUESTS), str(grp))
check("...and that group is a foursome, not a fivesome",
      len(grp) == 4, str(grp))

# Match Play still wins a member off the bound group (rule 8).
mp = db._random_groups(roster_names, pmap, {}, True,
                       fixed_units=[["Mark Villa", "Gus Vasquez"]],
                       host_units=units)
mp_grp = next((g for g in mp if "Mark Villa" in g), [])
check("Match Play still outranks the bound group for a shared player",
      "Gus Vasquez" in mp_grp, str(mp_grp))

# Locked names protect the whole unit from the swap improver.
locked = db._partner_locked_names(roster_names, pmap, True, host_units=units)
check("every bound-group member is locked against swaps",
      all(g in locked for g in GUESTS) and "Daniel South" in locked,
      str(sorted(locked)))

# An APPROVED member request joins the same way in the generator.
appr_units = db._merge_name_units(
    db._host_units(host_of, roster_names),
    [("Richard Palacios", "Larry Anthis"), ("Larry Anthis", "Michael Murphy")])
u = next((u for u in appr_units if "Larry Anthis" in u), [])
check("an approved request joins the group that claimed its partner",
      set(u) == {"Richard Palacios", "Larry Anthis", "Michael Murphy"}, str(u))

print("\n== the generator honors requests in SIGNUP ORDER, like the panel ==")
# Kerry 2026-07-31, "Nor is it honoring requests": the sheet split
# Richard Palacios from Larry Anthis even though the panel showed that
# request active. Cause — the generator built PRIVILEGED units (guest /
# approved) FIRST, so the later approved "Anthis -> Murphy" claimed Larry
# before the earlier "Palacios -> Anthis" ever ran. Walking signup order
# lets Palacios claim him and the approval JOIN that unit.
SIGNUP = {                      # insertion order IS signup order
    "Gus Vasquez":      "Chuck Fehlis",
    "Chuck Fehlis":     "Gus Vasquez",
    "Richard Palacios": "Larry Anthis",
    "Larry Anthis":     "Michael Murphy",   # approved, and LATER
    "Mark Villa":       "Daniel South",     # guest
    "Orlando Kypuros":  "Daniel South",     # guest
}
FIELD_NAMES = ["Richard Palacios", "Larry Anthis", "Michael Murphy",
               "Gus Vasquez", "Chuck Fehlis", "Daniel South", "Mark Villa",
               "Orlando Kypuros", "Jacob Williams", "Pat Youngs"]
_APPROVED = {"larry anthis"}
_GUESTS = {"Mark Villa", "Orlando Kypuros", "Jacob Williams"}
_HOSTU = [["Daniel South", "Jacob Williams"]]


def _priv(n):
    return db._pair_key_name(n) in _APPROVED or n in _GUESTS


UNITS = db._build_bound_units(
    FIELD_NAMES, SIGNUP, _HOSTU, _priv,
    lambda t, w: db._find_partner_name(t, FIELD_NAMES, w), 4)
_anthis = next((u for u in UNITS if "Larry Anthis" in u), [])
check("the EARLIER request keeps its claim — Palacios stays with Anthis",
      "Richard Palacios" in _anthis, str(UNITS))
check("...and the approved later request JOINS rather than displacing",
      "Michael Murphy" in _anthis, str(_anthis))
check("...making a threesome, not two broken pairs", len(_anthis) == 3, str(_anthis))
_south = next((u for u in UNITS if "Daniel South" in u), [])
check("the host foursome is intact", len(_south) == 4 and
      all(g in _south for g in ("Jacob Williams", "Mark Villa", "Orlando Kypuros")),
      str(_south))
check("the reciprocal pair is intact",
      "Chuck Fehlis" in next((u for u in UNITS if "Gus Vasquez" in u), []), str(UNITS))
check("nobody appears in two units",
      len([n for u in UNITS for n in u]) == len({n for u in UNITS for n in u}),
      str(UNITS))
check("a player with no request is left free",
      not any("Pat Youngs" in u for u in UNITS), str(UNITS))

# A plain MEMBER request onto a claimed player still loses — that is the
# rule the approval exists to override.
NOAPPROVE = db._build_bound_units(
    FIELD_NAMES, SIGNUP, _HOSTU, lambda n: n in _GUESTS,
    lambda t, w: db._find_partner_name(t, FIELD_NAMES, w), 4)
_a2 = next((u for u in NOAPPROVE if "Larry Anthis" in u), [])
check("without the approval, the member's later request is dropped",
      "Michael Murphy" not in _a2 and "Richard Palacios" in _a2, str(_a2))

# The ceiling still holds when a join would overflow.
TIGHT = dict(SIGNUP)
TIGHT["Pat Youngs"] = "Daniel South"
UNITS5 = db._build_bound_units(
    FIELD_NAMES, TIGHT, _HOSTU, lambda n: True,
    lambda t, w: db._find_partner_name(t, FIELD_NAMES, w), 4)
_s5 = next((u for u in UNITS5 if "Daniel South" in u), [])
check("a 5th cannot join a full group even when privileged",
      len(_s5) == 4 and "Pat Youngs" not in _s5, str(_s5))

print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL PARTNER-REQUEST TESTS PASSED")
