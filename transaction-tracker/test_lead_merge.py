"""Tests for duplicate-lead detection and merge (Kerry 2026-09-03).

  "I see we have two Shane Winters. Those need to be merged. I thought
   we already merged them on HubSpot side."

Throwaway SQLite database; checks:
  - duplicates are found by email, by phone (last 10 digits, so +1 and
    formatting differences still match), and by full name;
  - the suggested keeper is the row carrying the most work;
  - merge folds notes across, takes the strongest status, the earliest
    dates, fills blank fields from the loser, and recovers payload keys
    the keeper lacks (an earlier survey's answers survive);
  - the loser is marked merged_into and dismissed but NEVER deleted —
    its external_id must stay or the next HubSpot poll re-creates it;
  - merged rows drop out of get_leads and out of the duplicate report;
  - dry run changes nothing; self-merge and double-merge are refused;
  - unmerge puts the row back.

Run: python3 test_lead_merge.py
"""

import json
import os
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


def plant(conn, ext, first, last, email, phone, status="new", tag=None,
          arrived="2026-09-01 12:00:00", payload=None, cid=None, notes=0):
    conn.execute(
        "INSERT INTO leads (source, external_id, first_name, last_name, email, "
        "phone, chapter, status, tag, payload, arrived_at, customer_id) "
        "VALUES ('hubspot', ?, ?, ?, ?, ?, 'San Antonio', ?, ?, ?, ?, ?)",
        (ext, first, last, email, phone, status, tag,
         json.dumps(payload or {}), arrived, cid))
    lid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    for i in range(notes):
        conn.execute("INSERT INTO lead_notes (lead_id, author, note) "
                     "VALUES (?, 'K', ?)", (lid, f"note {i} on {ext}"))
    return lid


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, "
                     "customer_id INTEGER, transaction_status TEXT, merchant TEXT, item_name TEXT, parent_item_id INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS customers (customer_id INTEGER "
                     "PRIMARY KEY, first_name TEXT, last_name TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY "
                     "KEY, value TEXT, updated_at TEXT)")
        leads.ensure_leads_table(conn)
        # The Shane Winter shape: two HubSpot contacts, same person. The
        # older row carries the work; the newer carries a later survey.
        old_id = plant(conn, "hs-1", "Shane", "Winter", "shane.winter@x.com",
                       "+12108754541", status="touched", tag="Texted",
                       arrived="2026-08-28 09:00:00", notes=2, cid=42,
                       payload={"can_you_play_tuesdays_or_saturdays":
                                "yes_-_i_can_play_tuesdays",
                                "old_survey_answer": "kept"})
        new_id = plant(conn, "hs-2", "Shane", "Winter", None,
                       "(210) 875-4541", status="converted",
                       tag="Became member", arrived="2026-09-01 17:53:00",
                       notes=1,
                       payload={"can_you_play_tuesdays_or_saturdays":
                                "yes_-_i_can_play_both_tuesdays_or_saturdays",
                                "new_survey_answer": "recovered"})
        # same email, different person-ish rows
        e1 = plant(conn, "hs-3", "Chris", "A", "dup@x.com", "+12105550001")
        e2 = plant(conn, "hs-4", "Chris", "B", "DUP@X.com ", "+12105550002")
        # a lone lead
        solo = plant(conn, "hs-5", "Solo", "Player", "solo@x.com", "+12105559999")
        conn.commit()

    print("Detection")
    d = leads.find_duplicate_leads(p)
    ids = [g["lead_ids"] for g in d["groups"]]
    check("finds the phone/name pair (formatting differs)",
          sorted([old_id, new_id]) in ids, ids)
    check("finds the email pair (case + whitespace normalized)",
          sorted([e1, e2]) in ids, ids)
    check("a lone lead is not a group",
          not any(solo in g for g in ids), ids)
    shane = [g for g in d["groups"] if sorted([old_id, new_id]) == g["lead_ids"]][0]
    check("matched on both phone and name",
          set(shane["matched_on"]) == {"phone", "name"}, shane["matched_on"])
    check("suggests keeping the row with the strongest status",
          shane["suggested_keep"] == new_id, shane["suggested_keep"])

    print("Dry run")
    pre = leads.find_duplicate_leads(p)["duplicate_groups"]
    dry = leads.merge_leads(new_id, old_id, dry_run=True, db_path=p)
    check("dry run reports the notes it would move", dry["notes_moved"] == 2, dry)
    check("dry run reports the payload keys it would recover",
          dry["payload_keys_recovered"] == ["old_survey_answer"], dry)
    check("dry run changes nothing",
          leads.find_duplicate_leads(p)["duplicate_groups"] == pre)

    print("Merge")
    res = leads.merge_leads(new_id, old_id, author="Kerry", db_path=p)
    check("merge reports ok", res.get("ok"), res)
    with db._connect(p) as conn:
        keep = dict(conn.execute("SELECT * FROM leads WHERE id = ?",
                                 (new_id,)).fetchone())
        drop = dict(conn.execute("SELECT * FROM leads WHERE id = ?",
                                 (old_id,)).fetchone())
        kn = conn.execute("SELECT COUNT(*) FROM lead_notes WHERE lead_id = ?",
                          (new_id,)).fetchone()[0]
        dn = conn.execute("SELECT COUNT(*) FROM lead_notes WHERE lead_id = ?",
                          (old_id,)).fetchone()[0]
    check("all notes moved to the keeper (2 + 1 + the merge note)",
          kn == 4 and dn == 0, (kn, dn))
    check("keeper keeps the stronger status + tag",
          keep["status"] == "converted" and keep["tag"] == "Became member", keep)
    check("keeper takes the EARLIEST arrival (the true first contact)",
          keep["arrived_at"] == "2026-08-28 09:00:00", keep["arrived_at"])
    check("blank field filled from the loser (email)",
          keep["email"] == "shane.winter@x.com", keep["email"])
    check("blank customer_id filled from the loser", keep["customer_id"] == 42,
          keep["customer_id"])
    kp = json.loads(keep["payload"])
    check("earlier survey's unique answer recovered",
          kp.get("old_survey_answer") == "kept", kp)
    check("keeper's own answer still wins on a conflict",
          kp["can_you_play_tuesdays_or_saturdays"]
          == "yes_-_i_can_play_both_tuesdays_or_saturdays", kp)
    check("loser is marked merged_into + dismissed",
          drop["merged_into"] == new_id and drop["status"] == "dismissed", drop)
    check("loser is NEVER deleted — its external_id stays as the dedup key",
          drop["external_id"] == "hs-1", drop)

    print("Queue reads")
    live = [l["id"] for l in leads.get_leads(limit=100, db_path=p)]
    check("merged row drops out of the queue",
          new_id in live and old_id not in live, live)
    d2 = leads.find_duplicate_leads(p)
    check("merged pair no longer reported as duplicates",
          sorted([old_id, new_id]) not in [g["lead_ids"] for g in d2["groups"]],
          [g["lead_ids"] for g in d2["groups"]])
    check("the other duplicate pair is still reported",
          sorted([e1, e2]) in [g["lead_ids"] for g in d2["groups"]])

    print("Guards")
    check("self-merge refused", leads.merge_leads(new_id, new_id, db_path=p).get("error"))
    check("re-merging an already-merged row refused",
          leads.merge_leads(new_id, old_id, db_path=p).get("error"))
    check("merging INTO a merged row refused",
          leads.merge_leads(old_id, e1, db_path=p).get("error"))
    check("unknown id refused", leads.merge_leads(new_id, 9999, db_path=p).get("error"))

    print("Unmerge")
    u = leads.unmerge_lead(old_id, db_path=p)
    check("unmerge restores the row", u.get("ok"), u)
    check("restored row is back in the queue",
          old_id in [l["id"] for l in leads.get_leads(limit=100, db_path=p)])
    check("unmerging a live row refused", leads.unmerge_lead(e1, db_path=p).get("error"))

    os.unlink(p)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
