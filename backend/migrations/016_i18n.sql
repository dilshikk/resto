-- Migration 016: i18n support for bot and checklist items
--
-- Changes:
--   1. Add preferred_language to employees (ru | uz | en, default ru)
--   2. Drop name_tr from roles (keep name_ru, name_uz, name_en)
--   3. Add title_uz, title_en, description_uz, description_en
--      to checklist_template_items and checklist_items

-- 1. Employee preferred language
ALTER TABLE employees
    ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(5) NOT NULL DEFAULT 'ru';

-- 2. Remove Turkish name from roles
ALTER TABLE roles DROP COLUMN IF EXISTS name_tr;

-- 3. i18n columns for template items
ALTER TABLE checklist_template_items
    ADD COLUMN IF NOT EXISTS title_uz        VARCHAR(300),
    ADD COLUMN IF NOT EXISTS title_en        VARCHAR(300),
    ADD COLUMN IF NOT EXISTS description_uz  VARCHAR(500),
    ADD COLUMN IF NOT EXISTS description_en  VARCHAR(500);

-- 4. i18n columns for checklist items (denormalized from template at creation)
ALTER TABLE checklist_items
    ADD COLUMN IF NOT EXISTS title_uz        VARCHAR(300),
    ADD COLUMN IF NOT EXISTS title_en        VARCHAR(300),
    ADD COLUMN IF NOT EXISTS description_uz  VARCHAR(500),
    ADD COLUMN IF NOT EXISTS description_en  VARCHAR(500);
