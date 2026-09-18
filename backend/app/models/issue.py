from sqlalchemy import BigInteger, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY
from app.database import Base
import datetime


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    # checklist_item_id link (optional)
    checklist_id: Mapped[int | None] = mapped_column(ForeignKey("checklists.id"))
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    # JSON-array of CDN/base64 photo URLs stored as text[]
    photo_urls: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    reported_by_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    assigned_to_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IssueComment(Base):
    __tablename__ = "issue_comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    author_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
