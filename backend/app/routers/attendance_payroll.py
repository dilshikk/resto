"""
Табель и расчёт зарплаты по данным FaceID.

Правила:
- Смена считается с 06:00 до 05:59 следующего дня. Ночной уход (01:00-03:00)
  относится к дню прихода.
- День засчитывается только если есть и приход, и уход
  (из FaceID или введённые вручную).
- Ручные правки хранятся в основной БД и имеют приоритет над FaceID.
- Начислено = дней * ставка + премия; К выдаче = начислено - штраф - посуда.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.attendance_database import get_attendance_db
from app.auth import require_manager
from app.database import get_db
from app.models.attendance_payroll import (
    AttendanceEmployeeProfile,
    AttendancePayrollAdjustment,
    AttendancePunchOverride,
)
from app.models.attendance_rate import AttendanceRate
from app.models.employee import Employee

router = APIRouter(prefix="/attendance-payroll", tags=["attendance"])

MAX_PERIOD_DAYS = 62
SHIFT_CUTOFF_MINUTES = 6 * 60
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


# ── Схемы ────────────────────────────────────────────────────────────────────

class PayrollDayOut(BaseModel):
    arrival: str | None
    departure: str | None
    faceid_arrival: str | None
    faceid_departure: str | None
    manual: bool
    counted: bool


class PayrollEmployeeOut(BaseModel):
    employee_id: str
    name: str
    position: str | None
    rate_per_shift: float
    currency: str
    days: dict[str, PayrollDayOut]
    worked_days: int
    bonus: float
    fine: float
    posuda: float
    gross: float
    net: float


class PayrollOut(BaseModel):
    date_from: date
    date_to: date
    dates: list[str]
    employees: list[PayrollEmployeeOut]


class PunchUpsert(BaseModel):
    faceid_employee_id: str = Field(min_length=1, max_length=64)
    shift_date: date
    # None = не переопределять, брать из FaceID. Если оба None - правка удаляется.
    arrival: str | None = Field(default=None, pattern=TIME_PATTERN)
    departure: str | None = Field(default=None, pattern=TIME_PATTERN)
    note: str | None = Field(default=None, max_length=255)


class AdjustmentUpsert(BaseModel):
    faceid_employee_id: str = Field(min_length=1, max_length=64)
    date_from: date
    date_to: date
    # None = поле не менять
    bonus: float | None = Field(default=None, ge=0, le=1e10)
    fine: float | None = Field(default=None, ge=0, le=1e10)
    posuda: float | None = Field(default=None, ge=0, le=1e10)


class PositionUpsert(BaseModel):
    faceid_employee_id: str = Field(min_length=1, max_length=64)
    position: str | None = Field(default=None, max_length=100)


# ── Время и смены ────────────────────────────────────────────────────────────

@dataclass
class _RawDay:
    ins: list[str] = field(default_factory=list)
    outs: list[str] = field(default_factory=list)


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _shift_minutes(hhmm: str) -> int:
    """Минуты от начала смены: ночные часы (до 06:00) идут после 23:59."""
    minutes = _to_minutes(hhmm)
    return minutes + 24 * 60 if minutes < SHIFT_CUTOFF_MINUTES else minutes


def _shift_date(day: date, hhmm: str) -> date:
    return day - timedelta(days=1) if _to_minutes(hhmm) < SHIFT_CUTOFF_MINUTES else day


def _to_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _to_hhmm(value: object) -> str | None:
    if value is None:
        return None
    parts = str(value).split(":")
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1][:2].isdigit():
        return None
    return f"{int(parts[0]):02d}:{int(parts[1][:2]):02d}"


def _faceid_times(raw: _RawDay) -> tuple[str | None, str | None]:
    """Первый приход и последний уход, который случился после прихода."""
    arrival = min(raw.ins, key=_shift_minutes, default=None)
    outs = [o for o in raw.outs if arrival is None or _shift_minutes(o) > _shift_minutes(arrival)]
    departure = max(outs, key=_shift_minutes, default=None)
    return arrival, departure


def _validate_period(date_from: date, date_to: date) -> list[date]:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="Дата окончания раньше даты начала")
    length = (date_to - date_from).days + 1
    if length > MAX_PERIOD_DAYS:
        raise HTTPException(status_code=422, detail=f"Период не может быть больше {MAX_PERIOD_DAYS} дней")
    return [date_from + timedelta(days=i) for i in range(length)]


async def _load_faceid_days(
    attendance_db: AsyncSession, date_from: date, date_to: date
) -> tuple[dict[tuple[str, date], _RawDay], dict[str, str]]:
    # +1 день: ночные события следующих суток относятся к последней смене периода
    result = await attendance_db.execute(
        text(
            """
            SELECT employee_id, access_date, access_time, direction, first_name, last_name
            FROM public.access_logs
            WHERE access_date BETWEEN :date_from AND :date_to
              AND employee_id IS NOT NULL
            ORDER BY access_datetime
            """
        ),
        {"date_from": str(date_from), "date_to": str(date_to + timedelta(days=1))},
    )
    days: dict[tuple[str, date], _RawDay] = {}
    names: dict[str, str] = {}
    for row in result.mappings().all():
        access_date = _to_date(row["access_date"])
        hhmm = _to_hhmm(row["access_time"])
        if access_date is None or hhmm is None:
            continue
        shift_day = _shift_date(access_date, hhmm)
        if shift_day < date_from or shift_day > date_to:
            continue
        employee_id = str(row["employee_id"])
        raw = days.setdefault((employee_id, shift_day), _RawDay())
        direction = (row["direction"] or "").lower()
        if direction == "in":
            raw.ins.append(hhmm)
        elif direction == "out":
            raw.outs.append(hhmm)
        name = " ".join(p for p in (row["first_name"], row["last_name"]) if p)
        if name:
            names[employee_id] = name
    return days, names


def _build_days(
    employee_id: str,
    dates: list[date],
    faceid: dict[tuple[str, date], _RawDay],
    overrides: dict[tuple[str, date], AttendancePunchOverride],
) -> dict[str, PayrollDayOut]:
    result: dict[str, PayrollDayOut] = {}
    for day in dates:
        raw = faceid.get((employee_id, day))
        override = overrides.get((employee_id, day))
        if raw is None and override is None:
            continue
        face_arrival, face_departure = _faceid_times(raw) if raw else (None, None)
        arrival = (override.arrival if override else None) or face_arrival
        departure = (override.departure if override else None) or face_departure
        result[day.isoformat()] = PayrollDayOut(
            arrival=arrival,
            departure=departure,
            faceid_arrival=face_arrival,
            faceid_departure=face_departure,
            manual=bool(override and (override.arrival or override.departure)),
            counted=bool(arrival and departure),
        )
    return result


# ── Эндпоинты ────────────────────────────────────────────────────────────────

@router.get("", response_model=PayrollOut)
async def get_payroll(
    date_from: date = Query(..., description="Начало периода YYYY-MM-DD"),
    date_to: date = Query(..., description="Конец периода YYYY-MM-DD"),
    _current: Employee = Depends(require_manager),
    attendance_db: AsyncSession = Depends(get_attendance_db),
    main_db: AsyncSession = Depends(get_db),
):
    """Табель за произвольный период с расчётом зарплаты по каждому сотруднику."""
    dates = _validate_period(date_from, date_to)
    faceid, names = await _load_faceid_days(attendance_db, date_from, date_to)

    override_rows = (
        await main_db.execute(
            select(AttendancePunchOverride).where(
                AttendancePunchOverride.shift_date >= date_from,
                AttendancePunchOverride.shift_date <= date_to,
            )
        )
    ).scalars().all()
    overrides = {(o.faceid_employee_id, o.shift_date): o for o in override_rows}

    adjustment_rows = (
        await main_db.execute(
            select(AttendancePayrollAdjustment).where(
                AttendancePayrollAdjustment.date_from == date_from,
                AttendancePayrollAdjustment.date_to == date_to,
            )
        )
    ).scalars().all()
    adjustments = {a.faceid_employee_id: a for a in adjustment_rows}

    rates = {r.faceid_employee_id: r for r in (await main_db.execute(select(AttendanceRate))).scalars().all()}
    profiles = {
        p.faceid_employee_id: p
        for p in (await main_db.execute(select(AttendanceEmployeeProfile))).scalars().all()
    }

    # В табель попадают те, у кого есть отметки/правки/премии за период или задана ставка
    employee_ids = {eid for eid, _ in faceid} | {eid for eid, _ in overrides} | set(adjustments)
    employee_ids |= {eid for eid, rate in rates.items() if rate.rate_per_shift > 0}

    def display_name(employee_id: str) -> str:
        rate = rates.get(employee_id)
        return names.get(employee_id) or (rate.display_name if rate and rate.display_name else employee_id)

    employees: list[PayrollEmployeeOut] = []
    for employee_id in sorted(employee_ids, key=lambda e: display_name(e).lower()):
        rate = rates.get(employee_id)
        adjustment = adjustments.get(employee_id)
        profile = profiles.get(employee_id)
        days = _build_days(employee_id, dates, faceid, overrides)
        worked = sum(1 for d in days.values() if d.counted)
        rate_value = Decimal(rate.rate_per_shift) if rate else Decimal(0)
        bonus = Decimal(adjustment.bonus) if adjustment else Decimal(0)
        fine = Decimal(adjustment.fine) if adjustment else Decimal(0)
        posuda = Decimal(adjustment.posuda) if adjustment else Decimal(0)
        gross = rate_value * worked + bonus
        employees.append(
            PayrollEmployeeOut(
                employee_id=employee_id,
                name=display_name(employee_id),
                position=profile.position if profile else None,
                rate_per_shift=float(rate_value),
                currency=rate.currency if rate else "UZS",
                days=days,
                worked_days=worked,
                bonus=float(bonus),
                fine=float(fine),
                posuda=float(posuda),
                gross=float(gross),
                net=float(gross - fine - posuda),
            )
        )

    return PayrollOut(
        date_from=date_from,
        date_to=date_to,
        dates=[d.isoformat() for d in dates],
        employees=employees,
    )


@router.put("/punch")
async def upsert_punch(
    body: PunchUpsert,
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Ручной приход/уход за смену. Если оба времени пустые - правка удаляется."""
    row = (
        await db.execute(
            select(AttendancePunchOverride).where(
                AttendancePunchOverride.faceid_employee_id == body.faceid_employee_id,
                AttendancePunchOverride.shift_date == body.shift_date,
            )
        )
    ).scalar_one_or_none()

    if body.arrival is None and body.departure is None:
        if row is not None:
            await db.delete(row)
            await db.commit()
        return {"status": "ok"}

    if row is None:
        row = AttendancePunchOverride(
            faceid_employee_id=body.faceid_employee_id,
            shift_date=body.shift_date,
        )
        db.add(row)
    row.arrival = body.arrival
    row.departure = body.departure
    row.note = body.note
    await db.commit()
    return {"status": "ok"}


@router.put("/adjustment")
async def upsert_adjustment(
    body: AdjustmentUpsert,
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Премия, штраф, посуда сотрудника за период. Меняются только переданные поля."""
    _validate_period(body.date_from, body.date_to)
    row = (
        await db.execute(
            select(AttendancePayrollAdjustment).where(
                AttendancePayrollAdjustment.faceid_employee_id == body.faceid_employee_id,
                AttendancePayrollAdjustment.date_from == body.date_from,
                AttendancePayrollAdjustment.date_to == body.date_to,
            )
        )
    ).scalar_one_or_none()

    if row is None:
        row = AttendancePayrollAdjustment(
            faceid_employee_id=body.faceid_employee_id,
            date_from=body.date_from,
            date_to=body.date_to,
            bonus=Decimal(0),
            fine=Decimal(0),
            posuda=Decimal(0),
        )
        db.add(row)

    if body.bonus is not None:
        row.bonus = Decimal(str(body.bonus))
    if body.fine is not None:
        row.fine = Decimal(str(body.fine))
    if body.posuda is not None:
        row.posuda = Decimal(str(body.posuda))
    await db.commit()
    return {"status": "ok"}


@router.put("/position")
async def upsert_position(
    body: PositionUpsert,
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Должность сотрудника для табеля."""
    row = (
        await db.execute(
            select(AttendanceEmployeeProfile).where(
                AttendanceEmployeeProfile.faceid_employee_id == body.faceid_employee_id
            )
        )
    ).scalar_one_or_none()
    position = (body.position or "").strip() or None
    if row is None:
        db.add(AttendanceEmployeeProfile(faceid_employee_id=body.faceid_employee_id, position=position))
    else:
        row.position = position
    await db.commit()
    return {"status": "ok"}
