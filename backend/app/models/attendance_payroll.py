import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AttendancePunchOverride(Base):
    """Ручная правка прихода/ухода за смену. NULL = взять время из FaceID."""
    __tablename__ = "attendance_punch_overrides"
    __table_args__ = (
        UniqueConstraint("faceid_employee_id", "shift_date", name="uq_attendance_punch_employee_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    faceid_employee_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Дата НАЧАЛА смены (ночной уход относится к дню прихода)
    shift_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    arrival: Mapped[str | None] = mapped_column(String(5), nullable=True)
    departure: Mapped[str | None] = mapped_column(String(5), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AttendancePayrollAdjustment(Base):
    """Премия, штраф и вычет за посуду для сотрудника за конкретный период."""
    __tablename__ = "attendance_payroll_adjustments"
    __table_args__ = (
        UniqueConstraint(
            "faceid_employee_id", "date_from", "date_to",
            name="uq_attendance_adjustment_employee_period",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    faceid_employee_id: Mapped[str] = mapped_column(String(64), nullable=False)
    date_from: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    date_to: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    bonus: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    fine: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    posuda: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AttendanceEmployeeProfile(Base):
    """Дополнительные данные сотрудника FaceID (должность для табеля)."""
    __tablename__ = "attendance_employee_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    faceid_employee_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
