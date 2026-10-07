-- The explicit N/H flag (Kerry, "Good on both", CoS #1078 item 1, correction
-- #1079). A manager marks a player with no handicap as N/H for ONE event:
-- the player's scores still enter like anyone's; Side Games' engine plays
-- them at zero and a blind stands in for their money (#1064, #1067, #1073).
-- One row per event per player. Clearing sets nh = 0 with who/when; rows are
-- kept so the history stays explainable. Keyed by customer_id (principle 6);
-- a GG RSVP with no customer cannot be flagged until it is linked.
CREATE TABLE IF NOT EXISTS event_nh_flags (
    event_id     INTEGER NOT NULL REFERENCES events(id),
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
    nh           INTEGER NOT NULL DEFAULT 1 CHECK (nh IN (0, 1)),
    set_by       TEXT NOT NULL,
    set_at       TEXT NOT NULL DEFAULT (datetime('now')),
    note         TEXT,
    PRIMARY KEY (event_id, customer_id)
);
CREATE INDEX IF NOT EXISTS idx_event_nh_flags_event ON event_nh_flags (event_id, nh);
