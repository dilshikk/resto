"""
Импорт событий FaceID из JSON, который отдаёт терминал (Hikvision ISAPI, AcsEvent).

Менеджер вставляет JSON в окно на странице «Посещаемость (FaceID)», события
добавляются в public.access_logs базы FaceID.

Правила:
- Берутся только события checkIn (вход) и checkOut (выход).
- Время приводится к местному (Ташкент, UTC+5): в базе хранится местное время.
- Отметка пропускается, если у сотрудника уже есть событие в ту же дату и минуту
  (так же, как в SQL-импорте из Excel), поэтому повторная вставка ничего не дублирует.
- Если терминал отдал ID сотрудника в зашифрованном виде (длинная hex-строка),
  такие события не импортируются: их нельзя связать с сотрудниками в базе.
- auth_type = 'json_import' - метка, чтобы импорт можно было найти и откатить:
  DELETE FROM public.access_logs WHERE auth_type = 'json_import';
"""
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.attendance_database import get_attendance_db
from app.auth import require_manager
from app.models.employee import Employee

router = APIRouter(prefix="/attendance-import", tags=["attendance"])

# Ташкент без перехода на летнее время
TASHKENT = timezone(timedelta(hours=5))
AUTH_TYPE = "json_import"
MAX_EVENTS = 20000
MAX_ID_LENGTH = 32
ID_PATTERN = re.compile(r"^[A-Za-z0-9]+$")
DIRECTIONS = {"checkIn": "in", "checkOut": "out"}


# ── Схемы ────────────────────────────────────────────────────────────────────

class AcsInfo(BaseModel):
    # Остальные поля терминала (карта, фото, имя) нам не нужны
    model_config = ConfigDict(extra="ignore")

    time: str | None = None
    employeeNoString: str | None = None
    attendanceStatus: str | None = None


class AcsEventBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    InfoList: list[AcsInfo] = Field(default_factory=list, max_length=MAX_EVENTS)


class ImportJsonBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    AcsEvent: AcsEventBody


class SkippedReason(BaseModel):
    reason: str
    count: int


class ImportResult(BaseModel):
    total: int
    inserted: int
    duplicates: int
    skipped: int
    skipped_reasons: list[SkippedReason]
    date_from: str | None
    date_to: str | None


@router.post("/json", response_model=ImportResult)
async def import_json(
    body: ImportJsonBody,
    _current: Employee = Depends(require_manager),
    attendance_db: AsyncSession = Depends(get_attendance_db),
):
    """Добавляет события FaceID из JSON терминала в базу посещаемости."""
    items = body.AcsEvent.InfoList
    skipped: Counter[str] = Counter()
    events: dict[tuple[str, str, str], dict[str, str]] = {}
    duplicates = 0

    for item in items:
        event, reason = _parse_event(item)
        if event is None:
            skipped[reason] += 1
            continue
        key = (event["employee_id"], event["access_date"], event["access_time"][:5])
        if key in events:
            duplicates += 1
            continue
        events[key] = event

    new_events: list[dict[str, str]] = []
    if events:
        existing = await _existing_keys(attendance_db, events)
        duplicates += len(events) - sum(1 for k in events if k not in existing)
        new_events = sorted(
            (e for k, e in events.items() if k not in existing),
            key=lambda e: (e["access_date"], e["access_time"], e["employee_id"]),
        )

    if new_events:
        await _insert_events(attendance_db, new_events)
        await attendance_db.commit()

    dates = sorted(e["access_date"] for e in events.values())
    return ImportResult(
        total=len(items),
        inserted=len(new_events),
        duplicates=duplicates,
        skipped=sum(skipped.values()),
        skipped_reasons=[SkippedReason(reason=r, count=c) for r, c in skipped.most_common()],
        date_from=dates[0] if dates else None,
        date_to=dates[-1] if dates else None,
    )


# ── Разбор событий ───────────────────────────────────────────────────────────

def _parse_event(item: AcsInfo) -> tuple[dict[str, str] | None, str]:
    """Возвращает (событие, "") или (None, причина пропуска)."""
    employee_id = (item.employeeNoString or "").strip()
    if not employee_id:
        return None, "Нет ID сотрудника"
    if len(employee_id) > MAX_ID_LENGTH:
        return None, "ID сотрудника зашифрован терминалом"
    if not ID_PATTERN.match(employee_id):
        return None, "Некорректный ID сотрудника"

    direction = DIRECTIONS.get(item.attendanceStatus or "")
    if direction is None:
        return None, "Не вход и не выход"

    moment = _parse_time(item.time)
    if moment is None:
        return None, "Некорректное время"

    return {
        "employee_id": employee_id,
        "access_date": moment.strftime("%Y-%m-%d"),
        "access_time": moment.strftime("%H:%M:%S"),
        # С указанием пояса, чтобы колонка любого типа получила местное время
        "access_datetime": moment.isoformat(sep=" "),
        "direction": direction,
    }, ""


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=TASHKENT)
    return moment.astimezone(TASHKENT)


# ── Работа с базой ───────────────────────────────────────────────────────────

async def _existing_keys(
    db: AsyncSession, events: dict[tuple[str, str, str], dict[str, str]]
) -> set[tuple[str, str, str]]:
    """Отметки, которые уже есть в базе (сотрудник + дата + минута)."""
    ids = sorted({k[0] for k in events})
    dates = sorted({k[1] for k in events})
    result = await db.execute(
        text(
            """
            SELECT employee_id::text AS employee_id,
                   access_date::text AS access_date,
                   left(access_time::text, 5) AS minute
            FROM public.access_logs
            WHERE employee_id::text = ANY(CAST(:ids AS text[]))
              AND access_date::text BETWEEN :date_from AND :date_to
            """
        ),
        {"ids": ids, "date_from": dates[0], "date_to": dates[-1]},
    )
    return {(r.employee_id, r.access_date, r.minute) for r in result}


async def _insert_events(db: AsyncSession, events: list[dict[str, str]]) -> None:
    """Вставляет события, приводя значения к фактическим типам колонок access_logs."""
    columns = (
        await db.execute(
            text(
                """
                SELECT a.attname AS name,
                       format_type(a.atttypid, a.atttypmod) AS type,
                       (a.attidentity <> '' OR d.adbin IS NOT NULL) AS has_default
                FROM pg_attribute a
                LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                WHERE a.attrelid = 'public.access_logs'::regclass
                  AND a.attnum > 0 AND NOT a.attisdropped
                """
            )
        )
    ).all()
    types = {c.name: c.type for c in columns}
    id_needs_value = "id" in types and not next(c.has_default for c in columns if c.name == "id")

    wanted = ["employee_id", "access_date", "access_time", "access_datetime", "direction", "auth_type"]
    used = [c for c in wanted if c in types]
    if id_needs_value:
        used.insert(0, "id")

    # Имена колонок - из белого списка, типы - из каталога базы, значения - параметрами
    column_sql = ", ".join(used)
    values_sql = ", ".join(f"CAST(:{c} AS {types[c]})" for c in used)

    next_id = 0
    if id_needs_value:
        next_id = (await db.execute(text("SELECT COALESCE(MAX(id), 0) FROM public.access_logs"))).scalar_one()

    rows = []
    for index, event in enumerate(events, start=1):
        row = {c: event.get(c, AUTH_TYPE if c == "auth_type" else None) for c in used}
        if id_needs_value:
            row["id"] = next_id + index
        rows.append(row)

    await db.execute(text(f"INSERT INTO public.access_logs ({column_sql}) VALUES ({values_sql})"), rows)
