"""
FaceID Attendance API
Запустите на VPS рядом с PostgreSQL.

ВАЖНО: сервис отдаёт персональные данные сотрудников (имена, время проходов,
номера карт), поэтому каждый запрос требует секретный ключ в заголовке X-API-Key.
Если основной backend уже читает FaceID напрямую (ATTENDANCE_DATABASE_URL),
этот сервис не нужен - его лучше остановить совсем.

Установка:
    pip install fastapi uvicorn asyncpg python-dotenv

Запуск (только локально, наружу - через reverse proxy с HTTPS):
    uvicorn main:app --host 127.0.0.1 --port 8001

Переменные окружения (файл .env):
    DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
    VPS_API_KEY=<случайная строка не короче 32 символов, например: openssl rand -hex 32>
    CORS_ORIGINS=https://staff.mado.uz          # через запятую, "*" запрещён
"""

import os
import secrets
from datetime import date

import asyncpg
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
API_KEY: str = os.getenv("VPS_API_KEY", "")
CORS_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
]
MAX_PERIOD_DAYS = 62

# Не запускаемся в небезопасной конфигурации, чтобы сервис нельзя было
# случайно оставить открытым.
if len(API_KEY) < 32:
    raise RuntimeError("Задайте VPS_API_KEY не короче 32 символов (openssl rand -hex 32)")
if "*" in CORS_ORIGINS:
    raise RuntimeError("CORS_ORIGINS='*' запрещён: перечислите разрешённые адреса явно")

# Документация API отключена: она раскрывает структуру данных
app = FastAPI(title="FaceID Attendance API", docs_url=None, redoc_url=None, openapi_url=None)

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["X-API-Key"],
    )


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    # compare_digest - сравнение за постоянное время, без утечки по таймингу
    if not secrets.compare_digest(x_api_key.encode(), API_KEY.encode()):
        raise HTTPException(status_code=401, detail="Неверный ключ доступа")


# Convert asyncpg DSN (postgresql+asyncpg://...) → plain postgresql://
def _pg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(_pg_dsn(DATABASE_URL))


def _check_period(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="Дата окончания раньше даты начала")
    if (date_to - date_from).days + 1 > MAX_PERIOD_DAYS:
        raise HTTPException(status_code=422, detail=f"Период не может быть больше {MAX_PERIOD_DAYS} дней")


@app.get("/attendance/logs", dependencies=[Depends(require_api_key)])
async def get_logs(
    date_from: date = Query(..., description="YYYY-MM-DD"),
    date_to: date = Query(..., description="YYYY-MM-DD"),
    employee_id: str | None = Query(None, max_length=64),
):
    """Return access_logs rows filtered by date range and optional employee."""
    _check_period(date_from, date_to)
    conn = await get_conn()
    try:
        if employee_id:
            rows = await conn.fetch(
                """
                SELECT id, employee_id, access_datetime, access_date, access_time,
                       auth_result, auth_type, device_name, device_sn,
                       first_name, last_name, card_no, direction
                FROM public.access_logs
                WHERE access_date BETWEEN $1 AND $2
                  AND employee_id = $3
                ORDER BY access_datetime
                """,
                date_from, date_to, employee_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, employee_id, access_datetime, access_date, access_time,
                       auth_result, auth_type, device_name, device_sn,
                       first_name, last_name, card_no, direction
                FROM public.access_logs
                WHERE access_date BETWEEN $1 AND $2
                ORDER BY access_datetime
                """,
                date_from, date_to,
            )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


@app.get("/attendance/employees", dependencies=[Depends(require_api_key)])
async def get_employees():
    """Return distinct employees from access_logs."""
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT employee_id, first_name, last_name
            FROM public.access_logs
            WHERE employee_id IS NOT NULL
            ORDER BY last_name, first_name
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


@app.get("/health")
async def health():
    return {"ok": True}
