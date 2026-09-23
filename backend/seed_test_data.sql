-- =============================================================================
-- MADO CHECKLIST — Test / demo seed data
-- =============================================================================
--
-- Purpose: fill a freshly migrated database with realistic example data so the
-- whole project (web panel + Telegram bot data model) can be tested end to
-- end: branches, all 12 positions/roles, employees, MADO standards, checklist
-- templates (opening + closing "examples/variants" for every position),
-- generated checklists for "today" in different states (completed, overdue,
-- in progress), photos, issues, shifts and notifications.
--
-- HOW TO USE
--   1. Apply the schema migrations first (001_initial_schema.sql through
--      019_template_role_ids.sql) — e.g. on a fresh `docker compose up`
--      they run automatically from backend/migrations/.
--   2. Run this file on that SAME fresh database, before creating any real
--      branches/employees, e.g.:
--        docker compose exec -T db psql -U mado -d mado_checklist \
--          < backend/seed_test_data.sql
--   3. Log in to the web panel with any of the test accounts below.
--      Password for ALL web accounts: Test1234!
--        alina.manager@mado.uz      — менеджер, Tashkent City Mall
--        ruslan.manager@mado.uz     — менеджер, Park in Mall
--        sevara.senior@mado.uz      — старший менеджер (оба филиала)
--        umid.supervisor@mado.uz    — управляющий (все филиалы)
--        dilshod.director@mado.uz   — директор (все филиалы)
--   Staff (waiter, cook, bartender, ...) log in only via the Telegram bot in
--   this project, so they have no password — they are seeded with a fake
--   `telegram_id` to simulate an already-linked bot account.
--
-- NOT idempotent by design: it assumes an empty branches/employees/checklists
-- state. Re-running it on a database that already has this seed will create
-- duplicate rows. Load it on a disposable test database.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. Branches
-- -----------------------------------------------------------------------------

INSERT INTO branches (name, address, city, timezone, is_active) VALUES
    ('Tashkent City Mall', 'ул. Амира Темура, 107Б', 'Ташкент', 'Asia/Tashkent', TRUE),
    ('Park in Mall',       'Мирзо-Улугбекский р-н, массив Боз-Су', 'Ташкент', 'Asia/Tashkent', TRUE);

-- -----------------------------------------------------------------------------
-- 2. MADO Standards (referenced by checklist items below)
-- -----------------------------------------------------------------------------

INSERT INTO standards (code, category, title, description, is_active) VALUES
    ('SERVICE-01',   'service',     'Приветствие гостя в течение 1 минуты', 'Сотрудник зала подходит к гостю и приветствует его не позднее 60 секунд после посадки.', TRUE),
    ('SERVICE-04',   'service',     'Передача заказа гостю только после проверки чека', 'Официант проверяет соответствие блюд чеку перед подачей гостю.', TRUE),
    ('CLEAN-01',     'cleanliness', 'Столы протёрты и продезинфицированы', 'Все поверхности столов чистые, без крошек и пятен, обработаны дезинфицирующим средством.', TRUE),
    ('CLEAN-02',     'cleanliness', 'Туалетные комнаты проверяются каждый час', 'Наличие мыла, бумаги, чистота раковин и полов фиксируется ежечасно.', TRUE),
    ('UNIFORM-01',   'uniform',     'Форма чистая и опрятная, бейдж на месте', 'Униформа без пятен и заломов, бейдж с именем закреплён на видном месте.', TRUE),
    ('KITCHEN-01',   'kitchen',     'Температура холодильников в норме (+2..+6°C)', 'Температура во всех холодильных установках кухни/бара проверяется и фиксируется.', TRUE),
    ('KITCHEN-02',   'kitchen',     'Сроки годности продуктов проверены', 'Все продукты подписаны датой открытия/приготовления, просроченные позиции утилизированы.', TRUE),
    ('BAR-01',       'bar',         'Чистота барной стойки и инвентаря', 'Барная стойка, шейкеры, джиггеры и разделочные доски чистые и разложены по местам.', TRUE),
    ('CASHIER-01',   'cashier',     'Сверка кассы в начале и в конце смены', 'Наличность в кассе сверяется с системным отчётом при открытии и закрытии смены.', TRUE),
    ('CASHIER-02',   'cashier',     'Чек выдан гостю при оплате', 'Каждому гостю после оплаты выдаётся фискальный чек.', TRUE),
    ('WAREHOUSE-01', 'warehouse',   'Складские остатки соответствуют накладным', 'Фактическое количество товара на складе соответствует данным в системе учёта.', TRUE),
    ('GRILL-01',     'grill',       'Мангал/гриль очищен и подготовлен', 'Рабочая поверхность мангала очищена от нагара, угли/газ подготовлены к смене.', TRUE),
    ('DELIVERY-01',  'delivery',    'Упаковка доставки герметична и подписана', 'Заказы на доставку упакованы без протечек и подписаны номером заказа.', TRUE),
    ('SAFETY-01',    'safety',      'Огнетушители на месте и не просрочены', 'Огнетушители присутствуют на всех точках, срок годности не истёк.', TRUE);

-- -----------------------------------------------------------------------------
-- 3. Employees (all 12 positions, 2 branches) + web users for management
-- -----------------------------------------------------------------------------
-- Password for every web account created below: Test1234!
-- pgcrypto's crypt()/gen_salt('bf') produces a real bcrypt hash compatible
-- with the backend's passlib[bcrypt] verification.

INSERT INTO users (email, password_hash) VALUES
    ('alina.manager@mado.uz',    crypt('Test1234!', gen_salt('bf'))),
    ('ruslan.manager@mado.uz',   crypt('Test1234!', gen_salt('bf'))),
    ('sevara.senior@mado.uz',    crypt('Test1234!', gen_salt('bf'))),
    ('umid.supervisor@mado.uz',  crypt('Test1234!', gen_salt('bf'))),
    ('dilshod.director@mado.uz', crypt('Test1234!', gen_salt('bf')));

-- Staff (Telegram-only, no web login). telegram_id values are fake but unique,
-- simulating an already-linked bot account so the UI shows "Привязан".
INSERT INTO employees (full_name, phone, role_id, status, invite_code, primary_branch_id, additional_branch_ids, hired_at, preferred_language, telegram_id) VALUES
    ('Иван Соколов',       '+998 90 111 11 01', (SELECT id FROM roles WHERE code = 'waiter'),       'active', 'WTR001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), '{}', '2025-02-10', 'ru', 500000101),
    ('Дилноза Юсупова',    '+998 90 111 11 02', (SELECT id FROM roles WHERE code = 'waiter'),       'active', 'WTR002PM', (SELECT id FROM branches WHERE name = 'Park in Mall'),       '{}', '2025-03-05', 'uz', 500000102),
    ('Тимур Ахмедов',      '+998 90 111 11 03', (SELECT id FROM roles WHERE code = 'runner'),       'active', 'RUN001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), '{}', '2025-04-01', 'ru', 500000103),
    ('Сардор Каримов',     '+998 90 111 11 04', (SELECT id FROM roles WHERE code = 'runner'),       'active', 'RUN002PM', (SELECT id FROM branches WHERE name = 'Park in Mall'),       '{}', '2025-04-12', 'ru', 500000104),
    ('Мадина Рахимова',    '+998 90 111 11 05', (SELECT id FROM roles WHERE code = 'hostess'),      'active', 'HST001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), '{}', '2025-01-20', 'ru', 500000105),
    ('Зарина Тошева',      '+998 90 111 11 06', (SELECT id FROM roles WHERE code = 'hostess'),      'active', 'HST002PM', (SELECT id FROM branches WHERE name = 'Park in Mall'),       '{}', '2025-05-15', 'ru', 500000106),
    ('Бекзод Назаров',     '+998 90 111 11 07', (SELECT id FROM roles WHERE code = 'bartender'),    'active', 'BAR001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), '{}', '2025-02-01', 'ru', 500000107),
    ('Отабек Юлдашев',     '+998 90 111 11 08', (SELECT id FROM roles WHERE code = 'bartender'),    'active', 'BAR002PM', (SELECT id FROM branches WHERE name = 'Park in Mall'),       '{}', '2025-06-01', 'ru', 500000108),
    ('Нилуфар Абдуллаева', '+998 90 111 11 09', (SELECT id FROM roles WHERE code = 'cashier'),      'active', 'CSH001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), '{}', '2025-03-20', 'ru', 500000109),
    ('Камила Исмаилова',   '+998 90 111 11 10', (SELECT id FROM roles WHERE code = 'cashier'),      'active', 'CSH002PM', (SELECT id FROM branches WHERE name = 'Park in Mall'),       '{}', '2025-07-01', 'en', 500000110),
    ('Фарход Расулов',     '+998 90 111 11 11', (SELECT id FROM roles WHERE code = 'cook'),         'active', 'COK001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), '{}', '2024-11-01', 'ru', 500000111),
    ('Жасур Эргашев',      '+998 90 111 11 12', (SELECT id FROM roles WHERE code = 'cook'),         'active', 'COK002PM', (SELECT id FROM branches WHERE name = 'Park in Mall'),       '{}', '2025-01-10', 'ru', 500000112),
    ('Гулноза Мирзаева',   '+998 90 111 11 13', (SELECT id FROM roles WHERE code = 'confectioner'), 'active', 'CNF001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), '{}', '2025-02-15', 'ru', 500000113),
    ('Азиз Турсунов',      '+998 90 111 11 14', (SELECT id FROM roles WHERE code = 'cleaner'),      'active', 'CLN001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), '{}', '2025-01-05', 'ru', 500000114),
    ('Шахзод Юлчиев',      '+998 90 111 11 15', (SELECT id FROM roles WHERE code = 'cleaner'),      'active', 'CLN002PM', (SELECT id FROM branches WHERE name = 'Park in Mall'),       '{}', '2025-04-20', 'ru', 500000115),
    -- Extra staff kept for status filter testing (fired / inactive) — not used in checklists below.
    ('Отабек Собиров',     '+998 90 111 11 16', (SELECT id FROM roles WHERE code = 'waiter'),       'fired',    'WTR003TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), '{}', '2024-08-01', 'ru', 500000116),
    ('Наргиза Ахмедова',   '+998 90 111 11 17', (SELECT id FROM roles WHERE code = 'cashier'),      'inactive', 'CSH003PM', (SELECT id FROM branches WHERE name = 'Park in Mall'),       '{}', '2024-09-15', 'ru', 500000117);

-- Management (web login via employee_accounts + users, no telegram_id).
INSERT INTO employees (full_name, phone, role_id, status, invite_code, primary_branch_id, additional_branch_ids, hired_at, preferred_language) VALUES
    ('Алина Каримова',   '+998 90 222 22 01', (SELECT id FROM roles WHERE code = 'manager'),        'active', 'MGR001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), '{}', '2024-06-01', 'ru'),
    ('Руслан Пулатов',   '+998 90 222 22 02', (SELECT id FROM roles WHERE code = 'manager'),        'active', 'MGR002PM', (SELECT id FROM branches WHERE name = 'Park in Mall'),       '{}', '2024-07-01', 'ru'),
    ('Севара Ахунова',   '+998 90 222 22 03', (SELECT id FROM roles WHERE code = 'senior_manager'), 'active', 'SRM001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'),
        ARRAY[(SELECT id FROM branches WHERE name = 'Park in Mall')::int], '2023-09-01', 'ru'),
    ('Умид Назиров',     '+998 90 222 22 04', (SELECT id FROM roles WHERE code = 'supervisor'),     'active', 'SUP001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'),
        ARRAY[(SELECT id FROM branches WHERE name = 'Park in Mall')::int], '2022-05-01', 'ru'),
    ('Дилшод Каримов',   '+998 90 222 22 05', (SELECT id FROM roles WHERE code = 'director'),       'active', 'DIR001TC', (SELECT id FROM branches WHERE name = 'Tashkent City Mall'),
        ARRAY[(SELECT id FROM branches WHERE name = 'Park in Mall')::int], '2021-01-15', 'ru');

INSERT INTO employee_accounts (employee_id, user_id) VALUES
    ((SELECT id FROM employees WHERE full_name = 'Алина Каримова'), (SELECT id FROM users WHERE email = 'alina.manager@mado.uz')),
    ((SELECT id FROM employees WHERE full_name = 'Руслан Пулатов'), (SELECT id FROM users WHERE email = 'ruslan.manager@mado.uz')),
    ((SELECT id FROM employees WHERE full_name = 'Севара Ахунова'), (SELECT id FROM users WHERE email = 'sevara.senior@mado.uz')),
    ((SELECT id FROM employees WHERE full_name = 'Умид Назиров'),   (SELECT id FROM users WHERE email = 'umid.supervisor@mado.uz')),
    ((SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), (SELECT id FROM users WHERE email = 'dilshod.director@mado.uz'));

-- -----------------------------------------------------------------------------
-- 4. Checklist templates — "Открытие" и "Закрытие" для КАЖДОЙ из 12 должностей
-- -----------------------------------------------------------------------------
-- branch_id = NULL => template applies to every branch (general).
-- role_ids restricts the template to a single position (mirrors migration 019).
-- created_by_employee_id = director (Дилшод Каримов) for all seed templates.

-- 4.1 Waiter (Официант)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Официант: Открытие', 'Чек-лист открытия смены для официанта', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 60,
        ARRAY[(SELECT id FROM roles WHERE code = 'waiter')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Проверить форму и бейдж', NULL, TRUE, 'UNIFORM-01', FALSE, FALSE, 'checkbox'),
    (2, 'Проверить чистоту стола и сервировку', NULL, TRUE, 'CLEAN-01', FALSE, FALSE, 'checkbox'),
    (3, 'Стоп-лист актуален?', NULL, TRUE, NULL, FALSE, FALSE, 'yes_no'),
    (4, 'Общее фото рабочей зоны', NULL, TRUE, NULL, TRUE, FALSE, 'photo')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Официант: Закрытие', 'Чек-лист закрытия смены для официанта', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 90,
        ARRAY[(SELECT id FROM roles WHERE code = 'waiter')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Все столы убраны и продезинфицированы', NULL, TRUE, 'CLEAN-01', FALSE, FALSE, 'checkbox'),
    (2, 'Количество столов, оставшихся неубранными', NULL, TRUE, NULL, FALSE, FALSE, 'number'),
    (3, 'Есть незакрытые проблемы с гостями?', NULL, TRUE, NULL, FALSE, TRUE, 'yes_no'),
    (4, 'Комментарий по смене', NULL, FALSE, NULL, FALSE, FALSE, 'text')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- 4.2 Runner (Раннер)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Раннер: Открытие', 'Чек-лист открытия смены для раннера', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 60,
        ARRAY[(SELECT id FROM roles WHERE code = 'runner')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Проверить чистоту подносов и разносов', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (2, 'Проверить схему зала на сегодня', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (3, 'Форма и бейдж в порядке', NULL, TRUE, 'UNIFORM-01', FALSE, FALSE, 'checkbox'),
    (4, 'Фото рабочего места раннера', NULL, TRUE, NULL, TRUE, FALSE, 'photo')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Раннер: Закрытие', 'Чек-лист закрытия смены для раннера', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 90,
        ARRAY[(SELECT id FROM roles WHERE code = 'runner')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Подносы и разносы вымыты и убраны', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (2, 'Комментарий по смене', NULL, FALSE, NULL, FALSE, FALSE, 'text'),
    (3, 'Возникали проблемы во время смены?', NULL, TRUE, NULL, FALSE, TRUE, 'problem')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- 4.3 Hostess (Хостес)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Хостес: Открытие', 'Чек-лист открытия смены для хостес', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 60,
        ARRAY[(SELECT id FROM roles WHERE code = 'hostess')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Проверить книгу бронирований на день', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (2, 'Стойка хостес чистая и опрятная', NULL, TRUE, 'CLEAN-01', FALSE, FALSE, 'checkbox'),
    (3, 'Меню и визитки на месте, без повреждений', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (4, 'Количество подтверждённых бронирований на сегодня', NULL, FALSE, NULL, FALSE, FALSE, 'number')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Хостес: Закрытие', 'Чек-лист закрытия смены для хостес', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 90,
        ARRAY[(SELECT id FROM roles WHERE code = 'hostess')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Все брони на сегодня закрыты в системе', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (2, 'Стойка убрана', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (3, 'Комментарий по загрузке зала', NULL, FALSE, NULL, FALSE, FALSE, 'text'),
    (4, 'Были конфликтные ситуации с гостями?', NULL, TRUE, NULL, FALSE, TRUE, 'yes_no')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- 4.4 Bartender (Бармен)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Бармен: Открытие', 'Чек-лист открытия смены для бармена', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 60,
        ARRAY[(SELECT id FROM roles WHERE code = 'bartender')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Проверить остатки алкоголя и сиропов', NULL, TRUE, 'WAREHOUSE-01', FALSE, FALSE, 'checkbox'),
    (2, 'Температура холодильных витрин бара, °C', NULL, TRUE, 'KITCHEN-01', FALSE, FALSE, 'temperature'),
    (3, 'Чистота барной стойки и инвентаря', NULL, TRUE, 'BAR-01', FALSE, FALSE, 'checkbox'),
    (4, 'Фото барной стойки перед открытием', NULL, TRUE, NULL, TRUE, FALSE, 'photo')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Бармен: Закрытие', 'Чек-лист закрытия смены для бармена', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 90,
        ARRAY[(SELECT id FROM roles WHERE code = 'bartender')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Барная стойка вымыта, инвентарь убран', NULL, TRUE, 'BAR-01', FALSE, FALSE, 'checkbox'),
    (2, 'Списание/остатки ингредиентов зафиксированы', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (3, 'Количество приготовленных напитков за смену', NULL, FALSE, NULL, FALSE, FALSE, 'number'),
    (4, 'Комментарий по нехватке ингредиентов', NULL, FALSE, NULL, FALSE, FALSE, 'text')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- 4.5 Cashier (Кассир)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Кассир: Открытие', 'Чек-лист открытия смены для кассира', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 60,
        ARRAY[(SELECT id FROM roles WHERE code = 'cashier')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Сверка остатка кассы на начало смены', NULL, TRUE, 'CASHIER-01', FALSE, FALSE, 'number'),
    (2, 'Проверить работу терминала и принтера чеков', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (3, 'Наличность и мелкие деньги на месте', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (4, 'Фото открытой кассовой смены', NULL, FALSE, NULL, FALSE, FALSE, 'photo')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Кассир: Закрытие', 'Чек-лист закрытия смены для кассира', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 90,
        ARRAY[(SELECT id FROM roles WHERE code = 'cashier')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Закрытие кассовой смены, сумма по Z-отчёту', NULL, TRUE, 'CASHIER-01', FALSE, FALSE, 'number'),
    (2, 'Чеки выдавались каждому гостю?', NULL, TRUE, 'CASHIER-02', FALSE, FALSE, 'yes_no'),
    (3, 'Расхождения в кассе', NULL, TRUE, NULL, FALSE, TRUE, 'problem'),
    (4, 'Комментарий по смене', NULL, FALSE, NULL, FALSE, FALSE, 'text')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- 4.6 Cook (Повар)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Повар: Открытие', 'Чек-лист открытия смены для повара', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 60,
        ARRAY[(SELECT id FROM roles WHERE code = 'cook')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Температура холодильников и морозильников, °C', NULL, TRUE, 'KITCHEN-01', FALSE, FALSE, 'temperature'),
    (2, 'Проверка сроков годности продуктов', NULL, TRUE, 'KITCHEN-02', FALSE, FALSE, 'checkbox'),
    (3, 'Рабочее место и инвентарь готовы', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (4, 'Фото рабочей зоны кухни перед открытием', NULL, TRUE, NULL, TRUE, FALSE, 'photo')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Повар: Закрытие', 'Чек-лист закрытия смены для повара', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 90,
        ARRAY[(SELECT id FROM roles WHERE code = 'cook')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Кухня вымыта, поверхности продезинфицированы', NULL, TRUE, 'CLEAN-01', FALSE, FALSE, 'checkbox'),
    (2, 'Остатки продуктов убраны и подписаны', NULL, TRUE, 'KITCHEN-02', FALSE, FALSE, 'checkbox'),
    (3, 'Температура холодильников на конец смены, °C', NULL, TRUE, 'KITCHEN-01', FALSE, FALSE, 'temperature'),
    (4, 'Были нештатные ситуации на кухне?', NULL, TRUE, NULL, FALSE, TRUE, 'problem')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- 4.7 Confectioner (Кондитер)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Кондитер: Открытие', 'Чек-лист открытия смены для кондитера', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 60,
        ARRAY[(SELECT id FROM roles WHERE code = 'confectioner')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Температура кондитерской витрины, °C', NULL, TRUE, 'KITCHEN-01', FALSE, FALSE, 'temperature'),
    (2, 'Проверка остатков десертов и полуфабрикатов', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (3, 'Рабочее место кондитера подготовлено', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (4, 'Фото витрины с десертами', NULL, TRUE, NULL, TRUE, FALSE, 'photo')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Кондитер: Закрытие', 'Чек-лист закрытия смены для кондитера', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 90,
        ARRAY[(SELECT id FROM roles WHERE code = 'confectioner')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Витрина и рабочее место убраны', NULL, TRUE, 'CLEAN-01', FALSE, FALSE, 'checkbox'),
    (2, 'Остатки десертов списаны/сохранены', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (3, 'Количество приготовленных десертов за смену', NULL, FALSE, NULL, FALSE, FALSE, 'number'),
    (4, 'Комментарий по смене', NULL, FALSE, NULL, FALSE, FALSE, 'text')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- 4.8 Cleaner (Уборщик)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Уборщик: Открытие', 'Чек-лист открытия смены для уборщика', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 60,
        ARRAY[(SELECT id FROM roles WHERE code = 'cleaner')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Уборка зала перед открытием выполнена', NULL, TRUE, 'CLEAN-01', FALSE, FALSE, 'checkbox'),
    (2, 'Туалетные комнаты проверены и убраны', NULL, TRUE, 'CLEAN-02', FALSE, FALSE, 'checkbox'),
    (3, 'Инвентарь для уборки на месте', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (4, 'Фото убранного зала', NULL, TRUE, NULL, TRUE, FALSE, 'photo')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Уборщик: Закрытие', 'Чек-лист закрытия смены для уборщика', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 90,
        ARRAY[(SELECT id FROM roles WHERE code = 'cleaner')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Финальная уборка зала выполнена', NULL, TRUE, 'CLEAN-01', FALSE, FALSE, 'checkbox'),
    (2, 'Туалетные комнаты убраны на закрытие', NULL, TRUE, 'CLEAN-02', FALSE, FALSE, 'checkbox'),
    (3, 'Мусор вынесен', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (4, 'Обнаружены поломки/проблемы при уборке?', NULL, TRUE, NULL, FALSE, TRUE, 'problem')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- 4.9 Manager (Менеджер)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Менеджер: Открытие', 'Чек-лист открытия смены для менеджера', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 30,
        ARRAY[(SELECT id FROM roles WHERE code = 'manager')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Внешний вид команды соответствует стандарту', NULL, TRUE, 'UNIFORM-01', FALSE, FALSE, 'checkbox'),
    (2, 'Касса, бар, кухня и зал готовы к открытию', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (3, 'Проведена пятиминутка с командой', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (4, 'Общее фото команды перед открытием', NULL, TRUE, NULL, TRUE, FALSE, 'photo')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Менеджер: Закрытие', 'Чек-лист закрытия смены для менеджера', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 60,
        ARRAY[(SELECT id FROM roles WHERE code = 'manager')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Все чек-листы смены закрыты сотрудниками', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (2, 'Касса сверена и сдана', NULL, TRUE, 'CASHIER-01', FALSE, FALSE, 'checkbox'),
    (3, 'Количество открытых проблем на конец смены', NULL, TRUE, NULL, FALSE, FALSE, 'number'),
    (4, 'Комментарий менеджера по смене', NULL, FALSE, NULL, FALSE, FALSE, 'text')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- 4.10 Senior manager (Старший менеджер)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Старший менеджер: Открытие', 'Контроль готовности филиалов к открытию', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 60,
        ARRAY[(SELECT id FROM roles WHERE code = 'senior_manager')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Проверка готовности обоих филиалов к открытию', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (2, 'Контроль стандартов сервиса за прошлые сутки', NULL, TRUE, 'SERVICE-01', FALSE, FALSE, 'checkbox'),
    (3, 'Количество активных проблем по филиалам', NULL, TRUE, NULL, FALSE, FALSE, 'number'),
    (4, 'Комментарий по итогам проверки', NULL, FALSE, NULL, FALSE, FALSE, 'text')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Старший менеджер: Закрытие', 'Итоговая сверка отчётов филиалов', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 90,
        ARRAY[(SELECT id FROM roles WHERE code = 'senior_manager')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Отчёты менеджеров филиалов получены', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (2, 'Сверка кассовых отчётов по филиалам', NULL, TRUE, 'CASHIER-01', FALSE, FALSE, 'checkbox'),
    (3, 'Есть эскалированные проблемы?', NULL, TRUE, NULL, FALSE, TRUE, 'yes_no'),
    (4, 'Комментарий по итогам дня', NULL, FALSE, NULL, FALSE, FALSE, 'text')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- 4.11 Supervisor (Управляющий)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Управляющий: Открытие', 'Контроль безопасности и складских остатков', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 90,
        ARRAY[(SELECT id FROM roles WHERE code = 'supervisor')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Проверка стандартов безопасности (огнетушители, эвакуация)', NULL, TRUE, 'SAFETY-01', FALSE, FALSE, 'checkbox'),
    (2, 'Контроль складских остатков', NULL, TRUE, 'WAREHOUSE-01', FALSE, FALSE, 'checkbox'),
    (3, 'Количество филиалов с отклонениями от стандарта', NULL, TRUE, NULL, FALSE, FALSE, 'number'),
    (4, 'Фото проверки склада', NULL, TRUE, NULL, TRUE, FALSE, 'photo')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Управляющий: Закрытие', 'Итоговая проверка филиалов на конец дня', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 120,
        ARRAY[(SELECT id FROM roles WHERE code = 'supervisor')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Итоговая проверка филиалов на конец дня', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (2, 'Все просроченные чек-листы разобраны', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (3, 'Проблемы, требующие внимания директора', NULL, TRUE, NULL, FALSE, TRUE, 'problem'),
    (4, 'Комментарий по итогам проверки', NULL, FALSE, NULL, FALSE, FALSE, 'text')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- 4.12 Director (Директор)
WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Директор: Открытие', 'Обзор показателей всех филиалов', 'opening', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 120,
        ARRAY[(SELECT id FROM roles WHERE code = 'director')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Обзор показателей всех филиалов за сутки', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (2, 'Проверка ключевых стандартов MADO', NULL, TRUE, 'SERVICE-04', FALSE, FALSE, 'checkbox'),
    (3, 'Количество критических проблем за сутки', NULL, TRUE, NULL, FALSE, FALSE, 'number'),
    (4, 'Комментарий директора', NULL, FALSE, NULL, FALSE, FALSE, 'text')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

WITH t AS (
    INSERT INTO checklist_templates (name, description, category, branch_id, is_active, created_by_employee_id, deadline_offset_minutes, role_ids)
    VALUES ('Директор: Закрытие', 'Итоговый отчёт по выручке и выполнению чек-листов', 'closing', NULL, TRUE,
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), 180,
        ARRAY[(SELECT id FROM roles WHERE code = 'director')::int])
    RETURNING id
)
INSERT INTO checklist_template_items (template_id, title, description, sort_order, is_required, standard_code, requires_photo, requires_comment, task_type)
SELECT t.id, v.title, v.description, v.sort_order, v.is_required, v.standard_code, v.requires_photo, v.requires_comment, v.task_type FROM t, (VALUES
    (1, 'Итоговый отчёт по выручке и выполнению чек-листов', NULL, TRUE, NULL, FALSE, FALSE, 'checkbox'),
    (2, 'Все эскалации закрыты?', NULL, TRUE, NULL, FALSE, TRUE, 'yes_no'),
    (3, 'Количество филиалов, выполнивших план на 100%', NULL, FALSE, NULL, FALSE, FALSE, 'number'),
    (4, 'Комментарий директора по итогам дня', NULL, FALSE, NULL, FALSE, FALSE, 'text')
) AS v(sort_order, title, description, is_required, standard_code, requires_photo, requires_comment, task_type);

-- -----------------------------------------------------------------------------
-- 5. Checklists for "today" — one per position (opening template), mixed
--    statuses: completed / overdue / in progress — to exercise dashboards,
--    filters and deadline logic.
-- -----------------------------------------------------------------------------
-- Helper pattern per checklist:
--   WITH c AS (INSERT INTO checklists (...) RETURNING id)
--   INSERT INTO checklist_items (...) SELECT c.id, item fields... FROM checklist_template_items WHERE template_id = <opening template id> , c
-- Then an UPDATE marks some items completed for that checklist.

-- 5.1 Waiter — Tashkent City Mall — COMPLETED (on time)
WITH c AS (
    INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at, completed_at)
    VALUES ((SELECT id FROM checklist_templates WHERE name = 'Официант: Открытие'), 'Официант: Открытие',
        (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'completed',
        (SELECT id FROM employees WHERE full_name = 'Иван Соколов'),
        NOW() - INTERVAL '3 hours', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours 10 minutes')
    RETURNING id
)
INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type, is_completed, completed_by_employee_id, completed_at)
SELECT c.id, ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type, TRUE,
    (SELECT id FROM employees WHERE full_name = 'Иван Соколов'), NOW() - INTERVAL '2 hours 15 minutes'
FROM checklist_template_items ti, c WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Официант: Открытие');

-- 5.2 Cook — Park in Mall — COMPLETED (on time)
WITH c AS (
    INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at, completed_at)
    VALUES ((SELECT id FROM checklist_templates WHERE name = 'Повар: Открытие'), 'Повар: Открытие',
        (SELECT id FROM branches WHERE name = 'Park in Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'completed',
        (SELECT id FROM employees WHERE full_name = 'Жасур Эргашев'),
        NOW() - INTERVAL '4 hours', NOW() - INTERVAL '3 hours', NOW() - INTERVAL '3 hours 5 minutes')
    RETURNING id
)
INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type, is_completed, completed_by_employee_id, completed_at)
SELECT c.id, ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type, TRUE,
    (SELECT id FROM employees WHERE full_name = 'Жасур Эргашев'), NOW() - INTERVAL '3 hours 10 minutes'
FROM checklist_template_items ti, c WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Повар: Открытие');

-- 5.3 Manager — Tashkent City Mall — COMPLETED (on time)
WITH c AS (
    INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at, completed_at)
    VALUES ((SELECT id FROM checklist_templates WHERE name = 'Менеджер: Открытие'), 'Менеджер: Открытие',
        (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'completed',
        (SELECT id FROM employees WHERE full_name = 'Алина Каримова'),
        NOW() - INTERVAL '2 hours 30 minutes', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours 5 minutes')
    RETURNING id
)
INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type, is_completed, completed_by_employee_id, completed_at)
SELECT c.id, ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type, TRUE,
    (SELECT id FROM employees WHERE full_name = 'Алина Каримова'), NOW() - INTERVAL '2 hours 10 minutes'
FROM checklist_template_items ti, c WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Менеджер: Открытие');

-- 5.4 Director — Tashkent City Mall — COMPLETED (on time)
WITH c AS (
    INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at, completed_at)
    VALUES ((SELECT id FROM checklist_templates WHERE name = 'Директор: Открытие'), 'Директор: Открытие',
        (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'completed',
        (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'),
        NOW() - INTERVAL '5 hours', NOW() - INTERVAL '3 hours', NOW() - INTERVAL '3 hours 20 minutes')
    RETURNING id
)
INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type, is_completed, completed_by_employee_id, completed_at)
SELECT c.id, ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type, TRUE,
    (SELECT id FROM employees WHERE full_name = 'Дилшод Каримов'), NOW() - INTERVAL '3 hours 30 minutes'
FROM checklist_template_items ti, c WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Директор: Открытие');

-- 5.5 Runner — Park in Mall — OVERDUE (still open, nothing done)
INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at)
VALUES ((SELECT id FROM checklist_templates WHERE name = 'Раннер: Открытие'), 'Раннер: Открытие',
    (SELECT id FROM branches WHERE name = 'Park in Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'open',
    (SELECT id FROM employees WHERE full_name = 'Сардор Каримов'), NOW() - INTERVAL '2 hours', NOW() - INTERVAL '1 hour');

INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type)
SELECT (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Сардор Каримов') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD')),
    ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type
FROM checklist_template_items ti WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Раннер: Открытие');

-- 5.6 Bartender — Tashkent City Mall — OVERDUE (half done)
INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at)
VALUES ((SELECT id FROM checklist_templates WHERE name = 'Бармен: Открытие'), 'Бармен: Открытие',
    (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'open',
    (SELECT id FROM employees WHERE full_name = 'Бекзод Назаров'), NOW() - INTERVAL '2 hours', NOW() - INTERVAL '30 minutes');

INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type)
SELECT (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Бекзод Назаров') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD')),
    ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type
FROM checklist_template_items ti WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Бармен: Открытие');

UPDATE checklist_items SET is_completed = TRUE, completed_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Бекзод Назаров'), completed_at = NOW() - INTERVAL '90 minutes'
WHERE checklist_id = (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Бекзод Назаров') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD'))
    AND sort_order <= 2;

-- 5.7 Cashier — Park in Mall — OVERDUE (half done)
INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at)
VALUES ((SELECT id FROM checklist_templates WHERE name = 'Кассир: Открытие'), 'Кассир: Открытие',
    (SELECT id FROM branches WHERE name = 'Park in Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'open',
    (SELECT id FROM employees WHERE full_name = 'Камила Исмаилова'), NOW() - INTERVAL '2 hours', NOW() - INTERVAL '45 minutes');

INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type)
SELECT (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Камила Исмаилова') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD')),
    ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type
FROM checklist_template_items ti WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Кассир: Открытие');

UPDATE checklist_items SET is_completed = TRUE, completed_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Камила Исмаилова'), completed_at = NOW() - INTERVAL '80 minutes'
WHERE checklist_id = (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Камила Исмаилова') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD'))
    AND sort_order = 1;

-- 5.8 Cleaner — Tashkent City Mall — OVERDUE (nothing done)
INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at)
VALUES ((SELECT id FROM checklist_templates WHERE name = 'Уборщик: Открытие'), 'Уборщик: Открытие',
    (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'open',
    (SELECT id FROM employees WHERE full_name = 'Азиз Турсунов'), NOW() - INTERVAL '90 minutes', NOW() - INTERVAL '15 minutes');

INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type)
SELECT (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Азиз Турсунов') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD')),
    ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type
FROM checklist_template_items ti WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Уборщик: Открытие');

-- Escalation already fired for this overdue checklist (demonstrates migration 015 fields)
UPDATE checklists SET overdue_manager_notified_at = NOW() - INTERVAL '5 minutes'
WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Азиз Турсунов') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD');

-- 5.9 Hostess — Park in Mall — IN PROGRESS (due in the future)
INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at)
VALUES ((SELECT id FROM checklist_templates WHERE name = 'Хостес: Открытие'), 'Хостес: Открытие',
    (SELECT id FROM branches WHERE name = 'Park in Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'open',
    (SELECT id FROM employees WHERE full_name = 'Зарина Тошева'), NOW() - INTERVAL '20 minutes', NOW() + INTERVAL '40 minutes');

INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type)
SELECT (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Зарина Тошева') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD')),
    ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type
FROM checklist_template_items ti WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Хостес: Открытие');

UPDATE checklist_items SET is_completed = TRUE, completed_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Зарина Тошева'), completed_at = NOW() - INTERVAL '5 minutes'
WHERE checklist_id = (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Зарина Тошева') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD'))
    AND sort_order = 1;

-- 5.10 Confectioner — Tashkent City Mall — IN PROGRESS (due in the future)
INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at)
VALUES ((SELECT id FROM checklist_templates WHERE name = 'Кондитер: Открытие'), 'Кондитер: Открытие',
    (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'open',
    (SELECT id FROM employees WHERE full_name = 'Гулноза Мирзаева'), NOW() - INTERVAL '15 minutes', NOW() + INTERVAL '45 minutes');

INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type)
SELECT (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Гулноза Мирзаева') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD')),
    ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type
FROM checklist_template_items ti WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Кондитер: Открытие');

-- 5.11 Senior manager — Tashkent City Mall — IN PROGRESS
INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at)
VALUES ((SELECT id FROM checklist_templates WHERE name = 'Старший менеджер: Открытие'), 'Старший менеджер: Открытие',
    (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'open',
    (SELECT id FROM employees WHERE full_name = 'Севара Ахунова'), NOW() - INTERVAL '30 minutes', NOW() + INTERVAL '30 minutes');

INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type)
SELECT (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Севара Ахунова') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD')),
    ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type
FROM checklist_template_items ti WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Старший менеджер: Открытие');

UPDATE checklist_items SET is_completed = TRUE, completed_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Севара Ахунова'), completed_at = NOW() - INTERVAL '10 minutes'
WHERE checklist_id = (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Севара Ахунова') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD'))
    AND sort_order <= 2;

-- 5.12 Supervisor — Tashkent City Mall — IN PROGRESS
INSERT INTO checklists (template_id, template_name, branch_id, shift, date, status, created_by_employee_id, started_at, due_at)
VALUES ((SELECT id FROM checklist_templates WHERE name = 'Управляющий: Открытие'), 'Управляющий: Открытие',
    (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), 'morning', to_char(CURRENT_DATE, 'YYYY-MM-DD'), 'open',
    (SELECT id FROM employees WHERE full_name = 'Умид Назиров'), NOW() - INTERVAL '20 minutes', NOW() + INTERVAL '70 minutes');

INSERT INTO checklist_items (checklist_id, title, description, is_required, sort_order, standard_code, requires_photo, requires_comment, task_type)
SELECT (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Умид Назиров') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD')),
    ti.title, ti.description, ti.is_required, ti.sort_order, ti.standard_code, ti.requires_photo, ti.requires_comment, ti.task_type
FROM checklist_template_items ti WHERE ti.template_id = (SELECT id FROM checklist_templates WHERE name = 'Управляющий: Открытие');

-- -----------------------------------------------------------------------------
-- 6. Photos — for completed "photo" task_type items above
-- -----------------------------------------------------------------------------

INSERT INTO photos (checklist_item_id, uploaded_by_employee_id, url)
SELECT ci.id, (SELECT id FROM employees WHERE full_name = 'Иван Соколов'), '/api/v1/checklists/photos/seed_waiter_open_' || ci.id || '.jpg'
FROM checklist_items ci
JOIN checklists c ON c.id = ci.checklist_id
WHERE c.created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Иван Соколов')
  AND c.date = to_char(CURRENT_DATE, 'YYYY-MM-DD') AND ci.task_type = 'photo' AND ci.is_completed = TRUE;

INSERT INTO photos (checklist_item_id, uploaded_by_employee_id, url)
SELECT ci.id, (SELECT id FROM employees WHERE full_name = 'Жасур Эргашев'), '/api/v1/checklists/photos/seed_cook_open_' || ci.id || '.jpg'
FROM checklist_items ci
JOIN checklists c ON c.id = ci.checklist_id
WHERE c.created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Жасур Эргашев')
  AND c.date = to_char(CURRENT_DATE, 'YYYY-MM-DD') AND ci.task_type = 'photo' AND ci.is_completed = TRUE;

INSERT INTO photos (checklist_item_id, uploaded_by_employee_id, url)
SELECT ci.id, (SELECT id FROM employees WHERE full_name = 'Алина Каримова'), '/api/v1/checklists/photos/seed_manager_open_' || ci.id || '.jpg'
FROM checklist_items ci
JOIN checklists c ON c.id = ci.checklist_id
WHERE c.created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Алина Каримова')
  AND c.date = to_char(CURRENT_DATE, 'YYYY-MM-DD') AND ci.task_type = 'photo' AND ci.is_completed = TRUE;

-- -----------------------------------------------------------------------------
-- 7. Issues (проблемы) — exercise the "Проблемы" board
-- -----------------------------------------------------------------------------

INSERT INTO issues (title, description, branch_id, checklist_id, category, priority, status, reported_by_employee_id, assigned_to_employee_id) VALUES
    ('Не работает кондиционер в зале', 'Кондиционер у окна не охлаждает, гости жалуются на жару.',
        (SELECT id FROM branches WHERE name = 'Park in Mall'),
        (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Сардор Каримов') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD')),
        'general', 'high', 'new',
        (SELECT id FROM employees WHERE full_name = 'Сардор Каримов'),
        (SELECT id FROM employees WHERE full_name = 'Руслан Пулатов')),
    ('Просрочен товар на складе бара', 'Обнаружены 3 бутылки сиропа с истёкшим сроком годности.',
        (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), NULL,
        'warehouse', 'medium', 'in_progress',
        (SELECT id FROM employees WHERE full_name = 'Бекзод Назаров'),
        (SELECT id FROM employees WHERE full_name = 'Алина Каримова')),
    ('Сломан кран на кухне', 'Кран горячей воды на кухне подтекает, требуется ремонт сантехники.',
        (SELECT id FROM branches WHERE name = 'Park in Mall'), NULL,
        'kitchen', 'high', 'resolved',
        (SELECT id FROM employees WHERE full_name = 'Жасур Эргашев'),
        (SELECT id FROM employees WHERE full_name = 'Руслан Пулатов'));

UPDATE issues SET resolved_at = NOW() - INTERVAL '1 day' WHERE title = 'Сломан кран на кухне';

INSERT INTO issue_comments (issue_id, author_employee_id, text) VALUES
    ((SELECT id FROM issues WHERE title = 'Не работает кондиционер в зале'), (SELECT id FROM employees WHERE full_name = 'Руслан Пулатов'), 'Вызвал мастера, приедет сегодня после 15:00.'),
    ((SELECT id FROM issues WHERE title = 'Просрочен товар на складе бара'), (SELECT id FROM employees WHERE full_name = 'Алина Каримова'), 'Списали просроченные позиции, заказали новую партию.'),
    ((SELECT id FROM issues WHERE title = 'Сломан кран на кухне'), (SELECT id FROM employees WHERE full_name = 'Руслан Пулатов'), 'Сантехник заменил прокладку, кран больше не течёт.');

-- -----------------------------------------------------------------------------
-- 8. Shifts (смены) for today
-- -----------------------------------------------------------------------------

INSERT INTO shifts (employee_id, branch_id, shift_date, starts_at, ends_at, status) VALUES
    ((SELECT id FROM employees WHERE full_name = 'Иван Соколов'),     (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), to_char(CURRENT_DATE, 'YYYY-MM-DD'), '07:00', '16:00', 'active'),
    ((SELECT id FROM employees WHERE full_name = 'Дилноза Юсупова'),  (SELECT id FROM branches WHERE name = 'Park in Mall'),       to_char(CURRENT_DATE, 'YYYY-MM-DD'), '07:00', '16:00', 'active'),
    ((SELECT id FROM employees WHERE full_name = 'Фарход Расулов'),   (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), to_char(CURRENT_DATE, 'YYYY-MM-DD'), '06:30', '15:30', 'active'),
    ((SELECT id FROM employees WHERE full_name = 'Жасур Эргашев'),    (SELECT id FROM branches WHERE name = 'Park in Mall'),       to_char(CURRENT_DATE, 'YYYY-MM-DD'), '06:30', '15:30', 'active'),
    ((SELECT id FROM employees WHERE full_name = 'Алина Каримова'),   (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), to_char(CURRENT_DATE, 'YYYY-MM-DD'), '07:00', '19:00', 'active'),
    ((SELECT id FROM employees WHERE full_name = 'Руслан Пулатов'),   (SELECT id FROM branches WHERE name = 'Park in Mall'),       to_char(CURRENT_DATE, 'YYYY-MM-DD'), '07:00', '19:00', 'active'),
    ((SELECT id FROM employees WHERE full_name = 'Мадина Рахимова'),  (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), to_char(CURRENT_DATE, 'YYYY-MM-DD'), '10:00', '22:00', 'planned'),
    ((SELECT id FROM employees WHERE full_name = 'Азиз Турсунов'),    (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), to_char(CURRENT_DATE, 'YYYY-MM-DD'), '06:00', '14:00', 'active'),
    ((SELECT id FROM employees WHERE full_name = 'Отабек Собиров'),   (SELECT id FROM branches WHERE name = 'Tashkent City Mall'), to_char(CURRENT_DATE - 30, 'YYYY-MM-DD'), '07:00', '16:00', 'no_show');

-- -----------------------------------------------------------------------------
-- 9. Notifications (уведомления) — reminder / overdue / escalation / issue_assigned
-- -----------------------------------------------------------------------------

INSERT INTO notifications (recipient_employee_id, type, title, message, is_read) VALUES
    ((SELECT id FROM employees WHERE full_name = 'Сардор Каримов'), 'reminder', 'Начните чек-лист открытия', 'Через 30 минут дедлайн по чек-листу «Раннер: Открытие».', FALSE),
    ((SELECT id FROM employees WHERE full_name = 'Руслан Пулатов'), 'overdue', 'Чек-лист просрочен', 'Раннер Сардор Каримов не завершил «Раннер: Открытие» в срок.', FALSE),
    ((SELECT id FROM employees WHERE full_name = 'Севара Ахунова'), 'escalation', 'Эскалация: чек-лист уборщика просрочен', 'Чек-лист «Уборщик: Открытие» (Ташкент Сити Молл) просрочен более 30 минут.', FALSE),
    ((SELECT id FROM employees WHERE full_name = 'Руслан Пулатов'), 'issue_assigned', 'Вам назначена проблема', 'Проблема «Не работает кондиционер в зале» назначена вам.', TRUE),
    ((SELECT id FROM employees WHERE full_name = 'Алина Каримова'), 'issue_assigned', 'Вам назначена проблема', 'Проблема «Просрочен товар на складе бара» назначена вам.', TRUE);

-- -----------------------------------------------------------------------------
-- 10. Audit logs (журнал действий) — sample entries
-- -----------------------------------------------------------------------------

INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, metadata) VALUES
    ((SELECT id FROM employees WHERE full_name = 'Иван Соколов'),   'checklist.completed', 'checklist',
        (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Иван Соколов') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD')),
        '{"source": "seed"}'::jsonb),
    ((SELECT id FROM employees WHERE full_name = 'Алина Каримова'), 'template.created', 'checklist_template',
        (SELECT id FROM checklist_templates WHERE name = 'Менеджер: Открытие'),
        '{"source": "seed"}'::jsonb),
    (NULL, 'checklist.overdue', 'checklist',
        (SELECT id FROM checklists WHERE created_by_employee_id = (SELECT id FROM employees WHERE full_name = 'Азиз Турсунов') AND date = to_char(CURRENT_DATE, 'YYYY-MM-DD')),
        '{"source": "scheduler", "note": "seed"}'::jsonb);

COMMIT;

-- =============================================================================
-- Summary (run separately, informational only)
-- =============================================================================
-- SELECT (SELECT count(*) FROM branches) AS branches,
--        (SELECT count(*) FROM employees) AS employees,
--        (SELECT count(*) FROM checklist_templates) AS templates,
--        (SELECT count(*) FROM checklist_template_items) AS template_items,
--        (SELECT count(*) FROM checklists) AS checklists,
--        (SELECT count(*) FROM checklist_items) AS checklist_items,
--        (SELECT count(*) FROM standards) AS standards,
--        (SELECT count(*) FROM issues) AS issues,
--        (SELECT count(*) FROM shifts) AS shifts,
--        (SELECT count(*) FROM notifications) AS notifications;
