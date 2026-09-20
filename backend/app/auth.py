import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.employee import Employee, EmployeeAccount
from app.models.user import User
from app.models.role import Role
from app.models.revoked_token import RevokedToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access", "jti": uuid.uuid4().hex})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": uuid.uuid4().hex})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_pre_auth_token(user_id: int) -> str:
    """
    Short-lived (5 min) single-purpose token issued when a user with 2FA
    enabled provides correct credentials.  It can ONLY be exchanged at
    POST /auth/2fa/verify — it is not a valid access token and will be
    rejected by get_current_user / get_current_web_user.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    payload = {
        "sub": str(user_id),
        "type": "pre_auth",
        "exp": expire,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_pre_auth_token(token: str) -> dict[str, Any]:
    """Decode and validate a pre-auth token; raise 401 on any problem."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный pre-auth токен")
    if payload.get("type") != "pre_auth" or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный pre-auth токен")
    return payload


async def is_token_revoked(jti: str, db: AsyncSession) -> bool:
    row = (await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))).scalar_one_or_none()
    return row is not None


async def revoke_token(payload: dict[str, Any], db: AsyncSession) -> None:
    """
    Add a decoded token's jti to the denylist so it's rejected on every
    subsequent request even though it hasn't expired yet. Silently does
    nothing if the payload has no jti (e.g. a token minted before this
    denylist existed) or the jti is already revoked.
    """
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return
    existing = (await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))).scalar_one_or_none()
    if existing:
        return
    db.add(RevokedToken(jti=jti, expires_at=datetime.fromtimestamp(exp, tz=timezone.utc)))


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != expected_type or not payload.get("sub"):
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return payload


async def get_current_web_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolve the raw authenticated `User` row from the access token, with no
    requirement that an EmployeeAccount link already exists.

    Use this (instead of get_current_user) for endpoints that a logged-in web
    user must be able to call *before* their account is linked to an employee
    profile — e.g. POST /employees/claim. get_current_user cannot be used
    there because it 403s any user without an existing EmployeeAccount,
    which makes claiming impossible in the first place.
    """
    payload = decode_token(token, "access")
    if payload.get("jti") and await is_token_revoked(payload["jti"], db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия завершена, войдите снова",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось подтвердить учётные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token, "access")
    if payload.get("jti") and await is_token_revoked(payload["jti"], db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия завершена, войдите снова",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(User).where(User.id == int(payload["sub"]))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception

    acc_result = await db.execute(
        select(EmployeeAccount).where(EmployeeAccount.user_id == user.id)
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=403, detail="Профиль сотрудника не привязан")

    emp_result = await db.execute(
        select(Employee).where(Employee.id == account.employee_id)
    )
    employee = emp_result.scalar_one_or_none()
    if not employee or employee.status == "fired":
        raise credentials_exception

    return employee


async def require_manager(employee: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Employee:
    role_result = await db.execute(select(Role).where(Role.id == employee.role_id))
    role = role_result.scalar_one_or_none()
    if not role or role.permission_level < 1:
        raise HTTPException(status_code=403, detail="Требуются права менеджера")
    return employee


async def require_supervisor(employee: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Employee:
    role_result = await db.execute(select(Role).where(Role.id == employee.role_id))
    role = role_result.scalar_one_or_none()
    if not role or role.permission_level < 2:
        raise HTTPException(status_code=403, detail="Требуются права управляющего")
    return employee


async def verify_bot_secret(x_bot_secret: str = Header(...)) -> None:
    """
    Guards every /api/v1/bot/* endpoints. Only the Telegram bot service knows this
    secret (set as BOT_INTERNAL_SECRET on both the backend and the bot). Individual
    bot endpoints additionally trust a telegram_id in the request body/path to
    identify which employee is acting, since the bot has no per-user JWT.
    """
    if x_bot_secret != settings.BOT_INTERNAL_SECRET:
        raise HTTPException(status_code=401, detail="Неверный внутренний секрет")


async def get_employee_by_telegram_id(telegram_id: int, db: AsyncSession) -> Employee:
    result = await db.execute(select(Employee).where(Employee.telegram_id == telegram_id))
    employee = result.scalar_one_or_none()
    if not employee or employee.status != "active":
        raise HTTPException(status_code=404, detail="Профиль не найден или не привязан")
    return employee
