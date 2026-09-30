-- Drop the JSON hole list that 0004 added (CoS #1090-2: "drop the unused
-- column in its own migration"). Nothing ever wrote it; blind_draw_holes
-- (0006) holds the fact as rows. Requires SQLite 3.35+ (DROP COLUMN);
-- portable to Postgres as written.
ALTER TABLE blind_draws DROP COLUMN missed_holes;
