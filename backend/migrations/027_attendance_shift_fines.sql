-- 027: ручные штрафы за смену (опоздание, невыход).
-- Таблица также создаётся автоматически при старте backend (Base.metadata.create_all).

BEGIN;

CREATE TABLE IF NOT EXISTS attendance_shift_fines (
    id                 BIGSERIAL PRIMARY KEY,
    faceid_employee_id VARCHAR(64) NOT NULL,
    shift_date         DATE NOT NULL,
    kind               VARCHAR(16) NOT NULL,
    amount             NUMERIC(12, 2) NOT NULL DEFAULT 0,
    planned_start      VARCHAR(5),
    late_minutes       INTEGER,
    note               VARCHAR(255),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_attendance_shift_fine_employee_date_kind UNIQUE (faceid_employee_id, shift_date, kind)
);

CREATE INDEX IF NOT EXISTS ix_attendance_shift_fines_shift_date ON attendance_shift_fines (shift_date);

COMMIT;
