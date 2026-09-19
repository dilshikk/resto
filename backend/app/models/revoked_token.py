from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import datetime


class RevokedToken(Base):
    """
    Denylist of JWT ids (jti) that have been explicitly revoked, e.g. via
    POST /auth/logout. Every access/refresh token now carries a unique jti
    claim; a token is rejected if its jti shows up here, regardless of
    whether it has otherwise not yet expired.

    expires_at mirrors the token's own `exp` claim, so rows for tokens that
    would have expired naturally can be purged without ever needing a
    scheduled cleanup job — see revoke_token() in app.auth.
    """
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
