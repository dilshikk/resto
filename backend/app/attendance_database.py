"""
Отдельное подключение к базе данных FaceID (attendance).

URL задаётся через переменную окружения ATTENDANCE_DATABASE_URL.
Если переменная не задана — соединение не создаётся и эндпоинты
вернут 503 Service Unavailable.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from app.config import settings

_attendance_engine = None
_AttendanceSession = None

if settings.ATTENDANCE_DATABASE_URL:
    _attendance_engine = create_async_engine(
        settings.ATTENDANCE_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    _AttendanceSession = async_sessionmaker(
        _attendance_engine, expire_on_commit=False
    )


async def get_attendance_db() -> AsyncGenerator[AsyncSession, None]:
    if _AttendanceSession is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="ATTENDANCE_DATABASE_URL не задан. Посещаемость недоступна.",
        )
    async with _AttendanceSession() as session:
        yield session


def attendance_sync_enabled() -> bool:
    """True, если ATTENDANCE_DATABASE_URL задан и соединение создано."""
    return _AttendanceSession is not None


async def attendance_session() -> AsyncSession:
    """
    Открывает сессию базы FaceID для использования вне FastAPI-эндпоинтов
    (например, в фоновых задачах планировщика). В отличие от get_attendance_db,
    это обычная функция, а не generator-зависимость — вызывающий код сам
    должен закрыть сессию (`await session.close()`).
    """
    if _AttendanceSession is None:
        raise RuntimeError("ATTENDANCE_DATABASE_URL не задан")
    return _AttendanceSession()
