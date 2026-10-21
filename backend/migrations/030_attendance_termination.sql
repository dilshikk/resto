-- 030: статус увольнения сотрудника FaceID.
-- terminated_from - дата, с которой сотрудник уволен. NULL = активен.
-- Таблица также создаётся автоматически при старте backend (Base.metadata.create_all),
-- но новую колонку create_all не добавляет - для неё нужен этот файл.

BEGIN;

ALTER TABLE attendance_employee_profiles
    ADD COLUMN IF NOT EXISTS terminated_from DATE;

COMMIT;
