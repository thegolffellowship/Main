"""Tests for partner-request name resolution (Kerry 2026-07-30).

"Dan South should be recognized here as Daniel South. Are aliases at work
for the partner requests?" — they were not. The matcher did naive substring
comparison, and "dan south" is not a substring of "daniel south" (nor the
reverse), so the request fell through to "no roster match".

Run: python3 test_partner_matching.py
"""

import os
import sys

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


# No alias table in play unless a test asks for one.
db._PARTNER_ALIAS_CACHE.update({"at": 9e18, "map": {}})

ROSTER = ["Daniel South", "Mark Villa", "Orlando Kypuros", "Gus Vasquez",
          "Chuck Fehlis", "Pat Youngs", "Richard Palacios", "Larry Anthis"]


def find(req, roster=None, requester="Mark Villa"):
    return db._find_partner_name(req, roster or ROSTER, requester)


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
# brother. customer_aliases is the mechanism for that class.
check("an initial-changing nickname does NOT auto-resolve",
      find("Dick Palacios") is None, str(find("Dick Palacios")))
db._PARTNER_ALIAS_CACHE.update({"at": 9e18,
                                "map": {"dick palacios": "Richard Palacios"}})
try:
    check("...but a curated alias resolves it",
          find("Dick Palacios") == "Richard Palacios", str(find("Dick Palacios")))
finally:
    db._PARTNER_ALIAS_CACHE.update({"at": 9e18, "map": {}})

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

two_dans = ["Dan Smith", "Dan Jones", "Mark Villa"]
check("a bare first name shared by two players no longer picks one",
      db._find_partner_name("Dan", two_dans, "Mark Villa") is None,
      str(db._find_partner_name("Dan", two_dans, "Mark Villa")))

print("\n== curated aliases are consulted ==")

db._PARTNER_ALIAS_CACHE.update({"at": 9e18,
                                "map": {"skip vasquez": "Gus Vasquez"}})
try:
    check("an alias resolves to its canonical roster name",
          find("Skip Vasquez") == "Gus Vasquez", str(find("Skip Vasquez")))
    check("an unknown alias still returns nothing",
          find("Nobody Here") is None, str(find("Nobody Here")))
finally:
    db._PARTNER_ALIAS_CACHE.update({"at": 9e18, "map": {}})

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
