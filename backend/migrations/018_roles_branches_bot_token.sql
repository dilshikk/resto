-- Migration 018: columns referenced by the models but never created
--
--   1. roles.can_access_all_branches  — branch visibility flag (see app/models/role.py)
--   2. employees.bot_session_token_hash — hashed per-employee bot token (see app/models/employee.py)
--   3. allow task_type 'problem' (employee reports an issue from the bot)
--
-- Idempotent: safe to run several times and on existing databases.

-- 1. Branch visibility per role
ALTER TABLE roles
    ADD COLUMN IF NOT EXISTS can_access_all_branches BOOLEAN NOT NULL DEFAULT FALSE;

-- Supervisor and director see all branches (same as the old permission_level >= 2 rule)
UPDATE roles
SET can_access_all_branches = TRUE
WHERE permission_level >= 2 AND can_access_all_branches = FALSE;

-- 2. Per-employee bot session token (sha256 hex = 64 chars)
ALTER TABLE employees
    ADD COLUMN IF NOT EXISTS bot_session_token_hash VARCHAR(64);

CREATE UNIQUE INDEX IF NOT EXISTS ix_employees_bot_session_token_hash
    ON employees (bot_session_token_hash);

-- 3. Extend task_type constraints with 'problem'
ALTER TABLE checklist_template_items DROP CONSTRAINT IF EXISTS chk_template_item_task_type;
ALTER TABLE checklist_template_items
    ADD CONSTRAINT chk_template_item_task_type
    CHECK (task_type IN ('checkbox','number','temperature','text','photo','photo_geo','yes_no','problem'));

ALTER TABLE checklist_items DROP CONSTRAINT IF EXISTS chk_checklist_item_task_type;
ALTER TABLE checklist_items
    ADD CONSTRAINT chk_checklist_item_task_type
    CHECK (task_type IN ('checkbox','number','temperature','text','photo','photo_geo','yes_no','problem'));
