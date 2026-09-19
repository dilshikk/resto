-- MADO CHECKLIST — Deadline Tracking (v1.0)
-- Run after 010_revoked_tokens.sql
-- Adds deadline_offset_minutes to templates and started_at/due_at/completed_at
-- to checklists. Old rows keep NULL in all timing columns; the API returns
-- deadline_status: null for them (LEGACY behaviour, no fabricated dates).

BEGIN;

-- Template: optional deadline offset from checklist creation
ALTER TABLE checklist_templates
    ADD COLUMN IF NOT EXISTS deadline_offset_minutes INT;

COMMENT ON COLUMN checklist_templates.deadline_offset_minutes IS
    'Minutes after checklist creation until the deadline. NULL = no deadline.';

-- Checklist: timing fields
ALTER TABLE checklists
    ADD COLUMN IF NOT EXISTS started_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS due_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

COMMENT ON COLUMN checklists.started_at   IS 'When the checklist was created/started (UTC).';
COMMENT ON COLUMN checklists.due_at       IS 'Deadline timestamp (UTC). NULL if template had no deadline.';
COMMENT ON COLUMN checklists.completed_at IS 'When status was set to completed (UTC).';

-- Index for overdue-dashboard and analytics queries
CREATE INDEX IF NOT EXISTS checklists_due_at_idx
    ON checklists(due_at)
    WHERE due_at IS NOT NULL;

COMMIT;
