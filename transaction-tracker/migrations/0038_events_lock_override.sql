-- PER-EVENT LOCK OVERRIDE (Kerry 2026-10-26, Tracker Build 5 session: "Yes
-- build the manager override"; the standard lock days are the
-- pairings_auto_weekdays dial: Monday-Thursday events the day before,
-- Friday two days before, Saturday/Sunday three days before, all 5:00 PM).
-- lock_override is the event's own lock as Central wall-clock time,
-- 'YYYY-MM-DD HH:MM'. NULL (the default) means the standard. One reader:
-- database.event_lock_at(). Set on Edit Event by a manager or admin.
-- Reversible: the column is ignored when NULL.
ALTER TABLE events ADD COLUMN lock_override TEXT;
