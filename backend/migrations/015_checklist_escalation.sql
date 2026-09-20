-- Migration 015: Add escalation tracking columns to checklists
--
-- These two columns are set by the overdue_escalation background task
-- to record when each notification wave was dispatched for an overdue
-- checklist.  NULL means the wave has not been sent yet.
--
-- Escalation chain (configurable via env vars):
--   due_at + OVERDUE_MANAGER_NOTIFY_MINUTES (default 10 min)
--     → managers (permission_level == 1) notified, type=checklist_overdue
--   due_at + OVERDUE_SUPERVISOR_NOTIFY_MINUTES (default 30 min)
--     → supervisors/directors (permission_level >= 2) escalated,
--       type=checklist_escalation

ALTER TABLE checklists
    ADD COLUMN IF NOT EXISTS overdue_manager_notified_at    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS overdue_supervisor_notified_at TIMESTAMPTZ;

COMMENT ON COLUMN checklists.overdue_manager_notified_at IS
    'Timestamp when the first escalation wave (manager, permission_level==1) '
    'notification was dispatched for this overdue checklist. '
    'NULL = not yet sent.';

COMMENT ON COLUMN checklists.overdue_supervisor_notified_at IS
    'Timestamp when the second escalation wave (supervisor/director, permission_level>=2) '
    'notification was dispatched for this overdue checklist. '
    'NULL = not yet sent.';
