"""Plain-SQL migrations (CA #682, portable-SQL rule: "new tables and columns
get a migration file"). Every `migrations/NNNN_name.sql` is applied ONCE per
database, in name order, and recorded in `schema_migrations`. A file must be
idempotent (CREATE ... IF NOT EXISTS) and portable to Postgres."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def apply_migrations(conn) -> list:
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                        name       TEXT PRIMARY KEY,
                        applied_at TEXT NOT NULL DEFAULT (datetime('now')))""")
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations").fetchall()}
    applied = []
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if f.name in done:
            continue
        conn.executescript(f.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (f.name,))
        conn.commit()
        applied.append(f.name)
        logger.info("migration applied: %s", f.name)
    return applied
