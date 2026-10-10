"""
Роутер для управления ставками сотрудников FaceID.
Ставки хранятся в основной БД: attendance_rates - текущая ставка,
attendance_rate_history - история (с какой даты какая ставка действует).
"""
import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_manager
from app.database import get_db
from app.models.attendance_rate import AttendanceRate, AttendanceRateHistory
from app.models.employee import Employee

router = APIRouter(prefix="/attendance-rates", tags=["attendance"])

# Дата, с которой считается действующей ставка, заданная до появления истории
HISTORY_START = datetime.date(2000, 1, 1)


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
    # С какой даты действует новая ставка. По умолчанию - с сегодняшнего дня,
    # прошлые смены считаются по старой ставке.
    effective_from: datetime.date | None = None


class RateHistoryOut(BaseModel):
    effective_from: datetime.date
    rate: float
    currency: str


@router.get("", response_model=list[RateOut])
async def list_rates(
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Возвращает все текущие ставки."""
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


@router.get("/{faceid_employee_id}/history", response_model=list[RateHistoryOut])
async def rate_history(
    faceid_employee_id: str,
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """История ставок сотрудника, новые сверху."""
    rows = (
        await db.execute(
            select(AttendanceRateHistory)
            .where(AttendanceRateHistory.faceid_employee_id == faceid_employee_id)
            .order_by(AttendanceRateHistory.effective_from.desc())
        )
    ).scalars().all()
    return [RateHistoryOut(effective_from=r.effective_from, rate=float(r.rate), currency=r.currency) for r in rows]


async def _upsert_history(
    db: AsyncSession, employee_id: str, effective_from: datetime.date, rate: Decimal, currency: str
) -> None:
    row = (
        await db.execute(
            select(AttendanceRateHistory).where(
                AttendanceRateHistory.faceid_employee_id == employee_id,
                AttendanceRateHistory.effective_from == effective_from,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(
            AttendanceRateHistory(
                faceid_employee_id=employee_id, rate=rate, currency=currency, effective_from=effective_from
            )
        )
    else:
        row.rate = rate
        row.currency = currency


@router.put("/{faceid_employee_id}", response_model=RateOut)
async def upsert_rate(
    faceid_employee_id: str,
    body: RateUpsert,
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт или обновляет ставку. Старая ставка сохраняется в истории для прошлых смен."""
    if body.rate_per_shift < 0:
        raise HTTPException(status_code=422, detail="Ставка не может быть отрицательной")

    new_rate = Decimal(str(body.rate_per_shift))
    effective_from = body.effective_from or datetime.date.today()

    row = (
        await db.execute(
            select(AttendanceRate).where(
                AttendanceRate.faceid_employee_id == faceid_employee_id
            )
        )
    ).scalar_one_or_none()

    has_history = (
        await db.execute(
            select(AttendanceRateHistory.id)
            .where(AttendanceRateHistory.faceid_employee_id == faceid_employee_id)
            .limit(1)
        )
    ).scalar_one_or_none() is not None

    # Ставка задана до появления истории: сохраняем её для всех прошлых смен
    if row is not None and not has_history and effective_from > HISTORY_START:
        await _upsert_history(db, faceid_employee_id, HISTORY_START, Decimal(row.rate_per_shift), row.currency)

    await _upsert_history(db, faceid_employee_id, effective_from, new_rate, body.currency)

    if row is None:
        row = AttendanceRate(
            faceid_employee_id=faceid_employee_id,
            display_name=body.display_name,
            rate_per_shift=new_rate,
            currency=body.currency,
        )
        db.add(row)
    else:
        if body.display_name is not None:
            row.display_name = body.display_name
        # Текущая ставка меняется, только если новая уже действует
        if effective_from <= datetime.date.today():
            row.rate_per_shift = new_rate
            row.currency = body.currency

    await db.commit()
    await db.refresh(row)
    return RateOut(
        faceid_employee_id=row.faceid_employee_id,
        display_name=row.display_name,
        rate_per_shift=float(row.rate_per_shift),
        currency=row.currency,
    )
