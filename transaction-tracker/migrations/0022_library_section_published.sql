-- LIBRARY SECTION 'published' (Kerry 2026-10-14 to librarian-claude, verbatim:
-- "Yes, add a published section - what would go in there? Nothing yet
-- right?" then "Post the request now"; request #1854). Documents written for
-- members or the public, each its own doc_id; filing one is NOT publishing it
-- (each publication is a separate Kerry decision, rule 3b). Starts empty.
INSERT INTO library_sections (code, name, folder) VALUES
    ('published', 'Published', '08_PUBLISHED')
ON CONFLICT (code) DO NOTHING;
