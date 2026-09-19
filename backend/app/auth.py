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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


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
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int | None = payload.get("sub")
        if user_id is None or payload.get("type") != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int | None = payload.get("sub")
        if user_id is None or payload.get("type") != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception

    acc_result = await db.execute(
        select(EmployeeAccount).where(EmployeeAccount.user_id == user.id)
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=403, detail="No employee profile linked")

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
        raise HTTPException(status_code=403, detail="Manager access required")
    return employee


async def require_supervisor(employee: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Employee:
    role_result = await db.execute(select(Role).where(Role.id == employee.role_id))
    role = role_result.scalar_one_or_none()
    if not role or role.permission_level < 2:
        raise HTTPException(status_code=403, detail="Supervisor access required")
    return employee


async def verify_bot_secret(x_bot_secret: str = Header(...)) -> None:
    """
    Guards every /api/v1/bot/* endpoints. Only the Telegram bot service knows this
    secret (set as BOT_INTERNAL_SECRET on both the backend and the bot). Individual
    bot endpoints additionally trust a telegram_id in the request body/path to
    identify which employee is acting, since the bot has no per-user JWT.
    """
    if x_bot_secret != settings.BOT_INTERNAL_SECRET:
        raise HTTPException(status_code=401, detail="Invalid bot secret")


async def get_employee_by_telegram_id(telegram_id: int, db: AsyncSession) -> Employee:
    result = await db.execute(select(Employee).where(Employee.telegram_id == telegram_id))
    employee = result.scalar_one_or_none()
    if not employee or employee.status != "active":
        raise HTTPException(status_code=404, detail="Профиль не найден или не привязан")
    return employee
