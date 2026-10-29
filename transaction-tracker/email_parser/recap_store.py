"""WHERE A NIGHT'S RECAP LIVES (Kerry 2026-10-28, #2460-G: "RECAP LIVES IN
THE TRACKER").

A recap used to be a file in docs/claude/recaps/, so sending it needed a
deploy. A recap the Tracker writes itself (recap_writer.py) is stored in the
database instead, under app setting `event_recap:<key>`, and is named
"db:<key>" everywhere a recap file name is passed (the staff draft email,
the results email schedule). A plain name still reads the repo file, so the
hand-written recaps keep working.
"""
from __future__ import annotations

import json
from pathlib import Path

PREFIX = "db:"
SETTING = "event_recap:{}"
RECAP_DIR = Path(__file__).resolve().parent.parent / "docs" / "claude" / "recaps"


def is_db(name: str | None) -> bool:
    return bool(name) and str(name).startswith(PREFIX)


def _key(name: str) -> str:
    return str(name)[len(PREFIX):]


def save(key: str, md: str, meta: dict | None = None, db_path=None) -> str:
    """Store a recap; returns its name ("db:<key>")."""
    from . import database as db
    db.set_app_setting(SETTING.format(key), json.dumps({"md": md, "meta": meta or {}}),
                       db_path=db_path)
    return PREFIX + key


def load(name: str, db_path=None) -> dict | None:
    from . import database as db
    raw = db.get_app_setting(SETTING.format(_key(name)), db_path=db_path)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def exists(name: str | None, db_path=None) -> bool:
    if not name:
        return False
    if is_db(name):
        return load(name, db_path=db_path) is not None
    return (RECAP_DIR / name).is_file()


def read_text(name: str, db_path=None) -> str:
    """The recap's markdown, from the database or the repo file."""
    if is_db(name):
        rec = load(name, db_path=db_path)
        if not rec:
            raise ValueError(f"no stored recap {name!r}")
        return rec["md"]
    p = (RECAP_DIR / name).resolve()
    if RECAP_DIR.resolve() not in p.parents or not p.is_file():
        raise ValueError(f"no recap file {name!r} in docs/claude/recaps/")
    return p.read_text(encoding="utf-8")


def update_text(name: str, md: str, db_path=None, who: str | None = None) -> None:
    """Replace a stored recap's text (a manager's or Kerry's edit before it
    sends). Only stored recaps can be edited this way. `who` (the event
    SUMMARY's Save, #2460-E) records the editor, the time and the text it
    replaced (one level back) in the recap's meta."""
    if not is_db(name):
        raise ValueError("only a stored recap (db:...) can be edited here")
    rec = load(name, db_path=db_path) or {"meta": {}}
    meta = dict(rec.get("meta") or {})
    meta["edited"] = True
    if who:
        from .timezone_utils import now_central, stamp12
        meta["edited_by"] = who
        meta["edited_at"] = stamp12(now_central())
        meta["previous_md"] = rec.get("md")
    save(_key(name), md, meta, db_path=db_path)
