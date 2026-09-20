-- Migration 014: no-op sync marker
-- The columns requires_photo and requires_comment were already added by
-- migration 013_photo_comment_requirements.sql.
-- This file is idempotent (ADD COLUMN IF NOT EXISTS) and safe to re-run.

BEGIN;

ALTER TABLE checklist_template_items
    ADD COLUMN IF NOT EXISTS requires_photo   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS requires_comment BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE checklist_items
    ADD COLUMN IF NOT EXISTS requires_photo   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS requires_comment BOOLEAN NOT NULL DEFAULT FALSE;

COMMIT;
