-- COURSE STAFF (Kerry 2026-10-13: "Please do add these into our database and
-- assign appropriate roles. Also when we run events thru the quarry, those
-- contacts should come up in the event setup when Quarry is selected. Those
-- would be there for record and for the system to know who to send docs too.";
-- rule 3b "Deploy now" #1737). Shape: Tracker Build #1699, db-claude PASS with
-- changes #1701 (Schema v3.0 #9; customer_id stands in for user_id until R6).
-- Each contact is a person with a customer_id (principle 6); the email is read
-- from customer_emails, never copied here. One person may hold several roles.
-- Who gets the Course Files email is data on top (CCO #1687): To the primary
-- active 'tgf_contact', CC the other active 'tgf_contact' rows. A new role is
-- a new migration (#1087). Rows are deactivated, never deleted.
CREATE TABLE IF NOT EXISTS course_staff (
    course_staff_id INTEGER PRIMARY KEY,
    course_id       INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    customer_id     INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,
    role            TEXT NOT NULL CHECK (role IN ('tgf_contact', 'general_manager',
                        'head_golf_professional', 'assistant_general_manager',
                        'golf_shop', 'food_beverage', 'billing')),
    is_primary      INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    notes           TEXT,
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by      TEXT,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (course_id, customer_id, role)
);
CREATE INDEX IF NOT EXISTS idx_course_staff_course ON course_staff (course_id, active);
CREATE INDEX IF NOT EXISTS idx_course_staff_customer ON course_staff (customer_id);
-- One primary per role per course, among active rows (#1701).
CREATE UNIQUE INDEX IF NOT EXISTS ux_course_staff_primary
    ON course_staff (course_id, role) WHERE is_primary = 1 AND active = 1;
