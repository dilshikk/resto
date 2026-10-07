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
