from sqlalchemy import BigInteger, String, Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import datetime


class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    # None = applies to all branches
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    # Optional deadline: minutes after checklist creation until the due_at is set.
    # None means this template has no deadline (deadline_status will always be None).
    deadline_offset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChecklistTemplateItem(Base):
    __tablename__ = "checklist_template_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("checklist_templates.id", ondelete="CASCADE"), nullable=False
    )
    # Russian title (required, used as default fallback)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    # Localized titles (optional, fallback to title if empty)
    title_uz: Mapped[str | None] = mapped_column(String(300))
    title_en: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(String(500))
    description_uz: Mapped[str | None] = mapped_column(String(500))
    description_en: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Optional link to a MADO standard (e.g. "SERVICE-04"), see app/models/standard.py
    standard_code: Mapped[str | None] = mapped_column(ForeignKey("standards.code"), nullable=True)
    # Confirmation requirements — enforced at item-completion time.
    requires_photo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # How the employee should complete this item in the Telegram bot.
    # Supported: checkbox | number | temperature | text | photo | photo_geo | yes_no
    task_type: Mapped[str] = mapped_column(String(20), nullable=False, default="checkbox")


class Checklist(Base):
    __tablename__ = "checklists"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("checklist_templates.id"), nullable=False)
    template_name: Mapped[str] = mapped_column(String(150), nullable=False)  # denormalized
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    shift: Mapped[str] = mapped_column(String(20), nullable=False, default="morning")
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_by_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    overdue_manager_notified_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    overdue_supervisor_notified_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    checklist_id: Mapped[int] = mapped_column(
        ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False
    )
    # Russian title (required, used as default fallback)
    title: Mapped[str] = mapped_column(String(300), nullable=False)  # denormalized
    # Localized titles (denormalized from template item at checklist creation)
    title_uz: Mapped[str | None] = mapped_column(String(300))
    title_en: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(String(500))  # denormalized
    description_uz: Mapped[str | None] = mapped_column(String(500))
    description_en: Mapped[str | None] = mapped_column(String(500))
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(500))
    standard_code: Mapped[str | None] = mapped_column(ForeignKey("standards.code"), nullable=True)
    requires_photo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # How the employee should complete this item in the Telegram bot.
    # Denormalized from the template item at checklist-creation time.
    # Supported: checkbox | number | temperature | text | photo | photo_geo | yes_no
    task_type: Mapped[str] = mapped_column(String(20), nullable=False, default="checkbox")
