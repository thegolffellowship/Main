-- The Ambassador flag (Kerry, Pairings Spec v1.2 #1036-4: "I will currently
-- determine the Ambassador role. Definitely not something to be derived right
-- now."). One row per customer per chapter; set by Kerry (or Robert for
-- Austin on Kerry's say-so). Removing an ambassador sets ambassador = 0 with
-- who/when/why; rows are never deleted, so pairings history stays
-- explainable (Tracker Build #1055-3). Approved CoS #1046; shape #1055.
CREATE TABLE IF NOT EXISTS customer_ambassadors (
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
    chapter_id   INTEGER NOT NULL REFERENCES chapters(chapter_id),
    ambassador   INTEGER NOT NULL DEFAULT 1 CHECK (ambassador IN (0, 1)),
    set_by       TEXT NOT NULL,
    set_at       TEXT NOT NULL DEFAULT (datetime('now')),
    note         TEXT,
    PRIMARY KEY (customer_id, chapter_id)
);
CREATE INDEX IF NOT EXISTS idx_customer_ambassadors_chapter
    ON customer_ambassadors (chapter_id, ambassador);
