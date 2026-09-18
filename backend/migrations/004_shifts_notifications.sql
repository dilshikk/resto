-- MADO CHECKLIST — Shifts & Notifications (v1.3)
-- Run after 003_issues.sql

BEGIN;

CREATE TABLE IF NOT EXISTS shifts (
    id                      BIGSERIAL PRIMARY KEY,
    employee_id             BIGINT NOT NULL REFERENCES employees(id),
    branch_id               BIGINT NOT NULL REFERENCES branches(id),
    shift_date              VARCHAR(10) NOT NULL,  -- YYYY-MM-DD (local calendar day)
    starts_at               VARCHAR(5)  NOT NULL,  -- HH:MM (local)
    ends_at                 VARCHAR(5)  NOT NULL,  -- HH:MM (local)
    status                  VARCHAR(20) NOT NULL DEFAULT 'planned',  -- planned | active | completed | no_show
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS shifts_employee_date_idx ON shifts(employee_id, shift_date);
CREATE INDEX IF NOT EXISTS shifts_branch_date_idx   ON shifts(branch_id, shift_date);

CREATE TABLE IF NOT EXISTS notifications (
    id                          BIGSERIAL PRIMARY KEY,
    recipient_employee_id       BIGINT NOT NULL REFERENCES employees(id),
    type                        VARCHAR(30) NOT NULL,  -- reminder | overdue | escalation | issue_assigned
    title                       VARCHAR(200) NOT NULL,
    message                     VARCHAR(500),
    is_read                     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS notifications_recipient_read_idx ON notifications(recipient_employee_id, is_read);

COMMIT;
