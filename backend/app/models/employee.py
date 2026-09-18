from sqlalchemy import BigInteger, String, Boolean, DateTime, func, ForeignKey, ARRAY, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import datetime


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    invite_code: Mapped[str] = mapped_column(String(8), nullable=False)
    primary_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    additional_branch_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    hired_at: Mapped[str | None] = mapped_column(String(10))  # YYYY-MM-DD
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EmployeeAccount(Base):
    """Связь employee <-> user (веб-аккаунт менеджера)."""
    __tablename__ = "employee_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
