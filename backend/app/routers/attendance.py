"""
Роутер посещаемости (FaceID).

Читает данные из отдельной БД FaceID через attendance_database.py.
Все эндпоинты требуют JWT авторизации.

Логика смен: смена начинается в 06:00 и заканчивается в 06:00 следующего дня.
Поэтому для запроса за дату D нужны события с D 06:00 по (D+1) 06:00.
Для диапазона date_from..date_to берём события с date_from по date_to+1 день.
"""
from datetime import date, timedelta
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
    """
    Возвращает журнал событий FaceID за указанный период.

    Диапазон расширяется на +1 день в конце, чтобы захватить ночные
    события (00:00-05:59), принадлежащие смене последнего запрошенного дня.
    """
    # Расширяем диапазон на +1 день чтобы захватить ночные события смены
    extended_to = date_to + timedelta(days=1)

    params: dict = {
        "date_from": str(date_from),
        "date_to": str(extended_to),
    }

    if employee_id:
        params["employee_id"] = employee_id
        employee_filter = "AND employee_id = :employee_id"
    else:
        employee_filter = ""

    result = await db.execute(
        text(
            f"""
            SELECT id, employee_id, access_datetime, access_date, access_time,
                   auth_result, auth_type, device_name, device_sn,
                   first_name, last_name, card_no, direction
            FROM public.access_logs
            WHERE access_date BETWEEN :date_from AND :date_to
              {employee_filter}
            ORDER BY access_datetime
            """
        ),
        params,
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
