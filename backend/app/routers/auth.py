from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.auth import (
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_password,
    get_current_user,
    decode_token,
    is_token_revoked,
    revoke_token,
    oauth2_scheme,
)
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.employee import Employee, EmployeeAccount
from app.models.role import Role
from app.schemas.auth import TokenResponse, RefreshRequest, LogoutRequest, CreateUserRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token, "refresh")
    if payload.get("jti") and await is_token_revoked(payload["jti"], db):
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Rotate: the old refresh token must not be usable again once a new pair
    # has been issued from it.
    await revoke_token(payload, db)

    access_token = create_access_token({"sub": str(user.id)})
    new_refresh = create_refresh_token({"sub": str(user.id)})
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


@router.post("/logout")
async def logout(
    body: LogoutRequest | None = None,
    token: str = Depends(oauth2_scheme),
    _: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Actually end the session: revoke the access token used to call this
    endpoint (so it can't be replayed for the rest of its lifetime) and, if
    the client sends its refresh token, revoke that too (so it can't be used
    to mint fresh access tokens after logout).
    """
    access_payload = decode_token(token, "access")
    await revoke_token(access_payload, db)

    if body and body.refresh_token:
        try:
            refresh_payload = decode_token(body.refresh_token, "refresh")
            await revoke_token(refresh_payload, db)
        except HTTPException:
            # An already-invalid/expired refresh token needs no revocation.
            pass

    await db.commit()
    return {"ok": True}


@router.post("/create-user", include_in_schema=False)
async def create_user_internal(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
):
    """Создаёт веб-пользователя и привязывает его к сотруднику. Только при пустой БД.

    Принимает данные в теле запроса (JSON), а не в query-параметрах, чтобы
    пароль не попадал в URL (логи сервера, история браузера, referrer).
    """
    count_result = await db.execute(select(func.count()).select_from(User))
    count = count_result.scalar_one()
    if count > 0:
        raise HTTPException(status_code=403, detail="Users already exist")

    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    await db.flush()

    account = EmployeeAccount(employee_id=body.employee_id, user_id=user.id)
    db.add(account)
    await db.commit()
    return {"user_id": user.id}
