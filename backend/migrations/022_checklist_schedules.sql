-- 022: checklist schedules.
-- A schedule says: "create checklist from template T for branch B every
-- selected weekday between start_date and end_date, open from window_start
-- to window_end (branch local time)". Safe to run multiple times.

BEGIN;

CREATE TABLE IF NOT EXISTS checklist_schedules (
    id BIGSERIAL PRIMARY KEY,
    template_id BIGINT NOT NULL REFERENCES checklist_templates(id) ON DELETE CASCADE,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    shift VARCHAR(20) NOT NULL DEFAULT 'morning',
    start_date DATE NOT NULL,
    end_date DATE,
    weekdays INTEGER[] NOT NULL DEFAULT '{1,2,3,4,5,6,7}',
    window_start TIME NOT NULL,
    window_end TIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_employee_id BIGINT REFERENCES employees(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_checklist_schedules_branch_id ON checklist_schedules(branch_id);

ALTER TABLE checklists ADD COLUMN IF NOT EXISTS schedule_id BIGINT REFERENCES checklist_schedules(id) ON DELETE SET NULL;
ALTER TABLE checklists ADD COLUMN IF NOT EXISTS opens_at TIMESTAMPTZ;
ALTER TABLE checklists ADD COLUMN IF NOT EXISTS open_notified_at TIMESTAMPTZ;
ALTER TABLE checklists ADD COLUMN IF NOT EXISTS reminder_notified_at TIMESTAMPTZ;

-- One checklist per schedule per day (idempotent generation).
CREATE UNIQUE INDEX IF NOT EXISTS uq_checklists_schedule_date
    ON checklists(schedule_id, date) WHERE schedule_id IS NOT NULL;

COMMIT;
