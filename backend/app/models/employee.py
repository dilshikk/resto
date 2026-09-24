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
    # Nullable: a self-registered (Telegram-first) employee starts with
    # status="pending" and no role/branch until a manager approves them
    # via POST /employees/{id}/approve.
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # Nullable for the same reason as role_id — self-registered employees
    # never go through the /bot/link invite-code flow, so they have none.
    invite_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Set once the employee links their account in the Telegram bot, either
    # via /start + invite code (manager-first flow) or by self-registering
    # (bot-first flow — see POST /bot/register).
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    # Telegram @username captured at self-registration time. Display-only,
    # never used for authentication (telegram_id is the source of truth).
    telegram_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary_branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    additional_branch_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    hired_at: Mapped[str | None] = mapped_column(String(10))  # YYYY-MM-DD
    # Preferred UI language for the Telegram bot: "ru" | "uz" | "en"
    preferred_language: Mapped[str] = mapped_column(String(5), nullable=False, default="ru")
    # Last time the employee interacted with the bot (checklist toggle/skip,
    # photo upload, etc). Updated opportunistically, not on every request.
    last_activity_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ── Per-employee bot credential ───────────────────────────────────────────
    # SHA-256 hex digest of the per-employee bot session token issued on
    # /bot/link.  The bot stores the plaintext; we only keep the hash so that
    # a database dump does NOT expose usable credentials.
    # NULL means the employee has never linked via the bot (or was reset).
    bot_session_token_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )


class EmployeeAccount(Base):
    """Связь employee <-> user (веб-аккаунт менеджера)."""
    __tablename__ = "employee_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
