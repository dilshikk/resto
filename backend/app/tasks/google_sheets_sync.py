"""
Ежедневная выгрузка табеля FaceID в Google Sheets.

Что делает
──────────
Раз в сутки (в GOOGLE_SHEETS_SYNC_HOUR_UTC по UTC) берёт табель за текущий
календарный месяц (тот же расчёт, что видит менеджер на экране «Табель») и
полностью перезаписывает два листа в указанной Google-таблице:

  "Check"   — сырые данные по каждому сотруднику и дню: приход, уход, часы
              (как лист "Check" в примере пользователя — Приход/Уход/Часы
              для каждой даты).
  "Payroll" — сводная страница: по каждому сотруднику и дню итоговая сумма
              к выдаче (gross/net) с привязкой к ставке и штрафам.

Почему полная перезапись, а не построчное добавление
──────────────────────────────────────────────────────
Табель FaceID пересчитывается заново при каждом запуске (ручные правки,
штрафы, ставки меняются задним числом). Добавление строк привело бы к
дублям и расхождению с тем, что видно в приложении. Перезапись двух
листов гарантирует, что Google-таблица всегда отражает текущее состояние
табеля, как и веб-панель.

Доступ к Google Sheets
───────────────────────
Используется сервисный аккаунт Google (GOOGLE_SERVICE_ACCOUNT_JSON — JSON
ключ в одну строку) с доступом на редактирование таблицы с ID
GOOGLE_SHEET_ID (эту таблицу нужно явно "расшарить" на email сервисного
аккаунта в самом Google Sheets).

Если GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_ID или ATTENDANCE_DATABASE_URL
не заданы, цикл просто ничего не делает (как остальные опциональные
фоновые задачи в проекте, например schedule_generator).
"""

import asyncio
import json
import logging
from datetime import date, datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

from app.attendance_database import attendance_session, attendance_sync_enabled
from app.config import settings
from app.database import AsyncSessionLocal
from app.routers.attendance_payroll import PayrollOut, compute_payroll

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

_CHECK_SHEET_TITLE = "Check"
_PAYROLL_SHEET_TITLE = "Payroll"
_CHECK_HEADER = ["Сотрудник", "ID FaceID", "Дата", "Приход", "Уход", "Часы"]
_PAYROLL_HEADER = [
    "Сотрудник", "ID FaceID", "Отработано дней", "Оплачиваемые часы",
    "Переработка (часы)", "Ставка/час", "Начислено", "Штрафы и вычеты",
    "К выдаче", "Валюта",
]


def _sync_enabled() -> bool:
    return bool(
        settings.GOOGLE_SERVICE_ACCOUNT_JSON
        and settings.GOOGLE_SHEET_ID
        and attendance_sync_enabled()
    )


def _open_sheet() -> gspread.Spreadsheet:
    info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)  # type: ignore[arg-type]
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(settings.GOOGLE_SHEET_ID)  # type: ignore[arg-type]


def _get_or_create_worksheet(sheet: gspread.Spreadsheet, title: str, cols: int) -> gspread.Worksheet:
    try:
        return sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=title, rows=100, cols=cols)


def _check_rows(payroll: PayrollOut) -> list[list[object]]:
    rows: list[list[object]] = [_CHECK_HEADER]
    for emp in payroll.employees:
        for day_str in payroll.dates:
            day = emp.days.get(day_str)
            if day is None:
                continue
            # Пропускаем дни совсем без отметок и без часов — не захламляем лист
            if day.arrival is None and day.departure is None and not day.counted:
                continue
            rows.append(
                [
                    emp.name,
                    emp.employee_id,
                    day_str,
                    day.arrival or "",
                    day.departure or "",
                    round((day.minutes or 0) / 60, 2) if day.minutes else "",
                ]
            )
    return rows


def _payroll_rows(payroll: PayrollOut) -> list[list[object]]:
    rows: list[list[object]] = [_PAYROLL_HEADER]
    for emp in payroll.employees:
        deductions = round(emp.gross - emp.net, 2)
        rows.append(
            [
                emp.name,
                emp.employee_id,
                emp.worked_days,
                emp.hours,
                emp.overtime_hours,
                emp.rate_per_hour,
                round(emp.gross, 2),
                deductions,
                round(emp.net, 2),
                emp.currency,
            ]
        )
    return rows


def _write_rows(ws: gspread.Worksheet, rows: list[list[object]]) -> None:
    ws.clear()
    if rows:
        ws.update(values=rows, range_name="A1")


async def run_google_sheets_export() -> None:
    """Пересчитывает табель за текущий месяц и перезаписывает листы Check и Payroll."""
    if not _sync_enabled():
        return

    today = date.today()
    date_from = today.replace(day=1)

    attendance_db = await attendance_session()
    try:
        async with AsyncSessionLocal() as main_db:
            payroll = await compute_payroll(date_from, today, attendance_db, main_db)
    finally:
        await attendance_db.close()

    def _export() -> None:
        sheet = _open_sheet()
        check_ws = _get_or_create_worksheet(sheet, _CHECK_SHEET_TITLE, len(_CHECK_HEADER))
        payroll_ws = _get_or_create_worksheet(sheet, _PAYROLL_SHEET_TITLE, len(_PAYROLL_HEADER))
        _write_rows(check_ws, _check_rows(payroll))
        _write_rows(payroll_ws, _payroll_rows(payroll))

    # gspread делает блокирующие HTTP-запросы — выполняем их в отдельном потоке,
    # чтобы не блокировать событийный цикл остального приложения.
    await asyncio.to_thread(_export)
    logger.info(
        "google_sheets_sync: exported %d employee row(s) for %s..%s",
        len(payroll.employees), date_from.isoformat(), today.isoformat(),
    )


async def run_google_sheets_sync_loop() -> None:
    """Запускает run_google_sheets_export() один раз в сутки в заданный час UTC."""
    if not settings.GOOGLE_SERVICE_ACCOUNT_JSON or not settings.GOOGLE_SHEET_ID:
        logger.info("google_sheets_sync: disabled (GOOGLE_SERVICE_ACCOUNT_JSON/GOOGLE_SHEET_ID not set)")
        return

    trigger_hour = settings.GOOGLE_SHEETS_SYNC_HOUR_UTC

    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=trigger_hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run.replace(day=next_run.day)
            from datetime import timedelta
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()
        logger.info(
            "google_sheets_sync: next export at %s UTC (in %.0f s)",
            next_run.strftime("%Y-%m-%d %H:%M"), wait_seconds,
        )

        try:
            await asyncio.sleep(wait_seconds)
        except asyncio.CancelledError:
            raise

        try:
            await run_google_sheets_export()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("google_sheets_sync: export failed; will retry tomorrow")

        await asyncio.sleep(24 * 3600)
