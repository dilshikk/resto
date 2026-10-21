import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
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


class AttendanceShiftFine(Base):
    """Ручной штраф за конкретную смену: опоздание или невыход.

    kind: "late" (опоздание) | "absence" (невыход на смену).
    Для опоздания хранится плановое начало смены и минуты опоздания.
    """
    __tablename__ = "attendance_shift_fines"
    __table_args__ = (
        UniqueConstraint(
            "faceid_employee_id", "shift_date", "kind", name="uq_attendance_shift_fine_employee_date_kind"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    faceid_employee_id: Mapped[str] = mapped_column(String(64), nullable=False)
    shift_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    planned_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    late_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AttendancePlannedShift(Base):
    """План смены, заданный в табеле: во сколько должен прийти и уйти.

    Имеет приоритет над планом из раздела «Смены».
    Оба времени пустые = выходной (план из «Смен» на этот день игнорируется).
    """
    __tablename__ = "attendance_planned_shifts"
    __table_args__ = (
        UniqueConstraint("faceid_employee_id", "shift_date", name="uq_attendance_plan_employee_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    faceid_employee_id: Mapped[str] = mapped_column(String(64), nullable=False)
    shift_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    planned_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    planned_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
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
    """Дополнительные данные сотрудника FaceID: должность, привязка к сотруднику системы
    и статус увольнения.
    """
    __tablename__ = "attendance_employee_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    faceid_employee_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Сотрудник системы: по нему берётся план из раздела «Смены» (migration 028)
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    # Дата увольнения (migration 030). NULL - сотрудник активен (работает).
    # Если задана, сотрудник скрывается из табеля в периодах без реальных
    # отметок/начислений за него (чтобы не мешал искать текущих сотрудников),
    # но остаётся виден там, где есть данные - для сверки при увольнении.
    terminated_from: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
