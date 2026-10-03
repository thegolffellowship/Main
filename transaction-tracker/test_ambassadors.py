"""customer_ambassadors — the Ambassador flag (Pairings Spec v1.2 #1036-4;
approved CoS #1046; shape Tracker Build #1055).
Run: python3 test_ambassadors.py"""
import os, sys, json, sqlite3, tempfile, contextlib, io, logging, pathlib, re
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-amb-"), "t.db")
os.environ["DATABASE_PATH"] = DB; os.environ.setdefault("SECRET_KEY", "x")
logging.disable(logging.CRITICAL)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)
    import mcp_server
from email_parser import ambassadors as amb

c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
check("migration 0002 applied once and recorded", c.execute(
    "SELECT COUNT(*) FROM schema_migrations WHERE name = '0002_customer_ambassadors.sql'").fetchone()[0] == 1)

# Fixture: a chapter, two customers, and mailbox posts with / without Kerry's word.
if not c.execute("SELECT 1 FROM chapters WHERE lower(name) = 'san antonio'").fetchone():
    c.execute("INSERT INTO chapters (name, short_code) VALUES ('San Antonio', 'SA')")
sa = c.execute("SELECT chapter_id FROM chapters WHERE lower(name) = 'san antonio'").fetchone()[0]
c.execute("INSERT INTO customers (customer_id, first_name, last_name, gender, current_player_status) "
          "VALUES (9001, 'Mary', 'Wade', 'F', 'active_member')")
c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (9002, 'Jim', 'Test')")
c.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
          "VALUES (9003, 'Ian', 'Intro', 'active_member')")
c.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
          "VALUES (9004, 'Al', 'Alumni', 'expired_member')")
# Established: 3 posted differentials inside the lookback (Mary, Al); Ian has one.
import datetime as _dt
_d = (_dt.date.today() - _dt.timedelta(days=10)).isoformat()
for _nm, _cid, _n in (("Mary Wade", 9001, 3), ("Al Alumni", 9004, 3), ("Ian Intro", 9003, 1)):
    c.execute("INSERT INTO handicap_player_links (player_name, customer_id) VALUES (?, ?)", (_nm, _cid))
    for _i in range(_n):
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, differential) "
                  "VALUES (?, ?, 90, 72.0, 113, ?)",
                  (_nm, _d, 10.0 + _i))
kerry = c.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES "
                  "('platform-claude', 'pairings', 'Kerry: \"Mary Wade is an Ambassador.\"') "
                  "RETURNING id").fetchone()[0]
lane = c.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES "
                 "('tracker-claude', 'pairings', 'Kerry would want Mary as an ambassador') "
                 "RETURNING id").fetchone()[0]
c.commit()

r = amb.set_ambassador(9001, "SA", True, lane, db_path=DB)
check("refused without Kerry's word (a lane post that only mentions him)", "refused" in r, r)
r = amb.set_ambassador(9001, "Nowhere", True, kerry, db_path=DB)
check("an unknown chapter is refused", "refused" in r and "chapter" in r["refused"], r)
r = amb.set_ambassador(9003, "SA", True, kerry, db_path=DB)
check("#1080-1: an intro handicap (not established) cannot be an Ambassador",
      "refused" in r and "established" in r["refused"], r)
r = amb.set_ambassador(9004, "SA", True, kerry, db_path=DB)
check("#1080-1: an alumnus (expired) cannot be an Ambassador",
      "refused" in r and "not a member" in r["refused"], r)
r = amb.set_ambassador(9002, "SA", True, kerry, db_path=DB)
check("#1080-1: a guest with no status cannot be an Ambassador", "refused" in r, r)
r = amb.set_ambassador(9001, "SA", True, kerry, note="Kerry #test", db_path=DB)
check("dry run by default: says what it would do, writes nothing",
      r["dry_run"] and r["changed"] and c.execute("SELECT COUNT(*) FROM customer_ambassadors").fetchone()[0] == 0, r)
r = amb.set_ambassador(9001, "San Antonio", True, kerry, note="Kerry #test", apply=True, db_path=DB)
check("applied: chapter resolves by name or short code; row written", r.get("applied") and r["chapter_id"] == sa, r)
check("the ONE reader returns her", amb.chapter_ambassadors(c, sa) == {9001})
r = amb.set_ambassador(9001, "SA", True, kerry, apply=True, db_path=DB)
check("setting the same value again changes nothing", r["changed"] is False and not r.get("applied"), r)
r = amb.set_ambassador(9002, "SA", False, kerry, apply=True, db_path=DB)
check("removing someone who was never an ambassador is a no-op", r["changed"] is False, r)
r = amb.set_ambassador(9001, "SA", False, kerry, note="stepped back", apply=True, db_path=DB)
row = c.execute("SELECT ambassador, note FROM customer_ambassadors WHERE customer_id = 9001").fetchone()
check("unflag KEEPS the row (ambassador = 0, with the note) — never deleted",
      r.get("applied") and row is not None and row["ambassador"] == 0 and row["note"] == "stepped back", dict(row) if row else None)
check("...and the reader no longer returns her", amb.chapter_ambassadors(c, sa) == set())
lst = amb.list_ambassadors("SA", include_removed=True, db_path=DB)
check("list with history shows the removed row; default list hides it",
      lst["count"] == 1 and amb.list_ambassadors("SA", db_path=DB)["count"] == 0, lst)
logs = c.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type = 'set_ambassador'").fetchone()[0]
check("every applied change is action-logged (2 changes -> 2 rows)", logs == 2, logs)

out = json.loads(mcp_server._scoring_dispatch("", "scoring-ambassadors:SA|all"))
check("bridge scoring-ambassadors reads", out.get("count") == 1, out)
out = json.loads(mcp_server._scoring_dispatch("", "scoring-ambassador-set:" + json.dumps(
    {"customer_id": 9001, "chapter": "SA", "on": True, "kerry_ok_post": kerry})))
check("bridge scoring-ambassador-set is a dry run unless apply", out.get("dry_run") is True, out)
# #1116-4 backfill: an eligible Ambassador with the chip on and NO row,
# flagged ON again, inserts a row; the dry run must say so ("changed" was
# False for all 13). Mary (9001) is gate-eligible; take her row away.
_saved_row = c.execute("SELECT ambassador, set_by, set_at, note FROM customer_ambassadors WHERE customer_id = 9001").fetchone()
_saved_chip = c.execute("SELECT ambassador FROM customers WHERE customer_id = 9001").fetchone()[0]
c.execute("DELETE FROM customer_ambassadors WHERE customer_id = 9001")
c.execute("UPDATE customers SET ambassador = 1 WHERE customer_id = 9001")
c.commit()
r = amb.set_ambassador(9001, "SA", True, kerry, note="backfill", db_path=DB)
check("#1116-4: chip on, no row, flag on: the dry run reports a change (it inserts a row)",
      r.get("changed") is True and r.get("dry_run") is True and "refused" not in r, r)
r = amb.set_ambassador(9001, "SA", True, kerry, note="backfill", apply=True, db_path=DB)
check("#1116-4: applied, the row exists; a repeat is then no change",
      c.execute("SELECT ambassador FROM customer_ambassadors WHERE customer_id = 9001").fetchone()[0] == 1
      and amb.set_ambassador(9001, "SA", True, kerry, db_path=DB).get("changed") is False, r)
# put Mary back exactly as the earlier checks left her
c.execute("DELETE FROM customer_ambassadors WHERE customer_id = 9001")
if _saved_row is not None:
    c.execute("INSERT INTO customer_ambassadors (customer_id, chapter_id, ambassador, set_by, set_at, note) "
              "VALUES (9001, ?, ?, ?, ?, ?)", (sa, *_saved_row))
c.execute("UPDATE customers SET ambassador = ? WHERE customer_id = 9001", (_saved_chip,))
c.commit()
# #1110 (Rolando): a 9/15-seeded Ambassador carries the CHIP
# (customers.ambassador = 1) and no customer_ambassadors row. Rescinding must
# clear the chip AND leave a kept row (ambassador = 0), not "nothing to remove".
c.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status, ambassador) "
          "VALUES (9005, 'Rolo', 'Seeded', 'active_member', 1)")
c.commit()
r = amb.set_ambassador(9005, "SA", False, kerry, note="auto-rescind standard", db_path=DB)
check("#1110 dry run: a seeded chip with no row reads as an Ambassador and would change",
      r.get("before") is True and r.get("changed") is True and r.get("dry_run") is True, r)
r = amb.set_ambassador(9005, "SA", False, kerry, note="auto-rescind standard", apply=True, db_path=DB)
_chip = c.execute("SELECT ambassador FROM customers WHERE customer_id = 9005").fetchone()[0]
_row = c.execute("SELECT ambassador, note FROM customer_ambassadors WHERE customer_id = 9005").fetchone()
check("#1110 applied: the chip is off and a row is kept (ambassador 0, with the note)",
      r.get("applied") and _chip == 0 and _row is not None and _row[0] == 0 and _row[1] == "auto-rescind standard",
      (r, _chip, _row))
r = amb.set_ambassador(9005, "SA", False, kerry, apply=True, db_path=DB)
check("#1110 a second rescind changes nothing", not r.get("applied"), r)
_chip_mary = c.execute("SELECT ambassador FROM customers WHERE customer_id = 9001").fetchone()[0]
check("the chip mirrors every applied change (Mary was set then unset)", _chip_mary == 0, _chip_mary)
check("the reader survives a database without the table", amb.chapter_ambassadors(sqlite3.connect(":memory:"), 1) == set())

# Guard (#1055-6): only this module (and the migration) names the table,
# plus set_customer_field's existence probe. Pairings code reads the reader.
root = pathlib.Path(__file__).resolve().parent
allowed = {"email_parser/ambassadors.py", "email_parser/customer_query.py", "test_ambassadors.py"}
_q = re.compile(r"(FROM|INTO|UPDATE|JOIN)\s+customer_ambassadors", re.IGNORECASE)
bad = [str(p.relative_to(root)) for p in list(root.glob("*.py")) + list(root.glob("email_parser/*.py"))
       if str(p.relative_to(root)) not in allowed
       and _q.search(p.read_text(encoding="utf-8", errors="ignore"))]
check("no other module queries customer_ambassadors directly", not bad, bad)
sql = (root / "migrations/0002_customer_ambassadors.sql").read_text()
check("portable SQL: no INSERT OR REPLACE, no COLLATE NOCASE",
      "INSERT OR REPLACE" not in sql.upper() and "NOCASE" not in sql.upper())

print()
if F:
    print(f"FAILED ({len(F)}): {F}"); sys.exit(1)
print("ALL AMBASSADOR TESTS PASSED")
