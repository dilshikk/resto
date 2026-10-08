-- 023: таблица ставок сотрудников FaceID (зарплата за смену)
-- Хранит ставку за смену для каждого employee_id из системы FaceID.
-- employee_id — это строковый ID из таблицы access_logs.faceid_db.

BEGIN;

CREATE TABLE IF NOT EXISTS attendance_rates (
    id           BIGSERIAL PRIMARY KEY,
    -- ID сотрудника в системе FaceID (из access_logs.employee_id)
    faceid_employee_id   VARCHAR(64) NOT NULL UNIQUE,
    -- Имя сотрудника для отображения (синхронизируется вручную)
    display_name         VARCHAR(150),
    -- Ставка за одну смену (в любой валюте — просто число)
    rate_per_shift       NUMERIC(12, 2) NOT NULL DEFAULT 0,
    -- Валюта (UZS, USD и т.д.)
    currency             VARCHAR(10) NOT NULL DEFAULT 'UZS',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
