"""EVERY table that names a person carries the person's id.

Kerry 2026-09-18: "I thought we had specifically made the 1st commandment
to be customer_id tying to everything... EVERY person gets a customer_id,
no matter what their role is... customer_id is king. There are other top
level ids too, but everything remotely related to a customer needs to be
tied to that customer."

This builds the REAL schema (init_db on a scratch file) and checks every
person-naming column has a sibling id column: `customer_id`, or
`<prefix>_id` / `<prefix>_customer_id` for `<prefix>_name` (player1_name
-> player1_id, winner_name -> winner_id). A new table that names a person
without an id fails this test. The allow-list is empty and must stay so.

Run: python3 test_customer_id_everywhere.py
"""
import os, sys, io, contextlib, logging, sqlite3, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db"); os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db                      # noqa: E402
    db.init_db(DB)

PERSON = {"player_name", "customer_name", "customer", "member_name", "golfer",
          "golfer_name", "payee", "payee_name", "recipient_name", "member"}
NON_PERSON_PREFIXES = {"event", "course", "tee", "item", "account", "category", "agent",
                       "entity", "tag", "template", "campaign", "facility", "chapter",
                       "pool", "list", "file", "sheet", "short", "display", "alias",
                       "canonical_event", "matched_event", "merchant", "vendor",
                       "bank", "product", "session", "widget", "round", "portal"}
conn = sqlite3.connect(DB)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                     "AND name NOT LIKE 'sqlite_%'")]
gaps = []
for t in sorted(tables):
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
    ids = {c for c in cols if c == "customer_id" or c.endswith("_customer_id") or c.endswith("_id")}
    for c in sorted(cols):
        if c in PERSON:
            if "customer_id" not in cols and "player_id" not in cols:
                gaps.append((t, c))
        elif c.endswith("_name") and c[:-5] not in NON_PERSON_PREFIXES and c != "name":
            pre = c[:-5]
            if not ({f"{pre}_id", f"{pre}_customer_id", "customer_id"} & cols):
                gaps.append((t, c))
print(f"{len(tables)} tables scanned")
for t, c in gaps:
    print(f"  GAP  {t}.{c} has no sibling id column")
print("ALL PASS" if not gaps else f"{len(gaps)} GAP(S)")
try: os.unlink(DB)
except OSError: pass
sys.exit(1 if gaps else 0)
