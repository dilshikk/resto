"""
Табель и расчёт зарплаты по данным FaceID.

Правила:
- Смена считается с 06:00 до 05:59 следующего дня. Ночной уход (01:00-03:00)
  относится к дню прихода.
- За смену может быть несколько отрезков (пришёл - ушёл на учёбу - вернулся - ушёл).
  Часы = сумма закрытых отрезков вход -> выход. Время вне работы не оплачивается.
- Повторные сканы подряд (два входа или два выхода) считаются одним событием.
- Если после последнего входа нет выхода, этот отрезок не считается (смена открыта).
- Ручные правки хранятся в основной БД и имеют приоритет над FaceID:
  заданы и приход, и уход - вся смена одним отрезком; задан только один -
  он заменяет начало первого отрезка или закрывает последний открытый.
- Оплата почасовая, но за смену оплачивается не более 10 часов.
  Всё, что больше 10 часов, - переработка: она считается и показывается
  отдельно, но в зарплату НЕ засчитывается.
- Ставка за час берётся из истории ставок (attendance_rate_history) на день смены,
  поэтому изменение ставки не пересчитывает прошлые периоды. Если истории нет,
  используется текущая ставка из attendance_rates.rate_per_shift (имя колонки историческое).
- Начислено = сумма по сменам (оплачиваемые часы * ставка дня) + премия;
  К выдаче = начислено - штраф - посуда.
- Имя сотрудника: ПРИОРИТЕТ у display_name из основной БД (attendance_rates).
  FaceID-имя используется только если display_name не задан. Это гарантирует,
  что смена имени в FaceID не ломает табель и все данные остаются привязаны к ID.
"""
from bisect import bisect_right
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
from app.models.attendance_rate import AttendanceRate, AttendanceRateHistory
from app.models.employee import Employee

router = APIRouter(prefix="/attendance-payroll", tags=["attendance"])

MAX_PERIOD_DAYS = 62
SHIFT_CUTOFF_MINUTES = 6 * 60
# Максимум оплачиваемого времени за одну смену; остальное - переработка
MAX_PAID_MINUTES_PER_SHIFT = 10 * 60
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
MONEY_STEP = Decimal("0.01")


# ── Схемы ────────────────────────────────────────────────────────────────────

class PayrollDayOut(BaseModel):
    # Первый приход и последний закрытый уход за смену
    arrival: str | None
    departure: str | None
    faceid_arrival: str | None
    faceid_departure: str | None
    manual: bool
    counted: bool
    # Фактически отработано минут за смену (None, если смена не засчитана)
    minutes: int | None
    # Оплачиваемые минуты: не больше 10 часов (None, если смена не засчитана)
    paid_minutes: int | None
    # Переработка сверх 10 часов, не оплачивается
    overtime_minutes: int
    # После последнего входа нет выхода
    open: bool
    # Отрезки работы "06:58-12:25", если их больше одного видно перерыв
    segments: list[str]
    # Ставка за час, действовавшая в день смены
    rate: float = 0


class PayrollEmployeeOut(BaseModel):
    employee_id: str
    name: str
    # Имя из FaceID — для информации, чтобы менеджер мог сверить
    faceid_name: str | None = None
    position: str | None
    # Ставка за час на конец периода
    rate_per_hour: float
    # В периоде действовало несколько разных ставок
    rate_changed: bool = False
    currency: str
    days: dict[str, PayrollDayOut]
    worked_days: int
    # Фактически отработано минут за период (включая переработку)
    worked_minutes: int
    # Оплачиваемые минуты за период (не больше 10 часов за каждую смену)
    paid_minutes: int
    # Переработка за период, не оплачивается
    overtime_minutes: int
    # Оплачиваемые часы
    hours: float
    overtime_hours: float
    bonus: float
    fine: float
    posuda: float
    gross: float
    net: float


class PayrollOut(BaseModel):
    date_from: date
    date_to: date
    dates: list[str]
    max_paid_minutes_per_shift: int
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
    # События смены в хронологическом порядке: ("in" | "out", "HH:MM")
    events: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class _Session:
    # Закрытые отрезки [начало, конец] и начало незакрытого отрезка
    segments: list[list[str]] = field(default_factory=list)
    open_start: str | None = None


@dataclass
class _RateTimeline:
    """Ставки сотрудника по датам начала действия (по возрастанию)."""
    starts: list[date] = field(default_factory=list)
    rates: list[Decimal] = field(default_factory=list)
    fallback: Decimal = Decimal(0)

    def on(self, day: date) -> Decimal:
        if not self.starts:
            return self.fallback
        idx = bisect_right(self.starts, day) - 1
        # Смена раньше первой записи истории - берём самую раннюю ставку
        return self.rates[max(idx, 0)]


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _shift_minutes(hhmm: str) -> int:
    """Минуты от начала смены: ночные часы (до 06:00) идут после 23:59."""
    minutes = _to_minutes(hhmm)
    return minutes + 24 * 60 if minutes < SHIFT_CUTOFF_MINUTES else minutes


def _shift_date(day: date, hhmm: str) -> date:
    return day - timedelta(days=1) if _to_minutes(hhmm) < SHIFT_CUTOFF_MINUTES else day


def _day_minutes(start: str, end: str) -> int | None:
    """Длительность отрезка в минутах; None, если конец не позже начала."""
    diff = _shift_minutes(end) - _shift_minutes(start)
    return diff if diff > 0 else None


def _split_paid(minutes: int) -> tuple[int, int]:
    """Делит отработанные минуты смены на оплачиваемые (до 10 ч) и переработку."""
    paid = min(minutes, MAX_PAID_MINUTES_PER_SHIFT)
    return paid, minutes - paid


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


def _build_session(events: list[tuple[str, str]]) -> _Session:
    """Собирает отрезки работы из событий FaceID.

    Подряд идущие входы - один вход (берём первый), подряд идущие выходы - один
    выход (берём последний). Выход в ту же минуту или раньше входа считается
    дублем скана и игнорируется.
    """
    session = _Session()
    prev_kind: str | None = None
    for kind, hhmm in events:
        if kind == "in":
            if session.open_start is None:
                session.open_start = hhmm
        elif session.open_start is not None:
            if _shift_minutes(hhmm) > _shift_minutes(session.open_start):
                session.segments.append([session.open_start, hhmm])
                session.open_start = None
        elif (
            prev_kind == "out"
            and session.segments
            and _shift_minutes(hhmm) > _shift_minutes(session.segments[-1][1])
        ):
            session.segments[-1][1] = hhmm
        prev_kind = kind
    return session


def _apply_override(session: _Session, arrival: str | None, departure: str | None) -> _Session:
    """Накладывает ручной приход/уход на отрезки из FaceID."""
    if arrival and departure:
        return _Session(segments=[[arrival, departure]])
    segments = [seg[:] for seg in session.segments]
    open_start = session.open_start
    if arrival:
        if segments:
            segments[0][0] = arrival
        else:
            open_start = arrival
    if departure:
        if open_start is not None:
            segments.append([open_start, departure])
            open_start = None
        elif segments:
            segments[-1][1] = departure
    return _Session(segments=segments, open_start=open_start)


def _session_minutes(session: _Session) -> int:
    return sum(_day_minutes(start, end) or 0 for start, end in session.segments)


def _session_bounds(session: _Session) -> tuple[str | None, str | None]:
    """Первый приход и последний закрытый уход."""
    if session.segments:
        return session.segments[0][0], session.segments[-1][1]
    return session.open_start, None


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
    """Загружает события FaceID и возвращает (карта дней, карта имён из FaceID)."""
    extended_to = date_to + timedelta(days=1)
    result = await attendance_db.execute(
        text(
            """
            SELECT employee_id, access_date, access_time, direction,
                   first_name, last_name
            FROM public.access_logs
            WHERE access_date BETWEEN :date_from AND :date_to
              AND employee_id IS NOT NULL
              AND access_time IS NOT NULL
            ORDER BY employee_id, access_datetime
            """
        ),
        {"date_from": str(date_from), "date_to": str(extended_to)},
    )
    rows = result.mappings().all()
    days: dict[tuple[str, date], _RawDay] = {}
    # Имена из FaceID — используются только если display_name не задан
    faceid_names: dict[str, str] = {}
    for row in rows:
        eid = str(row["employee_id"])
        raw_date = _to_date(row["access_date"])
        raw_time = _to_hhmm(row["access_time"])
        if raw_date is None or raw_time is None:
            continue
        direction = (row["direction"] or "").lower()
        if direction not in ("in", "out"):
            continue
        shift_day = _shift_date(raw_date, raw_time)
        if not (date_from <= shift_day <= date_to):
            continue
        key = (eid, shift_day)
        if key not in days:
            days[key] = _RawDay()
        days[key].events.append((direction, raw_time))
        # Сохраняем имя из FaceID как запасной вариант
        if eid not in faceid_names:
            fn = (row["first_name"] or "").strip()
            ln = (row["last_name"] or "").strip()
            name = " ".join(filter(None, [fn, ln]))
            if name:
                faceid_names[eid] = name
    return days, faceid_names


async def _load_rate_timelines(
    main_db: AsyncSession, rates: dict[str, AttendanceRate]
) -> dict[str, _RateTimeline]:
    """История ставок по сотрудникам; без истории - текущая ставка как запасной вариант."""
    timelines = {
        eid: _RateTimeline(fallback=Decimal(rate.rate_per_shift)) for eid, rate in rates.items()
    }
    rows = (
        await main_db.execute(
            select(AttendanceRateHistory).order_by(
                AttendanceRateHistory.faceid_employee_id, AttendanceRateHistory.effective_from
            )
        )
    ).scalars().all()
    for row in rows:
        timeline = timelines.setdefault(row.faceid_employee_id, _RateTimeline())
        timeline.starts.append(row.effective_from)
        timeline.rates.append(Decimal(row.rate))
    return timelines


def _build_days(
    employee_id: str,
    dates: list[date],
    faceid: dict[tuple[str, date], _RawDay],
    overrides: dict[tuple[str, date], AttendancePunchOverride],
    timeline: _RateTimeline,
) -> dict[str, PayrollDayOut]:
    result: dict[str, PayrollDayOut] = {}
    for day in dates:
        raw = faceid.get((employee_id, day))
        override = overrides.get((employee_id, day))
        if raw is None and override is None:
            continue
        face_session = _build_session(raw.events) if raw else _Session()
        manual_arrival = override.arrival if override else None
        manual_departure = override.departure if override else None
        manual = bool(manual_arrival or manual_departure)
        session = (
            _apply_override(face_session, manual_arrival, manual_departure) if manual else face_session
        )
        minutes = _session_minutes(session)
        paid, overtime = _split_paid(minutes)
        arrival, departure = _session_bounds(session)
        face_arrival, face_departure = _session_bounds(face_session)
        result[day.isoformat()] = PayrollDayOut(
            arrival=arrival,
            departure=departure,
            faceid_arrival=face_arrival,
            faceid_departure=face_departure,
            manual=manual,
            counted=minutes > 0,
            minutes=minutes or None,
            paid_minutes=paid or None,
            overtime_minutes=overtime,
            open=session.open_start is not None,
            segments=[f"{start}-{end}" for start, end in session.segments],
            rate=float(timeline.on(day)),
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
    """Табель за период: оплата по часам по ставке дня смены, не более 10 часов за смену."""
    dates = _validate_period(date_from, date_to)
    faceid, faceid_names = await _load_faceid_days(attendance_db, date_from, date_to)

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
    timelines = await _load_rate_timelines(main_db, rates)
    profiles = {
        p.faceid_employee_id: p
        for p in (await main_db.execute(select(AttendanceEmployeeProfile))).scalars().all()
    }

    # В табель попадают те, у кого есть отметки/правки/премии за период или задана ставка
    employee_ids = {eid for eid, _ in faceid} | {eid for eid, _ in overrides} | set(adjustments)
    employee_ids |= {eid for eid, rate in rates.items() if rate.rate_per_shift > 0}

    def display_name(employee_id: str) -> str:
        """
        ПРИОРИТЕТ: display_name из основной БД (задаётся менеджером).
        Запасной вариант: имя из FaceID (может меняться при обновлении устройства).
        Так переименование в FaceID не ломает табель и данные всегда по ID.
        """
        rate = rates.get(employee_id)
        if rate and rate.display_name and rate.display_name.strip():
            return rate.display_name.strip()
        return faceid_names.get(employee_id) or employee_id

    employees: list[PayrollEmployeeOut] = []
    for employee_id in sorted(employee_ids, key=lambda e: display_name(e).lower()):
        rate = rates.get(employee_id)
        timeline = timelines.get(employee_id, _RateTimeline())
        adjustment = adjustments.get(employee_id)
        profile = profiles.get(employee_id)
        days = _build_days(employee_id, dates, faceid, overrides, timeline)
        worked_days = sum(1 for d in days.values() if d.counted)
        worked_minutes = sum(d.minutes or 0 for d in days.values())
        paid_minutes = sum(d.paid_minutes or 0 for d in days.values())
        overtime_minutes = sum(d.overtime_minutes for d in days.values())
        bonus = Decimal(adjustment.bonus) if adjustment else Decimal(0)
        fine = Decimal(adjustment.fine) if adjustment else Decimal(0)
        posuda = Decimal(adjustment.posuda) if adjustment else Decimal(0)
        # Каждая смена оплачивается по ставке своего дня, не более 10 часов
        pay = sum(
            (Decimal(str(d.rate)) * (d.paid_minutes or 0) / 60 for d in days.values()),
            Decimal(0),
        ).quantize(MONEY_STEP)
        gross = pay + bonus
        period_rates = {timeline.on(day) for day in dates}
        employees.append(
            PayrollEmployeeOut(
                employee_id=employee_id,
                name=display_name(employee_id),
                faceid_name=faceid_names.get(employee_id),
                position=profile.position if profile else None,
                rate_per_hour=float(timeline.on(date_to)),
                rate_changed=len(period_rates) > 1,
                currency=rate.currency if rate else "UZS",
                days=days,
                worked_days=worked_days,
                worked_minutes=worked_minutes,
                paid_minutes=paid_minutes,
                overtime_minutes=overtime_minutes,
                hours=round(paid_minutes / 60, 2),
                overtime_hours=round(overtime_minutes / 60, 2),
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
        max_paid_minutes_per_shift=MAX_PAID_MINUTES_PER_SHIFT,
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
