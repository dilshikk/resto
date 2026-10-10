from sqlalchemy import BigInteger, Date, String, Numeric, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import datetime
from decimal import Decimal


class AttendanceRate(Base):
    """Текущая ставка за час для сотрудника FaceID (имя колонки rate_per_shift историческое)."""
    __tablename__ = "attendance_rates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    faceid_employee_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    rate_per_shift: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="UZS")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AttendanceRateHistory(Base):
    """История ставок: ставка действует с effective_from до следующей записи.

    Табель берёт для каждой смены ставку, действовавшую в день смены,
    поэтому изменение ставки не пересчитывает прошлые периоды.
    """
    __tablename__ = "attendance_rate_history"
    __table_args__ = (
        UniqueConstraint("faceid_employee_id", "effective_from", name="uq_attendance_rate_history_employee_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    faceid_employee_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="UZS")
    effective_from: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
