"""
Роутер для управления ставками сотрудников FaceID.
Ставки хранятся в основной БД (attendance_rates).
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_web_user, require_manager
from app.database import get_db
from app.models.attendance_rate import AttendanceRate
from app.models.employee import Employee

router = APIRouter(prefix="/attendance-rates", tags=["attendance"])


class RateOut(BaseModel):
    faceid_employee_id: str
    display_name: str | None
    rate_per_shift: float
    currency: str


class RateUpsert(BaseModel):
    faceid_employee_id: str
    display_name: str | None = None
    rate_per_shift: float
    currency: str = "UZS"


@router.get("", response_model=list[RateOut])
async def list_rates(
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Возвращает все ставки."""
    rows = (await db.execute(select(AttendanceRate).order_by(AttendanceRate.display_name))).scalars().all()
    return [
        RateOut(
            faceid_employee_id=r.faceid_employee_id,
            display_name=r.display_name,
            rate_per_shift=float(r.rate_per_shift),
            currency=r.currency,
        )
        for r in rows
    ]


@router.put("/{faceid_employee_id}", response_model=RateOut)
async def upsert_rate(
    faceid_employee_id: str,
    body: RateUpsert,
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт или обновляет ставку для сотрудника FaceID."""
    if body.rate_per_shift < 0:
        raise HTTPException(status_code=422, detail="Ставка не может быть отрицательной")

    row = (
        await db.execute(
            select(AttendanceRate).where(
                AttendanceRate.faceid_employee_id == faceid_employee_id
            )
        )
    ).scalar_one_or_none()

    if row is None:
        row = AttendanceRate(
            faceid_employee_id=faceid_employee_id,
            display_name=body.display_name,
            rate_per_shift=Decimal(str(body.rate_per_shift)),
            currency=body.currency,
        )
        db.add(row)
    else:
        if body.display_name is not None:
            row.display_name = body.display_name
        row.rate_per_shift = Decimal(str(body.rate_per_shift))
        row.currency = body.currency

    await db.commit()
    await db.refresh(row)
    return RateOut(
        faceid_employee_id=row.faceid_employee_id,
        display_name=row.display_name,
        rate_per_shift=float(row.rate_per_shift),
        currency=row.currency,
    )
