# MADO Checklist

Система контроля операционных стандартов сети ресторанов MADO.
Менеджеры создают чек-листы по шаблонам, персонал выполняет задачи — всё фиксируется в системе.

## Возможности

- **Авторизация** — JWT (email + пароль), ролевая система доступа
- **Филиалы** — управление сетью ресторанов, часовые пояса
- **Сотрудники** — учёт персонала с инвайт-кодами для привязки аккаунтов
- **Шаблоны чек-листов** — библиотека задач по категориям (открытие, закрытие, уборка...)
- **Чек-листы** — запуск смен (утро/день/вечер), контроль выполнения в реальном времени
- **Ролевой доступ** — 4 уровня: персонал → менеджер → управляющий → директор

## Технологический стек

| Слой | Технологии |
|------|-----------|
| Frontend | React 19, Vite 8, Tailwind CSS 4, Tanstack Query 5, Axios |
| Backend | Python 3.12, FastAPI 0.115, SQLAlchemy 2 async, asyncpg |
| База данных | PostgreSQL 16 |
| Деплой | Docker Compose + nginx |

## Быстрый старт

### Требования

- Docker Engine 24+ и Docker Compose

### 1. Клонировать и настроить

```bash
git clone https://github.com/dilshikk/resto.git
cd resto
cp backend/env.example .env
# Откройте .env и задайте SECRET_KEY и POSTGRES_PASSWORD
```

### 2. Запустить

```bash
docker compose up -d --build
```

Сервисы после запуска:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs

### 3. Первичная инициализация

**Шаг 1.** Создать первого директора и главный филиал:
```bash
curl -X POST http://localhost:8000/api/v1/employees/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Иванов Иван", "branch_name": "Главный филиал", "timezone": "Asia/Tashkent"}'
# → {"ok": true, "employee_id": 1, "branch_id": 1}
```

**Шаг 2.** Создать веб-аккаунт для директора:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/create-user?email=admin@mado.uz&password=YourPassword&employee_id=1"
```

**Шаг 3.** Добавить стандартные должности:
```bash
curl -X POST http://localhost:8000/api/v1/roles/seed
```

**Шаг 4.** Войти: http://localhost:3000

## Структура проекта

```
resto/
├── frontend/               # React SPA
│   ├── src/
│   │   ├── api/            # HTTP-клиенты (axios)
│   │   │   ├── client.ts   # Axios instance + JWT interceptors
│   │   │   ├── auth.ts
│   │   │   ├── branches.ts
│   │   │   ├── employees.ts
│   │   │   └── checklists.ts
│   │   ├── context/
│   │   │   └── auth-context.tsx  # JWT AuthContext
│   │   ├── components/providers/ # QueryClient, Theme, Toaster
│   │   └── pages/
│   │       ├── LoginPage.tsx
│   │       └── app/
│   │           ├── AppLayout.tsx   # Sidebar + bottom nav
│   │           ├── dashboard/      # Статистика
│   │           ├── branches/       # Управление филиалами
│   │           ├── employees/      # Управление персоналом
│   │           ├── templates/      # Шаблоны чек-листов
│   │           └── checklists/     # Активные чек-листы
│   ├── index.html
│   ├── vite.config.ts
│   ├── nginx.conf          # Reverse proxy /api → backend
│   └── Dockerfile
├── backend/                # FastAPI
│   ├── app/
│   │   ├── models/
│   │   │   ├── branch.py
│   │   │   ├── role.py
│   │   │   ├── employee.py
│   │   │   ├── user.py
│   │   │   └── checklist.py  # Template, TemplateItem, Checklist, ChecklistItem
│   │   ├── schemas/        # Pydantic схемы
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── branches.py
│   │   │   ├── roles.py
│   │   │   ├── employees.py
│   │   │   ├── templates.py
│   │   │   └── checklists.py
│   │   ├── auth.py         # JWT helpers, зависимости
│   │   ├── config.py       # Настройки (pydantic-settings)
│   │   ├── database.py     # Async SQLAlchemy engine
│   │   └── main.py
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   └── 002_checklists.sql
│   ├── requirements.txt
│   ├── env.example
│   └── Dockerfile
└── docker-compose.yml
```

## API

| Метод | Путь | Описание | Мин. уровень |
|-------|------|----------|-------------|
| POST | `/api/v1/auth/login` | Вход (email/password) | — |
| POST | `/api/v1/auth/refresh` | Обновить access токен | — |
| GET | `/api/v1/employees/me` | Мой профиль | 0 |
| GET | `/api/v1/branches` | Список доступных филиалов | 0 |
| GET/POST | `/api/v1/employees` | Список / создание сотрудников | 1 |
| PATCH | `/api/v1/employees/{id}` | Обновить сотрудника | 1 |
| GET/POST | `/api/v1/templates` | Шаблоны чек-листов | 0/1 |
| GET | `/api/v1/templates/{id}` | Шаблон с пунктами | 0 |
| POST | `/api/v1/templates/{id}/items` | Добавить пункт | 1 |
| GET/POST | `/api/v1/checklists` | Чек-листы | 0/1 |
| GET | `/api/v1/checklists/{id}` | Чек-лист с пунктами | 0 |
| PATCH | `/api/v1/checklists/{id}/items/{item_id}/toggle` | Отметить/снять пункт | 0 |
| POST | `/api/v1/checklists/{id}/complete` | Завершить чек-лист | 1 |

Полная интерактивная документация: http://localhost:8000/docs

## Уровни доступа

| Уровень | Роли | Возможности |
|---------|------|-------------|
| 0 | Официант, кассир, повар, бармен... | Просмотр и заполнение чек-листов |
| 1 | Менеджер, старший менеджер | + Управление сотрудниками, создание чек-листов и шаблонов |
| 2 | Управляющий | + Управление всеми филиалами |
| 3 | Директор | Полный доступ |

## Переменные окружения

Файл `.env` в корне проекта (создаётся из `backend/env.example`):

| Переменная | Описание | Пример |
|-----------|---------|--------|
| `POSTGRES_PASSWORD` | Пароль PostgreSQL | `strongpassword` |
| `SECRET_KEY` | Секрет для подписи JWT (мин. 32 символа) | `change-this-in-prod-long-key` |
| `CORS_ORIGINS` | Разрешённые origins через запятую | `https://yourdomain.com` |

## Разработка без Docker

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://mado:password@localhost:5432/mado_checklist
export SECRET_KEY=dev-secret-key-change-in-prod
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev  # прокси /api → http://localhost:8000
```
