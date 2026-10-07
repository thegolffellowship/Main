"""SCHEMA AUDIT, read-only (Kerry 2026-09-30, CoS #1064-2 / #1067-2).

Kerry: "We need to find other situations like the chapters text field in our
schema. That's a problem. I thought we had rooted all of that out, but that's
a bad example with redundant data that dominoes through things."

Two reads, neither writes anything:

  chapter_dry_run()   the home-chapter migration (#1064-2) as a dry run:
      the chapters table as it stands, every distinct customers.chapter
      value and whether it resolves to a chapter_id, the rows that would
      not, and the proposed migration text (NOT applied; Kerry rules).
  redundancy_scan()   every table and column, flagged by kind:
      entity_text     a text column naming an entity that has (or should
                      have) its own table and id (chapter, course, event,
                      customer/player, tee, game/contest, account/category)
      twin            that text column sits beside its id column (the same
                      fact stored twice); counts rows where they disagree in
                      the simplest sense: text present, id missing
      money_text      a money-named column whose values are stored as TEXT
      free_enum       a status/type/category/source column with no CHECK,
                      with its distinct values
    and, per flagged column, row counts, rows that don't resolve to an id
    where a resolver exists, and the fix pattern (FK + backfill + text
    read-only until its readers move).

Portable SQL (#682): lower() on both sides, no NOCASE, no writes.
"""
from __future__ import annotations

import re

CHAPTER_ALIASES = {"aus": "austin", "atx": "austin", "sa": "san antonio",
                   "sat": "san antonio", "dal": "dfw", "dallas": "dfw",
                   "fort worth": "dfw", "hou": "houston"}

PROPOSED_CHAPTER_MIGRATION = """-- migrations/00xx_home_chapter.sql  (PROPOSED, not applied; Kerry rules, rule 3b)
-- 1. Chapter fields (the chapter is the entity; everything else points at it)
ALTER TABLE chapters ADD COLUMN city TEXT;
ALTER TABLE chapters ADD COLUMN state TEXT;
ALTER TABLE chapters ADD COLUMN manager_customer_id INTEGER REFERENCES customers(customer_id);
ALTER TABLE chapters ADD COLUMN gg_portal_ids TEXT;        -- JSON list of Golf Genius portal ids
ALTER TABLE chapters ADD COLUMN default_tee_band TEXT;     -- e.g. '50-64'
ALTER TABLE chapters ADD COLUMN sender_email TEXT;         -- the chapter's outgoing address
ALTER TABLE chapters ADD COLUMN launched_on DATE;
-- (chapter_id, name, short_code, timezone, status already exist)

-- 2. ONE home chapter per customer, by id
ALTER TABLE customers ADD COLUMN home_chapter_id INTEGER REFERENCES chapters(chapter_id);

-- 3. A move is a new row, never an overwrite
CREATE TABLE customer_chapter_history (
    id           INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
    chapter_id   INTEGER NOT NULL REFERENCES chapters(chapter_id),
    from_date    DATE NOT NULL,
    to_date      DATE,                -- NULL = current
    set_by       TEXT NOT NULL,
    reason       TEXT,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_cch_customer ON customer_chapter_history(customer_id, to_date);

-- 4. Backfill (a separate, reported step): home_chapter_id from the text
--    column where it resolves; one open history row per resolved customer,
--    from_date = first event played (else created_at), set_by 'backfill'.
--    Unresolved rows stay NULL and are listed for Kerry.
-- 5. customers.chapter stays, READ-ONLY, until every reader moves to
--    home_chapter_id; then it is dropped in its own migration."""


def _chapter_map(conn) -> dict:
    m = {}
    for r in conn.execute("SELECT chapter_id, name, short_code FROM chapters"):
        m[(r["name"] or "").strip().lower()] = r["chapter_id"]
        if r["short_code"]:
            m.setdefault(r["short_code"].strip().lower(), r["chapter_id"])
    for a, full in CHAPTER_ALIASES.items():
        if full in m:
            m.setdefault(a, m[full])
    return m


def chapter_dry_run(db_path=None) -> dict:
    from email_parser import database as db
    with db._connect(db_path) as conn:
        chapters = [dict(r) for r in conn.execute("SELECT * FROM chapters ORDER BY chapter_id")]
        cmap = _chapter_map(conn)
        vals = [dict(r) for r in conn.execute(
            """SELECT chapter AS value, COUNT(*) AS customers
               FROM customers GROUP BY chapter ORDER BY COUNT(*) DESC""")]
        unresolved_rows = []
        for v in vals:
            raw = (v["value"] or "").strip()
            v["resolves_to"] = cmap.get(raw.lower()) if raw else None
            if raw and v["resolves_to"] is None:
                unresolved_rows += [dict(r) for r in conn.execute(
                    """SELECT customer_id, first_name, last_name, chapter, current_player_status
                       FROM customers WHERE chapter = ? ORDER BY customer_id""", (v["value"],))]
        ev = conn.execute(
            """SELECT COUNT(*) AS n, SUM(CASE WHEN chapter_id IS NULL AND COALESCE(chapter,'') <> ''
                                            THEN 1 ELSE 0 END) AS text_no_id
               FROM events""").fetchone()
        it = conn.execute(
            """SELECT COUNT(*) AS n, SUM(CASE WHEN chapter_id IS NULL AND COALESCE(chapter,'') <> ''
                                            THEN 1 ELSE 0 END) AS text_no_id
               FROM items""").fetchone()
        # A member whose home chapter disagrees with where they play most:
        # informational, for the backfill's eye (items.chapter is the EVENT's
        # chapter, so it is evidence, never a source).
        disagree = conn.execute(
            """SELECT COUNT(*) FROM (
                 SELECT c.customer_id, lower(c.chapter) AS home,
                        (SELECT lower(e.chapter) FROM items i JOIN events e ON e.id = i.event_id
                          WHERE i.customer_id = c.customer_id AND COALESCE(e.chapter,'') <> ''
                          GROUP BY lower(e.chapter) ORDER BY COUNT(*) DESC LIMIT 1) AS plays
                 FROM customers c WHERE COALESCE(c.chapter,'') <> '') x
               WHERE x.plays IS NOT NULL AND x.plays <> x.home""").fetchone()[0]
    total = sum(v["customers"] for v in vals)
    resolved = sum(v["customers"] for v in vals if v["resolves_to"])
    blank = sum(v["customers"] for v in vals if not (v["value"] or "").strip())
    return {"chapters": chapters,
            "customers_total": total,
            "would_resolve": resolved,
            "blank": blank,
            "unresolved_text": total - resolved - blank,
            "values": vals,
            "unresolved_rows": unresolved_rows[:200],
            "home_vs_most_played_disagree": disagree,
            "events_chapter_text_without_id": ev["text_no_id"] or 0,
            "items_chapter_text_without_id": it["text_no_id"] or 0,
            "proposed_migration": PROPOSED_CHAPTER_MIGRATION,
            "applied": False}


# ── the redundancy scan ─────────────────────────────────────────────────────
ENTITY_PATTERNS = [
    ("chapter", re.compile(r"^(home_)?chapter(_name)?$"), "chapter_id"),
    ("course", re.compile(r"^course(_name)?$"), "course_id"),
    ("event", re.compile(r"^(event_name|item_name|matched_event|event|canonical_event_name|event_title)$"), "event_id"),
    ("customer", re.compile(r"^(customer|customer_name|player_name|player|golfer|golfer_name|member_name|"
                            r"player_a|player_b|name_a|name_b|winner_name|winner)$"), "customer_id"),
    ("tee", re.compile(r"^(tee|tee_choice|tee_name|tee_label)$"), "tee_id"),
    ("game", re.compile(r"^(game|game_name|contest|contest_type|contest_name)$"), "game_id"),
    ("account", re.compile(r"^(account|account_name|category|category_name|vendor|vendor_name)$"), "account_id"),
]
MONEY = re.compile(r"(price|amount|fee|cost|total|paid|payout|balance|credit|refund|purse|pot|markup|tax|"
                   r"revenue|expense|net|gross_amt|prize)", re.I)
NOT_MONEY = re.compile(r"(_id$|_at$|_date$|count|holes|_pct$|percent|rate$|net_points|gross_points|"
                       r"^net$|^gross$|network|_net_|stableford|_rank|_type$|status|method|_by$|note|flag)", re.I)
ENUMISH = re.compile(r"(^|_)(status|type|category|source|kind|role|mode|state)$", re.I)
IDS_FOR = {"chapter_id": ("chapter_id", "home_chapter_id"), "course_id": ("course_id",),
           "event_id": ("event_id", "tgf_event_id", "matched_event_id"),
           "customer_id": ("customer_id", "customer_a_id", "customer_b_id", "winner_customer_id",
                           "player_customer_id"),
           "tee_id": ("tee_id", "course_tee_id", "tee_set_id"), "game_id": ("game_id", "contest_id"),
           "account_id": ("account_id", "category_id", "vendor_id", "coa_id")}


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _resolver_sql(kind: str, t: str, col: str):
    """SQL counting rows whose text names no entity row (where a lookup
    table exists). None when there is nothing sensible to resolve against."""
    c = f"{_q(t)}.{_q(col)}"
    if kind == "event":
        return (f"""SELECT COUNT(*) FROM {_q(t)} WHERE COALESCE({c},'') <> ''
                    AND NOT EXISTS (SELECT 1 FROM events e WHERE lower(e.item_name) = lower({c}))
                    AND NOT EXISTS (SELECT 1 FROM event_aliases a WHERE lower(a.alias_name) = lower({c}))""")
    if kind == "course":
        return (f"""SELECT COUNT(*) FROM {_q(t)} WHERE COALESCE({c},'') <> ''
                    AND NOT EXISTS (SELECT 1 FROM courses x WHERE lower(x.name) = lower({c}))
                    AND NOT EXISTS (SELECT 1 FROM course_aliases a WHERE lower(a.alias_name) = lower({c}))""")
    if kind == "chapter":
        return (f"""SELECT COUNT(*) FROM {_q(t)} WHERE COALESCE({c},'') <> ''
                    AND NOT EXISTS (SELECT 1 FROM chapters x WHERE lower(x.name) = lower({c})
                                    OR lower(x.short_code) = lower({c}))""")
    return None


def redundancy_scan(db_path=None, enum_values: int = 12) -> dict:
    from email_parser import database as db
    out, errors = [], []
    with db._connect(db_path) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        sql_of = {r[0]: (r[1] or "") for r in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table'")}
        for t in tables:
            try:
                cols = [dict(r) for r in conn.execute(f"PRAGMA table_info({_q(t)})")]
                n_rows = conn.execute(f"SELECT COUNT(*) FROM {_q(t)}").fetchone()[0]
            except Exception as e:
                errors.append({"table": t, "error": str(e)})
                continue
            names = {c["name"] for c in cols}
            for c in cols:
                col, decl = c["name"], (c["type"] or "").upper()
                qc = f"{_q(t)}.{_q(col)}"
                try:
                    # entity text
                    for kind, pat, idcol in ENTITY_PATTERNS:
                        if not pat.match(col.lower()):
                            continue
                        if t in ("customers", "events", "courses", "chapters") and \
                                (kind == {"customers": "customer", "events": "event",
                                          "courses": "course", "chapters": "chapter"}[t]):
                            break  # the entity's own name column
                        filled = conn.execute(f"SELECT COUNT(*) FROM {_q(t)} WHERE COALESCE({qc},'') <> ''").fetchone()[0]
                        if not filled:
                            break
                        sib = [i for i in IDS_FOR[idcol] if i in names]
                        row = {"table": t, "column": col, "kind": "twin" if sib else "entity_text",
                               "entity": kind, "rows": n_rows, "filled": filled, "id_column": sib[0] if sib else None}
                        if sib:
                            row["text_without_id"] = conn.execute(
                                f"SELECT COUNT(*) FROM {_q(t)} WHERE COALESCE({qc},'') <> '' AND {_q(t)}.{_q(sib[0])} IS NULL"
                            ).fetchone()[0]
                        rs = _resolver_sql(kind, t, col)
                        if rs:
                            row["names_matching_nothing"] = conn.execute(rs).fetchone()[0]
                        out.append(row)
                        break
                    # money as text
                    if MONEY.search(col) and not NOT_MONEY.search(col):
                        as_text = conn.execute(
                            f"SELECT COUNT(*) FROM {_q(t)} WHERE typeof({qc}) = 'text' AND trim({qc}) <> ''").fetchone()[0]
                        if as_text or decl in ("TEXT", "VARCHAR") or decl.startswith("VARCHAR"):
                            out.append({"table": t, "column": col, "kind": "money_text", "declared": decl or "(none)",
                                        "rows": n_rows, "stored_as_text": as_text})
                    # free enum
                    if ENUMISH.search(col) and decl.split("(")[0] in ("TEXT", "VARCHAR", ""):
                        has_check = bool(re.search(rf"{re.escape(col)}[^,]*CHECK\s*\(", sql_of.get(t, ""), re.I))
                        if not has_check and n_rows:
                            vals = [dict(r) for r in conn.execute(
                                f"SELECT {qc} AS v, COUNT(*) AS n FROM {_q(t)} GROUP BY {qc} ORDER BY COUNT(*) DESC LIMIT ?",
                                (enum_values + 1,))]
                            distinct = conn.execute(f"SELECT COUNT(DISTINCT {qc}) FROM {_q(t)}").fetchone()[0]
                            # case/space variants of one value are the smell
                            variants = conn.execute(
                                f"SELECT COUNT(DISTINCT {qc}) - COUNT(DISTINCT lower(trim({qc}))) FROM {_q(t)}").fetchone()[0]
                            out.append({"table": t, "column": col, "kind": "free_enum", "rows": n_rows,
                                        "distinct": distinct, "case_variants": variants,
                                        "top_values": vals[:enum_values]})
                except Exception as e:
                    errors.append({"table": t, "column": col, "error": str(e)})
    summary: dict = {}
    for r in out:
        summary[r["kind"]] = summary.get(r["kind"], 0) + 1
    return {"tables_scanned": len(tables), "findings": len(out), "by_kind": summary,
            "rows": out, "errors": errors, "writes": 0}
