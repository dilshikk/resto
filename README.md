# MADO Checklist

Система контроля операционных стандартов сети ресторанов MADO.
Менеджеры создают чек-листы по шаблонам, персонал выполняет задачи пошагово — всё фиксируется в системе.

## Быстрый старт (Docker)

### Требования
- Docker Engine 24+ и Docker Compose

### 1. Клонировать и настроить

```bash
git clone https://github.com/dilshikk/resto.git
cd resto

# Создать .env в корне проекта
cp backend/env.example .env
```

Откройте `.env` и задайте минимум два значения:

```env
POSTGRES_PASSWORD=ваш_пароль
SECRET_KEY=минимум-32-символа-случайная-строка
```

### 2. Запустить

```bash
docker compose up -d --build
```

После запуска:
| Сервис | URL |
|--------|-----|
| Frontend | http://localhost:3001 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |

### 3. Первичная инициализация (один раз)

**Шаг 1.** Заполнить должности:
```bash
curl -X POST http://localhost:8000/api/v1/roles/seed
```

**Шаг 2.** Создать первого директора + первый филиал:
```bash
curl -X POST http://localhost:8000/api/v1/employees/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Иванов Иван", "branch_name": "Tashkent City Mall", "timezone": "Asia/Tashkent"}'
# → {"ok": true, "employee_id": 1, "branch_id": 1}
```

**Шаг 3.** Создать логин/пароль для директора:
```bash
curl -X POST http://localhost:8000/api/v1/auth/create-user \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@mado.uz", "password": "YourPassword", "employee_id": 1}'
```

**Шаг 4.** Войти на http://localhost:3001

---

## Разработка без Docker

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Создать базу данных и применить миграции вручную:
psql -U postgres -c "CREATE DATABASE mado_checklist;"
psql -U postgres -d mado_checklist -f migrations/001_initial_schema.sql
psql -U postgres -d mado_checklist -f migrations/002_checklists.sql
psql -U postgres -d mado_checklist -f migrations/003_issues.sql
psql -U postgres -d mado_checklist -f migrations/004_shifts_notifications.sql
psql -U postgres -d mado_checklist -f migrations/005_photos.sql
psql -U postgres -d mado_checklist -f migrations/006_standards.sql
psql -U postgres -d mado_checklist -f migrations/007_audit_logs.sql
psql -U postgres -d mado_checklist -f migrations/008_checklist_item_skip.sql
psql -U postgres -d mado_checklist -f migrations/009_telegram.sql
psql -U postgres -d mado_checklist -f migrations/010_revoked_tokens.sql
psql -U postgres -d mado_checklist -f migrations/011_checklist_deadlines.sql

# Запустить сервер
export DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/mado_checklist
export SECRET_KEY=dev-secret-key-min-32-chars-here
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # прокси /api → http://localhost:8000
```

---

## Переменные окружения

Файл `.env` в корне проекта:

| Переменная | Описание | Пример |
|-----------|---------|--------|
| `POSTGRES_PASSWORD` | Пароль PostgreSQL | `strongpassword` |
| `SECRET_KEY` | Секрет для JWT (мин. 32 символа) | `change-this-in-prod-long-key` |
| `CORS_ORIGINS` | Разрешённые origins (через запятую) | `https://yourdomain.com` |

---

## Технологический стек

| Слой | Технологии |
|------|-----------|
| Frontend | React 19, Vite 8, Tailwind CSS 4, Tanstack Query 5, Axios |
| Backend | Python 3.12, FastAPI 0.115, SQLAlchemy 2 async, asyncpg |
| База данных | PostgreSQL 16 |
| Деплой | Docker Compose + nginx |

---

## Уровни доступа

| Уровень | Роли | Возможности |
|---------|------|-------------|
| 0 | Официант, кассир, повар, бармен... | Просмотр и заполнение чек-листов |
| 1 | Менеджер, старший менеджер | + Управление сотрудниками, создание чек-листов и шаблонов |
| 2 | Управляющий | + Управление всеми филиалами |
| 3 | Директор | Полный доступ |

---

## Структура проекта

```
resto/
├── frontend/               # React SPA
│   ├── src/
│   │   ├── api/            # HTTP-клиенты (axios)
│   │   ├── context/        # JWT AuthContext
│   │   ├── components/     # UI-компоненты
│   │   └── pages/
│   │       ├── LoginPage.tsx
│   │       └── app/
│   │           ├── AppLayout.tsx
│   │           ├── dashboard/
│   │           ├── branches/
│   │           ├── employees/
│   │           ├── templates/
│   │           ├── checklists/
│   │           ├── issues/
│   │           └── reports/
│   ├── nginx.conf          # /api → backend proxy
│   └── Dockerfile
├── backend/                # FastAPI
│   ├── app/
│   │   ├── models/         # SQLAlchemy ORM модели
│   │   ├── schemas/        # Pydantic схемы
│   │   ├── routers/        # API endpoints
│   │   ├── auth.py         # JWT helpers
│   │   ├── config.py       # Настройки
│   │   ├── database.py     # Async engine
│   │   └── main.py
│   ├── migrations/         # SQL миграции (001–011)
│   ├── requirements.txt
│   └── Dockerfile
└── docker-compose.yml
```
