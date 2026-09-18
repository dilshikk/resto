from sqlalchemy import BigInteger, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import datetime


class Notification(Base):
    """Уведомление сотруднику (напоминание, просрочка, эскалация, назначение проблемы)."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recipient_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)  # reminder|overdue|escalation|issue_assigned
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str | None] = mapped_column(String(500))
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
