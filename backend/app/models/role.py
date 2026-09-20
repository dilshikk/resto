from sqlalchemy import Integer, String, SmallInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_ru: Mapped[str] = mapped_column(String(100), nullable=False)
    name_uz: Mapped[str | None] = mapped_column(String(100))
    name_en: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # staff | management

    # ── Hierarchy ────────────────────────────────────────────────────────────
    # Used ONLY to enforce that a manager cannot assign a role with a higher
    # level than their own.  0 = staff, 1 = manager, 2 = supervisor, 3 = director.
    permission_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    # ── Branch visibility ────────────────────────────────────────────────────
    # When True the role holder can see and act on employees / checklists /
    # photos across ALL branches, not just the ones they are assigned to.
    # Deliberately separate from permission_level so a future role like
    # "regional auditor" can have full branch visibility (True) at a low
    # hierarchy level (0) without changing any business-logic thresholds.
    can_access_all_branches: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
