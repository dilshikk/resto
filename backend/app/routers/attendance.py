"""
Роутер посещаемости (FaceID) + ставки из основной БД.
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.attendance_database import get_attendance_db
from app.auth import get_current_web_user, require_manager
from app.database import get_db
from app.models.attendance_rate import AttendanceRate
from app.models.employee import Employee
from app.models.user import User

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("/logs")
async def get_attendance_logs(
    date_from: date = Query(..., description="Начало периода YYYY-MM-DD"),
    date_to: date = Query(..., description="Конец периода YYYY-MM-DD"),
    employee_id: Optional[str] = Query(None, description="Фильтр по ID сотрудника"),
    _current_user: User = Depends(get_current_web_user),
    attendance_db: AsyncSession = Depends(get_attendance_db),
    main_db: AsyncSession = Depends(get_db),
):
    """
    Возвращает журнал FaceID + ставки из основной БД.
    Диапазон расширяется на +1 день чтобы захватить ночные события смены.
    """
    extended_to = date_to + timedelta(days=1)
    params: dict = {"date_from": str(date_from), "date_to": str(extended_to)}

    if employee_id:
        params["employee_id"] = employee_id
        employee_filter = "AND employee_id = :employee_id"
    else:
        employee_filter = ""

    result = await attendance_db.execute(
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
    logs = [dict(r) for r in result.mappings().all()]

    # Загружаем ставки из основной БД одним запросом
    rates_rows = (await main_db.execute(select(AttendanceRate))).scalars().all()
    rates_map: dict[str, dict] = {
        r.faceid_employee_id: {"rate_per_shift": float(r.rate_per_shift), "currency": r.currency}
        for r in rates_rows
    }

    # Добавляем ставку к каждому логу
    for log in logs:
        eid = log.get("employee_id") or ""
        rate_info = rates_map.get(eid)
        log["rate_per_shift"] = rate_info["rate_per_shift"] if rate_info else None
        log["currency"] = rate_info["currency"] if rate_info else "UZS"

    return logs


@router.get("/employees")
async def get_attendance_employees(
    _current_user: User = Depends(get_current_web_user),
    attendance_db: AsyncSession = Depends(get_attendance_db),
    main_db: AsyncSession = Depends(get_db),
):
    """Возвращает список уникальных сотрудников + их ставки."""
    result = await attendance_db.execute(
        text(
            """
            SELECT DISTINCT employee_id, first_name, last_name
            FROM public.access_logs
            WHERE employee_id IS NOT NULL
            ORDER BY last_name, first_name
            """
        )
    )
    employees = [dict(r) for r in result.mappings().all()]

    rates_rows = (await main_db.execute(select(AttendanceRate))).scalars().all()
    rates_map = {
        r.faceid_employee_id: {"rate_per_shift": float(r.rate_per_shift), "currency": r.currency}
        for r in rates_rows
    }

    for emp in employees:
        eid = emp.get("employee_id") or ""
        rate_info = rates_map.get(eid)
        emp["rate_per_shift"] = rate_info["rate_per_shift"] if rate_info else None
        emp["currency"] = rate_info["currency"] if rate_info else "UZS"

    return employees
