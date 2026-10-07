-- THE TGF LIBRARY: governing documents as append-only rows.
-- Authority: KERRY "Ok yes" (#1117) to option A of the Librarian's spec
-- (#1114 §0): "may the Library keep its documents in a new append-only
-- library_documents table, with the repo copy exported daily?"
-- Gate: db-claude #1124-2, number 0008, PASS on the shape with conditions
-- (a)-(h); the final PASS is on this file.
--
-- WHY NOT REDUNDANT (Librarian #1123, accepted by db-claude #1124-h):
-- No existing table holds governing documents. The repo files are lost at
-- deploy, and app_settings and the mailbox are not versioned document
-- stores. Authority: #1117 (KERRY: "Ok yes"), spec #1114 §0.
--
-- Rows are never deleted or edited in place. Superseding sets
-- status='superseded' and superseded_by_id on the old row; that is the only
-- UPDATE the module (email_parser/library.py) issues.
-- Foreign keys are DECLARATIONS ONLY on production (foreign_keys = 0,
-- #1124-f): library_put checks every supersedes target and section in code.

-- (a) the section taxonomy is a lookup table, not a CHECK list (#1087)
CREATE TABLE IF NOT EXISTS library_sections (
    code    TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    folder  TEXT NOT NULL      -- the OneDrive folder(s), OneDrive IA v1.0 (#1118)
);
INSERT INTO library_sections (code, name, folder) VALUES
    ('standards', 'Standards', '01_STANDARDS'),
    ('specs',     'Specs',     '07_TECHNOLOGY/Specs'),
    ('strategy',  'Strategy',  '06_STRATEGY/Plans + 06_STRATEGY/Chief_of_Staff'),
    ('decisions', 'Decisions', '06_STRATEGY/Update_Fragments + 06_STRATEGY/Decision_Captures'),
    ('context',   'Context',   '06_STRATEGY/Session_Summaries + 06_STRATEGY/Chief_of_Staff'),
    ('audits',    'Audits',    '07_TECHNOLOGY/UX_Audits + 04_FINANCE/Audits')
ON CONFLICT (code) DO NOTHING;

-- (h) id INTEGER PRIMARY KEY, no AUTOINCREMENT (same form as 0005)
CREATE TABLE IF NOT EXISTS library_documents (
    id                INTEGER PRIMARY KEY,
    doc_id            TEXT NOT NULL,
    section           TEXT NOT NULL REFERENCES library_sections(code),
    lane              TEXT,                          -- context/ only; (g) TEXT until a lanes table
    filename          TEXT NOT NULL,
    version_major     INTEGER NOT NULL,              -- (c) NOT NULL: UNIQUE treats NULLs as distinct
    version_minor     INTEGER NOT NULL,
    title             TEXT NOT NULL,
    -- (b) a closed lifecycle keeps its CHECK
    status            TEXT NOT NULL CHECK (status IN ('draft', 'proposed', 'ratified', 'living', 'superseded')),
    owner             TEXT NOT NULL,                 -- (g)
    ratified_by       TEXT,
    ratified_date     TEXT,
    authority_post    INTEGER,                       -- the mailbox post carrying the authority
    onedrive_path     TEXT,
    project_files     INTEGER NOT NULL DEFAULT 0 CHECK (project_files IN (0, 1)),   -- (d)
    body              TEXT NOT NULL,
    body_sha256       TEXT NOT NULL,
    supersedes_id     INTEGER REFERENCES library_documents(id),
    superseded_by_id  INTEGER REFERENCES library_documents(id),                     -- (d)
    filed_by          TEXT NOT NULL,                 -- (g)
    filed_at          TEXT NOT NULL DEFAULT (datetime('now')),                       -- (d)
    exported_commit   TEXT,
    UNIQUE (doc_id, version_major, version_minor)
);
CREATE INDEX IF NOT EXISTS idx_library_documents_section ON library_documents (section, status);
CREATE INDEX IF NOT EXISTS idx_library_documents_doc ON library_documents (lower(doc_id));

-- Who must read a document (lanes / skills, by name), one row each.
CREATE TABLE IF NOT EXISTS library_document_reads (
    document_id  INTEGER NOT NULL REFERENCES library_documents(id),              -- (e)
    reader       TEXT NOT NULL,
    PRIMARY KEY (document_id, reader)
);
