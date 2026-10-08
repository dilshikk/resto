from sqlalchemy import BigInteger, String, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import datetime
from decimal import Decimal


class AttendanceRate(Base):
    """Ставка за смену для сотрудника FaceID."""
    __tablename__ = "attendance_rates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    faceid_employee_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    rate_per_shift: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="UZS")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
