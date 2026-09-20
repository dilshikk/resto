-- Migration 013: photo and comment confirmation requirements on checklist items
-- Run after 012_2fa_totp.sql
--
-- requires_photo:   when TRUE the employee must upload at least one photo
--                   before the item can be marked as completed.
-- requires_comment: when TRUE the employee must supply a non-empty note/comment
--                   before the item can be marked as completed.
--
-- Both columns are added to checklist_template_items (config source) and
-- checklist_items (denormalised runtime copy, same pattern as standard_code).

BEGIN;

-- Template item config
ALTER TABLE checklist_template_items
    ADD COLUMN IF NOT EXISTS requires_photo   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS requires_comment BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN checklist_template_items.requires_photo IS
    'When TRUE the employee must upload at least one photo to complete this item.';
COMMENT ON COLUMN checklist_template_items.requires_comment IS
    'When TRUE the employee must provide a non-empty note/comment to complete this item.';

-- Runtime item (denormalised copy so historical checklists keep their settings)
ALTER TABLE checklist_items
    ADD COLUMN IF NOT EXISTS requires_photo   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS requires_comment BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN checklist_items.requires_photo IS
    'Denormalised from checklist_template_items.requires_photo at checklist creation time.';
COMMENT ON COLUMN checklist_items.requires_comment IS
    'Denormalised from checklist_template_items.requires_comment at checklist creation time.';

COMMIT;
