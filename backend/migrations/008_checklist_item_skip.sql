-- Migration 008: add is_skipped to checklist_items for step-by-step flow
-- is_skipped can only be true when is_required = false.
-- Required items must always be completed before moving to the next step.

ALTER TABLE checklist_items
    ADD COLUMN IF NOT EXISTS is_skipped BOOLEAN NOT NULL DEFAULT FALSE;

-- Constraint: a required item must never be skipped
ALTER TABLE checklist_items
    ADD CONSTRAINT chk_required_not_skipped
    CHECK (NOT (is_required = TRUE AND is_skipped = TRUE));
