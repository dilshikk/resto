import pyotp

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.auth import (
    verify_password,
    create_access_token,
    create_refresh_token,
    create_pre_auth_token,
    decode_pre_auth_token,
    hash_password,
    get_current_user,
    get_current_web_user,
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
from app.schemas.auth import (
    TokenResponse,
    LoginResponse,
    RefreshRequest,
    LogoutRequest,
    CreateUserRequest,
    TwoFASetupResponse,
    TwoFAConfirmRequest,
    TwoFAVerifyRequest,
    TwoFADisableRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Issuer label shown in authenticator apps (e.g. Google Authenticator).
_APP_NAME = "MADO Checklist"


def _verify_totp(secret: str, code: str) -> bool:
    """Return True if `code` is a valid current TOTP code for `secret`."""
    totp = pyotp.TOTP(secret)
    # valid_window=1 accepts the previous and next 30-second window to tolerate
    # small clock skew between the server and the user's device.
    return totp.verify(code, valid_window=1)


@router.post("/login", response_model=LoginResponse)
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

    # If 2FA is enabled the client must complete a second step before receiving
    # real tokens.  We issue a short-lived pre-auth token instead so there is
    # nothing useful an attacker can do with stolen credentials alone.
    if user.is_2fa_enabled and user.totp_secret:
        pre_auth_token = create_pre_auth_token(user.id)
        return LoginResponse(requires_2fa=True, pre_auth_token=pre_auth_token)

    # No 2FA — issue tokens immediately.
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return LoginResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/2fa/verify", response_model=TokenResponse)
async def verify_2fa(
    body: TwoFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a pre-auth token + valid TOTP code for a full access/refresh pair.

    Called after POST /auth/login returns requires_2fa=True.
    """
    payload = decode_pre_auth_token(body.pre_auth_token)
    user = (await db.execute(select(User).where(User.id == int(payload["sub"])))).scalar_one_or_none()
    if not user or not user.is_2fa_enabled or not user.totp_secret:
        raise HTTPException(status_code=401, detail="Недействительный pre-auth токен")

    if not _verify_totp(user.totp_secret, body.code.strip()):
        raise HTTPException(status_code=400, detail="Неверный код аутентификатора")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a new TOTP secret for the authenticated user and return the
    otpauth:// URI for QR display.  The secret is stored but 2FA is NOT yet
    enabled — the user must confirm with POST /auth/2fa/confirm first.
    """
    if current_user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA уже включена")

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.email, issuer_name=_APP_NAME)

    current_user.totp_secret = secret
    await db.commit()

    return TwoFASetupResponse(otp_auth_uri=uri, secret=secret)


@router.post("/2fa/confirm")
async def confirm_2fa(
    body: TwoFAConfirmRequest,
    current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify the first code from the authenticator app to prove the user has
    successfully scanned the QR and enable 2FA on the account.
    """
    if current_user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA уже включена")
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Сначала вызовите POST /auth/2fa/setup")

    if not _verify_totp(current_user.totp_secret, body.code.strip()):
        raise HTTPException(status_code=400, detail="Неверный код. Убедитесь, что время устройства верно")

    current_user.is_2fa_enabled = True
    await db.commit()
    return {"ok": True, "message": "2FA успешно включена"}


@router.post("/2fa/disable")
async def disable_2fa(
    body: TwoFADisableRequest,
    current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Disable 2FA after confirming possession of the authenticator device.
    Requires the current TOTP code so an attacker who steals an active session
    cannot silently turn off 2FA without the physical device.
    """
    if not current_user.is_2fa_enabled or not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA не включена")

    if not _verify_totp(current_user.totp_secret, body.code.strip()):
        raise HTTPException(status_code=400, detail="Неверный код аутентификатора")

    current_user.is_2fa_enabled = False
    current_user.totp_secret = None
    await db.commit()
    return {"ok": True, "message": "2FA отключена"}


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
