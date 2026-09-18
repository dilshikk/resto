-- MADO CHECKLIST — Audit log (v1.6)
-- Run after 006_standards.sql

BEGIN;

CREATE TABLE IF NOT EXISTS audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    actor_id        BIGINT REFERENCES employees(id),  -- NULL = system/scheduler action
    action          VARCHAR(100) NOT NULL,             -- e.g. task.completed, template.updated
    entity_type     VARCHAR(50) NOT NULL,
    entity_id       BIGINT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_logs_entity_idx  ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS audit_logs_actor_idx   ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS audit_logs_created_idx ON audit_logs(created_at);

COMMIT;
