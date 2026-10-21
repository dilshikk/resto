-- 029: сопоставление зашифрованных ID (хешей), которые терминал шлёт при проходе
-- по карте, с обычным employee_id FaceID. Таблицы также создаются автоматически
-- при старте backend (Base.metadata.create_all); этот файл - для ручного
-- применения и как документация схемы.

BEGIN;

CREATE TABLE IF NOT EXISTS attendance_card_mappings (
    id                 BIGSERIAL PRIMARY KEY,
    hashed_id          VARCHAR(128) NOT NULL UNIQUE,
    faceid_employee_id VARCHAR(64) NOT NULL,
    note               VARCHAR(255),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_attendance_card_mappings_employee
    ON attendance_card_mappings (faceid_employee_id);

COMMIT;
