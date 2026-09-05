#!/usr/bin/env python3
"""Emailing a lead the SAME ratified preset (Kerry 2026-09-05).

One copy of the copy: email reuses the SMS text verbatim so the two can
never drift. The only thing email adds is a subject.

The guard that matters most: TGF must never email somebody who answered
NO to invitations. Being asked once is a survey answer; being emailed
after saying no is spam.
"""
import json
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


LOOP = leads.LOOP_QUESTION_KEY


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS customers "
                     "(customer_id INTEGER PRIMARY KEY, first_name TEXT, "
                     " last_name TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS items "
                     "(id INTEGER PRIMARY KEY, customer_id INTEGER, "
                     " item_name TEXT, transaction_status TEXT, "
                     " merchant TEXT, order_date TEXT, "
                     " parent_item_id INTEGER, item_price REAL, "
                     " order_id TEXT, item_index INTEGER, customer TEXT, "
                     " chapter TEXT, holes TEXT, side_games TEXT, "
                     " user_status TEXT, quantity INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS events "
                     "(id INTEGER PRIMARY KEY, item_name TEXT, "
                     " event_date TEXT, course TEXT, chapter TEXT, "
                     " format TEXT, course_cost REAL, tgf_markup REAL, "
                     " side_game_fee REAL, start_time TEXT, "
                     " start_type TEXT, registration_url TEXT, "
                     " event_type TEXT, course_surcharge REAL, "
                     " transaction_fee_pct REAL, range_balls_included INTEGER)")
        conn.execute(
            "INSERT INTO events (item_name, event_date, course, chapter, "
            " format, course_cost, tgf_markup, side_game_fee, start_time, "
            " start_type, registration_url, event_type, course_surcharge, "
            " transaction_fee_pct) VALUES "
            "('s9.22 Silverhorn','2026-09-08','Silverhorn Golf Club of Texas',"
            " 'San Antonio','9 Hole',48.71,8.0,7.0,'17:30','Shotgun',"
            " 'https://tgf.example/s922','event',0.0,3.5)")
        leads.ensure_leads_table(conn)

        def plant(name, email, loop_answer):
            payload = {LOOP: loop_answer,
                       "can_you_play_tuesdays_or_saturdays":
                           "yes_-_i_can_play_tuesdays"}
            conn.execute(
                "INSERT INTO leads (source, external_id, first_name, "
                " last_name, email, phone, chapter, status, payload, "
                " arrived_at) VALUES ('hubspot',?,?,'T',?, '2105550100', "
                " 'San Antonio','new',?, '2026-09-04 10:00:00')",
                (f"x-{name}", name, email, json.dumps(payload)))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        yes_id = plant("Yes", "yes@example.com", "yes_for_san_antonio")
        no_id = plant("No", "no@example.com", "no_thanks")
        conn.execute("INSERT INTO leads (source, external_id, first_name, "
                     " last_name, phone, chapter, status, arrived_at) "
                     "VALUES ('referral','r-1','Rick','B','2105550111',"
                     " 'Austin','new','2026-09-04 10:00:00')")
        noemail_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

    print("Email reuses the ratified SMS text, it does not restate it")
    e = leads.lead_email_text(yes_id, preset="p4", db_path=p)
    s = leads.lead_sms_text(yes_id, preset="p4", db_path=p)
    check("the body is character-for-character the SMS preset",
          e.get("text") == s.get("text"), (e.get("text"), s.get("text")))
    check("and it carries a subject, which is the only thing email adds",
          bool(e.get("subject")), e.get("subject"))
    check("the HTML wraps the same words", "<p" in (e.get("html") or "")
          and e["text"].split("\n")[0][:20].split("{")[0][:12]
          in (e.get("html") or "").replace("&#x27;", "'"), e.get("subject"))
    check("no placeholder survives into the subject",
          "{" not in (e.get("subject") or ""), e.get("subject"))

    print("A different preset gives a different subject")
    subs = {k: leads.lead_email_text(yes_id, preset=k, db_path=p).get("subject")
            for k in ("p4", "p6", "p7b")}
    check("P6 asks its own question", "when does golf" in (subs["p6"] or "").lower(), subs)
    check("P7b names itself as the last one",
          "last one" in (subs["p7b"] or "").lower(), subs)
    check("and they are not all the same line",
          len(set(subs.values())) > 1, subs)

    print("TGF never emails somebody who said no")
    check("the opt-out is detected from the survey answer",
          leads.lead_email_text(no_id, db_path=p).get("opted_out") is True)
    r = leads.send_lead_email(no_id, preset="p4", db_path=p)
    check("and the send is REFUSED", "error" in r, r)
    check("with a reason a human can read",
          "opted out" in (r.get("error") or ""), r)
    check("a lead who said yes is not refused for that reason",
          "opted out" not in
          (leads.send_lead_email(yes_id, preset="p4", db_path=p).get("error")
           or ""))

    print("Other refusals are equally explicit")
    r2 = leads.send_lead_email(noemail_id, preset="p4", db_path=p)
    check("no email address is refused", "error" in r2 and
          "no email" in r2["error"], r2)
    check("an unknown preset is refused",
          "error" in leads.lead_email_text(yes_id, preset="p99", db_path=p))
    check("an unknown lead is refused",
          "error" in leads.lead_email_text(999999, db_path=p))

    # Graph creds are absent in the test environment, which is itself the
    # last guard: nothing is sent and nothing is logged.
    print("A send that cannot happen logs nothing")
    r3 = leads.send_lead_email(yes_id, preset="p4", db_path=p)
    check("it fails rather than pretending", "error" in r3, r3)
    with db._connect(p) as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM lead_notes "
                         "WHERE note LIKE 'Emailed%'").fetchone()["n"]
        st = conn.execute("SELECT status FROM leads WHERE id = ?",
                          (yes_id,)).fetchone()["status"]
    check("no 'Emailed' note was written", n == 0, n)
    check("and the lead was NOT marked touched for a send that never went",
          st == "new", st)

    os.unlink(p)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
