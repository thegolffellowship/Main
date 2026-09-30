"""Schema audit (#1064-2 / #1067-2): read-only, and it finds the chapter text
column and a money column stored as text."""
import contextlib, io, os, sqlite3, tempfile
from email_parser import database as db, schema_audit as sa


def _db():
    tmp = os.path.join(tempfile.mkdtemp(), "t.db")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        db.init_db(tmp)
    k = sqlite3.connect(tmp)
    k.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter) VALUES "
              "(1,'A','B','San Antonio'),(2,'C','D','SATX'),(3,'E','F','austin'),(4,'G','H',NULL)")
    k.commit(); k.close()
    return tmp


def _snapshot(path):
    k = sqlite3.connect(path)
    out = {t: k.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
           for (t,) in k.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    k.close()
    return out


def test_chapter_dry_run_counts_and_writes_nothing():
    tmp = _db()
    before = _snapshot(tmp)
    d = sa.chapter_dry_run(tmp)
    assert (d["customers_total"], d["would_resolve"], d["blank"], d["unresolved_text"]) == (4, 2, 1, 1)
    assert [r["customer_id"] for r in d["unresolved_rows"]] == [2]
    assert d["applied"] is False and "customer_chapter_history" in d["proposed_migration"]
    assert _snapshot(tmp) == before


def test_scan_finds_customers_chapter_and_writes_nothing():
    tmp = _db()
    before = _snapshot(tmp)
    s = sa.redundancy_scan(tmp)
    assert s["errors"] == [] and s["writes"] == 0
    hit = [r for r in s["rows"] if r["table"] == "customers" and r["column"] == "chapter"]
    assert hit and hit[0]["entity"] == "chapter" and hit[0]["names_matching_nothing"] == 1
    assert _snapshot(tmp) == before
