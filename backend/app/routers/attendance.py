"""
Роутер посещаемости (FaceID).

Читает данные из отдельной БД FaceID через attendance_database.py.
Все эндпоинты требуют JWT авторизации (менеджер и выше).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.attendance_database import get_attendance_db
from app.auth import get_current_web_user
from app.models.user import User

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("/logs")
async def get_attendance_logs(
    date_from: date = Query(..., description="Начало периода YYYY-MM-DD"),
    date_to: date = Query(..., description="Конец периода YYYY-MM-DD"),
    employee_id: Optional[str] = Query(None, description="Фильтр по ID сотрудника"),
    _current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_attendance_db),
):
    """Возвращает журнал событий FaceID за указанный период."""
    if employee_id:
        result = await db.execute(
            text(
                """
                SELECT id, employee_id, access_datetime, access_date, access_time,
                       auth_result, auth_type, device_name, device_sn,
                       first_name, last_name, card_no, direction
                FROM public.access_logs
                WHERE access_date BETWEEN :date_from AND :date_to
                  AND employee_id = :employee_id
                ORDER BY access_datetime
                """
            ),
            {"date_from": str(date_from), "date_to": str(date_to), "employee_id": employee_id},
        )
    else:
        result = await db.execute(
            text(
                """
                SELECT id, employee_id, access_datetime, access_date, access_time,
                       auth_result, auth_type, device_name, device_sn,
                       first_name, last_name, card_no, direction
                FROM public.access_logs
                WHERE access_date BETWEEN :date_from AND :date_to
                ORDER BY access_datetime
                """
            ),
            {"date_from": str(date_from), "date_to": str(date_to)},
        )

    rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.get("/employees")
async def get_attendance_employees(
    _current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_attendance_db),
):
    """Возвращает список уникальных сотрудников из журнала FaceID."""
    result = await db.execute(
        text(
            """
            SELECT DISTINCT employee_id, first_name, last_name
            FROM public.access_logs
            WHERE employee_id IS NOT NULL
            ORDER BY last_name, first_name
            """
        )
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]
