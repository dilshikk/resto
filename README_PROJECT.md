
Техническое задание v1.0
Система контроля операционных стандартов «MADO CHECKLIST»
Версия документа: 1.0 Дата: 17.09.2026 Заказчик: MADO (сеть ресторанов, филиалы Tashkent City Mall, Park in Mall)

1. Назначение и цели проекта
Цель: создать единую цифровую систему контроля выполнения операционных чек-листов персоналом ресторанов MADO, объединяющую Telegram-бот для сотрудников и веб-панель для менеджеров/руководства на общей базе данных.

Задачи системы:

Каждый сотрудник получает свой чек-лист по должности и этапу смены и выполняет его в Telegram.
Менеджер в реальном времени видит статус выполнения по всему ресторану без открытия десятков файлов.
Руководство видит сводную картину по всем филиалам.
Система автоматически фиксирует просрочки, проблемы и историю действий.
Задачи и чек-листы настраиваются менеджером без изменения кода (шаблоны + конструктор).
Не входит в версию 1.0 (сознательно исключено на первом этапе): зарплаты, бухгалтерия, складской учёт, CRM гостей, бонусная система, сложная AI-аналитика, публичные рейтинги сотрудников.

2. Архитектура системы
MADO CHECKLIST

Telegram Bot

Web Panel

Сотрудники

Менеджеры / Руководство

PostgreSQL

Checklists

Employees

Reports

2.1 Технологический стек
Компонент	Технология
Backend	Python + FastAPI
Telegram-бот	aiogram 3
База данных	PostgreSQL
Frontend	React + TypeScript + Vite
UI-фреймворк	Tailwind CSS
Авторизация	JWT (веб), Telegram auth (сотрудники)
Хранение фото	Локальное хранилище / VPS или S3-совместимое
Реалтайм-обновления	WebSocket
Планировщик задач	APScheduler / Celery
Деплой	Ubuntu + Nginx + systemd / PM2
Языки интерфейса	RU / UZ / EN / TR
Система проектируется как отдельный модуль, использующий общую базу авторизации и сотрудников с существующей инфраструктурой MADO (Telegram HR-бот на aiogram/PostgreSQL).

2.2 Поддержка филиалов
Система изначально мультифилиальная:

MADO
├── Tashkent City Mall
└── Park in Mall
С возможностью добавления новых филиалов без изменения архитектуры. Один сотрудник может быть привязан к одному или нескольким филиалам. Шаблон чек-листа может быть общим для всех филиалов либо дополнен задачами, специфичными для конкретного филиала (например, «проверить состояние мангала» только для Park in Mall).

3. Роли пользователей и права доступа
3.1 Роли
Сотрудники: официант, раннер, хостес, бармен, кассир, повар, кондитер, уборщик.

Управление: менеджер, старший менеджер, управляющий, директор.

3.2 Матрица прав доступа
Функция	Сотрудник	Менеджер	Управляющий	Директор
Свой чек-лист	✅	✅	✅	✅
Просмотр всех сотрудников	❌	✅	✅	✅
Создание шаблонов	❌	✅	✅	✅
Изменение стандартов	❌	⚠️ ограниченно	✅	✅
Отчёты	❌	✅	✅	✅
Все филиалы	❌	❌	✅	✅
Управление пользователями	❌	⚠️ ограниченно	✅	✅
3.3 Авторизация
Сотрудник: вход через Telegram, система автоматически определяет должность, филиал и текущую смену.
Менеджер/руководство: веб-логин + пароль, желательно с 2FA.
Управляющий: видит оба филиала.
Директор: видит все филиалы без ограничений.
4. Логика чек-листов
4.1 Структура чек-листа
Чек-лист
├── Филиал
├── Должность
├── Смена / этап (открытие, работа в течение смены, закрытие)
├── Время начала
├── Дедлайн
├── Задачи
└── Правила выполнения
4.2 Типы заданий
Тип	Пример
☑ Чекбокс	«Столы чистые»
🔢 Число	«Количество бутылок воды: [120]»
🌡 Температура	«Холодильник: [+4.2 °C]»
📝 Текст	Свободный комментарий
📷 Фото	Фото-подтверждение
📍 Фото + геолокация	Для критических проверок
🔘 Да / Нет	«Кондиционер работает?»
⚠️ Проблема	При ответе «Да» — обязательный комментарий и/или фото
4.3 Контроль времени выполнения
Каждая задача имеет время начала и дедлайн. Статусы по факту выполнения:

В срок — выполнено до дедлайна;
Просрочено — выполнено после дедлайна;
Не выполнено — дедлайн прошёл, задача не закрыта.
4.4 Пример чек-листа: Официант — Открытие (07:00–08:00)
№	Задача	Обязательно	Фото
1	Проверить форму	✅	❌
2	Проверить чистоту стола	✅	❌
3	Проверить меню	✅	❌
4	Проверить стоп-лист	✅	❌
5	Проверить приборы	✅	❌
6	Проверить кондиционеры	✅	❌
7	Подготовить рабочее место	✅	❌
8	Общее фото команды	✅	📷
Аналогичные чек-листы (открытие/смена/закрытие) проектируются для всех должностей: менеджер, повар, бармен, официант, раннер, хостес, кассир, уборщик, кондитер.

4.5 Чек-листы по этапу дня (не только по должности)
Этап	Пример задач
Утро (07:00)	Открытие
В течение смены (10:00–18:00)	Контроль зала, проверка туалетов, проверка холодильников, контроль чистоты, контроль сервиса
Закрытие (23:00)	Закрытие
4.6 Пример чек-листа менеджера (Открытие, 07:30–08:00)
Проверить внешний вид команды, открытие кухни, бар, кассу, зал, туалеты, музыку, кондиционеры, освещение, стоп-лист, холодильники, готовность доставки; провести пятиминутку; сделать общее фото команды.

5. Шаблоны и конструктор чек-листов
5.1 Шаблоны
Менеджер не создаёт чек-лист заново каждый день — используются готовые шаблоны по должности и этапу:

Шаблоны
├── Официант: Открытие / Смена / Закрытие
├── Бармен: Открытие / Смена / Закрытие
├── Повар: Открытие / Смена / Закрытие
└── Менеджер: Открытие / Контроль / Закрытие
5.2 Конструктор задач (без изменения кода)
Менеджер может самостоятельно добавлять задачи через интерфейс:

Название задачи
Тип (чекбокс / число / температура / текст / фото / да-нет)
Время выполнения
Обязательность
Требование фото
Условная логика: если ответ «Нет» → требовать комментарий и/или фото
6. Уведомления и эскалация
6.1 Автоматические напоминания
Время	Событие
07:00	🔔 Начало чек-листа открытия
07:30	⚠️ Осталось 30 минут до дедлайна
08:00	🔴 Чек-лист не завершён — уведомление менеджеру
6.2 Логика эскалации
Сотрудник

Напоминание

Менеджер

Старший менеджер

Управляющий

Пример: 08:00 — задача просрочена → 08:10 — уведомление менеджеру → 08:30 — если проблема не решена, уведомление управляющему.

7. Экран «Проблемы»
Один из ключевых разделов веб-панели. При отметке «Проблема» создаётся карточка:

Время, должность и имя сотрудника
Описание проблемы, фото
Назначение ответственного и срока
Комментарий менеджера
Статус: 🔴 Новая → 🟡 В работе → 🟢 Исправлена
8. Telegram-бот: пользовательские сценарии
Стартовый экран сотрудника:

Приветствие, филиал, должность, время смены
Прогресс-бар по текущему чек-листу (открытие/смена/закрытие)
Кнопка «Продолжить»
Прохождение чек-листа: задачи показываются по одной, с указанием номера («1/10»), текстом задачи и кнопками действия («✅ Выполнено», «⚠️ Проблема»). Следующая задача открывается автоматически.

Фото-подтверждение: бот запрашивает конкретное фото (например, общее фото команды с перечислением, кто должен быть в кадре), сотрудник отправляет фото, система сохраняет дату, время, филиал, сотрудника, чек-лист, задачу и файл.

9. Веб-панель менеджера: разделы
MADO CHECKLIST
├── 🏠 Dashboard
├── 📋 Чек-листы (Сегодня / Открытие / Смена / Закрытие)
├── ⚠️ Проблемы
├── 👥 Сотрудники
├── 🏢 Филиалы
├── 📝 Шаблоны
├── 📊 Аналитика
├── 📸 Фотоотчёты
├── 🔔 Уведомления
├── 📚 Стандарты MADO
└── ⚙️ Настройки
Dashboard филиала показывает общий процент выполнения, количество выполненных/проблемных/невыполненных/просроченных задач за день.

Контроль сотрудников — таблица выполнения по сотруднику (без публичного рейтинга — инструмент контроля, а не соревнования).

10. Стандарты MADO
Отдельный раздел с категориями стандартов: сервис, чистота, форма, кухня, бар, касса, склад, мангал, доставка, безопасность. Каждая задача может ссылаться на конкретный стандарт (например, SERVICE-04 — «Передача заказа гостю: заказ передаётся только после проверки чека»).

11. Мультиязычность
Интерфейс поддерживает RU / UZ / EN / TR. Администратор создаёт задачу один раз — система хранит переводы для каждой формулировки, например:

Язык	Текст задачи
RU	Проверить чистоту стола
UZ	Stol tozaligini tekshirish
EN	Check table cleanliness
TR	Masa temizliğini kontrol edin
12. Отчётность и аналитика
Ежедневный отчёт по филиалу: общий процент выполнения и разбивка по должностям (официанты, раннеры, бармены, хостес, кухня, кассиры).

Еженедельный отчёт: количество невыполненных задач, количество просрочек, количество проблем, наиболее часто нарушаемые задачи, филиалы, требующие дополнительного контроля, наиболее часто не выполняемые стандарты.

Аналитика паттернов: например, если задача «Проверить меню» пропускается систематически на протяжении месяца — это сигнал не к наказанию сотрудника, а к пересмотру самого процесса/чек-листа.

История действий: каждое действие сотрудника (выполнение, проблема, фото) сохраняется без возможности удаления — полный аудит по датам.

13. Структура базы данных
13.1 Основные таблицы
users
employees
roles
branches

checklist_templates
checklist_sections
checklist_tasks

checklist_assignments
task_results

photos
issues
issue_comments

shifts
notifications

audit_logs
13.2 Логическая связь сущностей
Employee

Role

Checklist Template

Checklist Assignment

Tasks

Task Results

Photo / Issue

13.3 Детальная схема таблиц
Типы данных приведены в нотации PostgreSQL. Во всех таблицах id — BIGSERIAL PRIMARY KEY, если не указано иное; created_at / updated_at — TIMESTAMPTZ DEFAULT now().

branches — филиалы
Поле	Тип	Описание
id	BIGSERIAL PK	
name	VARCHAR(150)	Название филиала
address	VARCHAR(255)	Адрес
city	VARCHAR(100)	Город
timezone	VARCHAR(50)	Часовой пояс
is_active	BOOLEAN	Активен ли филиал
created_at / updated_at	TIMESTAMPTZ	
roles — должности/роли
Поле	Тип	Описание
id	SERIAL PK	
code	VARCHAR(50) UNIQUE	waiter, runner, hostess, bartender, cashier, cook, confectioner, cleaner, manager, senior_manager, supervisor, director
name_ru / name_uz / name_en / name_tr	VARCHAR(100)	Переводы названия роли
category	VARCHAR(20)	staff | management
permission_level	SMALLINT	Уровень доступа (см. п.3.2)
users — учётные записи (веб-доступ, для management-ролей)
Поле	Тип	Описание
id	BIGSERIAL PK	
employee_id	BIGINT FK → employees.id	
email	VARCHAR(150) UNIQUE	
password_hash	VARCHAR(255)	
is_2fa_enabled	BOOLEAN	
last_login_at	TIMESTAMPTZ	
created_at / updated_at	TIMESTAMPTZ	
employees — сотрудники
Поле	Тип	Описание
id	BIGSERIAL PK	
full_name	VARCHAR(150)	ФИО
telegram_id	BIGINT UNIQUE	Telegram user id
phone	VARCHAR(30)	
role_id	INT FK → roles.id	
preferred_language	VARCHAR(5)	ru | uz | en | tr
status	VARCHAR(20)	active | inactive | fired
hired_at	DATE	
created_at / updated_at	TIMESTAMPTZ	
employee_branches — связь сотрудник ↔ филиал (many-to-many)
Поле	Тип	Описание
id	BIGSERIAL PK	
employee_id	BIGINT FK → employees.id	
branch_id	BIGINT FK → branches.id	
is_primary	BOOLEAN	Основной филиал
shifts — смены
Поле	Тип	Описание
id	BIGSERIAL PK	
employee_id	BIGINT FK → employees.id	
branch_id	BIGINT FK → branches.id	
shift_date	DATE	
starts_at	TIME	
ends_at	TIME	
status	VARCHAR(20)	planned | active | completed | no_show
checklist_templates — шаблоны чек-листов
Поле	Тип	Описание
id	BIGSERIAL PK	
name	VARCHAR(150)	Название шаблона
role_id	INT FK → roles.id	Должность, для которой предназначен
stage	VARCHAR(20)	opening | during_shift | closing
branch_id	BIGINT FK → branches.id NULL	NULL = общий для всех филиалов
starts_at	TIME	Плановое время начала
deadline_at	TIME	Дедлайн
is_active	BOOLEAN	
created_by	BIGINT FK → users.id	
created_at / updated_at	TIMESTAMPTZ	
checklist_sections — секции внутри шаблона (опционально, для группировки задач)
Поле	Тип	Описание
id	BIGSERIAL PK	
template_id	BIGINT FK → checklist_templates.id	
name	VARCHAR(150)	
sort_order	INT	
checklist_tasks — задачи внутри шаблона
Поле	Тип	Описание
id	BIGSERIAL PK	
template_id	BIGINT FK → checklist_templates.id	
section_id	BIGINT FK → checklist_sections.id NULL	
title_ru / title_uz / title_en / title_tr	VARCHAR(255)	Переводы формулировки задачи
task_type	VARCHAR(20)	checkbox | number | temperature | text | photo | photo_geo | yes_no
is_required	BOOLEAN	
requires_photo	BOOLEAN	
requires_comment_on_negative	BOOLEAN	Требовать комментарий, если ответ «Нет»/«Проблема»
standard_code	VARCHAR(30) NULL	Ссылка на стандарт, например SERVICE-04
sort_order	INT	
due_offset_minutes	INT NULL	Смещение дедлайна относительно начала чек-листа
checklist_assignments — назначенные (сгенерированные на день) чек-листы
Поле	Тип	Описание
id	BIGSERIAL PK	
template_id	BIGINT FK → checklist_templates.id	
employee_id	BIGINT FK → employees.id	
branch_id	BIGINT FK → branches.id	
shift_id	BIGINT FK → shifts.id NULL	
assignment_date	DATE	
status	VARCHAR(20)	not_started | in_progress | completed | overdue
started_at	TIMESTAMPTZ NULL	
completed_at	TIMESTAMPTZ NULL	
task_results — результаты выполнения задач
Поле	Тип	Описание
id	BIGSERIAL PK	
assignment_id	BIGINT FK → checklist_assignments.id	
task_id	BIGINT FK → checklist_tasks.id	
value	JSONB	Ответ (значение чекбокса, число, температура, текст, да/нет)
status	VARCHAR(20)	done | problem | not_relevant | pending
completed_at	TIMESTAMPTZ NULL	
is_overdue	BOOLEAN	
completed_by	BIGINT FK → employees.id	
photos — фотоподтверждения
Поле	Тип	Описание
id	BIGSERIAL PK	
task_result_id	BIGINT FK → task_results.id	
file_url	VARCHAR(500)	
latitude	NUMERIC(9,6) NULL	
longitude	NUMERIC(9,6) NULL	
uploaded_at	TIMESTAMPTZ	
issues — проблемы
Поле	Тип	Описание
id	BIGSERIAL PK	
task_result_id	BIGINT FK → task_results.id NULL	
branch_id	BIGINT FK → branches.id	
reported_by	BIGINT FK → employees.id	
title	VARCHAR(255)	
description	TEXT	
assigned_to	BIGINT FK → employees.id NULL	
due_at	TIMESTAMPTZ NULL	
status	VARCHAR(20)	new | in_progress | resolved
created_at / updated_at	TIMESTAMPTZ	
issue_comments — комментарии к проблемам
Поле	Тип	Описание
id	BIGSERIAL PK	
issue_id	BIGINT FK → issues.id	
author_id	BIGINT FK → employees.id	
comment	TEXT	
created_at	TIMESTAMPTZ	
notifications — уведомления
Поле	Тип	Описание
id	BIGSERIAL PK	
recipient_id	BIGINT FK → employees.id	
type	VARCHAR(30)	reminder | overdue | escalation | issue_assigned
payload	JSONB	
is_read	BOOLEAN	
sent_at	TIMESTAMPTZ	
audit_logs — журнал действий
Поле	Тип	Описание
id	BIGSERIAL PK	
actor_id	BIGINT FK → employees.id NULL	
action	VARCHAR(100)	Например task.completed, template.updated
entity_type	VARCHAR(50)	
entity_id	BIGINT	
metadata	JSONB	
created_at	TIMESTAMPTZ	
13.4 Ключевые внешние связи
has

belongs_to

defines

works

targets

contains

generates

assigned

produces

answered_as

attaches

may_raise

has

BRANCHES

EMPLOYEE_BRANCHES

EMPLOYEES

ROLES

SHIFTS

CHECKLIST_TEMPLATES

CHECKLIST_TASKS

CHECKLIST_ASSIGNMENTS

TASK_RESULTS

PHOTOS

ISSUES

ISSUE_COMMENTS

Рекомендуемые индексы: checklist_assignments(employee_id, assignment_date), task_results(assignment_id), issues(status, branch_id), notifications(recipient_id, is_read), audit_logs(entity_type, entity_id).

14. API Endpoints (FastAPI)
Базовый префикс: /api/v1. Аутентификация: Bearer <JWT> для веб-панели, отдельная схема Telegram-авторизации для бота (подпись initData / внутренний сервисный токен бота).

14.1 Auth
Метод	Endpoint	Описание
POST	/auth/login	Логин менеджера/руководства (email + пароль)
POST	/auth/refresh	Обновление JWT
POST	/auth/logout	Выход
POST	/auth/telegram	Авторизация сотрудника через Telegram (проверка initData)
POST	/auth/2fa/verify	Подтверждение 2FA-кода
14.2 Branches
Метод	Endpoint	Описание
GET	/branches	Список филиалов
POST	/branches	Создать филиал
GET	/branches/{id}	Данные филиала
PATCH	/branches/{id}	Изменить филиал
DELETE	/branches/{id}	Деактивировать филиал
14.3 Roles
Метод	Endpoint	Описание
GET	/roles	Список должностей
POST	/roles	Создать должность
PATCH	/roles/{id}	Изменить должность/переводы
14.4 Employees
Метод	Endpoint	Описание
GET	/employees	Список сотрудников (фильтры: branch, role, status)
POST	/employees	Создать сотрудника
GET	/employees/{id}	Карточка сотрудника
PATCH	/employees/{id}	Изменить данные сотрудника
DELETE	/employees/{id}	Уволить/деактивировать
GET	/employees/{id}/performance	Статистика выполнения по сотруднику
GET	/employees/me	Данные текущего сотрудника (для бота)
14.5 Shifts
Метод	Endpoint	Описание
GET	/shifts	Список смен (фильтры: branch, employee, date)
POST	/shifts	Создать смену
PATCH	/shifts/{id}	Изменить смену
GET	/shifts/current	Текущая активная смена сотрудника (для бота)
14.6 Checklist Templates
Метод	Endpoint	Описание
GET	/checklist-templates	Список шаблонов (фильтры: role, branch, stage)
POST	/checklist-templates	Создать шаблон
GET	/checklist-templates/{id}	Шаблон с задачами
PATCH	/checklist-templates/{id}	Изменить шаблон
DELETE	/checklist-templates/{id}	Архивировать шаблон
POST	/checklist-templates/{id}/tasks	Добавить задачу в шаблон (конструктор)
PATCH	/checklist-templates/{id}/tasks/{task_id}	Изменить задачу шаблона
DELETE	/checklist-templates/{id}/tasks/{task_id}	Удалить задачу из шаблона
POST	/checklist-templates/{id}/tasks/reorder	Изменить порядок задач
14.7 Checklist Assignments (ежедневные чек-листы)
Метод	Endpoint	Описание
GET	/assignments	Список назначений (фильтры: branch, employee, date, status)
GET	/assignments/{id}	Детали назначения с задачами и результатами
POST	/assignments/generate	Сгенерировать назначения на дату по шаблонам (обычно вызывается планировщиком)
GET	/assignments/my-current	Текущий чек-лист сотрудника (для бота)
POST	/assignments/{id}/start	Отметить начало выполнения
14.8 Task Results
Метод	Endpoint	Описание
POST	/assignments/{id}/tasks/{task_id}/result	Зафиксировать результат по задаче
POST	/assignments/{id}/tasks/{task_id}/photo	Загрузить фото к задаче
GET	/assignments/{id}/tasks/{task_id}/result	Получить текущий результат по задаче
14.9 Issues
Метод	Endpoint	Описание
GET	/issues	Список проблем (фильтры: branch, status, assigned_to)
POST	/issues	Создать проблему
GET	/issues/{id}	Детали проблемы
PATCH	/issues/{id}	Изменить статус/назначение/срок
POST	/issues/{id}/comments	Добавить комментарий
GET	/issues/{id}/comments	Список комментариев
14.10 Notifications
Метод	Endpoint	Описание
GET	/notifications	Список уведомлений текущего пользователя
POST	/notifications/{id}/read	Отметить как прочитанное
WS	/ws/notifications	WebSocket-канал для realtime-уведомлений (веб-панель)
14.11 Reports / Analytics
Метод	Endpoint	Описание
GET	/reports/daily	Дневной отчёт по филиалу
GET	/reports/weekly	Недельный отчёт
GET	/reports/branch/{id}/summary	Сводка по филиалу (dashboard)
GET	/reports/analytics/task-failures	Наиболее часто пропускаемые задачи
GET	/reports/analytics/branch-comparison	Сравнение филиалов
14.12 Standards (Стандарты MADO)
Метод	Endpoint	Описание
GET	/standards	Список стандартов по категориям
POST	/standards	Создать стандарт
PATCH	/standards/{code}	Изменить стандарт
14.13 Audit
Метод	Endpoint	Описание
GET	/audit-logs	Журнал действий (фильтры: entity_type, actor, date range)
15. План разработки (roadmap)
Этап 1 — Core
PostgreSQL; пользователи; филиалы; должности; Telegram-авторизация; чек-листы; задачи; выполнение; фото; история.

Этап 2 — Manager Panel
Dashboard; сотрудники; чек-листы; проблемы; история; отчёты.

Этап 3 — Automation
Расписание; напоминания; просрочки; эскалация; ежедневные отчёты.

Этап 4 — Advanced
Конструктор чек-листов; мультиязычность; аналитика; стандарты; несколько филиалов; аудит действий.

16. Дальнейшие шаги (после утверждения ТЗ)
Ревью и утверждение схемы БД (раздел 13) и списка API endpoints (раздел 14) командой разработки.
Настройка окружения (PostgreSQL, FastAPI-каркас, миграции — Alembic).
Разработка сценариев Telegram-бота (aiogram) для всех должностей и этапов смены.
Проектирование экранов React-панели (Dashboard, Чек-листы, Проблемы, Сотрудники, Шаблоны, Аналитика).
Определение ролей и permissions на уровне API.
Подготовка 20–30 готовых чек-листов для всех должностей MADO.
Проработка логики напоминаний и просрочек (интервалы, получатели).
Инфраструктура: структура Docker/systemd/Nginx, план установки на VPS.
Структура проекта по папкам (backend, bot, frontend, docs).
Документ подготовлен как основа для технического проектирования. Схема БД (13.3–13.4) и список endpoints (14) являются рабочей версией v1.0 и могут уточняться в процессе разработки Этапа 1.
