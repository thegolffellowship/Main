"""Home chapter by id (Kerry APPROVED, CoS #1084): migration 0004, the
reported backfill from customers.chapter (never from play), and the one
setter that closes/opens history rows."""
import contextlib, io, os, sqlite3, tempfile
from email_parser import database as db, home_chapter as hc


def _db():
    tmp = os.path.join(tempfile.mkdtemp(), "t.db")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        db.init_db(tmp)
    k = sqlite3.connect(tmp)
    k.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, current_player_status) VALUES "
              "(1,'A','Sa','San Antonio','active_member'),(2,'B','Aus','austin','active_member'),"
              "(3,'C','Blank',NULL,'active_member'),(4,'D','Code','SA','inactive'),"
              "(5,'E','Weird','Mars',NULL)")
    k.execute("INSERT INTO customers (customer_id, first_name, last_name, acquisition_source) VALUES (394,'Anthropic','','vendor')")
    k.commit(); k.close()
    return tmp


def test_migration_applied_on_a_fresh_database():
    tmp = _db()
    k = sqlite3.connect(tmp)
    cols = {r[1] for r in k.execute("PRAGMA table_info(customers)")}
    ch_cols = {r[1] for r in k.execute("PRAGMA table_info(chapters)")}
    assert "home_chapter_id" in cols and {"manager_customer_id", "sender_email"} <= ch_cols and "gg_portal_ids" not in ch_cols
    assert k.execute("SELECT 1 FROM schema_migrations WHERE name = '0005_home_chapter.sql'").fetchone()


def test_backfill_dry_run_then_apply():
    tmp = _db()
    d = hc.backfill_home_chapters(db_path=tmp)
    assert d["dry_run"] and d["would_set"] == 3 and d["blank"] == 1
    assert [u["chapter"] for u in d["unresolved"]] == ["Mars"]
    a = hc.backfill_home_chapters(apply=True, db_path=tmp)
    assert a["set"] == 3
    k = sqlite3.connect(tmp)
    got = dict(k.execute("SELECT customer_id, home_chapter_id FROM customers WHERE customer_id IN (1,2,3,4,394)"))
    sa, aus = [k.execute("SELECT chapter_id FROM chapters WHERE name=?", (n,)).fetchone()[0] for n in ("San Antonio", "Austin")]
    assert got == {1: sa, 2: aus, 3: None, 4: sa, 394: None}
    assert k.execute("SELECT COUNT(*) FROM customer_chapter_history WHERE to_date IS NULL").fetchone()[0] == 3
    assert hc.backfill_home_chapters(apply=True, db_path=tmp)["set"] == 0   # idempotent


def test_a_move_is_a_new_history_row():
    tmp = _db()
    hc.backfill_home_chapters(apply=True, db_path=tmp)
    r = hc.set_home_chapter(1, "Austin", "test ruling", db_path=tmp)
    assert r["after"] == "Austin"
    k = sqlite3.connect(tmp)
    rows = k.execute("SELECT chapter_id, to_date FROM customer_chapter_history WHERE customer_id=1 ORDER BY id").fetchall()
    aus = k.execute("SELECT chapter_id FROM chapters WHERE name='Austin'").fetchone()[0]
    assert len(rows) == 2 and rows[0][1] is not None and rows[1] == (aus, None)
    assert k.execute("SELECT home_chapter_id, chapter FROM customers WHERE customer_id=1").fetchone() == (aus, "Austin")
