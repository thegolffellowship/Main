"""Player score entry (Track A, "CTO › Live Score Entry", 2026-09-25).

A phone-first screen where one scorer per group enters GROSS scores hole by
hole. This module is the data layer and the rules; `app.py` is a thin HTTP
shell over it and `templates/score_entry.html` is the client.

RULES OF RECORD (mailbox #654, #655, #661; not negotiable):
- Golf Genius stays the official and money record. Entered scores feed our
  own board and the diff against GG ONLY. No payout path reads se_*
  (guarded by test_score_entry.py).
- Every score keys to customer_id (CLAUDE.md guiding principle 6). A team
  row (Foursomes, one ball per pair) records BOTH customer_ids.
- Lock/take-over: one device holds a group. A second device must take over
  explicitly; the first then goes read-only. A write from a device that does
  not hold the lock is REFUSED and kept in se_audit with its value, so a
  hole is never silently lost.
- Weak signal: the client queues each hole write with its own op_id and
  retries until acked. The server is idempotent on op_id (a replay returns
  the first result and never re-applies an older value over a newer one).
- Gross only. Nothing here computes net or a game — live_scoring.py and the
  match play engine read the same rows.
- Playing handicap is the LOCKED handicap, snapshotted at seed time from
  the one computation the starter sheet prints (get_event_print_pack).

Read shape (CA #661): event-scoped, ROUNDS plural, one version per event;
`round_id` is an optional filter. See `get_entered_scores`.

Portable: plain SQL, no Flask. Moves to the combined product with the same
API shape (token -> group -> customer_id).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

GROSS_MIN, GROSS_MAX = 1, 20
# TGF plays MAX TRIPLE (Kerry, 2026-09-25: "We do Max Triple, so it can't be
# more than that."): a hole's gross is at most par + 3. And "hole in ones
# wouldn't be possible on Par 5s": the lowest gross on a par 5 is 2. A hole
# with no par on the card falls back to the 1-20 sanity range.
MAX_OVER_PAR = 3


def gross_bounds(par) -> tuple[int, int]:
    """(lowest, highest) gross a scorer may enter on a hole of this par."""
    if not par:
        return GROSS_MIN, GROSS_MAX
    par = int(par)
    return (2 if par >= 5 else 1), par + MAX_OVER_PAR
MAX_OPS_PER_BATCH = 200


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _conn(db_path=None) -> sqlite3.Connection:
    from email_parser.database import get_connection
    conn = get_connection(db_path)
    ensure_score_entry_tables(conn)
    return conn


# ---------------------------------------------------------------------------
# Schema (rule 3b: Kerry ratifies before this reaches main)
# ---------------------------------------------------------------------------

def ensure_score_entry_tables(conn: sqlite3.Connection) -> None:
    """Once per database file per process (CLAUDE.md "Lazy DDL is once per
    database"): CREATE ... IF NOT EXISTS still takes the write lock, and this
    runs on every score-entry connection, so it must not run every time."""
    from email_parser.database import _once_per_db
    global _ensure_once
    if _ensure_once is None:
        _ensure_once = _once_per_db(_ensure_score_entry_tables)
    _ensure_once(conn)


_ensure_once = None


def _ensure_score_entry_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS se_rounds (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id      INTEGER NOT NULL REFERENCES events(id),
        round_date    TEXT,
        label         TEXT,
        holes         INTEGER NOT NULL CHECK(holes IN (9, 18)),
        pairings_holes TEXT,
        course_id     INTEGER,
        tee_note      TEXT,
        status        TEXT NOT NULL DEFAULT 'open'
                          CHECK(status IN ('open', 'closed')),
        created_by    TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now')));
    CREATE INDEX IF NOT EXISTS idx_se_rounds_event ON se_rounds(event_id);

    CREATE TABLE IF NOT EXISTS se_round_holes (
        round_id      INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
        hole_number   INTEGER NOT NULL,
        par           INTEGER,
        stroke_index  INTEGER,
        yardage       INTEGER,
        PRIMARY KEY (round_id, hole_number));

    CREATE TABLE IF NOT EXISTS se_groups (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id      INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
        group_num     INTEGER NOT NULL,
        label         TEXT,
        start_hole    INTEGER NOT NULL DEFAULT 1,
        tee_time      TEXT,
        token_version INTEGER NOT NULL DEFAULT 1,
        UNIQUE(round_id, group_num));

    CREATE TABLE IF NOT EXISTS se_players (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id         INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
        group_id         INTEGER NOT NULL REFERENCES se_groups(id) ON DELETE CASCADE,
        customer_id      INTEGER NOT NULL REFERENCES customers(customer_id),
        display_name     TEXT,
        tee              TEXT,
        playing_handicap REAL,
        seat             INTEGER,
        UNIQUE(round_id, customer_id));

    -- FOURSOMES (CA #661 item 2): one ball per pair. Both people are
    -- recorded; the pair is the subject of its own hole rows.
    CREATE TABLE IF NOT EXISTS se_teams (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id       INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
        group_id       INTEGER NOT NULL REFERENCES se_groups(id) ON DELETE CASCADE,
        customer_id_a  INTEGER NOT NULL REFERENCES customers(customer_id),
        customer_id_b  INTEGER NOT NULL REFERENCES customers(customer_id),
        label          TEXT,
        UNIQUE(round_id, customer_id_a, customer_id_b));

    -- One row per subject per hole. subject_key is 'c:<customer_id>' for a
    -- player row or 't:<team_id>' for a team row, so the UNIQUE holds for
    -- both kinds (NULLs would not collide in SQLite).
    CREATE TABLE IF NOT EXISTS se_hole_scores (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id                INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
        group_id                INTEGER NOT NULL REFERENCES se_groups(id) ON DELETE CASCADE,
        subject_key             TEXT NOT NULL,
        customer_id             INTEGER REFERENCES customers(customer_id),
        team_id                 INTEGER REFERENCES se_teams(id) ON DELETE CASCADE,
        team_customer_id_a      INTEGER REFERENCES customers(customer_id),
        team_customer_id_b      INTEGER REFERENCES customers(customer_id),
        hole_number             INTEGER NOT NULL,
        gross                   INTEGER CHECK(gross IS NULL OR gross BETWEEN 1 AND 20),
        entered_by_customer_id  INTEGER REFERENCES customers(customer_id),
        device_id               TEXT NOT NULL,
        op_id                   TEXT NOT NULL,
        client_ts               TEXT,
        server_ts               TEXT NOT NULL,
        CHECK ((customer_id IS NOT NULL AND team_id IS NULL)
            OR (customer_id IS NULL AND team_id IS NOT NULL
                AND team_customer_id_a IS NOT NULL
                AND team_customer_id_b IS NOT NULL)),
        UNIQUE(round_id, subject_key, hole_number));
    CREATE INDEX IF NOT EXISTS idx_se_scores_round ON se_hole_scores(round_id);

    CREATE TABLE IF NOT EXISTS se_group_locks (
        group_id              INTEGER PRIMARY KEY REFERENCES se_groups(id) ON DELETE CASCADE,
        device_id             TEXT NOT NULL,
        holder_customer_id    INTEGER REFERENCES customers(customer_id),
        claimed_at            TEXT NOT NULL,
        heartbeat_at          TEXT NOT NULL);

    -- Every claim, take-over, accepted write and refused write. A refused
    -- write keeps its value here, so no hole is ever lost. op_id is UNIQUE:
    -- it is the idempotency key for the offline queue.
    CREATE TABLE IF NOT EXISTS se_audit (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id           INTEGER,
        group_id           INTEGER,
        kind               TEXT NOT NULL,
        customer_id        INTEGER REFERENCES customers(customer_id),
        device_id          TEXT,
        prev_device_id     TEXT,
        op_id              TEXT UNIQUE,
        result             TEXT,
        detail             TEXT,
        at                 TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_se_audit_group ON se_audit(group_id);

    -- SIGN-OFF (Kerry #666 A): one scorekeeper, everyone signs their own
    -- card at the end. kind: 'player' (his own card), 'scorekeeper' (I kept
    -- these scores), 'manager' (on the player's behalf, with a note). An
    -- edit to a signed card voids THAT player's signature only.
    CREATE TABLE IF NOT EXISTS se_signoffs (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id               INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
        group_id               INTEGER NOT NULL REFERENCES se_groups(id) ON DELETE CASCADE,
        customer_id            INTEGER NOT NULL REFERENCES customers(customer_id),
        kind                   TEXT NOT NULL CHECK(kind IN ('player', 'scorekeeper', 'manager')),
        signed_by_customer_id  INTEGER REFERENCES customers(customer_id),
        device_id              TEXT,
        card                   TEXT,
        note                   TEXT,
        at                     TEXT NOT NULL,
        voided_at              TEXT,
        void_reason            TEXT);
    CREATE INDEX IF NOT EXISTS idx_se_signoffs_group ON se_signoffs(group_id);

    -- "Something's wrong": the player taps the hole; the scorekeeper and the
    -- chapter manager fix it. Resolved by an edit of that hole or by hand.
    CREATE TABLE IF NOT EXISTS se_card_flags (
        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id                 INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
        group_id                 INTEGER NOT NULL REFERENCES se_groups(id) ON DELETE CASCADE,
        customer_id              INTEGER NOT NULL REFERENCES customers(customer_id),
        hole_number              INTEGER NOT NULL,
        note                     TEXT,
        raised_by_customer_id    INTEGER REFERENCES customers(customer_id),
        device_id                TEXT,
        at                       TEXT NOT NULL,
        resolved_at              TEXT,
        resolved_by_customer_id  INTEGER REFERENCES customers(customer_id),
        resolution               TEXT);

    -- CLOSEST TO THE PIN (Kerry #666 C): no distances. The latest claim on a
    -- hole is the current holder the next group sees; 'none' records a group
    -- that answered "No one closer". A manager ruling is a claim too.
    CREATE TABLE IF NOT EXISTS se_ctp_claims (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id                INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
        group_id                INTEGER REFERENCES se_groups(id) ON DELETE CASCADE,
        hole_number             INTEGER NOT NULL,
        customer_id             INTEGER REFERENCES customers(customer_id),
        kind                    TEXT NOT NULL CHECK(kind IN ('claim', 'none', 'manager')),
        claimed_by_customer_id  INTEGER REFERENCES customers(customer_id),
        device_id               TEXT,
        at                      TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_se_ctp_round_hole ON se_ctp_claims(round_id, hole_number);

    -- HOLE-IN-ONE (Kerry #666 C): a raw 1 opens a claim. The scorekeeper
    -- confirms, one other player in the group confirms, then the manager
    -- verifies. An ineligible player's 1 is a score only (eligible = 0).
    CREATE TABLE IF NOT EXISTS se_hio_claims (
        id                        INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id                  INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
        group_id                  INTEGER NOT NULL REFERENCES se_groups(id) ON DELETE CASCADE,
        customer_id               INTEGER NOT NULL REFERENCES customers(customer_id),
        hole_number               INTEGER NOT NULL,
        eligible                  INTEGER NOT NULL DEFAULT 1,
        status                    TEXT NOT NULL DEFAULT 'pending'
                                      CHECK(status IN ('pending', 'confirmed', 'witnessed',
                                                       'verified', 'rejected', 'withdrawn')),
        scorekeeper_customer_id   INTEGER REFERENCES customers(customer_id),
        scorekeeper_at            TEXT,
        witness_customer_id       INTEGER REFERENCES customers(customer_id),
        witness_at                TEXT,
        verified_by               TEXT,
        verified_at               TEXT,
        at                        TEXT NOT NULL,
        UNIQUE(round_id, customer_id, hole_number));

    CREATE TABLE IF NOT EXISTS se_event_versions (
        event_id   INTEGER PRIMARY KEY,
        version    INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT);
    """)


def _bump(conn, event_id: int) -> int:
    conn.execute(
        "INSERT INTO se_event_versions (event_id, version, updated_at) VALUES (?, 1, ?) "
        "ON CONFLICT(event_id) DO UPDATE SET version = version + 1, "
        "updated_at = excluded.updated_at", (event_id, _now()))
    return conn.execute("SELECT version FROM se_event_versions WHERE event_id = ?",
                        (event_id,)).fetchone()[0]


def round_event_id(round_id: int, db_path=None) -> int | None:
    with _closing(_conn(db_path)) as conn:
        r = conn.execute("SELECT event_id FROM se_rounds WHERE id = ?", (round_id,)).fetchone()
    return int(r[0]) if r else None


def event_version(event_id: int, db_path=None) -> int:
    with _closing(_conn(db_path)) as conn:
        r = conn.execute("SELECT version FROM se_event_versions WHERE event_id = ?",
                         (event_id,)).fetchone()
    return int(r[0]) if r else 0


class _closing:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *exc):
        self.conn.close()


# ---------------------------------------------------------------------------
# Group links (one signed link per group; Kerry hands them out, nothing sends)
# ---------------------------------------------------------------------------

def _secret() -> bytes:
    s = os.getenv("SECRET_KEY") or "tgf-portal-token-dev-fallback-do-not-use-in-prod"
    return ("score-entry:" + s).encode("utf-8")


def make_group_token(group_id: int, db_path=None) -> str | None:
    with _closing(_conn(db_path)) as conn:
        r = conn.execute("SELECT token_version FROM se_groups WHERE id = ?",
                         (group_id,)).fetchone()
    if not r:
        return None
    raw = json.dumps({"g": group_id, "v": r[0]}, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    sig = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def verify_group_token(token: str, db_path=None) -> int | None:
    """The group_id the link grants, or None (bad, revoked, or round closed)."""
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    good = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, good):
        return None
    try:
        p = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        gid, ver = int(p["g"]), int(p["v"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
    with _closing(_conn(db_path)) as conn:
        r = conn.execute(
            "SELECT g.token_version, r.status FROM se_groups g "
            "JOIN se_rounds r ON r.id = g.round_id WHERE g.id = ?", (gid,)).fetchone()
    if not r or r[0] != ver or r[1] != "open":
        return None
    return gid


def revoke_group_links(group_id: int, db_path=None) -> bool:
    with _closing(_conn(db_path)) as conn:
        cur = conn.execute("UPDATE se_groups SET token_version = token_version + 1 "
                           "WHERE id = ?", (group_id,))
        conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Admin: build a round (from PAIRINGS, or by hand for the cup)
# ---------------------------------------------------------------------------

def create_round(event_id: int, holes: int, *, round_date=None, label=None,
                 course_holes=None, course_id=None, tee_note=None,
                 pairings_holes=None, created_by=None, db_path=None) -> dict:
    if int(holes) not in (9, 18):
        return {"error": "holes must be 9 or 18"}
    with _closing(_conn(db_path)) as conn:
        cur = conn.execute(
            "INSERT INTO se_rounds (event_id, round_date, label, holes, pairings_holes, "
            "course_id, tee_note, created_by) VALUES (?,?,?,?,?,?,?,?) RETURNING id",
            (event_id, round_date, label, int(holes), pairings_holes, course_id,
             tee_note, created_by))
        rid = cur.fetchone()[0]
        for h in (course_holes or []):
            _upsert_hole(conn, rid, h)
        _bump(conn, event_id)
        conn.commit()
    return {"round_id": rid}


def _upsert_hole(conn, round_id, h: dict):
    conn.execute(
        "INSERT INTO se_round_holes (round_id, hole_number, par, stroke_index, yardage) "
        "VALUES (?,?,?,?,?) ON CONFLICT(round_id, hole_number) DO UPDATE SET "
        "par = COALESCE(excluded.par, par), "
        "stroke_index = COALESCE(excluded.stroke_index, stroke_index), "
        "yardage = COALESCE(excluded.yardage, yardage)",
        (round_id, int(h["hole"]), h.get("par"), h.get("stroke_index"), h.get("yardage")))


def set_course_holes(round_id: int, holes: list[dict], db_path=None) -> dict:
    with _closing(_conn(db_path)) as conn:
        ev = conn.execute("SELECT event_id FROM se_rounds WHERE id = ?",
                          (round_id,)).fetchone()
        if not ev:
            return {"error": "no such round"}
        for h in holes:
            _upsert_hole(conn, round_id, h)
        _bump(conn, ev[0])
        conn.commit()
    return {"ok": True}


def upsert_group(round_id: int, group_num: int, *, label=None, start_hole=1,
                 tee_time=None, players=(), db_path=None) -> dict:
    """players: [{customer_id, display_name?, tee?, playing_handicap?, seat?}].
    Re-running it is safe: existing scores stay; a player moved between groups
    moves (UNIQUE round+customer)."""
    with _closing(_conn(db_path)) as conn:
        ev = conn.execute("SELECT event_id FROM se_rounds WHERE id = ?",
                          (round_id,)).fetchone()
        if not ev:
            return {"error": "no such round"}
        conn.execute(
            "INSERT INTO se_groups (round_id, group_num, label, start_hole, tee_time) "
            "VALUES (?,?,?,?,?) ON CONFLICT(round_id, group_num) DO UPDATE SET "
            "label = excluded.label, start_hole = excluded.start_hole, "
            "tee_time = excluded.tee_time",
            (round_id, int(group_num), label, int(start_hole or 1), tee_time))
        gid = conn.execute("SELECT id FROM se_groups WHERE round_id = ? AND group_num = ?",
                           (round_id, int(group_num))).fetchone()[0]
        missing = []
        for p in players:
            cid = p.get("customer_id")
            if not cid:
                missing.append(p.get("display_name") or "?")
                continue
            conn.execute(
                "INSERT INTO se_players (round_id, group_id, customer_id, display_name, "
                "tee, playing_handicap, seat) VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(round_id, customer_id) DO UPDATE SET "
                "group_id = excluded.group_id, display_name = excluded.display_name, "
                "tee = excluded.tee, playing_handicap = excluded.playing_handicap, "
                "seat = excluded.seat",
                (round_id, gid, int(cid), p.get("display_name"), p.get("tee"),
                 p.get("playing_handicap"), p.get("seat")))
        _bump(conn, ev[0])
        conn.commit()
    out = {"group_id": gid}
    if missing:
        # Principle 6: a seat with no customer_id cannot be scored. Say so.
        out["skipped_no_customer_id"] = missing
    return out


def add_team(round_id: int, group_id: int, customer_id_a: int, customer_id_b: int,
             label=None, db_path=None) -> dict:
    """A Foursomes pair: one ball, one gross per hole, both people recorded.
    Both must already be players in this group."""
    a, b = sorted((int(customer_id_a), int(customer_id_b)))
    if a == b:
        return {"error": "a team needs two different people"}
    with _closing(_conn(db_path)) as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM se_players WHERE round_id = ? AND group_id = ? "
            "AND customer_id IN (?, ?)", (round_id, group_id, a, b)).fetchone()[0]
        if n != 2:
            return {"error": "both players must be in this group"}
        conn.execute(
            "INSERT INTO se_teams (round_id, group_id, customer_id_a, customer_id_b, label) "
            "VALUES (?,?,?,?,?) ON CONFLICT(round_id, customer_id_a, customer_id_b) DO NOTHING",
            (round_id, group_id, a, b, label))
        tid = conn.execute(
            "SELECT id FROM se_teams WHERE round_id = ? AND customer_id_a = ? "
            "AND customer_id_b = ?", (round_id, a, b)).fetchone()[0]
        ev = conn.execute("SELECT event_id FROM se_rounds WHERE id = ?",
                          (round_id,)).fetchone()[0]
        _bump(conn, ev)
        conn.commit()
    return {"team_id": tid}


def seed_round_from_pairings(event_id: int, holes: str = "9", *, round_date=None,
                             label=None, created_by=None, db_path=None) -> dict:
    """Build a round from the event's saved PAIRINGS (the one builder) via the
    starter-sheet read, so the playing handicap is the LOCKED one the sheet
    prints (handicaps.md, "The handicap lock"). Course holes come from the
    event's course card. Re-seeding the same event+holes updates groups and
    players in place and never touches a score."""
    from email_parser import database as db
    pack = db.get_event_print_pack(event_id, db_path=db_path)
    if not pack:
        return {"error": "no such event"}
    groups = [g for g in (pack.get("groups") or []) if str(g.get("holes")) == str(holes)]
    if not groups:
        return {"error": f"no saved {holes}-hole pairings for this event"}
    n_holes = 18 if str(holes) == "18" else 9
    with _closing(_conn(db_path)) as conn:
        r = conn.execute("SELECT id FROM se_rounds WHERE event_id = ? AND pairings_holes = ? "
                         "ORDER BY id LIMIT 1", (event_id, str(holes))).fetchone()
        evrow = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        evrow = dict(evrow) if evrow else {}
        course_holes = _event_course_holes(conn, evrow, n_holes)
    if r:
        rid = r[0]
        if course_holes:
            set_course_holes(rid, course_holes, db_path=db_path)
    else:
        rid = create_round(
            event_id, n_holes,
            round_date=round_date or (evrow.get("event_date") or "")[:10] or None,
            label=label or evrow.get("item_name"),
            course_holes=course_holes, course_id=evrow.get("course_id"),
            pairings_holes=str(holes), created_by=created_by,
            db_path=db_path)["round_id"]
    skipped = []
    first = _first_hole(evrow, n_holes)
    pev = pack.get("event") or {}
    shotgun = (pev.get("start_type") or "").strip().lower().startswith("shotgun")
    for g in groups:
        start = _start_hole(g.get("hole_label"), first)
        res = upsert_group(
            rid, int(g["group_num"]), label=g.get("start_line") or g.get("slot_label"),
            start_hole=start,
            # On a shotgun the slot is a hole and the time is the one start
            # clock; on tee times the slot IS the time.
            tee_time=(pev.get("start_clock") if shotgun else g.get("slot_label")),
            players=[{"customer_id": p.get("customer_id"), "display_name": p.get("name"),
                      "tee": p.get("tee_choice"),
                      "playing_handicap": p.get("playing_handicap"),
                      "seat": p.get("cart_pos")} for p in g.get("players") or []],
            db_path=db_path)
        skipped += res.get("skipped_no_customer_id", [])
    out = {"round_id": rid, "groups": len(groups),
           "course_holes": len(course_holes)}
    if skipped:
        out["skipped_no_customer_id"] = skipped
    if len(course_holes) < n_holes:
        out["warning"] = (f"course card gave {len(course_holes)} of {n_holes} holes; "
                          "set par and stroke index before scoring")
    return out


def _first_hole(ev: dict, n_holes: int) -> int:
    if n_holes == 9 and (ev.get("nine_side") or "").strip().lower() == "back":
        return 10
    return 1


def _start_hole(hole_label, default: int) -> int:
    import re
    m = re.match(r"^\s*hole\s+(\d+)", str(hole_label or ""), re.I)
    return int(m.group(1)) if m else default


def _event_course_holes(conn, ev: dict, n_holes: int) -> list[dict]:
    """Par / stroke index / yardage for the event's course, merged across the
    tee's per-nine ratings (database._ls_tee_holes). A nine picks its side."""
    from email_parser import database as db
    cid = ev.get("course_id")
    if not cid:
        return []
    t = conn.execute("SELECT tee_id FROM course_tees WHERE course_id = ? "
                     "ORDER BY tee_id DESC LIMIT 1", (cid,)).fetchone()
    if not t:
        return []
    holes = db._ls_tee_holes(conn, t[0])
    by = {h["hole_number"]: h for h in holes}
    first = _first_hole(ev, n_holes)
    want = range(first, first + n_holes)
    if n_holes == 9 and first == 10 and not any(n in by for n in want):
        want = range(1, 10)          # a named nine numbers 1-9 (handicaps.md)
    return [{"hole": n, "par": by[n]["par"], "stroke_index": by[n]["stroke_index"],
             "yardage": by[n]["yardage"]} for n in want if n in by]


# ---------------------------------------------------------------------------
# PREVIEW round (Front Desk, 2026-09-25: Kerry asked "Where do I see the Live
# Score Entry on the Tracker?"). A clearly labelled test round on an event,
# separate from any round seeded from PAIRINGS (pairings_holes stays NULL, so
# seed_round_from_pairings never reuses it). Nothing member-facing: the link
# opens only for an admin session while score_entry_live is off.
# ---------------------------------------------------------------------------

PREVIEW_LABEL = "PREVIEW (test round, not a real card)"


def create_preview_round(event_id: int, customer_ids: list[int], db_path=None) -> dict:
    ids = [int(c) for c in customer_ids if str(c).strip()]
    if not ids or len(ids) > 5:
        return {"error": "one to five customer_ids"}
    with _closing(_conn(db_path)) as conn:
        ev = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not ev:
            return {"error": "no such event"}
        ev = dict(ev)
        names = {r[0]: r[1] for r in conn.execute(
            "SELECT customer_id, TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) "
            f"FROM customers WHERE customer_id IN ({','.join('?' * len(ids))})", ids)}
        missing = [c for c in ids if c not in names]
        if missing:
            return {"error": f"unknown customer_id(s): {missing}"}
        existing = conn.execute("SELECT id FROM se_rounds WHERE event_id = ? AND label = ? "
                                "AND status = 'open' ORDER BY id LIMIT 1",
                                (event_id, PREVIEW_LABEL)).fetchone()
        holes = 18 if "18" in str(ev.get("format") or "") and "9/18" not in str(ev.get("format") or "") else 9
        course = _event_course_holes(conn, ev, holes)
    rid = existing[0] if existing else create_round(
        event_id, holes, round_date=(ev.get("event_date") or "")[:10] or None,
        label=PREVIEW_LABEL, course_holes=course, course_id=ev.get("course_id"),
        created_by="preview", db_path=db_path)["round_id"]
    g = upsert_group(rid, 1, label="Preview group", start_hole=_first_hole(ev, holes),
                     players=[{"customer_id": c, "display_name": names[c], "seat": i + 1}
                              for i, c in enumerate(ids)], db_path=db_path)
    out = {"round_id": rid, "group_id": g["group_id"], "reused": bool(existing),
           "course_holes": len(course), "holes": holes}
    if len(course) < holes:
        out["warning"] = f"course card gave {len(course)} of {holes} holes"
    return out


def close_round(round_id: int, db_path=None) -> dict:
    """Close a round: its links stop opening. Nothing is deleted."""
    with _closing(_conn(db_path)) as conn:
        r = conn.execute("SELECT event_id FROM se_rounds WHERE id = ?", (round_id,)).fetchone()
        if not r:
            return {"error": "no such round"}
        conn.execute("UPDATE se_rounds SET status = 'closed' WHERE id = ?", (round_id,))
        _bump(conn, r[0])
        conn.commit()
    return {"closed": round_id}


def round_links(round_id: int, base_url: str | None = None, db_path=None) -> list[dict]:
    base = (base_url or os.getenv("PUBLIC_BASE_URL")
            or "https://tgf-tracker.up.railway.app").rstrip("/")
    with _closing(_conn(db_path)) as conn:
        rows = conn.execute("SELECT id, group_num, label FROM se_groups WHERE round_id = ? "
                            "ORDER BY group_num", (round_id,)).fetchall()
        players = {}
        for p in conn.execute("SELECT group_id, display_name FROM se_players WHERE round_id = ? "
                              "ORDER BY COALESCE(seat, 99), id", (round_id,)):
            players.setdefault(p[0], []).append(p[1])
    return [{"group_id": r[0], "group_num": r[1], "label": r[2], "players": players.get(r[0], []),
             "url": f"{base}/member/score?t={make_group_token(r[0], db_path=db_path)}"}
            for r in rows]


# ---------------------------------------------------------------------------
# Cart-sign QR (Kerry #666 B: "QR Code printed on cart sign"). Which events
# and groups carry one is a dial, `score_entry_qr` in app_settings:
#   {"<event_id>": "all" | [group_num, ...]}
# The 9/29 dry run lists Kerry's group only. A sign never carries a code for
# a group that has no round: the round is seeded from PAIRINGS (idempotent)
# the first time the sign is printed.
# ---------------------------------------------------------------------------

def _qr_dial(event_id: int, db_path=None):
    from email_parser.database import get_app_setting
    try:
        raw = get_app_setting("score_entry_qr", db_path) or ""
        dial = json.loads(raw) if raw.strip() else {}
    except (ValueError, TypeError):
        return None
    return dial.get(str(event_id))


def qr_svg(url: str) -> str | None:
    try:
        import segno
    except ImportError:
        return None
    return segno.make(url, error="m").svg_inline(scale=4, border=1, dark="#111111")


def attach_cart_sign_qr(pack: dict, base_url: str | None = None, db_path=None) -> dict:
    """Stamp `score_qr` {url, svg} on each group of a print pack whose event
    and group the dial enables. Returns {"groups": n, "skipped": [...]}. Never
    raises: a sign without a code is the old sign, not a broken one."""
    out = {"groups": 0}
    try:
        event_id = int((pack.get("event") or {}).get("id"))
        want = _qr_dial(event_id, db_path)
        if not want:
            return out
        base = (base_url or os.getenv("PUBLIC_BASE_URL")
                or "https://tgf-tracker.up.railway.app").rstrip("/")
        for holes in sorted({str(g.get("holes")) for g in pack.get("groups") or []}):
            seeded = seed_round_from_pairings(event_id, holes, db_path=db_path)
            rid = seeded.get("round_id")
            if not rid:
                continue
            with _closing(_conn(db_path)) as conn:
                gids = {r[0]: r[1] for r in conn.execute(
                    "SELECT group_num, id FROM se_groups WHERE round_id = ?", (rid,))}
            for g in pack.get("groups") or []:
                if str(g.get("holes")) != holes:
                    continue
                gnum = g.get("group_num")
                if want != "all" and gnum not in want:
                    continue
                gid = gids.get(gnum)
                if not gid:
                    continue
                url = f"{base}/member/score?t={make_group_token(gid, db_path=db_path)}"
                svg = qr_svg(url)
                if svg:
                    g["score_qr"] = {"url": url, "svg": svg}
                    out["groups"] += 1
    except Exception as e:                       # noqa: BLE001 — print must not fail
        out["error"] = str(e)[:200]
    return out


# ---------------------------------------------------------------------------
# The scorer: open a group, claim / take over, write
# ---------------------------------------------------------------------------

def _group_ctx(conn, group_id: int):
    return conn.execute(
        "SELECT g.*, r.event_id, r.holes, r.status, r.label AS round_label, "
        "r.round_date FROM se_groups g JOIN se_rounds r ON r.id = g.round_id "
        "WHERE g.id = ?", (group_id,)).fetchone()


def _lock_view(lock, device_id: str | None, names: dict) -> dict:
    if not lock:
        return {"state": "free"}
    mine = device_id is not None and lock["device_id"] == device_id
    return {"state": "mine" if mine else "held",
            "holder_customer_id": lock["holder_customer_id"],
            "holder_name": names.get(lock["holder_customer_id"]),
            "heartbeat_at": lock["heartbeat_at"]}


def get_group_card(group_id: int, device_id: str | None = None, db_path=None) -> dict:
    """Everything the entry screen needs for one group."""
    with _closing(_conn(db_path)) as conn:
        g = _group_ctx(conn, group_id)
        if not g:
            return {"error": "no such group"}
        players = [dict(p) for p in conn.execute(
            "SELECT customer_id, display_name, tee, playing_handicap, seat "
            "FROM se_players WHERE group_id = ? ORDER BY COALESCE(seat, 99), id",
            (group_id,))]
        names = {p["customer_id"]: p["display_name"] for p in players}
        teams = [dict(t) for t in conn.execute(
            "SELECT id AS team_id, customer_id_a, customer_id_b, label FROM se_teams "
            "WHERE group_id = ? ORDER BY id", (group_id,))]
        holes = [dict(h) for h in conn.execute(
            "SELECT hole_number AS hole, par, stroke_index, yardage FROM se_round_holes "
            "WHERE round_id = ? ORDER BY hole_number", (g["round_id"],))]
        scores = {}
        for s in conn.execute(
                "SELECT subject_key, hole_number, gross FROM se_hole_scores "
                "WHERE group_id = ? AND gross IS NOT NULL", (group_id,)):
            scores.setdefault(s["subject_key"], {})[str(s["hole_number"])] = s["gross"]
        lock = conn.execute("SELECT * FROM se_group_locks WHERE group_id = ?",
                            (group_id,)).fetchone()
        extras = _card_extras(conn, g, group_id)
    return {**extras, "group_id": group_id, "round_id": g["round_id"], "event_id": g["event_id"],
            "round_label": g["round_label"], "round_date": g["round_date"],
            "holes": g["holes"], "status": g["status"], "label": g["label"],
            "group_num": g["group_num"],
            "start_hole": g["start_hole"], "tee_time": g["tee_time"],
            "course": holes, "players": players, "teams": teams, "scores": scores,
            "lock": _lock_view(lock, device_id, names)}


def claim_group(group_id: int, device_id: str, customer_id: int | None,
                takeover: bool = False, db_path=None) -> dict:
    """Claim the scorer's seat. Free -> granted. Held by this device ->
    refreshed. Held by another device -> refused unless `takeover`, which
    moves the lock and audits both devices. There is no silent timeout:
    a dead phone is replaced by an explicit take-over, never by a clock."""
    if not device_id:
        return {"error": "device_id required"}
    with _closing(_conn(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        g = _group_ctx(conn, group_id)
        if not g:
            conn.rollback()
            return {"error": "no such group"}
        if customer_id is not None and not conn.execute(
                "SELECT 1 FROM se_players WHERE group_id = ? AND customer_id = ?",
                (group_id, customer_id)).fetchone():
            conn.rollback()
            return {"error": "that person is not in this group"}
        lock = conn.execute("SELECT * FROM se_group_locks WHERE group_id = ?",
                            (group_id,)).fetchone()
        now = _now()
        if lock and lock["device_id"] != device_id and not takeover:
            names = {r[0]: r[1] for r in conn.execute(
                "SELECT customer_id, display_name FROM se_players WHERE group_id = ?",
                (group_id,))}
            conn.rollback()
            return {"granted": False, "lock": _lock_view(lock, device_id, names)}
        kind = ("takeover" if lock and lock["device_id"] != device_id
                else "refresh" if lock else "claim")
        conn.execute(
            "INSERT INTO se_group_locks (group_id, device_id, holder_customer_id, "
            "claimed_at, heartbeat_at) VALUES (?,?,?,?,?) ON CONFLICT(group_id) DO UPDATE "
            "SET device_id = excluded.device_id, "
            "holder_customer_id = CASE WHEN device_id = excluded.device_id "
            "THEN COALESCE(excluded.holder_customer_id, holder_customer_id) "
            "ELSE excluded.holder_customer_id END, "
            "claimed_at = CASE WHEN device_id = excluded.device_id THEN claimed_at "
            "ELSE excluded.claimed_at END, heartbeat_at = excluded.heartbeat_at",
            (group_id, device_id, customer_id, now, now))
        if kind != "refresh":
            conn.execute(
                "INSERT INTO se_audit (round_id, group_id, kind, customer_id, device_id, "
                "prev_device_id, at) VALUES (?,?,?,?,?,?,?)",
                (g["round_id"], group_id, kind, customer_id, device_id,
                 lock["device_id"] if lock else None, now))
            _bump(conn, g["event_id"])
        conn.commit()
    return {"granted": True, "kind": kind}


def write_scores(group_id: int, device_id: str, entered_by: int | None,
                 ops: list[dict], db_path=None) -> dict:
    """Apply a batch of queued hole writes, in order.

    Each op: {op_id, hole, gross (1-20, or null to clear), client_ts?,
              customer_id | team_id}.
    Per-op result: "ok", "dup" (op_id already seen; its first result is
    returned and nothing is re-applied), "refused_lock" (this device does
    not hold the group; the value is kept in se_audit), or "invalid".
    The client drops an op from its queue on ok / dup / invalid, and on
    refused_lock tells the scorer someone else has the card."""
    if not device_id:
        return {"error": "device_id required"}
    if len(ops) > MAX_OPS_PER_BATCH:
        return {"error": f"at most {MAX_OPS_PER_BATCH} ops per batch"}
    results = []
    with _closing(_conn(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        g = _group_ctx(conn, group_id)
        if not g:
            conn.rollback()
            return {"error": "no such group"}
        lock = conn.execute("SELECT device_id FROM se_group_locks WHERE group_id = ?",
                            (group_id,)).fetchone()
        holds = bool(lock and lock["device_id"] == device_id)
        members = {r[0] for r in conn.execute(
            "SELECT customer_id FROM se_players WHERE group_id = ?", (group_id,))}
        teams = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT id, customer_id_a, customer_id_b FROM se_teams WHERE group_id = ?",
            (group_id,))}
        par_of = {r[0]: r[1] for r in conn.execute(
            "SELECT hole_number, par FROM se_round_holes WHERE round_id = ?", (g["round_id"],))}
        valid_holes = set(par_of)
        if not valid_holes:
            first = 10 if g["start_hole"] >= 10 and g["holes"] == 9 else 1
            valid_holes = set(range(first, first + g["holes"]))
        now = _now()
        applied = 0
        for op in ops:
            op_id = str(op.get("op_id") or "").strip()
            if not op_id:
                results.append({"op_id": None, "result": "invalid", "why": "op_id missing"})
                continue
            seen = conn.execute("SELECT result FROM se_audit WHERE op_id = ?",
                                (op_id,)).fetchone()
            if seen:
                results.append({"op_id": op_id, "result": "dup", "first": seen[0]})
                continue
            why = None
            try:
                hole = int(op.get("hole"))
            except (TypeError, ValueError):
                hole, why = None, "hole missing"
            gross = op.get("gross")
            if why is None and hole not in valid_holes:
                why = "hole not in this round"
            if why is None and gross is not None:
                try:
                    gross = int(gross)
                except (TypeError, ValueError):
                    why = "gross not a number"
                else:
                    lo, hi = gross_bounds(par_of.get(hole))
                    if not lo <= gross <= hi:
                        why = (f"gross must be {lo}-{hi} on a par {par_of.get(hole)} (max triple)"
                               if par_of.get(hole) else f"gross must be {lo}-{hi}")
            cid = op.get("customer_id")
            tid = op.get("team_id")
            if why is None:
                if tid is not None:
                    tid = int(tid)
                    if tid not in teams:
                        why = "team not in this group"
                    subject = f"t:{tid}"
                    cid = None
                elif cid is not None:
                    cid = int(cid)
                    if cid not in members:
                        why = "player not in this group"
                    subject = f"c:{cid}"
                else:
                    why = "customer_id or team_id required"
            detail = json.dumps({"hole": op.get("hole"), "gross": op.get("gross"),
                                 "customer_id": op.get("customer_id"),
                                 "team_id": op.get("team_id"),
                                 "client_ts": op.get("client_ts")})
            if why:
                result = "invalid"
            elif not holds:
                result = "refused_lock"
            else:
                result = "ok"
                ta, tb = teams.get(tid, (None, None)) if tid is not None else (None, None)
                prev = conn.execute(
                    "SELECT gross FROM se_hole_scores WHERE round_id = ? AND subject_key = ? "
                    "AND hole_number = ?", (g["round_id"], subject, hole)).fetchone()
                if (prev[0] if prev else None) != gross:
                    _after_change(conn, g, group_id,
                                  [cid] if cid is not None else [ta, tb], hole, gross,
                                  entered_by, now, is_team=tid is not None)
                conn.execute(
                    "INSERT INTO se_hole_scores (round_id, group_id, subject_key, customer_id, "
                    "team_id, team_customer_id_a, team_customer_id_b, hole_number, gross, "
                    "entered_by_customer_id, device_id, op_id, client_ts, server_ts) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(round_id, subject_key, hole_number) DO UPDATE SET "
                    "gross = excluded.gross, entered_by_customer_id = excluded.entered_by_customer_id, "
                    "device_id = excluded.device_id, op_id = excluded.op_id, "
                    "client_ts = excluded.client_ts, server_ts = excluded.server_ts",
                    (g["round_id"], group_id, subject, cid, tid, ta, tb, hole, gross,
                     entered_by, device_id, op_id, op.get("client_ts"), now))
                applied += 1
            conn.execute(
                "INSERT INTO se_audit (round_id, group_id, kind, customer_id, device_id, "
                "op_id, result, detail, at) VALUES (?,?,?,?,?,?,?,?,?)",
                (g["round_id"], group_id, "write", entered_by, device_id, op_id, result,
                 json.dumps({**json.loads(detail), "why": why}) if why else detail, now))
            results.append({"op_id": op_id, "result": result, **({"why": why} if why else {})})
        if holds:
            conn.execute("UPDATE se_group_locks SET heartbeat_at = ? WHERE group_id = ?",
                         (now, group_id))
        version = _bump(conn, g["event_id"]) if applied else None
        conn.commit()
    return {"results": results, "holds_lock": holds, "version": version}


# ---------------------------------------------------------------------------
# Sign-off, card flags, closest to the pin, hole-in-one (Kerry #666, ratified
# with the schema in #667)
# ---------------------------------------------------------------------------

def _after_change(conn, g, group_id, cids, hole, gross, entered_by, now, is_team=False):
    """A hole's value changed. Void the affected players' signatures (theirs
    only) and the scorekeeper's attestation, resolve any open flag on that
    hole, and open or withdraw a hole-in-one claim."""
    cids = [c for c in cids if c is not None]
    for c in cids:
        conn.execute(
            "UPDATE se_signoffs SET voided_at = ?, void_reason = ? WHERE group_id = ? "
            "AND customer_id = ? AND kind IN ('player', 'manager') AND voided_at IS NULL",
            (now, f"hole {hole} changed", group_id, c))
        conn.execute(
            "UPDATE se_card_flags SET resolved_at = ?, resolved_by_customer_id = ?, "
            "resolution = 'edited' WHERE group_id = ? AND customer_id = ? AND hole_number = ? "
            "AND resolved_at IS NULL", (now, entered_by, group_id, c, hole))
    conn.execute(
        "UPDATE se_signoffs SET voided_at = ?, void_reason = ? WHERE group_id = ? "
        "AND kind = 'scorekeeper' AND voided_at IS NULL", (now, f"hole {hole} changed", group_id))
    if is_team:
        return                         # the HIO pot is an individual prize
    for c in cids:
        if gross == 1:
            conn.execute(
                "INSERT INTO se_hio_claims (round_id, group_id, customer_id, hole_number, "
                "eligible, at) VALUES (?,?,?,?,?,?) ON CONFLICT(round_id, customer_id, "
                "hole_number) DO UPDATE SET status = 'pending', scorekeeper_customer_id = NULL, "
                "scorekeeper_at = NULL, witness_customer_id = NULL, witness_at = NULL, "
                "verified_by = NULL, verified_at = NULL, at = excluded.at",
                (g["round_id"], group_id, c, hole, 1 if hio_eligible(conn, c, g["round_date"]) else 0,
                 now))
        else:
            conn.execute(
                "UPDATE se_hio_claims SET status = 'withdrawn' WHERE round_id = ? "
                "AND customer_id = ? AND hole_number = ? AND status != 'verified'",
                (g["round_id"], c, hole))


def hio_eligible(conn, customer_id: int, round_date) -> bool:
    """HIO pot: members only (side-games spec). A membership term covering the
    round date, per customer_memberships. No membership table, or no date,
    means 'we cannot say' and the claim stays open for the manager."""
    day = str(round_date or "")[:10]
    if len(day) != 10 or not day[:4].isdigit():
        return True
    try:
        r = conn.execute(
            "SELECT 1 FROM customer_memberships WHERE customer_id = ? "
            "AND substr(started_at, 1, 10) <= ? AND substr(expires_at, 1, 10) >= ? LIMIT 1",
            (customer_id, day, day)).fetchone()
    except sqlite3.OperationalError:
        return True
    return bool(r)


def _subject_keys_for(conn, group_id: int, customer_id: int) -> list[str]:
    keys = [f"c:{customer_id}"]
    for t in conn.execute("SELECT id FROM se_teams WHERE group_id = ? AND ? IN "
                          "(customer_id_a, customer_id_b)", (group_id, customer_id)):
        keys.append(f"t:{t[0]}")
    return keys


def _player_card(conn, g, group_id: int, customer_id: int) -> dict:
    """The gross card a player signs: his own holes, or his team's ball."""
    holes = [r[0] for r in conn.execute(
        "SELECT hole_number FROM se_round_holes WHERE round_id = ? ORDER BY hole_number",
        (g["round_id"],))]
    keys = _subject_keys_for(conn, group_id, customer_id)
    rows = {}
    for k in keys:
        for s in conn.execute("SELECT hole_number, gross FROM se_hole_scores WHERE group_id = ? "
                              "AND subject_key = ? AND gross IS NOT NULL", (group_id, k)):
            rows.setdefault(s[0], s[1])
    if not holes:
        holes = sorted(rows)
    complete = bool(holes) and all(h in rows for h in holes)
    return {"holes": {str(h): rows.get(h) for h in holes}, "complete": complete,
            "total": sum(v for v in rows.values() if v is not None)}


def sign_card(group_id: int, device_id: str, customer_id: int, kind: str = "player",
              signed_by: int | None = None, note: str | None = None, db_path=None) -> dict:
    """Sign a card. 'player': the player signs his own complete card.
    'scorekeeper': the lock holder attests the group. 'manager': on the
    player's behalf, a note required (only via the admin route)."""
    if kind not in ("player", "scorekeeper", "manager"):
        return {"error": "unknown kind"}
    if kind == "manager" and not (note or "").strip():
        return {"error": "a manager signature needs a note"}
    with _closing(_conn(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        g = _group_ctx(conn, group_id)
        if not g:
            conn.rollback()
            return {"error": "no such group"}
        if not conn.execute("SELECT 1 FROM se_players WHERE group_id = ? AND customer_id = ?",
                            (group_id, customer_id)).fetchone():
            conn.rollback()
            return {"error": "that person is not in this group"}
        if kind == "scorekeeper":
            lock = conn.execute("SELECT device_id FROM se_group_locks WHERE group_id = ?",
                                (group_id,)).fetchone()
            if not lock or lock[0] != device_id:
                conn.rollback()
                return {"error": "only the scorekeeper's phone can attest the group"}
            card = {"subjects": {k: v for k, v in _group_scores(conn, group_id).items()}}
        else:
            card = _player_card(conn, g, group_id, customer_id)
            if not card["complete"]:
                conn.rollback()
                return {"error": "the card isn't complete yet"}
            if conn.execute("SELECT 1 FROM se_card_flags WHERE group_id = ? AND customer_id = ? "
                            "AND resolved_at IS NULL", (group_id, customer_id)).fetchone():
                conn.rollback()
                return {"error": "a hole on this card is flagged; it has to be fixed first"}
        now = _now()
        conn.execute(
            "UPDATE se_signoffs SET voided_at = ?, void_reason = 'signed again' WHERE group_id = ? "
            "AND customer_id = ? AND kind = ? AND voided_at IS NULL",
            (now, group_id, customer_id, kind))
        conn.execute(
            "INSERT INTO se_signoffs (round_id, group_id, customer_id, kind, signed_by_customer_id, "
            "device_id, card, note, at) VALUES (?,?,?,?,?,?,?,?,?)",
            (g["round_id"], group_id, customer_id, kind,
             signed_by if signed_by is not None else customer_id, device_id,
             json.dumps(card, sort_keys=True), note, now))
        _bump(conn, g["event_id"])
        conn.commit()
    return {"signed": True, "kind": kind}


def _group_scores(conn, group_id: int) -> dict:
    out: dict = {}
    for s in conn.execute("SELECT subject_key, hole_number, gross FROM se_hole_scores "
                          "WHERE group_id = ? AND gross IS NOT NULL", (group_id,)):
        out.setdefault(s[0], {})[str(s[1])] = s[2]
    return out


def flag_hole(group_id: int, device_id: str, customer_id: int, hole: int,
              note: str | None = None, raised_by: int | None = None, db_path=None) -> dict:
    """'Something's wrong': the flag reopens only this player's card."""
    with _closing(_conn(db_path)) as conn:
        g = _group_ctx(conn, group_id)
        if not g:
            return {"error": "no such group"}
        if not conn.execute("SELECT 1 FROM se_players WHERE group_id = ? AND customer_id = ?",
                            (group_id, customer_id)).fetchone():
            return {"error": "that person is not in this group"}
        now = _now()
        cur = conn.execute(
            "INSERT INTO se_card_flags (round_id, group_id, customer_id, hole_number, note, "
            "raised_by_customer_id, device_id, at) VALUES (?,?,?,?,?,?,?,?) RETURNING id",
            (g["round_id"], group_id, customer_id, int(hole), (note or "").strip() or None,
             raised_by if raised_by is not None else customer_id, device_id, now))
        flag_id = cur.fetchone()[0]
        conn.execute(
            "UPDATE se_signoffs SET voided_at = ?, void_reason = ? WHERE group_id = ? "
            "AND customer_id = ? AND kind IN ('player', 'manager') AND voided_at IS NULL",
            (now, f"hole {hole} flagged", group_id, customer_id))
        _bump(conn, g["event_id"])
        conn.commit()
        return {"flag_id": flag_id}


def resolve_flag(flag_id: int, resolution: str, resolved_by: int | None = None,
                 db_path=None) -> dict:
    with _closing(_conn(db_path)) as conn:
        r = conn.execute("SELECT f.group_id, g.round_id, r.event_id FROM se_card_flags f "
                         "JOIN se_groups g ON g.id = f.group_id JOIN se_rounds r ON r.id = g.round_id "
                         "WHERE f.id = ?", (flag_id,)).fetchone()
        if not r:
            return {"error": "no such flag"}
        conn.execute("UPDATE se_card_flags SET resolved_at = ?, resolved_by_customer_id = ?, "
                     "resolution = ? WHERE id = ? AND resolved_at IS NULL",
                     (_now(), resolved_by, resolution or "resolved", flag_id))
        _bump(conn, r["event_id"])
        conn.commit()
    return {"ok": True}


def _ctp_current(conn, round_id: int, hole: int):
    """The current holder is the latest claim naming a person (a manager
    ruling included); 'No one closer' answers never unseat a holder."""
    return conn.execute(
        "SELECT c.customer_id, c.group_id, c.kind, c.at, p.display_name, g.group_num "
        "FROM se_ctp_claims c LEFT JOIN se_players p ON p.round_id = c.round_id "
        "AND p.customer_id = c.customer_id LEFT JOIN se_groups g ON g.id = c.group_id "
        "WHERE c.round_id = ? AND c.hole_number = ? AND c.kind IN ('claim', 'manager') "
        "ORDER BY c.id DESC LIMIT 1", (round_id, hole)).fetchone()


def claim_ctp(group_id: int, device_id: str, hole: int, customer_id: int | None,
              claimed_by: int | None = None, db_path=None) -> dict:
    """The scorekeeper answers "Did anyone in your group get closer?" with a
    player (claim) or None ("No one closer"). Par 3s only; lock holder only."""
    with _closing(_conn(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        g = _group_ctx(conn, group_id)
        if not g:
            conn.rollback()
            return {"error": "no such group"}
        lock = conn.execute("SELECT device_id FROM se_group_locks WHERE group_id = ?",
                            (group_id,)).fetchone()
        if not lock or lock[0] != device_id:
            conn.rollback()
            return {"error": "only the scorekeeper's phone can answer this"}
        h = conn.execute("SELECT par FROM se_round_holes WHERE round_id = ? AND hole_number = ?",
                         (g["round_id"], int(hole))).fetchone()
        if not h or h[0] != 3:
            conn.rollback()
            return {"error": "closest to the pin is on par 3s only"}
        if customer_id is not None and not conn.execute(
                "SELECT 1 FROM se_players WHERE group_id = ? AND customer_id = ?",
                (group_id, customer_id)).fetchone():
            conn.rollback()
            return {"error": "that person is not in this group"}
        conn.execute(
            "INSERT INTO se_ctp_claims (round_id, group_id, hole_number, customer_id, kind, "
            "claimed_by_customer_id, device_id, at) VALUES (?,?,?,?,?,?,?,?)",
            (g["round_id"], group_id, int(hole), customer_id,
             "claim" if customer_id is not None else "none", claimed_by, device_id, _now()))
        _bump(conn, g["event_id"])
        conn.commit()
    return {"ok": True}


def rule_ctp(round_id: int, hole: int, customer_id: int, db_path=None) -> dict:
    """The manager settles a dispute (or two claims at once on a shotgun)."""
    with _closing(_conn(db_path)) as conn:
        p = conn.execute("SELECT group_id FROM se_players WHERE round_id = ? AND customer_id = ?",
                         (round_id, customer_id)).fetchone()
        ev = conn.execute("SELECT event_id FROM se_rounds WHERE id = ?", (round_id,)).fetchone()
        if not p or not ev:
            return {"error": "that person is not in this round"}
        conn.execute(
            "INSERT INTO se_ctp_claims (round_id, group_id, hole_number, customer_id, kind, at) "
            "VALUES (?,?,?,?, 'manager', ?)", (round_id, p[0], int(hole), customer_id, _now()))
        _bump(conn, ev[0])
        conn.commit()
    return {"ok": True}


def confirm_hio(group_id: int, device_id: str, hio_id: int, confirmer: int,
                db_path=None) -> dict:
    """Scorekeeper confirms from the lock-holding phone; then ONE OTHER player
    in the group (not the ace-maker, not the scorekeeper) confirms from his
    own view. The manager verifies after that (verify_hio)."""
    with _closing(_conn(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        h = conn.execute("SELECT * FROM se_hio_claims WHERE id = ? AND group_id = ?",
                         (hio_id, group_id)).fetchone()
        g = _group_ctx(conn, group_id)
        if not h or not g:
            conn.rollback()
            return {"error": "no such hole-in-one claim"}
        if not h["eligible"]:
            conn.rollback()
            return {"error": "recorded as a score only; the pot is for members"}
        if not conn.execute("SELECT 1 FROM se_players WHERE group_id = ? AND customer_id = ?",
                            (group_id, confirmer)).fetchone():
            conn.rollback()
            return {"error": "that person is not in this group"}
        lock = conn.execute("SELECT device_id FROM se_group_locks WHERE group_id = ?",
                            (group_id,)).fetchone()
        now = _now()
        if h["status"] == "pending":
            if not lock or lock[0] != device_id:
                conn.rollback()
                return {"error": "the scorekeeper confirms first"}
            conn.execute("UPDATE se_hio_claims SET status = 'confirmed', "
                         "scorekeeper_customer_id = ?, scorekeeper_at = ? WHERE id = ?",
                         (confirmer, now, hio_id))
        elif h["status"] == "confirmed":
            if confirmer in (h["customer_id"], h["scorekeeper_customer_id"]):
                conn.rollback()
                return {"error": "another player in the group has to confirm"}
            conn.execute("UPDATE se_hio_claims SET status = 'witnessed', "
                         "witness_customer_id = ?, witness_at = ? WHERE id = ?",
                         (confirmer, now, hio_id))
        else:
            conn.rollback()
            return {"error": f"this claim is already {h['status']}"}
        _bump(conn, g["event_id"])
        conn.commit()
    return {"ok": True}


def verify_hio(hio_id: int, verified_by: str, approve: bool = True, db_path=None) -> dict:
    with _closing(_conn(db_path)) as conn:
        h = conn.execute("SELECT h.status, r.event_id FROM se_hio_claims h JOIN se_rounds r "
                         "ON r.id = h.round_id WHERE h.id = ?", (hio_id,)).fetchone()
        if not h:
            return {"error": "no such hole-in-one claim"}
        if approve and h["status"] != "witnessed":
            return {"error": "the scorekeeper and one other player confirm first"}
        conn.execute("UPDATE se_hio_claims SET status = ?, verified_by = ?, verified_at = ? "
                     "WHERE id = ?", ("verified" if approve else "rejected", verified_by, _now(),
                                      hio_id))
        _bump(conn, h["event_id"])
        conn.commit()
    return {"ok": True}


def _strokes_by_player(players, course) -> dict:
    """Handicap strokes per hole off the LOCKED playing handicap. On a nine
    the convention is open (CA Queue #10/#11), so the screen labels it
    'strokes per GG convention' — GG's league setting is the full card."""
    try:
        from email_parser.handicap_calc import allocate_strokes
    except Exception:
        return {}
    si = {h["hole"]: h["stroke_index"] for h in course if h.get("stroke_index")}
    if not si:
        return {}
    out = {}
    for p in players:
        ph = p.get("playing_handicap")
        if ph is None:
            continue
        try:
            alloc = allocate_strokes(int(round(ph)), si, mode="full_card")
        except Exception:
            # The card's stroke indexes can't carry this handicap on the full
            # card (a nine indexed 1-9). Say so; never guess.
            out.setdefault("_unresolved", []).append(p["customer_id"])
            continue
        out[str(p["customer_id"])] = {str(k): v for k, v in alloc.items() if v}
    return out


def _card_extras(conn, g, group_id: int) -> dict:
    signoffs = [dict(r) for r in conn.execute(
        "SELECT customer_id, kind, signed_by_customer_id, at FROM se_signoffs "
        "WHERE group_id = ? AND voided_at IS NULL ORDER BY id", (group_id,))]
    flags = [dict(r) for r in conn.execute(
        "SELECT id, customer_id, hole_number AS hole, note, at FROM se_card_flags "
        "WHERE group_id = ? AND resolved_at IS NULL ORDER BY id", (group_id,))]
    ctp = {}
    for (hole,) in conn.execute("SELECT hole_number FROM se_round_holes WHERE round_id = ? "
                                "AND par = 3", (g["round_id"],)).fetchall():
        cur = _ctp_current(conn, g["round_id"], hole)
        answered = conn.execute("SELECT 1 FROM se_ctp_claims WHERE round_id = ? AND hole_number = ? "
                                "AND group_id = ?", (g["round_id"], hole, group_id)).fetchone()
        ctp[str(hole)] = {"holder_customer_id": cur["customer_id"] if cur else None,
                          "holder_name": cur["display_name"] if cur else None,
                          "holder_group_num": cur["group_num"] if cur else None,
                          "answered": bool(answered)}
    hio = [dict(r) for r in conn.execute(
        "SELECT id, customer_id, hole_number AS hole, eligible, status, "
        "scorekeeper_customer_id, witness_customer_id FROM se_hio_claims "
        "WHERE group_id = ? AND status NOT IN ('withdrawn') ORDER BY id", (group_id,))]
    players = [dict(p) for p in conn.execute(
        "SELECT customer_id, playing_handicap FROM se_players WHERE group_id = ?", (group_id,))]
    course = [dict(h) for h in conn.execute(
        "SELECT hole_number AS hole, stroke_index FROM se_round_holes WHERE round_id = ?",
        (g["round_id"],))]
    return {"signoffs": signoffs, "flags": flags, "ctp": ctp, "hio": hio,
            "strokes": _strokes_by_player(players, course),
            "strokes_note": "strokes per GG convention" if g["holes"] == 9 else None}


# ---------------------------------------------------------------------------
# The read (Track B, the GG diff, the admin board). CA #661 shape.
# ---------------------------------------------------------------------------

def get_entered_scores(event_id: int, round_id: int | None = None, db_path=None) -> dict:
    with _closing(_conn(db_path)) as conn:
        vr = conn.execute("SELECT version, updated_at FROM se_event_versions "
                          "WHERE event_id = ?", (event_id,)).fetchone()
        q = "SELECT * FROM se_rounds WHERE event_id = ?"
        args: list = [event_id]
        if round_id is not None:
            q += " AND id = ?"
            args.append(round_id)
        rounds_out = []
        for r in conn.execute(q + " ORDER BY round_date, id", args).fetchall():
            rid = r["id"]
            course = [dict(h) for h in conn.execute(
                "SELECT hole_number AS hole, par, stroke_index, yardage "
                "FROM se_round_holes WHERE round_id = ? ORDER BY hole_number", (rid,))]
            locks = {l["group_id"]: l for l in conn.execute(
                "SELECT l.* FROM se_group_locks l JOIN se_groups g ON g.id = l.group_id "
                "WHERE g.round_id = ?", (rid,))}
            last = {}
            by_subject: dict = {}
            for s in conn.execute(
                    "SELECT subject_key, group_id, hole_number, gross, server_ts "
                    "FROM se_hole_scores WHERE round_id = ?", (rid,)):
                last[s["group_id"]] = max(last.get(s["group_id"]) or "", s["server_ts"])
                d = by_subject.setdefault(s["subject_key"], {"scores": {}, "last": ""})
                if s["gross"] is not None:
                    d["scores"][str(s["hole_number"])] = s["gross"]
                d["last"] = max(d["last"], s["server_ts"])
            groups = [{"group_id": g["id"], "group_num": g["group_num"], "label": g["label"],
                       "tee_time": g["tee_time"], "start_hole": g["start_hole"],
                       "scorer_customer_id": (locks[g["id"]]["holder_customer_id"]
                                              if g["id"] in locks else None),
                       "lock_state": "held" if g["id"] in locks else "free",
                       "last_write_at": last.get(g["id"])}
                      for g in conn.execute("SELECT * FROM se_groups WHERE round_id = ? "
                                            "ORDER BY group_num", (rid,))]
            players = []
            for p in conn.execute("SELECT * FROM se_players WHERE round_id = ? "
                                  "ORDER BY group_id, COALESCE(seat, 99), id", (rid,)):
                d = by_subject.get(f"c:{p['customer_id']}", {"scores": {}, "last": None})
                players.append({"customer_id": p["customer_id"], "name": p["display_name"],
                                "group_id": p["group_id"], "tee": p["tee"],
                                "playing_handicap": p["playing_handicap"],
                                "scores": d["scores"], "thru": len(d["scores"]),
                                "last_write_at": d["last"] or None})
            teams = []
            for t in conn.execute("SELECT * FROM se_teams WHERE round_id = ? ORDER BY id",
                                  (rid,)):
                d = by_subject.get(f"t:{t['id']}", {"scores": {}, "last": None})
                teams.append({"team_id": t["id"], "group_id": t["group_id"],
                              "customer_ids": [t["customer_id_a"], t["customer_id_b"]],
                              "label": t["label"], "scores": d["scores"],
                              "thru": len(d["scores"]), "last_write_at": d["last"] or None})
            signed = [dict(x) for x in conn.execute(
                "SELECT customer_id, kind, at FROM se_signoffs WHERE round_id = ? "
                "AND voided_at IS NULL ORDER BY id", (rid,))]
            ctp = {}
            for (hole,) in conn.execute("SELECT hole_number FROM se_round_holes WHERE "
                                        "round_id = ? AND par = 3", (rid,)).fetchall():
                cur = _ctp_current(conn, rid, hole)
                ctp[str(hole)] = ({"customer_id": cur["customer_id"], "name": cur["display_name"],
                                   "group_num": cur["group_num"], "by_manager": cur["kind"] == "manager"}
                                  if cur else None)
            hio = [dict(x) for x in conn.execute(
                "SELECT id, customer_id, hole_number AS hole, eligible, status FROM se_hio_claims "
                "WHERE round_id = ? AND status != 'withdrawn' ORDER BY id", (rid,))]
            rounds_out.append({"round_id": rid, "date": r["round_date"], "label": r["label"],
                               "holes": r["holes"], "status": r["status"],
                               "course": course, "groups": groups, "players": players,
                               "teams": teams, "signoffs": signed, "ctp": ctp, "hio": hio})
    return {"event_id": event_id, "official": False, "source": "tgf-entry",
            "version": int(vr["version"]) if vr else 0,
            "as_of": (vr["updated_at"] if vr else None) or _now(),
            "rounds": rounds_out}
