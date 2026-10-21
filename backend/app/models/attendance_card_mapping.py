import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AttendanceCardMapping(Base):
    """Сопоставление зашифрованного ID, присланного терминалом, с обычным
    faceid_employee_id (как в access_logs.employee_id для сотрудников,
    которые проходят по лицу).

    Нужно, когда терминал в режиме прохода по карте шлёт employeeNoString как
    длинный хеш (например SHA-256) вместо обычного короткого числового ID.
    Менеджер один раз указывает, какому сотруднику принадлежит хеш, дальше
    JSON-импорт подставляет его сам вместо того, чтобы пропускать событие.
    """

    __tablename__ = "attendance_card_mappings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Хеш, который прислал терминал в employeeNoString (до 128 симв. - sha256/512 hex)
    hashed_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    faceid_employee_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
