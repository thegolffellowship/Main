#!/usr/bin/env python3
"""Manual lead entry (mailbox #420 §6, Kerry: "Leads shouldn't only cover
Facebook campaigns. Should also be able to add manual leads.").

The Lead Center was a Facebook campaign screen. Referrals and in-person
meets are TGF's cheapest acquisitions and had no record anywhere.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import database as db   # noqa: E402
from email_parser import leads            # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS customers "
                     "(customer_id INTEGER PRIMARY KEY, first_name TEXT, "
                     " last_name TEXT)")
        leads.ensure_leads_table(conn)
        conn.commit()

    print("A referral becomes a real lead")
    r = leads.add_manual_lead(
        "Rick", "Billeaud", phone="(337) 281-6169", source="referral",
        chapter="Austin", referred_by="Logan Billeaud", author="K",
        note="Logan's dad", db_path=p)
    check("it is added", r.get("ok") and r.get("lead_id"), r)
    check("the source is the channel, not 'hubspot'",
          r["source"] == "referral", r)
    check("it says which answers we do NOT have, rather than inventing them",
          set(r["answers_missing"]) == {"availability", "importance",
                                        "invitations"}, r)

    with db._connect(p) as conn:
        row = dict(conn.execute("SELECT * FROM leads WHERE id = ?",
                                (r["lead_id"],)).fetchone())
        notes = [dict(n) for n in conn.execute(
            "SELECT author, note FROM lead_notes WHERE lead_id = ? "
            "ORDER BY id", (r["lead_id"],))]
    check("it lands in the queue as NEW, same as any other lead",
          row["status"] == "new", row["status"])
    check("the chapter routes it to the right owner",
          row["chapter"] == "Austin", row)
    check("the card records who sent them",
          any("Logan Billeaud" in (n["note"] or "") for n in notes), notes)
    check("and Kerry's own note is kept as HIS, not as bookkeeping",
          any(n["author"] == "K" and n["note"] == "Logan's dad"
              for n in notes), notes)

    print("A lead you cannot reach is not a lead")
    check("no phone and no email is refused",
          "error" in leads.add_manual_lead("Ghost", db_path=p))
    check("no first name is refused",
          "error" in leads.add_manual_lead("", phone="2105551212", db_path=p))
    check("an invented source is refused",
          "error" in leads.add_manual_lead("X", phone="2105551212",
                                           source="tiktok", db_path=p))
    check("an invented chapter is refused",
          "error" in leads.add_manual_lead("X", phone="2105551212",
                                           chapter="Dallas", db_path=p))
    check("an answer that is not a real survey option is refused",
          "error" in leads.add_manual_lead(
              "X", phone="2105551212",
              answers={"availability": "whenever"}, db_path=p))

    # Guiding principle 6 in spirit: one person, one lead row. A manual
    # add must not mint a second record for somebody already in the queue.
    print("One person, one lead row")
    dupe = leads.add_manual_lead("Rick", "Billeaud", phone="337-281-6169",
                                 source="referral", db_path=p)
    check("the same number in another format is caught",
          "error" in dupe and dupe.get("existing_lead_id") == r["lead_id"],
          dupe)
    check("and it points at the card that already exists",
          "open that card instead" in dupe["error"], dupe)
    with db._connect(p) as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM leads").fetchone()["n"]
    check("so nothing was duplicated", n == 1, n)

    print("Answers we DO know drive the text, exactly like a survey")
    r2 = leads.add_manual_lead(
        "Joey", "Difrank", phone="(614) 361-4234", source="referral",
        chapter="Austin", referred_by="Logan Billeaud",
        answers={"availability": "yes_-_i_can_play_tuesdays"},
        author="K", db_path=p)
    check("it is added with the one answer we have",
          r2.get("ok") and r2["answers_captured"] == ["availability"], r2)
    with db._connect(p) as conn:
        row2 = dict(conn.execute("SELECT * FROM leads WHERE id = ?",
                                 (r2["lead_id"],)).fetchone())
    import json
    row2["payload"] = json.loads(row2["payload"])
    check("the preset picker reads it as a Tuesday lead",
          leads.sms_slot_for(row2) == "tue", leads.sms_slot_for(row2))
    check("and the two we don't have stay genuinely blank",
          leads._lead_answer(row2, "importance") == "", row2["payload"])

    os.unlink(p)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
