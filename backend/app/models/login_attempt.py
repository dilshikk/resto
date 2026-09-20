import datetime

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LoginAttempt(Base):
    """
    Persistent per-email brute-force counter.

    Replaces the former in-process LoginAttemptTracker so that lockout
    state survives process restarts and is shared across all replicas.

    Rows are cheap to write (upsert on PK) and are periodically purged by
    run_login_attempt_cleanup_loop once the lockout window has passed.
    """

    __tablename__ = "login_attempts"

    # Normalised to lower-case before storage (matches auth router behaviour).
    email: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Consecutive wrong-password count since the last successful login.
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Non-null only while the account is locked out.
    locked_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamp of the most recent failure; used by the cleanup task to
    # decide when a row can safely be deleted.
    last_failure: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
