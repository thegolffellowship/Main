"""Tests for the 48-hour outreach alarm (Kerry 2026-09-03).

  "Need a timestamp with alarm set when I click Texted or Emailed for
   someone for the first time. That should auto set a 48 hour alarm that
   resets when I change status or add a note, which probably signifies
   that there's been a response."

Throwaway SQLite database; checks:
  - tagging Texted / Sent email / Left VM stamps outreach_at and sets
    follow_up_at 2 days out, with an auto note carrying the timestamp;
  - "for the first time": re-tagging never pushes the date out, and a
    follow-up date Kerry set BY HAND is never armed over or cleared;
  - the alarm CLEARS on a real status change, on a non-outreach tag, and
    on a note from a person / GG RSVP / HubSpot re-submission;
  - author 'auto' bookkeeping notes leave it armed;
  - re-marking the status it already had leaves it armed;
  - after a response clears it, texting again arms a fresh clock;
  - the armed lead rides the EXISTING follow-up rails: it shows up in the
    morning digest's due list on its due day, and the digest mail goes only
    to a chapter's own list (Kerry's copy is the COO Daily Briefing).

Run: python3 test_lead_outreach_alarm.py
"""

import json
import os
import tempfile
from datetime import date, datetime, timedelta

os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import database as db  # noqa: E402
from email_parser import leads  # noqa: E402
from email_parser.timezone_utils import now_central  # noqa: E402

# ONE reference date for the whole run, on the SAME clock the code stamps
# with. Reading date.today() (UTC) per assertion made this suite fail if a
# run straddled midnight Central — which it did, 2026-09-03 23:59 UTC.
TODAY = now_central().date()

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def row(db_path, lid):
    with db._connect(db_path) as conn:
        return dict(conn.execute(
            "SELECT status, tag, follow_up_at, follow_up_notified_for, "
            "outreach_at FROM leads WHERE id = ?", (lid,)).fetchone())


def notes(db_path, lid):
    with db._connect(db_path) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT author, note FROM lead_notes WHERE lead_id = ? "
            "ORDER BY id", (lid,))]


def plant(db_path, name, status="new"):
    with db._connect(db_path) as conn:
        leads.ensure_leads_table(conn)
        conn.execute(
            "INSERT INTO leads (source, external_id, first_name, last_name, "
            "email, chapter, status, arrived_at) VALUES ('hubspot', ?, ?, "
            "'T', ?, 'San Antonio', ?, datetime('now'))",
            (f"ext-{name}", name, f"{name.lower()}@x.com", status))
        lid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
    return lid


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = p_db = tmp.name
    with db._connect(p) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, "
                     "customer_id INTEGER, transaction_status TEXT, merchant TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS customers (customer_id INTEGER "
                     "PRIMARY KEY, first_name TEXT, last_name TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY "
                     "KEY, value TEXT, updated_at TEXT)")
        conn.commit()
    due2 = (TODAY + timedelta(days=2)).isoformat()

    print("Arming")
    a = plant(p, "Texted")
    res = leads.set_lead_tag(a, "Texted", db_path=p)
    r = row(p, a)
    check("Texted sets follow_up_at 2 days out", r["follow_up_at"] == due2, r)
    check("Texted stamps outreach_at (the timestamp)", bool(r["outreach_at"]), r)
    with db._connect(p_db) as conn:
        utc_now = conn.execute("SELECT datetime('now') AS n").fetchone()["n"]
    check("outreach_at is stored UTC like every other datetime column "
          "(the UI converts to Central)",
          abs((__import__("datetime").datetime.fromisoformat(r["outreach_at"])
               - __import__("datetime").datetime.fromisoformat(utc_now))
              .total_seconds()) < 120,
          (r["outreach_at"], utc_now))
    check("tagging a NEW lead still marks it touched", r["status"] == "touched", r)
    check("the call reports the alarm date", res.get("follow_up_at") == due2, res)
    n = notes(p, a)
    check("an auto note records the timestamp + the alarm",
          len(n) == 1 and n[0]["author"] == "auto"
          and n[0]["note"].startswith("Texted ")
          and "48-hour follow-up set for" in n[0]["note"],
          n)
    for tag in ("Sent email", "Left VM"):
        lid = plant(p, tag.replace(" ", ""))
        leads.set_lead_tag(lid, tag, db_path=p)
        check(f"{tag} arms the same clock", row(p, lid)["follow_up_at"] == due2)

    print('"For the first time"')
    before = row(p, a)["follow_up_at"]
    leads.set_lead_tag(a, "Texted", db_path=p)
    check("re-tagging Texted does NOT push the date out",
          row(p, a)["follow_up_at"] == before and len(notes(p, a)) == 1,
          (row(p, a), len(notes(p, a))))
    manual = plant(p, "Manual")
    hand = (date.today() + timedelta(days=10)).isoformat()
    leads.set_lead_followup(manual, hand, db_path=p)
    leads.set_lead_tag(manual, "Texted", db_path=p)
    r = row(p, manual)
    check("a hand-set follow-up date is never armed over",
          r["follow_up_at"] == hand and r["outreach_at"] is None, r)
    leads.add_lead_note(manual, "just checking in", author="K", db_path=p)
    check("a note never clears a HAND-SET date",
          row(p, manual)["follow_up_at"] == hand, row(p, manual))

    print("Resets — a response happened")
    b = plant(p, "Noted")
    leads.set_lead_tag(b, "Texted", db_path=p)
    res = leads.add_lead_note(b, "he replied, wants in", author="K", db_path=p)
    r = row(p, b)
    check("a note from a person clears the alarm",
          r["follow_up_at"] is None and r["outreach_at"] is None
          and res.get("alarm_cleared") is True, (r, res))

    c = plant(p, "Rsvp")
    leads.set_lead_tag(c, "Texted", db_path=p)
    leads.add_lead_note(c, "RSVPd", author="GG", db_path=p)
    check("a GG RSVP clears it (a real member action)",
          row(p, c)["follow_up_at"] is None, row(p, c))

    d = plant(p, "Resub")
    leads.set_lead_tag(d, "Texted", db_path=p)
    leads.add_lead_note(d, "Re-submitted the FB survey", author="HS", db_path=p)
    check("a HubSpot re-submission clears it (they re-engaged)",
          row(p, d)["follow_up_at"] is None, row(p, d))

    e = plant(p, "Book")
    leads.set_lead_tag(e, "Texted", db_path=p)
    res = leads.add_lead_note(e, "Campaign set to Fall 2026 Leads by Kerry",
                              author="auto", db_path=p)
    check("an 'auto' bookkeeping note leaves it ARMED",
          row(p, e)["follow_up_at"] == due2 and res.get("alarm_cleared") is False,
          (row(p, e), res))

    f = plant(p, "Status")
    leads.set_lead_tag(f, "Texted", db_path=p)
    res = leads.mark_lead(f, "converted", db_path=p)
    check("a real status change clears it",
          row(p, f)["follow_up_at"] is None and res.get("alarm_cleared") is True,
          (row(p, f), res))

    g = plant(p, "Same")
    leads.set_lead_tag(g, "Texted", db_path=p)          # -> touched
    res = leads.mark_lead(g, "touched", db_path=p)      # no actual change
    check("re-marking the SAME status leaves it armed",
          row(p, g)["follow_up_at"] == due2 and res.get("alarm_cleared") is False,
          (row(p, g), res))

    h = plant(p, "Hot")
    leads.set_lead_tag(h, "Texted", db_path=p)
    leads.set_lead_tag(h, "Interested", db_path=p)
    check("a non-outreach tag clears it", row(p, h)["follow_up_at"] is None,
          row(p, h))

    print("Re-arming after a response")
    leads.set_lead_tag(b, "Texted", db_path=p)
    check("texting again after a reply starts a fresh clock",
          row(p, b)["follow_up_at"] == due2 and bool(row(p, b)["outreach_at"]),
          row(p, b))

    print("Rides the existing follow-up rails")
    i = plant(p, "Due")
    leads.set_lead_tag(i, "Texted", db_path=p)
    with db._connect(p) as conn:            # pretend the 48 hours elapsed
        conn.execute("UPDATE leads SET follow_up_at = ? WHERE id = ?",
                     (TODAY.isoformat(), i))
        conn.commit()
    due_ids = {r["id"] for r in leads.followups_due(db_path=p)}
    check("the armed lead shows up in the morning digest's due list",
          i in due_ids, sorted(due_ids))

    print("Dial")
    with db._connect(p) as conn:
        conn.execute("INSERT INTO app_settings (key, value) VALUES "
                     "('lead_outreach_tags', '[\"Texted\"]')")
        conn.commit()
    check("lead_outreach_tags dial narrows the set",
          leads.get_outreach_tags(p) == ["Texted"], leads.get_outreach_tags(p))
    j = plant(p, "DialVM")
    leads.set_lead_tag(j, "Left VM", db_path=p)
    check("a tag dropped from the dial no longer arms",
          row(p, j)["follow_up_at"] is None, row(p, j))

    print("Backfill for leads tagged before the release (#405)")
    from datetime import timedelta as _td
    # The Dial section above narrowed lead_outreach_tags to ["Texted"];
    # restore the default or "Sent email" and "Left VM" silently fail to
    # match here. Test isolation, not a code behaviour.
    with db._connect(p_db) as conn:
        conn.execute("DELETE FROM app_settings WHERE key = 'lead_outreach_tags'")
        conn.commit()
    pre = []
    for i, (name, tag, day) in enumerate([
            ("PreA", "Texted", 2), ("PreB", "Texted", 2),
            ("PreC", "Sent email", 1), ("PreD", "Left VM", 0)]):
        lid = plant(p_db, name, status="touched")
        stamp = (TODAY - _td(days=day)).isoformat() + " 14:00:00"
        with db._connect(p_db) as conn:
            conn.execute("UPDATE leads SET tag = ?, touched_at = ? WHERE id = ?",
                         (tag, stamp, lid))
            conn.commit()
        pre.append((lid, day))
    # a hand-set follow-up must survive untouched
    hand = plant(p_db, "HandSet", status="touched")
    hand_date = (TODAY + _td(days=10)).isoformat()
    with db._connect(p_db) as conn:
        conn.execute("UPDATE leads SET tag = 'Texted', touched_at = ?, "
                     "follow_up_at = ? WHERE id = ?",
                     ((TODAY - _td(days=2)).isoformat() + " 09:00:00",
                      hand_date, hand))
        conn.commit()
    # a non-outreach tag must be left alone
    hot = plant(p_db, "HotTag", status="touched")
    with db._connect(p_db) as conn:
        conn.execute("UPDATE leads SET tag = 'Interested', touched_at = ? "
                     "WHERE id = ?",
                     ((TODAY - _td(days=2)).isoformat() + " 09:00:00", hot))
        conn.commit()

    dry = leads.backfill_outreach_alarms(dry_run=True, db_path=p_db)
    dry_ids = {l["id"] for l in dry["leads"]}
    check("dry run finds every pre-release outreach lead",
          {lid for lid, _ in pre} <= dry_ids, sorted(dry_ids))
    check("dry run excludes the hand-set and non-outreach leads",
          hand not in dry_ids and hot not in dry_ids, sorted(dry_ids))
    check("dry run changes nothing",
          row(p_db, pre[0][0])["follow_up_at"] is None)
    check("dry run reports a due date for each",
          all(l.get("due") for l in dry["leads"]), dry["leads"][:2])
    res = leads.backfill_outreach_alarms(db_path=p_db)
    check("backfill updated what the dry run previewed",
          res["updated"] == dry["found"], (res.get("updated"), dry.get("found")))
    for lid, day in pre:
        r = row(p_db, lid)
        want = (TODAY - _td(days=day) + _td(days=2)).isoformat()
        check(f"lead touched {day}d ago is due {want}",
              r["follow_up_at"] == want and r["outreach_at"] is not None,
              (r["follow_up_at"], want))
    check("a HAND-SET follow-up date is never overwritten",
          row(p_db, hand)["follow_up_at"] == hand_date, row(p_db, hand))
    check("a non-outreach tag is left alone",
          row(p_db, hot)["follow_up_at"] is None, row(p_db, hot))
    check("backfill is idempotent — a second run finds nothing",
          leads.backfill_outreach_alarms(db_path=p_db)["updated"] == 0)
    n = notes(p_db, pre[0][0])
    check("each backfilled lead gets an auto note explaining it",
          any("backfilled" in x["note"] for x in n), n)

    # Kerry texts prospects at night. touched_at is stored UTC, so a 9 PM
    # Central text is stored on the NEXT calendar day — reading date()
    # straight off the stored value armed those alarms a day late, which
    # is most of them. The due day is Central, same as the live path.
    evening = plant(p_db, "EveningText", status="touched")
    with db._connect(p_db) as conn:
        conn.execute("UPDATE leads SET tag = 'Texted', touched_at = ?, "
                     "follow_up_at = NULL, outreach_at = NULL WHERE id = ?",
                     ("2026-08-30 02:13:53", evening))   # 8/29 9:13 PM CT
        conn.commit()
    ev = leads.backfill_outreach_alarms(dry_run=True, db_path=p_db)
    ev_row = next(l for l in ev["leads"] if l["id"] == evening)
    check("a 9 PM Central text is due 2 days from THAT day, not UTC's",
          ev_row["due"] == "2026-08-31", ev_row)
    leads.backfill_outreach_alarms(db_path=p_db)
    check("the evening lead is written with the Central due date",
          row(p_db, evening)["follow_up_at"] == "2026-08-31",
          row(p_db, evening))
    check("its note names the Central day it was texted",
          any("2026-08-29" in x["note"] for x in notes(p_db, evening)),
          notes(p_db, evening))

    # The old ping-suppression guard is gone with the per-lead ping: a
    # backfill of any size costs one line in the morning digest, so a
    # backfilled lead is left plainly due like any other.
    check("a backfilled lead is left plainly due, not pre-silenced",
          row(p_db, evening)["follow_up_notified_for"] is None,
          row(p_db, evening))
    future = plant(p_db, "FutureDue", status="touched")
    with db._connect(p_db) as conn:
        conn.execute("UPDATE leads SET tag = 'Texted', touched_at = ?, "
                     "follow_up_at = NULL, outreach_at = NULL WHERE id = ?",
                     ((TODAY + _td(days=1)).isoformat() + " 14:00:00", future))
        conn.commit()
    fdry = leads.backfill_outreach_alarms(dry_run=True, db_path=p_db)
    check("the dry run reports how many are already due",
          fdry["already_due"] <= fdry["found"], fdry)
    leads.backfill_outreach_alarms(db_path=p_db)
    check("a future due date is armed and left alone",
          row(p_db, future)["follow_up_notified_for"] is None
          and row(p_db, future)["follow_up_at"] is not None,
          row(p_db, future))

    print('"Followed up" resets the timer (Kerry 2026-09-03)')
    # "Need something like a Followed Up option that resets the timer."
    # The ordinary outreach tags arm only on a FIRST touch, so re-tapping
    # Texted on a lead whose alarm already fired did nothing at all and
    # the chip stayed red while Kerry kept working the person.
    fu = plant(p_db, "FollowUp")
    leads.set_lead_tag(fu, "Texted", db_path=p_db)
    with db._connect(p_db) as conn:                 # let it go overdue
        conn.execute("UPDATE leads SET follow_up_at = ? WHERE id = ?",
                     ((TODAY - _td(days=3)).isoformat(), fu))
        conn.commit()
    check("re-tapping Texted still does NOT move an overdue date",
          (leads.set_lead_tag(fu, "Texted", db_path=p_db)
           .get("follow_up_at")) is None
          and row(p_db, fu)["follow_up_at"] == (TODAY - _td(days=3)).isoformat(),
          row(p_db, fu))
    res = leads.set_lead_tag(fu, "Followed up", db_path=p_db)
    r = row(p_db, fu)
    check("Followed up restarts the 48-hour clock",
          r["follow_up_at"] == due2 and res.get("follow_up_at") == due2, (r, res))
    check("it re-stamps outreach_at, so the chip reads as an auto alarm",
          bool(r["outreach_at"]) and r["tag"] == "Followed up", r)
    check("and re-arms the digest ping for the new date",
          r["follow_up_notified_for"] is None, r)
    n = notes(p_db, fu)[-1]
    check("the note says it was RESET and what it replaced",
          "reset to" in n["note"] and "was " in n["note"], n)

    # A date Kerry set BY HAND is deliberate, so replacing it must be
    # deliberate too: an ordinary tag still never touches it, but
    # choosing Followed up says "I just reached out" in so many words.
    hand2 = plant(p_db, "HandThenFollow")
    hand2_date = (TODAY + _td(days=20)).isoformat()
    leads.set_lead_followup(hand2, hand2_date, db_path=p_db)
    leads.set_lead_tag(hand2, "Texted", db_path=p_db)
    check("an ordinary outreach tag still never overrides a hand-set date",
          row(p_db, hand2)["follow_up_at"] == hand2_date, row(p_db, hand2))
    leads.set_lead_tag(hand2, "Followed up", db_path=p_db)
    check("Followed up does override it — explicitly",
          row(p_db, hand2)["follow_up_at"] == due2, row(p_db, hand2))
    check("and the note records the date it replaced, so nothing is lost",
          "was " in notes(p_db, hand2)[-1]["note"], notes(p_db, hand2)[-1])

    check("Followed up is offered in the tag list",
          "Followed up" in leads.get_tag_options(p_db),
          leads.get_tag_options(p_db))

    print("Morning digest routing (Kerry 2026-09-03)")
    # Kerry's copy rides the COO Daily Briefing, so the digest mail must
    # go ONLY to a chapter's own list — otherwise he gets the same names
    # twice every morning, which is the noise this replaced.
    import os as _os
    aus = plant(p_db, "AustinDue", status="touched")
    with db._connect(p_db) as conn:
        conn.execute("UPDATE leads SET chapter = 'Austin', tag = 'Texted', "
                     "follow_up_at = ? WHERE id = ?",
                     ((TODAY - _td(days=1)).isoformat(), aus))
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES "
            "('lead_notify_recipients', ?)",
            (json.dumps({"default": ["kerry@tgf.com"],
                         "Austin": ["robert@tgf.com"]}),))
        conn.commit()
    posted = []
    real = leads._send_digest_mail
    leads._send_digest_mail = lambda to, rows, heading: (
        posted.append((to, [r["id"] for r in rows])) or True)
    prev_coo = _os.environ.get("COO_EMAIL_TO")
    _os.environ["COO_EMAIL_TO"] = "kerry@tgf.com"
    try:
        import email_parser.timezone_utils as _tz
        real_now = _tz.now_central
        _tz.now_central = lambda: datetime(TODAY.year, TODAY.month,
                                           TODAY.day, 9, 0, 0)
        try:
            res = leads.send_followup_digests(db_path=p_db)
            check("one digest, to the chapter's own list only",
                  len(posted) == 1 and posted[0][0] == "robert@tgf.com",
                  posted)
            check("it carries that chapter's leads",
                  posted and aus in posted[0][1], posted)
            check("Kerry is not mailed separately — his copy is the briefing",
                  all("kerry@tgf.com" not in t for t, _ in posted), posted)
            posted.clear()
            leads.send_followup_digests(db_path=p_db)
            check("a second sweep the same day does not re-send",
                  posted == [], posted)
        finally:
            _tz.now_central = real_now
    finally:
        leads._send_digest_mail = real
        if prev_coo is None:
            _os.environ.pop("COO_EMAIL_TO", None)
        else:
            _os.environ["COO_EMAIL_TO"] = prev_coo

    print("Tag path attributes the toucher (#405)")
    t = plant(p_db, "Attrib")
    leads.set_lead_tag(t, "Texted", db_path=p_db, author="kerry")
    with db._connect(p_db) as conn:
        tb = conn.execute("SELECT touched_by, status FROM leads WHERE id = ?",
                          (t,)).fetchone()
    check("tagging a NEW lead records who did it",
          tb["touched_by"] == "kerry" and tb["status"] == "touched", dict(tb))
    t2 = plant(p_db, "NoAuthor")
    leads.set_lead_tag(t2, "Texted", db_path=p_db)
    with db._connect(p_db) as conn:
        tb2 = conn.execute("SELECT touched_by FROM leads WHERE id = ?",
                           (t2,)).fetchone()
    check("no author supplied leaves it NULL rather than blank",
          tb2["touched_by"] is None, dict(tb2))

    os.unlink(p)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
