-- PACE OF PLAY, MEASURED (Kerry 2026-10-19, rule 3b: "Yes to both, go ahead"
-- #2092; design db-claude #2073 §1, measure #2084, entry_split #2103,
-- clean + adjusted count #2084/#2093, suggest only #2100, notice = the
-- morning digest #2096 so there is NO notice key and NO mailer here).
-- Two DERIVED tables, rebuilt from se_audit (the lossless record of every
-- save) by email_parser/score_entry.py `rebuild_pace` -- the only writer.
-- Nothing here is ever the record: drop both tables and a rebuild restores
-- them. Integer seconds, ids not names, no JSON, enums by CHECK.
-- Also declared in email_parser/score_entry.py's DDL (CREATE IF NOT EXISTS
-- both places, so the order they run in never matters; same as 0009).
-- Reversible: DROP TABLE se_player_pace; DROP TABLE se_group_pace.

-- One row per GROUP per timed round.
--   seconds_per_hole      (t[end anchor] - t[start anchor]) / holes_timed,
--                         first hole to second-to-last in play order; the
--                         last hole is never used
--   holes_timed           play-order holes between the two anchors
--   field_median_seconds  median seconds_per_hole of the round's COUNTING
--                         groups (status clean/adjusted); NULL when none
--   status                clean | adjusted (a catch-up spread or an anchor
--                         moved) | flagged (any flag_* = 1; shown, not counted)
--   batches               catch-up batches spread inside the series
--   takeovers             se_audit 'takeover' rows for the group (why an
--                         entry_split may have fired)
CREATE TABLE IF NOT EXISTS se_group_pace (
    id                    INTEGER PRIMARY KEY,
    round_id              INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
    group_id              INTEGER NOT NULL REFERENCES se_groups(id) ON DELETE CASCADE,
    holes_timed           INTEGER NOT NULL CHECK (holes_timed >= 0),
    seconds_per_hole      INTEGER,
    field_median_seconds  INTEGER,
    status                TEXT NOT NULL CHECK (status IN ('clean', 'adjusted', 'flagged')),
    start_moved           INTEGER NOT NULL DEFAULT 0 CHECK (start_moved IN (0, 1)),
    end_moved             INTEGER NOT NULL DEFAULT 0 CHECK (end_moved IN (0, 1)),
    batches               INTEGER NOT NULL DEFAULT 0 CHECK (batches >= 0),
    flag_few_holes        INTEGER NOT NULL DEFAULT 0 CHECK (flag_few_holes IN (0, 1)),
    flag_long_gap         INTEGER NOT NULL DEFAULT 0 CHECK (flag_long_gap IN (0, 1)),
    flag_clock            INTEGER NOT NULL DEFAULT 0 CHECK (flag_clock IN (0, 1)),
    flag_entry_split      INTEGER NOT NULL DEFAULT 0 CHECK (flag_entry_split IN (0, 1)),
    flag_manager_entry    INTEGER NOT NULL DEFAULT 0 CHECK (flag_manager_entry IN (0, 1)),
    takeovers             INTEGER NOT NULL DEFAULT 0 CHECK (takeovers >= 0),
    method_version        INTEGER NOT NULL,
    computed_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (round_id, group_id)
);
CREATE INDEX IF NOT EXISTS idx_se_group_pace_round ON se_group_pace (round_id);

-- One row per PLAYER per timed round, carrying the GROUP's pace (Kerry:
-- "Pace is measured per group but that group number should be an entry for
-- each player as well"). A player's history is simply their rows; the
-- average and the counting-round count are read on the fly.
--   group_seconds_per_hole  the group's number, copied
--   rel_seconds_per_hole    group pace minus that round's field median
--   holes_saved             span holes this player has a save on
--   status                  the group's status, or 'flagged' when the
--                           player's own flag is set
--   flag_partial            saves on fewer than the minimum span holes
--   flag_regrouped          saves in more than one group this round (the row
--                           carries the group holding most of them)
--   counts                  1 = counts toward the 10 rounds and the average
CREATE TABLE IF NOT EXISTS se_player_pace (
    id                      INTEGER PRIMARY KEY,
    customer_id             INTEGER NOT NULL REFERENCES customers(customer_id),
    round_id                INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
    group_id                INTEGER NOT NULL REFERENCES se_groups(id) ON DELETE CASCADE,
    group_size              INTEGER NOT NULL CHECK (group_size >= 1),
    group_seconds_per_hole  INTEGER,
    rel_seconds_per_hole    INTEGER,
    holes_saved             INTEGER NOT NULL DEFAULT 0 CHECK (holes_saved >= 0),
    status                  TEXT NOT NULL CHECK (status IN ('clean', 'adjusted', 'flagged')),
    flag_partial            INTEGER NOT NULL DEFAULT 0 CHECK (flag_partial IN (0, 1)),
    flag_regrouped          INTEGER NOT NULL DEFAULT 0 CHECK (flag_regrouped IN (0, 1)),
    counts                  INTEGER NOT NULL DEFAULT 0 CHECK (counts IN (0, 1)),
    method_version          INTEGER NOT NULL,
    computed_at             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (counts = 0 OR status <> 'flagged'),
    UNIQUE (customer_id, round_id)
);
CREATE INDEX IF NOT EXISTS idx_se_player_pace_customer ON se_player_pace (customer_id, counts);
CREATE INDEX IF NOT EXISTS idx_se_player_pace_round ON se_player_pace (round_id);
