-- Migration 013: photo/comment confirmation requirements for checklist items
-- Run after 012_2fa_totp.sql
--
-- Adds requires_photo / requires_comment to checklist_template_items (the
-- manager-configured setting on a template step) and to checklist_items
-- (a denormalized copy taken when a checklist is created from the template,
-- so editing the template later never changes the requirements of checklists
-- already in progress — same pattern as title/description/standard_code).

BEGIN;

ALTER TABLE checklist_template_items
    ADD COLUMN IF NOT EXISTS requires_photo   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS requires_comment BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE checklist_items
    ADD COLUMN IF NOT EXISTS requires_photo   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS requires_comment BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN checklist_template_items.requires_photo IS
    'When true, employees must attach a photo before marking this step complete.';
COMMENT ON COLUMN checklist_template_items.requires_comment IS
    'When true, employees must leave a text comment before marking this step complete.';

COMMIT;
