from sqlalchemy import BigInteger, String, Boolean, DateTime, func, ForeignKey, ARRAY, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import datetime


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        # Enforce uniqueness at the DB level so that concurrent inserts
        # cannot produce duplicate invite codes even if the application-level
        # retry loop has a race window.
        UniqueConstraint("invite_code", name="uq_employees_invite_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    invite_code: Mapped[str] = mapped_column(String(8), nullable=False)
    # Set once the employee links their account in the Telegram bot via /start + invite code
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    primary_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    additional_branch_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    hired_at: Mapped[str | None] = mapped_column(String(10))  # YYYY-MM-DD
    # Preferred UI language for the Telegram bot: "ru" | "uz" | "en"
    preferred_language: Mapped[str] = mapped_column(String(5), nullable=False, default="ru")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EmployeeAccount(Base):
    """\u0421\u0432\u044f\u0437\u044c employee <-> user (\u0432\u0435\u0431-\u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u0430)."""
    __tablename__ = "employee_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
