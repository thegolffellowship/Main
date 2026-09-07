"""No-days availability auto-dismisses, once (Kerry 2026-09-07).

"if selection is No Days for availability, they should get automatically
Dismissed for now."

The survey option reads "Neither - but I'm still interested", so this is
a PARK rather than a rejection — which is exactly why the sweep must run
ONCE per lead. The no-loop sweep re-dismisses forever, and it should:
somebody who asked for no contact stays out. Somebody who merely can't
make Tuesday or Saturday is the person Kerry pulls back in after a
schedule change, and a sweep that ran every poll would undo that Restore
silently.

Run: python3 test_lead_no_days.py
"""

import json
import os
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import database as db  # noqa: E402
from email_parser import leads  # noqa: E402

AVAIL = "can_you_play_tuesdays_or_saturdays"
LOOP = leads.LOOP_QUESTION_KEY
FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILURES.append(label)


def plant(conn, name, avail, status="touched", loop="yes_for_both"):
    payload = {LOOP: loop}
    if avail is not None:
        payload[AVAIL] = avail
    conn.execute(
        "INSERT INTO leads (source, external_id, first_name, last_name, "
        "email, chapter, status, payload, arrived_at) VALUES "
        "('hubspot', ?, ?, 'Testcase', ?, 'Austin', ?, ?, datetime('now'))",
        (f"ext-{name}", name, f"{name}@x.com", status, json.dumps(payload)))
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def statuses(p, ids):
    with db._connect(p) as conn:
        return {i: conn.execute("SELECT status FROM leads WHERE id = ?",
                                (i,)).fetchone()["status"] for i in ids}


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS items ("
                     "id INTEGER PRIMARY KEY, customer_id INTEGER, "
                     "transaction_status TEXT, merchant TEXT, "
                     "item_name TEXT, parent_item_id INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS customers ("
                     "customer_id INTEGER PRIMARY KEY, first_name TEXT, "
                     "last_name TEXT)")
        leads.ensure_leads_table(conn)
        neither = "neither_-_but_i'm_still_interested"
        i_none = plant(conn, "NoDays", neither)
        i_both = plant(conn, "BothDays",
                       "yes_-_i_can_play_both_tuesdays_or_saturdays")
        i_tue = plant(conn, "TueOnly", "yes_-_i_can_play_tuesdays")
        i_blank = plant(conn, "NoAnswer", None)
        i_conv = plant(conn, "Converted", neither, status="converted")
        i_new = plant(conn, "BrandNew", neither, status="new")
        conn.commit()

    with db._connect(p) as conn:
        n = leads.dismiss_no_days_leads(conn)
        conn.commit()
    st = statuses(p, [i_none, i_both, i_tue, i_blank, i_conv, i_new])

    check("a No-days lead is dismissed", st[i_none] == "dismissed", st)
    check("a NEW No-days lead is dismissed too", st[i_new] == "dismissed", st)
    check("Both stays put", st[i_both] == "touched", st)
    check("Tuesdays-only stays put", st[i_tue] == "touched", st)
    check("a blank availability answer is left alone",
          st[i_blank] == "touched", st)
    check("a converted lead keeps its status", st[i_conv] == "converted", st)
    check("the sweep reports what it moved", n == 2, n)

    with db._connect(p) as conn:
        note = conn.execute(
            "SELECT note FROM lead_notes WHERE lead_id = ?",
            (i_none,)).fetchone()
    check("the card says why it left the queue",
          note is not None and "No days" in note["note"], note and note["note"])
    check("and that Restore brings it back",
          note is not None and "Restore" in note["note"])

    # Re-running must not write a second note.
    with db._connect(p) as conn:
        again = leads.dismiss_no_days_leads(conn)
        conn.commit()
        n_notes = conn.execute(
            "SELECT COUNT(*) FROM lead_notes WHERE lead_id = ?",
            (i_none,)).fetchone()[0]
    check("re-running is a no-op", again == 0, again)
    check("exactly one note, however often it runs", n_notes == 1, n_notes)

    # THE RESTORE RULE: one-time means a Restore is permanent.
    leads.mark_lead(i_none, "touched", db_path=p)
    with db._connect(p) as conn:
        leads.dismiss_no_days_leads(conn)
        conn.commit()
    check("a Restore is NOT undone by the next sweep",
          statuses(p, [i_none])[i_none] == "touched",
          statuses(p, [i_none]))

    # The decoder is shared with the card badge and the SMS picker.
    check("it uses the same availability decoder the card badge does",
          leads.sms_slot_for({"payload": {AVAIL: "neither_-_but_i'm_still"
                                                 "_interested"}}) == "none")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: " + ", ".join(FAILURES))
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
