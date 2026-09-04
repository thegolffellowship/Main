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
                     "transaction_status TEXT, merchant TEXT, "
                     "item_name TEXT, parent_item_id INTEGER)")
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

    # ---- RSVP → lead-note bridge (sync_lead_rsvp_notes) ----
    with db._connect(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS rsvps ("
                     "id INTEGER PRIMARY KEY, email_uid TEXT UNIQUE, "
                     "player_name TEXT, player_email TEXT, "
                     "gg_event_name TEXT, event_identifier TEXT, "
                     "response TEXT, received_at TEXT, matched_event TEXT, "
                     "customer_id INTEGER, created_at TEXT)")
        lid_rsvp = plant_lead(conn, "Alexp", "Quality2068@Yahoo.com",
                              "San Antonio", "yes_for_san_antonio",
                              status="touched", tag="Texted")
        lid_cid = plant_lead(conn, "CidMatch", "other@x.com",
                             "Austin", "yes_for_austin", status="touched")
        conn.execute("UPDATE leads SET customer_id = 903 WHERE id = ?",
                     (lid_cid,))
        conn.execute("INSERT INTO rsvps (email_uid, player_email, response, "
                     "matched_event, received_at) VALUES ('u1', "
                     "'quality2068@yahoo.com', 'NOT PLAYING', "
                     "'s9.21 Canyon Springs', '2026-08-31T20:37:12Z')")
        conn.execute("INSERT INTO rsvps (email_uid, player_email, response, "
                     "event_identifier, customer_id, received_at) VALUES "
                     "('u2', 'ggalias@x.com', 'PLAYING', 's18.10 Landa', "
                     "903, '2026-08-30T15:00:00Z')")
        conn.execute("INSERT INTO rsvps (email_uid, player_email, response, "
                     "matched_event) VALUES ('u3', 'stranger@x.com', "
                     "'PLAYING', 's9.21 Canyon Springs')")
        conn.commit()
    r_sync = leads.sync_lead_rsvp_notes(db_path=db_path)
    r_again = leads.sync_lead_rsvp_notes(db_path=db_path)
    with db._connect(db_path) as conn:
        notes = {r["lead_id"]: (r["author"], r["note"], r["created_at"])
                 for r in conn.execute(
                     "SELECT lead_id, author, note, created_at "
                     "FROM lead_notes WHERE author = 'GG'")}
        n_total = conn.execute("SELECT COUNT(*) FROM lead_notes "
                               "WHERE author = 'GG'").fetchone()[0]
    check("RSVP bridge adds notes (email + customer_id matches)",
          r_sync.get("rsvp_notes_added") == 2 and n_total == 2,
          f"{r_sync} notes={notes}")
    check("email match is case-insensitive, note text + RSVP timestamp",
          notes.get(lid_rsvp) == ("GG", "RSVP'd Not Playing — s9.21 Canyon "
                                  "Springs", "2026-08-31 20:37:12"),
          str(notes.get(lid_rsvp)))
    check("customer_id match works with different email",
          notes.get(lid_cid) == ("GG", "RSVP'd Playing — s18.10 Landa",
                                 "2026-08-30 15:00:00"),
          str(notes.get(lid_cid)))
    check("re-run is a no-op (idempotent)",
          r_again.get("rsvp_notes_added") == 0, str(r_again))

    # ---- Follow-up / snooze (set_lead_followup, mailbox #365) ----
    r_fu = leads.set_lead_followup(lid_pros, "2026-09-07", db_path=db_path)
    r_bad = leads.set_lead_followup(lid_pros, "next week", db_path=db_path)
    with db._connect(db_path) as conn:
        fu = conn.execute("SELECT follow_up_at FROM leads WHERE id = ?",
                          (lid_pros,)).fetchone()[0]
    check("follow-up date sets", r_fu.get("ok") and fu == "2026-09-07",
          f"{r_fu} {fu}")
    check("bad follow-up date rejected (value kept)",
          r_bad.get("error") is not None and fu == "2026-09-07", str(r_bad))
    leads.set_lead_followup(lid_pros, "", db_path=db_path)
    with db._connect(db_path) as conn:
        fu2 = conn.execute("SELECT follow_up_at FROM leads WHERE id = ?",
                           (lid_pros,)).fetchone()[0]
    check("blank clears follow-up", fu2 is None, str(fu2))

    # ---- No-loop auto-dismiss (Kerry 2026-09-01) ----
    with db._connect(db_path) as conn:
        lid_noloop = plant_lead(conn, "Noloop", "noloop@x.com", "Austin",
                                loop_answer="no", status="new")
        lid_convno = plant_lead(conn, "Convno", "convno@x.com", "Austin",
                                loop_answer="no", status="converted")
        conn.commit()
        n1 = leads.dismiss_no_loop_leads(conn)
        n2 = leads.dismiss_no_loop_leads(conn)
        conn.commit()
        st = {r["id"]: r["status"] for r in conn.execute(
            "SELECT id, status FROM leads WHERE id IN (?, ?)",
            (lid_noloop, lid_convno))}
        n_notes = conn.execute(
            "SELECT COUNT(*) FROM lead_notes WHERE lead_id = ? "
            "AND author = 'auto'", (lid_noloop,)).fetchone()[0]
    check("No-loop lead auto-dismisses with ONE note (idempotent)",
          st[lid_noloop] == "dismissed" and n_notes == 1 and n1 >= 1,
          f"{st} notes={n_notes} n1={n1} n2={n2}")
    check("converted no-loop lead untouched",
          st[lid_convno] == "converted", str(st))

    # ---- Morning follow-up digest (#370, reshaped Kerry 2026-09-03:
    #      "should be part of morning digest") ----
    sent = []
    real_send = leads._send_digest_mail
    leads._send_digest_mail = lambda to, rows, heading: (
        sent.append((to, [r["id"] for r in rows], heading)) or True)
    import email_parser.timezone_utils as tzu
    real_now = tzu.now_central
    from datetime import datetime as _dt

    class _FakeNow:
        val = _dt(2026, 9, 7, 9, 0, 0)
    tzu.now_central = lambda: _FakeNow.val
    try:
        leads.set_lead_followup(lid_pros, "2026-09-07", db_path=db_path)
        with db._connect(db_path) as conn:
            conn.execute("INSERT INTO lead_notes (lead_id, author, note) "
                         "VALUES (?, 'kerry', 'ping me for Silverhorn')",
                         (lid_pros,))
            conn.commit()
        _FakeNow.val = _dt(2026, 9, 7, 5, 0, 0)
        r_early = leads.send_followup_digests(db_path=db_path)
        check("pre-7AM sweep leaves the queue alone",
              r_early["due"] == 0 and not sent, str(r_early))

        _FakeNow.val = _dt(2026, 9, 7, 9, 0, 0)
        r_due = leads.send_followup_digests(db_path=db_path)
        check("the due lead is picked up", r_due["due"] >= 1, str(r_due))
        rows = leads.followups_due(db_path=db_path)
        me = [r for r in rows if r["id"] == lid_pros]
        check("the digest row carries the latest note",
              len(me) == 1 and me[0]["last_note"] == "ping me for Silverhorn",
              str(me))

        # A lead that stays overdue is listed AGAIN tomorrow — the whole
        # point of a digest, and the opposite of the old one-shot ping.
        _FakeNow.val = _dt(2026, 9, 9, 9, 0, 0)
        again = leads.followups_due(db_path=db_path)
        me2 = [r for r in again if r["id"] == lid_pros]
        check("an unresolved follow-up appears again, now marked overdue",
              len(me2) == 1 and me2[0]["days_over"] == 2, str(me2))

        with db._connect(db_path) as conn:
            conn.execute("UPDATE leads SET status = 'dismissed' "
                         "WHERE id = ?", (lid_pros,))
            conn.commit()
        check("a dismissed lead drops out of the digest",
              not any(r["id"] == lid_pros
                      for r in leads.followups_due(db_path=db_path)))
    finally:
        leads._send_digest_mail = real_send
        tzu.now_central = real_now

    os.unlink(db_path)
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURE(S)")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
