-- MADO CHECKLIST — Initial schema (v1.0)
-- PostgreSQL 16+

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS branches (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    address     VARCHAR(255),
    city        VARCHAR(100),
    timezone    VARCHAR(50) NOT NULL DEFAULT 'Asia/Tashkent',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roles (
    id                SERIAL PRIMARY KEY,
    code              VARCHAR(50) UNIQUE NOT NULL,
    name_ru           VARCHAR(100) NOT NULL,
    name_uz           VARCHAR(100),
    name_en           VARCHAR(100),
    name_tr           VARCHAR(100),
    category          VARCHAR(20) NOT NULL CHECK (category IN ('staff', 'management')),
    permission_level  SMALLINT NOT NULL DEFAULT 0
);

INSERT INTO roles (code, name_ru, category, permission_level) VALUES
    ('waiter',          'Официант',          'staff',      0),
    ('runner',          'Раннер',            'staff',      0),
    ('hostess',         'Хостес',            'staff',      0),
    ('bartender',       'Бармен',            'staff',      0),
    ('cashier',         'Кассир',            'staff',      0),
    ('cook',            'Повар',             'staff',      0),
    ('confectioner',    'Кондитер',          'staff',      0),
    ('cleaner',         'Уборщик',           'staff',      0),
    ('manager',         'Менеджер',          'management', 1),
    ('senior_manager',  'Старший менеджер',  'management', 1),
    ('supervisor',      'Управляющий',       'management', 2),
    ('director',        'Директор',          'management', 3)
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS users (
    id               BIGSERIAL PRIMARY KEY,
    email            VARCHAR(150) UNIQUE NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,
    is_2fa_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at    TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS employees (
    id                    BIGSERIAL PRIMARY KEY,
    full_name             VARCHAR(150) NOT NULL,
    phone                 VARCHAR(30),
    role_id               INT NOT NULL REFERENCES roles(id),
    status                VARCHAR(20) NOT NULL DEFAULT 'active',
    invite_code           VARCHAR(8) NOT NULL,
    primary_branch_id     BIGINT NOT NULL REFERENCES branches(id),
    additional_branch_ids INT[] NOT NULL DEFAULT '{}',
    hired_at              VARCHAR(10),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS employee_accounts (
    id           BIGSERIAL PRIMARY KEY,
    employee_id  BIGINT NOT NULL UNIQUE REFERENCES employees(id) ON DELETE CASCADE,
    user_id      BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE
);

COMMIT;
