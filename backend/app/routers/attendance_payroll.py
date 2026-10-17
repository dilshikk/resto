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
- Штраф за пропущенную отметку: если в FaceID за смену есть приход без ухода
  или уход без прихода - штраф MISSING_PUNCH_FINE за каждую такую смену.
  Ручная правка исправляет часы, но штраф НЕ отменяет (он считается по FaceID).
  Смены за сегодня и вчера не штрафуются - сотрудник может быть ещё на работе.
- Ручные штрафы за смену (attendance_shift_fines): опоздание и невыход.
  Менеджер ставит их в окне смены; сумма за опоздание обычно
  LATE_FINE_PER_MINUTE * минуты, но сохраняется та, что ввёл менеджер.
- График (план смены): во сколько сотрудник должен прийти и уйти.
  Источники по приоритету: план из табеля (attendance_planned_shifts, Shift+клик)
  -> план из раздела «Смены» (shifts), если сотрудник FaceID привязан к сотруднику
  системы. План из табеля с пустым временем = выходной.
- Автоштраф за опоздание: если приход позже плана больше чем на LATE_GRACE_MINUTES,
  штраф = все минуты опоздания * LATE_FINE_PER_MINUTE (5 минут - порог, а не вычет).
  Ручной штраф за опоздание или невыход заменяет автоматический.
- Автоштраф за ранний уход: минуты раньше планового ухода * EARLY_LEAVE_FINE_PER_MINUTE.
  Не считается, если смена открыта (после последнего входа нет выхода) или стоит невыход.
- Невыход на смену штрафуется только вручную.
- Посуда: POSUDA_PER_SHIFT за каждую засчитанную смену удерживается автоматически.
  Ручная сумма посуды за период (если задана) добавляется сверху.
- Оплата почасовая, но за смену оплачивается не более 10 часов.
  Всё, что больше 10 часов, - переработка: она считается и показывается
  отдельно, но в зарплату НЕ засчитывается.
- Ставка за час берётся из истории ставок (attendance_rate_history) на день смены,
  поэтому изменение ставки не пересчитывает прошлые периоды. Если истории нет,
  используется текущая ставка из attendance_rates.rate_per_shift (имя колонки историческое).
- Начислено = сумма по сменам (оплачиваемые часы * ставка дня) + премия;
  К выдаче = начислено - штраф - штраф за отметки - штрафы за смены
  - автоштрафы за опоздание и ранний уход - посуда.
- Имя сотрудника: ПРИОРИТЕТ у display_name из основной БД (attendance_rates).
  FaceID-имя используется только если display_name не задан. Это гарантирует,
  что смена имени в FaceID не ломает табель и все данные остаются привязаны к ID.
"""
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

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
    AttendancePlannedShift,
    AttendancePunchOverride,
    AttendanceShiftFine,
)
from app.models.attendance_rate import AttendanceRate, AttendanceRateHistory
from app.models.employee import Employee
from app.models.shift import Shift
from app.routers.audit_logs import log_action

router = APIRouter(prefix="/attendance-payroll", tags=["attendance"])

MAX_PERIOD_DAYS = 62
SHIFT_CUTOFF_MINUTES = 6 * 60
# Максимум оплачиваемого времени за одну смену; остальное - переработка
MAX_PAID_MINUTES_PER_SHIFT = 10 * 60
# Штраф за смену, где в FaceID нет прихода или ухода
MISSING_PUNCH_FINE = Decimal(30000)
# Удержание за посуду за каждую засчитанную смену
POSUDA_PER_SHIFT = Decimal(5000)
# Штраф за минуту опоздания (и подсказка в окне смены)
LATE_FINE_PER_MINUTE = Decimal(1000)
# Опоздание до этого количества минут включительно не штрафуется
LATE_GRACE_MINUTES = 5
# Штраф за минуту раннего ухода
EARLY_LEAVE_FINE_PER_MINUTE = Decimal(1000)
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
MONEY_STEP = Decimal("0.01")

FineKind = Literal["late", "absence"]
PlanSource = Literal["tabel", "shifts"]


# ── Схемы ────────────────────────────────────────────────────────────────────

class ShiftFineOut(BaseModel):
    kind: FineKind
    amount: float
    planned_start: str | None = None
    late_minutes: int | None = None
    note: str | None = None


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
    # В FaceID нет прихода или ухода за смену
    missing_punch: bool = False
    # Штраф за пропущенную отметку за эту смену
    missing_punch_fine: float = 0
    # Ручные штрафы за смену (опоздание, невыход)
    fines: list[ShiftFineOut] = []
    # График: плановый приход и уход
    planned_start: str | None = None
    planned_end: str | None = None
    # Откуда план: "tabel" - задан в табеле, "shifts" - из раздела «Смены»
    plan_source: PlanSource | None = None
    # В табеле отмечен выходной
    day_off: bool = False
    # Отклонение от графика в минутах
    late_minutes: int = 0
    early_minutes: int = 0
    # Автоштрафы по графику
    late_fine: float = 0
    early_fine: float = 0


class PayrollEmployeeOut(BaseModel):
    employee_id: str
    name: str
    # Имя из FaceID — для информации, чтобы менеджер мог сверить
    faceid_name: str | None = None
    position: str | None
    # Сотрудник системы, по которому берётся план из «Смен»
    linked_employee_id: int | None = None
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
    # Смен без прихода или ухода в FaceID и сумма штрафа за них
    missing_punch_count: int = 0
    missing_punch_fine: float = 0
    # Ручные штрафы за смены (опоздания, невыходы)
    shift_fines_count: int = 0
    shift_fines_total: float = 0
    # Автоштрафы по графику
    late_count: int = 0
    late_fine_total: float = 0
    early_count: int = 0
    early_fine_total: float = 0
    # Ручная посуда за период (вводит менеджер)
    posuda: float
    # Автоматическая посуда: POSUDA_PER_SHIFT * засчитанные смены
    posuda_auto: float = 0
    # Всего посуды к удержанию
    posuda_total: float = 0
    gross: float
    net: float


class PayrollOut(BaseModel):
    date_from: date
    date_to: date
    dates: list[str]
    max_paid_minutes_per_shift: int
    missing_punch_fine_amount: float
    posuda_per_shift: float
    late_fine_per_minute: float
    late_grace_minutes: int
    early_leave_fine_per_minute: float
    employees: list[PayrollEmployeeOut]


class PunchUpsert(BaseModel):
    faceid_employee_id: str = Field(min_length=1, max_length=64)
    shift_date: date
    # None = не переопределять, брать из FaceID. Если оба None - правка удаляется.
    arrival: str | None = Field(default=None, pattern=TIME_PATTERN)
    departure: str | None = Field(default=None, pattern=TIME_PATTERN)
    note: str | None = Field(default=None, max_length=255)


class ShiftFineUpsert(BaseModel):
    faceid_employee_id: str = Field(min_length=1, max_length=64)
    shift_date: date
    kind: FineKind
    # 0 или None = удалить штраф этого вида за смену
    amount: float | None = Field(default=None, ge=0, le=1e10)
    planned_start: str | None = Field(default=None, pattern=TIME_PATTERN)
    late_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    note: str | None = Field(default=None, max_length=255)


class PlanUpsert(BaseModel):
    faceid_employee_id: str = Field(min_length=1, max_length=64)
    # Можно задать сразу несколько дней (например, все понедельники периода)
    shift_dates: list[date] = Field(min_length=1, max_length=MAX_PERIOD_DAYS)
    # set - задать время; day_off - выходной; clear - убрать план табеля (вернуть «Смены»)
    mode: Literal["set", "day_off", "clear"]
    planned_start: str | None = Field(default=None, pattern=TIME_PATTERN)
    planned_end: str | None = Field(default=None, pattern=TIME_PATTERN)


class LinkUpsert(BaseModel):
    faceid_employee_id: str = Field(min_length=1, max_length=64)
    # None = отвязать
    employee_id: int | None = None


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
class _Plan:
    """План смены. start и end оба None = выходной."""
    start: str | None
    end: str | None
    source: PlanSource

    @property
    def day_off(self) -> bool:
        return self.start is None and self.end is None


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


def _has_missing_punch(raw: _RawDay | None, day: date, today: date) -> bool:
    """В FaceID есть отметки за смену, но нет прихода или ухода.

    Считается только по FaceID: ручная правка штраф не снимает.
    Смены за сегодня и вчера пропускаем - ночная смена может быть ещё не закрыта.
    """
    if raw is None or not raw.events or day >= today - timedelta(days=1):
        return False
    kinds = {kind for kind, _ in raw.events}
    if kinds != {"in", "out"}:
        return True
    session = _build_session(raw.events)
    # Последний вход остался без выхода
    return session.open_start is not None or not session.segments


def _plan_deviation(
    plan: _Plan | None, arrival: str | None, departure: str | None, is_open: bool
) -> tuple[int, int]:
    """Минуты опоздания и раннего ухода относительно графика."""
    if plan is None or plan.day_off:
        return 0, 0
    late = 0
    early = 0
    if plan.start and arrival:
        late = max(0, _shift_minutes(arrival) - _shift_minutes(plan.start))
    # Если смена открыта, последний уход может быть перерывом, а не концом смены
    if plan.end and departure and not is_open:
        early = max(0, _shift_minutes(plan.end) - _shift_minutes(departure))
    return late, early


def _auto_fines(late: int, early: int, fines: list[ShiftFineOut]) -> tuple[Decimal, Decimal]:
    """Автоштрафы по графику. Ручной штраф за опоздание или невыход заменяет автоматический."""
    kinds = {f.kind for f in fines}
    late_fine = Decimal(0)
    early_fine = Decimal(0)
    if late > LATE_GRACE_MINUTES and not kinds & {"late", "absence"}:
        late_fine = LATE_FINE_PER_MINUTE * late
    if early > 0 and "absence" not in kinds:
        early_fine = EARLY_LEAVE_FINE_PER_MINUTE * early
    return late_fine, early_fine


def _plan_fields(plan: _Plan | None) -> dict[str, object]:
    if plan is None:
        return {}
    return {
        "planned_start": plan.start,
        "planned_end": plan.end,
        "plan_source": plan.source,
        "day_off": plan.day_off,
    }


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


async def _load_shift_fines(
    main_db: AsyncSession, date_from: date, date_to: date
) -> dict[tuple[str, date], list[ShiftFineOut]]:
    rows = (
        await main_db.execute(
            select(AttendanceShiftFine).where(
                AttendanceShiftFine.shift_date >= date_from,
                AttendanceShiftFine.shift_date <= date_to,
            )
        )
    ).scalars().all()
    result: dict[tuple[str, date], list[ShiftFineOut]] = {}
    for row in rows:
        if row.kind not in ("late", "absence"):
            continue
        result.setdefault((row.faceid_employee_id, row.shift_date), []).append(
            ShiftFineOut(
                kind=row.kind,
                amount=float(row.amount),
                planned_start=row.planned_start,
                late_minutes=row.late_minutes,
                note=row.note,
            )
        )
    return result


async def _load_plans(
    main_db: AsyncSession, date_from: date, date_to: date, links: dict[int, str]
) -> dict[tuple[str, date], _Plan]:
    """План смен: сначала из «Смен» по привязке, затем поверх - план из табеля."""
    plans: dict[tuple[str, date], _Plan] = {}
    if links:
        shift_rows = (
            await main_db.execute(
                select(Shift)
                .where(
                    Shift.employee_id.in_(list(links)),
                    # shift_date хранится строкой YYYY-MM-DD, сравнение строк корректно
                    Shift.shift_date >= date_from.isoformat(),
                    Shift.shift_date <= date_to.isoformat(),
                )
                .order_by(Shift.shift_date, Shift.starts_at)
            )
        ).scalars().all()
        for row in shift_rows:
            day = _to_date(row.shift_date)
            start = _to_hhmm(row.starts_at)
            end = _to_hhmm(row.ends_at)
            if day is None or (start is None and end is None):
                continue
            key = (links[row.employee_id], day)
            existing = plans.get(key)
            if existing is None:
                plans[key] = _Plan(start=start, end=end, source="shifts")
            elif end and (existing.end is None or _shift_minutes(end) > _shift_minutes(existing.end)):
                # Несколько смен в день - от самого раннего начала до самого позднего конца
                existing.end = end

    table_rows = (
        await main_db.execute(
            select(AttendancePlannedShift).where(
                AttendancePlannedShift.shift_date >= date_from,
                AttendancePlannedShift.shift_date <= date_to,
            )
        )
    ).scalars().all()
    for row in table_rows:
        plans[(row.faceid_employee_id, row.shift_date)] = _Plan(
            start=row.planned_start, end=row.planned_end, source="tabel"
        )
    return plans


def _empty_day(fines: list[ShiftFineOut], plan: _Plan | None) -> PayrollDayOut:
    """День без отметок, но со штрафом (например, невыход) или с планом смены."""
    return PayrollDayOut(
        arrival=None,
        departure=None,
        faceid_arrival=None,
        faceid_departure=None,
        manual=False,
        counted=False,
        minutes=None,
        paid_minutes=None,
        overtime_minutes=0,
        open=False,
        segments=[],
        fines=fines,
        **_plan_fields(plan),
    )


def _build_days(
    employee_id: str,
    dates: list[date],
    faceid: dict[tuple[str, date], _RawDay],
    overrides: dict[tuple[str, date], AttendancePunchOverride],
    shift_fines: dict[tuple[str, date], list[ShiftFineOut]],
    plans: dict[tuple[str, date], _Plan],
    timeline: _RateTimeline,
) -> dict[str, PayrollDayOut]:
    result: dict[str, PayrollDayOut] = {}
    today = date.today()
    for day in dates:
        raw = faceid.get((employee_id, day))
        override = overrides.get((employee_id, day))
        fines = shift_fines.get((employee_id, day), [])
        plan = plans.get((employee_id, day))
        if raw is None and override is None:
            if fines or plan:
                result[day.isoformat()] = _empty_day(fines, plan)
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
        missing_punch = _has_missing_punch(raw, day, today)
        is_open = session.open_start is not None
        late, early = _plan_deviation(plan, arrival, departure, is_open)
        late_fine, early_fine = _auto_fines(late, early, fines)
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
            open=is_open,
            segments=[f"{start}-{end}" for start, end in session.segments],
            rate=float(timeline.on(day)),
            missing_punch=missing_punch,
            missing_punch_fine=float(MISSING_PUNCH_FINE) if missing_punch else 0,
            fines=fines,
            late_minutes=late,
            early_minutes=early,
            late_fine=float(late_fine),
            early_fine=float(early_fine),
            **_plan_fields(plan),
        )
    return result


def _sum_money(values: list[float]) -> Decimal:
    return sum((Decimal(str(v)) for v in values), Decimal(0))


# ── Основной расчёт (используется и роутом, и фоновой выгрузкой) ────────────

async def compute_payroll(
    date_from: date,
    date_to: date,
    attendance_db: AsyncSession,
    main_db: AsyncSession,
) -> PayrollOut:
    """Табель за период: оплата по часам по ставке дня смены, не более 10 часов за смену.

    Вынесено из get_payroll(), чтобы фоновая выгрузка в Google Sheets
    (app/tasks/google_sheets_sync.py) могла использовать тот же расчёт без
    HTTP-запроса и без зависимости require_manager.
    """
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
    shift_fines = await _load_shift_fines(main_db, date_from, date_to)

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
    links = {p.employee_id: eid for eid, p in profiles.items() if p.employee_id is not None}
    plans = await _load_plans(main_db, date_from, date_to, links)

    # В табель попадают те, у кого есть отметки/правки/премии/штрафы/план за период или задана ставка
    employee_ids = {eid for eid, _ in faceid} | {eid for eid, _ in overrides} | set(adjustments)
    employee_ids |= {eid for eid, _ in shift_fines}
    employee_ids |= {eid for eid, _ in plans}
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
        days = _build_days(employee_id, dates, faceid, overrides, shift_fines, plans, timeline)
        day_list = list(days.values())
        worked_days = sum(1 for d in day_list if d.counted)
        worked_minutes = sum(d.minutes or 0 for d in day_list)
        paid_minutes = sum(d.paid_minutes or 0 for d in day_list)
        overtime_minutes = sum(d.overtime_minutes for d in day_list)
        bonus = Decimal(adjustment.bonus) if adjustment else Decimal(0)
        fine = Decimal(adjustment.fine) if adjustment else Decimal(0)
        posuda = Decimal(adjustment.posuda) if adjustment else Decimal(0)
        posuda_auto = POSUDA_PER_SHIFT * worked_days
        posuda_total = posuda + posuda_auto
        missing_punch_count = sum(1 for d in day_list if d.missing_punch)
        missing_punch_fine = MISSING_PUNCH_FINE * missing_punch_count
        all_fines = [f for d in day_list for f in d.fines]
        shift_fines_total = _sum_money([f.amount for f in all_fines])
        late_fine_total = _sum_money([d.late_fine for d in day_list])
        early_fine_total = _sum_money([d.early_fine for d in day_list])
        # Каждая смена оплачивается по ставке своего дня, не более 10 часов
        pay = sum(
            (Decimal(str(d.rate)) * (d.paid_minutes or 0) / 60 for d in day_list),
            Decimal(0),
        ).quantize(MONEY_STEP)
        gross = pay + bonus
        deductions = (
            fine + missing_punch_fine + shift_fines_total + late_fine_total + early_fine_total + posuda_total
        )
        period_rates = {timeline.on(day) for day in dates}
        employees.append(
            PayrollEmployeeOut(
                employee_id=employee_id,
                name=display_name(employee_id),
                faceid_name=faceid_names.get(employee_id),
                position=profile.position if profile else None,
                linked_employee_id=profile.employee_id if profile else None,
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
                missing_punch_count=missing_punch_count,
                missing_punch_fine=float(missing_punch_fine),
                shift_fines_count=len(all_fines),
                shift_fines_total=float(shift_fines_total),
                late_count=sum(1 for d in day_list if d.late_fine > 0),
                late_fine_total=float(late_fine_total),
                early_count=sum(1 for d in day_list if d.early_fine > 0),
                early_fine_total=float(early_fine_total),
                posuda=float(posuda),
                posuda_auto=float(posuda_auto),
                posuda_total=float(posuda_total),
                gross=float(gross),
                net=float(gross - deductions),
            )
        )

    return PayrollOut(
        date_from=date_from,
        date_to=date_to,
        dates=[d.isoformat() for d in dates],
        max_paid_minutes_per_shift=MAX_PAID_MINUTES_PER_SHIFT,
        missing_punch_fine_amount=float(MISSING_PUNCH_FINE),
        posuda_per_shift=float(POSUDA_PER_SHIFT),
        late_fine_per_minute=float(LATE_FINE_PER_MINUTE),
        late_grace_minutes=LATE_GRACE_MINUTES,
        early_leave_fine_per_minute=float(EARLY_LEAVE_FINE_PER_MINUTE),
        employees=employees,
    )


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
    return await compute_payroll(date_from, date_to, attendance_db, main_db)


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


@router.put("/shift-fine")
async def upsert_shift_fine(
    body: ShiftFineUpsert,
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Штраф за смену (опоздание или невыход). Сумма 0 или пустая - штраф удаляется."""
    row = (
        await db.execute(
            select(AttendanceShiftFine).where(
                AttendanceShiftFine.faceid_employee_id == body.faceid_employee_id,
                AttendanceShiftFine.shift_date == body.shift_date,
                AttendanceShiftFine.kind == body.kind,
            )
        )
    ).scalar_one_or_none()

    if not body.amount:
        if row is not None:
            await db.delete(row)
            await db.commit()
        return {"status": "ok"}

    if row is None:
        row = AttendanceShiftFine(
            faceid_employee_id=body.faceid_employee_id,
            shift_date=body.shift_date,
            kind=body.kind,
        )
        db.add(row)
    row.amount = Decimal(str(body.amount))
    row.planned_start = body.planned_start if body.kind == "late" else None
    row.late_minutes = body.late_minutes if body.kind == "late" else None
    row.note = (body.note or "").strip() or None
    await db.commit()
    return {"status": "ok"}


@router.put("/plan")
async def upsert_plan(
    body: PlanUpsert,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """График в табеле: время прихода/ухода, выходной или сброс к плану из «Смен»."""
    if body.mode == "set" and body.planned_start is None and body.planned_end is None:
        raise HTTPException(status_code=422, detail="Укажите время прихода или ухода")

    dates = sorted(set(body.shift_dates))
    existing = {
        row.shift_date: row
        for row in (
            await db.execute(
                select(AttendancePlannedShift).where(
                    AttendancePlannedShift.faceid_employee_id == body.faceid_employee_id,
                    AttendancePlannedShift.shift_date.in_(dates),
                )
            )
        ).scalars().all()
    }
    start = body.planned_start if body.mode == "set" else None
    end = body.planned_end if body.mode == "set" else None

    for day in dates:
        row = existing.get(day)
        if body.mode == "clear":
            if row is not None:
                await db.delete(row)
            continue
        if row is None:
            row = AttendancePlannedShift(faceid_employee_id=body.faceid_employee_id, shift_date=day)
            db.add(row)
        row.planned_start = start
        row.planned_end = end

    # entity_id - BigInteger, а ID FaceID строковый, поэтому он в metadata
    await log_action(
        db,
        actor_id=current.id,
        action=f"attendance.plan_{body.mode}",
        entity_type="attendance_plan",
        entity_id=None,
        metadata={
            "faceid_employee_id": body.faceid_employee_id,
            "dates": [d.isoformat() for d in dates],
            "planned_start": start,
            "planned_end": end,
        },
    )
    await db.commit()
    return {"status": "ok"}


@router.put("/link")
async def upsert_link(
    body: LinkUpsert,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Привязка сотрудника FaceID к сотруднику системы, чтобы брать график из «Смен»."""
    if body.employee_id is not None:
        employee = await db.get(Employee, body.employee_id)
        if employee is None:
            raise HTTPException(status_code=404, detail="Сотрудник не найден")
        taken = (
            await db.execute(
                select(AttendanceEmployeeProfile).where(
                    AttendanceEmployeeProfile.employee_id == body.employee_id,
                    AttendanceEmployeeProfile.faceid_employee_id != body.faceid_employee_id,
                )
            )
        ).scalar_one_or_none()
        if taken is not None:
            raise HTTPException(
                status_code=409, detail="Этот сотрудник уже привязан к другому человеку из FaceID"
            )

    row = (
        await db.execute(
            select(AttendanceEmployeeProfile).where(
                AttendanceEmployeeProfile.faceid_employee_id == body.faceid_employee_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = AttendanceEmployeeProfile(faceid_employee_id=body.faceid_employee_id)
        db.add(row)
    previous = row.employee_id
    row.employee_id = body.employee_id

    await log_action(
        db,
        actor_id=current.id,
        action="attendance.employee_linked" if body.employee_id else "attendance.employee_unlinked",
        entity_type="employee",
        entity_id=body.employee_id or previous,
        metadata={"faceid_employee_id": body.faceid_employee_id, "previous_employee_id": previous},
    )
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
