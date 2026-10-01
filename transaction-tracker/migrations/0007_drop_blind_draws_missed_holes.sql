-- Drop the JSON hole list that 0004 added (CoS #1090-2: "drop the unused
-- column in its own migration"; db-claude PASS #1124). Nothing ever wrote it;
-- blind_draw_holes (0006, live v2.522.59) holds the fact as rows.
-- Why this is not redundant: it removes a redundant store and adds none.
-- Needs SQLite 3.35+ for DROP COLUMN; production is 3.46.1 (#1107). Portable
-- to Postgres as written.
ALTER TABLE blind_draws DROP COLUMN missed_holes;
