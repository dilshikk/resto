# MADO Checklist — примерные файлы (v1.0)

Комплект основан на ТЗ v1.0 (разделы 13 «Структура БД» и 14 «API Endpoints»).

## Состав

```
mado_checklist/
├── migrations/
│   └── 001_initial_schema.sql   — полная SQL-миграция (CREATE TABLE) всех 15 таблиц
└── app/
    ├── dependencies.py          — заглушки авторизации (JWT / Telegram)
    ├── schemas/
    │   ├── employees.py         — Pydantic-схемы: Employee (create/update/out), Performance
    │   ├── checklists.py        — Pydantic-схемы: ChecklistTemplate, ChecklistTask
    │   ├── assignments.py       — Pydantic-схемы: Assignment, TaskResult, Photo
    │   └── issues.py            — Pydantic-схемы: Issue, IssueComment
    └── routers/
        ├── assignments.py       — пример роутера /api/v1/assignments/...
        └── issues.py            — пример роутера /api/v1/issues/...
```

## Как использовать

1. **Миграция:** применить `001_initial_schema.sql` к пустой базе PostgreSQL 15+
   (`psql -f migrations/001_initial_schema.sql`) либо перенести содержимое в Alembic-ревизию.
2. **Схемы:** это готовые Pydantic-модели request/response — можно сразу подключать к роутерам.
3. **Роутеры:** показывают форму контракта (пути, методы, коды ответов, response_model).
   Тела функций — `raise NotImplementedError` / заглушки; реальную бизнес-логику
   (обращения к БД, сервисный слой) нужно дописать под выбранный ORM (например, SQLAlchemy 2.0 + asyncpg).
4. **dependencies.py** — заглушки `get_current_employee` / `get_current_manager`,
   которые нужно заменить на реальную проверку JWT/Telegram-токена и permission_level.

## Не включено в этот пример

- Модели SQLAlchemy (ORM-слой) — схема БД описана только в SQL-миграции.
- Реализация Telegram-бота (aiogram).
- Логика планировщика (генерация assignments, напоминания, эскалация).
- Остальные роутеры из раздела 14 ТЗ (auth, branches, roles, employees, shifts,
  checklist-templates, notifications, reports, standards, audit) — сделаны по тому же
  принципу, что и `assignments.py` / `issues.py`.

Это отправная точка для Этапа 1 (Core) из roadmap ТЗ, а не production-ready код.
