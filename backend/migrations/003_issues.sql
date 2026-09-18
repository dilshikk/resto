-- MADO CHECKLIST — Issues & Comments (v1.2)
-- Run after 002_checklists.sql

BEGIN;

CREATE TABLE IF NOT EXISTS issues (
    id                          BIGSERIAL PRIMARY KEY,
    title                       VARCHAR(200) NOT NULL,
    description                 TEXT,
    branch_id                   BIGINT NOT NULL REFERENCES branches(id),
    checklist_id                BIGINT REFERENCES checklists(id),
    category                    VARCHAR(50) NOT NULL DEFAULT 'general',
    priority                    VARCHAR(20) NOT NULL DEFAULT 'medium',
    status                      VARCHAR(20) NOT NULL DEFAULT 'open',
    photo_urls                  TEXT[] NOT NULL DEFAULT '{}',
    reported_by_employee_id     BIGINT NOT NULL REFERENCES employees(id),
    assigned_to_employee_id     BIGINT REFERENCES employees(id),
    resolved_at                 TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS issues_status_idx    ON issues(status);
CREATE INDEX IF NOT EXISTS issues_branch_idx    ON issues(branch_id);
CREATE INDEX IF NOT EXISTS issues_priority_idx  ON issues(priority);

CREATE TABLE IF NOT EXISTS issue_comments (
    id                      BIGSERIAL PRIMARY KEY,
    issue_id                BIGINT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    author_employee_id      BIGINT NOT NULL REFERENCES employees(id),
    text                    TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
