-- HOME CHAPTER BY ID (Kerry APPROVED, CoS #1084, rule 3b; shape #1077 /
-- #1064-2). Every member carries ONE home chapter by chapter_id; a move is a
-- new history row, never an overwrite; chapters carry their own fields.
-- The backfill is a separate, reported step (home_chapter.backfill_home_chapters):
-- it copies from customers.chapter (the ruled source, CA #784), never from
-- where someone plays. customers.chapter stays, READ-ONLY by rule, until
-- every reader moves to home_chapter_id; it is dropped in its own migration.
-- The org_units rename waits for the Postgres move (#728, #1082-1).

-- 1. Chapter fields. Per Kerry's standing rule (#1087: "hardened schema
--    driving everything"), NOT here: gg_portal_ids (a JSON list; it becomes a
--    chapter_portals table, its own ruling) and default_tee_band (waits on
--    the A-6 tee-band decision).
ALTER TABLE chapters ADD COLUMN city TEXT;
ALTER TABLE chapters ADD COLUMN state TEXT;
ALTER TABLE chapters ADD COLUMN manager_customer_id INTEGER REFERENCES customers(customer_id);
ALTER TABLE chapters ADD COLUMN sender_email TEXT;
ALTER TABLE chapters ADD COLUMN launched_on TEXT;

-- 2. One home chapter per customer, by id
ALTER TABLE customers ADD COLUMN home_chapter_id INTEGER REFERENCES chapters(chapter_id);
CREATE INDEX IF NOT EXISTS idx_customers_home_chapter ON customers (home_chapter_id);

-- 3. A move closes the open row and opens a new one
CREATE TABLE IF NOT EXISTS customer_chapter_history (
    id           INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
    chapter_id   INTEGER NOT NULL REFERENCES chapters(chapter_id),
    from_date    TEXT NOT NULL,
    to_date      TEXT,
    set_by       TEXT NOT NULL,
    reason       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cch_customer ON customer_chapter_history (customer_id, to_date);
