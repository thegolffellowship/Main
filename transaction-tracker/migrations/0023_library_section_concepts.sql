-- LIBRARY SECTION 'concepts' (Kerry 2026-10-15 ~12:05 PM, via CoS #1904: "Are
-- you able to wire that into my Tracker so it's visible on the internet? For
-- manager/admin view only... Probably need a new section that I can click in
-- the Nav Bar to access it."). Self-contained HTML concept pages, served by
-- the Tracker's CONCEPTS section (manager and above, plus advisors per #1905).
-- The Library stays the source and the versioning; the Tracker only reads.
INSERT INTO library_sections (code, name, folder) VALUES
    ('concepts', 'Concepts', '09_CONCEPTS')
ON CONFLICT (code) DO NOTHING;
