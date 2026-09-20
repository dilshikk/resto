from sqlalchemy import Integer, String, SmallInteger
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
    permission_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
