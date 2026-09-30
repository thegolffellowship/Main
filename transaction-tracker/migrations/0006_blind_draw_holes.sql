-- Which holes a missed-hole blind covers (spec #1073 section 5; Kerry OK
-- #1078; CoS #1090-2 under Kerry's #1087 hardened-schema rule: a hole list is
-- rows, not a JSON column). One row per (blind, hole). No rows for a blind =
-- it covers every hole (the open-seat and N/H blinds).
-- Why this is not redundant: it replaces blind_draws.missed_holes (JSON,
-- never written; dropped in 0007). No other table records which holes a
-- blind plays; blind_draws.holes is the 9/18 SHEET, a different fact.
CREATE TABLE IF NOT EXISTS blind_draw_holes (
    blind_draw_id  INTEGER NOT NULL REFERENCES blind_draws(id) ON DELETE CASCADE,
    hole           INTEGER NOT NULL CHECK (hole BETWEEN 1 AND 18),
    PRIMARY KEY (blind_draw_id, hole)
);
