from sqlalchemy import BigInteger, String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import datetime


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Tashkent")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
