"""Tests for the Hole-In-One pot CARRY-IN (Kerry 2026-07-31: "Hole In One
Pot is not persisting").

`get_hio_pot` has read `hio_pot_carry_in` from app_settings since
2026-07-20, but NOTHING in the app ever wrote it — no route, no UI, no MCP
tool. So the carry-in could not be set or corrected, and the running pot
only ever showed what the Tracker itself had accrued.

Run: python3 test_hio_carry_in.py
"""

import os
import sys
import sqlite3
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


fd, path = tempfile.mkstemp(suffix=".db")
os.close(fd)
db.init_db(path)

print("\n== the carry-in round-trips through app_settings ==")

check("it starts unset", db.get_app_setting("hio_pot_carry_in", db_path=path)
      in (None, ""), repr(db.get_app_setting("hio_pot_carry_in", db_path=path)))

pot = db.get_hio_pot(db_path=path)
check("an unset carry-in reads as 0, not an error",
      pot.get("carry_in") == 0, str(pot.get("carry_in")))
base_pot = pot.get("pot")

db.set_app_setting("hio_pot_carry_in", "1822.0", db_path=path)
db.set_app_setting("hio_pot_carry_in_note", "Ratified 2026-07-20", db_path=path)

pot = db.get_hio_pot(db_path=path)
check("the ratified $1,822 is picked up", pot.get("carry_in") == 1822.0,
      str(pot.get("carry_in")))
check("the provenance note comes back too",
      pot.get("carry_in_note") == "Ratified 2026-07-20",
      str(pot.get("carry_in_note")))
check("the running pot moves by exactly the carry-in",
      round(pot.get("pot") - base_pot, 2) == 1822.0,
      f'{pot.get("pot")} vs {base_pot}')

print("\n== it SURVIVES a reconnect (this is the persistence claim) ==")

# A fresh connection to the same file is what a redeploy looks like to the
# app, provided DATABASE_PATH points at the Railway volume.
again = db.get_hio_pot(db_path=path)
check("a new read still sees the carry-in", again.get("carry_in") == 1822.0,
      str(again.get("carry_in")))
raw = sqlite3.connect(path)
row = raw.execute("SELECT value FROM app_settings WHERE key = ?",
                  ("hio_pot_carry_in",)).fetchone()
raw.close()
check("it is stored in app_settings, not in memory", row is not None and row[0] == "1822.0",
      str(row))

print("\n== corrections overwrite rather than accumulate ==")

db.set_app_setting("hio_pot_carry_in", "2000.0", db_path=path)
pot = db.get_hio_pot(db_path=path)
check("a corrected value replaces the old one", pot.get("carry_in") == 2000.0,
      str(pot.get("carry_in")))
check("the running pot follows the correction",
      round(pot.get("pot") - base_pot, 2) == 2000.0, str(pot.get("pot")))

print("\n== the endpoint's input parsing ==")


def parse(raw):
    """Mirror of api_set_hio_carry_in's coercion."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        v = round(float(str(raw).replace("$", "").replace(",", "").strip()), 2)
    except (TypeError, ValueError):
        return None
    return None if v < 0 else v


check("a plain number is accepted", parse("1822") == 1822.0)
check("a typed dollar sign is tolerated", parse("$1822") == 1822.0)
check("thousands separators are tolerated", parse("1,822.00") == 1822.0)
check("surrounding whitespace is tolerated", parse("  1822.5 ") == 1822.5)
check("a blank is rejected", parse("") is None)
check("a non-number is rejected", parse("abc") is None)
check("a negative pot is rejected", parse("-5") is None)
check("zero is allowed (a legitimate reset)", parse("0") == 0.0)

os.unlink(path)

print("\n" + ("ALL PASS" if not FAILURES else f"{len(FAILURES)} FAILED"))
for f in FAILURES:
    print("  -", f)
sys.exit(1 if FAILURES else 0)
