"""A store title with a bar ("s18.12 FALL CHAMPIONSHIP | Kissing Tree") must
land on ONE event (Kerry 2026-10-18: "But why did the second create to begin
with?"). Two guards: the parser puts the printed title back when the LLM
dropped the part after the bar, and the event sync aliases a short name to the
one recent "<name> | ..." event instead of creating a dateless duplicate.

Run: python3 test_event_title_bar.py
"""
import contextlib, io, logging, os, sqlite3, sys, tempfile
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser.parser import restore_full_title
    DB = os.environ["DATABASE_PATH"]
    db.init_db(DB)

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


body = ("Order Summary\n s18.12 FALL CHAMPIONSHIP | Kissing Tree\n $170.00\n"
        "s9.29 SILVERHORN\n $58.00\n")
print("parser")
check("short name gets its printed venue back",
      restore_full_title("s18.12 FALL CHAMPIONSHIP", body) == "s18.12 FALL CHAMPIONSHIP | Kissing Tree",
      restore_full_title("s18.12 FALL CHAMPIONSHIP", body))
check("a full name is left alone",
      restore_full_title("s18.12 FALL CHAMPIONSHIP | Kissing Tree", body) == "s18.12 FALL CHAMPIONSHIP | Kissing Tree")
check("a name with no bar in the email is left alone",
      restore_full_title("s9.29 SILVERHORN", body) == "s9.29 SILVERHORN")
check("empty stays empty", restore_full_title("", body) == "")

print("event sync")
soon = (date.today() + timedelta(days=13)).isoformat()
c = sqlite3.connect(DB)
c.execute("DELETE FROM events")
c.execute("INSERT INTO events (item_name, event_date) VALUES ('s18.12 FALL CHAMPIONSHIP | Kissing Tree', ?)", (soon,))
c.execute("INSERT INTO items (email_uid, item_index, merchant, order_date, customer, item_name, course) "
          "VALUES ('u1', 0, 'The Golf Fellowship', ?, 'Brian Thompson', 's18.12 FALL CHAMPIONSHIP', 'Kissing Tree')",
          (date.today().isoformat(),))
c.commit()
db.sync_events_from_items(DB)
n = c.execute("SELECT COUNT(*) FROM events WHERE item_name LIKE 's18.12%'").fetchone()[0]
al = c.execute("SELECT canonical_event_name FROM event_aliases WHERE alias_name = 's18.12 FALL CHAMPIONSHIP'").fetchone()
check("no duplicate event is created", n == 1, n)
check("the short name is an alias of the real event",
      al and al[0] == "s18.12 FALL CHAMPIONSHIP | Kissing Tree", al)

print()
if F:
    print(f"{len(F)} FAILED")
    sys.exit(1)
print("ALL PASS")
