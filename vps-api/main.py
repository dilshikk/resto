"""
FaceID Attendance API
Запустите на VPS рядом с PostgreSQL.

Установка:
    pip install fastapi uvicorn asyncpg python-dotenv

Запуск:
    uvicorn main:app --host 0.0.0.0 --port 8001

Переменные окружения (файл .env):
    DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
    CORS_ORIGINS=https://your-hercules-app.onhercules.app
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import asyncpg

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
CORS_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")
]

app = FastAPI(title="FaceID Attendance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Convert asyncpg DSN (postgresql+asyncpg://...) → plain postgresql://
def _pg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(_pg_dsn(DATABASE_URL))


@app.get("/attendance/logs")
async def get_logs(
    date_from: str = Query(..., description="YYYY-MM-DD"),
    date_to: str = Query(..., description="YYYY-MM-DD"),
    employee_id: str | None = Query(None),
):
    """Return access_logs rows filtered by date range and optional employee."""
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


@app.get("/attendance/employees")
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
