"""add_contact: the named single-contact exception to the sync's create scope.

Kerry 2026-09-21 — Britton Reger is a real customer whose last order was in
March, so the nightly sync's "recent" create scope correctly skips him and
just as correctly should not keep him off the list once Kerry names him.

Isolated from the DB layer on purpose: `tracker_contact_targets` is the seam,
and importing the real one drags in init_db's boot repairs.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import brevo

FAIL = []
def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + str(detail) if not cond else ""))
    if not cond: FAIL.append(label)

KNOWN = {"jbrittonreger@gmail.com": {
    "status": "prospect", "chapter": "San Antonio", "first_name": "Britton",
    "last_name": "Reger", "last_played": None, "importable": True}}
brevo.tracker_contact_targets = lambda db_path=None: dict(KNOWN)
brevo._dial = lambda db, key, db_path: None          # no dial → DEFAULT_LIST_ID
sent = []
brevo._import_missing = lambda key, rows, list_id, errors: (sent.extend(rows), len(rows))[1]

print("add_contact")
os.environ.pop("BREVO_API_KEY", None)
r = brevo.add_contact("jbrittonreger@gmail.com")
check("no API key is an error, not a crash", r.get("error", "").startswith("BREVO_API_KEY"), r)

os.environ["BREVO_API_KEY"] = "test-key"
check("empty email is refused", "error" in brevo.add_contact(""))
check("whitespace-only email is refused", "error" in brevo.add_contact("   "))

r = brevo.add_contact("typo@nowhere.example")
check("an address the Tracker does not know is REFUSED — a typo must not "
      "mint a contact", "not a customer email" in r.get("error", ""), r)
check("...and nothing was sent to Brevo", not sent, sent)

r = brevo.add_contact("JBrittonReger@Gmail.com", dry_run=True)
check("a known customer resolves, case-insensitively", "error" not in r, r)
check("dry run writes nothing", r.get("dry_run") is True and "created" not in r
      and not sent, (r, sent))
check("the new contact carries the name (the Insider greets by FIRSTNAME)",
      r["attributes"].get("FIRSTNAME") == "Britton"
      and r["attributes"].get("LASTNAME") == "Reger", r["attributes"])
check("it targets the TGF CONTACTS list", r.get("list_id") == brevo.DEFAULT_LIST_ID, r)

r = brevo.add_contact("jbrittonreger@gmail.com")
check("a real run imports exactly one row", r.get("created") == 1 and len(sent) == 1, (r, sent))
check("the row is shaped the way the sync's importer expects",
      sent[0].get("email") == "jbrittonreger@gmail.com"
      and isinstance(sent[0].get("attributes"), dict), sent)
check("no errors on the happy path", r.get("errors") == [], r)

print(("\nALL PASS" if not FAIL else f"\n{len(FAIL)} FAILURE(S): {FAIL}"))
sys.exit(1 if FAIL else 0)
