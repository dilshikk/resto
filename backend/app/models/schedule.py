import datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Time, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChecklistSchedule(Base):
    """
    Recurring checklist: created once, generates one checklist per matching
    day between start_date and end_date (inclusive; end_date None = forever).
    window_start / window_end are local times of the branch timezone.
    If window_end <= window_start the window ends on the next day.
    """

    __tablename__ = "checklist_schedules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("checklist_templates.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    shift: Mapped[str] = mapped_column(String(20), nullable=False, default="morning")
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # ISO weekdays: 1 = Monday ... 7 = Sunday
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=lambda: [1, 2, 3, 4, 5, 6, 7])
    window_start: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    window_end: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
