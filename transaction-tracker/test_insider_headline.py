"""Insider headline rotation (Kerry 2026-09-16: "We copied the Brevo title
from last week"): never repeat last week's title; the fraction headline is
Kerry's shape; last_insider_headline reads the draft ping before as-of."""
import os, sys, tempfile
os.environ.setdefault("DATABASE_PATH", ":memory:")
sys.path.insert(0, os.path.dirname(__file__))
from datetime import date
from email_parser import database as db
from email_parser.insider import pick_headline, _fraction_headline, last_insider_headline

DEFAULT = "You don't have to be the best golfer out here to get paid"
c = ["First round. First payday.", "A par won money Tuesday", "Half the Field Won Money!", DEFAULT]
assert pick_headline(c, None) == "First round. First payday."
assert pick_headline(c, "First round. First payday.") == "A par won money Tuesday"
assert pick_headline(c, "first round. first payday. ") == "A par won money Tuesday"
assert pick_headline([None, None, "Half the Field Won Money!", DEFAULT], "Half the Field Won Money!") == DEFAULT
assert pick_headline([None, None, None, DEFAULT], DEFAULT) == DEFAULT, "default may repeat when nothing else is left"
assert _fraction_headline(17, 33) == "Half the Field Won Money!"
assert _fraction_headline(8, 12) == "Two-Thirds of the Field Won Money!"
assert _fraction_headline(9, 21) == "A Third of the Field Won Money!"
assert _fraction_headline(2, 21) is None and _fraction_headline(0, 0) is None

tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); tmp.close(); p = tmp.name
db.init_db(p)
with db._connect(p) as conn:
    conn.execute("INSERT INTO message_log (event_name, channel, recipient_address, subject, status, sent_at) VALUES "
                 "('insider-draft','email','k@x','Insider draft ready — TGF Insider | First round. First payday.','sent','2026-09-10 15:00:00')")
    conn.execute("INSERT INTO message_log (event_name, channel, recipient_address, subject, status, sent_at) VALUES "
                 "('insider-draft','email','k@x','TGF Insider | Half the Field Won Money!','sent','2026-09-16 13:00:00')")
    conn.commit()
assert last_insider_headline(db_path=p, before=date(2026, 9, 16)) == "First round. First payday."
assert last_insider_headline(db_path=p, before=date(2026, 9, 17)) == "Half the Field Won Money!"
assert last_insider_headline(db_path=p, before=date(2026, 9, 1)) is None
os.unlink(p)
print("ALL PASSED")
