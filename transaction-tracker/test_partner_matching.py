"""Tests for partner-request name resolution (Kerry 2026-07-30).

"Dan South should be recognized here as Daniel South. Are aliases at work
for the partner requests?" — they were not. The matcher did naive substring
comparison, and "dan south" is not a substring of "daniel south" (nor the
reverse), so the request fell through to "no roster match".

Follow-up, same day: "For the pairings request alias thing, why not just
reference actual aliases in customer_id profiles?" — so the alias rung no
longer compares name strings at all. It resolves BOTH sides to a
customer_id (canonical profile name + every customer_aliases row carrying
that id) and matches id-to-id, which is guiding principle 6.

Run: python3 test_partner_matching.py
"""

import os
import sqlite3
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def set_identity(mapping):
    """Pin the name -> customer_id index (skips the DB read)."""
    db._PARTNER_IDENTITY_CACHE.update({"at": 9e18, "map": dict(mapping)})


def clear_identity():
    # A far-future "at" with an empty map would re-read the DB (the cache
    # only short-circuits on a NON-empty map), so park a harmless entry.
    set_identity({"__none__": -1})


clear_identity()

ROSTER = ["Daniel South", "Mark Villa", "Orlando Kypuros", "Gus Vasquez",
          "Chuck Fehlis", "Pat Youngs", "Richard Palacios", "Larry Anthis"]


def find(req, roster=None, requester="Mark Villa", roster_ids=None):
    return db._find_partner_name(req, roster or ROSTER, requester,
                                 roster_ids=roster_ids)


print("\n== the reported case ==")

check("'Dan South' resolves to Daniel South", find("Dan South") == "Daniel South",
      str(find("Dan South")))
check("'Dan South' resolves for the other requester too",
      find("Dan South", requester="Orlando Kypuros") == "Daniel South")
check("the old substring matcher genuinely could not do this",
      "dan south" not in "daniel south" and "daniel south" not in "dan south")

print("\n== nickname class, generally ==")

# Surname + first initial. Covers the shortening class — Dan/Daniel,
# Matt/Matthew, Rob/Robert, Chris/Christopher — because the initial is
# unchanged.
for req, want in [("Daniel South", "Daniel South"),
                  ("daniel south", "Daniel South"),
                  ("  Daniel   South  ", "Daniel South"),
                  ("Rich Palacios", "Richard Palacios"),
                  ("Larry Anthis", "Larry Anthis"),
                  ("Chuck Fehlis", "Chuck Fehlis")]:
    check(f"'{req}' -> {want}", find(req) == want, str(find(req)))

# It deliberately does NOT cover nicknames that CHANGE the initial —
# Dick/Richard, Bill/William, Jack/John, Peggy/Margaret. Guessing those
# would mean matching on surname alone, which is how you pair the wrong
# brother. The customer_id profile is the mechanism for that class.
check("an initial-changing nickname does NOT auto-resolve",
      find("Dick Palacios") is None, str(find("Dick Palacios")))
set_identity({"dick palacios": 7, "richard palacios": 7})
try:
    check("...but the same customer_id resolves it",
          find("Dick Palacios") == "Richard Palacios", str(find("Dick Palacios")))
    check("a DIFFERENT customer_id is a different person, so no match",
          db._find_partner_name("Dick Palacios", ROSTER, "Mark Villa",
                                roster_ids={"Richard Palacios": 99}) is None,
          str(db._find_partner_name("Dick Palacios", ROSTER, "Mark Villa",
                                    roster_ids={"Richard Palacios": 99})))
finally:
    clear_identity()

print("\n== the roster's own customer_id is authoritative ==")

# Two people can share a display name. When the caller knows which
# customer_id is actually on the roster, that id — not the name index —
# decides. This is the whole point of resolving through profiles.
set_identity({"skip vasquez": 12, "gus vasquez": 12})
try:
    check("roster_ids agreeing with the profile resolves",
          find("Skip Vasquez", roster_ids={"Gus Vasquez": 12}) == "Gus Vasquez",
          str(find("Skip Vasquez", roster_ids={"Gus Vasquez": 12})))
    check("roster_ids naming a different person blocks the match",
          find("Skip Vasquez", roster_ids={"Gus Vasquez": 55}) is None,
          str(find("Skip Vasquez", roster_ids={"Gus Vasquez": 55})))
    check("roster_ids for OTHER players don't interfere",
          find("Skip Vasquez", roster_ids={"Mark Villa": 3}) == "Gus Vasquez")
finally:
    clear_identity()

print("\n== exact match still wins, and self-requests are ignored ==")

check("a requester never matches themselves",
      find("Mark Villa", requester="Mark Villa") is None,
      str(find("Mark Villa", requester="Mark Villa")))
check("first-name-only still works when unambiguous",
      find("Gus") == "Gus Vasquez", str(find("Gus")))

print("\n== AMBIGUITY MUST NOT RESOLVE ==")

# Two Souths: the generator must not pick one. A wrong pairing is worse
# than "no roster match — fix", which puts a dropdown in front of a human.
two = ROSTER + ["Danny South"]
check("two players sharing surname + initial yield NO match",
      db._find_partner_name("Dan South", two, "Mark Villa") is None,
      str(db._find_partner_name("Dan South", two, "Mark Villa")))
check("...but the exact full name still resolves cleanly",
      db._find_partner_name("Danny South", two, "Mark Villa") == "Danny South")
check("...and so does the other exact name",
      db._find_partner_name("Daniel South", two, "Mark Villa") == "Daniel South")

# ...and the customer_id rung breaks that tie, because the id says which
# South the requester meant.
set_identity({"dan south": 41, "daniel south": 41, "danny south": 42})
try:
    check("customer_id disambiguates two same-key Souths",
          db._find_partner_name("Dan South", two, "Mark Villa") == "Daniel South",
          str(db._find_partner_name("Dan South", two, "Mark Villa")))
finally:
    clear_identity()

two_dans = ["Dan Smith", "Dan Jones", "Mark Villa"]
check("a bare first name shared by two players no longer picks one",
      db._find_partner_name("Dan", two_dans, "Mark Villa") is None,
      str(db._find_partner_name("Dan", two_dans, "Mark Villa")))

print("\n== the index is built from customer_id profiles ==")

fd, tmp_db = tempfile.mkstemp(suffix=".db")
os.close(fd)
try:
    conn = sqlite3.connect(tmp_db)
    conn.executescript(
        """
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
                                first_name TEXT, last_name TEXT,
                                company_name TEXT, account_status TEXT);
        CREATE TABLE customer_aliases (id INTEGER PRIMARY KEY,
                                       customer_id INTEGER,
                                       customer_name TEXT,
                                       alias_type TEXT, alias_value TEXT);
        INSERT INTO customers VALUES
            (1, 'Daniel', 'South',  NULL, 'active'),
            (2, 'Gus',    'Vasquez', NULL, 'active'),
            (3, 'Chris',  'Martin', NULL, 'active'),
            (4, 'Chris',  'Martin', NULL, 'active');
        INSERT INTO customer_aliases (customer_id, customer_name, alias_type, alias_value)
        VALUES (1, 'Daniel South', 'name', 'Dan South'),
               (1, 'Daniel South', 'name', 'Danny South'),
               (2, 'Gus Vasquez',  'name', 'Skip Vasquez'),
               (NULL, 'Nobody',    'name', 'Orphan Alias');
        """
    )
    conn.commit()
    conn.close()

    db._PARTNER_IDENTITY_CACHE.update({"at": 0.0, "map": {}})
    idx = db._partner_identity_map(tmp_db)

    check("canonical profile names are indexed", idx.get("daniel south") == 1,
          str(idx.get("daniel south")))
    check("alias values resolve to the SAME customer_id",
          idx.get("dan south") == 1 and idx.get("danny south") == 1,
          f"{idx.get('dan south')} / {idx.get('danny south')}")
    check("a second person's alias keeps its own id",
          idx.get("skip vasquez") == 2, str(idx.get("skip vasquez")))
    check("two real people sharing a name are dropped, not guessed",
          "chris martin" not in idx, str(idx.get("chris martin")))
    check("an alias with no customer_id is ignored",
          "orphan alias" not in idx, str(idx.get("orphan alias")))

    # End to end against the same DB: the alias rung resolves the request
    # even though the strings share nothing beyond the surname.
    db._PARTNER_IDENTITY_CACHE.update({"at": 0.0, "map": {}})
    got = db._find_partner_name("Skip Vasquez", ROSTER, "Mark Villa",
                                db_path=tmp_db)
    check("'Skip Vasquez' -> Gus Vasquez straight off the profile",
          got == "Gus Vasquez", str(got))
finally:
    os.unlink(tmp_db)
    clear_identity()

print("\n== nothing blows up on junk ==")

for junk in ["", "   ", None, "???", "a"]:
    try:
        r = db._find_partner_name(junk, ROSTER, "Mark Villa")
        check(f"junk input {junk!r} returns cleanly", r is None or r in ROSTER, str(r))
    except Exception as e:
        check(f"junk input {junk!r} does not raise", False, str(e))

check("an empty roster returns nothing",
      db._find_partner_name("Dan South", [], "Mark Villa") is None)

print("\n== multi-name requests keep their existing behaviour ==")

# "Dan Other or Ed Fifth" — people name more than one partner. Rule 1
# honors only one, so the matcher takes the FIRST and the caller flags
# candidates>1 for the manager. Uniqueness must NOT apply here, or the
# multi-name flow silently stops matching anything.
multi = ["Dan Other", "Ed Fifth", "Gil Seventh"]
check("a multi-name request returns the first named player",
      db._find_partner_name("Dan Other or Ed Fifth", multi, "Gil Seventh")
      == "Dan Other",
      str(db._find_partner_name("Dan Other or Ed Fifth", multi, "Gil Seventh")))
check("order within the request is respected",
      db._find_partner_name("Ed Fifth or Dan Other", multi, "Gil Seventh")
      == "Ed Fifth")

# The OTHER direction — a fragment matching several roster names — is
# genuine ambiguity and must still refuse.
check("a fragment matching two roster names still refuses",
      db._find_partner_name("Dan", ["Dan Smith", "Dan Jones"], "X") is None)

print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL PARTNER-MATCHING TESTS PASSED")
