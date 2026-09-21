-- Migration 017 — task_type column for checklist items
--
-- Supported task types:
--   checkbox    (default) — employee ticks the item as done (existing behaviour)
--   number      — employee enters a numeric value (e.g. guest count, weight)
--   temperature — employee enters a numeric temperature value (°C)
--   text        — employee types a free-text answer
--   photo       — employee must attach a photo to complete the item
--   photo_geo   — employee must attach a photo with GPS coordinates
--   yes_no      — employee picks Да / Нет (Yes / No)
--
-- Backward-compatible: all existing rows default to 'checkbox'.

ALTER TABLE checklist_template_items
    ADD COLUMN IF NOT EXISTS task_type VARCHAR(20) NOT NULL DEFAULT 'checkbox';

ALTER TABLE checklist_items
    ADD COLUMN IF NOT EXISTS task_type VARCHAR(20) NOT NULL DEFAULT 'checkbox';

-- Add CHECK constraints idempotently (Postgres does not have IF NOT EXISTS for
-- constraints, so we check pg_constraint first).

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_template_item_task_type'
          AND conrelid = 'checklist_template_items'::regclass
    ) THEN
        ALTER TABLE checklist_template_items
            ADD CONSTRAINT chk_template_item_task_type
            CHECK (task_type IN ('checkbox','number','temperature','text','photo','photo_geo','yes_no'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_checklist_item_task_type'
          AND conrelid = 'checklist_items'::regclass
    ) THEN
        ALTER TABLE checklist_items
            ADD CONSTRAINT chk_checklist_item_task_type
            CHECK (task_type IN ('checkbox','number','temperature','text','photo','photo_geo','yes_no'));
    END IF;
END $$;
