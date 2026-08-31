"""Tests for the Lead Center invite-list CSV filter and deactivating tags.

Builds a throwaway SQLite database, plants leads covering every
inclusion/exclusion rule of get_lead_export_rows (Kerry 2026-08-28 CSV
spec + 2026-08-31 amendments), then checks:

  - explicit invitations opt-OUT ('no', and future 'no_-_…' variants)
    never lands on either chapter's CSV — the load-bearing rule from
    Kerry 2026-08-31: "make sure those that don't want invites don't
    get put on the CSV downloads";
  - yes_for_both / yes_for_<chapter> route to the right CSV(s);
  - a lead with no invitations answer falls back to its routed chapter;
  - dismissed leads, deactivating/cold tags, and email-less rows are out;
  - set_lead_tag: DEACTIVATING_TAGS flip the lead to dismissed (never
    delete), converted leads keep their status, and a normal tag still
    auto-touches a NEW lead.

Run: python3 test_leads_export.py
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
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def plant_lead(conn, first, email, chapter, loop_answer=None,
               status="touched", tag=None):
    payload = {}
    if loop_answer is not None:
        payload["would_you_like_to_stay_in_the_loop_with_tgf_and_receive"
                "_event_invitations"] = loop_answer
    conn.execute(
        "INSERT INTO leads (source, external_id, first_name, last_name, "
        "email, chapter, status, tag, payload, arrived_at) "
        "VALUES ('hubspot', ?, ?, 'Testcase', ?, ?, ?, ?, ?, "
        "datetime('now'))",
        (f"ext-{first}", first, email, chapter, status, tag,
         json.dumps(payload)))
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    with db._connect(db_path) as conn:
        # items/customers only need to exist for the history check and
        # the prospect-name sync
        conn.execute("CREATE TABLE IF NOT EXISTS items ("
                     "id INTEGER PRIMARY KEY, customer_id INTEGER, "
                     "transaction_status TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS customers ("
                     "customer_id INTEGER PRIMARY KEY, "
                     "first_name TEXT, last_name TEXT)")
        leads.ensure_leads_table(conn)
        plant_lead(conn, "OptOut", "optout@x.com", "San Antonio", "no")
        plant_lead(conn, "OptOutVariant", "optoutv@x.com", "Austin",
                   "no_-_not_interested_in_emails")
        plant_lead(conn, "BothYes", "both@x.com", "San Antonio",
                   "yes_for_both")
        plant_lead(conn, "SaOnly", "sa@x.com", "Austin",
                   "yes_for_san_antonio")
        plant_lead(conn, "AtxOnly", "atx@x.com", "San Antonio",
                   "yes_for_austin")
        plant_lead(conn, "NoAnswerSa", "fallback@x.com", "San Antonio")
        plant_lead(conn, "DismissedGuy", "dismissed@x.com", "San Antonio",
                   "yes_for_both", status="dismissed")
        plant_lead(conn, "PriceyTag", "pricey@x.com", "San Antonio",
                   "yes_for_both", tag="Too expensive")
        plant_lead(conn, "BadContact", "bad@x.com", "Austin",
                   "yes_for_both", tag="Bad contact")
        plant_lead(conn, "NotNow", "notnow@x.com", "Austin",
                   "yes_for_both", tag="Not now")
        plant_lead(conn, "NoEmail", "", "San Antonio", "yes_for_both")
        conn.commit()

    sa = {r["first_name"] for r in
          leads.get_lead_export_rows("San Antonio", db_path=db_path)}
    atx = {r["first_name"] for r in
           leads.get_lead_export_rows("Austin", db_path=db_path)}

    print("SA CSV:", sorted(sa))
    print("Austin CSV:", sorted(atx))
    check("explicit 'no' is on neither CSV",
          "OptOut" not in sa and "OptOut" not in atx)
    check("'no_-_…' variant is on neither CSV",
          "OptOutVariant" not in sa and "OptOutVariant" not in atx)
    check("'no' does NOT fall back to routed chapter",
          "OptOut" not in sa)
    check("yes_for_both lands on both CSVs",
          "BothYes" in sa and "BothYes" in atx)
    check("yes_for_san_antonio: SA only (overrides routed chapter)",
          "SaOnly" in sa and "SaOnly" not in atx)
    check("yes_for_austin: Austin only (overrides routed chapter)",
          "AtxOnly" in atx and "AtxOnly" not in sa)
    check("no answer falls back to routed chapter",
          "NoAnswerSa" in sa and "NoAnswerSa" not in atx)
    check("dismissed lead excluded", "DismissedGuy" not in sa)
    check("'Too expensive' tag excluded", "PriceyTag" not in sa)
    check("'Bad contact' tag excluded", "BadContact" not in atx)
    check("'Not now' tag excluded", "NotNow" not in atx)
    # Boot-heal: PRE-EXISTING deactivating tags (applied before the tag
    # auto-dismissed, e.g. John Oscar 2026-08-31) get swept to dismissed
    # by ensure_leads_table on any read — the export calls above were
    # enough to trigger it.
    with db._connect(db_path) as conn:
        healed = {r["first_name"]: r["status"] for r in conn.execute(
            "SELECT first_name, status FROM leads "
            "WHERE first_name IN ('BadContact', 'PriceyTag', 'NotNow')")}
    check("pre-existing 'Bad contact' healed to dismissed",
          healed.get("BadContact") == "dismissed", str(healed))
    check("pre-existing 'Too expensive' healed to dismissed",
          healed.get("PriceyTag") == "dismissed", str(healed))
    check("'Not now' is NOT a deactivating tag (stays touched)",
          healed.get("NotNow") == "touched", str(healed))
    check("email-less row excluded",
          all(r["email"] for chap in ("San Antonio", "Austin")
              for r in leads.get_lead_export_rows(chap, db_path=db_path)))

    # ---- Deactivating-tag behavior (set_lead_tag) ----
    with db._connect(db_path) as conn:
        lid_new = plant_lead(conn, "TagMeNew", "tagnew@x.com",
                             "San Antonio", "yes_for_both", status="new")
        lid_conv = plant_lead(conn, "TagMeConv", "tagconv@x.com",
                              "San Antonio", "yes_for_both",
                              status="converted")
        lid_bad = plant_lead(conn, "TagMeBad", "tagbad@x.com",
                             "Austin", "yes_for_both", status="touched")
        conn.commit()

    leads.set_lead_tag(lid_new, "Too expensive", db_path=db_path)
    leads.set_lead_tag(lid_conv, "Too expensive", db_path=db_path)
    leads.set_lead_tag(lid_bad, "Bad contact", db_path=db_path)
    with db._connect(db_path) as conn:
        st = {r["first_name"]: (r["status"], r["tag"]) for r in conn.execute(
            "SELECT first_name, status, tag FROM leads "
            "WHERE first_name LIKE 'TagMe%'")}
    check("'Too expensive' deactivates (status -> dismissed)",
          st["TagMeNew"] == ("dismissed", "Too expensive"), str(st))
    check("converted lead keeps status when tagged",
          st["TagMeConv"] == ("converted", "Too expensive"), str(st))
    check("'Bad contact' deactivates (status -> dismissed)",
          st["TagMeBad"] == ("dismissed", "Bad contact"), str(st))

    lid_norm = None
    with db._connect(db_path) as conn:
        lid_norm = plant_lead(conn, "TagMeInt", "tagint@x.com",
                              "San Antonio", "yes_for_both", status="new")
        conn.commit()
    leads.set_lead_tag(lid_norm, "Interested", db_path=db_path)
    with db._connect(db_path) as conn:
        row = conn.execute("SELECT status, tag FROM leads WHERE id = ?",
                           (lid_norm,)).fetchone()
    check("normal tag on a NEW lead still auto-touches",
          (row["status"], row["tag"]) == ("touched", "Interested"),
          str(dict(row)))

    # ---- Name edit + prospect sync (edit_lead_identity) ----
    with db._connect(db_path) as conn:
        conn.execute("INSERT INTO customers (customer_id, first_name, "
                     "last_name) VALUES (901, 'Aden', NULL)")
        conn.execute("INSERT INTO customers (customer_id, first_name, "
                     "last_name) VALUES (902, 'Real', 'Buyer')")
        conn.execute("INSERT INTO items (customer_id, transaction_status) "
                     "VALUES (902, 'active')")
        lid_pros = plant_lead(conn, "Aden", "moralesaden69@x.com",
                              "San Antonio", "yes_for_both", status="new")
        lid_buyr = plant_lead(conn, "Real", "real@x.com",
                              "Austin", "yes_for_both", status="touched")
        conn.execute("UPDATE leads SET customer_id = 901 WHERE id = ?",
                     (lid_pros,))
        conn.execute("UPDATE leads SET customer_id = 902 WHERE id = ?",
                     (lid_buyr,))
        conn.commit()
    r1 = leads.edit_lead_identity(lid_pros, last_name="Morales",
                                  db_path=db_path)
    r2 = leads.edit_lead_identity(lid_buyr, first_name="Realname",
                                  last_name="Changed", db_path=db_path)
    with db._connect(db_path) as conn:
        lead_row = conn.execute(
            "SELECT first_name, last_name FROM leads WHERE id = ?",
            (lid_pros,)).fetchone()
        pros = conn.execute("SELECT first_name, last_name FROM customers "
                            "WHERE customer_id = 901").fetchone()
        buyr = conn.execute("SELECT first_name, last_name FROM customers "
                            "WHERE customer_id = 902").fetchone()
    check("edit_lead_identity updates the lead's name",
          (lead_row["first_name"], lead_row["last_name"])
          == ("Aden", "Morales"), str(dict(lead_row)))
    check("purchase-less prospect customer synced",
          r1.get("customer_synced") is True
          and (pros["first_name"], pros["last_name"]) == ("Aden", "Morales"),
          f"{r1} {dict(pros)}")
    check("customer WITH purchase history untouched",
          r2.get("customer_synced") is False
          and (buyr["first_name"], buyr["last_name"]) == ("Real", "Buyer"),
          f"{r2} {dict(buyr)}")
    check("empty edit rejected",
          leads.edit_lead_identity(lid_pros,
                                   db_path=db_path).get("error") is not None)

    os.unlink(db_path)
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURE(S)")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
