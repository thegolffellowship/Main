"""THE SCREENS LIBRARY (Kerry 2026-10-26): "I want to be able to go to a page
and select whatever I want to look at to review standard screenshot layouts
and sequences" ... "managed by the Librarian" ... "review/comment on these
while in the interface ... That information would go to the librarian who
would submit back to the Front Desk or Chief of Staff".

- Screenshots live in the repo under docs/claude/screenshots/<folder>/.
- docs/claude/screenshots/catalog.json (the Librarian's file) names each
  sequence, its steps in order, captions, status and source doc. Files in a
  folder but not in the catalogue, and folders with no sequence, are listed
  as Not catalogued so the Librarian sees the gap.
- A comment is a MAILBOX POST (topic "screens", author "screens-page") to
  the Librarian, cc the Front Desk. The thread under a sequence is every
  "screens" post whose SEQUENCE line names it, so the Librarian's replies
  (same topic, same SEQUENCE line) show there too. No new table.
- A comment is a review note, never a ruling: the author is not "kerry" and
  the header names no relay, so customer_query._kerry_ok refuses it.
- Admin only for now; dial screens_viewer_role ("admin" | "manager") opens
  it to managers later.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_APP = Path(__file__).resolve().parent.parent
ROOT = _APP / "docs" / "claude" / "screenshots"
CATALOG = ROOT / "catalog.json"
# A sequence's "base" says which folder its pictures live under, so pictures
# already in use elsewhere are catalogued where they are, never copied.
BASES = {"screenshots": ROOT, "static": _APP / "static" / "img", "mockups": _APP / "docs" / "claude" / "mockups"}
TOPIC = "screens"
AUTHOR = "screens-page"
ROLE_DIAL = "screens_viewer_role"
KINDS = ("Improve", "Submit for review", "Note")
DEVICES = ("desktop", "tablet", "mobile")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
FILE_EXT = IMAGE_EXT | {".pdf"}
MAX_TEXT = 4000

_SEQ_LINE = re.compile(r"^SEQUENCE:\s*([A-Za-z0-9._-]+)", re.MULTILINE)


def viewer_role(db_path=None) -> str:
    from email_parser import database as db
    try:
        v = (db.get_app_setting(ROLE_DIAL, db_path=db_path) or "admin").strip().lower()
    except Exception:
        v = "admin"
    return v if v in ("admin", "manager") else "admin"


def _load(root: Path = ROOT) -> dict:
    try:
        return json.loads((root / "catalog.json").read_text())
    except (OSError, ValueError):
        return {"areas": [], "sequences": []}


def catalog(root: Path = ROOT) -> dict:
    """The catalogue as the page shows it: each step marked missing when its
    file is gone, plus what is on disk but not catalogued."""
    cat = _load(root)
    listed: dict[str, set] = {}
    for s in cat.get("sequences", []):
        folder = s.get("folder") or ""
        base = BASES.get(s.get("base") or "screenshots", root) if root == ROOT else root
        s["base"] = s.get("base") or "screenshots"
        if s["base"] == "screenshots":
            listed.setdefault(folder, set())
        for st in s.get("steps", []):
            # shots: device (desktop / tablet / mobile / any) -> file. A step
            # written the old way (one file) is that file on mobile.
            shots = st.get("shots") or {"mobile": st.get("file")}
            st["shots"] = shots
            st["missing"] = sorted(d for d, f in shots.items()
                                   if not (base / folder / (f or "")).is_file())
            st["kinds"] = {d: ("pdf" if str(f).lower().endswith(".pdf") else "image")
                           for d, f in shots.items()}
            if s["base"] == "screenshots":
                listed[folder].update(shots.values())
                listed[folder].add(st.get("file"))
    loose = []
    if root.is_dir():
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            files = sorted(f.name for f in d.iterdir()
                           if f.is_file() and f.suffix.lower() in FILE_EXT)
            extra = [f for f in files if f not in listed.get(d.name, set())]
            if extra:
                loose.append({"folder": d.name, "files": extra,
                              "has_sequence": d.name in listed})
    cat["not_catalogued"] = loose
    cat.setdefault("devices", list(DEVICES))
    return cat


def safe_file(rel: str, root: Path = ROOT, base: str = "") -> Path | None:
    """A picture path inside its base folder with an allowed extension, else None."""
    if base:
        if base not in BASES:
            return None
        root = BASES[base]
    try:
        p = (root / rel).resolve()
        p.relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    if p.suffix.lower() not in FILE_EXT or not p.is_file():
        return None
    return p


def _sequence(seq_id: str, root: Path = ROOT) -> dict | None:
    for s in _load(root).get("sequences", []):
        if s.get("id") == seq_id:
            return s
    return None


def comment_body(seq: dict, kind: str, text: str, step_file: str = "",
                 who: str = "admin", when: str = "", device: str = "") -> str:
    step = next((st for st in seq.get("steps", []) if st.get("file") == step_file), None)
    lines = [
        "TO: librarian-claude (COO › Library)",
        "CC: front-desk",
        f"FROM: {AUTHOR} (signed in as {who}){', ' + when if when else ''}",
        f"KIND: {kind}",
        f"SEQUENCE: {seq['id']} — {seq.get('title', '')}",
    ]
    if step:
        dev = f" ({device})" if device in DEVICES else ""
        lines.append(f"STEP: {step['file']} — {step.get('caption', '')}{dev}")
    lines += ["", text.strip(), "",
              "A review note from the Screens page (/admin/screens), not a ruling: it carries "
              "no one's OK for a change. Librarian: file it, route it (Front Desk by default), "
              "and reply here with topic screens and this SEQUENCE line so the thread shows it."]
    return "\n".join(lines)


def add_comment(seq_id: str, kind: str, text: str, step_file: str = "",
                who: str = "admin", root: Path = ROOT, db_path=None, device: str = "") -> dict:
    from email_parser import database as db
    from email_parser.timezone_utils import now_central
    seq = _sequence(seq_id, root)
    if not seq:
        return {"error": f"no sequence {seq_id}"}
    kind = kind if kind in KINDS else "Note"
    text = (text or "").strip()
    if not text:
        return {"error": "write a comment first"}
    if len(text) > MAX_TEXT:
        return {"error": f"keep it under {MAX_TEXT} characters"}
    try:
        when = now_central().strftime("%a %-m/%-d %-I:%M %p CT")
    except Exception:
        when = ""
    body = comment_body(seq, kind, text, step_file, who, when, device)
    kw = {"db_path": db_path} if db_path else {}
    return db.post_platform_dialogue_entry(AUTHOR, body, TOPIC, **kw)


def thread(seq_id: str, db_path=None) -> list[dict]:
    """Every screens post whose SEQUENCE line names this sequence, oldest first."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, author, topic, body, created_at FROM platform_dialogue "
            "WHERE topic = ? ORDER BY id", (TOPIC,)).fetchall()
    out = []
    for r in rows:
        m = _SEQ_LINE.search(r["body"] or "")
        if m and m.group(1) == seq_id:
            out.append(dict(r))
    return out


def counts(db_path=None) -> dict:
    """Comment count per sequence id, for the list."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        rows = conn.execute("SELECT body FROM platform_dialogue WHERE topic = ?",
                            (TOPIC,)).fetchall()
    out: dict[str, int] = {}
    for r in rows:
        m = _SEQ_LINE.search(r["body"] or "")
        if m:
            out[m.group(1)] = out.get(m.group(1), 0) + 1
    return out
