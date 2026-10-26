-- PARTIAL ROUNDS: LATE ARRIVAL, LAST-SECOND ADD / SWITCH, WD (Kerry
-- 2026-10-26, verbatim: "what happens when player shows up on hole 4???";
-- "Interesting call on the +Player. Could also be there for a threesome as a
-- standard, for someone we add last second or switches from another group
-- last second"; "someone could WD due to whatever reason too, having to
-- leave after any number of holes"; "Player late arrival needs to ask if
-- that player will make up missed holes at end of regular scoring").
-- RULE 3b SCHEMA CHANGE: built on branch tb5-no-show-2, waits on Kerry's OK.
--
-- One row per player per round per kind, written only by
-- email_parser/score_entry.py (mark_player_missing / add_player_to_card /
-- set_makeup):
--   kind    joined  a player on this card put back with "+ Player" / "Here
--                   now" after his group had started: plays from `hole`
--           added   someone put on this card by "+ Player" (a roster player
--                   on no card, or a switch from another card of the same
--                   round, `from_group_id`): plays from `hole`
--           left    left the course (WD): `hole` is the first hole he does
--                   NOT play
--   makeup  joined / added only: will he make up the holes before `hole`
--           at the end of regular scoring? yes | no | unfinished (said yes,
--           then could not finish) | NULL (not asked yet: treated as no)
-- The holes a partial round did not play are NOT PLAYED: never par, never
-- holding the card, covered for Team / Cart Net by a Rule 15 missed-hole blind
-- (blind_draw_holes). ids not names (customer_id), enums by CHECK, no JSON.
-- Also declared in score_entry.py's DDL (CREATE IF NOT EXISTS both places,
-- as 0037 / 0040). Reversible: DROP TABLE se_partial_rounds.
CREATE TABLE IF NOT EXISTS se_partial_rounds (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id       INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
    group_id       INTEGER NOT NULL REFERENCES se_groups(id) ON DELETE CASCADE,
    customer_id    INTEGER NOT NULL REFERENCES customers(customer_id),
    kind           TEXT NOT NULL CHECK (kind IN ('joined', 'added', 'left')),
    hole           INTEGER NOT NULL CHECK (hole BETWEEN 1 AND 18),
    makeup         TEXT CHECK (makeup IN ('yes', 'no', 'unfinished')),
    from_group_id  INTEGER REFERENCES se_groups(id) ON DELETE SET NULL,
    marked_by      INTEGER REFERENCES customers(customer_id),
    device_id      TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    UNIQUE (round_id, customer_id, kind));
CREATE INDEX IF NOT EXISTS idx_se_partial_rounds_group ON se_partial_rounds (group_id);
