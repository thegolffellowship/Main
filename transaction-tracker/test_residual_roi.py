"""Residual ROI: what a campaign's leads REFERRED, on its own line.

Kerry 2026-09-21: "ROAS to me, includes the people that Leads
referred/brought/became members and anything they purchase in the
future ... I like the 'direct' and '+ referred' idea."
"""
import os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FAIL = []
def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + str(detail) if not cond else ""))
    if not cond: FAIL.append(label)

from email_parser.campaigns import referred_lead_rows


def conn_with(rows, memberships, with_tables=True):
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
            first_name TEXT, last_name TEXT, referred_by_customer_id INTEGER);
    """)
    if with_tables:
        c.execute("CREATE TABLE customer_memberships (id INTEGER PRIMARY KEY "
                  "AUTOINCREMENT, customer_id INTEGER, started_at TEXT)")
    for cid, f, l, ref in rows:
        c.execute("INSERT INTO customers VALUES (?,?,?,?)", (cid, f, l, ref))
    if with_tables:
        for cid in memberships:
            c.execute("INSERT INTO customer_memberships (customer_id, started_at) "
                      "VALUES (?, '2026-09-13')", (cid,))
    c.commit()
    return c

# 709 Justin (a campaign lead) referred 829 Ty (member) and 830 Nate (not).
# 821 Guillermo (member) was referred by 31 Robert, who is NOT in this campaign.
# 831 Chain was referred by Ty — a referral of a referral.
PEOPLE = [
    (709, "Justin", "Angelone", None),
    (829, "Ty", "Bubela", 709),
    (830, "Nate", "Nomember", 709),
    (831, "Chain", "Reaction", 829),
    (31, "Robert", "Straiton", None),
    (821, "Guillermo", "Arevalo", 31),
]
MEMBERS = [829, 831, 821]
LEADS = [{"customer_id": 709}]

print("Who the residual picks up")
out = referred_lead_rows(LEADS, conn_with(PEOPLE, MEMBERS))
ids = sorted(r["customer_id"] for r in out)
check("a lead's referral who JOINED counts", 829 in ids, ids)
check("a lead's referral who did NOT join does not — membership is the gate",
      830 not in ids, ids)
check("a referral of a REFERRAL does not — one hop only", 831 not in ids, ids)
check("somebody else's referral does not", 821 not in ids, ids)
check("exactly one person credited", ids == [829], ids)
check("the row is shaped for campaign_value (customer_id is all it reads)",
      out and "customer_id" in out[0], out)
check("...and carries who referred them, for the audit",
      out and out[0].get("referred_by_customer_id") == 709, out)

print("Never double-counted")
both = referred_lead_rows([{"customer_id": 709}, {"customer_id": 829}],
                          conn_with(PEOPLE, MEMBERS))
check("someone already IN the campaign's leads is not also residual — "
      "they are direct value",
      all(r["customer_id"] != 829 for r in both), both)

print("Degrading safely")
check("a campaign with no customer ids has no residual",
      referred_lead_rows([{"customer_id": None}], conn_with(PEOPLE, MEMBERS)) == [])
check("an empty lead set has no residual",
      referred_lead_rows([], conn_with(PEOPLE, MEMBERS)) == [])
check("a database with no memberships table loses the residual, never the ROI",
      referred_lead_rows(LEADS, conn_with(PEOPLE, MEMBERS, with_tables=False)) == [])

print("The '+ referred' line keeps DIRECT untouched")
import email_parser.campaigns as C
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "email_parser/campaigns.py")).read()
check("the direct roi block is still computed from `value` alone",
      'if value and spend:' in src, "")
check("the residual is a SEPARATE key, never merged into roi",
      '"value_referred": value_referred, "roi_referred": roi_referred' in src)
check("the combined total is offered so the page can toggle",
      '"total_roas_margin"' in src and '"total_margin"' in src)

print(f"\n{len(FAIL)} FAILURE(S): {FAIL}" if FAIL else "\nALL PASS")
sys.exit(1 if FAIL else 0)
