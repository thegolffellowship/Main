"""System message templates must reach deployments that already booted,
and the compose audience must not fall open.

Two defects are pinned here:

1. The system-template seed ran only when the table held NO system rows
   ("on first run"). Every deployment seeded once in 2026; a template
   added to the list afterwards would never have appeared on any of
   them — the backfill rule (#405) in reverse. Kerry asked for a
   Fellowship preset; without this fix he would have seen nothing.
   Re-seeding must also NOT overwrite a template he has edited.

2. /api/messages/send matched the audience with a chain of elif and an
   `else: filtered.append(r)` fallback, so an unrecognised audience —
   a typo, a stale client, a renamed option — mailed the ENTIRE roster
   instead of nobody.

Run: python3 -m pytest test_message_presets.py -q
"""
import re
import sqlite3
import tempfile
from pathlib import Path

import email_parser.database as db


def _fresh_db():
    d = Path(tempfile.mkdtemp()) / "t.db"
    db.init_db(str(d))
    return d


def test_fellowship_template_is_seeded():
    d = _fresh_db()
    with sqlite3.connect(d) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM message_templates WHERE name LIKE 'Fellowship%'"
        ).fetchall()
    assert len(rows) == 1, "expected exactly one Fellowship template"
    t = rows[0]
    assert t["is_system"] == 1
    # Kerry's two asks must both be in the copy.
    assert "[MEETING SPOT]" in t["html_body"], "no place to put the venue"
    assert "headcount" in t["html_body"], "no nudge to correct the count"
    assert "{player_name}" in t["html_body"]
    assert "{event_name}" in t["subject"]


def test_seed_reaches_a_database_that_already_seeded():
    """The real production shape: a DB seeded BEFORE the template existed."""
    d = _fresh_db()
    with sqlite3.connect(d) as c:
        c.execute("DELETE FROM message_templates WHERE name LIKE 'Fellowship%'")
        before = c.execute("SELECT COUNT(*) FROM message_templates").fetchone()[0]
    assert before > 0, "table must be non-empty — that is the whole trap"

    db.init_db(str(d))  # boot again

    with sqlite3.connect(d) as c:
        after = c.execute(
            "SELECT COUNT(*) FROM message_templates WHERE name LIKE 'Fellowship%'"
        ).fetchone()[0]
    assert after == 1, "the new template never reached an already-seeded DB"


def test_reseeding_does_not_revert_an_edited_template():
    d = _fresh_db()
    with sqlite3.connect(d) as c:
        c.execute("UPDATE message_templates SET html_body = 'KERRY EDITED THIS' "
                  "WHERE name LIKE 'Fellowship%'")

    db.init_db(str(d))

    with sqlite3.connect(d) as c:
        body = c.execute(
            "SELECT html_body FROM message_templates WHERE name LIKE 'Fellowship%'"
        ).fetchone()[0]
    assert body == "KERRY EDITED THIS", "re-seed clobbered a hand-edited template"


def test_no_duplicates_after_repeated_boots():
    d = _fresh_db()
    db.init_db(str(d))
    db.init_db(str(d))
    with sqlite3.connect(d) as c:
        n = c.execute("SELECT COUNT(*) FROM message_templates "
                      "WHERE is_system = 1").fetchone()[0]
        distinct = c.execute("SELECT COUNT(DISTINCT name) FROM message_templates "
                             "WHERE is_system = 1").fetchone()[0]
    assert n == distinct, "boot re-inserted system templates"


def test_send_rejects_an_unknown_audience():
    src = Path("app.py").read_text(encoding="utf-8")
    assert "VALID_AUDIENCES" in src
    m = re.search(r"VALID_AUDIENCES = \{(.*?)\}", src, re.S)
    assert m, "audience allowlist not found"
    assert "fellowship" in m.group(1)
    assert re.search(
        r"if audience not in VALID_AUDIENCES:\s*\n\s*return jsonify\("
        r'\{"error": f"unknown audience', src), \
        "an unrecognised audience must 400, not mail the whole roster"


def test_send_has_a_fellowship_branch():
    src = Path("app.py").read_text(encoding="utf-8")
    assert re.search(
        r'elif audience == "fellowship":[\s\S]{0,400}?'
        r'r\.get\("fellowship"\)[\s\S]{0,80}?startswith\("Y"\)', src), \
        "server-side fellowship filter missing — the client filter alone " \
        "would let the server fall through to everyone"
