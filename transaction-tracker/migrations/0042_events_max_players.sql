-- MAX PLAYERS (Kerry 2026-10-29, verbatim: "There of course needs to be the
-- ability to add max players for an event. I obviously had a max I
-- contracted, but system didn't know that.").
-- The contracted field size, set on Edit Event. NULL = no limit. Only a paid
-- registration holds a spot (email_parser/waitlist.py `capacity`); at the
-- limit the registration gate (/register/<event_id>) shows the waitlist page
-- instead of the store. RULE 3b schema: Kerry asked for it in the same
-- message that ruled the waitlist ("Deploy", 10/29).
-- Reversible: the column is ignored when NULL.
ALTER TABLE events ADD COLUMN max_players INTEGER CHECK (max_players IS NULL OR max_players > 0);
