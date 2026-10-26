-- NO-SHOW: THE SCORER'S "PLAYER MISSING" (Kerry 2026-09-30, mailbox #1021,
-- ratified; Pairings Spec v1.4 12.2; Event Ops one-pager 10/26; built for
-- 10/27 on Kerry's "would like to build for tomorrow"). One row per player
-- per round once the scorer taps Player missing:
--   status  late     "Running late, keep him on the card"
--           unknown  "Don't know yet": asked again each hole; absent after
--                    no_show_absent_after_holes holes (default 3, Kerry 10/26:
--                    "Both should be at 3p"; 4 on 9/30)
--           absent   "No, take him off this card"
--           present  "+ Player": back on the card
-- ids not names (customer_id), enums by CHECK. Only email_parser/
-- score_entry.py reads or writes it. Also declared in score_entry.py's DDL
-- (CREATE IF NOT EXISTS both places, as 0037). Reversible: DROP TABLE se_no_shows.
CREATE TABLE IF NOT EXISTS se_no_shows (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id          INTEGER NOT NULL REFERENCES se_rounds(id) ON DELETE CASCADE,
    group_id          INTEGER NOT NULL REFERENCES se_groups(id) ON DELETE CASCADE,
    customer_id       INTEGER NOT NULL REFERENCES customers(customer_id),
    status            TEXT NOT NULL CHECK (status IN ('late', 'unknown', 'absent', 'present')),
    first_asked_hole  INTEGER,
    last_asked_hole   INTEGER,
    holes_asked       INTEGER NOT NULL DEFAULT 0 CHECK (holes_asked >= 0),
    marked_by         INTEGER REFERENCES customers(customer_id),
    device_id         TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE (round_id, customer_id));
CREATE INDEX IF NOT EXISTS idx_se_no_shows_group ON se_no_shows (group_id);
