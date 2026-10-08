-- 024: табель и расчёт зарплаты по данным FaceID
-- Таблицы также создаются автоматически при старте backend (Base.metadata.create_all),
-- этот файл нужен для ручного применения и как документация схемы.

BEGIN;

-- Ручные правки прихода/ухода. Ключ: сотрудник FaceID + дата начала смены.
-- NULL в arrival/departure означает "берём время из FaceID".
CREATE TABLE IF NOT EXISTS attendance_punch_overrides (
    id                 BIGSERIAL PRIMARY KEY,
    faceid_employee_id VARCHAR(64) NOT NULL,
    shift_date         DATE NOT NULL,
    arrival            VARCHAR(5),
    departure          VARCHAR(5),
    note               VARCHAR(255),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_attendance_punch_employee_date UNIQUE (faceid_employee_id, shift_date)
);

CREATE INDEX IF NOT EXISTS ix_attendance_punch_overrides_shift_date
    ON attendance_punch_overrides (shift_date);

-- Ручные начисления/удержания за произвольный период.
CREATE TABLE IF NOT EXISTS attendance_payroll_adjustments (
    id                 BIGSERIAL PRIMARY KEY,
    faceid_employee_id VARCHAR(64) NOT NULL,
    date_from          DATE NOT NULL,
    date_to            DATE NOT NULL,
    bonus              NUMERIC(12, 2) NOT NULL DEFAULT 0,
    fine               NUMERIC(12, 2) NOT NULL DEFAULT 0,
    posuda             NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_attendance_adjustment_employee_period UNIQUE (faceid_employee_id, date_from, date_to)
);

-- Должность сотрудника для табеля.
CREATE TABLE IF NOT EXISTS attendance_employee_profiles (
    id                 BIGSERIAL PRIMARY KEY,
    faceid_employee_id VARCHAR(64) NOT NULL UNIQUE,
    position           VARCHAR(100),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
