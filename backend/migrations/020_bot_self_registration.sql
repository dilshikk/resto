-- Migration 020: self-service Telegram registration for employees
--
-- Adds support for employees who register themselves via the Telegram bot
-- (pressing /start with no invite code and sharing their contact) instead
-- of being created by a manager first. Such employees start in status
-- 'pending' with no role or branch assigned yet; a manager reviews the
-- request in the "Сотрудники" screen and either confirms it (assigning a
-- restaurant + position, moving the employee to 'active') or rejects it
-- (the pending record is deleted, see POST /employees/{id}/reject).
--
-- Status values after this migration: active | inactive | fired | pending | blocked | archived
-- ('inactive' and 'fired' are kept for backward compatibility with existing
--  rows created by older code; new manual actions from the web panel use
--  'blocked' and 'archived' instead.)
--
-- Idempotent: safe to run multiple times and on existing databases.

BEGIN;

-- Self-registered employees have no role/branch/invite code until a
-- manager approves them, so these columns can no longer be NOT NULL.
ALTER TABLE employees ALTER COLUMN role_id DROP NOT NULL;
ALTER TABLE employees ALTER COLUMN primary_branch_id DROP NOT NULL;
ALTER TABLE employees ALTER COLUMN invite_code DROP NOT NULL;

-- Telegram username captured at self-registration time (display only, not
-- used for authentication — telegram_id remains the source of truth).
ALTER TABLE employees ADD COLUMN IF NOT EXISTS telegram_username VARCHAR(64);

-- Last time the employee interacted with the bot (toggled/skipped a
-- checklist item, uploaded a photo, etc). Updated opportunistically.
ALTER TABLE employees ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ;

COMMIT;
