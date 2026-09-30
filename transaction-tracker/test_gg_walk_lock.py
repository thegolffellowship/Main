"""The Golf Genius results/flights walks never hold the write lock across a
network fetch (Tracker Health, digest #1008): 9/29 6:11 PM a live scorer's
save failed "database is locked" while the hourly walk fetched GG pages
inside an open write transaction."""
import os, sys, sqlite3, tempfile, inspect, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ["PERF_SAMPLES"] = "0"
from email_parser import database as db

F = []
def check(label, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + label + ("" if ok else f"  {detail}"))
    if not ok: F.append(label)

p = os.path.join(tempfile.mkdtemp(), "lock.db")
a = sqlite3.connect(p); a.execute("PRAGMA journal_mode=WAL"); a.execute("CREATE TABLE t (v)"); a.commit()
a.execute("INSERT INTO t VALUES (1)")                       # the walk's open write
b = sqlite3.connect(p, timeout=0.2)
try:
    b.execute("INSERT INTO t VALUES (2)"); b.commit(); blocked = False
except sqlite3.OperationalError:
    blocked = True
check("an open write transaction blocks another writer (the 9/29 condition)", blocked)
db._commit_before_network([a])                              # what fetch() now does first
b.execute("INSERT INTO t VALUES (3)"); b.commit()
check("after the pre-fetch commit a scorer's write goes straight through",
      [r[0] for r in b.execute("SELECT v FROM t ORDER BY v")] == [1, 3])
db._commit_before_network([a]); db._commit_before_network([])  # no-op when nothing is open
check("the pre-fetch commit is a no-op with nothing pending", not a.in_transaction)

for fn in (db.import_gg_game_results, db.import_gg_game_flights):
    src = inspect.getsource(fn)
    m = re.search(r"def fetch\(.*?\):\n(.*?)\n\s*return page", src, re.S)
    body = m.group(1) if m else ""
    check(f"{fn.__name__}: fetch() commits before it calls Golf Genius",
          "_commit_before_network(_open)" in body
          and body.index("_commit_before_network") < body.index("fetch_public_page"))
    check(f"{fn.__name__}: the walk's connection is registered for it",
          re.search(r"with _connect\(db_path\) as conn:\n\s+_open\.append\(conn\)", src) is not None)

print(); print("ALL PASS" if not F else f"FAILED: {F}"); sys.exit(1 if F else 0)
