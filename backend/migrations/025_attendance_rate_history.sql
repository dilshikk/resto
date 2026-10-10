-- 025: история ставок сотрудников FaceID.
-- Табель берёт ставку, действовавшую в день смены, поэтому изменение ставки
-- больше не пересчитывает прошлые месяцы.
-- Таблица также создаётся автоматически при старте backend (Base.metadata.create_all).

BEGIN;

CREATE TABLE IF NOT EXISTS attendance_rate_history (
    id                 BIGSERIAL PRIMARY KEY,
    faceid_employee_id VARCHAR(64) NOT NULL,
    rate               NUMERIC(12, 2) NOT NULL,
    currency           VARCHAR(10) NOT NULL DEFAULT 'UZS',
    effective_from     DATE NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_attendance_rate_history_employee_date UNIQUE (faceid_employee_id, effective_from)
);

CREATE INDEX IF NOT EXISTS ix_attendance_rate_history_faceid_employee_id
    ON attendance_rate_history (faceid_employee_id);

-- Текущие ставки считаем действующими "с начала времён", чтобы прошлые табели не изменились.
INSERT INTO attendance_rate_history (faceid_employee_id, rate, currency, effective_from)
SELECT faceid_employee_id, rate_per_shift, currency, DATE '2000-01-01'
FROM attendance_rates
ON CONFLICT (faceid_employee_id, effective_from) DO NOTHING;

COMMIT;
