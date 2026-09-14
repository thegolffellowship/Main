"""CA QUEUE tests (mailbox #473/#474 — Kerry directed 2026-09-11).

Covers the DB layer end to end: insert / upsert-by-title / upsert-by-id,
enum validation, append-only notes, done-never-deletes, reopen keeps
history, move + reorder, and list grouping order.

Run: python3 test_ca_queue.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_parser import database as db  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    dbp = tmp.name

    print("== insert & list ==")
    r1 = db.upsert_ca_queue_item(
        {"title": "Ratify team-net schema import", "section": "kerry_decision",
         "owner": "kerry", "mailbox_ref": "472"},
        author="tracker-claude", db_path=dbp)
    check("insert returns ok+created", r1.get("ok") and r1.get("created"), r1)
    r2 = db.upsert_ca_queue_item(
        {"title": "Post ca-queue seed JSON", "section": "ca_owed",
         "owner": "ca"}, author="platform-claude", db_path=dbp)
    r3 = db.upsert_ca_queue_item(
        {"title": "Backup restore drill", "section": "finance_cleanup"},
        author="tracker-claude", db_path=dbp)
    check("three inserts distinct ids",
          len({r1["id"], r2["id"], r3["id"]}) == 3)

    lst = db.list_ca_queue(db_path=dbp)
    check("list has 3 items, all open",
          len(lst["items"]) == 3 and lst["n_open"] == 3 and lst["n_done"] == 0, lst)
    check("sections enum order in payload",
          lst["sections"][0] == "kerry_decision" and lst["sections"][-1] == "settled")
    check("items grouped by enum order",
          [i["section"] for i in lst["items"]] ==
          ["kerry_decision", "ca_owed", "finance_cleanup"],
          [i["section"] for i in lst["items"]])
    check("created note stamped with author",
          lst["items"][0]["notes_log"] and
          lst["items"][0]["notes_log"][0]["author"] == "tracker-claude",
          lst["items"][0]["notes_log"])

    print("== validation ==")
    bad = db.upsert_ca_queue_item({"title": "x", "section": "nope"}, db_path=dbp)
    check("bad section rejected", "error" in bad, bad)
    bad2 = db.upsert_ca_queue_item({"title": "x", "status": "wip"}, db_path=dbp)
    check("bad status rejected", "error" in bad2, bad2)
    bad3 = db.upsert_ca_queue_item({"section": "parked"}, db_path=dbp)
    check("new item without title rejected", "error" in bad3, bad3)
    bad4 = db.upsert_ca_queue_item({"id": 999, "status": "done"}, db_path=dbp)
    check("unknown id rejected", "error" in bad4, bad4)

    print("== upsert by exact title (case-insensitive) ==")
    r5 = db.upsert_ca_queue_item(
        {"title": "  POST CA-QUEUE SEED JSON ", "status": "blocked",
         "blocked_on": "waiting on deploy confirm", "note": "held per #474"},
        author="platform-claude", db_path=dbp)
    check("title match updates, not inserts",
          r5.get("ok") and not r5.get("created") and r5["id"] == r2["id"], r5)
    row = [i for i in db.list_ca_queue(db_path=dbp)["items"]
           if i["id"] == r2["id"]][0]
    check("blocked status + blocked_on stored",
          row["status"] == "blocked" and "deploy" in row["blocked_on"], row)
    check("inline note appended",
          any("held per #474" in n["note"] for n in row["notes_log"]),
          row["notes_log"])

    print("== notes ==")
    rn = db.note_ca_queue_item(r1["id"], "Kerry said yes verbally, need mailbox",
                               "kerry", db_path=dbp)
    check("note ok", rn.get("ok"), rn)
    row = [i for i in db.list_ca_queue(db_path=dbp)["items"]
           if i["id"] == r1["id"]][0]
    check("note appended with author kerry",
          row["notes_log"][-1]["author"] == "kerry" and
          "verbally" in row["notes_log"][-1]["note"], row["notes_log"])
    rn2 = db.note_ca_queue_item(999, "x", "y", db_path=dbp)
    check("note on unknown id rejected", "error" in rn2, rn2)

    print("== close (done never deletes) & reopen keeps history ==")
    rc = db.close_ca_queue_item(r3["id"], "kerry", db_path=dbp)
    check("close ok", rc.get("ok"), rc)
    lst = db.list_ca_queue(db_path=dbp)
    check("done row still listed", any(i["id"] == r3["id"] for i in lst["items"]))
    row = [i for i in lst["items"] if i["id"] == r3["id"]][0]
    check("done stamps done_at + done_by",
          row["status"] == "done" and row["done_at"] and row["done_by"] == "kerry",
          row)
    check("counts split", lst["n_open"] == 2 and lst["n_done"] == 1, lst)
    done_lst = db.list_ca_queue(status="done", db_path=dbp)
    check("status filter", len(done_lst["items"]) == 1)

    rr = db.upsert_ca_queue_item({"id": r3["id"], "status": "open"},
                                 author="kerry", db_path=dbp)
    check("reopen ok", rr.get("ok"), rr)
    row = [i for i in db.list_ca_queue(db_path=dbp)["items"]
           if i["id"] == r3["id"]][0]
    check("reopen nulls done_at/done_by",
          row["status"] == "open" and not row["done_at"] and not row["done_by"],
          row)
    check("reopen logged in notes",
          any(n["note"].startswith("reopened (was done") for n in row["notes_log"]),
          row["notes_log"])

    print("== move & reorder ==")
    r6 = db.upsert_ca_queue_item({"title": "Second decision item",
                                  "section": "kerry_decision"},
                                 author="tracker-claude", db_path=dbp)
    r7 = db.upsert_ca_queue_item({"title": "Third decision item",
                                  "section": "kerry_decision"},
                                 author="tracker-claude", db_path=dbp)
    ids_before = [i["id"] for i in db.list_ca_queue(
        section="kerry_decision", db_path=dbp)["items"]]
    check("insert appends to section bottom",
          ids_before == [r1["id"], r6["id"], r7["id"]], ids_before)

    rm = db.move_ca_queue_item(r7["id"], position=1, db_path=dbp)
    check("move to position 1 ok", rm.get("ok") and rm["position"] == 1, rm)
    ids_after = [i["id"] for i in db.list_ca_queue(
        section="kerry_decision", db_path=dbp)["items"]]
    check("reorder within section",
          ids_after == [r7["id"], r1["id"], r6["id"]], ids_after)

    rmv = db.move_ca_queue_item(r6["id"], section="parked", db_path=dbp)
    check("cross-section move ok",
          rmv.get("ok") and rmv["section"] == "parked", rmv)
    parked = db.list_ca_queue(section="parked", db_path=dbp)["items"]
    check("row landed in parked",
          len(parked) == 1 and parked[0]["id"] == r6["id"], parked)
    rbad = db.move_ca_queue_item(r6["id"], section="nope", db_path=dbp)
    check("move to bad section rejected", "error" in rbad, rbad)
    rbad2 = db.move_ca_queue_item(999, db_path=dbp)
    check("move unknown id rejected", "error" in rbad2, rbad2)

    print("== inline note on INSERT (v2.380.1 fix) ==")
    r8 = db.upsert_ca_queue_item(
        {"title": "Item born with a note", "section": "followups",
         "note": "context arrives with the row"},
        author="platform-claude", db_path=dbp)
    row = [i for i in db.list_ca_queue(db_path=dbp)["items"]
           if i["id"] == r8["id"]][0]
    check("insert-time note appended after 'created'",
          len(row["notes_log"]) == 2 and
          row["notes_log"][1]["note"] == "context arrives with the row",
          row["notes_log"])

    print("== field updates leave others untouched ==")
    db.upsert_ca_queue_item({"id": r1["id"], "owner": "ca"},
                            author="platform-claude", db_path=dbp)
    row = [i for i in db.list_ca_queue(db_path=dbp)["items"]
           if i["id"] == r1["id"]][0]
    check("owner changed, title/refs intact",
          row["owner"] == "ca" and row["mailbox_ref"] == "472" and
          row["title"] == "Ratify team-net schema import", row)

    os.unlink(dbp)
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
