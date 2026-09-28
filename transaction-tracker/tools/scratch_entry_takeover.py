"""Scratch entry takeover (CA #811, GO in #829) — Tracker Build.

On the REHEARSAL SCRATCH COPY ONLY: make entered scores the scoring record
for chosen events, so the downstream lanes (handicaps, games, MVP, payouts,
points) run on entered rows instead of Golf Genius's, and can diff against
GG afterwards.

publish_entered_round never writes entered rows beside GG rows (about 110
readers of scoring_rounds ignore `source` and would double-count). So, per
event, this tool:

  1. SAVES THE SHADOW DIFF FIRST: publish_event(dry run) + entry_parity,
     as JSON beside the scratch file. That file is the G-0 parity result
     (CA #829: "Save the shadow diff first").
  2. PARKS the event's non-entry scoring_rounds / scoring_holes in
     `scoring_rounds_gg_parked` / `scoring_holes_gg_parked` INSIDE THE
     SCRATCH FILE, same ids, and removes them from the live tables.
  3. Moves the scratch file's `entry_record_from` cutover back to the
     earliest chosen event date (the old value is kept in the report).
  4. Runs publish_event(apply=True), now in authoritative mode.

`--undo` puts the parked rows back, removes the `source='entry'` rows the
takeover wrote, and restores the cutover.

GUARDS (the same family as Track A / Track B's harnesses):
  * always needs --i-am-scratch;
  * the file must sit in a `rehearsal/` directory or carry "scratch" in its
    name, must not be /data/transactions.db, and must not be the file
    DATABASE_PATH names in this environment;
  * prints the file it is about to change before touching it;
  * sets TGF_REHEARSAL=1 before importing the app (outbound blocked);
  * is never imported by the app and has no route or bridge.

usage:
  python3 tools/scratch_entry_takeover.py <scratch.db> --events 3309,3315 --i-am-scratch
  python3 tools/scratch_entry_takeover.py <scratch.db> --events 3309,3315 --i-am-scratch --undo
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PARKED_ROUNDS = "scoring_rounds_gg_parked"
PARKED_HOLES = "scoring_holes_gg_parked"
SETTING = "entry_record_from"
SETTING_SAVED = "entry_record_from_before_takeover"


def refuse_unless_scratch(db: str, argv: list[str], env: dict) -> Path:
    """The guard, as a function so the test can prove every refusal.
    Returns the resolved path or raises SystemExit with the reason."""
    if "--i-am-scratch" not in argv:
        raise SystemExit("refusing: pass --i-am-scratch (this tool only runs on the rehearsal copy)")
    p = Path(db).resolve()
    if not p.is_file():
        raise SystemExit(f"refusing: {p} does not exist")
    if str(p) == "/data/transactions.db":
        raise SystemExit(f"refusing: {p} is the production database")
    live = env.get("DATABASE_PATH")
    if live and live != ":memory:" and Path(live).resolve() == p:
        raise SystemExit(f"refusing: {p} is this environment's DATABASE_PATH (the live file)")
    if p.parent.name != "rehearsal" and "scratch" not in p.name.lower():
        raise SystemExit(f"refusing: {p} is not in a rehearsal/ directory and has no "
                         "'scratch' in its name")
    return p


def _cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _ensure_parked(conn):
    # Scratch-only tables, never created by the app: copy the live shape.
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if PARKED_ROUNDS not in have:
        conn.execute(f"CREATE TABLE {PARKED_ROUNDS} AS SELECT * FROM scoring_rounds WHERE 0")
    if PARKED_HOLES not in have:
        conn.execute(f"CREATE TABLE {PARKED_HOLES} AS SELECT * FROM scoring_holes WHERE 0")


def park_event(conn, event_id: int) -> dict:
    """Move the event's non-entry rounds (and their holes) to the parked
    tables, keeping ids. Idempotent: a second call finds nothing to move."""
    _ensure_parked(conn)
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM scoring_rounds WHERE event_id = ? "
        "AND lower(COALESCE(source, 'gg')) <> 'entry'", (event_id,)).fetchall()]
    out = {"rounds_parked": len(ids), "holes_parked": 0, "handicap_rounds_pointing": 0}
    if not ids:
        return out
    q = ",".join("?" * len(ids))
    rc, hc = ",".join(_cols(conn, "scoring_rounds")), ",".join(_cols(conn, "scoring_holes"))
    conn.execute(f"INSERT INTO {PARKED_ROUNDS} ({rc}) SELECT {rc} FROM scoring_rounds "
                 f"WHERE id IN ({q})", ids)
    out["holes_parked"] = conn.execute(
        f"INSERT INTO {PARKED_HOLES} ({hc}) SELECT {hc} FROM scoring_holes "
        f"WHERE scoring_round_id IN ({q})", ids).rowcount
    if "scoring_round_id" in _cols(conn, "handicap_rounds"):
        # Left as they are: undo restores the same round ids, so the links
        # come back whole. Reported so a lane reading handicaps knows.
        out["handicap_rounds_pointing"] = conn.execute(
            f"SELECT COUNT(*) FROM handicap_rounds WHERE scoring_round_id IN ({q})",
            ids).fetchone()[0]
    conn.execute(f"DELETE FROM scoring_holes WHERE scoring_round_id IN ({q})", ids)
    conn.execute(f"DELETE FROM scoring_rounds WHERE id IN ({q})", ids)
    return out


def unpark_event(conn, event_id: int) -> dict:
    _ensure_parked(conn)
    entry = [r[0] for r in conn.execute(
        "SELECT id FROM scoring_rounds WHERE event_id = ? AND lower(source) = 'entry'",
        (event_id,)).fetchall()]
    if entry:
        q = ",".join("?" * len(entry))
        conn.execute(f"DELETE FROM scoring_holes WHERE scoring_round_id IN ({q})", entry)
        conn.execute(f"DELETE FROM scoring_rounds WHERE id IN ({q})", entry)
    ids = [r[0] for r in conn.execute(
        f"SELECT id FROM {PARKED_ROUNDS} WHERE event_id = ?", (event_id,)).fetchall()]
    if ids:
        q = ",".join("?" * len(ids))
        rc, hc = ",".join(_cols(conn, "scoring_rounds")), ",".join(_cols(conn, "scoring_holes"))
        conn.execute(f"INSERT INTO scoring_rounds ({rc}) SELECT {rc} FROM {PARKED_ROUNDS} "
                     f"WHERE id IN ({q})", ids)
        conn.execute(f"INSERT INTO scoring_holes ({hc}) SELECT {hc} FROM {PARKED_HOLES} "
                     f"WHERE scoring_round_id IN ({q})", ids)
        conn.execute(f"DELETE FROM {PARKED_HOLES} WHERE scoring_round_id IN ({q})", ids)
        conn.execute(f"DELETE FROM {PARKED_ROUNDS} WHERE id IN ({q})", ids)
    return {"entry_rounds_removed": len(entry), "rounds_restored": len(ids)}


def _raw(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = OFF")   # parked ids keep handicap links for undo
    return conn


def run(db: Path, event_ids: list[int], undo: bool = False, out_dir: Path | None = None) -> dict:
    os.environ["TGF_REHEARSAL"] = "1"
    os.environ["DATABASE_PATH"] = str(db)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from email_parser import database as _db            # noqa: E402
    from email_parser import entry_publish as ep        # noqa: E402

    out_dir = out_dir or db.parent
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {"db": str(db), "events": event_ids, "undo": undo, "at": stamp, "per_event": {}}

    if undo:
        with _raw(db) as conn:
            for eid in event_ids:
                report["per_event"][eid] = unpark_event(conn, eid)
            conn.commit()
        saved = _db.get_app_setting(SETTING_SAVED, str(db))
        if saved is not None:
            _db.set_app_setting(SETTING, saved, str(db))
            report["cutover_restored_to"] = saved
        return report

    # 1. The shadow diff, BEFORE anything changes.
    shadow = {}
    for eid in event_ids:
        shadow[eid] = {"publish_dry_run": ep.publish_event(eid, apply=False, db_path=str(db)),
                       "parity": ep.entry_parity(eid, db_path=str(db))}
    shadow_path = out_dir / f"takeover-shadow-diff-{stamp}.json"
    shadow_path.write_text(json.dumps(shadow, indent=2, default=str))
    report["shadow_diff_file"] = str(shadow_path)

    # 2. Park the GG rows inside the scratch file.
    dates = []
    with _raw(db) as conn:
        for eid in event_ids:
            r = conn.execute("SELECT event_date FROM events WHERE id = ?", (eid,)).fetchone()
            if not r:
                report["per_event"][eid] = {"error": f"no event {eid}"}
                continue
            if r[0]:
                dates.append(str(r[0])[:10])
            report["per_event"][eid] = {"park": park_event(conn, eid)}
        conn.commit()

    # 3. Cutover back to the earliest chosen event (scratch file only).
    before = ep.cutover_date(str(db))
    if _db.get_app_setting(SETTING_SAVED, str(db)) is None:
        _db.set_app_setting(SETTING_SAVED, before, str(db))
    if dates and min(dates) < before:
        _db.set_app_setting(SETTING, min(dates), str(db))
    report["cutover"] = {"before": before, "now": ep.cutover_date(str(db))}

    # 4. Publish, now authoritative.
    for eid, rec in report["per_event"].items():
        if "error" in rec:
            continue
        pub = ep.publish_event(eid, apply=True, db_path=str(db))
        rec.update({"mode": pub.get("mode"), "mode_reason": pub.get("mode_reason"),
                    "applied": pub.get("applied"), "summary": pub.get("summary")})
    return report


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        raise SystemExit(__doc__)
    db = refuse_unless_scratch(argv[0], argv, dict(os.environ))
    try:
        ev = argv[argv.index("--events") + 1]
    except (ValueError, IndexError):
        raise SystemExit("refusing: --events <id,id> is required")
    event_ids = [int(x) for x in ev.split(",") if x.strip()]
    undo = "--undo" in argv
    print(f"{'UNDO on' if undo else 'TAKEOVER on'} scratch file {db} for events {event_ids}")
    rep = run(db, event_ids, undo=undo)
    path = db.parent / f"takeover-report-{rep['at']}{'-undo' if undo else ''}.json"
    path.write_text(json.dumps(rep, indent=2, default=str))
    print(json.dumps(rep, indent=2, default=str))
    print(f"report: {path}")


if __name__ == "__main__":
    main()
