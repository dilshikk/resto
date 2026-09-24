-- Migration 008: add is_skipped to checklist_items for step-by-step flow
-- is_skipped can only be true when is_required = false.
-- Required items must always be completed before moving to the next step.
--
-- Idempotent: safe to run several times and on existing databases.

ALTER TABLE checklist_items
    ADD COLUMN IF NOT EXISTS is_skipped BOOLEAN NOT NULL DEFAULT FALSE;

-- Constraint: a required item must never be skipped.
-- Postgres has no ADD CONSTRAINT IF NOT EXISTS, so check pg_constraint first.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_required_not_skipped'
          AND conrelid = 'checklist_items'::regclass
    ) THEN
        ALTER TABLE checklist_items
            ADD CONSTRAINT chk_required_not_skipped
            CHECK (NOT (is_required = TRUE AND is_skipped = TRUE));
    END IF;
END $$;
