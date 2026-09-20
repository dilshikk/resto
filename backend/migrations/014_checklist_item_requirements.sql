-- Migration 014: no-op sync marker for feature/checklist-item-requirements
-- The columns requires_photo and requires_comment were already added by
-- migration 013_photo_comment_requirements.sql which landed on main first.
-- This file is intentionally empty (idempotent) so the migration history
-- stays numbered correctly for this branch.
--
-- Both ALTER TABLE statements use ADD COLUMN IF NOT EXISTS so running this
-- on a database that already has the columns is safe.

BEGIN;

ALTER TABLE checklist_template_items
    ADD COLUMN IF NOT EXISTS requires_photo   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS requires_comment BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE checklist_items
    ADD COLUMN IF NOT EXISTS requires_photo   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS requires_comment BOOLEAN NOT NULL DEFAULT FALSE;

COMMIT;
