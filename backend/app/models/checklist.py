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
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Optional link to a MADO standard (e.g. "SERVICE-04"), see app/models/standard.py
    standard_code: Mapped[str | None] = mapped_column(ForeignKey("standards.code"), nullable=True)


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
    # Deadline tracking fields — NULL for checklists created before migration 011.
    # started_at: when the checklist was created (set on insert, not updated).
    # due_at:     calculated deadline (started_at + template.deadline_offset_minutes).
    # completed_at: set when status transitions to "completed".
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    checklist_id: Mapped[int] = mapped_column(
        ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)  # denormalized
    description: Mapped[str | None] = mapped_column(String(500))  # denormalized
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # is_skipped: True only when is_required=False and the employee chose to skip this step.
    # Required items (is_required=True) can never be skipped.
    is_skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(500))
    # denormalized from the template item, so historical checklists keep their standard link
    standard_code: Mapped[str | None] = mapped_column(ForeignKey("standards.code"), nullable=True)
