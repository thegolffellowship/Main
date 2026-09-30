-- Why a blind was drawn (Kerry 2026-09-30, "Good on both", CoS #1078/#1079;
-- spec #1073 section 6). A blind used to mean only an EMPTY seat; it now also
-- stands in for an N/H player's seat (no index of record and no starting
-- handicap) and, with the #1021 wave, for the holes a player missed.
--   reason        open_seat | nh | missed_hole
--   missed_holes  JSON list of hole numbers the blind covers; NULL = every hole
-- (`holes` already exists on this table and means the 9/18 sheet, so the
-- hole list gets its own name.) Existing rows are open-seat blinds.
ALTER TABLE blind_draws ADD COLUMN reason TEXT DEFAULT 'open_seat';
ALTER TABLE blind_draws ADD COLUMN missed_holes TEXT;
UPDATE blind_draws SET reason = 'open_seat' WHERE reason IS NULL;
