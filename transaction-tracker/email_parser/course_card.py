"""Course-card entry: load a course's tees, ratings and hole data from the
printed card (CA #786 GO 3, Kerry 2026-09-27).

Until now tees reached the Tracker ONLY through the Golf Genius scorecard
import (`_upsert_course_tee` in database.py). With Golf Genius off after the
Lone Star Cup, a course we have never imported (The Hideout, course 65112)
has no tees, pars, stroke indexes, slope or rating, so there is no course
handicap, no pops, no net and no handicap posting. This module lets a card
be typed in once and writes the SAME three tables the import writes:

  course_tees       one row per tee set (source 'course_card')
  tee_set_ratings   'total' plus 'front' / 'back' nine ratings when given
                    (9-hole handicap posting needs the nine's rating)
  course_tee_holes  par / stroke index / yardage per hole, per tee

A card is validated as a whole before anything is written, and the default
is a dry run that returns the plan. Re-loading the same card updates in
place (the tee is found by course, name, gender and holes), so a typo is
fixed by loading the corrected card.

Card shape (JSON):
  {
    "holes": 18,                         # 9 or 18
    "par":          {"1": 4, ..., "18": 5},   # shared by every tee unless
    "stroke_index": {"1": 7, ..., "18": 10},  #   a tee carries its own
    "tees": [
      {"tee_name": "Blue", "gender": "M", "bands": ["<50"],
       "rating": 71.2, "slope": 128,
       "front": {"rating": 35.7, "slope": 127},
       "back":  {"rating": 35.5, "slope": 129},
       "yardage": {"1": 402, ...},            # optional
       "par": {...}, "stroke_index": {...}}   # optional per-tee override
    ]
  }

Portable-SQL rule (#682): lower() on both sides, no INSERT OR REPLACE,
RETURNING for new ids. No schema change: every column already exists.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SOURCE = "course_card"
_VALID_BANDS = {"<50", "50-64", "65+", "L"}


def _intmap(m) -> dict:
    out = {}
    for k, v in (m or {}).items():
        try:
            out[int(k)] = int(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            out[k] = v  # kept so validation can name it
    return out


def validate_card(card: dict) -> list[str]:
    """Every problem with the card, as plain sentences. Empty = loadable."""
    errs: list[str] = []
    n = card.get("holes")
    if n not in (9, 18):
        return ["holes must be 9 or 18"]
    want = set(range(1, n + 1))
    shared_par, shared_si = _intmap(card.get("par")), _intmap(card.get("stroke_index"))
    tees = card.get("tees") or []
    if not tees:
        errs.append("the card has no tees")
    names = set()
    for i, t in enumerate(tees, 1):
        label = t.get("tee_name") or f"tee #{i}"
        if not (t.get("tee_name") or "").strip():
            errs.append(f"tee #{i} has no name")
        g = (t.get("gender") or "M").upper()
        if g not in ("M", "F"):
            errs.append(f"{label}: gender must be M or F")
        key = ((t.get("tee_name") or "").strip().lower(), g)
        if key in names:
            errs.append(f"{label}: listed twice for the same gender")
        names.add(key)
        for b in t.get("bands") or []:
            if b not in _VALID_BANDS:
                errs.append(f"{label}: unknown TGF band {b!r} (use <50, 50-64, 65+ or L)")
        lo, hi = (60.0, 80.0) if n == 18 else (27.0, 40.0)
        r, s = t.get("rating"), t.get("slope")
        if r is None or s is None:
            errs.append(f"{label}: rating and slope are required")
        else:
            if not (lo <= float(r) <= hi):
                errs.append(f"{label}: rating {r} is outside {lo}-{hi} for {n} holes")
            if not (55 <= int(s) <= 155):
                errs.append(f"{label}: slope {s} is outside 55-155")
        for side in ("front", "back"):
            nr = t.get(side)
            if nr is None:
                continue
            if n == 9:
                errs.append(f"{label}: a 9-hole card has no {side} nine rating")
                continue
            if nr.get("rating") is None or nr.get("slope") is None:
                errs.append(f"{label}: {side} nine needs rating and slope")
            elif not (27.0 <= float(nr["rating"]) <= 40.0 and 55 <= int(nr["slope"]) <= 155):
                errs.append(f"{label}: {side} nine rating/slope look wrong "
                            f"({nr['rating']}/{nr['slope']})")
        par = _intmap(t.get("par")) or shared_par
        si = _intmap(t.get("stroke_index")) or shared_si
        if set(par) != want:
            errs.append(f"{label}: par must list holes 1-{n} exactly")
        elif any(p not in (3, 4, 5, 6) for p in par.values()):
            errs.append(f"{label}: a par is not 3-6")
        if set(si) != want:
            errs.append(f"{label}: stroke index must list holes 1-{n} exactly")
        elif sorted(si.values()) != list(range(1, n + 1)):
            errs.append(f"{label}: stroke indexes must use 1-{n} once each")
        yd = _intmap(t.get("yardage"))
        if yd and not set(yd) <= want:
            errs.append(f"{label}: yardage lists holes outside 1-{n}")
    return errs


def load_course_card(course_id: int, card: dict, apply: bool = False,
                     db_path=None) -> dict:
    """Validate and (with apply) write a course card. Dry run by default."""
    from . import database as db
    errs = validate_card(card)
    out = {"course_id": course_id, "applied": False, "errors": errs, "tees": []}
    with db._connect(db_path) as conn:
        db._ensure_scoring_tables(conn)  # course_tees / tee_set_ratings exist
        c = conn.execute("SELECT course_id, name FROM courses WHERE course_id = ?",
                         (int(course_id),)).fetchone()
        if not c:
            out["errors"] = [f"no course {course_id}"] + errs
            return out
        out["course"] = c["name"]
        if errs:
            return out
        n = card["holes"]
        shared_par, shared_si = _intmap(card.get("par")), _intmap(card.get("stroke_index"))
        for t in card["tees"]:
            name = t["tee_name"].strip()
            g = (t.get("gender") or "M").upper()
            par = _intmap(t.get("par")) or shared_par
            si = _intmap(t.get("stroke_index")) or shared_si
            yd = _intmap(t.get("yardage"))
            existing = conn.execute(
                """SELECT tee_id, source FROM course_tees
                    WHERE course_id = ? AND lower(tee_name) = lower(?)
                      AND gender = ? AND holes = ?
                    ORDER BY tee_id LIMIT 1""",
                (c["course_id"], name, g, n)).fetchone()
            plan = {"tee_name": name, "gender": g, "holes": n,
                    "rating": float(t["rating"]), "slope": int(t["slope"]),
                    "par": sum(par.values()),
                    "bands": t.get("bands") or [],
                    "nines": [s for s in ("front", "back") if t.get(s)],
                    "action": "update" if existing else "create",
                    "tee_id": existing["tee_id"] if existing else None}
            if existing and existing["source"] not in (SOURCE, "admin"):
                plan["note"] = (f"updates a tee first written by '{existing['source']}'; "
                                "the card's numbers replace it")
            out["tees"].append(plan)
            if not apply:
                continue
            bands = ",".join(t.get("bands") or []) or None
            yard_total = sum(v for v in yd.values() if v) or None
            if existing:
                tee_id = existing["tee_id"]
                conn.execute(
                    """UPDATE course_tees SET rating = ?, slope = ?, par = ?,
                              tgf_bands = COALESCE(?, tgf_bands),
                              yardage_total = COALESCE(?, yardage_total),
                              nine = ?, is_ladies = ?, source = ?
                        WHERE tee_id = ?""",
                    (plan["rating"], plan["slope"], plan["par"], bands, yard_total,
                     "full" if n == 18 else None, 1 if g == "F" else 0, SOURCE, tee_id))
            else:
                tee_id = conn.execute(
                    """INSERT INTO course_tees (course_id, tee_name, tgf_bands, gender,
                                               holes, nine, par, slope, rating,
                                               yardage_total, is_ladies, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING tee_id""",
                    (c["course_id"], name, bands, g, n, "full" if n == 18 else None,
                     plan["par"], plan["slope"], plan["rating"], yard_total,
                     1 if g == "F" else 0, SOURCE)).fetchone()[0]
            plan["tee_id"] = tee_id
            ratings = [("total", plan["rating"], plan["slope"])]
            for side in ("front", "back"):
                if t.get(side):
                    ratings.append((side, float(t[side]["rating"]), int(t[side]["slope"])))
            for rtype, rating, slope in ratings:
                hit = conn.execute("SELECT 1 FROM tee_set_ratings WHERE tee_id = ? "
                                   "AND rating_type = ?", (tee_id, rtype)).fetchone()
                if hit:
                    conn.execute("""UPDATE tee_set_ratings SET course_rating = ?, slope = ?,
                                           source = ?, updated_at = datetime('now')
                                     WHERE tee_id = ? AND rating_type = ?""",
                                 (rating, slope, SOURCE, tee_id, rtype))
                else:
                    conn.execute("""INSERT INTO tee_set_ratings
                                        (tee_id, rating_type, course_rating, slope, source)
                                    VALUES (?, ?, ?, ?, ?)""",
                                 (tee_id, rtype, rating, slope, SOURCE))
            for h in range(1, n + 1):
                hit = conn.execute("SELECT 1 FROM course_tee_holes WHERE tee_id = ? "
                                   "AND hole_number = ?", (tee_id, h)).fetchone()
                vals = (par.get(h), yd.get(h), si.get(h))
                if hit:
                    conn.execute("""UPDATE course_tee_holes SET par = ?, yardage = ?,
                                           stroke_index = ?
                                     WHERE tee_id = ? AND hole_number = ?""",
                                 vals + (tee_id, h))
                else:
                    conn.execute("""INSERT INTO course_tee_holes
                                        (tee_id, hole_number, par, yardage, stroke_index)
                                    VALUES (?, ?, ?, ?, ?)""", (tee_id, h) + vals)
        if apply:
            conn.commit()
            out["applied"] = True
            logger.info("course card loaded: course %s, %d tee(s)", course_id, len(out["tees"]))
    return out


def read_course_card(course_id: int, db_path=None) -> dict:
    """The course card as the Tracker holds it now: every tee with its
    ratings and hole rows. Read-only; for checking a load against paper."""
    from . import database as db
    with db._connect(db_path) as conn:
        db._ensure_scoring_tables(conn)
        c = conn.execute("SELECT course_id, name FROM courses WHERE course_id = ?",
                         (int(course_id),)).fetchone()
        if not c:
            return {"error": f"no course {course_id}"}
        tees = []
        for t in conn.execute(
                """SELECT tee_id, tee_name, gg_alias, tgf_bands, gender, holes, nine,
                          par, slope, rating, source FROM course_tees
                    WHERE course_id = ? ORDER BY tee_id""", (c["course_id"],)):
            t = dict(t)
            t["ratings"] = {r["rating_type"]: {"rating": r["course_rating"],
                                               "slope": r["slope"], "source": r["source"]}
                            for r in conn.execute(
                                "SELECT rating_type, course_rating, slope, source "
                                "FROM tee_set_ratings WHERE tee_id = ?", (t["tee_id"],))}
            t["holes"] = [dict(h) for h in conn.execute(
                "SELECT hole_number AS hole, par, stroke_index, yardage "
                "FROM course_tee_holes WHERE tee_id = ? ORDER BY hole_number",
                (t["tee_id"],))]
            tees.append(t)
        return {"course_id": c["course_id"], "course": c["name"],
                "n_tees": len(tees), "tees": tees}


def archive_tee_versions(course_id: int, as_of: str, label: str, apply: bool = False,
                         db_path=None) -> dict:
    """VERSION A COURSE'S TEES BEFORE A CORRECTION (Kerry 10/30, Kissing Tree:
    "Those past events are what they are and nothing should change for them.
    Version control updates to the course's tees").

    For every tee of the course that carries hole data and is not itself an
    archive, a copy is made of the tee as it stands now (row, ratings, holes)
    named "<tee> (before <as_of>)", with version_label=<label>,
    valid_to=<the day before as_of>, no TGF bands
    and no GG alias, so nothing that picks a tee by band or name finds it.
    Every scoring round on that tee dated BEFORE as_of is re-pointed to the
    copy, so a past event keeps the par, stroke index, yardage and rating it
    was played on. The live tee keeps its id and its bands; the corrected
    card is then loaded onto it (load_course_card). Idempotent: a tee that
    already has a copy under this label is skipped. Dry run by default."""
    from datetime import date, timedelta
    from . import database as db
    try:
        valid_to = (date.fromisoformat(as_of) - timedelta(days=1)).isoformat()
    except ValueError:
        return {"error": f"as_of must be YYYY-MM-DD, got {as_of!r}"}
    out = {"course_id": course_id, "as_of": as_of, "label": label, "applied": False, "tees": []}
    with db._connect(db_path) as conn:
        db._ensure_scoring_tables(conn)
        tees = [dict(r) for r in conn.execute(
            """SELECT * FROM course_tees WHERE course_id = ?
                 AND COALESCE(version_label, '') = '' AND COALESCE(valid_to, '') = ''
                 AND EXISTS (SELECT 1 FROM course_tee_holes h WHERE h.tee_id = course_tees.tee_id)
               ORDER BY tee_id""", (int(course_id),))]
        cols = [r[1] for r in conn.execute("PRAGMA table_info(course_tees)")]
        for t in tees:
            # The archive is named "<tee> (before <as_of>)": the schema's
            # unique key (course, name, gender, holes, nine, slope, rating)
            # forbids a same-named twin, and a tee lookup by name ("Back")
            # must never land on the archive.
            arc_name = f"{t['tee_name']} (before {as_of})"
            done = conn.execute(
                """SELECT tee_id FROM course_tees WHERE course_id = ? AND lower(tee_name) = lower(?)
                     AND gender = ? AND holes = ? AND version_label = ?""",
                (t["course_id"], arc_name, t["gender"], t["holes"], label)).fetchone()
            rounds = conn.execute(
                "SELECT COUNT(*) FROM scoring_rounds WHERE tee_id = ? AND COALESCE(round_date, '') < ?",
                (t["tee_id"], as_of)).fetchone()[0]
            plan = {"tee_id": t["tee_id"], "tee_name": t["tee_name"], "gender": t["gender"],
                    "bands": t.get("tgf_bands"), "past_rounds": rounds,
                    "action": "skip (already archived)" if done else "archive"}
            out["tees"].append(plan)
            if done or not apply:
                if done:
                    plan["archive_tee_id"] = done[0]
                continue
            copy = {c: t.get(c) for c in cols if c != "tee_id"}
            copy.update({"tee_name": arc_name, "tgf_bands": None, "gg_alias": None, "version_label": label,
                         "valid_to": valid_to, "source": "admin"})  # the schema allows import|course_card|usga_crdb|admin
            names = list(copy)
            new_id = conn.execute(
                f"INSERT INTO course_tees ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)}) "
                "RETURNING tee_id", [copy[n] for n in names]).fetchone()[0]
            conn.execute("""INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index)
                            SELECT ?, hole_number, par, yardage, stroke_index
                              FROM course_tee_holes WHERE tee_id = ?""", (new_id, t["tee_id"]))
            rcols = [r[1] for r in conn.execute("PRAGMA table_info(tee_set_ratings)")
                     if r[1] not in ("id", "tee_id")]
            conn.execute(f"""INSERT INTO tee_set_ratings (tee_id, {', '.join(rcols)})
                             SELECT ?, {', '.join(rcols)} FROM tee_set_ratings WHERE tee_id = ?""",
                         (new_id, t["tee_id"]))
            moved = conn.execute(
                "UPDATE scoring_rounds SET tee_id = ? WHERE tee_id = ? AND COALESCE(round_date, '') < ?",
                (new_id, t["tee_id"], as_of)).rowcount
            plan.update({"archive_tee_id": new_id, "rounds_repointed": moved})
        if apply:
            conn.commit()
            out["applied"] = True
            try:
                db.log_agent_action("course_card", "tee_versions_archived",
                                    f"course {course_id}: {label}, valid_to {valid_to}, "
                                    f"{sum(p.get('rounds_repointed', 0) for p in out['tees'])} past rounds kept on the archive",
                                    db_path=db_path)
            except Exception:
                pass
    return out
