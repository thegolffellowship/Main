-- EVENT DECLINE REASONS (Kerry 2026-10-13: "Make sure database is setup to
-- recieve player selections of reasons they can't play. We'll want to track
-- whatever people are willing to give us."). The optional one-tap reason on
-- the invitation's Can't make it page (email_parser/invitations.py). One row
-- per event and person (principle 6: customer_id); a later tap updates the
-- row, never adds a second. A new reason is a new migration.
CREATE TABLE IF NOT EXISTS event_decline_reasons (
    event_decline_reason_id INTEGER PRIMARY KEY,
    event_id     INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,
    reason       TEXT NOT NULL CHECK (reason IN ('Schedule', 'Weather', 'Course or price',
                     'Injury', 'Other')),
    source       TEXT NOT NULL DEFAULT 'invitation',
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (event_id, customer_id)
);
CREATE INDEX IF NOT EXISTS idx_event_decline_reasons_customer ON event_decline_reasons (customer_id);
