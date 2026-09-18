-- MADO CHECKLIST — Photo confirmations for checklist items (v1.4)
-- Run after 004_shifts_notifications.sql

BEGIN;

CREATE TABLE IF NOT EXISTS photos (
    id                      BIGSERIAL PRIMARY KEY,
    checklist_item_id       BIGINT NOT NULL REFERENCES checklist_items(id) ON DELETE CASCADE,
    uploaded_by_employee_id BIGINT NOT NULL REFERENCES employees(id),
    url                     VARCHAR(300) NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS photos_checklist_item_idx ON photos(checklist_item_id);

COMMIT;
