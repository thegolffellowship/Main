-- THE SCORE A FLAG PROPOSES (Kerry 2026-10-09, on his practice card: "Flagged
-- for fix but doesn't say what it should be fixed to. Seems like the
-- notification should come thru just for approval and do I approve or deny as
-- the manager"). A player who flags a hole now says what it should be; the
-- scorekeeper or the manager approves (the score is written) or denies (the
-- card stays, the player signs). One row per flag; a flag raised before this
-- table (or by an old phone) has none and keeps the "Fix it" path.
-- Also declared in email_parser/score_entry.py's DDL (CREATE IF NOT EXISTS
-- both places, so the order they run in never matters).
CREATE TABLE IF NOT EXISTS se_flag_proposals (
    flag_id         INTEGER PRIMARY KEY REFERENCES se_card_flags(id) ON DELETE CASCADE,
    proposed_gross  INTEGER NOT NULL CHECK (proposed_gross BETWEEN 1 AND 20)
);
