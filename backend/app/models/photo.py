from sqlalchemy import BigInteger, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import datetime


class Photo(Base):
    """Фотоподтверждение выполнения пункта чек-листа (раздел 13.3 ТЗ)."""
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    checklist_item_id: Mapped[int] = mapped_column(
        ForeignKey("checklist_items.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
