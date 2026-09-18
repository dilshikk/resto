-- MADO CHECKLIST — Checklists & Templates (v1.1)
-- Run after 001_initial_schema.sql

BEGIN;

CREATE TABLE IF NOT EXISTS checklist_templates (
    id                      BIGSERIAL PRIMARY KEY,
    name                    VARCHAR(150) NOT NULL,
    description             VARCHAR(500),
    category                VARCHAR(50) NOT NULL DEFAULT 'general',
    branch_id               BIGINT REFERENCES branches(id),
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_employee_id  BIGINT REFERENCES employees(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS checklist_template_items (
    id           BIGSERIAL PRIMARY KEY,
    template_id  BIGINT NOT NULL REFERENCES checklist_templates(id) ON DELETE CASCADE,
    title        VARCHAR(300) NOT NULL,
    description  VARCHAR(500),
    sort_order   INT NOT NULL DEFAULT 0,
    is_required  BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS checklists (
    id                      BIGSERIAL PRIMARY KEY,
    template_id             BIGINT NOT NULL REFERENCES checklist_templates(id),
    template_name           VARCHAR(150) NOT NULL,
    branch_id               BIGINT NOT NULL REFERENCES branches(id),
    shift                   VARCHAR(20) NOT NULL DEFAULT 'morning',
    date                    VARCHAR(10) NOT NULL,
    status                  VARCHAR(20) NOT NULL DEFAULT 'open',
    created_by_employee_id  BIGINT NOT NULL REFERENCES employees(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS checklists_date_idx ON checklists(date);
CREATE INDEX IF NOT EXISTS checklists_branch_date_idx ON checklists(branch_id, date);

CREATE TABLE IF NOT EXISTS checklist_items (
    id                          BIGSERIAL PRIMARY KEY,
    checklist_id                BIGINT NOT NULL REFERENCES checklists(id) ON DELETE CASCADE,
    title                       VARCHAR(300) NOT NULL,
    description                 VARCHAR(500),
    is_required                 BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order                  INT NOT NULL DEFAULT 0,
    is_completed                BOOLEAN NOT NULL DEFAULT FALSE,
    completed_by_employee_id    BIGINT REFERENCES employees(id),
    completed_at                TIMESTAMPTZ,
    note                        VARCHAR(500)
);

COMMIT;
