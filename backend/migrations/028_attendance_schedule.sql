-- 028: график смен в табеле.
-- 1) attendance_planned_shifts - плановое время прихода/ухода, заданное прямо в табеле
--    (Shift+клик по ячейке). Строка с пустыми planned_start и planned_end = выходной.
-- 2) attendance_employee_profiles.employee_id - привязка сотрудника FaceID к сотруднику
--    системы, чтобы брать план из раздела «Смены» (таблица shifts).
-- Таблица также создаётся автоматически при старте backend (Base.metadata.create_all),
-- но новую колонку create_all не добавляет - для неё нужен этот файл.

BEGIN;

CREATE TABLE IF NOT EXISTS attendance_planned_shifts (
    id                 BIGSERIAL PRIMARY KEY,
    faceid_employee_id VARCHAR(64) NOT NULL,
    shift_date         DATE NOT NULL,
    planned_start      VARCHAR(5),
    planned_end        VARCHAR(5),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_attendance_plan_employee_date UNIQUE (faceid_employee_id, shift_date)
);

CREATE INDEX IF NOT EXISTS ix_attendance_planned_shifts_shift_date
    ON attendance_planned_shifts (shift_date);

ALTER TABLE attendance_employee_profiles
    ADD COLUMN IF NOT EXISTS employee_id BIGINT REFERENCES employees(id) ON DELETE SET NULL;

-- Один сотрудник системы - не больше одного человека в FaceID
CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_profiles_employee_id
    ON attendance_employee_profiles (employee_id)
    WHERE employee_id IS NOT NULL;

COMMIT;
