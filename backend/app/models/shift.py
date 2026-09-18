from sqlalchemy import BigInteger, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import datetime


class Shift(Base):
    """Плановая или фактическая смена сотрудника (раздел 13.3 ТЗ)."""
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    shift_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD, local calendar day
    starts_at: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM local
    ends_at: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM local
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")  # planned|active|completed|no_show
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
