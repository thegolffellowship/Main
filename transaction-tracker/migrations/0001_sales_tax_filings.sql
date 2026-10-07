-- Texas sales-tax filing record (Kerry 2026-09-30, #1047: "I approve the
-- sales_tax_filings table"; CFO #1043 ASK 2). A month is FILED only when a
-- row here says so; otherwise OPEN, or LATE once past due. Money is numeric.
CREATE TABLE IF NOT EXISTS sales_tax_filings (
    period            TEXT PRIMARY KEY,          -- 'YYYY-MM'
    due_date          TEXT NOT NULL,             -- 'YYYY-MM-DD'
    filed_at          TEXT,                      -- date the return was filed
    total_tx_sales    NUMERIC,
    taxable_sales     NUMERIC,
    tax               NUMERIC,
    discount          NUMERIC,
    penalty           NUMERIC,
    interest          NUMERIC,
    amount_paid       NUMERIC,
    webfile_ref       TEXT,
    payment_ref       TEXT,
    confirmation_path TEXT,
    evidence          TEXT NOT NULL CHECK (evidence IN ('confirmation', 'kerry_word')),
    note              TEXT,
    entered_by        TEXT NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
