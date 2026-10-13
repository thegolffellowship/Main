-- COURSE STAFF: a 'scheduling' role (Kerry 2026-10-13: "Yes, add a scheduling
-- role after close-out"). The person who books TGF's dates and handles the
-- contracts (e.g. a course's Director of Sales). 0014's role list had no such
-- role; Canyon Springs' sales director was filed under 'billing' with a note
-- until this lands (#1745/#1746). SQLite cannot alter a CHECK, so the table is
-- rebuilt: same columns, same rows, same ids, the CHECK widened by one value,
-- and the three indexes re-created. Nothing else changes.
CREATE TABLE course_staff_new (
    course_staff_id INTEGER PRIMARY KEY,
    course_id       INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    customer_id     INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,
    role            TEXT NOT NULL CHECK (role IN ('tgf_contact', 'scheduling', 'general_manager',
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
INSERT INTO course_staff_new (course_staff_id, course_id, customer_id, role, is_primary, notes,
                              active, created_at, created_by, updated_at)
    SELECT course_staff_id, course_id, customer_id, role, is_primary, notes,
           active, created_at, created_by, updated_at
      FROM course_staff;
DROP TABLE course_staff;
ALTER TABLE course_staff_new RENAME TO course_staff;
CREATE INDEX IF NOT EXISTS idx_course_staff_course ON course_staff (course_id, active);
CREATE INDEX IF NOT EXISTS idx_course_staff_customer ON course_staff (customer_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_course_staff_primary
    ON course_staff (course_id, role) WHERE is_primary = 1 AND active = 1;
