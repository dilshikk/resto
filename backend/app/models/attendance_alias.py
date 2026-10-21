from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import datetime


class AttendanceIdAlias(Base):
    """Соответствие зашифрованного терминалом ID сотрудника настоящему ID в базе FaceID.

    Терминал может отдавать employeeNoString в виде хэша. Соответствие определяется
    при импорте JSON по совпадению отметок (дата, минута, вход/выход) с уже имеющимися
    в базе и запоминается здесь, чтобы следующие импорты узнавали сотрудника сразу.
    """
    __tablename__ = "attendance_id_aliases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    faceid_employee_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
