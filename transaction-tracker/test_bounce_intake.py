"""
Bounce intake (CA #688, Kerry 2026-09-25: "Deal with this."): an Exchange
non-delivery report marks the address undeliverable and raises one COO
action item; transient failures are only logged. Run: python3 test_bounce_intake.py
"""
import contextlib
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402
from email_parser.bounces import parse_ndr, process_bounces  # noqa: E402

FAILS = 0


def check(label, cond, detail=""):
    global FAILS
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  -> {detail}"))
    if not cond:
        FAILS += 1


# The shape Exchange Online sends (trimmed from the 9/25 Hayden Cooper NDR).
NDR_HTML = """<html><body>
<p>Your message to <b>hayden@roofrevivecrs.com</b> couldn't be delivered.</p>
<p>roofrevivecrs.com wasn't found at roofrevivecrs.com.</p>
<p>admin&nbsp;&nbsp;Office 365&nbsp;&nbsp;roofrevivecrs.com<br>Action Required Recipient</p>
<p>Diagnostic information for administrators:</p>
<p>Generating server: SA1PR12MB1234.namprd12.prod.outlook.com<br>
hayden@roofrevivecrs.com<br>
Remote server returned '550 5.1.2 SMTP; 550 5.1.2 Domain not found'</p>
<p>Original message headers: From: admin@thegolffellowship.com</p>
</body></html>"""

NDR_TRANSIENT = ("Delivery is delayed to these recipients or groups:\n"
                 "Delivery has failed to these recipients or groups:\n"
                 "Pat Guy <pat@fullbox.com>\n"
                 "Remote server returned '452 4.2.2 Mailbox full'")


def mail(uid, subject, frm, html="", text=""):
    return {"uid": uid, "subject": subject, "from": frm,
            "date": "2026-09-25T14:00:05Z", "html": html, "text": text}


def main():
    print("parse_ndr")
    n = parse_ndr("Undeliverable: One last note from TGF",
                  "MicrosoftExchange329e71ec88ae4615bbc36ab6ce41109e@thegolffellowship.com", NDR_HTML)
    check("reads the rejected address", n and n["recipient"] == "hayden@roofrevivecrs.com", n)
    check("reads 550 / 5.1.2 and calls it permanent",
          n and n["code"] == "550" and n["enhanced"] == "5.1.2" and n["permanent"], n)
    check("keeps the server's words", n and "domain not found" in n["detail"].lower(), n)
    t = parse_ndr("Undeliverable: Your pairings", "postmaster@outlook.com", "", )
    check("an NDR that names no recipient is ignored", t is None, t)
    t = parse_ndr("Undeliverable: Your pairings", "postmaster@outlook.com", NDR_TRANSIENT)
    check("4.x.x is transient", t and t["recipient"] == "pat@fullbox.com" and not t["permanent"], t)
    check("an ordinary email is not an NDR",
          parse_ndr("New Order #R1", "noreply@mysimplestore.com", NDR_HTML) is None)

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    os.environ["DATABASE_PATH"] = p
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        db.init_db(p)
    with db._connect(p) as conn:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter) "
                     "VALUES (161, 'Hayden', 'Cooper', 'Austin')")
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter) "
                     "VALUES (162, 'Pat', 'Guy', 'Austin')")
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter) "
                     "VALUES (163, 'Two', 'Box', 'Austin')")
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) "
                     "VALUES (161, 'Hayden@RoofReviveCRS.com', 1)")
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) "
                     "VALUES (162, 'pat@fullbox.com', 1)")
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) "
                     "VALUES (163, 'dead@gone.com', 1)")
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) "
                     "VALUES (163, 'live@here.com', 0)")
        conn.commit()

    print("process_bounces")
    batch = [
        mail("ndr-1", "Undeliverable: One last note from TGF",
             "MicrosoftExchange329e@thegolffellowship.com", html=NDR_HTML),
        mail("ndr-2", "Undeliverable: Your pairings", "postmaster@outlook.com",
             text=NDR_TRANSIENT),
        mail("ndr-3", "Undeliverable: Pairings", "MicrosoftExchange@x.com",
             text="Your message to dead@gone.com couldn't be delivered.\n"
                  "Remote server returned '550 5.1.1 User unknown'"),
        mail("ndr-4", "Undeliverable: hello", "MicrosoftExchange@x.com",
             text="Your message to stranger@nowhere.com couldn't be delivered.\n"
                  "Remote server returned '550 5.1.1 User unknown'"),
        mail("ord-1", "New Order #R1", "noreply@mysimplestore.com", text="order"),
    ]
    with contextlib.redirect_stderr(io.StringIO()):
        r = process_bounces(batch, db_path=p)
    with db._connect(p) as conn:
        em = {row["email"].lower(): dict(row) for row in conn.execute(
            "SELECT email, undeliverable, undeliverable_reason, is_primary FROM customer_emails")}
        items = [dict(x) for x in conn.execute(
            "SELECT email_uid, subject, summary FROM action_items WHERE subject LIKE 'Email bounced:%'")]
        seen = {x["email_uid"]: x["classified_as"] for x in conn.execute(
            "SELECT email_uid, classified_as FROM expense_seen_emails")}
    h = em["hayden@roofrevivecrs.com"]
    check("Hayden's address is undeliverable with code and date as the reason",
          h["undeliverable"] == 1 and "550 5.1.2" in h["undeliverable_reason"]
          and "NDR 2026-09-25" in h["undeliverable_reason"] and h["is_primary"] == 0, h)
    check("the transient bounce is only logged", em["pat@fullbox.com"]["undeliverable"] == 0
          and r["transient"] == 1, (em["pat@fullbox.com"], r))
    check("a second live address is promoted when one dies",
          em["dead@gone.com"]["undeliverable"] == 1 and em["live@here.com"]["is_primary"] == 1, em)
    check("one action item per bounced customer, naming them",
          sorted(i["subject"] for i in items) == [
              "Email bounced: Hayden Cooper <Hayden@RoofReviveCRS.com>",
              "Email bounced: Two Box <dead@gone.com>"], items)
    hi = next(i for i in items if "Hayden" in i["subject"])
    check("the item says nothing deliverable is left",
          "No other deliverable email is on file" in hi["summary"], hi["summary"])
    check("an address on no customer is only reported", r["unmatched"] == ["stranger@nowhere.com"], r)
    check("every NDR is marked seen as 'ndr'; the order email is untouched",
          all(seen.get(u) == "ndr" for u in ("ndr-1", "ndr-2", "ndr-3", "ndr-4"))
          and "ord-1" not in seen, seen)

    print("idempotent")
    with contextlib.redirect_stderr(io.StringIO()):
        r2 = process_bounces(batch, db_path=p)
    with db._connect(p) as conn:
        n_items = conn.execute("SELECT COUNT(*) FROM action_items "
                               "WHERE subject LIKE 'Email bounced:%'").fetchone()[0]
    check("a second pass handles nothing and files nothing",
          r2["ndrs"] == 0 and n_items == 2, (r2, n_items))

    print(f"\n{'ALL PASS' if not FAILS else f'{FAILS} FAILURE(S)'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
