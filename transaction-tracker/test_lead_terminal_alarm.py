"""A finished lead carries no 48-hour alarm (Kerry 2026-09-07).

"Jeff Sekiguchi shouldn't be in Follow-Ups Due anymore because he signed
up for an event."

He WAS converted — the auto-detect had seen his registration and flipped
him hours earlier. What kept him in the section was the 48-hour alarm
still armed on the row: FOLLOW-UPS DUE is tested before status, because
a due action outranks an outcome. So the row has to stop being due.

`mark_lead` already cleared the alarm on any status change, but every
AUTOMATIC writer — the conversion detect, the membership detect, the
no-loop and no-days sweeps — set status with plain SQL and left it
armed. These tests pin the rule over the terminal statuses rather than
over any one of those writers.

Run: python3 test_lead_terminal_alarm.py
"""

import json
import os
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import database as db  # noqa: E402
from email_parser import leads  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILURES.append(label)


def plant(conn, name, status, follow_up, outreach):
    conn.execute(
        "INSERT INTO leads (source, external_id, first_name, last_name, "
        "email, chapter, status, payload, arrived_at, follow_up_at, "
        "outreach_at, follow_up_notified_for) VALUES "
        "('hubspot', ?, ?, 'Testcase', ?, 'Austin', ?, '{}', "
        "datetime('now'), ?, ?, ?)",
        (f"ext-{name}", name, f"{name}@x.com", status, follow_up,
         outreach, follow_up))
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def row(p, i):
    with db._connect(p) as conn:
        return dict(conn.execute(
            "SELECT status, follow_up_at, outreach_at, "
            "follow_up_notified_for FROM leads WHERE id = ?",
            (i,)).fetchone())


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
        # Jeff's exact shape: converted, alarm still armed.
        i_conv = plant(conn, "Sekiguchi", "converted", "2026-09-06",
                       "2026-09-04 12:35:45")
        i_dism = plant(conn, "Dismissed", "dismissed", "2026-09-06",
                       "2026-09-04 12:35:45")
        i_work = plant(conn, "StillWorking", "touched", "2026-09-06",
                       "2026-09-04 12:35:45")
        # A HAND-SET date on a converted lead: outreach_at is NULL, and
        # Kerry meant that reminder.
        i_hand = plant(conn, "HandSet", "converted", "2026-09-20", None)
        conn.commit()

    with db._connect(p) as conn:
        n = leads.clear_alarms_on_terminal_leads(conn)
        conn.commit()

    r = row(p, i_conv)
    check("a converted lead's auto alarm is cleared",
          r["follow_up_at"] is None and r["outreach_at"] is None, r)
    check("the ping stamp goes with it, so a restore re-arms cleanly",
          r["follow_up_notified_for"] is None, r)
    check("a dismissed lead is cleared too — same terminal rule",
          row(p, i_dism)["follow_up_at"] is None, row(p, i_dism))
    check("a lead still being worked keeps its alarm",
          row(p, i_work)["follow_up_at"] == "2026-09-06", row(p, i_work))
    check("a HAND-SET date on a converted lead is never touched",
          row(p, i_hand)["follow_up_at"] == "2026-09-20", row(p, i_hand))
    check("it reports what it cleared", n == 2, n)

    with db._connect(p) as conn:
        again = leads.clear_alarms_on_terminal_leads(conn)
        conn.commit()
    check("re-running clears nothing more", again == 0, again)

    # The section test that put Jeff in the wrong place: a due alarm
    # outranks status, so clearing the alarm is what moves him.
    check("with the alarm gone the row is no longer due",
          row(p, i_conv)["follow_up_at"] is None)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: " + ", ".join(FAILURES))
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
