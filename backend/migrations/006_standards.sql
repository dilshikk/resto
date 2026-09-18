-- MADO CHECKLIST — MADO Standards (v1.5)
-- Run after 005_photos.sql

BEGIN;

CREATE TABLE IF NOT EXISTS standards (
    code            VARCHAR(30) PRIMARY KEY,   -- e.g. SERVICE-04
    category        VARCHAR(50) NOT NULL,      -- service | cleanliness | uniform | kitchen | bar | cashier | warehouse | grill | delivery | safety
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS standards_category_idx ON standards(category);

-- Link checklist template items to a standard (nullable — not every task maps to one).
ALTER TABLE checklist_template_items
    ADD COLUMN IF NOT EXISTS standard_code VARCHAR(30) REFERENCES standards(code);

COMMIT;
