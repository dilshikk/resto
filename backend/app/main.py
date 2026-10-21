import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.rate_limit import limiter, login_attempt_tracker
from app.tasks.revoked_token_cleanup import run_revoked_token_cleanup_loop
from app.tasks.checklist_scheduler import run_checklist_scheduler_loop
from app.tasks.overdue_escalation import run_overdue_escalation_loop
from app.tasks.login_attempt_cleanup import run_login_attempt_cleanup_loop
from app.tasks.schedule_generator import run_schedule_generator_loop
from app.tasks.google_sheets_sync import run_google_sheets_sync_loop
from app.routers import (
    auth,
    branches,
    roles,
    employees,
    employee_removal,
    templates,
    checklists,
    checklist_complete_report,
    analytics,
    issues,
    shifts,
    notifications,
    standards,
    audit_logs,
    bot,
    bot_complete,
    bot_today,
    schedules,
)
from app.routers import attendance
from app.routers import attendance_import
from app.routers import attendance_rates
from app.routers import attendance_payroll
from app.routers import attendance_card_mappings


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    login_attempt_tracker.configure(AsyncSessionLocal)

    cleanup_task = asyncio.create_task(run_revoked_token_cleanup_loop(), name="revoked_token_cleanup")
    scheduler_task = asyncio.create_task(run_checklist_scheduler_loop(), name="checklist_scheduler")
    escalation_task = asyncio.create_task(run_overdue_escalation_loop(), name="overdue_escalation")
    login_cleanup_task = asyncio.create_task(run_login_attempt_cleanup_loop(), name="login_attempt_cleanup")
    schedule_task = asyncio.create_task(run_schedule_generator_loop(), name="schedule_generator")
    # Опционально: выгрузка табеля FaceID в Google Sheets раз в сутки.
    # Сама задача ничего не делает, если GOOGLE_SERVICE_ACCOUNT_JSON / GOOGLE_SHEET_ID не заданы.
    google_sheets_task = asyncio.create_task(run_google_sheets_sync_loop(), name="google_sheets_sync")

    try:
        yield
    finally:
        tasks = (
            cleanup_task, scheduler_task, escalation_task,
            login_cleanup_task, schedule_task, google_sheets_task,
        )
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="MADO Checklist API",
    version="1.12.0",
    description="Система контроля операционных стандартов ресторанов MADO",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(branches.router, prefix="/api/v1")
app.include_router(roles.router, prefix="/api/v1")
app.include_router(employees.router, prefix="/api/v1")
app.include_router(employee_removal.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(checklist_complete_report.router, prefix="/api/v1")
app.include_router(checklists.router, prefix="/api/v1")
app.include_router(schedules.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(issues.router, prefix="/api/v1")
app.include_router(shifts.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(standards.router, prefix="/api/v1")
app.include_router(audit_logs.router, prefix="/api/v1")
app.include_router(bot_today.router, prefix="/api/v1")
app.include_router(bot.router, prefix="/api/v1")
app.include_router(bot_complete.router, prefix="/api/v1")
# FaceID посещаемость — отдельная БД (ATTENDANCE_DATABASE_URL)
app.include_router(attendance.router, prefix="/api/v1")
# Импорт событий FaceID из JSON терминала (вставка в странице «Посещаемость»)
app.include_router(attendance_import.router, prefix="/api/v1")
# Ставки сотрудников FaceID — основная БД
app.include_router(attendance_rates.router, prefix="/api/v1")
# Табель и расчёт зарплаты по FaceID (ручные правки в основной БД)
app.include_router(attendance_payroll.router, prefix="/api/v1")
# Привязка зашифрованных ID карт терминала к сотрудникам FaceID (основная БД)
app.include_router(attendance_card_mappings.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mado-checklist-backend"}
